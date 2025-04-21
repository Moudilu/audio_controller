#!/usr/bin/env python

import logging

from argparse import ArgumentParser
from asyncio import run, TaskGroup

from .event_router import get_event_router


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        "-log",
        "--loglevel",
        default="info",
        help="One of debug, info, warning, error. Default=info",
        choices=["debug", "info", "warning", "error"],
    )
    parser.add_argument("--pcm", action="append", default=[], help="Enable PCM monitor")
    parser.add_argument(
        "--hk970", action="store_true", help="Control HK970 via infrared"
    )
    parser.add_argument(
        "--rc",
        action="store_true",
        help="Receive and process remote control inputs",
    )
    parser.add_argument(
        "--bt",
        action="store_true",
        help="Enable Bluetooth controller",
    )
    parser.add_argument(
        "--api",
        action="append",
        default=[],
        type=int,
        help="Serve the REST API on the specified port.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel.upper())

    logger = logging.getLogger()

    async def init():
        async with TaskGroup() as tg:
            # Instantiate all devices
            for pcm in args.pcm:
                from .devices.pcm_monitor import PcmMonitor

                PcmMonitor(tg, pcm)
            if args.hk970:
                from .devices.hk970 import HK970

                HK970()
            if args.rc:
                from .devices.remote_control import RemoteControl

                RemoteControl(tg)
            if args.bt:
                from .devices.bluetoothController import BluetoothController

                await BluetoothController(tg)
            if args.api:
                from .devices.rest_api import RestApi

                RestApi(tg, args.api)

            # Initialization complete, start forwarding events
            get_event_router().start_routing()

    # Run the loop
    run(init())

    logger.error("Loop exited unexpectedly. Stop audio controller.")


if __name__ == "main":
    main()
