from ast import Tuple
from asyncio import TaskGroup
from logging import getLogger
from typing import Dict

from evdev import InputDevice, ecodes
from evdev.events import KeyEvent

from ..event_router import get_event_router, Event


class RemoteControl:
    """Routes events from evdev keyboard devices"""

    KEY_EVENTS: Dict[str, Event] = {
        "KEY_EJECTCLOSECD": Event.KEY_OPENCLOSE,
    }
    """Maps the keycodes to the events to be emitted when the key is released.
    If the key is pressed for long and a corresponding event is in KEY_EVENTS_LONGPRESS,
    the event from there is emitted. If no event is in the other dictionary for this
    key, the event from this KEY_EVENTS dictionary is emitted even if the keypres was
    long."""

    KEY_EVENTS_LONGPRESS: Dict[str, Event] = {
        "KEY_EJECTCLOSECD": Event.KEY_OPENCLOSE_LONG,
    }
    """Maps the keycodes to the events to be emitted when a key is pressed for long.
    If the key is pressed only shortly, the corresponding event from KEY_EVENTS is
    emitted instead."""

    LONGPRESS_THRESHOLD: float = 3.0
    """Time in seconds, after which a keypress is considered long."""

    def __init__(self, tg: TaskGroup, device_number: int = 0) -> None:
        self.device = InputDevice(f"/dev/input/event{device_number}")
        self.device_name = f"evdev{device_number}"

        self._router = get_event_router()
        self._logger = getLogger(self.device_name)

        self._key_down_timestamps: Dict[str, float] = {}
        """For key currently pressed that have registered longpress events, holds the
        timestamp it had been pressed"""

        # Instantiate the monitoring task
        tg.create_task(self._read_keys())

    async def _read_keys(self) -> None:
        self._logger.debug("Reading events from %s", self.device)

        async for ev in self.device.async_read_loop():
            if ev.type == ecodes.EV_KEY:
                ev = KeyEvent(ev)

                # Theoretically it is possible that one code is mapped to several
                # keycodes. In this case, just take the first one.
                if isinstance(ev.keycode, Tuple):
                    self._logger.warning(
                        "Key with several keycodes received: %s. Use %s.",
                        ev.keycode,
                        ev.keycode[0],
                    )
                    ev.keycode = ev.keycode[0]

                if (
                    ev.keystate == ev.key_down
                    and ev.keycode in self.KEY_EVENTS_LONGPRESS
                ):
                    # There is an event for a longpress for this key, track how long it
                    # is pressed
                    self._key_down_timestamps[ev.keycode] = ev.event.timestamp()

                elif ev.keystate == ev.key_up:
                    # A key has been released - emit corresponding event if available
                    if (
                        ev.keycode in self._key_down_timestamps
                        and (
                            ev.event.timestamp() - self._key_down_timestamps[ev.keycode]
                        )
                        >= self.LONGPRESS_THRESHOLD
                    ):
                        # the key was pressed for long and there is an longpress event
                        # registered, fire it
                        self._logger.info("%s long pressed", ev.keycode)
                        await self._router.fire_event(
                            self.KEY_EVENTS_LONGPRESS[ev.keycode], self.device_name
                        )
                    elif ev.keycode in self.KEY_EVENTS:
                        # fire the normal event for this key
                        self._logger.info("%s pressed", ev.keycode)
                        await self._router.fire_event(
                            self.KEY_EVENTS[ev.keycode], self.device_name
                        )

                    # If there is a timestamp registered for this key, remove it
                    try:
                        del self._key_down_timestamps[ev.keycode]
                    except KeyError:
                        pass
