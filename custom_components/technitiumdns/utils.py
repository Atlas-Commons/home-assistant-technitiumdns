"""Utility functions for TechnitiumDNS integration."""

import ipaddress
import logging
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MAX_IP_RANGE_ADDRESSES = 10_000


@dataclass(frozen=True)
class ParsedIPRanges:
    """Compact, merged IPv4 intervals parsed from a filter configuration."""

    intervals: tuple[tuple[int, int], ...]
    address_count: int
    error: str | None = None


def server_device_info(entry_id: str, server_name: str) -> DeviceInfo:
    """Return device info for a Technitium DNS server config entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=server_name,
        manufacturer="Technitium",
        model="DNS Server",
    )


def normalize_mac_address(mac_address: str) -> str:
    """Normalize MAC address to uppercase with colons format.
    
    Converts MAC addresses from various formats to consistent format:
    - AA-BB-CC-DD-EE-FF -> AA:BB:CC:DD:EE:FF
    - aabbccddeeff -> AA:BB:CC:DD:EE:FF
    - aa:bb:cc:dd:ee:ff -> AA:BB:CC:DD:EE:FF
    
    Args:
        mac_address: MAC address in any common format
        
    Returns:
        MAC address in uppercase with colons format (AA:BB:CC:DD:EE:FF)
    """
    if not mac_address:
        return ""
    
    mac_upper = mac_address.upper()
    
    if len(mac_upper) == 12:  # No separators: AABBCCDDEEFF
        return ':'.join([mac_upper[i:i+2] for i in range(0, 12, 2)])
    elif len(mac_upper) == 17:  # With separators: AA-BB-CC-DD-EE-FF or AA:BB:CC:DD:EE:FF
        return mac_upper.replace('-', ':')
    else:
        return mac_upper  # Keep as-is if unexpected format


def normalize_hostname(hostname) -> str:
    """Normalize hostname to a safe string value.
    
    Ensures hostname is always a string, handling None and non-string types.
    Logs a warning when unexpected types (dict, list, etc.) are encountered.
    
    Args:
        hostname: Hostname value from API (may be str, None, or unexpected type)
        
    Returns:
        Empty string if None, string representation otherwise
    """
    if hostname is None:
        return ""

    if isinstance(hostname, str):
        return hostname

    # Unexpected type - log warning and convert to string
    hostname_type = type(hostname).__name__
    _LOGGER.warning(
        "Unexpected hostname type '%s' (value: %s). Converting to string. "
        "This may indicate an API format change.",
        hostname_type,
        repr(hostname)[:100]  # Limit to 100 chars to avoid log spam
    )
    return str(hostname)

@lru_cache(maxsize=128)
def parse_ip_ranges(ip_ranges_str: str) -> ParsedIPRanges:
    """
    Parse IP ranges into merged integer intervals without expanding addresses.
    
    Supports:
    - Single IPs: 192.168.1.100
    - CIDR ranges: 192.168.1.0/24
    - IP ranges: 192.168.1.1-192.168.1.50
    - Multiple entries separated by commas, semicolons, or newlines
    
    Args:
        ip_ranges_str: String containing IP addresses/ranges
        
    Returns:
        Parsed intervals, their unique address count, and any parse error.
    """
    if not ip_ranges_str or not ip_ranges_str.strip():
        return ParsedIPRanges((), 0, "At least one IP address or range is required")

    intervals = []
    parse_error = None
    for range_entry in re.split(r"[,;\r\n]+", ip_ranges_str):
        range_entry = range_entry.strip()
        if not range_entry:
            continue

        try:
            if "/" in range_entry:
                network = ipaddress.IPv4Network(range_entry, strict=False)
                start = int(network.network_address)
                end = int(network.broadcast_address)
                if network.prefixlen <= 30:
                    start += 1
                    end -= 1
            elif "-" in range_entry:
                start_text, end_text = range_entry.split("-", 1)
                start = int(ipaddress.IPv4Address(start_text.strip()))
                end = int(ipaddress.IPv4Address(end_text.strip()))
                if start > end:
                    raise ValueError("start IP is greater than end IP")
            else:
                start = end = int(ipaddress.IPv4Address(range_entry))
            intervals.append((start, end))
        except ValueError as err:
            if parse_error is None:
                parse_error = f"Invalid IP address or range '{range_entry}': {err}"
            _LOGGER.warning("Invalid IP address or range '%s': %s", range_entry, err)

    if not intervals:
        return ParsedIPRanges((), 0, parse_error or "No valid IP addresses found")

    merged_intervals: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged_intervals and start <= merged_intervals[-1][1] + 1:
            previous_start, previous_end = merged_intervals[-1]
            merged_intervals[-1] = (previous_start, max(previous_end, end))
        else:
            merged_intervals.append((start, end))

    address_count = sum(end - start + 1 for start, end in merged_intervals)
    return ParsedIPRanges(tuple(merged_intervals), address_count, parse_error)


def should_track_ip(ip_address: str, filter_mode: str, ip_ranges_str: str) -> bool:
    """
    Determine if an IP address should be tracked based on filter settings.
    
    Args:
        ip_address: IP address to check
        filter_mode: One of 'disabled', 'include', 'exclude'
        ip_ranges_str: String containing IP ranges configuration
        
    Returns:
        True if the IP should be tracked, False otherwise
    """
    if filter_mode == "disabled":
        return True

    if filter_mode not in ("include", "exclude"):
        _LOGGER.warning("Unknown IP filter mode: %s", filter_mode)
        return False
    
    try:
        address = int(ipaddress.IPv4Address(ip_address))
    except ValueError:
        _LOGGER.warning("Invalid IP address format: %s", ip_address)
        return False
    
    configured_ranges = parse_ip_ranges(ip_ranges_str)
    if (
        configured_ranges.error
        or not configured_ranges.intervals
        or configured_ranges.address_count > MAX_IP_RANGE_ADDRESSES
    ):
        return False

    interval_index = bisect_right(configured_ranges.intervals, (address, 1 << 32)) - 1
    is_configured = (
        interval_index >= 0
        and configured_ranges.intervals[interval_index][0] <= address
        <= configured_ranges.intervals[interval_index][1]
    )
    return is_configured if filter_mode == "include" else not is_configured


def validate_ip_ranges_config(ip_ranges_str: str) -> tuple[bool, str]:
    """
    Validate IP ranges configuration string.
    
    Args:
        ip_ranges_str: String containing IP ranges configuration
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    parsed_ranges = parse_ip_ranges(ip_ranges_str)
    if parsed_ranges.error:
        return False, parsed_ranges.error

    if parsed_ranges.address_count > MAX_IP_RANGE_ADDRESSES:
        return (
            False,
            f"Too many IP addresses ({parsed_ranges.address_count}). "
            f"Maximum {MAX_IP_RANGE_ADDRESSES:,} allowed.",
        )

    return (
        True,
        f"Configuration valid. {parsed_ranges.address_count} IP addresses will be processed.",
    )


def parse_timestamp(timestamp_value):
    """Parse an ISO timestamp or datetime and return timezone-aware UTC."""
    if isinstance(timestamp_value, datetime):
        parsed = timestamp_value
    elif isinstance(timestamp_value, str) and timestamp_value:
        try:
            parsed = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
        except ValueError:
            _LOGGER.warning("Failed to parse timestamp '%s'", timestamp_value)
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
