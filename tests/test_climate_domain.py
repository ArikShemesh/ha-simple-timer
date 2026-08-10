"""The sensor read sites, driven by a climate entity.

A climate entity's state is its hvac mode, so every site that used to compare
against the literal `"on"` had a wrong answer for it: a unit running in `heat`
read as "not on", so the meter stopped, the card showed off, and the coupled
auto-cancel could not tell "the user switched it off" from "the user changed
the mode".

Two failure modes drive what is weighted here, in the project's own order:

* **the device acting on its own** - a mode change or a dropped radio message
  must not cancel a running timer, and must not auto-start a second one;
* **a timer silently vanishing** - `unavailable` is not off, and must never
  reach the coupled-cancel branch.

`_handle_switch_change` had no direct test before this file, so the switch-side
rows are here too: this phase rewired its predicates, and without them the
refactor would be unguarded on the domain that every existing user runs.
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

sensor_module = load("sensor")
switch_module = load("switch_control")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor

NOW = datetime(2026, 5, 1, 9, 0, 0)


def _state(value):
    """A state object, or None for "HA has no state for this entity"."""
    if value is None:
        return None
    st = MagicMock()
    st.state = value
    return st


def _event(old, new):
    ev = MagicMock()
    ev.data = {"old_state": _state(old), "new_state": _state(new)}
    return ev


class ClimateSensorTestBase(unittest.IsolatedAsyncioTestCase):
    """Fixtures build the sensor through object.__new__, per repo convention.

    Only the attributes the path under test touches are set. A new attribute
    read on one of these paths breaks the fixture with AttributeError - fix the
    fixture, never reach for getattr.
    """

    def setUp(self):
        self._real_utcnow = sensor_module.dt_util.utcnow
        sensor_module.dt_util.utcnow = lambda: NOW

        # asyncio is a shared module object; restore both or later suites
        # silently skip their real waits.
        self._real_sensor_sleep = sensor_module.asyncio.sleep
        self._real_switch_sleep = switch_module.asyncio.sleep

        async def fake_sleep(seconds):
            return None

        sensor_module.asyncio.sleep = fake_sleep
        switch_module.asyncio.sleep = fake_sleep

        self._real_track_point = sensor_module.async_track_point_in_utc_time
        sensor_module.async_track_point_in_utc_time = MagicMock(return_value=MagicMock())

    def tearDown(self):
        sensor_module.dt_util.utcnow = self._real_utcnow
        sensor_module.asyncio.sleep = self._real_sensor_sleep
        switch_module.asyncio.sleep = self._real_switch_sleep
        sensor_module.async_track_point_in_utc_time = self._real_track_point

    def make_sensor(self, device_state="off", entity="climate.ac",
                    turn_on_option="cool"):
        s = object.__new__(TimerRuntimeSensor)
        s.hass = MagicMock()
        s.hass.services.async_call = AsyncMock()
        s._log = MagicMock()
        s._entry = MagicMock()
        s._entry.data = {"turn_on_option": turn_on_option}
        s._entry_id = "entry123"
        s._switch_entity_id = entity
        s._stop_event_received = False

        s._states = {}
        if device_state is not None and entity:
            s._states[entity] = _state(device_state)
        s.hass.states.get = lambda eid: s._states.get(eid)

        s._turn_on_option = turn_on_option
        s._switch = switch_module.SwitchController(
            s.hass, lambda: s._switch_entity_id,
            notify=AsyncMock(),
            is_timer_active=lambda: s._timer_state == "active",
            get_turn_on_option=lambda: s._turn_on_option,
            log=s._log,
        )
        s._timer_state = "idle"
        return s

    def set_state(self, s, value, entity="climate.ac"):
        s._states[entity] = _state(value)

    def calls_of(self, s):
        return [(c.args[0], c.args[1], c.args[2])
                for c in s.hass.services.async_call.call_args_list]


class DeviceActiveAttributeTestCase(ClimateSensorTestBase):
    """ATTR_DEVICE_ACTIVE is what stops the card guessing from the raw state."""

    def test_truth_table(self):
        for state, expected in [("heat", True), ("cool", True), ("auto", True),
                                ("fan_only", True), ("off", False),
                                ("unavailable", False), ("unknown", False)]:
            with self.subTest(state=state):
                s = self.make_sensor(device_state=state)
                self.assertIs(s._device_active(), expected)

    def test_no_entity_or_no_state_is_not_active(self):
        self.assertFalse(self.make_sensor(entity=None)._device_active())
        self.assertFalse(self.make_sensor(device_state=None)._device_active())

    def test_switch_domain_still_means_the_literal_on_state(self):
        s = self.make_sensor(device_state="on", entity="switch.boiler",
                             turn_on_option=None)
        self.assertTrue(s._device_active())
        self.set_state(s, "heat", entity="switch.boiler")
        self.assertFalse(s._device_active())


class PowerToggleRouteAttributeTestCase(unittest.TestCase):
    """Where the card sends a power press, published instead of guessed.

    The card must never match on the entity id: it ships as a built bundle
    nobody rebuilds, so a domain added to `domains.py` later has to work
    without a card release. This attribute is that contract, and it is part of
    the card's public API - the name cannot change.

    `extra_state_attributes` reads roughly thirty attributes, so the fixture is
    a MagicMock rather than the usual `object.__new__` sensor. Only
    `_switch_entity_id` needs a real value: `descriptor_for` does a string
    membership test on it.
    """

    def _attributes(self, entity_id):
        fake = MagicMock()
        fake._switch_entity_id = entity_id
        return TimerRuntimeSensor.extra_state_attributes.fget(fake)

    def test_switch_like_entity_publishes_direct(self):
        for entity_id in ("switch.boiler", "input_boolean.test", "light.hall",
                          "fan.office"):
            with self.subTest(entity_id=entity_id):
                self.assertEqual(
                    self._attributes(entity_id)["power_toggle_route"], "direct"
                )

    def test_climate_entity_publishes_integration(self):
        self.assertEqual(
            self._attributes("climate.ac")["power_toggle_route"], "integration"
        )

    def test_unconfigured_or_unknown_entity_publishes_direct(self):
        for entity_id in (None, "", "media_player.tv"):
            with self.subTest(entity_id=entity_id):
                self.assertEqual(
                    self._attributes(entity_id)["power_toggle_route"], "direct"
                )


class SwitchChangeTestBase(ClimateSensorTestBase):
    """`_handle_switch_change` is a sync callback that queues real work.

    Every coroutine it would create is replaced by a MagicMock, so the test can
    assert what was queued without a coroutine ever being created - which also
    keeps "never awaited" warnings out of the suite.
    """

    def make_sensor(self, device_state="off", entity="climate.ac",
                    turn_on_option="cool", timer_state="active", reverse=False):
        s = super().make_sensor(device_state=device_state, entity=entity,
                                turn_on_option=turn_on_option)
        s._timer_state = timer_state
        s._timer_reverse_mode = reverse
        s._watchdog_message = None
        s._last_on_timestamp = None
        s._default_timer_enabled = False
        s._default_timer_duration = 0
        s._default_timer_unit = "min"
        s._default_timer_reverse_mode = False

        s.async_write_ha_state = MagicMock()
        s._start_realtime_accumulation = MagicMock(name="start_accumulation")
        s._stop_realtime_accumulation = MagicMock(name="stop_accumulation")
        s.async_cancel_timer = MagicMock(name="cancel_timer")
        s.async_start_timer = MagicMock(name="start_timer")
        s.hass.async_create_task = MagicMock(name="create_task")
        return s


class ClimateCoupledCancelTestCase(SwitchChangeTestBase):
    """The device turning off cancels the timer. Nothing else does."""

    def test_a_climate_unit_switched_off_cancels_an_active_timer(self):
        s = self.make_sensor(device_state="cool")
        s._handle_switch_change(_event("cool", "off"))

        s.async_cancel_timer.assert_called_once()
        s._stop_realtime_accumulation.assert_called_once()
        self.assertIsNone(s._last_on_timestamp)

    def test_a_mode_change_mid_timer_cancels_nothing(self):
        """heat -> fan_only is still the device running. Cancelling here would
        be the timer vanishing because somebody touched the thermostat."""
        s = self.make_sensor(device_state="heat")
        s._handle_switch_change(_event("heat", "fan_only"))

        s.async_cancel_timer.assert_not_called()
        s._stop_realtime_accumulation.assert_not_called()

    def test_a_unit_that_stops_answering_cancels_nothing(self):
        """unavailable is not off - it is the entity saying nothing at all."""
        for dropped in ("unavailable", "unknown"):
            with self.subTest(state=dropped):
                s = self.make_sensor(device_state="cool")
                s._last_on_timestamp = NOW - timedelta(minutes=5)

                s._handle_switch_change(_event("cool", dropped))

                s.async_cancel_timer.assert_not_called()
                # The meter is left running: the device was on a moment ago,
                # and nothing has said otherwise.
                s._stop_realtime_accumulation.assert_not_called()
                self.assertIsNotNone(s._last_on_timestamp)

    def test_a_reverse_timer_is_never_cancelled_by_the_device_going_off(self):
        s = self.make_sensor(device_state="cool", reverse=True)
        s._handle_switch_change(_event("cool", "off"))
        s.async_cancel_timer.assert_not_called()

    def test_an_idle_instance_cancels_nothing(self):
        s = self.make_sensor(device_state="cool", timer_state="idle")
        s._handle_switch_change(_event("cool", "off"))
        s.async_cancel_timer.assert_not_called()

    def test_the_switch_domain_keeps_its_behaviour(self):
        s = self.make_sensor(device_state="on", entity="switch.boiler",
                             turn_on_option=None)
        s._handle_switch_change(_event("on", "off"))
        s.async_cancel_timer.assert_called_once()

    def test_an_unavailable_switch_does_not_cancel_either(self):
        s = self.make_sensor(device_state="on", entity="switch.boiler",
                             turn_on_option=None)
        s._handle_switch_change(_event("on", "unavailable"))
        s.async_cancel_timer.assert_not_called()


class ClimateOnEdgeTestCase(SwitchChangeTestBase):
    """The on-edge seeds the meter and may auto-start the default timer."""

    def test_off_to_a_mode_is_an_edge(self):
        s = self.make_sensor(device_state="off", timer_state="idle")
        s._handle_switch_change(_event("off", "heat"))

        self.assertEqual(s._last_on_timestamp, NOW)
        s._start_realtime_accumulation.assert_called_once()

    def test_unavailable_to_a_mode_is_an_edge(self):
        """Coming back from unavailable IS a start - nothing was metering."""
        s = self.make_sensor(device_state="unavailable", timer_state="idle")
        s._handle_switch_change(_event("unavailable", "cool"))

        self.assertEqual(s._last_on_timestamp, NOW)
        s._start_realtime_accumulation.assert_called_once()

    def test_a_mode_to_mode_change_is_not_an_edge(self):
        """The one that would re-seed the meter and auto-start a SECOND
        default timer every time the user touched the thermostat."""
        s = self.make_sensor(device_state="cool", timer_state="idle")
        s._default_timer_enabled = True
        s._default_timer_duration = 30

        s._handle_switch_change(_event("cool", "heat"))

        self.assertIsNone(s._last_on_timestamp)
        s._start_realtime_accumulation.assert_not_called()
        s.async_start_timer.assert_not_called()

    def test_the_edge_auto_starts_the_default_timer(self):
        s = self.make_sensor(device_state="off", timer_state="idle")
        s._default_timer_enabled = True
        s._default_timer_duration = 45

        s._handle_switch_change(_event("off", "heat"))

        s.async_start_timer.assert_called_once_with(45, "min", reverse_mode=False)

    def test_a_first_ever_state_with_no_previous_one_is_an_edge(self):
        s = self.make_sensor(device_state="off", timer_state="idle")
        s._handle_switch_change(_event(None, "heat"))
        self.assertEqual(s._last_on_timestamp, NOW)

    def test_the_switch_domain_keeps_its_edge(self):
        s = self.make_sensor(device_state="off", entity="switch.boiler",
                             turn_on_option=None, timer_state="idle")
        s._handle_switch_change(_event("off", "on"))
        self.assertEqual(s._last_on_timestamp, NOW)


class ClimateAccumulationTickTestCase(ClimateSensorTestBase):
    """The tick decides whether a second of runtime is counted."""

    def make_sensor(self, device_state="heat", **kwargs):
        s = super().make_sensor(device_state=device_state, **kwargs)
        s._state = 0.0
        s._last_on_timestamp = NOW - timedelta(seconds=10)
        s._last_accumulated_seconds = 0
        s._last_published_seconds = 0
        s._runtime_write_interval = lambda: 30
        s.async_write_ha_state = MagicMock()
        s._stop_realtime_accumulation = MagicMock()
        s.hass.async_create_task = MagicMock()
        return s

    def test_a_running_mode_accumulates(self):
        for mode in ("heat", "cool", "dry", "fan_only", "auto"):
            with self.subTest(mode=mode):
                s = self.make_sensor(device_state=mode)
                s._async_update_accumulated_runtime(NOW)
                self.assertEqual(s._state, 10)

    def test_an_unavailable_unit_keeps_accumulating(self):
        """Unchanged behaviour, deliberately: a dropped connection is not
        evidence the boiler stopped burning gas."""
        for dropped in ("unavailable", "unknown"):
            with self.subTest(state=dropped):
                s = self.make_sensor(device_state=dropped)
                s._async_update_accumulated_runtime(NOW)
                self.assertEqual(s._state, 10)

    def test_an_off_unit_stops_the_meter(self):
        s = self.make_sensor(device_state="off")
        s._async_update_accumulated_runtime(NOW)

        self.assertEqual(s._state, 0.0)
        s.hass.async_create_task.assert_called_once()

    def test_the_switch_domain_still_only_counts_the_on_state(self):
        s = self.make_sensor(device_state="heat", entity="switch.boiler",
                             turn_on_option=None)
        s._async_update_accumulated_runtime(NOW)
        self.assertEqual(s._state, 0.0)


class ClimateStartTimerTestCase(ClimateSensorTestBase):
    """Starting a timer over a climate device applies the configured mode."""

    def make_sensor(self, **kwargs):
        s = super().make_sensor(**kwargs)
        s._timer_state = "idle"
        s._timer_reverse_mode = False
        s._timer_finishes_at = None
        s._timer_duration = 0
        s._timer_start_moment = None
        s._timer_unsub = None
        s._timer_start_method = None
        s._runtime_at_timer_start = 0
        s._watchdog_message = None
        s._state = 0.0
        s._last_on_timestamp = None
        s._accumulation_task = None
        s._store = MagicMock()
        s._store.async_save_timer = AsyncMock()
        s._notifier = MagicMock()
        s._notifier.async_config = AsyncMock(return_value=([], False))
        s._notifier.async_send = AsyncMock()
        s.async_write_ha_state = MagicMock()
        s._start_timer_update_task = AsyncMock()
        s._stop_timer_update_task = AsyncMock()
        s._start_realtime_accumulation = AsyncMock()
        s._stop_realtime_accumulation = AsyncMock()
        s._fire_logbook_event = AsyncMock()
        s._async_setup_switch_listener = AsyncMock()
        s.hass.async_create_task = MagicMock()
        return s

    async def test_a_stopped_unit_is_commanded_into_the_configured_mode(self):
        s = self.make_sensor(device_state="off")
        await s.async_start_timer(30, "min")

        self.assertEqual(
            self.calls_of(s)[0],
            ("climate", "set_hvac_mode",
             {"entity_id": "climate.ac", "hvac_mode": "cool"}),
        )

    async def test_a_unit_already_running_is_left_in_its_current_mode(self):
        """Documented: the configured mode is applied from a stopped device
        only, so a mode the user picked by hand survives the start."""
        s = self.make_sensor(device_state="heat")
        await s.async_start_timer(30, "min")
        self.assertEqual(self.calls_of(s), [])

    async def test_an_unavailable_unit_is_still_commanded(self):
        s = self.make_sensor(device_state="unavailable")
        await s.async_start_timer(30, "min")
        self.assertEqual(self.calls_of(s)[0][1], "set_hvac_mode")


class ClimateRestorePathTestCase(ClimateSensorTestBase):
    """Restart recovery, where a wrong predicate turns the device on unasked."""

    def make_sensor(self, **kwargs):
        s = super().make_sensor(**kwargs)
        s._timer_state = "active"
        s._timer_reverse_mode = False
        s._timer_duration = 30
        s._timer_finishes_at = NOW + timedelta(minutes=10)
        s._timer_start_moment = NOW - timedelta(minutes=20)
        s._timer_unsub = None
        s._runtime_at_timer_start = 0
        s._watchdog_message = None
        s._state = 0.0
        s._last_on_timestamp = None
        s._accumulation_task = None
        s._store = MagicMock()
        s._store.async_read = AsyncMock(return_value={})
        s.async_get_last_state = AsyncMock(return_value=None)
        s._notifier = MagicMock()
        s._notifier.async_config = AsyncMock(return_value=([], False))
        s._send_notification = AsyncMock()
        s.async_write_ha_state = MagicMock()
        s._cleanup_timer_state = AsyncMock()
        s._start_timer_update_task = AsyncMock()
        s._start_realtime_accumulation = AsyncMock()
        # The restore paths spawn a real background retry chain. Close it
        # rather than run it: these tests are about the foreground commands,
        # and a live chain would fight the state the test just set.
        s.hass.async_create_task = lambda coro: coro.close()
        return s

    async def test_an_active_normal_timer_reasserts_the_configured_mode(self):
        s = self.make_sensor(device_state="off")
        await s._restore_active_timer(NOW)

        self.assertEqual(
            self.calls_of(s)[0],
            ("climate", "set_hvac_mode",
             {"entity_id": "climate.ac", "hvac_mode": "cool"}),
        )

    async def test_a_unit_already_running_is_not_recommanded_on_restart(self):
        s = self.make_sensor(device_state="heat")
        await s._restore_active_timer(NOW)
        self.assertEqual(self.calls_of(s), [])

    async def test_a_reverse_timer_never_touches_the_device_on_restart(self):
        """Decoupled: arming a delayed start makes no claim about the device
        before it fires, so a running unit keeps running."""
        s = self.make_sensor(device_state="heat")
        s._timer_reverse_mode = True
        await s._restore_active_timer(NOW)
        self.assertEqual(self.calls_of(s), [])

    async def test_an_expired_normal_timer_sets_hvac_mode_off(self):
        s = self.make_sensor(device_state="heat")
        await s._handle_expired_timer()

        self.assertEqual(
            self.calls_of(s)[0],
            ("climate", "set_hvac_mode",
             {"entity_id": "climate.ac", "hvac_mode": "off"}),
        )

    async def test_an_expired_reverse_timer_commands_the_mode_twice(self):
        """Both attempts of the two-attempt path must reach the device.

        The pair spans 8s and is the entire budget for an unattended restart
        turn-on; collapsing it shipped as a regression once already, so this
        asserts both commands carry the configured mode.
        """
        s = self.make_sensor(device_state="off")
        await s._handle_expired_reverse_timer()

        commands = [c for c in self.calls_of(s) if c[1] == "set_hvac_mode"]
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(c[2]["hvac_mode"] == "cool" for c in commands))

    async def test_an_expired_reverse_timer_reports_a_unit_that_came_up_running(self):
        s = self.make_sensor(device_state="off")

        async def land_in_heat(domain, service, data, **kwargs):
            self.set_state(s, "heat")

        s.hass.services.async_call = AsyncMock(side_effect=land_in_heat)
        await s._handle_expired_reverse_timer()

        self.assertEqual(
            s._send_notification.await_args.args[0],
            "Delayed start timer completed - device turned ON",
        )

    async def test_an_expired_reverse_timer_reports_a_unit_that_stayed_off(self):
        s = self.make_sensor(device_state="off")
        await s._handle_expired_reverse_timer()

        self.assertEqual(
            s._send_notification.await_args.args[0],
            "Delayed start timer completed - device did not turn on",
        )


class UpdateSwitchEntityRejectionTestCase(ClimateSensorTestBase):
    """Fail at misconfiguration time, not at 2am when the timer fires."""

    def make_sensor(self, **kwargs):
        s = super().make_sensor(**kwargs)
        s._last_on_timestamp = None
        s.async_write_ha_state = MagicMock()
        s._async_setup_switch_listener = AsyncMock()
        s._start_realtime_accumulation = AsyncMock()
        s._stop_realtime_accumulation = AsyncMock()
        return s

    def _with_modes(self, s, entity, modes):
        st = _state("off")
        st.attributes = {"hvac_modes": modes}
        s._states[entity] = st

    async def test_repointing_to_climate_without_an_option_is_rejected(self):
        s = self.make_sensor(entity="switch.boiler", turn_on_option=None)
        s._entry.data = {}
        self._with_modes(s, "climate.ac", ["off", "heat", "cool"])

        with self.assertRaises(Exception):
            await s.async_update_switch_entity("climate.ac")

        # And it must not have re-pointed on the way out.
        self.assertEqual(s._switch_entity_id, "switch.boiler")

    async def test_repointing_to_a_climate_with_an_incompatible_mode_is_rejected(self):
        s = self.make_sensor(entity="climate.old", turn_on_option="dry")
        s._entry.data = {"turn_on_option": "dry"}
        self._with_modes(s, "climate.new", ["off", "heat"])

        with self.assertRaises(Exception):
            await s.async_update_switch_entity("climate.new")

    async def test_repointing_to_climate_with_a_valid_option_is_allowed(self):
        s = self.make_sensor(entity="climate.old", turn_on_option="heat")
        s._entry.data = {"turn_on_option": "heat"}
        self._with_modes(s, "climate.new", ["off", "heat", "cool"])

        await s.async_update_switch_entity("climate.new")

        self.assertEqual(s._switch_entity_id, "climate.new")

    async def test_repointing_to_a_switch_is_never_rejected(self):
        """Existing users must see no new failure mode - not even one carrying
        a leftover option from a previous climate entity."""
        s = self.make_sensor(entity="climate.ac", turn_on_option="cool")
        s._states["switch.boiler"] = _state("on")

        await s.async_update_switch_entity("switch.boiler")

        self.assertEqual(s._switch_entity_id, "switch.boiler")

    async def test_repointing_to_a_climate_that_cannot_be_turned_off_is_rejected(self):
        """A usable on-mode is only half the contract. An entity advertising no
        `off` mode would start fine and then ignore the set_hvac_mode: off at
        the deadline, leaving the heater running - which is the config flow's
        `climate_no_off_mode` refusal, and this boundary must match it."""
        s = self.make_sensor(entity="climate.old", turn_on_option="heat")
        s._entry.data = {"turn_on_option": "heat"}
        self._with_modes(s, "climate.new", ["heat", "cool"])

        with self.assertRaises(Exception):
            await s.async_update_switch_entity("climate.new")

        self.assertEqual(s._switch_entity_id, "climate.old")

    async def test_an_unreadable_climate_entity_is_rejected(self):
        s = self.make_sensor(entity="switch.boiler", turn_on_option=None)
        s._entry.data = {}

        with self.assertRaises(Exception):
            await s.async_update_switch_entity("climate.not_loaded_yet")


class UpdateSwitchEntityPersistenceTestCase(ClimateSensorTestBase):
    """Re-pointing must survive a restart.

    The config entry is what `_wait_for_startup_completion` reads back, so a
    re-point that only moved the in-memory attribute is undone by the next
    restart - and an armed delayed start then fires against the OLD device,
    which is this project's worst failure mode.
    """

    def make_sensor(self, **kwargs):
        s = super().make_sensor(**kwargs)
        s._last_on_timestamp = None
        s.async_write_ha_state = MagicMock()
        s._async_setup_switch_listener = AsyncMock()
        s._start_realtime_accumulation = AsyncMock()
        s._stop_realtime_accumulation = AsyncMock()
        s._entry.data = {"switch_entity_id": "switch.boiler",
                         "turn_on_option": "cool", "show_seconds": True}
        s._switch_entity_id = "switch.boiler"
        s._states["switch.new"] = _state("on")
        return s

    def written_data(self, s):
        return s.hass.config_entries.async_update_entry.call_args.kwargs["data"]

    async def test_a_repoint_is_written_to_the_config_entry(self):
        s = self.make_sensor()

        await s.async_update_switch_entity("switch.new")

        s.hass.config_entries.async_update_entry.assert_called_once()
        self.assertEqual(self.written_data(s)["switch_entity_id"], "switch.new")

    async def test_the_write_keeps_every_other_option(self):
        """A dict replace, so anything dropped here is silently lost config."""
        s = self.make_sensor()

        await s.async_update_switch_entity("switch.new")

        self.assertEqual(self.written_data(s)["show_seconds"], True)
        self.assertEqual(self.written_data(s)["turn_on_option"], "cool")

    async def test_the_options_flow_listener_does_not_write_again(self):
        """The other caller arrives with the entry ALREADY carrying the new
        device. Writing there would fire the update listener from inside the
        update listener."""
        s = self.make_sensor()
        s._entry.data = {"switch_entity_id": "switch.new"}
        s._switch_entity_id = "switch.boiler"

        await s.async_update_switch_entity("switch.new")

        self.assertEqual(s._switch_entity_id, "switch.new")
        s.hass.config_entries.async_update_entry.assert_not_called()

    async def test_a_rejected_device_persists_nothing(self):
        s = self.make_sensor()
        s._entry.data = {"switch_entity_id": "switch.boiler"}
        st = _state("off")
        st.attributes = {"hvac_modes": ["off", "heat"]}
        s._states["climate.new"] = st

        with self.assertRaises(Exception):
            await s.async_update_switch_entity("climate.new")

        s.hass.config_entries.async_update_entry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
