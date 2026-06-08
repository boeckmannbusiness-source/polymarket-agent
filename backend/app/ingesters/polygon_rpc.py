import asyncio
import uuid
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

        self.Web3 = Web3
        self.ctf_exchange = Web3.to_checksum_address(settings.CTF_EXCHANGE_ADDRESS)
        self.neg_risk_ctf_exchange = Web3.to_checksum_address(settings.NEG_RISK_CTF_EXCHANGE_ADDRESS)
        self.conditional_tokens = Web3.to_checksum_address(settings.CONDITIONAL_TOKENS_ADDRESS)
        self.pusd_token = Web3.to_checksum_address(settings.PUSD_TOKEN_ADDRESS)
        self._exchange_addresses = [self.ctf_exchange, self.neg_risk_ctf_exchange]

    async def run(self):
        self.running = True
        if not self.w3.is_connected():
            logger.error("polygon_rpc_not_connected")
            return

        self.last_block = await asyncio.to_thread(self._get_latest_block)
        logger.info("polygon_rpc_connected", block=self.last_block)

        self._tasks.append(asyncio.create_task(self._poll_blocks()))
        await asyncio.gather(*self._tasks)

    async def stop(self):
        self.running = False
        for task in self._tasks:
            task.cancel()

    def _get_latest_block(self) -> int:
        return self.w3.eth.block_number

    def _fetch_logs(self, from_block: int, to_block: int) -> list[Any]:
        return self.w3.eth.get_logs({
            "address": self._exchange_addresses,
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
        })

    async def _poll_blocks(self):
        while self.running:
            try:
                current_block = await asyncio.to_thread(self._get_latest_block)
                logger.info("block_poll_cycle", last=self.last_block, current=current_block, ahead=current_block - (self.last_block or 0))

                if self.last_block and current_block > self.last_block:
                    block_from = self.last_block + 1
                    block_to = current_block

                    logs = await asyncio.to_thread(self._fetch_logs, block_from, block_to)
                    logger.info("block_logs_fetched", from_block=block_from, to_block=block_to, log_count=len(logs))

                    per_block: dict[int, set[str]] = {}
                    for log in logs:
                        blk = log["blockNumber"]
                        if not isinstance(blk, int):
                            blk = int(blk, 16) if isinstance(blk, str) else blk
                        tx_hash_raw = log["transactionHash"]
                        tx_hash_str = tx_hash_raw.hex() if hasattr(tx_hash_raw, "hex") else str(tx_hash_raw)
                        if blk not in per_block:
                            per_block[blk] = set()
                        if tx_hash_str in per_block[blk]:
                            continue
                        per_block[blk].add(tx_hash_str)
                        raw_from = b""
                        if log.get("topics") and len(log["topics"]) > 1:
                            raw_from = log["topics"][1]
                            if isinstance(raw_from, bytes) and len(raw_from) == 32:
                                raw_from = raw_from[-20:]
                        from_addr = self.Web3.to_checksum_address(raw_from) if isinstance(raw_from, bytes) and len(raw_from) == 20 else ""
                        await self._process_ctf_trade(
                            block_num=blk,
                            tx_hash=tx_hash_str,
                            exchange=log.get("address", ""),
                            from_addr=from_addr,
                            correlation_id=str(uuid.uuid4()),
                        )

                    for blk, txs in per_block.items():
                        await EventBus.publish(
                            "market:data",
                            "block_processed",
                            self.name,
                            {"block_number": blk, "tx_count": len(txs)},
                            correlation_id=str(uuid.uuid4()),
                        )

                    logger.info("block_process_complete", blocks=len(per_block), total_txs=sum(len(v) for v in per_block.values()))
                    self.last_block = current_block

            except Exception as e:
                logger.error("block_poll_failed", error=str(e))

            await asyncio.sleep(self.poll_interval)

    async def _process_ctf_trade(self, block_num: int, tx_hash: str, exchange: str, from_addr: str, correlation_id: str):
        logger.info("publishing_onchain_trade", block=block_num, tx=tx_hash[:12], exchange=exchange[:20], from_addr=from_addr[:12])
        await EventBus.publish(
            "market:data",
            "onchain_trade",
            self.name,
            {
                "block_number": block_num,
                "transaction_hash": tx_hash,
                "from": from_addr,
                "to": exchange,
            },
            correlation_id=correlation_id,
        )


if __name__ == "__main__":
    listener = PolygonRPCListener()
    asyncio.run(listener.run())
