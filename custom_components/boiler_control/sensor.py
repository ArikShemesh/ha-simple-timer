"""Boiler Control – runtime counter + countdown timer sensor."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    STATE_ON,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
# **FIX**: Import RestoreEntity, the correct class for restoring full entity state.
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_TIMER_STATE = "timer_state"
ATTR_TIMER_FINISHES_AT = "timer_finishes_at"
ATTR_TIMER_DURATION = "timer_duration"
ATTR_WATCHDOG_MESSAGE = "watchdog_message"
ATTR_SWITCH_ENTITY_ID = "switch_entity_id"
ATTR_LAST_ON_TIMESTAMP = "last_on_timestamp"


STORAGE_VERSION = 1
STORAGE_KEY_FORMAT = f"{DOMAIN}_{{}}"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Create a BoilerRuntimeSensor for this config entry."""
    async_add_entities(
        [BoilerRuntimeSensor(hass, entry)]
    )

# **FIX**: Inherit from both SensorEntity and RestoreEntity.
class BoilerRuntimeSensor(SensorEntity, RestoreEntity):
    """The sensor entity for Boiler Control."""
    _attr_has_entity_name = False
    _attr_name = "Daily Runtime"
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_daily_runtime"
        self._attr_suggested_object_id = f"{entry.title.lower().replace(' ', '_')}_daily_runtime"
        
        self._state: float = 0.0
        self._switch_entity_id: str | None = None
        self._last_on_timestamp: dt_util.dt | None = None
        self._timer_task: asyncio.Task | None = None
        self._timer_state = "idle"
        self._timer_finishes_at: dt_util.dt | None = None
        self._timer_duration = 0
        self._watchdog_message: str | None = None
        self._state_listener: callback | None = None
        self._midnight_listener: callback | None = None
        self._store = Store(
            hass, STORAGE_VERSION, STORAGE_KEY_FORMAT.format(self._entry_id)
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": entry.title,
            "manufacturer": "Boiler Control Project",
            "model": "Boiler Control System",
        }

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes for the card and for restoring state."""
        return {
            ATTR_TIMER_STATE: self._timer_state,
            ATTR_TIMER_FINISHES_AT: self._timer_finishes_at,
            ATTR_TIMER_DURATION: self._timer_duration,
            ATTR_WATCHDOG_MESSAGE: self._watchdog_message,
            "entry_id": self._entry_id,
            ATTR_SWITCH_ENTITY_ID: self._switch_entity_id,
            ATTR_LAST_ON_TIMESTAMP: self._last_on_timestamp.isoformat() if self._last_on_timestamp else None,
        }

    async def async_update_switch_entity(self, switch_entity_id: str):
        """Service call handler to set which switch this sensor should monitor."""
        _LOGGER.info("Boiler Control: Service call to update tracked switch to: %s", switch_entity_id)

        if self._switch_entity_id == switch_entity_id and self._state_listener is not None:
            return

        self._switch_entity_id = switch_entity_id
        
        if self._state_listener:
            self._state_listener()
            self._state_listener = None

        if switch_entity_id:
            self._state_listener = async_track_state_change_event(
                self.hass, switch_entity_id, self._handle_switch_change
            )
            current_switch_state = self.hass.states.get(switch_entity_id)
            if current_switch_state and current_switch_state.state == STATE_ON and not self._last_on_timestamp:
                _LOGGER.info("Boiler Control: Switch %s is already ON. Starting timer from now.", switch_entity_id)
                self._last_on_timestamp = dt_util.utcnow()
        
        self.async_write_ha_state()

    @callback
    def _handle_switch_change(self, event: Event) -> None:
        """The core logic to calculate runtime based on the switch's state."""
        from_state = event.data.get("old_state")
        to_state = event.data.get("new_state")

        _LOGGER.info(
            "Boiler Control: Handling switch change for %s. From: %s, To: %s",
            self._switch_entity_id,
            from_state.state if from_state else "None",
            to_state.state if to_state else "None",
        )

        if not from_state or not to_state:
            return

        if to_state.state == STATE_ON and from_state.state != STATE_ON:
            _LOGGER.info("Boiler Control: Switch turned ON. Recording timestamp.")
            self._last_on_timestamp = dt_util.utcnow()
        
        elif to_state.state != STATE_ON and from_state.state == STATE_ON:
            if self._last_on_timestamp:
                duration = (dt_util.utcnow() - self._last_on_timestamp).total_seconds()
                self._state += duration
                _LOGGER.info(
                    "Boiler Control: Switch %s turned OFF. Added %.2f seconds. New total: %.2f",
                    self._switch_entity_id,
                    duration,
                    self._state,
                )
            else:
                _LOGGER.warning(
                    "Boiler Control: Switch %s turned OFF, but no 'last_on_timestamp' was found.",
                    self._switch_entity_id
                )
            self._last_on_timestamp = None
        
        self.async_write_ha_state()

    async def async_start_timer(self, duration_minutes: int) -> None:
        """Start/restart a countdown."""
        _LOGGER.info("Boiler Control: async_start_timer called with duration: %s minutes", duration_minutes)
        if self._watchdog_message:
            self._watchdog_message = None
        
        if self._timer_task:
            self._timer_task.cancel()
        self._timer_duration = duration_minutes
        self._timer_state = "active"
        self._timer_finishes_at = dt_util.utcnow() + timedelta(minutes=duration_minutes)
        await self._store.async_save(
            {"finishes_at": self._timer_finishes_at.isoformat(), "duration": duration_minutes}
        )
        self.async_write_ha_state()
        self._timer_task = self.hass.async_create_task(
            self._async_timer_finished()
        )

    async def async_cancel_timer(self) -> None:
        """Stop the countdown."""
        if self._timer_state == "idle":
            return

        current = asyncio.current_task()
        if self._timer_task and self._timer_task is not current:
            self._timer_task.cancel()
        
        self._timer_task = None
        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0
        
        try:
            await self._store.async_remove()
        except Exception:
            _LOGGER.warning("Could not remove persisted timer data on cancel.")
        
        self.async_write_ha_state()

    async def _async_timer_finished(self) -> None:
        """When the timer completes, turn off the switch and clean up the state."""
        _LOGGER.info("Boiler Control: Timer task started. Checking finish time.")
        try:
            if self._timer_finishes_at:
                delay = (self._timer_finishes_at - dt_util.utcnow()).total_seconds()
                _LOGGER.info("Boiler Control: Calculated timer delay is %.2f seconds.", delay)
                if delay > 0:
                    await asyncio.sleep(delay)
            
            _LOGGER.info("Boiler Control: Timer sleep finished.")

            if self._switch_entity_id:
                _LOGGER.info(
                    "Boiler Control: Timer finished. Turning off switch %s.", self._switch_entity_id
                )
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": self._switch_entity_id}
                )
            else:
                _LOGGER.warning("Boiler Control: Timer finished, but no switch entity ID is set. Cannot turn off switch.")
            
            await self.async_cancel_timer()
        except asyncio.CancelledError:
            _LOGGER.info("Boiler Control: Timer task was cancelled manually.")
            await self.async_cancel_timer()
        except Exception as e:
            _LOGGER.error("Boiler Control: Unexpected error in _async_timer_finished: %s", e)
            await self.async_cancel_timer()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added and on Home Assistant startup."""
        await super().async_added_to_hass()
        self.hass.data[DOMAIN][self._entry_id]["sensor"] = self
        
        # **FIX**: Use the state object provided by RestoreEntity.
        last_state = await self.async_get_last_state()
        
        if last_state and last_state.state not in ("unknown", "unavailable"):
            _LOGGER.info("Boiler Control: Restoring state. Last state was: %s", last_state.state)
            
            if dt_util.as_local(last_state.last_updated).date() < dt_util.as_local(dt_util.utcnow()).date():
                _LOGGER.info("Boiler Control: Missed midnight reset detected. Resetting daily runtime.")
                self._state = 0.0
                self._last_on_timestamp = None
            else:
                try:
                    self._state = float(last_state.state)
                    last_on_iso = last_state.attributes.get(ATTR_LAST_ON_TIMESTAMP)
                    if last_on_iso:
                        self._last_on_timestamp = dt_util.parse_datetime(last_on_iso)
                except (ValueError, TypeError):
                    self._state = 0.0
                    self._last_on_timestamp = None

            self._switch_entity_id = last_state.attributes.get(ATTR_SWITCH_ENTITY_ID)
            self._watchdog_message = last_state.attributes.get(ATTR_WATCHDOG_MESSAGE)
        
        self._midnight_listener = async_track_time_change(
            self.hass, self._reset_at_midnight, hour=0, minute=0, second=0
        )
        
        if self._switch_entity_id:
            await self.async_update_switch_entity(self._switch_entity_id)

        if self._last_on_timestamp:
            current_switch_state = self.hass.states.get(self._switch_entity_id)
            if current_switch_state and current_switch_state.state == STATE_ON:
                offline_duration = (dt_util.utcnow() - self._last_on_timestamp).total_seconds()
                if offline_duration > 0:
                    self._state += offline_duration
                    _LOGGER.info(
                        "Boiler Control: Restored state was ON. Added %.2f seconds for offline duration.",
                        offline_duration,
                    )
                    self.async_write_ha_state()

        await self._restore_timer_on_startup()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is removed."""
        self.hass.data[DOMAIN].pop(self._entry_id, None)
        if self._state_listener:
            self._state_listener()
        if self._midnight_listener:
            self._midnight_listener()
        if self._timer_task:
            self._timer_task.cancel()

    async def _restore_timer_on_startup(self) -> None:
        """If a timer was active before restart, mark it as interrupted."""
        stored = await self._store.async_load()
        if stored:
            self._watchdog_message = (
                f"{dt_util.now().strftime('%d/%m/%Y %H:%M')} Warning: Boiler timer was "
                "interrupted by a Home Assistant restart. Manual intervention may be required."
            )
            self._timer_state = "idle"
            self._timer_finishes_at = None
            self._timer_duration = 0
            try:
                await self._store.async_remove()
            except Exception:
                _LOGGER.warning("Could not remove persisted timer data on cancel.")
            self.async_write_ha_state()

    @callback
    def _reset_at_midnight(self, now) -> None:
        """Reset the counter at midnight."""
        _LOGGER.info("Boiler daily runtime reset at midnight. Current state: %s", self._state)
        if self._switch_entity_id and self._last_on_timestamp:
             current_switch_state = self.hass.states.get(self._switch_entity_id)
             if current_switch_state and current_switch_state.state == STATE_ON:
                duration = (dt_util.utcnow() - self._last_on_timestamp).total_seconds()
                self._state += duration
                _LOGGER.info("Boiler Control: Adding final %.2f seconds before midnight reset.", duration)

        self._state = 0
        self._last_on_timestamp = None
        
        if self._switch_entity_id:
            current_switch_state = self.hass.states.get(self._switch_entity_id)
            if current_switch_state and current_switch_state.state == STATE_ON:
                self._last_on_timestamp = dt_util.utcnow()
        
        self.async_write_ha_state()
