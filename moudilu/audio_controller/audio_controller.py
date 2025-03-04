#!/usr/bin/env python

import logging

from argparse import ArgumentParser
from asyncio import run, TaskGroup

from .event_router import get_event_router
from .devices.bluetoothController import BluetoothController
from .devices.pcm_monitor import PcmMonitor
from .devices.hk970 import HK970
from .devices.remote_control import RemoteControl


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        "-log",
        "--loglevel",
        default="info",
        help="One of debug, info, warning, error. Default=info",
        choices=["debug", "info", "warning", "error"],
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel.upper())

    logger = logging.getLogger()

    async def init():
        async with TaskGroup() as tg:
            # Instantiate all devices
            PcmMonitor(tg, "E30")
            HK970()
            RemoteControl(tg)
            await BluetoothController(tg)

            # Initialization complete, start forwarding events
            get_event_router().start_routing()

    # Run the loop
    run(init())

    logger.error("Loop exited unexpectedly. Stop audio controller.")


if __name__ == "main":
    main()
