from asyncio import get_running_loop
import logging
from typing import Any, Generator

from dbus_next import is_object_path_valid, is_bus_name_valid
from dbus_next.constants import BusType
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method

from ..event_router import get_event_router, Event


class BluetoothController:
    """Class which controls the bluetooth adapter

    It implements the 'Just works' association model. When pairing is triggered, any
    device requesting to pair is trusted.

    In case pairing fails, the device possible is some half-registered state.
    In that case, the following command might help: `bluetoothctl`, then enter
    `devices` to see all registered devices, den `remove <device>` of the
    concerned device. After that, retry pairing.

    TODO:
    - Turn BT off after no device has been connected for some time
    """

    DISCOVERABLE_TIMEOUT = 90
    """Time in seconds, how long the adapter should remain discoverable once set into
    this mode"""

    BLUEZ_DBUS_SERVICE_NAME = "org.bluez"

    def __init__(self, hciNumber: int = 0):
        self._logger = logging.getLogger(f"BT hci{hciNumber}")
        self._hci = hciNumber

    async def _init(self) -> "BluetoothController":
        """Some of the initialization has to be done async. Thus every object of this
        class has to be awaited before using it!."""
        await self._init_dbus()

        # The adapter should always be pairable in this scenario
        await self._adapter.set_pairable(True)

        # Set the discovery timeout
        await self._adapter.set_discoverable_timeout(self.DISCOVERABLE_TIMEOUT)

        powered = await self._adapter.get_powered()
        self._logger.info(
            "The adapter hci%i was found powered %s.",
            self._hci,
            "on" if powered else "off",
        )
        # Start in a well defined state: Powered off
        if powered:
            await self.power_off()

        # Register event handler
        get_event_router().add_listener(self.process_events)

        return self

    def process_events(self, event: Event, caler: str) -> None:
        match event:
            case Event.KEY_OPENCLOSE:
                # Turn BT on
                get_running_loop().create_task(self.power_on())
            case Event.KEY_OPENCLOSE_LONG:
                # Turn BT on and make device discoverable
                get_running_loop().create_task(self.start_discoverable())

    async def power_on(self) -> None:
        self._logger.info("Turning adapter on")
        await self._adapter.set_powered(True)

    async def power_off(self) -> None:
        self._logger.info("Turning adapter off")
        await self._adapter.set_powered(False)

    async def start_discoverable(
        self,
    ) -> None:
        """Set the adapter into the discoverable state

        If discoverable, can be seen by other devices and connection be requested.
        If BT is not powered, first turn it on."""
        if not await self._adapter.get_powered():
            await self.power_on()
        self._logger.info(
            f"Adapter is discoverable for the next {self.DISCOVERABLE_TIMEOUT} seconds"
        )
        await self._adapter.set_discoverable(True)

    async def stop_discoverable(
        self,
    ) -> None:
        """Set the adapter into the undiscoverable state

        If discoverable, can be seen by other devices and connection be requested."""
        self._logger.info("Adapter is not discoverable anymore")
        await self._adapter.set_discoverable(False)

    async def _init_dbus(self) -> None:
        """Initialize all required dbus interfaces"""

        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        adapter_path = f"/org/bluez/hci{self._hci}"
        adapter_introspection = await bus.introspect(
            self.BLUEZ_DBUS_SERVICE_NAME, adapter_path
        )
        adapter_object = bus.get_proxy_object(
            self.BLUEZ_DBUS_SERVICE_NAME, adapter_path, adapter_introspection
        )
        # The adapter interface as specified in
        # https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.Adapter.rst
        self._adapter = adapter_object.get_interface("org.bluez.Adapter1")

        await self._register_agent(bus)

    async def _register_agent(self, bus: MessageBus):
        """Register a Nice bluetooth agent that will give its trust to anyone asking"""
        agent = _NiceBluetoothAgent(self, bus)

        agent_manager_path = "/org/bluez"
        agent_manager_introspection = await bus.introspect(
            self.BLUEZ_DBUS_SERVICE_NAME, agent_manager_path
        )
        agent_manager_object = bus.get_proxy_object(
            self.BLUEZ_DBUS_SERVICE_NAME,
            agent_manager_path,
            agent_manager_introspection,
        )
        agent_manager = agent_manager_object.get_interface("org.bluez.AgentManager1")

        # Promote the nice agent to be default agent
        await agent_manager.call_register_agent(agent.path, "NoInputNoOutput")
        await agent_manager.call_request_default_agent(agent.path)

    def __await__(self) -> Generator[Any, Any, "BluetoothController"]:
        """Make the object itself awaitable"""
        return self._init().__await__()


class _NiceBluetoothAgent(ServiceInterface):
    """Implements a Just-works Bluez authorization agent

    It will trust anyone.
    It is definitely not the most secure, but is good enough for this usecase.

    It implements part of the interface defined in
    https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.Agent.rst
    The remaining methods seem to be not required"""

    def __init__(self, controller: BluetoothController, bus: MessageBus):
        self._controller = controller

        # Use the module name for the bus name and the path, with a fallback
        self.bus_name = (
            __name__
            if is_bus_name_valid(__name__)
            else "audio_controller.nice_bluetooth_agent"
        )
        super().__init__("org.bluez.Agent1")
        path = "/" + __name__.replace(".", "/")
        self.path = (
            path
            if is_object_path_valid(path)
            else "/audio_controller/nice_bluetooth_agent"
        )
        controller._logger.info(
            "Exporting bluetooth agent on bus '%s', path '%s'", self.bus_name, self.path
        )

        bus.export(self.path, self)

    @method()
    def AuthorizeService(self, device: "o", uuid: "s") -> None:  # noqa: F821
        """This method is called when a device tries to pair.

        If no error is returned, the call is considered succesfull and pairing is
        granted.
        """
        self._controller._logger.warning(
            "Authorize device on path %s with UUID %s", device, uuid
        )
        get_running_loop().create_task(self._controller.stop_discoverable())

    @method()
    def Release(self) -> None:
        self._controller._logger.error(
            "Bluetooth pairing agent has been released. What is going on?"
        )

    @method()
    def Cancel(self) -> None:
        self._controller._logger.warning(
            "Authorization has been cancelled by the service."
        )
