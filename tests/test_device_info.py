"""Which device the timer entities sit on, and what it is called.

Both sensors claim the monitored device's identifiers so they land beside it -
that is what puts a timer in a device's Activity feed, and the only reason
`TimerStatusSensor` exists at all. Observed on HA 2026.8.0: supplying another
integration's identifiers does not merge us into its device, it gives our
config entry its own row holding only our two entities. So the row we name is
ours.

The rule this file exists to pin: **Home Assistant validates device info by
category, and a dict matching no category takes the entity offline.** It finds
the first type in `device_registry.DEVICE_INFO_TYPES` whose allowed keys cover
every key present. `name` sits in "primary" alongside `identifiers`, so it is
usable. `default_name` sits in "secondary", which does not allow `identifiers`
at all - combining them matches nothing and HA refuses to add the entity:

    Not adding entity with invalid device info: ... device info needs to either
    describe a device, link to existing device or provide extra information.

That was learned by shipping it and taking every Simple Timer entity off a live
instance. The category sweep below is here so the next person finds out from a
red test instead.
"""
import inspect
import unittest
from unittest.mock import MagicMock

from ha_harness import load

helpers = load("helpers")

# device_registry.DEVICE_INFO_TYPES, mirrored. Kept in the same order, because
# HA takes the FIRST match and "link" is deliberately first.
DEVICE_INFO_TYPES = {
    "link": {"connections", "identifiers"},
    "primary": {
        "configuration_url", "connections", "entry_type", "hw_version",
        "identifiers", "manufacturer", "model", "model_id", "name",
        "serial_number", "suggested_area", "sw_version", "via_device",
        "via_device_id",
    },
    "secondary": {
        "connections", "default_manufacturer", "default_model", "default_name",
        "via_device",
    },
}


def _category(info):
    """The category HA would file this device info under, or None."""
    keys = set(info)
    for name, allowed in DEVICE_INFO_TYPES.items():
        if keys <= allowed:
            return name
    return None


def _registries(*, device_id="dev1", identifiers=None, connections=None, device=True):
    """Point helpers' registry lookups at a fake switch and its device."""
    entity_entry = MagicMock()
    entity_entry.device_id = device_id
    helpers.er.async_get.return_value.async_get.return_value = entity_entry

    if device:
        device_entry = MagicMock()
        device_entry.identifiers = identifiers or {("demo", "switch2")}
        device_entry.connections = connections or set()
    else:
        device_entry = None
    helpers.dr.async_get.return_value.async_get.return_value = device_entry


class DeviceInfoTestCase(unittest.TestCase):

    def setUp(self):
        helpers.er.async_get.reset_mock()
        helpers.dr.async_get.reset_mock()
        _registries()

    def test_it_claims_the_switch_device_identifiers(self):
        info = helpers.device_info_for_switch(MagicMock(), "switch.ac")
        self.assertEqual(info["identifiers"], {("demo", "switch2")})

    def test_what_it_produces_is_always_a_category_ha_accepts(self):
        """The one that would have caught the outage.

        Not "these exact keys" - that would go red on any harmless addition.
        This goes red only when the combination is one HA would reject, which
        is the property that actually matters.
        """
        for name in (None, "", "Boiler Timer"):
            with self.subTest(name=name):
                info = helpers.device_info_for_switch(MagicMock(), "switch.ac", name=name)
                self.assertIsNotNone(_category(info), f"HA would reject {info}")

    def test_a_named_device_is_primary_and_an_unnamed_one_is_a_link(self):
        self.assertEqual(
            _category(helpers.device_info_for_switch(MagicMock(), "switch.ac")), "link")
        self.assertEqual(
            _category(helpers.device_info_for_switch(MagicMock(), "switch.ac",
                                                     name="Boiler Timer")), "primary")

    def test_default_name_is_never_used(self):
        """It is the better instruction and HA forbids it here - `identifiers`
        and `default_name` share no category, so the pair is unfileable."""
        info = helpers.device_info_for_switch(MagicMock(), "switch.ac", name="Boiler Timer")
        self.assertNotIn("default_name", info)
        self.assertIsNone(_category({"identifiers": set(), "default_name": "x"}))

    def test_the_name_given_is_the_name_offered(self):
        info = helpers.device_info_for_switch(MagicMock(), "switch.ac", name="Boiler Timer")
        self.assertEqual(info["name"], "Boiler Timer")

    def test_no_name_leaves_the_key_out_rather_than_setting_none(self):
        # A present-but-None name is a value HA would write. Absent means "we
        # are not naming it", which is a different instruction - and it is what
        # every caller sent before names existed.
        for name in (None, ""):
            with self.subTest(name=name):
                info = helpers.device_info_for_switch(MagicMock(), "switch.ac", name=name)
                self.assertNotIn("name", info)

    def test_no_switch_configured_has_no_device(self):
        self.assertIsNone(helpers.device_info_for_switch(MagicMock(), None))
        self.assertIsNone(helpers.device_info_for_switch(MagicMock(), ""))

    def test_a_switch_with_no_registry_entry_has_no_device(self):
        helpers.er.async_get.return_value.async_get.return_value = None
        self.assertIsNone(helpers.device_info_for_switch(MagicMock(), "switch.ac"))

    def test_a_switch_that_belongs_to_no_device_has_no_device(self):
        _registries(device_id=None)
        self.assertIsNone(helpers.device_info_for_switch(MagicMock(), "switch.ac"))

    def test_a_missing_device_row_has_no_device(self):
        _registries(device=False)
        self.assertIsNone(helpers.device_info_for_switch(MagicMock(), "switch.ac"))


class BothSensorsAgreeTestCase(unittest.TestCase):
    """The two entities must land on the SAME device, named the same way.

    They are separate classes with separate device_info properties, so a change
    to one is easy to forget in the other - and the result would be a timer
    whose status sensor sits on a different device card than its runtime, or on
    the same card under a different name.
    """

    def test_both_pass_the_instance_title_to_the_shared_helper(self):
        sources = {
            "runtime": inspect.getsource(load("sensor").TimerRuntimeSensor.device_info.fget),
            "status": inspect.getsource(load("status_sensor").TimerStatusSensor.device_info.fget),
        }
        for sensor, src in sources.items():
            with self.subTest(sensor=sensor):
                self.assertIn("device_info_for_switch", src)
                self.assertIn("name=self.instance_title", src)


if __name__ == "__main__":
    unittest.main()
