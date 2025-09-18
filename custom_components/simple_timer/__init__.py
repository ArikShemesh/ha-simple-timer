"""The Simple Timer integration."""
import voluptuous as vol
import logging
import os
import json
import shutil
import asyncio
import homeassistant.helpers.config_validation as cv

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import async_register_built_in_panel, add_extra_js_url
from homeassistant.components.lovelace.resources import ResourceStorageCollection

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

def _copy_file_sync(source_file: str, dest_file: str, www_dir: str) -> bool:
    """Synchronous file copy function to be run in executor."""
    try:
        # Create www/simple-timer directory if it doesn't exist
        os.makedirs(www_dir, exist_ok=True)
        
        # Copy the file if source exists
        if os.path.exists(source_file):
            shutil.copy2(source_file, dest_file)
            return True
        else:
            return False
    except Exception:
        return False

async def copy_frontend_files(hass: HomeAssistant) -> bool:
    """Copy frontend files from integration dist folder to www folder."""
    try:
        # Source: custom_components/simple_timer/dist/timer-card.js
        integration_path = os.path.dirname(__file__)
        source_file = os.path.join(integration_path, "dist", "timer-card.js")
        
        # Destination: config/www/simple-timer/timer-card.js
        www_dir = hass.config.path("www", "simple-timer")
        dest_file = os.path.join(www_dir, "timer-card.js")
        
        # Run the file copy in executor to avoid blocking I/O
        success = await hass.async_add_executor_job(
            _copy_file_sync, source_file, dest_file, www_dir
        )
        
        if success:
            _LOGGER.debug(f"Copied {source_file} to {dest_file}")
            return True
        else:
            _LOGGER.warning(f"Source file not found: {source_file}")
            return False
            
    except Exception as e:
        _LOGGER.error(f"Failed to copy frontend files: {e}")
        return False

async def init_resource(hass: HomeAssistant, url: str, ver: str) -> bool:
    """Add extra JS module for lovelace mode YAML and new lovelace resource
    for mode GUI. It's better to add extra JS for all modes, because it has
    random url to avoid problems with the cache. But chromecast don't support
    extra JS urls and can't load custom card.
    """
    resources: ResourceStorageCollection = hass.data["lovelace"].resources
    # force load storage
    await resources.async_get_info()

    url2 = f"{url}?v={ver}"

    for item in resources.async_items():
        if not item.get("url", "").startswith(url):
            continue

        # no need to update
        if item["url"].endswith(ver):
            return False

        _LOGGER.debug(f"Update lovelace resource to: {url2}")

        if isinstance(resources, ResourceStorageCollection):
            await resources.async_update_item(
                item["id"], {"res_type": "module", "url": url2}
            )
        else:
            # not the best solution, but what else can we do
            item["url"] = url2

        return True

    if isinstance(resources, ResourceStorageCollection):
        _LOGGER.debug(f"Add new lovelace resource: {url2}")
        await resources.async_create_item({"res_type": "module", "url": url2})
    else:
        _LOGGER.debug(f"Add extra JS module: {url2}")
        add_extra_js_url(hass, url2)

    return True

