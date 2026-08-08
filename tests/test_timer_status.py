"""Unit tests for the status sensor's state derivation."""
import unittest
from ha_harness import load

status_module = load("status_sensor")
const_module = load("const")
helpers = load("helpers")

derive_timer_status = status_module.derive_timer_status
duration_to_seconds = helpers.duration_to_seconds
_format_time = helpers.format_duration_natural
format_duration_exact = helpers.format_duration_exact

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

    show_seconds is overridden below a minute, so sub-minute values report
    seconds whatever the instance setting says. format_duration_exact
    additionally pins show_seconds to True, which is what keeps compound
    durations precise in logbook lines and in the notifications that quote a
    duration. Only cumulative daily-usage totals still honour the setting.
    """

    def test_short_durations_survive(self):
        """A 10 second timer must never read as "0 minutes", setting be damned."""
        self.assertEqual(_format_time(10, show_seconds=True), "10 seconds")
        self.assertEqual(_format_time(10, show_seconds=False), "10 seconds")

    def test_sub_minute_ignores_show_seconds(self):
        """Every sub-minute value reports seconds; "0 minutes" is unreachable."""
        for seconds, expected in [(0, "0 seconds"), (1, "1 second"),
                                  (30, "30 seconds"), (59, "59 seconds")]:
            with self.subTest(seconds=seconds):
                self.assertEqual(_format_time(seconds, show_seconds=False), expected)
                self.assertEqual(_format_time(seconds, show_seconds=True), expected)

    def test_a_minute_and_over_still_honours_show_seconds(self):
        """The override stops at 60s - coarse durations round as before."""
        self.assertEqual(_format_time(60, show_seconds=False), "1 minute")
        self.assertEqual(_format_time(90, show_seconds=False), "1 minute")
        self.assertEqual(_format_time(90, show_seconds=True), "1 minute 30 seconds")
        self.assertEqual(_format_time(3661, show_seconds=False), "1 hour 1 minute")

    def test_compound_durations(self):
        self.assertEqual(_format_time(365, show_seconds=True), "6 minutes 5 seconds")
        self.assertEqual(_format_time(5400, show_seconds=True), "1 hour 30 minutes")

    def test_format_duration_exact_always_includes_seconds(self):
        """The wrapper the logbook and duration notifications actually call.

        Tested directly: the other cases here drive format_duration_natural, so
        a wrapper that forgot to pin show_seconds=True would still pass them.
        """
        self.assertEqual(format_duration_exact(108), "1 minute 48 seconds")
        self.assertEqual(format_duration_exact(3661), "1 hour 1 minute 1 second")
        self.assertEqual(format_duration_exact(10), "10 seconds")
        self.assertEqual(format_duration_exact(60), "1 minute")

    def test_scheduled_ten_second_duration_reads_naturally(self):
        """End to end for the case that prompted this: schedule 10 s."""
        seconds = duration_to_seconds(10, "s")
        self.assertEqual(_format_time(seconds, show_seconds=True), "10 seconds")


if __name__ == '__main__':
    unittest.main()
