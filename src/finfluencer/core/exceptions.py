"""
finfluencer.core.exceptions
============================

Exception hierarchy for the Finfluencer Research Platform.

All platform-specific errors inherit from :class:`FinfluencerError`.
Modules raise the most specific subclass applicable to the situation;
callers catch specific subclasses rather than the root class. Catching
bare :class:`Exception` in platform code is discouraged.

Each exception carries:

* ``message`` — human-readable description (positional first argument);
* ``context`` — structured fields preserved as a ``dict`` for logging
  (any keyword arguments passed to the constructor).

Example
-------

.. code-block:: python

    from finfluencer.core.exceptions import QuotaExhaustedError

    raise QuotaExhaustedError(
        "YouTube API daily quota exhausted",
        quota_used=9847,
        quota_limit=10000,
        analyst="satiroglu",
    )

The :attr:`FinfluencerError.context` attribute is subsequently inspected
by the logging layer (``core.logging``) so structured fields land in JSON
log records rather than being flattened into an unstructured message.

Design rationale
----------------
* **Exceptions are data carriers, not logic.** No methods beyond
  ``__init__``, ``__str__``, and ``__repr__``. Business logic lives in
  the module that raises the exception, not on the exception itself.

* **Recoverable vs non-recoverable errors are distinct classes.**
  :class:`RateLimitError` is recoverable and warrants retry;
  :class:`QuotaExhaustedError` is non-recoverable within the day and
  warrants a checkpointed exit. The retry decorator uses class identity
  to decide.

* **The hierarchy is complete on day one.** Exceptions used only by
  later phases (e.g. :class:`DirtyWorkingTreeError` for Phase 8) are
  defined here to avoid a later "patch touches core" refactor. This is
  not architectural expansion; it is completion of the vocabulary the
  frozen v2.1 architecture already implies.
"""

from __future__ import annotations

from typing import Any


# =============================================================================
# Root exception
# =============================================================================


class FinfluencerError(Exception):
    """Root exception for all platform-specific errors.

    Callers who wish to catch *any* platform error write::

        try:
            run_pipeline()
        except FinfluencerError as exc:
            log.error("Pipeline failed", message=exc.message, **exc.context)

    Attributes
    ----------
    message : str
        Human-readable description.
    context : dict[str, Any]
        Structured fields for logging, taken from keyword arguments.
    """

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message: str = message
        self.context: dict[str, Any] = context

    def __str__(self) -> str:
        if self.context:
            ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} [{ctx}]"
        return self.message

    def __repr__(self) -> str:
        if self.context:
            ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{type(self).__name__}({self.message!r}, {ctx})"
        return f"{type(self).__name__}({self.message!r})"


# =============================================================================
# Configuration errors
# =============================================================================


class ConfigError(FinfluencerError):
    """Base class for configuration-related errors."""


class ConfigFileNotFoundError(ConfigError):
    """Raised when a required configuration file is missing.

    Raised by :func:`finfluencer.core.config.load_settings` when
    ``settings.yaml`` or ``analysts.yaml`` cannot be located.
    """


class ConfigValidationError(ConfigError):
    """Raised when configuration content fails Pydantic validation.

    The Pydantic error report is preserved in ``context['validation_errors']``.
    """


class ConfigSchemaMismatchError(ConfigError):
    """Raised when configuration contains keys unknown to the schema.

    Enforced in strict mode to catch YAML-key typos that would otherwise
    be silently ignored — a common source of "why isn't my setting
    taking effect?" bugs.
    """


# =============================================================================
# Provider errors (language, platform, market, sentiment backends)
# =============================================================================


class ProviderError(FinfluencerError):
    """Base class for language/platform/market/backend provider errors."""


