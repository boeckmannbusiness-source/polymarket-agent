class PolymarketAgentError(Exception):
    """Base exception for all application errors."""


class ConfigurationError(PolymarketAgentError):
    """Raised when required configuration is missing or invalid."""


class StartupSafetyViolation(ConfigurationError):
    """Raised when process starts with unsafe configuration."""


class IngestionError(PolymarketAgentError):
    """Raised when data ingestion fails."""


class WhaleAnalysisError(PolymarketAgentError):
    """Raised when wallet analysis encounters an error."""


class SignalError(PolymarketAgentError):
    """Raised when signal generation fails."""


class RiskCheckError(PolymarketAgentError):
    """Raised when risk validation fails."""


class TradeExecutionError(PolymarketAgentError):
    """Raised when trade execution fails."""


class LLMProviderError(PolymarketAgentError):
    """Raised when an LLM provider call fails."""


class BacktestError(PolymarketAgentError):
    """Raised during backtesting operations."""


class NotificationError(PolymarketAgentError):
    """Raised when sending notifications fails."""


class MarketNotFoundError(PolymarketAgentError):
    """Raised when a requested market is not found."""


class WalletNotFoundError(PolymarketAgentError):
    """Raised when a requested wallet is not found."""


class InsufficientCapitalError(TradeExecutionError):
    """Raised when there is not enough capital for a trade."""


class RiskLimitReachedError(TradeExecutionError):
    """Raised when a risk limit has been reached."""
