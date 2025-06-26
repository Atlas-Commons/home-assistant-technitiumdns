"""Utility functions for TechnitiumDNS integration."""

import ipaddress
import logging
from typing import List, Set

_LOGGER = logging.getLogger(__name__)


def parse_ip_ranges(ip_ranges_str: str) -> Set[str]:
    """
    Parse IP ranges string into a set of IP addresses.
    
    Supports:
    - Single IPs: 192.168.1.100
    - CIDR ranges: 192.168.1.0/24
    - IP ranges: 192.168.1.1-192.168.1.50
    - Multiple entries separated by commas, semicolons, or newlines
    
    Args:
        ip_ranges_str: String containing IP addresses/ranges
        
    Returns:
        Set of individual IP addresses as strings
    """
    ip_set = set()
    
    if not ip_ranges_str or not ip_ranges_str.strip():
        return ip_set
    
    # Split by various delimiters
    ranges = []
    for delimiter in [',', ';', '\n']:
        if delimiter in ip_ranges_str:
            ranges = [r.strip() for r in ip_ranges_str.split(delimiter)]
            break
    else:
        ranges = [ip_ranges_str.strip()]
    
    for range_entry in ranges:
        range_entry = range_entry.strip()
        if not range_entry:
            continue
            
        try:
            if '-' in range_entry and '/' not in range_entry:
                # Handle IP ranges like 192.168.1.1-192.168.1.50
                start_ip, end_ip = range_entry.split('-', 1)
                start_ip = start_ip.strip()
                end_ip = end_ip.strip()
                
                start_addr = ipaddress.IPv4Address(start_ip)
                end_addr = ipaddress.IPv4Address(end_ip)
                
                if start_addr > end_addr:
                    _LOGGER.warning("Invalid IP range %s: start IP is greater than end IP", range_entry)
                    continue
                
                # Add all IPs in the range
                current = start_addr
                while current <= end_addr:
                    ip_set.add(str(current))
                    current += 1
                    
            elif '/' in range_entry:
                # Handle CIDR notation like 192.168.1.0/24
                network = ipaddress.IPv4Network(range_entry, strict=False)
                for ip in network.hosts():
                    ip_set.add(str(ip))
                # Also include network and broadcast if it's a single host (/32)
                if network.prefixlen == 32:
                    ip_set.add(str(network.network_address))
                    
            else:
                # Handle single IP
                ip_addr = ipaddress.IPv4Address(range_entry)
                ip_set.add(str(ip_addr))
                
        except (ipaddress.AddressValueError, ValueError) as e:
            _LOGGER.warning("Invalid IP address or range '%s': %s", range_entry, e)
            continue
    
    _LOGGER.debug("Parsed %d IP addresses from ranges: %s", len(ip_set), ip_ranges_str[:100])
    return ip_set


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
    if filter_mode == "disabled" or not ip_ranges_str:
        return True
    
    try:
        ipaddress.IPv4Address(ip_address)  # Validate IP format
    except ipaddress.AddressValueError:
        _LOGGER.warning("Invalid IP address format: %s", ip_address)
        return False
    
    configured_ips = parse_ip_ranges(ip_ranges_str)
    
    if filter_mode == "include":
        # Only track IPs that are in the configured ranges
        return ip_address in configured_ips
    elif filter_mode == "exclude":
        # Track all IPs except those in the configured ranges
        return ip_address not in configured_ips
    
    # Default to tracking if unknown mode
    return True


def validate_ip_ranges_config(ip_ranges_str: str) -> tuple[bool, str]:
    """
    Validate IP ranges configuration string.
    
    Args:
        ip_ranges_str: String containing IP ranges configuration
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not ip_ranges_str or not ip_ranges_str.strip():
        return True, ""
    
    try:
        ip_set = parse_ip_ranges(ip_ranges_str)
        if not ip_set:
            return False, "No valid IP addresses found in configuration"
        
        # Check for reasonable limits (prevent memory issues)
        if len(ip_set) > 10000:
            return False, f"Too many IP addresses ({len(ip_set)}). Maximum 10,000 allowed."
        
        return True, f"Configuration valid. {len(ip_set)} IP addresses will be processed."
        
    except Exception as e:
        return False, f"Configuration error: {str(e)}"
