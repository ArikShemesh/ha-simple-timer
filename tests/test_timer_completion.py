"""Timer completion and expired-restore, at the point the switch command fails.

Both paths clear the timer's state and storage BEFORE commanding the switch, so
an exception there is not a clean abort - it strands the user with no timer, no
notification and a device in the wrong position. Weighted entirely to that
failure; the happy path is covered by the live instance.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

sensor_module = load("sensor")
switch_module = load("switch_control")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor


def make_sensor(switch_state="off", entity="switch.boiler", reverse=True,
                turn_on_option=None):
    s = object.__new__(TimerRuntimeSensor)
    s.hass = MagicMock()
    s.hass.data = {}
    s.hass.services.async_call = AsyncMock()
    s._log = MagicMock()
    s._entry_id = "entry123"
    s._switch_entity_id = entity
    s._stop_event_received = False
    s._timer_state = "active"
    s._timer_reverse_mode = reverse
    s._timer_duration = 1.0
    s._timer_unsub = None
    s._timer_start_moment = None
    s._runtime_at_timer_start = 0
    s._watchdog_message = None
    s._timer_start_method = "button"
    s._state = 0
    s._last_on_timestamp = None
    # Real __init__ always sets this; the reverse-completion path reads it to
    # decide whether a metering session is already open.
    s._accumulation_task = None

    s._states = {}
    if switch_state is not None and entity:
        st = MagicMock()
        st.state = switch_state
        s._states[entity] = st
    s.hass.states.get = lambda eid: s._states.get(eid)
    # Detached work is discarded: these tests are about the foreground path.
    s.hass.async_create_task = lambda coro: coro.close()

    s._send_notification = AsyncMock()
    s._fire_logbook_event = AsyncMock()
    s.async_write_ha_state = MagicMock()
    s._cleanup_timer_state = AsyncMock()
    s._start_realtime_accumulation = AsyncMock()
    s._stop_realtime_accumulation = AsyncMock()
    s._start_timer_update_task = AsyncMock()
    s._stop_timer_update_task = AsyncMock()
    s._async_setup_switch_listener = AsyncMock()
    s._notifier = MagicMock()
    s._notifier.async_config = AsyncMock(return_value=(None, False))
    s._store = MagicMock()
    s._store.async_save_timer = AsyncMock()

    s._turn_on_option = turn_on_option
    s._switch = switch_module.SwitchController(
        s.hass, lambda: s._switch_entity_id,
        notify=s._send_notification,
        is_timer_active=lambda: s._timer_state == "active",
        get_turn_on_option=lambda: s._turn_on_option,
        log=s._log,
    )
    return s


class CompletionTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Both modules share one fake, so self.slept is the whole wait
        # sequence in order - that is what makes the verification WINDOW
        # assertable, not just the number of service calls.
        #
        # asyncio is a shared module object - restore both patches in tearDown
        # or later suites silently skip their real waits.
        self.slept = []
        self._real_switch_sleep = switch_module.asyncio.sleep
        self._real_sensor_sleep = sensor_module.asyncio.sleep

        async def fake_sleep(seconds):
            self.slept.append(seconds)

        switch_module.asyncio.sleep = fake_sleep
        sensor_module.asyncio.sleep = fake_sleep

    def tearDown(self):
        switch_module.asyncio.sleep = self._real_switch_sleep
        sensor_module.asyncio.sleep = self._real_sensor_sleep

    def notified(self, s):
        return [c.args[0] for c in s._send_notification.await_args_list]


def set_state(s, value, entity="switch.boiler"):
    st = MagicMock()
    st.state = value
    s._states[entity] = st


TURNED_ON = "Delayed start timer completed - device turned ON"
DID_NOT = "Delayed start timer completed - device did not turn on"


class ReverseCompletionTestCase(CompletionTestBase):

    async def test_completion_finishes_when_the_switch_command_fails(self):
        """CURRENT BEHAVIOUR IS A DEFECT (W3).

        _async_timer_finished clears the timer, then the raw async_command
        raises out of the whole method: no accumulation, no notification, no
        logbook entry, no state write. The delayed start vanishes and the
        device stays off. Asserts the WANTED behaviour - fails today.
        """
        s = make_sensor()
        s.hass.services.async_call = AsyncMock(
            side_effect=RuntimeError("switch integration unavailable")
        )

        await s._async_timer_finished()

        s._fire_logbook_event.assert_awaited()
        s.async_write_ha_state.assert_called()
        self.assertTrue(self.notified(s))

    async def test_completion_says_the_device_turned_on_when_it_did(self):
        """Guards option B from under-firing: a real turn-on must read as
        success. Starts OFF and lets the command flip the state, deliberately.

        Seeding the state to "on" instead would leave this green even with the
        switch command deleted entirely, and would additionally bless the
        stale-"on" false positive - where HA reports on, the command fails,
        and is_on() reads the same stale value back as success.
        """
        s = make_sensor(switch_state="off")

        async def turn_on(domain, service, data, **kwargs):
            set_state(s, "on")

        s.hass.services.async_call = AsyncMock(side_effect=turn_on)

        await s._async_timer_finished()

        self.assertIn(TURNED_ON, self.notified(s))

    async def test_completion_does_not_claim_the_device_turned_on_when_it_did_not(self):
        """CURRENT BEHAVIOUR IS A DEFECT (option B).

        The message is sent unconditionally today - it is not even inside the
        `if self._switch_entity_id:` block - so a switch that never turned on
        is still reported as "device turned ON". Asserts the WANTED behaviour.
        """
        s = make_sensor(switch_state="off")

        await s._async_timer_finished()

        self.assertIn(DID_NOT, self.notified(s))
        self.assertNotIn(TURNED_ON, self.notified(s))

    async def test_completion_does_not_claim_a_turn_on_with_no_switch_configured(self):
        """Same defect (B), second trigger: no switch at all still says
        "device turned ON" today, because is_on() is never consulted."""
        s = make_sensor(entity=None)
        s._switch_entity_id = None

        await s._async_timer_finished()

        self.assertIn(DID_NOT, self.notified(s))
        self.assertNotIn(TURNED_ON, self.notified(s))

    async def test_completion_warns_the_user_that_the_switch_failed(self):
        """The failure must not be silent - it once reached nobody.

        Pinned on what the user is told rather than on the internal action
        description, which belongs in the log and no longer ships in the
        notification text.
        """
        s = make_sensor()
        s.hass.services.async_call = AsyncMock(
            side_effect=RuntimeError("switch integration unavailable")
        )

        await s._async_timer_finished()

        self.assertIn(
            "Warning: failed to turn the device ON. Please check the switch.",
            self.notified(s),
        )

    async def test_completion_commands_once_when_the_switch_is_off(self):
        """Characterization, repointed: today it is command + ensure = two
        calls for one intent. force=True keeps 'command unconditionally' with
        one. turn_on is idempotent, so this is invisible to the device."""
        s = make_sensor(switch_state="off")

        await s._async_timer_finished()

        self.assertEqual(s.hass.services.async_call.await_count, 1)


class ExpiredReverseRestoreTestCase(CompletionTestBase):

    async def test_restore_still_cleans_up_when_the_switch_fails(self):
        """CURRENT BEHAVIOUR IS A DEFECT (W3, worse half).

        _handle_expired_reverse_timer re-raises the switch error past its own
        cleanup, so _cleanup_timer_state never runs: the timer stays 'active'
        in memory with storage un-cleared, and the next restart reads it as
        another expired delayed-start. Asserts the WANTED behaviour.
        """
        s = make_sensor()
        s.hass.services.async_call = AsyncMock(
            side_effect=RuntimeError("switch integration unavailable")
        )

        await s._handle_expired_reverse_timer()

        s._cleanup_timer_state.assert_awaited_once()
        self.assertTrue(self.notified(s))

    async def test_restore_makes_two_attempts_over_an_eight_second_window(self):
        """The verification window is a safety property, so it is pinned.

        This path has NO retry chain behind it - its sibling
        _handle_expired_timer uses async_ensure_with_retries, this one uses a
        plain async_ensure. So these two commands and 8s of polling are the
        entire budget for an unattended restart turn-on against a switch
        integration that may still be coming up.

        Collapsing to a single forced ensure cut it to one command and 6s.
        Asserting call count alone would not have caught that; the wait
        sequence is the thing that matters.
        """
        s = make_sensor(switch_state="off")

        await s._handle_expired_reverse_timer()

        self.assertEqual(s.hass.services.async_call.await_count, 2)
        self.assertEqual(self.slept, [2, 1, 2, 3])
        self.assertEqual(sum(self.slept), 8)

    async def test_restore_second_attempt_survives_a_failed_first_command(self):
        """The recovery attempt must not be skipped because attempt one raised
        - that is the case it exists for. Mirrors async_ensure_with_retries,
        which spawns its chain even when the first attempt fails.
        """
        s = make_sensor(switch_state="off")
        s.hass.services.async_call = AsyncMock(
            side_effect=RuntimeError("switch integration unavailable")
        )

        await s._handle_expired_reverse_timer()

        self.assertGreaterEqual(s.hass.services.async_call.await_count, 2)
        s._cleanup_timer_state.assert_awaited_once()

    async def test_restore_does_not_claim_the_device_turned_on_when_it_did_not(self):
        """Option B at the second site. Same unconditional message, and this
        path is the one that runs unattended after a restart - a false
        "device turned ON" here is the user's only signal."""
        s = make_sensor(switch_state="off")

        await s._handle_expired_reverse_timer()

        self.assertIn(DID_NOT, self.notified(s))
        self.assertNotIn(TURNED_ON, self.notified(s))

    async def test_restore_says_the_device_turned_on_when_it_did(self):
        """Same as the completion twin: starts OFF and lets the command flip
        the state, so deleting the command makes this red."""
        s = make_sensor(switch_state="off")

        async def turn_on(domain, service, data, **kwargs):
            set_state(s, "on")

        s.hass.services.async_call = AsyncMock(side_effect=turn_on)

        await s._handle_expired_reverse_timer()

        self.assertIn(TURNED_ON, self.notified(s))


