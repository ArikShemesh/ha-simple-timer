"""Simple Timer – runtime counter + countdown timer sensor."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTime,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback, Context, Event, CoreState
from homeassistant.exceptions import ServiceValidationError
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
    async_track_time_change,
    async_track_point_in_utc_time,
    async_track_time_interval,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    WARNING_MSG_OFFLINE,
    SIGNAL_STATE_UPDATED,
    CONF_TURN_ON_OPTION,
    ATTR_TIMER_STATE,
    ATTR_TIMER_FINISHES_AT,
    ATTR_TIMER_DURATION,
    ATTR_TIMER_REMAINING,
    ATTR_WATCHDOG_MESSAGE,
    ATTR_SWITCH_ENTITY_ID,
    ATTR_DEVICE_ACTIVE,
    ATTR_POWER_TOGGLE_ROUTE,
    POWER_TOGGLE_DIRECT,
    POWER_TOGGLE_INTEGRATION,
    ATTR_STATUS_ENTITY_ID,
    ATTR_LAST_ON_TIMESTAMP,
    ATTR_INSTANCE_TITLE,
    ATTR_NEXT_RESET_DATE,
    ATTR_RESET_TIME,
    ATTR_TIMER_START_METHOD,
    ATTR_SCHEDULE_STATE,
    ATTR_SCHEDULED_START,
    ATTR_SCHEDULED_DURATION,
    ATTR_SCHEDULED_UNIT,
    ATTR_SCHEDULE_REPEAT,
    ATTR_SCHEDULE_DAYS,
    EVENT_TIMER_STARTED,
    EVENT_TIMER_EXTENDED,
    EVENT_TIMER_CANCELLED,
    EVENT_TIMER_FINISHED,
)
from .helpers import (
    DEFAULT_RESET_TIME,
    format_duration_exact,
    instance_logger,
    instance_title,
    device_info_for_switch,
    duration_to_seconds,
    format_duration_natural,
    next_reset_datetime,
    parse_reset_time,
)
from .domains import (
    descriptor_for,
    needs_turn_on_option,
    supports_generic_toggle,
    supports_off,
)
from .notify import Notifier
from .schedule import ScheduleManager
from .startup import async_wait_until_ready
from .switch_control import SwitchController
from .timer_store import TimerStore
from .status_sensor import TimerStatusSensor

_LOGGER = logging.getLogger(__name__)

# How often the accumulated runtime is published to the state machine while the
# switch is on. Runtime is still accumulated every second; this only controls
# how many rows the recorder writes. The card renders daily usage as HH:MM
# unless show_seconds is on, so at this cadence the displayed value is never
# stale by a visible amount. See _runtime_write_interval.
RUNTIME_WRITE_INTERVAL_SECONDS = 30

# How often an active timer republishes state. The card runs its own 500ms
# countdown off timer_finishes_at and does not need these writes; they exist to
# keep the timer_remaining attribute fresh for templates, automations and the
# stock entity card. Timer *firing* is a separate async_track_point_in_utc_time
# and does not depend on this interval.
TIMER_TICK_INTERVAL_SECONDS = 15

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Create the runtime and status sensors for this config entry."""
    async_add_entities([TimerRuntimeSensor(hass, entry), TimerStatusSensor(hass, entry)])

