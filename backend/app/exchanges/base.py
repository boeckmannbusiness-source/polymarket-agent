from typing import Union
from app.models import ExchangeOrder
from app.domain.execution import ExecutionIntent


class BaseExchangeAdapter:
    async def submit_order(self, order: Union[ExchangeOrder, ExecutionIntent]):
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> dict:
        raise NotImplementedError

    async def get_order_status(self, order_id: str) -> dict:
        raise NotImplementedError
