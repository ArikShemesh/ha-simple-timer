"""Characterization tests for scheduled starts.

Written BEFORE extracting ScheduleManager, to pin current behaviour.

A scheduled start arms a point-in-time callback that later runs a *bounded*
timer. The subtle parts are all in the edges: what survives a restart, what a
repeat re-arms to, and which paths deliberately do NOT clear the schedule.
Weighted accordingly - the happy path is the least interesting thing here.
"""
import unittest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

sensor_module = load("sensor")
schedule_module = load("schedule")
timer_store_module = load("timer_store")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor

# A Wednesday, so weekday filtering is observable (Mon=0 ... Wed=2).
NOW = datetime(2026, 3, 4, 8, 0, 0)


def make_sensor():
    """A sensor wired to a real ScheduleManager, so delegation is exercised.

    Assertions still read the manager's state, which is what the sensor's
    attributes and the status sensor derive from.
    """
    s = object.__new__(TimerRuntimeSensor)
    s.hass = MagicMock()
    s._log = MagicMock()
    s._entry = MagicMock()
    s._entry.data = {}
    s._entry_id = "entry123"

    s._store = MagicMock()
    s._store.async_save_schedule = AsyncMock()
    s._store.async_clear_schedule = AsyncMock()

    s.async_write_ha_state = MagicMock()
    s._fire_logbook_event = AsyncMock()
    s.async_start_timer = AsyncMock()

    s._schedule = schedule_module.ScheduleManager(
        s.hass,
        store=s._store,
        start_timer=s.async_start_timer,
        write_state=s.async_write_ha_state,
        fire_logbook=s._fire_logbook_event,
        log=s._log,
    )
    return s


class ScheduleTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Mutable, because firing a schedule has to happen AT the fire time -
        # compute_next_fire reads the clock, so a frozen one re-arms to the
        # instant that just fired instead of the next occurrence.
        self.now = NOW
        schedule_module.dt_util.now = lambda: self.now
        schedule_module.dt_util.as_utc = lambda d: d
        # Identity, so this suite's naive clock stays internally consistent.
        # The aware/naive path has its own test; real DST behaviour is a known
        # gap recorded in TODO.md.
        schedule_module.dt_util.as_local = lambda d: d
        self.unsub = MagicMock()
        schedule_module.async_track_point_in_utc_time = MagicMock(return_value=self.unsub)

    async def fire(self, s):
        """Advance the clock to the armed moment, then run the callback."""
        self.now = s._schedule.fire_at
        await s._schedule._async_fired()

    async def restore(self, s, payload):
        """Restore the way production does - through TimerStore's sanitizer.

        `_complete_initialization` passes the result of `TimerStore.async_load`,
        which type-checks the payload. Feeding async_restore a raw dict would
        test a path that never happens and would demand the manager re-validate
        what the store already guarantees.
        """
        clean = timer_store_module._sanitize(payload, s._log)
        await s._schedule.async_restore(clean)


class ArmingTestCase(ScheduleTestBase):

    async def test_arms_for_the_next_occurrence_and_persists(self):
        s = make_sensor()
        await s.async_schedule_timer(time(7, 30), 45, "min")

        self.assertEqual(s._schedule.fire_at, datetime(2026, 3, 5, 7, 30))
        self.assertEqual(s._schedule.duration, 45)
        s._store.async_save_schedule.assert_awaited_once()
        s.async_write_ha_state.assert_called()

    async def test_later_today_arms_today(self):
        s = make_sensor()
        await s.async_schedule_timer(time(9, 0), 10, "min")
        self.assertEqual(s._schedule.fire_at, datetime(2026, 3, 4, 9, 0))

    async def test_days_are_deduped_and_sorted(self):
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 5, "min", repeat=True, days=[4, 0, 4, 2])
        self.assertEqual(s._schedule.days, [0, 2, 4])

    async def test_rearming_disposes_the_previous_callback(self):
        """Otherwise the old point-in-time callback still fires."""
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 5, "min")
        first_unsub = self.unsub

        await s.async_schedule_timer(time(8, 30), 5, "min")
        first_unsub.assert_called_once()

    async def test_logbook_event_carries_the_armed_time(self):
        s = make_sensor()
        await s.async_schedule_timer(time(7, 30), 45, "min")
        kwargs = s._fire_logbook_event.await_args.kwargs
        self.assertEqual(kwargs["start_time"], "07:30")
        self.assertEqual(kwargs["duration"], "45 minutes")

    async def test_empty_weekday_set_means_every_day(self):
        """`days=[]` is "no filter", not "never" - it must still arm."""
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 5, "min", repeat=True, days=[])
        self.assertEqual(s._schedule.fire_at, datetime(2026, 3, 5, 7, 0))

    async def test_unresolvable_weekdays_change_nothing(self):
        """Out-of-range weekday numbers are the real way this resolves to None.

        Driven through the actual helper rather than mocking it - an earlier
        version of this test mocked compute_next_fire and claimed empty days
        could not resolve, which is false.
        """
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 5, "min", repeat=True, days=[9])

        self.assertIsNone(s._schedule.fire_at)
        s._store.async_save_schedule.assert_not_awaited()
        s.async_write_ha_state.assert_not_called()
        s._log.warning.assert_called()


class FiringTestCase(ScheduleTestBase):

    async def test_runs_a_bounded_forward_timer(self):
        """Reverse is always overridden - a scheduled run must auto-off."""
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 20, "min")
        await self.fire(s)

        s.async_start_timer.assert_awaited_once_with(
            20, "min", reverse_mode=False, start_method="schedule")

    async def test_one_shot_clears_itself_after_firing(self):
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 20, "min")
        await self.fire(s)

        self.assertIsNone(s._schedule.fire_at)
        s._store.async_clear_schedule.assert_awaited()

    async def test_repeat_rearms_for_the_following_day(self):
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 20, "min", repeat=True)
        armed = s._schedule.fire_at

        await self.fire(s)

        self.assertEqual(s._schedule.fire_at, armed + timedelta(days=1))
        s._store.async_clear_schedule.assert_not_awaited()

    async def test_repeat_with_weekdays_skips_to_the_next_allowed_day(self):
        """Exact dates, not just "an allowed weekday".

        From Wed 4 Mar 08:00 with Mon/Wed only, 07:00 today has passed, so the
        next allowed slot is Mon 9 Mar; firing that re-arms to Wed 11 Mar.
        Asserting only `weekday in [0, 2]` would pass for the wrong one.
        """
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 20, "min", repeat=True, days=[0, 2])
        self.assertEqual(s._schedule.fire_at, datetime(2026, 3, 9, 7, 0))   # Monday

        await self.fire(s)
        self.assertEqual(s._schedule.fire_at, datetime(2026, 3, 11, 7, 0))  # Wednesday

    async def test_callback_hands_off_to_the_event_loop(self):
        """_fired runs in HA's callback context, so it must not await inline."""
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 20, "min")

        s._schedule._fired(None)

        s.hass.async_create_task.assert_called_once()
        coro = s.hass.async_create_task.call_args.args[0]
        self.assertEqual(coro.__name__, "_async_fired")
        coro.close()          # never awaited; stop the "coroutine not awaited" warning


class CancelTestCase(ScheduleTestBase):

    async def test_cancel_clears_everything(self):
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 20, "min")
        await s.async_cancel_schedule()

        self.assertIsNone(s._schedule.fire_at)
        self.assertEqual(s._schedule.duration, 0.0)
        self.assertEqual(s._schedule.days, [])
        self.assertIsNone(s._schedule._unsub)
        s._store.async_clear_schedule.assert_awaited()

    async def test_cancelling_an_armed_schedule_is_logged(self):
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 20, "min")
        s._fire_logbook_event.reset_mock()

        await s.async_cancel_schedule()
        s._fire_logbook_event.assert_awaited_once()

    async def test_cancelling_nothing_writes_no_logbook_entry(self):
        """No schedule to describe, so the Activity feed stays quiet."""
        s = make_sensor()
        await s.async_cancel_schedule()

        s._fire_logbook_event.assert_not_awaited()
        s._store.async_clear_schedule.assert_awaited()


