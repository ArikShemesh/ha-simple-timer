"""The Simple Timer integration."""
import voluptuous as vol
import logging
import os
import json

import asyncio
import homeassistant.helpers.config_validation as cv

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import async_register_built_in_panel, add_extra_js_url
from homeassistant.components.lovelace.resources import ResourceStorageCollection

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

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

    # Serve directly from custom_components
    integration_path = os.path.dirname(__file__)
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            "/local/simple-timer/timer-card.js",
            os.path.join(integration_path, "dist", "timer-card.js"),
            True
        )
    ])

    # Initialize the frontend resource
    version = getattr(hass.data["integrations"][DOMAIN], "version", "1.0.0")
    
    # Calculate cache_id using version and file mtime
    try:
        integration_path = os.path.dirname(__file__)
        js_path = os.path.join(integration_path, "dist", "timer-card.js")
        file_mtime = os.path.getmtime(js_path)
        cache_id = f"{version}.{int(file_mtime)}"
    except Exception:
        cache_id = str(version)

    await init_resource(hass, "/local/simple-timer/timer-card.js", cache_id)

    UNIT_OPTIONS = ["s", "sec", "seconds", "m", "min", "minutes", "h", "hr", "hours", "d", "day", "days"]

    # Services accept either entry_id or entity_id (exactly one). entity_id
    # resolves via the entity registry to the owning config entry.
    SERVICE_START_TIMER_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
            vol.Required("duration"): cv.positive_float,
            vol.Optional("unit", default="min"): vol.In(UNIT_OPTIONS),
            vol.Optional("reverse_mode", default=False): cv.boolean,
            vol.Optional("start_method", default="button"): vol.In(["button", "slider"]),
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    DAY_OPTIONS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    DAY_TO_WEEKDAY = {d: i for i, d in enumerate(DAY_OPTIONS)}

    SERVICE_SCHEDULE_TIMER_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
            vol.Required("start_time"): cv.time,
            vol.Required("duration"): cv.positive_float,
            vol.Optional("unit", default="min"): vol.In(UNIT_OPTIONS),
            vol.Optional("repeat", default=False): cv.boolean,
            vol.Optional("days", default=list): [vol.In(DAY_OPTIONS)],
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    SERVICE_CANCEL_SCHEDULE_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    SERVICE_ADD_TIMER_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
            vol.Required("duration"): cv.positive_float,
            vol.Optional("unit", default="min"): vol.In(UNIT_OPTIONS),
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    SERVICE_CANCEL_TIMER_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
            vol.Optional("turn_off_entity", default=True): cv.boolean,
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    SERVICE_UPDATE_SWITCH_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
            vol.Required("switch_entity_id"): cv.string,
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    # force_name_sync: both identifiers optional; if neither given, syncs all.
    SERVICE_FORCE_NAME_SYNC_SCHEMA = vol.Schema({
        vol.Exclusive("entry_id", "target"): cv.string,
        vol.Exclusive("entity_id", "target"): cv.entity_id,
    })
    SERVICE_MANUAL_POWER_TOGGLE_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
            vol.Required("action"): vol.In(["turn_on", "turn_off"]),
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    SERVICE_TEST_NOTIFICATION_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
            vol.Optional("message", default="Test notification"): cv.string,
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    SERVICE_RESET_DAILY_USAGE_SCHEMA = vol.Schema(vol.All(
        {
            vol.Exclusive("entry_id", "target"): cv.string,
            vol.Exclusive("entity_id", "target"): cv.entity_id,
        },
        cv.has_at_least_one_key("entry_id", "entity_id"),
    ))
    SERVICE_RELOAD_RESOURCES_SCHEMA = vol.Schema({})

    def _resolve_entry_id(call: ServiceCall) -> tuple[str, str]:
        """Return (config_entry_id, human_label) from entry_id or entity_id."""
        entry_id = call.data.get("entry_id")
        if entry_id:
            return entry_id, f"entry_id: {entry_id}"

        entity_id = call.data["entity_id"]
        registry = er.async_get(hass)
        reg_entry = registry.async_get(entity_id)
        if reg_entry is None or reg_entry.platform != DOMAIN:
            raise ServiceValidationError(
                f"'{entity_id}' is not a Simple Timer entity"
            )
        if reg_entry.config_entry_id is None:
            raise ServiceValidationError(
                f"'{entity_id}' has no associated config entry"
            )
        return reg_entry.config_entry_id, f"entity_id: {entity_id}"

    def _get_sensor(entry_id: str, label: str):
        """Return the loaded sensor for entry_id or raise a clear error."""
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
        sensor = entry_data.get("sensor") if isinstance(entry_data, dict) else None
        if sensor is None:
            raise ServiceValidationError(
                f"No Simple Timer sensor loaded for {label}"
            )
        return sensor

    async def test_notification(call: ServiceCall):
        """Test notification functionality."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        await sensor._send_notification(call.data.get("message", "Test notification"))

    async def start_timer(call: ServiceCall):
        """Handle the service call to start the device timer."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        await sensor.async_start_timer(
            call.data["duration"],
            call.data.get("unit", "min"),
            call.data.get("reverse_mode", False),
            call.data.get("start_method", "button"),
        )

    async def add_timer(call: ServiceCall):
        """Handle the service call to add time to an active timer."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        await sensor.async_add_timer(call.data["duration"], call.data.get("unit", "min"))

    async def schedule_timer(call: ServiceCall):
        """Handle the service call to arm a scheduled start."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        days = [DAY_TO_WEEKDAY[d] for d in call.data.get("days", [])]
        await sensor.async_schedule_timer(
            call.data["start_time"],
            call.data["duration"],
            call.data.get("unit", "min"),
            call.data.get("repeat", False),
            days,
        )

    async def cancel_schedule(call: ServiceCall):
        """Handle the service call to cancel an armed schedule."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        await sensor.async_cancel_schedule()

    async def cancel_timer(call: ServiceCall):
        """Handle the service call to cancel the device timer."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        await sensor.async_cancel_timer(call.data.get("turn_off_entity", True))

    async def update_switch_entity(call: ServiceCall):
        """Handle the service call to update the switch entity for the sensor."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        await sensor.async_update_switch_entity(call.data["switch_entity_id"])

    async def force_name_sync(call: ServiceCall):
        """Handle the service call to force immediate name synchronization."""
        # If either identifier is supplied, sync only that entry; otherwise sync all.
        if call.data.get("entry_id") or call.data.get("entity_id"):
            sensor = _get_sensor(*_resolve_entry_id(call))
            await sensor.async_force_name_sync()
            return

        for entry_data in hass.data[DOMAIN].values():
            sensor = entry_data.get("sensor") if isinstance(entry_data, dict) else None
            if sensor is None:
                continue
            try:
                await sensor.async_force_name_sync()
            except Exception:
                # Continue syncing remaining sensors on individual failure.
                pass

    async def manual_power_toggle(call: ServiceCall):
        """Handle manual power toggle from frontend card."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        await sensor.async_manual_power_toggle(call.data["action"])

    async def reset_daily_usage(call: ServiceCall):
        """Handle manual daily usage reset."""
        sensor = _get_sensor(*_resolve_entry_id(call))
        await sensor.async_reset_daily_usage()
            
    async def reload_resources(call: ServiceCall):
        """Reload frontend resources with current manifest version."""
        try:
            _LOGGER.info("Simple Timer: Reloading resources")
            

            
            # Read version from manifest using async executor to avoid blocking
            def read_manifest():
                manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    return manifest.get('version', '1.0.0')
            
            version = await hass.async_add_executor_job(read_manifest)
            
            # Calculate cache_id using version and file mtime
            def get_cache_id(ver):
                try:
                    integration_path = os.path.dirname(__file__)
                    js_path = os.path.join(integration_path, "dist", "timer-card.js")
                    file_mtime = os.path.getmtime(js_path)
                    return f"{ver}.{int(file_mtime)}"
                except Exception:
                    return str(ver)
            
            cache_id = await hass.async_add_executor_job(get_cache_id, version)

            # Re-register resource with new version
            await init_resource(hass, "/local/simple-timer/timer-card.js", cache_id)
            
            _LOGGER.info(f"Simple Timer: Resources updated to version {cache_id}")
            
            # Send notification
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Simple Timer resources reloaded with version {cache_id}. Please refresh your browser (Ctrl+Shift+R).",
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
        DOMAIN, "add_timer", add_timer, schema=SERVICE_ADD_TIMER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "schedule_timer", schedule_timer, schema=SERVICE_SCHEDULE_TIMER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "cancel_schedule", cancel_schedule, schema=SERVICE_CANCEL_SCHEDULE_SCHEMA
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

