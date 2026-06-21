import base64
import json
from datetime import datetime, timezone
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.solana.models import TransactionEnvelope, TransactionPayload


class SolanaTransactionBuilder:
    """Translates a TransactionPlan into a Solana TransactionEnvelope.

    Deterministic and pure (no signing, no RPC).
    """

    async def build_envelope(self, plan: TransactionPlan) -> TransactionEnvelope:
        # Create a deterministic payload for simulation

        payload_data = {
            "instructions": [
                {
                    "type": instr.instruction_type,
                    "source": instr.source_asset,
                    "target": instr.target_asset,
                    "amount": str(instr.amount)
                } for instr in plan.instructions
            ],
            "estimated_fees": plan.estimated_fees,
            "quote_source": plan.quote.source if plan.quote else "unknown"
        }

        serialized = json.dumps(payload_data, sort_keys=True)
        payload_b64 = base64.b64encode(serialized.encode()).decode()

        payload = TransactionPayload(serialized_payload_b64=payload_b64)

        return TransactionEnvelope(
            instructions=plan.instructions,
            payload=payload,
            slippage_bps=plan.slippage_bps or 100,
            fee_estimate=plan.estimated_fees or 5000,
            metadata={
                "plan_quote_source": plan.quote.source if plan.quote else "none"
            }
        )
