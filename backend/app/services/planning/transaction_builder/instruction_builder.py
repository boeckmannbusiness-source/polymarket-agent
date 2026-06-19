from decimal import Decimal

from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.transaction_instruction import TransactionInstruction


BASE_FEE_LAMPORTS = 5000
HOP_FEE_LAMPORTS = 5000
SPLIT_FEE_MULTIPLIER = 2


class InstructionBuilder:
    """Derives abstract transaction instructions from a Route + Quote.

    NO blockchain-specific encoding.
    NO signing.
    NO execution.
    """

    @staticmethod
    def build_instructions(quote: Quote, route: Route) -> list[TransactionInstruction]:
        route_type = route.route_type
        if route_type == "SPLIT":
            return InstructionBuilder._build_split_instructions(quote, route)
        return InstructionBuilder._build_direct_instructions(quote, route)

    @staticmethod
    def _build_direct_instructions(quote: Quote, route: Route) -> list[TransactionInstruction]:
        return [
            TransactionInstruction(
                instruction_type="SWAP",
                source_asset=quote.instrument.asset_identifier,
                target_asset=quote.instrument.quote_asset,
                amount=quote.amount_in,
                metadata={
                    "hop_index": 0,
                    "venue": route.venue,
                    "expected_out": str(quote.expected_amount_out),
                },
            )
        ]

    @staticmethod
    def _build_split_instructions(quote: Quote, route: Route) -> list[TransactionInstruction]:
        split_meta = route.metadata or {}
        amount_a = Decimal(str(split_meta.get("split_1", str(quote.amount_in / Decimal("2")))))
        amount_b = Decimal(str(split_meta.get("split_2", str(quote.amount_in / Decimal("2")))))

        return [
            TransactionInstruction(
                instruction_type="ROUTE_HOP",
                source_asset=quote.instrument.asset_identifier,
                target_asset=quote.instrument.quote_asset,
                amount=amount_a,
                metadata={"hop_index": 0, "venue": route.venue, "split_part": 1},
            ),
            TransactionInstruction(
                instruction_type="ROUTE_HOP",
                source_asset=quote.instrument.asset_identifier,
                target_asset=quote.instrument.quote_asset,
                amount=amount_b,
                metadata={"hop_index": 1, "venue": route.venue, "split_part": 2},
            ),
        ]

    @staticmethod
    def estimate_total_fees(instructions: list[TransactionInstruction]) -> int:
        base = BASE_FEE_LAMPORTS
        hop_count = len(instructions)
        if hop_count > 1:
            base += (hop_count - 1) * HOP_FEE_LAMPORTS
            base *= SPLIT_FEE_MULTIPLIER
        return base
