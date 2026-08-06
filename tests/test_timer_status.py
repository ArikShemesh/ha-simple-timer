"""Unit tests for the status sensor's state derivation."""
import unittest
import sys
import os
import importlib.util
from unittest.mock import MagicMock

# Mock voluptuous
sys.modules['voluptuous'] = MagicMock()

# Base classes to avoid metaclass conflict and duplicate base errors
class MockSensorEntity:
    pass

class MockRestoreEntity:
    pass

# Setup hierarchical Home Assistant mocks
ha = MagicMock()
sys.modules['homeassistant'] = ha
sys.modules['homeassistant.components'] = ha.components
sys.modules['homeassistant.components.sensor'] = ha.components.sensor
sys.modules['homeassistant.components.persistent_notification'] = ha.components.persistent_notification
sys.modules['homeassistant.components.http'] = ha.components.http
sys.modules['homeassistant.config_entries'] = ha.config_entries
sys.modules['homeassistant.const'] = ha.const
sys.modules['homeassistant.core'] = ha.core
sys.modules['homeassistant.exceptions'] = ha.exceptions
sys.modules['homeassistant.helpers'] = ha.helpers
sys.modules['homeassistant.helpers.config_validation'] = ha.helpers.config_validation
sys.modules['homeassistant.helpers.device_registry'] = ha.helpers.device_registry
sys.modules['homeassistant.helpers.dispatcher'] = ha.helpers.dispatcher
sys.modules['homeassistant.helpers.entity'] = ha.helpers.entity
sys.modules['homeassistant.helpers.event'] = ha.helpers.event
sys.modules['homeassistant.helpers.restore_state'] = ha.helpers.restore_state
sys.modules['homeassistant.helpers.storage'] = ha.helpers.storage
sys.modules['homeassistant.util'] = ha.util
sys.modules['homeassistant.util.dt'] = ha.util.dt

# Assign separate mock classes to base classes used by the sensors
ha.components.sensor.SensorEntity = MockSensorEntity
ha.helpers.restore_state.RestoreEntity = MockRestoreEntity

# Create simple_timer package mock and load const.py
simple_timer_pkg = MagicMock()
simple_timer_pkg.__path__ = [os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "simple_timer"))]
sys.modules['simple_timer'] = simple_timer_pkg

const_path = os.path.join(simple_timer_pkg.__path__[0], "const.py")
spec_const = importlib.util.spec_from_file_location("simple_timer.const", const_path)
const_module = importlib.util.module_from_spec(spec_const)
sys.modules["simple_timer.const"] = const_module
spec_const.loader.exec_module(const_module)

# Load sensor.py as simple_timer.sensor
sensor_path = os.path.join(simple_timer_pkg.__path__[0], "sensor.py")
spec_sensor = importlib.util.spec_from_file_location("simple_timer.sensor", sensor_path)
sensor_module = importlib.util.module_from_spec(spec_sensor)
sys.modules["simple_timer.sensor"] = sensor_module
spec_sensor.loader.exec_module(sensor_module)

derive_timer_status = sensor_module.derive_timer_status
duration_to_seconds = sensor_module.duration_to_seconds
_format_time = sensor_module.TimerRuntimeSensor._format_time_for_notification

STATUS_IDLE = const_module.STATUS_IDLE
STATUS_ACTIVE = const_module.STATUS_ACTIVE
STATUS_DELAYED_START = const_module.STATUS_DELAYED_START
STATUS_SCHEDULED = const_module.STATUS_SCHEDULED


