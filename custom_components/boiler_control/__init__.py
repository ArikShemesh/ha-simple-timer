"""The Boiler Control integration."""
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, PLATFORMS

async def async_setup(hass: HomeAssistant, _: dict) -> bool:
    """Set up the integration by registering services."""
    if hass.data.setdefault(DOMAIN, {}).get("services_registered"):
        return True

    # Schema for the timer services
    SERVICE_START_TIMER_SCHEMA = vol.Schema({
        vol.Required("entry_id"): cv.string,
        vol.Required("duration"): cv.positive_int,
    })
    SERVICE_CANCEL_TIMER_SCHEMA = vol.Schema({
        vol.Required("entry_id"): cv.string,
    })
    # **NEW**: Schema for the service that tells the sensor which switch to monitor
    SERVICE_UPDATE_SWITCH_SCHEMA = vol.Schema({
        vol.Required("entry_id"): cv.string,
        vol.Required("switch_entity_id"): cv.string,
    })

    async def start_timer(call: ServiceCall):
        entry_id = call.data["entry_id"]
        sensor = hass.data[DOMAIN].get(entry_id, {}).get("sensor")
        if sensor:
            await sensor.async_start_timer(call.data["duration"])

    async def cancel_timer(call: ServiceCall):
        entry_id = call.data["entry_id"]
        sensor = hass.data[DOMAIN].get(entry_id, {}).get("sensor")
        if sensor:
            await sensor.async_cancel_timer()

    async def update_switch_entity(call: ServiceCall):
        """Handle the service call to update the switch entity for the sensor."""
        entry_id = call.data["entry_id"]
        switch_entity_id = call.data["switch_entity_id"]
        sensor = hass.data[DOMAIN].get(entry_id, {}).get("sensor")
        if sensor:
            await sensor.async_update_switch_entity(switch_entity_id)

    # Register all three services
    hass.services.async_register(
        DOMAIN, "start_timer", start_timer, schema=SERVICE_START_TIMER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "cancel_timer", cancel_timer, schema=SERVICE_CANCEL_TIMER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "update_switch_entity", update_switch_entity, schema=SERVICE_UPDATE_SWITCH_SCHEMA
    )

    hass.data[DOMAIN]["services_registered"] = True
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a single Boiler Control config entry."""
    hass.data[DOMAIN][entry.entry_id] = {}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Boiler Control config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
