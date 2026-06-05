from datetime import datetime, timezone
from typing import Any

from app.schemas.evolution import Candidate


class StrategyCandidateService:
    LIFECYCLE = ["EXPERIMENTAL", "SHADOW", "PAPER", "LIVE", "RETIRED"]

    def validate_transition(self, current: str, target: str) -> bool:
        if current not in self.LIFECYCLE or target not in self.LIFECYCLE:
            return False
        if current == "RETIRED":
            return False
        current_idx = self.LIFECYCLE.index(current)
        target_idx = self.LIFECYCLE.index(target)
        if target_idx == current_idx + 1:
            return True
        if target == "RETIRED":
            return True
        return False

    def get_next_status(self, current: str) -> str | None:
        if current not in self.LIFECYCLE or current == "RETIRED":
            return None
        idx = self.LIFECYCLE.index(current)
        if idx + 1 < len(self.LIFECYCLE):
            return self.LIFECYCLE[idx + 1]
        return None

    async def transition(self, candidate: Candidate, target: str, population_service) -> Candidate | None:
        if not self.validate_transition(candidate.status, target):
            return None
        candidate.status = target
        candidate.updated_at = datetime.now(timezone.utc).isoformat()
        await population_service.update_candidate_status(candidate.candidate_id, target)
        return candidate


candidate_service = StrategyCandidateService()