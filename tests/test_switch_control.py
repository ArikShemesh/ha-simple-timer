"""Characterization tests for switch commanding.

Written BEFORE extracting SwitchController, to pin current behaviour.

This is the code that actually moves the user's boiler, and it is the least
obvious in the project: a blocking attempt with a poll loop, then a detached
background chain that re-checks on a backoff and re-commands. Two rules in
there are load-bearing and easy to lose in a refactor:

* the retry chain aborts a pending turn-OFF if a new timer has started, so it
  cannot fight a user who just pressed start;
* `force` makes the FIRST retry re-command even when HA already reports the
  desired state, which is what recovers from a stale state after a restart.

Weighted to those and to the failure paths rather than the happy path.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

sensor_module = load("sensor")
switch_module = load("switch_control")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor


class FakeTask:
    """Stands in for the asyncio.Task hass.async_create_task returns.

    The controller retains its retry tasks so removal can cancel them, so the
    fake has to expose the task API. `_spawned` still collects the raw
    coroutines, so every existing test drives the chain exactly as before.

    Two known divergences from a real asyncio.Task, neither of which any
    assertion here depends on: done callbacks fire synchronously inside
    cancel() rather than after cancellation completes, and a task never
    reaches "done", so _tasks only ever drains via async_shutdown's clear().
    """

    def __init__(self, coro):
        self.coro = coro
        self.cancelled = False
        self._done_callbacks = []

    def add_done_callback(self, cb):
        self._done_callbacks.append(cb)

    def cancel(self):
        self.cancelled = True
        for cb in self._done_callbacks:
            cb(self)


def make_sensor(switch_state="off", entity="switch.boiler", turn_on_option=None):
    s = object.__new__(TimerRuntimeSensor)
    # What "on" means for the configured device. None for every switch-like
    # domain; an hvac mode for climate. Held on the fixture rather than passed
    # by value so a test can change it mid-flight, which is how the spawn-time
    # capture gets pinned.
    s._turn_on_option = turn_on_option
    s.hass = MagicMock()
    s.hass.services.async_call = AsyncMock()
    s._log = MagicMock()
    s._switch_entity_id = entity
    s._timer_state = "idle"
    # Real __init__ always sets this; async_start_timer's removal guard reads it.
    s._stop_event_received = False
    s._send_notification = AsyncMock()

    s._states = {}
    if switch_state is not None and entity:
        st = MagicMock()
        st.state = switch_state
        s._states[entity] = st
    s.hass.states.get = lambda eid: s._states.get(eid)

    # Detached retries are captured rather than run, so a test drives them
    # deliberately instead of a background chain running away.
    s._spawned = []

    def _create_task(coro):
        s._spawned.append(coro)
        return FakeTask(coro)

    s.hass.async_create_task = _create_task

    s._switch = switch_module.SwitchController(
        s.hass, lambda: s._switch_entity_id,
        notify=s._send_notification,
        is_timer_active=lambda: s._timer_state == "active",
        get_turn_on_option=lambda: s._turn_on_option,
        log=s._log,
    )
    return s


def set_state(s, value, entity="switch.boiler"):
    st = MagicMock()
    st.state = value
    s._states[entity] = st


def calls_of(s):
    """(domain, service, data) per call. Use full_calls_of for blocking/context."""
    return [(c.args[0], c.args[1], c.args[2]) for c in s.hass.services.async_call.call_args_list]


def full_calls_of(s):
    """(domain, service, data, blocking, context) - kwargs included.

    calls_of() drops kwargs, so on its own it cannot see a changed `blocking`
    or a dropped `context`.
    """
    return [(c.args[0], c.args[1], c.args[2],
             c.kwargs.get("blocking"), c.kwargs.get("context"))
            for c in s.hass.services.async_call.call_args_list]


def drop_spawned(s):
    """Close captured coroutines so Python does not warn about them."""
    for coro in s._spawned:
        coro.close()
    s._spawned.clear()


class EnsureStateTestCase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.slept = []

        async def fake_sleep(seconds):
            self.slept.append(seconds)

        # Restore it: asyncio is a shared module object, so leaving the patch
        # in place makes later unrelated tests skip their real waits.
        original = switch_module.asyncio.sleep
        self.addCleanup(lambda: setattr(switch_module.asyncio, "sleep", original))
        switch_module.asyncio.sleep = fake_sleep

    async def test_no_switch_configured_does_nothing(self):
        s = make_sensor(entity=None)
        await s._switch.async_ensure("on", "test")
        self.assertEqual(calls_of(s), [])

    async def test_a_configured_entity_with_no_state_is_still_commanded(self):
        """A configured switch that HA has no state for is still commanded.

        It used to return silently - no command, no warning, no notification -
        so a timer expiring while the switch's integration was reloading would
        report "Timer was turned off" with the boiler still on. Absent state is
        exactly when a command matters most; the old behaviour optimised for
        the wrong case.
        """
        s = make_sensor(switch_state=None)
        await s._switch.async_ensure("off", "Timer completion turn-off")

        self.assertEqual(calls_of(s)[0][:2], ("homeassistant", "turn_off"))

    async def test_a_switch_with_no_state_that_never_reports_back_warns(self):
        """Commanding blind is not enough - the user must hear if it failed."""
        s = make_sensor(switch_state=None)
        await s._switch.async_ensure("off", "Timer completion turn-off")

        s._log.warning.assert_called()
        s._send_notification.assert_awaited_once()

    async def test_no_switch_configured_is_still_a_no_op(self):
        """Nothing configured is a different case from configured-but-absent."""
        s = make_sensor(entity=None)
        await s._switch.async_ensure("off", "test")
        self.assertEqual(calls_of(s), [])

    async def test_already_correct_is_left_alone(self):
        s = make_sensor(switch_state="on")
        await s._switch.async_ensure("on", "test")
        self.assertEqual(calls_of(s), [])

    async def test_force_commands_even_when_already_correct(self):
        """Recovers from a stale HA state after a restart."""
        s = make_sensor(switch_state="on")
        await s._switch.async_ensure("on", "test", force=True)
        self.assertEqual(calls_of(s)[0][:2], ("homeassistant", "turn_on"))

    async def test_mismatch_commands_the_switch(self):
        s = make_sensor(switch_state="off")
        await s._switch.async_ensure("on", "test")
        self.assertEqual(calls_of(s),
                         [("homeassistant", "turn_on", {"entity_id": "switch.boiler"})])

    async def test_desired_off_maps_to_turn_off(self):
        s = make_sensor(switch_state="on")
        await s._switch.async_ensure("off", "test")
        self.assertEqual(calls_of(s)[0][1], "turn_off")

    async def test_context_is_forwarded_for_attribution(self):
        """The logbook names the acting user from this."""
        s = make_sensor(switch_state="off")
        ctx = object()
        await s._switch.async_ensure("on", "test", context=ctx)
        self.assertIs(s.hass.services.async_call.call_args.kwargs["context"], ctx)

    async def test_polls_with_growing_waits_until_the_state_lands(self):
        s = make_sensor(switch_state="off")

        async def slow(seconds):
            self.slept.append(seconds)
            if len(self.slept) == 2:        # arrives on the second poll
                set_state(s, "on")

        switch_module.asyncio.sleep = slow
        await s._switch.async_ensure("on", "test")

        self.assertEqual(self.slept, [1.0, 2.0])
        s._send_notification.assert_not_awaited()

    async def test_a_switch_that_never_lands_warns_and_notifies(self):
        s = make_sensor(switch_state="off")
        await s._switch.async_ensure("on", "test")

        self.assertEqual(self.slept, [1.0, 2.0, 3.0])
        # The log keeps the internal detail; the notification is read by a
        # person, and often spoken aloud by a voice assistant.
        self.assertIn("Check switch connectivity", s._log.warning.call_args.args[0])
        s._send_notification.assert_awaited_once()
        self.assertEqual(
            s._send_notification.await_args.args[0],
            "Warning: tried to turn the device ON but it is still OFF. "
            "Please check the switch connectivity.",
        )

    async def test_an_unreachable_switch_is_reported_by_its_real_state(self):
        """Saying "still OFF" about an unavailable switch would be a guess."""
        s = make_sensor(switch_state="unavailable")
        await s._switch.async_ensure("on", "test")

        self.assertEqual(
            s._send_notification.await_args.args[0],
            "Warning: tried to turn the device ON but it is reporting "
            "unavailable. Please check the switch connectivity.",
        )

    async def test_a_failing_service_call_warns_and_never_raises(self):
        s = make_sensor(switch_state="off")
        s.hass.services.async_call = AsyncMock(side_effect=RuntimeError("boom"))

        await s._switch.async_ensure("on", "test")     # must not raise

        # The exception text is for the log. A notification carrying a Python
        # error is noise to the user and gibberish to an assistant reading it.
        self.assertIn("boom", s._log.warning.call_args.args[0])
        s._send_notification.assert_awaited_once()
        self.assertEqual(
            s._send_notification.await_args.args[0],
            "Warning: failed to turn the device ON. Please check the switch.",
        )


class RetryChainTestCase(unittest.IsolatedAsyncioTestCase):
    """The detached background chain - where a bug keeps commanding a device."""

    def setUp(self):
        self.slept = []

        async def fake_sleep(seconds):
            self.slept.append(seconds)

        # Restore it: asyncio is a shared module object, so leaving the patch
        # in place makes later unrelated tests skip their real waits.
        original = switch_module.asyncio.sleep
        self.addCleanup(lambda: setattr(switch_module.asyncio, "sleep", original))
        switch_module.asyncio.sleep = fake_sleep

    async def test_with_retries_makes_a_blocking_attempt_then_spawns_one(self):
        s = make_sensor(switch_state="off")
        await s._switch.async_ensure_with_retries("on", "test")

        self.assertEqual(calls_of(s)[0][1], "turn_on")
        self.assertEqual(len(s._spawned), 1)
        drop_spawned(s)

    async def test_with_retries_still_spawns_when_the_first_attempt_raises(self):
        """The background chain is the recovery path; it must not be skipped."""
        s = make_sensor(switch_state="off")
        s._switch.async_ensure = AsyncMock(side_effect=RuntimeError("boom"))

        await s._switch.async_ensure_with_retries("on", "test")

        self.assertEqual(len(s._spawned), 1)
        s._log.warning.assert_called()
        drop_spawned(s)

    async def test_no_switch_configured_spawns_nothing(self):
        s = make_sensor(entity=None)
        await s._switch.async_ensure_with_retries("on", "test")
        self.assertEqual(s._spawned, [])

    async def test_backoff_schedule(self):
        s = make_sensor(switch_state="on")
        for attempt, expected in [(1, 2), (2, 5), (3, 10), (4, 20)]:
            with self.subTest(attempt=attempt):
                self.slept.clear()
                await s._switch._async_verify_and_retry("on", "switch.boiler", attempt=attempt)
                self.assertEqual(self.slept, [expected])
        drop_spawned(s)

    async def test_the_chain_stops_after_the_last_delay(self):
        s = make_sensor(switch_state="off")
        await s._switch._async_verify_and_retry("on", "switch.boiler", attempt=5)
        self.assertEqual(self.slept, [])
        self.assertEqual(calls_of(s), [])
        self.assertEqual(s._spawned, [])

    async def test_a_pending_turn_off_aborts_once_a_timer_is_running(self):
        """The timer must be able to start DURING the backoff wait.

        An earlier version set _timer_state before invoking, which proved
        nothing about ordering - moving the abort check above the sleep would
        have passed it, reopening exactly the race this rule exists to close.
        """
        s = make_sensor(switch_state="on")

        async def timer_starts_while_we_wait(seconds):
            self.slept.append(seconds)
            s._timer_state = "active"

        switch_module.asyncio.sleep = timer_starts_while_we_wait

        await s._switch._async_verify_and_retry("off", "switch.boiler")

        self.assertEqual(self.slept, [2])        # it really did wait first
        self.assertEqual(calls_of(s), [])
        self.assertEqual(s._spawned, [])

    async def test_a_pending_turn_on_is_not_aborted_by_a_running_timer(self):
        """The abort is deliberately one-directional."""
        s = make_sensor(switch_state="off")
        s._timer_state = "active"

        await s._switch._async_verify_and_retry("on", "switch.boiler")

        self.assertEqual(calls_of(s)[0][1], "turn_on")
        drop_spawned(s)

    async def test_matching_state_ends_the_chain(self):
        s = make_sensor(switch_state="on")
        await s._switch._async_verify_and_retry("on", "switch.boiler")

        self.assertEqual(calls_of(s), [])
        self.assertEqual(s._spawned, [])

    async def test_force_recommands_on_the_first_retry_despite_a_match(self):
        s = make_sensor(switch_state="on")
        await s._switch._async_verify_and_retry("on", "switch.boiler", attempt=1, force=True)

        self.assertEqual(calls_of(s)[0][1], "turn_on")
        drop_spawned(s)

    async def test_force_stops_overriding_after_the_first_retry(self):
        s = make_sensor(switch_state="on")
        await s._switch._async_verify_and_retry("on", "switch.boiler", attempt=2, force=True)

        self.assertEqual(calls_of(s), [])
        self.assertEqual(s._spawned, [])

    async def test_a_missing_entity_retries_without_commanding(self):
        s = make_sensor(switch_state=None)
        await s._switch._async_verify_and_retry("on", "switch.boiler")

        self.assertEqual(calls_of(s), [])
        self.assertEqual(len(s._spawned), 1)
        drop_spawned(s)

    async def test_a_mismatch_recommands_and_chains(self):
        s = make_sensor(switch_state="off")
        await s._switch._async_verify_and_retry("on", "switch.boiler")

        self.assertEqual(calls_of(s)[0][1], "turn_on")
        self.assertEqual(len(s._spawned), 1)
        s._log.warning.assert_called()
        drop_spawned(s)

    async def test_a_failing_retry_still_chains(self):
        s = make_sensor(switch_state="off")
        s.hass.services.async_call = AsyncMock(side_effect=RuntimeError("nope"))

        await s._switch._async_verify_and_retry("on", "switch.boiler")

        self.assertEqual(len(s._spawned), 1)
        drop_spawned(s)


class CallSiteContractTestCase(unittest.IsolatedAsyncioTestCase):
    """The sensor's own call sites, end to end through a real controller.

    The controller tests all call async_command directly, so a wrong `blocking`
    or a dropped `context` at a sensor call site would survive every one of
    them. `context` is what the logbook uses to name the acting user, and
    `blocking=False` on start is deliberate - the timer must not wait on a slow
    switch integration.
    """

    def setUp(self):
        async def instant(seconds):
            pass

        original = switch_module.asyncio.sleep
        self.addCleanup(lambda: setattr(switch_module.asyncio, "sleep", original))
        switch_module.asyncio.sleep = instant
        sensor_module.dt_util.utcnow = lambda: __import__("datetime").datetime(2026, 3, 1, 8, 0)
        sensor_module.async_track_point_in_utc_time = MagicMock(return_value=MagicMock())

    def _timer_sensor(self):
        s = make_sensor(switch_state="off")
        s._entry = MagicMock()
        s._entry.data = {}
        s._log = MagicMock()
        s._timer_finishes_at = None
        s._timer_duration = 0
        s._timer_start_moment = None
        s._timer_reverse_mode = False
        s._timer_unsub = None
        s._runtime_at_timer_start = 0
        s._timer_start_method = None
        s._watchdog_message = None
        s._state = 0.0
        s._last_on_timestamp = None
        s._store = MagicMock()
        s._store.async_save_timer = AsyncMock()
        s._store.async_clear_timer = AsyncMock()
        s._notifier = MagicMock()
        s._notifier.async_config = AsyncMock(return_value=([], False))
        s.async_write_ha_state = MagicMock()
        s._stop_timer_update_task = AsyncMock()
        s._start_timer_update_task = AsyncMock()
        s._async_setup_switch_listener = AsyncMock()
        s._start_realtime_accumulation = AsyncMock()
        s._stop_realtime_accumulation = AsyncMock()
        s._fire_logbook_event = AsyncMock()
        return s

    async def test_start_timer_turns_on_without_blocking_and_forwards_context(self):
        s = self._timer_sensor()
        ctx = object()

        await s.async_start_timer(30, "min", context=ctx)

        domain, service, data, blocking, context = full_calls_of(s)[0]
        self.assertEqual((domain, service), ("homeassistant", "turn_on"))
        self.assertEqual(data, {"entity_id": "switch.boiler"})
        self.assertFalse(blocking)          # must not wait on a slow switch
        self.assertIs(context, ctx)         # logbook attribution

    async def test_cancel_turns_off_blocking_and_forwards_context(self):
        s = self._timer_sensor()
        s._timer_state = "active"
        s._timer_start_moment = sensor_module.dt_util.utcnow()
        ctx = object()

        await s.async_cancel_timer(context=ctx)

        domain, service, data, blocking, context = full_calls_of(s)[0]
        self.assertEqual((domain, service), ("homeassistant", "turn_off"))
        self.assertTrue(blocking)
        self.assertIs(context, ctx)


class EntityIdSyncTestCase(unittest.IsolatedAsyncioTestCase):
    """One source of truth: the controller reads the sensor's id, never a copy.

    Guards a regression where the sensor updated _switch_entity_id in three
    places but only one of them mirrored it onto the controller, leaving the
    controller commanding the OLD switch.
    """

    def test_controller_follows_every_reassignment(self):
        s = make_sensor()
        for new_id in ["switch.b", "switch.c", None]:
            with self.subTest(new_id=new_id):
                s._switch_entity_id = new_id
                self.assertEqual(s._switch.entity_id, new_id)

    async def test_commands_target_the_current_switch(self):
        s = make_sensor(switch_state="off")
        s._switch_entity_id = "switch.other"
        await s._switch.async_command("on")
        self.assertEqual(calls_of(s)[0][2], {"entity_id": "switch.other"})

    async def test_command_with_no_entity_still_reaches_ha(self):
        """Fail loud. A silent no-op would let a timer start believing the
        device was switched on."""
        s = make_sensor(entity=None)
        await s._switch.async_command("on")
        self.assertEqual(len(calls_of(s)), 1)


class IsSwitchOnTestCase(unittest.TestCase):

    def test_reports_on_only_for_the_on_state(self):
        for state, expected in [("on", True), ("off", False),
                                ("unavailable", False), ("unknown", False)]:
            with self.subTest(state=state):
                self.assertEqual(make_sensor(switch_state=state)._switch.is_on(), expected)

    def test_no_entity_or_no_state_is_not_on(self):
        self.assertFalse(make_sensor(entity=None)._switch.is_on())
        self.assertFalse(make_sensor(switch_state=None)._switch.is_on())


class ControllerShutdownTestCase(unittest.IsolatedAsyncioTestCase):
    """CURRENT BEHAVIOUR IS A DEFECT (W2): retry chains outlive the entity."""

    def setUp(self):
        self._real_sleep = switch_module.asyncio.sleep

        async def fake_sleep(seconds):
            return None

        switch_module.asyncio.sleep = fake_sleep

    def tearDown(self):
        switch_module.asyncio.sleep = self._real_sleep

    async def test_a_retry_does_not_command_after_shutdown(self):
        """The one that matters: reload the config entry during the 2/5/10/20s
        backoff and today the old chain still turns the boiler on."""
        s = make_sensor(switch_state="off")
        await s._switch.async_ensure_with_retries("on", "Expired reverse timer turn-on")
        calls_before = len(calls_of(s))

        s._switch.async_shutdown()
        # Drive the queued link the cancel may not have reached.
        await s._spawned[-1]

        self.assertEqual(len(calls_of(s)), calls_before)
        drop_spawned(s)

    async def test_shutdown_cancels_the_retained_chain(self):
        """Asserts the task was CANCELLED, not merely forgotten.

        async_shutdown clears _tasks unconditionally, so checking the set is
        empty proves only that clear() ran - deleting task.cancel() outright
        left this green until the cancelled flag was asserted.
        """
        s = make_sensor(switch_state="off")
        await s._switch.async_ensure_with_retries("on", "Expired reverse timer turn-on")
        self.assertEqual(len(s._switch._tasks), 1)
        task = next(iter(s._switch._tasks))

        s._switch.async_shutdown()

        self.assertTrue(task.cancelled)
        self.assertEqual(s._switch._tasks, set())
        drop_spawned(s)

    async def test_a_chain_spawned_after_shutdown_does_not_even_wait(self):
        """Pins the guard BEFORE the sleep.

        The post-sleep check would stop this one too, but only after burning
        the whole backoff - a removed entity should not hold a coroutine alive
        for 2s to decide to do nothing. Asserting "no command" cannot tell the
        two guards apart, so this asserts the wait itself never happened.
        """
        s = make_sensor(switch_state="off")
        s._switch.async_shutdown()
        slept = []

        async def record_sleep(seconds):
            slept.append(seconds)

        switch_module.asyncio.sleep = record_sleep
        await s._switch._async_verify_and_retry("on", "switch.boiler")

        self.assertEqual(slept, [])

    async def test_shutdown_during_the_backoff_aborts_the_retry(self):
        """Pins the guard AFTER the sleep, which the opening guard hides.

        The captured coroutine has not started when the other tests call
        async_shutdown, so the opening check catches those and the post-sleep
        check is never reached - it passed for the wrong reason until this
        test existed. The real W2 window is a chain already parked in its
        backoff, so shutdown is fired from inside the wait.
        """
        s = make_sensor(switch_state="off")
        await s._switch.async_ensure_with_retries("on", "Expired reverse timer turn-on")
        calls_before = len(calls_of(s))

        async def shutdown_mid_wait(seconds):
            s._switch.async_shutdown()

        switch_module.asyncio.sleep = shutdown_mid_wait
        await s._spawned[-1]

        self.assertEqual(len(calls_of(s)), calls_before)
        drop_spawned(s)

    async def test_shutdown_stops_a_chain_from_extending_itself(self):
        """Cancelling one link is not enough if the link queues the next."""
        s = make_sensor(switch_state="off")
        await s._switch.async_ensure_with_retries("on", "Expired reverse timer turn-on")
        s._switch.async_shutdown()
        spawned_before = len(s._spawned)

        await s._spawned[-1]

        self.assertEqual(len(s._spawned), spawned_before)
        drop_spawned(s)


class ClimateIsOnTestCase(unittest.TestCase):
    """A climate entity's state IS its hvac mode, never the string "on"."""

    def test_any_non_off_mode_counts_as_running(self):
        for state, expected in [("heat", True), ("cool", True), ("dry", True),
                                ("fan_only", True), ("auto", True),
                                ("heat_cool", True), ("off", False),
                                ("unavailable", False), ("unknown", False)]:
            with self.subTest(state=state):
                s = make_sensor(switch_state=state, entity="climate.ac",
                                turn_on_option="cool")
                self.assertEqual(s._switch.is_on(), expected)

    def test_switch_domain_is_unaffected(self):
        # The eight sensor call sites read is_on(); this is the regression pin
        # that the climate rules did not leak into switch-likes.
        self.assertTrue(make_sensor(switch_state="on")._switch.is_on())
        self.assertFalse(make_sensor(switch_state="heat")._switch.is_on())


