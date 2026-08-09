"""Persistence for a single timer instance.

Everything the sensor keeps across a restart lives in one `.storage` file per
config entry. The keys are a wire format: `_complete_initialization` and the
restore paths read them straight back, so a renamed or dropped key does not
fail loudly, it silently loses a running timer on the next restart. Key names
and value shapes here must not change without a migration.

    finishes_at       str   timer end, UTC isoformat
    duration          float total timer length in minutes (grows on extend)
    timer_start       str   timer start, UTC isoformat
    runtime_at_start  float daily runtime when the timer began
    reverse_mode      bool  delayed-start rather than normal
    next_reset_date   str   next daily reset, local isoformat
    schedule          dict  {fire_at, duration, unit, repeat, days}

**Error policy is not uniform**, and mirrors what the sensor did before this
module existed rather than anything principled: `async_save_timer` and
`async_extend_timer` let exceptions propagate, every other write swallows and
logs. `test_storage_roundtrip.StorageErrorPolicyTestCase` pins both halves so
the split is at least deliberate and visible.

Two things that policy does NOT buy you, both verified rather than assumed:

* **It does not detect ordinary write failures.** HA's `Store.async_save`
  catches `SerializationError` and `WriteError` internally, logs them, and
  returns normally, so a full disk or a permission problem never reaches a
  caller here — a timer whose end time never made it to disk still reports
  success and disappears on the next restart. Load failures, and unexpected
  errors such as cancellation, do still propagate.
* **Swallowing in `async_clear_timer` is not merely untidy.** The keys left
  behind are live lifecycle data: a cancelled timer whose keys survive can be
  read back after a restart as an expired timer and switch the device.

Both are pre-existing defects, recorded in TODO.md. They are documented here so
the next reader does not mistake the current split for a considered design.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION = 2
STORAGE_KEY_FORMAT = f"{DOMAIN}_{{}}"

# Written together when a timer starts; cleared together when it ends.
# reverse_mode is NOT in this set - see async_clear_timer.
_TIMER_KEYS = ("finishes_at", "duration", "timer_start", "runtime_at_start")


def _is_number(value) -> bool:
    """True for a real number. bool is an int subclass, so exclude it."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# Expected type per key. A stored value failing its check is dropped on read,
# so callers fall back to their own defaults instead of acting on nonsense.
#
# This matters more than ordinary input validation: these values drive device
# actions during restore. `reverse_mode` is the sharp one - anything truthy,
# `"yes"` included, used to send the switch a turn_on during startup.
def _is_weekday_list(value) -> bool:
    """A list of real weekday numbers. `"MWF"` is iterable but not this."""
    return isinstance(value, list) and all(
        isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 6 for d in value
    )


# The nested `schedule` payload. Checked as a unit: a schedule missing or
# corrupt in any known field cannot be executed faithfully, and guessing at a
# duration or a weekday set means acting on the device at the wrong time.
_SCHEDULE_VALIDATORS = {
    "fire_at": lambda v: isinstance(v, str),
    "duration": _is_number,
    "unit": lambda v: isinstance(v, str),
    "repeat": lambda v: isinstance(v, bool),
    "days": _is_weekday_list,
}


def _is_valid_schedule(value) -> bool:
    """True when every known field of the schedule dict is well formed."""
    if not isinstance(value, dict):
        return False
    return all(
        v is None or _SCHEDULE_VALIDATORS[k](v)
        for k, v in value.items()
        if k in _SCHEDULE_VALIDATORS
    )


_VALIDATORS = {
    "finishes_at": lambda v: isinstance(v, str),
    "timer_start": lambda v: isinstance(v, str),
    "next_reset_date": lambda v: isinstance(v, str),
    "duration": _is_number,
    "runtime_at_start": _is_number,
    "reverse_mode": lambda v: isinstance(v, bool),
    "schedule": _is_valid_schedule,
}


def _sanitize(data: dict, log) -> dict:
    """Drop stored values whose type does not match the wire format.

    None always survives: it means "unset", every reader already guards for it,
    and the v1 migration writes `next_reset_date: None` deliberately. Unknown
    keys pass through untouched so a future version's data is not destroyed by
    an older one reading it.
    """
    clean = {}
    for key, value in data.items():
        validator = _VALIDATORS.get(key)
        if validator is None or value is None or validator(value):
            clean[key] = value
        else:
            log.warning(
                f"Ignoring malformed stored {key!r}: {value!r} ({type(value).__name__})"
            )
    return clean


