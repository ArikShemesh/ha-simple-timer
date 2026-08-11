"""Removal as a barrier: nothing the sensor started may outlive it.

A config-entry reload removes the entity and builds a new one. Anything still
in flight at that moment - the deferred initialisation task, the HA-stop
listener - belongs to an instance that no longer exists, and can still write
state or command the device.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

sensor_module = load("sensor")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor


def make_sensor():
    s = object.__new__(TimerRuntimeSensor)
    s.hass = MagicMock()
    s.hass.data = {}
    s._log = MagicMock()
    s._entry = MagicMock()
    s._entry.data = {}
    s._entry_id = "entry123"
    s.entity_id = "sensor.boiler_timer"

    s._stop_event_received = False
    s._accumulation_task = None
    s._timer_update_task = None
    s._timer_unsub = None
    s._reset_time_tracker = None
    s._state_listener_disposer = None
    s._registry_listener_disposer = None
    s._state = 0.0

    s._store = MagicMock()
    s._store.async_read = AsyncMock(return_value={})
    s._schedule = MagicMock()
    s.async_get_last_state = AsyncMock(return_value=None)
    s.async_write_ha_state = MagicMock()
    s._stop_timer_update_task = AsyncMock()
    s._switch = MagicMock()
    return s


class DeferredInitTaskTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_removal_cancels_the_deferred_initialisation_task(self):
        """CURRENT BEHAVIOUR IS A DEFECT (S4).

        async_added_to_hass fires the startup wait with a discarded
        create_task, so removal cannot stop it. It can then resume and restore
        a timer - commanding the switch - against a sensor HA already removed.
        Asserts the WANTED behaviour; fails today with AttributeError.
        """
        s = make_sensor()
        started = asyncio.Event()

        async def slow_init():
            started.set()
            await asyncio.sleep(30)

        s._wait_for_startup_completion = slow_init
        await s.async_added_to_hass()
        await started.wait()
        task = s._init_task

        await s.async_will_remove_from_hass()

        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_initialisation_stops_if_removal_already_happened(self):
        """Belt and braces for the same defect: cancellation may arrive after
        the task passed its last await, so the phase itself must check."""
        s = make_sensor()
        s._stop_event_received = True
        s._load_storage_data = AsyncMock(return_value={})

        await s._complete_initialization()

        s._load_storage_data.assert_not_awaited()


class StopListenerTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_removal_disposes_the_ha_stop_listener(self):
        """CURRENT BEHAVIOUR IS A DEFECT (S4).

        bus.async_listen returns a disposer that is dropped on the floor, so
        every removed instance is kept alive by the bus until HA stops - and
        the entry is reloaded on every options-flow change.
        """
        s = make_sensor()
        disposer = MagicMock()
        s.hass.bus.async_listen = MagicMock(return_value=disposer)
        s._wait_for_startup_completion = AsyncMock()

        await s.async_added_to_hass()
        await s.async_will_remove_from_hass()

        disposer.assert_called_once()


class HaShutdownTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_ha_shutdown_stops_the_same_work_removal_does(self):
        """CURRENT BEHAVIOUR IS A DEFECT (S4).

        _handle_ha_shutdown set _stop_event_received and cancelled its own
        three trackers, but left the deferred init task, the schedule and the
        switch retry chains running. HA moves tasks that predate
        EVENT_HOMEASSISTANT_STOP aside and does not cancel them until the
        final shutdown stage, so a turn-on chain sleeping through its 2/5/10/20s
        backoff can still wake and command the boiler - and a turn-on retry
        never consults the timer-active predicate.

        Asserts the WANTED behaviour; fails today.
        """
        s = make_sensor()
        started = asyncio.Event()

        async def slow_init():
            started.set()
            await asyncio.sleep(30)

        s._wait_for_startup_completion = slow_init
        await s.async_added_to_hass()
        await started.wait()
        task = s._init_task

        await s._handle_ha_shutdown(MagicMock())

        s._schedule.async_shutdown.assert_called_once()
        s._switch.async_shutdown.assert_called_once()
        with self.assertRaises(asyncio.CancelledError):
            await task


class SwitchShutdownTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_removal_shuts_the_switch_controller_down(self):
        """Pairs with W2 (Task 4): retry chains must be told to stop."""
        s = make_sensor()
        s._wait_for_startup_completion = AsyncMock()

        await s.async_added_to_hass()
        await s.async_will_remove_from_hass()

        s._switch.async_shutdown.assert_called_once()


class ReAddAfterRemovalTestCase(unittest.IsolatedAsyncioTestCase):
    """Removal is a barrier; being added again is the other side of it (L1).

    Home Assistant handles an entity_id change by removing and re-adding the
    SAME entity object - and it performs one whenever a device is renamed,
    including from the "Name and assign" dialog it shows the moment a config
    entry is created. Every barrier removal raises is one-way, so without this
    the revived object registers itself in hass.data, answers every service
    call, and silently does nothing.
    """

    def _revivable(self):
        s = make_sensor()
        s._wait_for_startup_completion = AsyncMock()
        s._build_collaborators = MagicMock()
        return s

    async def test_a_re_add_lowers_the_shutdown_barrier(self):
        s = self._revivable()
        await s.async_added_to_hass()
        await s.async_will_remove_from_hass()
        self.assertTrue(s._stop_event_received)     # removal really did latch

        await s.async_added_to_hass()

        self.assertFalse(s._stop_event_received)

    async def test_a_re_add_replaces_the_latched_collaborators(self):
        """Clearing the flag alone would leave a sensor that accepts timer
        starts while holding a controller that can never command again."""
        s = self._revivable()
        await s.async_added_to_hass()
        await s.async_will_remove_from_hass()
        s._build_collaborators.reset_mock()

        await s.async_added_to_hass()

        s._build_collaborators.assert_called_once()

    async def test_a_first_add_rebuilds_nothing(self):
        """The narrow condition, pinned: a normal startup must not discard the
        collaborators __init__ just built, schedule state and all."""
        s = self._revivable()
        await s.async_added_to_hass()
        s._build_collaborators.assert_not_called()

    async def test_a_revived_sensor_starts_timers_again(self):
        """The user-visible symptom: the card's start button did nothing.

        Driven through the real guard in async_start_timer rather than the
        flag, because that guard is what turned the press into a no-op.
        """
        s = self._revivable()
        s._store.async_save_timer = AsyncMock()
        await s.async_added_to_hass()
        await s.async_will_remove_from_hass()
        await s.async_added_to_hass()

        s._timer_state = "idle"
        s._async_setup_switch_listener = AsyncMock()
        s._switch.async_command = AsyncMock()
        s._start_realtime_accumulation = AsyncMock()
        s._stop_realtime_accumulation = AsyncMock()
        s._start_timer_update_task = AsyncMock()
        s._fire_logbook_event = AsyncMock()
        s._send_notification = AsyncMock()
        s._notifier = MagicMock()
        s._notifier.async_config = AsyncMock(return_value=([], False))
        s.hass.states.get.return_value = None
        s._switch_entity_id = "switch.boiler"
        s._timer_reverse_mode = False
        s._timer_finishes_at = None
        s._timer_duration = 0
        s._timer_start_moment = None
        s._runtime_at_timer_start = 0
        s._timer_start_method = None
        s._watchdog_message = None
        s._last_on_timestamp = None
        s._accumulation_task = None

        await s.async_start_timer(5, "min")

        self.assertEqual(s._timer_state, "active")
