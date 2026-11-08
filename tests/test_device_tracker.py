"""Focused regression tests for DHCP tracker connectivity and activity status."""

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "custom_components.technitiumdns"
INTEGRATION_PATH = REPOSITORY_ROOT / "custom_components" / "technitiumdns"


def _install_import_stubs():
    """Provide the Home Assistant surfaces needed to import the tracker."""
    package = sys.modules.setdefault(PACKAGE_NAME, types.ModuleType(PACKAGE_NAME))
    package.__path__ = [str(INTEGRATION_PATH)]

    homeassistant = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    homeassistant.__path__ = []
    components = sys.modules.setdefault(
        "homeassistant.components", types.ModuleType("homeassistant.components")
    )
    components.__path__ = []
    device_tracker_module = types.ModuleType("homeassistant.components.device_tracker")
    device_tracker_module.ScannerEntity = type("ScannerEntity", (), {})
    tracker_const = types.ModuleType("homeassistant.components.device_tracker.const")
    tracker_const.SourceType = SimpleNamespace(ROUTER="router")
    components.device_tracker = device_tracker_module
    sensor_module = types.ModuleType("homeassistant.components.sensor")
    sensor_module.SensorEntity = type("SensorEntity", (), {})
    sensor_module.SensorDeviceClass = SimpleNamespace(TIMESTAMP="timestamp")
    components.sensor = sensor_module
    sys.modules["homeassistant.components.device_tracker"] = device_tracker_module
    sys.modules["homeassistant.components.device_tracker.const"] = tracker_const
    sys.modules["homeassistant.components.sensor"] = sensor_module

    helpers = sys.modules.setdefault(
        "homeassistant.helpers", types.ModuleType("homeassistant.helpers")
    )
    helpers.__path__ = []
    entity = sys.modules.setdefault(
        "homeassistant.helpers.entity", types.ModuleType("homeassistant.helpers.entity")
    )
    entity.DeviceInfo = lambda **kwargs: kwargs
    entity.EntityCategory = SimpleNamespace(DIAGNOSTIC="diagnostic")

    class DataUpdateCoordinator:
        def __init__(self, hass, _logger, **_kwargs):
            self.hass = hass
            self.data = None
            self.last_update_success = False

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    update_coordinator = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.ConfigEntryNotReady = type("ConfigEntryNotReady", (Exception,), {})
    sys.modules["homeassistant.exceptions"] = exceptions

    util = sys.modules.setdefault("homeassistant.util", types.ModuleType("homeassistant.util"))
    util.__path__ = []
    dt = types.ModuleType("homeassistant.util.dt")
    dt.parse_datetime = lambda value: None
    dt.utcnow = lambda: datetime.now(timezone.utc)
    util.dt = dt
    sys.modules["homeassistant.util.dt"] = dt

    technitiumdns = sys.modules.setdefault(
        "technitiumdns", types.ModuleType("technitiumdns")
    )
    technitiumdns.TransportError = type("TransportError", (Exception,), {})


_install_import_stubs()

from custom_components.technitiumdns import device_tracker, dns_logs, sensor, utils  # noqa: E402


CLIENT_IP = "192.168.1.25"
CLIENT_MAC = "AA:BB:CC:DD:EE:FF"


def _activity_lease():
    return {
        "ip_address": CLIENT_IP,
        "mac_address": CLIENT_MAC,
        "lease_obtained": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "last_seen": None,
        "is_stale": None,
        "minutes_since_seen": None,
        "activity_score": None,
        "is_actively_used": None,
        "activity_evidence": None,
        "score_breakdown": None,
        "activity_status": "unavailable",
        "activity_summary": "",
    }


def _coordinator(*, smart_activity=True):
    coordinator = device_tracker.TechnitiumDHCPCoordinator(
        SimpleNamespace(data={}),
        SimpleNamespace(),
        60,
        log_tracking=True,
        smart_activity=smart_activity,
    )
    coordinator._cleanup_orphaned_entities = AsyncMock()
    return coordinator


