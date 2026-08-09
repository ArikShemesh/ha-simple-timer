"""Scheduled starts: run a bounded timer at a future absolute clock time.

Distinct from a *delayed start* (reverse mode), which counts down a relative
interval. A schedule arms a point-in-time callback for a wall-clock moment,
optionally repeating on a weekday set, and what it runs when it fires is always
a normal forward timer - a scheduled run must switch the device off again, so
reverse mode is overridden rather than inherited.

The manager owns its own state and the callback disposer. It reaches back into
the sensor only through the four callables handed to it, so the dependency runs
one way: sensor -> schedule, never the reverse.

Restart semantics are the subtle part, and differ by kind:

* A **recurring** schedule is always recomputed from now. Its stored fire time
  may be days old and replaying it would fire immediately.
* A **future one-shot** is re-armed exactly as stored, and deliberately not
  re-saved - nothing about it changed.
* A **missed one-shot** is discarded. Running a bounded timer hours after its
  intended start is worse than not running it.
* A payload with no schedule, or one whose `fire_at` is absent, is left alone
  rather than cleared: there is nothing to tear down, and clearing would mean
  a pointless storage write on every restart.
"""
from __future__ import annotations

import logging
from datetime import datetime, time

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import EVENT_SCHEDULE_SET, EVENT_SCHEDULE_CANCELLED
from .helpers import compute_next_fire, duration_to_seconds, format_duration_exact

_LOGGER = logging.getLogger(__name__)


