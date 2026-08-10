"""What "on" and "off" mean for the monitored device, per entity domain.

Everything else in the integration speaks an abstract "on"/"off". That was
always a half-truth: the read sites compared the device state against the
literal string ``"on"``, which is right for a switch and wrong for a climate
entity, whose state IS its hvac mode (``heat``/``cool``/``dry``/``fan_only``/
``auto``/``heat_cool``, or ``off``). A climate device running in ``heat`` read
as "not on", so timers warned that the device never turned on, and coupled
auto-cancel could not tell "user switched it off" from "mode changed".

One descriptor entry per domain answers the whole contract - how to read
"running", how to command both directions, what the config flow must ask, and
which services must exist before we may act. Adding a domain is a data change
here plus the ``services.yaml`` selector list, which ``test_domains.py`` pins
against :func:`selectable_domains` so it cannot drift silently. Nothing else
should learn a domain name.

Two predicates, not one, because "not running" is not the same question as
"definitively off":

* :attr:`DomainDescriptor.is_active` - the device is doing work. Drives
  metering, notification wording and the on-edge.
* :attr:`DomainDescriptor.is_definitive_off` - the user (or something else)
  positively turned it off, which cancels a coupled timer. Never true for
  ``unavailable``/``unknown``: an entity that stopped answering has not told us
  it is off, and cancelling a timer on a dropped Z-Wave message is exactly the
  "a timer silently vanishes" failure this project weights against.

This module is a leaf. It imports ``homeassistant.const`` and nothing else -
never ``sensor``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

# (service_domain, service, extra_service_data). The caller adds entity_id -
# a command is what to send, not who to send it to.
Command = tuple[str, str, dict]

# States that mean "the entity is not answering", never "the device is off".
_NOT_ANSWERING = (STATE_UNAVAILABLE, STATE_UNKNOWN)


@dataclass(frozen=True)
class DomainDescriptor:
    """Everything the integration needs to know about one entity domain."""

    #: The device is running.
    is_active: Callable[[str], bool]
    #: The device positively reports off. Must be False while not answering.
    is_definitive_off: Callable[[str], bool]
    #: Turn-on command for the configured option, or None when the option is
    #: required and missing. None means "unresolvable" - callers fail loud
    #: rather than guessing a mode for the user's boiler.
    on_command: Callable[[str | None], Command | None]
    off_command: Callable[[], Command]
    #: Choices for the config-flow turn-on dropdown, read off the entity's own
    #: attributes. None means the domain needs no such question at all.
    turn_on_options: Callable[[dict], list[str]] | None
    #: True when the entity can be turned off. Only meaningful for domains that
    #: advertise their capabilities in attributes; "turn it off later" is the
    #: core promise, so the config flow refuses an entity that cannot.
    off_supported: Callable[[dict], bool]
    #: True when ``homeassistant.turn_on``/``turn_off``/``toggle`` reach this
    #: entity, so a caller outside the integration can flip its power without
    #: us. False means power must go through the integration - either because
    #: the generic services do not reach the domain at all, or because "on" is
    #: a stored choice only the config entry knows.
    generic_toggle_supported: bool
    #: Services that must be registered before we may command the device.
    required_services: tuple[tuple[str, str], ...]

    def matches(self, desired: str, state: str) -> bool:
        """Has the abstract command `desired` landed, given `state`?

        Asymmetric on purpose, and this is the whole false-warning fix: a
        turn-on lands on any active state (a climate entity commanded to
        ``cool`` that a user then moved to ``heat`` is still on), while a
        turn-off only lands on a definitive off.
        """
        return self.is_active(state) if desired == "on" else self.is_definitive_off(state)


# ----------------------------------------------------------------------
# Switch-likes: state is literally on/off, commanded through homeassistant.*
# ----------------------------------------------------------------------

_SWITCH_LIKE = DomainDescriptor(
    is_active=lambda state: state == STATE_ON,
    is_definitive_off=lambda state: state == STATE_OFF,
    on_command=lambda option: ("homeassistant", "turn_on", {}),
    off_command=lambda: ("homeassistant", "turn_off", {}),
    turn_on_options=None,
    off_supported=lambda attrs: True,
    generic_toggle_supported=True,
    required_services=(("homeassistant", "turn_on"), ("homeassistant", "turn_off")),
)


# ----------------------------------------------------------------------
# Climate: state is the hvac mode; both directions go through set_hvac_mode
# ----------------------------------------------------------------------

def _climate_modes(attrs: dict | None) -> list[str]:
    """Every hvac mode the entity advertises, as plain strings.

    HVACMode is a StrEnum, so members compare equal to their value already;
    coercion is for malformed or foreign payloads. A non-list `hvac_modes`
    yields nothing rather than raising - an unreadable entity must look like
    an entity offering no modes, which is the conservative answer everywhere
    this feeds.
    """
    modes = (attrs or {}).get("hvac_modes")
    if not isinstance(modes, (list, tuple)):
        return []
    return [str(mode) for mode in modes]


def _climate_turn_on_options(attrs: dict | None) -> list[str]:
    """The modes that count as turning the device ON - everything but off."""
    return [mode for mode in _climate_modes(attrs) if mode != STATE_OFF]


def _climate_on_command(option: str | None) -> Command | None:
    """Apply the configured mode, or refuse to invent one."""
    if not option:
        return None
    return ("climate", "set_hvac_mode", {"hvac_mode": option})


_CLIMATE = DomainDescriptor(
    # Any non-off mode is the device working, including one the user picked by
    # hand mid-timer. HVACMode.OFF's value is the same string as STATE_OFF.
    is_active=lambda state: bool(state) and state not in (STATE_OFF, *_NOT_ANSWERING),
    is_definitive_off=lambda state: state == STATE_OFF,
    on_command=_climate_on_command,
    # set_hvac_mode both ways, rather than homeassistant.turn_on/turn_off:
    # those need ClimateEntityFeature.TURN_ON/TURN_OFF, which many climate
    # integrations still do not declare.
    off_command=lambda: ("climate", "set_hvac_mode", {"hvac_mode": STATE_OFF}),
    turn_on_options=_climate_turn_on_options,
    off_supported=lambda attrs: STATE_OFF in _climate_modes(attrs),
    # Same reason as off_command: the generic services need feature flags many
    # climate integrations omit, and turning one "on" means applying the mode
    # stored on the config entry, which nothing outside the integration knows.
    generic_toggle_supported=False,
    required_services=(("climate", "set_hvac_mode"),),
)


# Insertion order is the order the config flow and services.yaml offer.
DESCRIPTORS: dict[str, DomainDescriptor] = {
    "switch": _SWITCH_LIKE,
    "input_boolean": _SWITCH_LIKE,
    "light": _SWITCH_LIKE,
    "fan": _SWITCH_LIKE,
    "climate": _CLIMATE,
}


def selectable_domains() -> list[str]:
    """Domains a user may point a timer at, in display order."""
    return list(DESCRIPTORS)


def descriptor_for(entity_id: str | None) -> DomainDescriptor:
    """The descriptor governing `entity_id`.

    An unknown or absent domain falls back to switch-like, which is exactly
    what every read site did before this module existed - so nothing that used
    to work starts behaving differently.
    """
    if not entity_id or "." not in entity_id:
        return _SWITCH_LIKE
    return DESCRIPTORS.get(entity_id.split(".", 1)[0], _SWITCH_LIKE)


def needs_turn_on_option(entity_id: str | None, stored_option: str | None,
                         entity_attrs: dict | None) -> bool:
    """Must the user be asked what "on" means for this entity?

    True when the domain has a choice to make AND the stored answer is missing
    or is not among the modes this particular entity offers. The second half is
    what catches a climate-to-climate re-point where the new device has no
    ``dry``, which a plain domain comparison would wave through and only fail
    at 2am when the timer fires.

    An entity whose attributes cannot be read offers no modes, so this answers
    True - ask again rather than keep an answer we cannot confirm.
    """
    descriptor = descriptor_for(entity_id)
    if descriptor.turn_on_options is None:
        return False
    return stored_option not in descriptor.turn_on_options(entity_attrs)


def supports_off(entity_id: str | None, entity_attrs: dict | None) -> bool:
    """Can this entity be turned off at all?

    Home Assistant does not guarantee a climate entity offers ``off``, and a
    timer that cannot turn the device off is worse than no timer.
    """
    return descriptor_for(entity_id).off_supported(entity_attrs)


def supports_generic_toggle(entity_id: str | None) -> bool:
    """May a caller outside the integration toggle this entity's power itself?

    The card asks this - through a published attribute, never by inspecting the
    entity id, so that adding a domain here needs no rebuilt bundle. An unknown
    domain answers True via the switch-like fallback, which is the behaviour
    every shipped card already has.
    """
    return descriptor_for(entity_id).generic_toggle_supported
