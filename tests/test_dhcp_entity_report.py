"""Tests for identifying DHCP entity candidates without registry mutation."""

import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "custom_components.technitiumdns"


def _install_import_stubs():
    """Provide the Home Assistant modules needed to import integration setup."""
    package = sys.modules.setdefault(PACKAGE_NAME, types.ModuleType(PACKAGE_NAME))
    package.__path__ = [str(REPOSITORY_ROOT / "custom_components" / "technitiumdns")]

    homeassistant = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    homeassistant.__path__ = []
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    persistent_notification = types.ModuleType("homeassistant.components.persistent_notification")
    persistent_notification.async_create = Mock()
    components.persistent_notification = persistent_notification
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.persistent_notification"] = persistent_notification
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core_module = sys.modules.setdefault("homeassistant.core", core)
    homeassistant.core = core_module

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    sys.modules.setdefault("homeassistant.config_entries", config_entries)

    helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
    helpers.__path__ = []
    entity = types.ModuleType("homeassistant.helpers.entity")
    entity.DeviceInfo = object
    sys.modules.setdefault("homeassistant.helpers.entity", entity)
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.async_get = lambda _hass: None
    sys.modules.setdefault("homeassistant.helpers.device_registry", device_registry)
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda _hass: None
    sys.modules.setdefault("homeassistant.helpers.entity_registry", entity_registry)
    config_validation = types.ModuleType("homeassistant.helpers.config_validation")
    config_validation.string = str
    config_validation.boolean = bool
    sys.modules.setdefault("homeassistant.helpers.config_validation", config_validation)

    util = sys.modules.setdefault("homeassistant.util", types.ModuleType("homeassistant.util"))
    util.__path__ = []
    dt = types.ModuleType("homeassistant.util.dt")
    dt.parse_datetime = lambda value: None
    util.dt = dt
    sys.modules.setdefault("homeassistant.util.dt", dt)

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = lambda schema: schema
    voluptuous.Optional = lambda *args, **kwargs: object()
    sys.modules.setdefault("voluptuous", voluptuous)

    config_flow = types.ModuleType(f"{PACKAGE_NAME}.config_flow")
    config_flow.CONFIG_VERSION = 4
    sys.modules.setdefault(f"{PACKAGE_NAME}.config_flow", config_flow)
    client = types.ModuleType(f"{PACKAGE_NAME}.client")
    client.create_api_client = lambda *args, **kwargs: None
    sys.modules.setdefault(f"{PACKAGE_NAME}.client", client)


_install_import_stubs()
integration = importlib.import_module(f"{PACKAGE_NAME}.__init__")
sys.modules.pop(f"{PACKAGE_NAME}.config_flow", None)
sys.modules.pop(f"{PACKAGE_NAME}.client", None)


def _entity(entity_id, unique_id, platform="technitiumdns", config_entry_id="entry"):
    return SimpleNamespace(
        entity_id=entity_id,
        unique_id=unique_id,
        platform=platform,
        config_entry_id=config_entry_id,
    )


class TestDHCPEntityCandidates(unittest.TestCase):
    """Only current DHCP tracker and per-device sensor IDs are candidates."""

    def test_tracker_and_overridden_sensor_unique_ids_are_detected(self):
        tracker = _entity(
            "device_tracker.client", "technitiumdns_device_tracker_aabbccddeeff"
        )
        sensor = _entity(
            "sensor.client_ip", "technitiumdns_dhcp_aabbccddeeff_ip_address", "technitiumdns"
        )

        self.assertEqual(integration.dhcp_entity_mac(tracker), "AA:BB:CC:DD:EE:FF")
        self.assertEqual(integration.dhcp_entity_mac(sensor), "AA:BB:CC:DD:EE:FF")

    def test_ip_only_tracker_is_detected_without_inventing_a_mac(self):
        tracker = _entity(
            "device_tracker.client", "technitiumdns_device_tracker_ip_192_168_1_25"
        )

        self.assertEqual(integration.dhcp_entity_mac(tracker), "")

    def test_other_platforms_domains_and_unrelated_ids_are_ignored(self):
        unrelated_platform = _entity(
            "sensor.client_ip",
            "technitiumdns_dhcp_aabbccddeeff_ip_address",
            "another_integration",
        )
        unrelated_domain = _entity(
            "switch.client", "technitiumdns_device_tracker_aabbccddeeff"
        )
        unrelated_id = _entity("sensor.queries", "technitiumdns_total_queries", "technitiumdns")

        for entity in (unrelated_platform, unrelated_domain, unrelated_id):
            with self.subTest(entity=entity.entity_id):
                self.assertIsNone(integration.dhcp_entity_mac(entity))


