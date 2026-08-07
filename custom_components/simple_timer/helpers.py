"""Helpers shared by the Simple Timer entities.

Lives in its own module so `sensor.py` and `status_sensor.py` can both import it
without either depending on the other. Everything here is a free function with no
entity state, so it can be unit tested without standing up an entity.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

# Fallback when a config entry carries no usable reset time.
DEFAULT_RESET_TIME = time(0, 0, 0)


def device_info_for_switch(hass: HomeAssistant, switch_entity_id: str | None) -> DeviceInfo | None:
    """Return DeviceInfo that groups an entity onto the switch's device.

    Reuses the switch device's identifiers so HA merges our entities into that
    device rather than creating a second one. Shared by both sensors.
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

    return DeviceInfo(
        connections=device_entry.connections,
        identifiers=device_entry.identifiers,
    )


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

    `show_seconds` mirrors the instance setting, but is overridden below a
    minute: the coarse form can only ever say "0 minutes" there, which is a
    plain lie about a 30 second timer. Durations of a minute or more round as
    the setting asks.
    """
    total_seconds_int = max(0, int(total_seconds))
    if total_seconds_int < 60:
        show_seconds = True
    hours = total_seconds_int // 3600
    minutes = (total_seconds_int % 3600) // 60
    seconds = total_seconds_int % 60 if show_seconds else 0

    parts = []
    if hours > 0:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    if minutes > 0 or (hours == 0 and not show_seconds and seconds == 0):
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
