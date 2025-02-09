from lirc import Client
from logging import getLogger

from .event_router import Event, router


class HK970:
    """Control and track state of a Harman Kardon HK970 amplifier.

    IR Remote commands are received via evdev events.
    Amp is controlled with IR commands issued with Lirc.
    """

    def __init__(self) -> None:
        self._lirc = Client()

        router.add_listener(self.process_events)

        self._logger = getLogger("HK970")

    def process_events(self, event: Event, caller: str) -> None:
        match event:
            case Event.PLAYBACK_START:
                self.power_on()
            case Event.PLAYBACK_STOP:
                self.power_off()
            case _:
                pass

    def power_on(self) -> None:
        self._lirc.send_once("HK970", "KEY_POWER")
        self._logger.info("Power HK970 on")

    def power_off(self) -> None:
        self._lirc.send_once("HK970", "KEY_SLEEP")
        self._logger.info("Power HK970 off")
