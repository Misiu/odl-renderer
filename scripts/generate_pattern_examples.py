"""Generate the example pictures for the rectangle `pattern` field.

Each picture is written to docs/screenshots/patterns/. They show what the pattern types
look like, how a tone compares with a gray under dithering, how patterns layer with fills,
outlines and rounded corners, and what a calendar looks like with and without them.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odl_renderer import generate_image

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "screenshots" / "patterns"

Element = dict[str, Any]


def rectangle(x: int, y: int, w: int, h: int, **fields: Any) -> Element:
    """Return a rectangle given its corner and size (`width` stays the outline width)."""
    return {
        "type": "rectangle",
        "x_start": x,
        "y_start": y,
        "x_end": x + w - 1,
        "y_end": y + h - 1,
        **fields,
    }


def text(value: str, x: int, y: int, size: int = 12, **fields: Any) -> Element:
    """Return a text element anchored at its middle top."""
    return {"type": "text", "value": value, "x": x, "y": y, "size": size, "anchor": "mt", **fields}


def line(x_start: int, y_start: int, x_end: int, y_end: int, **fields: Any) -> Element:
    """Return a dashed one pixel line."""
    return {
        "type": "line",
        "x_start": x_start,
        "y_start": y_start,
        "x_end": x_end,
        "y_end": y_end,
        "dashed": True,
        "dash_length": 2,
        "space_length": 2,
        **fields,
    }


async def render(elements: list[Element], width: int, height: int) -> Image.Image:
    """Render elements on a white canvas."""
    image = await generate_image(width=width, height=height, elements=elements, background="white")
    return image.convert("RGB")


def save(image: Image.Image, name: str) -> None:
    """Write a picture with a thin border, so it stands out on a white page."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ImageOps.expand(image, border=1, fill="black").save(OUTPUT_DIR / f"{name}.png")
    print(f"  OK  {name}.png")


def without_patterns(elements: list[Element]) -> list[Element]:
    """Return the same payload as a renderer that does not know `pattern` draws it."""
    return [{key: value for key, value in element.items() if key != "pattern"} for element in elements]


def tone_ramp() -> list[Element]:
    """Bars with a tone each, the way other e-paper frameworks show their gray backgrounds."""
    levels = [100, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 0]
    elements: list[Element] = []
    for index, level in enumerate(levels):
        x = 30 + index * 46
        elements.append(text(str(level), x + 18, 14, 13))
        elements.append(
            rectangle(
                x,
                40,
                36,
                360,
                radius=12,
                corners="all",
                outline="black" if level == 0 else None,
                pattern={"type": "tone", "level": level},
            )
        )
    elements.append(
        rectangle(
            20,
            418,
            760,
            44,
            radius=12,
            corners="all",
            outline=None,
            pattern={"type": "tone", "level": 22},
        )
    )
    elements.append(text("Tone backgrounds: level is the share of ink, in percent", 400, 430, 18))
    return elements


def pattern_types() -> list[Element]:
    """Every pattern type, angle and a few parameters, each with a caption."""
    cells: list[tuple[str, dict[str, Any] | str]] = [
        ("hatch (45)", "hatch"),
        ("hatch angle 135", {"type": "hatch", "angle": 135}),
        ("hatch angle 0", {"type": "hatch", "angle": 0}),
        ("hatch angle 90", {"type": "hatch", "angle": 90}),
        ("hatch angle 30", {"type": "hatch", "angle": 30, "spacing": 7}),
        ("hatch width 3", {"type": "hatch", "width": 3, "spacing": 9}),
        ("dots", "dots"),
        ("dots width 3", {"type": "dots", "width": 3, "spacing": 9}),
        ("grid", {"type": "grid", "spacing": 8}),
        ("tone level 25", {"type": "tone", "level": 25}),
        ("tone level 50", {"type": "tone", "level": 50}),
        ("tone level 75", {"type": "tone", "level": 75}),
        ("red hatch on yellow", {"type": "hatch", "color": "red", "width": 2, "spacing": 6}),
        ("red dots", {"type": "dots", "color": "red", "width": 2, "spacing": 7}),
        ("red grid", {"type": "grid", "color": "red", "spacing": 10}),
        ("red tone", {"type": "tone", "level": 40, "color": "red"}),
    ]
    elements: list[Element] = []
    for index, (caption, pattern) in enumerate(cells):
        x = 20 + (index % 4) * 190
        y = 20 + (index // 4) * 118
        fill = "yellow" if caption == "red hatch on yellow" else None
        elements.append(rectangle(x, y, 170, 80, radius=8, corners="all", fill=fill, pattern=pattern))
        elements.append(text(caption, x + 85, y + 86, 13))
    return elements


def layers() -> list[Element]:
    """Fill, pattern and outline in order, rounded corners, alpha and shapes that touch."""
    return [
        rectangle(
            20,
            20,
            220,
            120,
            fill="yellow",
            radius=20,
            corners="all",
            outline="black",
            width=3,
            pattern={"type": "hatch", "color": "red", "width": 2, "spacing": 8},
        ),
        text("fill, pattern, then outline", 130, 148, 13),
        rectangle(
            260,
            20,
            220,
            120,
            radius=40,
            corners="top_left,bottom_right",
            width=2,
            pattern={"type": "hatch", "angle": 0, "spacing": 5},
        ),
        text("clipped to the rounded corners", 370, 148, 13),
        rectangle(
            500,
            20,
            280,
            120,
            fill="#DDDDFF",
            outline=None,
            pattern={"type": "hatch", "color": "#FF000090", "width": 5, "spacing": 14},
        ),
        text("color with alpha blends", 640, 148, 13),
        rectangle(20, 200, 105, 120, outline=None, pattern="hatch"),
        rectangle(125, 200, 105, 120, outline=None, pattern="hatch"),
        rectangle(230, 200, 105, 120, outline=None, pattern="hatch"),
        text("three shapes that touch: one pattern, no seams", 177, 328, 13),
        rectangle(
            380, 200, 400, 120, fill="white", pattern={"type": "dots", "spacing": 6, "width": 2}, outline="black"
        ),
        text("no fill: the red below shows between the white lines", 580, 328, 13),
        rectangle(400, 220, 360, 40, fill="red", outline=None),
        rectangle(
            400,
            220,
            360,
            80,
            outline=None,
            pattern={"type": "hatch", "angle": 0, "spacing": 4, "width": 2, "color": "white"},
        ),
    ]


def dithering() -> tuple[list[Element], list[Element]]:
    """Grays that a display dithers next to patterns that are already exact pixels."""
    grays = [("dark_gray", None), ("gray", None), ("light_gray", None)]
    elements: list[Element] = []
    for index, (color, _) in enumerate(grays):
        elements.append(rectangle(20 + index * 130, 20, 110, 90, fill=color, outline="black"))
        elements.append(text(color, 75 + index * 130, 116, 13))
    for index, level in enumerate((75, 50, 25)):
        elements.append(
            rectangle(
                420 + index * 130,
                20,
                110,
                90,
                outline="black",
                pattern={"type": "tone", "level": level},
            )
        )
        elements.append(text(f"tone {level}", 475 + index * 130, 116, 13))
    elements.append(rectangle(20, 150, 360, 40, outline="black", pattern="hatch"))
    elements.append(rectangle(420, 150, 360, 40, outline="black", pattern={"type": "dots", "spacing": 5}))
    return elements, []


async def dithering_picture() -> Image.Image:
    """Stack the picture as rendered over the same picture after 1-bit dithering."""
    elements, _ = dithering()
    rendered = await render(elements, 800, 210)
    dithered = rendered.convert("1").convert("RGB")
    sheet = Image.new("RGB", (800, 470), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 2), "As rendered", fill="black")
    sheet.paste(rendered, (0, 14))
    draw.text((10, 236), "After 1-bit Floyd-Steinberg dithering: the grays change, the patterns do not", fill="black")
    sheet.paste(dithered, (0, 248))
    return sheet


