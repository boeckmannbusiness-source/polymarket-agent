import json
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.base import BaseLLMProvider, LLMResponse


class BlockrunProvider(BaseLLMProvider):
    provider_name = "blockrun"

    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.BLOCKRUN_BASE_URL,
            api_key=settings.BLOCKRUN_API_KEY,
        )
        self.default_model = settings.BLOCKRUN_DEFAULT_MODEL

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
            raise LLMProviderError(f"Blockrun API call failed: {e}") from e

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> BaseModel:
        system_prompt = system or "You are a precise analytical assistant. Respond with valid JSON."
        system_prompt += f"\n\nYou MUST respond with a JSON object matching this schema:\n{json.dumps(schema.model_json_schema(), indent=2)}"

        response = await self.generate(
            prompt=prompt,
            system=system_prompt,
            model=model,
            temperature=temperature,
        )

        try:
            parsed = json.loads(response.content)
            return schema.model_validate(parsed)
        except (json.JSONDecodeError, ValueError) as e:
            raise LLMProviderError(f"Failed to parse structured response: {e}\nContent: {response.content[:500]}") from e
