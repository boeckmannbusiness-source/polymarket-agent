import logging

from openai import RateLimitError
from pydantic import BaseModel

from app.llm.base import BaseLLMProvider, LLMResponse
from app.llm.groq import GroqProvider
from app.llm.zai import ZAIProvider
from app.llm.ollama import OllamaProvider
from app.llm.mistral import MistralProvider

logger = logging.getLogger(__name__)


class FallbackProvider(BaseLLMProvider):
    """Tries providers in order: z.ai → groq → ollama."""

    provider_name = "fallback"

    def __init__(self):
        self.providers = [ZAIProvider(), GroqProvider(), OllamaProvider(), MistralProvider()]

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        return await self._try_all(
            "generate",
            prompt=prompt, system=system, model=model,
            temperature=temperature, max_tokens=max_tokens,
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseModel:
        return await self._try_all(
            "generate_structured",
            prompt=prompt, schema=schema, system=system, model=model,
            temperature=temperature,
        )

    async def _try_all(self, method_name: str, **kwargs):
        last_error = None
        for provider in self.providers:
            try:
                fn = getattr(provider, method_name)
                return await fn(**kwargs)
            except RateLimitError as e:
                last_error = e
                logger.warning("%s rate-limited, trying next fallback", provider.provider_name)
            except Exception as e:
                last_error = e
                logger.warning("%s failed (%s), trying next fallback", provider.provider_name, e)
        raise last_error or RuntimeError("All LLM providers exhausted")
