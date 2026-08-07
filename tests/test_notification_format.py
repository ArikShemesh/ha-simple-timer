"""Unit tests for notification time formatting in Simple Timer."""
import unittest
from ha_harness import load

sensor_module = load("sensor")
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
