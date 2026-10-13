from __future__ import annotations

import logging
import os
from pathlib import Path, PurePath
from typing import Dict, Tuple

from PIL import ImageFont

from .types import SourceGuard, SourceNotAllowedError, check_source

_LOGGER = logging.getLogger(__name__)

# Assets directory (bundled fonts)
_ASSETS_DIR = Path(__file__).parent / "assets"

# Module-level cache of loaded fonts keyed by (resolved_path, size), shared across
# every FontManager instance. core.generate_image() builds a fresh FontManager per
# call, so without this the truetype file would be re-read from disk on every render
# (blocking I/O on the event loop — several ms per render on an SD card). Mirrors the
# module-level MDI font cache in elements/icons.py.
_truetype_cache: dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


def _load_truetype(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TrueType font, reusing the process-wide cache when possible.

    Args:
        path: Absolute path to the font file.
        size: Font size in pixels.

    Returns:
        The loaded (and cached) font object.
    """
    key = (path, size)
    cached = _truetype_cache.get(key)
    if cached is None:
        cached = ImageFont.truetype(path, size)
        _truetype_cache[key] = cached
    return cached


class FontManager:
    """Manages font loading and caching.

    Supports multiple input types:
    - PIL ImageFont objects (passed through)
    - Absolute file paths (loaded from disk)
    - Built-in font names (loaded from assets/)
    - Relative names resolved against caller-supplied search directories
    """

    def __init__(self, font_dirs: list[str] | None = None, allow_source: SourceGuard | None = None) -> None:
        """Initialize the font manager.

        Args:
            font_dirs: Optional list of directories to search for fonts by name,
                       in priority order, before falling back to bundled assets.
            allow_source: Optional policy consulted before a font is loaded from an
                          absolute path. Fonts found by name in font_dirs or in the
                          bundled assets are not subject to it.
        """
        self._allow_source = allow_source
        self._font_cache: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}
        self._font_dirs: list[str] = [d for d in (font_dirs or []) if os.path.isdir(d)]

    def get_font(self, font: str | ImageFont.FreeTypeFont, size: int) -> ImageFont.FreeTypeFont:
        """Get a font, loading it if necessary.

        Args:
            font: Font specification - can be:
                  - PIL ImageFont.FreeTypeFont object (returned as-is)
                  - Absolute path to font file (loaded from disk)
                  - Built-in font name like "ppb" or "ppb.ttf" (loaded from assets/)
            size: Font size in pixels (ignored if font is already a Font object)

        Returns:
            Loaded font object

        Raises:
            ValueError: If font cannot be loaded
        """
        # If already a Font object, return it
        if isinstance(font, ImageFont.FreeTypeFont):
            return font

        # For string font specifications, use cache
        cache_key = (font, size)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        # Load the font
        loaded_font = self._load_font(font, size)

        # Cache it
        self._font_cache[cache_key] = loaded_font
        return loaded_font

    def _load_font(self, font_spec: str, size: int) -> ImageFont.FreeTypeFont:
        """Load a font from disk.

        Args:
            font_spec: Font path or name
            size: Font size in pixels

        Returns:
            Loaded font object

        Raises:
            ValueError: If font cannot be loaded
            SourceNotAllowedError: If the path is refused by allow_source, or a
                                   font name tries to leave the search directories
        """
        # If absolute path, load directly
        if os.path.isabs(font_spec):
            check_source(self._allow_source, "file", font_spec)
            if not os.path.exists(font_spec):
                raise ValueError(f"Font file not found: {font_spec}")
            try:
                return _load_truetype(font_spec, size)
            except (OSError, IOError) as err:
                raise ValueError(f"Failed to load font from {font_spec}: {err}") from err

        # Normalise: support both "ppb" and "ppb.ttf" / "ppb.otf"
        font_name = font_spec if font_spec.endswith((".ttf", ".otf")) else f"{font_spec}.ttf"

        # A name is joined onto the search directories; it must not climb out of them.
        if ".." in PurePath(font_name).parts:
            raise SourceNotAllowedError("file", font_spec)

        # Search caller-supplied directories first
        for directory in self._font_dirs:
            candidate = os.path.join(directory, font_name)
            if os.path.isfile(candidate):
                try:
                    return _load_truetype(candidate, size)
                except (OSError, IOError) as err:
                    _LOGGER.warning("Failed to load font from %s: %s", candidate, err)

        # Fall back to built-in assets directory
        asset_path = _ASSETS_DIR / font_name
        if asset_path.exists():
            try:
                return _load_truetype(str(asset_path), size)
            except (OSError, IOError) as err:
                raise ValueError(f"Failed to load built-in font '{font_name}': {err}") from err

        # Font not found
        search_hint = f", searched: {self._font_dirs}" if self._font_dirs else ""
        raise ValueError(
            f"Font '{font_spec}' not found{search_hint}. "
            f"Provide an absolute path, a directory via font_dirs, or use a built-in font (ppb, rbm). "
            f"Built-in fonts are in: {_ASSETS_DIR}"
        )

    def clear_cache(self) -> None:
        """Clear the font cache.

        Removes all cached fonts, forcing them to be reloaded on next request.
        """
        self._font_cache.clear()
