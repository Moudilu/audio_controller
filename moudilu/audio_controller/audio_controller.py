#!/usr/bin/env python

import logging

from argparse import ArgumentParser


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "-log",
        "--loglevel",
        default="warning",
        help="One of debug, info, warning, error. Default=warning",
        choices=["debug", "info", "warning", "error"],
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel.upper())


if __name__ == "main":
    main()
