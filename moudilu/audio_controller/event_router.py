from asyncio import Future, get_running_loop
from enum import StrEnum, auto
from logging import Logger
import logging
from typing import Callable


class Event(StrEnum):
    PLAYBACK_START = auto()
    PLAYBACK_STOP = auto()


def get_event_router() -> "get_event_router._EventRouter":
    """Returns the global singleton Event Router

    After initialization is complete, call start_routing on the returned object to
    start routing of events."""

    class _EventRouter:
        _callbacks: set[Callable[[Event, str], None]] = set()

        def __init__(self) -> None:
            self._logger: Logger = logging.getLogger("EventRouter")
            self._start_routing: Future = get_running_loop().create_future()

        def add_listener(self, callback: Callable[[Event, str], None]) -> None:
            """Register callback function to be forwarded any event"""
            self._callbacks.add(callback)
            self._logger.debug("Add event callback %s", callback)

        async def fire_event(self, event: Event, caller: str) -> None:
            """Broadcast an event to all listeners

            :param event: Event enum
            : param caller: String representing who fired the event
            """
            await self._start_routing
            for c in self._callbacks:
                c(event, caller)
            self._logger.debug(
                "Called %i callbacks with event %s from %s",
                len(self._callbacks),
                event.name,
                caller,
            )

        def start_routing(self) -> None:
            """Start to route events.

            Has to be called before any events start to be distributed"""
            self._start_routing.set_result(None)
            self._logger.debug("Start routing events")

    # Return the singleton object, create if it does not yet exist
    try:
        return get_event_router.global_router
    except AttributeError:
        get_event_router.global_router = _EventRouter()
        return get_event_router.global_router
