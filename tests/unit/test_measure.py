"""Unit tests for the public text measurement API."""

import pytest
from PIL import Image, ImageChops

from odl_renderer import generate_image, line_pitch, measure_text

TEXT = "The quick brown fox jumps over the lazy dog"


def test_single_line_height_is_font_metrics(load_font):
    font = load_font("ppb", 40)
    ascent, descent = font.getmetrics()
    assert measure_text("Ay", font).height == ascent + descent
    # Glyph content does not change the height
    assert measure_text("ace", font).height == measure_text("Ay", font).height


def test_multiline_height_uses_line_pitch(load_font):
    font = load_font("ppb", 40)
    single = measure_text("Ay", font).height
    assert measure_text("Ay\nAy\nAy", font, spacing=5).height == single + 2 * line_pitch(font, 5)


def test_width_is_widest_line(load_font):
    font = load_font("ppb", 20)
    metrics = measure_text("a\nwide line\nb", font)
    assert metrics.width == measure_text("wide line", font).width
    assert metrics.lines == ("a", "wide line", "b")


def test_wrapping_respects_max_width(load_font):
    font = load_font("ppb", 16)
    metrics = measure_text(TEXT, font, max_width=100)
    assert len(metrics.lines) > 1
    # Line breaking uses advance width (like the renderer); ink may overhang slightly
    assert all(font.getlength(line) <= 100 for line in metrics.lines)


def test_truncate_keeps_single_line(load_font):
    font = load_font("ppb", 16)
    metrics = measure_text(TEXT, font, max_width=100, truncate=True)
    assert len(metrics.lines) == 1
    assert metrics.lines[0].endswith("...")
    # Line breaking uses advance width (like the renderer); ink may overhang slightly
    assert all(font.getlength(line) <= 100 for line in metrics.lines)


def test_max_lines_clamps_with_ellipsis(load_font):
    font = load_font("ppb", 16)
    metrics = measure_text(TEXT, font, max_width=100, max_lines=2)
    assert len(metrics.lines) == 2
    assert metrics.lines[-1].endswith("...")
    # Line breaking uses advance width (like the renderer); ink may overhang slightly
    assert all(font.getlength(line) <= 100 for line in metrics.lines)


def test_max_lines_not_exceeded_leaves_text_alone(load_font):
    font = load_font("ppb", 16)
    assert measure_text("short", font, max_width=200, max_lines=2).lines == ("short",)


def test_parse_colors_strips_markup(load_font):
    font = load_font("ppb", 16)
    assert measure_text("[red]Hot[/red] day", font, parse_colors=True).width == measure_text("Hot day", font).width


def test_non_string_value(load_font):
    font = load_font("ppb", 16)
    assert measure_text(42, font).lines == ("42",)


@pytest.mark.parametrize("value", ["Ay", "Hello World\nsecond line gjpq", "[red]red[/red] text"])
async def test_rendered_ink_fits_measured_box(load_font, value):
    """Text drawn with anchor 'la' stays inside the measured box."""
    size, x, y = 32, 10, 10
    font = load_font("ppb", size)
    parse_colors = "[" in value
    metrics = measure_text(value, font, parse_colors=parse_colors)

    img = await generate_image(
        width=400,
        height=200,
        elements=[
            {
                "type": "text",
                "value": value,
                "x": x,
                "y": y,
                "size": size,
                "font": "ppb",
                "anchor": "la",
                "parse_colors": parse_colors,
            }
        ],
        background="white",
    )
    ink = ImageChops.difference(img.convert("RGB"), Image.new("RGB", img.size, "white")).getbbox()
    assert ink is not None
    left, top, right, bottom = ink
    assert left >= x
    assert top >= y
    assert right <= x + metrics.width + 1
    assert bottom <= y + metrics.height
