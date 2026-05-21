import json

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.base import BaseLLMProvider, LLMResponse


class ZAIProvider(BaseLLMProvider):
    provider_name = "zai"

    def __init__(self):
        base_url = settings.ZAI_BASE_URL or "https://api.z.ai/v1"
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=settings.ZAI_API_KEY,
        )
        self.default_model = settings.ZAI_DEFAULT_MODEL

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if response.usage else None,
                },
                raw=response,
            )
        except Exception as e:
            raise LLMProviderError(f"z.ai API call failed: {e}") from e

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseModel:
        system_prompt = system or "You are a precise analytical assistant. Respond with valid JSON."
        system_prompt += f"\n\nRespond with JSON matching:\n{json.dumps(schema.model_json_schema(), indent=2)}"

        response = await self.generate(prompt=prompt, system=system_prompt, model=model, temperature=temperature)
        try:
            parsed = json.loads(response.content)
            return schema.model_validate(parsed)
        except (json.JSONDecodeError, ValueError) as e:
            raise LLMProviderError(f"Failed to parse structured response: {e}") from e
