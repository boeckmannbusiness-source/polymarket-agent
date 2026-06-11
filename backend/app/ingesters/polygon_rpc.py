import asyncio
import uuid
from typing import Any

from eth_abi import decode as abi_decode

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
                        decoded = self._decode_trade_log(log)
                        await self._process_ctf_trade(
                            block_num=blk,
                            tx_hash=tx_hash_str,
                            exchange=log.get("address", ""),
                            from_addr=from_addr,
                            correlation_id=str(uuid.uuid4()),
                            decoded=decoded,
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

    @staticmethod
    def _decode_trade_log(log: dict) -> dict[str, Any]:
        topics = log.get("topics", [])
        result: dict[str, Any] = {
            "size": None,
            "price": None,
            "outcome": None,
            "condition_id": None,
            "value": None,
        }

        try:
            if len(topics) >= 4:
                t2, t3 = topics[2], topics[3]
                t2b = t2 if isinstance(t2, bytes) else b""
                t3b = t3 if isinstance(t3, bytes) else b""
                t3_int = int.from_bytes(t3b, "big")

                if t3_int <= 2:
                    result["outcome"] = ("NO", "YES", str(t3_int))[t3_int] if t3_int < 3 else str(t3_int)

            data_raw = log.get("data", "")
            data_bytes = (
                bytes.fromhex(data_raw[2:])
                if isinstance(data_raw, str) and data_raw.startswith("0x")
                else data_raw if isinstance(data_raw, bytes)
                else b""
            )
            if len(data_bytes) < 32:
                return result

            decoded = None
            for types in (
                ("uint256", "bytes32", "uint256", "uint256"),
                ("uint256", "uint256", "uint256", "uint256"),
                ("uint256", "uint256", "uint256"),
                ("uint256", "uint256", "bytes32"),
                ("uint256", "uint256"),
            ):
                try:
                    candidate = abi_decode(types, data_bytes[:sum(32 for _ in types)])
                    c0 = int(candidate[0])
                    if c0 in (0, 1):
                        if result["outcome"] is None:
                            result["outcome"] = ("NO", "YES")[c0]
                        if isinstance(candidate[1], bytes) and len(candidate[1]) == 32:
                            if result["condition_id"] is None and any(b != 0 for b in candidate[1]):
                                result["condition_id"] = "0x" + candidate[1].hex()
                            result["size"] = int(candidate[2]) if len(candidate) >= 3 else None
                            result["value"] = int(candidate[3]) if len(candidate) >= 4 else None
                        else:
                            result["size"] = int(candidate[1])
                            result["value"] = int(candidate[2]) if len(candidate) >= 3 else None
                    elif result["size"] is None:
                        result["size"] = c0
                        result["value"] = int(candidate[1])
                    decoded = candidate
                    break
                except Exception:
                    continue

            if decoded is not None and len(decoded) >= 3 and result["condition_id"] is None:
                cid = decoded[-1]
                if isinstance(cid, bytes) and len(cid) == 32 and any(b != 0 for b in cid):
                    result["condition_id"] = "0x" + cid.hex()
                elif isinstance(cid, int):
                    h = format(cid, "064x")
                    if h != "0" * 64:
                        result["condition_id"] = "0x" + h

            sz, val = result.get("size"), result.get("value")
            if sz is not None and val is not None and sz > 0:
                result["price"] = round(val / sz, 12)

        except Exception:
            logger.warning("trade_decoding_failed", tx=log.get("transactionHash", ""))

        return result

    async def _process_ctf_trade(
        self,
        block_num: int,
        tx_hash: str,
        exchange: str,
        from_addr: str,
        correlation_id: str,
        decoded: dict[str, Any] | None = None,
    ):
        d = decoded or {}
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
                "size": d.get("size"),
                "price": d.get("price"),
                "outcome": d.get("outcome"),
                "condition_id": d.get("condition_id"),
                "value": d.get("value"),
            },
            correlation_id=correlation_id,
        )


if __name__ == "__main__":
    listener = PolygonRPCListener()
    asyncio.run(listener.run())
