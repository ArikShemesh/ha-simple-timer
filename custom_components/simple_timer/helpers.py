"""Helpers shared by the Simple Timer entities.

Lives in its own module so `sensor.py` and `status_sensor.py` can both import it
without either depending on the other. Everything here is a free function with no
entity state, so it can be unit tested without standing up an entity.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

# Fallback when a config entry carries no usable reset time.
DEFAULT_RESET_TIME = time(0, 0, 0)


class _InstanceLogger(logging.LoggerAdapter):
    """Prefixes every record with the integration name and config entry id."""

    def process(self, msg, kwargs):
        return f"Simple Timer: [{self.extra['entry_id']}] {msg}", kwargs


def instance_logger(logger: logging.Logger, entry_id: str) -> logging.LoggerAdapter:
    """Return a logger that tags each line with `entry_id`.

    Every line this integration writes is prefixed so multi-instance setups can
    be told apart in the log. Doing it in an adapter rather than at each call
    site keeps the prefix out of ~130 f-strings, and lets each module keep its
    own `getLogger(__name__)` so records stay attributable to the module.
    """
    return _InstanceLogger(logger, {"entry_id": entry_id})


def device_info_for_switch(hass: HomeAssistant, switch_entity_id: str | None,
                           name: str | None = None) -> DeviceInfo | None:
    """Return DeviceInfo placing an entity on the monitored device's card.

    Reuses the switch device's identifiers so our entities sit with that
    device. Shared by both sensors.

    **We do not actually merge into the switch's device.** Observed on HA
    2026.8.0 across four cases: an entry supplying another integration's
    identifiers gets its OWN device row, holding only our entities, alongside
    the original. So the row this describes is ours, and naming it renames
    nothing of anyone else's. Should a future HA start merging again, `name`
    would rewrite the shared device's name - a label, and `name_by_user` still
    wins in the UI, but that is the assumption being made here.

    **Which keys may appear is not a style question.** Home Assistant
    classifies device info by finding the first type whose allowed keys cover
    every key present (`device_registry.DEVICE_INFO_TYPES`):

    * "link" - `connections`, `identifiers`
    * "primary" - those plus `name`, `manufacturer`, `model`, ...
    * "secondary" - `default_name` and friends, but NOT `identifiers`

    `default_name` would have been the better instruction ("use this only if
    the device has no name"), but it cannot appear next to `identifiers`: the
    dict then matches no type and HA refuses to add the entity at all, with
    "device info needs to either describe a device, link to existing device or
    provide extra information". Verified the hard way - it took every Simple
    Timer entity off a live instance. `name` is the only usable form.
    """
    if not switch_entity_id:
        return None

    # Access the Entity Registry to find the registry entry for the switch
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(switch_entity_id)

    # If the switch doesn't exist or isn't linked to a device, we can't link
    if not entity_entry or not entity_entry.device_id:
        return None

    # Access the Device Registry to get the device details
    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get(entity_entry.device_id)

    if not device_entry:
        return None

    info = DeviceInfo(
        connections=device_entry.connections,
        identifiers=device_entry.identifiers,
    )
    # Omitted rather than passed as None: an absent key leaves the dict in the
    # "link" category, which is what every caller got before names existed.
    if name:
        info["name"] = name
    return info


def cleanup_orphan_devices(hass: HomeAssistant, entry_id: str) -> None:
    """Drop our claim on device rows that no longer hold any of our entities.

    Re-pointing an instance at a different device moves both sensors, which
    leaves the previous row empty. Home Assistant deletes a device only once no
    config entry still references it, and ours still does - so without this the
    integration page grows one dead row per re-point, each named after whatever
    the timer was called at the time.

    `include_disabled_entities=True`, or disabling an entity would look like an
    empty device and take the row out from under it.

    Called on load, not at re-point time: when the re-point happens our
    entities are still on the old device and it would correctly look occupied.
    They move when the reload re-adds them, so load is the first moment the
    membership is final - which is also why this cleans up rows stranded by
    earlier versions.
    """
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    # Snapshot: removing the last entry deletes the device mid-iteration.
    for device in list(dev_reg.devices.values()):
        if entry_id not in device.config_entries:
            continue
        if er.async_entries_for_device(ent_reg, device.id,
                                       include_disabled_entities=True):
            continue
        dev_reg.async_update_device(device.id, remove_config_entry_id=entry_id)


def duration_to_seconds(duration: float, unit: str) -> float:
    """Convert a service-call duration + unit pair to seconds."""
    if unit in ["s", "sec", "seconds"]:
        return duration
    if unit in ["h", "hr", "hours"]:
        return duration * 3600
    if unit in ["d", "day", "days"]:
        return duration * 86400
    return duration * 60  # minutes is the default unit


def format_duration_natural(total_seconds: float, show_seconds: bool = False) -> str:
    """Format a duration as natural text, for voice assistants and notifications.

    e.g. "1 hour 30 minutes" rather than a clock-style "01:30", so a speaking
    assistant reads it correctly.

    Days are a unit the start service accepts, so they get their own place
    rather than piling up as "48 hours".

    `show_seconds` mirrors the instance setting, but is overridden below a
    minute: the coarse form can only ever say "0 minutes" there, which is a
    plain lie about a 30 second timer. Durations of a minute or more round as
    the setting asks.
    """
    total_seconds_int = max(0, int(total_seconds))
    if total_seconds_int < 60:
        show_seconds = True
    days = total_seconds_int // 86400
    hours = (total_seconds_int % 86400) // 3600
    minutes = (total_seconds_int % 3600) // 60
    seconds = total_seconds_int % 60 if show_seconds else 0

    parts = []
    if days > 0:
        parts.append(f"{days} day" if days == 1 else f"{days} days")
    if hours > 0:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    # The coarse form needs SOMETHING to say when nothing bigger landed, hence
    # the "0 minutes" fallback - but only when no larger part was emitted.
    if minutes > 0 or (not parts and not show_seconds and seconds == 0):
        parts.append(f"{minutes} minute" if minutes == 1 else f"{minutes} minutes")
    if show_seconds and (seconds > 0 or not parts):
        parts.append(f"{seconds} second" if seconds == 1 else f"{seconds} seconds")

    return " ".join(parts) if parts else "0 minutes"


def parse_reset_time(time_str: str) -> time | None:
    """Parse a "HH:MM" or "HH:MM:SS" reset time; None if unusable.

    Returns None rather than silently substituting a default, so the caller can
    log which entry held the bad value before falling back to DEFAULT_RESET_TIME.
    """
    try:
        if len(time_str) == 5:  # HH:MM
            time_str += ":00"
        return time.fromisoformat(time_str)
    except (ValueError, TypeError):
        return None


def next_reset_datetime(reset_time: time, from_date=None) -> datetime:
    """Next local datetime at `reset_time`, rolling to tomorrow if already past."""
    if from_date is None:
        from_date = dt_util.now().date()

    reset_datetime = datetime.combine(from_date, reset_time)
    reset_datetime = dt_util.as_local(reset_datetime)

    now = dt_util.now()
    if reset_datetime <= now:
        tomorrow = from_date + timedelta(days=1)
        reset_datetime = datetime.combine(tomorrow, reset_time)
        reset_datetime = dt_util.as_local(reset_datetime)

    return reset_datetime


def compute_next_fire(start_time: time, repeat: bool, days: list[int],
                      now: datetime | None = None) -> datetime | None:
    """Return the next local datetime >= now matching start_time (and weekday set)."""
    now = now or dt_util.now()
    candidate = now.replace(
        hour=start_time.hour, minute=start_time.minute,
        second=getattr(start_time, "second", 0), microsecond=0,
    )
    if candidate <= now:
        candidate += timedelta(days=1)

    if repeat and days:
        # Advance up to 7 days to the next allowed weekday (Mon=0).
        for _ in range(7):
            if candidate.weekday() in days:
                break
            candidate += timedelta(days=1)
        else:
            return None  # No valid weekday (shouldn't happen with non-empty days)
    return candidate


def instance_title(entry) -> str:
    """Display name for a timer instance.

    Prefers the config entry's editable title, falling back to the name it was
    created with. Shared so the two sensors and the notifier cannot drift.
    """
    if entry.title:
        return entry.title
    return entry.data.get("name") or "Timer"


def format_duration_exact(total_seconds: float) -> str:
    """Format a duration the user chose, never dropping the seconds.

    Used for logbook lines and for notifications quoting a timer's duration or
    remaining time. `show_seconds` deliberately does not apply: it truncates, so
    a 108 second timer would report as "1 minute". Echoing a value back to the
    person who just entered it must not round it away, and a history record must
    not lie. Cumulative daily-usage totals are the other case and DO honour
    `show_seconds` - there the seconds are noise, not the point.
    """
    return format_duration_natural(total_seconds, show_seconds=True)
