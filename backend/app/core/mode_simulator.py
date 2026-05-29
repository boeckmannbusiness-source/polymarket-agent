import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from app.core.system_mode import SystemMode, _MODE_ORDER, ModeManager
from app.core.mode_context import MODE_CONTEXTS, get_hold_time, adjust_metric


# ── Recording ─────────────────────────────────────────

_RECORDING_ENABLED: bool = False
_SNAPSHOT_BUFFER: deque["MetricSnapshot"] = deque(maxlen=10000)
_FILE_WRITER: Any = None


@dataclass
class MetricSnapshot:
    timestamp: float
    raw_metrics: dict[str, float]
    adjusted_metrics: dict[str, float]
    sensitivity: float
    mode_before: str
    mode_proposed: str
    mode_after: str
    reason: str


def enable_recording(file_path: str | None = None):
    global _RECORDING_ENABLED, _FILE_WRITER
    _RECORDING_ENABLED = True
    if file_path:
        _FILE_WRITER = open(file_path, "a", encoding="utf-8")


def disable_recording():
    global _RECORDING_ENABLED, _FILE_WRITER
    _RECORDING_ENABLED = False
    if _FILE_WRITER:
        _FILE_WRITER.close()
        _FILE_WRITER = None


def record_snapshot(
    raw: dict,
    adjusted: dict,
    sensitivity: float,
    mode_before: str,
    mode_proposed: str,
    mode_after: str,
    reason: str,
):
    if not _RECORDING_ENABLED:
        return
    snap = MetricSnapshot(
        timestamp=time.monotonic(),
        raw_metrics=raw,
        adjusted_metrics=adjusted,
        sensitivity=sensitivity,
        mode_before=mode_before,
        mode_proposed=mode_proposed,
        mode_after=mode_after,
        reason=reason,
    )
    _SNAPSHOT_BUFFER.append(snap)
    if _FILE_WRITER:
        d = asdict(snap)
        d["timestamp_iso"] = datetime.now(timezone.utc).isoformat()
        _FILE_WRITER.write(json.dumps(d) + "\n")
        _FILE_WRITER.flush()


def get_recorded_snapshots() -> list[MetricSnapshot]:
    return list(_SNAPSHOT_BUFFER)


def clear_recording():
    _SNAPSHOT_BUFFER.clear()


# ── Side-effect-free evaluator copy ───────────────────

class SimulatedModeManager(ModeManager):
    """ModeManager subclass that suppresses all persistence side effects."""

    async def _transition(self, target: SystemMode, reason: str, trigger_metrics: dict | None = None):
        previous = self._mode
        self._mode = target
        self._reason = reason
        self._last_transition_time = time.monotonic()
        self._entry_time[target] = time.monotonic()

    async def _persist(self, mode: SystemMode, reason: str):
        pass

    async def record_transition_db(self, **kwargs):
        pass

    async def set_manual_override(self, **kwargs):
        pass


# ── Replay Engine ─────────────────────────────────

@dataclass
class SimulatedTransition:
    index: int
    sim_time: float
    from_mode: str
    to_mode: str
    reason: str
    trigger_metrics: dict


@dataclass
class OscillationEvent:
    window_start: float
    window_end: float
    flip_count: int
    modes_visited: list[str]
    chain_depth: int


@dataclass
class SimulationReport:
    total_steps: int
    transitions: list[SimulatedTransition]
    oscillation_events: list[OscillationEvent]
    time_in_mode: dict[str, float]
    total_duration: float
    transition_count: int
    flip_count_total: int
    max_escalation_chain: int
    mode_proposed_but_rejected: int
    rejected_by_hysteresis: int
    rejected_by_hold: int

    def summary(self) -> dict:
        return {
            "total_steps": self.total_steps,
            "transitions": self.transition_count,
            "total_duration_s": round(self.total_duration, 1),
            "flip_count": self.flip_count_total,
            "max_escalation_chain": self.max_escalation_chain,
            "time_in_mode_pct": {
                m: round((t / max(self.total_duration, 1)) * 100, 1)
                for m, t in sorted(self.time_in_mode.items())
            },
            "oscillation_events": len(self.oscillation_events),
            "mode_proposed_but_rejected": self.mode_proposed_but_rejected,
            "rejected_by_hysteresis": self.rejected_by_hysteresis,
            "rejected_by_hold": self.rejected_by_hold,
        }


