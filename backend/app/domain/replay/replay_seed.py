from pydantic import BaseModel


class ReplaySeed(BaseModel):
    seed: int
    timestamp_bucket: str  # ISO-8601 truncated to minute for deterministic time bucketing
