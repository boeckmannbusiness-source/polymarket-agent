# Promotion Target Report

**Date:** 2026-07-01
**Method:** Trace what metrics drive promotion decisions

---

## There Are Two Parallel Promotion Paths

### Path A: Shadow Readiness Pipeline (DOMINANT — active promotion gate)

This is the **newer, more comprehensive** pipeline that determines whether a strategy graduates from shadow to sandbox/live.

**Files:**
- `services/shadow/promotion_readiness_service.py`
- `services/shadow/promotion_observation_service.py`
- `services/shadow/promotion_audit_service.py`
- `services/shadow/evidence_engine.py`
- `services/shadow/scorecard_engine.py`
- `services/shadow/readiness_evaluator.py`
- `services/shadow/outcome_engine.py`
- `services/shadow/outcome_evaluator.py`

**Metrics used for promotion readiness (all gates must pass):**

| Gate | Metric | Threshold | Domain |
|------|--------|-----------|--------|
| Decision volume | `decision_count` | >= 500 | Prediction outcome |
| Replay parity | `replay_parity` | >= 0.95 | Determinism of predictions |
| Realized EV | `realized_ev` | > 0 | Prediction PnL |
| Brier Score | `brier_score` | <= 0.25 | Prediction calibration |
| Certification violations | count | == 0 | Governance |
| Data origin | `data_origin` | == "shadow" | Authenticity |

**All six gates are derived from `ShadowDecisionLog` records, which store prediction market outcomes.** The `OutcomeReceipt` (domain/shadow/models.py) records:
- `realized_ev` — PnL from prediction being right/wrong
- `win_loss` — did the binary outcome resolve correctly?
- `calibration_delta` — how well-calibrated was the probability estimate?
- `prediction_error` — absolute error in prediction

**There is zero consideration of:**
- Slippage efficiency
- Route optimization quality
- Fill latency
- Token alpha
- Pool depth impact

### Path B: Shadow Promotion Service (LEGACY — still exists)

**Files:**
- `services/shadow/shadow_promotion_service.py`

**Metrics:**

| Metric | Domain |
|--------|--------|
| `trade_count` (closed positions) | Trade execution |
| `win_rate` | Trade execution |
| `sharpe_ratio` | Portfolio performance |
| `max_drawdown` | Portfolio risk |
| `alpha` (vs benchmark) | Portfolio returns |
| `expectancy` | Trade PnL |

This path **does** evaluate token swap performance, not prediction accuracy. However:
- It only sees `ShadowPosition` records from the shadow portfolio projector, which are derived from execution results
- This path is used for tier assignment (`SHADOW → PAPER → LIVE`) but is overshadowed by Path A's readiness pipeline for the actual sandbox promotion decision
- The `PromotionReadinessService` (Path A) is what gates sandbox entry

---

## Evidence: What Counts as "Evidence"

`EvidenceEngine` (`services/shadow/evidence_engine.py`) produces `PromotionEvidenceSnapshot`:

| Field | Source | Domain |
|-------|--------|--------|
| `decision_count` | ShadowDecisionLog decision_status=RESOLVED | Prediction |
| `replay_parity` | ShadowDecisionLog replay_match ratio | Prediction |
| `realized_ev` | ShadowDecisionLog realized_ev | Prediction |
| `brier_score` | ShadowDecisionLog predicted_probability + actual_ev | Prediction |
| `certification_violations` | ShadowDecisionLog certification_violation | Governance |
| `data_origin` | Existence check on ShadowDecisionLog | Source authenticity |
| `decision_ids` | Full list of resolved decision UUIDs | Prediction |
| `resolution_range` | Min/max outcome_timestamp | Prediction |
| `source_tables` | ["shadow_decision_log"] | Lineage |
| `reconstruction_hash` | SHA256 of decisions + range + tables | Integrity |
| `snapshot_hash` | SHA256 of all fields | Integrity |

**All evidence metrics derive from prediction outcomes.** None derive from Solana-native execution properties.

---

## Outcome Evaluation

`OutcomeClosureEngine` (`services/shadow/outcome_engine.py`) determines:
- `realized_ev = size * (resolution_price - entry_price)` — price difference on resolved prediction market
- `win_loss = realized_ev > 0` — was the prediction correct?
- `prediction_error = |confidence - outcome_val|` — how wrong was the probability estimate?
- `calibration_delta = predicted_probability - outcome_val` — confidence bias

`OutcomeEvaluator` (`services/shadow/outcome_evaluator.py`) aggregates:
- `win_rate` = prediction accuracy across all decisions
- `brier_score` = mean squared prediction error
- `overconfidence_index` = calibration bias
- `replay_parity` = deterministic reproducibility

**All metrics are prediction-centric. Token swap performance is not evaluated.**

---

## Classification

```
PROMOTION_TARGET = prediction_accuracy
```

| Metric Class | Present in Path A? | Present in Path B? | Primary Driver? |
|-------------|-------------------|-------------------|----------------|
| Prediction accuracy | ✅ (win_rate, Brier, calibration) | ❌ | ✅ YES |
| Execution quality | ❌ | ❌ (no slippage/latency) | ❌ |
| Portfolio growth | ❌ | ✅ (sharpe, drawdown, alpha) | Minimal |
| Token alpha | ❌ | Partial (alpha vs benchmark) | Minimal |

**The system optimizes for prediction accuracy.** A strategy graduates from shadow when it correctly predicts binary outcomes on Polymarket markets. Token swap execution quality (slippage, routing efficiency) is not a promotion factor.

**Implication for migration claim:** Even if execution is routed through Solana/Jupiter, the system's feedback loop evaluates prediction quality — not swap execution quality. Moving execution to Solana does not change what the system optimizes for.
