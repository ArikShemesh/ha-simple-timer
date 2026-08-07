"""Helpers shared by both Simple Timer sensor entities.

Lives in its own module so `sensor.py` and `status_sensor.py` can both import it
without either depending on the other.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo


def device_info_for_switch(hass: HomeAssistant, switch_entity_id: str | None) -> DeviceInfo | None:
    """Return DeviceInfo that groups an entity onto the switch's device.

    Reuses the switch device's identifiers so HA merges our entities into that
    device rather than creating a second one. Shared by both sensors.
    """
    if not switch_entity_id:
        return None

    # Access the Entity Registry to find the registry entry for the switch
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(switch_entity_id)

    # If the switch doesn't exist or isn't linked to a device, we can't link
    if not entity_entry or not entity_entry.device_id:
        return None

    # Access the Device Registry to get the device details
    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get(entity_entry.device_id)

    if not device_entry:
        return None

    return DeviceInfo(
        connections=device_entry.connections,
        identifiers=device_entry.identifiers,
    )
