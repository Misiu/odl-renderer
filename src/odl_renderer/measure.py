"""Text measurement matching the text element's rendering.

Layout engines built on top of the renderer need to know how much space a text
element occupies before placing it. This module exposes that measurement using
the same wrapping/truncation helpers and line pitch as the ``text`` handler, so
measured boxes agree with what is drawn.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .elements.text import _truncate_to_width, _wrap_to_width, parse_colored_text

_ELLIPSIS = "..."
_DRAW = ImageDraw.Draw(Image.new("1", (1, 1)))


@dataclass(frozen=True)
class TextMetrics:
    """Size of a text block when drawn with anchor ``"la"`` (left, ascender).

    Attributes:
        width: Width of the widest line in pixels.
        height: Height from the ascender of the first line to the descender of the last line.
        lines: The final lines after wrapping, truncation and line clamping.
    """

    width: int
    height: int
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        """Lines joined with newlines, ready to pass as a text element ``value``."""
        return "\n".join(self.lines)


def line_pitch(font: ImageFont.FreeTypeFont, spacing: int = 5, stroke_width: int = 0) -> int:
    """Return the distance between consecutive lines of multiline text.

    Mirrors Pillow's multiline spacing: the bottom of an ``"A"`` bounding box
    plus stroke width plus ``spacing``.

    Args:
        font: Font used to draw the text.
        spacing: Extra pixels between lines (text element ``spacing`` field).
        stroke_width: Stroke width in pixels.

    Returns:
        Line pitch in pixels.
    """
    return int(_DRAW.textbbox((0, 0), "A", font=font, stroke_width=stroke_width)[3]) + stroke_width + spacing


def measure_text(
    value: object,
    font: ImageFont.FreeTypeFont,
    max_width: float | None = None,
    *,
    truncate: bool = False,
    max_lines: int | None = None,
    spacing: int = 5,
    stroke_width: int = 0,
    parse_colors: bool = False,
) -> TextMetrics:
    """Measure a text block the way the ``text`` element renders it.

    Wrapping and truncation follow the ``text`` element: with ``max_width`` the
    text is word-wrapped, or truncated with an ellipsis when ``truncate`` is set.
    ``max_lines`` additionally clamps the result, ending the last kept line with
    an ellipsis.

    Heights come from font metrics (ascent + descent), not from glyph ink, so two
    blocks with the same line count always have the same height.

    Args:
        value: Text content (coerced to ``str``).
        font: Font used to draw the text.
        max_width: Optional maximum line width in pixels.
        truncate: Truncate to a single line instead of wrapping.
        max_lines: Optional maximum number of lines (minimum 1).
        spacing: Extra pixels between lines.
        stroke_width: Stroke width in pixels.
        parse_colors: Strip ``[color]...[/color]`` markup before measuring.

    Returns:
        The measured size and the final lines.
    """
    text = str(value)
    if parse_colors:
        text = "".join(segment.text for segment in parse_colored_text(text))

    if max_width is not None:
        text = _truncate_to_width(text, font, max_width) if truncate else _wrap_to_width(text, font, max_width)

    lines = text.split("\n")
    if max_lines is not None and len(lines) > max(max_lines, 1):
        lines = lines[: max(max_lines, 1)]
        clamped = lines[-1] + _ELLIPSIS
        # Truncating "line..." keeps the full ellipsis when it fits, otherwise cuts the line itself.
        lines[-1] = clamped if max_width is None else _truncate_to_width(clamped, font, max_width)

    width = max(
        int(_DRAW.textbbox((0, 0), line, font=font, anchor="la", stroke_width=stroke_width)[2]) for line in lines
    )
    ascent, descent = font.getmetrics()
    height = (len(lines) - 1) * line_pitch(font, spacing, stroke_width) + ascent + descent + 2 * stroke_width
    return TextMetrics(width=width, height=height, lines=tuple(lines))
