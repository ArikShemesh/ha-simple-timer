"""Reverse mode is decoupled: the device may be ON during a countdown.

A delayed start says only "turn it ON at time T". It says nothing about what
the device does before then, and `async_start_timer` deliberately stopped
forcing the switch off. Daily usage is a meter of device runtime, not of timer
state - so arming a delayed start over a running device must not stop the
meter, and restarting mid-countdown must not switch the device off.

Half the code believed the opposite, which is what these tests pin. Written
against the real accumulation methods with a controlled clock, because the
observable property is "seconds of runtime counted", not "a mock was called".
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

sensor_module = load("sensor")
switch_module = load("switch_control")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor

SESSION_START = datetime(2026, 1, 1, 10, 0, 0)


class _Clock:
    """Mutable stand-in for dt_util.utcnow()."""

    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class ReverseModeTestBase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.clock = _Clock(SESSION_START)
        self._real_utcnow = sensor_module.dt_util.utcnow
        sensor_module.dt_util.utcnow = self.clock

        # asyncio is a shared module object; restore or later suites silently
        # skip their real waits.
        self._real_sensor_sleep = sensor_module.asyncio.sleep
        self._real_switch_sleep = switch_module.asyncio.sleep

        async def fake_sleep(seconds):
            return None

        sensor_module.asyncio.sleep = fake_sleep
        switch_module.asyncio.sleep = fake_sleep

        self._real_track_point = sensor_module.async_track_point_in_utc_time
        sensor_module.async_track_point_in_utc_time = MagicMock(return_value=MagicMock())
        self._real_track_interval = sensor_module.async_track_time_interval
        sensor_module.async_track_time_interval = MagicMock(return_value=MagicMock())

    def tearDown(self):
        sensor_module.dt_util.utcnow = self._real_utcnow
        sensor_module.asyncio.sleep = self._real_sensor_sleep
        switch_module.asyncio.sleep = self._real_switch_sleep
        sensor_module.async_track_point_in_utc_time = self._real_track_point
        sensor_module.async_track_time_interval = self._real_track_interval

    def make_sensor(self, switch_state="on", entity="switch.boiler",
                    turn_on_option=None):
        """Real accumulation and real SwitchController; everything else stubbed.

        _start_realtime_accumulation and _stop_realtime_accumulation are NOT
        mocked - whether the meter keeps running is the entire point.
        """
        s = object.__new__(TimerRuntimeSensor)
        s.hass = MagicMock()
        s.hass.data = {}
        s.hass.services.async_call = AsyncMock()
        s._log = MagicMock()
        s._entry = MagicMock()
        s._entry.data = {"show_seconds": True}
        s._entry_id = "entry123"

        s._switch_entity_id = entity
        s._stop_event_received = False
        s._accumulation_task = None
        s._state = 0.0
        s._last_on_timestamp = None
        s._last_accumulated_seconds = 0
        s._last_published_seconds = 0

        s._timer_state = "idle"
        s._timer_reverse_mode = False
        s._timer_duration = 0
        s._timer_finishes_at = None
        s._timer_start_moment = None
        s._timer_unsub = None
        s._runtime_at_timer_start = 0
        s._watchdog_message = None
        s._timer_start_method = "button"

        s._states = {}
        if switch_state is not None and entity:
            st = MagicMock()
            st.state = switch_state
            s._states[entity] = st
        s.hass.states.get = lambda eid: s._states.get(eid)
        s.hass.async_create_task = lambda coro: coro.close()

        s.async_write_ha_state = MagicMock()
        s._send_notification = AsyncMock()
        s._fire_logbook_event = AsyncMock()
        s._cleanup_timer_state = AsyncMock()
        s._start_timer_update_task = AsyncMock()
        s._stop_timer_update_task = AsyncMock()
        s._async_setup_switch_listener = AsyncMock()
        s.async_get_last_state = AsyncMock(return_value=None)
        s._notifier = MagicMock()
        s._notifier.async_config = AsyncMock(return_value=(None, False))
        s._store = MagicMock()
        s._store.async_save_timer = AsyncMock()
        s._store.async_read = AsyncMock(return_value={})

        s._turn_on_option = turn_on_option
        s._switch = switch_module.SwitchController(
            s.hass, lambda: s._switch_entity_id,
            notify=s._send_notification,
            is_timer_active=lambda: s._timer_state == "active",
            get_turn_on_option=lambda: s._turn_on_option,
            log=s._log,
        )
        return s

    def tick(self, s, seconds):
        """Advance the clock and run one accumulator tick."""
        self.clock.advance(seconds)
        s._async_update_accumulated_runtime(self.clock.now)

    def commands(self, s):
        return [(c.args[1], c.args[2]) for c in s.hass.services.async_call.await_args_list]


class ArmingOverARunningDeviceTestCase(ReverseModeTestBase):

    async def test_the_meter_keeps_running_through_the_countdown(self):
        """CURRENT BEHAVIOUR IS A DEFECT (R1). Live-reproduced.

        Helper ON and accumulating, arm a 10 second delayed start, and daily
        usage stops moving for those 10 seconds - permanently lost, because
        the completion path then opens a fresh session from now.

        async_start_timer's reverse branch clears _last_on_timestamp and stops
        accumulation unconditionally. That was correct when reverse mode forced
        the switch off; the force-off was removed and this was never updated.
        """
        s = self.make_sensor(switch_state="on")
        s._last_on_timestamp = self.clock.now
        await s._start_realtime_accumulation()
        self.assertIsNotNone(s._accumulation_task)

        await s.async_start_timer(1, "min", reverse_mode=True)

        self.tick(s, 10)
        self.assertEqual(s._state, 10)

    async def test_arming_over_a_device_that_is_off_still_stops_the_meter(self):
        """Characterization - green before and after. A device that is off has
        no runtime to count, so clearing the session there stays correct."""
        s = self.make_sensor(switch_state="off")
        s._last_on_timestamp = self.clock.now

        await s.async_start_timer(1, "min", reverse_mode=True)

        self.assertIsNone(s._last_on_timestamp)
        self.assertIsNone(s._accumulation_task)

    async def test_a_normal_timer_over_a_running_device_is_unaffected(self):
        """Guard: normal mode never had this bug and must not acquire one."""
        s = self.make_sensor(switch_state="on")
        s._last_on_timestamp = self.clock.now
        await s._start_realtime_accumulation()

        await s.async_start_timer(1, "min", reverse_mode=False)

        self.tick(s, 10)
        self.assertEqual(s._state, 10)


class CompletionOverARunningMeterTestCase(ReverseModeTestBase):

    async def test_completion_does_not_stall_a_meter_already_running(self):
        """CURRENT BEHAVIOUR IS A DEFECT (R3), and the reason the one-line fix
        for R1 alone would be worse than the bug.

        _async_timer_finished sets _last_on_timestamp = now unconditionally,
        then calls _start_realtime_accumulation, which returns early when a
        task is already running and so never reseeds _last_accumulated_seconds.
        The tick then computes `~0 - old_baseline`, a negative diff, and the
        meter freezes for as long as the device had already been on.
        """
        s = self.make_sensor(switch_state="on")
        s._last_on_timestamp = self.clock.now
        await s._start_realtime_accumulation()
        self.tick(s, 300)
        self.assertEqual(s._state, 300)

        s._timer_state = "active"
        s._timer_reverse_mode = True
        await s._async_timer_finished()

        self.tick(s, 10)
        self.assertEqual(s._state, 310)

    async def test_completion_opens_a_session_when_none_is_running(self):
        """Characterization - green before and after. The device was off during
        the countdown, so completion turning it on starts usage from now."""
        s = self.make_sensor(switch_state="on")
        s._accumulation_task = None
        s._last_on_timestamp = None
        s._timer_state = "active"
        s._timer_reverse_mode = True

        await s._async_timer_finished()

        self.assertEqual(s._last_on_timestamp, self.clock.now)
        self.assertIsNotNone(s._accumulation_task)


class RestartDuringACountdownTestCase(ReverseModeTestBase):

    async def test_startup_does_not_switch_a_running_device_off(self):
        """CURRENT BEHAVIOUR IS A DEFECT (R2).

        _start_accumulation_if_needed commands the switch OFF during a reverse
        countdown - "Ensuring switch stays OFF" - so arming a delayed start
        over a running boiler and then restarting HA turns the boiler off.
        Decoupled means whatever the device is doing is the user's business.
        """
        s = self.make_sensor(switch_state="on")
        s._timer_state = "active"
        s._timer_reverse_mode = True

        await s._start_accumulation_if_needed()

        self.assertEqual(self.commands(s), [])

    async def test_startup_keeps_metering_a_running_device(self):
        """Same defect, the other half: it also returns early, so the meter
        never starts for the rest of the countdown."""
        s = self.make_sensor(switch_state="on")
        s._timer_state = "active"
        s._timer_reverse_mode = True

        await s._start_accumulation_if_needed()

        self.assertIsNotNone(s._accumulation_task)
        self.tick(s, 10)
        self.assertEqual(s._state, 10)

    async def test_restoring_an_active_reverse_timer_does_not_command_the_switch(self):
        """CURRENT BEHAVIOUR IS A DEFECT (R2), second site.

        _restore_active_timer runs ensure("off") for reverse mode on every
        restart, which is the same force-off from the other direction.
        """
        s = self.make_sensor(switch_state="on")
        s._timer_state = "active"
        s._timer_reverse_mode = True
        s._timer_finishes_at = self.clock.now + timedelta(minutes=5)

        await s._restore_active_timer(self.clock.now)

        self.assertEqual(self.commands(s), [])

    async def test_restoring_an_active_normal_timer_still_ensures_on(self):
        """Characterization - green before and after. Normal mode stays
        coupled: the device is supposed to be running for the duration."""
        s = self.make_sensor(switch_state="off")
        s._timer_state = "active"
        s._timer_reverse_mode = False
        s._timer_finishes_at = self.clock.now + timedelta(minutes=5)

        await s._restore_active_timer(self.clock.now)

        self.assertEqual(
            [service for service, _ in self.commands(s)], ["turn_on"]
        )