class TimerStore:
    """Owns the config entry's `.storage` file and the lock guarding it."""

    def __init__(self, hass: HomeAssistant, entry_id: str, log):
        self._hass = hass
        self._entry_id = entry_id
        self._log = log
        self._lock = asyncio.Lock()
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY_FORMAT.format(entry_id))

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def async_read(self) -> dict:
        """Current contents, sanitized; {} if unreadable. Never raises."""
        async with self._lock:
            try:
                return _sanitize(await self._store.async_load() or {}, self._log)
            except Exception as e:
                self._log.warning(f"Could not read storage: {e}")
                return {}

    async def async_load(self) -> dict:
        """Read for startup, migrating a v1 payload if one is found.

        HA's Store raises NotImplementedError when the file on disk predates
        STORAGE_VERSION and no migration function is registered; that is the
        signal to re-read it as v1 and write it back in the current shape.
        """
        async with self._lock:
            try:
                return _sanitize(await self._store.async_load() or {}, self._log)
            except NotImplementedError:
                self._log.info("Migrating storage format")
                try:
                    v1_store = Store(self._hass, 1, STORAGE_KEY_FORMAT.format(self._entry_id))
                    old_data = await v1_store.async_load()
                    if old_data:
                        new_data = old_data.copy()
                        new_data["next_reset_date"] = None
                        await self._store.async_save(new_data)
                        return _sanitize(new_data, self._log)
                except Exception as migration_error:
                    self._log.error(f"Storage migration failed: {migration_error}")
            except Exception as e:
                self._log.error(f"Error loading storage: {e}")
        return {}

    # ------------------------------------------------------------------
    # Timer lifecycle - these two propagate, everything below swallows
    # ------------------------------------------------------------------

    async def async_save_timer(self, *, finishes_at: datetime, duration: float,
                               timer_start: datetime, runtime_at_start: float,
                               reverse_mode: bool) -> None:
        """Persist a freshly started timer. Raises if storage is unwritable."""
        async with self._lock:
            data = await self._store.async_load() or {}
            data.update({
                "finishes_at": finishes_at.isoformat(),
                "duration": duration,
                "timer_start": timer_start.isoformat(),
                "runtime_at_start": runtime_at_start,
                "reverse_mode": reverse_mode,
            })
            await self._store.async_save(data)

    async def async_extend_timer(self, *, finishes_at: datetime, duration: float) -> None:
        """Persist a new end time and total. Raises if storage is unwritable.

        Deliberately leaves timer_start and runtime_at_start alone: an
        extension moves the finish line, it does not restart the timer.
        """
        async with self._lock:
            data = await self._store.async_load() or {}
            data.update({
                "finishes_at": finishes_at.isoformat(),
                "duration": duration,
            })
            await self._store.async_save(data)

    async def async_clear_timer(self) -> None:
        """Drop the running-timer keys, keeping reverse_mode.

        reverse_mode survives on purpose: async_cancel_timer reads it *after*
        calling this, to decide whether to turn the switch off. Clearing it
        here would make cancelling a delayed start switch the device off.
        """
        async with self._lock:
            try:
                data = await self._store.async_load() or {}
                for key in _TIMER_KEYS:
                    data.pop(key, None)
                await self._store.async_save(data)
            except Exception as e:
                self._log.warning(f"Could not clean timer storage: {e}")

    async def async_save_runtime_at_start(self, runtime_at_start: float) -> None:
        """Rewrite runtime_at_start alone, after a daily reset mid-timer.

        Without this the restored value would still be the pre-reset one, and
        the reset would be undone by the next restart.
        """
        async with self._lock:
            try:
                data = await self._store.async_load() or {}
                data["runtime_at_start"] = runtime_at_start
                await self._store.async_save(data)
                self._log.debug(f"Persisted adjusted runtime_at_start: {runtime_at_start}s")
            except Exception as e:
                self._log.error(f"Failed to persist adjusted runtime_at_start: {e}")

    # ------------------------------------------------------------------
    # Daily reset + schedule
    # ------------------------------------------------------------------

    async def async_save_next_reset_date(self, next_reset_date: datetime) -> None:
        """Persist when the daily runtime should next roll over."""
        async with self._lock:
            try:
                data = await self._store.async_load() or {}
                data["next_reset_date"] = next_reset_date.isoformat()
                await self._store.async_save(data)
            except Exception as e:
                self._log.error(f"Failed to save next reset date: {e}")

    async def async_save_schedule(self, *, fire_at: datetime | None, duration: float,
                                  unit: str, repeat: bool, days: list[int]) -> None:
        """Persist the armed scheduled start."""
        async with self._lock:
            try:
                data = await self._store.async_load() or {}
                data["schedule"] = {
                    "fire_at": fire_at.isoformat() if fire_at else None,
                    "duration": duration,
                    "unit": unit,
                    "repeat": repeat,
                    "days": days,
                }
                await self._store.async_save(data)
            except Exception as e:
                self._log.warning(f"Could not save schedule: {e}")

    async def async_clear_schedule(self) -> None:
        """Drop the schedule, writing only if there was one to drop."""
        async with self._lock:
            try:
                data = await self._store.async_load() or {}
                if data.pop("schedule", None) is not None:
                    await self._store.async_save(data)
            except Exception as e:
                self._log.warning(f"Could not clear schedule storage: {e}")
