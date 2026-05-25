"""DNS query log helpers for device tracking (uses technitiumdns-api)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from technitiumdns import AsyncClient

_LOGGER = logging.getLogger(__name__)


def _entry_to_dict(entry: Any) -> dict[str, Any]:
    """Convert a QueryLogEntry (or dict) to the dict shape activity_analyzer expects."""
    if isinstance(entry, dict):
        return entry
    raw = getattr(entry, "raw", None)
    if raw:
        return raw
    return {
        "clientIpAddress": getattr(entry, "client_ip_address", None),
        "timestamp": (
            entry.timestamp.isoformat()
            if getattr(entry, "timestamp", None) is not None
            else None
        ),
        "protocol": getattr(entry, "protocol", None),
        "qname": getattr(entry, "qname", None),
        "qtype": getattr(entry, "qtype", None),
    }


async def test_dns_logs_api(client: AsyncClient) -> dict[str, Any]:
    """Test if DNS query logging is available via an installed DNS app."""
    try:
        loggers = await client.apps.list_dns_loggers()
        if not loggers:
            try:
                log_files = await client.logs.list()
                return {
                    "available": False,
                    "method": "file_logs_only",
                    "log_files_count": len(log_files),
                    "error": "no_query_logging",
                    "message": (
                        f"Found {len(log_files)} log files but no DNS apps with query "
                        "logging. Install a DNS app that supports query logging."
                    ),
                }
            except Exception as err:
                return {
                    "available": False,
                    "method": "no_access",
                    "error": str(err),
                    "message": f"Cannot access DNS logs: {err}",
                }

        first = loggers[0]
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)

        page = await client.logs.query(
            name=first["name"],
            class_path=first["classPath"],
            entries_per_page=5,
            page_number=1,
            start=start_time.isoformat() + "Z",
            end=end_time.isoformat() + "Z",
        )
        entries = page.entries if hasattr(page, "entries") else []
        return {
            "available": True,
            "method": "dns_app_logging",
            "app_name": first["name"],
            "app_class": first["classPath"],
            "entries_count": len(entries),
            "sample_entry": _entry_to_dict(entries[0]) if entries else None,
            "message": (
                f"DNS logs accessible via {first['name']} app ({len(entries)} entries found)"
            ),
        }
    except Exception as err:
        return {
            "available": False,
            "error": str(err),
            "message": f"DNS logs API test failed: {err}",
        }


async def _query_logs(
    client: AsyncClient,
    *,
    start_date: str,
    end_date: str,
    limit: int,
    client_ip: str | None = None,
) -> list[dict[str, Any]]:
    """Query DNS logs using the first available query logger app."""
    loggers = await client.apps.list_dns_loggers()
    if not loggers:
        return []

    first = loggers[0]
    page = await client.logs.query(
        name=first["name"],
        class_path=first["classPath"],
        entries_per_page=limit,
        page_number=1,
        start=start_date,
        end=end_date,
        client_ip_address=client_ip,
    )
    return [_entry_to_dict(e) for e in page.entries]


async def get_last_seen_for_multiple_ips(
    client: AsyncClient,
    ip_addresses: list[str],
    hours_back: int = 24,
) -> dict[str, str]:
    """Return {ip_address: last_seen_iso_timestamp} from DNS query logs."""
    if not ip_addresses:
        return {}

    api_test = await test_dns_logs_api(client)
    if not api_test.get("available", False):
        _LOGGER.warning(
            "DNS logs API is not available: %s",
            api_test.get("message", "Unknown error"),
        )
        return {}

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours_back)

    base_limit = 2000
    device_multiplier = max(1, len(ip_addresses) // 10)
    dynamic_limit = min(10000, base_limit + (device_multiplier * 200))

    try:
        entries = await _query_logs(
            client,
            start_date=start_time.isoformat() + "Z",
            end_date=end_time.isoformat() + "Z",
            limit=dynamic_limit,
        )

        target_ips = set(ip_addresses)
        last_seen_times: dict[str, str] = {}

        for entry in entries:
            client_ip = entry.get("clientIpAddress")
            timestamp = entry.get("timestamp")
            if client_ip and timestamp and client_ip in target_ips:
                if client_ip not in last_seen_times:
                    last_seen_times[client_ip] = timestamp
                    if len(last_seen_times) == len(target_ips):
                        break

        _LOGGER.info(
            "Batch DNS log query completed: found activity for %d/%d devices",
            len(last_seen_times),
            len(ip_addresses),
        )
        return last_seen_times
    except Exception as err:
        _LOGGER.error("Error in batch DNS log query: %s", err)
        return {}


async def get_dns_logs_for_analysis(
    client: AsyncClient,
    hours_back: int = 2,
) -> list[dict[str, Any]]:
    """Return DNS log entries as dicts for smart activity analysis."""
    api_test = await test_dns_logs_api(client)
    if not api_test.get("available", False):
        _LOGGER.warning(
            "DNS logs API is not available for activity analysis: %s",
            api_test.get("message", "Unknown error"),
        )
        return []

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours_back)

    try:
        entries = await _query_logs(
            client,
            start_date=start_time.isoformat() + "Z",
            end_date=end_time.isoformat() + "Z",
            limit=5000,
        )
        _LOGGER.info("Retrieved %d DNS log entries for activity analysis", len(entries))
        return entries
    except Exception as err:
        _LOGGER.error("Error getting DNS logs for activity analysis: %s", err)
        return []
