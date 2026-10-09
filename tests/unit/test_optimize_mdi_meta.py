"""Unit tests for MDI metadata loading and optimization."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the scripts directory importable
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from optimize_materialdesignicons_meta import _load_source_json, _optimize_meta  # noqa: E402


class TestOptimizeMeta:
    def test_flat_dict_is_returned_sorted(self):
        raw: dict[str, object] = {"home": "F02DC", "cog": "F0493"}
        result = _optimize_meta(raw)
        assert result == {"cog": "F0493", "home": "F02DC"}
        assert list(result.keys()) == sorted(result.keys())

    def test_flat_dict_skips_non_string_values(self):
        raw: dict[str, object] = {"home": "F02DC", "bad": 123}
        result = _optimize_meta(raw)
        assert "bad" not in result
        assert result["home"] == "F02DC"

    def test_list_format_basic(self):
        raw = [{"name": "home", "codepoint": "F02DC", "aliases": []}]
        result = _optimize_meta(raw)
        assert result["home"] == "F02DC"

    def test_list_format_aliases_expanded(self):
        raw = [{"name": "home", "codepoint": "F02DC", "aliases": ["house", "dwelling"]}]
        result = _optimize_meta(raw)
        assert result["home"] == "F02DC"
        assert result["house"] == "F02DC"
        assert result["dwelling"] == "F02DC"

    def test_list_format_primary_name_overrides_alias(self):
        # Primary name assignment (direct =) takes precedence over alias (setdefault)
        # because primary names are processed after the alias is set.
        raw = [
            {"name": "home", "codepoint": "F02DC", "aliases": ["house"]},
            {"name": "house", "codepoint": "FAAAA", "aliases": []},
        ]
        result = _optimize_meta(raw)
        # "house" alias is set first via setdefault; then "house" primary overwrites it
        assert result["house"] == "FAAAA"
        assert result["home"] == "F02DC"

    def test_list_format_skips_invalid_entries(self):
        raw: list[object] = [
            {"name": "home", "codepoint": "F02DC"},
            {"name": "bad"},  # missing codepoint
            {"codepoint": "F0001"},  # missing name
        ]
        result = _optimize_meta(raw)  # type: ignore[arg-type]
        assert list(result.keys()) == ["home"]

    def test_list_format_result_is_sorted(self):
        raw = [
            {"name": "zig", "codepoint": "FFFFF", "aliases": []},
            {"name": "alpha", "codepoint": "F0001", "aliases": []},
        ]
        result = _optimize_meta(raw)
        assert list(result.keys()) == sorted(result.keys())

    def test_already_optimized_roundtrip(self):
        """Running _optimize_meta on an already-flat dict is idempotent."""
        original: dict[str, object] = {"alpha": "F0001", "beta": "F0002"}
        first_pass = _optimize_meta(original)
        second_pass = _optimize_meta(first_pass)  # type: ignore[arg-type]
        assert first_pass == second_pass


class TestLoadSourceJson:
    def test_loads_flat_dict(self, tmp_path: Path):
        data = {"home": "F02DC"}
        p = tmp_path / "meta.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = _load_source_json(p)
        assert result == data

    def test_loads_list_format(self, tmp_path: Path):
        data = [{"name": "home", "codepoint": "F02DC", "aliases": []}]
        p = tmp_path / "meta.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = _load_source_json(p)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_list_filters_non_dicts(self, tmp_path: Path):
        data: list[object] = [{"name": "home", "codepoint": "F02DC"}, "not-a-dict", 42]
        p = tmp_path / "meta.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = _load_source_json(p)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(RuntimeError, match="Failed to read"):
            _load_source_json(tmp_path / "nonexistent.json")

    def test_invalid_json_raises(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("not json", encoding="utf-8")
        with pytest.raises(RuntimeError, match="Failed to parse"):
            _load_source_json(p)

    def test_wrong_type_raises(self, tmp_path: Path):
        p = tmp_path / "meta.json"
        p.write_text('"just a string"', encoding="utf-8")
        with pytest.raises(ValueError, match="list or dict"):
            _load_source_json(p)


class TestMainScript:
    def test_main_writes_optimized_file(self, tmp_path: Path):
        """main() converts list format to flat dict in-place."""
        from optimize_materialdesignicons_meta import main

        data = [{"name": "home", "codepoint": "F02DC", "aliases": ["house"]}]
        src = tmp_path / "meta.json"
        src.write_text(json.dumps(data), encoding="utf-8")

        orig_argv = sys.argv
        sys.argv = ["optimize_materialdesignicons_meta.py", "--source", str(src), "--output", str(src)]
        try:
            main()
        finally:
            sys.argv = orig_argv

        result = json.loads(src.read_text(encoding="utf-8"))
        assert isinstance(result, dict)
        assert result["home"] == "F02DC"
        assert result["house"] == "F02DC"
