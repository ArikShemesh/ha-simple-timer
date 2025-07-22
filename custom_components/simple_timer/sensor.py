"""Simple Timer – runtime counter + countdown timer sensor."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import (
    STATE_ON,
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
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Global reset time configuration (hour, minute, second)
# Default is midnight (0, 0, 0). Can be changed for testing.
RESET_TIME = time(0, 0, 0)

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

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Create a TimerRuntimeSensor for this config entry."""
    async_add_entities([TimerRuntimeSensor(hass, entry)])

class TimerRuntimeSensor(SensorEntity, RestoreEntity):
    """The sensor entity for Simple Timer."""
    _attr_has_entity_name = False
    _attr_icon = "mdi:timer"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

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
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_icon = "mdi:timer"

        self._last_known_title = entry.title
        self._last_known_data_name = entry.data.get("name")

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
        self._runtime_at_timer_start = 0  # NEW: Track runtime when timer started
        self._timer_unsub = None
        self._watchdog_message = None
        self._timer_update_task = None
        self._is_performing_reset = False

        # Reset scheduling
        self._next_reset_date = None
        self._last_reset_was_catchup = False
        self._catchup_reset_info = None

        # Storage setup
        self._storage_lock = asyncio.Lock()
        self._store = Store(hass, self.STORAGE_VERSION, self.STORAGE_KEY_FORMAT.format(self._entry_id))

    @property
    def instance_title(self) -> str:
        """Get the current instance title from the config entry."""
        data_name = self._entry.data.get("name")
        if data_name:
            return data_name
        return self._entry.title or "Timer"

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
        }

        if self._last_reset_was_catchup:
            attrs["last_reset_type"] = "catch-up"
            if self._catchup_reset_info:
                attrs["reset_info"] = self._catchup_reset_info
            self._last_reset_was_catchup = False

        return attrs

    async def _get_card_notification_config(self) -> tuple[str | None, bool]:
        """Get notification entity and show_seconds setting from timer card configuration."""
        try:
            # Try to get from storage files first
            notification_entity, show_seconds = await self._get_notification_from_storage()
            if notification_entity:
                return notification_entity, show_seconds
            
            # Fallback to runtime lovelace data
            if hasattr(self.hass, 'data') and 'lovelace' in self.hass.data:
                lovelace_data = self.hass.data['lovelace']
                
                # Iterate through dashboard configurations to find our card
                for dashboard in lovelace_data.values():
                    try:
                        if hasattr(dashboard, 'config') and dashboard.config:
                            notification_entity, show_seconds = self._search_cards_in_config(dashboard.config)
                            if notification_entity:
                                return notification_entity, show_seconds
                    except Exception:
                        continue
            
            return None, False
                            
        except Exception as e:
            _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Error getting notification config: {e}")
            return None, False

    def _search_cards_in_config(self, config: dict) -> tuple[str | None, bool]:
        """Recursively search for timer cards in lovelace config."""
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
        """Get notification config from storage files using async operations."""
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

    async def _send_notification(self, message: str) -> None:
        """Send notification using configured notification entity."""
        try:
            notification_entity, show_seconds = await self._get_card_notification_config()
            
            if not notification_entity:
                return
                
            # Parse the service call format
            service_parts = notification_entity.split('.')
            if len(service_parts) < 2:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Invalid notification entity format: {notification_entity}")
                return
                
            domain = service_parts[0]
            service = '.'.join(service_parts[1:])
            title = self.instance_title or "Timer"
            
            await self.hass.services.async_call(
                domain, service, {"message": message, "title": title}
            )
            
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Failed to send notification: {e}")
            
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
        """Calculate the next reset datetime from a given date."""
        if from_date is None:
            from_date = dt_util.now().date()
        
        reset_datetime = datetime.combine(from_date, RESET_TIME)
        reset_datetime = dt_util.as_local(reset_datetime)
        
        now = dt_util.now()
        if reset_datetime <= now:
            tomorrow = from_date + timedelta(days=1)
            reset_datetime = datetime.combine(tomorrow, RESET_TIME)
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
            _LOGGER.info(
                f"Simple Timer: [{self._entry_id}] Performing {reset_type} daily runtime reset. "
                f"Current state: {self._state}s"
            )

            await self._stop_realtime_accumulation()

            if self._timer_state == "active":
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Reset occurred during an active timer. Adjusting timer's base runtime.")
                self._runtime_at_timer_start = 0.0 - self._calculate_timer_elapsed_since_start()

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
        if self._timer_update_task and not self._timer_update_task.done():
            return
        self._timer_update_task = self.hass.async_create_task(self._timer_update_loop())

    async def _stop_timer_update_task(self):
        """Stop timer update task."""
        if self._timer_update_task and not self._timer_update_task.done():
            self._timer_update_task.cancel()
            try:
                await self._timer_update_task
            except asyncio.CancelledError:
                pass
            self._timer_update_task = None

    async def _timer_update_loop(self):
        """Timer update loop."""
        try:
            iteration = 0
            while self._timer_state == "active" and self._timer_finishes_at and not self._stop_event_received:
                iteration += 1
                
                if self._calculate_timer_remaining() <= 0:
                    break
                
                # Use slower updates initially to be gentler on startup
                update_interval = 5 if iteration <= 12 else 1
                
                self.async_write_ha_state()
                await asyncio.sleep(update_interval)
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error in timer update loop: {e}")

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

        # Switch turned off
        elif to_state.state != STATE_ON and from_state and from_state.state == STATE_ON:
            self.hass.async_create_task(self._stop_realtime_accumulation())
            self._last_on_timestamp = None
            if self._timer_state == "active":
                self.hass.async_create_task(self._auto_cancel_timer_on_external_off())
        
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
        self._runtime_at_timer_start = 0  # Reset this too
        
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
        
        if self._accumulation_task and not self._accumulation_task.done():
            return
        
        if not self._last_on_timestamp:
            current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
            if current_switch_state and current_switch_state.state == STATE_ON:
                self._last_on_timestamp = dt_util.utcnow()
            else:
                return
        
        self._accumulation_task = self.hass.async_create_task(self._async_accumulate_runtime())

    async def _stop_realtime_accumulation(self) -> None:
        """Stop real-time accumulation task."""
        if self._accumulation_task and not self._accumulation_task.done():
            self._accumulation_task.cancel()
            try:
                await self._accumulation_task
            except asyncio.CancelledError:
                pass
            self._accumulation_task = None

    async def _async_accumulate_runtime(self) -> None:
        """Accumulate runtime while switch is on using actual elapsed time."""
        try:
            # For timer-based accumulation, use a more precise approach
            if self._timer_state == "active" and self._timer_start_moment:
                runtime_at_start = getattr(self, '_runtime_at_timer_start', self._state)
                last_whole_second = -1
                
                while not self._stop_event_received:
                    if not self._switch_entity_id:
                        break
                    
                    current_switch_state = self.hass.states.get(self._switch_entity_id)
                    if current_switch_state and current_switch_state.state == STATE_ON and self._timer_start_moment:
                        # Calculate total elapsed time from timer start
                        now = dt_util.utcnow()
                        total_elapsed = (now - self._timer_start_moment).total_seconds()
                        current_whole_second = int(total_elapsed)
                        
                        # Only update when we cross a whole second boundary
                        if current_whole_second != last_whole_second:
                            self._state = runtime_at_start + current_whole_second
                            last_whole_second = current_whole_second
                            self.async_write_ha_state()
                        
                        # Check if timer is about to end
                        if self._timer_finishes_at:
                            remaining = (self._timer_finishes_at - now).total_seconds()
                            if remaining <= 0.2:
                                # Timer is about to finish, let the timer callback handle final update
                                break
                        
                        await asyncio.sleep(0.05)  # Check 20 times per second for accuracy
                    else:
                        break
            else:
                # For manual on/off, use the original accumulation method
                accumulation_start = self._last_on_timestamp or dt_util.utcnow()
                base_runtime = self._state
                last_whole_second = -1
                
                while not self._stop_event_received:
                    if not self._switch_entity_id:
                        break
                    
                    current_switch_state = self.hass.states.get(self._switch_entity_id)
                    if current_switch_state and current_switch_state.state == STATE_ON and self._last_on_timestamp:
                        # Calculate total elapsed time from when switch turned on
                        now = dt_util.utcnow()
                        total_elapsed = (now - accumulation_start).total_seconds()
                        current_whole_second = int(total_elapsed)
                        
                        # Only update when we cross a whole second boundary
                        if current_whole_second != last_whole_second:
                            self._state = base_runtime + current_whole_second
                            last_whole_second = current_whole_second
                            self.async_write_ha_state()
                        
                        await asyncio.sleep(0.05)  # Check 20 times per second for accuracy
                    else:
                        break
                    
        except asyncio.CancelledError:
            # If the timer is finishing normally OR a reset is happening, do nothing.
            if getattr(self, '_is_finishing_normally', False) or getattr(self, '_is_performing_reset', False):
                raise

            # Ensure final state is correct when cancelled MANUALLY or externally
            if self._timer_state == "active" and self._timer_start_moment:
                runtime_at_start = getattr(self, '_runtime_at_timer_start', 0)
                final_elapsed = round((dt_util.utcnow() - self._timer_start_moment).total_seconds())
                self._state = runtime_at_start + final_elapsed
                self.async_write_ha_state()
            elif self._last_on_timestamp:
                # For manual mode
                accumulation_start = self._last_on_timestamp
                base_runtime = self._state - int((dt_util.utcnow() - accumulation_start).total_seconds())
                final_elapsed = int((dt_util.utcnow() - accumulation_start).total_seconds())
                self._state = base_runtime + final_elapsed
                self.async_write_ha_state()
            raise
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error in accumulation task: {e}")

    async def async_start_timer(self, duration_minutes: int) -> None:
        """Start a countdown timer with synchronized accumulation."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Starting timer for {duration_minutes} minutes")
        
        # Clear any existing watchdog message
        if self._watchdog_message:
            self._watchdog_message = None
        
        # Clean up existing timer
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        await self._stop_timer_update_task()
        
        # Store the runtime at timer start (before we turn on the switch)
        self._runtime_at_timer_start = self._state
        
        # Turn on switch first if needed
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        if not current_switch_state or current_switch_state.state != STATE_ON:
            await self.hass.services.async_call(
               "homeassistant", "turn_on", {"entity_id": self._switch_entity_id}, blocking=True
            )
            # Wait for switch to actually turn on
            for _ in range(10):  # Max 1 second wait
                await asyncio.sleep(0.1)
                state = self.hass.states.get(self._switch_entity_id)
                if state and state.state == STATE_ON:
                    break
        
        # Now set timer start time and duration atomically
        timer_start_moment = dt_util.utcnow()
        self._timer_duration = duration_minutes
        self._timer_state = "active"
        self._timer_finishes_at = timer_start_moment + timedelta(minutes=duration_minutes)
        self._timer_start_moment = timer_start_moment
        
        # Set last_on_timestamp to the exact same moment
        if not self._last_on_timestamp:
            self._last_on_timestamp = timer_start_moment
        
        # Save timer state to storage
        async with self._storage_lock:
            data = await self._store.async_load() or {}
            data.update({
               "finishes_at": self._timer_finishes_at.isoformat(),
               "duration": duration_minutes,
               "timer_start": timer_start_moment.isoformat(),  # Store exact start time
               "runtime_at_start": self._runtime_at_timer_start  # Store runtime when timer started
            })
            await self._store.async_save(data)
        
        # Start timer tasks
        await self._start_timer_update_task()
        await self._async_setup_switch_listener()
        
        # Start accumulation immediately
        if self._is_switch_on():
            await self._start_realtime_accumulation()
        
        # Set up timer completion callback
        if self._timer_finishes_at:
            self._timer_unsub = async_track_point_in_utc_time(
               self.hass, self._async_timer_finished, self._timer_finishes_at
            )
        
        # Send notification
        await self._send_notification(f"Timer was turned on for {duration_minutes} minutes")
        
        self.async_write_ha_state()

    async def async_cancel_timer(self) -> None:
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
        
        # Turn off switch
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        if current_switch_state and current_switch_state.state == STATE_ON:
            await self.hass.services.async_call(
               "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
            )
        else:
            await self._stop_realtime_accumulation()
        
        # Send notification
        await self._send_notification(f"Timer finished – daily usage {formatted_time} {label}")
        
        self.async_write_ha_state()
        
    @callback
    async def _async_timer_finished(self, now: dt_util.dt | None = None) -> None:
        """Handle timer completion with runtime compensation."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer finished")
        
        if self._timer_state != "active":
            return
        
        try:
            # Set a flag to prevent the cancellation handler from running its logic
            self._is_finishing_normally = True
            
            # Stop accumulation task first to prevent race conditions
            await self._stop_realtime_accumulation()
            
            # Always set runtime to exact timer duration for timer-based usage
            if self._timer_duration > 0:
                expected_runtime = self._timer_duration * 60  # Convert to seconds
                runtime_at_start = getattr(self, '_runtime_at_timer_start', 0)
                self._state = runtime_at_start + expected_runtime
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Set runtime to exact timer duration: {self._state}s (start: {runtime_at_start}s + duration: {expected_runtime}s)")
            
            self.async_write_ha_state()
            
            await asyncio.sleep(0.1)
            
            current_usage = self._state
            notification_entity, show_seconds = await self._get_card_notification_config()
            formatted_time, label = self._format_time_for_notification(current_usage, show_seconds)
            
            await self._cleanup_timer_state()
            
            if self._switch_entity_id:
                await self.hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
                )
            
            await self._send_notification(f"Timer was turned off - daily usage {formatted_time} {label}")
            
            self.async_write_ha_state()
        finally:
            # Always unset the flag
            self._is_finishing_normally = False

    async def async_manual_power_toggle(self, action: str) -> None:
        """Handle manual power toggle from frontend."""
        if action == "turn_on":
            await self.hass.services.async_call(
                "homeassistant", "turn_on", {"entity_id": self._switch_entity_id}
            )
            await self._send_notification("Timer started")
        elif action == "turn_off":
            current_usage = self._state
            notification_entity, show_seconds = await self._get_card_notification_config()
            formatted_time, label = self._format_time_for_notification(current_usage, show_seconds)
            
            await self.hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}
            )
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
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Home Assistant shutdown - cancelling tasks")
        
        self._stop_event_received = True
        
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
                    self._timer_state = attrs.get(ATTR_TIMER_STATE, "idle")
                    self._timer_duration = attrs.get(ATTR_TIMER_DURATION, 0)
                    
                    if attrs.get(ATTR_TIMER_FINISHES_AT):
                        self._timer_finishes_at = datetime.fromisoformat(attrs[ATTR_TIMER_FINISHES_AT])
                    
                    if attrs.get(ATTR_LAST_ON_TIMESTAMP):
                        self._last_on_timestamp = datetime.fromisoformat(attrs[ATTR_LAST_ON_TIMESTAMP])
                    
                    # Restore runtime_at_timer_start from storage if timer was active
                    if self._timer_state == "active":
                        async with self._storage_lock:
                            try:
                                storage_data = await self._store.async_load()
                                if storage_data and "runtime_at_start" in storage_data:
                                    self._runtime_at_timer_start = storage_data["runtime_at_start"]
                                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored runtime_at_timer_start: {self._runtime_at_timer_start}s")
                            except Exception as e:
                                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not restore runtime_at_start: {e}")
                        
                except (ValueError, TypeError) as e:
                    _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not restore state: {e}")
                    self._state = 0.0
            else:
                self._state = 0.0
                
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error during basic state restoration: {e}")
            self._state = 0.0

    async def _wait_for_startup_completion(self):
        """Wait for HA startup to complete, then finish initialization."""
        try:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Waiting for HA startup completion...")
            
            # Wait for HA to reach running state
            startup_wait_time = 30
            for i in range(startup_wait_time):
                if self.hass.state == CoreState.running:
                    await asyncio.sleep(5)  # Buffer time
                    break
                await asyncio.sleep(1)
            else:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] HA state never became running, proceeding after {startup_wait_time}s")
            
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] HA startup completed, finishing initialization")
            await self._complete_initialization()
            
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error during startup completion: {e}")
            try:
                await self._complete_initialization()
            except Exception as restore_error:
                _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error during initialization: {restore_error}")

    async def _complete_initialization(self):
        """Complete full initialization after HA startup."""
        try:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Completing initialization...")
            
            # Load storage data
            storage_data = await self._load_storage_data()
            
            # Initialize reset scheduling
            await self._setup_reset_scheduling(storage_data)
            
            # Set up listeners and handlers
            await self._setup_listeners_and_handlers()
            
            # Handle active timers
            if self._timer_state == "active" and self._timer_finishes_at:
                await self._handle_active_timer_restoration(storage_data)

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
        """Set up daily reset scheduling."""
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

        # Set up scheduled reset
        async_track_time_change(
            self.hass, self._reset_at_scheduled_time, 
            hour=RESET_TIME.hour, minute=RESET_TIME.minute, second=RESET_TIME.second
        )

    async def _setup_listeners_and_handlers(self):
        """Set up event listeners and handlers."""
        await self._async_setup_switch_listener()
        self._entry.add_update_listener(self._handle_config_entry_update)

    async def _handle_active_timer_restoration(self, storage_data: dict):
        """Handle restoration of active timers with stored timer start time."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restoring active timer")
        
        # Restore timer start moment if available
        if storage_data.get("timer_start"):
            try:
                self._timer_start_moment = datetime.fromisoformat(storage_data["timer_start"])
            except (ValueError, TypeError):
                self._timer_start_moment = None
        
        now = dt_util.utcnow()
        remaining_time = (self._timer_finishes_at - now).total_seconds()
        
        if remaining_time <= 0:
            # Timer expired while offline
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer expired during offline period")
            await self._handle_expired_timer()
        else:
            # Timer still active
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restoring active timer with {int(remaining_time)} seconds remaining")
            await self._restore_active_timer(now)

    async def _handle_expired_timer(self):
        """Handle timer that expired while HA was offline."""
        await asyncio.sleep(2)  # Safety delay
        
        # Load runtime_at_start from storage first
        async with self._storage_lock:
            try:
                data = await self._store.async_load()
                if data and "runtime_at_start" in data:
                    self._runtime_at_timer_start = data["runtime_at_start"]
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restored runtime_at_start for expired timer: {self._runtime_at_timer_start}s")
            except Exception as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not load runtime_at_start: {e}")
        
        # Set runtime to be the timer start runtime plus the full timer duration
        if self._timer_duration > 0 and hasattr(self, '_runtime_at_timer_start'):
            expected_runtime = self._timer_duration * 60  # Whole seconds
            self._state = self._runtime_at_timer_start + expected_runtime
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Set runtime for expired timer: {self._state}s (start: {self._runtime_at_timer_start}s + duration: {expected_runtime}s)")
        
        # Add watchdog message
        self._watchdog_message = "Warning: Home assistant was offline during a running timer! Usage time may be unsynchronized."
        
        # Get usage for notification
        current_usage = self._state
        notification_entity, show_seconds = await self._get_card_notification_config()
        formatted_time, label = self._format_time_for_notification(current_usage, show_seconds)
        
        # Clean up timer state
        await self._cleanup_timer_state()
        
        # Turn off switch
        if self._switch_entity_id:
            try:
                await self.hass.services.async_call(
                    "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
                )
            except Exception as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not turn off switch: {e}")
        
        # Send notification
        await asyncio.sleep(1)
        await self._send_notification(f"Timer was turned off - daily usage {formatted_time} {label}")

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
            except Exception as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not load timer data: {e}")
        
        # Add offline time and set watchdog message
        last_state = await self.async_get_last_state()
        if last_state and last_state.state != "unavailable":
            offline_seconds = (now - last_state.last_updated).total_seconds()
            if offline_seconds > 0:
                # Add offline time to the current state
                self._state += int(offline_seconds)
                self._watchdog_message = "Warning: Home assistant was offline during a running timer! Usage time may be unsynchronized."
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Added {int(offline_seconds)}s offline time to runtime")
        
        # Restore timer tracking
        self._timer_unsub = async_track_point_in_utc_time(
            self.hass, self._async_timer_finished, self._timer_finishes_at
        )
        await self._start_timer_update_task()

    async def _start_accumulation_if_needed(self):
        """Start accumulation if switch is on."""
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
        """Handle config entry updates."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Config entry updated")
        self._last_known_title = entry.title
        self._last_known_data_name = entry.data.get("name")
        
        new_switch_entity = entry.data.get("switch_entity_id")
        if new_switch_entity != self._switch_entity_id:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Switch entity changed to: {new_switch_entity}")
            await self.async_update_switch_entity(new_switch_entity)
        
        await self._handle_name_change()
        
    def _calculate_timer_elapsed_since_start(self) -> int:
        """Calculate elapsed time in seconds since the timer started."""
        if self._timer_state == "active" and self._timer_start_moment:
            now = dt_util.utcnow()
            elapsed = (now - self._timer_start_moment).total_seconds()
            return max(0, round(elapsed))
        return 0