class ScheduleManager:
    """Arms, fires, restores and tears down one instance's scheduled start."""

    def __init__(self, hass: HomeAssistant, store, start_timer, write_state,
                 fire_logbook, log=None):
        self._hass = hass
        self._store = store
        self._start_timer = start_timer
        self._write_state = write_state
        self._fire_logbook = fire_logbook
        self._log = log or _LOGGER

        self._unsub = None
        self._shutdown = False
        self._fire_at: datetime | None = None   # next fire, local tz aware
        self._duration: float = 0.0
        self._unit: str = "min"
        self._repeat: bool = False
        self._days: list[int] = []              # weekday Mon=0; empty = every day

    # ------------------------------------------------------------------
    # Read-only view, for the sensor's attributes and status derivation
    # ------------------------------------------------------------------

    @property
    def is_armed(self) -> bool:
        return self._fire_at is not None

    @property
    def fire_at(self) -> datetime | None:
        return self._fire_at

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def repeat(self) -> bool:
        return self._repeat

    @property
    def days(self) -> list[int]:
        return self._days

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_arm(self, start_time: time, duration: float, unit: str = "min",
                        repeat: bool = False, days: list[int] | None = None,
                        context: Context | None = None) -> None:
        """Arm a scheduled start; at `start_time` run a timer for `duration`.

        `context` is the originating service call's context, so the logbook
        attributes arming to the user who set it. The timer that later fires
        from this schedule is deliberately unattributed.
        """
        days = sorted(set(days or []))
        fire_at = compute_next_fire(start_time, repeat, days)
        if fire_at is None:
            self._log.warning("Could not compute schedule fire time")
            return

        # Dispose any previous callback before arming the new one, or the old
        # one still fires.
        self._dispose()

        self._fire_at = fire_at
        self._duration = duration
        self._unit = unit
        self._repeat = repeat
        self._days = days

        self._arm()
        await self._async_save()

        self._log.info(
            f"Scheduled start at {fire_at.isoformat()} "
            f"for {duration} {unit} (repeat={repeat}, days={days})"
        )

        await self._fire_logbook(
            EVENT_SCHEDULE_SET,
            context=context,
            start_time=fire_at.strftime("%H:%M"),
            duration=format_duration_exact(duration_to_seconds(duration, unit)),
            repeat=repeat,
        )

        self._write_state()

    async def async_cancel(self, context: Context | None = None) -> None:
        """Cancel an armed scheduled start."""
        self._log.info("Cancelling schedule")

        # Fire before clearing, while there is still a schedule to describe.
        if self.is_armed:
            await self._fire_logbook(EVENT_SCHEDULE_CANCELLED, context=context)

        await self.async_clear(write_state=True)

    async def async_clear(self, write_state: bool = False) -> None:
        """Tear down schedule state and its stored payload."""
        self._dispose()
        self._fire_at = None
        self._duration = 0.0
        self._unit = "min"
        self._repeat = False
        self._days = []

        await self._store.async_clear_schedule()

        if write_state:
            self._write_state()

    def async_shutdown(self) -> None:
        """Drop the pending callback without touching stored state.

        Used on entity removal and HA shutdown, where the schedule should
        survive to be restored, not be cancelled.

        Sticky: disposing the tracker cannot recall an _async_fired() already
        queued on the loop, so the flag is what actually stops it (S4). Safe to
        latch, because a config-entry reload builds a new manager.
        """
        self._shutdown = True
        self._dispose()

    # ------------------------------------------------------------------
    # Firing
    # ------------------------------------------------------------------

    def _arm(self) -> None:
        """Register the point-in-time callback for the current fire time."""
        if not self._fire_at:
            return
        self._unsub = async_track_point_in_utc_time(
            self._hass, self._fired, dt_util.as_utc(self._fire_at)
        )

    def _dispose(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _fired(self, now) -> None:
        """Point-in-time callback - hand off to the event loop."""
        self._hass.async_create_task(self._async_fired())

    async def _async_fired(self) -> None:
        """Run the scheduled timer, then re-arm (recurring) or clear (one-shot)."""
        if self._shutdown:
            self._log.debug("Schedule fired after shutdown - ignoring")
            return

        self._unsub = None
        # Captured before starting the timer: async_arm from a concurrent
        # service call would otherwise change what we re-arm to.
        duration, unit = self._duration, self._unit
        repeat, days = self._repeat, self._days
        start_time = (self._fire_at or dt_util.now()).timetz().replace(tzinfo=None)

        self._log.info("Schedule fired - starting bounded timer")

        # Reverse is always overridden for scheduled runs (bounded auto-off).
        #
        # Widened on purpose: the schedule's own bookkeeping below must run
        # whatever the timer did. Letting this escape leaves _unsub cleared and
        # _fire_at set - armed forever, nothing registered to fire it (S2).
        # Nothing upstack handles it either; _async_fired is a detached task.
        # This repairs the SCHEDULE only - a start that raised part-way can
        # still leave the timer half-committed (persistence defect #4).
        try:
            await self._start_timer(duration, unit, reverse_mode=False,
                                    start_method="schedule")
        except Exception as e:
            self._log.error(f"Scheduled timer failed to start: {e}")

        if repeat:
            next_fire = compute_next_fire(start_time, repeat, days)
            if next_fire:
                self._fire_at = next_fire
                self._arm()
                await self._async_save()
                self._write_state()
                return

        # One-shot, or a recurrence that no longer resolves.
        await self.async_clear(write_state=True)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _async_save(self) -> None:
        await self._store.async_save_schedule(
            fire_at=self._fire_at,
            duration=self._duration,
            unit=self._unit,
            repeat=self._repeat,
            days=self._days,
        )

    async def async_restore(self, storage_data: dict) -> None:
        """Re-arm a stored schedule on startup; discard missed one-shots."""
        sched = storage_data.get("schedule")
        if not sched or not sched.get("fire_at"):
            return

        try:
            fire_at = datetime.fromisoformat(sched["fire_at"])
            if fire_at.tzinfo is None:
                # Everything we write carries an offset; a naive value means
                # hand-edited storage. Assume local rather than blow up later
                # comparing it against HA's aware now().
                fire_at = dt_util.as_local(fire_at)
        except (ValueError, TypeError) as e:
            self._log.warning(f"Bad stored schedule fire_at: {e}")
            await self.async_clear()
            return

        self._duration = sched.get("duration", 0.0)
        self._unit = sched.get("unit", "min")
        self._repeat = sched.get("repeat", False)
        self._days = sched.get("days", []) or []
        now = dt_util.now()

        if self._repeat:
            # Recurring: always recompute, the stored time may be days old.
            start_time = fire_at.timetz().replace(tzinfo=None)
            next_fire = compute_next_fire(start_time, True, self._days, now)
            if not next_fire:
                await self.async_clear()
                return
            self._fire_at = next_fire
            self._arm()
            await self._async_save()
            self._log.info(f"Restored recurring schedule -> {next_fire.isoformat()}")
        elif fire_at > now:
            # One-shot still ahead: re-arm as stored, nothing to re-save.
            self._fire_at = fire_at
            self._arm()
            self._log.info(f"Restored one-shot schedule -> {fire_at.isoformat()}")
        else:
            # Missed while offline: a late bounded run is wrong.
            self._log.warning(f"Discarding missed one-shot schedule ({fire_at.isoformat()})")
            await self.async_clear()
