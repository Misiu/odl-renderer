"""generate_image() consults allow_source before loading a URL, an image file or a font file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from odl_renderer import SourceNotAllowedError, generate_image, media_loader
from odl_renderer.fonts import _ASSETS_DIR

from .test_event_loop import _dlimg, _FakeSession, _png

TEXT = {"type": "text", "value": "hi", "x": 0, "y": 0, "size": 12}


class _Guard:
    """Refuses everything not in *allowed*, recording what it was asked."""

    def __init__(self, *allowed: str) -> None:
        self.allowed = set(allowed)
        self.asked: list[tuple[str, str]] = []

    def __call__(self, kind: str, source: str) -> bool:
        self.asked.append((kind, source))
        return source in self.allowed


async def test_refused_url_is_never_requested() -> None:
    session = _FakeSession(_png((0, 0, 255)))
    guard = _Guard()

    with pytest.raises(SourceNotAllowedError) as exc_info:
        await generate_image(40, 40, [_dlimg("https://example.com/a.png")], session=session, allow_source=guard)  # type: ignore[arg-type]

    assert (exc_info.value.kind, exc_info.value.source) == ("url", "https://example.com/a.png")
    assert session.calls == []


@pytest.mark.parametrize(
    "element",
    [
        _dlimg("/outside/secret.png"),
        {**TEXT, "font": "/outside/secret.ttf"},
        {"type": "multiline", "value": "a|b", "delimiter": "|", "x": 0, "offset_y": 10, "font": "/outside/secret.ttf"},
        {
            "type": "progress_bar",
            "x_start": 0,
            "y_start": 0,
            "x_end": 30,
            "y_end": 10,
            "progress": 50,
            "show_percentage": True,
            "font_name": "/outside/secret.ttf",
        },
        {
            "type": "diagram",
            "x": 0,
            "height": 30,
            "bars": {"values": "a,1;b,2", "color": "black", "font": "/outside/secret.ttf"},
        },
        {"type": "debug_grid", "font": "/outside/secret.ttf"},
    ],
    ids=["image", "text_font", "multiline_font", "progress_bar_font", "diagram_bars_font", "debug_grid_font"],
)
async def test_refused_file_is_not_opened(element: dict[str, Any]) -> None:
    guard = _Guard()

    with pytest.raises(SourceNotAllowedError) as exc_info:
        await generate_image(40, 40, [TEXT, element], allow_source=guard)

    assert exc_info.value.kind == "file"
    assert exc_info.value.source.startswith("/outside/secret.")
    # Refused before the file is looked at: the error does not reveal whether it exists.
    assert "not found" not in str(exc_info.value).lower()


async def test_allowed_sources_render(tmp_path: Path) -> None:
    image_path = tmp_path / "blue.png"
    image_path.write_bytes(_png((0, 0, 255)))
    font_path = str(_ASSETS_DIR / "rbm.ttf")
    guard = _Guard(str(image_path), font_path, "https://example.com/a.png")
    session = _FakeSession(_png((255, 0, 0)))
    elements = [
        _dlimg(str(image_path)),
        _dlimg("https://example.com/a.png", x=20),
        {**TEXT, "y": 25, "font": font_path},
    ]

    img = await generate_image(40, 40, elements, session=session, allow_source=guard)  # type: ignore[arg-type]

    assert img.getpixel((10, 10)) == (0, 0, 255, 255)
    assert img.getpixel((30, 10)) == (255, 0, 0, 255)
    assert sorted(guard.asked) == sorted(
        [("file", str(image_path)), ("url", "https://example.com/a.png"), ("file", font_path)]
    )


async def test_embedded_and_named_sources_are_not_subject_to_the_guard() -> None:
    guard = _Guard()
    elements = [
        _dlimg(_png((0, 0, 255))),
        _dlimg(Image.new("RGB", (20, 20), "red"), x=20),
        {**TEXT, "y": 25, "font": "rbm"},
    ]

    await generate_image(40, 40, elements, allow_source=guard)

    assert guard.asked == []


async def test_hidden_elements_are_not_checked() -> None:
    guard = _Guard()

    await generate_image(40, 40, [_dlimg("/outside/secret.png", visible=False)], allow_source=guard)

    assert guard.asked == []


@pytest.mark.parametrize("font", ["../../outside/secret.ttf", "fonts/../../secret"])
async def test_font_name_cannot_leave_the_font_directories(font: str, tmp_path: Path) -> None:
    # Enforced with or without a guard: a name is only ever meant to be looked up inside font_dirs.
    with pytest.raises(SourceNotAllowedError):
        await generate_image(40, 40, [{**TEXT, "font": font}], font_dirs=[str(tmp_path)])


async def test_oversized_http_image_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_loader, "MAX_IMAGE_BYTES", 1024)
    session = _FakeSession(b"x" * 4096)

    with pytest.raises(ValueError, match=r"example\.com/big\.png: image is larger than"):
        await generate_image(40, 40, [_dlimg("https://example.com/big.png")], session=session)  # type: ignore[arg-type]


async def test_oversized_http_image_without_a_length_header_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_loader, "MAX_IMAGE_BYTES", 1024)
    session = _FakeSession(b"x" * 4096)
    response = session.get("https://example.com/big.png")
    response.content_length = None
    session.get = lambda url, timeout=None: response  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="image is larger than"):
        await generate_image(40, 40, [_dlimg("https://example.com/big.png")], session=session)  # type: ignore[arg-type]


async def test_http_fetch_is_bounded_by_a_timeout() -> None:
    session = _FakeSession(_png((0, 0, 255)))

    await generate_image(40, 40, [_dlimg("https://example.com/a.png")], session=session)  # type: ignore[arg-type]

    assert session.timeouts[0].total == media_loader.FETCH_TIMEOUT_SECONDS


async def test_http_timeout_is_reported_with_the_url() -> None:
    class _TimingOutSession:
        def get(self, url: str, timeout: Any = None) -> Any:
            raise TimeoutError

    with pytest.raises(ValueError, match=r"example\.com/slow\.png: timed out after 30 s"):
        await generate_image(40, 40, [_dlimg("https://example.com/slow.png")], session=_TimingOutSession())  # type: ignore[arg-type]
