"""Unit tests for runtime accumulation across a Home Assistant restart.

Covers the manual-on case: the monitored switch is on with no timer running,
Home Assistant restarts, and accumulation resumes. `_restore_basic_state`
restores `_last_on_timestamp` from the pre-restart attributes, so the resumed
session must not re-count the elapsed time that `_state` already contains.
"""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from ha_harness import load

sensor_module = load("sensor")
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


class AccumulationRestartTestCase(unittest.TestCase):
    """Drives the real accumulation methods with a controlled clock."""

    def setUp(self):
        self.clock = _Clock(SESSION_START)
        sensor_module.dt_util.utcnow = self.clock

        # The switch the sensor watches, reported as on.
        self.switch_state = MagicMock()
        # The literal, not sensor_module.STATE_ON: sensor.py no longer imports
        # the state constants now that the domain descriptors own that
        # comparison.
        self.switch_state.state = "on"

    def _make_sensor(self, state: float, last_on_timestamp: datetime, show_seconds: bool = False):
        """Build a TimerRuntimeSensor with only what accumulation touches.

        Bypasses __init__ so the test does not depend on config-entry or Store
        setup, but keeps the real class so the real methods run.
        """
        sensor = object.__new__(TimerRuntimeSensor)

        sensor.hass = MagicMock()
        sensor.hass.states.get.return_value = self.switch_state

        sensor._entry = MagicMock()
        sensor._entry.data = {"show_seconds": show_seconds}

        sensor._switch_entity_id = "switch.boiler"
        sensor._stop_event_received = False
        sensor._accumulation_task = None
        sensor._state = state
        sensor._last_on_timestamp = last_on_timestamp
        sensor._last_accumulated_seconds = 0
        sensor._last_published_seconds = 0

        # Instance attribute shadows the class method, so no HA state write is
        # attempted and we can count publishes.
        sensor.async_write_ha_state = MagicMock()

        return sensor

    def _run_ticks(self, sensor, seconds: int) -> None:
        """Advance the clock one second at a time, ticking the accumulator."""
        for _ in range(seconds):
            self.clock.advance(1)
            sensor._async_update_accumulated_runtime(self.clock.now)

    def test_accumulates_within_a_single_session(self):
        """Baseline: 30 minutes on adds 1800s, and no more."""
        sensor = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)

        self.clock.advance(1800)
        sensor._async_update_accumulated_runtime(self.clock.now)

        self.assertAlmostEqual(sensor._state, 1800, delta=1)

    def test_repeated_ticks_do_not_double_count(self):
        """Several ticks in one session still total the real elapsed time."""
        sensor = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)

        for _ in range(6):
            self.clock.advance(300)
            sensor._async_update_accumulated_runtime(self.clock.now)

        self.assertAlmostEqual(sensor._state, 1800, delta=1)

    def test_resumed_session_after_restart_does_not_double_count(self):
        """The pre-restart portion of a manual-on session is counted once.

        Reproduces the restart path: the switch goes on at 10:00 and runs for
        30 minutes, HA restarts with 120s of downtime, and _restore_basic_state
        brings back both the accumulated state and the original
        _last_on_timestamp. Accumulation then resumes on top of that.

        The resumed session must continue from the restored 1800s, not add the
        whole elapsed period again. The 120s of downtime is knowingly forfeited
        - see the limitation note in _start_realtime_accumulation - so the
        expected total is 1801, not 1921 and emphatically not 3721.
        """
        # Session runs 30 minutes and gets published.
        pre_restart = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)
        self.clock.advance(1800)
        pre_restart._async_update_accumulated_runtime(self.clock.now)
        self.assertAlmostEqual(pre_restart._state, 1800, delta=1)

        # HA restarts. _restore_basic_state restores the state value and the
        # original last_on_timestamp; the switch is still on.
        self.clock.advance(120)
        restored = self._make_sensor(
            state=pre_restart._state,
            last_on_timestamp=SESSION_START,
        )

        # Accumulation resumes through the real entry point.
        asyncio.run(restored._start_realtime_accumulation())

        self.clock.advance(1)
        restored._async_update_accumulated_runtime(self.clock.now)

        self.assertAlmostEqual(restored._state, 1801, delta=2)

    def test_resumed_session_forfeits_at_most_the_downtime(self):
        """The loss is bounded by the outage, and never grows the total.

        Guards the trade-off explicitly: however long HA was down, the resumed
        session may under-count by that much but must never exceed the true
        elapsed time.
        """
        pre_restart = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)
        self.clock.advance(600)
        pre_restart._async_update_accumulated_runtime(self.clock.now)

        downtime = 45
        self.clock.advance(downtime)
        restored = self._make_sensor(
            state=pre_restart._state,
            last_on_timestamp=SESSION_START,
        )
        asyncio.run(restored._start_realtime_accumulation())

        self._run_ticks(restored, 60)

        true_elapsed = (self.clock.now - SESSION_START).total_seconds()
        self.assertLessEqual(restored._state, true_elapsed)
        self.assertGreaterEqual(restored._state, true_elapsed - downtime - 1)


