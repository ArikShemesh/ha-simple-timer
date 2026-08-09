"""What can be tested about the config flow without Home Assistant.

The flow itself cannot be driven here - `async_show_form`, the selectors and
the entry store are all mocked, and a test that asserts a MagicMock was called
proves nothing. So the flow was written to keep its decisions in pure
functions: `domains.py` (pinned in test_domains.py) and
`_resolve_turn_on_options` here.

What is left is worth pinning anyway, because each failure mode is silent:

* the module must still import - it has no other coverage, so a typo in it
  surfaces as an integration that will not load;
* every error key the flow can raise must exist in `en.json`, or the user sees
  the raw key;
* the domain list must not be hardcoded again.
"""
import json
import os
import re
import unittest

from ha_harness import COMPONENT_DIR, load

config_flow = load("config_flow")
domains = load("domains")

CLIMATE_ATTRS = {"hvac_modes": ["off", "heat", "cool", "dry"]}


def _source():
    with open(os.path.join(COMPONENT_DIR, "config_flow.py"), encoding="utf-8") as handle:
        return handle.read()


def _translations():
    path = os.path.join(COMPONENT_DIR, "translations", "en.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class SmokeImportTestCase(unittest.TestCase):
    """config_flow.py has no other coverage; at minimum it must load."""

    def test_both_flows_are_real_classes(self):
        self.assertTrue(isinstance(config_flow.SimpleTimerConfigFlow, type))
        self.assertTrue(isinstance(config_flow.SimpleTimerOptionsFlow, type))

    def test_the_flow_exposes_the_steps_the_ui_dispatches_to(self):
        for step in ("async_step_user", "async_step_name"):
            self.assertTrue(hasattr(config_flow.SimpleTimerConfigFlow, step), step)
        for step in ("async_step_init", "async_step_turn_on_option"):
            self.assertTrue(hasattr(config_flow.SimpleTimerOptionsFlow, step), step)


class ResolveTurnOnOptionsTestCase(unittest.TestCase):
    """Turning a descriptor's answer into a form error, or a dropdown."""

    def test_a_switch_asks_nothing(self):
        self.assertEqual(config_flow._resolve_turn_on_options("switch.boiler", {}), (None, []))
        self.assertEqual(config_flow._resolve_turn_on_options("input_boolean.t", None), (None, []))

    def test_a_climate_entity_offers_its_own_modes_minus_off(self):
        error, options = config_flow._resolve_turn_on_options("climate.ac", CLIMATE_ATTRS)
        self.assertIsNone(error)
        self.assertEqual(options, ["heat", "cool", "dry"])

    def test_a_climate_entity_that_cannot_be_turned_off_is_refused(self):
        """"Turn it off later" is the whole promise; HA does not guarantee it."""
        error, options = config_flow._resolve_turn_on_options(
            "climate.ac", {"hvac_modes": ["heat", "cool"]})
        self.assertEqual(error, "climate_no_off_mode")
        self.assertEqual(options, [])

    def test_an_entity_reporting_nothing_yet_is_not_ready(self):
        """Distinct from the refusal above: this one is worth retrying."""
        for attrs in ({}, None, {"hvac_modes": []}, {"hvac_modes": "heat"}):
            with self.subTest(attrs=attrs):
                error, options = config_flow._resolve_turn_on_options("climate.ac", attrs)
                self.assertEqual(error, "entity_not_ready")
                self.assertEqual(options, [])

    def test_an_entity_offering_only_off_is_not_ready_either(self):
        error, _ = config_flow._resolve_turn_on_options("climate.ac", {"hvac_modes": ["off"]})
        self.assertEqual(error, "entity_not_ready")

    def test_every_offered_option_resolves_to_a_command(self):
        """The two halves must agree: whatever the flow can store, the
        controller must be able to command."""
        _, options = config_flow._resolve_turn_on_options("climate.ac", CLIMATE_ATTRS)
        descriptor = domains.descriptor_for("climate.ac")
        for option in options:
            with self.subTest(option=option):
                self.assertIsNotNone(descriptor.on_command(option))
                self.assertFalse(
                    domains.needs_turn_on_option("climate.ac", option, CLIMATE_ATTRS))


class TranslationMirrorTestCase(unittest.TestCase):
    """An error key with no translation reaches the user as the raw key."""

    def test_every_error_key_the_flow_raises_is_translated(self):
        source = _source()
        translations = _translations()

        # Only the keys assigned as bare identifiers - the file also assigns
        # some literal English sentences, which are their own message.
        raised = set(re.findall(r'errors\[[^\]]+\]\s*=\s*"([a-z_]+)"', source))
        raised.update(re.findall(r'return "([a-z_]+)", \[\]', source))

        for section in ("config", "options"):
            with self.subTest(section=section):
                translated = set(translations[section]["error"])
                self.assertTrue(raised)
                self.assertEqual(raised - translated, set())

    def test_the_new_error_keys_are_present(self):
        translations = _translations()
        for section in ("config", "options"):
            for key in ("climate_no_off_mode", "entity_not_ready"):
                with self.subTest(section=section, key=key):
                    self.assertIn(key, translations[section]["error"])

    def test_the_second_options_step_is_translated(self):
        step = _translations()["options"]["step"]["turn_on_option"]
        self.assertIn("title", step)
        self.assertIn("turn_on_option", step["data"])
        # The step's description names the device it is asking about.
        self.assertIn("{device}", step["description"])

    def test_the_turn_on_option_field_is_labelled_in_both_flows(self):
        translations = _translations()
        self.assertIn("turn_on_option", translations["config"]["step"]["name"]["data"])
        self.assertIn("turn_on_option", translations["options"]["step"]["init"]["data"])


class NoHardcodedDomainsTestCase(unittest.TestCase):
    """The whole point of the descriptor table is one place to add a domain."""

    def test_the_flow_does_not_carry_its_own_domain_list(self):
        source = _source()
        for domain in domains.selectable_domains():
            with self.subTest(domain=domain):
                self.assertNotIn(f'"{domain}"', source)
                self.assertNotIn(f"'{domain}'", source)

    def test_the_flow_asks_domains_py_instead(self):
        self.assertEqual(_source().count("selectable_domains()"), 3)


if __name__ == "__main__":
    unittest.main()