class TestDeriveTimerStatus(unittest.TestCase):
    """Test suite for the status sensor's state derivation."""

    def test_idle_when_nothing_running(self):
        """No timer and no schedule reports idle."""
        self.assertEqual(
            derive_timer_status("idle", reverse_mode=False, has_schedule=False),
            STATUS_IDLE,
        )

    def test_active_normal_timer(self):
        """A running normal-mode timer reports active."""
        self.assertEqual(
            derive_timer_status("active", reverse_mode=False, has_schedule=False),
            STATUS_ACTIVE,
        )

    def test_delayed_start_for_reverse_mode(self):
        """A running reverse-mode timer is a delayed start, not a normal run."""
        self.assertEqual(
            derive_timer_status("active", reverse_mode=True, has_schedule=False),
            STATUS_DELAYED_START,
        )

    def test_scheduled_when_armed_and_no_timer(self):
        """An armed schedule with no running timer reports scheduled."""
        self.assertEqual(
            derive_timer_status("idle", reverse_mode=False, has_schedule=True),
            STATUS_SCHEDULED,
        )

    def test_running_timer_wins_over_armed_schedule(self):
        """A repeating schedule re-arms while its timer runs; the timer wins."""
        self.assertEqual(
            derive_timer_status("active", reverse_mode=False, has_schedule=True),
            STATUS_ACTIVE,
        )

    def test_reverse_timer_wins_over_armed_schedule(self):
        """Same precedence holds for reverse mode."""
        self.assertEqual(
            derive_timer_status("active", reverse_mode=True, has_schedule=True),
            STATUS_DELAYED_START,
        )

    def test_reverse_mode_ignored_when_idle(self):
        """A stale reverse flag must not leak into the idle state."""
        self.assertEqual(
            derive_timer_status("idle", reverse_mode=True, has_schedule=False),
            STATUS_IDLE,
        )

    def test_all_results_are_declared_options(self):
        """Every derivable status must be in STATUS_OPTIONS, or HA rejects it."""
        combos = [
            ("idle", False, False), ("idle", True, False),
            ("idle", False, True), ("active", False, False),
            ("active", True, False), ("active", False, True),
            ("active", True, True),
        ]
        for timer_state, reverse, sched in combos:
            with self.subTest(timer_state=timer_state, reverse=reverse, sched=sched):
                self.assertIn(
                    derive_timer_status(timer_state, reverse, sched),
                    const_module.STATUS_OPTIONS,
                )


class TestDurationToSeconds(unittest.TestCase):
    """Test suite for the duration/unit -> seconds conversion."""

    def test_seconds_units(self):
        for unit in ("s", "sec", "seconds"):
            with self.subTest(unit=unit):
                self.assertEqual(duration_to_seconds(30, unit), 30)

    def test_minutes_units(self):
        for unit in ("m", "min", "minutes"):
            with self.subTest(unit=unit):
                self.assertEqual(duration_to_seconds(2, unit), 120)

    def test_hours_units(self):
        for unit in ("h", "hr", "hours"):
            with self.subTest(unit=unit):
                self.assertEqual(duration_to_seconds(1.5, unit), 5400)

    def test_days_units(self):
        for unit in ("d", "day", "days"):
            with self.subTest(unit=unit):
                self.assertEqual(duration_to_seconds(1, unit), 86400)

    def test_unknown_unit_defaults_to_minutes(self):
        """The service schema defaults unit to 'min'; keep that fallback."""
        self.assertEqual(duration_to_seconds(3, "wibble"), 180)


class TestLogbookDurationFormatting(unittest.TestCase):
    """Logbook durations must stay precise regardless of show_seconds.

    Notifications honour show_seconds, which collapses sub-minute values to
    "0 minutes". That is acceptable when spoken but wrong in a history log,
    so _format_duration_for_logbook pins show_seconds to True.
    """

    def test_short_durations_survive(self):
        """A 10 second timer must never log as "0 minutes"."""
        self.assertEqual(_format_time(None, 10, show_seconds=True)[0], "10 seconds")
        # Guards the regression this exists to prevent:
        self.assertEqual(_format_time(None, 10, show_seconds=False)[0], "0 minutes")

    def test_compound_durations(self):
        self.assertEqual(_format_time(None, 365, show_seconds=True)[0], "6 minutes 5 seconds")
        self.assertEqual(_format_time(None, 5400, show_seconds=True)[0], "1 hour 30 minutes")

    def test_scheduled_ten_second_duration_reads_naturally(self):
        """End to end for the case that prompted this: schedule 10 s."""
        seconds = duration_to_seconds(10, "s")
        self.assertEqual(_format_time(None, seconds, show_seconds=True)[0], "10 seconds")


if __name__ == '__main__':
    unittest.main()
