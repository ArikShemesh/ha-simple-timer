"""Characterization tests for the .storage payload.

Written BEFORE extracting TimerStore, to pin what the sensor currently writes.
The stored keys are a wire format: a restart reads them back, so a renamed or
dropped key does not fail a test, it silently loses a running timer on the next
HA restart. Every assertion here is "what it does today", not "what would be
nice" - if the refactor changes one, that is the signal to stop and look.
"""
import copy
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

sensor_module = load("sensor")
timer_store_module = load("timer_store")
schedule_module = load("schedule")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor

NOW = datetime(2026, 3, 1, 8, 0, 0)


class FakeStore:
    """In-memory stand-in for homeassistant.helpers.storage.Store."""

    def __init__(self, hass=None, version=None, key=None, initial=None):
        self.hass, self.version, self.key = hass, version, key
        self.data = copy.deepcopy(initial) if initial else None
        self.saves = []
        self.load_error = None

    async def async_load(self):
        if self.load_error:
            raise self.load_error
        return copy.deepcopy(self.data)

    async def async_save(self, data):
        self.data = copy.deepcopy(data)
        self.saves.append(copy.deepcopy(data))


def make_sensor(stored=None):
    """A TimerRuntimeSensor with only what the storage paths touch."""
    s = object.__new__(TimerRuntimeSensor)
    s.hass = MagicMock()
    s._entry = MagicMock()
    s._entry.data = {}
    s._entry_id = "entry123"
    s._log = MagicMock()
    # Real TimerStore over a fake Store, so the sensor -> TimerStore -> Store
    # wiring is exercised and assertions still see the raw payload.
    v1 = FakeStore()
    def _store_factory(hass, version, key):
        return v1 if version == 1 else FakeStore(hass, version, key, initial=stored)
    timer_store_module.Store = _store_factory
    s._store = timer_store_module.TimerStore(s.hass, "entry123", s._log)
    s.fake = s._store._store
    s.fake_v1 = v1

    s._switch_entity_id = "switch.boiler"
    s._timer_state = "idle"
    # Real __init__ always sets this; async_start_timer's removal guard reads it.
    s._stop_event_received = False
    s._timer_finishes_at = None
    s._timer_duration = 0
    s._timer_start_moment = None
    s._timer_reverse_mode = False
    s._timer_unsub = None
    s._timer_update_task = None
    s._runtime_at_timer_start = 0
    s._timer_start_method = None
    s._watchdog_message = None
    s._state = 0.0
    s._last_on_timestamp = None
    s._next_reset_date = None

    # Everything the timer paths call that is not storage.
    s.async_write_ha_state = MagicMock()
    s._stop_timer_update_task = AsyncMock()
    s._start_timer_update_task = AsyncMock()
    s._async_setup_switch_listener = AsyncMock()
    s._start_realtime_accumulation = AsyncMock()
    s._stop_realtime_accumulation = AsyncMock()
    s._send_notification = AsyncMock()
    s._notifier = MagicMock()
    s._notifier.async_config = AsyncMock(return_value=([], False))
    s._fire_logbook_event = AsyncMock()
    s._schedule = schedule_module.ScheduleManager(
        s.hass, store=s._store, start_timer=AsyncMock(),
        write_state=s.async_write_ha_state, fire_logbook=s._fire_logbook_event,
        log=s._log,
    )
    s._switch = MagicMock()
    s._switch.is_on = MagicMock(return_value=True)
    s._switch.async_ensure = AsyncMock()
    s._switch.async_command = AsyncMock()
    s._switch.async_ensure_with_retries = AsyncMock()
    s.hass.services.async_call = AsyncMock()
    return s


