from dataclasses import dataclass
from typing import Literal


TrimMode = Literal["approximate", "exact"]


@dataclass(frozen=True)
class StreamConfig:
    name: str
    maxlen: int
    trim_mode: TrimMode
    consumer_groups: tuple[str, ...]
    description: str
    phase: Literal["1", "2"] = "1"


class StreamRegistry:
    _streams: dict[str, StreamConfig] = {}

    @classmethod
    def register(cls, config: StreamConfig) -> None:
        cls._streams[config.name] = config

    @classmethod
    def get(cls, name: str) -> StreamConfig | None:
        return cls._streams.get(name)

    @classmethod
    def all(cls) -> dict[str, StreamConfig]:
        return dict(cls._streams)

    @classmethod
    def active_in_phase1(cls) -> list[StreamConfig]:
        return [s for s in cls._streams.values() if s.phase == "1"]

    @classmethod
    def validate_group(cls, stream: str, group: str) -> bool:
        config = cls._streams.get(stream)
        if not config:
            return False
        return group in config.consumer_groups

    @classmethod
    def stream_names(cls) -> list[str]:
        return list(cls._streams.keys())

    @classmethod
    def phase1_stream_names(cls) -> list[str]:
        return [s.name for s in cls._streams.values() if s.phase == "1"]


# ── Stream Definitions ──────────────────────────────────────

StreamRegistry.register(StreamConfig(
    name="market:data",
    maxlen=100_000,
    trim_mode="approximate",
    consumer_groups=("helius_ingester", "smart_wallet_agent", "research_trade_worker", "monitoring"),
    description="Raw swap events from Helius, enriched prices from Birdeye",
    phase="1",
))

StreamRegistry.register(StreamConfig(
    name="wallet:trade",
    maxlen=100_000,
    trim_mode="approximate",
    consumer_groups=("smart_wallet_agent", "research_trade_worker", "monitoring"),
    description="Normalized wallet trade events with research score",
    phase="1",
))

StreamRegistry.register(StreamConfig(
    name="signal:generated",
    maxlen=50_000,
    trim_mode="approximate",
    consumer_groups=("shadow_portfolio_service", "monitoring"),
    description="Trading signals from SmartWalletAgent",
    phase="1",
))

StreamRegistry.register(StreamConfig(
    name="trade:request",
    maxlen=50_000,
    trim_mode="approximate",
    consumer_groups=("monitoring",),
    description="Shadow trade requests (logged only, no consumer in Phase 1)",
    phase="1",
))

StreamRegistry.register(StreamConfig(
    name="shadow:position",
    maxlen=50_000,
    trim_mode="approximate",
    consumer_groups=("monitoring",),
    description="Shadow position lifecycle events (opened, closed)",
    phase="1",
))

StreamRegistry.register(StreamConfig(
    name="agent:event",
    maxlen=50_000,
    trim_mode="approximate",
    consumer_groups=("monitoring_agent", "whale_agent", "signal_agent", "risk_agent", "execution_agent"),
    description="Agent lifecycle and health events (unchanged from existing)",
    phase="1",
))

StreamRegistry.register(StreamConfig(
    name="system:alert",
    maxlen=10_000,
    trim_mode="approximate",
    consumer_groups=("monitoring", "notification"),
    description="System alerts (unchanged from existing)",
    phase="1",
))

StreamRegistry.register(StreamConfig(
    name="solana:trade:detected",
    maxlen=100_000,
    trim_mode="approximate",
    consumer_groups=("smart_wallet_agent", "research_trade_worker", "monitoring"),
    description="Raw Solana trades detected via Helius webhook",
    phase="1",
))

# Phase 2 — deferred
StreamRegistry.register(StreamConfig(
    name="trade:execution",
    maxlen=50_000,
    trim_mode="approximate",
    consumer_groups=("monitoring",),
    description="Live trade execution events — DEFERRED TO PHASE 2",
    phase="2",
))
