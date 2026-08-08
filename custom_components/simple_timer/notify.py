"""Notification dispatch for a timer instance.

A configured "notification entity" is really a `domain.service` pair drawn from
the options flow, and three domain families are handled differently:

    input_boolean / switch / light   turned on   - used as a signal, not a sink
    input_button                     pressed
    anything else                    called as domain.service(message, title)

The last case is the normal one (`notify.mobile_app_x`). The first two exist so
a timer can drive a helper entity that an automation watches, for people who do
not use HA's notify platform at all.

Nothing here raises. Notifications are fired from the middle of timer
lifecycle transitions - start, expiry, cancel - and none of those callers
guard, so a dead notification target must not take a timer down with it. Each
target is also isolated from the others: one unreachable phone cannot silence
the rest.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .helpers import instance_title

_LOGGER = logging.getLogger(__name__)

# Domains driven as a signal rather than sent a message.
_TURN_ON_DOMAINS = ("input_boolean", "switch", "light")
_PRESS_DOMAINS = ("input_button",)


class Notifier:
    """Sends an instance's notifications to its configured targets."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, log=None):
        self._hass = hass
        self._entry = entry
        self._log = log or _LOGGER

    async def async_config(self) -> tuple[list[str], bool]:
        """Configured targets and the show_seconds display setting.

        Read live from the config entry every time, so changing either in the
        options flow takes effect without a reload.
        """
        try:
            notification_entities = self._entry.data.get("notification_entities", [])
            show_seconds = self._entry.data.get("show_seconds", False)

            if notification_entities:
                self._log.debug(f"Using notification entities from config: {notification_entities}")
                return notification_entities, show_seconds

            self._log.debug("No notification entities configured in backend")
            return [], show_seconds
        except Exception as e:
            self._log.error(f"Error getting notification config: {e}")
            return [], False

    async def async_send(self, message: str) -> None:
        """Deliver `message` to every configured target. Never raises."""
        try:
            notification_entities, _ = await self.async_config()

            if not notification_entities:
                self._log.debug("No notification entities configured - staying silent")
                return

            # Underscores are markdown in Telegram; an unescaped one mangles the
            # message, so spend them rather than escape per-platform.
            title = instance_title(self._entry).replace("_", " ")

            for target in notification_entities:
                await self._async_send_one(target, message, title)
        except Exception as e:
            self._log.error(f"Failed to send notifications: {e}")

    async def _async_send_one(self, target: str, message: str, title: str) -> None:
        """Deliver to a single target, absorbing its failure."""
        try:
            # Exactly `domain.service`, both parts non-empty. Accepting a
            # longer string and using its first two parts would silently call
            # a different service than the one configured - "notify.a.b" was
            # dispatched as notify.a. Refusing is diagnosable; guessing is not.
            parts = target.split(".")
            if len(parts) != 2 or not all(parts):
                self._log.warning(f"Invalid notification entity format: {target}")
                return

            domain, service = parts

            if domain in _TURN_ON_DOMAINS:
                self._log.debug(f"Turning on configured notification entity: {target}")
                await self._hass.services.async_call(domain, "turn_on", {"entity_id": target})
            elif domain in _PRESS_DOMAINS:
                self._log.debug(f"Pressing configured notification button: {target}")
                await self._hass.services.async_call(domain, "press", {"entity_id": target})
            else:
                self._log.info(f"Sending notification to {domain}.{service}: '{message}'")
                await self._hass.services.async_call(
                    domain, service, {"message": message, "title": title}
                )
        except Exception as e:
            self._log.error(f"Failed to send notification to {target}: {e}")
