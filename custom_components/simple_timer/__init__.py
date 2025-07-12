"""The Simple Timer integration."""
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, PLATFORMS

# Configuration schema for YAML setup (required by hassfest)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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
    # Schema for the service that tells the sensor which switch to monitor
    SERVICE_UPDATE_SWITCH_SCHEMA = vol.Schema({
        vol.Required("entry_id"): cv.string,
        vol.Required("switch_entity_id"): cv.string,
    })
    # Schema for manual name sync service
    SERVICE_FORCE_NAME_SYNC_SCHEMA = vol.Schema({
        vol.Optional("entry_id"): cv.string,
    })

    async def start_timer(call: ServiceCall):
        """Handle the service call to start the device timer."""
        entry_id = call.data["entry_id"]
        duration = call.data["duration"]
        
        # Find the sensor by entry_id
        sensor = None
        for stored_entry_id, entry_data in hass.data[DOMAIN].items():
            if stored_entry_id == entry_id and "sensor" in entry_data:
                sensor = entry_data["sensor"]
                break
        
        if sensor:
            await sensor.async_start_timer(duration)
        else:
            raise ValueError(f"No simple timer sensor found for entry_id: {entry_id}")

    async def cancel_timer(call: ServiceCall):
        """Handle the service call to cancel the device timer."""
        entry_id = call.data["entry_id"]
        
        # Find the sensor by entry_id
        sensor = None
        for stored_entry_id, entry_data in hass.data[DOMAIN].items():
            if stored_entry_id == entry_id and "sensor" in entry_data:
                sensor = entry_data["sensor"]
                break
        
        if sensor:
            await sensor.async_cancel_timer()
        else:
            raise ValueError(f"No simple timer sensor found for entry_id: {entry_id}")

    async def update_switch_entity(call: ServiceCall):
        """Handle the service call to update the switch entity for the sensor."""
        entry_id = call.data["entry_id"]
        switch_entity_id = call.data["switch_entity_id"]
        
        # Find the sensor by entry_id
        sensor = None
        for stored_entry_id, entry_data in hass.data[DOMAIN].items():
            if stored_entry_id == entry_id and "sensor" in entry_data:
                sensor = entry_data["sensor"]
                break
        
        if sensor:
            await sensor.async_update_switch_entity(switch_entity_id)
        else:
            raise ValueError(f"No simple timer sensor found for entry_id: {entry_id}")

    async def force_name_sync(call: ServiceCall):
        """Handle the service call to force immediate name synchronization."""
        entry_id = call.data.get("entry_id")
        
        if entry_id:
            # Sync specific entry
            if entry_id in hass.data[DOMAIN] and "sensor" in hass.data[DOMAIN][entry_id]:
                sensor = hass.data[DOMAIN][entry_id]["sensor"]
                if sensor:
                    result = await sensor.async_force_name_sync()
                    if result:
                        return
            raise ValueError(f"No simple timer sensor found for entry_id: {entry_id}")
        else:
            # Sync all entries
            synced_count = 0
            for stored_entry_id, entry_data in hass.data[DOMAIN].items():
                if "sensor" in entry_data and entry_data["sensor"]:
                    try:
                        await entry_data["sensor"].async_force_name_sync()
                        synced_count += 1
                    except Exception as e:
                        # Log error but continue with other sensors
                        pass
            
            if synced_count > 0:
                # Could add notification here if desired
                pass

    # Register all services
    hass.services.async_register(
        DOMAIN, "start_timer", start_timer, schema=SERVICE_START_TIMER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "cancel_timer", cancel_timer, schema=SERVICE_CANCEL_TIMER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "update_switch_entity", update_switch_entity, schema=SERVICE_UPDATE_SWITCH_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "force_name_sync", force_name_sync, schema=SERVICE_FORCE_NAME_SYNC_SCHEMA
    )

    hass.data[DOMAIN]["services_registered"] = True
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a single Simple Timer config entry."""
    hass.data[DOMAIN][entry.entry_id] = {"sensor": None} # Initialize with None
    
    # Add update listener to block title-only changes (3-dots rename)
    entry.add_update_listener(_async_update_listener)
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry updates and block unwanted renames."""
    # This listener intentionally does minimal work
    # The real update handling is done in the sensor's _handle_config_entry_update method
    # This listener is mainly here to ensure the sensor gets notified of changes
    pass

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Simple Timer config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok