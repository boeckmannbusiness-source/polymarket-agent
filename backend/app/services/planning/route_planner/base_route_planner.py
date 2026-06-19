from abc import ABC, abstractmethod

from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints


class RoutePlanner(ABC):
    @abstractmethod
    async def build_route(
        self,
        quote: Quote,
        constraints: ExecutionConstraints | None = None,
    ) -> Route:
        ...
