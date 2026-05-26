import asyncio
from typing import Any

from app.config import settings
from app.core.logging import logger
from app.ingesters.base import BaseIngester
from app.core.events import EventBus


class PolygonRPCListener(BaseIngester):
    name = "polygon_rpc"

    def __init__(self, poll_interval: int = 15):
        from web3 import Web3

        super().__init__()
        self.poll_interval = poll_interval
        self.w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
        self.last_block: int | None = None
        self._tasks: list[asyncio.Task] = []

        self.ctf_exchange = Web3.to_checksum_address(settings.CTF_EXCHANGE_ADDRESS)
        self.conditional_tokens = Web3.to_checksum_address(settings.CONDITIONAL_TOKENS_ADDRESS)
        self.pusd_token = Web3.to_checksum_address(settings.PUSD_TOKEN_ADDRESS)

    async def run(self):
        self.running = True
        if not self.w3.is_connected():
            logger.error("polygon_rpc_not_connected")
            return

        self.last_block = self.w3.eth.block_number
        logger.info("polygon_rpc_connected", block=self.last_block)

        self._tasks.append(asyncio.create_task(self._poll_blocks()))
        await asyncio.gather(*self._tasks)

    async def stop(self):
        self.running = False
        for task in self._tasks:
            task.cancel()

    async def _poll_blocks(self):
        while self.running:
            try:
                current_block = self.w3.eth.block_number

                if self.last_block and current_block > self.last_block:
                    for block_num in range(self.last_block + 1, current_block + 1):
                        await self._process_block(block_num)

                    self.last_block = current_block

            except Exception as e:
                logger.error("block_poll_failed", error=str(e))

            await asyncio.sleep(self.poll_interval)

    async def _process_block(self, block_num: int):
        try:
            block = self.w3.eth.get_block(block_num, full_transactions=True)

            for tx in block.transactions:
                if isinstance(tx, dict) and tx.get("to"):
                    to_addr = tx["to"]
                    if isinstance(to_addr, str):
                        to_checksum = Web3.to_checksum_address(to_addr)
                        if to_checksum == self.ctf_exchange:
                            await self._process_ctf_trade(tx, block_num)

            await EventBus.publish(
                "market:data",
                "block_processed",
                self.name,
                {"block_number": block_num, "tx_count": len(block.transactions)},
            )

        except Exception as e:
            logger.error("block_process_failed", block=block_num, error=str(e))

    async def _process_ctf_trade(self, tx: dict, block_num: int):
        await EventBus.publish(
            "market:data",
            "onchain_trade",
            self.name,
            {
                "block_number": block_num,
                "transaction_hash": tx.get("hash", "").hex() if isinstance(tx.get("hash"), bytes) else str(tx.get("hash", "")),
                "from": tx.get("from", ""),
                "to": tx.get("to", ""),
                "value": str(tx.get("value", 0)),
                "gas_price": str(tx.get("gasPrice", 0)),
            },
        )


if __name__ == "__main__":
    listener = PolygonRPCListener()
    asyncio.run(listener.run())
