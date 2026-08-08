"""Characterization tests for notification dispatch.

Written BEFORE extracting Notifier, to pin what the sensor currently sends.
Deliberately weighted towards the failure paths - a happy-path-only suite is
what let a regression through in the TimerStore extraction.

The dispatch rules are not obvious from the call sites: a configured
"notification entity" is really a `domain.service` pair, and three domain
families are handled differently.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

sensor_module = load("sensor")
notify_module = load("notify")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor


def make_sensor(entities=None, title="Boiler", show_seconds=False):
    """A sensor wired to a real Notifier, so the delegation is exercised too."""
    s = object.__new__(TimerRuntimeSensor)
    s.hass = MagicMock()
    s.hass.services.async_call = AsyncMock()
    s._log = MagicMock()
    s._entry = MagicMock()
    s._entry.data = {
        "notification_entities": entities if entities is not None else [],
        "show_seconds": show_seconds,
    }
    s._entry.title = title
    s._notifier = notify_module.Notifier(s.hass, s._entry, s._log)
    return s


def calls_of(s):
    """(domain, service, data) for each service call made."""
    return [(c.args[0], c.args[1], c.args[2]) for c in s.hass.services.async_call.call_args_list]


class ConfigTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_reads_entities_and_show_seconds_from_the_config_entry(self):
        s = make_sensor(entities=["notify.phone"], show_seconds=True)
        self.assertEqual(await s._notifier.async_config(), (["notify.phone"], True))

    async def test_no_entities_still_reports_show_seconds(self):
        """show_seconds drives formatting even when nothing is notified."""
        s = make_sensor(entities=[], show_seconds=True)
        self.assertEqual(await s._notifier.async_config(), ([], True))


class DispatchTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_notify_service_gets_message_and_title(self):
        s = make_sensor(entities=["notify.mobile_app_x"])
        await s._send_notification("Timer was started for 30 minutes")

        self.assertEqual(calls_of(s), [
            ("notify", "mobile_app_x",
             {"message": "Timer was started for 30 minutes", "title": "Boiler"}),
        ])

    async def test_switchlike_domains_are_turned_on_instead(self):
        """input_boolean/switch/light are used as a signal, not a message sink."""
        for domain in ["input_boolean", "switch", "light"]:
            with self.subTest(domain=domain):
                s = make_sensor(entities=[f"{domain}.flag"])
                await s._send_notification("ignored")
                self.assertEqual(calls_of(s),
                                 [(domain, "turn_on", {"entity_id": f"{domain}.flag"})])

    async def test_input_button_is_pressed(self):
        s = make_sensor(entities=["input_button.ping"])
        await s._send_notification("ignored")
        self.assertEqual(calls_of(s),
                         [("input_button", "press", {"entity_id": "input_button.ping"})])

    async def test_nothing_configured_sends_nothing(self):
        s = make_sensor(entities=[])
        await s._send_notification("Timer finished")
        self.assertEqual(calls_of(s), [])

    async def test_every_configured_entity_is_notified(self):
        s = make_sensor(entities=["notify.a", "switch.b", "input_button.c"])
        await s._send_notification("hi")
        self.assertEqual(len(calls_of(s)), 3)


class TitleTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_underscores_become_spaces(self):
        """Telegram treats _ as markdown; an unescaped one breaks the message."""
        s = make_sensor(entities=["notify.phone"], title="Living_Room_Heater")
        await s._send_notification("hi")
        self.assertEqual(calls_of(s)[0][2]["title"], "Living Room Heater")

    async def test_falls_back_to_timer_when_untitled(self):
        s = make_sensor(entities=["notify.phone"], title="")
        s._entry.data["name"] = ""
        await s._send_notification("hi")
        self.assertEqual(calls_of(s)[0][2]["title"], "Timer")


class FailurePathTestCase(unittest.IsolatedAsyncioTestCase):
    """The half that actually matters: one bad target must not silence the rest."""

    async def test_entity_without_a_domain_is_skipped_and_warned(self):
        s = make_sensor(entities=["garbage"])
        await s._send_notification("hi")
        self.assertEqual(calls_of(s), [])
        s._log.warning.assert_called()

    async def test_a_malformed_entity_does_not_block_the_others(self):
        s = make_sensor(entities=["garbage", "notify.phone"])
        await s._send_notification("hi")
        self.assertEqual([c[0] for c in calls_of(s)], ["notify"])

    async def test_a_failing_service_call_does_not_block_the_others(self):
        s = make_sensor(entities=["notify.dead", "notify.alive"])

        async def flaky(domain, service, data):
            if service == "dead":
                raise RuntimeError("service unavailable")

        s.hass.services.async_call = AsyncMock(side_effect=flaky)
        await s._send_notification("hi")

        self.assertEqual([c[1] for c in calls_of(s)], ["dead", "alive"])
        s._log.error.assert_called()

    async def test_send_never_raises_at_the_top_level(self):
        """Callers fire notifications mid-timer-lifecycle and do not guard.

        Exercises the OUTER boundary specifically: a truthy but non-iterable
        target list blows up in the for-loop, which no per-target handler can
        catch. The previous version of this test raised inside a service call,
        which the per-target boundary already absorbed - it would have passed
        even with the outer try/except deleted.
        """
        s = make_sensor(entities=42)
        await s._send_notification("hi")        # must not raise
        s._log.error.assert_called()

    async def test_a_failing_target_still_lets_the_timer_continue(self):
        """Per-target failure is absorbed, so the caller sees a clean return."""
        s = make_sensor(entities=["notify.phone"])
        s.hass.services.async_call = AsyncMock(side_effect=RuntimeError("boom"))
        await s._send_notification("hi")        # must not raise
        s._log.error.assert_called()

    async def test_malformed_targets_are_rejected_not_truncated(self):
        """A target must be exactly `domain.service`, both parts non-empty.

        The dangerous case is the third one: it used to be truncated to
        `notify.mobile_app` and sent, silently invoking a DIFFERENT service
        than the one configured. Refusing and warning is diagnosable; guessing
        is not.
        """
        for bad in ["notify.mobile_app.extra", "notify.", ".service", "..",
                    "notify", "", "a.b.c.d"]:
            with self.subTest(target=bad):
                s = make_sensor(entities=[bad])
                await s._send_notification("hi")
                self.assertEqual(calls_of(s), [])
                s._log.warning.assert_called()

    async def test_wellformed_targets_still_go_through(self):
        """The validation must not reject anything that worked before."""
        for good, expected in [("notify.phone", ("notify", "phone")),
                               ("switch.flag", ("switch", "turn_on")),
                               ("input_button.ping", ("input_button", "press")),
                               ("notify.mobile_app_pixel_7", ("notify", "mobile_app_pixel_7"))]:
            with self.subTest(target=good):
                s = make_sensor(entities=[good])
                await s._send_notification("hi")
                self.assertEqual(calls_of(s)[0][:2], expected)

    async def test_a_malformed_target_does_not_block_a_valid_one(self):
        s = make_sensor(entities=["notify.a.b", "notify.phone"])
        await s._send_notification("hi")
        self.assertEqual([c[1] for c in calls_of(s)], ["phone"])


class LiveConfigTestCase(unittest.IsolatedAsyncioTestCase):
    """The Notifier holds `entry` and re-reads it, so options-flow edits apply
    without a reload. Previously asserted only by inspection."""

    async def test_targets_added_after_construction_are_used(self):
        """Replaces the whole mapping, as HA does.

        `async_update_entry` swaps entry.data for a new MappingProxyType on the
        same entry object; it does not mutate in place. Mutating the existing
        dict here would still pass if the Notifier had cached entry.data in
        __init__ - the cached reference would see the edit - so the test has to
        rebind the attribute to catch that.
        """
        s = make_sensor(entities=[])
        await s._send_notification("first")
        self.assertEqual(calls_of(s), [])

        s._entry.data = {**s._entry.data, "notification_entities": ["notify.phone"]}
        await s._send_notification("second")
        self.assertEqual(calls_of(s)[0][1], "phone")

    async def test_title_change_after_construction_is_picked_up(self):
        s = make_sensor(entities=["notify.phone"], title="Old")
        s._entry.title = "New Name"
        await s._send_notification("hi")
        self.assertEqual(calls_of(s)[0][2]["title"], "New Name")


class TitleFallbackMatrixTestCase(unittest.IsolatedAsyncioTestCase):
    """Full title/name matrix - the two duplicated copies this replaced were
    assumed identical, so pin the fallback chain explicitly."""

    async def _title(self, title, name):
        s = make_sensor(entities=["notify.phone"], title=title)
        s._entry.data["name"] = name
        await s._send_notification("hi")
        return calls_of(s)[0][2]["title"]

    async def test_title_wins_over_name(self):
        self.assertEqual(await self._title("Boiler", "ignored"), "Boiler")

    async def test_falls_back_to_data_name(self):
        for empty in ["", None]:
            with self.subTest(title=empty):
                self.assertEqual(await self._title(empty, "From Name"), "From Name")

    async def test_falls_back_to_timer_when_both_empty(self):
        for title in ["", None]:
            for name in ["", None]:
                with self.subTest(title=title, name=name):
                    self.assertEqual(await self._title(title, name), "Timer")


class ConstructorWiringTestCase(unittest.TestCase):
    """Every other test bypasses __init__, so nothing else proves the wiring."""

    def test_sensor_constructor_builds_a_notifier(self):
        timer_store_module = load("timer_store")
        timer_store_module.Store = lambda hass, version, key: MagicMock()

        entry = MagicMock()
        entry.entry_id = "abcdef123456"
        entry.title = "Boiler"
        entry.data = {"switch_entity_id": "switch.boiler", "reset_time": "00:00"}

        sensor = TimerRuntimeSensor(MagicMock(), entry)
        self.assertIsInstance(sensor._notifier, notify_module.Notifier)


class DelegationTestCase(unittest.IsolatedAsyncioTestCase):
    """__init__.py's test_notification service handler calls this on the sensor."""

    async def test_sensor_send_notification_still_reaches_the_targets(self):
        s = make_sensor(entities=["notify.phone"])
        await s._send_notification("Test notification")
        self.assertEqual(calls_of(s)[0][2]["message"], "Test notification")


if __name__ == "__main__":
    unittest.main()
