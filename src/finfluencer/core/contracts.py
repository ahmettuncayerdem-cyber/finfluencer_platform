"""
finfluencer.core.contracts
===========================

Inter-module Pydantic schemas.

Every function that crosses a subpackage boundary accepts and returns
values conforming to schemas in this module. Contract violations are
:class:`SchemaContractError` - bugs in a producer module, never user
error.

Two categories of schema live here:

1. **Configuration schemas** - mirror the shape of ``settings.yaml`` and
   ``analysts.yaml``. Loaded once at startup by
   :func:`finfluencer.core.config.load_settings`.

2. **Data-record schemas** - describe rows in Parquet frames passed
   between stages. Serve as documentation and, in strict mode, as
   validators (opt-in per stage because per-row validation is costly).

Design conventions
------------------
* ``model_config = ConfigDict(extra="forbid")`` on every model - unknown
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
# the v2.1 pluggability contract (Sections H, I of ARCHITECTURE_v2.1).
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
    """Target of affect (Methods Section 3.4.2)."""
    analyst = "analyst"
    market = "market"
    both = "both"
    neither = "neither"


# =============================================================================
# Configuration schemas - settings.yaml
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
    posted_date: str  # YYYY-MM-DD (day-truncated, Methods Section 3.11)
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
    """One row in the topic-assignment frame (per BERTopic configuration).

    ``scope_id`` (Phase 3, entity-centric migration): additive as of
    Migration Step 3.1 - see ``AnalysisScope`` below. ``None`` for every
    row today, since :mod:`finfluencer.topics.pipeline` still constructs
    rows via ``configuration``/``analyst_key`` only; a future migration
    step (3.2) will populate it and, per the migration plan's
    backward-compatibility commitment, continue setting ``configuration``
    for one full release via ``AnalysisScope.legacy_configuration_label()``.
    """
    comment_id: str
    topic_id: int  # -1 for outlier
    topic_prob: float = Field(ge=0.0, le=1.0)
    topic_tier: TopicTier | None = None
    configuration: str  # "within_analyst" or "pooled"
    scope_id: str | None = None  # Phase 3 - not yet populated (Step 3.1 status)
    # Populated from BERTopic's own get_topic_info() name (e.g.
    # "3_borsa_faiz_piyasa") when the fitted/loaded model exposes it;
    # None when unavailable (e.g. injected test doubles). Manual/
    # LLM-assisted semantic relabeling (e.g. "faiz beklentisi") remains
    # future work and would overwrite this value, not replace the field.
    topic_label: str | None = None


class DictionaryRecord(_Base):
    """Binary category indicators per comment (Family I/II/III collapsed).

    Column names correspond to the 13 categories in the variable table.
    Rendered flexibly as dict[str, int] to keep schema evolution simple.
    """
    comment_id: str
    indicators: dict[str, int]  # each value 0 or 1


class EmbeddingIndexRecord(_Base):
    """One row in ``embeddings_index.parquet`` (Phase 2.1).

    Maps a comment to its cached embedding vector. ``embedding_hash`` is
    the SHA-256 of ``(text_clean, model_name, revision, device)`` - the
    same text encoded on CPU vs GPU, or with a different model/revision,
    is a cache miss by design (see
    :mod:`finfluencer.embeddings.pipeline`). Additive to the schema;
    does not touch ``comments.parquet``.
    """
    comment_id: str
    embedding_hash: str
    embedding_path: str
    model_name: str
    revision: str
    dimension: int = Field(ge=1)


class TopicSentimentRecord(_Base):
    """One row in the topic x sentiment cross-analysis frame (Phase 2.4).

    Descriptive aggregation over the joined ``topics.parquet`` x
    ``sentiment.parquet`` frames, grouped by ``(configuration, topic_id)``
    and, for ``within_analyst``, additionally by ``analyst_key``. Purely
    descriptive counts/ratios - formal significance testing (chi-square,
    Bonferroni/FDR correction) belongs to the later statistics module
    (see :class:`StatisticsConfig`) and is out of scope here.
    """
    configuration: str  # "pooled" or "within_analyst"
    analyst_key: str | None = None  # populated for within_analyst only
    scope_id: str | None = None  # populated by analysis/topic_sentiment.py (Step 3.4);
    # carried through from topics.parquet's own scope_id, never re-derived here
    topic_id: int  # -1 for outlier
    topic_label: str | None = None
    n_comments: int = Field(ge=0)
    n_positive: int = Field(ge=0)
    n_negative: int = Field(ge=0)
    n_pseudo_neutral: int = Field(ge=0)
    positive_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_sentiment_prob: float | None = Field(default=None, ge=0.0, le=1.0)


class TopicEvolutionRecord(_Base):
    """One row in the topic evolution frame (Phase 2.5).

    Produced by BERTopic's own ``topics_over_time()`` applied to an
    already-fitted/cached model (see
    :mod:`finfluencer.topics.pipeline`). Same model, same corpus
    fingerprint as the topics stage - this is a read-only downstream
    view, never a refit.
    """
    configuration: str  # "pooled" or "within_analyst"
    analyst_key: str | None = None  # populated for within_analyst only
    scope_id: str | None = None  # Phase 3 - not yet populated (Step 3.1 status)
    topic_id: int  # -1 for outlier
    topic_label: str | None = None  # stable label from topics.parquet
    time_bin: str  # representative ISO timestamp for this bin
    frequency: int = Field(ge=0)
    bin_words: list[str] = Field(default_factory=list)  # bin-specific top words


# =============================================================================
# Phase 0: entity-centric platform migration (additive, non-breaking)
# =============================================================================
#
# Generalizes ``analyst_key`` (a fixed, single-owner partition) into
# ``entity_key`` (a many-to-many label attached to a video via
# ``EntityVideoLinkRecord``). None of the schemas below replace
# ``AnalystRecord``/``VideoRecord``/``CommentRecord`` above - they are
# additive, produced by a one-time migration/backfill step
# (:mod:`finfluencer.migration.backfill_entity_model`), and exist
# alongside the current analyst-centric frames until downstream stages
# are migrated to consume them.
#
# See ``entity_centric_platform_architecture.md`` for the full design
# rationale (Sections 2-3): a video/comment exists exactly once;
# ``EntityVideoLinkRecord`` is the sole place the entity<->video
# many-to-many relationship lives.


class EntityType(str, Enum):
    """Controlled vocabulary for what an ``Entity`` represents.

    ``creator`` generalizes today's ``analyst_key``/``AnalystRecord``.
    The others are the domains this migration is meant to unlock
    (discourse/topic corpora, campaigns, events) without any change to
    collection/processing code - only a new membership resolver.
    """
    creator = "creator"
    topic = "topic"
    campaign = "campaign"
    event = "event"
    custom = "custom"


class EntityRecord(_Base):
    """One row in ``entities.parquet`` (Phase 0).

    ``membership_strategy`` is a key into a registry of resolvers
    (mirrors the existing ``core.registry`` pattern for
    language/platform/embedding/sentiment providers) that populate
    ``EntityVideoLinkRecord`` rows for this entity. ``membership_params``
    is strategy-specific (e.g. ``{"channel_ids": [...]}`` for
    ``creator``; ``{"keywords": [...], "date_range": [...]}`` for
    ``topic``).
    """
    entity_key: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    entity_type: EntityType
    display_name: str = Field(min_length=1)
    description: str = ""
    membership_strategy: str = Field(min_length=1)
    membership_params: dict[str, Any] = Field(default_factory=dict)
    study_id: str = Field(min_length=1)
    created_at: str  # ISO 8601 UTC


class EntityVideoLinkRecord(_Base):
    """One row in ``entity_video_link.parquet`` (Phase 0).

    The sole place the entity<->video many-to-many relationship lives.
    A video referenced by N entities has N rows here and exactly one
    row in ``CanonicalVideoRecord``. ``eligible``/``exclusion_reason``/
    ``selected`` move here from ``VideoRecord`` because they are
    per-entity selection decisions, not intrinsic video properties - the
    same video can be eligible/selected for one entity and not another.
    """
    entity_key: str
    video_id: str
    matched_via: str = Field(min_length=1)
    eligible: bool = True
    exclusion_reason: str = ""
    selected: bool = False
    criteria_version: str = Field(min_length=1)
    linked_at: str  # ISO 8601 UTC


class CanonicalVideoRecord(_Base):
    """One row in ``videos_canonical.parquet`` (Phase 0).

    Video-intrinsic fields only. Exists exactly once per ``video_id``
    regardless of how many entities reference it via
    ``EntityVideoLinkRecord`` - the direct fix for the duplicate-fetch
    behaviour of today's ``analyst_key``-partitioned ``VideoRecord``.
    """
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


class CanonicalCommentRecord(_Base):
    """One row in ``comments_canonical.parquet`` (Phase 0).

    Comment-intrinsic fields only - no ``analyst_key``. A comment
    belongs to exactly one video (YouTube's own model); entity
    attribution is derived transitively via
    ``video_id -> EntityVideoLinkRecord.entity_key``, never stored on
    the comment itself. Exists exactly once per ``comment_id`` - the
    direct fix for the duplicate-row behaviour observed in production
    (144 videos shared across multiple analysts produced ~4,756
    duplicated comment rows under the old schema).
    """
    video_id: str
    comment_id: str
    commenter_hash: str  # anonymised
    posted_date: str  # YYYY-MM-DD (day-truncated)
    text_raw: str
    text_clean: str
    tokens: list[str]
    n_tokens: int = Field(ge=0)
    emojis: list[str] = Field(default_factory=list)
    likes: int = Field(ge=0)


# =============================================================================
# Phase 3: analysis-scope generalization (additive, non-breaking)
# =============================================================================
#
# Migration Step 3.1. Generalizes the ``configuration`` (``"pooled"`` /
# ``"within_analyst"``) + ``analyst_key`` pair on ``TopicRecord`` /
# ``TopicSentimentRecord`` / ``TopicEvolutionRecord`` into a single
# persisted ``AnalysisScope`` reference (``scope_id``). This is the
# direct structural fix for the bug where ``run_topics`` and
# ``run_topic_evolution`` (:mod:`finfluencer.topics.pipeline`) each
# independently re-derive "which comments are in scope" through a
# different join path and can disagree - see
# ``entity_centric_platform_architecture.md`` and
# ``Entity_Centric_Migration_Plan_v2.md`` (Section 4) for the full
# design rationale, and ``AnalysisScope_Impact_Analysis.md`` for the
# traced blast radius across the repository.
#
# Status as of Step 3.1: purely additive. ``AnalysisScope`` is a new
# class; ``scope_id`` was added above as a new, optional
# (default ``None``) field on the three existing records. Nothing in
# :mod:`finfluencer.topics.pipeline` or
# :mod:`finfluencer.analysis.topic_sentiment` sets or reads ``scope_id``
# yet, and :mod:`finfluencer.scope` (``resolve_scope()``) is not called
# by any pipeline stage yet. ``configuration``/``analyst_key`` remain
# the sole fields those stages actually use - existing pipeline
# behavior, existing manuscript outputs, and existing checkpoints are
# therefore unaffected by this step.


class AnalysisScopeType(str, Enum):
    """Controlled vocabulary for what an ``AnalysisScope`` represents.

    ``global_`` (value ``"global"`` - ``global`` alone is a reserved
    Python keyword and cannot be a class attribute name) is the
    pre-migration ``configuration="pooled"`` equivalent: every comment
    in the corpus. ``entity`` with a single ``entity_keys`` member is
    the pre-migration ``configuration="within_analyst"`` equivalent.
    ``entity_set`` and ``filtered`` have no pre-migration equivalent -
    they are new expressiveness this migration unlocks (Phase 4:
    ``topic``/``campaign``/``event`` entity types), not yet reachable
    from any pipeline stage.
    """
    entity = "entity"
    entity_set = "entity_set"
    global_ = "global"
    filtered = "filtered"


class AnalysisScope(_Base):
    """Persisted, content-addressed record of "which comments are in
    scope" for one analysis run.

    Design principle: resolve once, persist, never re-derive. A scope
    is resolved exactly once (see :func:`finfluencer.scope.resolve_scope`,
    not yet wired into any pipeline stage as of Migration Step 3.1) and
    every later reader loads the persisted ``resolved_comment_ids_hash``
    from this record rather than recomputing it independently through
    its own join/filter logic.

    ``scope_id`` is a content hash of this scope's *definition*
    (``scope_type`` + ``entity_keys`` + ``filter_params`` +
    ``criteria_version``) - it identifies *what was asked for*.
    ``resolved_comment_ids_hash`` is a hash of the *resolved membership*
    (the sorted, deduplicated ``comment_id`` list this scope actually
    resolved to at ``resolved_at``) - it identifies *what was found*.
    Keeping these separate means a scope's definition can be looked up
    (``scope_id``) independently of re-verifying its membership hasn't
    drifted (``resolved_comment_ids_hash``), which matters once
    collection can add new comments to an already-analyzed video.
    """
    scope_id: str = Field(min_length=1)
    scope_type: AnalysisScopeType
    entity_keys: list[str] = Field(default_factory=list)
    filter_params: dict[str, Any] = Field(default_factory=dict)
    resolved_comment_ids_hash: str = Field(min_length=1)
    resolved_at: str  # ISO 8601 UTC
    criteria_version: str = Field(min_length=1)

    def legacy_configuration_label(self) -> str:
        """Backward-compatible alias: derive the pre-migration
        ``TopicRecord.configuration`` string (``"pooled"`` or
        ``"within_analyst"``) this scope corresponds to.

        This is the mechanism later migration steps (3.2-3.4) will use
        so that a ``TopicRecord`` row constructed the new way (via
        ``scope_id``) still populates the old ``configuration`` field
        for one full release, per ``Entity_Centric_Migration_Plan_v2.md``
        Section 6's backward-compatibility commitment and
        ``AnalysisScope_Impact_Analysis.md``'s recommendation that the
        alias be built into the contract layer rather than bolted on
        per call site. **Not called by any pipeline code as of Step
        3.1** - `finfluencer.topics.pipeline` still sets `configuration`
        directly and does not construct `AnalysisScope` rows.

        Returns
        -------
        str
            ``"pooled"`` for ``scope_type=global_``; ``"within_analyst"``
            for ``scope_type=entity`` with exactly one member in
            ``entity_keys``.

        Raises
        ------
        ValueError
            If this scope has no pre-migration equivalent - i.e.
            ``scope_type in (entity_set, filtered)``, or ``entity`` with
            zero or more than one ``entity_keys`` member. These
            represent analysis scopes that were not expressible before
            this migration (e.g. Phase 4's multi-entity or
            keyword-filtered scopes) and therefore have no legacy string
            to alias to - callers needing a legacy-compatible output for
            such a scope have a genuine design decision to make, which
            this method deliberately does not make silently on their
            behalf.
        """
        if self.scope_type == AnalysisScopeType.global_:
            return "pooled"
        if self.scope_type == AnalysisScopeType.entity and len(self.entity_keys) == 1:
            return "within_analyst"
        raise ValueError(
            f"AnalysisScope {self.scope_id!r} (scope_type={self.scope_type!r}, "
            f"entity_keys={self.entity_keys!r}) has no pre-migration "
            f"configuration-string equivalent.",
        )


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
    "TopicRecord", "DictionaryRecord", "EmbeddingIndexRecord",
    "TopicSentimentRecord", "TopicEvolutionRecord",
    # Phase 0: entity-centric platform migration
    "EntityType", "EntityRecord", "EntityVideoLinkRecord",
    "CanonicalVideoRecord", "CanonicalCommentRecord",
    # Phase 3: analysis-scope generalization
    "AnalysisScopeType", "AnalysisScope",
]
