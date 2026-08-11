"""Unit tests for the startup readiness probes.

These ran on every HA restart but had no coverage until they were free
functions. Each probe must answer "not ready" rather than raise: they run while
HA is still coming up, and a raising probe would abort the sensor's deferred
initialization instead of retrying.
"""
import unittest
from unittest.mock import MagicMock, patch

from ha_harness import load

startup = load("startup")


def _hass(*, services=("turn_on", "turn_off"), switch_state="on",
          service_registry=None):
    """A hass double whose registries answer, unless told otherwise.

    `services` names the homeassistant.* services present, which is what every
    switch-like domain waits for. `service_registry` replaces the whole
    registry when a test needs another domain's services.
    """
    hass = MagicMock()
    hass.services.async_services.return_value = service_registry or {
        "homeassistant": {name: object() for name in services}
    }
    if switch_state is None:
        hass.states.get.return_value = None
    else:
        state = MagicMock()
        state.state = switch_state
        hass.states.get.return_value = state
    return hass


class TestSwitchEntityReady(unittest.IsolatedAsyncioTestCase):
    async def test_no_switch_configured_is_ready(self):
        """Nothing to wait for, so do not hold up startup."""
        self.assertTrue(await startup.async_switch_entity_ready(_hass(), None))

    async def test_missing_state_is_not_ready(self):
        hass = _hass(switch_state=None)
        self.assertFalse(await startup.async_switch_entity_ready(hass, "switch.boiler"))

    async def test_unavailable_and_unknown_are_not_ready(self):
        """The states that would corrupt a restored runtime if trusted."""
        for bad in ["unavailable", "unknown"]:
            with self.subTest(state=bad):
                hass = _hass(switch_state=bad)
                self.assertFalse(await startup.async_switch_entity_ready(hass, "switch.boiler"))

    async def test_on_and_off_are_ready(self):
        for good in ["on", "off"]:
            with self.subTest(state=good):
                hass = _hass(switch_state=good)
                self.assertTrue(await startup.async_switch_entity_ready(hass, "switch.boiler"))

    async def test_raising_hass_is_not_ready(self):
        hass = MagicMock()
        hass.states.get.side_effect = RuntimeError("core not up")
        self.assertFalse(await startup.async_switch_entity_ready(hass, "switch.boiler"))


class TestServiceRegistryReady(unittest.IsolatedAsyncioTestCase):
    async def test_both_switch_services_present(self):
        self.assertTrue(await startup.async_service_registry_ready(_hass()))

    async def test_either_service_missing_is_not_ready(self):
        """Both are needed - every switch command goes through one of them."""
        for present in [("turn_on",), ("turn_off",), ()]:
            with self.subTest(present=present):
                hass = _hass(services=present)
                self.assertFalse(await startup.async_service_registry_ready(hass))

    async def test_raising_registry_is_not_ready(self):
        hass = MagicMock()
        hass.services.async_services.side_effect = RuntimeError("not up")
        self.assertFalse(await startup.async_service_registry_ready(hass))

    async def test_a_switch_entity_still_waits_on_the_homeassistant_services(self):
        hass = _hass(switch_state="on")
        self.assertTrue(
            await startup.async_service_registry_ready(hass, "switch.boiler"))

        hass = _hass(services=("turn_on",))
        self.assertFalse(
            await startup.async_service_registry_ready(hass, "switch.boiler"))

    async def test_a_climate_entity_waits_on_set_hvac_mode_instead(self):
        """Waiting for the wrong service would let a climate timer command a
        registry that cannot serve it - and waiting for homeassistant.turn_on
        would block forever on setups that never register it."""
        hass = _hass(service_registry={"climate": {"set_hvac_mode": object()}})
        self.assertTrue(
            await startup.async_service_registry_ready(hass, "climate.ac"))

    async def test_a_climate_entity_is_not_ready_without_set_hvac_mode(self):
        hass = _hass(service_registry={"climate": {"turn_on": object()},
                                       "homeassistant": {"turn_on": object(),
                                                         "turn_off": object()}})
        self.assertFalse(
            await startup.async_service_registry_ready(hass, "climate.ac"))

    async def test_an_unknown_domain_keeps_the_switch_like_requirement(self):
        hass = _hass(service_registry={"climate": {"set_hvac_mode": object()}})
        self.assertFalse(
            await startup.async_service_registry_ready(hass, "media_player.tv"))


class TestDependenciesReady(unittest.IsolatedAsyncioTestCase):
    """The aggregate must fail if any single probe fails."""

    async def test_all_ready(self):
        with patch.object(startup, "async_entity_registry_ready", return_value=True):
            self.assertTrue(await startup.async_dependencies_ready(_hass(), "switch.boiler"))

    async def test_entity_registry_down_blocks(self):
        with patch.object(startup, "async_entity_registry_ready", return_value=False):
            self.assertFalse(await startup.async_dependencies_ready(_hass(), "switch.boiler"))

    async def test_service_registry_down_blocks(self):
        with patch.object(startup, "async_entity_registry_ready", return_value=True):
            hass = _hass(services=())
            self.assertFalse(await startup.async_dependencies_ready(hass, "switch.boiler"))

    async def test_switch_down_blocks(self):
        with patch.object(startup, "async_entity_registry_ready", return_value=True):
            hass = _hass(switch_state="unavailable")
            self.assertFalse(await startup.async_dependencies_ready(hass, "switch.boiler"))

    async def test_the_entity_id_reaches_the_service_probe(self):
        """The aggregate must pass the entity through, or a climate instance
        waits on switch services that its setup may never register."""
        with patch.object(startup, "async_entity_registry_ready", return_value=True):
            hass = _hass(service_registry={"climate": {"set_hvac_mode": object()}},
                         switch_state="heat")
            self.assertTrue(await startup.async_dependencies_ready(hass, "climate.ac"))

    async def test_returns_a_real_bool(self):
        """`and` chaining returns the last operand - it must still be a bool."""
        with patch.object(startup, "async_entity_registry_ready", return_value=True):
            result = await startup.async_dependencies_ready(_hass(), "switch.boiler")
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
