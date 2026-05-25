# Polymarket WebSocket Event Types

> **Last updated:** 2026-05-25
> **Source:** Empirical observation from `/debug/ws-events` and `/debug/event-stats`

## Dominant Event: `price_change` (99.8% of traffic)

### Raw Payload Structure

```json
{
  "event_type": "price_change",
  "market": "0x<64-char-hex-condition_id>",
  "price_changes": [
    {
      "asset_id": "<numeric-asset-token-id>",
      "price": "<string-or-float>",
      "size": "<trade-size>",
      "side": "BUY|SELL",
      "hash": "<40-char-hex>",
      "best_bid": "<string-or-float>",
      "best_ask": "<string-or-float>"
    }
  ],
  "timestamp": "<unix-ms>"
}
```

### Key Fields

| Field | Location | Type | Description |
|-------|----------|------|-------------|
| `event_type` | top level | string | Always `"price_change"` |
| `market` | top level | hex string | **This is the condition_id** (64 bytes, 0x-prefixed) |
| `price_changes` | top level | array | Array of price update objects (typically 1-3 items) |
| `asset_id` | per item | numeric string | CLOB token asset ID (up to 77 digits) |
| `price` | per item | string/float | Current market price (e.g. `"0.89"`, `0.11`) |
| `size` | per item | string/float | Last trade size |
| `side` | per item | `"BUY"` / `"SELL"` | Side of last trade |
| `timestamp` | top level | unix ms | Event timestamp as milliseconds |

### Parsing Behavior

- `market` field IS the `condition_id` — used directly, no reverse lookup needed
- Each `price_changes` item becomes one normalized `price_change` event
- Normalization: `condition_id` + `asset_id` + `price` + `timestamp` (required fields)
- Schema validation: all 3 required fields present — passes

### Frequency

- ~2-4 messages/second during active market hours
- Each message contains 1-3 price changes
- ~4-8 normalized events/second peak

---

## Minor Event: `book` (0.1% of traffic)

### Raw Payload Structure

```json
{
  "event_type": "book",
  "market": "0x<condition_id>",
  "bids": [[...], ...],
  "asks": [[...], ...],
  "timestamp": "<unix-ms>"
}
```

### Parsing Behavior

- Published directly to `market:data` stream as `orderbook_snapshot`
- Not normalized (no bridge handler yet)
- Stored in `_last_raw_events` buffer for debug inspection

---

## Minor Event: `last_trade_price` (<0.1% of traffic)

Rarely observed. Only 2 instances in ~4,000 messages.

### Raw Payload Structure

```json
{
  "asset_id": "<numeric-id>",
  "price": "<string-or-float>",
  "size": "<string-or-float>",
  "timestamp": "<unix-ms>",
  "type": "last_trade_price"
}
```

### Parsing Behavior

- Normalized as `trade` event type
- Published to `market:data` stream as `trade`
- Condition_id resolved from `_asset_to_condition` mapping (asset_id → condition_id)
- If mapping lookup fails, `condition_id` is None → validation FAILS → dropped

---

## System Messages: `subscription`, `ack`, `error`

Occur during connection setup and subscription. Not published to stream.

---

## Not Observed

The following event types were NOT observed in the actual WS feed:
- `tick` — not present
- `live_activity` — not present
- `user_*` events — not subscribed
- `market_metadata` — only from REST ingester
- `trade` — `last_trade_price` is the closest; no raw `trade` events observed

---

## Pipeline Flow Summary

```
WS receive (price_change)
  → event_type registry: "price_change"
  → _normalize_price_events() — extracts condition_id from "market", iterates price_changes[]
  → _validate_normalized() — checks condition_id, asset_id, timestamp
  → _compute_event_hash() — SHA-256 dedup check
  → EventBus.publish(market:data, "price_change", normalized)
  → Redis stream (market:data, maxlen=10000)
  → EventPersistenceBridge._consume_market_events()
  → _persist_price_change() — creates MarketEvent with price, condition_id
  → DB commit
```

---

## Schema Validation Requirements

For a normalized event to be published, it must pass:

1. `condition_id` present and non-empty
2. `asset_id` present and non-empty  
3. `timestamp` present and non-empty

Events failing validation → `validation_failures++` → dropped (logged in `_last_raw_events`)

Events with duplicate hash → `duplicate_events_detected++` → dropped

---

## Performance Metrics (from production data)

- **Validation pass rate:** 100% (0 failures out of ~8,000 events)
- **Duplicate rate:** ~0.2% (14 out of ~7,800)
- **Bridge persist rate:** >99% (1,999 persisted / ~2,000 processed)
- **Bridge failure rate:** 0%
- **DLQ utilization:** 0%