class StartShutdownGuardTestCase(CompletionTestBase):

    async def test_a_start_after_shutdown_does_not_command_the_switch(self):
        """CURRENT BEHAVIOUR IS A DEFECT (S4, the half the latch misses).

        ScheduleManager's _shutdown latch only stops an _async_fired that has
        not begun. One already suspended inside _start_timer - and there are
        several awaits in there - resumes after removal and reaches
        async_start_timer, which has no removal guard of its own. So a
        schedule that fired microseconds before a config-entry reload still
        commands the device, and persists a timer, on a dead sensor.

        Asserts the WANTED behaviour; fails today.
        """
        s = make_sensor(switch_state="off", reverse=False)
        s._timer_state = "idle"
        s._stop_event_received = True

        await s.async_start_timer(5, "min")

        self.assertEqual(s.hass.services.async_call.await_count, 0)
        self.assertEqual(s._timer_state, "idle")
        s._store.async_save_timer.assert_not_awaited()


class StartFailLoudTestCase(CompletionTestBase):
    """Regression guard for the P2-13 fix. Must stay green through this task."""

    async def test_start_aborts_when_no_switch_is_configured(self):
        """The actual P2-13 guard. entity=None is load-bearing.

        A previous refactor added `if not self.entity_id: return` to
        async_command, turning HA's target validation into a silent no-op,
        after which async_start_timer marked and persisted a running timer
        with nothing switched on. With a VALID entity id that guard never
        fires, so a test using switch.boiler stays green while the regression
        is fully reintroduced - which is exactly what this test used to do.

        The service mock raises the way HA's schema validation does, and only
        if the call is actually made.
        """
        s = make_sensor(entity=None, reverse=False)
        s._timer_state = "idle"

        async def raise_on_missing_target(domain, service, data, **kwargs):
            if not data.get("entity_id"):
                raise RuntimeError("Entity ID is required")

        s.hass.services.async_call = AsyncMock(side_effect=raise_on_missing_target)

        with self.assertRaises(RuntimeError):
            await s.async_start_timer(5, "min")

        self.assertEqual(s._timer_state, "idle")
        s._store.async_save_timer.assert_not_awaited()

    async def test_start_aborts_when_the_switch_command_raises(self):
        """The other half: a configured switch whose integration is down.
        Propagation is correct here too - nothing is persisted yet."""
        s = make_sensor(switch_state="off", reverse=False)
        s._timer_state = "idle"
        s.hass.services.async_call = AsyncMock(
            side_effect=RuntimeError("switch integration unavailable")
        )

        with self.assertRaises(RuntimeError):
            await s.async_start_timer(5, "min")

        self.assertEqual(s._timer_state, "idle")
        s._store.async_save_timer.assert_not_awaited()


class CancelNotificationTestCase(unittest.IsolatedAsyncioTestCase):
    """What a cancelled timer tells the user.

    Cancelling sent "Timer finished", which is the one thing that did not
    happen. It matters most when a voice assistant reads the message out.
    """

    async def test_cancelling_says_cancelled_not_finished(self):
        s = make_sensor(reverse=True)
        s._state = 5400

        await s.async_cancel_timer()

        self.assertEqual(
            s._send_notification.await_args.args[0],
            "Timer cancelled – daily usage 1 hour 30 minutes",
        )
