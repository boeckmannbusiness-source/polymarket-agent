# Market Quality Report

The following signals are evaluated for every asset admission request:

| Signal | Threshold | Impact |
| --- | --- | --- |
| Market Cap | < $1,000,000 | BLOCK |
| Liquidity | < $50,000 | BLOCK |
| Holder Concentration | > 25% | WATCH |
| Asset Age | < 7 days | WATCH |
| Route Confidence | < 80% | WATCH |

## Policy Rules

- `LOW_MARKET_CAP` OR `LOW_LIQUIDITY` -> `BLOCK`
- `HIGH_CONCENTRATION` OR `NEW_ASSET` OR `LOW_ROUTE_CONFIDENCE` -> `WATCH`
- All checks passed -> `APPROVED`
