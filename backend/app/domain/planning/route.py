from pydantic import BaseModel
from typing import Literal


RouteType = Literal["DIRECT", "SPLIT", "OPTIMIZED"]


class Route(BaseModel):
    venue: str
    hops: list[str]
    route_type: RouteType = "DIRECT"
    estimated_latency_ms: float | None = None
    estimated_cost_bps: int | None = None
    price_impact_estimate: float | None = None
    metadata: dict | None = None
