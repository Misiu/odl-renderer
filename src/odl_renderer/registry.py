from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    import aiohttp

    from .types import DataProvider, DrawingContext, ElementType

# Type alias for element handler functions. Handlers are synchronous: they run in a
# worker thread and must not touch the event loop.
_HandlerFn = Callable[..., None]

# Type alias for element resolvers: the async half of an element, run on the event
# loop before drawing. Returns the element to draw (a copy carrying whatever was fetched).
_ResolverFn = Callable[..., Awaitable[dict[str, Any]]]

# Global registries populated by decorators
_handlers: dict[ElementType, tuple[_HandlerFn, list[str]]] = {}
_resolvers: dict[ElementType, _ResolverFn] = {}


def element_handler(
    element_type: ElementType,
    requires: list[str] | None = None,
    resolve: _ResolverFn | None = None,
) -> Callable[[_HandlerFn], _HandlerFn]:
    """
    Decorator to register and validate element handlers.

    Args:
        element_type: The ElementType this handler processes
        requires: List of required element keys (validated before handler runs)
        resolve: Optional coroutine ``resolve(element, *, session, data_provider)`` for
                 elements that need I/O (HTTP, history). It runs on the event loop before
                 any drawing and returns the element the handler will receive.
    """

    def validate(element: dict[str, Any]) -> None:
        if requires:
            missing = [key for key in requires if key not in element]
            if missing:
                raise ValueError(f"{element_type.value} requires: {', '.join(missing)}")

    def decorator(func: _HandlerFn) -> _HandlerFn:
        @wraps(func)
        def wrapper(ctx: DrawingContext, element: dict[str, Any]) -> None:
            validate(element)
            func(ctx, element)

        _handlers[element_type] = (wrapper, requires or [])

        if resolve is not None:

            @wraps(resolve)
            async def resolver(
                element: dict[str, Any],
                *,
                session: aiohttp.ClientSession | None,
                data_provider: DataProvider | None,
            ) -> dict[str, Any]:
                validate(element)
                return await resolve(element, session=session, data_provider=data_provider)

            _resolvers[element_type] = resolver

        return wrapper

    return decorator


def get_all_handlers() -> dict[ElementType, tuple[_HandlerFn, list[str]]]:
    """Return all registered handlers."""
    return _handlers


def get_resolver(element_type: ElementType) -> _ResolverFn | None:
    """Return the resolver registered for an element type, if it has one."""
    return _resolvers.get(element_type)
