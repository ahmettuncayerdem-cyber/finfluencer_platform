"""
finfluencer.utils.io
=====================

File I/O helpers for Parquet, YAML, JSON, JSONL, and Excel.

Design invariants
-----------------
* Parquet is the canonical inter-stage format (lossless, typed, nested-
  type safe, cross-language).
* JSONL is the checkpoint format (append-only, streaming, crash-safe).
* Excel is a **delivery** format only; never used for inter-stage data.
* All writes are atomic when practical (temp file + rename) to survive
  crashes without leaving half-written files.
* JSON writes use ``sort_keys=True`` for byte-deterministic output
  suitable for hashing and diffing.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Iterator

import pandas as pd
import yaml


# =============================================================================
# Directory helpers
# =============================================================================


def ensure_dir(path: Path | str) -> Path:
    """Create the directory (and parents) if missing; return the Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_parent(path: Path | str) -> Path:
    """Create the parent directory of ``path`` if missing; return the Path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# =============================================================================
# Atomic-write helper
# =============================================================================


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    ensure_parent(path)
    # Temp file in same directory → same filesystem → atomic rename.
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    _atomic_write_bytes(path, text.encode(encoding))


# =============================================================================
# YAML
# =============================================================================


def read_yaml(path: Path | str) -> Any:
    """Load a YAML file safely (no arbitrary Python object construction)."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_yaml(data: Any, path: Path | str) -> None:
    """Write ``data`` to a YAML file atomically."""
    p = Path(path)
    text = yaml.safe_dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    _atomic_write_text(p, text)


# =============================================================================
# JSON
# =============================================================================


def read_json(path: Path | str) -> Any:
    """Load a JSON file."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(data: Any, path: Path | str, *, sort_keys: bool = True, indent: int = 2) -> None:
    """Write ``data`` to a JSON file atomically.

    Default ``sort_keys=True`` produces byte-deterministic output suitable
    for hashing and diffing (e.g. ``provenance.json``).
    """
    p = Path(path)
    text = json.dumps(
        data,
        sort_keys=sort_keys,
        indent=indent,
        ensure_ascii=False,
        default=str,  # explicit, reproducible fallback for dates/Paths
    )
    _atomic_write_text(p, text + "\n")


# =============================================================================
# JSONL (append-only streaming records)
# =============================================================================


def append_jsonl(record: dict[str, Any], path: Path | str) -> None:
    """Append a single record to a JSONL file. Not atomic; caller must
    tolerate partial last lines on crash (readers should be robust to this).
    """
    p = Path(path)
    ensure_parent(p)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_jsonl(path: Path | str) -> Iterator[dict[str, Any]]:
    """Iterate records in a JSONL file.

    Silently skips blank lines and warns (via return-then-continue) on
    unparseable lines; a truncated last line does not abort iteration.
    """
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                # Truncated last line after crash — stop cleanly.
                if lineno > 1:
                    return
                raise


def load_completed_ids(path: Path | str, *, key: str = "id") -> set[str]:
    """Return the set of ``key`` values already recorded in a JSONL file.

    Used by collection stages to skip already-processed items on resume.
    """
    return {rec.get(key) for rec in read_jsonl(path) if rec.get(key) is not None}


# =============================================================================
# Parquet
# =============================================================================


def read_parquet(path: Path | str) -> pd.DataFrame:
    """Read a Parquet file into a DataFrame using the pyarrow engine."""
    return pd.read_parquet(path, engine="pyarrow")


def write_parquet(df: pd.DataFrame, path: Path | str, *, compression: str = "snappy") -> None:
    """Write a DataFrame to Parquet atomically using the pyarrow engine."""
    p = Path(path)
    ensure_parent(p)
    # Pandas does not support atomic writes natively; write to temp then rename.
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        df.to_parquet(tmp, engine="pyarrow", index=False, compression=compression)
        os.replace(tmp, p)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


# =============================================================================
# Excel (delivery-only)
# =============================================================================


def write_excel(sheets: dict[str, pd.DataFrame], path: Path | str) -> None:
    """Write one or more DataFrames as sheets to an Excel file.

    Delivery-only: never used between pipeline stages. Sheet order
    follows dict insertion order.
    """
    p = Path(path)
    ensure_parent(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                # Excel sheet name limit is 31 chars.
                clean_name = sheet_name[:31]
                df.to_excel(writer, sheet_name=clean_name, index=False)
        os.replace(tmp, p)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


# =============================================================================
# CSV (secondary delivery)
# =============================================================================


def write_csv(df: pd.DataFrame, path: Path | str, *, decimal_places: int | None = None) -> None:
    """Write a DataFrame to CSV atomically. UTF-8 with BOM for Excel."""
    p = Path(path)
    ensure_parent(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        kwargs: dict[str, Any] = {"index": False, "encoding": "utf-8-sig"}
        if decimal_places is not None:
            kwargs["float_format"] = f"%.{decimal_places}f"
        df.to_csv(tmp, **kwargs)
        os.replace(tmp, p)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


__all__ = [
    "ensure_dir",
    "ensure_parent",
    "read_yaml",
    "write_yaml",
    "read_json",
    "write_json",
    "append_jsonl",
    "read_jsonl",
    "load_completed_ids",
    "read_parquet",
    "write_parquet",
    "write_excel",
    "write_csv",
]