class RestoreTestCase(ScheduleTestBase):
    """Restart behaviour: what is re-armed, recomputed, or discarded."""

    async def test_no_stored_schedule_is_left_alone(self):
        """Deliberately does NOT clear: there is nothing to tear down."""
        s = make_sensor()
        await self.restore(s, {})
        s._store.async_clear_schedule.assert_not_awaited()

    async def test_schedule_without_fire_at_is_left_alone(self):
        s = make_sensor()
        await self.restore(s, {"schedule": {"duration": 5}})
        s._store.async_clear_schedule.assert_not_awaited()

    async def test_future_one_shot_is_rearmed_as_stored(self):
        s = make_sensor()
        fire_at = NOW + timedelta(hours=3)
        await self.restore(s, {"schedule": {
            "fire_at": fire_at.isoformat(), "duration": 15, "unit": "min"}})

        self.assertEqual(s._schedule.fire_at, fire_at)
        self.assertEqual(s._schedule.duration, 15)
        # Re-arming a stored one-shot must not rewrite storage.
        s._store.async_save_schedule.assert_not_awaited()

    async def test_missed_one_shot_is_discarded(self):
        """A bounded run hours late is wrong - drop it rather than fire it."""
        s = make_sensor()
        await self.restore(s, {"schedule": {
            "fire_at": (NOW - timedelta(hours=2)).isoformat(), "duration": 15}})

        self.assertIsNone(s._schedule.fire_at)
        s._store.async_clear_schedule.assert_awaited()
        s._log.warning.assert_called()

    async def test_recurring_is_recomputed_from_now_not_replayed(self):
        """A repeat armed days ago must jump forward, not fire immediately."""
        s = make_sensor()
        await self.restore(s, {"schedule": {
            "fire_at": (NOW - timedelta(days=3)).replace(hour=7, minute=0).isoformat(),
            "duration": 15, "unit": "min", "repeat": True, "days": []}})

        self.assertGreater(s._schedule.fire_at, NOW)
        self.assertEqual(s._schedule.fire_at.hour, 7)
        s._store.async_save_schedule.assert_awaited()

    async def test_malformed_fire_at_is_discarded(self):
        s = make_sensor()
        await self.restore(s, {"schedule": {"fire_at": "not-a-date"}})

        self.assertIsNone(s._schedule.fire_at)
        s._store.async_clear_schedule.assert_awaited()
        s._log.warning.assert_called()

    async def test_malformed_days_does_not_raise(self):
        """`"days": "MWF"` reaches `candidate.weekday() in days` and raises
        TypeError, which is caught outside the manager - so restoration AND the
        rest of _complete_initialization are skipped, every restart."""
        s = make_sensor()
        await self.restore(s, {"schedule": {
            "fire_at": (NOW + timedelta(hours=2)).isoformat(),
            "duration": 15, "repeat": True, "days": "MWF"}})

        self.assertIsNone(s._schedule.fire_at)

    async def test_a_truthy_string_does_not_promote_a_one_shot_to_recurring(self):
        """`"repeat": "false"` is truthy - it used to silently make the
        schedule repeat forever."""
        s = make_sensor()
        await self.restore(s, {"schedule": {
            "fire_at": (NOW + timedelta(hours=2)).isoformat(),
            "duration": 15, "repeat": "false"}})

        self.assertFalse(s._schedule.repeat)

    async def test_a_non_numeric_duration_is_not_armed(self):
        """It would arm happily and then fail when the timer starts."""
        s = make_sensor()
        await self.restore(s, {"schedule": {
            "fire_at": (NOW + timedelta(hours=2)).isoformat(), "duration": "5"}})

        self.assertIsNone(s._schedule.fire_at)

    async def test_a_timezone_naive_fire_at_does_not_raise(self):
        """Comparing a naive datetime against HA's aware now() raises
        TypeError. Only reachable from hand-edited storage, but it lands
        outside the parse guard."""
        s = make_sensor()
        aware_now = datetime(2026, 3, 4, 8, 0, tzinfo=timezone.utc)
        schedule_module.dt_util.now = lambda: aware_now
        schedule_module.dt_util.as_local = lambda d: d.replace(tzinfo=timezone.utc)

        await self.restore(s, {"schedule": {
            "fire_at": "2026-03-04T10:00:00", "duration": 15}})   # no offset

        self.assertIsNotNone(s._schedule.fire_at)

    async def test_null_days_survives_as_empty_list(self):
        """`days: None` must not become a None the weekday filter indexes."""
        s = make_sensor()
        await self.restore(s, {"schedule": {
            "fire_at": (NOW + timedelta(hours=2)).isoformat(),
            "repeat": True, "days": None}})
        self.assertEqual(s._schedule.days, [])