class RuntimeWriteThrottleTestCase(unittest.TestCase):
    """The published-write cadence must not affect the accumulated value."""

    def setUp(self):
        self.clock = _Clock(SESSION_START)
        sensor_module.dt_util.utcnow = self.clock

        self.switch_state = MagicMock()
        # The literal, not sensor_module.STATE_ON: sensor.py no longer imports
        # the state constants now that the domain descriptors own that
        # comparison.
        self.switch_state.state = "on"

    _make_sensor = AccumulationRestartTestCase._make_sensor
    _run_ticks = AccumulationRestartTestCase._run_ticks

    def test_default_publishes_on_the_interval_not_every_second(self):
        """show_seconds off: 90s of ticks publishes 3 times, not 90."""
        sensor = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)

        self._run_ticks(sensor, 90)

        self.assertEqual(sensor.async_write_ha_state.call_count, 3)

    def test_show_seconds_keeps_per_second_writes(self):
        """show_seconds on: the per-second cadence is unchanged."""
        sensor = self._make_sensor(
            state=0.0, last_on_timestamp=SESSION_START, show_seconds=True
        )

        self._run_ticks(sensor, 90)

        self.assertEqual(sensor.async_write_ha_state.call_count, 90)

    def test_accumulated_value_is_exact_regardless_of_cadence(self):
        """Throttling publishes must not lose runtime."""
        throttled = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)
        self._run_ticks(throttled, 95)

        self.setUp()  # reset the clock for a clean comparison run
        per_second = self._make_sensor(
            state=0.0, last_on_timestamp=SESSION_START, show_seconds=True
        )
        self._run_ticks(per_second, 95)

        self.assertEqual(throttled._state, per_second._state)
        self.assertAlmostEqual(throttled._state, 95, delta=1)

    def test_final_update_publishes_immediately(self):
        """Switch-off and shutdown flushes must publish mid-interval."""
        sensor = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)

        self._run_ticks(sensor, 5)
        self.assertEqual(sensor.async_write_ha_state.call_count, 0)

        self.clock.advance(1)
        sensor._async_update_accumulated_runtime(self.clock.now, final_update=True)

        self.assertEqual(sensor.async_write_ha_state.call_count, 1)
        self.assertAlmostEqual(sensor._state, 6, delta=1)

    def test_flush_publishes_when_it_lands_mid_second(self):
        """A flush must not be skipped just because it arrives between ticks.

        Shutdown and switch-off flushes fire at an arbitrary moment. When that
        moment rounds to the same whole second as the last tick there is no new
        second to add, but seconds accumulated since the last publish are still
        pending and must be written.
        """
        sensor = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)

        self._run_ticks(sensor, 10)
        self.assertEqual(sensor.async_write_ha_state.call_count, 0)

        # Mid-second: round() yields the same whole second as the last tick,
        # so the accumulator adds nothing on this call.
        self.clock.advance(0.4)
        sensor._async_update_accumulated_runtime(self.clock.now, final_update=True)

        self.assertEqual(sensor.async_write_ha_state.call_count, 1)
        self.assertAlmostEqual(sensor._state, 10, delta=1)

    def test_flush_with_nothing_pending_does_not_write(self):
        """A flush right after a publish must not add a redundant row."""
        sensor = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)

        self._run_ticks(sensor, 30)
        self.assertEqual(sensor.async_write_ha_state.call_count, 1)

        sensor._async_update_accumulated_runtime(self.clock.now, final_update=True)

        self.assertEqual(sensor.async_write_ha_state.call_count, 1)

    def test_interval_follows_config_entry_without_reload(self):
        """Toggling show_seconds takes effect on the next tick."""
        sensor = self._make_sensor(state=0.0, last_on_timestamp=SESSION_START)

        self._run_ticks(sensor, 40)
        self.assertEqual(sensor.async_write_ha_state.call_count, 1)

        sensor._entry.data["show_seconds"] = True
        self._run_ticks(sensor, 5)

        self.assertEqual(sensor.async_write_ha_state.call_count, 6)


if __name__ == "__main__":
    unittest.main()
