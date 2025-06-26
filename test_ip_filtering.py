#!/usr/bin/env python3
"""
Test script for IP filtering functionality in TechnitiumDNS DHCP device tracking.
"""

import sys
import os

# Add the custom_components path to sys.path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components', 'technitiumdns'))

from utils import parse_ip_ranges, should_track_ip, validate_ip_ranges_config

def test_ip_parsing():
    """Test IP range parsing functionality."""
    print("=== Testing IP Range Parsing ===\n")
    
    test_cases = [
        # Single IPs
        ("192.168.1.100", {"192.168.1.100"}),
        
        # CIDR ranges
        ("192.168.1.0/30", {"192.168.1.1", "192.168.1.2"}),  # Small range
        ("10.0.0.0/32", {"10.0.0.0"}),  # Single host
        
        # IP ranges
        ("192.168.1.10-192.168.1.12", {"192.168.1.10", "192.168.1.11", "192.168.1.12"}),
        
        # Multiple entries with different separators
        ("192.168.1.100,192.168.1.101", {"192.168.1.100", "192.168.1.101"}),
        ("192.168.1.100;192.168.1.101", {"192.168.1.100", "192.168.1.101"}),
        ("192.168.1.100\n192.168.1.101", {"192.168.1.100", "192.168.1.101"}),
        
        # Mixed formats
        ("192.168.1.100,10.0.0.0/30,172.16.1.1-172.16.1.3", {
            "192.168.1.100", "10.0.0.1", "10.0.0.2", 
            "172.16.1.1", "172.16.1.2", "172.16.1.3"
        }),
        
        # Empty/invalid cases
        ("", set()),
        ("   ", set()),
        ("invalid.ip.address", set()),
    ]
    
    for i, (input_str, expected) in enumerate(test_cases):
        result = parse_ip_ranges(input_str)
        success = result == expected
        print(f"Test {i+1}: {'✓ PASS' if success else '✗ FAIL'}")
        print(f"  Input: '{input_str}'")
        print(f"  Expected: {expected}")
        print(f"  Got: {result}")
        if not success:
            print(f"  Missing: {expected - result}")
            print(f"  Extra: {result - expected}")
        print()

def test_ip_filtering():
    """Test IP filtering logic."""
    print("=== Testing IP Filtering Logic ===\n")
    
    test_cases = [
        # Disabled mode - should always track
        ("192.168.1.100", "disabled", "", True),
        ("10.0.0.1", "disabled", "192.168.1.0/24", True),
        
        # Include mode
        ("192.168.1.100", "include", "192.168.1.0/24", True),
        ("10.0.0.1", "include", "192.168.1.0/24", False),
        ("192.168.1.50", "include", "192.168.1.100,192.168.1.101", False),
        ("192.168.1.100", "include", "192.168.1.100,192.168.1.101", True),
        
        # Exclude mode
        ("192.168.1.100", "exclude", "192.168.1.0/24", False),
        ("10.0.0.1", "exclude", "192.168.1.0/24", True),
        ("192.168.1.100", "exclude", "192.168.1.100,192.168.1.101", False),
        ("192.168.1.102", "exclude", "192.168.1.100,192.168.1.101", True),
        
        # Edge cases
        ("invalid.ip", "include", "192.168.1.0/24", False),
        ("192.168.1.100", "unknown_mode", "192.168.1.0/24", True),
    ]
    
    for i, (ip, mode, ranges, expected) in enumerate(test_cases):
        result = should_track_ip(ip, mode, ranges)
        success = result == expected
        print(f"Test {i+1}: {'✓ PASS' if success else '✗ FAIL'}")
        print(f"  IP: {ip}")
        print(f"  Mode: {mode}")
        print(f"  Ranges: '{ranges}'")
        print(f"  Expected: {expected}")
        print(f"  Got: {result}")
        print()

def test_config_validation():
    """Test configuration validation."""
    print("=== Testing Configuration Validation ===\n")
    
    test_cases = [
        # Valid configurations
        ("", True, ""),
        ("192.168.1.100", True, ""),
        ("192.168.1.0/24", True, ""),
        ("192.168.1.1-192.168.1.5", True, ""),
        ("192.168.1.100,10.0.0.1", True, ""),
        
        # Invalid configurations
        ("invalid.ip.address", False, ""),
        ("192.168.1.1-192.168.1.300", False, ""),  # Invalid end IP
        ("192.168.1.100-192.168.1.50", False, ""),  # Start > end
    ]
    
    for i, (config, should_be_valid, _) in enumerate(test_cases):
        is_valid, message = validate_ip_ranges_config(config)
        success = is_valid == should_be_valid
        print(f"Test {i+1}: {'✓ PASS' if success else '✗ FAIL'}")
        print(f"  Config: '{config}'")
        print(f"  Expected valid: {should_be_valid}")
        print(f"  Is valid: {is_valid}")
        print(f"  Message: {message}")
        print()

def test_real_world_scenarios():
    """Test real-world usage scenarios."""
    print("=== Testing Real-World Scenarios ===\n")
    
    scenarios = [
        {
            "name": "Home network - include only trusted devices",
            "mode": "include",
            "ranges": "192.168.1.100,192.168.1.101,192.168.1.102",
            "test_ips": [
                ("192.168.1.100", True, "Family phone"),
                ("192.168.1.105", False, "Unknown device"),
                ("192.168.1.1", False, "Router"),
            ]
        },
        {
            "name": "Office network - exclude servers and infrastructure",
            "mode": "exclude", 
            "ranges": "10.0.0.0/28,10.0.1.1-10.0.1.10",
            "test_ips": [
                ("10.0.0.5", False, "Server"),
                ("10.0.1.5", False, "Infrastructure"),
                ("10.0.2.50", True, "Employee device"),
                ("10.0.0.50", True, "Guest device"),
            ]
        },
        {
            "name": "Mixed format configuration",
            "mode": "include",
            "ranges": "192.168.1.100\n10.0.0.0/30\n172.16.1.1-172.16.1.3",
            "test_ips": [
                ("192.168.1.100", True, "Static device"),
                ("10.0.0.1", True, "Server range"),
                ("172.16.1.2", True, "DMZ device"),
                ("192.168.1.200", False, "Outside range"),
            ]
        }
    ]
    
    for scenario in scenarios:
        print(f"Scenario: {scenario['name']}")
        print(f"Mode: {scenario['mode']}")
        print(f"Ranges: {scenario['ranges']}")
        print()
        
        for ip, expected, description in scenario["test_ips"]:
            result = should_track_ip(ip, scenario['mode'], scenario['ranges'])
            success = result == expected
            status = "✓ PASS" if success else "✗ FAIL"
            action = "TRACK" if result else "SKIP"
            print(f"  {status} {ip} ({description}) -> {action}")
        
        print()

if __name__ == "__main__":
    print("TechnitiumDNS IP Filtering Test Suite")
    print("=" * 50)
    print()
    
    test_ip_parsing()
    test_ip_filtering()
    test_config_validation()
    test_real_world_scenarios()
    
    print("Test suite complete!")
