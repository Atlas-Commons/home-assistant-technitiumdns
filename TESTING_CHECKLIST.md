# Testing Checklist for Diagnostic Sensors Fix

## Files Modified
1. `custom_components/technitiumdns/__init__.py` - Fixed platform loading order
2. `custom_components/technitiumdns/sensor.py` - Added diagnostic sensor classes and improved setup
3. `DIAGNOSTIC_SENSORS_FIX.md` - Documentation of changes made

## Pre-Test Setup
1. **Restart Home Assistant** completely to reload the integration
2. **Enable DHCP tracking** in the TechnitiumDNS integration options (if not already enabled)
3. **Ensure DNS logging is working** on your TechnitiumDNS server

## What to Check After Restart

### 1. Platform Loading Order (Check Logs)
Look for these log entries in the correct order:
```
Setting up TechnitiumDNS integration for entry...
Added device_tracker platform to load list
Starting TechnitiumDNS DHCP device tracker setup...
Setting up TechnitiumDNS sensor platform for entry...
```

### 2. Sensor Creation (Check Logs)
Look for these entries:
```
Created X main DNS statistics sensors
Processing X DHCP devices to create diagnostic sensors
Created X diagnostic sensors for device Y
Total sensors to register: X
All sensors registered successfully with Home Assistant
```

### 3. Entity Registry (Developer Tools > States)
Search for entities with these patterns:
- `sensor.device_name_activity_score`
- `sensor.device_name_is_actively_used`
- `sensor.device_name_activity_summary`
- `sensor.device_name_ip_address`
- `sensor.device_name_last_seen`

### 4. Device Pages (Settings > Devices & Services)
1. Navigate to TechnitiumDNS integration
2. Click on individual device cards for DHCP devices
3. Verify you see 11 diagnostic sensors per device:
   - IP Address
   - MAC Address  
   - Hostname
   - Lease Obtained
   - Lease Expires
   - Last Seen
   - Is Stale
   - Minutes Since Seen
   - **Activity Score** ⭐
   - **Is Actively Used** ⭐
   - **Activity Summary** ⭐

### 5. Sensor Values (Most Important)
Check that the new activity sensors show meaningful values:

#### Activity Score Sensor
- Should show values 0-100 (not all zeros)
- Icon should change based on score:
  - 75+: Green checkmark (mdi:account-check)
  - 50-74: Regular account (mdi:account)
  - 25-49: Outline account (mdi:account-outline)
  - 0-24: Red X (mdi:account-off)

#### Is Actively Used Sensor
- Should show "Yes" or "No" (not always "No")
- Icon: Green checkmark for "Yes", red X for "No"

#### Activity Summary Sensor
- Should show descriptive text like:
  - "High activity: 45 queries, 12 domains, diverse protocols"
  - "Moderate activity: 23 queries, 8 domains, mixed traffic"
  - "Low activity: 5 queries, 2 domains, mostly background"

### 6. Entity Categories
Diagnostic sensors should appear in the **"Diagnostic"** section when viewing device details, not mixed with regular sensors.

## Troubleshooting If Sensors Don't Appear

### Check Integration Status
1. Go to Settings > Devices & Services > TechnitiumDNS
2. Verify "DHCP Device Tracking" is enabled in options
3. Check for any error messages or warnings

### Check Logs for Errors
Look for error messages containing:
- "Could not initialize TechnitiumDNS sensor platform"
- "DHCP coordinator found but no data available"
- "No DHCP coordinator found"

### Verify DHCP Data
1. Check that device tracker entities exist and show "Home"/"Away" status
2. Verify DHCP API is returning device data
3. Ensure DNS logs API is accessible (if smart activity is enabled)

### Manual Entity Registration Check
If sensors exist but don't show values:
1. Go to Developer Tools > States
2. Find the activity score sensor for a device
3. Click on it to see entity details and current state
4. Check attributes for additional debug information

## Success Criteria
✅ All diagnostic sensors appear in Home Assistant UI  
✅ Sensors are categorized as "Diagnostic" entities  
✅ Activity Score shows values between 0-100 (not all zeros)  
✅ Is Actively Used shows "Yes" for genuinely active devices  
✅ Activity Summary provides meaningful descriptions  
✅ Sensors update according to coordinator refresh interval  
✅ No errors in Home Assistant logs during setup  

## If Problems Persist
1. Check entity registry file: `config/.storage/core.entity_registry`
2. Look for duplicate or conflicting entity IDs
3. Try removing and re-adding the integration
4. Verify TechnitiumDNS server API access and DNS logging configuration

This fix should resolve the issue where diagnostic sensors weren't showing up, particularly the new Smart Activity Analysis sensors that distinguish between genuinely active devices and those making only background DNS calls.
