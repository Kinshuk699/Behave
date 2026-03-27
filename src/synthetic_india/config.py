"""Central configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PERSONAS_DIR = DATA_DIR / "personas"
RUNS_DIR = DATA_DIR / "runs"


@dataclass(frozen=True)
class LLMConfig:
    eval_model: str = field(default_factory=lambda: os.getenv("EVAL_MODEL", "claude-haiku-3-20250307"))
    creative_analysis_model: str = field(
        default_factory=lambda: os.getenv("CREATIVE_ANALYSIS_MODEL", "claude-sonnet-4-20250514")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    recommendation_model: str = field(
        default_factory=lambda: os.getenv("RECOMMENDATION_MODEL", "claude-sonnet-4-20250514")
    )
    critic_model: str = field(
        default_factory=lambda: os.getenv("CRITIC_MODEL", "claude-sonnet-4-20250514")
    )
    reflection_model: str = field(
        default_factory=lambda: os.getenv("REFLECTION_MODEL", "claude-haiku-3-20250307")
    )
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""), repr=False)
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""), repr=False)


@dataclass(frozen=True)
class MemoryConfig:
    recency_weight: float = field(
        default_factory=lambda: float(os.getenv("MEMORY_RECENCY_WEIGHT", "1.0"))
    )
    relevance_weight: float = field(
        default_factory=lambda: float(os.getenv("MEMORY_RELEVANCE_WEIGHT", "1.0"))
    )
    importance_weight: float = field(
        default_factory=lambda: float(os.getenv("MEMORY_IMPORTANCE_WEIGHT", "1.0"))
    )
    recency_decay: float = field(
        default_factory=lambda: float(os.getenv("MEMORY_RECENCY_DECAY", "0.99"))
    )
    reflection_threshold: float = 50.0  # cumulative importance before reflection triggers
    max_retrieval_results: int = 10
    full_dump_threshold: int = 50  # per-category node count before switching to scored retrieval
    include_cross_reflections: bool = True  # include cross-category reflections in consumption


@dataclass(frozen=True)
class PipelineConfig:
    default_cohort_size: int = field(
        default_factory=lambda: int(os.getenv("DEFAULT_COHORT_SIZE", "20"))
    )
    max_personas: int = field(
        default_factory=lambda: int(os.getenv("MAX_PERSONAS", "50"))
    )


def get_llm_config() -> LLMConfig:
    return LLMConfig()


def get_memory_config() -> MemoryConfig:
    return MemoryConfig()


def get_pipeline_config() -> PipelineConfig:
    return PipelineConfig()
