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
from unittest.mock import AsyncMock, MagicMock

from ha_harness import load

helpers = load("helpers")
sensor_module = load("sensor")


def _component_source(filename):
    """Read a component file as text, for the modules the harness cannot load."""
    import os
    from ha_harness import COMPONENT_DIR

    with open(os.path.join(COMPONENT_DIR, filename), encoding="utf-8") as handle:
        return handle.read()

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


class RepointRegroupsTestCase(unittest.IsolatedAsyncioTestCase):
    """A re-point must reload the entry, or the device grouping goes stale.

    `device_info` is read by Home Assistant's entity platform only when an
    entity is ADDED to the registry. Re-pointing moves `_switch_entity_id` and
    rebuilds the state listener, but the entity object is never removed and
    re-added, so both sensors stay on whichever device they landed on when the
    entry last loaded. Observed on a live instance: re-pointing to a climate
    entity did nothing visible until Home Assistant was restarted.

    Nothing reloads the entry on its own - the `__init__.py` update listener is
    a bare `pass` - so this has to ask for it.
    """

    def _sensor(self, current="switch.old"):
        s = object.__new__(sensor_module.TimerRuntimeSensor)
        s.hass = MagicMock()
        s.hass.states.get.return_value = None
        s._entry = MagicMock()
        s._entry.data = {"switch_entity_id": current}
        s._entry_id = "entry1"
        s._log = MagicMock()
        s._switch_entity_id = current
        s._last_on_timestamp = None
        s._async_setup_switch_listener = AsyncMock()
        s._start_realtime_accumulation = AsyncMock()
        s._stop_realtime_accumulation = AsyncMock()
        s.async_write_ha_state = MagicMock()
        return s

    async def test_repointing_to_another_device_schedules_a_reload(self):
        s = self._sensor()

        await s.async_update_switch_entity("switch.new")

        s.hass.config_entries.async_schedule_reload.assert_called_once_with("entry1")

    async def test_repointing_to_the_same_device_schedules_nothing(self):
        """Both callers can arrive with no actual change - the service, and the
        update listener firing for a name or reset-time edit. Reloading there
        would tear the entity down for nothing, and a reload that re-triggers
        its own listener is how this becomes a loop."""
        s = self._sensor()

        await s.async_update_switch_entity("switch.old")

        s.hass.config_entries.async_schedule_reload.assert_not_called()

    async def test_a_rejected_device_schedules_nothing(self):
        """The refusal must leave the instance exactly as it was. A reload here
        would re-add the entities against the OLD entity id and look like the
        re-point half-worked."""
        s = self._sensor()
        unusable = MagicMock()
        unusable.attributes = {"hvac_modes": ["heat", "cool"]}  # no "off"
        s.hass.states.get.return_value = unusable

        with self.assertRaises(Exception):
            await s.async_update_switch_entity("climate.new")

        s.hass.config_entries.async_schedule_reload.assert_not_called()


class OrphanDeviceCleanupTestCase(unittest.TestCase):
    """Re-pointing leaves the previous device row behind, empty and forever.

    Home Assistant deletes a device only once no config entry still references
    it, and ours does. So every re-point from a device-backed entity to another
    one strands a row holding nothing - visible on the integration page, one
    more each time. Confirmed on a live instance: "2 devices - 4 entities" with
    one row empty.

    This runs on load rather than at re-point time, and that is not a detail.
    When the re-point happens our entities are still ON the old device; they
    move only when the reload re-adds them. The load path is the first moment
    device membership is final.
    """

    def setUp(self):
        self._real_entries_for_device = helpers.er.async_entries_for_device

    def tearDown(self):
        # The harness shares module objects across test files; leaving a stub
        # behind silently changes whatever runs next.
        helpers.er.async_entries_for_device = self._real_entries_for_device

    def _device(self, device_id, entries):
        device = MagicMock()
        device.id = device_id
        device.config_entries = set(entries)
        return device

    def _registries(self, devices, entities_by_device):
        dev_reg = MagicMock()
        dev_reg.devices = {device.id: device for device in devices}
        helpers.dr.async_get.return_value = dev_reg
        helpers.er.async_get.return_value = MagicMock()
        helpers.er.async_entries_for_device = MagicMock(
            side_effect=lambda reg, device_id, include_disabled_entities=False:
                entities_by_device.get(device_id, [])
        )
        return dev_reg

    def test_a_device_of_ours_holding_nothing_is_detached(self):
        dev_reg = self._registries([self._device("old", {"entry1"})], {})

        helpers.cleanup_orphan_devices(MagicMock(), "entry1")

        dev_reg.async_update_device.assert_called_once_with(
            "old", remove_config_entry_id="entry1")

    def test_a_device_still_holding_our_entities_is_left_alone(self):
        dev_reg = self._registries(
            [self._device("current", {"entry1"})],
            {"current": [MagicMock(), MagicMock()]},
        )

        helpers.cleanup_orphan_devices(MagicMock(), "entry1")

        dev_reg.async_update_device.assert_not_called()

    def test_an_empty_device_belonging_to_someone_else_is_left_alone(self):
        """The sweep walks every device in the registry, so the config-entry
        check is the only thing standing between it and another integration's
        rows."""
        dev_reg = self._registries([self._device("theirs", {"other_entry"})], {})

        helpers.cleanup_orphan_devices(MagicMock(), "entry1")

        dev_reg.async_update_device.assert_not_called()

    def test_a_device_whose_only_entity_is_disabled_is_left_alone(self):
        """A disabled entity still lives on that device. Sweeping it away would
        delete the row a user is about to re-enable an entity onto."""
        dev_reg = self._registries(
            [self._device("current", {"entry1"})],
            {"current": [MagicMock()]},
        )

        helpers.cleanup_orphan_devices(MagicMock(), "entry1")

        helpers.er.async_entries_for_device.assert_called_once_with(
            helpers.er.async_get.return_value, "current",
            include_disabled_entities=True)
        dev_reg.async_update_device.assert_not_called()

    def test_setup_entry_runs_the_sweep_after_the_platforms(self):
        """Source-level because `__init__.py` pulls in frontend and lovelace and
        will not import under the harness. Order is the whole correctness
        argument: before the forward, our entities are not added yet and every
        row of ours looks empty."""
        source = _component_source("__init__.py")
        forward = source.index("async_forward_entry_setups")
        sweep = source.index("cleanup_orphan_devices(hass, entry.entry_id)")
        self.assertLess(forward, sweep,
                        "the sweep must run after the platforms are set up")


if __name__ == "__main__":
    unittest.main()
