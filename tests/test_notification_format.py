"""Unit tests for notification time formatting in Simple Timer."""
import unittest
from ha_harness import load

helpers = load("helpers")
format_duration_natural = helpers.format_duration_natural


class TestNotificationFormat(unittest.TestCase):
    """Test suite for notification time formatting."""

    def test_format_hours_and_minutes(self):
        """Test formatting hours and minutes without seconds."""
        formatted = format_duration_natural(5400, show_seconds=False)
        self.assertEqual(formatted, "1 hour 30 minutes")

    def test_format_multiple_hours(self):
        """Test formatting multiple hours without seconds."""
        formatted = format_duration_natural(7200, show_seconds=False)
        self.assertEqual(formatted, "2 hours")

    def test_format_single_hour(self):
        """Test formatting exactly 1 hour."""
        formatted = format_duration_natural(3600, show_seconds=False)
        self.assertEqual(formatted, "1 hour")

    def test_format_minutes_only(self):
        """Test formatting minutes only (less than 1 hour)."""
        formatted = format_duration_natural(2700, show_seconds=False)
        self.assertEqual(formatted, "45 minutes")

    def test_format_single_minute(self):
        """Test formatting exactly 1 minute."""
        formatted = format_duration_natural(60, show_seconds=False)
        self.assertEqual(formatted, "1 minute")

    def test_format_zero_seconds(self):
        """Zero reads in seconds even with show_seconds off - it is sub-minute."""
        formatted = format_duration_natural(0, show_seconds=False)
        self.assertEqual(formatted, "0 seconds")

    def test_format_with_show_seconds_minutes_and_seconds(self):
        """Test formatting with show_seconds=True for minutes and seconds."""
        formatted = format_duration_natural(90, show_seconds=True)
        self.assertEqual(formatted, "1 minute 30 seconds")

    def test_format_with_show_seconds_single_second(self):
        """Test formatting 1 second with show_seconds=True."""
        formatted = format_duration_natural(1, show_seconds=True)
        self.assertEqual(formatted, "1 second")

    def test_format_with_show_seconds_zero(self):
        """Test formatting 0 seconds with show_seconds=True."""
        formatted = format_duration_natural(0, show_seconds=True)
        self.assertEqual(formatted, "0 seconds")

    def test_format_hours_minutes_and_seconds(self):
        """Test formatting hours, minutes, and seconds with show_seconds=True."""
        formatted = format_duration_natural(3661, show_seconds=True)
        self.assertEqual(formatted, "1 hour 1 minute 1 second")

    def test_format_exactly_one_day(self):
        """A day reads as a day; "24 hours" is how a clock format would say it."""
        formatted = format_duration_natural(86400, show_seconds=False)
        self.assertEqual(formatted, "1 day")

    def test_format_days_and_hours(self):
        """Days are a real duration here - the service accepts a "days" unit."""
        formatted = format_duration_natural(90000, show_seconds=False)
        self.assertEqual(formatted, "1 day 1 hour")

    def test_format_multiple_days(self):
        formatted = format_duration_natural(180000, show_seconds=False)
        self.assertEqual(formatted, "2 days 2 hours")


if __name__ == "__main__":
    unittest.main()