class ProviderNotFoundError(ProviderError):
    """Raised when a configured provider key is not registered.

    Example: ``providers.language: "arabic"`` in ``settings.yaml`` but
    no Arabic LanguageProvider is registered in :mod:`core.registry`.
    """


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is registered but improperly configured.

    Distinct from :class:`ConfigValidationError` because the provider
    itself performs the additional validation (e.g. verifying that an
    API key is set for the platform provider).
    """


# =============================================================================
# Collection and external-API errors
# =============================================================================


class CollectionError(FinfluencerError):
    """Base class for data-collection errors."""


class AuthenticationError(CollectionError):
    """Raised when an API credential is missing, invalid, or expired.

    Non-recoverable within a run — callers should surface this to the
    user rather than retrying.
    """


class QuotaExhaustedError(CollectionError):
    """Raised when a daily API quota is exhausted at the server side.

    Non-recoverable within a day — the pipeline should checkpoint and
    exit cleanly. Users re-run on the next quota window.

    Distinguished from :class:`QuotaBudgetExceededError`
    (raised pre-emptively by our own quota tracker).
    """


class RateLimitError(CollectionError):
    """Raised on transient rate-limit responses.

    Recoverable via backoff — the retry decorator distinguishes this
    from :class:`QuotaExhaustedError` because it warrants retry, not
    termination.
    """


class ResourceNotFoundError(CollectionError):
    """Raised when a requested channel, video, or comment does not exist."""


class NetworkError(CollectionError):
    """Raised on transient network failures (DNS, connection reset, etc.).

    Recoverable via backoff.
    """


# =============================================================================
# Data, checkpoint, and inter-module contract errors
# =============================================================================


class DataError(FinfluencerError):
    """Base class for data-integrity and I/O errors."""


class CheckpointError(DataError):
    """Base class for checkpoint-related errors."""


class CheckpointCorruptedError(CheckpointError):
    """Raised when a checkpoint file exists but cannot be read cleanly."""


class CheckpointInvalidatedError(CheckpointError):
    """Raised when a checkpoint exists but its stage-config hash mismatches.

    Indicates that the upstream configuration has changed since the
    checkpoint was written; the downstream stage must re-run to reflect
    the new configuration.
    """


class SchemaContractError(DataError):
    """Raised when data crossing a module boundary violates its schema.

    Enforced by Pydantic-validated inter-module contracts
    (:mod:`finfluencer.core.contracts`). Indicates a bug in a producer
    module rather than user error.
    """


class CorpusValidationError(DataError):
    """Raised when a corpus violates structural expectations.

    Example: comment count of zero after preprocessing, missing required
    columns, mixed dtypes in a column expected to be homogeneous.
    """


# =============================================================================
# Reproducibility errors
# =============================================================================


class ReproducibilityError(FinfluencerError):
    """Base class for reproducibility-guarantee violations."""


class DirtyWorkingTreeError(ReproducibilityError):
    """Raised in publication mode when the git working tree is not clean.

    Publication-stage runs require a clean tree so the exact code state
    that produced the outputs is what has been committed.
    """


class UnpinnedRevisionError(ReproducibilityError):
    """Raised in publication mode when a HuggingFace revision is unpinned.

    Publication-stage runs refuse to proceed with placeholder or wildcard
    revisions (e.g. ``"main"``, ``"REPLACE_WITH_HF_COMMIT_SHA"``).
    """


class RevisionMismatchError(ReproducibilityError):
    """Raised when a resolved HuggingFace revision differs from the pinned one.

    Indicates that the model on the Hub has changed since pinning.
    Investigate and either update the pin (with a new provenance record)
    or investigate why the resolved revision differs.
    """


class EnvironmentMismatchError(ReproducibilityError):
    """Raised when the runtime environment differs from a pinned snapshot.

    Used by the ``reproduce`` sub-command when the current environment
    (Python version, package versions) does not match ``provenance.json``.
    """


# =============================================================================
# Preprocessing errors
# =============================================================================


class PreprocessingError(FinfluencerError):
    """Base class for preprocessing errors."""


class LanguageDetectionError(PreprocessingError):
    """Raised when language detection cannot decide reliably.

    Typically caused by very short or symbol-only comments.
    """


# =============================================================================
# Analysis errors
# =============================================================================


class AnalysisError(FinfluencerError):
    """Base class for analysis-stage errors."""


class ModelLoadError(AnalysisError):
    """Raised when a model cannot be loaded from cache or the HuggingFace Hub."""


class InferenceError(AnalysisError):
    """Raised on inference failures (OOM, tensor shape mismatch, etc.)."""


# =============================================================================
# Budget errors (memory, quota accounting)
# =============================================================================


class BudgetError(FinfluencerError):
    """Base class for resource-budget violations."""


class MemoryBudgetExceededError(BudgetError):
    """Raised when a stage exceeds its configured memory ceiling."""


class QuotaBudgetExceededError(BudgetError):
    """Raised pre-emptively by the quota tracker before a call would cross
    the daily limit.

    Distinct from :class:`QuotaExhaustedError`: the former is raised by
    the API on 403; this one is raised by us before we make the call.
    Both categories of quota event are logged separately in provenance.
    """


# =============================================================================
# Ethics errors
# =============================================================================


class EthicsError(FinfluencerError):
    """Base class for ethics-in-design policy violations."""


class RetentionPolicyError(EthicsError):
    """Raised when data older than the retention period is accessed.

    Enforced by :mod:`finfluencer.ethics.retention`.
    """


class SensitiveContentError(EthicsError):
    """Raised when sensitive-content thresholds are exceeded.

    Enforced by :mod:`finfluencer.ethics.sensitive`.
    """


# =============================================================================
# Public API
# =============================================================================


__all__ = [
    # Root
    "FinfluencerError",
    # Configuration
    "ConfigError",
    "ConfigFileNotFoundError",
    "ConfigValidationError",
    "ConfigSchemaMismatchError",
    # Providers
    "ProviderError",
    "ProviderNotFoundError",
    "ProviderConfigurationError",
    # Collection
    "CollectionError",
    "AuthenticationError",
    "QuotaExhaustedError",
    "RateLimitError",
    "ResourceNotFoundError",
    "NetworkError",
    # Data
    "DataError",
    "CheckpointError",
    "CheckpointCorruptedError",
    "CheckpointInvalidatedError",
    "SchemaContractError",
    "CorpusValidationError",
    # Reproducibility
    "ReproducibilityError",
    "DirtyWorkingTreeError",
    "UnpinnedRevisionError",
    "RevisionMismatchError",
    "EnvironmentMismatchError",
    # Preprocessing
    "PreprocessingError",
    "LanguageDetectionError",
    # Analysis
    "AnalysisError",
    "ModelLoadError",
    "InferenceError",
    # Budget
    "BudgetError",
    "MemoryBudgetExceededError",
    "QuotaBudgetExceededError",
    # Ethics
    "EthicsError",
    "RetentionPolicyError",
    "SensitiveContentError",
]
