"""Tests for `PreprocessEngineAdapter` (Release Blocker #6,
`docs/implementation/RB6_ANALYSIS_DISPATCH_READINESS_REVIEW.md` section 5.1).

Unlike the embeddings/topics/sentiment adapters (which fake their heavy ML dependency), this
adapter's only non-trivial dependency -- the registered `LanguageProvider` -- is genuinely
lightweight (`turkish.py` imports only `re`/`unicodedata`/`langdetect`, no `torch`/
`transformers`). These tests therefore use the real `TurkishLanguageProvider`, not a fake, same
discipline `preprocess/pipeline.py` itself already establishes for its own reuse.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from finfluencer.core.registry import register
from finfluencer.infrastructure.analysis import PreprocessEngineAdapter, PreprocessOutcome
from finfluencer.providers.language.turkish import TurkishLanguageProvider
from finfluencer.utils.io import read_parquet, write_parquet


@pytest.fixture(autouse=True)
def _register_turkish_provider(_reset_registry: None) -> None:
    """`tests/conftest.py`'s own `_reset_registry` (autouse) clears the provider registry before
    every test -- same workaround `test_t017_live_interruption.py`'s
    `_ensure_youtube_provider_registered` already uses for a different `kind`. Depends on
    `_reset_registry` by name so pytest clears first.
    """
    register("language", "turkish")(TurkishLanguageProvider)


def _fake_settings(root_seed: int = 1) -> Any:
    from finfluencer.core.contracts import PreprocessingConfig, ProvidersConfig

    return SimpleNamespace(
        providers=ProvidersConfig(language="turkish", platform="youtube"),
        preprocessing=PreprocessingConfig(min_tokens=1, jaccard_dup_threshold=0.9),
        study=SimpleNamespace(root_seed=root_seed),
    )


_ROWS = [
    ("satiroglu", "c1", "harika bir gelisme"),
    ("satiroglu", "c2", "kotu bir haber"),
    ("gecer", "c3", "notr bir yorum"),
]


def _write_uncleaned_comments(
    base_root: Path, collection_run_id: str, rows: list[tuple[str, str, str]],
) -> Path:
    """Mirrors `providers/platform/youtube.py`'s real output shape: `text_clean=""`, exactly the
    placeholder collected comments carry before preprocessing runs (confirmed via code in the
    Release Blocker #6 Readiness Review, not assumed).
    """
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [
            dict(
                analyst_key=a, video_id="v1", comment_id=cid, commenter_hash="h", posted_date="2025-01-01",
                text_raw=t, text_clean="", tokens=[], n_tokens=0, emojis=[], likes=0,
            )
            for a, cid, t in rows
        ],
    )
    write_parquet(df, comments_path)
    return comments_path


def test_ensure_clean_populates_text_clean_in_place(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    comments_path = _write_uncleaned_comments(base_root, "cr-1", _ROWS)
    assert (read_parquet(comments_path)["text_clean"] == "").all()

    adapter = PreprocessEngineAdapter(settings=_fake_settings(), base_root=base_root)
    outcome = adapter.ensure_clean("cr-1")

    assert isinstance(outcome, PreprocessOutcome)
    assert outcome.comments_path == comments_path
    assert outcome.row_count == 3

    updated = read_parquet(comments_path)
    assert (updated["text_clean"] != "").all()  # every row now populated, none still placeholder
    assert set(updated["text_clean"]) == {"harika bir gelisme", "kotu bir haber", "notr bir yorum"}


def test_ensure_clean_is_idempotent(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    _write_uncleaned_comments(base_root, "cr-2", _ROWS)
    adapter = PreprocessEngineAdapter(settings=_fake_settings(), base_root=base_root)

    first = adapter.ensure_clean("cr-2")
    second = adapter.ensure_clean("cr-2")

    assert first.row_count == second.row_count == 3


def test_two_collection_run_ids_never_share_checkpoint_state(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    _write_uncleaned_comments(base_root, "cr-a", _ROWS)
    _write_uncleaned_comments(base_root, "cr-b", _ROWS)
    adapter = PreprocessEngineAdapter(settings=_fake_settings(), base_root=base_root)

    adapter.ensure_clean("cr-a")
    adapter.ensure_clean("cr-b")

    assert (base_root / "cr-a" / "preprocess" / "checkpoints").exists()
    assert (base_root / "cr-b" / "preprocess" / "checkpoints").exists()
    assert (base_root / "cr-a" / "preprocess") != (base_root / "cr-b" / "preprocess")


def test_ensure_clean_rejects_empty_collection_run_id(tmp_path: Path) -> None:
    adapter = PreprocessEngineAdapter(settings=_fake_settings(), base_root=tmp_path)
    with pytest.raises(ValueError):
        adapter.ensure_clean("")


def test_adapter_module_does_not_import_presentation_or_api() -> None:
    import finfluencer.infrastructure.analysis.preprocess_adapter as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)


def test_adapter_never_modifies_wrapped_legacy_modules() -> None:
    import finfluencer.infrastructure.analysis.preprocess_adapter as module

    source = inspect.getsource(module)
    for forbidden in ("setattr(", "monkeypatch", "importlib.reload"):
        assert forbidden not in source
