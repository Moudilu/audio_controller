#!/usr/bin/env python

import logging

from argparse import ArgumentParser
from asyncio import run, get_running_loop

from .devices.pcm_monitor import PcmMonitor
from .devices.hk970 import HK970


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
        # Instantiate all devices
        PcmMonitor("E30")
        HK970()

        # handover to the event loop, let the magic happen
        await get_running_loop().create_future()

    # Run the loop
    run(init())

    logger.error("Loop exited unexpectedly. Stop audio controller.")


if __name__ == "main":
    main()
