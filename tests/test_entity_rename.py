"""Following the monitored entity when Home Assistant renames it.

Home Assistant does not rewrite config entry data when an entity id changes,
and it changes more often than it looks: renaming a device offers to rename its
entities, and the post-create "Name and assign" dialog does it without asking.

Left alone, the entry keeps pointing at an id nothing answers to. `states.get`
returns None, `async_switch_entity_ready` never goes true so setup waits out its
full 60s cap, and the card falls into its "linked to missing or invalid device"
branch — with nothing anywhere saying why.

The rename must land on the **config entry**, not just the in-memory attribute.
The entry is what `_wait_for_startup_completion` reads back, so a fix that only
moved the attribute would be undone by the next restart.
"""
import unittest
from unittest.mock import MagicMock

from ha_harness import load

sensor_module = load("sensor")
TimerRuntimeSensor = sensor_module.TimerRuntimeSensor


class MonitoredEntityRenameTestCase(unittest.TestCase):
    """Fixtures build the sensor through object.__new__, per repo convention."""

    def _sensor(self, current="switch.old"):
        s = object.__new__(TimerRuntimeSensor)
        s.hass = MagicMock()
        s._entry = MagicMock()
        s._entry.data = {"switch_entity_id": current, "name": "Boiler",
                         "show_seconds": True}
        s._entry_id = "entry1"
        s._log = MagicMock()
        s._switch_entity_id = current
        return s

    def _event(self, **data):
        event = MagicMock()
        event.data = data
        return event

    def _written(self, s):
        return s.hass.config_entries.async_update_entry.call_args.kwargs["data"]

    def test_a_rename_is_written_to_the_config_entry(self):
        s = self._sensor()

        s._handle_monitored_entity_registry_update(self._event(
            action="update", entity_id="switch.new", old_entity_id="switch.old"))

        self.assertEqual(self._written(s)["switch_entity_id"], "switch.new")

    def test_the_write_keeps_every_other_option(self):
        """A dict replace, so anything dropped here is silently lost config."""
        s = self._sensor()

        s._handle_monitored_entity_registry_update(self._event(
            action="update", entity_id="switch.new", old_entity_id="switch.old"))

        self.assertEqual(self._written(s)["name"], "Boiler")
        self.assertEqual(self._written(s)["show_seconds"], True)

    def test_an_update_that_is_not_a_rename_writes_nothing(self):
        """`update` fires for an icon, a friendly name, an area — most of them
        carry no `old_entity_id`. Writing the entry on those would restart the
        instance every time somebody edits a label."""
        s = self._sensor()

        s._handle_monitored_entity_registry_update(self._event(
            action="update", entity_id="switch.old", changes={"icon": "mdi:fire"}))

        s.hass.config_entries.async_update_entry.assert_not_called()

    def test_a_removal_writes_nothing(self):
        """Deleting the monitored entity is a different problem, and the id it
        reports is the one that just stopped existing. Persisting that would
        overwrite a working config with a dead pointer.

        Honest about what holds this: the SAME `old_entity_id` requirement as
        the test above, since a `remove` does not carry one. An explicit
        `action` check was tried and deleted - the suite stayed green without
        it, which makes it a guard no test can hold. This case is here as a
        documented scenario, not as a second pin.
        """
        s = self._sensor()

        s._handle_monitored_entity_registry_update(self._event(
            action="remove", entity_id="switch.old"))

        s.hass.config_entries.async_update_entry.assert_not_called()


class RegistryListenerSetupTestCase(unittest.IsolatedAsyncioTestCase):
    """The handler is dead code unless something subscribes it.

    It rides `_async_setup_switch_listener` so it re-targets whenever the
    monitored entity changes - the registry subscription is indexed by entity
    id, so one left pointing at the old id would follow a device this instance
    no longer watches.
    """

    def setUp(self):
        self._real_track = getattr(
            sensor_module, "async_track_entity_registry_updated_event", None)
        sensor_module.async_track_entity_registry_updated_event = MagicMock(
            return_value=MagicMock())
        self._real_state_track = sensor_module.async_track_state_change_event
        sensor_module.async_track_state_change_event = MagicMock(
            return_value=MagicMock())

    def tearDown(self):
        # Module objects are shared across test files; leaving a stub behind
        # silently changes whatever runs next.
        if self._real_track is None:
            del sensor_module.async_track_entity_registry_updated_event
        else:
            sensor_module.async_track_entity_registry_updated_event = self._real_track
        sensor_module.async_track_state_change_event = self._real_state_track

    def _sensor(self, current="switch.old"):
        s = object.__new__(TimerRuntimeSensor)
        s.hass = MagicMock()
        s._log = MagicMock()
        s._switch_entity_id = current
        s._state_listener_disposer = None
        s._registry_listener_disposer = None
        return s

    async def test_it_tracks_registry_updates_for_the_monitored_entity(self):
        s = self._sensor()

        await s._async_setup_switch_listener()

        sensor_module.async_track_entity_registry_updated_event.assert_called_once_with(
            s.hass, "switch.old", s._handle_monitored_entity_registry_update)

    async def test_re_pointing_disposes_the_previous_subscription(self):
        """Indexed by entity id, so a stale one keeps reporting renames of a
        device this instance stopped watching."""
        s = self._sensor()
        await s._async_setup_switch_listener()
        first = s._registry_listener_disposer

        s._switch_entity_id = "switch.new"
        await s._async_setup_switch_listener()

        first.assert_called_once_with()

    async def test_no_entity_configured_subscribes_to_nothing(self):
        s = self._sensor(current=None)

        await s._async_setup_switch_listener()

        sensor_module.async_track_entity_registry_updated_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
