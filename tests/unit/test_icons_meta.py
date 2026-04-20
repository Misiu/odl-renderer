"""Unit tests for MDI metadata loading in the icons element module."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestBuildMdiIndex:
    """Tests for _build_mdi_index — exercising both metadata formats."""

    def test_flat_dict_format_loaded(self, tmp_path: Path):
        meta = {"home": "F02DC", "cog": "F0493"}
        meta_file = tmp_path / "materialdesignicons-webfont_meta.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")

        from odl_renderer.elements.icons import _build_mdi_index

        # Use real file via patching Path resolution
        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if "materialdesignicons-webfont_meta.json" in str(path):
                return real_open(meta_file, *args, **kwargs)
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=fake_open):
            result = _build_mdi_index()

        assert result["home"] == "F02DC"
        assert result["cog"] == "F0493"

    def test_legacy_list_format_loaded(self, tmp_path: Path):
        meta = [
            {"name": "home", "codepoint": "F02DC", "aliases": ["house"]},
            {"name": "cog", "codepoint": "F0493", "aliases": []},
        ]
        meta_file = tmp_path / "materialdesignicons-webfont_meta.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")

        from odl_renderer.elements.icons import _build_mdi_index

        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if "materialdesignicons-webfont_meta.json" in str(path):
                return real_open(meta_file, *args, **kwargs)
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=fake_open):
            result = _build_mdi_index()

        assert result["home"] == "F02DC"
        assert result["house"] == "F02DC"  # alias expanded
        assert result["cog"] == "F0493"

    def test_invalid_file_raises_value_error(self, tmp_path: Path):
        meta_file = tmp_path / "materialdesignicons-webfont_meta.json"
        meta_file.write_text("not valid json", encoding="utf-8")

        from odl_renderer.elements.icons import _build_mdi_index

        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if "materialdesignicons-webfont_meta.json" in str(path):
                return real_open(meta_file, *args, **kwargs)
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=fake_open):
            with pytest.raises(ValueError, match="Failed to load MDI metadata"):
                _build_mdi_index()

    def test_unexpected_format_raises_value_error(self, tmp_path: Path):
        meta_file = tmp_path / "materialdesignicons-webfont_meta.json"
        meta_file.write_text('"just a string"', encoding="utf-8")

        from odl_renderer.elements.icons import _build_mdi_index

        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if "materialdesignicons-webfont_meta.json" in str(path):
                return real_open(meta_file, *args, **kwargs)
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=fake_open):
            with pytest.raises(ValueError, match="Unexpected MDI metadata format"):
                _build_mdi_index()