class ClimateCommandTestCase(unittest.IsolatedAsyncioTestCase):
    """Both directions go through set_hvac_mode, never homeassistant.turn_*."""

    def setUp(self):
        self.slept = []

        async def fake_sleep(seconds):
            self.slept.append(seconds)

        original = switch_module.asyncio.sleep
        self.addCleanup(lambda: setattr(switch_module.asyncio, "sleep", original))
        switch_module.asyncio.sleep = fake_sleep

    def _climate(self, state="off", option="cool"):
        return make_sensor(switch_state=state, entity="climate.ac", turn_on_option=option)

    async def test_turn_on_applies_the_configured_mode(self):
        s = self._climate()
        await s._switch.async_ensure("on", "test")

        self.assertEqual(
            calls_of(s)[0],
            ("climate", "set_hvac_mode",
             {"entity_id": "climate.ac", "hvac_mode": "cool"}),
        )

    async def test_turn_off_sets_hvac_mode_off(self):
        s = self._climate(state="heat")
        await s._switch.async_ensure("off", "test")

        self.assertEqual(
            calls_of(s)[0],
            ("climate", "set_hvac_mode",
             {"entity_id": "climate.ac", "hvac_mode": "off"}),
        )

    async def test_starting_over_an_already_running_unit_sends_nothing(self):
        """Documented consequence: the configured mode is applied only from a
        stopped device, so a manual mode the user picked is left alone."""
        s = self._climate(state="heat")
        await s._switch.async_ensure("on", "test")
        self.assertEqual(calls_of(s), [])

    async def test_force_commands_the_configured_mode_over_a_manual_one(self):
        """The other half of the same rule - reverse completion and restart
        recovery both force, and both assert the configured mode."""
        s = self._climate(state="heat")
        await s._switch.async_ensure("on", "test", force=True)

        self.assertEqual(calls_of(s)[0][2]["hvac_mode"], "cool")

    async def test_a_mode_the_user_changed_mid_settle_is_not_a_failure(self):
        """THE false-warning fix.

        Commanded cool, the unit comes back reporting heat because the user
        turned the dial. The device is running, so nothing should warn - under
        the old literal comparison this notified the user that their AC had
        failed to turn on.
        """
        s = self._climate()

        async def user_changes_mode(seconds):
            self.slept.append(seconds)
            set_state(s, "heat", entity="climate.ac")

        switch_module.asyncio.sleep = user_changes_mode
        await s._switch.async_ensure("on", "test")

        self.assertEqual(self.slept, [1.0])
        s._send_notification.assert_not_awaited()
        s._log.warning.assert_not_called()

    async def test_a_unit_that_stays_off_still_warns_in_the_existing_wording(self):
        s = self._climate(state="off")
        await s._switch.async_ensure("on", "test")

        self.assertEqual(self.slept, [1.0, 2.0, 3.0])
        self.assertEqual(
            s._send_notification.await_args.args[0],
            "Warning: tried to turn the device ON but it is still OFF. "
            "Please check the switch connectivity.",
        )

    async def test_a_turn_off_that_lands_on_a_mode_is_a_failure(self):
        """matches() is asymmetric: only a definitive off satisfies "off"."""
        s = self._climate(state="heat")
        await s._switch.async_ensure("off", "test")

        self.assertEqual(self.slept, [1.0, 2.0, 3.0])
        s._send_notification.assert_awaited_once()

    async def test_an_unavailable_unit_never_satisfies_either_direction(self):
        for desired in ("on", "off"):
            with self.subTest(desired=desired):
                self.slept.clear()
                s = self._climate(state="unavailable")
                await s._switch.async_ensure(desired, "test")
                self.assertEqual(self.slept, [1.0, 2.0, 3.0])
                s._send_notification.assert_awaited_once()

    async def test_context_and_blocking_are_forwarded_for_climate_too(self):
        s = self._climate()
        ctx = object()
        await s._switch.async_ensure("on", "test", blocking=False, context=ctx)

        domain, service, data, blocking, context = full_calls_of(s)[0]
        self.assertEqual((domain, service), ("climate", "set_hvac_mode"))
        self.assertFalse(blocking)
        self.assertIs(context, ctx)


