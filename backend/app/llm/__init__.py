from app.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse
from app.llm.openrouter import OpenRouterProvider
from app.llm.ollama import OllamaProvider
from app.llm.mistral import MistralProvider
from app.llm.zai import ZAIProvider
from app.llm.groq import GroqProvider
from app.llm.blockrun import BlockrunProvider
from app.llm.fallback import FallbackProvider


def get_llm_provider(provider: str | None = None) -> BaseLLMProvider:
    provider = provider or settings.LLM_DEFAULT_PROVIDER
    single_registry = {
        "openrouter": OpenRouterProvider,
        "ollama": OllamaProvider,
        "mistral": MistralProvider,
        "zai": ZAIProvider,
        "groq": GroqProvider,
        "blockrun": BlockrunProvider,
    }
    if provider == "fallback":
        return FallbackProvider()
    cls = single_registry.get(provider)
    if cls is None:
        raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(single_registry.keys()) + ['fallback']}")
    return cls()


__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "OpenRouterProvider",
    "OllamaProvider",
    "MistralProvider",
    "ZAIProvider",
    "GroqProvider",
    "BlockrunProvider",
    "FallbackProvider",
    "get_llm_provider",
]
