# Runtime Ownership Report

**Date:** 2026-07-01
**Method:** Static code-path tracing from ingestion through persistence

---

## What Object Enters Execution?

**Answer: A) Prediction decisions** (wrapped in a venue-neutral `ExecutionIntent`)

---

## Exact Code Path

### Step 1: Signal Generation (Polymarket-owned)

```
backend/app/strategies/whale_following.py

class WhaleFollowingStrategy(BaseStrategy):
    async def generate_signal(self, market_state: dict) -> StructuredSignal:
        return StructuredSignal(
            strategy="whale_following",
            signal="BUY_YES",                     # ← prediction market decision
            confidence=0.75,
            market_id=market_state["market_id"],   # ← Polymarket identity
            market_condition_id=market_state["condition_id"],  # ← Polymarket on-chain ID
            ...
        )
```

The `StructuredSignal` schema (`strategies/signal.py`):
- `signal`: Literal["BUY_YES", "BUY_NO", "NEUTRAL"] — prediction market binary outcome
- `market_id`: UUID — Polymarket market internal ID
- `market_condition_id`: str — Polymarket CTF condition ID

### Step 2: Signal Persistence (Polymarket-owned)

```
backend/app/services/signal_service.py

class SignalService:
    async def create_signal(self, market_id: UUID, signal_type: str, direction: str, ...) -> Signal:
        signal = Signal(
            market_id=market_id,    # ← Polymarket UUID
            signal_type=signal_type,
            direction=direction,    # ← "BUY_YES" / "BUY_NO"
            ...
        )
```

The `direction` field stores Polymarket outcome semantics (`BUY_YES`, `BUY_NO`), not token swap direction.

### Step 3: Execution Intent Construction (Neutral adapter layer)

```
backend/app/services/execution/intent_factory.py

class ExecutionIntentFactory:
    @staticmethod
    def create_from_trade(trade: Trade, engine_type: str, ...) -> ExecutionIntent:
        asset_in = trade.market_id          # ← Polymarket UUID as asset identifier
        instrument = Instrument(
            venue=engine_type,              # ← execution venue ("paper" / "live_jupiter")
            symbol=str(trade.market_id),    # ← Polymarket UUID
            asset_identifier=asset_in,      # ← Polymarket UUID
            quote_asset="USDC",
        )
        intent = ExecutionIntent(
            instrument=instrument,
            side=trade.side,               # ← "buy" / "sell"
            strategy_id=str(trade.agent_id),
            metadata={"trade_id": str(trade.id)},
        )
        # Persistence compatibility — Polymarket concepts
        intent.compat_trade = trade
        intent.compat_outcome = trade.outcome  # ← YES/NO prediction market outcome
```

### Step 4: Planner — Conversion to Solana-native (the switch)

```
backend/app/services/execution/execution_service.py (line 556-566)

# Inside create_trade_execution():
constraints = ExecutionConstraints(max_slippage_bps=slippage)
plan = await self._planner.plan(
    instrument=intent.instrument,         # ← Instrument(symbol=market_id)
    amount_in=intent.quantity,
    side=intent.side,                     # ← "buy"/"sell"
    constraints=constraints,
    asset_resolution=asset_res,
)
intent.transaction_plan = plan            # ← TransactionPlan (Solana-native)
```

The `Planner.plan()` (`services/planning/planner.py`) creates a `TransactionPlan` with:
- `Quote` (instrument, amount, price, slippage)
- `Route` (venue, hops, route_type)
- `TransactionInstruction` (SWAP/TRANSFER — Solana instruction types)
- `ExecutionConstraints` (max_slippage, latency)

This is the **switch point**: Polymarket decision → Solana transaction plan.

### Step 5: Execution — Simulated Solana swap

```
backend/app/exchanges/adapters/jupiter_execution_adapter.py

class JupiterExecutionAdapter:
    async def execute(self, plan: TransactionPlan, seed=None) -> ExecutionResult:
        return await self._simulator.simulate(plan, adapter_name="jupiter_simulated", seed=seed)
```

The simulator produces fills, latency, fees — all simulated. No real Solana interaction.

### Step 6: Evidence Recording — Polymarket-owned again

```
backend/app/services/execution/execution_service.py (line 704-767)

async def _record_shadow_decision(self, result, intent, plan, trace_id, authorization):
    market_id = intent.instrument.symbol if intent and intent.instrument else "unknown"
    strategy_id = intent.strategy_id if intent else "unknown"
    signal_id = ...
    confidence = ...      # prediction confidence
    predicted_prob = ...  # predicted probability of outcome
    expected_ev = ...     # expected value based on prediction

    await ledger.record_decision(
        market_id=market_id,                    # ← Polymarket identity
        signal_id=signal_id,
        strategy_id=strategy_id,
        confidence=confidence,                  # ← prediction confidence
        decision=intent.side,
        ...
    )
```

### Step 7: Shadow Ledger — Full Polymarket context

```
backend/app/services/shadow/shadow_ledger.py

async def record_decision(self, market_id, signal_id, strategy_id, confidence, decision, ...):
    log = ShadowDecisionLog(
        market_id=market_id,          # ← Polymarket identity
        strategy_id=strategy_id,
        signal_id=signal_id,
        confidence=confidence,        # ← prediction confidence
        decision=decision,            # ← "buy"/"sell" (of prediction outcome)
        simulated_size=...,
        simulated_entry_price=...,
        expected_ev=...,              # ← expected value of prediction
        ...
    )
```

---

## Summary

```
Polymarket Decision ──► Neutral Intent ──► Solana Plan ──► Simulated Execution ──► Polymarket Evidence
      (BUY_YES/NO)     (Instrument)      (TransactionPlan)  (ExecutionResult)    (ShadowDecisionLog)
           │                  │                  │                  │                    │
      market_id          symbol=         Route, Quote        simulated fills      market_id
      condition_id       market_id       instructions        latency             confidence
      direction                         slippage            fees                win/loss (prediction)
                                                                                realized_ev
```

**What actually enters execution:** A `Signal` containing a **prediction decision** (BUY_YES/BUY_NO for a Polymarket market outcome). This is converted to a venue-neutral `ExecutionIntent`, then amplified into a `TransactionPlan` via Jupiter routing. But the underlying business intent is always a prediction market decision — the Solana execution is an implementation detail applied to a Polymarket-rooted trade idea.

The system does NOT generate token swap intents ("swap X SOL for Y USDC on Orca"). It generates prediction market intents ("buy YES on market X") and then routes them through Solana infrastructure because Polymarket CLOB execution is disabled.
