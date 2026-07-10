"""
finfluencer.core.contracts
===========================

Inter-module Pydantic schemas.

Every function that crosses a subpackage boundary accepts and returns
values conforming to schemas in this module. Contract violations are
:class:`SchemaContractError` — bugs in a producer module, never user
error.

Two categories of schema live here:

1. **Configuration schemas** — mirror the shape of ``settings.yaml`` and
   ``analysts.yaml``. Loaded once at startup by
   :func:`finfluencer.core.config.load_settings`.

2. **Data-record schemas** — describe rows in Parquet frames passed
   between stages. Serve as documentation and, in strict mode, as
   validators (opt-in per stage because per-row validation is costly).

Design conventions
------------------
* ``model_config = ConfigDict(extra="forbid")`` on every model — unknown
  keys are rejected. This catches YAML typos.
* ``Enum`` for closed vocabularies (expertise class, replication stage,
  LLM provider). Values live in code, not string comparisons.
* ``Path`` for filesystem paths; Pydantic converts strings automatically.
* Optional fields default to ``None`` explicitly, not ``= None``
  implicit-optional inference.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# =============================================================================
# Enumerations (controlled vocabularies)
# =============================================================================
#
# NOTE ON PROVIDER KEYS
# ---------------------
# Language and platform provider keys are deliberately NOT closed enums.
# They are declared as ``str`` fields with pattern validation. Actual
# existence checking happens at runtime via ``core.registry.get()``,
# which raises :class:`ProviderNotFoundError` with the list of registered
# alternatives when a key is missing.
#
# This is what makes the LanguageProvider and PlatformProvider abstractions
# genuinely pluggable: registering a new provider (e.g. English, Arabic,
# German, TikTok, Reddit) requires only adding a subclass under
# ``providers/*/`` (or a third-party plugin package advertising an entry
# point). No change to :mod:`core.contracts` is required. This satisfies
# the v2.1 pluggability contract (§H, §I of ARCHITECTURE_v2.1).
#
# Analytical enums (ExpertiseClass, TopicTier, SentimentClass,
# AffectTarget) remain closed because they belong to the pre-registered
# analytical scheme; extending them would change the study's hypotheses.

#: Regex constraining valid provider keys: lowercase ASCII letters,
#: digits, and underscores. Any subclass name that matches may register.
_PROVIDER_KEY_PATTERN: str = r"^[a-z][a-z0-9_]*$"


class ExpertiseClass(str, Enum):
    """Analyst expertise controlled vocabulary. See analysts.yaml."""
    technical_macro = "technical_macro"
    macro_political = "macro_political"
    long_horizon = "long_horizon"
    equity_portfolio = "equity_portfolio"


class ReplicationStage(str, Enum):
    """Study reproducibility stage; controls strictness."""
    exploratory = "exploratory"
    internal = "internal"
    submission = "submission"
    publication = "publication"


class ReplicationTarget(str, Enum):
    """Where the replication package is deposited."""
    zenodo = "zenodo"
    local = "local"


class LLMProvider(str, Enum):
    """Backend for optional LLM integration."""
    openai = "openai"
    anthropic = "anthropic"
    offline_stub = "offline_stub"


class MatchMode(str, Enum):
    """Dictionary matching mode."""
    token = "token"
    substring = "substring"


class TopicTier(str, Enum):
    """Four-tier macro-thematic taxonomy for the pooled BERTopic solution."""
    finance = "finance"
    trust = "trust"
    ritual = "ritual"
    residual = "residual"


class SentimentClass(str, Enum):
    """Binary sentiment label from the primary classifier."""
    positive = "positive"
    negative = "negative"


class AffectTarget(str, Enum):
    """Target of affect (Methods §3.4.2)."""
    analyst = "analyst"
    market = "market"
    both = "both"
    neither = "neither"


# =============================================================================
# Configuration schemas — settings.yaml
# =============================================================================


class _Base(BaseModel):
    """All contracts forbid unknown keys."""
    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)


class ObservationWindow(_Base):
    start: date
    end: date

    @model_validator(mode="after")
    def _end_after_start(self) -> "ObservationWindow":
        if self.end < self.start:
            raise ValueError("observation_window.end must be >= start")
        return self


class StudyMeta(_Base):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    root_seed: int = Field(ge=0)
    description: str
    observation_window: ObservationWindow


class ProvidersConfig(_Base):
    """Provider selection.

    ``language`` and ``platform`` are validated as pattern-constrained
    strings; existence checking is deferred to registry lookup at
    runtime. This preserves pluggability for future language and
    platform providers (see the note above the enum block).
    """
    language: Annotated[str, Field(pattern=_PROVIDER_KEY_PATTERN, min_length=1, max_length=32)]
    platform: Annotated[str, Field(pattern=_PROVIDER_KEY_PATTERN, min_length=1, max_length=32)]


class QuotaConfig(_Base):
    daily_units: int = Field(ge=1)
    safety_margin: int = Field(ge=0)


class CollectionConfig(_Base):
    max_videos_per_analyst: int = Field(ge=1)
    max_comments_per_video: int = Field(ge=1)
    max_comments_per_user_per_video: int = Field(ge=1)
    shorts_max_duration_sec: int = Field(ge=0)
    promo_keywords: list[str] = Field(default_factory=list)
    quota: QuotaConfig


class PreprocessingConfig(_Base):
    min_tokens: int = Field(ge=1)
    jaccard_dup_threshold: float = Field(ge=0.0, le=1.0)
    stopwords_augment_path: Path | None = None


class ModelReference(_Base):
    name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    max_length: int | None = None


class TargetOfAffectConfig(_Base):
    enabled: bool
    base_model: str
    base_revision: str
    heads: list[str]
    target_labels: list[str]
    fine_tune_checkpoint: Path | None = None


class SentimentConfig(_Base):
    primary_model: ModelReference
    batch_size: int = Field(ge=1)
    pseudo_neutral_band: tuple[float, float]
    target_of_affect: TargetOfAffectConfig

    @field_validator("pseudo_neutral_band")
    @classmethod
    def _band_valid(cls, v: tuple[float, float]) -> tuple[float, float]:
        lo, hi = v
        if not (0.0 <= lo < hi <= 1.0):
            raise ValueError(
                f"pseudo_neutral_band must satisfy 0.0 <= lo < hi <= 1.0, got {v}",
            )
        return v


class UMAPConfig(_Base):
    n_neighbors: int = Field(ge=2)
    n_components: int = Field(ge=1)
    min_dist: float = Field(ge=0.0)
    metric: str
    low_memory: bool = True


class HDBSCANConfig(_Base):
    min_cluster_size: int = Field(ge=2)
    min_samples: int = Field(ge=1)
    metric: str
    cluster_selection_method: str


class TopicConfigurations(_Base):
    within_analyst: bool
    pooled: bool


class TopicsConfig(_Base):
    embedding_model: ModelReference
    umap: UMAPConfig
    hdbscan: HDBSCANConfig
    configurations: TopicConfigurations
    merge_similarity_threshold: float = Field(ge=0.0, le=1.0)
    reduce_outliers: bool
    quality_metrics: list[str]


class DictionariesConfig(_Base):
    files: dict[str, Path]
    match_mode: MatchMode
    case_fold: bool


class StatisticsConfig(_Base):
    alpha: float = Field(gt=0.0, lt=1.0)
    bonferroni_within_family: bool
    fdr_method: str
    permutations: int = Field(ge=1)
    post_hoc_pairwise: str


class BehaviouralIndicesConfig(_Base):
    panic_rolling_window: int = Field(ge=1)
    herding_variance_threshold: float = Field(ge=0.0)
    loss_aversion_lag_weeks: int = Field(ge=0)


class OutputPaths(_Base):
    data_raw: Path
    data_interim: Path
    data_processed: Path
    data_external: Path
    cache: Path
    logs: Path
    checkpoints: Path
    tables: Path
    figures: Path
    appendices: Path
    reports: Path
    manuscript: Path
    replication: Path


class FigureOutput(_Base):
    dpi: int = Field(ge=72)
    formats: list[str]
    style: str
    colourblind_safe: bool


class TableOutput(_Base):
    formats: list[str]
    decimal_places: int = Field(ge=0)
    thousands_separator: bool


class OutputConfig(_Base):
    paths: OutputPaths
    figures: FigureOutput
    tables: TableOutput


class EthicsConfig(_Base):
    retention_days: int = Field(ge=0)
    sensitive_topic_detection: bool
    strict_reproducibility: bool


class ZenodoConfig(_Base):
    community: str | None = None
    sandbox: bool
    embargo_until: date | None = None


class RestrictedTierConfig(_Base):
    provider: str | None = None


class ReplicationConfig(_Base):
    stage: ReplicationStage
    target: ReplicationTarget
    zenodo: ZenodoConfig
    include_model_weights: bool
    restricted_tier: RestrictedTierConfig


class LLMConfig(_Base):
    enabled: bool
    provider: LLMProvider
    require_human_validation: bool
    model: str | None = None
    prompt_version: str = Field(pattern=r"^v\d+\.\d+\.\d+$")


class Settings(_Base):
    """Top-level settings; the shape of ``settings.yaml``."""
    study: StudyMeta
    providers: ProvidersConfig
    collection: CollectionConfig
    preprocessing: PreprocessingConfig
    sentiment: SentimentConfig
    topics: TopicsConfig
    dictionaries: DictionariesConfig
    statistics: StatisticsConfig
    behavioural_indices: BehaviouralIndicesConfig
    output: OutputConfig
    ethics: EthicsConfig
    replication: ReplicationConfig
    llm: LLMConfig


# =============================================================================
# analysts.yaml
# =============================================================================


class AnalystRecord(_Base):
    key: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=1)
    handle: str
    channel_id: str | None = None
    expertise_class: ExpertiseClass
    expertise_description: str
    pilot: bool
    channel_url: str | None = None
    verified_at: date | None = None


class AnalystRoster(_Base):
    """Top-level analysts.yaml container."""
    analysts: list[AnalystRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_roster(self) -> "AnalystRoster":
        keys = [a.key for a in self.analysts]
        if len(keys) != len(set(keys)):
            raise ValueError("analyst keys must be unique")
        pilots = [a for a in self.analysts if a.pilot]
        if len(pilots) != 1:
            raise ValueError(
                f"exactly one analyst must have pilot=true, found {len(pilots)}",
            )
        return self


# =============================================================================
# Data-record schemas (for Parquet frames)
# =============================================================================


class VideoRecord(_Base):
    """One row in the video metadata frame."""
    analyst_key: str
    video_id: str
    published_at: str  # ISO 8601 UTC
    title: str
    description: str = ""
    duration_sec: int = Field(ge=0)
    views: int = Field(ge=0)
    likes: int | None = None
    comment_count: int = Field(ge=0)
    made_for_kids: bool = False
    category_id: str = ""
    eligible: bool = True
    exclusion_reason: str = ""
    selected: bool = False


class CommentRecord(_Base):
    """One row in the analytical comment frame (post-preprocessing).

    Raw text is retained in ``text_raw`` for internal validation only and
    is stripped before release (see Module L Tier 1 requirements).
    """
    analyst_key: str
    video_id: str
    comment_id: str
    commenter_hash: str  # anonymised
    posted_date: str  # YYYY-MM-DD (day-truncated, Methods §3.11)
    text_raw: str
    text_clean: str
    tokens: list[str]
    n_tokens: int = Field(ge=0)
    emojis: list[str] = Field(default_factory=list)
    likes: int = Field(ge=0)


class SentimentRecord(_Base):
    """One row in the sentiment output frame."""
    comment_id: str
    sentiment_prob: float = Field(ge=0.0, le=1.0)
    sentiment_class: SentimentClass
    sentiment_pseudo_neutral: bool
    sentiment_target: AffectTarget | None = None
    sentiment_market_directed: float | None = Field(default=None, ge=0.0, le=1.0)


class TopicRecord(_Base):
    """One row in the topic-assignment frame (per BERTopic configuration)."""
    comment_id: str
    topic_id: int  # -1 for outlier
    topic_prob: float = Field(ge=0.0, le=1.0)
    topic_tier: TopicTier | None = None
    configuration: str  # "within_analyst" or "pooled"


class DictionaryRecord(_Base):
    """Binary category indicators per comment (Family I/II/III collapsed).

    Column names correspond to the 13 categories in the variable table.
    Rendered flexibly as dict[str, int] to keep schema evolution simple.
    """
    comment_id: str
    indicators: dict[str, int]  # each value 0 or 1


# =============================================================================
# Public API
# =============================================================================


__all__ = [
    # Enums
    "ExpertiseClass",
    "ReplicationStage", "ReplicationTarget", "LLMProvider",
    "MatchMode", "TopicTier", "SentimentClass", "AffectTarget",
    # Settings sub-schemas
    "ObservationWindow", "StudyMeta", "ProvidersConfig",
    "QuotaConfig", "CollectionConfig", "PreprocessingConfig",
    "ModelReference", "TargetOfAffectConfig", "SentimentConfig",
    "UMAPConfig", "HDBSCANConfig", "TopicConfigurations", "TopicsConfig",
    "DictionariesConfig", "StatisticsConfig", "BehaviouralIndicesConfig",
    "OutputPaths", "FigureOutput", "TableOutput", "OutputConfig",
    "EthicsConfig", "ZenodoConfig", "RestrictedTierConfig", "ReplicationConfig",
    "LLMConfig",
    # Top-level
    "Settings", "AnalystRecord", "AnalystRoster",
    # Data records
    "VideoRecord", "CommentRecord", "SentimentRecord",
    "TopicRecord", "DictionaryRecord",
]