def _trans_dir(t):
    f = _MODE_ORDER.index(SystemMode(t.from_mode))
    to = _MODE_ORDER.index(SystemMode(t.to_mode))
    return to - f


def _detect_oscillations(
    transitions: list[SimulatedTransition],
    window_seconds: float = 120.0,
) -> list[OscillationEvent]:
    if len(transitions) < 2:
        return []

    events: list[OscillationEvent] = []
    n = len(transitions)

    for i in range(n):
        window_end = transitions[i].sim_time + window_seconds
        flips = 0
        chain_depth = 0
        modes_seen: list[str] = []
        prev_dir: int = 0

        for j in range(i, n):
            if transitions[j].sim_time > window_end:
                break
            t = transitions[j]
            if t.from_mode not in modes_seen:
                modes_seen.append(t.from_mode)
            if t.to_mode not in modes_seen:
                modes_seen.append(t.to_mode)

            dir = _trans_dir(t)
            if dir != 0:
                if prev_dir != 0 and dir != prev_dir:
                    flips += 1
                prev_dir = dir
                if dir > 0:
                    chain_depth += 1
                else:
                    chain_depth = 0

        if flips >= 2 or (flips >= 1 and chain_depth >= 2):
            events.append(OscillationEvent(
                window_start=transitions[i].sim_time,
                window_end=transitions[i].sim_time + window_seconds,
                flip_count=flips,
                modes_visited=modes_seen,
                chain_depth=chain_depth,
            ))

    return events


def run_simulation(
    snapshots: list[MetricSnapshot],
    start_mode: str = "normal",
) -> SimulationReport:
    mgr = SimulatedModeManager()
    mgr._mode = SystemMode(start_mode)
    mgr._reason = start_mode
    mgr._entry_time[start_mode] = 0.0

    transitions: list[SimulatedTransition] = []
    now = 0.0
    step_interval = 15.0

    rejected_hysteresis = 0
    rejected_hold = 0
    proposed_count = 0

    for idx, snap in enumerate(snapshots):
        now = (idx + 1) * step_interval
        mode_before = mgr._mode.value

        proposed = mgr._compute_mode_from_metrics(snap.raw_metrics)

        if proposed != mgr._mode:
            proposed_count += 1

        target = proposed
        target_idx = _MODE_ORDER.index(target)
        current_idx = _MODE_ORDER.index(SystemMode(mgr._mode.value))

        if target != mgr._mode:
            if target_idx > current_idx:
                if target != SystemMode.EMERGENCY_STOP:
                    elapsed = now - mgr._entry_time.get(mgr._mode, 0)
                    hold = get_hold_time(mgr._mode.value)
                    if elapsed < hold:
                        rejected_hold += 1
                        continue
            else:
                if mgr._mode in mgr._entry_time:
                    elapsed = now - mgr._entry_time[mgr._mode]
                    min_dur = mgr._minimum_duration.get(mgr._mode, 60.0)
                    if elapsed < min_dur:
                        rejected_hysteresis += 1
                        continue

                downgrade_map = {
                    SystemMode.PROTECTED: SystemMode.DEGRADED,
                    SystemMode.DEGRADED: SystemMode.NORMAL,
                }
                if mgr._mode in downgrade_map and target != downgrade_map[mgr._mode]:
                    target = downgrade_map[mgr._mode]

        if target != mgr._mode:
            reason = mgr._reason
            transitions.append(SimulatedTransition(
                index=idx,
                sim_time=now,
                from_mode=mode_before,
                to_mode=target.value,
                reason=reason,
                trigger_metrics=snap.raw_metrics,
            ))
            mgr._mode = target
            mgr._reason = reason
            mgr._last_transition_time = now
            mgr._entry_time[target] = now

    time_in_mode: dict[str, float] = {}
    if transitions:
        prev_time = 0.0
        prev_mode = start_mode
        for t in transitions:
            dur = t.sim_time - prev_time
            time_in_mode[prev_mode] = time_in_mode.get(prev_mode, 0) + dur
            prev_time = t.sim_time
            prev_mode = t.to_mode
        time_in_mode[prev_mode] = time_in_mode.get(prev_mode, 0) + (now - prev_time)
    else:
        time_in_mode[start_mode] = now

    oscillations = _detect_oscillations(transitions)

    flip_count = 0
    for i in range(1, len(transitions)):
        prev_dir = _trans_dir(transitions[i - 1])
        curr_dir = _trans_dir(transitions[i])
        if prev_dir * curr_dir < 0:
            flip_count += 1

    max_chain = 0
    current_chain = 0
    for t in transitions:
        if _trans_dir(t) > 0:
            current_chain += 1
            max_chain = max(max_chain, current_chain)
        else:
            current_chain = 0

    return SimulationReport(
        total_steps=len(snapshots),
        transitions=transitions,
        oscillation_events=oscillations,
        time_in_mode=time_in_mode,
        total_duration=now,
        transition_count=len(transitions),
        flip_count_total=flip_count,
        max_escalation_chain=max_chain,
        mode_proposed_but_rejected=proposed_count - len(transitions),
        rejected_by_hysteresis=rejected_hysteresis,
        rejected_by_hold=rejected_hold,
    )