class MissingTurnOnOptionTestCase(unittest.IsolatedAsyncioTestCase):
    """A climate device with no configured mode: fail, never guess one."""

    def setUp(self):
        async def instant(seconds):
            pass

        original = switch_module.asyncio.sleep
        self.addCleanup(lambda: setattr(switch_module.asyncio, "sleep", original))
        switch_module.asyncio.sleep = instant

    async def test_async_command_raises_so_a_start_aborts_before_persisting(self):
        s = make_sensor(entity="climate.ac", turn_on_option=None)

        with self.assertRaises(Exception):
            await s._switch.async_command("on")

        self.assertEqual(calls_of(s), [])

    async def test_turning_off_needs_no_option(self):
        s = make_sensor(switch_state="heat", entity="climate.ac", turn_on_option=None)
        await s._switch.async_command("off")

        self.assertEqual(calls_of(s)[0][2]["hvac_mode"], "off")

    async def test_async_ensure_warns_and_notifies_instead_of_raising(self):
        s = make_sensor(switch_state="off", entity="climate.ac", turn_on_option=None)

        await s._switch.async_ensure("on", "Timer start")     # must not raise

        self.assertEqual(calls_of(s), [])
        s._log.warning.assert_called()
        s._send_notification.assert_awaited_once()


class TurnOnOptionCaptureTestCase(unittest.IsolatedAsyncioTestCase):
    """The retry chain snapshots the mode, exactly as it snapshots the entity."""

    def setUp(self):
        async def instant(seconds):
            pass

        original = switch_module.asyncio.sleep
        self.addCleanup(lambda: setattr(switch_module.asyncio, "sleep", original))
        switch_module.asyncio.sleep = instant

    async def test_the_controller_reads_the_option_live(self):
        s = make_sensor(entity="climate.ac", turn_on_option="cool")
        s._turn_on_option = "heat"
        self.assertEqual(s._switch.turn_on_option, "heat")

    async def test_a_retry_uses_the_option_captured_at_spawn(self):
        """An options-flow edit during the 37s backoff must not redirect a
        retry that is already in flight - the same rule the entity id has."""
        s = make_sensor(switch_state="off", entity="climate.ac", turn_on_option="cool")
        await s._switch.async_ensure_with_retries("on", "test")
        s.hass.services.async_call.reset_mock()

        s._turn_on_option = "heat"          # user reconfigures mid-chain
        await s._spawned[-1]

        self.assertEqual(calls_of(s)[0][2]["hvac_mode"], "cool")
        drop_spawned(s)

    async def test_a_retry_recommands_set_hvac_mode(self):
        s = make_sensor(switch_state="off", entity="climate.ac", turn_on_option="dry")
        await s._switch._async_verify_and_retry(
            "on", "climate.ac", turn_on_option="dry")

        self.assertEqual(
            calls_of(s)[0],
            ("climate", "set_hvac_mode",
             {"entity_id": "climate.ac", "hvac_mode": "dry"}),
        )
        self.assertEqual(len(s._spawned), 1)
        drop_spawned(s)

    async def test_a_running_unit_ends_the_chain_whatever_mode_it_landed_in(self):
        s = make_sensor(switch_state="heat", entity="climate.ac", turn_on_option="cool")
        await s._switch._async_verify_and_retry(
            "on", "climate.ac", turn_on_option="cool")

        self.assertEqual(calls_of(s), [])
        self.assertEqual(s._spawned, [])

    async def test_an_option_that_vanished_mid_chain_warns_and_keeps_chaining(self):
        """Resolution failure must not kill the recovery path."""
        s = make_sensor(switch_state="off", entity="climate.ac", turn_on_option="cool")
        await s._switch._async_verify_and_retry(
            "on", "climate.ac", turn_on_option=None)

        self.assertEqual(calls_of(s), [])
        self.assertEqual(len(s._spawned), 1)
        s._log.warning.assert_called()
        drop_spawned(s)


if __name__ == "__main__":
    unittest.main()
