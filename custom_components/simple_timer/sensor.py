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
)
from homeassistant.core import HomeAssistant, callback, Event, State
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
RESET_TIME = time(0, 0, 0)  # Change to time(14, 30, 0) for 2:30 PM reset

# Attributes for the sensor state
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
    _LOGGER.debug("Simple Timer: Setting up entry for %s", entry.entry_id)
    async_add_entities(
        [TimerRuntimeSensor(hass, entry)]
    )

class TimerRuntimeSensor(SensorEntity, RestoreEntity):
    """The sensor entity for Simple Timer."""
    _attr_has_entity_name = False
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    STORAGE_VERSION = 2
    STORAGE_KEY_FORMAT = f"{DOMAIN}_{{}}"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._switch_entity_id = entry.data.get("switch_entity_id")

        entry_id_short = self._entry_id[:8]
        self._entry_id_short = entry_id_short

        self._attr_unique_id = f"timer_runtime_{self._entry_id}"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_icon = "mdi:timer"

        self._last_known_title = entry.title
        self._last_known_data_name = entry.data.get("name")

        _LOGGER.info(f"Simple Timer: Creating sensor for entry_id: {self._entry_id}")

        self._state = 0.0
        self._last_on_timestamp = None
        self._accumulation_task = None
        self._state_listener_disposer = None
        self._stop_event_received = False

        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0
        self._timer_unsub = None
        self._watchdog_message = None
        self._timer_update_task = None

        self._next_reset_date = None
        self._last_reset_was_catchup = False
        self._catchup_reset_info = None

        self._storage_lock = asyncio.Lock()
        self._store = Store(
            hass,
            self.STORAGE_VERSION,
            self.STORAGE_KEY_FORMAT.format(self._entry_id),
        )

        _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Sensor initialized")

    @property
    def instance_title(self) -> str:
        """Get the current instance title from the config entry (always fresh)."""
        data_name = self._entry.data.get("name")
        if data_name:
            return data_name
        return self._entry.title or "Timer"

    @property
    def name(self) -> str:
        """Return the name of the sensor (dynamically generated from current config)."""
        current_title = self.instance_title
        return f"{current_title} Runtime ({self._entry_id_short})"

    @property
    def native_value(self) -> float:
        """Return the current daily runtime in seconds."""
        return self._state

    def _calculate_timer_remaining(self) -> int:
        """Calculate remaining time in seconds for active timer."""
        if self._timer_state == "active" and self._timer_finishes_at:
            now = dt_util.utcnow()
            remaining = (self._timer_finishes_at - now).total_seconds()
            return max(0, int(remaining))
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes for the card and for restoring state."""
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

    async def _save_next_reset_date(self):
        """Save the next reset date to storage, protected by a lock."""
        async with self._storage_lock:
            try:
                data = await self._store.async_load() or {}
                data["next_reset_date"] = self._next_reset_date.isoformat()
                await self._store.async_save(data)
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Saved next reset date: {self._next_reset_date}")
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
        """Centralized reset logic used by both scheduled and catch-up resets."""
        reset_type = "catch-up" if is_catchup else "scheduled"
        _LOGGER.info(
            f"Simple Timer: [{self._entry_id}] Performing {reset_type} daily runtime reset. "
            f"Current state: {self._state}s"
        )
        
        self._state = 0.0
        self._last_on_timestamp = None
        
        if self._switch_entity_id:
            current_switch_state = self.hass.states.get(self._switch_entity_id)
            if current_switch_state and current_switch_state.state == STATE_ON:
                self._last_on_timestamp = dt_util.utcnow()
                await self._start_realtime_accumulation()
            else:
                await self._stop_realtime_accumulation()
        
        self.async_write_ha_state()

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
                    entity_registry.async_update_entity(
                        self.entity_id,
                        name=self.name
                    )
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] Updated entity registry with new name: '{self.name}'")
                except Exception as e:
                    _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not update entity registry: {e}")

    def _check_and_handle_name_changes(self):
        """Check for name changes and handle them synchronously when possible."""
        current_title = self._entry.title
        current_data_name = self._entry.data.get("name")

        if (current_title != self._last_known_title or
            current_data_name != self._last_known_data_name):

            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Name change detected: title='{current_title}', data_name='{current_data_name}'")
            self._last_known_title = current_title
            self._last_known_data_name = current_data_name
            self.hass.async_create_task(self._handle_name_change())

    async def async_force_name_sync(self):
        """Force immediate name synchronization - callable via service."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] MANUAL name sync triggered via service")
        self._last_known_title = None
        self._last_known_data_name = None
        await self._handle_name_change()
        self.async_write_ha_state()

        try:
            from homeassistant.helpers import entity_registry as er
            entity_registry = er.async_get(self.hass)
            if entity_registry:
                entity_entry = entity_registry.async_get(self.entity_id)
                if entity_entry:
                    new_name = self.name
                    entity_registry.async_update_entity(
                        self.entity_id,
                        name=new_name
                    )
                    _LOGGER.info(f"Simple Timer: [{self._entry_id}] MANUAL SYNC: Updated entity registry to: '{new_name}'")
        except Exception as e:
            _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Manual sync entity registry update failed: {e}")

        return True

    async def async_added_to_hass(self):
        """Called when entity is added to hass."""
        await super().async_added_to_hass()

        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
        if self._entry_id not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][self._entry_id] = {}
        self.hass.data[DOMAIN][self._entry_id]["sensor"] = self

        self._entry.add_update_listener(self._handle_config_entry_update)
        self.hass.bus.async_listen_once("homeassistant_stop", self._handle_ha_shutdown)
        self.hass.bus.async_listen_once("homeassistant_final_write", self._handle_ha_shutdown)

        _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Sensor stored in hass.data")

        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._state = float(last_state.state)
                attrs = last_state.attributes
                self._timer_state = attrs.get(ATTR_TIMER_STATE, "idle")
                self._timer_duration = attrs.get(ATTR_TIMER_DURATION, 0)
                self._watchdog_message = attrs.get(ATTR_WATCHDOG_MESSAGE)
                if attrs.get(ATTR_TIMER_FINISHES_AT):
                    self._timer_finishes_at = datetime.fromisoformat(attrs[ATTR_TIMER_FINISHES_AT])
                if attrs.get(ATTR_LAST_ON_TIMESTAMP):
                    self._last_on_timestamp = datetime.fromisoformat(attrs[ATTR_LAST_ON_TIMESTAMP])
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Restored state: {self._state}s, timer: {self._timer_state}")
            except (ValueError, TypeError) as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not restore state: {e}")
                self._state = 0.0

        storage_data = None
        async with self._storage_lock:
            try:
                storage_data = await self._store.async_load()
            except NotImplementedError:
                _LOGGER.info("Simple Timer: [{self._entry_id}] Old storage version detected. Attempting manual migration.")
                try:
                    v1_store = Store(self.hass, 1, self.STORAGE_KEY_FORMAT.format(self._entry_id))
                    old_data = await v1_store.async_load()
                    if old_data:
                        new_data = old_data.copy()
                        new_data["next_reset_date"] = None
                        await self._store.async_save(new_data)
                        _LOGGER.info("Simple Timer: [{self._entry_id}] Manual migration successful.")
                        storage_data = new_data
                except Exception as migration_error:
                    _LOGGER.error("Simple Timer: [{self._entry_id}] Failed to manually migrate storage: %s", migration_error)
            except Exception as e:
                _LOGGER.error("Simple Timer: [{self._entry_id}] Error loading storage: %s", e)

        storage_data = storage_data or {}

        if storage_data.get("next_reset_date"):
            try:
                self._next_reset_date = datetime.fromisoformat(storage_data["next_reset_date"])
                _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Restored next reset date: {self._next_reset_date}")
            except (ValueError, TypeError) as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not parse stored next reset date: {e}")
                self._next_reset_date = None

        if not self._next_reset_date:
            self._next_reset_date = self._get_next_reset_datetime()
            await self._save_next_reset_date()
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Initialized next reset date to: {self._next_reset_date}")

        await self._check_missed_reset()
        await self._async_setup_switch_listener()

        async_track_time_change(
            self.hass, 
            self._reset_at_scheduled_time, 
            hour=RESET_TIME.hour, 
            minute=RESET_TIME.minute, 
            second=RESET_TIME.second
        )

        if self._timer_state == "active" and self._timer_finishes_at:
            self.hass.async_create_task(self._restore_active_timer())

        if self._is_switch_on() and not self._last_on_timestamp:
            self._last_on_timestamp = dt_util.utcnow()
            self.hass.async_create_task(self._start_realtime_accumulation())
        elif self._is_switch_on() and self._last_on_timestamp:
            self.hass.async_create_task(self._delayed_start_accumulation())

    async def _handle_config_entry_update(self, hass: HomeAssistant, entry: ConfigEntry):
        """Handle updates to the config entry (including renames)."""
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Config entry updated - triggering immediate state refresh")
        self._last_known_title = entry.title
        self._last_known_data_name = entry.data.get("name")
        new_switch_entity = entry.data.get("switch_entity_id")
        if new_switch_entity != self._switch_entity_id:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Switch entity changed from '{self._switch_entity_id}' to '{new_switch_entity}'")
            await self.async_update_switch_entity(new_switch_entity)
        await self._handle_name_change()

    async def _delayed_start_accumulation(self):
        """Start accumulation with a short delay to ensure HA startup is complete."""
        await asyncio.sleep(0.5)
        if self._is_switch_on() and self._last_on_timestamp and not self._stop_event_received:
            _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Starting delayed accumulation after restart")
            await self._start_realtime_accumulation()

    async def _restore_active_timer(self):
        """Restore an active timer after restart."""
        now = dt_util.utcnow()
        _LOGGER.info(f"Simple Timer: [{self._entry_id}] Restoring an active timer state after restart.")

        last_state = await self.async_get_last_state()
        if last_state and last_state.state != "unavailable":
            offline_seconds = (now - last_state.last_updated).total_seconds()
            if offline_seconds > 0:
                rounded_offline_seconds = round(offline_seconds)
                _LOGGER.info(f"Simple Timer: [{self._entry_id}] Adding {rounded_offline_seconds}s of offline runtime.")
                self._state += rounded_offline_seconds
                self._watchdog_message = "Warning: Home assistant was offline during a running timer! Usage time may be unsynchronized."

        if self._timer_finishes_at and self._timer_finishes_at > now:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer is still active, resuming. Finishes at {self._timer_finishes_at}")
            self._timer_unsub = async_track_point_in_utc_time(
                self.hass, self._async_timer_finished, self._timer_finishes_at
            )
            await self._start_timer_update_task()
            async with self._storage_lock:
                try:
                    data = await self._store.async_load()
                    if data:
                        self._timer_duration = data.get("duration", self._timer_duration)
                except Exception as e:
                    _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not load timer data: {e}")
        else:
            _LOGGER.info(f"Simple Timer: [{self._entry_id}] Timer expired during restart. Cleaning up and turning off switch.")
            await self._cleanup_timer_state()
            if self._switch_entity_id:
                await self.hass.services.async_call(
                    "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
                )
        
        self.async_write_ha_state()

    async def _start_timer_update_task(self):
        """Start a task to update timer attributes every second."""
        if self._timer_update_task and not self._timer_update_task.done():
            return
        self._timer_update_task = self.hass.async_create_task(self._timer_update_loop())

    async def _stop_timer_update_task(self):
        """Stop the timer update task."""
        if self._timer_update_task and not self._timer_update_task.done():
            self._timer_update_task.cancel()
            try:
                await self._timer_update_task
            except asyncio.CancelledError:
                pass
            self._timer_update_task = None

    async def _timer_update_loop(self):
        """Update timer attributes every second while timer is active."""
        try:
            while self._timer_state == "active" and self._timer_finishes_at and not self._stop_event_received:
                if self._calculate_timer_remaining() <= 0:
                    break
                self.async_write_ha_state()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Timer update task cancelled")
            raise
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._entry_id}] Error in timer update loop: {e}")

    async def _async_setup_switch_listener(self) -> None:
        """Sets up the state change listener for the tracked switch."""
        if self._state_listener_disposer:
            self._state_listener_disposer()
        if self._switch_entity_id:
            _LOGGER.info("Simple Timer: [%s] Registering new state listener for switch: %s", self._entry_id, self._switch_entity_id)
            self._state_listener_disposer = async_track_state_change_event(
                self.hass, self._switch_entity_id, self._handle_switch_change_event
            )
        else:
            _LOGGER.warning("Simple Timer: [%s] Cannot set up switch listener: _switch_entity_id is None.", self._entry_id)

    async def async_update_switch_entity(self, switch_entity_id: str):
        """Service call handler to set which switch this sensor should monitor."""
        _LOGGER.info("Simple Timer: [%s] Service call to update tracked switch to: %s", self._entry_id, switch_entity_id)
        if self._switch_entity_id != switch_entity_id:
            self._switch_entity_id = switch_entity_id
            await self._async_setup_switch_listener()
        
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
        """Handle switch state change event using the new event API."""
        if self._stop_event_received:
            return
        self._handle_switch_change(event)

    @callback
    def _handle_switch_change(self, event: Event) -> None:
        """The core logic to calculate runtime based on the switch's state."""
        if self._stop_event_received:
            return

        from_state = event.data.get("old_state")
        to_state = event.data.get("new_state")
        now = dt_util.utcnow()

        if not to_state:
            _LOGGER.warning("Simple Timer: [%s] Missing new_state data in switch change event.", self._entry_id)
            return

        if to_state.state == STATE_ON and (not from_state or from_state.state != STATE_ON):
            if self._watchdog_message:
                self._watchdog_message = None
            self._last_on_timestamp = now
            self.hass.async_create_task(self._start_realtime_accumulation())

        elif to_state.state != STATE_ON and from_state and from_state.state == STATE_ON:
            self.hass.async_create_task(self._stop_realtime_accumulation())
            self._last_on_timestamp = None
            if self._timer_state == "active":
                self.hass.async_create_task(self._auto_cancel_timer_on_external_off())
        self.async_write_ha_state()

    async def _cleanup_timer_state(self):
        """Internal function to reset timer attributes and storage."""
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        await self._stop_timer_update_task()
        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0
        async with self._storage_lock:
            try:
                data = await self._store.async_load() or {}
                data.pop("finishes_at", None)
                data.pop("duration", None)
                await self._store.async_save(data)
            except Exception as e:
                _LOGGER.warning(f"Simple Timer: [{self._entry_id}] Could not clean timer data during cleanup: {e}")

    async def _auto_cancel_timer_on_external_off(self):
        """Auto-cancel timer when switch is turned off externally."""
        _LOGGER.info("Simple Timer: [%s] Auto-cancelling timer due to external switch off", self._entry_id)
        if self._watchdog_message:
            self._watchdog_message = None
        await self._cleanup_timer_state()
        self.async_write_ha_state()

    async def _start_realtime_accumulation(self) -> None:
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
        if self._accumulation_task and not self._accumulation_task.done():
            self._accumulation_task.cancel()
            try:
                await self._accumulation_task
            except asyncio.CancelledError:
                pass
            self._accumulation_task = None

    async def _async_accumulate_runtime(self) -> None:
        try:
            while not self._stop_event_received:
                if not self._switch_entity_id:
                    break
                current_switch_state = self.hass.states.get(self._switch_entity_id)
                if current_switch_state and current_switch_state.state == STATE_ON and self._last_on_timestamp:
                    self._state += 1.0
                    self.async_write_ha_state()
                    await asyncio.sleep(1)
                else:
                    break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _LOGGER.error("Simple Timer: [%s] Error in accumulation task: %s", self._entry_id, e)

    async def async_start_timer(self, duration_minutes: int) -> None:
        """Starts a countdown timer for the device and turns on the switch."""
        _LOGGER.info("Simple Timer: [%s] async_start_timer called with duration: %s minutes", self._entry_id, duration_minutes)
        if self._watchdog_message:
            self._watchdog_message = None
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        await self._stop_timer_update_task()
        self._timer_duration = duration_minutes
        self._timer_state = "active"
        self._timer_finishes_at = dt_util.utcnow() + timedelta(minutes=duration_minutes)
        async with self._storage_lock:
            data = await self._store.async_load() or {}
            data.update({
               "finishes_at": self._timer_finishes_at.isoformat(),
               "duration": duration_minutes
            })
            await self._store.async_save(data)
        await self._start_timer_update_task()
        await self._async_setup_switch_listener()
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        if not current_switch_state or current_switch_state.state != STATE_ON:
            await self.hass.services.async_call(
               "homeassistant", "turn_on", {"entity_id": self._switch_entity_id}, blocking=True
            )
            await asyncio.sleep(0.1)
        if not self._last_on_timestamp and self._is_switch_on():
            self._last_on_timestamp = dt_util.utcnow()
        if self._is_switch_on():
            await self._start_realtime_accumulation()
        if self._timer_finishes_at:
            self._timer_unsub = async_track_point_in_utc_time(
               self.hass, self._async_timer_finished, self._timer_finishes_at
            )
        self.async_write_ha_state()

    async def async_cancel_timer(self) -> None:
        """Cancels an active countdown timer."""
        _LOGGER.info("Simple Timer: [%s] async_cancel_timer called.", self._entry_id)
        if self._timer_state == "idle":
            return
        if self._watchdog_message:
            self._watchdog_message = None
        await self._cleanup_timer_state()
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        if current_switch_state and current_switch_state.state == STATE_ON:
            await self.hass.services.async_call(
               "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
            )
        else:
            await self._stop_realtime_accumulation()
        self.async_write_ha_state()

    @callback
    async def _async_timer_finished(self, now: dt_util.dt | None = None) -> None:
        """Callback executed when the scheduled timer finishes."""
        _LOGGER.info("Simple Timer: [%s] _async_timer_finished callback triggered.", self._entry_id)
        if self._timer_state != "active":
            return
        await self._cleanup_timer_state()
        if self._switch_entity_id:
            await self.hass.services.async_call(
               "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
            )
        self.async_write_ha_state()

    def _is_switch_on(self) -> bool:
        """Helper to check if the tracked switch is currently ON."""
        if self._switch_entity_id:
            switch_state = self.hass.states.get(self._switch_entity_id)
            return switch_state is not None and switch_state.state == STATE_ON
        return False

    @callback
    def _reset_at_scheduled_time(self, now) -> None:
        """Resets the daily runtime counter at the scheduled time."""
        self.hass.async_create_task(self._async_reset_at_scheduled_time())

    async def _async_reset_at_scheduled_time(self):
        """Async version of scheduled reset."""
        await self._perform_reset(is_catchup=False)
        self._next_reset_date = self._get_next_reset_datetime()
        await self._save_next_reset_date()
        _LOGGER.debug(f"Simple Timer: [{self._entry_id}] Next reset scheduled for: {self._next_reset_date}")

    @callback
    def _handle_ha_shutdown(self, event: Event) -> None:
        """Handle Home Assistant shutdown event to gracefully shutdown tasks."""
        _LOGGER.info("Simple Timer: [%s] Home Assistant shutdown event received, cancelling tasks immediately.", self._entry_id)
        self._stop_event_received = True
        if self._accumulation_task and not self._accumulation_task.done():
            self._accumulation_task.cancel()
        if self._timer_update_task and not self._timer_update_task.done():
            self._timer_update_task.cancel()

    async def async_will_remove_from_hass(self):
        """Called when entity will be removed from hass."""
        self._stop_event_received = True
        if hasattr(self._entry, 'remove_update_listener'):
            try:
                self._entry.remove_update_listener(self._handle_config_entry_update)
            except (ValueError, AttributeError):
                pass
        if (DOMAIN in self.hass.data and
            self._entry_id in self.hass.data[DOMAIN] and
            "sensor" in self.hass.data[DOMAIN][self._entry_id]):
            del self.hass.data[DOMAIN][self._entry_id]["sensor"]
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
