from decimal import Decimal
from app.domain.capital.models import CapitalPolicy

class PolicyService:
    def get_active_policy(self) -> CapitalPolicy:
        # For Sprint 2.3B, we use a static conservative policy
        return CapitalPolicy(
            policy_version="2.3B-CONSERVATIVE",
            max_position_size=Decimal("1000.0"),  # $1000 USD
            max_daily_loss=Decimal("500.0"),      # $500 USD
            max_total_exposure=Decimal("5000.0"), # $5000 USD
            max_asset_exposure=Decimal("2000.0"), # $2000 USD
            emergency_stop=False
        )
