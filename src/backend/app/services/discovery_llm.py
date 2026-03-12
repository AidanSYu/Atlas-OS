"""Discovery OS LLM Service — Isolated from global model selector.

This service provides API-based LLM access exclusively for Discovery OS agents
(Coordinator, Executor). It is completely independent from the main LLMService
used for chat/retrieval, ensuring that global model changes do not affect
active discovery sessions.

Architecture:
- DeepSeek: High-level orchestration and planning (deepseek-reasoner recommended)
- MiniMax: Fast tool calling and constrained generation (MiniMax-M2.5)
- LiteLLM: Unified API gateway for provider abstraction

Future: Can be extended to support local models once hardware permits.
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


class DiscoveryLLMService:
    """Isolated LLM service for Discovery OS agents.

    This service is completely independent from the global LLMService.
    It uses API models exclusively and maintains its own configuration.
    """

    def __init__(self, config: Settings):
        self.config = config
        self._deepseek_client: Optional[AsyncOpenAI] = None
        self._minimax_client_ready = False

        # Discovery-specific configuration (does NOT read from global state)
        # Load from config — these are isolated from global model selector
        self._orchestration_provider = config.DISCOVERY_ORCHESTRATION_PROVIDER
        self._orchestration_model = config.DISCOVERY_ORCHESTRATION_MODEL
        self._tool_provider = config.DISCOVERY_TOOL_PROVIDER
        self._tool_model = config.DISCOVERY_TOOL_MODEL

        # Validate API keys at initialization
        self._validate_configuration()

    def _validate_configuration(self):
        """Validate that required API keys are configured."""
        if self._orchestration_provider == "deepseek" and not self.config.DEEPSEEK_API_KEY:
            logger.warning(
                "DeepSeek API key not configured. Discovery OS orchestration will fail. "
                "Set DEEPSEEK_API_KEY in .env file."
            )
        if self._tool_provider == "minimax" and not self.config.MINIMAX_API_KEY:
            logger.warning(
                "MiniMax API key not configured. Discovery OS tool calling will fail. "
                "Set MINIMAX_API_KEY in .env file."
            )

    def _get_deepseek_client(self) -> AsyncOpenAI:
        """Lazy-load DeepSeek client."""
        if self._deepseek_client is None:
            if not self.config.DEEPSEEK_API_KEY:
                raise ValueError(
                    "DeepSeek API key not configured. Cannot initialize DiscoveryLLMService. "
                    "Set DEEPSEEK_API_KEY in .env file."
                )
            self._deepseek_client = AsyncOpenAI(
                api_key=self.config.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
            )
            logger.info("DeepSeek client initialized for Discovery OS orchestration")
        return self._deepseek_client

    def _ensure_minimax_ready(self):
        """Ensure MiniMax is configured via LiteLLM."""
        if not self._minimax_client_ready:
            if not self.config.MINIMAX_API_KEY:
                raise ValueError(
                    "MiniMax API key not configured. Cannot use tool calling. "
                    "Set MINIMAX_API_KEY in .env file."
                )
            try:
                import litellm as _litellm
            except ImportError:
                raise RuntimeError(
                    "litellm is not installed. Run: pip install litellm"
                )
            # LiteLLM uses environment variables or can be set at runtime
            _litellm.api_key = self.config.MINIMAX_API_KEY
            self._minimax_client_ready = True
            logger.info("MiniMax configured via LiteLLM for Discovery OS tool calling")

    # ========================================================================
    # Orchestration API (High-level planning and reasoning)
    # ========================================================================

    async def orchestrate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """Generate text using the orchestration model (DeepSeek).

        Use this for:
        - High-level planning and task decomposition
        - Reasoning about research strategy
        - Analyzing corpus context and generating questions

        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response
        """
        if self._orchestration_provider == "deepseek":
            return await self._orchestrate_deepseek(
                prompt, system_prompt, temperature, max_tokens, **kwargs
            )
        else:
            raise ValueError(f"Unsupported orchestration provider: {self._orchestration_provider}")

    async def _orchestrate_deepseek(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> str:
        """Generate text using DeepSeek API."""
        client = self._get_deepseek_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await client.chat.completions.create(
                model=self._orchestration_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"DeepSeek orchestration failed: {e}")
            raise RuntimeError(f"DeepSeek API error: {e}") from e

    # ========================================================================
    # Tool Calling API (Constrained generation for structured outputs)
    # ========================================================================

    async def generate_constrained(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate structured output using the tool model (MiniMax).

        Use this for:
        - Constrained JSON generation (questions, goals, scripts)
        - Tool call parameter extraction
        - Any structured output that must match a schema

        Args:
            prompt: The user prompt
            schema: JSON Schema for output validation
            system_prompt: Optional system instructions
            temperature: Sampling temperature (very low for strict schemas)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Parsed JSON object matching the schema

        Raises:
            RuntimeError: If MiniMax API key is not configured or the call fails.
                          Discovery OS requires both DeepSeek AND MiniMax to be fully
                          configured. Set MINIMAX_API_KEY in your .env file.
        """
        if self._tool_provider == "minimax":
            if not self.config.MINIMAX_API_KEY:
                raise RuntimeError(
                    "Discovery OS requires a working MiniMax API key for constrained generation. "
                    "Set MINIMAX_API_KEY in your .env file to proceed."
                )
            return await self._generate_minimax(
                prompt, schema, system_prompt, temperature, max_tokens, **kwargs
            )
        else:
            raise ValueError(f"Unsupported tool provider: {self._tool_provider}")

    def _extract_json_from_content(self, content: str) -> str:
        """Extract JSON from content that may contain markdown or extra text.

        Handles:
        - Markdown code blocks (```json ... ``` or ``` ... ```)
        - Mixed content (text before/after JSON)
        - Plain JSON

        Returns:
            Extracted JSON string ready for parsing
        """
        # Log raw content for debugging
        logger.debug(f"MiniMax raw content (first 500 chars): {content[:500]}")

        # Try to extract from markdown code block first
        if "```" in content:
            # Match ```json...``` or ```...```
            pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                logger.debug(f"Extracted from markdown: {extracted[:200]}")
                return extracted

        # Try to find JSON object boundaries { ... }
        start = content.find("{")
        if start != -1:
            # Find matching closing brace
            depth = 0
            for i in range(start, len(content)):
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        extracted = content[start:i+1]
                        logger.debug(f"Extracted JSON object: {extracted[:200]}")
                        return extracted

        # Try to find JSON array boundaries [ ... ]
        start = content.find("[")
        if start != -1:
            depth = 0
            for i in range(start, len(content)):
                if content[i] == "[":
                    depth += 1
                elif content[i] == "]":
                    depth -= 1
                    if depth == 0:
                        extracted = content[start:i+1]
                        logger.debug(f"Extracted JSON array: {extracted[:200]}")
                        return extracted

        # Fallback: return stripped content and hope for the best
        return content.strip()

    async def _generate_minimax(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate constrained output using MiniMax via LiteLLM."""
        self._ensure_minimax_ready()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            import litellm  # noqa: PLC0415 — lazy import (optional dependency)
            # LiteLLM supports response_format for JSON mode
            response = await asyncio.to_thread(
                litellm.completion,
                model=f"minimax/{self._tool_model}",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                api_key=self.config.MINIMAX_API_KEY,
                **kwargs,
            )

            content = response.choices[0].message.content or "{}"

            # Extract JSON from potentially mixed content
            json_str = self._extract_json_from_content(content)

            # Parse JSON
            parsed = json.loads(json_str)

            # MiniMax sometimes wraps the result in an array — unwrap it
            if isinstance(parsed, list):
                if parsed and isinstance(parsed[0], dict):
                    logger.warning("MiniMax returned a JSON array; unwrapping first element")
                    parsed = parsed[0]
                else:
                    # List of strings — retry with a stronger instruction
                    logger.warning(
                        "MiniMax returned a JSON array of non-dicts (%s); retrying with explicit dict instruction",
                        json_str[:100],
                    )
                    retry_messages = list(messages) + [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was a JSON array, but I need a single JSON object (dict). "
                                "Please respond again with ONLY a JSON object enclosed in curly braces {}."
                            ),
                        },
                    ]
                    retry_response = await asyncio.to_thread(
                        litellm.completion,
                        model=f"minimax/{self._tool_model}",
                        messages=retry_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format={"type": "json_object"},
                        api_key=self.config.MINIMAX_API_KEY,
                        **kwargs,
                    )
                    retry_content = retry_response.choices[0].message.content or "{}"
                    retry_json_str = self._extract_json_from_content(retry_content)
                    parsed = json.loads(retry_json_str)
                    if isinstance(parsed, list):
                        raise RuntimeError(
                            f"MiniMax returned a JSON array with no dict element after retry: {retry_json_str[:200]}"
                        )

            # Basic schema validation (keys exist)
            required = schema.get("required", [])
            for key in required:
                if key not in parsed:
                    logger.warning(f"MiniMax output missing required key: {key}")
                    parsed[key] = None  # Fallback to prevent crashes

            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"MiniMax returned invalid JSON: {e}")
            logger.error(f"Raw content: {content}")
            logger.error(f"Extracted JSON string: {json_str if 'json_str' in locals() else 'N/A'}")
            raise RuntimeError(f"MiniMax JSON decode error: {e}") from e
        except Exception as e:
            logger.error(f"MiniMax constrained generation failed: {e}")
            raise RuntimeError(f"MiniMax API error: {e}") from e

    # ========================================================================
    # Configuration Management
    # ========================================================================

    def get_orchestration_model(self) -> str:
        """Get the current orchestration model identifier."""
        return f"{self._orchestration_provider}/{self._orchestration_model}"

    def get_tool_model(self) -> str:
        """Get the current tool calling model identifier."""
        return f"{self._tool_provider}/{self._tool_model}"

    def set_orchestration_model(self, provider: str, model: str):
        """Change the orchestration model (e.g., switch to local DeepSeek).

        Args:
            provider: Provider name (e.g., "deepseek", "local")
            model: Model identifier (e.g., "deepseek-reasoner", "deepseek-r1-70b.gguf")
        """
        logger.info(f"Switching orchestration model: {provider}/{model}")
        self._orchestration_provider = provider
        self._orchestration_model = model
        # Clear cached client if switching providers
        if provider != "deepseek":
            self._deepseek_client = None
        self._validate_configuration()

    def set_tool_model(self, provider: str, model: str):
        """Change the tool calling model (e.g., switch to local MiniMax).

        Args:
            provider: Provider name (e.g., "minimax", "local")
            model: Model identifier (e.g., "MiniMax-M2.5", "minimax-text-01.gguf")
        """
        logger.info(f"Switching tool model: {provider}/{model}")
        self._tool_provider = provider
        self._tool_model = model
        # Clear cached client state
        if provider != "minimax":
            self._minimax_client_ready = False
        self._validate_configuration()


# ============================================================================
# Singleton Management
# ============================================================================

_discovery_llm_service: Optional[DiscoveryLLMService] = None


def get_discovery_llm_service() -> DiscoveryLLMService:
    """Get or create the singleton DiscoveryLLMService.

    This service is completely independent from the global LLMService.
    It maintains its own configuration and API clients.
    """
    global _discovery_llm_service
    if _discovery_llm_service is None:
        from app.core.config import settings
        _discovery_llm_service = DiscoveryLLMService(settings)
        logger.info(
            f"DiscoveryLLMService initialized — "
            f"Orchestration: {_discovery_llm_service.get_orchestration_model()}, "
            f"Tools: {_discovery_llm_service.get_tool_model()}"
        )
    return _discovery_llm_service
