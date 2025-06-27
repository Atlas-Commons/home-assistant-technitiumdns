# Diagnostic Sensors Fix for TechnitiumDNS Integration

## Problem Statement
The diagnostic sensors for DHCP devices (Activity Score, Is Actively Used, Activity Summary, etc.) were not showing up in Home Assistant UI after implementing the Smart Activity Analysis feature.

## Root Cause Analysis
The issue was identified as an entity registration and platform ordering problem:

1. **Platform Loading Order**: The sensor platform was loading before the device_tracker platform, meaning the DHCP coordinator wasn't available when sensors were being created.
2. **Entity Category**: Diagnostic sensors need to be properly marked with `EntityCategory.DIAGNOSTIC` to appear in the correct section of the UI.
3. **Cross-Platform Sensor Registration**: Diagnostic sensors were incorrectly attempting to be imported from device_tracker.py instead of being defined in the sensor platform itself.

## Solution Implemented

### 1. Fixed Platform Loading Order
**File**: `custom_components/technitiumdns/__init__.py`

Changed the platform loading order to ensure device_tracker loads before sensor:
```python
# Old order: ["sensor", "button", "switch", "device_tracker"]
# New order: ["button", "switch", "device_tracker", "sensor"]
```

This ensures that the DHCP coordinator is available when the sensor platform initializes.

### 2. Moved Diagnostic Sensors to Sensor Platform
**File**: `custom_components/technitiumdns/sensor.py`

- Added `EntityCategory` import for proper diagnostic entity categorization
- Defined all diagnostic sensor classes directly in the sensor platform:
  - `TechnitiumDHCPDeviceDiagnosticSensor` (base class)
  - `TechnitiumDHCPDeviceIPSensor`
  - `TechnitiumDHCPDeviceMaCSensor`
  - `TechnitiumDHCPDeviceHostnameSensor`
  - `TechnitiumDHCPDeviceLeaseObtainedSensor`
  - `TechnitiumDHCPDeviceLeaseExpiresSensor`
  - `TechnitiumDHCPDeviceLastSeenSensor`
  - `TechnitiumDHCPDeviceIsStaleSensor`
  - `TechnitiumDHCPDeviceMinutesSinceSeenSensor`
  - `TechnitiumDHCPDeviceActivityScoreSensor`
  - `TechnitiumDHCPDeviceIsActivelyUsedSensor`
  - `TechnitiumDHCPDeviceActivitySummarySensor`

### 3. Enhanced Entity Properties
Each diagnostic sensor now properly implements:
- **Entity Category**: `EntityCategory.DIAGNOSTIC` to appear in diagnostic section
- **Device Info**: Proper device association with unique identifiers
- **Unique IDs**: Consistent naming pattern using cleaned MAC addresses
- **Icons**: Dynamic icons based on sensor state
- **State Attributes**: Additional context for activity analysis sensors

### 4. Improved Logging and Debugging
Added comprehensive logging to track:
- Platform setup order
- Coordinator availability
- Sensor creation process
- Entity registration counts

## Key Changes Made

### Entity Registration Pattern
```python
# Base diagnostic sensor class with proper categorization
class TechnitiumDHCPDeviceDiagnosticSensor(CoordinatorEntity, SensorEntity):
    @property
    def entity_category(self):
        """Return the entity category."""
        return EntityCategory.DIAGNOSTIC
    
    @property
    def device_info(self):
        """Return device information for this entity."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return DeviceInfo(
            identifiers={(DOMAIN, f"dhcp_device_{mac_clean}")},
            name=self._device_name,
            manufacturer="Network Device",
            model="DHCP Client",
            via_device=(DOMAIN, self._entry_id),
        )
```

### Smart Activity Integration
The Activity Score, Is Actively Used, and Activity Summary sensors properly read from the coordinator data populated by the Smart Activity Analyzer:

```python
@property
def extra_state_attributes(self):
    """Return additional attributes for activity sensors."""
    device_data = self._get_device_data()
    if device_data and device_data.get("activity_score", 0) > 0:
        return {
            "activity_summary": device_data.get("activity_summary", ""),
            "is_actively_used": device_data.get("is_actively_used", False),
            "score_breakdown": device_data.get("score_breakdown", {}),
            "threshold": self.coordinator.activity_analyzer.score_threshold
        }
```

## What to Verify in Home Assistant

### 1. Check Entity Registry
After restarting Home Assistant, verify that diagnostic sensors appear in:
- **Developer Tools > States**: Look for entities like `sensor.device_name_activity_score`
- **Settings > Devices & Services > TechnitiumDNS > Devices**: Each DHCP device should show diagnostic sensors

### 2. Entity Categories
Diagnostic sensors should appear in the "Diagnostic" section when viewing device details, not mixed with regular sensors.

### 3. Sensor Values
With the timezone fix and increased analysis window:
- **Activity Score**: Should show values between 0-100 (not all zeros)
- **Is Actively Used**: Should show "Yes" or "No" based on activity analysis  
- **Activity Summary**: Should show descriptive text about device activity

### 4. Debug Logs
Check Home Assistant logs for:
```
Setting up TechnitiumDNS sensor platform for entry
Created X main DNS statistics sensors
Processing X DHCP devices to create diagnostic sensors
Created X diagnostic sensor entities for X DHCP devices
Total sensors to register: X
All sensors registered successfully with Home Assistant
```

## Testing Steps

1. **Restart Home Assistant** to reload the integration with new platform order
2. **Check Developer Tools > States** for new sensor entities
3. **Navigate to device pages** to see diagnostic sensors in the diagnostic section
4. **Monitor logs** for any registration or update errors
5. **Verify sensor values** are populated correctly with activity analysis data

## Expected Behavior After Fix

- All diagnostic sensors should be visible in Home Assistant UI
- Sensors should be properly categorized as diagnostic entities
- Activity analysis sensors should show meaningful values (not all zeros)
- Each DHCP device should have its own device page with 11 diagnostic sensors
- Sensors should update according to the DHCP coordinator's update interval

## Fallback Verification

If sensors still don't appear, check:
1. **Entity Registry**: `config/.storage/core.entity_registry` for entity entries
2. **Integration State**: Ensure DHCP tracking is enabled in integration options
3. **API Connectivity**: Verify DHCP and DNS logs APIs are accessible
4. **Coordinator Data**: Check that DHCP coordinator has device data populated

This fix addresses the core issues preventing diagnostic sensors from appearing in Home Assistant while maintaining compatibility with the existing Smart Activity Analysis functionality.
