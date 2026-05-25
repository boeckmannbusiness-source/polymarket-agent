# Polymarket Intelligence Agent — How It Works

## What is this?

This system watches Polymarket (a prediction market platform where people bet on real-world outcomes like elections, sports, and crypto prices). It automatically tracks what "whales" (big traders) are doing, detects patterns in market prices, and can simulate trading strategies to see which ones would make money.

Think of it as a **robotic trading assistant** that:
1. Watches 186+ markets 24/7
2. Learns what moves prices
3. Tests strategies against historical data
4. Could eventually execute trades automatically

---

## The Big Picture

```
Market Data (Polymarket)  →  Brain (Backend)  →  Dashboard (Website)
```

**Polymarket** = A marketplace where you can bet on anything (Will BTC hit $100K? Will Trump win?).
**The Brain** = A Python server that downloads all trade data, analyzes it, and generates signals.
**The Dashboard** = A website that shows you what the brain is thinking.

---

## Main Parts

### 1. Data Collectors ("Ingesters")

Two programs that constantly download data from Polymarket:

- **REST Ingester** — Polls Polymarket's API every 60 seconds for new trades
- **WebSocket Ingester** — Maintains a live connection to get price updates instantly

Every trade event goes into a PostgreSQL database (hosted on Neon Cloud).

### 2. The Memory (Database)

A PostgreSQL database with ~20 tables storing:
- **186 markets** — Each market is a prediction question
- **131,000+ trade events** — Every buy/sell that ever happened
- **Strategies & signals** — What trades the system recommends
- **Backtests** — How strategies performed on historical data

### 3. The Strategy Engine

Eight built-in trading strategies that look for patterns:

| Strategy | What It Does |
|----------|-------------|
| **Whale Following** | Tracks big traders (>$500 trades). If a whale buys YES, buy YES too. |
| **Momentum Spike** | Detects sharp 1-hour price moves. Trades in the direction of momentum. |
| **Mean Reversion** | Buys when prices move too far from average (expecting them to come back) |
| **Breakout** | Buys when price breaks through a support/resistance level |
| **Liquidity Grab** | Looks for fakeouts designed to trigger stop-losses |
| **Volume Profile** | Trades based on unusual volume patterns |
| **Sentiment** | Uses social media signals (if available) |
| **Ensemble** | Combines all strategies into one meta-signal |

Each strategy generates a **signal** (BUY_YES, BUY_NO, or NEUTRAL) with a confidence score.

### 4. The Time Machine (Replay Engine)

This is the most important part. The Replay Engine answers the question:

> "If I had used this strategy in the past, would I have made money?"

It works like a time machine:
1. Loads all historical trade events in chronological order
2. Feeds them to the strategy one at a time
3. When the strategy generates a signal, it tracks what happens next
4. Checks profit at 5 minutes, 15 minutes, 1 hour, 4 hours, and until market close
5. Reports the final statistics (win rate, total profit, etc.)

### 5. The Dashboard (Next.js)

A website at `polymarket-agent-tau.vercel.app` showing:
- Live market status
- Whale trades happening in real time
- Strategy signals and performance
- Backtest results with charts

---

## Key Findings So Far

### Whale Following Strategy (Best Performer)
- **15-minute horizon**: 70% win rate — the sweet spot
- How it works: When a whale makes a large trade, the market tends to move in that direction for about 15 minutes, then reverses
- **5-minute**: 50/50 — too noisy
- **1-hour**: 48% — mean reversion kicks in

### Momentum Spike Strategy
- Detects sharp 1-hour price moves (3%+)
- **15-minute**: 51% win rate — momentum continues briefly
- **Close**: 32% win rate — sharp moves almost always reverse by market close
- This means the strategy is actually good at identifying **overreactions** (you'd make money by betting AGAINST the momentum at close)

### What We Fixed
- **PnL Directionality Bug**: The system was mixing up YES and NO token prices, causing random-looking profits. Fixed by tracking each outcome's price separately.
- **Momentum Calculation Bug**: The 1-hour momentum was looking for a trade that happened at exactly the 3600-second mark (within a 60-second window). Changed to use the closest trade to that time, making it work on real market data.

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.14, FastAPI |
| Database | PostgreSQL (Neon Cloud — free tier) |
| Cache | Redis (Redis Cloud — free tier) |
| AI Models | Free tier LLMs (z.ai, Groq, Ollama, Mistral) with automatic fallback |
| Dashboard | Next.js (Vercel — free tier) |
| Backend Hosting | Render — free tier (512MB RAM) |
| Monitoring | Grafana Cloud (free tier) |
| Market Data | Polymarket REST + WebSocket APIs |

---

## Limits We Hit

- **Render free tier (512MB RAM)** can't run backtests on 46,000+ events — it runs out of memory. Backtests work fine on a local machine.
- **Polymarket WebSocket** only sends `"price_change"` events (not `"trade"` events). Our bridge currently processes `"trade"` events via REST API polling instead.
- **Free LLM APIs** have rate limits. The system falls back through 4 providers automatically.

---

## How to Use

### View the Dashboard
Visit `https://polymarket-agent-tau.vercel.app`

### Run a Backtest Locally
```bash
cd backend
python -c "
import asyncio
from app.database import async_session_factory
from app.replay.engine import ReplayEngine, ReplayMode
from app.services.execution_simulator import ExecutionSimulator
from datetime import datetime, timezone, timedelta

async def test():
    async with async_session_factory() as db:
        engine = ReplayEngine(db, ExecutionSimulator())
        result = await engine.run(
            strategy_name='whale_following',
            start_time=datetime.now(timezone.utc) - timedelta(days=7),
            end_time=datetime.now(timezone.utc),
            mode=ReplayMode.SIGNAL_ONLY,
        )
        print(f'Signals: {len(result.signals)}')
asyncio.run(test())
"
```

### Check the API
```bash
curl https://polymarket-agent-nw0o.onrender.com/health
```
