"""Simple Timer – runtime counter + countdown timer sensor."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
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

# Attributes for the sensor state
ATTR_TIMER_STATE = "timer_state"
ATTR_TIMER_FINISHES_AT = "timer_finishes_at"
ATTR_TIMER_DURATION = "timer_duration"
ATTR_TIMER_REMAINING = "timer_remaining"
ATTR_WATCHDOG_MESSAGE = "watchdog_message"
ATTR_SWITCH_ENTITY_ID = "switch_entity_id"
ATTR_LAST_ON_TIMESTAMP = "last_on_timestamp"
ATTR_INSTANCE_TITLE = "instance_title"

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

    STORAGE_VERSION = 1
    STORAGE_KEY_FORMAT = f"{DOMAIN}_{{}}"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._switch_entity_id = entry.data.get("switch_entity_id")

        # Store static parts that don't change
        entry_id_short = self._entry_id[:8]  # First 8 characters of entry_id
        self._entry_id_short = entry_id_short

        # Set properties that are truly static
        self._attr_unique_id = f"timer_runtime_{self._entry_id}"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_icon = "mdi:timer"

        # Track the last known entry state for change detection
        self._last_known_title = entry.title
        self._last_known_data_name = entry.data.get("name")

        _LOGGER.info(f"Simple Timer: Creating sensor for entry_id: {self._entry_id}")

        # State tracking
        self._state = 0.0
        self._last_on_timestamp = None
        self._accumulation_task = None
        self._state_listener_disposer = None
        self._stop_event_received = False

        # Timer functionality
        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0
        self._timer_unsub = None
        self._watchdog_message = None
        self._timer_update_task = None

        # Storage for timer persistence
        self._store = Store(hass, self.STORAGE_VERSION, self.STORAGE_KEY_FORMAT.format(self._entry_id))

        # Generate unique session ID
        import secrets
        self._session_id = secrets.token_urlsafe(20)

        _LOGGER.debug(f"Simple Timer: [{self._session_id}] Sensor initialized for {self._entry_id}")

    @property
    def instance_title(self) -> str:
        """Get the current instance title from the config entry (always fresh)."""
        # Try entry.data["name"] first (from options flow), then fall back to entry.title (from rename)
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

        return {
            ATTR_TIMER_STATE: self._timer_state,
            ATTR_TIMER_FINISHES_AT: self._timer_finishes_at.isoformat() if self._timer_finishes_at else None,
            ATTR_TIMER_DURATION: self._timer_duration,
            ATTR_TIMER_REMAINING: timer_remaining,
            ATTR_WATCHDOG_MESSAGE: self._watchdog_message,
            "entry_id": self._entry_id,
            ATTR_SWITCH_ENTITY_ID: self._switch_entity_id,
            ATTR_LAST_ON_TIMESTAMP: self._last_on_timestamp.isoformat() if self._last_on_timestamp else None,
            ATTR_INSTANCE_TITLE: self.instance_title,  # Always fresh from config entry
            "session_id": self._session_id,
        }

    async def _handle_name_change(self):
            """Handle detected name changes."""
            _LOGGER.info(f"Simple Timer: [{self._session_id}] Processing name change")

            # Force state update
            self.async_write_ha_state()

            # Update entity registry - FIXED: Correct import and access
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
                        _LOGGER.info(f"Simple Timer: [{self._session_id}] Updated entity registry with new name: '{self.name}'")
                    except Exception as e:
                        _LOGGER.warning(f"Simple Timer: [{self._session_id}] Could not update entity registry: {e}")

    def _check_and_handle_name_changes(self):
        """Check for name changes and handle them synchronously when possible."""
        current_title = self._entry.title
        current_data_name = self._entry.data.get("name")

        if (current_title != self._last_known_title or
            current_data_name != self._last_known_data_name):

            _LOGGER.info(f"Simple Timer: [{self._session_id}] Name change detected: title='{current_title}', data_name='{current_data_name}'")

            # Update tracking variables
            self._last_known_title = current_title
            self._last_known_data_name = current_data_name

            # Schedule immediate async update
            self.hass.async_create_task(self._handle_name_change())

    async def async_force_name_sync(self):
        """Force immediate name synchronization - callable via service."""
        _LOGGER.info(f"Simple Timer: [{self._session_id}] MANUAL name sync triggered via service")

        # Update tracking variables to force change detection
        self._last_known_title = None  # Force re-check
        self._last_known_data_name = None  # Force re-check

        # Immediate name change handling
        await self._handle_name_change()

        # Force multiple update mechanisms
        self.async_write_ha_state()

        # Additional aggressive entity registry update - FIXED: Correct import and access
        try:
            from homeassistant.helpers import entity_registry as er
            entity_registry = er.async_get(self.hass)
            if entity_registry:
                entity_entry = entity_registry.async_get(self.entity_id)
                if entity_entry:
                    new_name = self.name  # Get the current dynamic name
                    entity_registry.async_update_entity(
                        self.entity_id,
                        name=new_name
                    )
                    _LOGGER.info(f"Simple Timer: [{self._session_id}] MANUAL SYNC: Updated entity registry to: '{new_name}'")
        except Exception as e:
            _LOGGER.warning(f"Simple Timer: [{self._session_id}] Manual sync entity registry update failed: {e}")

        return True

    async def async_added_to_hass(self):
        """Called when entity is added to hass."""
        await super().async_added_to_hass()

        # Store this sensor instance so services can find it
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
        if self._entry_id not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][self._entry_id] = {}
        self.hass.data[DOMAIN][self._entry_id]["sensor"] = self

        # Listen for config entry updates (handles Configure button changes)
        self._entry.add_update_listener(self._handle_config_entry_update)

        # Listen for shutdown events
        self.hass.bus.async_listen_once("homeassistant_stop", self._handle_ha_shutdown)
        self.hass.bus.async_listen_once("homeassistant_final_write", self._handle_ha_shutdown)

        _LOGGER.debug(f"Simple Timer: [{self._session_id}] Sensor stored in hass.data for entry_id: {self._entry_id}")

        # Restore state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._state = float(last_state.state)
                attrs = last_state.attributes

                # Restore timer state
                self._timer_state = attrs.get(ATTR_TIMER_STATE, "idle")
                self._timer_duration = attrs.get(ATTR_TIMER_DURATION, 0)
                self._watchdog_message = attrs.get(ATTR_WATCHDOG_MESSAGE)

                # Restore timer finish time
                if attrs.get(ATTR_TIMER_FINISHES_AT):
                    self._timer_finishes_at = datetime.fromisoformat(attrs[ATTR_TIMER_FINISHES_AT])

                # Restore last on timestamp
                if attrs.get(ATTR_LAST_ON_TIMESTAMP):
                    self._last_on_timestamp = datetime.fromisoformat(attrs[ATTR_LAST_ON_TIMESTAMP])

                _LOGGER.debug(f"Simple Timer: [{self._session_id}] Restored state: {self._state}s, timer: {self._timer_state}")

            except (ValueError, TypeError) as e:
                _LOGGER.warning(f"Simple Timer: [{self._session_id}] Could not restore state: {e}")
                self._state = 0.0

        # Setup switch listener
        await self._async_setup_switch_listener()

        # Setup midnight reset
        async_track_time_change(self.hass, self._reset_at_midnight, hour=0, minute=0, second=0)

        # Restore timer if it was active - schedule without blocking
        if self._timer_state == "active" and self._timer_finishes_at:
            self.hass.async_create_task(self._restore_active_timer())

        # Start accumulation if switch is currently on
        if self._is_switch_on() and not self._last_on_timestamp:
            self._last_on_timestamp = dt_util.utcnow()
            self.hass.async_create_task(self._start_realtime_accumulation())
        elif self._is_switch_on() and self._last_on_timestamp:
            self.hass.async_create_task(self._delayed_start_accumulation())

    async def _handle_config_entry_update(self, hass: HomeAssistant, entry: ConfigEntry):
        """Handle updates to the config entry (including renames)."""
        _LOGGER.info(f"Simple Timer: [{self._session_id}] Config entry updated - triggering immediate state refresh")

        # Update tracked values
        self._last_known_title = entry.title
        self._last_known_data_name = entry.data.get("name")

        # Check if the switch entity has changed
        new_switch_entity = entry.data.get("switch_entity_id")
        if new_switch_entity != self._switch_entity_id:
            _LOGGER.info(f"Simple Timer: [{self._session_id}] Switch entity changed from '{self._switch_entity_id}' to '{new_switch_entity}'")
            await self.async_update_switch_entity(new_switch_entity)

        # Immediate name change handling
        await self._handle_name_change()

    def _schedule_accumulation_start(self):
        """Schedule accumulation start outside of startup context."""
        if not self._stop_event_received:
            # Use asyncio.create_task instead of hass.async_create_task to avoid HA tracking
            import asyncio
            self._accumulation_task = asyncio.create_task(self._async_accumulate_runtime())

    def _schedule_delayed_accumulation_start(self):
        """Schedule delayed accumulation start outside of startup context."""
        if not self._stop_event_received:
            import asyncio
            asyncio.create_task(self._delayed_start_accumulation())

    def _schedule_timer_restoration(self):
        """Schedule timer restoration outside of startup context."""
        if not self._stop_event_received:
            import asyncio
            asyncio.create_task(self._restore_active_timer())

    async def _delayed_start_accumulation(self):
        """Start accumulation with a short delay to ensure HA startup is complete."""
        await asyncio.sleep(0.5)  # Reduced from 2 seconds to 0.5 seconds

        if self._is_switch_on() and self._last_on_timestamp and not self._stop_event_received:
            _LOGGER.debug(f"Simple Timer: [{self._session_id}] Starting delayed accumulation after restart")
            await self._start_realtime_accumulation()

    async def _restore_active_timer(self):
        """Restore an active timer after restart."""
        now = dt_util.utcnow()

        if self._timer_finishes_at and self._timer_finishes_at > now:
            # Timer is still active, reschedule it
            self._timer_unsub = async_track_point_in_utc_time(
                self.hass, self._async_timer_finished, self._timer_finishes_at
            )
            _LOGGER.info(f"Simple Timer: [{self._session_id}] Restored active timer, finishing at {self._timer_finishes_at}")

            # Start timer update task for real-time countdown
            await self._start_timer_update_task()

            # Load persisted timer data
            try:
                data = await self._store.async_load()
                if data:
                    self._timer_duration = data.get("duration", self._timer_duration)
                    _LOGGER.debug(f"Simple Timer: [{self._session_id}] Loaded timer duration: {self._timer_duration}")
            except Exception as e:
                _LOGGER.warning(f"Simple Timer: [{self._session_id}] Could not load timer data: {e}")

        else:
            # ▼▼▼ SCENARIO 1 FIX APPLIED HERE ▼▼▼
            _LOGGER.info(f"Simple Timer: [{self._session_id}] Timer expired during restart. Turning off switch and cleaning up.")

            # Turn off the switch
            if self._switch_entity_id:
                _LOGGER.info(f"Simple Timer: [{self._session_id}] Turning off switch {self._switch_entity_id} as timer finished while HA was offline.")
                await self.hass.services.async_call(
                    "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
                )

            # Set the warning message
            self._watchdog_message = "Warning: Home Assistant was offline and interrupted the last timer!"

            # Clean up timer state
            self._timer_state = "idle"
            self._timer_finishes_at = None
            self._timer_duration = 0

            # Remove persisted timer data
            try:
                await self._store.async_remove()
            except Exception:
                pass

            # Update the state to show the warning message
            self.async_write_ha_state()
            # ▲▲▲ END OF FIX ▲▲▲

    async def _start_timer_update_task(self):
        """Start a task to update timer attributes every second."""
        if self._timer_update_task and not self._timer_update_task.done():
            return  # Task already running

        # Use asyncio.create_task to avoid HA tracking
        import asyncio
        self._timer_update_task = asyncio.create_task(self._timer_update_loop())

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
                remaining = self._calculate_timer_remaining()
                if remaining <= 0:
                    break

                # Update the state to trigger frontend refresh
                self.async_write_ha_state()

                # Use smaller sleep intervals to be more responsive to cancellation
                for _ in range(10):  # Sleep for 0.1s x 10 = 1s total
                    if self._stop_event_received:
                        return
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            _LOGGER.debug(f"Simple Timer: [{self._session_id}] Timer update task cancelled")
            raise
        except Exception as e:
            _LOGGER.error(f"Simple Timer: [{self._session_id}] Error in timer update loop: {e}")

    async def _async_setup_switch_listener(self) -> None:
        """Sets up the state change listener for the tracked switch."""
        # Dispose of any existing listener first to ensure a clean setup
        if self._state_listener_disposer:
            _LOGGER.debug("Simple Timer: [%s] Disposing existing switch state listener.", self._entry_id)
            self._state_listener_disposer()
            self._state_listener_disposer = None

        if self._switch_entity_id:
            _LOGGER.info("Simple Timer: [%s] Registering new state listener for switch: %s", self._entry_id, self._switch_entity_id)
            self._state_listener_disposer = async_track_state_change_event(
                self.hass, self._switch_entity_id, self._handle_switch_change_event
            )
            _LOGGER.debug("Simple Timer: [%s] New state listener registered. Disposer: %s", self._entry_id, self._state_listener_disposer)
        else:
            _LOGGER.warning("Simple Timer: [%s] Cannot set up switch listener: _switch_entity_id is None.", self._entry_id)

    async def async_update_switch_entity(self, switch_entity_id: str):
        """Service call handler to set which switch this sensor should monitor."""
        _LOGGER.info("Simple Timer: [%s] Service call to update tracked switch to: %s", self._entry_id, switch_entity_id)

        # Only update if the switch_entity_id has actually changed
        if self._switch_entity_id != switch_entity_id:
            self._switch_entity_id = switch_entity_id
            await self._async_setup_switch_listener() # Re-setup listener if ID changes
        else:
            _LOGGER.debug("Simple Timer: [%s] Switch entity %s is the same, no need to re-register listener.", self._entry_id, switch_entity_id)

        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        _LOGGER.debug("Simple Timer: [%s] Current switch state on async_update_switch_entity: %s (last_on_timestamp: %s)", self._entry_id, current_switch_state.state if current_switch_state else 'N/A', self._last_on_timestamp)
        if current_switch_state and current_switch_state.state == STATE_ON:
            if not self._last_on_timestamp:
                self._last_on_timestamp = dt_util.utcnow()
                _LOGGER.info("Simple Timer: [%s] Switch %s is ON after async_update_switch_entity, setting _last_on_timestamp to now.", self._entry_id, switch_entity_id)
            await self._start_realtime_accumulation()
        else:
            await self._stop_realtime_accumulation()

        self.async_write_ha_state()

    @callback
    def _handle_switch_change_event(self, event: Event) -> None:
        """Handle switch state change event using the new event API."""
        if self._stop_event_received:
            return  # Don't process events during shutdown

        entity_id = event.data.get("entity_id")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        _LOGGER.debug("Simple Timer: [%s] Event handler called for %s. Old: %s, New: %s",
                     self._entry_id, entity_id,
                     old_state.state if old_state else 'None',
                     new_state.state if new_state else 'None')

        if entity_id != self._switch_entity_id:
            _LOGGER.warning("Simple Timer: [%s] Mismatch: Listener for %s received event for %s. Ignoring.",
                           self._entry_id, self._switch_entity_id, entity_id)
            return

        # Call the core logic
        self._handle_switch_change(event)

    @callback
    def _handle_switch_change_with_states(self, entity_id: str, old_state: State | None, new_state: State | None):
        """Wrapper for backward compatibility - DEPRECATED."""
        if self._stop_event_received:
            return  # Don't process events during shutdown

        _LOGGER.debug("Simple Timer: [%s] Wrapper _handle_switch_change_with_states called for %s. Old: %s, New: %s", self._entry_id, entity_id, old_state.state if old_state else 'None', new_state.state if new_state else 'None')
        if entity_id != self._switch_entity_id:
            _LOGGER.warning("Simple Timer: [%s] Mismatch: Listener for %s received event for %s. Ignoring.", self._entry_id, self._switch_entity_id, entity_id)
            return

        # Create a mock Event object that _handle_switch_change expects
        mock_event = type('Event', (object,), {'data': {
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
        }})()
        self._handle_switch_change(mock_event)

    @callback
    def _handle_switch_change(self, event: Event) -> None:
        """The core logic to calculate runtime based on the switch's state."""
        if self._stop_event_received:
            return  # Don't process events during shutdown

        _LOGGER.info("Simple Timer: [%s] === _handle_switch_change CORE LOGIC CALLED === for %s", self._entry_id, self._switch_entity_id)
        _LOGGER.debug("Simple Timer: [%s] Full event data: %s", self._entry_id, event.data)

        from_state = event.data.get("old_state")
        to_state = event.data.get("new_state")
        now = dt_util.utcnow()

        _LOGGER.info(
            "Simple Timer: [%s] Switch %s state change. From: %s, To: %s at %s. Current _last_on_timestamp: %s, Timer state: %s",
            self._entry_id,
            self._switch_entity_id,
            from_state.state if from_state else "None",
            to_state.state if to_state else "None",
            now.isoformat(),
            self._last_on_timestamp,
            self._timer_state
        )

        if not to_state:
            _LOGGER.warning("Simple Timer: [%s] Missing new_state data in switch change event for %s. Cannot process.", self._entry_id, self._switch_entity_id)
            return

        if to_state.state == STATE_ON and (not from_state or from_state.state != STATE_ON):
            _LOGGER.info("Simple Timer: [%s] DETECTED ON TRANSITION for %s. Setting timestamp and starting accumulation.", self._entry_id, self._switch_entity_id)
            self._last_on_timestamp = now
            self.hass.async_create_task(self._start_realtime_accumulation())

        elif to_state.state != STATE_ON and from_state and from_state.state == STATE_ON:
            _LOGGER.info("Simple Timer: [%s] DETECTED OFF TRANSITION for %s. Stopping accumulation.", self._entry_id, self._switch_entity_id)
            self.hass.async_create_task(self._stop_realtime_accumulation())
            self._last_on_timestamp = None

            # 🔥 BUG FIX: Auto-cancel timer if switch turned off externally while timer is active
            if self._timer_state == "active":
                _LOGGER.info("Simple Timer: [%s] Switch turned OFF externally while timer was active. Auto-cancelling timer.", self._entry_id)
                self.hass.async_create_task(self._auto_cancel_timer_on_external_off())

        else:
            _LOGGER.debug("Simple Timer: [%s] State change for %s was not a clear ON/OFF transition. No action taken.", self._entry_id, self._switch_entity_id)

        self.async_write_ha_state()

    async def _auto_cancel_timer_on_external_off(self):
        """Auto-cancel timer when switch is turned off externally."""
        _LOGGER.info("Simple Timer: [%s] Auto-cancelling timer due to external switch off", self._entry_id)

        # Unsubscribe the scheduled timer callback
        if self._timer_unsub:
            _LOGGER.debug("Simple Timer: [%s] Unsubscribing timer listener on auto-cancel.", self._entry_id)
            self._timer_unsub()
            self._timer_unsub = None

        # Stop timer update task
        await self._stop_timer_update_task()

        # Clear timer state
        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0

        # Remove persisted timer data
        try:
            await self._store.async_remove()
            _LOGGER.debug("Simple Timer: [%s] Persisted timer data removed on auto-cancel.", self._entry_id)
        except Exception as e:
            _LOGGER.warning("Simple Timer: [%s] Could not remove persisted timer data on auto-cancel: %s", self._entry_id, e)

        # Update the state to reflect timer cancellation
        self.async_write_ha_state()

    async def _start_realtime_accumulation(self) -> None:
        if self._stop_event_received:
            return

        _LOGGER.debug("Simple Timer: [%s] Attempting to start accumulation task. Task status: %s", self._entry_id, self._accumulation_task.done() if self._accumulation_task else 'None')

        if self._accumulation_task and not self._accumulation_task.done():
            _LOGGER.debug("Simple Timer: [%s] Real-time accumulation task already running, not restarting.", self._entry_id)
            return

        if not self._last_on_timestamp:
            current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
            if current_switch_state and current_switch_state.state == STATE_ON:
                self._last_on_timestamp = dt_util.utcnow()
                _LOGGER.warning("Simple Timer: [%s] _last_on_timestamp was None but switch is ON. Setting now to start accumulation.", self._entry_id)
            else:
                _LOGGER.warning("Simple Timer: [%s] Cannot start accumulation. Switch not ON or _switch_entity_id missing. No timestamp set.", self._entry_id)
                return

        _LOGGER.info("Simple Timer: [%s] Creating new real-time accumulation task.", self._entry_id)
        # Use asyncio.create_task to avoid HA tracking
        import asyncio
        self._accumulation_task = asyncio.create_task(self._async_accumulate_runtime())

    async def _stop_realtime_accumulation(self) -> None:
        if self._accumulation_task:
            _LOGGER.info("Simple Timer: [%s] Stopping real-time accumulation task.", self._entry_id)
            self._accumulation_task.cancel()
            try:
                # Await the task directly after cancelling.
                # The task's own finally block will execute.
                await self._accumulation_task
                _LOGGER.debug("Simple Timer: [%s] Accumulation task finished gracefully.", self._entry_id)
            except asyncio.CancelledError:
                _LOGGER.debug("Simple Timer: [%s] Accumulation task was already cancelled or finished.", self._entry_id)
            except Exception as e:
                _LOGGER.error("Simple Timer: [%s] Error while waiting for accumulation task to stop: %s", self._entry_id, e)
            finally:
                self._accumulation_task = None
        else:
            _LOGGER.debug("Simple Timer: [%s] _stop_realtime_accumulation called but no task running.", self._entry_id)

    async def _async_accumulate_runtime(self) -> None:
        _LOGGER.debug("Simple Timer: [%s] _async_accumulate_runtime task started loop.", self._entry_id)
        try:
            while not self._stop_event_received:
                if not self._switch_entity_id:
                    _LOGGER.warning("Simple Timer: [%s] No switch entity ID in accumulation task loop. Exiting.", self._entry_id)
                    break

                current_switch_state = self.hass.states.get(self._switch_entity_id)

                if current_switch_state and current_switch_state.state == STATE_ON and self._last_on_timestamp:
                    self._state += 1.0
                    self.async_write_ha_state()
                    _LOGGER.debug("Simple Timer: [%s] Accumulated 1s. New state: %.0f. Written to HA.", self._entry_id, self._state)

                    # Use smaller sleep intervals to be more responsive to cancellation
                    for _ in range(10):  # Sleep for 0.1s x 10 = 1s total
                        if self._stop_event_received:
                            return
                        await asyncio.sleep(0.1)

                    # Check for cancellation after sleeping
                    if asyncio.current_task().cancelled():
                        _LOGGER.debug("Simple Timer: [%s] Accumulation task detected cancellation after sleep. Breaking loop.", self._entry_id)
                        break
                else:
                    _LOGGER.debug("Simple Timer: [%s] Accumulation condition not met (Switch not ON or timestamp missing). Exiting loop.", self._entry_id)
                    break

        except asyncio.CancelledError:
            _LOGGER.info("Simple Timer: [%s] Real-time accumulation task received cancellation signal. Exiting loop.", self._entry_id)
            raise
        except Exception as e:
            _LOGGER.error("Simple Timer: [%s] Error in accumulation task: %s", self._entry_id, e)
        finally:
            _LOGGER.debug("Simple Timer: [%s] _async_accumulate_runtime task finally block executed.", self._entry_id)

    async def async_start_timer(self, duration_minutes: int) -> None:
        """Starts a countdown timer for the device and turns on the switch."""
        _LOGGER.info("Simple Timer: [%s] async_start_timer called with duration: %s minutes", self._entry_id, duration_minutes)

        if self._watchdog_message:
            self._watchdog_message = None

        # Cancel any existing timer listener first
        if self._timer_unsub:
            _LOGGER.debug("Simple Timer: [%s] Unsubscribing existing timer listener.", self._entry_id)
            self._timer_unsub()
            self._timer_unsub = None

        # Stop any existing timer update task
        await self._stop_timer_update_task()

        self._timer_duration = duration_minutes
        self._timer_state = "active"
        self._timer_finishes_at = dt_util.utcnow() + timedelta(minutes=duration_minutes)

        await self._store.async_save(
            {"finishes_at": self._timer_finishes_at.isoformat(), "duration": duration_minutes}
        )

        # Start the timer update task for real-time countdown
        await self._start_timer_update_task()

        # Ensure the switch listener is set up
        await self._async_setup_switch_listener()

        # Turn on the switch if not already on
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        if not current_switch_state or current_switch_state.state != STATE_ON:
            _LOGGER.info("Simple Timer: [%s] Turning on switch %s for timer.", self._entry_id, self._switch_entity_id)
            await self.hass.services.async_call(
                "homeassistant", "turn_on", {"entity_id": self._switch_entity_id}, blocking=True
            )
            # Give HA a moment to process the switch turn_on service call,
            # which should trigger _handle_switch_change and start accumulation.
            await asyncio.sleep(0.1) # Short sleep to allow state propagation

        # Check if _last_on_timestamp is set after switch is turned on
        if not self._last_on_timestamp and self._is_switch_on():
            self._last_on_timestamp = dt_util.utcnow()
            _LOGGER.info("Simple Timer: [%s] Timer started and switch is ON, setting _last_on_timestamp.", self._entry_id)

        # Start accumulation if the switch is ON
        if self._is_switch_on():
            await self._start_realtime_accumulation()
        else:
            _LOGGER.warning("Simple Timer: [%s] Switch not ON after timer start service call, accumulation might not begin.", self._entry_id)

        # Schedule the _async_timer_finished callback using async_track_point_in_utc_time
        if self._timer_finishes_at:
            self._timer_unsub = async_track_point_in_utc_time(
                self.hass, self._async_timer_finished, self._timer_finishes_at
            )
            _LOGGER.debug("Simple Timer: [%s] Timer scheduled with async_track_point_in_utc_time to finish at %s", self._entry_id, self._timer_finishes_at.isoformat())
        else:
            _LOGGER.error("Simple Timer: [%s] Cannot schedule timer: _timer_finishes_at is None.", self._entry_id)

        # Update state immediately to reflect timer status
        self.async_write_ha_state()

    async def async_cancel_timer(self) -> None:
        """Cancels an active countdown timer."""
        _LOGGER.info("Simple Timer: [%s] async_cancel_timer called.", self._entry_id)
        if self._timer_state == "idle":
            _LOGGER.debug("Simple Timer: [%s] Timer already idle, no action needed on cancel.", self._entry_id)
            return

        # Unsubscribe the scheduled timer callback
        if self._timer_unsub:
            _LOGGER.debug("Simple Timer: [%s] Unsubscribing timer listener on cancel.", self._entry_id)
            self._timer_unsub()
            self._timer_unsub = None

        # Stop timer update task
        await self._stop_timer_update_task()

        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0

        try:
            await self._store.async_remove()
            _LOGGER.debug("Simple Timer: [%s] Persisted timer data removed on cancel.", self._entry_id)
        except Exception as e:
            _LOGGER.warning("Simple Timer: [%s] Could not remove persisted timer data on cancel: %s", self._entry_id, e)

        # Turn off the switch if it's currently on, as cancellation implies stopping heating.
        # This will trigger _handle_switch_change and stop accumulation.
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        if current_switch_state and current_switch_state.state == STATE_ON:
            _LOGGER.info("Simple Timer: [%s] Turning off switch %s on timer cancellation.", self._entry_id, self._switch_entity_id)
            await self.hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
            )
        else:
            # If switch is already off, just stop accumulation task if it's somehow running
            await self._stop_realtime_accumulation()

        self.async_write_ha_state()

    @callback
    async def _async_timer_finished(self, now: dt_util.dt | None = None) -> None:
        """Callback executed when the scheduled timer finishes.
        This method is designed to be idempotent.
        """
        # The 'now' argument is passed by async_track_point_in_utc_time, but we don't strictly need it.
        _LOGGER.info("Simple Timer: [%s] _async_timer_finished callback triggered.", self._entry_id)

        # Check if timer state is still active. This makes the handler idempotent.
        # If the timer was manually cancelled, _timer_state would be 'idle'.
        if self._timer_state != "active":
            _LOGGER.debug("Simple Timer: [%s] _async_timer_finished called but timer is not active. Ignoring.", self._entry_id)
            return

        if self._switch_entity_id:
            _LOGGER.info(
                "Simple Timer: [%s] Timer finished. Turning off switch %s.", self._entry_id, self._switch_entity_id
            )
            await self.hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": self._switch_entity_id}, blocking=True
            )
        else:
            _LOGGER.warning("Simple Timer: [%s] Timer finished, but no switch entity ID is set. Cannot turn off switch.", self._entry_id)

        # Call async_cancel_timer to clean up the timer state and storage.
        # This also ensures accumulation stops if switch turns off.
        await self.async_cancel_timer()

    def _is_switch_on(self) -> bool:
        """Helper to check if the tracked switch is currently ON."""
        if self._switch_entity_id:
            switch_state = self.hass.states.get(self._switch_entity_id)
            return switch_state is not None and switch_state.state == STATE_ON
        return False

    @callback
    def _reset_at_midnight(self, now) -> None:
        """Resets the daily runtime counter at midnight."""
        _LOGGER.info("Simple Timer: [%s] Daily runtime reset at midnight. Current state: %s", self._entry_id, self._state)

        self._state = 0.0
        self._last_on_timestamp = None

        if self._switch_entity_id:
            current_switch_state = self.hass.states.get(self._switch_entity_id)
            if current_switch_state and current_switch_state.state == STATE_ON:
                self._last_on_timestamp = dt_util.utcnow()
                self.hass.async_create_task(self._start_realtime_accumulation())
            else:
                self.hass.async_create_task(self._stop_realtime_accumulation())

        self.async_write_ha_state()

    @callback
    def _handle_ha_shutdown(self, event: Event) -> None:
        """Handle Home Assistant shutdown event to gracefully shutdown tasks."""
        _LOGGER.info("Simple Timer: [%s] Home Assistant shutdown event received, cancelling tasks immediately.", self._entry_id)
        self._stop_event_received = True

        # Cancel tasks immediately and aggressively
        if self._accumulation_task and not self._accumulation_task.done():
            _LOGGER.debug("Simple Timer: [%s] Cancelling accumulation task due to shutdown.", self._entry_id)
            self._accumulation_task.cancel()

        if self._timer_update_task and not self._timer_update_task.done():
            _LOGGER.debug("Simple Timer: [%s] Cancelling timer update task due to shutdown.", self._entry_id)
            self._timer_update_task.cancel()

    async def async_will_remove_from_hass(self):
        """Called when entity will be removed from hass."""
        self._stop_event_received = True

        # Remove update listener
        if hasattr(self._entry, 'remove_update_listener'):
            try:
                self._entry.remove_update_listener(self._handle_config_entry_update)
            except (ValueError, AttributeError):
                pass  # Listener might not be registered or already removed

        # Remove from hass.data
        if (DOMAIN in self.hass.data and
            self._entry_id in self.hass.data[DOMAIN] and
            "sensor" in self.hass.data[DOMAIN][self._entry_id]):
            del self.hass.data[DOMAIN][self._entry_id]["sensor"]
            _LOGGER.debug(f"Simple Timer: [{self._session_id}] Sensor removed from hass.data for entry_id: {self._entry_id}")

        # Cancel the accumulation task
        if self._accumulation_task and not self._accumulation_task.done():
            self._accumulation_task.cancel()
            try:
                await self._accumulation_task
            except asyncio.CancelledError:
                pass

        # Cancel timer update task
        await self._stop_timer_update_task()

        # Cancel timer if active
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None

        # Dispose state listener
        if self._state_listener_disposer:
            self._state_listener_disposer()
            self._state_listener_disposer = None

        await super().async_will_remove_from_hass()