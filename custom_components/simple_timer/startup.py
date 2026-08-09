"""Startup readiness probes.

The runtime sensor defers its real initialization until Home Assistant and the
monitored switch are actually usable — restoring a timer against a half-loaded
Z-Wave/Zigbee integration reads the switch as unavailable and corrupts the
restored runtime. Nothing here touches entity state, so it is all free
functions taking `hass`.

Every probe swallows its exceptions and reports "not ready" instead: this runs
during startup, when a raising dependency is the expected case, and the caller's
own timeout is what bounds the wait.
"""
from __future__ import annotations

import asyncio

from homeassistant.core import CoreState, HomeAssistant
from homeassistant.util import dt as dt_util

from .domains import descriptor_for

# Longest we will wait for core + dependencies before giving up and initializing
# anyway. Deliberately bounds the *total* wait, not each phase.
MAX_WAIT_SECONDS = 60
CHECK_INTERVAL_SECONDS = 1


async def async_wait_until_ready(hass: HomeAssistant, switch_entity_id: str | None,
                                 log, max_wait: int = MAX_WAIT_SECONDS) -> None:
    """Block until HA core is running and dependencies answer, or `max_wait` passes.

    Returns rather than raising on timeout — the caller initializes regardless,
    on the grounds that a degraded timer beats no timer.

    The budget starts before the core wait, so a slow core eats into the
    dependency wait rather than extending the total.
    """
    start_time = dt_util.utcnow()

    if hass.state != CoreState.running:
        log.info(f"Waiting for HA Core (current: {hass.state})...")
        await async_wait_for_core_state(hass, CoreState.running, log)

    # Core reporting "running" is not enough: integrations like Z-Wave/Zigbee
    # keep adding entities after that, so poll for what we actually need.
    while (dt_util.utcnow() - start_time).total_seconds() < max_wait:
        if await async_dependencies_ready(hass, switch_entity_id):
            log.info("Dependencies ready")
            break
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    elapsed = (dt_util.utcnow() - start_time).total_seconds()
    log.info(f"Startup wait completed after {elapsed:.1f}s")


async def async_wait_for_core_state(hass: HomeAssistant, target_state: CoreState,
                                    log, timeout: int = MAX_WAIT_SECONDS) -> None:
    """Wait for HA core to reach `target_state`, giving up after `timeout`."""
    start = dt_util.utcnow()
    while hass.state != target_state:
        if (dt_util.utcnow() - start).total_seconds() > timeout:
            log.warning(f"Timed out waiting for CoreState.{target_state}")
            return
        await asyncio.sleep(1)
    log.debug(f"Reached CoreState.{target_state}")


async def async_dependencies_ready(hass: HomeAssistant, switch_entity_id: str | None) -> bool:
    """True when every dependency the sensor needs is answering."""
    return (
        await async_entity_registry_ready(hass)
        and await async_service_registry_ready(hass, switch_entity_id)
        and await async_switch_entity_ready(hass, switch_entity_id)
    )


async def async_entity_registry_ready(hass: HomeAssistant) -> bool:
    """True once the entity registry can be fetched."""
    try:
        # Imported here rather than at module scope on purpose: this probe runs
        # while HA is still coming up, and an ImportError is a legitimate "not
        # ready yet" answer rather than a failure.
        from homeassistant.helpers import entity_registry as er

        return er.async_get(hass) is not None
    except ImportError:
        return False
    except Exception:
        return False


async def async_service_registry_ready(hass: HomeAssistant,
                                       switch_entity_id: str | None = None) -> bool:
    """True once the services this device is commanded through are registered.

    Which services those are depends on the monitored entity's domain — a
    switch goes through homeassistant.turn_on/turn_off, a climate entity
    through climate.set_hvac_mode. No entity configured keeps the switch-like
    requirement, which is what this always waited for.
    """
    try:
        services = hass.services.async_services()
        return all(
            service in services.get(domain, {})
            for domain, service in descriptor_for(switch_entity_id).required_services
        )
    except Exception:
        return False


async def async_switch_entity_ready(hass: HomeAssistant, switch_entity_id: str | None) -> bool:
    """True when the monitored switch reports a usable state.

    No configured switch counts as ready — there is nothing to wait for.
    """
    if not switch_entity_id:
        return True

    try:
        switch_state = hass.states.get(switch_entity_id)
        if not switch_state:
            return False
        return switch_state.state not in ["unavailable", "unknown"]
    except Exception:
        return False
