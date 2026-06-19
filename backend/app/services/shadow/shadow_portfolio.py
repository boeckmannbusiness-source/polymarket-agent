from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.execution import ExecutionResult
from app.domain.portfolio import PortfolioSnapshot


class ShadowPortfolio:
    def apply(self, result: ExecutionResult, current: PortfolioSnapshot | None = None) -> PortfolioSnapshot:
        portfolio_id = current.portfolio_id if current else str(uuid4())
        positions = dict(current.positions) if current and current.positions else {}
        cash_balance = current.cash_balance if current else Decimal("100000")
        realized_pnl = current.realized_pnl if current else Decimal("0")
        unrealized_pnl = current.unrealized_pnl if current else Decimal("0")
        exposure = current.exposure if current else Decimal("0")

        total_spent = Decimal("0")
        if result.fills:
            for fill in result.fills:
                instr = fill.fill_id
                qty_change = fill.size
                cost = qty_change * fill.price
                total_spent += cost
                if instr in positions:
                    positions[instr] += qty_change
                else:
                    positions[instr] = qty_change
                cash_balance -= cost
                if fill.fee:
                    cash_balance -= fill.fee

        exposure = sum(
            positions[k] * next(
                (f.price for f in (result.fills or []) if f.fill_id == k),
                Decimal("0"),
            )
            for k in positions
        )

        if result.fees is not None:
            cash_balance -= result.fees

        if result.status in ("filled", "complete"):
            trade_pnl = (result.average_price or Decimal("0")) * (result.quantity_executed or Decimal("0")) - total_spent
            realized_pnl += trade_pnl

        return PortfolioSnapshot(
            portfolio_id=portfolio_id,
            timestamp=datetime.now(timezone.utc),
            positions=positions,
            cash_balance=cash_balance,
            exposure=exposure,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            metadata={"execution_id": result.execution_id, "status": result.status},
        )