class StorageKeysTestCase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        sensor_module.dt_util.utcnow = lambda: NOW
        sensor_module.async_track_point_in_utc_time = MagicMock(return_value=MagicMock())

    async def test_start_timer_writes_the_five_timer_keys(self):
        """The payload a restart needs to rebuild a running timer."""
        s = make_sensor()
        await s.async_start_timer(30, "min", reverse_mode=False)

        self.assertEqual(
            set(s.fake.data),
            {"finishes_at", "duration", "timer_start", "runtime_at_start", "reverse_mode"},
        )
        self.assertEqual(s.fake.data["duration"], 30.0)
        self.assertEqual(s.fake.data["timer_start"], NOW.isoformat())
        self.assertEqual(s.fake.data["finishes_at"], (NOW + timedelta(minutes=30)).isoformat())
        self.assertEqual(s.fake.data["reverse_mode"], False)
        self.assertEqual(s.fake.data["runtime_at_start"], 0.0)

    async def test_start_timer_preserves_unrelated_keys(self):
        """Starting a timer must not wipe the reset date or an armed schedule."""
        s = make_sensor(stored={"next_reset_date": "2026-03-02T00:00:00",
                                "schedule": {"fire_at": "2026-03-02T07:00:00"}})
        await s.async_start_timer(5, "min")

        self.assertEqual(s.fake.data["next_reset_date"], "2026-03-02T00:00:00")
        self.assertEqual(s.fake.data["schedule"], {"fire_at": "2026-03-02T07:00:00"})

    async def test_add_timer_touches_only_finishes_at_and_duration(self):
        """An extension must not rewrite timer_start or runtime_at_start."""
        s = make_sensor()
        await s.async_start_timer(10, "min")
        before = copy.deepcopy(s.fake.data)

        s._timer_state = "active"
        await s.async_add_timer(5, "min")
        after = s.fake.data

        self.assertEqual(after["timer_start"], before["timer_start"])
        self.assertEqual(after["runtime_at_start"], before["runtime_at_start"])
        self.assertEqual(after["reverse_mode"], before["reverse_mode"])
        self.assertEqual(after["duration"], 15.0)
        self.assertEqual(after["finishes_at"], (NOW + timedelta(minutes=15)).isoformat())

    async def test_cleanup_clears_four_keys_but_keeps_reverse_mode(self):
        """reverse_mode deliberately survives: cancel reads it AFTER cleanup."""
        s = make_sensor()
        await s.async_start_timer(10, "min", reverse_mode=True)
        s._timer_unsub = None

        await s._cleanup_timer_state()

        self.assertNotIn("finishes_at", s.fake.data)
        self.assertNotIn("duration", s.fake.data)
        self.assertNotIn("timer_start", s.fake.data)
        self.assertNotIn("runtime_at_start", s.fake.data)
        self.assertEqual(s.fake.data["reverse_mode"], True)

    async def test_save_schedule_shape(self):
        s = make_sensor()
        s._schedule._fire_at = NOW + timedelta(hours=3)
        s._schedule._duration = 45.0
        s._schedule._unit = "min"
        s._schedule._repeat = True
        s._schedule._days = [0, 2, 4]

        await s._schedule._async_save()

        self.assertEqual(s.fake.data["schedule"], {
            "fire_at": (NOW + timedelta(hours=3)).isoformat(),
            "duration": 45.0,
            "unit": "min",
            "repeat": True,
            "days": [0, 2, 4],
        })

    async def test_clear_schedule_removes_only_schedule(self):
        s = make_sensor(stored={"schedule": {"fire_at": "x"}, "next_reset_date": "keep"})
        await s._schedule.async_clear()

        self.assertNotIn("schedule", s.fake.data)
        self.assertEqual(s.fake.data["next_reset_date"], "keep")

    async def test_clear_schedule_skips_the_write_when_nothing_armed(self):
        """Avoids a pointless .storage write on every idle teardown."""
        s = make_sensor(stored={"next_reset_date": "keep"})
        await s._schedule.async_clear()
        self.assertEqual(s.fake.saves, [])

    async def test_save_next_reset_date(self):
        s = make_sensor(stored={"reverse_mode": True})
        s._next_reset_date = NOW + timedelta(days=1)
        await s._save_next_reset_date()

        self.assertEqual(s.fake.data["next_reset_date"], (NOW + timedelta(days=1)).isoformat())
        self.assertEqual(s.fake.data["reverse_mode"], True)

    async def test_full_payload_is_json_serializable(self):
        """Store writes JSON - a datetime or set here would break at runtime."""
        import json
        s = make_sensor()
        await s.async_start_timer(30, "min")
        s._next_reset_date = NOW + timedelta(days=1)
        await s._save_next_reset_date()
        s._schedule._fire_at = NOW + timedelta(hours=2)
        await s._schedule._async_save()

        json.dumps(s.fake.data)  # raises if any value is not JSON-native