class TimerRuntimeSensor(SensorEntity, RestoreEntity):
    """The sensor entity for Simple Timer."""
    _attr_has_entity_name = False
    # Purely push-driven: state is written from switch events, timer callbacks
    # and the accumulator. There is no async_update, so polling would only
    # produce a redundant write every SCAN_INTERVAL.
    _attr_should_poll = False

    # icon, unit and state_class are set in __init__.

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._switch_entity_id = entry.data.get("switch_entity_id")
        self._entry_id_short = self._entry_id[:8]
        # Must exist before anything else in __init__ logs (_parse_reset_time does).
        self._log = instance_logger(_LOGGER, self._entry_id)

        self._attr_unique_id = f"timer_runtime_{self._entry_id}"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.TOTAL
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
        self._registry_listener_disposer = None
        self._stop_listener_disposer = None
        self._init_task = None
        self._stop_event_received = False

        self._timer_state = "idle"
        self._timer_finishes_at = None
        self._timer_duration = 0
        # Sticky by design: cleared only when a new timer starts or a restore
        # overwrites it. async_cancel_timer reads it *after* _cleanup_timer_state
        # to decide whether to turn the switch off, so cleanup must not reset it.
        self._timer_reverse_mode = False
        self._timer_start_moment = None  # Track exact timer start moment
        self._runtime_at_timer_start = 0  # Track runtime when timer started
        self._timer_unsub = None
        self._watchdog_message = None
        self._timer_update_task = None
        self._is_performing_reset = False
        self._timer_start_method = None
        self._last_accumulated_seconds = 0
        # Session-elapsed value at the last publish, in the same units as
        # _last_accumulated_seconds, so the publish cadence cannot drift.
        self._last_published_seconds = 0

        # Reset scheduling
        self._next_reset_date = None
        self._last_reset_was_catchup = False
        self._catchup_reset_info = None

        # Default timer config
        # Default timer config from entry data
        self._default_timer_duration = entry.data.get("default_timer_duration", 0.0)
        self._default_timer_unit = entry.data.get("default_timer_unit", "min")
        self._default_timer_enabled = self._default_timer_duration > 0
        self._default_timer_reverse_mode = False # Config flow currently doesn't support reverse mode default

        # Storage setup
        self._store = TimerStore(hass, self._entry_id, self._log)
        self._notifier = Notifier(hass, entry, self._log)

        self._build_collaborators()

    def _build_collaborators(self) -> None:
        """Create the two collaborators whose shutdown is one-way.

        Both `SwitchController.async_shutdown()` and
        `ScheduleManager.async_shutdown()` are sticky on purpose - a chain
        already sleeping through its backoff must not be able to wake up and
        command the device after the entity is gone (W2/S4). Sticky means the
        only way back is a new object, which a config-entry reload gives us for
        free. An entity_id rename does not: Home Assistant removes and re-adds
        the SAME entity object, so this is called again from
        async_added_to_hass to hand the revived entity working collaborators.
        """
        self._switch = SwitchController(
            self.hass,
            lambda: self._switch_entity_id,
            notify=self._send_notification,
            is_timer_active=lambda: self._timer_state == "active",
            # Read off the entry each time, not copied: the options flow
            # updates entry data in place without reloading the entry.
            get_turn_on_option=lambda: self._entry.data.get(CONF_TURN_ON_OPTION),
            log=self._log,
        )

        # Scheduled-start (future absolute clock time). Needs the store, and is
        # handed the sensor callbacks it reaches back through - so the
        # dependency runs one way, sensor -> schedule.
        self._schedule = ScheduleManager(
            self.hass,
            store=self._store,
            start_timer=self.async_start_timer,
            write_state=self.async_write_ha_state,
            fire_logbook=self._fire_logbook_event,
            log=self._log,
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Link this entity to the device of the switch it monitors."""
        return device_info_for_switch(self.hass, self._switch_entity_id,
                                      name=self.instance_title)

    @property
    def _monitored_descriptor(self):
        """Domain rules for the device this timer watches.

        A property rather than an attribute set in __init__, deliberately: the
        monitored entity is re-pointed at runtime, and the test fixtures build
        sensors through object.__new__ and set only what the path under test
        touches. Derived on read, so neither can go stale.
        """
        return descriptor_for(self._switch_entity_id)

    def _device_active(self) -> bool:
        """Is the monitored device running right now?

        "on" for a switch, any non-off hvac mode for climate. Published as an
        attribute so the card does not have to know the difference.
        """
        if not self._switch_entity_id:
            return False
        state = self.hass.states.get(self._switch_entity_id)
        return state is not None and self._monitored_descriptor.is_active(state.state)

    def _parse_reset_time(self, time_str: str) -> time:
        """Parse a configured reset time, warning and falling back if unusable."""
        parsed = parse_reset_time(time_str)
        if parsed is None:
            self._log.warning(f"Invalid reset time '{time_str}', using default 00:00:00")
            return DEFAULT_RESET_TIME
        return parsed

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
            
            self._log.info(f"Reset time updated from {old_reset_time} to {self._reset_time}")
            
            # Cancel existing reset tracker
            if self._reset_time_tracker:
                self._reset_time_tracker()
                self._reset_time_tracker = None
            
            # Reschedule reset with new time
            await self._setup_reset_scheduling({})
            
            # Update next reset date
            self._next_reset_date = next_reset_datetime(self._reset_time)
            await self._save_next_reset_date()
            
            self.async_write_ha_state()

    @property
    def instance_title(self) -> str:
        """Get the current instance title."""
        return instance_title(self._entry)

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

    def async_write_ha_state(self) -> None:
        """Write state, then notify the status sensor.

        Overridden rather than firing the signal at each of the ~30 write sites
        in this class. The signal fires often (the runtime accumulator writes
        once a second while a timer runs); the status sensor debounces by only
        writing when its derived state actually changes.
        """
        super().async_write_ha_state()
        async_dispatcher_send(self.hass, SIGNAL_STATE_UPDATED.format(self._entry_id))

    @property
    def timer_state(self) -> str:
        """Internal timer state: "idle" or "active"."""
        return self._timer_state

    @property
    def timer_reverse_mode(self) -> bool:
        """Whether the current (or most recent) timer is a delayed start.

        Sticky once set - see the note in __init__.
        """
        return self._timer_reverse_mode

    @property
    def has_armed_schedule(self) -> bool:
        """Whether a scheduled start is currently armed."""
        return self._schedule.is_armed

    @property
    def status_entity_id(self) -> str | None:
        """Entity id of this instance's status sensor, or None if not registered yet."""
        ent_reg = er.async_get(self.hass)
        return ent_reg.async_get_entity_id("sensor", DOMAIN, f"timer_status_{self._entry_id}")

    async def _fire_logbook_event(
        self,
        event_type: str,
        context: Context | None = None,
        **data: Any,
    ) -> None:
        """Fire a bus event that logbook.py renders as an Activity line.

        Anchored to the status sensor, since that is the entity users see in a
        device's Activity feed. No-ops until the status sensor is registered.

        The event carries `context`, and we additionally resolve the acting
        user's display name into the event data. HA surfaces context.user_id on
        state-change entries but not on custom-event entries, so the name has to
        travel in the payload for logbook.py to put it in the message.

        Callers with no user behind them (timer expiry, a schedule firing) pass
        no context, so no name is resolved and those lines stay unattributed.
        """
        status_entity_id = self.status_entity_id
        if not status_entity_id:
            return

        user_name = await self._resolve_user_name(context)

        event_data = {
            "entity_id": status_entity_id,
            "entry_id": self._entry_id,
            "name": self.instance_title,
            **data,
        }
        if user_name:
            event_data["user_name"] = user_name

        self.hass.bus.async_fire(event_type, event_data, context=context)

    async def _resolve_user_name(self, context: Context | None) -> str | None:
        """Return the display name of the user behind `context`, if any."""
        if not context or not context.user_id:
            return None

        try:
            user = await self.hass.auth.async_get_user(context.user_id)
        except Exception as e:
            self._log.debug(f"Could not resolve user: {e}")
            return None

        return user.name if user else None

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
            # Additive: the card used to compare the device state against "on"
            # itself, which is wrong for climate. Old bundles keep their own
            # fallback, so this must never be renamed or removed.
            ATTR_DEVICE_ACTIVE: self._device_active(),
            # Keeps the domain table the only place that knows domain names -
            # the card reads this instead of matching on the entity id, so a
            # new domain never needs a rebuilt bundle. Additive: bundles that
            # predate it keep their own hardcoded check.
            ATTR_POWER_TOGGLE_ROUTE: (
                POWER_TOGGLE_DIRECT if supports_generic_toggle(self._switch_entity_id)
                else POWER_TOGGLE_INTEGRATION
            ),
            # Lets the card open more-info on the status sensor without having
            # to scan for it. Safe to add here: the card's instance lookup keys
            # off entry_id + switch_entity_id, both of which stay on this entity.
            ATTR_STATUS_ENTITY_ID: self.status_entity_id,
            ATTR_LAST_ON_TIMESTAMP: self._last_on_timestamp.isoformat() if self._last_on_timestamp else None,
            ATTR_INSTANCE_TITLE: self.instance_title,
            ATTR_NEXT_RESET_DATE: self._next_reset_date.isoformat() if self._next_reset_date else None,
            ATTR_RESET_TIME: self._reset_time.strftime("%H:%M:%S"),  # Expose current reset time
            ATTR_TIMER_START_METHOD: self._timer_start_method,
            "show_seconds": show_seconds_setting,  # Expose show_seconds from config entry
            "reverse_mode": self._timer_reverse_mode,
            
            # Default timer attributes for frontend sync
            "default_timer_enabled": self._default_timer_enabled,
            "default_timer_duration": self._default_timer_duration,
            "default_timer_unit": self._default_timer_unit,
            "default_timer_reverse_mode": self._default_timer_reverse_mode,

            # Scheduled-start attributes for frontend sync
            ATTR_SCHEDULE_STATE: "armed" if self._schedule.is_armed else "idle",
            ATTR_SCHEDULED_START: self._schedule.fire_at.isoformat() if self._schedule.is_armed else None,
            ATTR_SCHEDULED_DURATION: self._schedule.duration,
            ATTR_SCHEDULED_UNIT: self._schedule.unit,
            ATTR_SCHEDULE_REPEAT: self._schedule.repeat,
            ATTR_SCHEDULE_DAYS: self._schedule.days,
        }

        if self._last_reset_was_catchup:
            attrs["last_reset_type"] = "catch-up"
            if self._catchup_reset_info:
                attrs["reset_info"] = self._catchup_reset_info
            self._last_reset_was_catchup = False

        return attrs

    async def _send_notification(self, message: str) -> None:
        """Send a notification to the instance's configured targets.

        Kept as a delegate because the `test_notification` service handler
        in __init__.py reaches for it on the sensor.
        """
        await self._notifier.async_send(message)

    async def _save_next_reset_date(self):
        """Save the next reset date to storage."""
        await self._store.async_save_next_reset_date(self._next_reset_date)

    async def _check_missed_reset(self):
        """Check if we missed a reset while HA was offline."""
        if not self._next_reset_date:
            return
        
        now = dt_util.now()
        
        if now >= self._next_reset_date:
            time_diff = now - self._next_reset_date
            days_missed = time_diff.days + (1 if time_diff.seconds > 0 else 0)
            
            self._log.warning(
                f"Detected missed reset! "
                f"Expected reset: {self._next_reset_date}, Current time: {now}, "
                f"Missed resets: {days_missed}"
            )
            
            await self._perform_reset(is_catchup=True)
            
            self._next_reset_date = next_reset_datetime(self._reset_time)
            await self._save_next_reset_date()
            
            self._last_reset_was_catchup = True
            self._catchup_reset_info = f"Reset performed on startup (missed {days_missed} reset(s))"

    async def _perform_reset(self, is_catchup=False):
        """Perform daily runtime reset."""
        self._is_performing_reset = True
        try:
            reset_type = "catch-up" if is_catchup else "scheduled"
            reset_time_str = self._reset_time.strftime("%H:%M:%S")
            self._log.info(
                f"Performing {reset_type} daily runtime reset at {reset_time_str}. "
                f"Current state: {self._state}s"
            )

            await self._stop_realtime_accumulation()

            if self._timer_state == "active":
                self._log.debug("Reset occurred during an active timer. Adjusting timer's base runtime.")
                self._runtime_at_timer_start = 0.0 - self._calculate_timer_elapsed_since_start()
                
                # PERSISTENCE FIX: Save the adjusted runtime_at_start to storage immediately.
                # Otherwise, if HA restarts, it will load the old (positive) runtime_at_start
                # and ignore this daily reset, leading to incorrect usage calculation.
                await self._store.async_save_runtime_at_start(self._runtime_at_timer_start)

            self._state = 0.0
            self._last_on_timestamp = None
            
            if self._switch_entity_id:
                current_switch_state = self.hass.states.get(self._switch_entity_id)
                if current_switch_state and self._monitored_descriptor.is_active(current_switch_state.state):
                    self._last_on_timestamp = dt_util.utcnow()
                    await self._start_realtime_accumulation()

            self.async_write_ha_state()
        finally:
            self._is_performing_reset = False

    async def _handle_name_change(self):
        """Handle detected name changes."""
        self._log.info("Processing name change")
        self.async_write_ha_state()

        from homeassistant.helpers import entity_registry as er
        entity_registry = er.async_get(self.hass)
        if entity_registry:
            entity_entry = entity_registry.async_get(self.entity_id)
            if entity_entry:
                try:
                    entity_registry.async_update_entity(self.entity_id, name=self.name)
                    self._log.info(f"Updated entity registry with new name: '{self.name}'")
                except Exception as e:
                    self._log.warning(f"Could not update entity registry: {e}")

    async def async_force_name_sync(self):
        """Force immediate name synchronization."""
        self._log.info("Manual name sync triggered")
        self._last_known_title = None
        self._last_known_data_name = None
        await self._handle_name_change()

    async def _start_timer_update_task(self):
        """Start timer update task."""
        if self._timer_update_task:
            return
            
        # Use standard HA timer helper instead of a custom loop.
        #
        # Do not remove this task. In reverse mode the switch is off so the
        # accumulator never runs, and this is the only thing refreshing the
        # timer_remaining attribute for templates, automations and the stock
        # entity card. The card itself does not need it - it interpolates the
        # countdown locally from timer_finishes_at.
        self._timer_update_task = async_track_time_interval(
            self.hass,
            self._async_timer_update_tick,
            timedelta(seconds=TIMER_TICK_INTERVAL_SECONDS),
        )

    async def _stop_timer_update_task(self):
        """Stop timer update task."""
        if self._timer_update_task:
            self._timer_update_task()  # Remove callback
            self._timer_update_task = None

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
        # Both subscriptions are indexed by entity id, so both have to move
        # when the monitored entity does - a stale registry one keeps reporting
        # renames of a device this instance no longer watches.
        if self._registry_listener_disposer:
            self._registry_listener_disposer()
            self._registry_listener_disposer = None

        if self._switch_entity_id:
            self._log.info(f"Setting up switch listener for: {self._switch_entity_id}")
            self._state_listener_disposer = async_track_state_change_event(
                self.hass, self._switch_entity_id, self._handle_switch_change_event
            )
            self._registry_listener_disposer = async_track_entity_registry_updated_event(
                self.hass, self._switch_entity_id,
                self._handle_monitored_entity_registry_update
            )
        else:
            self._log.warning("No switch entity configured")

    @callback
    def _handle_monitored_entity_registry_update(self, event: Event) -> None:
        """Follow the monitored entity when Home Assistant renames it.

        HA does not rewrite config entry data when an entity id changes, and it
        changes without being asked for - renaming a device offers to rename its
        entities, and the post-create "Name and assign" dialog just does it.
        Left alone the entry points at an id nothing answers to, and the only
        recovery is re-pointing by hand.

        `old_entity_id` is the whole test, and it is deliberately the ONLY one.
        It appears on exactly one thing: an `update` whose entity id changed.
        An `update` for an icon, a friendly name or an area does not carry it,
        so those cannot rewrite the entry and reload the instance every time
        somebody edits a label. Neither does a `remove`, whose reported id is
        the one that just stopped existing - the last thing worth persisting.

        An `action` check on top of this looked prudent and was dead code: the
        suite stayed green with it deleted, because nothing reaches the write
        without `old_entity_id` anyway. Two guards over one path is how a test
        here passes for the wrong reason, so there is one.

        The write goes to the entry, not to `_switch_entity_id`, because the
        entry is what `_wait_for_startup_completion` reads back. Its update
        listener then performs the re-point through machinery already tested.
        """
        data = event.data
        new_entity_id = data.get("entity_id")
        old_entity_id = data.get("old_entity_id")
        if not new_entity_id or not old_entity_id or new_entity_id == old_entity_id:
            return

        self._log.info(
            f"Monitored entity renamed {old_entity_id} -> {new_entity_id}, "
            f"updating the config entry"
        )
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, "switch_entity_id": new_entity_id},
        )

    async def async_update_switch_entity(self, switch_entity_id: str):
        """Update the monitored switch entity."""
        self._log.info(f"Updating switch entity to: {switch_entity_id}")

        # Refuse a device we would not know how to turn on, or could not turn
        # off again. The alternative is accepting it and failing at 2am when the
        # timer fires, with the user asleep and the boiler cold - or still hot.
        # Both refusals mirror the config flow's, which checks the same two
        # things before it will accept an entity at all.
        if switch_entity_id:
            new_state = self.hass.states.get(switch_entity_id)
            new_attrs = new_state.attributes if new_state else None
            if needs_turn_on_option(switch_entity_id,
                                    self._entry.data.get(CONF_TURN_ON_OPTION),
                                    new_attrs):
                raise ServiceValidationError(
                    f"Cannot monitor {switch_entity_id}: this device needs a "
                    f"turn-on mode, and none is configured for it. Change the "
                    f"device through the integration's options instead."
                )
            if not supports_off(switch_entity_id, new_attrs):
                raise ServiceValidationError(
                    f"Cannot monitor {switch_entity_id}: this device offers no "
                    f"way to turn it off, so a timer could never end it."
                )

        repointed = self._switch_entity_id != switch_entity_id
        if repointed:
            self._switch_entity_id = switch_entity_id
            await self._async_setup_switch_listener()

        # Persist it. The config entry is what _wait_for_startup_completion
        # reads back, so a re-point that only moved this attribute is undone by
        # the next restart - and an armed delayed start then fires against the
        # OLD device. Unprompted device activation is the failure this project
        # weights heaviest, so the two must not be allowed to disagree.
        #
        # Written only when it actually differs. That is what makes the other
        # caller - _handle_config_entry_update, which arrives BECAUSE the entry
        # already changed - a no-op here, instead of writing the entry from
        # inside the entry's own update listener.
        #
        # The turn-on option needs no companion write: the validation above
        # already proved the stored one fits this device.
        if self._entry.data.get("switch_entity_id") != switch_entity_id:
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, "switch_entity_id": switch_entity_id},
            )

        # Update accumulation based on current switch state
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        if current_switch_state and self._monitored_descriptor.is_active(current_switch_state.state):
            if not self._last_on_timestamp:
                self._last_on_timestamp = dt_util.utcnow()
            await self._start_realtime_accumulation()
        else:
            await self._stop_realtime_accumulation()

        self.async_write_ha_state()

        # Re-add both entities so their device_info is read again. Home
        # Assistant consumes device_info only when an entity is ADDED to the
        # registry, so without this the timer stays on whichever device it
        # landed on when the entry last loaded, and the re-point shows up only
        # after a restart. Nothing else reloads us - the __init__.py update
        # listener is a bare `pass`.
        #
        # Scheduled, never awaited: this also runs from inside the entry's own
        # update listener, and awaiting a reload there deadlocks. Last in the
        # method so the reload cannot tear the entity down mid-update.
        if repointed:
            self.hass.config_entries.async_schedule_reload(self._entry_id)

    @callback
    def _handle_switch_change_event(self, event: Event) -> None:
        """Handle switch state change events."""
        if self._stop_event_received:
            return
        self._handle_switch_change(event)

    async def _handle_config_entry_update(self, hass: HomeAssistant, entry: ConfigEntry):
        """Handle config entry updates including reset time changes."""
        self._log.info("Config entry updated")
        
        # 1. Title/Name
        last_title = getattr(self, "_last_known_title", None)
        if entry.title != last_title:
             self._last_known_title = entry.title
             await self._handle_name_change()

        # 2. Switch Entity
        new_switch_entity = entry.data.get("switch_entity_id")
        if new_switch_entity != self._switch_entity_id:
            self._log.info(f"Switch entity changed to: {new_switch_entity}")
            await self.async_update_switch_entity(new_switch_entity)
        
        # 3. Reset Time
        await self._update_reset_time()

        # 4. Default Timer Config
        await self._update_default_timer_config()

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

        # Device started running. For climate the edge is off/unavailable ->
        # any mode; cool -> heat is NOT an edge, so a user changing the mode
        # mid-timer does not re-seed the meter or auto-start a second timer.
        descriptor = self._monitored_descriptor
        if descriptor.is_active(to_state.state) and (
            not from_state or not descriptor.is_active(from_state.state)
        ):
            if self._watchdog_message:
                self._watchdog_message = None
            self._last_on_timestamp = now
            self.hass.async_create_task(self._start_realtime_accumulation())

            # Auto-start default timer if enabled and idle
            self._log.debug(f"Switch ON detected. Default timer enabled: {self._default_timer_enabled}, State: {self._timer_state}")
            if self._default_timer_enabled and self._timer_state == "idle" and self._default_timer_duration > 0:
                self._log.info(f"Auto-starting default timer ({self._default_timer_duration} {self._default_timer_unit}, reverse={self._default_timer_reverse_mode})")
                self.hass.async_create_task(
                    self.async_start_timer(self._default_timer_duration, self._default_timer_unit, reverse_mode=self._default_timer_reverse_mode)
                )

        # Device stopped running, or stopped answering
        elif not descriptor.is_active(to_state.state):
            # Only a positive off cancels a coupled timer. An entity that went
            # unavailable has told us nothing, and cancelling a running timer
            # on a dropped radio message is the failure this weights against.
            is_definitive_off = descriptor.is_definitive_off(to_state.state)

            if is_definitive_off:
                self.hass.async_create_task(self._stop_realtime_accumulation())
                self._last_on_timestamp = None

            # We exclude reverse_mode because the switch is supposed to be off during those.
            is_reverse_mode = self._timer_reverse_mode

            if (
                self._timer_state == "active"
                and not is_reverse_mode
                and is_definitive_off
            ):
                # COUPLED: Auto-cancel timer when switch turns off
                self._log.info("Switch turned off - cancelling timer (coupled)")
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
        
        await self._store.async_clear_timer()

    async def _auto_cancel_timer_on_external_off(self):
        """Auto-cancel timer when switch is turned off externally."""
        self._log.info("Auto-cancelling timer due to external switch off")
        
        if self._watchdog_message:
            self._watchdog_message = None
        
        await self._cleanup_timer_state()
        self.async_write_ha_state()
        
    async def _start_realtime_accumulation(self) -> None:
        """Start real-time accumulation task."""
        if self._stop_event_received:
            return
        
        # If already running, don't start again
        if self._accumulation_task:
            return
            
        current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
        
        # Only start if the device is running (or we are in a permissive state)
        if current_switch_state and self._monitored_descriptor.is_active(current_switch_state.state):
            if not self._last_on_timestamp:
                self._last_on_timestamp = dt_util.utcnow()
        else:
             return
             
        # Initialize session state
        # We perform accumulation by adding the elapsed time of CURRENT session to the base state
        # The base state is the state at the beginning of THIS accumulation session
        #
        # Seed from the existing session start rather than 0. On a fresh session
        # _last_on_timestamp was just set to now, so this is 0 and behaviour is
        # unchanged. After a restart it is the PRE-restart start time restored by
        # _restore_basic_state, and self._state already contains that elapsed
        # time - zeroing here would make the next tick add the whole session a
        # second time. The active-timer restore path guards against this
        # separately by resetting _last_on_timestamp to now.
        #
        # Known limitation: a manual-on session (switch on, no timer) forfeits
        # the time HA was actually down, because the restored self._state only
        # goes up to the last publish and nothing records where this on-period
        # started. Counting it exactly would mean persisting the session counter
        # and clearing it at every site that begins a new on-period; losing at
        # most one restart's worth of runtime is the accepted trade. Timer-driven
        # sessions are unaffected - _restore_active_timer recomputes them from
        # _timer_start_moment and adds the offline gap explicitly.
        self._last_accumulated_seconds = round(
            (dt_util.utcnow() - self._last_on_timestamp).total_seconds()
        )
        self._last_published_seconds = self._last_accumulated_seconds

        # Use standard HA timer helper instead of a custom loop
        # Accumulate once per second; how often that gets *published* to the
        # state machine is decided in the tick, see _runtime_write_interval.
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

    def _runtime_write_interval(self) -> int:
        """Seconds between published runtime writes while the switch is on.

        The card renders daily usage as HH:MM unless show_seconds is on, so in
        the default configuration per-second writes are invisible and only cost
        recorder rows. Users who turned show_seconds on see a per-second display
        and keep the per-second cadence.

        Read live from the config entry rather than cached, so toggling the
        option in the options flow takes effect without a reload.
        """
        if self._entry.data.get("show_seconds", False):
            return 1
        return RUNTIME_WRITE_INTERVAL_SECONDS

    @callback
    def _async_update_accumulated_runtime(self, now, final_update=False) -> None:
        """Periodically update the accumulated runtime."""
        if self._stop_event_received or not self._switch_entity_id:
            if not final_update:
                self.hass.async_create_task(self._stop_realtime_accumulation())
            return

        current_switch_state = self.hass.states.get(self._switch_entity_id)
        
        # Accumulate ONLY if the device is running. An entity that stopped
        # answering keeps accumulating, unchanged: it was on a moment ago and
        # nothing has said otherwise.
        should_accumulate = (
            current_switch_state
            and self._last_on_timestamp
            and (
                self._monitored_descriptor.is_active(current_switch_state.state)
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

            # self._state is now exact. Publishing it is what costs a recorder
            # row, so that is decided separately - every other write site (timer
            # start/finish, reset, switch change) still publishes the exact
            # current value on demand.
            #
            # Deliberately outside the `diff > 0` branch: a flush can land
            # mid-second, where diff is 0 but seconds accumulated since the last
            # publish are still pending. Gating on diff would silently drop them.
            unpublished = self._last_accumulated_seconds - self._last_published_seconds
            if unpublished > 0 and (
                final_update or unpublished >= self._runtime_write_interval()
            ):
                self._last_published_seconds = self._last_accumulated_seconds
                self.async_write_ha_state()
        else:
            if not final_update:
                self.hass.async_create_task(self._stop_realtime_accumulation())

    async def async_start_timer(self, duration: float, unit: str = "min", reverse_mode: bool = False, start_method: str = "button", context: Context | None = None) -> None:
        """Start a countdown timer with synchronized accumulation.

        `context` is the originating service call's context. Passing it through to
        the switch turn-on lets the logbook attribute the change to the user who
        pressed start, instead of "Generic turn on".
        """
        # The last barrier before the device is commanded. ScheduleManager's
        # own latch only stops an _async_fired that has not begun; one already
        # suspended inside this call resumes after removal and would otherwise
        # command the switch and persist a timer on a dead sensor (S4).
        if self._stop_event_received:
            self._log.info("Ignoring timer start - entity is shutting down")
            return

        # Convert duration to minutes for internal storage
        duration_minutes = duration_to_seconds(duration, unit) / 60.0

        self._log.info(f"Starting {'reverse' if reverse_mode else 'normal'} timer for {duration} {unit}")
        
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
            # REVERSE MODE: decoupled. A delayed start says only "turn it ON at
            # time T" - the device may well already be running, and daily usage
            # is a meter of device RUNTIME, not of timer state. Stopping the
            # meter here lost that runtime outright, because completion then
            # opens a fresh session from now (R1). Only stop when the device is
            # genuinely off, where there is nothing to count.
            #
            # Order matters: _stop_realtime_accumulation's final flush is gated
            # on _last_on_timestamp, so clearing it first skipped the flush.
            if not self._switch.is_on():
                await self._stop_realtime_accumulation()
                self._last_on_timestamp = None
        else:
            # NORMAL MODE: Convenience turn ON, but don't wait for it
            current_switch_state = self.hass.states.get(self._switch_entity_id) if self._switch_entity_id else None
            if not current_switch_state or not self._monitored_descriptor.is_active(current_switch_state.state):
                await self._switch.async_command("on", blocking=False, context=context)
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
        if not reverse_mode and self._switch.is_on() and not self._last_on_timestamp:
            self._last_on_timestamp = timer_start_moment
        
        # Save timer state to storage
        await self._store.async_save_timer(
            finishes_at=self._timer_finishes_at,
            duration=duration_minutes,
            timer_start=timer_start_moment,
            runtime_at_start=self._runtime_at_timer_start,
            reverse_mode=reverse_mode,
        )
        
        # Start timer tasks
        await self._start_timer_update_task()
        await self._async_setup_switch_listener()
        
        # Start accumulation only in normal mode when switch is ON
        if not reverse_mode and self._switch.is_on():
            await self._start_realtime_accumulation()
        
        # Set up timer completion callback
        if self._timer_finishes_at:
            self._timer_unsub = async_track_point_in_utc_time(
               self.hass, self._async_timer_finished, self._timer_finishes_at
            )
        
        # Send notification
        formatted_duration = format_duration_exact(duration_minutes * 60.0)
        mode_text = "Delayed timer started for" if reverse_mode else "Timer was started for"
        notification_msg = f"{mode_text} {formatted_duration}"
        await self._send_notification(notification_msg)

        await self._fire_logbook_event(
            EVENT_TIMER_STARTED,
            context=context,
            duration=format_duration_exact(duration_minutes * 60.0),
            reverse_mode=reverse_mode,
        )

        self.async_write_ha_state()

    async def async_add_timer(self, duration: float, unit: str = "min", context: Context | None = None) -> None:
        """Extend a currently running timer by adding duration.

        `context` is the originating service call's context, so the logbook
        attributes the extension to the user who requested it.
        """
        if self._timer_state != "active":
            self._log.warning("Cannot add time: Timer is not active")
            return

        # Convert duration to minutes
        duration_minutes = duration_to_seconds(duration, unit) / 60.0

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
                 self._log.warning("Cannot extend: Timer is at maximum limit")
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

            self._log.info(f"Extension capped from {old_duration_minutes} to {duration_minutes} min to stay within limit")

        # Calculate new duration and finish time
        self._timer_duration += duration_minutes
        self._timer_finishes_at += timedelta(minutes=duration_minutes)
        
        # Update storage
        await self._store.async_extend_timer(
            finishes_at=self._timer_finishes_at,
            duration=self._timer_duration,
        )
            
        # Update timer completion callback
        if self._timer_unsub:
            self._timer_unsub()
            
        self._timer_unsub = async_track_point_in_utc_time(
           self.hass, self._async_timer_finished, self._timer_finishes_at
        )
        
        # Send notification
        remaining_seconds = max(0, int((self._timer_finishes_at - dt_util.utcnow()).total_seconds()))
        formatted_rest = format_duration_exact(remaining_seconds)
        formatted_added = format_duration_exact(duration_minutes * 60.0)
        
        notification_msg = f"Timer extended by {formatted_added}. New remaining: {formatted_rest}"
        await self._send_notification(notification_msg)

        await self._fire_logbook_event(
            EVENT_TIMER_EXTENDED,
            context=context,
            added=format_duration_exact(duration_minutes * 60.0),
            remaining=format_duration_exact(remaining_seconds),
        )

        self.async_write_ha_state()

    async def async_cancel_timer(self, turn_off_entity: bool = True, context: Context | None = None) -> None:
        """Cancel an active timer.

        `context` is the originating service call's context, so the logbook
        attributes the switch turn-off to the user who cancelled.
        """
        self._log.info("Cancelling timer")
        
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
        notification_entity, show_seconds = await self._notifier.async_config()
        formatted_time = format_duration_natural(current_usage, show_seconds)
        
        # Clean up timer
        await self._cleanup_timer_state()
        
        # Handle switch state based on timer mode
        reverse_mode = self._timer_reverse_mode
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
                    # async_ensure cannot raise, but the try stays: it also
                    # covers _stop_realtime_accumulation, and dropping it here
                    # would silently widen what escapes async_cancel_timer.
                    try:
                        await self._switch.async_ensure(
                            "off", "Timer cancellation turn-off",
                            force=True, context=context,
                        )
                        await self._stop_realtime_accumulation()
                    except Exception as e:
                        self._log.warning(f"Could not turn off switch: {e}")
            else:
                 # DECOUPLED: Do nothing
                 pass
        
        # Send notification. Says cancelled, not finished: the timer was cut
        # short, and a user hearing "finished" would think it ran its course.
        notification_msg = f"Timer cancelled – daily usage {formatted_time}"
        await self._send_notification(notification_msg)

        await self._fire_logbook_event(
            EVENT_TIMER_CANCELLED,
            context=context,
            usage=format_duration_exact(current_usage),
        )

        self.async_write_ha_state()
        
    @callback
    async def _async_timer_finished(self, now: dt_util.dt | None = None) -> None:
        """Handle timer completion with runtime compensation."""
        self._log.info("Timer finished")
        
        # Guard against zombie execution during shutdown
        if self._stop_event_received or self.hass.state == CoreState.stopping:
            self._log.info("Timer finished during shutdown - ignoring to preserve state")
            return
        
        if self._timer_state != "active":
            return
            
        reverse_mode = self._timer_reverse_mode
        
        if reverse_mode:
            # REVERSE MODE: Turn switch ON when timer finishes
            await self._cleanup_timer_state()

            if self._switch_entity_id:
                # force: command unconditionally, as the bare async_command
                # this replaced did. Going through async_ensure means a switch
                # integration that is down warns the user instead of raising
                # past the notification, logbook and state write - the timer
                # state and storage are already cleared by this point, so an
                # exception here strands the device off with no timer (W3).
                await self._switch.async_ensure(
                    "on", "Reverse timer completion turn-on",
                    blocking=True, force=True,
                )

                # Open a new session only if one is not already running. When
                # the device was off through the countdown this starts usage
                # from now, which is the point of reverse mode. When it was ON
                # the meter is still going, and moving the timestamp under a
                # live session is destructive: _start_realtime_accumulation
                # returns early on an existing task, so _last_accumulated_seconds
                # keeps the OLD baseline while the timestamp jumps to now. The
                # tick then computes a negative diff and the meter freezes for
                # as long as the device had already been on (R3).
                if not self._accumulation_task:
                    self._last_on_timestamp = dt_util.utcnow()
                await self._start_realtime_accumulation()

            # Only claim the device turned on if it did. This went out
            # unconditionally - outside the switch guard entirely - so a failed
            # command, or no switch configured at all, still reported success.
            if self._switch.is_on():
                await self._send_notification(
                    "Delayed start timer completed - device turned ON"
                )
            else:
                await self._send_notification(
                    "Delayed start timer completed - device did not turn on"
                )

            # No context: expiry is the integration acting on its own, not
            # the user who started the timer. Leaving it unattributed keeps
            # the logbook from claiming they acted hours after the fact.
            await self._fire_logbook_event(EVENT_TIMER_FINISHED, reverse_mode=True)
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
                 self._log.info(f"Corrected final usage to {self._state}s (Target: {expected_usage}s)")

            self.async_write_ha_state()

            await asyncio.sleep(0.1)

            current_usage = self._state
            notification_entity, show_seconds = await self._notifier.async_config()
            formatted_time = format_duration_natural(current_usage, show_seconds)

            await self._cleanup_timer_state()

            if self._switch_entity_id:
                await self._switch.async_ensure("off", "Timer completion turn-off", blocking=True)

            notification_msg = f"Timer was turned off - daily usage {formatted_time}"
            await self._send_notification(notification_msg)

            # Unattributed on purpose — see the reverse-mode branch above.
            await self._fire_logbook_event(
                EVENT_TIMER_FINISHED,
                reverse_mode=False,
                usage=format_duration_exact(current_usage),
            )

        self.async_write_ha_state()

    async def async_manual_power_toggle(self, action: str, context: Context | None = None) -> None:
        """Handle manual power toggle from frontend.

        `context` is the originating service call's context, so the logbook
        attributes the switch change to the user who pressed the power button.
        """
        if action == "turn_on":
            await self._switch.async_ensure("on", "Manual turn-on", context=context)
            await self._send_notification("Timer started")
        elif action == "turn_off":
            current_usage = self._state
            notification_entity, show_seconds = await self._notifier.async_config()
            formatted_time = format_duration_natural(current_usage, show_seconds)
            
            await self._switch.async_ensure("off", "Manual turn-off", context=context)
            notification_msg = f"Timer was turned off - daily usage {formatted_time}"
            await self._send_notification(notification_msg)

    @callback
    def _reset_at_scheduled_time(self, now) -> None:
        """Handle scheduled daily reset."""
        self.hass.async_create_task(self._async_reset_at_scheduled_time())

    async def _async_reset_at_scheduled_time(self):
        """Perform scheduled daily reset."""
        await self._perform_reset(is_catchup=False)
        self._next_reset_date = next_reset_datetime(self._reset_time)
        await self._save_next_reset_date()

    async def _handle_ha_shutdown(self, event):
        """Handle Home Assistant shutdown."""
        # Publish the un-written tail before the stop flag goes up: runtime is
        # only published every _runtime_write_interval() seconds, and the
        # accumulator's opening guard returns early once _stop_event_received
        # is set. Best effort - whether restore_state snapshots this depends on
        # EVENT_HOMEASSISTANT_STOP listener ordering - but it at least leaves
        # hass.states holding the correct value at shutdown.
        if self._accumulation_task and self._last_on_timestamp:
            self._async_update_accumulated_runtime(dt_util.utcnow(), final_update=True)

        self._stop_event_received = True
        self._log.info("Home Assistant shutdown - cancelling tasks")
        
        # Cancel all tasks
        if self._accumulation_task:
            self._accumulation_task()
            self._accumulation_task = None
            
        if self._timer_update_task:
            self._timer_update_task()
            self._timer_update_task = None
            
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None

        # The same barrier removal raises. Setting _stop_event_received is not
        # enough on its own: HA moves tasks that predate this event aside and
        # does not cancel them until its final shutdown stage, so a retry chain
        # sleeping through its 2/5/10/20s backoff can still wake and command
        # the device - and a turn-on retry never consults the timer-active
        # predicate. The schedule and the init task have the same window.
        if self._init_task and not self._init_task.done():
            self._init_task.cancel()
        self._init_task = None

        self._schedule.async_shutdown()
        self._switch.async_shutdown()

    async def async_will_remove_from_hass(self):
        """Handle entity removal."""
        self._stop_event_received = True

        # Cancel before anything else: the flag alone does not stop a task
        # parked in the startup wait. CancelledError is a BaseException, so
        # _wait_for_startup_completion's `except Exception` fallback will not
        # swallow it and re-run initialization.
        if self._init_task and not self._init_task.done():
            self._init_task.cancel()
        self._init_task = None

        if self._stop_listener_disposer:
            self._stop_listener_disposer()
            self._stop_listener_disposer = None

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

        # Drop the pending schedule callback, keeping its stored payload so
        # the schedule survives to be restored.
        self._schedule.async_shutdown()

        # Retry chains are detached; without this they outlive the entity and
        # can still command the device (W2).
        self._switch.async_shutdown()

        # Clean up domain data
        if (DOMAIN in self.hass.data and
            self._entry_id in self.hass.data[DOMAIN] and
            "sensor" in self.hass.data[DOMAIN][self._entry_id]):
            del self.hass.data[DOMAIN][self._entry_id]["sensor"]
        
        # Cancel tasks
        if self._accumulation_task:
            self._accumulation_task()
            self._accumulation_task = None
        
        await self._stop_timer_update_task()
        
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        
        if self._state_listener_disposer:
            self._state_listener_disposer()
            self._state_listener_disposer = None
        if self._registry_listener_disposer:
            self._registry_listener_disposer()
            self._registry_listener_disposer = None

        self.async_write_ha_state()
        await super().async_will_remove_from_hass()

        try:
            from homeassistant.helpers import entity_registry as er
            entity_registry = er.async_get(self.hass)
            if entity_registry:
                entity_entry = entity_registry.async_get(self.entity_id)
                if entity_entry:
                    new_name = self.name
                    entity_registry.async_update_entity(self.entity_id, name=new_name)
                    self._log.info(f"Manual sync: Updated entity registry to: '{new_name}'")
        except Exception as e:
            self._log.warning(f"Manual sync entity registry update failed: {e}")

        return True

    async def _update_default_timer_config(self):
        """Update default timer configuration from config entry."""
        self._default_timer_duration = self._entry.data.get("default_timer_duration", 0.0)
        self._default_timer_unit = self._entry.data.get("default_timer_unit", "min")
        self._default_timer_enabled = self._default_timer_duration > 0
        
        self.async_write_ha_state()
        self._log.info(f"Updated default timer config: {self._default_timer_enabled}, {self._default_timer_duration} {self._default_timer_unit}")

    async def async_added_to_hass(self):
        """Called when entity is added to hass - startup-safe initialization."""
        # Being added while shut down means this object was REMOVED and is now
        # coming back: Home Assistant handles an entity_id change - including
        # the one it performs when a device is renamed, which is what its
        # post-create "Name and assign" dialog does - by removing and re-adding
        # the same entity object.
        #
        # Everything below assumes a live entity, and the barriers raised on
        # removal do not lower themselves: _stop_event_received gates
        # _complete_initialization and async_start_timer, and both collaborators
        # latch shut permanently. Left as-is the revived entity registers itself
        # in hass.data, so every service call resolves to it, and then quietly
        # does nothing - no switch listener, no daily reset, no timer starts.
        if self._stop_event_received:
            self._log.info("Entity re-added after removal - resetting shutdown state")
            self._stop_event_received = False
            self._build_collaborators()

        self._log.info("Entity added to hass - startup safe mode")


        # Register sensor in domain data for service calls
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
        if self._entry_id not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][self._entry_id] = {}
        self.hass.data[DOMAIN][self._entry_id]["sensor"] = self
        
        # Restore basic state immediately to prevent history gaps
        await self._restore_basic_state()
        
        # Register shutdown handler.
        # Keep the disposer: dropping it leaves the bus holding a reference to
        # every removed instance until HA stops, and re-pointing the monitored
        # device reloads the entry (S4).
        self._stop_listener_disposer = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, self._handle_ha_shutdown
        )

        # Defer complex initialization until after startup.
        # Retained so removal can cancel it. Fire-and-forget let this resume
        # after the entity was gone and restore a timer against a dead sensor.
        self._init_task = asyncio.create_task(self._wait_for_startup_completion())

    async def _restore_basic_state(self):
        """Restore basic state values immediately to prevent history gaps."""
        try:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state != "unavailable":
                try:
                    restored_value = float(last_state.state)
                    self._state = restored_value
                    self._log.info(f"Restored state value: {restored_value}s")
                    
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
                        self._log.info(f"Restored reverse mode: {self._timer_reverse_mode}")
                    
                    # Restore runtime_at_timer_start from storage if timer was active
                    if self._timer_state == "active":
                        storage_data = await self._store.async_read()
                        if "runtime_at_start" in storage_data:
                            self._runtime_at_timer_start = storage_data["runtime_at_start"]
                            self._log.info(f"Restored runtime_at_timer_start: {self._runtime_at_timer_start}s")

                        # Also restore reverse mode from storage if available (takes precedence)
                        if "reverse_mode" in storage_data:
                            self._timer_reverse_mode = storage_data["reverse_mode"]
                            self._log.info(f"Restored reverse mode from storage: {self._timer_reverse_mode}")
                        
                except (ValueError, TypeError) as e:
                    self._log.warning(f"Could not restore state: {e}")
                    self._state = 0.0
            else:
                self._state = 0.0
                
        except Exception as e:
            self._log.error(f"Error during basic state restoration: {e}")
            self._state = 0.0

    async def _wait_for_startup_completion(self):
        """Wait for HA startup or essential dependencies with defensive checks."""
        try:
            self._log.info("Waiting for HA startup or dependencies...")

            # Setup switch entity ID from config early for checks
            self._switch_entity_id = getattr(self._entry, 'data', {}).get('switch_entity_id')

            await async_wait_until_ready(self.hass, self._switch_entity_id, self._log)

            await self._complete_initialization()
            
        except Exception as e:
            self._log.error(f"Error during startup wait: {e}")
            # Always try to initialize even if startup wait fails
            try:
                await self._complete_initialization()
            except Exception as init_error:
                self._log.error(f"Error during fallback initialization: {init_error}")

    async def _complete_initialization(self):
        """Complete full initialization after HA startup."""
        try:
            if self._stop_event_received:
                self._log.info("Skipping initialization - entity is being removed")
                return

            self._log.info("Completing initialization...")

            # Load storage data
            storage_data = await self._load_storage_data()
            
            # Restore default timer config (LEGACY STORAGE MIGRATION ONLY)
            if "default_timer" in storage_data:
                 # We only log this, we DO NOT restore it because Config Entry is now source of truth
                 dt_config = storage_data["default_timer"]
                 self._log.info(f"Found legacy default timer config in storage (ignored in favor of config entry): {dt_config}")
            
            # Initialize reset scheduling with configurable reset time
            await self._setup_reset_scheduling(storage_data)
            
            # Set up listeners and handlers
            await self._setup_listeners_and_handlers()
            
            # Check for any timer that needs restoration (active OR expired)
            if storage_data.get("finishes_at"):
                self._log.info("Found timer data in storage - checking if restoration needed")
                try:
                    stored_finish_time = datetime.fromisoformat(storage_data["finishes_at"])
                    now = dt_util.utcnow()
                    remaining_time = (stored_finish_time - now).total_seconds()
                    reverse_mode = storage_data.get("reverse_mode", False)
                    
                    self._log.info(f"Timer check - remaining: {remaining_time}s, reverse: {reverse_mode}")
                    
                    if remaining_time <= 0:
                        # Timer expired while offline - handle based on mode
                        self._log.info("Expired timer detected - forcing restoration")
                        
                        # Temporarily set timer state as active to trigger restoration
                        self._timer_state = "active"
                        self._timer_finishes_at = stored_finish_time
                        self._timer_reverse_mode = reverse_mode
                        
                        await self._handle_active_timer_restoration(storage_data)
                    elif self._timer_state == "active" and self._timer_finishes_at:
                        # Regular active timer restoration
                        await self._handle_active_timer_restoration(storage_data)
                    else:
                        self._log.info("No active timer restoration needed")
                except Exception as e:
                    self._log.error(f"Error during timer restoration check: {e}")
            else:
                self._log.info("No timer data in storage")

            # Restore any armed scheduled-start
            await self._schedule.async_restore(storage_data)

            # Start accumulation if needed
            await self._start_accumulation_if_needed()

            # Final state write
            self.async_write_ha_state()
            self._log.info("Initialization completed successfully")
            
        except Exception as e:
            self._log.error(f"Error during initialization: {e}")

    async def _load_storage_data(self) -> dict:
        """Load storage data with migration support."""
        return await self._store.async_load()

    async def _setup_reset_scheduling(self, storage_data: dict):
        """Set up daily reset scheduling with configurable reset time."""
        # Initialize next reset date
        self._next_reset_date = next_reset_datetime(self._reset_time)
        
        # Restore from storage if available
        if storage_data.get("next_reset_date"):
            try:
                self._next_reset_date = datetime.fromisoformat(storage_data["next_reset_date"])
            except (ValueError, TypeError) as e:
                self._log.warning(f"Could not parse stored reset date: {e}")
                self._next_reset_date = next_reset_datetime(self._reset_time)

        if not self._next_reset_date:
            self._next_reset_date = next_reset_datetime(self._reset_time)
            await self._save_next_reset_date()

        # Check for missed resets only if we have historical data
        if storage_data.get("next_reset_date"):
            await self._check_missed_reset()

        # Set up scheduled reset with configurable time
        reset_time_str = self._reset_time.strftime("%H:%M:%S")
        self._log.info(f"Scheduling daily reset at {reset_time_str}")
        
        self._reset_time_tracker = async_track_time_change(
            self.hass, self._reset_at_scheduled_time, 
            hour=self._reset_time.hour, 
            minute=self._reset_time.minute, 
            second=self._reset_time.second
        )

    # ------------------------------------------------------------------
    # Scheduled-start - delegated to ScheduleManager. Both entry points
    # stay on the sensor because __init__.py's service handlers call them.
    # ------------------------------------------------------------------

    async def async_schedule_timer(self, start_time: time, duration: float,
                                   unit: str = "min", repeat: bool = False,
                                   days: list[int] | None = None,
                                   context: Context | None = None) -> None:
        """Arm a scheduled start: at start_time run a bounded timer."""
        await self._schedule.async_arm(start_time, duration, unit, repeat, days, context)

    async def async_cancel_schedule(self, context: Context | None = None) -> None:
        """Cancel an armed scheduled start."""
        await self._schedule.async_cancel(context)

    async def _setup_listeners_and_handlers(self):
        """Set up event listeners and handlers."""
        await self._async_setup_switch_listener()
        self._entry.add_update_listener(self._handle_config_entry_update)

    async def _handle_active_timer_restoration(self, storage_data: dict):
        """Handle restoration of active timers with stored timer start time."""
        self._log.info("Starting timer restoration")
        
        # Restore timer start moment if available
        if storage_data.get("timer_start"):
            try:
                self._timer_start_moment = datetime.fromisoformat(storage_data["timer_start"])
                self._log.info(f"Restored timer_start_moment: {self._timer_start_moment}")
            except (ValueError, TypeError):
                self._timer_start_moment = None
                self._log.warning("Failed to restore timer_start_moment")

        # Restore total duration from storage if available (for extended timers)
        if storage_data.get("duration"):
            self._timer_duration = storage_data["duration"]
            self._log.info(f"Restored duration from storage: {self._timer_duration}")
        
        # Restore reverse mode from storage
        reverse_mode = storage_data.get("reverse_mode", False)
        self._timer_reverse_mode = reverse_mode
        self._log.info(f"Restored reverse_mode from storage: {reverse_mode}")
        
        now = dt_util.utcnow()
        remaining_time = (self._timer_finishes_at - now).total_seconds()
        self._log.info(f"Remaining time: {remaining_time} seconds")
        
        if remaining_time <= 0:
            # Timer expired while offline - handle based on mode
            self._log.info(f"Timer expired during offline period ({'REVERSE' if reverse_mode else 'NORMAL'} mode)")
            
            if reverse_mode:
                await self._handle_expired_reverse_timer()
            else:
                await self._handle_expired_timer()
        else:
            # Timer still active
            self._log.info(f"Timer still active with {int(remaining_time)} seconds remaining")
            await self._restore_active_timer(now)
        
        self._log.info("Timer restoration completed")

    async def _handle_expired_timer(self):
        """Handle timer that expired while HA was offline."""
        await asyncio.sleep(2)  # Safety delay
        
        # Load timer data from storage including reverse mode
        reverse_mode = False
        data = await self._store.async_read()
        if "runtime_at_start" in data:
            self._runtime_at_timer_start = data["runtime_at_start"]
            self._log.info(f"Restored runtime_at_start for expired timer: {self._runtime_at_timer_start}s")
        if "reverse_mode" in data:
            reverse_mode = data["reverse_mode"]
            self._timer_reverse_mode = reverse_mode
            self._log.info(f"Restored reverse mode for expired timer: {reverse_mode}")
        
        # Handle runtime calculation based on timer mode
        if reverse_mode:
            # For reverse mode: timer was counting down, device should now turn ON
            # Runtime should start from when timer finishes (now), not include countdown period
            self._log.info("Reverse mode timer expired - device will turn ON now")
            # Don't add the timer duration to runtime since device was OFF during countdown
        else:
            # For normal mode: device was ON during timer, add full duration to runtime
            # Since timer expired offline, we assume it completed successfully.
            if self._timer_duration > 0 and hasattr(self, '_runtime_at_timer_start'):
                expected_runtime = self._timer_duration * 60  # Whole seconds
                # Use round() for more accurate integer seconds
                self._state = self._runtime_at_timer_start + round(expected_runtime)
                self._log.info(f"Set runtime for expired normal timer: {self._state}s (start: {self._runtime_at_timer_start}s + duration: {expected_runtime}s)")
        
        # Get usage for notification BEFORE cleaning up (as cleanup might affect state access?)
        # Actually _state is safe.
        current_usage = self._state
        notification_entity, show_seconds = await self._notifier.async_config()
        formatted_time = format_duration_natural(current_usage, show_seconds)
        
        # FIX: Clear last_on_timestamp BEFORE cleanup to prevent final accumulation update from adding offline time
        self._last_on_timestamp = None

        # Clean up timer state FIRST to ensure we are in a clean idle state
        await self._cleanup_timer_state()
        
        # Add watchdog message AFTER cleanup so it persists
        self._watchdog_message = WARNING_MSG_OFFLINE
        self.async_write_ha_state() # Ensure message is written to state
        
        # Handle switch state based on timer mode
        if reverse_mode:
            # For reverse mode: timer finished, turn switch ON and start accumulation
            if self._switch_entity_id:
                try:
                    # Use robust retry logic
                    await self._switch.async_ensure_with_retries("on", "Expired reverse timer turn-on")
                    
                    # Start accumulation since device is now ON (or will be soon)
                    self._last_on_timestamp = dt_util.utcnow()
                    await self._start_realtime_accumulation()
                    
                except Exception as e:
                    self._log.warning(f"Could not turn on switch: {e}")
            
            # Send notification
            await asyncio.sleep(1)
            await self._send_notification(f"Delayed start timer completed - device turned ON")
        else:
            # For normal mode: timer finished, turn switch OFF
            if self._switch_entity_id:
                try:
                    # Use robust retry logic
                    await self._switch.async_ensure_with_retries("off", "Expired timer turn-off", force=True)
                except Exception as e:
                    self._log.warning(f"Could not turn off switch: {e}")
            
            # Send notification
            await asyncio.sleep(1)
            notification_msg = f"Timer was turned off - daily usage {formatted_time}"
            await self._send_notification(notification_msg)

    async def _handle_expired_reverse_timer(self):
        """Handle reverse mode timer that expired while HA was offline."""
        self._log.info("Handling expired reverse timer")
        
        try:
            # Add watchdog message before cleanup
            self._watchdog_message = WARNING_MSG_OFFLINE
            
            # Turn switch ON first (delayed start completed)
            if self._switch_entity_id:
                # TWO attempts, spanning 8s, on purpose. This path has no retry
                # chain behind it - the sibling _handle_expired_timer uses
                # async_ensure_with_retries, this one does not - so the command
                # here plus the forced re-command inside async_ensure are the
                # entire budget for an unattended restart turn-on against an
                # integration that may still be coming up. Collapsing the pair
                # into one forced ensure cut it to one command and 6s.
                #
                # Swallowed rather than re-raised (W3): the second attempt is
                # the recovery path, so a failed first must not skip it, and
                # _cleanup_timer_state below must run either way. The previous
                # version re-raised past cleanup, leaving the timer 'active'
                # with storage un-cleared for the next restart to re-read.
                try:
                    await self._switch.async_command("on", blocking=False)
                except Exception as e:
                    self._log.warning(f"First expired-restore turn-on failed: {e}")

                await asyncio.sleep(2)

                await self._switch.async_ensure(
                    "on", "Expired reverse timer completion turn-on",
                    blocking=False, force=True,
                )

                # Set timestamp and start accumulation BEFORE cleanup
                self._last_on_timestamp = dt_util.utcnow()

            else:
                self._log.error("No switch entity configured!")
            
            # Clean up timer state AFTER switch is turned on
            await self._cleanup_timer_state()
            
            # Start accumulation after cleanup
            if self._switch_entity_id and self._last_on_timestamp:
                await self._start_realtime_accumulation()
            else:
                self._log.error(f"Cannot start accumulation - switch_entity: {self._switch_entity_id}, last_on: {self._last_on_timestamp}")
            
            if self._switch.is_on():
                await self._send_notification(
                    "Delayed start timer completed - device turned ON"
                )
            else:
                await self._send_notification(
                    "Delayed start timer completed - device did not turn on"
                )

            self.async_write_ha_state()
            
            self._log.info("Expired reverse timer handling completed successfully")
            
        except Exception as e:
            self._log.error(f"Error handling expired reverse timer: {e}")
            import traceback
            self._log.error(f"Error traceback: {traceback.format_exc()}")

    async def _restore_active_timer(self, now: datetime):
        """Restore an active timer after restart."""
        await asyncio.sleep(1)  # Safety delay
        
        # Load timer data from storage including runtime_at_start
        data = await self._store.async_read()
        self._timer_duration = data.get("duration", self._timer_duration)
        if data.get("timer_start"):
            # Guarded: a malformed stored value must not escape here. This runs
            # before the completion callback is armed, so an exception would
            # leave the timer active with nothing scheduled to finish it.
            try:
                self._timer_start_moment = datetime.fromisoformat(data["timer_start"])
            except (ValueError, TypeError):
                self._timer_start_moment = None
                self._log.warning("Failed to restore timer_start_moment")
        if "runtime_at_start" in data:
            self._runtime_at_timer_start = data["runtime_at_start"]
            self._log.info(f"Restored runtime_at_start from storage: {self._runtime_at_timer_start}s")
        # Ensure reverse mode is restored from storage
        if "reverse_mode" in data:
            self._timer_reverse_mode = data["reverse_mode"]
            self._log.info(f"Restored reverse mode from storage: {self._timer_reverse_mode}")
        
        # Add offline time and set watchdog message
        last_state = await self.async_get_last_state()
        if last_state and last_state.state != "unavailable":
            offline_seconds = (now - last_state.last_updated).total_seconds()
            if offline_seconds > 0:
                self._watchdog_message = WARNING_MSG_OFFLINE
                
                # For reverse mode, we don't add offline time since device was OFF
                reverse_mode = self._timer_reverse_mode
                if not reverse_mode:
                    # For normal timers, recalculate total usage from start time if available
                    # This is more accurate than adding offline time to potentially stale state
                    if self._runtime_at_timer_start is not None and self._timer_start_moment:
                         elapsed = (now - self._timer_start_moment).total_seconds()
                         self._state = self._runtime_at_timer_start + int(elapsed)
                         self._log.info(f"Recalculated usage from start time: {self._state}s")
                    else:
                        # Fallback to adding offline time if we lack start data
                        self._log.info(f"Adjusting for offline gap of {int(offline_seconds)}s")
                        self._state += int(offline_seconds)
                    
                    # CRITICAL: We MUST reset _last_on_timestamp to NOW.
                    # Why? Because self._state now includes everything up to NOW.
                    # If we leave _last_on_timestamp at T0, the accumulation loop will calculate (NOW - T0)
                    # and add it to self._state, which would double-count the initial period.
                    self._last_on_timestamp = now
                else:
                    self._log.info("Reverse mode timer - not adding offline time during countdown")
        
        # Restore timer tracking
        self._timer_unsub = async_track_point_in_utc_time(
            self.hass, self._async_timer_finished, self._timer_finishes_at
        )
        await self._start_timer_update_task()
        
        # Normal mode stays coupled: the device is supposed to be running for
        # the timer's whole duration, so a restart re-asserts that.
        #
        # Reverse mode does NOT. It used to ensure("off") here, which switched
        # the device off on every restart during a countdown - the same
        # force-off _start_accumulation_if_needed used to do, from the other
        # direction. Decoupled means the countdown makes no claim about the
        # device until it fires (R2).
        if not self._timer_reverse_mode:
            await self._switch.async_ensure("on", "Active timer state verification on restart", blocking=True)

    async def _start_accumulation_if_needed(self):
        """Start accumulation if switch is on.

        Reverse mode gets no special case. It used to command the switch OFF
        here ("Ensuring switch stays OFF during reverse timer countdown") and
        then return without metering - so arming a delayed start over a running
        device and restarting HA switched the device off and stopped counting
        its runtime. Reverse mode is decoupled: whatever the device is doing
        during a countdown is the user's business, and runtime is runtime (R2).
        """
        if self._switch.is_on() and not self._last_on_timestamp:
            self._last_on_timestamp = dt_util.utcnow()
            await self._start_realtime_accumulation()
        elif self._switch.is_on() and self._last_on_timestamp:
            await self._delayed_start_accumulation()

    async def _delayed_start_accumulation(self):
        """Start accumulation with a delay."""
        await asyncio.sleep(0.5)
        if self._switch.is_on() and self._last_on_timestamp and not self._stop_event_received:
            await self._start_realtime_accumulation()
        
    def _calculate_timer_elapsed_since_start(self) -> int:
        """Calculate elapsed time in seconds since the timer started."""
        if self._timer_state == "active" and self._timer_start_moment:
            now = dt_util.utcnow()
            elapsed = (now - self._timer_start_moment).total_seconds()
            return max(0, round(elapsed))
        return 0
        
    async def async_reset_daily_usage(self) -> None:
        """Manually reset daily usage to zero."""
        self._log.info("Manual daily usage reset requested")
        
        # Get current usage for notification
        current_usage = self._state
        notification_entity, show_seconds = await self._notifier.async_config()
        formatted_time = format_duration_natural(current_usage, show_seconds)
        formatted_zero = format_duration_natural(0, show_seconds)
        
        # Stop any ongoing accumulation
        await self._stop_realtime_accumulation()
        
        # If timer is active, adjust the runtime_at_timer_start to maintain timer accuracy
        if self._timer_state == "active":
            # Set runtime_at_timer_start to negative elapsed time so final calculation remains correct
            if self._timer_start_moment:
                elapsed_seconds = (dt_util.utcnow() - self._timer_start_moment).total_seconds()
                self._runtime_at_timer_start = -elapsed_seconds
                self._log.debug(f"Adjusted runtime_at_timer_start for active timer: {self._runtime_at_timer_start}s")
        else:
            self._runtime_at_timer_start = 0
        
        # Reset the state
        old_state = self._state
        self._state = 0.0
        self._last_on_timestamp = None
        
        # If the device is currently running, restart accumulation from zero
        if self._switch_entity_id:
            current_switch_state = self.hass.states.get(self._switch_entity_id)
            if current_switch_state and self._monitored_descriptor.is_active(current_switch_state.state):
                self._last_on_timestamp = dt_util.utcnow()
                await self._start_realtime_accumulation()
        
        # Update state immediately
        self.async_write_ha_state()
        
        # Send notification
        notification_msg = f"Daily usage reset from {formatted_time} to {formatted_zero}"
        await self._send_notification(notification_msg)
        
        self._log.info(f"Daily usage reset: {old_state}s -> 0s")

