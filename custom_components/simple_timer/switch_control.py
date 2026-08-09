"""Commanding the monitored switch, and making the command stick.

Turning a switch on is not reliable enough to fire-and-forget here: the
integration behind it may be slow (Z-Wave, Zigbee), still coming up after a
restart, or reporting a stale state. So a command is made in two stages.

**Foreground** (`async_ensure`) — command, then poll for the state to land on
waits of 1s, 2s, 3s. If it never lands, warn the user; a boiler that ignored a
turn-off is something they need to know about.

**Background** (`async_ensure_with_retries`) — the same first attempt, then a
detached chain that re-checks and re-commands on a 2/5/10/20s backoff. Used on
the restart paths, where the switch is most likely to be briefly unavailable.

Two rules in the retry chain are load-bearing:

* A pending turn-**off** aborts as soon as a timer is running again. Without it
  the chain fights a user who started a new timer while it was waiting.
  Deliberately one-directional: a pending turn-on is not aborted.
* `force` makes the **first** retry re-command even when HA already reports the
  desired state. That is what recovers from a stale state after a restart,
  where HA says "on" but the device is not.

The chain also captures its entity id **and the configured turn-on option** at
spawn time rather than reading them back, so re-pointing the sensor at a
different device cannot redirect a retry that is already in flight, nor make it
apply a mode the user chose for some other device.

What "on" and "off" mean is not decided here — `domains.py` owns that. This
module's public API stays abstract: callers ask for "on" or "off" and never
learn that a climate entity is commanded with `set_hvac_mode` while a switch
goes through `homeassistant.turn_on`.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .domains import descriptor_for

_LOGGER = logging.getLogger(__name__)


def _spoken_state(value: str) -> str:
    """A switch state as a notification should say it.

    Anything that is not plainly on or off - unavailable, unknown, missing -
    passes through as itself. Flattening those to "OFF" would tell the user
    the device is off when all we know is that it stopped answering.
    """
    if value == STATE_ON:
        return "ON"
    if value == STATE_OFF:
        return "OFF"
    return value

# Foreground poll waits after commanding, in seconds.
_SETTLE_WAITS = (1.0, 2.0, 3.0)

# Background re-check backoff. Its length is also the retry limit.
_RETRY_DELAYS = (2, 5, 10, 20)


def _resolve_command(entity_id: str | None, desired_state: str,
                     turn_on_option: str | None):
    """The concrete service call for an abstract "on"/"off".

    Raises when the domain needs a turn-on option and none is configured. That
    is deliberate and it is why on_command may answer None: the alternative is
    picking an hvac mode for somebody's house, and a loud failure at the call
    site beats a heating strategy we invented.
    """
    descriptor = descriptor_for(entity_id)
    command = (descriptor.on_command(turn_on_option) if desired_state == "on"
               else descriptor.off_command())
    if command is None:
        raise HomeAssistantError(
            f"Cannot turn on {entity_id}: no turn-on option is configured for "
            f"this device. Reconfigure the timer and choose one."
        )
    return command


class SwitchController:
    """Commands one device and verifies the command took effect."""

    def __init__(self, hass: HomeAssistant, get_entity_id, notify,
                 is_timer_active, get_turn_on_option, log=None):
        self._hass = hass
        self._get_entity_id = get_entity_id
        self._notify = notify
        self._is_timer_active = is_timer_active
        self._get_turn_on_option = get_turn_on_option
        self._log = log or _LOGGER
        self._tasks: set = set()
        self._shutdown = False

    @property
    def entity_id(self) -> str | None:
        """Read through to the sensor rather than caching.

        The monitored switch can be re-pointed at runtime, and it is assigned
        in three places on the sensor. Holding a second copy here meant one of
        those could silently miss it and leave the controller commanding the
        OLD device - so there is deliberately only one source of truth.
        """
        return self._get_entity_id()

    @property
    def turn_on_option(self) -> str | None:
        """What "on" means for this device, read live for the same reason.

        An options-flow edit patches the config entry in place without
        reloading, so a copy taken at construction would keep applying the
        mode the user just changed away from.
        """
        return self._get_turn_on_option()

    @property
    def _descriptor(self):
        """The domain rules for whatever entity is configured right now."""
        return descriptor_for(self.entity_id)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def is_on(self) -> bool:
        """True only when the device definitively reports it is running.

        For a switch that is the literal state "on"; for a climate entity it is
        any non-off hvac mode, including one the user selected by hand.
        """
        if not self.entity_id:
            return False
        state = self._hass.states.get(self.entity_id)
        return state is not None and self._descriptor.is_active(state.state)

    # ------------------------------------------------------------------
    # Commanding
    # ------------------------------------------------------------------

    async def async_command(self, desired_state: str, blocking: bool = True,
                            context: Context | None = None) -> None:
        """Send turn_on/turn_off unconditionally, without verifying.

        **This raises, deliberately.** HA validates the service data before the
        blocking/non-blocking split, so a missing or malformed entity_id raises
        out of the await even with blocking=False; an execution failure under
        blocking=False does not surface here at all.

        That makes it the right primitive for async_start_timer, which has
        persisted nothing yet and must abort rather than mark a timer running
        with nothing switched on. Callers that have ALREADY cleared their state
        must not use it - they want async_ensure, which warns instead.

        An unresolvable turn-on (a climate device with no mode configured)
        raises here too, and travels the same paths for the same reason.
        """
        domain, service, extra = _resolve_command(
            self.entity_id, desired_state, self.turn_on_option
        )
        await self._hass.services.async_call(
            domain, service, {"entity_id": self.entity_id, **extra},
            blocking=blocking, context=context,
        )

    async def async_ensure(self, desired_state: str, action_description: str,
                           blocking: bool = True, force: bool = False,
                           context: Context | None = None) -> None:
        """Command the switch if needed, then wait for the state to land.

        `context` is the originating service call's context, passed only on
        user-initiated paths so the logbook names the user who acted. Paths with
        no user behind them (timer expiry, restart recovery) omit it
        deliberately.

        Never raises: callers are mid-timer-lifecycle and do not guard.
        """
        if not self.entity_id:
            return

        # A configured switch with no state object is NOT a reason to skip the
        # command. It usually means the switch's integration is reloading, and
        # that is exactly when a pending turn-off matters most - returning here
        # used to let a timer report "turned off" with the device still on.
        # Only a state that positively matches lets us skip the work.
        #
        # For climate that means starting a timer while the unit already runs
        # in ANY mode sends nothing, so the configured mode is applied only
        # from a stopped device. force=True paths command regardless.
        current_state = self._hass.states.get(self.entity_id)
        if current_state and self._descriptor.matches(desired_state, current_state.state) and not force:
            return

        try:
            await self.async_command(desired_state, blocking=blocking, context=context)

            # Give the integration behind the switch time to report back.
            for wait in _SETTLE_WAITS:
                await asyncio.sleep(wait)
                updated = self._hass.states.get(self.entity_id)
                if updated and self._descriptor.matches(desired_state, updated.state):
                    return

            # A switch that reports nothing back is as much a failure as one
            # reporting the wrong state - staying silent about it is what let
            # "Timer was turned off" go out with the device still on.
            updated = self._hass.states.get(self.entity_id)
            if not updated or not self._descriptor.matches(desired_state, updated.state):
                actual = updated.state if updated else "no state"
                # The log keeps the internal wording; the notification is read
                # by a person, and often spoken by a voice assistant, so it
                # talks about the device rather than about entity states.
                self._log.warning(
                    f"Warning: {action_description} - switch should be "
                    f"'{desired_state}' but remains '{actual}'. "
                    f"Check switch connectivity."
                )
                spoken_actual = _spoken_state(actual)
                still_or_reporting = (
                    f"it is still {spoken_actual}"
                    if spoken_actual in ("ON", "OFF")
                    else f"it is reporting {spoken_actual}"
                )
                await self._notify(
                    f"Warning: tried to turn the device "
                    f"{_spoken_state(desired_state)} but {still_or_reporting}. "
                    f"Please check the switch connectivity."
                )
        except Exception as e:
            # The exception text stays in the log: a notification carrying a
            # Python error is noise to the user and gibberish when spoken.
            self._log.warning(f"Warning: {action_description} - failed to set switch "
                              f"to '{desired_state}': {e}")
            await self._notify(
                f"Warning: failed to turn the device "
                f"{_spoken_state(desired_state)}. Please check the switch."
            )

    async def async_ensure_with_retries(self, desired_state: str, action_description: str,
                                        force: bool = False) -> None:
        """Foreground attempt, then hand off to the background retry chain.

        The chain is spawned even when the first attempt raises - it is the
        recovery path, so skipping it would defeat the point.
        """
        if not self.entity_id:
            return

        try:
            await self.async_ensure(desired_state, action_description,
                                    blocking=True, force=force)
        except Exception as e:
            self._log.warning(f"Initial switch attempt failed: {e}")

        self._spawn(
            self._async_verify_and_retry(
                desired_state, self.entity_id,
                turn_on_option=self.turn_on_option, force=force,
            )
        )

    def async_shutdown(self) -> None:
        """Stop retrying, and drop chains already in flight.

        A retry chain is detached and lives for up to 37s. Reload or unload the
        config entry inside that window and it outlives the entity, keeping the
        old controller alive and still able to switch the device - a turn-on
        chain never consults the timer-active predicate, so nothing else stops
        it (W2). Sticky, because a reload builds a new controller.
        """
        self._shutdown = True
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()

    def _spawn(self, coro) -> None:
        """Create a retry task and keep a handle so shutdown can cancel it."""
        task = self._hass.async_create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _async_verify_and_retry(self, desired_state: str, entity_id: str, *,
                                      turn_on_option: str | None = None,
                                      attempt: int = 1, force: bool = False) -> None:
        """Re-check on a backoff and re-command; chains until the limit.

        `turn_on_option` is captured at spawn, alongside `entity_id`, so a
        re-point or an options-flow edit during the 37s window cannot make a
        retry apply the new device's mode to the old one. None is correct for
        every switch-like domain, which has no such choice to make.
        """
        if attempt > len(_RETRY_DELAYS) or self._shutdown:
            return

        await asyncio.sleep(_RETRY_DELAYS[attempt - 1])

        if self._shutdown:
            self._log.debug("Aborting switch retry - controller was shut down")
            return

        # Do not fight a user who started a new timer while we were waiting.
        # One-directional on purpose: a pending turn-on is still wanted.
        if desired_state == "off" and self._is_timer_active():
            self._log.debug("Aborting switch retry (off) because timer is now active")
            return

        state = self._hass.states.get(entity_id)
        if not state:
            # Entity not there yet - almost certainly still starting up.
            self._log.debug(f"Switch entity missing during verify, scheduling retry {attempt + 1}")
            self._chain(desired_state, entity_id, turn_on_option, attempt, force)
            return

        actual = state.state
        # Resolved from the captured entity id, not the live one.
        descriptor = descriptor_for(entity_id)
        # `force` overrides the match check once, to shake off a stale state.
        if descriptor.matches(desired_state, actual) and not (force and attempt == 1):
            return

        self._log.warning(
            f"Switch state mismatch detected (Expected {desired_state}, got {actual}). "
            f"Retrying attempt {attempt}..."
        )

        try:
            # Resolution is inside the try on purpose: an option that went away
            # mid-chain must warn and keep chaining, not kill the recovery path.
            domain, service, extra = _resolve_command(entity_id, desired_state, turn_on_option)
            await self._hass.services.async_call(
                domain, service, {"entity_id": entity_id, **extra}, blocking=True
            )
        except Exception as e:
            self._log.warning(f"Retry attempt {attempt} failed: {e}")

        self._chain(desired_state, entity_id, turn_on_option, attempt, force)

    def _chain(self, desired_state: str, entity_id: str, turn_on_option: str | None,
               attempt: int, force: bool) -> None:
        """Queue the next link of the retry chain."""
        self._spawn(
            self._async_verify_and_retry(
                desired_state, entity_id, turn_on_option=turn_on_option,
                attempt=attempt + 1, force=force,
            )
        )
