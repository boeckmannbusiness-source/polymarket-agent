# Grafana Cloud Dashboards — Polymarket Intelligence Agent

Three dashboards for Grafana Cloud free tier, connecting to the Neon PostgreSQL database.

## Prerequisites

1. Grafana Cloud account at `https://boeckmannbusiness.grafana.net` (prod-eu-west-2)
2. Neon PostgreSQL instance (already connected to the backend)

## Setup

### 1. Add Grafana Cloud egress IPs to Neon allowlist

Add all IPs from `neon-allowlist-ips.txt` to your Neon project:
- Go to Neon Console → your project → **Settings** → **IP Allowlisting**
- Paste the IPs (one per line or comma-separated)
- Save

### 2. Create PostgreSQL datasource in Grafana Cloud

1. Login to `https://boeckmannbusiness.grafana.net`
2. **Connections** → **Data sources** → **Add new data source** → **PostgreSQL**
3. Configure:
   - **Name**: `Neon PostgreSQL`
   - **Host**: `<neon-host>.us-east-2.aws.neon.tech:5432`
   - **Database**: `neondb`
   - **User**: `neondb_owner`
   - **Password**: (from `.env` / Render env vars under `DATABASE_URL`)
   - **TLS/SSL**: Enable
   - **PostgreSQL version**: 16
4. **Save & Test** — should return "Database Connection OK"

### 3. Import dashboards

1. In Grafana Cloud, go to **Dashboards** → **New** → **Import**
2. Upload or paste each JSON file from `dashboards/`
3. Select the `Neon PostgreSQL` datasource when prompted
4. Repeat for all 3 dashboards

### 4. Verify

- Open each dashboard
- Set time range to "Last 24 hours" (or "Last 7 days")
- Panels should show data if ingestion pipeline is running

## Dashboards

| Dashboard | File | Purpose |
|---|---|---|
| Market Intelligence | `dashboards/market-intelligence.json` | Price, volume, liquidity, whale activity, regime detection |
| Signal & Strategy Performance | `dashboards/signal-strategy-performance.json` | Signal outcomes, win rate, Sharpe, calibration |
| Portfolio & Risk | `dashboards/portfolio-risk.json` | Exposure, P&L, drawdown, safety state, correlations |

## Notes

- Dashboards use `${datasource}` variable — set to your `Neon PostgreSQL` datasource on import
- All dashboards refresh every 60s by default
- Free tier limit: 3 dashboards, unlimited panels
