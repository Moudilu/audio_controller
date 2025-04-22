from asyncio import TimerHandle, get_running_loop
from logging import getLogger
from typing import Union

from lirc import Client

from ..event_router import Event, get_event_router


class HK970:
    """Control and track state of a Harman Kardon HK970 amplifier.

    IR Remote commands are received via evdev events.
    Amp is controlled with IR commands issued with Lirc.
    """

    _shutdown_timer: Union[TimerHandle, None] = None
    """Timer which schedules delayed powering off of the amp"""
    SHUTDOWN_DELAY: float = 60
    """Delay in seconds to wait before turning amp off after playback stops"""

    def __init__(self) -> None:
        self._lirc = Client()

        get_event_router().subscribe((Event.PLAYBACK_START,), self.playback_start)
        get_event_router().subscribe((Event.PLAYBACK_STOP,), self.playback_stop)

        self._logger = getLogger("HK970")

        # Start in a well defined state
        # If stream is currently running, amp will be restarted soon after by an event
        self.power_off()

    def playback_stop(self):
        self._shutdown_timer = get_running_loop().call_later(
            self.SHUTDOWN_DELAY, self.power_off
        )

    def playback_start(self):
        if self._shutdown_timer is not None:
            self._shutdown_timer.cancel()
        self.power_on()

    def power_on(self) -> None:
        self._lirc.send_once("HK970", "KEY_POWER")
        self._logger.info("Power HK970 on")

    def power_off(self) -> None:
        self._lirc.send_once("HK970", "KEY_SLEEP")
        self._logger.info("Power HK970 off")