class TestDHCPTrackerActivityStatus(unittest.IsolatedAsyncioTestCase):
    """Unknown DNS evidence must not become an activity score or state."""

    async def test_default_dns_disabled_mode_keeps_lease_connected(self):
        api_lease = SimpleNamespace(
            type="Dynamic",
            address=CLIENT_IP,
            hardware_address=CLIENT_MAC,
            host_name="client",
            address_status="InUse",
            lease_expires=None,
            lease_obtained=None,
        )
        api = SimpleNamespace(dhcp=SimpleNamespace(leasing=None))
        api.dhcp.leases_list = AsyncMock(return_value=[api_lease])
        coordinator = device_tracker.TechnitiumDHCPCoordinator(
            SimpleNamespace(data={}), api, 60
        )
        coordinator._cleanup_orphaned_entities = AsyncMock()

        with patch.object(device_tracker, "test_dns_logs_api", new_callable=AsyncMock) as test_api:
            coordinator.data = await coordinator._async_update_data()

        self.assertFalse(coordinator.log_tracking)
        self.assertTrue(coordinator.smart_activity_enabled)
        test_api.assert_not_awaited()
        self.assertEqual(coordinator.data[0]["activity_status"], "disabled")
        self.assertIsNone(coordinator.data[0]["activity_score"])
        self.assertIsNone(coordinator.data[0]["is_actively_used"])
        self.assertTrue(
            device_tracker.TechnitiumDHCPDeviceTracker(
                coordinator, coordinator.data[0], "server", "entry", "server-id"
            ).is_connected
        )

    async def test_unavailable_dns_api_leaves_activity_unknown(self):
        coordinator = _coordinator()
        lease = _activity_lease()

        with patch.object(
            device_tracker,
            "test_dns_logs_api",
            new_callable=AsyncMock,
            return_value={"available": False, "message": "offline"},
        ):
            await coordinator._get_last_seen_for_devices([lease])

        self.assertEqual(lease["activity_status"], "unavailable")
        self.assertIsNone(lease["activity_score"])
        self.assertIsNone(lease["is_actively_used"])

    async def test_empty_logs_are_no_data_not_inactive(self):
        coordinator = _coordinator()
        lease = _activity_lease()

        with (
            patch.object(
                device_tracker,
                "test_dns_logs_api",
                new_callable=AsyncMock,
                return_value={"available": True},
            ),
            patch.object(
                device_tracker,
                "get_dns_logs_for_analysis",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                coordinator,
                "_perform_basic_last_seen_tracking",
                new_callable=AsyncMock,
            ) as basic_tracking,
        ):
            await coordinator._get_last_seen_for_devices([lease])

        self.assertEqual(lease["activity_status"], "no_data")
        self.assertIsNone(lease["activity_score"])
        self.assertIsNone(lease["is_actively_used"])
        self.assertIsNone(lease["last_seen"])
        self.assertIsNone(lease["minutes_since_seen"])
        self.assertIsNone(lease["score_breakdown"])
        basic_tracking.assert_not_awaited()

    async def test_batch_analysis_error_is_not_mislabeled_no_data(self):
        coordinator = _coordinator()
        failed_lease = _activity_lease()
        healthy_ip = "192.168.1.26"
        healthy_lease = _activity_lease()
        healthy_lease["ip_address"] = healthy_ip

        def analyze_device(_dns_logs, ip_address):
            if ip_address == CLIENT_IP:
                raise RuntimeError("device analysis failed")
            return {
                "total_queries": 1,
                "activity_score": 72.5,
                "is_actively_used": True,
                "analysis_summary": "Recent queries",
            }

        with (
            patch.object(
                device_tracker,
                "test_dns_logs_api",
                new_callable=AsyncMock,
                return_value={"available": True},
            ),
            patch.object(
                device_tracker,
                "get_dns_logs_for_analysis",
                new_callable=AsyncMock,
                return_value=[{
                    "clientIpAddress": CLIENT_IP,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            ),
            patch.object(
                coordinator.activity_analyzer,
                "analyze_device_activity",
                side_effect=analyze_device,
            ),
        ):
            await coordinator._get_last_seen_for_devices(
                [failed_lease, healthy_lease]
            )

        self.assertEqual(failed_lease["activity_status"], "error")
        self.assertIsNone(failed_lease["activity_score"])
        self.assertIsNone(failed_lease["is_actively_used"])
        self.assertIsNone(failed_lease["last_seen"])
        self.assertIsNone(failed_lease["score_breakdown"])
        self.assertEqual(healthy_lease["activity_status"], "analyzed")
        self.assertEqual(healthy_lease["activity_score"], 72.5)
        self.assertTrue(healthy_lease["is_actively_used"])

    async def test_insufficient_evidence_remains_unknown_in_lease(self):
        coordinator = _coordinator()
        lease = _activity_lease()
        evidence = {
            "minimum_recent_queries": 3,
            "recent_window_minutes": 30,
            "observed_recent_queries": 1,
        }

        with (
            patch.object(
                device_tracker,
                "test_dns_logs_api",
                new_callable=AsyncMock,
                return_value={"available": True},
            ),
            patch.object(
                device_tracker,
                "get_dns_logs_for_analysis",
                new_callable=AsyncMock,
                return_value=[{
                    "clientIpAddress": CLIENT_IP,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            ),
            patch.object(
                device_tracker,
                "analyze_batch_device_activity",
                return_value={CLIENT_IP: {
                    "status": "insufficient_evidence",
                    "total_queries": 1,
                    "activity_score": None,
                    "is_actively_used": None,
                    "activity_evidence": evidence,
                    "analysis_summary": "Insufficient recent DNS evidence",
                }},
            ),
        ):
            await coordinator._get_last_seen_for_devices([lease])

        self.assertEqual(lease["activity_status"], "insufficient_evidence")
        self.assertIsNone(lease["activity_score"])
        self.assertIsNone(lease["is_actively_used"])
        self.assertIsNone(lease["is_stale"])
        self.assertIsNone(lease["last_seen"])
        self.assertIsNone(lease["minutes_since_seen"])
        self.assertIsNone(lease["score_breakdown"])
        self.assertEqual(lease["activity_evidence"], evidence)

    async def test_valid_device_logs_are_marked_analyzed(self):
        coordinator = _coordinator()
        lease = _activity_lease()
        activity_data = {
            "total_queries": 1,
            "activity_score": 72.5,
            "is_actively_used": True,
            "analysis_summary": "Recent queries",
            "score_breakdown": {
                "background_score": 80,
                "protocol_score": 60,
            },
        }
        last_seen = datetime.now(timezone.utc).isoformat()
        lease_start = datetime.fromisoformat(last_seen) - timedelta(minutes=2)
        lease["lease_obtained"] = lease_start.isoformat()
        older_seen = (lease_start - timedelta(minutes=3)).isoformat()

        with (
            patch.object(
                device_tracker,
                "test_dns_logs_api",
                new_callable=AsyncMock,
                return_value={"available": True},
            ),
            patch.object(
                device_tracker,
                "get_dns_logs_for_analysis",
                new_callable=AsyncMock,
                return_value=[
                    {"clientIpAddress": CLIENT_IP, "timestamp": older_seen},
                    {"clientIpAddress": CLIENT_IP, "timestamp": last_seen},
                ],
            ),
            patch.object(
                device_tracker,
                "analyze_batch_device_activity",
                return_value={CLIENT_IP: activity_data},
            ) as analyze_batch,
        ):
            await coordinator._get_last_seen_for_devices([lease])

        self.assertEqual(lease["activity_status"], "analyzed")
        self.assertEqual(lease["activity_score"], 72.5)
        self.assertTrue(lease["is_actively_used"])
        self.assertEqual(lease["score_breakdown"], activity_data["score_breakdown"])
        self.assertEqual(lease["last_seen"], last_seen)
        self.assertIsInstance(lease["minutes_since_seen"], int)
        analyzed_logs = analyze_batch.call_args.args[0]
        self.assertEqual(len(analyzed_logs), 1)
        self.assertEqual(analyzed_logs[0]["timestamp"], last_seen)

    async def test_processing_exception_marks_error_without_fallback_activity(self):
        coordinator = _coordinator()
        lease = _activity_lease()

        with (
            patch.object(
                device_tracker,
                "test_dns_logs_api",
                new_callable=AsyncMock,
                return_value={"available": True},
            ),
            patch.object(
                device_tracker,
                "get_dns_logs_for_analysis",
                new_callable=AsyncMock,
                return_value=[{
                    "clientIpAddress": CLIENT_IP,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            ),
            patch.object(
                device_tracker,
                "analyze_batch_device_activity",
                side_effect=RuntimeError("analysis failed"),
            ),
        ):
            await coordinator._get_last_seen_for_devices([lease])

        self.assertEqual(lease["activity_status"], "error")
        self.assertIsNone(lease["activity_score"])
        self.assertIsNone(lease["is_actively_used"])

    async def test_log_helper_can_propagate_query_errors_to_activity_status(self):
        api = SimpleNamespace()

        with (
            patch.object(
                dns_logs,
                "test_dns_logs_api",
                new_callable=AsyncMock,
                return_value={"available": True},
            ),
            patch.object(
                dns_logs,
                "_query_logs",
                new_callable=AsyncMock,
                side_effect=RuntimeError("query failed"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                await dns_logs.get_dns_logs_for_analysis(api, raise_on_error=True)

    async def test_duplicate_ip_leases_have_ambiguous_activity(self):
        coordinator = _coordinator()
        first = _activity_lease()
        second = _activity_lease()
        second["mac_address"] = "11:22:33:44:55:66"

        with patch.object(
            device_tracker,
            "test_dns_logs_api",
            new_callable=AsyncMock,
        ) as test_api:
            await coordinator._get_last_seen_for_devices([first, second])

        test_api.assert_not_awaited()
        for lease in (first, second):
            self.assertEqual(lease["activity_status"], "ambiguous")
            self.assertIsNone(lease["activity_score"])
            self.assertIsNone(lease["is_actively_used"])
            self.assertIsNone(lease["last_seen"])
            self.assertIsNone(lease["is_stale"])

    async def test_missing_lease_start_has_ambiguous_activity(self):
        coordinator = _coordinator()
        lease = _activity_lease()
        lease["lease_obtained"] = None

        with patch.object(
            device_tracker,
            "test_dns_logs_api",
            new_callable=AsyncMock,
        ) as test_api:
            await coordinator._get_last_seen_for_devices([lease])

        test_api.assert_not_awaited()
        self.assertEqual(lease["activity_status"], "ambiguous")
        self.assertIsNone(lease["last_seen"])

    async def test_no_data_does_not_overwrite_ambiguous_peer_lease(self):
        coordinator = _coordinator()
        ambiguous = _activity_lease()
        duplicate = _activity_lease()
        duplicate["mac_address"] = "11:22:33:44:55:66"
        unique = _activity_lease()
        unique["ip_address"] = "192.168.1.30"

        with (
            patch.object(
                device_tracker,
                "test_dns_logs_api",
                new_callable=AsyncMock,
                return_value={"available": True},
            ),
            patch.object(
                device_tracker,
                "get_dns_logs_for_analysis",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await coordinator._get_last_seen_for_devices([ambiguous, duplicate, unique])

        self.assertEqual(ambiguous["activity_status"], "ambiguous")
        self.assertEqual(duplicate["activity_status"], "ambiguous")
        self.assertEqual(unique["activity_status"], "no_data")


class TestDHCPLeaseEligibility(unittest.IsolatedAsyncioTestCase):
    """Track valid leases with explicit status or an unexpired lease time."""

    async def test_unexpired_lease_without_status_is_trackable(self):
        now = datetime.now(timezone.utc)
        lease = SimpleNamespace(
            type="Reserved",
            address=CLIENT_IP,
            hardware_address=CLIENT_MAC,
            host_name="client",
            address_status=None,
            lease_expires=now + timedelta(hours=1),
            lease_obtained=now - timedelta(minutes=5),
        )
        api = SimpleNamespace(dhcp=SimpleNamespace(leases_list=AsyncMock(return_value=[lease])))
        coordinator = device_tracker.TechnitiumDHCPCoordinator(
            SimpleNamespace(data={}), api, 60
        )
        coordinator._cleanup_orphaned_entities = AsyncMock()

        leases = await coordinator._async_update_data()

        self.assertEqual(len(leases), 1)
        self.assertIsNone(leases[0]["address_status"])
        coordinator._cleanup_orphaned_entities.assert_not_awaited()

    async def test_missing_status_requires_valid_future_expiry(self):
        for expiry in (None, "invalid", datetime.now(timezone.utc) - timedelta(minutes=1)):
            with self.subTest(expiry=expiry):
                lease = SimpleNamespace(
                    type="Dynamic",
                    address=CLIENT_IP,
                    hardware_address=CLIENT_MAC,
                    host_name="client",
                    address_status=None,
                    lease_expires=expiry,
                    lease_obtained=None,
                )
                api = SimpleNamespace(dhcp=SimpleNamespace(leases_list=AsyncMock(return_value=[lease])))
                coordinator = device_tracker.TechnitiumDHCPCoordinator(
                    SimpleNamespace(data={}), api, 60
                )

                self.assertEqual(await coordinator._async_update_data(), [])

    async def test_dynamic_and_reserved_in_use_are_trackable_only_when_unexpired(self):
        now = datetime.now(timezone.utc)

        def api_lease(address, lease_type, address_status, expires):
            return SimpleNamespace(
                type=lease_type,
                address=address,
                hardware_address=f"AA:BB:CC:DD:EE:{len(address):02X}",
                host_name="client",
                address_status=address_status,
                lease_expires=expires,
                lease_obtained=now - timedelta(minutes=5),
            )

        api_leases = [
            api_lease("192.168.1.25", "Dynamic", "InUse", now + timedelta(hours=1)),
            api_lease("192.168.1.26", "Reserved", "InUse", now + timedelta(hours=1)),
            api_lease("192.168.1.27", "Dynamic", "Available", now + timedelta(hours=1)),
            api_lease("192.168.1.28", "Reserved", "InUse", now - timedelta(seconds=1)),
            api_lease("192.168.1.29", "Dynamic", None, now + timedelta(hours=1)),
        ]
        api = SimpleNamespace(dhcp=SimpleNamespace())
        api.dhcp.leases_list = AsyncMock(return_value=api_leases)
        coordinator = device_tracker.TechnitiumDHCPCoordinator(
            SimpleNamespace(data={}), api, 60
        )
        coordinator._cleanup_orphaned_entities = AsyncMock()

        leases = await coordinator._async_update_data()

        self.assertEqual(
            [lease["ip_address"] for lease in leases],
            ["192.168.1.25", "192.168.1.26", "192.168.1.29"],
        )
        self.assertEqual([lease["type"] for lease in leases], ["Dynamic", "Reserved", "Dynamic"])
        self.assertEqual([lease["address_status"] for lease in leases], ["InUse", "InUse", None])
        self.assertTrue(all(lease["lease_expires"] for lease in leases))


class TestDHCPLeaseTimestampParsing(unittest.TestCase):
    """Timestamp parsing produces aware UTC values and rejects invalid input."""

    def test_naive_and_aware_iso_values_and_datetime_inputs_are_utc(self):
        naive = utils.parse_timestamp("2026-01-02T03:04:05")
        aware = utils.parse_timestamp("2026-01-02T05:04:05+02:00")
        datetime_input = utils.parse_timestamp(datetime(2026, 1, 2, 3, 4, 5))

        self.assertEqual(naive.utcoffset(), timedelta(0))
        self.assertEqual(aware, naive)
        self.assertEqual(datetime_input, naive)

    def test_invalid_values_return_none(self):
        for value in (None, "", "not-a-date", 123):
            with self.subTest(value=value):
                self.assertIsNone(utils.parse_timestamp(value))


class TestBasicLastSeen(unittest.IsolatedAsyncioTestCase):
    """Basic last-seen uses the newest valid post-lease DNS record."""

    async def test_out_of_order_records_use_max_timestamp_after_lease_start(self):
        lease_start = datetime.now(timezone.utc) - timedelta(minutes=20)
        old = lease_start - timedelta(seconds=1)
        newer = lease_start + timedelta(minutes=2)
        latest = lease_start + timedelta(minutes=5)
        api = SimpleNamespace()

        with (
            patch.object(
                dns_logs,
                "test_dns_logs_api",
                new_callable=AsyncMock,
                return_value={"available": True},
            ),
            patch.object(
                dns_logs,
                "_query_logs",
                new_callable=AsyncMock,
                return_value=[
                    {"clientIpAddress": CLIENT_IP, "timestamp": newer.isoformat()},
                    {"clientIpAddress": CLIENT_IP, "timestamp": old.isoformat()},
                    {"clientIpAddress": CLIENT_IP, "timestamp": "invalid"},
                    {"clientIpAddress": CLIENT_IP, "timestamp": latest.isoformat()},
                ],
            ),
        ):
            last_seen = await dns_logs.get_last_seen_for_multiple_ips(
                api,
                [CLIENT_IP],
                lease_obtained_by_ip={CLIENT_IP: lease_start},
            )

        self.assertEqual(last_seen[CLIENT_IP], latest.isoformat())


class TestDHCPTrackerLeasePresence(unittest.TestCase):
    """Tracker connectivity is the presence of the current DHCP lease."""

    def test_activity_does_not_override_present_or_missing_lease(self):
        lease = {
            "ip_address": CLIENT_IP,
            "mac_address": CLIENT_MAC,
            "activity_score": 0,
            "is_actively_used": False,
            "is_stale": True,
        }
        coordinator = SimpleNamespace(
            data=[lease], last_update_success=True, smart_activity_enabled=True
        )
        tracker = device_tracker.TechnitiumDHCPDeviceTracker(
            coordinator, lease, "server", "entry", "server-id"
        )

        with self.assertNoLogs(device_tracker._LOGGER, level="DEBUG"):
            self.assertTrue(all(tracker.is_connected for _ in range(20)))
        self.assertEqual(
            tracker.extra_state_attributes["activity_status"], "unknown"
        )
        coordinator.data = []
        with self.assertNoLogs(device_tracker._LOGGER, level="DEBUG"):
            self.assertFalse(tracker.is_connected)

    def test_missing_coordinator_data_is_unavailable(self):
        lease = {"mac_address": CLIENT_MAC, "hostname": "client"}
        coordinator = SimpleNamespace(
            data=None, last_update_success=True, smart_activity_enabled=True
        )
        tracker = device_tracker.TechnitiumDHCPDeviceTracker(
            coordinator, lease, "server", "entry", "server-id"
        )

        self.assertFalse(tracker.available)

    def test_statistics_sensor_state_read_does_not_log_at_debug(self):
        coordinator = SimpleNamespace(
            data={"queries": 42}, last_update_success=True
        )
        stats_sensor = sensor.TechnitiumDNSSensor(
            coordinator, "queries", "server", "entry"
        )

        with self.assertNoLogs(sensor._LOGGER, level="DEBUG"):
            self.assertEqual(stats_sensor.state, 42)


class TestDHCPTrackerDynamicEntities(unittest.IsolatedAsyncioTestCase):
    """Tracker entities follow coordinator lease changes without duplicates."""

    async def test_empty_startup_adds_new_tracker_once_and_unloads_listener(self):
        callbacks = []
        remove_listener = Mock()
        coordinator = SimpleNamespace(
            data=[],
            async_config_entry_first_refresh=AsyncMock(),
            async_add_listener=lambda callback: callbacks.append(callback)
            or remove_listener,
        )
        entry = SimpleNamespace(entry_id="entry", options={})
        hass = SimpleNamespace(
            data={
                device_tracker.DOMAIN: {
                    entry.entry_id: {
                        "api": object(),
                        "server_name": "server",
                        "server_device_id": "server-id",
                    }
                }
            }
        )
        added_batches = []

        def add_entities(entities, update_before_add):
            added_batches.append((entities, update_before_add))

        with patch.object(
            device_tracker,
            "TechnitiumDHCPCoordinator",
            return_value=coordinator,
        ):
            await device_tracker.async_setup_entry(hass, entry, add_entities)

        self.assertEqual(added_batches, [([], True)])
        lease = _activity_lease()
        coordinator.data = [lease]
        callbacks[0]()
        callbacks[0]()
        coordinator.data = []
        callbacks[0]()
        coordinator.data = [lease]
        callbacks[0]()

        self.assertEqual(len(added_batches), 2)
        self.assertEqual(len(added_batches[1][0]), 1)
        self.assertEqual(
            added_batches[1][0][0].unique_id,
            "technitiumdns_device_tracker_aabbccddeeff",
        )

        await device_tracker.async_unload_entry(hass, entry)
        remove_listener.assert_called_once_with()
        self.assertNotIn(
            "device_tracker_listener",
            hass.data[device_tracker.DOMAIN][entry.entry_id],
        )


class TestDynamicDHCPSensors(unittest.IsolatedAsyncioTestCase):
    """Dynamic diagnostics retry failed additions and retain registration history."""

    def setUp(self):
        self.callbacks = []
        self.entry = SimpleNamespace(entry_id="entry")
        self.coordinator = SimpleNamespace(
            data=[],
            last_update_success=True,
            async_add_listener=lambda callback: self.callbacks.append(callback)
            or Mock(),
            hass=SimpleNamespace(
                data={sensor.DOMAIN: {"entry": {"server_device_id": "server-id"}}}
            ),
        )

    async def test_sensor_add_retries_and_reappearance_does_not_duplicate(self):
        add_attempts = []

        def add_entities(entities, update_before_add):
            add_attempts.append(entities)
            if len(add_attempts) == 1:
                raise RuntimeError("temporary registration failure")

        manager = sensor.DynamicSensorManager(
            self.coordinator.hass,
            self.entry,
            add_entities,
            self.coordinator,
            "server",
        )
        await manager.setup()

        lease = _activity_lease()
        self.coordinator.data = [lease]
        await manager._handle_coordinator_update()
        self.assertNotIn(CLIENT_MAC, manager.known_devices)

        await manager._handle_coordinator_update()
        self.assertIn(CLIENT_MAC, manager.known_devices)
        await manager._handle_coordinator_update()
        self.coordinator.data = []
        await manager._handle_coordinator_update()
        self.coordinator.data = [lease]
        await manager._handle_coordinator_update()

        self.assertEqual(len(add_attempts), 2)
        self.assertEqual(len(add_attempts[0]), 11)
        self.assertEqual(len(add_attempts[1]), 11)

    def test_missing_and_no_data_diagnostics_are_unavailable_or_unknown(self):
        ip_sensor = sensor.TechnitiumDHCPDeviceIPSensor(
            self.coordinator, CLIENT_MAC, "server", "entry", "client"
        )
        hostname_sensor = sensor.TechnitiumDHCPDeviceHostnameSensor(
            self.coordinator, CLIENT_MAC, "server", "entry", "client"
        )

        self.assertFalse(ip_sensor.available)
        self.assertIsNone(ip_sensor.native_value)
        self.assertIsNone(hostname_sensor.native_value)

        self.coordinator.data = [{
            "mac_address": CLIENT_MAC,
            "activity_status": "no_data",
            "activity_score": None,
            "is_stale": None,
            "minutes_since_seen": None,
            "last_seen": None,
            "score_breakdown": None,
        }]
        score_sensor = sensor.TechnitiumDHCPDeviceActivityScoreSensor(
            self.coordinator, CLIENT_MAC, "server", "entry", "client"
        )
        minutes_sensor = sensor.TechnitiumDHCPDeviceMinutesSinceSeenSensor(
            self.coordinator, CLIENT_MAC, "server", "entry", "client"
        )
        stale_sensor = sensor.TechnitiumDHCPDeviceIsStaleSensor(
            self.coordinator, CLIENT_MAC, "server", "entry", "client"
        )

        self.assertTrue(score_sensor.available)
        self.assertIsNone(score_sensor.native_value)
        self.assertIsNone(minutes_sensor.native_value)
        self.assertIsNone(stale_sensor.native_value)


if __name__ == "__main__":
    unittest.main()