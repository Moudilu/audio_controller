from asyncio import sleep, get_running_loop
from logging import getLogger

from psutil import NoSuchProcess, AccessDenied, Process

from ..event_router import Event, router


class PcmMonitor:
    """Monitor ALSA PCM devices.

    Send events when playback on these start or stop."""

    period: float = 1
    """Interval at which status of PCM device is polled"""

    was_closed: bool
    """Last read state of the PCM device"""

    def __init__(self, device: str, subdevice: int = 0) -> None:
        self.device = device
        self.subdevice = subdevice
        self.device_name = f"{device}.{subdevice}"
        self._status_file = (
            f"/proc/asound/{self.device}/pcm0p/sub{self.subdevice}/status"
        )

        self._router = router
        self._logger = getLogger(self.device_name)

        # Instantiate the monitoring task
        get_running_loop().create_task(self.monitor())

    async def monitor(self) -> None:
        """Runs infinite loop

        Sends events when playback starts/stops.
        First sends the event for the currently detected state.
        """
        self.was_closed = self.is_closed()
        self._logger.info(
            "%s was %s at startup. Start monitoring.",
            self.device_name,
            "stopped" if self.was_closed else "running",
        )
        self.send_event(self.was_closed)

        while True:
            if (state := self.is_closed()) != self.was_closed:
                self.send_event(state)
                self.was_closed = state
            await sleep(self.period)

    def send_event(self, is_closed: bool) -> None:
        """Send playback event"""
        if is_closed is True:
            self._logger.info(
                "Detected stop of playback on %s PCM device", self.device_name
            )
            self._router.fire_event(Event.PLAYBACK_STOP, f"{self.device} PCM device")
        else:
            self._logger.info(
                "Process '%s' started playback on %s PCM device",
                self.get_playing_process(),
                self.device_name,
            )
            self._router.fire_event(Event.PLAYBACK_START, f"{self.device} PCM device")

    def is_closed(self) -> bool:
        """Detects if this device is closed or not.

        Returns true if the state of this device is closed.
        Otherwhise (running, closing, ...) returns false.
        """
        with open(self._status_file, "r") as soundStatusfile:
            status = soundStatusfile.readline().strip("\n")
        self._logger.debug("%s status: %s", self.device_name, status)
        return status == "closed"

    def get_playing_process(self) -> str:
        """Gets the process currently playing on this device

        :returns: Commandline of the process currently playing on this device.
                  'UNKNOWN' if nothing is playing.
        """
        with open(self._status_file, "r") as soundStatusfile:
            for line in soundStatusfile:
                if line.startswith("owner_pid"):
                    # Expect this line in the second line in format "owner_pid   : 615"
                    try:
                        tid = int(line.split(":")[-1].strip())
                        cmd = Process(tid).cmdline()
                        return " ".join(cmd)
                    except ValueError:
                        self._logger.exception(
                            "Failed to read PID from line '%s'", line
                        )
                    except (NoSuchProcess, AccessDenied):
                        self._logger.exception(
                            "Failed to get info of process from line '%s'", line
                        )

        return "UNKNOWN"