class FiringFailureTestCase(ScheduleTestBase):
    """What happens to the SCHEDULE when the timer it fires refuses to start.

    Deliberately not about the timer: a start that raised part-way can still
    leave the timer half-committed, which is persistence defect #4 and is not
    fixed here.
    """

    async def test_recurring_rearms_when_the_timer_fails_to_start(self):
        """CURRENT BEHAVIOUR IS A DEFECT (S2).

        The exception escapes _async_fired after _unsub was already cleared,
        so fire_at survives with no callback registered - the card reads
        'armed' and it never fires again. A transient start failure must not
        kill a daily schedule. Asserts the WANTED behaviour; fails today.
        """
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 30, "min", repeat=True)
        s.async_start_timer.side_effect = RuntimeError("storage unavailable")

        await self.fire(s)

        self.assertEqual(s._schedule.fire_at, datetime(2026, 3, 6, 7, 0))
        self.assertIs(s._schedule._unsub, self.unsub)
        s._store.async_save_schedule.assert_awaited()

    async def test_one_shot_clears_when_the_timer_fails_to_start(self):
        """Same defect (S2), one-shot half. The schedule is spent either way -
        it fired. Today the clear is skipped and fire_at survives."""
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 30, "min")
        s.async_start_timer.side_effect = RuntimeError("storage unavailable")

        await self.fire(s)

        self.assertIsNone(s._schedule.fire_at)
        s._store.async_clear_schedule.assert_awaited()

    async def test_the_start_failure_is_logged(self):
        """Swallowing is only acceptable because it is recorded - nothing
        upstack handles this; _async_fired runs as a detached task."""
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 30, "min")
        s.async_start_timer.side_effect = RuntimeError("storage unavailable")

        await self.fire(s)

        s._log.error.assert_called()


class ScheduleShutdownTestCase(ScheduleTestBase):

    async def test_a_firing_queued_before_shutdown_does_not_start_a_timer(self):
        """CURRENT BEHAVIOUR IS A DEFECT (S4).

        _fired() only enqueues; async_shutdown() disposes the tracker but
        cannot recall work already on the loop. So _async_fired can land after
        the entity was removed and command the switch on a dead sensor.
        Asserts the WANTED behaviour; fails today.
        """
        s = make_sensor()
        await s.async_schedule_timer(time(7, 0), 30, "min")

        s._schedule.async_shutdown()
        await self.fire(s)

        s.async_start_timer.assert_not_awaited()


class ConstructorWiringTestCase(unittest.TestCase):
    """Nothing else proves the real __init__ builds a manager over the store."""

    def test_sensor_constructor_wires_the_schedule_manager(self):
        load("timer_store").Store = lambda hass, version, key: MagicMock()

        entry = MagicMock()
        entry.entry_id = "abcdef123456"
        entry.title = "Boiler"
        entry.data = {"switch_entity_id": "switch.boiler", "reset_time": "00:00"}

        sensor = TimerRuntimeSensor(MagicMock(), entry)

        self.assertIsInstance(sensor._schedule, schedule_module.ScheduleManager)
        self.assertIs(sensor._schedule._store, sensor._store)
        self.assertFalse(sensor._schedule.is_armed)


if __name__ == "__main__":
    unittest.main()
