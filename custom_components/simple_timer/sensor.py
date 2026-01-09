"""Simple Timer – runtime counter + countdown timer sensor."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTime,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback, Event, State, CoreState
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_call_later,
    async_track_point_in_utc_time,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Default reset time configuration (hour, minute, second)
DEFAULT_RESET_TIME = time(0, 0, 0)

# Sensor state attributes
ATTR_TIMER_STATE = "timer_state"
ATTR_TIMER_FINISHES_AT = "timer_finishes_at"
ATTR_TIMER_DURATION = "timer_duration"
ATTR_TIMER_REMAINING = "timer_remaining"
ATTR_WATCHDOG_MESSAGE = "watchdog_message"
ATTR_SWITCH_ENTITY_ID = "switch_entity_id"
ATTR_LAST_ON_TIMESTAMP = "last_on_timestamp"
ATTR_INSTANCE_TITLE = "instance_title"
ATTR_NEXT_RESET_DATE = "next_reset_date"
ATTR_RESET_TIME = "reset_time"
ATTR_TIMER_START_METHOD = "timer_start_method"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Create a TimerRuntimeSensor for this config entry."""
    async_add_entities([TimerRuntimeSensor(hass, entry)])

class TimerRuntimeSensor(SensorEntity, RestoreEntity):
    """The sensor entity for Simple Timer."""
    _attr_has_entity_name = False
    _attr_icon = "mdi:timer"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    STORAGE_VERSION = 2
    STORAGE_KEY_FORMAT = f"{DOMAIN}_{{}}"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._switch_entity_id = entry.data.get("switch_entity_id")
        self._entry_id_short = self._entry_id[:8]

        self._attr_unique_id = f"timer_runtime_{self._entry_id}"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_icon = "mdi:timer"

        self._last_known_title = entry.title
        self._last_known_data_name = entry.data.get("name")

        # Initialize reset time from config
        self._reset_time = self._parse_reset_time(entry.data.get("reset_time", "00:00"))
        self._reset_time_tracker = None  # Track the current reset time listener

        # Initialize state and timer variables
        self._state = 0.0
        self._last_on_timestamp = None
        self._accumulation_task = None
        self._state_listener_disposer = None
        self._stop_event_received = False
        self._is_finishing_normally = False

        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0
        self._timer_start_moment = None  # Track exact timer start moment
        self._runtime_at_timer_start = 0  # Track runtime when timer started
        self._timer_unsub = None
        self._watchdog_message = None
        self._timer_update_task = None
        self._is_performing_reset = False
        self._timer_start_method = None
        self._last_accumulated_seconds = 0

        # Reset scheduling
        self._next_reset_date = None
        self._last_reset_was_catchup = False
        self._catchup_reset_info = None

        # Default timer config
        self._default_timer_enabled = False
        self._default_timer_duration = 0.0
        self._default_timer_unit = "min"
        self._default_timer_reverse_mode = False

        # Storage setup
        self._storage_lock = asyncio.Lock()
        self._store = Store(hass, self.STORAGE_VERSION, self.STORAGE_KEY_FORMAT.format(self._entry_id))

    @property
    def device_info(self) -> DeviceInfo | None:
        """Link this entity to the device of the switch it monitors."""
        if not self._switch_entity_id:
            return None

        # Access the Entity Registry to find the registry entry for the switch
        ent_reg = er.async_get(self.hass)
        entity_entry = ent_reg.async_get(self._switch_entity_id)
        
        # If the switch doesn't exist or isn't linked to a device, we can't link
        if not entity_entry or not entity_entry.device_id:
            return None

        # Access the Device Registry to get the device details
        dev_reg = dr.async_get(self.hass)
        device_entry = dev_reg.async_get(entity_entry.device_id)

        if not device_entry:
            return None

        # Return DeviceInfo with the SAME identifiers as the switch's device.
        # This tells HA to group this sensor with that device.
        return DeviceInfo(
            connections=device_entry.connections,
            identifiers=device_entry.identifiers,
        )

    def _parse_reset_time(self, time_str: str) -> time:
        """Parse reset time string into time object."""
        try:
            # Support both HH:MM and HH:MM:SS formats
            if len(time_str) == 5:  # HH:MM
                time_str += ":00"
            return time.fromisoformat(time_str)
        except (ValueError, TypeError):
            _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Invalid reset time '{time_str}', using default 00:00:00")
            return DEFAULT_RESET_TIME

    @property
    def reset_time(self) -> time:
        """Get the current reset time."""
        return self._reset_time

    async def _update_reset_time(self):
        """Update reset time from config entry and reschedule reset."""
        new_reset_time_str = self._entry.data.get("reset_time", "00:00")
        new_reset_time = self._parse_reset_time(new_reset_time_str)
        
        if new_reset_time != self._reset_time:
            old_reset_time = self._reset_time
            self._reset_time = new_reset_time
            
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Reset time updated from {old_reset_time} to {self._reset_time}")
            
            # Cancel existing reset tracker
            if self._reset_time_tracker:
                self._reset_time_tracker()
                self._reset_time_tracker = None
            
            # Reschedule reset with new time
            await self._setup_reset_scheduling({})
            
            # Update next reset date
            self._next_reset_date = self._get_next_reset_datetime()
            await self._save_next_reset_date()
            
            self.async_write_ha_state()

    @property
    def instance_title(self) -> str:
        """Get the current instance title."""
        # Prefer the editable title from the config entry
        if self._entry.title:
            return self._entry.title
        # Fallback to data name
        return self._entry.data.get("name") or "Timer"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        current_title = self.instance_title
        return f"{current_title} Runtime ({self._entry_id_short})"

    @property
    def native_value(self) -> float:
        """Return the current daily runtime in seconds."""
        # Return whole seconds only
        return float(int(self._state))

    def _calculate_timer_remaining(self) -> int:
        """Calculate remaining time in seconds for active timer."""
        if self._timer_state == "active" and self._timer_finishes_at:
            now = dt_util.utcnow()
            remaining = (self._timer_finishes_at - now).total_seconds()
            return max(0, int(remaining))
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        timer_remaining = self._calculate_timer_remaining()
        
        # Get show_seconds from config entry
        show_seconds_setting = self._entry.data.get("show_seconds", False)

        attrs = {
            ATTR_TIMER_STATE: self._timer_state,
            ATTR_TIMER_FINISHES_AT: self._timer_finishes_at.isoformat() if self._timer_finishes_at else None,
            ATTR_TIMER_DURATION: self._timer_duration,
            ATTR_TIMER_REMAINING: timer_remaining,
            ATTR_WATCHDOG_MESSAGE: self._watchdog_message,
            "entry_id": self._entry_id,
            ATTR_SWITCH_ENTITY_ID: self._switch_entity_id,
            ATTR_LAST_ON_TIMESTAMP: self._last_on_timestamp.isoformat() if self._last_on_timestamp else None,
            ATTR_INSTANCE_TITLE: self.instance_title,
            ATTR_NEXT_RESET_DATE: self._next_reset_date.isoformat() if self._next_reset_date else None,
            ATTR_RESET_TIME: self._reset_time.strftime("%H:%M:%S"),  # Expose current reset time
            ATTR_TIMER_START_METHOD: self._timer_start_method,
            "show_seconds": show_seconds_setting,  # Expose show_seconds from config entry
            "reverse_mode": getattr(self, '_timer_reverse_mode', False),
            
            # Default timer attributes for frontend sync
            "default_timer_enabled": self._default_timer_enabled,
            "default_timer_duration": self._default_timer_duration,
            "default_timer_unit": self._default_timer_unit,
            "default_timer_reverse_mode": self._default_timer_reverse_mode,
        }

        if self._last_reset_was_catchup:
            attrs["last_reset_type"] = "catch-up"
            if self._catchup_reset_info:
                attrs["reset_info"] = self._catchup_reset_info
            self._last_reset_was_catchup = False

        return attrs

    async def _get_card_notification_config(self) -> tuple[list[str], bool]:
        """Get notification entities and show_seconds setting from config entry ONLY."""
        try:
            # ALWAYS use config entry data - never fall back to old card configs
            notification_entities = self._entry.data.get("notification_entities", [])
            show_seconds = self._entry.data.get("show_seconds", False)
            
            if notification_entities:
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Using notification entities from config: {notification_entities}")
                return notification_entities, show_seconds
            
            # No notifications configured in backend
            _LOGGER.debug(f"Simple Timer: [{self._entry_id}] No notification entities configured in backend")
            return [], show_seconds
                                
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error getting notification config: {e}")
            return [], False

    def _search_cards_in_config(self, config: dict) -> tuple[str | None, bool]:
        """Recursively search for timer cards in lovelace config (LEGACY - for migration warning only)."""
        if isinstance(config, dict):
            # Check if this is a timer card for our instance
            if (config.get('type') == 'custom:timer-card' and 
                config.get('timer_instance_id') == self._entry_id):
                notification_entity = config.get('notification_entity')
                show_seconds = config.get('show_seconds', False)
                if notification_entity and notification_entity != 'none_selected':
                    return notification_entity, show_seconds
            
            # Search nested structures
            for value in config.values():
                if isinstance(value, (dict, list)):
                    result = self._search_cards_in_config(value)
                    if result[0]:
                        return result
                        
        elif isinstance(config, list):
            for item in config:
                if isinstance(item, (dict, list)):
                    result = self._search_cards_in_config(item)
                    if result[0]:
                        return result
        
        return None, False

    async def _get_notification_from_storage(self) -> tuple[str | None, bool]:
        """Get notification config from storage files using async operations (LEGACY - for migration warning only)."""
        try:
            import json
            import asyncio
            
            storage_path = self.hass.config.path('.storage')
            
            try:
                # List files asynchronously
                loop = asyncio.get_event_loop()
                import os
                filenames = await loop.run_in_executor(None, os.listdir, storage_path)
            except (OSError, FileNotFoundError):
                return None, False
                
            # Search through lovelace storage files
            for filename in filenames:
                if filename.startswith('lovelace'):
                    try:
                        file_path = os.path.join(storage_path, filename)
                        content = await loop.run_in_executor(None, self._read_file_sync, file_path)
                        if content:
                            data = json.loads(content)
                            if 'data' in data and 'config' in data['data']:
                                notification_entity, show_seconds = self._search_cards_in_config(data['data']['config'])
                                if notification_entity:
                                    return notification_entity, show_seconds
                    except (json.JSONDecodeError, KeyError, IOError, UnicodeDecodeError):
                        continue
                        
        except Exception as e:
            _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Could not read storage files: {e}")
        
        return None, False

    def _read_file_sync(self, file_path: str) -> str | None:
        """Synchronous file reading helper for executor."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except (IOError, UnicodeDecodeError):
            return None

    def _format_time_for_notification(self, total_seconds: float, show_seconds: bool = False) -> tuple[str, str]:
        """Format time for notifications."""
        if show_seconds:
            total_seconds_int = int(total_seconds)
            hours = total_seconds_int // 3600
            minutes = (total_seconds_int % 3600) // 60
            seconds = total_seconds_int % 60
            formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            return formatted_time, "(hh:mm:ss)"
        else:
            total_minutes = int(total_seconds // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            formatted_time = f"{hours:02d}:{minutes:02d}"
            return formatted_time, "(hh:mm)"

    async def _ensure_switch_state(self, desired_state: str, action_description: str, blocking: bool = True, force: bool = False) -> None:
        """Ensure switch is in desired state, attempt to correct if not, and warn on failure."""
        if not self._switch_entity_id:
            return
            
        current_state = self.hass.states.get(self._switch_entity_id)

        if not current_state:
            return
            
        # If state is already correct and NOT forcing, do nothing
        if current_state.state == desired_state and not force:
            return
            
        # State mismatch - attempt to correct
        try:
            action = "turn_on" if desired_state == "on" else "turn_off"
            await self.hass.services.async_call(
                "homeassistant", action, {"entity_id": self._switch_entity_id}, blocking=blocking
            )
            
            # Wait a moment for state change to propagate
            # Retry a few times to account for slow state updates from integrations
            max_retries = 3
            wait_time = 1.0
            
            for attempt in range(max_retries):
                await asyncio.sleep(wait_time)
                
                updated_state = self.hass.states.get(self._switch_entity_id)
                if updated_state and updated_state.state == desired_state:
                    return
                
                # If checking failed, wait a bit longer next time
                wait_time += 1.0
            
            # Verify correction worked
            updated_state = self.hass.states.get(self._switch_entity_id)
            if updated_state and updated_state.state != desired_state:
                warning_msg = f"Warning: {action_description} - switch should be '{desired_state}' but remains '{updated_state.state}'. Check switch connectivity."
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] {warning_msg}")
                await self._send_notification(warning_msg)
                
        except Exception as e:
            warning_msg = f"Warning: {action_description} - failed to set switch to '{desired_state}': {e}"
            _LOGGER.warning(f"Simple Timer: [{self._entry_id}] {warning_msg}")
            await self._send_notification(warning_msg)

    async def _send_notification(self, message: str) -> None:
        """Send notification using configured notification entities."""
        try:
            notification_entities, show_seconds = await self._get_card_notification_config()
            
            if not notification_entities:
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] No notification entities configured - staying silent")
                return
            
            # Use instance title but sanitized to prevent Markdown errors in Telegram
            # (Replace underscores with spaces)
            raw_title = self.instance_title or "Timer"
            title = raw_title.replace("_", " ")
            
            # Send to all configured notification services
            for notification_entity in notification_entities:
                try:
                    # Parse the service call format
                    service_parts = notification_entity.split('.')
                    if len(service_parts) < 2:
                        _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Invalid notification entity format: {notification_entity}")
                        continue
                        
                    domain = service_parts[0]
                    service = service_parts[1]
                    
                    # Special handling for boolean/switch/button entities used as notifications
                    if domain in ["input_boolean", "switch", "light"]:
                        _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Turning on configured notification entity: {notification_entity}")
                        await self.hass.services.async_call(
                            domain, "turn_on", {"entity_id": notification_entity}
                        )
                    elif domain == "input_button":
                         _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Pressing configured notification button: {notification_entity}")
                         await self.hass.services.async_call(
                            domain, "press", {"entity_id": notification_entity}
                        )
                    else:
                        # Standard notification service (e.g., notify.mobile_app_x)
                        # We assume the second part is the service name
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Sending notification to {domain}.{service}: '{message}'")
                        
                        await self.hass.services.async_call(
                            domain, service, {"message": message, "title": title}
                        )
                    
                except Exception as e:
                    _LOGGER.error(f"Simple Timer: [{self._entry_id}] Failed to send notification to {notification_entity}: {e}")

        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Failed to send notifications: {e}")
            
    async def async_test_notification(self) -> None:
        """Test notification functionality."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Testing notification system...")
        await self._send_notification("Test notification from Simple Timer")

    async def _save_next_reset_date(self):
        """Save the next reset date to storage."""
        async with self._storage_lock:
            try:
                data = await self._store.async_load() or {}
                data["next_reset_date"] = self._next_reset_date.isoformat()
                await self._store.async_save(data)
            except Exception as e:
                _LOGGER.error(f"Simple Timer: [{self._entry_id}] Failed to save next reset date: {e}")

    def _get_next_reset_datetime(self, from_date=None):
        """Calculate the next reset datetime from a given date using configured reset time."""
        if from_date is None:
            from_date = dt_util.now().date()
        
        reset_datetime = datetime.combine(from_date, self._reset_time)
        reset_datetime = dt_util.as_local(reset_datetime)
        
        now = dt_util.now()
        if reset_datetime <= now:
            tomorrow = from_date + timedelta(days=1)
            reset_datetime = datetime.combine(tomorrow, self._reset_time)
            reset_datetime = dt_util.as_local(reset_datetime)
        
        return reset_datetime

    async def _check_missed_reset(self):
        """Check if we missed a reset while HA was offline."""
        if not self._next_reset_date:
            return
        
        now = dt_util.now()
        
        if now >= self._next_reset_date:
            time_diff = now - self._next_reset_date
            days_missed = time_diff.days + (1 if time_diff.seconds > 0 else 0)
            
            _LOGGER.warning(
                f"Simple Timer: [{self._entry_id}] Detected missed reset! "
                f"Expected reset: {self._next_reset_date}, Current time: {now}, "
                f"Missed resets: {days_missed}"
            )
            
            await self._perform_reset(is_catchup=True)
            
            self._next_reset_date = self._get_next_reset_datetime()
            await self._save_next_reset_date()
            
            self._last_reset_was_catchup = True
            self._catchup_reset_info = f"Reset performed on startup (missed {days_missed} reset(s))"

    async def _perform_reset(self, is_catchup=False):
        """Perform daily runtime reset."""
        self._is_performing_reset = True
        try:
            reset_type = "catch-up" if is_catchup else "scheduled"
            reset_time_str = self._reset_time.strftime("%H:%M:%S")
            _LOGGER.info(
                f"Simple Timer: [{self._entry_id}] Performing {reset_type} daily runtime reset at {reset_time_str}. "
                f"Current state: {self._state}s"
            )

            await self._stop_realtime_accumulation()

            if self._timer_state == "active":
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Reset occurred during an active timer. Adjusting timer's base runtime.")
                self._runtime_at_timer_start = 0.0 - self._calculate_timer_elapsed_since_start()
                
                # PERSISTENCE FIX: Save the adjusted runtime_at_start to storage immediately.
                # Otherwise, if HA restarts, it will load the old (positive) runtime_at_start
                # and ignore this daily reset, leading to incorrect usage calculation.
                async with self._storage_lock:
                    try:
                        data = await self._store.async_load() or {}
                        data["runtime_at_start"] = self._runtime_at_timer_start
                        await self._store.async_save(data)
                        _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Persisted adjusted runtime_at_start: {self._runtime_at_timer_start}s")
                    except Exception as e:
                        _LOGGER.error(f"Simple Timer: [{self._entry_id}] Failed to persist adjusted runtime_at_start: {e}")

            self._state = 0.0
            self._last_on_timestamp = None
            
            if self._switch_entity_id:
                current_switch_state = self.hass.states.get(self._switch_entity_id)
                if current_switch_state and current_switch_state.state == STATE_ON:
                    self._last_on_timestamp = dt_util.utcnow()
                    await self._start_realtime_accumulation()
            
            self.async_write_ha_state()
        finally:
            self._is_performing_reset = False

    async def _handle_name_change(self):
        """Handle detected name changes."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Processing name change")
        self.async_write_ha_state()

        from homeassistant.helpers import entity_registry as er
        entity_registry = er.async_get(self.hass)
        if entity_registry:
            entity_entry = entity_registry.async_get(self.entity_id)
            if entity_entry:
                try:
                    entity_registry.async_update_entity(self.entity_id, name=self.name)
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Updated entity registry with new name: '{self.name}'")
                except Exception as e:
                    _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not update entity registry: {e}")

    async def async_force_name_sync(self):
        """Force immediate name synchronization."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Manual name sync triggered")
        self._last_known_title = None
        self._last_known_data_name = None
        await self._handle_name_change()

    async def _start_timer_update_task(self):
        """Start timer update task."""
        if self._timer_update_task:
            return
            
        # Use standard HA timer helper instead of a custom loop
        self._timer_update_task = async_track_time_interval(
            self.hass, self._async_timer_update_tick, timedelta(seconds=1)
        )

    async def _stop_timer_update_task(self):
        """Stop timer update task."""
        if self._timer_update_task:
            self._timer_update_task()  # Remove callback
            self._timer_update_task = None

    @callback
    async def _async_timer_update_tick(self, now):
        """Timer update tick."""
        if self._timer_state != "active" or not self._timer_finishes_at or self._stop_event_received:
            await self._stop_timer_update_task()
            return

        if self._calculate_timer_remaining() <= 0:
            await self._stop_timer_update_task()
            return
        
        self.async_write_ha_state()

    async def _async_setup_switch_listener(self) -> None:
        """Set up switch state change listener."""
        if self._state_listener_disposer:
            self._state_listener_disposer()
        
        if self._switch_entity_id:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Setting up switch listener for: {self._switch_entity_id}")
            self._state_listener_disposer = async_track_state_change_event(
                self.hass, self._switch_entity_id, self._handle_switch_change_event
            )
        else:
            _LOGGER.warning(f"Simple Timer: [{self._entry_id}] No switch entity configured")

    async def async_update_switch_entity(self, switch_entity_id: str):
        """Update the monitored switch entity."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Updating switch entity to: {switch_entity_id}")
        
        if self._switch_entity_id != switch_entity_id:
            self._switch_entity_id = switch_entity_id
            await self._async_setup_switch_listener()
        
        # Update accumulation based on current switch state
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        if current_switch_state and current_switch_state.state == STATE_ON:
            if not self._last_on_timestamp:
                self._last_on_timestamp = dt_util.utcnow()
            await self._start_realtime_accumulation()
        else:
            await self._stop_realtime_accumulation()
        
        self.async_write_ha_state()

    @callback
    def _handle_switch_change_event(self, event: Event) -> None:
        """Handle switch state change events."""
        if self._stop_event_received:
            return
        self._handle_switch_change(event)

    @callback
    def _handle_switch_change(self, event: Event) -> None:
        """Process switch state changes for runtime calculation."""
        if self._stop_event_received:
            return

        from_state = event.data.get("old_state")
        to_state = event.data.get("new_state")
        now = dt_util.utcnow()

        if not to_state:
            return

        # Switch turned on
        if to_state.state == STATE_ON and (not from_state or from_state.state != STATE_ON):
            if self._watchdog_message:
                self._watchdog_message = None
            self._last_on_timestamp = now
            self.hass.async_create_task(self._start_realtime_accumulation())

            # Auto-start default timer if enabled and idle
            _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Switch ON detected. Default timer enabled: {self._default_timer_enabled}, State: {self._timer_state}")
            if self._default_timer_enabled and self._timer_state == "idle" and self._default_timer_duration > 0:
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Auto-starting default timer ({self._default_timer_duration} {self._default_timer_unit}, reverse={self._default_timer_reverse_mode})")
                self.hass.async_create_task(
                    self.async_start_timer(self._default_timer_duration, self._default_timer_unit, reverse_mode=self._default_timer_reverse_mode)
                )

        # Switch transitioned to a non-ON state
        elif to_state.state != STATE_ON:
            is_definitive_off = to_state.state == STATE_OFF

            if is_definitive_off:
                self.hass.async_create_task(self._stop_realtime_accumulation())
                self._last_on_timestamp = None

            # We exclude reverse_mode because the switch is supposed to be off during those.
            is_reverse_mode = getattr(self, '_timer_reverse_mode', False)

            if (
                self._timer_state == "active"
                and not is_reverse_mode
                and is_definitive_off
            ):
                # COUPLED: Auto-cancel timer when switch turns off
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Switch turned off - cancelling timer (coupled)")
                self.hass.async_create_task(self.async_cancel_timer())
        
        self.async_write_ha_state()

    async def _cleanup_timer_state(self):
        """Clean up timer state and storage."""
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        
        await self._stop_timer_update_task()
        
        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0
        self._timer_start_moment = None
        self._runtime_at_timer_start = 0
        self._timer_start_method = None
        
        # Clean storage
        async with self._storage_lock:
            try:
                data = await self._store.async_load() or {}
                data.pop("finishes_at", None)
                data.pop("duration", None)
                data.pop("timer_start", None)
                data.pop("runtime_at_start", None)
                await self._store.async_save(data)
            except Exception as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not clean timer storage: {e}")

    async def _auto_cancel_timer_on_external_off(self):
        """Auto-cancel timer when switch is turned off externally."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Auto-cancelling timer due to external switch off")
        
        if self._watchdog_message:
            self._watchdog_message = None
        
        await self._cleanup_timer_state()
        self.async_write_ha_state()
        
    def _is_switch_on(self) -> bool:
        """Check if the monitored switch is currently on."""
        if self._switch_entity_id:
            switch_state = self.hass.states.get(self._switch_entity_id)
            return switch_state is not None and switch_state.state == STATE_ON
        return False

    async def _start_realtime_accumulation(self) -> None:
        """Start real-time accumulation task."""
        if self._stop_event_received:
            return
        
        # If already running, don't start again
        if self._accumulation_task:
            return
            
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        
        # Only start if switch is ON (or we are in a permissive state)
        if current_switch_state and current_switch_state.state == STATE_ON:
            if not self._last_on_timestamp:
                self._last_on_timestamp = dt_util.utcnow()
        else:
             return
             
        # Initialize session state
        # We perform accumulation by adding the elapsed time of CURRENT session to the base state
        # The base state is the state at the beginning of THIS accumulation session
        self._last_accumulated_seconds = 0
        
        # Use standard HA timer helper instead of a custom loop
        # Update once per second - the frontend card handles smooth interpolation
        self._accumulation_task = async_track_time_interval(
            self.hass, self._async_update_accumulated_runtime, timedelta(seconds=1)
        )

    async def _stop_realtime_accumulation(self) -> None:
        """Stop real-time accumulation task."""
        if self._accumulation_task:
            self._accumulation_task()  # This is a remove callback for async_track_time_interval
            self._accumulation_task = None
            
        # Ensure final state update when stopping
        if self._last_on_timestamp:
             # Final update to capture any sub-second remainder or final segment
             self._async_update_accumulated_runtime(dt_util.utcnow(), final_update=True)

    @callback
    def _async_update_accumulated_runtime(self, now, final_update=False) -> None:
        """Periodically update the accumulated runtime."""
        if self._stop_event_received or not self._switch_entity_id:
            if not final_update:
                self.hass.async_create_task(self._stop_realtime_accumulation())
            return

        current_switch_state = self.hass.states.get(self._switch_entity_id)
        
        # Accumulate ONLY if switch is ON
        should_accumulate = (
            current_switch_state 
            and self._last_on_timestamp
            and (
                current_switch_state.state == STATE_ON 
                or current_switch_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            )
        )

        if should_accumulate:
            # Calculate total elapsed time from when switch turned on
            # We calculate purely based on (NOW - START) to avoid drift
            total_elapsed = (dt_util.utcnow() - self._last_on_timestamp).total_seconds()
            current_whole_second = round(total_elapsed)
            
            # Since self._state is monotonic, we only add the *difference* since last update
            # OR we can just rely on the fact that self._state should be base + elapsed,
            # but self._state might be modified by other things (like resets).
            # The safest way for "accumulation" is:
            # self._state += (current_whole_second - self._last_accumulated_seconds)
            
            diff = current_whole_second - self._last_accumulated_seconds
            if diff > 0:
                self._state += diff
                self._last_accumulated_seconds = current_whole_second
                self.async_write_ha_state()
        else:
            if not final_update:
                self.hass.async_create_task(self._stop_realtime_accumulation())

    async def async_start_timer(self, duration: float, unit: str = "min", reverse_mode: bool = False, start_method: str = "button") -> None:
        """Start a countdown timer with synchronized accumulation."""
        
        # Convert duration to minutes for internal storage
        duration_minutes = duration
        if unit in ["s", "sec", "seconds"]:
             duration_minutes = duration / 60.0
        elif unit in ["h", "hr", "hours"]:
             duration_minutes = duration * 60
        elif unit in ["d", "day", "days"]:
             duration_minutes = duration * 1440
             
        # Format for logging and notification
        unit_display = unit
        if unit in ["s", "sec", "seconds"]:
             unit_display = "sec"
             # Show integer if it's a whole number
             duration_display = int(duration) if duration.is_integer() else duration
        elif unit in ["m", "min", "minutes"]:
             unit_display = "min"
             duration_display = int(duration)
        elif unit in ["h", "hr", "hours"]:
             unit_display = "hr"
             # Show integer if it's a whole number, otherwise float
             duration_display = int(duration) if duration.is_integer() else duration
        elif unit in ["d", "day", "days"]:
             unit_display = "day"
             # Show integer if it's a whole number, otherwise float
             duration_display = int(duration) if duration.is_integer() else duration
        else:
             duration_display = duration
        
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Starting {'reverse' if reverse_mode else 'normal'} timer for {duration} {unit}")
        
        self._timer_start_method = start_method
        
        # Clear any existing watchdog message
        if self._watchdog_message:
            self._watchdog_message = None
        
        # Clean up existing timer
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        await self._stop_timer_update_task()
        
        # Store the runtime at timer start
        # For reverse mode, we don't want to count runtime until switch actually turns ON
        if reverse_mode:
            self._runtime_at_timer_start = self._state  # Set to current runtime, but don't accumulate until timer finishes
        else:
            self._runtime_at_timer_start = self._state
        
        # Handle switch state based on mode
        if reverse_mode:
            # REVERSE MODE: Decoupled - Do not force switch OFF.
            # Just ensure we aren't accumulating until timer finishes (which turns it ON).
            self._last_on_timestamp = None
            await self._stop_realtime_accumulation()
            # Logic removed: We no longer force turn_off here.
        else:
            # NORMAL MODE: Convenience turn ON, but don't wait for it
            current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
            if not current_switch_state or current_switch_state.state != STATE_ON:
                await self.hass.services.async_call(
                   "homeassistant", "turn_on", {"entity_id": self._switch_entity_id}, blocking=False
                )
                # DECOUPLED: Do NOT wait for state change. Start timer immediately.
                # User can turn switch on/off manually during timer.
        
        # Now set timer start time and duration atomically
        timer_start_moment = dt_util.utcnow()
        self._timer_duration = duration_minutes
        self._timer_state = "active"
        self._timer_finishes_at = timer_start_moment + timedelta(minutes=duration_minutes)
        self._timer_start_moment = timer_start_moment
        self._timer_reverse_mode = reverse_mode
        
        # Set last_on_timestamp only for normal mode
        if not reverse_mode and self._is_switch_on() and not self._last_on_timestamp:
            self._last_on_timestamp = timer_start_moment
        
        # Save timer state to storage
        async with self._storage_lock:
            data = await self._store.async_load() or {}
            data.update({
               "finishes_at": self._timer_finishes_at.isoformat(),
               "duration": duration_minutes,
               "timer_start": timer_start_moment.isoformat(),  # Store exact start time
               "runtime_at_start": self._runtime_at_timer_start,  # Store runtime when timer started
               "reverse_mode": reverse_mode
            })
            await self._store.async_save(data)
        
        # Start timer tasks
        await self._start_timer_update_task()
        await self._async_setup_switch_listener()
        
        # Start accumulation only in normal mode when switch is ON
        if not reverse_mode and self._is_switch_on():
            await self._start_realtime_accumulation()
        
        # Set up timer completion callback
        if self._timer_finishes_at:
            self._timer_unsub = async_track_point_in_utc_time(
               self.hass, self._async_timer_finished, self._timer_finishes_at
            )
        
        # Send notification
        mode_text = "Delayed timer started for" if reverse_mode else "Timer was started for"
        await self._send_notification(f"{mode_text} {duration_display} {unit_display}")
        
        self.async_write_ha_state()

    async def async_add_timer(self, duration: float, unit: str = "min") -> None:
        """Extend a currently running timer by adding duration."""
        if self._timer_state != "active":
            _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Cannot add time: Timer is not active")
            return

        # Convert duration to minutes
        duration_minutes = duration
        if unit in ["s", "sec", "seconds"]:
             duration_minutes = duration / 60.0
        elif unit in ["h", "hr", "hours"]:
             duration_minutes = duration * 60
        elif unit in ["d", "day", "days"]:
             duration_minutes = duration * 1440
             
        # Format for notification
        unit_display = unit
        duration_display = int(duration) if isinstance(duration, (int, float)) and duration % 1 == 0 else duration
        if unit in ["s", "sec", "seconds"]: unit_display = "sec"
        elif unit in ["m", "min", "minutes"]: unit_display = "min"
        
        # Check max limit (9999 days)
        MAX_DURATION_MINUTES = 9999 * 1440
        
        # Calculate current remaining time to check against limit
        remaining_seconds = 0
        if self._timer_finishes_at:
             remaining_seconds = max(0, (self._timer_finishes_at - dt_util.utcnow()).total_seconds())
        remaining_minutes = remaining_seconds / 60.0

        if remaining_minutes + duration_minutes > MAX_DURATION_MINUTES:
            old_duration_minutes = duration_minutes
            duration_minutes = max(0, MAX_DURATION_MINUTES - remaining_minutes)
            
            # If we can't add anything significant (less than 1 second approx), show notification
            if duration_minutes < 0.02:
                 _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Cannot extend: Timer is at maximum limit")
                 await self.hass.services.async_call(
                     "persistent_notification", 
                     "create", 
                     {
                         "title": "Simple Timer Limit",
                         "message": f"Cannot extend: Timer is at maximum limit ({int(MAX_DURATION_MINUTES/1440)} days)",
                         "notification_id": f"simple_timer_limit_{self._entry_id}"
                     }
                 )
                 return

            # Update display values to reflect capped amount
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Extension capped from {old_duration_minutes} to {duration_minutes} min to stay within limit")
            duration_display = round(duration_minutes, 1)
            # Simplify display if it's basically an integer now
            if duration_display % 1 == 0: duration_display = int(duration_display)
            unit_display = "min" # Force min unit since we calculated in minutes

        # Calculate new duration and finish time
        self._timer_duration += duration_minutes
        self._timer_finishes_at += timedelta(minutes=duration_minutes)
        
        # Update storage
        async with self._storage_lock:
            data = await self._store.async_load() or {}
            data.update({
               "finishes_at": self._timer_finishes_at.isoformat(),
               "duration": self._timer_duration,
            })
            await self._store.async_save(data)
            
        # Update timer completion callback
        if self._timer_unsub:
            self._timer_unsub()
            
        self._timer_unsub = async_track_point_in_utc_time(
           self.hass, self._async_timer_finished, self._timer_finishes_at
        )
        
        # Send notification
        remaining_seconds = max(0, int((self._timer_finishes_at - dt_util.utcnow()).total_seconds()))
        notification_entity, show_seconds = await self._get_card_notification_config()
        formatted_rest, label = self._format_time_for_notification(remaining_seconds, show_seconds)
        
        await self._send_notification(f"Timer extended by {duration_display} {unit_display}. New remaining: {formatted_rest} {label}")
        self.async_write_ha_state()

    async def async_cancel_timer(self, turn_off_entity: bool = True) -> None:
        """Cancel an active timer."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Cancelling timer")
        
        if self._timer_state == "idle":
            return
        
        if self._watchdog_message:
            self._watchdog_message = None
        
        # For cancelled timers, ensure we use the actual elapsed time, not the full duration
        if self._timer_start_moment:
            actual_elapsed = round((dt_util.utcnow() - self._timer_start_moment).total_seconds())
            runtime_at_timer_start = self._state - actual_elapsed
            # Recalculate to ensure accuracy with whole seconds
            self._state = runtime_at_timer_start + actual_elapsed
        
        # Get current usage for notification
        current_usage = self._state
        notification_entity, show_seconds = await self._get_card_notification_config()
        formatted_time, label = self._format_time_for_notification(current_usage, show_seconds)
        
        # Clean up timer
        await self._cleanup_timer_state()
        
        # Handle switch state based on timer mode
        reverse_mode = getattr(self, '_timer_reverse_mode', False)
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None

        if reverse_mode:
            # In reverse mode, canceling just stops the timer
            # Ensure we don't start accumulation (though it shouldn't if switch is off)
            await self._stop_realtime_accumulation()
        else:
            # Normal mode: Check passed argument for cancellation behavior
            if turn_off_entity:
                # COUPLED: Turn switch OFF.
                if self._switch_entity_id:
                    try:
                        await self.hass.services.async_call(
                            "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
                        )
                        await self._ensure_switch_state("off", "Timer cancellation turn-off")
                        await self._stop_realtime_accumulation()
                    except Exception as e:
                        _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not turn off switch: {e}")
            else:
                 # DECOUPLED: Do nothing
                 pass
        
        # Send notification
        await self._send_notification(f"Timer finished – daily usage {formatted_time} {label}")
        
        self.async_write_ha_state()
        
    @callback
    async def _async_timer_finished(self, now: dt_util.dt | None = None) -> None:
        """Handle timer completion with runtime compensation."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer finished")
        
        # Guard against zombie execution during shutdown
        if self._stop_event_received or self.hass.state == CoreState.stopping:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer finished during shutdown - ignoring to preserve state")
            return
        
        if self._timer_state != "active":
            return
            
        reverse_mode = getattr(self, '_timer_reverse_mode', False)
        
        try:
            # Set a flag to prevent the cancellation handler from running its logic
            self._is_finishing_normally = True
            
            if reverse_mode:
                # REVERSE MODE: Turn switch ON when timer finishes
                await self._cleanup_timer_state()
                
                if self._switch_entity_id:
                    await self.hass.services.async_call(
                        "homeassistant", "turn_on", {"entity_id": self._switch_entity_id}, blocking=True
                    )
                    await self._ensure_switch_state("on", "Reverse timer completion turn-on", blocking=True)
                    
                    # Reset state to not count the timer wait time as usage
                    # In reverse mode, usage should start from when switch turns ON
                    self._last_on_timestamp = dt_util.utcnow()
                    await self._start_realtime_accumulation()
                
                await self._send_notification(f"Delayed start timer completed - device turned ON")
            else:
                # NORMAL MODE: Original logic - turn switch OFF
                await self._stop_realtime_accumulation()
                
                # FORCE PRECISE ACCUMULATION FOR TIMER DURATION
                # This ensures that even if accumulation missed a second, we record the exact timer duration
                if self._runtime_at_timer_start is not None:
                     # Calculate what the state should be: base + duration
                     # But we must be careful not to double count if the timer was extended
                     # Actually, simplest path: Duration is king when limiting.
                     
                     # We want total usage = runtime_at_start + total_elapsed_during_timer
                     # runtime_at_start was the snapshot when timer started.
                     # duration is in minutes. 
                     
                     expected_usage = self._runtime_at_timer_start + (self._timer_duration * 60)
                     self._state = round(expected_usage)
                     _LOGGER.info(f"Simple Timer: [{self._entry_id}] Corrected final usage to {self._state}s (Target: {expected_usage}s)")

                self.async_write_ha_state()
                
                await asyncio.sleep(0.1)
                
                current_usage = self._state
                notification_entity, show_seconds = await self._get_card_notification_config()
                formatted_time, label = self._format_time_for_notification(current_usage, show_seconds)
                
                await self._cleanup_timer_state()
                
                if self._switch_entity_id:
                    await self._ensure_switch_state("off", "Timer completion turn-off", blocking=True)
                    
                await self._send_notification(f"Timer was turned off - daily usage {formatted_time} {label}")
            
            self.async_write_ha_state()
        finally:
            # Always unset the flag
            self._is_finishing_normally = False

    async def async_manual_power_toggle(self, action: str) -> None:
        """Handle manual power toggle from frontend."""
        if action == "turn_on":
            await self._ensure_switch_state("on", "Manual turn-on")
            await self._send_notification("Timer started")
        elif action == "turn_off":
            current_usage = self._state
            notification_entity, show_seconds = await self._get_card_notification_config()
            formatted_time, label = self._format_time_for_notification(current_usage, show_seconds)
            
            await self._ensure_switch_state("off", "Manual turn-off")
            await self._send_notification(f"Timer was turned off - daily usage {formatted_time} {label}")

    @callback
    def _reset_at_scheduled_time(self, now) -> None:
        """Handle scheduled daily reset."""
        self.hass.async_create_task(self._async_reset_at_scheduled_time())

    async def _async_reset_at_scheduled_time(self):
        """Perform scheduled daily reset."""
        await self._perform_reset(is_catchup=False)
        self._next_reset_date = self._get_next_reset_datetime()
        await self._save_next_reset_date()

    async def _handle_ha_shutdown(self, event):
        """Handle Home Assistant shutdown."""
        self._stop_event_received = True
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Home Assistant shutdown - cancelling tasks")
        
        # Cancel all tasks
        if self._accumulation_task and not self._accumulation_task.done():
            self._accumulation_task.cancel()
            
        if self._timer_update_task and not self._timer_update_task.done():
            self._timer_update_task.cancel()
            
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None

    async def async_will_remove_from_hass(self):
        """Handle entity removal."""
        self._stop_event_received = True
        
        # Remove listeners
        if hasattr(self._entry, 'remove_update_listener'):
            try:
                self._entry.remove_update_listener(self._handle_config_entry_update)
            except (ValueError, AttributeError):
                pass
        
        # Clean up reset time tracker
        if self._reset_time_tracker:
            self._reset_time_tracker()
            self._reset_time_tracker = None
        
        # Clean up domain data
        if (DOMAIN in self.hass.data and
            self._entry_id in self.hass.data[DOMAIN] and
            "sensor" in self.hass.data[DOMAIN][self._entry_id]):
            del self.hass.data[DOMAIN][self._entry_id]["sensor"]
        
        # Cancel tasks
        if self._accumulation_task and not self._accumulation_task.done():
            self._accumulation_task.cancel()
            try:
                await self._accumulation_task
            except asyncio.CancelledError:
                pass
        
        await self._stop_timer_update_task()
        
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        
        if self._state_listener_disposer:
            self._state_listener_disposer()
            self._state_listener_disposer = None
        
        await super().async_will_remove_from_hass()
        self.async_write_ha_state()

        try:
            from homeassistant.helpers import entity_registry as er
            entity_registry = er.async_get(self.hass)
            if entity_registry:
                entity_entry = entity_registry.async_get(self.entity_id)
                if entity_entry:
                    new_name = self.name
                    entity_registry.async_update_entity(self.entity_id, name=new_name)
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Manual sync: Updated entity registry to: '{new_name}'")
        except Exception as e:
            _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Manual sync entity registry update failed: {e}")

        return True

    async def async_set_default_timer_config(self, enabled: bool, duration: float, unit: str, reverse_mode: bool = False):
        """Update default timer configuration and save to storage."""
        self._default_timer_enabled = enabled
        self._default_timer_duration = duration
        self._default_timer_unit = unit
        self._default_timer_reverse_mode = reverse_mode
        
        async with self._storage_lock:
            data = await self._store.async_load() or {}
            data["default_timer"] = {
                "enabled": enabled,
                "duration": duration,
                "unit": unit,
                "reverse_mode": reverse_mode
            }
            await self._store.async_save(data)
            
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Called when entity is added to hass - startup-safe initialization."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Entity added to hass - startup safe mode")
        
        # Register sensor in domain data for service calls
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
        if self._entry_id not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][self._entry_id] = {}
        self.hass.data[DOMAIN][self._entry_id]["sensor"] = self
        
        # Restore basic state immediately to prevent history gaps
        await self._restore_basic_state()
        
        # Register shutdown handler
        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self._handle_ha_shutdown)
        
        # Defer complex initialization until after startup
        asyncio.create_task(self._wait_for_startup_completion())

    async def _restore_basic_state(self):
        """Restore basic state values immediately to prevent history gaps."""
        try:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state != "unavailable":
                try:
                    restored_value = float(last_state.state)
                    self._state = restored_value
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored state value: {restored_value}s")
                    
                    # Restore essential timer attributes
                    attrs = last_state.attributes
                    self._timer_duration = attrs.get(ATTR_TIMER_DURATION, 0)

                    if attrs.get(ATTR_TIMER_FINISHES_AT):
                        self._timer_finishes_at = datetime.fromisoformat(attrs[ATTR_TIMER_FINISHES_AT])
                        
                        # Only restore as "active" if timer hasn't expired
                        if self._timer_finishes_at and dt_util.utcnow() < self._timer_finishes_at:
                            self._timer_state = "active"
                        else:
                            self._timer_state = "idle"
                    else:
                        self._timer_state = attrs.get(ATTR_TIMER_STATE, "idle")
                    
                    if attrs.get(ATTR_LAST_ON_TIMESTAMP):
                        self._last_on_timestamp = datetime.fromisoformat(attrs[ATTR_LAST_ON_TIMESTAMP])
                    
                    self._timer_reverse_mode = attrs.get("reverse_mode", False)
                    if self._timer_reverse_mode:
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored reverse mode: {self._timer_reverse_mode}")
                    
                    # Restore runtime_at_timer_start from storage if timer was active
                    if self._timer_state == "active":
                        async with self._storage_lock:
                            try:
                                storage_data = await self._store.async_load()
                                if storage_data and "runtime_at_start" in storage_data:
                                    self._runtime_at_timer_start = storage_data["runtime_at_start"]
                                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored runtime_at_timer_start: {self._runtime_at_timer_start}s")
                                    
                                # Also restore reverse mode from storage if available (takes precedence)
                                if "reverse_mode" in storage_data:
                                    self._timer_reverse_mode = storage_data["reverse_mode"]
                                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored reverse mode from storage: {self._timer_reverse_mode}")
                            except Exception as e:
                                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not restore runtime_at_start or reverse_mode: {e}")
                        
                except (ValueError, TypeError) as e:
                    _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not restore state: {e}")
                    self._state = 0.0
            else:
                self._state = 0.0
                
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error during basic state restoration: {e}")
            self._state = 0.0

    async def _wait_for_startup_completion(self):
        """Wait for HA startup or essential dependencies with defensive checks."""
        try:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Waiting for HA startup or dependencies...")
            
            # Setup switch entity ID from config early for checks
            self._switch_entity_id = getattr(self._entry, 'data', {}).get('switch_entity_id')
            
            max_wait = 60
            start_time = dt_util.utcnow()
            check_interval = 1
            
            # 1. Wait for Core State Running
            if self.hass.state != CoreState.running:
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Waiting for HA Core (current: {self.hass.state})...")
                await self._wait_for_core_state(CoreState.running)
            
            # 2. Wait for dependencies even after Core is running
            # This ensures that even if Core says "running", we give integrations like Z-Wave/Zigbee
            # a chance to fully initialize their entities.
            while (dt_util.utcnow() - start_time).total_seconds() < max_wait:
                if await self._are_dependencies_ready():
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Dependencies ready")
                    break
                await asyncio.sleep(check_interval)
            
            elapsed = (dt_util.utcnow() - start_time).total_seconds()
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Startup wait completed after {elapsed:.1f}s")
            
            await self._complete_initialization()
            
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error during startup wait: {e}")
            # Always try to initialize even if startup wait fails
            try:
                await self._complete_initialization()
            except Exception as init_error:
                _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error during fallback initialization: {init_error}")

    async def _wait_for_core_state(self, target_state: CoreState):
        """Wait for HA core to reach a specific state."""
        start = dt_util.utcnow()
        while self.hass.state != target_state:
            if (dt_util.utcnow() - start).total_seconds() > 60:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Timed out waiting for CoreState.{target_state}")
                return
            await asyncio.sleep(1)
        _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Reached CoreState.{target_state}")

    async def _are_dependencies_ready(self) -> bool:
        """Check if all essential dependencies are ready."""
        # 1. Entity Registry
        if not await self._safe_check_entity_registry():
            return False
            
        # 2. Service Registry
        if not await self._safe_check_service_registry():
            return False
            
        # 3. Switch Entity (if configured)
        if not await self._safe_check_switch_entity():
            return False
            
        return True

    async def _safe_check_entity_registry(self) -> bool:
        """Safely check if entity registry is ready."""
        try:
            from homeassistant.helpers import entity_registry as er
            entity_registry = er.async_get(self.hass)
            
            # Basic availability test
            return entity_registry is not None
        except ImportError:
            # Module not available yet
            return False
        except Exception:
            # Any other error
            return False

    async def _safe_check_service_registry(self) -> bool:
        """Safely check if essential services are available."""
        try:
            services = self.hass.services.async_services()
            
            # Check for homeassistant domain (most critical)
            ha_services = services.get("homeassistant", {})
            has_turn_on = "turn_on" in ha_services
            has_turn_off = "turn_off" in ha_services
            
            return has_turn_on and has_turn_off
        except Exception:
            return False

    async def _safe_check_switch_entity(self) -> bool:
        """Safely check if switch entity is available."""
        if not self._switch_entity_id:
            return True
        
        try:
            switch_state = self.hass.states.get(self._switch_entity_id)
            if not switch_state:
                return False
            
            # Accept any state except unavailable/unknown
            return switch_state.state not in ["unavailable", "unknown"]
        except Exception:
            return False

    async def _complete_initialization(self):
        """Complete full initialization after HA startup."""
        try:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Completing initialization...")
            
            # Load storage data
            storage_data = await self._load_storage_data()
            
            # Restore default timer config
            if "default_timer" in storage_data:
                dt_config = storage_data["default_timer"]
                self._default_timer_enabled = dt_config.get("enabled", False)
                self._default_timer_duration = dt_config.get("duration", 0.0)
                self._default_timer_unit = dt_config.get("unit", "min")
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored default timer config: {self._default_timer_enabled}, {self._default_timer_duration} {self._default_timer_unit}")
            
            # Initialize reset scheduling with configurable reset time
            await self._setup_reset_scheduling(storage_data)
            
            # Set up listeners and handlers
            await self._setup_listeners_and_handlers()
            
            # Check for any timer that needs restoration (active OR expired)
            if storage_data.get("finishes_at"):
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Found timer data in storage - checking if restoration needed")
                try:
                    stored_finish_time = datetime.fromisoformat(storage_data["finishes_at"])
                    now = dt_util.utcnow()
                    remaining_time = (stored_finish_time - now).total_seconds()
                    reverse_mode = storage_data.get("reverse_mode", False)
                    
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer check - remaining: {remaining_time}s, reverse: {reverse_mode}")
                    
                    if remaining_time <= 0:
                        # Timer expired while offline - handle based on mode
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Expired timer detected - forcing restoration")
                        
                        # Temporarily set timer state as active to trigger restoration
                        self._timer_state = "active"
                        self._timer_finishes_at = stored_finish_time
                        self._timer_reverse_mode = reverse_mode
                        
                        await self._handle_active_timer_restoration(storage_data)
                    elif self._timer_state == "active" and self._timer_finishes_at:
                        # Regular active timer restoration
                        await self._handle_active_timer_restoration(storage_data)
                    else:
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] No active timer restoration needed")
                except Exception as e:
                    _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error during timer restoration check: {e}")
            else:
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] No timer data in storage")

            # Start accumulation if needed
            await self._start_accumulation_if_needed()

            # Final state write
            self.async_write_ha_state()
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Initialization completed successfully")
            
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error during initialization: {e}")

    async def _load_storage_data(self) -> dict:
        """Load storage data with migration support."""
        storage_data = None
        async with self._storage_lock:
            try:
                storage_data = await self._store.async_load()
            except NotImplementedError:
                # Handle storage migration
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Migrating storage format")
                try:
                    v1_store = Store(self.hass, 1, self.STORAGE_KEY_FORMAT.format(self._entry_id))
                    old_data = await v1_store.async_load()
                    if old_data:
                        new_data = old_data.copy()
                        new_data["next_reset_date"] = None
                        await self._store.async_save(new_data)
                        storage_data = new_data
                except Exception as migration_error:
                    _LOGGER.error(f"Simple Timer: [{self._entry_id}] Storage migration failed: {migration_error}")
            except Exception as e:
                _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error loading storage: {e}")
        
        return storage_data or {}

    async def _setup_reset_scheduling(self, storage_data: dict):
        """Set up daily reset scheduling with configurable reset time."""
        # Initialize next reset date
        self._next_reset_date = self._get_next_reset_datetime()
        
        # Restore from storage if available
        if storage_data.get("next_reset_date"):
            try:
                self._next_reset_date = datetime.fromisoformat(storage_data["next_reset_date"])
            except (ValueError, TypeError) as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not parse stored reset date: {e}")
                self._next_reset_date = self._get_next_reset_datetime()

        if not self._next_reset_date:
            self._next_reset_date = self._get_next_reset_datetime()
            await self._save_next_reset_date()

        # Check for missed resets only if we have historical data
        if storage_data.get("next_reset_date"):
            await self._check_missed_reset()

        # Set up scheduled reset with configurable time
        reset_time_str = self._reset_time.strftime("%H:%M:%S")
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Scheduling daily reset at {reset_time_str}")
        
        self._reset_time_tracker = async_track_time_change(
            self.hass, self._reset_at_scheduled_time, 
            hour=self._reset_time.hour, 
            minute=self._reset_time.minute, 
            second=self._reset_time.second
        )

    async def _setup_listeners_and_handlers(self):
        """Set up event listeners and handlers."""
        await self._async_setup_switch_listener()
        self._entry.add_update_listener(self._handle_config_entry_update)

    async def _handle_active_timer_restoration(self, storage_data: dict):
        """Handle restoration of active timers with stored timer start time."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Starting timer restoration")
        
        # Restore timer start moment if available
        if storage_data.get("timer_start"):
            try:
                self._timer_start_moment = datetime.fromisoformat(storage_data["timer_start"])
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored timer_start_moment: {self._timer_start_moment}")
            except (ValueError, TypeError):
                self._timer_start_moment = None
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Failed to restore timer_start_moment")

        # Restore total duration from storage if available (for extended timers)
        if storage_data.get("duration"):
            self._timer_duration = storage_data["duration"]
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored duration from storage: {self._timer_duration}")
        
        # Restore reverse mode from storage
        reverse_mode = storage_data.get("reverse_mode", False)
        self._timer_reverse_mode = reverse_mode
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored reverse_mode from storage: {reverse_mode}")
        
        now = dt_util.utcnow()
        remaining_time = (self._timer_finishes_at - now).total_seconds()
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Remaining time: {remaining_time} seconds")
        
        if remaining_time <= 0:
            # Timer expired while offline - handle based on mode
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer expired during offline period ({'REVERSE' if reverse_mode else 'NORMAL'} mode)")
            
            if reverse_mode:
                await self._handle_expired_reverse_timer()
            else:
                await self._handle_expired_timer()
        else:
            # Timer still active
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer still active with {int(remaining_time)} seconds remaining")
            await self._restore_active_timer(now)
        
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer restoration completed")

    async def _handle_expired_timer(self):
        """Handle timer that expired while HA was offline."""
        await asyncio.sleep(2)  # Safety delay
        
        # Load timer data from storage including reverse mode
        reverse_mode = False
        async with self._storage_lock:
            try:
                data = await self._store.async_load()
                if data:
                    if "runtime_at_start" in data:
                        self._runtime_at_timer_start = data["runtime_at_start"]
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored runtime_at_start for expired timer: {self._runtime_at_timer_start}s")
                    if "reverse_mode" in data:
                        reverse_mode = data["reverse_mode"]
                        self._timer_reverse_mode = reverse_mode
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored reverse mode for expired timer: {reverse_mode}")
            except Exception as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not load timer data: {e}")
        
        # Handle runtime calculation based on timer mode
        if reverse_mode:
            # For reverse mode: timer was counting down, device should now turn ON
            # Runtime should start from when timer finishes (now), not include countdown period
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Reverse mode timer expired - device will turn ON now")
            # Don't add the timer duration to runtime since device was OFF during countdown
        else:
            # For normal mode: device was ON during timer, add full duration to runtime
            # Since timer expired offline, we assume it completed successfully.
            if self._timer_duration > 0 and hasattr(self, '_runtime_at_timer_start'):
                expected_runtime = self._timer_duration * 60  # Whole seconds
                # Use round() for more accurate integer seconds
                self._state = self._runtime_at_timer_start + round(expected_runtime)
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Set runtime for expired normal timer: {self._state}s (start: {self._runtime_at_timer_start}s + duration: {expected_runtime}s)")
        
        # Get usage for notification BEFORE cleaning up (as cleanup might affect state access?)
        # Actually _state is safe.
        current_usage = self._state
        notification_entity, show_seconds = await self._get_card_notification_config()
        formatted_time, label = self._format_time_for_notification(current_usage, show_seconds)
        
        # FIX: Clear last_on_timestamp BEFORE cleanup to prevent final accumulation update from adding offline time
        self._last_on_timestamp = None

        # Clean up timer state FIRST to ensure we are in a clean idle state
        await self._cleanup_timer_state()
        
        # Add watchdog message AFTER cleanup so it persists
        self._watchdog_message = "Warning: Home assistant was offline during a running timer! Usage time may be unsynchronized."
        self.async_write_ha_state() # Ensure message is written to state
        
        # Handle switch state based on timer mode
        if reverse_mode:
            # For reverse mode: timer finished, turn switch ON and start accumulation
            if self._switch_entity_id:
                try:
                    # Use robust retry logic
                    await self._ensure_switch_state_with_retries("on", "Expired reverse timer turn-on")
                    
                    # Start accumulation since device is now ON (or will be soon)
                    self._last_on_timestamp = dt_util.utcnow()
                    await self._start_realtime_accumulation()
                    
                except Exception as e:
                    _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not turn on switch: {e}")
            
            # Send notification
            await asyncio.sleep(1)
            await self._send_notification(f"Delayed start timer completed - device turned ON")
        else:
            # For normal mode: timer finished, turn switch OFF
            if self._switch_entity_id:
                try:
                    # Use robust retry logic
                    await self._ensure_switch_state_with_retries("off", "Expired timer turn-off", force=True)
                except Exception as e:
                    _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not turn off switch: {e}")
            
            # Send notification
            await asyncio.sleep(1)
            await self._send_notification(f"Timer was turned off - daily usage {formatted_time} {label}")

    async def _ensure_switch_state_with_retries(self, desired_state: str, context: str, force: bool = False):
        """Ensure switch state with retries to handle startup unavailability."""
        if not self._switch_entity_id:
            return

        # First attempt (blocking to try and get it right immediately)
        # We wrap this in try/except to ensure we proceed to scheduling retry even if first attempt fails
        try:
             await self._ensure_switch_state(desired_state, context, blocking=True, force=force)
        except Exception as e:
             _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Initial switch attempt failed: {e}")

        # Schedule background verification
        self.hass.async_create_task(self._verify_and_retry_switch_state(desired_state, self._switch_entity_id, force=force))

    async def _verify_and_retry_switch_state(self, desired_state: str, entity_id: str, attempt: int = 1, force: bool = False):
        """Background task to verify switch state and retry if needed."""
        # Wait before checking (exponential-ish backoff: 2s, 5s, 10s, 20s)
        delays = [2, 5, 10, 20]
        if attempt > len(delays):
            return
            
        await asyncio.sleep(delays[attempt-1])
        
        # Safety Check: If we are trying to turn OFF, but a new timer has started and is active, ABORT.
        # This prevents the retry logic from fighting a user who just started a new timer.
        if desired_state == "off" and self._timer_state == "active":
             _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Aborting switch retry (off) because timer is now active")
             return
             
        current_state_obj = self.hass.states.get(entity_id)
        if not current_state_obj:
             # Entity missing, definitely retry
             _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Switch entity missing during verify, scheduling retry {attempt+1}")
             self.hass.async_create_task(self._verify_and_retry_switch_state(desired_state, entity_id, attempt + 1, force=force))
             return
             
        actual = current_state_obj.state
        
        # Check if state matches
        # If forcing (on first retry attempt), we ignore the match check to deal with stale HA state
        state_match = (actual == desired_state)
        should_skip_check = (force and attempt == 1)
        
        if state_match and not should_skip_check:
             return
             
        # If unavailable/unknown, we retry
        # If definitive mismatch (e.g. ON when should be OFF), we retry
        
        _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Switch state mismatch detected (Expected {desired_state}, got {actual}). Retrying attempt {attempt}...")
        
        action = "turn_on" if desired_state == "on" else "turn_off"
        try:
            await self.hass.services.async_call("homeassistant", action, {"entity_id": entity_id}, blocking=True)
        except Exception as e:
            _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Retry attempt {attempt} failed: {e}")
        
        # Schedule next check
        self.hass.async_create_task(self._verify_and_retry_switch_state(desired_state, entity_id, attempt + 1, force=force))

    async def _handle_expired_reverse_timer(self):
        """Handle reverse mode timer that expired while HA was offline."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Handling expired reverse timer")
        
        try:
            # Set a flag to prevent the cancellation handler from running its logic
            self._is_finishing_normally = True
            
            # Add watchdog message before cleanup
            self._watchdog_message = "Warning: Home assistant was offline during a running timer! Usage time may be unsynchronized."
            
            # Turn switch ON first (delayed start completed)
            if self._switch_entity_id:
                
                # Check current switch state first
                current_state = self.hass.states.get(self._switch_entity_id)
                if current_state:
                    pass  # State exists
                else:
                    _LOGGER.error(f"Simple Timer: [{self._entry_id}] Switch entity not found in hass.states!")
                
                try:
                    await self.hass.services.async_call(
                        "homeassistant", "turn_on", {"entity_id": self._switch_entity_id}, blocking=False
                    )
                    
                    # Wait and check if it worked
                    await asyncio.sleep(2)
                    updated_state = self.hass.states.get(self._switch_entity_id)
                    if updated_state:
                        pass  # State updated successfully
                    else:
                        _LOGGER.error(f"Simple Timer: [{self._entry_id}] Could not get updated switch state!")
                    
                    await self._ensure_switch_state("on", "Expired reverse timer completion turn-on", blocking=False, force=True)
                    
                except Exception as switch_error:
                    _LOGGER.error(f"Simple Timer: [{self._entry_id}] ERROR turning switch ON: {switch_error}")
                    import traceback
                    _LOGGER.error(f"Simple Timer: [{self._entry_id}] Switch error traceback: {traceback.format_exc()}")
                    raise
                
                # Set timestamp and start accumulation BEFORE cleanup
                self._last_on_timestamp = dt_util.utcnow()
                
            else:
                _LOGGER.error(f"Simple Timer: [{self._entry_id}] No switch entity configured!")
            
            # Clean up timer state AFTER switch is turned on
            await self._cleanup_timer_state()
            
            # Start accumulation after cleanup
            if self._switch_entity_id and self._last_on_timestamp:
                await self._start_realtime_accumulation()
            else:
                _LOGGER.error(f"Simple Timer: [{self._entry_id}] Cannot start accumulation - switch_entity: {self._switch_entity_id}, last_on: {self._last_on_timestamp}")
            
            await self._send_notification(f"Delayed start timer completed - device turned ON")
            
            self.async_write_ha_state()
            
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Expired reverse timer handling completed successfully")
            
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error handling expired reverse timer: {e}")
            import traceback
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error traceback: {traceback.format_exc()}")
        finally:
            # Always unset the flag
            self._is_finishing_normally = False

    async def _restore_active_timer(self, now: datetime):
        """Restore an active timer after restart."""
        await asyncio.sleep(1)  # Safety delay
        
        # Load timer data from storage including runtime_at_start
        async with self._storage_lock:
            try:
                data = await self._store.async_load()
                if data:
                    self._timer_duration = data.get("duration", self._timer_duration)
                    if data.get("timer_start"):
                        self._timer_start_moment = datetime.fromisoformat(data["timer_start"])
                    if "runtime_at_start" in data:
                        self._runtime_at_timer_start = data["runtime_at_start"]
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored runtime_at_start from storage: {self._runtime_at_timer_start}s")
                    # Ensure reverse mode is restored from storage
                    if "reverse_mode" in data:
                        self._timer_reverse_mode = data["reverse_mode"]
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored reverse mode from storage: {self._timer_reverse_mode}")
            except Exception as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not load timer data: {e}")
        
        # Add offline time and set watchdog message
        last_state = await self.async_get_last_state()
        if last_state and last_state.state != "unavailable":
            offline_seconds = (now - last_state.last_updated).total_seconds()
            if offline_seconds > 0:
                self._watchdog_message = "Warning: Home assistant was offline during a running timer! Usage time may be unsynchronized."
                
                # For reverse mode, we don't add offline time since device was OFF
                reverse_mode = getattr(self, '_timer_reverse_mode', False)
                if not reverse_mode:
                    # For normal timers, recalculate total usage from start time if available
                    # This is more accurate than adding offline time to potentially stale state
                    if self._runtime_at_timer_start is not None and self._timer_start_moment:
                         elapsed = (now - self._timer_start_moment).total_seconds()
                         self._state = self._runtime_at_timer_start + int(elapsed)
                         _LOGGER.info(f"Simple Timer: [{self._entry_id}] Recalculated usage from start time: {self._state}s")
                    else:
                        # Fallback to adding offline time if we lack start data
                        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Adjusting for offline gap of {int(offline_seconds)}s")
                        self._state += int(offline_seconds)
                    
                    # CRITICAL: We MUST reset _last_on_timestamp to NOW.
                    # Why? Because self._state now includes everything up to NOW.
                    # If we leave _last_on_timestamp at T0, the accumulation loop will calculate (NOW - T0)
                    # and add it to self._state, which would double-count the initial period.
                    self._last_on_timestamp = now
                else:
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Reverse mode timer - not adding offline time during countdown")
        
        # Restore timer tracking
        self._timer_unsub = async_track_point_in_utc_time(
            self.hass, self._async_timer_finished, self._timer_finishes_at
        )
        await self._start_timer_update_task()
        
        # Handle switch state based on timer mode
        reverse_mode = getattr(self, '_timer_reverse_mode', False)
        if reverse_mode:
            # For reverse mode, ensure switch stays OFF during countdown
            await self._ensure_switch_state("off", "Reverse timer state verification on restart", blocking=True)
        else:
            # For normal mode, ensure switch is ON
            await self._ensure_switch_state("on", "Active timer state verification on restart", blocking=True)

    async def _start_accumulation_if_needed(self):
        """Start accumulation if switch is on."""
        # Check if we have an active reverse mode timer
        reverse_mode_active = (
            self._timer_state == "active" and 
            getattr(self, '_timer_reverse_mode', False)
        )
        
        if reverse_mode_active:
            # For reverse mode timers, ensure switch stays OFF during countdown
            if self._switch_entity_id:
                current_switch_state = self.hass.states.get(self._switch_entity_id)
                if current_switch_state and current_switch_state.state == "on":
                    # Switch should be OFF during reverse timer countdown
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Ensuring switch stays OFF during reverse timer countdown")
                    try:
                        await self.hass.services.async_call(
                            "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
                        )
                    except Exception as e:
                        _LOGGER.error(f"Simple Timer: [{self._entry_id}] Failed to turn off switch during reverse timer: {e}")
            
            # Don't start accumulation during reverse timer countdown
            return
        
        # Normal behavior for non-reverse timers
        if self._is_switch_on() and not self._last_on_timestamp:
            self._last_on_timestamp = dt_util.utcnow()
            await self._start_realtime_accumulation()
        elif self._is_switch_on() and self._last_on_timestamp:
            await self._delayed_start_accumulation()

    async def _delayed_start_accumulation(self):
        """Start accumulation with a delay."""
        await asyncio.sleep(0.5)
        if self._is_switch_on() and self._last_on_timestamp and not self._stop_event_received:
            await self._start_realtime_accumulation()

    async def _handle_config_entry_update(self, hass: HomeAssistant, entry: ConfigEntry):
        """Handle config entry updates including reset time changes."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Config entry updated")
        self._last_known_title = entry.title
        self._last_known_data_name = entry.data.get("name")
        
        new_switch_entity = entry.data.get("switch_entity_id")
        if new_switch_entity != self._switch_entity_id:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Switch entity changed to: {new_switch_entity}")
            await self.async_update_switch_entity(new_switch_entity)
        
        # Check for reset time changes
        await self._update_reset_time()
        
        await self._handle_name_change()
        
    def _calculate_timer_elapsed_since_start(self) -> int:
        """Calculate elapsed time in seconds since the timer started."""
        if self._timer_state == "active" and self._timer_start_moment:
            now = dt_util.utcnow()
            elapsed = (now - self._timer_start_moment).total_seconds()
            return max(0, round(elapsed))
        return 0
        
    async def async_reset_daily_usage(self) -> None:
        """Manually reset daily usage to zero."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Manual daily usage reset requested")
        
        # Get current usage for notification
        current_usage = self._state
        notification_entity, show_seconds = await self._get_card_notification_config()
        formatted_time, label = self._format_time_for_notification(current_usage, show_seconds)
        
        # Stop any ongoing accumulation
        await self._stop_realtime_accumulation()
        
        # If timer is active, adjust the runtime_at_timer_start to maintain timer accuracy
        if self._timer_state == "active":
            # Set runtime_at_timer_start to negative elapsed time so final calculation remains correct
            if self._timer_start_moment:
                elapsed_seconds = (dt_util.utcnow() - self._timer_start_moment).total_seconds()
                self._runtime_at_timer_start = -elapsed_seconds
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Adjusted runtime_at_timer_start for active timer: {self._runtime_at_timer_start}s")
        else:
            self._runtime_at_timer_start = 0
        
        # Reset the state
        old_state = self._state
        self._state = 0.0
        self._last_on_timestamp = None
        
        # If switch is currently on, restart accumulation from zero
        if self._switch_entity_id:
            current_switch_state = self.hass.states.get(self._switch_entity_id)
            if current_switch_state and current_switch_state.state == STATE_ON:
                self._last_on_timestamp = dt_util.utcnow()
                await self._start_realtime_accumulation()
        
        # Update state immediately
        self.async_write_ha_state()
        
        # Send notification
        await self._send_notification(f"Daily usage reset from {formatted_time} {label} to 00:00")
        
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Daily usage reset: {old_state}s -> 0s")