class StorageErrorPolicyTestCase(unittest.IsolatedAsyncioTestCase):
    """Which storage failures are swallowed and which propagate, as of today."""

    def setUp(self):
        sensor_module.dt_util.utcnow = lambda: NOW
        sensor_module.async_track_point_in_utc_time = MagicMock(return_value=MagicMock())

    async def test_save_next_reset_date_swallows(self):
        s = make_sensor()
        s._next_reset_date = NOW
        s.fake.load_error = OSError("disk gone")
        await s._save_next_reset_date()          # must not raise
        s._log.error.assert_called()

    async def test_cleanup_swallows(self):
        s = make_sensor()
        s.fake.load_error = OSError("disk gone")
        await s._cleanup_timer_state()           # must not raise
        s._log.warning.assert_called()

    async def test_save_and_clear_schedule_swallow(self):
        for method in ("_async_save", "async_clear"):
            with self.subTest(method=method):
                s = make_sensor()
                s.fake.load_error = OSError("disk gone")
                await getattr(s._schedule, method)()   # must not raise
                s._log.warning.assert_called()

    async def test_start_timer_does_NOT_swallow(self):
        """Inconsistent with every other site - start/add have no try/except."""
        s = make_sensor()
        s.fake.load_error = OSError("disk gone")
        with self.assertRaises(OSError):
            await s.async_start_timer(10, "min")

    async def test_add_timer_does_NOT_swallow(self):
        s = make_sensor()
        await s.async_start_timer(10, "min")
        s._timer_state = "active"
        s.fake.load_error = OSError("disk gone")
        with self.assertRaises(OSError):
            await s.async_add_timer(5, "min")


class MalformedPayloadTestCase(unittest.IsolatedAsyncioTestCase):
    """A corrupt stored value must not escape the restore paths.

    These run before the timer's completion callback is armed, so an exception
    here leaves the sensor "active" with nothing scheduled to finish it - the
    timer never fires and the switch is never turned off.
    """

    def setUp(self):
        sensor_module.dt_util.utcnow = lambda: NOW
        sensor_module.async_track_point_in_utc_time = MagicMock(return_value=MagicMock())

    async def test_restore_active_timer_survives_malformed_timer_start(self):
        s = make_sensor(stored={"timer_start": "not-a-date", "duration": 30,
                                "runtime_at_start": 120, "reverse_mode": False})
        s._timer_state = "active"
        s._timer_finishes_at = NOW + timedelta(minutes=10)
        s.async_get_last_state = AsyncMock(return_value=None)
        s._ensure_switch_state = AsyncMock()

        await s._restore_active_timer(NOW)          # must not raise

        self.assertIsNone(s._timer_start_moment)
        # The rest of the payload is still applied.
        self.assertEqual(s._runtime_at_timer_start, 120)
        self.assertEqual(s._timer_duration, 30)

    async def test_malformed_reverse_mode_cannot_turn_the_switch_on(self):
        """The whole point of the sanitizer.

        "yes" is truthy. Before validation it sent the expired-timer path down
        the reverse branch, which calls turn_on - a corrupt storage file could
        switch the device on during startup. It must now fall back to a normal
        expired timer, which turns the switch OFF.
        """
        s = make_sensor(stored={"reverse_mode": "yes", "duration": 10})
        s._cleanup_timer_state = AsyncMock()
        sensor_module.asyncio.sleep = AsyncMock()

        await s._handle_expired_timer()

        self.assertFalse(s._timer_reverse_mode)
        desired_states = [c.args[0] for c in s._switch.async_ensure_with_retries.call_args_list]
        self.assertIn("off", desired_states)
        self.assertNotIn("on", desired_states)

    async def test_malformed_schedule_does_not_abort_initialization(self):
        """A truthy non-dict schedule used to raise AttributeError out of
        _restore_schedule, skipping accumulation start and the final state
        write, and repeating on every restart."""
        s = make_sensor(stored={"schedule": "bad"})
        storage_data = await s._store.async_read()

        await s._schedule.async_restore(storage_data)     # must not raise

        self.assertIsNone(s._schedule.fire_at)


