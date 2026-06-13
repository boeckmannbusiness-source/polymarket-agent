from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


def _find_dotenv() -> str:
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_find_dotenv(), env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    APP_DEBUG: bool = True
    APP_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"

    # Polymarket APIs
    POLYMARKET_CLOB_API_URL: str = "https://clob.polymarket.com"
    POLYMARKET_GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    POLYMARKET_DATA_API_URL: str = "https://data-api.polymarket.com"
    POLYMARKET_WS_URL: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    POLYMARKET_API_KEY: str = ""
    POLYMARKET_SECRET: str = ""
    POLYMARKET_PASSPHRASE: str = ""
    POLYMARKET_ETH_PRIVATE_KEY: str = ""

    # Polygon
    POLYGON_RPC_URL: str = "https://polygon-rpc.com"
    POLYGON_WS_URL: str = "wss://polygon-rpc.com/ws"
    POLYGON_CHAIN_ID: int = 137

    # Smart Contracts
    CTF_EXCHANGE_ADDRESS: str = "0xE111180000d2663C0091e4f400237545B87B996B"
    NEG_RISK_CTF_EXCHANGE_ADDRESS: str = "0xe2222d279d744050d28e00520010520000310F59"
    CONDITIONAL_TOKENS_ADDRESS: str = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    PUSD_TOKEN_ADDRESS: str = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"

    # LLM
    LLM_DEFAULT_PROVIDER: str = "openrouter"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = "anthropic/claude-3.5-sonnet"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_API_KEY: str = ""
    OLLAMA_DEFAULT_MODEL: str = "llama3"
    MISTRAL_API_KEY: str = ""
    MISTRAL_DEFAULT_MODEL: str = "mistral-small-latest"
    ZAI_API_KEY: str = ""
    ZAI_BASE_URL: str = ""
    ZAI_DEFAULT_MODEL: str = "z-ai-model"
    GROQ_API_KEY: str = ""
    GROQ_DEFAULT_MODEL: str = "llama-3.3-70b-versatile"
    BLOCKRUN_API_KEY: str = "not-required"
    BLOCKRUN_BASE_URL: str = "https://blockrun.ai/api/v1"
    BLOCKRUN_DEFAULT_MODEL: str = "nvidia/deepseek-v4-flash"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@host:5432/polymarket"
    DATABASE_POOL_SIZE: int = 15
    DATABASE_MAX_OVERFLOW: int = 5

    # Redis
    REDIS_URL: str = "redis://user:password@host:6379/0"
    REDIS_MAX_CONNECTIONS: int = 5
    REDIS_STREAM_MAXLEN: int = 1000
    REDIS_PLAN_LIMIT_MB: int = 30

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ALERT_LEVEL: str = "info"

    # Trading
    TRADING_MODE: Literal["paper", "live"] = "paper"
    PAPER_INITIAL_CAPITAL: float = 10000.0
    MAX_POSITION_SIZE_PERCENT: float = 10.0
    MAX_DAILY_LOSS: float = 500.0
    MAX_OPEN_POSITIONS: int = 5
    EXPOSURE_LIMIT: float = 0.3
    COOLDOWN_MINUTES: int = 15
    MIN_CONFIDENCE_THRESHOLD: float = 0.6
    # Monitoring
    LOG_LEVEL: str = "WARNING"
    LOG_FORMAT: Literal["json", "text"] = "json"
    # Admin
    ADMIN_API_KEY: str = ""

    METRICS_ENABLED: bool = True
    HEARTBEAT_INTERVAL_SECONDS: int = 30

    # Shadow mode
    SHADOW_MODE: bool = False

    # Kill switch
    FORCE_TRADING_DISABLED: bool = False
    CLOSE_ALL_POSITIONS_ON_KILL: bool = False

    # Micro-live safety
    MICRO_LIVE_SAFE_MODE: bool = False
    MICRO_LIVE_MAX_POSITION_SIZE: float = 1.0
    MICRO_LIVE_MAX_DAILY_LOSS: float = 2.0
    MICRO_LIVE_MAX_CONCURRENT: int = 2

    # WS stability
    WS_STALL_SECONDS: int = 60
    WS_RECONNECT_STORM_THRESHOLD: int = 5
    WS_RECONNECT_WINDOW_MINUTES: int = 10

    # Runtime health
    MEMORY_WARN_MB: int = 500
    EVENT_LOOP_STALL_SECONDS: float = 2.0
    TASK_WATCHDOG_INTERVAL: int = 60

    # ── Dedup ─────────────────────────────────────────────────
    DEDUP_REDIS_ENABLED: bool = True
    DEDUP_TTL_SECONDS: int = 3600
    DEDUP_MAX_KEYS: int = 100000
    DEDUP_REDIS_PREFIX: str = "dedup:event"

    # ── Pending message recovery ──────────────────────────────
    PENDING_RECOVERY_ENABLED: bool = True
    PENDING_RECOVERY_INTERVAL: int = 60
    PENDING_IDLE_TIMEOUT: int = 120
    PENDING_MAX_RETRIES: int = 3
    PENDING_CLAIM_COUNT: int = 100
    PENDING_DLQ_STREAM: str = "system:dlq:pending"

    # ── DLQ replay ────────────────────────────────────────────
    DLQ_REPLAY_ENABLED: bool = True
    DLQ_REPLAY_INTERVAL: int = 300
    DLQ_REPLAY_MAX_RETRIES: int = 5
    DLQ_REPLAY_BACKOFF_BASE: float = 5.0
    DLQ_REPLAY_MAX_ENTRIES: int = 100

    # ── WS stall detection ────────────────────────────────────
    WS_STALE_TIMEOUT: int = 30
    WS_WATCHDOG_INTERVAL: int = 15

    # ── Event schema enforcement ──────────────────────────────
    EVENT_SCHEMA_ENFORCEMENT: Literal["strict", "log", "off"] = "strict"

    # ── Solana ──────────────────────────────────────────────
    HELIUS_API_KEY: str = ""
    HELIUS_WEBHOOK_SECRET: str = ""
    BIRDEYE_API_KEY: str = ""
    SOLANA_RPC_URL: str = ""
    SOLANA_CHAIN_ID: int = 0
    SOLANA_HIGH_SCORE_THRESHOLD: float = 0.7

    # ── Stream trimming ───────────────────────────────────────
    STREAM_TRIM_APPROX: bool = True
    STREAM_TRIM_INTERVAL: int = 600


settings = Settings()
