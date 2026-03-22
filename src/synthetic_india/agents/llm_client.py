"""
LLM client wrapper — handles both Anthropic and OpenAI calls
with cost tracking and structured output parsing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import anthropic
import openai

from synthetic_india.config import LLMConfig, get_llm_config


@dataclass
class LLMResponse:
    """Standardized LLM response with cost tracking."""
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float

    def parse_json(self) -> dict[str, Any]:
        """Extract JSON from the response, handling markdown code blocks."""
        text = self.content.strip()
        if text.startswith("```"):
            # Strip markdown code fence
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            text = text.strip()
        return json.loads(text)


# Approximate cost per 1M tokens (as of early 2026)
COST_TABLE = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-3-20250307": {"input": 0.25, "output": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    costs = COST_TABLE.get(model, {"input": 1.0, "output": 3.0})
    return (prompt_tokens * costs["input"] + completion_tokens * costs["output"]) / 1_000_000


async def call_anthropic(
    prompt: str,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    config: Optional[LLMConfig] = None,
) -> LLMResponse:
    """Call Anthropic's Claude API."""
    config = config or get_llm_config()
    model = model or config.eval_model
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)

    start = time.perf_counter()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    latency = (time.perf_counter() - start) * 1000

    content = response.content[0].text
    prompt_tokens = response.usage.input_tokens
    completion_tokens = response.usage.output_tokens

    return LLMResponse(
        content=content,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=_estimate_cost(model, prompt_tokens, completion_tokens),
        latency_ms=latency,
    )


async def call_openai(
    prompt: str,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    config: Optional[LLMConfig] = None,
) -> LLMResponse:
    """Call OpenAI's API."""
    config = config or get_llm_config()
    model = model or "gpt-4o-mini"
    client = openai.AsyncOpenAI(api_key=config.openai_api_key)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    start = time.perf_counter()
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=messages,
    )
    latency = (time.perf_counter() - start) * 1000

    choice = response.choices[0]
    content = choice.message.content or ""
    prompt_tokens = response.usage.prompt_tokens if response.usage else 0
    completion_tokens = response.usage.completion_tokens if response.usage else 0

    return LLMResponse(
        content=content,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=_estimate_cost(model, prompt_tokens, completion_tokens),
        latency_ms=latency,
    )


async def get_embedding(
    text: str,
    model: Optional[str] = None,
    config: Optional[LLMConfig] = None,
) -> list[float]:
    """Get an embedding vector from OpenAI."""
    config = config or get_llm_config()
    model = model or config.embedding_model
    client = openai.AsyncOpenAI(api_key=config.openai_api_key)

    response = await client.embeddings.create(
        model=model,
        input=text,
    )
    return response.data[0].embedding
