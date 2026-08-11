"""Simple Timer – status sensor.

Companion to the runtime sensor in sensor.py. Split out so a change to timer
status handling does not touch the runtime counter, and vice versa.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    SIGNAL_STATE_UPDATED,
    STATUS_IDLE,
    STATUS_ACTIVE,
    STATUS_DELAYED_START,
    STATUS_SCHEDULED,
    STATUS_OPTIONS,
)
from .helpers import device_info_for_switch, instance_title

if TYPE_CHECKING:
    # Import-time cycle otherwise: sensor.py imports TimerStatusSensor from here.
    # Safe under `from __future__ import annotations` - annotations stay strings.
    from .sensor import TimerRuntimeSensor


def derive_timer_status(timer_state: str, reverse_mode: bool, has_schedule: bool) -> str:
    """Map the runtime sensor's internal flags to a single user-facing status.

    A schedule can stay armed while a timer is running (a repeating schedule
    arms its next fire immediately), so a running timer deliberately wins.

    Kept as a module-level pure function so it can be unit tested without
    standing up an entity.
    """
    if timer_state == "active":
        return STATUS_DELAYED_START if reverse_mode else STATUS_ACTIVE
    if has_schedule:
        return STATUS_SCHEDULED
    return STATUS_IDLE


class TimerStatusSensor(SensorEntity):
    """Non-numeric companion sensor exposing the timer's status as its state.

    Exists so the timer shows up in HA's logbook and device Activity feed. The
    runtime sensor cannot: it carries a unit_of_measurement, and logbook skips
    continuous sensors to avoid drowning in numbers.

    Deliberately exposes NO extra state attributes. The card locates a timer
    instance by scanning every sensor.* for one carrying both `entry_id` and
    `switch_entity_id` and taking the first match (_determineEffectiveEntities
    in timer-card.ts). Adding those attributes here would let this entity win
    that race and break existing cards, including bundles already shipped to
    users who will not rebuild. Do not add them.
    """

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the status sensor."""
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._entry_id_short = self._entry_id[:8]
        self._switch_entity_id = entry.data.get("switch_entity_id")

        self._attr_unique_id = f"timer_status_{self._entry_id}"
        self._attr_native_value = STATUS_IDLE

        self._unsub_dispatcher = None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Group with the switch's device, same as the runtime sensor."""
        return device_info_for_switch(self.hass, self._switch_entity_id,
                                      name=self.instance_title)

    @property
    def instance_title(self) -> str:
        """Current instance title, mirroring the runtime sensor."""
        return instance_title(self._entry)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.instance_title} Status ({self._entry_id_short})"

    @property
    def icon(self) -> str:
        """Icon reflecting the current status."""
        if self._attr_native_value == STATUS_ACTIVE:
            return "mdi:timer-play"
        if self._attr_native_value == STATUS_DELAYED_START:
            return "mdi:timer-sand"
        if self._attr_native_value == STATUS_SCHEDULED:
            return "mdi:timer-cog"
        return "mdi:timer-outline"

    def _read_runtime_sensor(self) -> TimerRuntimeSensor | None:
        """Return this entry's runtime sensor, if it is loaded."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if not isinstance(entry_data, dict):
            return None
        return entry_data.get("sensor")

    @callback
    def _handle_state_updated(self) -> None:
        """Recompute status; write only when it actually changed.

        The signal fires on every runtime sensor write, which is once a second
        while a timer runs. Filtering here keeps the recorder to a handful of
        rows per timer instead of one per second.
        """
        runtime = self._read_runtime_sensor()
        if runtime is None:
            return

        new_status = derive_timer_status(
            runtime.timer_state,
            runtime.timer_reverse_mode,
            runtime.has_armed_schedule,
        )

        if new_status != self._attr_native_value:
            self._attr_native_value = new_status
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime sensor updates and seed the initial status."""
        await super().async_added_to_hass()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            SIGNAL_STATE_UPDATED.format(self._entry_id),
            self._handle_state_updated,
        )

        # Seed from the runtime sensor if it is already loaded, so a restart
        # mid-timer does not report idle until the next write.
        self._handle_state_updated()

    async def async_will_remove_from_hass(self) -> None:
        """Drop the dispatcher subscription."""
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None
        await super().async_will_remove_from_hass()
