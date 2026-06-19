from datetime import datetime, timezone
from decimal import Decimal

from app.domain.execution import ExecutionResult
from app.domain.portfolio import PortfolioSnapshot, PositionProjection
from app.domain.execution import FillInfo


class PortfolioProjector:
    def project(self, result: ExecutionResult, current: PortfolioSnapshot | None = None) -> list[PositionProjection]:
        projections: list[PositionProjection] = []
        if not result.fills:
            return projections

        for fill in result.fills:
            instr = fill.fill_id
            qty_before = Decimal("0")
            qty_after = fill.size
            avg_price_before = Decimal("0")
            avg_price_after = fill.price
            estimated_fees = fill.fee or Decimal("0")

            if current and current.positions:
                existing_qty = current.positions.get(instr, Decimal("0"))
                qty_before = existing_qty
                qty_after = existing_qty + fill.size

            estimated_pnl = (fill.price - avg_price_before) * qty_after if avg_price_before else Decimal("0")

            projections.append(PositionProjection(
                instrument=instr,
                quantity_before=qty_before,
                quantity_after=qty_after,
                avg_price_before=avg_price_before,
                avg_price_after=avg_price_after,
                estimated_pnl=estimated_pnl,
                estimated_fees=estimated_fees,
            ))

        return projections