# ── Synthetic stress generators ──────────────────────

def synthetic_db_spike(
    steps: int = 100,
    base_pct: float = 30.0,
    spike_to: float = 92.0,
    spike_at: int = 30,
    spike_duration: int = 10,
) -> list[MetricSnapshot]:
    now = time.monotonic()
    snapshots: list[MetricSnapshot] = []
    for i in range(steps):
        if spike_at <= i < spike_at + spike_duration:
            pct = spike_to
        else:
            pct = base_pct + (spike_to - base_pct) * max(0, 1 - abs(i - spike_at - spike_duration // 2) / (spike_duration // 2)) * 0.1
        raw = {
            "db_pool_utilization_pct": min(100, pct),
            "redis_memory_pct": 40.0,
            "redis_max_pending": 50.0,
            "reconnect_storm": 0.0,
            "circuit_breaker_open": False,
            "drawdown": 0.02,
            "stream_pressure_ratio": 0.3,
            "db_ok": True,
        }
        snapshots.append(MetricSnapshot(
            timestamp=now + i * 15,
            raw_metrics=raw,
            adjusted_metrics=raw,
            sensitivity=1.0,
            mode_before="normal",
            mode_proposed="normal",
            mode_after="normal",
            reason="synthetic",
        ))
    return snapshots


def synthetic_oscillation(
    cycles: int = 5,
    steps_per_cycle: int = 20,
    seed: int | None = None,
) -> list[MetricSnapshot]:
    import random as _random
    if seed is not None:
        _random.seed(seed)
    now = time.monotonic()
    snapshots: list[MetricSnapshot] = []
    for cycle in range(cycles):
        for i in range(steps_per_cycle):
            phase = i / steps_per_cycle
            jitter = (_random.random() - 0.5) * 5 if seed is not None else 0
            db_pct = 50 + 45 * (1 if phase < 0.3 else 0 if phase < 0.6 else 0.8) + jitter
            raw = {
                "db_pool_utilization_pct": db_pct,
                "redis_memory_pct": 40.0 + 40 * phase,
                "redis_max_pending": 100 + 400 * phase,
                "reconnect_storm": 0.0,
                "circuit_breaker_open": False,
                "drawdown": 0.02,
                "stream_pressure_ratio": 0.3 + 0.5 * phase,
                "db_ok": True,
            }
            snapshots.append(MetricSnapshot(
                timestamp=now + (cycle * steps_per_cycle + i) * 15,
                raw_metrics=raw,
                adjusted_metrics=raw,
                sensitivity=1.0,
                mode_before="normal",
                mode_proposed="normal",
                mode_after="normal",
                reason="synthetic_oscillation",
            ))
    return snapshots