class SanitizerTestCase(unittest.IsolatedAsyncioTestCase):
    """Type validation on read. Malformed values are dropped, not trusted."""

    async def _read(self, stored):
        return await make_sensor(stored=stored)._store.async_read()

    async def test_malformed_values_are_dropped(self):
        for key, bad in [("reverse_mode", "yes"), ("reverse_mode", 1),
                         ("duration", "30"), ("runtime_at_start", "nonsense"),
                         ("finishes_at", 12345), ("timer_start", []),
                         ("next_reset_date", 7), ("schedule", "bad")]:
            with self.subTest(key=key, bad=bad):
                self.assertNotIn(key, await self._read({key: bad}))

    async def test_wellformed_values_survive_untouched(self):
        good = {
            "finishes_at": "2026-03-01T09:00:00",
            "timer_start": "2026-03-01T08:00:00",
            "next_reset_date": "2026-03-02T00:00:00",
            "duration": 30.5,
            "runtime_at_start": 120,
            "reverse_mode": True,
            "schedule": {"fire_at": None, "duration": 5},
        }
        self.assertEqual(await self._read(good), good)

    async def test_reverse_mode_false_survives(self):
        """False is well-formed; it must not be mistaken for a missing key."""
        self.assertEqual(await self._read({"reverse_mode": False}), {"reverse_mode": False})

    async def test_none_always_survives(self):
        """None means unset. The v1 migration writes next_reset_date: None."""
        for key in ["finishes_at", "duration", "reverse_mode", "schedule", "next_reset_date"]:
            with self.subTest(key=key):
                self.assertEqual(await self._read({key: None}), {key: None})

    async def test_booleans_are_not_accepted_as_numbers(self):
        """bool subclasses int, so a naive isinstance check would let True through."""
        self.assertNotIn("duration", await self._read({"duration": True}))
        self.assertNotIn("runtime_at_start", await self._read({"runtime_at_start": False}))

    async def test_unknown_keys_pass_through(self):
        """A newer version's data must survive being read by an older one."""
        self.assertEqual(await self._read({"future_key": {"x": 1}}), {"future_key": {"x": 1}})

    async def test_dropping_a_value_is_logged(self):
        s = make_sensor(stored={"reverse_mode": "yes"})
        await s._store.async_read()
        self.assertTrue(any("reverse_mode" in str(c) for c in s._log.warning.call_args_list))

class StorageWiringTestCase(unittest.IsolatedAsyncioTestCase):
    """The other tests bypass __init__, so nothing else checks the real wiring."""

    def test_constructor_builds_a_store_with_the_expected_key_and_version(self):
        captured = {}

        def _factory(hass, version, key):
            captured.update(version=version, key=key)
            return FakeStore(hass, version, key)

        timer_store_module.Store = _factory
        entry = MagicMock()
        entry.entry_id = "abcdef123456"
        entry.title = "Boiler"
        entry.data = {"switch_entity_id": "switch.boiler", "reset_time": "00:00"}

        sensor = TimerRuntimeSensor(MagicMock(), entry)

        self.assertIsInstance(sensor._store, timer_store_module.TimerStore)
        self.assertEqual(captured["version"], 2)
        self.assertEqual(captured["key"], "simple_timer_abcdef123456")


class StorageMigrationTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_v1_payload_is_migrated_with_a_null_reset_date(self):
        s = make_sensor()
        s.fake.load_error = NotImplementedError("no migration func")
        s.fake_v1.data = {"finishes_at": "2026-03-01T09:00:00", "duration": 60}

        data = await s._load_storage_data()

        self.assertEqual(data["finishes_at"], "2026-03-01T09:00:00")
        self.assertEqual(data["duration"], 60)
        self.assertIsNone(data["next_reset_date"])
        self.assertEqual(s.fake.saves[-1], data)

    async def test_missing_storage_yields_empty_dict(self):
        s = make_sensor()
        self.assertEqual(await s._load_storage_data(), {})

    async def test_load_failure_yields_empty_dict(self):
        s = make_sensor()
        s.fake.load_error = OSError("disk gone")
        self.assertEqual(await s._load_storage_data(), {})
        s._log.error.assert_called()


if __name__ == "__main__":
    unittest.main()
