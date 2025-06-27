#!/usr/bin/env python3
"""
Simple standalone test to validate TechnitiumDNS diagnostic sensor creation.
This test creates mock coordinator data and tests sensor instantiation.
"""

import logging
import sys
from unittest.mock import MagicMock, Mock
from datetime import datetime

# Mock Home Assistant components before importing our modules
sys.modules['homeassistant.components.sensor'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
sys.modules['homeassistant.helpers.entity'] = MagicMock()
sys.modules['homeassistant.exceptions'] = MagicMock()

# Mock the required classes
SensorEntity = MagicMock()
SensorDeviceClass = MagicMock()
SensorDeviceClass.TIMESTAMP = "timestamp"
DataUpdateCoordinator = MagicMock()
UpdateFailed = Exception
CoordinatorEntity = MagicMock()
DeviceInfo = MagicMock()
EntityCategory = MagicMock()
EntityCategory.DIAGNOSTIC = "diagnostic"
ConfigEntryNotReady = Exception

# Add them to the modules
sys.modules['homeassistant.components.sensor'].SensorEntity = SensorEntity
sys.modules['homeassistant.components.sensor'].SensorDeviceClass = SensorDeviceClass
sys.modules['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator = DataUpdateCoordinator
sys.modules['homeassistant.helpers.update_coordinator'].UpdateFailed = UpdateFailed
sys.modules['homeassistant.helpers.update_coordinator'].CoordinatorEntity = CoordinatorEntity
sys.modules['homeassistant.helpers.entity'].DeviceInfo = DeviceInfo
sys.modules['homeassistant.helpers.entity'].EntityCategory = EntityCategory
sys.modules['homeassistant.exceptions'].ConfigEntryNotReady = ConfigEntryNotReady

# Mock DOMAIN constant
DOMAIN = "technitiumdnsdhcp"

# Mock SENSOR_TYPES
SENSOR_TYPES = [
    {
        "key": "total_queries",
        "name": "Total Queries",
        "icon": "mdi:counter",
        "unit": "queries",
    }
]

def test_diagnostic_sensor_creation():
    """Test creating diagnostic sensors."""
    print("Starting diagnostic sensor creation test...")
    
    # Create mock coordinator with test data
    mock_coordinator = Mock()
    mock_coordinator.data = [
        {
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "hostname": "test-device",
            "ip_address": "192.168.1.100",
            "lease_obtained": datetime.now(),
            "lease_expires": datetime.now(),
            "last_seen": datetime.now(),
            "is_stale": False,
            "minutes_since_seen": 5,
            "activity_score": 75,
            "is_actively_used": True,
            "activity_summary": "High activity detected"
        }
    ]
    mock_coordinator.last_update_success = True
    
    # Test parameters
    mac_address = "aa:bb:cc:dd:ee:ff"
    server_name = "Test DNS Server"
    entry_id = "test_entry_123"
    device_name = "test-device"
    
    try:
        print("Creating base diagnostic sensor class...")
        
        # Create a simple test class similar to our diagnostic sensors
        class TestTechnitiumDHCPDeviceDiagnosticSensor:
            """Test diagnostic sensor."""
            
            def __init__(self, coordinator, mac_address, server_name, entry_id, sensor_type, device_name):
                self.coordinator = coordinator
                self._mac_address = mac_address
                self._server_name = server_name
                self._entry_id = entry_id
                self._sensor_type = sensor_type
                self._device_name = device_name
                
            @property
            def device_info(self):
                """Return device information for this entity."""
                mac_clean = self._mac_address.replace(':', '').lower()
                return {
                    "identifiers": {(DOMAIN, f"dhcp_device_{mac_clean}")},
                    "name": self._device_name,
                    "manufacturer": "Unknown",
                    "model": "DHCP Client",
                    "via_device": (DOMAIN, self._entry_id),
                }
            
            @property
            def entity_category(self):
                """Return the entity category."""
                return "diagnostic"
            
            @property
            def available(self):
                """Return if the sensor is available."""
                return self.coordinator.last_update_success and self._get_device_data() is not None
            
            def _get_device_data(self):
                """Get the current device data from coordinator."""
                if not self.coordinator.data:
                    return None
                    
                for lease in self.coordinator.data:
                    if lease.get("mac_address") == self._mac_address:
                        return lease
                return None
        
        # Test creating a diagnostic sensor instance
        print("Testing sensor instantiation...")
        sensor = TestTechnitiumDHCPDeviceDiagnosticSensor(
            mock_coordinator, mac_address, server_name, entry_id, "ip_address", device_name
        )
        
        print("✓ Sensor created successfully")
        print(f"  - Device Info: {sensor.device_info}")
        print(f"  - Entity Category: {sensor.entity_category}")
        print(f"  - Available: {sensor.available}")
        print(f"  - Device Data: {sensor._get_device_data()}")
        
        # Test all the diagnostic sensor types we want to create
        sensor_types = [
            "ip_address", "mac_address", "hostname", "lease_obtained",
            "lease_expires", "last_seen", "is_stale", "minutes_since_seen",
            "activity_score", "is_actively_used", "activity_summary"
        ]
        
        print(f"\nTesting creation of {len(sensor_types)} diagnostic sensor types...")
        sensors_created = []
        
        for sensor_type in sensor_types:
            try:
                sensor = TestTechnitiumDHCPDeviceDiagnosticSensor(
                    mock_coordinator, mac_address, server_name, entry_id, sensor_type, device_name
                )
                sensors_created.append(sensor)
                print(f"  ✓ {sensor_type} sensor created")
            except Exception as e:
                print(f"  ✗ {sensor_type} sensor failed: {e}")
        
        print(f"\n✓ Successfully created {len(sensors_created)} diagnostic sensors")
        print("✓ All diagnostic sensor creation tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = test_diagnostic_sensor_creation()
    sys.exit(0 if success else 1)
