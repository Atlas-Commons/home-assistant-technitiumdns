# Diagnostic Sensors Still Not Showing - Troubleshooting Guide

## Current Status
Despite implementing the diagnostic sensors in the sensor platform and fixing the platform loading order, the sensors are still not appearing in Home Assistant.

## Changes Made
1. ✅ Fixed platform loading order in `__init__.py`
2. ✅ Moved all diagnostic sensor classes to `sensor.py` 
3. ✅ Added proper `EntityCategory.DIAGNOSTIC` marking
4. ✅ Fixed device_class for timestamp sensors
5. ✅ Added retry logic with 5-second delay
6. ✅ Enhanced error handling and logging
7. ✅ Incremented version to 2.5.1

## What to Check Next

### 1. Restart Home Assistant COMPLETELY
- **Stop Home Assistant**
- **Clear entity registry cache** (if possible)
- **Start Home Assistant**
- Check logs during startup

### 2. Check DHCP Tracking is Enabled
1. Go to Settings > Devices & Services > TechnitiumDNS
2. Click "Configure" 
3. Ensure "Enable DHCP Device Tracking" is checked
4. Save and restart

### 3. Monitor Startup Logs
Look for these specific log entries:

```
Setting up TechnitiumDNS integration for entry...
Added device_tracker platform to load list
Starting TechnitiumDNS DHCP device tracker setup...
TechnitiumDNS DHCP device tracker setup completed successfully
Setting up TechnitiumDNS sensor platform for entry...
DHCP coordinator found! Processing X DHCP devices
Successfully created X diagnostic sensor entities
All sensors registered successfully with Home Assistant
```

### 4. Check for Missing Log Entries
If you DON'T see:
- **"DHCP coordinator found!"** → DHCP coordinator issue
- **"Successfully created X diagnostic sensors"** → Sensor creation issue  
- **"All sensors registered successfully"** → Registration issue

### 5. Potential Root Causes

#### A. DHCP Coordinator Not Available
**Symptoms**: Log shows "No DHCP coordinator found after X retries"
**Solutions**:
- Verify DHCP tracking is enabled in integration options
- Check device_tracker entities exist and show device status
- Ensure TechnitiumDNS DHCP API is accessible

#### B. Platform Loading Race Condition
**Symptoms**: Sensor platform starts before device_tracker completes
**Solutions**:
- Increase retry count in sensor.py
- Check if platforms are loading in correct order
- Verify device_tracker completes before sensor starts

#### C. Entity Registry Conflicts
**Symptoms**: Sensors created but not visible in UI
**Solutions**:
- Check `config/.storage/core.entity_registry`
- Look for duplicate or conflicting entity IDs
- Try removing and re-adding the integration

#### D. Sensor Creation Errors
**Symptoms**: Log shows "Failed to create diagnostic sensors"
**Solutions**:
- Check specific error messages
- Verify all sensor classes are properly defined
- Test individual sensor creation

### 6. Debug Steps

#### Step 1: Verify Device Tracker Works
1. Check if device tracker entities exist
2. Verify they show "Home"/"Away" status  
3. Confirm DHCP data is being fetched

#### Step 2: Check Coordinator Availability
Add this debug code to sensor.py temporarily:
```python
_LOGGER.error("DEBUG: config_entry keys: %s", list(config_entry.keys()))
_LOGGER.error("DEBUG: coordinators: %s", config_entry.get("coordinators"))
if dhcp_coordinator:
    _LOGGER.error("DEBUG: coordinator.data: %s", dhcp_coordinator.data)
```

#### Step 3: Test Simple Sensor Creation
Create a basic sensor first to verify registration works:
```python
test_sensor = TechnitiumDNSTestSensor(coordinator, server_name, entry.entry_id)
sensors.append(test_sensor)
```

### 7. Alternative Approaches

If current approach fails:

#### A. Move Sensors to Device Tracker Platform
Register diagnostic sensors directly in device_tracker.py as device tracker entities with diagnostic category.

#### B. Use Entry Setup Hook
Set up diagnostic sensors using `entry.async_on_unload()` callback when DHCP coordinator becomes available.

#### C. Create Separate Diagnostic Platform
Create a custom platform specifically for diagnostic sensors.

## Testing Checklist

- [ ] Home Assistant completely restarted
- [ ] DHCP tracking enabled in integration options
- [ ] Device tracker entities exist and functional
- [ ] Platform loading order in logs is correct
- [ ] DHCP coordinator found in sensor platform logs
- [ ] Diagnostic sensors creation logged
- [ ] No entity registration errors
- [ ] Entity registry checked for conflicts
- [ ] Developer Tools > States shows new entities

## Expected Results

After fixing, you should see:
- 11 diagnostic sensors per DHCP device
- Entities visible in Developer Tools > States
- Sensors appear in device diagnostic section
- Activity sensors show meaningful values (not zeros)

## If Still Failing

1. Try removing integration completely
2. Restart Home Assistant
3. Re-add integration from scratch
4. Enable DHCP tracking during initial setup

The issue is likely either a timing problem between platforms or an entity registration conflict that requires a clean restart/re-setup.
