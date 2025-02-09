from enum import StrEnum, auto
from logging import Logger
import logging
from typing import Callable


class Event(StrEnum):
    PLAYBACK_START = auto()
    PLAYBACK_STOP = auto()


class EventRouter:
    _callbacks: set[Callable[[Event, str], None]] = set()

    def __init__(self) -> None:
        self._logger: Logger = logging.getLogger("EventRouter")

    def add_listener(self, callback: Callable[[Event, str], None]) -> None:
        """Register callback function to be forwarded any event"""
        self._callbacks.add(callback)
        self._logger.debug("Add event callback %s", callback)

    def fire_event(self, event: Event, caller: str) -> None:
        """Broadcast an event to all listeners

        :param event: Event enum
        : param caller: String representing who fired the event
        """
        for c in self._callbacks:
            c(event, caller)
        self._logger.debug(
            "Called %i callbacks with event %s from %s",
            len(self._callbacks),
            event.name,
            caller,
        )


router = EventRouter()
"""Global singleton of the event router"""
