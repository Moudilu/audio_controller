#!/usr/bin/env python

import logging

from argparse import ArgumentParser
from asyncio import TaskGroup, run

from .pcm_monitor import PcmMonitor
from .hk970 import HK970


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

    # Instantiate all devices
    pcm = PcmMonitor("E30")
    HK970()

    # Run the loop
    run(runner(pcm.monitor()))

    logger.error("Loop exited unexpectedly. Stop audio controller.")


async def runner(*args):
    async with TaskGroup() as tg:
        for coro in args:
            tg.create_task(coro)


if __name__ == "main":
    main()
