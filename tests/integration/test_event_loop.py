"""generate_image() awaits I/O on the event loop and draws in a worker thread."""

from __future__ import annotations

import io
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from PIL import Image

from odl_renderer import ElementType, generate_image, registry


def _png(color: tuple[int, int, int], size: tuple[int, int] = (20, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, data: bytes, fail: bool) -> None:
        self._data = data
        self._fail = fail

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self._fail:
            raise RuntimeError("404 Not Found")

    async def read(self) -> bytes:
        return self._data


class _FakeSession:
    """Stands in for aiohttp.ClientSession; records the thread each request is made on."""

    def __init__(self, data: bytes = b"", fail: bool = False) -> None:
        self._data = data
        self._fail = fail
        self.calls: list[tuple[str, int]] = []

    def get(self, url: str) -> _FakeResponse:
        self.calls.append((url, threading.get_ident()))
        return _FakeResponse(self._data, self._fail)


class _RecordingProvider:
    def __init__(self) -> None:
        self.threads: list[int] = []

    async def get_history(self, entity_ids: list[str], start: datetime, end: datetime) -> dict[str, list[dict]]:
        self.threads.append(threading.get_ident())
        now = datetime.now(timezone.utc)
        return {
            entity_id: [
                {"state": str(20 + i), "last_changed": (now - timedelta(hours=3 - i)).isoformat()} for i in range(4)
            ]
            for entity_id in entity_ids
        }


def _dlimg(url: Any, **extra: Any) -> dict[str, Any]:
    return {"type": "dlimg", "url": url, "x": 0, "y": 0, "xsize": 20, "ysize": 20, **extra}


async def test_drawing_runs_off_the_event_loop_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    handler, requires = registry.get_all_handlers()[ElementType.RECTANGLE]
    draw_threads: list[int] = []

    def spy(ctx: Any, element: dict[str, Any]) -> None:
        draw_threads.append(threading.get_ident())
        handler(ctx, element)

    monkeypatch.setitem(registry._handlers, ElementType.RECTANGLE, (spy, requires))

    img = await generate_image(
        50, 50, [{"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 49, "y_end": 49, "fill": "red"}]
    )

    assert img.getpixel((25, 25)) == (255, 0, 0, 255)
    assert draw_threads and draw_threads[0] != threading.get_ident()


async def test_http_image_is_fetched_on_the_event_loop_and_drawn() -> None:
    session = _FakeSession(_png((0, 0, 255)))

    img = await generate_image(40, 40, [_dlimg("https://example.com/a.png")], session=session)  # type: ignore[arg-type]

    assert session.calls == [("https://example.com/a.png", threading.get_ident())]
    assert img.getpixel((10, 10)) == (0, 0, 255, 255)
    assert img.getpixel((30, 30)) == (255, 255, 255, 255)


async def test_http_fetch_failure_names_the_element_and_url() -> None:
    session = _FakeSession(fail=True)
    elements = [
        {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 9, "y_end": 9},
        _dlimg("http://example.com/missing.png"),
    ]

    with pytest.raises(ValueError, match=r"Element 2: Failed to process image: .*missing\.png.*404"):
        await generate_image(40, 40, elements, session=session)  # type: ignore[arg-type]


async def test_undecodable_http_image_names_the_url() -> None:
    session = _FakeSession(b"not an image")

    with pytest.raises(ValueError, match=r"Element 1: Failed to process image: .*example\.com/bad\.png"):
        await generate_image(40, 40, [_dlimg("https://example.com/bad.png")], session=session)  # type: ignore[arg-type]


async def test_hidden_http_image_is_not_fetched() -> None:
    session = _FakeSession(_png((0, 0, 255)))

    await generate_image(40, 40, [_dlimg("https://example.com/a.png", visible=False)], session=session)  # type: ignore[arg-type]

    assert session.calls == []


async def test_plot_history_is_fetched_on_the_event_loop() -> None:
    provider = _RecordingProvider()

    await generate_image(200, 100, [{"type": "plot", "data": [{"entity": "sensor.temp"}]}], data_provider=provider)

    assert provider.threads == [threading.get_ident()]


async def test_caller_elements_are_not_mutated() -> None:
    session = _FakeSession(_png((0, 0, 255)))
    provider = _RecordingProvider()
    elements = [_dlimg("https://example.com/a.png"), {"type": "plot", "data": [{"entity": "sensor.temp"}]}]

    await generate_image(200, 100, elements, session=session, data_provider=provider)  # type: ignore[arg-type]

    assert elements[0]["url"] == "https://example.com/a.png"
    assert "_history" not in elements[1]
