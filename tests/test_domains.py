"""Tests for the per-domain descriptor table.

`domains.py` is pure data plus small pure functions, so this is the one place
in the project where exhaustive truth tables are cheap. It is also the place a
future domain entry (lock, media_player) gets checked, which is the point of
the table existing at all — so the sweep below asserts the *contract*, not just
the two domains that exist today.

Weighted to the three things that would otherwise fail silently:

* an incomplete future descriptor entry (the completeness sweep);
* `is_definitive_off` answering True for an entity that merely stopped talking,
  which would cancel a running timer on a dropped Z-Wave message;
* `services.yaml` drifting from the table — YAML cannot import Python, so that
  mirror is the one unavoidable duplication in this design, and it is pinned
  here rather than left to be noticed by a user.
"""
import dataclasses
import os
import re
import unittest

from ha_harness import COMPONENT_DIR, load

domains = load("domains")

# Every state the sweeps run over: both switch states, four hvac modes, the two
# not-answering states, and the empty string a half-built State object yields.
ALL_STATES = ("on", "off", "heat", "cool", "fan_only", "unavailable", "unknown", "")

NOT_ANSWERING = ("unavailable", "unknown", "")

CLIMATE_ATTRS = {"hvac_modes": ["off", "heat", "cool", "dry", "fan_only"]}


class DescriptorContractTestCase(unittest.TestCase):
    """Every entry in the table answers the whole contract.

    A future `lock` entry that forgets a field, or answers one with the wrong
    shape, goes red here instead of at the call site that first needs it.
    """

    def test_every_field_is_required_so_a_new_entry_cannot_omit_one(self):
        # A field with a default would let a new domain silently inherit
        # switch-like behaviour for the half of the contract it forgot.
        for field in dataclasses.fields(domains.DomainDescriptor):
            self.assertIs(field.default, dataclasses.MISSING, field.name)
            self.assertIs(field.default_factory, dataclasses.MISSING, field.name)

    def test_descriptors_are_frozen(self):
        descriptor = domains.DESCRIPTORS["switch"]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            descriptor.is_active = lambda state: True

    def test_every_descriptor_answers_both_predicates_with_a_bool(self):
        for domain, descriptor in domains.DESCRIPTORS.items():
            for state in ALL_STATES:
                with self.subTest(domain=domain, state=state):
                    self.assertIsInstance(descriptor.is_active(state), bool)
                    self.assertIsInstance(descriptor.is_definitive_off(state), bool)

    def test_not_answering_is_never_active_and_never_definitively_off(self):
        # The load-bearing invariant: an entity that stopped answering has told
        # us nothing, so it neither meters runtime nor cancels a timer.
        for domain, descriptor in domains.DESCRIPTORS.items():
            for state in NOT_ANSWERING:
                with self.subTest(domain=domain, state=state):
                    self.assertFalse(descriptor.is_active(state))
                    self.assertFalse(descriptor.is_definitive_off(state))

    def test_no_state_is_both_active_and_definitively_off(self):
        for domain, descriptor in domains.DESCRIPTORS.items():
            for state in ALL_STATES:
                with self.subTest(domain=domain, state=state):
                    self.assertFalse(
                        descriptor.is_active(state) and descriptor.is_definitive_off(state)
                    )

    def test_every_descriptor_resolves_an_off_command(self):
        for domain, descriptor in domains.DESCRIPTORS.items():
            with self.subTest(domain=domain):
                service_domain, service, extra = descriptor.off_command()
                self.assertIsInstance(service_domain, str)
                self.assertIsInstance(service, str)
                self.assertIsInstance(extra, dict)
                self.assertNotIn("entity_id", extra)

    def test_every_descriptor_resolves_an_on_command_from_its_own_options(self):
        # Feeding each descriptor the first option it offers proves the two
        # halves agree: whatever the config flow can store, on_command accepts.
        for domain, descriptor in domains.DESCRIPTORS.items():
            with self.subTest(domain=domain):
                if descriptor.turn_on_options is None:
                    option = None
                else:
                    options = descriptor.turn_on_options(CLIMATE_ATTRS)
                    self.assertTrue(options, "domain offers options but resolved none")
                    option = options[0]
                command = descriptor.on_command(option)
                self.assertIsNotNone(command)
                service_domain, service, extra = command
                self.assertIsInstance(service_domain, str)
                self.assertIsInstance(service, str)
                self.assertIsInstance(extra, dict)

    def test_optionless_domains_ignore_a_stored_option(self):
        # A leftover option from a previous climate entity must not change how
        # a switch is commanded.
        for domain, descriptor in domains.DESCRIPTORS.items():
            if descriptor.turn_on_options is not None:
                continue
            with self.subTest(domain=domain):
                self.assertEqual(descriptor.on_command(None), descriptor.on_command("heat"))

    def test_every_descriptor_declares_required_services(self):
        for domain, descriptor in domains.DESCRIPTORS.items():
            with self.subTest(domain=domain):
                self.assertTrue(descriptor.required_services)
                for pair in descriptor.required_services:
                    self.assertEqual(len(pair), 2)
                    self.assertTrue(all(isinstance(part, str) and part for part in pair))

    def test_every_descriptor_answers_off_supported_with_a_bool(self):
        for domain, descriptor in domains.DESCRIPTORS.items():
            for attrs in ({}, CLIMATE_ATTRS, {"hvac_modes": []}):
                with self.subTest(domain=domain, attrs=attrs):
                    self.assertIsInstance(descriptor.off_supported(attrs), bool)

    def test_every_descriptor_declares_generic_toggle_support_as_a_bool(self):
        for domain, descriptor in domains.DESCRIPTORS.items():
            with self.subTest(domain=domain):
                self.assertIsInstance(descriptor.generic_toggle_supported, bool)

    def test_generic_toggle_support_agrees_with_how_the_domain_is_commanded(self):
        # The invariant behind the published route attribute. A domain that
        # claims a caller outside the integration can flip its power must be
        # commanded through the generic services and must need no stored
        # option - otherwise the card's direct toggle lands on nothing, or
        # lands on a device whose "on" it was never told.
        for domain, descriptor in domains.DESCRIPTORS.items():
            if not descriptor.generic_toggle_supported:
                continue
            with self.subTest(domain=domain):
                self.assertIsNone(descriptor.turn_on_options)
                self.assertEqual(descriptor.on_command(None)[0], "homeassistant")
                self.assertEqual(descriptor.off_command()[0], "homeassistant")

    def test_command_services_are_covered_by_required_services(self):
        # Startup waits on required_services before acting. A descriptor that
        # commands a service it never waits for can fire into a dead registry.
        for domain, descriptor in domains.DESCRIPTORS.items():
            with self.subTest(domain=domain):
                declared = set(descriptor.required_services)
                off_domain, off_service, _ = descriptor.off_command()
                self.assertIn((off_domain, off_service), declared)

                option = (None if descriptor.turn_on_options is None
                          else descriptor.turn_on_options(CLIMATE_ATTRS)[0])
                on_domain, on_service, _ = descriptor.on_command(option)
                self.assertIn((on_domain, on_service), declared)


class SwitchLikePredicateTestCase(unittest.TestCase):
    """Switch-likes keep the exact literal comparisons they always had."""

    def setUp(self):
        self.descriptor = domains.DESCRIPTORS["switch"]

    def test_is_active_truth_table(self):
        expected = {
            "on": True, "off": False, "heat": False, "cool": False,
            "fan_only": False, "unavailable": False, "unknown": False, "": False,
        }
        for state, want in expected.items():
            with self.subTest(state=state):
                self.assertEqual(self.descriptor.is_active(state), want)

    def test_is_definitive_off_truth_table(self):
        expected = {
            "on": False, "off": True, "heat": False, "cool": False,
            "fan_only": False, "unavailable": False, "unknown": False, "": False,
        }
        for state, want in expected.items():
            with self.subTest(state=state):
                self.assertEqual(self.descriptor.is_definitive_off(state), want)

    def test_matches_on_and_off(self):
        self.assertTrue(self.descriptor.matches("on", "on"))
        self.assertFalse(self.descriptor.matches("on", "off"))
        self.assertTrue(self.descriptor.matches("off", "off"))
        self.assertFalse(self.descriptor.matches("off", "on"))
        # An unresponsive switch has not landed either command.
        self.assertFalse(self.descriptor.matches("on", "unavailable"))
        self.assertFalse(self.descriptor.matches("off", "unavailable"))

    def test_commands_are_byte_identical_to_the_previous_hardcoded_calls(self):
        self.assertEqual(self.descriptor.on_command(None), ("homeassistant", "turn_on", {}))
        self.assertEqual(self.descriptor.off_command(), ("homeassistant", "turn_off", {}))

    def test_no_config_flow_question(self):
        self.assertIsNone(self.descriptor.turn_on_options)
        self.assertTrue(self.descriptor.off_supported({}))

    def test_all_switch_like_domains_share_one_descriptor(self):
        for domain in ("switch", "input_boolean", "light", "fan"):
            with self.subTest(domain=domain):
                self.assertIs(domains.DESCRIPTORS[domain], domains.DESCRIPTORS["switch"])


class ClimatePredicateTestCase(unittest.TestCase):
    """Climate state IS the hvac mode; any non-off mode is the device running."""

    def setUp(self):
        self.descriptor = domains.DESCRIPTORS["climate"]

    def test_is_active_truth_table(self):
        expected = {
            "heat": True, "cool": True, "dry": True, "fan_only": True,
            "auto": True, "heat_cool": True,
            # Not a real climate state, but a stale attribute or a foreign
            # integration could produce it, and "on" is not off.
            "on": True,
            "off": False, "unavailable": False, "unknown": False, "": False,
        }
        for state, want in expected.items():
            with self.subTest(state=state):
                self.assertEqual(self.descriptor.is_active(state), want)

    def test_is_definitive_off_only_for_off(self):
        expected = {
            "off": True, "heat": False, "cool": False, "auto": False,
            "unavailable": False, "unknown": False, "": False,
        }
        for state, want in expected.items():
            with self.subTest(state=state):
                self.assertEqual(self.descriptor.is_definitive_off(state), want)

    def test_matches_accepts_a_mode_the_user_changed_by_hand(self):
        # The false-warning fix in one line: commanded cool, user moved it to
        # heat, the device is still on and nothing should warn.
        self.assertTrue(self.descriptor.matches("on", "heat"))
        self.assertTrue(self.descriptor.matches("on", "cool"))
        self.assertFalse(self.descriptor.matches("on", "off"))

    def test_matches_off_requires_a_definitive_off(self):
        self.assertTrue(self.descriptor.matches("off", "off"))
        self.assertFalse(self.descriptor.matches("off", "heat"))
        self.assertFalse(self.descriptor.matches("off", "unavailable"))

    def test_on_command_applies_the_configured_mode(self):
        self.assertEqual(
            self.descriptor.on_command("cool"),
            ("climate", "set_hvac_mode", {"hvac_mode": "cool"}),
        )

    def test_on_command_without_an_option_is_unresolvable(self):
        # None, not a guess. Guessing a mode picks a heating strategy for
        # somebody's house; callers turn this into a loud failure instead.
        self.assertIsNone(self.descriptor.on_command(None))
        self.assertIsNone(self.descriptor.on_command(""))

    def test_off_command_uses_set_hvac_mode_not_turn_off(self):
        # homeassistant.turn_off needs ClimateEntityFeature.TURN_OFF, which
        # plenty of climate integrations still do not declare.
        self.assertEqual(
            self.descriptor.off_command(),
            ("climate", "set_hvac_mode", {"hvac_mode": "off"}),
        )

    def test_turn_on_options_strip_off_and_keep_order(self):
        self.assertEqual(
            self.descriptor.turn_on_options(CLIMATE_ATTRS),
            ["heat", "cool", "dry", "fan_only"],
        )

    def test_turn_on_options_survive_a_malformed_or_missing_attribute(self):
        for attrs in ({}, None, {"hvac_modes": None}, {"hvac_modes": "heat,cool"}):
            with self.subTest(attrs=attrs):
                self.assertEqual(self.descriptor.turn_on_options(attrs), [])

    def test_turn_on_options_coerce_enum_members_to_strings(self):
        class FakeHVACMode(str):
            def __str__(self):
                return str.__str__(self)

        attrs = {"hvac_modes": [FakeHVACMode("off"), FakeHVACMode("heat")]}
        options = self.descriptor.turn_on_options(attrs)
        self.assertEqual(options, ["heat"])
        self.assertIs(type(options[0]), str)

    def test_off_supported_reads_the_entity_own_modes(self):
        self.assertTrue(self.descriptor.off_supported(CLIMATE_ATTRS))
        self.assertFalse(self.descriptor.off_supported({"hvac_modes": ["heat", "cool"]}))
        self.assertFalse(self.descriptor.off_supported({}))


class DescriptorLookupTestCase(unittest.TestCase):

    def test_known_domains_resolve(self):
        self.assertIs(domains.descriptor_for("climate.ac"), domains.DESCRIPTORS["climate"])
        self.assertIs(domains.descriptor_for("switch.boiler"), domains.DESCRIPTORS["switch"])

    def test_unknown_or_absent_entity_falls_back_to_switch_like(self):
        # This fallback IS today's behaviour — every read site compared against
        # "on" regardless of domain. An unsupported entity must not change.
        for entity_id in (None, "", "boiler", "media_player.tv", "lock.front"):
            with self.subTest(entity_id=entity_id):
                self.assertIs(domains.descriptor_for(entity_id), domains.DESCRIPTORS["switch"])

    def test_only_the_first_dot_splits_the_domain(self):
        self.assertIs(domains.descriptor_for("climate.a.b"), domains.DESCRIPTORS["climate"])

    def test_selectable_domains_is_the_table(self):
        self.assertEqual(domains.selectable_domains(), list(domains.DESCRIPTORS))

    def test_selectable_domains_returns_a_copy(self):
        selectable = domains.selectable_domains()
        selectable.append("not_a_real_domain")
        self.assertNotIn("not_a_real_domain", domains.selectable_domains())


class NeedsTurnOnOptionTestCase(unittest.TestCase):
    """Decision 6 and the options flow both hang off this one predicate."""

    def test_switch_like_never_needs_an_option(self):
        for stored in (None, "", "heat"):
            with self.subTest(stored=stored):
                self.assertFalse(
                    domains.needs_turn_on_option("switch.boiler", stored, {})
                )

    def test_climate_without_a_stored_option_needs_one(self):
        self.assertTrue(domains.needs_turn_on_option("climate.ac", None, CLIMATE_ATTRS))
        self.assertTrue(domains.needs_turn_on_option("climate.ac", "", CLIMATE_ATTRS))

    def test_climate_with_an_offered_option_does_not(self):
        self.assertFalse(domains.needs_turn_on_option("climate.ac", "cool", CLIMATE_ATTRS))

    def test_climate_to_climate_repoint_with_an_unoffered_mode_needs_one(self):
        # The case a domain comparison waves through: old unit had "dry", the
        # new one does not, and the timer would only fail when it fires.
        self.assertTrue(
            domains.needs_turn_on_option("climate.ac", "dry", {"hvac_modes": ["off", "heat"]})
        )

    def test_off_is_never_an_acceptable_stored_option(self):
        self.assertTrue(domains.needs_turn_on_option("climate.ac", "off", CLIMATE_ATTRS))

    def test_unreadable_attributes_ask_again(self):
        for attrs in (None, {}, {"hvac_modes": []}):
            with self.subTest(attrs=attrs):
                self.assertTrue(domains.needs_turn_on_option("climate.ac", "cool", attrs))

    def test_unknown_domain_needs_nothing(self):
        self.assertFalse(domains.needs_turn_on_option("lock.front", None, {}))


class SupportsOffTestCase(unittest.TestCase):

    def test_switch_like_always_supports_off(self):
        self.assertTrue(domains.supports_off("switch.boiler", {}))
        self.assertTrue(domains.supports_off(None, None))

    def test_climate_must_advertise_an_off_mode(self):
        self.assertTrue(domains.supports_off("climate.ac", CLIMATE_ATTRS))
        self.assertFalse(domains.supports_off("climate.ac", {"hvac_modes": ["heat", "cool"]}))


class SupportsGenericToggleTestCase(unittest.TestCase):
    """What the card's power button is allowed to call for itself."""

    def test_switch_like_domains_may_be_toggled_directly(self):
        for entity_id in ("switch.boiler", "input_boolean.test", "light.hall",
                          "fan.office"):
            with self.subTest(entity_id=entity_id):
                self.assertTrue(domains.supports_generic_toggle(entity_id))

    def test_climate_must_go_through_the_integration(self):
        self.assertFalse(domains.supports_generic_toggle("climate.ac"))

    def test_unknown_or_absent_entity_keeps_the_direct_toggle(self):
        # Matches descriptor_for's switch-like fallback, which is what every
        # shipped bundle already does for an entity it does not recognise.
        for entity_id in (None, "", "boiler", "media_player.tv"):
            with self.subTest(entity_id=entity_id):
                self.assertTrue(domains.supports_generic_toggle(entity_id))


class ServicesYamlMirrorTestCase(unittest.TestCase):
    """services.yaml is the one place the table is duplicated.

    YAML cannot import Python, so the `update_switch_entity` selector has to
    repeat the domain list. Pinning it here turns "somebody added a domain and
    forgot the YAML" into a red test instead of a service that silently refuses
    to target the new entity type.
    """

    def _selector_domains(self):
        path = os.path.join(COMPONENT_DIR, "services.yaml")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()

        block = re.search(r"^update_switch_entity:\n(.*?)(?=^\S|\Z)", text, re.S | re.M)
        self.assertIsNotNone(block, "update_switch_entity service is missing")

        listed = re.search(r"^\s*domain:\s*\n((?:\s*-\s*\S+\n)+)", block.group(1), re.M)
        self.assertIsNotNone(listed, "switch_entity_id selector has no domain list")

        return re.findall(r"-\s*(\S+)", listed.group(1))

    def test_selector_lists_every_selectable_domain(self):
        self.assertEqual(self._selector_domains(), domains.selectable_domains())


if __name__ == "__main__":
    unittest.main()