class TestDHCPOrphanReport(unittest.IsolatedAsyncioTestCase):
    """The scan must remain read-only and avoid false orphan claims."""

    async def test_report_keeps_identifiers_out_of_logs(self):
        entities = [
            _entity(f"sensor.client_{index}", f"technitiumdns_dhcp_{index:012x}_ip_address")
            for index in range(100)
        ]
        registry = SimpleNamespace(entities={entity.entity_id: entity for entity in entities})

        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(integration.persistent_notification, "async_create") as notify,
        ):
            with self.assertLogs(integration.__name__, level="DEBUG") as logs:
                await integration.async_cleanup_orphaned_entities(
                    SimpleNamespace(), "entry", set()
                )

        report = notify.call_args.args[1]
        self.assertIn("sensor.client_0", report)
        self.assertIn("80 additional candidates omitted", report)
        self.assertNotIn("00:00:00:00:00:00", report)
        self.assertLessEqual(len(logs.output), 10)
        self.assertFalse(any("sensor.client_0" in entry for entry in logs.output))
        self.assertFalse(any("00:00:00:00:00:00" in entry for entry in logs.output))

    async def test_unavailable_data_reports_unknown_without_registry_changes(self):
        tracker = _entity(
            "device_tracker.client", "technitiumdns_device_tracker_aabbccddeeff"
        )
        sensor = _entity(
            "sensor.client_ip", "technitiumdns_dhcp_aabbccddeeff_ip_address"
        )
        other_entry = _entity(
            "sensor.other_ip",
            "technitiumdns_dhcp_112233445566_ip_address",
            config_entry_id="another_entry",
        )
        original_entries = {
            tracker.entity_id: tracker,
            sensor.entity_id: sensor,
            other_entry.entity_id: other_entry,
        }
        registry = SimpleNamespace(entities=dict(original_entries))

        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(integration.persistent_notification, "async_create") as notify,
        ):
            with self.assertLogs(integration.__name__, level="INFO") as logs:
                await integration.async_cleanup_orphaned_entities(
                    SimpleNamespace(), "entry", None
                )

        self.assertEqual(registry.entities, original_entries)
        self.assertTrue(any("orphan status is unknown" in entry for entry in logs.output))
        self.assertTrue(any("2 tracker/sensor candidates" in entry for entry in logs.output))
        self.assertIn("orphan status is unknown", notify.call_args.args[1])


class TestDHCPLeasesService(unittest.IsolatedAsyncioTestCase):
    """A successful empty DHCP response still produces the retrieval event."""

    async def _invoke_service(self, leases_result):
        class Services:
            def __init__(self):
                self.handlers = {}

            def has_service(self, _domain, _service):
                return False

            def async_register(self, _domain, name, handler, **_kwargs):
                self.handlers[name] = handler

        services = Services()
        events = []
        api = SimpleNamespace(dhcp=SimpleNamespace())
        api.dhcp.leases_list = AsyncMock(return_value=leases_result)
        hass = SimpleNamespace(
            services=services,
            data={integration.DOMAIN: {"entry": {"api": api}}},
            bus=SimpleNamespace(async_fire=lambda event, data: events.append((event, data))),
        )

        await integration.async_register_services(hass)
        await services.handlers["get_dhcp_leases"](
            SimpleNamespace(data={"config_entry_id": "entry"})
        )
        return events

    async def test_empty_success_fires_event_with_zero_leases(self):
        events = await self._invoke_service([])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "technitiumdns_dhcp_leases_retrieved")
        self.assertEqual(events[0][1]["leases"], [])
        self.assertEqual(events[0][1]["total_leases"], 0)

    async def test_none_response_does_not_masquerade_as_empty_success(self):
        self.assertEqual(await self._invoke_service(None), [])


if __name__ == "__main__":
    unittest.main()