"""
finfluencer.preprocess.pipeline
=================================

Preprocessing stage: fills the placeholder ``text_clean``/``tokens``/
``n_tokens``/``emojis`` columns in ``comments.parquet`` (Methods §3.3).

Generic NLP (case-folding, noise-stripping, tokenisation, emoji
extraction) is delegated entirely to the registered ``LanguageProvider``;
this module adds only Turkish financial-domain normalisation
(:mod:`finfluencer.preprocess.financial_tr`) plus the corpus-level
filtering (min-token, near-duplicate) that spans rows.

``financial_tr`` emits tokens such as ``PERCENT_10``/``MONEY_TRY``
*before* ``LanguageProvider.strip_noise`` runs. ``strip_noise`` strips
digits, underscores, and punctuation, which would destroy these tokens,
so each is swapped for an all-letter placeholder and restored after
tokenisation.

One checkpoint stage per analyst (``preprocess_comments::<analyst_key>``):
re-running after a config change for one analyst does not force
reprocessing of the rest. When a stage is skipped, previously-written
rows are sourced from ``output_path`` (falling back to the raw input for
analysts never processed), so results are correct whether ``output_path``
equals ``comments_path`` (in-place update, the default) or a distinct
destination.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import Settings
from finfluencer.core.logging import bind_context, clear_context, get_logger
from finfluencer.core.reproducibility import derive_seed
from finfluencer.preprocess.base import PreprocessedText, TextPreprocessor
from finfluencer.preprocess.financial_tr import normalize_financial_text
from finfluencer.providers.language.base import LanguageProvider
from finfluencer.utils.dedup import find_near_duplicates
from finfluencer.utils.io import read_parquet, write_parquet


_log = get_logger(__name__)
_STAGE_PREFIX = "preprocess_comments"

# All-letter placeholder alphabet: survives LanguageProvider.strip_noise,
# which strips digits, underscores, and punctuation.
_PLACEHOLDER_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
_FIN_TOKEN_RE = re.compile(r"\b(CASHTAG_[A-Z]+|PERCENT_\d+|MONEY_(?:TRY|USD|EUR|GOLD))\b")


def _placeholder_key(index: int) -> str:
    """All-letter, index-unique placeholder immune to non-letter stripping."""
    digits: list[str] = []
    n = index
    while True:
        n, r = divmod(n, 26)
        digits.append(_PLACEHOLDER_ALPHABET[r])
        if n == 0:
            break
    return "zzzfin" + "".join(reversed(digits)) + "zzz"


def _mask_financial_tokens(text: str) -> tuple[str, dict[str, str]]:
    """Swap financial_tr tokens for letter-only placeholders; return the map."""
    mapping: dict[str, str] = {}
    counter = 0

    def _sub(m: re.Match[str]) -> str:
        nonlocal counter
        key = _placeholder_key(counter)
        counter += 1
        mapping[key] = m.group(1).lower()
        return key

    return _FIN_TOKEN_RE.sub(_sub, text), mapping


class _TurkishFinancialPreprocessor:
    """``TextPreprocessor``: LanguageProvider + financial_tr composition."""

    key = "turkish_financial"

    def __init__(self, language: LanguageProvider) -> None:
        self._language = language

    def process(self, text_raw: str) -> PreprocessedText:
        normalized = normalize_financial_text(text_raw)
        masked, mapping = _mask_financial_tokens(normalized)
        without_emoji, emojis = self._language.extract_emojis(masked)
        folded = self._language.fold_case(without_emoji)
        stripped = self._language.strip_noise(folded)
        tokens = [mapping.get(t, t) for t in self._language.tokenize(stripped)]
        return PreprocessedText(
            text_clean=" ".join(tokens),
            tokens=tokens,
            n_tokens=len(tokens),
            emojis=emojis,
        )


def build_default_preprocessor(language: LanguageProvider) -> TextPreprocessor:
    """Default Turkish + financial-domain preprocessor for ``language``."""
    return _TurkishFinancialPreprocessor(language)


def _stage_name(analyst_key: str) -> str:
    return f"{_STAGE_PREFIX}__{analyst_key}"


def _config_slice(
    preprocessor_key: str,
    min_tokens: int,
    jaccard_dup_threshold: float,
    stage_seed: int,
) -> dict[str, Any]:
    # stage_seed ties checkpoint identity to root_seed: a seed change
    # forces reprocessing even though this stage's own logic is
    # deterministic (no RNG is used by dedup/min-token filtering).
    return {
        "preprocessor_key": preprocessor_key,
        "min_tokens": min_tokens,
        "jaccard_dup_threshold": jaccard_dup_threshold,
        "stage_seed": stage_seed,
    }


def _process_group(
    group: pd.DataFrame,
    *,
    preprocessor: TextPreprocessor,
    min_tokens: int,
    jaccard_dup_threshold: float,
) -> pd.DataFrame:
    """Fill placeholder columns and filter one analyst's comment subset.

    Per-row work happens in ``preprocessor.process`` (pure Python, no
    pandas calls inside the loop); pandas is used only to assemble and
    filter the resulting columns afterwards.
    """
    texts_raw = group["text_raw"].tolist()
    processed = [preprocessor.process(t) for t in texts_raw]

    text_clean = [p.text_clean for p in processed]
    tokens = [p.tokens for p in processed]
    n_tokens = [p.n_tokens for p in processed]
    emojis = [p.emojis for p in processed]

    dup_indices = find_near_duplicates(tokens, threshold=jaccard_dup_threshold)
    keep = [
        i not in dup_indices and n_tokens[i] >= min_tokens
        for i in range(len(group))
    ]
    keep_mask = pd.Series(keep, index=group.index)

    out = group.copy()
    out["text_clean"] = text_clean
    out["tokens"] = tokens
    out["n_tokens"] = n_tokens
    out["emojis"] = emojis
    return out.loc[keep_mask]


def run_preprocessing(
    settings: Settings,
    comments_path: Path | str,
    checkpoint: CheckpointManager,
    *,
    preprocessor: TextPreprocessor,
    output_path: Path | str | None = None,
    analyst_key: str | None = None,
) -> pd.DataFrame:
    """Fill text_clean/tokens/n_tokens/emojis in comments.parquet.

    Parameters
    ----------
    settings
        Validated settings; uses ``settings.preprocessing`` and
        ``settings.study.root_seed``.
    comments_path
        Source ``comments.parquet`` (read-only within this call).
    checkpoint
        Shared :class:`CheckpointManager`; one stage per analyst.
    preprocessor
        Any :class:`TextPreprocessor`-compatible object (Turkish,
        English, TikTok, Reddit, ...); see :func:`build_default_preprocessor`.
    output_path
        Destination. Defaults to ``comments_path`` (in-place update).
    analyst_key
        If given, only that analyst's rows are (re)processed; others are
        carried through unchanged.
    """
    comments_path = Path(comments_path)
    output_path = Path(output_path) if output_path is not None else comments_path

    df = read_parquet(comments_path)
    if df.empty or "analyst_key" not in df.columns:
        _log.warning("preprocess_no_comments_available")
        write_parquet(df, output_path)
        return df

    existing_df: pd.DataFrame | None = None
    if output_path.exists():
        try:
            existing_df = read_parquet(output_path)
        except Exception:  # noqa: BLE001
            existing_df = None

    def _prior_rows(key: str) -> pd.DataFrame:
        """Rows to reuse for an analyst that is not (re)processed now."""
        if existing_df is not None and "analyst_key" in existing_df.columns:
            rows = existing_df.loc[existing_df["analyst_key"] == key]
            if not rows.empty:
                return rows
        return df.loc[df["analyst_key"] == key]

    cfg = settings.preprocessing
    stage_seed = derive_seed(settings.study.root_seed, _STAGE_PREFIX)
    cfg_slice = _config_slice(
        preprocessor.key, cfg.min_tokens, cfg.jaccard_dup_threshold, stage_seed,
    )

    all_keys = sorted(df["analyst_key"].unique().tolist())
    target_keys = [analyst_key] if analyst_key is not None else all_keys
    out_of_scope_keys = [k for k in all_keys if k not in target_keys]

    processed_parts: list[pd.DataFrame] = [_prior_rows(k) for k in out_of_scope_keys]

    for key in target_keys:
        group = df.loc[df["analyst_key"] == key]
        if group.empty:
            continue

        stage_name = _stage_name(key)
        marker = checkpoint.checkpoint_root / f"{stage_name}.done"
        had_marker = marker.exists()

        if not checkpoint.should_run(stage_name, cfg_slice):
            processed_parts.append(_prior_rows(key))
            continue
        if had_marker and not marker.exists():
            checkpoint.invalidate(stage_name)

        bind_context(analyst_key=key, stage=stage_name)
        try:
            result = _process_group(
                group,
                preprocessor=preprocessor,
                min_tokens=cfg.min_tokens,
                jaccard_dup_threshold=cfg.jaccard_dup_threshold,
            )
            processed_parts.append(result)
            checkpoint.mark_done(
                stage_name, cfg_slice,
                extras={"n_in": len(group), "n_kept": len(result)},
            )
            _log.info(
                "preprocess_analyst_done",
                analyst_key=key, n_in=len(group), n_kept=len(result),
            )
        finally:
            clear_context()

    result_df = (
        pd.concat(processed_parts, ignore_index=True)
        if processed_parts else df.iloc[0:0]
    )
    write_parquet(result_df, output_path)
    _log.info("preprocess_stage_summary", n_rows_out=len(result_df))
    return result_df


__all__ = [
    "PreprocessedText",
    "build_default_preprocessor",
    "run_preprocessing",
]
