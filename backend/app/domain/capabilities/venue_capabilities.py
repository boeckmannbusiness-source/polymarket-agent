from pydantic import BaseModel, Field
from typing import Set
from .venue_capability import VenueCapability


class VenueCapabilities(BaseModel):
    venue: str
    supports: Set[VenueCapability] = Field(default_factory=set)

    def has(self, capability: VenueCapability) -> bool:
        return capability in self.supports

    class Config:
        frozen = True
