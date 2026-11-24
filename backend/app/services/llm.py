"""
LLM service: Official Google GenAI SDK integration with streaming and circuit breaker.
"""

import asyncio
import concurrent.futures
import json
import logging
import re
import time
from typing import AsyncGenerator, Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def _run_sync(coro):
    """Run an async coroutine synchronously, even inside an existing event loop."""
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


class LLMServiceError(Exception):
    """Raised when the LLM service encounters an error."""
    pass


class LLMService:
    """Manages Gemini API calls using google-genai with failover, circuit breaker, and streaming."""

    def __init__(self, api_key: str, model_name: str = "gemini-3.8-flash"):
        if not api_key:
            raise LLMServiceError("Gemini API key is not configured")
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)
        # Tracks timestamp until which a model is cooled down (e.g. rate-limited)
        self._model_cooldown: dict[str, float] = {}
        self.cooldown_seconds: float = 60.0

    def _get_candidate_models(self) -> list[str]:
        """Return prioritized list of candidate models, leading with ultra-fast flash-lite models."""
        candidates = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite"]
        if self.model_name not in candidates:
            candidates.insert(0, self.model_name)
        for fallback in [
            "gemini-flash-latest",
            "gemini-3.8-flash",
            "gemini-pro-latest",
        ]:
            if fallback not in candidates:
                candidates.append(fallback)
        return candidates

    def _is_cooled_down(self, model_id: str) -> bool:
        """Check if model is currently in a cooldown period."""
        cool_until = self._model_cooldown.get(model_id, 0.0)
        return time.time() < cool_until

    def _trip_circuit(self, model_id: str, duration: Optional[float] = None):
        """Put model in cooldown."""
        dur = duration if duration is not None else self.cooldown_seconds
        self._model_cooldown[model_id] = time.time() + dur
        logger.warning(f"Circuit breaker tripped for {model_id} for {dur:.0f}s")

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 4096,
    ) -> str:
        """Generate text synchronously using Gemini with multi-model fallback."""
        return _run_sync(
            self._async_generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        )

    async def _async_generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 4096,
    ) -> str:
        candidate_models = self._get_candidate_models()
        last_err = None

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction if system_instruction else None,
        )

        for model_id in candidate_models:
            if self._is_cooled_down(model_id):
                continue

            for attempt in range(2):
                try:
                    response = await asyncio.wait_for(
                        self.client.aio.models.generate_content(
                            model=model_id,
                            contents=prompt,
                            config=config,
                        ),
                        timeout=6.0,
                    )

                    if response and response.text:
                        self.model_name = model_id
                        return response.text
                except Exception as e:
                    err_str = str(e)
                    last_err = e

                    if isinstance(e, asyncio.TimeoutError):
                        self._trip_circuit(model_id, 30.0)
                        logger.warning(f"Timeout on model {model_id} after 6s; trying next model")
                        break

                    if "503" in err_str or "unavailable" in err_str.lower() or "high demand" in err_str.lower():
                        self._trip_circuit(model_id, 30.0)
                        break

                    if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                        self._trip_circuit(model_id, 45.0)
                        break

                    if "404" in err_str or "not found" in err_str.lower() or "not supported" in err_str.lower():
                        self._trip_circuit(model_id, 300.0)
                        break

                    if "api_key" in err_str.lower() or "api key" in err_str.lower():
                        raise LLMServiceError(f"Gemini API key error: {e}")

                    logger.warning(f"Generation attempt {attempt+1} failed on {model_id}: {e}")

        if last_err and ("429" in str(last_err) or "quota" in str(last_err).lower()):
            raise LLMServiceError("Gemini rate limit reached. Please wait a few seconds before trying again.")

        raise LLMServiceError(f"Gemini generation failed on candidate models: {last_err}")

    async def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Generate text asynchronously with token streaming and failover."""
        candidate_models = self._get_candidate_models()
        last_err = None

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction if system_instruction else None,
        )

        for model_id in candidate_models:
            if self._is_cooled_down(model_id):
                continue

            try:
                stream = await self.client.aio.models.generate_content_stream(
                    model=model_id,
                    contents=prompt,
                    config=config,
                )

                emitted_any = False
                async for chunk in stream:
                    if chunk.text:
                        emitted_any = True
                        yield chunk.text

                if emitted_any:
                    self.model_name = model_id
                    return

            except Exception as e:
                err_str = str(e)
                last_err = e
                if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                    self._trip_circuit(model_id, 45.0)
                elif "404" in err_str or "not found" in err_str.lower():
                    self._trip_circuit(model_id, 300.0)
                else:
                    logger.warning(f"Stream failed on {model_id}: {e}")

        if last_err and ("429" in str(last_err) or "quota" in str(last_err).lower()):
            raise LLMServiceError("Gemini rate limit reached. Please wait a few seconds before trying again.")

        raise LLMServiceError(f"Gemini streaming failed on candidate models: {last_err}")

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 8192,
    ) -> dict | list:
        """Generate and parse JSON from Gemini."""
        return _run_sync(
            self._async_generate_json(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        )

    async def _async_generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 8192,
    ) -> dict | list:
        candidate_models = self._get_candidate_models()

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction if system_instruction else None,
            response_mime_type="application/json",
        )

        raw = None
        for model_id in candidate_models:
            if self._is_cooled_down(model_id):
                continue
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=model_id,
                        contents=prompt,
                        config=config,
                    ),
                    timeout=20.0,
                )
                if response and response.text:
                    raw = response.text
                    break
            except Exception as e:
                err_str = str(e)
                if isinstance(e, asyncio.TimeoutError):
                    self._trip_circuit(model_id, 30.0)
                    logger.warning(f"Timeout on JSON model {model_id} after 20s; trying next model")
                elif "503" in err_str or "unavailable" in err_str.lower() or "429" in err_str:
                    self._trip_circuit(model_id, 30.0)
                continue

        if raw is None:
            raw = await self._async_generate(prompt, system_instruction, temperature, max_output_tokens)

        # Parse JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```json" in raw:
            start = raw.index("```json") + 7
            end = raw.index("```", start)
            try:
                return json.loads(raw[start:end].strip())
            except json.JSONDecodeError:
                pass
        elif "```" in raw:
            start = raw.index("```") + 3
            end = raw.index("```", start)
            try:
                return json.loads(raw[start:end].strip())
            except json.JSONDecodeError:
                pass

        raise LLMServiceError(
            f"Failed to parse JSON from Gemini response. Raw output starts with: {raw[:200]}"
        )
