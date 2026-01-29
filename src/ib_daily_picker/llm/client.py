"""
LLM client abstraction.

PURPOSE: Provide unified interface for different LLM backends
DEPENDENCIES: instructor, anthropic, ollama

ARCHITECTURE NOTES:
- Supports Anthropic (Claude) and Ollama backends
- Uses Instructor for structured output
- Backend is configurable via settings
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from ib_daily_picker.config import get_settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> T:
        """Generate a structured response from the LLM.

        Args:
            prompt: User prompt
            response_model: Pydantic model for response structure
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Parsed response as Pydantic model
        """
        pass

    @abstractmethod
    def complete_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a text response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            Text response
        """
        pass


class AnthropicClient(LLMClient):
    """LLM client using Anthropic's Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key (or from settings)
            model: Model name (or from settings)
        """
        try:
            import anthropic
            import instructor
        except ImportError:
            raise ImportError(
                "anthropic and instructor packages required. "
                "Install with: pip install anthropic instructor"
            )

        settings = get_settings()
        self._api_key = api_key or settings.api.anthropic_api_key
        self._model = model or settings.api.llm_model

        if not self._api_key:
            raise ValueError(
                "Anthropic API key required. Set IB_PICKER_ANTHROPIC_API_KEY "
                "environment variable or pass api_key parameter."
            )

        # Create base client
        self._client = anthropic.Anthropic(api_key=self._api_key)

        # Wrap with instructor for structured output
        self._instructor = instructor.from_anthropic(self._client)

        logger.info(f"Initialized Anthropic client with model: {self._model}")

    def complete(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> T:
        """Generate structured response using Instructor."""
        messages = [{"role": "user", "content": prompt}]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "response_model": response_model,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        return self._instructor.messages.create(**kwargs)

    def complete_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate text response."""
        messages = [{"role": "user", "content": prompt}]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        return response.content[0].text


class OllamaClient(LLMClient):
    """LLM client using local Ollama."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str | None = None,
    ) -> None:
        """Initialize Ollama client.

        Args:
            host: Ollama server URL
            model: Model name (default from settings)
        """
        try:
            import instructor
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai and instructor packages required. "
                "Install with: pip install openai instructor"
            )

        settings = get_settings()
        self._model = model or settings.api.llm_model or "llama2"
        self._host = host

        # Ollama is compatible with OpenAI API
        self._client = OpenAI(
            base_url=f"{host}/v1",
            api_key="ollama",  # Ollama doesn't need a real key
        )

        # Wrap with instructor
        self._instructor = instructor.from_openai(self._client)

        logger.info(f"Initialized Ollama client with model: {self._model}")

    def complete(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> T:
        """Generate structured response using Instructor."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self._instructor.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_model=response_model,
        )

    def complete_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate text response."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


def get_llm_client() -> LLMClient:
    """Get configured LLM client based on settings.

    Returns:
        LLMClient instance for the configured provider
    """
    settings = get_settings()
    provider = settings.api.llm_provider.lower()

    if provider == "anthropic":
        return AnthropicClient()
    elif provider == "ollama":
        return OllamaClient()
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. Supported providers: anthropic, ollama"
        )
