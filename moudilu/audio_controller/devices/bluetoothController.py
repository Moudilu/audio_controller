from asyncio import TaskGroup, get_running_loop
import logging
from typing import Any, Generator

from dbus_next import is_object_path_valid, is_bus_name_valid, DBusError
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

    def __init__(self, tg: TaskGroup, hciNumber: int = 0):
        self._logger = logging.getLogger(f"BT hci{hciNumber}")
        self._hci = hciNumber
        self._tg = tg

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
        get_event_router().subscribe(
            (Event.KEY_OPENCLOSE, Event.API_BLUETOOTH_ON),
            lambda e, c: self._tg.create_task(self.power_on()),
        )
        get_event_router().subscribe(
            (Event.KEY_OPENCLOSE_LONG, Event.API_BLUETOOTH_DISCOVERABLE),
            lambda e, c: self._tg.create_task(self.make_discoverable()),
        )
        get_event_router().subscribe(
            (Event.API_BLUETOOTH_OFF,),
            lambda e, c: self._tg.create_task(self.power_off()),
        )

        return self

    async def make_discoverable(self) -> None:
        """Turn BT on and make device discoverable"""
        self._agent.start_pairing_mode()
        await self.power_on()

    async def power_on(self) -> None:
        """Power the BT adapter and make it temporarily discoverable

        If discoverable, can be seen by other devices and connection be requested."""
        self._logger.info(
            "Turning adapter on, make it discoverable for the next %s seconds",
            self.DISCOVERABLE_TIMEOUT,
        )
        await self._adapter.set_powered(True)
        await self._adapter.set_discoverable(True)

    async def power_off(self) -> None:
        self._logger.info("Turning adapter off")
        await self._adapter.set_powered(False)

    async def stop_discoverable(
        self,
    ) -> None:
        """Set the adapter into the undiscoverable state

        If discoverable, can be seen by other devices and connection be requested."""
        self._logger.info("Adapter is not discoverable anymore")
        await self._adapter.set_discoverable(False)

    async def trust_device(self, device_path: str) -> None:
        """Sets the specified device as trusted"""
        device_introspection = await self._bus.introspect(
            self.BLUEZ_DBUS_SERVICE_NAME, device_path
        )
        device_object = self._bus.get_proxy_object(
            self.BLUEZ_DBUS_SERVICE_NAME, device_path, device_introspection
        )
        device = device_object.get_interface("org.bluez.Device1")
        await device.set_trusted(True)
        self._logger.info(
            "Trust device %s (%s)", await device.get_alias(), await device.get_address()
        )

    async def forget_device(self, device_path: str) -> None:
        """Forgets the state of the specified device"""
        self._logger.debug("Remove device %s", device_path)
        await self._adapter.call_remove_device(device_path)

    async def _init_dbus(self) -> None:
        """Initialize all required dbus interfaces"""

        self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        adapter_path = f"/org/bluez/hci{self._hci}"
        adapter_introspection = await self._bus.introspect(
            self.BLUEZ_DBUS_SERVICE_NAME, adapter_path
        )
        adapter_object = self._bus.get_proxy_object(
            self.BLUEZ_DBUS_SERVICE_NAME, adapter_path, adapter_introspection
        )
        # The adapter interface as specified in
        # https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.Adapter.rst
        self._adapter = adapter_object.get_interface("org.bluez.Adapter1")

        self._agent = await _BluetoothAgent.register_agent(self)

    def __await__(self) -> Generator[Any, Any, "BluetoothController"]:
        """Make the object itself awaitable"""
        return self._init().__await__()


class _BluetoothAgent(ServiceInterface):
    """Implements a Bluez authorization agent

    It implements part of the interface defined in
    https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.Agent.rst
    The remaining methods seem to be not required"""

    PAIRING_TIMEOUT = BluetoothController.DISCOVERABLE_TIMEOUT
    """Time in seconds, for which pairing is allowed"""

    _allow_pairing: bool = False
    """If True, pairing requests are accepted, otherwhise denied"""

    def __init__(self, controller: BluetoothController, bus: MessageBus):
        self._controller = controller

        # Use the module name for the bus name and the path, with a fallback
        self.bus_name = (
            __name__
            if is_bus_name_valid(__name__)
            else "audio_controller.bluetooth_agent"
        )
        super().__init__("org.bluez.Agent1")
        path = "/" + __name__.replace(".", "/")
        self.path = (
            path if is_object_path_valid(path) else "/audio_controller/bluetooth_agent"
        )
        controller._logger.info(
            "Exporting bluetooth agent on bus '%s', path '%s'", self.bus_name, self.path
        )

        bus.export(self.path, self)

    async def register_agent(controller: BluetoothController) -> "_BluetoothAgent":
        """Create and register a bluetooth agent"""
        agent = _BluetoothAgent(controller, controller._bus)

        agent_manager_path = "/org/bluez"
        agent_manager_introspection = await controller._bus.introspect(
            controller.BLUEZ_DBUS_SERVICE_NAME, agent_manager_path
        )
        agent_manager_object = controller._bus.get_proxy_object(
            controller.BLUEZ_DBUS_SERVICE_NAME,
            agent_manager_path,
            agent_manager_introspection,
        )
        agent_manager = agent_manager_object.get_interface("org.bluez.AgentManager1")

        # Promote the agent to be default agent
        await agent_manager.call_register_agent(agent.path, "NoInputNoOutput")
        await agent_manager.call_request_default_agent(agent.path)

        return agent

    def start_pairing_mode(self) -> None:
        """Allow pairing for the next PAIRING_TIMEOUT seconds or until the first client
        got paired"""
        self.stop_pairing_mode()  # Cancel the timer
        self._allow_pairing = True
        self._pairing_timeout_timer = get_running_loop().call_later(
            self.PAIRING_TIMEOUT, self.stop_pairing_mode
        )

    def stop_pairing_mode(self) -> None:
        """Deny further pairing requests"""
        self._allow_pairing = False
        try:
            self._pairing_timeout_timer.cancel()
        except AttributeError:
            pass

    @method()
    def AuthorizeService(self, device: "o", uuid: "s") -> None:  # noqa: F821
        """Accept or deny pairing request

        If agent is in pairing mode, it allows the request and stops pairing mode.
        Otherwhise, request is denied.

        This method is called when a device tries to pair.
        If no error is returned, the call is considered succesfull and pairing is
        granted.
        """
        if self._allow_pairing:
            self._controller._logger.info(
                "Authorize device on path %s with UUID %s", device, uuid
            )
            self.stop_pairing_mode()
            self._controller._tg.create_task(self._controller.trust_device(device))
            self._controller._tg.create_task(self._controller.stop_discoverable())
        else:
            # Forget the device state, this enables later pairing attempts
            self._controller._tg.create_task(self._controller.forget_device(device))
            raise DBusError("org.bluez.Error.Rejected", "Not in pairing mode")

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
