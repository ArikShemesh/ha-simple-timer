"""Unit tests for notification time formatting in Simple Timer."""
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
sys.modules['homeassistant.helpers.entity'] = ha.helpers.entity
sys.modules['homeassistant.helpers.event'] = ha.helpers.event
sys.modules['homeassistant.helpers.restore_state'] = ha.helpers.restore_state
sys.modules['homeassistant.helpers.storage'] = ha.helpers.storage
sys.modules['homeassistant.util'] = ha.util
sys.modules['homeassistant.util.dt'] = ha.util.dt

# Assign separate mock classes to base classes used by TimerRuntimeSensor
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

TimerRuntimeSensor = sensor_module.TimerRuntimeSensor


class TestNotificationFormat(unittest.TestCase):
    """Test suite for notification time formatting."""

    def test_format_hours_and_minutes(self):
        """Test formatting hours and minutes without seconds."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 5400, show_seconds=False)
        self.assertEqual(formatted, "1 hour 30 minutes")
        self.assertEqual(label, "")

    def test_format_multiple_hours(self):
        """Test formatting multiple hours without seconds."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 7200, show_seconds=False)
        self.assertEqual(formatted, "2 hours")
        self.assertEqual(label, "")

    def test_format_single_hour(self):
        """Test formatting exactly 1 hour."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 3600, show_seconds=False)
        self.assertEqual(formatted, "1 hour")
        self.assertEqual(label, "")

    def test_format_minutes_only(self):
        """Test formatting minutes only (less than 1 hour)."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 2700, show_seconds=False)
        self.assertEqual(formatted, "45 minutes")
        self.assertEqual(label, "")

    def test_format_single_minute(self):
        """Test formatting exactly 1 minute."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 60, show_seconds=False)
        self.assertEqual(formatted, "1 minute")
        self.assertEqual(label, "")

    def test_format_zero_seconds(self):
        """Test formatting 0 seconds without show_seconds."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 0, show_seconds=False)
        self.assertEqual(formatted, "0 minutes")
        self.assertEqual(label, "")

    def test_format_with_show_seconds_minutes_and_seconds(self):
        """Test formatting with show_seconds=True for minutes and seconds."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 90, show_seconds=True)
        self.assertEqual(formatted, "1 minute 30 seconds")
        self.assertEqual(label, "")

    def test_format_with_show_seconds_single_second(self):
        """Test formatting 1 second with show_seconds=True."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 1, show_seconds=True)
        self.assertEqual(formatted, "1 second")
        self.assertEqual(label, "")

    def test_format_with_show_seconds_zero(self):
        """Test formatting 0 seconds with show_seconds=True."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 0, show_seconds=True)
        self.assertEqual(formatted, "0 seconds")
        self.assertEqual(label, "")

    def test_format_hours_minutes_and_seconds(self):
        """Test formatting hours, minutes, and seconds with show_seconds=True."""
        formatted, label = TimerRuntimeSensor._format_time_for_notification(None, 3661, show_seconds=True)
        self.assertEqual(formatted, "1 hour 1 minute 1 second")
        self.assertEqual(label, "")


if __name__ == "__main__":
    unittest.main()