# Configuration schema for YAML setup (required by hassfest)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, _: dict) -> bool:
    """Set up the integration by registering services and frontend resources."""
    if hass.data.setdefault(DOMAIN, {}).get("services_registered"):
        return True

    # Copy frontend files from integration to www folder
    await copy_frontend_files(hass)

    # Option 1: Register static path pointing to www folder (after copy)
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            "/local/simple-timer/timer-card.js",
            hass.config.path("www/simple-timer/timer-card.js"),
            True
        )
    ])
    
    # Option 2: Alternative - serve directly from custom_components (uncomment to use)
    # integration_path = os.path.dirname(__file__)
    # await hass.http.async_register_static_paths([
    #     StaticPathConfig(
    #         "/local/simple-timer/timer-card.js",
    #         os.path.join(integration_path, "dist", "timer-card.js"),
    #         True
    #     )
    # ])

    # Initialize the frontend resource
    version = getattr(hass.data["integrations"][DOMAIN], "version", "1.0.0")
    await init_resource(hass, "/local/simple-timer/timer-card.js", str(version))

    # Schema for the timer services
    SERVICE_START_TIMER_SCHEMA = vol.Schema({
        vol.Required("entry_id"): cv.string,
        vol.Required("duration"): cv.positive_int,
        vol.Optional("reverse_mode", default=False): cv.boolean,
        vol.Optional("start_method", default="button"): vol.In(["button", "slider"]),
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
    # Schema for manual power toggle service  
    SERVICE_MANUAL_POWER_TOGGLE_SCHEMA = vol.Schema({
        vol.Required("entry_id"): cv.string,
        vol.Required("action"): vol.In(["turn_on", "turn_off"]),
    })
    # Schema for test notification service  
    SERVICE_TEST_NOTIFICATION_SCHEMA = vol.Schema({
        vol.Required("entry_id"): cv.string,
        vol.Optional("message", default="Test notification"): cv.string,
    })
    SERVICE_RESET_DAILY_USAGE_SCHEMA = vol.Schema({
        vol.Required("entry_id"): cv.string,
    })
    SERVICE_RELOAD_RESOURCES_SCHEMA = vol.Schema({})

    async def test_notification(call: ServiceCall):
        """Test notification functionality."""
        entry_id = call.data["entry_id"]
        message = call.data.get("message", "Test notification")
        
        # Find the sensor by entry_id (hass is available from the outer scope here)
        sensor = None
        for stored_entry_id, entry_data in hass.data[DOMAIN].items():
            if stored_entry_id == entry_id and "sensor" in entry_data:
                sensor = entry_data["sensor"]
                break
        
        if sensor:
            await sensor._send_notification(message)
        else:
            raise ValueError(f"No simple timer sensor found for entry_id: {entry_id}")

    async def start_timer(call: ServiceCall):
        """Handle the service call to start the device timer."""
        entry_id = call.data["entry_id"]
        duration = call.data["duration"]
        reverse_mode = call.data.get("reverse_mode", False)
        start_method = call.data.get("start_method", "button")
        
        # Find the sensor by entry_id
        sensor = None
        for stored_entry_id, entry_data in hass.data[DOMAIN].items():
            if stored_entry_id == entry_id and "sensor" in entry_data:
                sensor = entry_data["sensor"]
                break
        
        if sensor:
            await sensor.async_start_timer(duration, reverse_mode, start_method)
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

    async def manual_power_toggle(call: ServiceCall):
        """Handle manual power toggle from frontend card."""
        entry_id = call.data["entry_id"]
        action = call.data["action"]
        
        # Find the sensor by entry_id
        sensor = None
        for stored_entry_id, entry_data in hass.data[DOMAIN].items():
            if stored_entry_id == entry_id and "sensor" in entry_data:
                sensor = entry_data["sensor"]
                break
        
        if sensor:
            await sensor.async_manual_power_toggle(action)
        else:
            raise ValueError(f"No simple timer sensor found for entry_id: {entry_id}")
            
    async def reset_daily_usage(call: ServiceCall):
        """Handle manual daily usage reset."""
        entry_id = call.data["entry_id"]
        
        # Find the sensor by entry_id
        sensor = None
        for stored_entry_id, entry_data in hass.data[DOMAIN].items():
            if stored_entry_id == entry_id and "sensor" in entry_data:
                sensor = entry_data["sensor"]
                break
        
        if sensor:
            await sensor.async_reset_daily_usage()
        else:
            raise ValueError(f"No simple timer sensor found for entry_id: {entry_id}")
            
    async def reload_resources(call: ServiceCall):
        """Reload frontend resources with current manifest version."""
        try:
            _LOGGER.info("Simple Timer: Reloading resources")
            
            # Copy updated files
            await copy_frontend_files(hass)
            
            # Read version from manifest using async executor to avoid blocking
            def read_manifest():
                manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    return manifest.get('version', '1.0.0')
            
            version = await hass.async_add_executor_job(read_manifest)
            
            # Re-register resource with new version
            await init_resource(hass, "/local/simple-timer/timer-card.js", version)
            
            _LOGGER.info(f"Simple Timer: Resources updated to version {version}")
            
            # Send notification
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Simple Timer resources reloaded with version {version}. Please refresh your browser (Ctrl+Shift+R).",
                    "title": "Simple Timer Resources Updated",
                    "notification_id": "simple_timer_resource_reload"
                }
            )
            
        except Exception as e:
            _LOGGER.error(f"Simple Timer: Resource reload failed: {e}")
            raise

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
    hass.services.async_register(
        DOMAIN, "manual_power_toggle", manual_power_toggle, schema=SERVICE_MANUAL_POWER_TOGGLE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "test_notification", test_notification, schema=SERVICE_TEST_NOTIFICATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "reset_daily_usage", reset_daily_usage, schema=SERVICE_RESET_DAILY_USAGE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "reload_resources", reload_resources, schema=vol.Schema({})
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