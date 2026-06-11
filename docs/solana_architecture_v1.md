# Solana Architecture v1

## Target Architecture

```text
On-chain Events (Helius Webhooks) -> EventBus (market:data)
Market Metrics (Birdeye/DexScreener) -> EventBus (market:data)
        ↓
WhaleAgent (Solana Wallet Tracking) -> EventBus (wallet:trade)
        ↓
SignalAgent (Ensemble Strategies) -> EventBus (signal:generated)
        ↓
RiskAgent (Micro-Capital Limits) -> EventBus (trade:request)
        ↓
ExecutionAgent (Jupiter Adapter) -> EventBus (trade:execution)
```

## Part 5 — Position Model Redesign (TokenPosition)

```python
class TokenPosition(Base):
    __tablename__ = "token_positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    mint_address: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 9))
    entry_price_usd: Mapped[Decimal] = mapped_column(Numeric(24, 9))
    current_price_usd: Mapped[Decimal] = mapped_column(Numeric(24, 9))
    realized_pnl_usd: Mapped[Decimal] = mapped_column(Numeric(24, 9), default=0)
    unrealized_pnl_usd: Mapped[Decimal] = mapped_column(Numeric(24, 9))
    status: Mapped[str] = mapped_column(String(16)) # open, closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

## Part 6 — Risk Model (Micro-Capital Risk Profile v1)

**Target Capital: 25€–100€**

| Metric | SOL / Large Cap | Mid Cap | Memecoin / New |
| :--- | :--- | :--- | :--- |
| **Max Position** | 10€ | 5€ | 2€ |
| **Portfolio Exposure**| 30% | 20% | 10% |
| **Stop Loss** | 5% | 10% | 25% |
| **Take Profit** | 10% | 25% | 100%+ |

---

## Part 7 — Migration Complexity Matrix

| Component | Status | Action | Effort | Risk | Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EventBus** | KEEP | No change. | 0h | Low | None |
| **PostgreSQL** | REFACTOR | Add `TokenPosition` tables. | 4h | Low | None |
| **PolymarketIngester**| DELETE | Remove entirely. | 1h | Low | None |
| **HeliusIngester** | REPLACE | New webhook listener. | 8h | Medium | Helius API |
| **WhaleAgent** | REFACTOR | ROI/clustering logic. | 12h | High | Helius/Birdeye |
| **SignalAgent** | REFACTOR | Feature vector pivot. | 10h | High | Data Layer |
| **RiskAgent** | REFACTOR | Volatility scaling. | 6h | Medium | None |
| **ExecutionAgent** | REPLACE | Jupiter SDK adapter. | 16h | High | Jupiter API |
| **SafetyGate** | KEEP | Threshold tuning. | 2h | Low | None |
