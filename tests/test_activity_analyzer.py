"""Focused regression tests for DNS log activity analysis."""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch


INTEGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "custom_components" / "technitiumdns"
)
integration_package = types.ModuleType("custom_components.technitiumdns")
integration_package.__path__ = [str(INTEGRATION_PATH)]
sys.modules["custom_components.technitiumdns"] = integration_package

from custom_components.technitiumdns import activity_analyzer, dns_logs  # noqa: E402


CLIENT_IP = "192.168.1.25"
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


class FixedDateTime(datetime):
    """Provide a stable current time for window-boundary tests."""

    @classmethod
    def now(cls, tz=None):
        return NOW if tz else NOW.replace(tzinfo=None)


def _activity_log(minutes_ago, qname="www.example.com", protocol="TCP"):
    return {
        "clientIpAddress": CLIENT_IP,
        "timestamp": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "protocol": protocol,
        "qname": qname,
        "qtype": "A",
    }


class TestSmartActivityAnalyzer(unittest.TestCase):
    """Cover documented DNS log shapes and timestamp edge cases."""

    def setUp(self):
        self.analyzer = activity_analyzer.SmartActivityAnalyzer()

    def test_flat_and_nested_query_fields_have_equal_diversity(self):
        flat_logs = [
            {"qname": f"host-{index}.example.com", "qtype": "A"}
            for index in range(5)
        ]
        nested_logs = [
            {"question": {"name": log["qname"], "type": log["qtype"]}}
            for log in flat_logs
        ]

        self.assertEqual(
            self.analyzer._calculate_diversity_score(flat_logs),
            self.analyzer._calculate_diversity_score(nested_logs),
        )
        self.assertGreater(self.analyzer._calculate_diversity_score(flat_logs), 0)

    def test_null_protocol_uses_neutral_unknown_weight(self):
        timestamp = (NOW - timedelta(minutes=5)).isoformat()
        logs = [{
            "clientIpAddress": CLIENT_IP,
            "timestamp": timestamp,
            "protocol": None,
            "qname": "www.example.com",
            "qtype": "A",
        }]

        with patch.object(activity_analyzer, "datetime", FixedDateTime):
            result = self.analyzer.analyze_device_activity(logs, CLIENT_IP)
            filtered = self.analyzer._filter_device_logs(logs, CLIENT_IP)

        self.assertEqual(result["total_queries"], 1)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["activity_score"])
        self.assertIsNone(result["is_actively_used"])
        self.assertEqual(filtered[0]["protocol"], "UNKNOWN")
        self.assertEqual(self.analyzer._calculate_protocol_score(filtered), 50)

    def test_one_recent_query_is_insufficient_evidence(self):
        with patch.object(activity_analyzer, "datetime", FixedDateTime):
            result = self.analyzer.analyze_device_activity(
                [_activity_log(2)], CLIENT_IP
            )

        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["activity_score"])
        self.assertIsNone(result["is_actively_used"])
        self.assertEqual(result["activity_evidence"]["observed_recent_queries"], 1)

    def test_old_burst_inside_analysis_window_is_insufficient(self):
        logs = [_activity_log(age, f"host-{age}.example.com") for age in (119, 118, 117, 116, 115)]

        with patch.object(activity_analyzer, "datetime", FixedDateTime):
            result = self.analyzer.analyze_device_activity(logs, CLIENT_IP)

        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["total_queries"], 5)
        self.assertEqual(result["activity_evidence"]["observed_recent_queries"], 0)
        self.assertEqual(result["activity_evidence"]["newest_query_age_minutes"], 115.0)
        self.assertIsNone(result["activity_score"])
        self.assertIsNone(result["is_actively_used"])

    def test_recent_adequate_sample_is_scored(self):
        logs = [
            _activity_log(age, domain)
            for age, domain in zip(
                (3, 2, 1),
                ("alpha.example.com", "bravo.example.com", "charlie.example.com"),
            )
        ]

        with patch.object(activity_analyzer, "datetime", FixedDateTime):
            result = self.analyzer.analyze_device_activity(logs, CLIENT_IP)

        self.assertEqual(result["status"], "analyzed")
        self.assertEqual(result["activity_evidence"]["observed_recent_queries"], 3)
        self.assertIsInstance(result["activity_score"], float)
        self.assertTrue(result["is_actively_used"])

    def test_empty_sample_has_unknown_activity_and_no_data_status(self):
        with patch.object(activity_analyzer, "datetime", FixedDateTime):
            result = self.analyzer.analyze_device_activity([], CLIENT_IP)

        self.assertEqual(result["status"], "no_data")
        self.assertIsNone(result["activity_score"])
        self.assertIsNone(result["is_actively_used"])
        self.assertEqual(result["activity_evidence"]["observed_recent_queries"], 0)

    def test_background_domain_matching_respects_dns_label_boundaries(self):
        matches = activity_analyzer._matches_background_domain

        self.assertTrue(matches("cloudflare.com", "cloudflare.com"))
        self.assertTrue(matches("API.Cloudflare.COM.", "cloudflare.com"))
        self.assertFalse(matches("notcloudflare.com", "cloudflare.com"))
        self.assertFalse(matches("cloudflare.com.example.net", "cloudflare.com"))
        self.assertTrue(
            self.analyzer._is_background_query(
                {"qname": "API.Cloudflare.COM.", "qtype": "A"}
            )
        )
        self.assertFalse(
            self.analyzer._is_background_query(
                {"qname": "notcloudflare.com", "qtype": "A"}
            )
        )

    def test_background_prefix_and_path_patterns_are_handled_explicitly(self):
        matches = activity_analyzer._matches_background_domain

        self.assertTrue(matches("time.cloudflare.com", "time."))
        self.assertTrue(matches("api.time.cloudflare.com", "time."))
        self.assertFalse(matches("not-time.cloudflare.com", "time."))
        self.assertFalse(matches("apple.com", "apple.com/updates"))

    def test_malformed_records_are_ignored(self):
        valid_log = {
            "clientIpAddress": CLIENT_IP,
            "timestamp": (NOW - timedelta(minutes=5)).isoformat(),
        }
        logs = [None, "not a DNS log", valid_log]

        with patch.object(activity_analyzer, "datetime", FixedDateTime):
            filtered = self.analyzer._filter_device_logs(logs, CLIENT_IP)

        self.assertEqual(len(filtered), 1)

    def test_entry_conversion_does_not_return_malformed_raw_payload(self):
        entry = SimpleNamespace(raw=["unexpected payload"])

        converted = dns_logs._entry_to_dict(entry)

        self.assertIsInstance(converted, dict)

    def test_timestamp_aliases_and_naive_values_use_utc_consistently(self):
        logs = [
            {"clientIpAddress": CLIENT_IP, "time": "2026-11-07T11:58:00"},
            {
                "clientIpAddress": CLIENT_IP,
                "dateTime": "2026-11-07T11:59:00Z",
            },
        ]

        with patch.object(activity_analyzer, "datetime", FixedDateTime):
            filtered = self.analyzer._filter_device_logs(logs, CLIENT_IP)
            time_span = self.analyzer._get_time_span_minutes(filtered)

        self.assertEqual(len(filtered), 2)
        self.assertEqual(time_span, 1.0)

    def test_records_beyond_clock_skew_are_excluded(self):
        logs = [
            {
                "clientIpAddress": CLIENT_IP,
                "timestamp": (NOW + timedelta(minutes=3)).isoformat(),
            },
            {
                "clientIpAddress": CLIENT_IP,
                "timestamp": (NOW + timedelta(minutes=1)).isoformat(),
            },
        ]

        with patch.object(activity_analyzer, "datetime", FixedDateTime):
            filtered = self.analyzer._filter_device_logs(logs, CLIENT_IP)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["timestamp"], logs[1]["timestamp"])


if __name__ == "__main__":
    unittest.main()