from asyncio import TaskGroup
import itertools
import logging

import uvicorn
from fastapi import FastAPI, APIRouter, Request

from ..event_router import get_event_router, Event

# Operations for bluetooth
bluetooth = APIRouter(prefix="/bluetooth")


@bluetooth.get("/on")
async def bluetooth_on(request: Request):
    """Turn on Bluetooth."""
    await get_event_router().fire_event(
        Event.API_BLUETOOTH_ON, f"REST API call from {request.client.host}"
    )
    logging.getLogger("API").debug(
        "Received request to turn on Bluetooth from %s", request.client.host
    )


@bluetooth.get("/off")
async def bluetooth_off(request: Request):
    """Turn off Bluetooth."""
    await get_event_router().fire_event(
        Event.API_BLUETOOTH_OFF, f"REST API call from {request.client.host}"
    )
    logging.getLogger("API").debug(
        "Received request to turn off Bluetooth from %s", request.client.host
    )


@bluetooth.get("/discoverable")
async def bluetooth_discoverable(request: Request):
    """Make Bluetooth discoverable"""
    await get_event_router().fire_event(
        Event.API_BLUETOOTH_DISCOVERABLE, f"REST API call from {request.client.host}"
    )
    logging.getLogger("API").debug(
        "Received request to make Bluetooth discoverable from %s", request.client.host
    )


# Create the main FastAPI app and include the router
api = APIRouter(prefix="/api/v1")
api.include_router(bluetooth)
app = FastAPI()
app.include_router(api)


class RestApi:
    """Expose a REST API which allows to control some aspects of the system."""

    def __init__(self, tg: TaskGroup, ports: list[int]) -> None:
        """
        Initialize the RestAPI instance.

        :tg: The task group to which the API server will be added.
        :ports: List of ports to serve the API on.
        """
        # For each port, create a server both on IPv4 and IPv6
        for ip, port in itertools.product(("::", "0.0.0.0"), ports):
            # This instantiates a server programmatically. Note that this is not the
            # recommended way to start a FastAPI app (which would be to invoke it via
            # the fastapi command)
            # The server is started with the default asyncio implementation instead of
            # the faster uvloop.
            config = uvicorn.Config(
                __name__ + ":app",
                host=ip,
                port=port,
                log_config=None,
                access_log=False,
            )
            server = uvicorn.Server(config)
            tg.create_task(server.serve())
