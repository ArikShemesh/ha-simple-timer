"""Shared Home Assistant stubs so the integration modules can be imported alone.

These tests run without Home Assistant installed. Importing this module installs
a mock `homeassistant` package tree plus a **real** `simple_timer` package entry,
after which `load("sensor")` and friends import normally.

Why a real package and not a MagicMock: importing `simple_timer.helpers` makes
CPython read `simple_timer.__spec__`, and MagicMock raises AttributeError for
dunders it was not explicitly given. A MagicMock parent therefore works only for
modules preloaded by hand into sys.modules, and breaks the moment one module of
the integration imports a sibling. A ModuleSpec built with is_package=True gives
a genuine __spec__ and __path__ without executing the integration's __init__.py
(which would pull in the real Home Assistant).

Installed once at import time, so every test module shares one mock tree and the
result does not depend on which test file runs first.
"""
import importlib
import importlib.machinery
import importlib.util
import os
import sys
from unittest.mock import MagicMock

COMPONENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "simple_timer")
)


# Separate base classes, to avoid metaclass conflicts and duplicate-base errors
# when an entity subclasses both.
class MockSensorEntity:
    async def async_will_remove_from_hass(self):
        """Real SensorEntity has this; the removal tests call through super()."""
        return None


class MockRestoreEntity:
    async def async_will_remove_from_hass(self):
        return None


class MockFlowBase:
    """Base for ConfigFlow / OptionsFlow.

    Real classes, not MagicMocks: `class X(Base, domain=DOMAIN)` needs a base
    that is genuinely a class, and the keyword goes to __init_subclass__, which
    plain object rejects.
    """

    def __init_subclass__(cls, **kwargs):
        return None


# Submodules the integration imports from. Each is bound to the matching
# attribute of the mock root, so `ha.helpers.event` and
# sys.modules["homeassistant.helpers.event"] stay the same object.
_HA_SUBMODULES = (
    "components",
    "components.sensor",
    "components.persistent_notification",
    "components.http",
    "config_entries",
    "const",
    "core",
    "exceptions",
    "helpers",
    "helpers.config_validation",
    "helpers.device_registry",
    "helpers.dispatcher",
    "helpers.entity",
    "helpers.event",
    "helpers.restore_state",
    "helpers.selector",
    "helpers.storage",
    "util",
    "util.dt",
)


def _install_homeassistant() -> MagicMock:
    """Install the mock homeassistant package tree; return its root."""
    sys.modules["voluptuous"] = MagicMock()

    ha = MagicMock()
    sys.modules["homeassistant"] = ha
    for dotted in _HA_SUBMODULES:
        obj = ha
        for part in dotted.split("."):
            obj = getattr(obj, part)
        sys.modules[f"homeassistant.{dotted}"] = obj

    ha.components.sensor.SensorEntity = MockSensorEntity
    ha.helpers.restore_state.RestoreEntity = MockRestoreEntity
    ha.config_entries.ConfigFlow = MockFlowBase
    ha.config_entries.OptionsFlow = MockFlowBase

    # DeviceInfo is a TypedDict, so a plain dict is what it really is at
    # runtime. Left as a MagicMock, DeviceInfo(...) returns a mock that happily
    # accepts __setitem__ and answers every lookup, so a test could not tell an
    # omitted key from a present one - which is the whole point of default_name.
    ha.helpers.device_registry.DeviceInfo = dict

    # Real values, not auto-mocked attributes. The integration compares entity
    # states against these by equality, and a MagicMock never equals the string
    # "on", so leaving them mocked silently makes every such comparison False.
    ha.const.STATE_ON = "on"
    ha.const.STATE_OFF = "off"
    ha.const.STATE_UNAVAILABLE = "unavailable"
    ha.const.STATE_UNKNOWN = "unknown"
    ha.const.EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"

    # Real exception classes, for the same reason the states above are real:
    # `raise ha.exceptions.HomeAssistantError(...)` on a MagicMock raises
    # TypeError instead, so a deliberate failure path would be untestable and
    # every `except HomeAssistantError` would be unreachable.
    ha.exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
    ha.exceptions.ServiceValidationError = type(
        "ServiceValidationError", (ha.exceptions.HomeAssistantError,), {}
    )

    # @callback must stay an identity decorator. Left as a MagicMock it would
    # replace every decorated method with the same mock object, and tests would
    # exercise that mock instead of the real code.
    ha.core.callback = lambda func: func

    return ha


def _install_package() -> None:
    """Register `simple_timer` as a real package rooted at the component dir."""
    spec = importlib.machinery.ModuleSpec("simple_timer", None, is_package=True)
    spec.submodule_search_locations = [COMPONENT_DIR]
    sys.modules["simple_timer"] = importlib.util.module_from_spec(spec)


def load(name: str):
    """Import `simple_timer.<name>`, letting normal machinery resolve siblings."""
    return importlib.import_module(f"simple_timer.{name}")


ha = _install_homeassistant()
_install_package()
