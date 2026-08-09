"""Logbook descriptions for Simple Timer events.

Turns the bus events fired by sensor.py into readable Activity lines. Without
this the logbook would only show raw status transitions ("changed to Active");
with it, entries name what actually happened and for how long.

Events fired with a user's context render as "... by <user>". Events fired
without one — timer expiry, schedule firing — stay unattributed, which is
correct: no person triggered them.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant, Event, callback

from .const import (
    DOMAIN,
    EVENT_TIMER_STARTED,
    EVENT_TIMER_EXTENDED,
    EVENT_TIMER_CANCELLED,
    EVENT_TIMER_FINISHED,
    EVENT_SCHEDULE_SET,
    EVENT_SCHEDULE_CANCELLED,
)


@callback
def async_describe_events(hass: HomeAssistant, async_describe_event) -> None:
    """Register a describer for each Simple Timer event type."""

    @callback
    def describe_started(event: Event) -> dict[str, str]:
        data = event.data
        if data.get("reverse_mode"):
            message = f"delayed start armed for {data.get('duration', 'a while')}"
        else:
            message = f"started for {data.get('duration', 'a while')}"
        return _entry(data, message)

    @callback
    def describe_extended(event: Event) -> dict[str, str]:
        data = event.data
        message = f"extended by {data.get('added', 'more time')}"
        remaining = data.get("remaining")
        if remaining:
            message += f", {remaining} remaining"
        return _entry(data, message)

    @callback
    def describe_cancelled(event: Event) -> dict[str, str]:
        data = event.data
        message = "cancelled"
        usage = data.get("usage")
        if usage:
            message += f" — daily usage {usage}"
        return _entry(data, message)

    @callback
    def describe_finished(event: Event) -> dict[str, str]:
        data = event.data
        if data.get("reverse_mode"):
            message = "delayed start completed — device turned on"
        else:
            message = "finished — device turned off"
            usage = data.get("usage")
            if usage:
                message += f", daily usage {usage}"
        return _entry(data, message)

    @callback
    def describe_scheduled(event: Event) -> dict[str, str]:
        data = event.data
        message = f"scheduled for {data.get('start_time', 'later')}"
        duration = data.get("duration")
        if duration:
            message += f" ({duration})"
        if data.get("repeat"):
            message += ", repeating"
        return _entry(data, message)

    @callback
    def describe_schedule_cancelled(event: Event) -> dict[str, str]:
        return _entry(event.data, "schedule cancelled")

    for event_type, describer in (
        (EVENT_TIMER_STARTED, describe_started),
        (EVENT_TIMER_EXTENDED, describe_extended),
        (EVENT_TIMER_CANCELLED, describe_cancelled),
        (EVENT_TIMER_FINISHED, describe_finished),
        (EVENT_SCHEDULE_SET, describe_scheduled),
        (EVENT_SCHEDULE_CANCELLED, describe_schedule_cancelled),
    ):
        async_describe_event(DOMAIN, event_type, describer)


def _entry(data, message: str) -> dict[str, str]:
    """Build a logbook entry anchored to the instance's status entity.

    The acting user is appended to the message rather than left to HA's own
    attribution: HA renders context.user_id for state-change entries, but not
    for custom-event entries like these. sensor.py resolves the name at fire
    time and ships it in the event data; events with no user behind them carry
    no name and are left unattributed.
    """
    user_name = data.get("user_name")
    if user_name:
        message = f"{message} by {user_name}"

    return {
        "name": data.get("name") or "Timer",
        "message": message,
        "entity_id": data.get("entity_id"),
    }
