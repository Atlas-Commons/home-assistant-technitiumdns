"""DNS query log helpers for device tracking (uses technitiumdns-api)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from technitiumdns import AsyncClient

_LOGGER = logging.getLogger(__name__)


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp or datetime as timezone-aware UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class DNSLogsUnavailableError(RuntimeError):
    """Raised when DNS logs are unavailable and the caller requests errors."""


def _entry_to_dict(entry: Any) -> dict[str, Any]:
    """Convert a QueryLogEntry (or dict) to the dict shape activity_analyzer expects."""
    if isinstance(entry, dict):
        return entry
    raw = getattr(entry, "raw", None)
    if isinstance(raw, dict):
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
    *,
    raise_on_error: bool = False,
    lease_obtained_by_ip: dict[str, datetime] | None = None,
) -> dict[str, str]:
    """Return each IP's newest valid DNS timestamp after its current lease start."""
    if not ip_addresses:
        return {}

    api_test = await test_dns_logs_api(client)
    if not api_test.get("available", False):
        message = api_test.get("message", "Unknown error")
        _LOGGER.warning(
            "DNS logs API is not available: %s",
            message,
        )
        if raise_on_error:
            raise DNSLogsUnavailableError(message)
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
        lease_starts = {
            ip_address: _parse_timestamp(lease_obtained)
            for ip_address, lease_obtained in (lease_obtained_by_ip or {}).items()
        }
        last_seen_times: dict[str, datetime] = {}

        for entry in entries:
            client_ip = entry.get("clientIpAddress")
            timestamp = _parse_timestamp(entry.get("timestamp"))
            if not client_ip or client_ip not in target_ips or timestamp is None:
                continue

            lease_start = lease_starts.get(client_ip)
            if lease_start is not None and timestamp < lease_start:
                continue

            previous_timestamp = last_seen_times.get(client_ip)
            if previous_timestamp is None or timestamp > previous_timestamp:
                last_seen_times[client_ip] = timestamp

        _LOGGER.info(
            "Batch DNS log query completed: found activity for %d/%d devices",
            len(last_seen_times),
            len(ip_addresses),
        )
        return {
            ip_address: timestamp.isoformat()
            for ip_address, timestamp in last_seen_times.items()
        }
    except Exception as err:
        _LOGGER.error("Error in batch DNS log query: %s", err)
        if raise_on_error:
            raise
        return {}


async def get_dns_logs_for_analysis(
    client: AsyncClient,
    hours_back: int = 2,
    *,
    raise_on_error: bool = False,
) -> list[dict[str, Any]]:
    """Return DNS log entries as dicts for smart activity analysis."""
    api_test = await test_dns_logs_api(client)
    if not api_test.get("available", False):
        message = api_test.get("message", "Unknown error")
        _LOGGER.warning(
            "DNS logs API is not available for activity analysis: %s",
            message,
        )
        if raise_on_error:
            raise DNSLogsUnavailableError(message)
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
        if raise_on_error:
            raise
        return []
