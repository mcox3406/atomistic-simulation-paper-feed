"""LLM provider abstraction for relevance scoring and categorization.

Both `LLMFilter` and `PaperCategorizer` only need to send a single-turn prompt
and read back text. This module hides the SDK differences so a config flag can
flip between providers without touching the rest of the pipeline.
"""

import os
from typing import Protocol


DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"
ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class InsufficientCreditsError(Exception):
    """Raised when API credits are depleted; halts the run cleanly."""
    pass


class LLMClient(Protocol):
    def complete(self, prompt: str, max_tokens: int) -> str: ...


class DeepSeekClient:
    """DeepSeek via the OpenAI-compatible SDK."""

    def __init__(self, api_key: str, model: str | None = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model = model or DEEPSEEK_DEFAULT_MODEL

    def complete(self, prompt: str, max_tokens: int) -> str:
        try:
            # json_object mode requires the word "json" in the prompt (both of
            # our prompts already say "JSON" and show a schema example).
            # Eliminates the malformed-JSON failures we saw without it.
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                stream=False,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            # DeepSeek returns HTTP 402 with body "Insufficient Balance" when the
            # account is out of credit. Match loosely so wording changes don't
            # silently degrade us to neutral 0.5 scoring.
            msg = str(e).lower()
            if "insufficient balance" in msg or "insufficient_user_quota" in msg:
                raise InsufficientCreditsError(str(e))
            raise


class AnthropicClient:
    """Anthropic Claude (legacy)."""

    def __init__(self, api_key: str, model: str | None = None):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)
        self.model = model or ANTHROPIC_DEFAULT_MODEL

    def complete(self, prompt: str, max_tokens: int) -> str:
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        except Exception as e:
            if "credit balance is too low" in str(e).lower():
                raise InsufficientCreditsError(str(e))
            raise


def make_llm_client(provider: str | None = None, model: str | None = None) -> LLMClient:
    """Build a client based on config. Reads the provider's API key from env."""
    provider = (provider or "deepseek").lower()
    if provider == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is required for provider='deepseek'")
        return DeepSeekClient(api_key=api_key, model=model)
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for provider='anthropic'")
        return AnthropicClient(api_key=api_key, model=model)
    raise ValueError(f"Unknown provider: {provider!r}. Use 'deepseek' or 'anthropic'.")