def calendar_week() -> list[Element]:
    """A week grid like the ones calendar widgets draw, using the patterns."""
    left, top, column, header, row = 10, 10, 111, 34, 145
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    elements: list[Element] = [rectangle(0, 0, 800, 480, outline="black", radius=8, corners="all")]
    for index, name in enumerate(names):
        x = left + index * column
        today = index == 2
        if today:
            elements.append(rectangle(x, top, column, header, fill="black", outline=None))
        elements.append(text(name, x + column // 2, top + 8, 16, color="white" if today else "black"))
    for week in range(3):
        y = top + header + week * row
        for index in (5, 6):
            elements.append(
                rectangle(
                    left + index * column + 1,
                    y + 1,
                    column - 1,
                    row - 1,
                    outline=None,
                    pattern={"type": "tone", "level": 14},
                )
            )
        for index in range(7):
            elements.append(
                text(str(10 + week * 7 + index), left + index * column + column - 12, y + 3, 11, anchor="rt")
            )
    for index in range(8):
        x = left + index * column
        elements.append(line(x, top + header, x, top + header + 3 * row))
    for week in range(4):
        y = top + header + week * row
        elements.append(line(left, y, left + 7 * column, y))
    bar_y = top + header + 22
    elements.append(
        rectangle(
            left + 3 * column + 3,
            bar_y,
            3 * column - 6,
            20,
            radius=4,
            corners="all",
            pattern={"type": "hatch", "spacing": 4},
        )
    )
    elements.append(text("Product offsite", left + 4 * column + 20, bar_y + 3, 12, stroke_width=2, stroke_fill="white"))
    elements.append(
        rectangle(
            left + 2 * column + 3,
            bar_y,
            column - 6,
            20,
            radius=4,
            corners="all",
            pattern={"type": "dots", "spacing": 4},
        )
    )
    elements.append(text("Audit", left + 2 * column + column // 2, bar_y + 3, 12, stroke_width=2, stroke_fill="white"))
    second = top + header + row + 22
    elements.append(
        rectangle(
            left + 1 * column + 3,
            second,
            4 * column - 6,
            20,
            radius=4,
            corners="all",
            fill="red",
            outline="red",
            pattern={"type": "hatch", "color": "yellow", "width": 2, "spacing": 7},
        )
    )
    elements.append(text("Summer break", left + 3 * column, second + 3, 12, stroke_width=2, stroke_fill="white"))
    for day, title, when in ((0, "Planning", "09:00"), (2, "Standup", "09:30"), (4, "Demo", "14:00")):
        y = top + header + 2 * row + 24
        x = left + day * column + 4
        elements.append(rectangle(x, y, 3, 30, fill="black", outline=None))
        elements.append(text(title, x + 8, y, 12, anchor="lt"))
        elements.append(text(when, x + 8, y + 15, 11, anchor="lt"))
    return elements


async def main() -> None:
    """Write every picture."""
    save(await render(tone_ramp(), 800, 480), "tone_ramp")
    save(await render(pattern_types(), 800, 480), "pattern_types")
    save(await render(layers(), 800, 340), "layers")
    save(await dithering_picture(), "dithering")
    week = calendar_week()
    save(await render(week, 800, 480), "calendar_week")
    save(await render(without_patterns(week), 800, 480), "calendar_week_older_renderer")


if __name__ == "__main__":
    asyncio.run(main())
