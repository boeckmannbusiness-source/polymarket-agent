from pydantic import BaseModel, Field
from typing import List


class CapabilityReport(BaseModel):
    supported: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.missing) == 0
