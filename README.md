# Polymarket Intelligence Agent

Autonomous prediction market analysis and execution system for Polymarket.

## Architecture

```
                    ┌─────────────────────┐
                    │   Next.js Dashboard  │
                    └────────┬────────────┘
                             │ SSE / REST
                    ┌────────┴────────────┐
                    │   FastAPI Backend    │
                    └────────┬────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌──────────┐      ┌──────────────┐    ┌──────────────┐
   │ Agents   │      │  Services    │    │  Ingesters   │
   │ (6 pods) │      │  (8 pods)    │    │  (3 pods)    │
   └──────────┘      └──────────────┘    └──────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    ┌─────────────────┐
                    │  Event Bus       │
                    │  (Redis Streams) │
                    └─────────────────┘
                             │
                    ┌─────────────────┐
                    │  PostgreSQL      │
                    │  (11 tables)     │
                    └─────────────────┘
```

## Quick Start

```bash
# Clone and enter
cd polymarket-agent

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Install Python dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the API
uvicorn app.main:app --reload --port 8000

# Start data ingestion
python -m app.ingesters.polymarket_ws

# Start whale tracking
python -m app.services.whale_service_worker

# Start agents
python -m app.agents.orchestrator
```

## Docker

```bash
docker-compose up -d
```

## Services

- **API**: FastAPI on `:8000`
- **Dashboard**: Next.js on `:3000`
- **Ingester**: Polymarket WebSocket + REST + Polygon RPC
- **Whale Tracker**: Wallet scoring and behavior analysis
- **Agent Runner**: Multi-agent orchestration system

## LLM Providers

Configure via `.env`: OpenRouter, Ollama, Mistral, or z.ai.

## License

MIT
