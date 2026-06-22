from app.models import ExchangeOrder


class BaseExchangeAdapter:
    async def submit_order(self, order: ExchangeOrder):
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> dict:
        raise NotImplementedError

    async def get_order_status(self, order_id: str) -> dict:
        raise NotImplementedError
