from pydantic import BaseModel, Field


class AssetMetadata(BaseModel):
    external_identifiers: dict[str, str] = Field(default_factory=dict)
    venue_metadata: dict[str, str] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
