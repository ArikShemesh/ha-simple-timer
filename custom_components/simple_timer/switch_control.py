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

The chain also captures its entity id at spawn time rather than reading it
back, so re-pointing the sensor at a different switch cannot redirect a retry
that is already in flight.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.const import STATE_ON
from homeassistant.core import Context, HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Foreground poll waits after commanding, in seconds.
_SETTLE_WAITS = (1.0, 2.0, 3.0)

# Background re-check backoff. Its length is also the retry limit.
_RETRY_DELAYS = (2, 5, 10, 20)


class SwitchController:
    """Commands one switch and verifies the command took effect."""

    def __init__(self, hass: HomeAssistant, get_entity_id, notify,
                 is_timer_active, log=None):
        self._hass = hass
        self._get_entity_id = get_entity_id
        self._notify = notify
        self._is_timer_active = is_timer_active
        self._log = log or _LOGGER

    @property
    def entity_id(self) -> str | None:
        """Read through to the sensor rather than caching.

        The monitored switch can be re-pointed at runtime, and it is assigned
        in three places on the sensor. Holding a second copy here meant one of
        those could silently miss it and leave the controller commanding the
        OLD device - so there is deliberately only one source of truth.
        """
        return self._get_entity_id()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def is_on(self) -> bool:
        """True only when the switch definitively reports on."""
        if not self.entity_id:
            return False
        state = self._hass.states.get(self.entity_id)
        return state is not None and state.state == STATE_ON

    # ------------------------------------------------------------------
    # Commanding
    # ------------------------------------------------------------------

    async def async_command(self, desired_state: str, blocking: bool = True,
                            context: Context | None = None) -> None:
        """Send turn_on/turn_off unconditionally, without verifying.

        Deliberately NOT guarded on a missing entity_id: the raw call this
        replaced was unguarded, so HA's own target validation raised and
        aborted the operation. Swallowing it here would let async_start_timer
        mark and persist a running timer when nothing was ever switched on.
        """
        action = "turn_on" if desired_state == "on" else "turn_off"
        await self._hass.services.async_call(
            "homeassistant", action, {"entity_id": self.entity_id},
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
        current_state = self._hass.states.get(self.entity_id)
        if current_state and current_state.state == desired_state and not force:
            return

        try:
            await self.async_command(desired_state, blocking=blocking, context=context)

            # Give the integration behind the switch time to report back.
            for wait in _SETTLE_WAITS:
                await asyncio.sleep(wait)
                updated = self._hass.states.get(self.entity_id)
                if updated and updated.state == desired_state:
                    return

            # A switch that reports nothing back is as much a failure as one
            # reporting the wrong state - staying silent about it is what let
            # "Timer was turned off" go out with the device still on.
            updated = self._hass.states.get(self.entity_id)
            if not updated or updated.state != desired_state:
                actual = updated.state if updated else "no state"
                warning_msg = (
                    f"Warning: {action_description} - switch should be "
                    f"'{desired_state}' but remains '{actual}'. "
                    f"Check switch connectivity."
                )
                self._log.warning(warning_msg)
                await self._notify(warning_msg)
        except Exception as e:
            warning_msg = (f"Warning: {action_description} - failed to set switch "
                           f"to '{desired_state}': {e}")
            self._log.warning(warning_msg)
            await self._notify(warning_msg)

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

        self._hass.async_create_task(
            self._async_verify_and_retry(desired_state, self.entity_id, force=force)
        )

    async def _async_verify_and_retry(self, desired_state: str, entity_id: str,
                                      attempt: int = 1, force: bool = False) -> None:
        """Re-check on a backoff and re-command; chains until the limit."""
        if attempt > len(_RETRY_DELAYS):
            return

        await asyncio.sleep(_RETRY_DELAYS[attempt - 1])

        # Do not fight a user who started a new timer while we were waiting.
        # One-directional on purpose: a pending turn-on is still wanted.
        if desired_state == "off" and self._is_timer_active():
            self._log.debug("Aborting switch retry (off) because timer is now active")
            return

        state = self._hass.states.get(entity_id)
        if not state:
            # Entity not there yet - almost certainly still starting up.
            self._log.debug(f"Switch entity missing during verify, scheduling retry {attempt + 1}")
            self._chain(desired_state, entity_id, attempt, force)
            return

        actual = state.state
        # `force` overrides the match check once, to shake off a stale state.
        if actual == desired_state and not (force and attempt == 1):
            return

        self._log.warning(
            f"Switch state mismatch detected (Expected {desired_state}, got {actual}). "
            f"Retrying attempt {attempt}..."
        )

        action = "turn_on" if desired_state == "on" else "turn_off"
        try:
            await self._hass.services.async_call(
                "homeassistant", action, {"entity_id": entity_id}, blocking=True
            )
        except Exception as e:
            self._log.warning(f"Retry attempt {attempt} failed: {e}")

        self._chain(desired_state, entity_id, attempt, force)

    def _chain(self, desired_state: str, entity_id: str, attempt: int, force: bool) -> None:
        """Queue the next link of the retry chain."""
        self._hass.async_create_task(
            self._async_verify_and_retry(desired_state, entity_id, attempt + 1, force=force)
        )