async def _async_cleanup_resources(hass: HomeAssistant) -> None:
    """Remove resources and legacy files."""
    # Remove Lovelace resource
    if "lovelace" in hass.data:
        resources = hass.data["lovelace"].resources
        # Ensure resources are loaded
        if not resources.loaded:
            await resources.async_get_info()

        for item in resources.async_items():
            if item.get("url", "").startswith("/local/simple-timer/timer-card.js"):
                _LOGGER.info("Simple Timer: Removing dashboard resource")
                if isinstance(resources, ResourceStorageCollection):
                    await resources.async_delete_item(item["id"])
                break
    
    # Remove legacy www file if it exists
    def cleanup_legacy_files():
        try:
            www_file = hass.config.path("www", "simple-timer", "timer-card.js")
            if os.path.exists(www_file):
                _LOGGER.info("Simple Timer: Removing legacy www file")
                os.remove(www_file)
                
                # Try to remove directory if empty
                www_dir = hass.config.path("www", "simple-timer")
                if os.path.exists(www_dir) and not os.listdir(www_dir):
                    os.rmdir(www_dir)
        except Exception as e:
            _LOGGER.warning(f"Simple Timer: Error cleaning up legacy files: {e}")

    await hass.async_add_executor_job(cleanup_legacy_files)

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a Simple Timer config entry."""
    # Check if there are other entries for this domain
    other_entries = [
        e for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ]

    # If this is the last entry, remove the resources
    if not other_entries:
        await _async_cleanup_resources(hass)