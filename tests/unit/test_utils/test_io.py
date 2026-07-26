"""Tests for :mod:`finfluencer.utils.io`."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pandas as pd
import pytest
from finfluencer.utils.io import (
    _atomic_write_bytes,
    append_jsonl,
    ensure_dir,
    ensure_parent,
    load_completed_ids,
    read_json,
    read_jsonl,
    read_parquet,
    read_yaml,
    write_csv,
    write_excel,
    write_json,
    write_parquet,
    write_yaml,
)


class TestEnsureDir:
    def test_creates_missing_dir(self, tmp_path):
        target = tmp_path / "a" / "b" / "c"
        result = ensure_dir(target)
        assert target.is_dir()
        assert result == target

    def test_noop_on_existing_dir(self, tmp_path):
        target = tmp_path / "existing"
        target.mkdir()
        result = ensure_dir(target)
        assert result == target

    def test_accepts_str(self, tmp_path):
        target = tmp_path / "strpath"
        ensure_dir(str(target))
        assert target.is_dir()


class TestEnsureParent:
    def test_creates_missing_parent(self, tmp_path):
        target = tmp_path / "nested" / "dir" / "file.txt"
        result = ensure_parent(target)
        assert target.parent.is_dir()
        assert result == target

    def test_noop_when_parent_exists(self, tmp_path):
        target = tmp_path / "file.txt"
        ensure_parent(target)
        assert target.parent.is_dir()


class TestAtomicWriteBytes:
    def test_writes_and_replaces(self, tmp_path):
        p = tmp_path / "out.bin"
        _atomic_write_bytes(p, b"hello")
        assert p.read_bytes() == b"hello"

    def test_no_tmp_file_left_behind_on_success(self, tmp_path):
        p = tmp_path / "out.bin"
        _atomic_write_bytes(p, b"data")
        leftovers = [f for f in tmp_path.iterdir() if f.name != "out.bin"]
        assert leftovers == []

    def test_cleans_up_tmp_file_on_write_failure(self, tmp_path):
        p = tmp_path / "out.bin"
        with patch("os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                _atomic_write_bytes(p, b"data")
        # Temp file must not survive a failed write.
        leftovers = list(tmp_path.iterdir())
        assert leftovers == []

    def test_cleanup_itself_failing_does_not_mask_original_error(self, tmp_path):
        p = tmp_path / "out.bin"
        with patch("os.replace", side_effect=OSError("disk full")):
            with patch("os.unlink", side_effect=OSError("cleanup also failed")):
                with pytest.raises(OSError, match="disk full"):
                    _atomic_write_bytes(p, b"data")


class TestYaml:
    def test_roundtrip_dict(self, tmp_path):
        p = tmp_path / "conf.yaml"
        data = {"a": 1, "b": [1, 2, 3]}
        write_yaml(data, p)
        assert read_yaml(p) == data

    def test_roundtrip_nested_and_unicode(self, tmp_path):
        p = tmp_path / "conf.yaml"
        data = {"name": "Şatıroğlu", "nested": {"x": [1, {"y": "değer"}]}}
        write_yaml(data, p)
        assert read_yaml(p) == data

    def test_preserves_key_order_not_sorted(self, tmp_path):
        p = tmp_path / "conf.yaml"
        write_yaml({"z": 1, "a": 2}, p)
        text = p.read_text(encoding="utf-8")
        assert text.index("z:") < text.index("a:")

    def test_accepts_str_path(self, tmp_path):
        p = tmp_path / "conf.yaml"
        write_yaml({"k": "v"}, str(p))
        assert read_yaml(str(p)) == {"k": "v"}


class TestJson:
    def test_roundtrip(self, tmp_path):
        p = tmp_path / "data.json"
        data = {"b": 2, "a": 1}
        write_json(data, p)
        assert read_json(p) == data

    def test_sort_keys_true_is_deterministic(self, tmp_path):
        p1 = tmp_path / "d1.json"
        p2 = tmp_path / "d2.json"
        write_json({"b": 2, "a": 1}, p1, sort_keys=True)
        write_json({"a": 1, "b": 2}, p2, sort_keys=True)
        assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")

    def test_sort_keys_false_preserves_insertion_order(self, tmp_path):
        p = tmp_path / "data.json"
        write_json({"z": 1, "a": 2}, p, sort_keys=False)
        text = p.read_text(encoding="utf-8")
        assert text.index('"z"') < text.index('"a"')

    def test_trailing_newline(self, tmp_path):
        p = tmp_path / "data.json"
        write_json({"a": 1}, p)
        assert p.read_text(encoding="utf-8").endswith("\n")

    def test_non_ascii_preserved(self, tmp_path):
        p = tmp_path / "data.json"
        write_json({"name": "Şatıroğlu"}, p)
        assert "Şatıroğlu" in p.read_text(encoding="utf-8")

    def test_default_str_fallback_for_unserializable_values(self, tmp_path):
        from datetime import date

        p = tmp_path / "data.json"
        write_json({"d": date(2025, 1, 1)}, p)
        assert read_json(p) == {"d": "2025-01-01"}

    def test_custom_indent(self, tmp_path):
        p = tmp_path / "data.json"
        write_json({"a": 1}, p, indent=4)
        text = p.read_text(encoding="utf-8")
        assert "    " in text


class TestJsonl:
    def test_append_then_read_roundtrip(self, tmp_path):
        p = tmp_path / "log.jsonl"
        append_jsonl({"id": "1"}, p)
        append_jsonl({"id": "2"}, p)
        records = list(read_jsonl(p))
        assert records == [{"id": "1"}, {"id": "2"}]

    def test_append_creates_parent_dir(self, tmp_path):
        p = tmp_path / "nested" / "log.jsonl"
        append_jsonl({"id": "1"}, p)
        assert p.exists()

    def test_read_missing_file_yields_nothing(self, tmp_path):
        p = tmp_path / "missing.jsonl"
        assert list(read_jsonl(p)) == []

    def test_read_skips_blank_lines(self, tmp_path):
        p = tmp_path / "log.jsonl"
        p.write_text('{"id": "1"}\n\n{"id": "2"}\n', encoding="utf-8")
        assert list(read_jsonl(p)) == [{"id": "1"}, {"id": "2"}]

    def test_read_stops_cleanly_on_truncated_last_line(self, tmp_path):
        p = tmp_path / "log.jsonl"
        p.write_text('{"id": "1"}\n{"id": "2", "trunc', encoding="utf-8")
        records = list(read_jsonl(p))
        assert records == [{"id": "1"}]

    def test_read_raises_when_first_line_is_malformed(self, tmp_path):
        p = tmp_path / "log.jsonl"
        p.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            list(read_jsonl(p))

    def test_non_ascii_round_trips(self, tmp_path):
        p = tmp_path / "log.jsonl"
        append_jsonl({"name": "Şatıroğlu"}, p)
        assert list(read_jsonl(p)) == [{"name": "Şatıroğlu"}]


class TestLoadCompletedIds:
    def test_collects_default_key(self, tmp_path):
        p = tmp_path / "log.jsonl"
        append_jsonl({"id": "a"}, p)
        append_jsonl({"id": "b"}, p)
        assert load_completed_ids(p) == {"a", "b"}

    def test_custom_key(self, tmp_path):
        p = tmp_path / "log.jsonl"
        append_jsonl({"video_id": "x"}, p)
        assert load_completed_ids(p, key="video_id") == {"x"}

    def test_ignores_records_missing_key(self, tmp_path):
        p = tmp_path / "log.jsonl"
        append_jsonl({"id": "a"}, p)
        append_jsonl({"other": "b"}, p)
        assert load_completed_ids(p) == {"a"}

    def test_missing_file_returns_empty_set(self, tmp_path):
        assert load_completed_ids(tmp_path / "missing.jsonl") == set()


class TestParquet:
    def test_roundtrip(self, tmp_path):
        p = tmp_path / "data.parquet"
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        write_parquet(df, p)
        result = read_parquet(p)
        pd.testing.assert_frame_equal(result, df)

    def test_creates_parent_dir(self, tmp_path):
        p = tmp_path / "nested" / "data.parquet"
        df = pd.DataFrame({"a": [1]})
        write_parquet(df, p)
        assert p.exists()

    def test_no_tmp_file_left_behind_on_success(self, tmp_path):
        p = tmp_path / "data.parquet"
        df = pd.DataFrame({"a": [1]})
        write_parquet(df, p)
        leftovers = [f for f in tmp_path.iterdir() if f.name != "data.parquet"]
        assert leftovers == []

    def test_cleans_up_tmp_file_on_failure(self, tmp_path):
        p = tmp_path / "data.parquet"
        df = pd.DataFrame({"a": [1]})
        with patch("os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError, match="boom"):
                write_parquet(df, p)
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == []

    def test_custom_compression(self, tmp_path):
        p = tmp_path / "data.parquet"
        df = pd.DataFrame({"a": [1, 2]})
        write_parquet(df, p, compression="gzip")
        pd.testing.assert_frame_equal(read_parquet(p), df)


class TestWriteExcel:
    def test_single_sheet_roundtrip(self, tmp_path):
        p = tmp_path / "out.xlsx"
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        write_excel({"Sheet1": df}, p)
        result = pd.read_excel(p, sheet_name="Sheet1")
        pd.testing.assert_frame_equal(result, df)

    def test_multiple_sheets_preserve_insertion_order(self, tmp_path):
        p = tmp_path / "out.xlsx"
        df1 = pd.DataFrame({"a": [1]})
        df2 = pd.DataFrame({"b": [2]})
        write_excel({"First": df1, "Second": df2}, p)
        with pd.ExcelFile(p) as xls:
            assert xls.sheet_names == ["First", "Second"]

    def test_sheet_name_truncated_to_31_chars(self, tmp_path):
        p = tmp_path / "out.xlsx"
        long_name = "a" * 40
        write_excel({long_name: pd.DataFrame({"a": [1]})}, p)
        with pd.ExcelFile(p) as xls:
            assert xls.sheet_names == [long_name[:31]]
            assert len(xls.sheet_names[0]) == 31

    def test_creates_parent_dir(self, tmp_path):
        p = tmp_path / "nested" / "out.xlsx"
        write_excel({"S": pd.DataFrame({"a": [1]})}, p)
        assert p.exists()

    def test_no_tmp_file_left_behind_on_success(self, tmp_path):
        p = tmp_path / "out.xlsx"
        write_excel({"S": pd.DataFrame({"a": [1]})}, p)
        leftovers = [f for f in tmp_path.iterdir() if f.name != "out.xlsx"]
        assert leftovers == []

    def test_cleans_up_tmp_file_on_failure(self, tmp_path):
        p = tmp_path / "out.xlsx"
        with patch("os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError, match="boom"):
                write_excel({"S": pd.DataFrame({"a": [1]})}, p)
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == []


class TestWriteCsv:
    def test_roundtrip_no_decimal_places(self, tmp_path):
        p = tmp_path / "out.csv"
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        write_csv(df, p)
        result = pd.read_csv(p, encoding="utf-8-sig")
        pd.testing.assert_frame_equal(result, df)

    def test_decimal_places_applies_float_format(self, tmp_path):
        p = tmp_path / "out.csv"
        df = pd.DataFrame({"a": [1.23456789]})
        write_csv(df, p, decimal_places=2)
        text = p.read_text(encoding="utf-8-sig")
        assert "1.23" in text
        assert "1.23456789" not in text

    def test_utf8_bom_used_for_excel(self, tmp_path):
        p = tmp_path / "out.csv"
        write_csv(pd.DataFrame({"name": ["Şatıroğlu"]}), p)
        raw = p.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")

    def test_creates_parent_dir(self, tmp_path):
        p = tmp_path / "nested" / "out.csv"
        write_csv(pd.DataFrame({"a": [1]}), p)
        assert p.exists()

    def test_no_tmp_file_left_behind_on_success(self, tmp_path):
        p = tmp_path / "out.csv"
        write_csv(pd.DataFrame({"a": [1]}), p)
        leftovers = [f for f in tmp_path.iterdir() if f.name != "out.csv"]
        assert leftovers == []

    def test_cleans_up_tmp_file_on_failure(self, tmp_path):
        p = tmp_path / "out.csv"
        with patch("os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError, match="boom"):
                write_csv(pd.DataFrame({"a": [1]}), p)
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == []
