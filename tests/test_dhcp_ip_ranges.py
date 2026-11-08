"""Focused regression tests for DHCP IP range filtering."""

import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "custom_components.technitiumdns"


def _install_import_stubs():
    """Load utils without requiring a full Home Assistant installation."""
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(REPOSITORY_ROOT / "custom_components" / "technitiumdns")]
    sys.modules[PACKAGE_NAME] = package

    homeassistant = types.ModuleType("homeassistant")
    helpers = types.ModuleType("homeassistant.helpers")
    entity = types.ModuleType("homeassistant.helpers.entity")
    entity.DeviceInfo = object
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    dt.parse_datetime = lambda value: None

    class FlowBase:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    class FlowHandlers:
        def register(self, _domain):
            return lambda flow_class: flow_class

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = FlowBase
    config_entries.OptionsFlow = FlowBase
    config_entries.HANDLERS = FlowHandlers()
    core = types.ModuleType("homeassistant.core")
    core.callback = lambda function: function
    selector = types.ModuleType("homeassistant.helpers.selector")
    selector.TextSelectorConfig = lambda **kwargs: kwargs
    selector.TextSelectorType = SimpleNamespace(URL="url", PASSWORD="password")
    selector.TextSelector = lambda *args, **kwargs: object()
    selector.BooleanSelector = lambda *args, **kwargs: object()
    selector.SelectSelectorConfig = lambda **kwargs: kwargs
    selector.SelectSelector = lambda *args, **kwargs: object()
    helpers.selector = selector

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = lambda schema: schema
    voluptuous.Required = lambda *args, **kwargs: object()
    voluptuous.Optional = lambda *args, **kwargs: object()
    voluptuous.In = lambda *args, **kwargs: object()
    client = types.ModuleType(f"{PACKAGE_NAME}.client")
    client.create_api_client = lambda *args, **kwargs: None
    technitiumdns = types.ModuleType("technitiumdns")
    technitiumdns.InvalidTokenError = type("InvalidTokenError", (Exception,), {})
    technitiumdns.TransportError = type("TransportError", (Exception,), {})
    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.config_entries": config_entries,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.entity": entity,
            "homeassistant.helpers.selector": selector,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt,
            "voluptuous": voluptuous,
            f"{PACKAGE_NAME}.client": client,
            "technitiumdns": technitiumdns,
        }
    )


_install_import_stubs()
utils = importlib.import_module(f"{PACKAGE_NAME}.utils")
config_flow = importlib.import_module(f"{PACKAGE_NAME}.config_flow")


class TestDHCPIPRanges(unittest.TestCase):
    """Cover bounded parsing and fail-closed filtering behavior."""

    def test_large_network_is_compact_and_cached(self):
        parsed = utils.parse_ip_ranges("10.0.0.0/8")

        self.assertEqual(len(parsed.intervals), 1)
        self.assertEqual(parsed.address_count, 16_777_214)
        self.assertIs(utils.parse_ip_ranges("10.0.0.0/8"), parsed)
        self.assertFalse(utils.validate_ip_ranges_config("10.0.0.0/8")[0])

    def test_mixed_separators_and_range_types(self):
        configured_ranges = (
            "192.168.1.1, 192.168.1.10-192.168.1.12;"
            "192.168.2.0/30\n192.168.2.10"
        )

        self.assertTrue(
            utils.should_track_ip("192.168.1.11", "include", configured_ranges)
        )
        self.assertTrue(
            utils.should_track_ip("192.168.2.2", "include", configured_ranges)
        )
        self.assertFalse(
            utils.should_track_ip("192.168.2.0", "include", configured_ranges)
        )
        self.assertFalse(
            utils.should_track_ip("192.168.2.3", "include", configured_ranges)
        )

    def test_invalid_or_empty_active_filter_fails_closed(self):
        for mode in ("include", "exclude"):
            with self.subTest(mode=mode):
                self.assertFalse(utils.should_track_ip("192.168.1.1", mode, ""))
                self.assertFalse(
                    utils.should_track_ip("192.168.1.1", mode, "192.168.1.1;invalid")
                )

    def test_oversized_and_unknown_filters_fail_closed(self):
        self.assertFalse(
            utils.should_track_ip("10.0.0.1", "include", "10.0.0.0/8")
        )
        self.assertFalse(
            utils.should_track_ip("192.168.1.1", "unknown", "192.168.1.1")
        )

    def test_disabled_filter_preserves_unfiltered_behavior(self):
        self.assertTrue(utils.should_track_ip("not-an-ip", "disabled", ""))


class TestDHCPOptionsFlow(unittest.IsolatedAsyncioTestCase):
    """Verify active IP filters are validated before options are saved."""

    async def test_numeric_radio_defaults_and_saved_values_round_trip(self):
        options = {
            "dhcp_update_interval": 180,
            "stats_update_interval": 120,
            "activity_score_threshold": 55,
            "activity_analysis_window": 60,
        }
        handler = config_flow.TechnitiumDNSOptionsFlowHandler()
        handler.config_entry = SimpleNamespace(options=options)
        defaults = {}
        markers = {}

        def capture_optional(name, **kwargs):
            defaults[name] = kwargs.get("default")
            markers[name] = object()
            return markers[name]

        with (
            patch.object(config_flow.vol, "Optional", side_effect=capture_optional),
            patch.object(config_flow.vol, "In", side_effect=list),
        ):
            form = await handler.async_step_init()

        for key, value in options.items():
            with self.subTest(key=key):
                self.assertEqual(defaults[key], str(value))
                choices = form["data_schema"][markers[key]]
                self.assertIn(defaults[key], choices)
                self.assertTrue(all(isinstance(choice, str) for choice in choices))

        submitted = {key: str(value) for key, value in options.items()}
        saved = await handler.async_step_init(submitted)
        self.assertEqual(saved["data"], options)

        with patch.object(config_flow.vol, "Optional", side_effect=capture_optional):
            await handler.async_step_init({
                **submitted,
                "dhcp_ip_filter_mode": "include",
                "dhcp_ip_ranges": "",
            })
        for key, value in submitted.items():
            self.assertEqual(defaults[key], value)

    async def test_valid_ranges_save_and_empty_ranges_redisplay_form(self):
        handler = config_flow.TechnitiumDNSOptionsFlowHandler()
        handler.config_entry = SimpleNamespace(options={})

        saved = await handler.async_step_init(
            {
                "dhcp_ip_filter_mode": "include",
                "dhcp_ip_ranges": "192.168.1.10",
                "test_dhcp": False,
            }
        )
        invalid = await handler.async_step_init(
            {
                "dhcp_ip_filter_mode": "include",
                "dhcp_ip_ranges": "",
                "test_dhcp": False,
            }
        )

        self.assertEqual(saved["type"], "create_entry")
        self.assertNotIn("test_dhcp", saved["data"])
        self.assertEqual(invalid["type"], "form")
        self.assertIn(
            "Invalid IP range configuration",
            invalid["description_placeholders"]["dhcp_description"],
        )


if __name__ == "__main__":
    unittest.main()