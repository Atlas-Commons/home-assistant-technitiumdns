# Entity Cleanup Implementation for TechnitiumDNS Integration

## Problem Solved

When users change IP filtering configuration in the TechnitiumDNS integration, Home Assistant does **not** automatically remove entities for devices that no longer match the filter criteria. This results in "orphaned" entities and devices that clutter the UI and entity registry.

## Solution Implemented

### 1. Automatic Cleanup During Updates

**File**: `custom_components/technitiumdns/device_tracker.py`

The DHCP coordinator now tracks which devices should exist based on current filtering criteria and automatically cleans up orphaned entities during each data update cycle.

**Key Changes**:
- Added `_cleanup_orphaned_entities()` method to `TechnitiumDHCPCoordinator`
- Modified `_async_update_data()` to trigger cleanup after processing DHCP leases
- Cleanup runs automatically whenever the coordinator updates data

### 2. Manual Cleanup Service

**File**: `custom_components/technitiumdns/__init__.py`

Added a Home Assistant service for manual cleanup when needed.

**Service**: `technitiumdnsdhcp.cleanup_devices`
**Parameters**:
- `config_entry_id` (optional): Clean specific integration entry, or all entries if omitted

### 3. Cleanup Button Entity

**File**: `custom_components/technitiumdns/button.py`

Added a button entity for easy manual cleanup from the UI.

**Button**: "Cleanup Devices" (appears on TechnitiumDNS device page when DHCP tracking is enabled)

### 4. Service Definition

**File**: `custom_components/technitiumdns/services.yaml`

Defines the cleanup service for Home Assistant UI.

## How Cleanup Works

### Entity Identification
The cleanup process identifies DHCP-related entities by their `unique_id` patterns:
- Device trackers: `dhcp_device_{mac_clean}`
- Diagnostic sensors: `technitiumdns_dhcp_{mac_clean}_{sensor_type}`

### MAC Address Extraction
From unique IDs, the system extracts MAC addresses and compares them against currently tracked devices:
```python
# Example: "technitiumdns_dhcp_aabbccddeeff_ip_address" -> "AA:BB:CC:DD:EE:FF"
mac_clean = unique_id.split("_")[2]  # "aabbccddeeff"
mac_address = ":".join([mac_clean[i:i+2] for i in range(0, 12, 2)]).upper()
```

### Cleanup Process
1. **Identify Current Devices**: Extract MAC addresses from current DHCP leases that pass IP filtering
2. **Find Orphaned Entities**: Compare existing entity unique IDs against current device list
3. **Remove Orphaned Entities**: Remove entities whose MAC addresses are no longer in the current device list
4. **Clean Up Devices**: Remove device registry entries that have no remaining entities

### Safety Measures
- Only entities belonging to this integration are affected
- Main DNS statistics sensors are never removed
- Non-DHCP entities (buttons, switches) are preserved
- Comprehensive logging tracks all cleanup actions

## Usage

### Automatic Cleanup
Cleanup happens automatically when:
- DHCP coordinator updates (based on configured interval)
- IP filter configuration changes
- Devices leave the network or no longer match filters

### Manual Cleanup Options

1. **Using the Button**: 
   - Go to Settings → Devices & Services → TechnitiumDNS → [Your Server]
   - Click "Cleanup Devices" button

2. **Using Developer Tools**:
   - Go to Developer Tools → Services
   - Search for "Cleanup Devices"
   - Call `technitiumdnsdhcp.cleanup_devices`

3. **Using Automation**:
   ```yaml
   service: technitiumdnsdhcp.cleanup_devices
   data:
     config_entry_id: "your_entry_id"  # Optional
   ```

## Available Services

### Cleanup Devices Service
- **Service**: `technitiumdnsdhcp.cleanup_devices`
- **Purpose**: Remove orphaned device tracker entities and sensors
- **Parameters**:
  - `config_entry_id` (optional): Target specific integration entry

### Get DHCP Leases Service
- **Service**: `technitiumdnsdhcp.get_dhcp_leases`
- **Purpose**: Retrieve all DHCP leases for automation and monitoring
- **Parameters**:
  - `config_entry_id` (optional): Target specific integration entry
  - `include_inactive` (default: false): Include expired/inactive leases
  - `filter_scope` (optional): Filter by specific DHCP scope (e.g., "192.168.1.0/24")
- **Returns**: Fires event `technitiumdnsdhcp_dhcp_leases_retrieved` with lease data

#### Example Usage:
```yaml
# Get all active leases
service: technitiumdnsdhcp.get_dhcp_leases

# Get all leases including inactive ones
service: technitiumdnsdhcp.get_dhcp_leases
data:
  include_inactive: true

# Get leases from specific scope
service: technitiumdnsdhcp.get_dhcp_leases
data:
  filter_scope: "192.168.1.0/24"
```

The service fires an event that can be listened to in automations:
```yaml
trigger:
  - platform: event
    event_type: technitiumdnsdhcp_dhcp_leases_retrieved
action:
  - service: notify.persistent_notification
    data:
      message: "Retrieved {{ trigger.event.data.total_leases }} DHCP leases"
```

## What Gets Cleaned Up

### Removed Entities
- Device tracker entities (`device_tracker.device_name`)
- All 11 diagnostic sensors per device:
  - IP Address, MAC Address, Hostname
  - Lease Obtained, Lease Expires, Last Seen
  - Is Stale, Minutes Since Seen
  - Activity Score, Is Actively Used, Activity Summary

### Removed Devices
- Device registry entries for devices with no remaining entities
- Only DHCP client devices (not the main DNS server device)

### Preserved Entities
- Main DNS statistics sensors (Total Queries, Top Clients, etc.)
- Button entities (Ad Blocking buttons, Cleanup button)
- Switch entities (Ad Blocking toggle)
- Devices and entities from other integrations

## Configuration Scenarios

### Example: Changing IP Filter from "Disabled" to "Include Only 192.168.1.0/24"

**Before Cleanup**:
- 50 device trackers for all DHCP leases
- 550 diagnostic sensors (50 devices × 11 sensors)

**After Cleanup**:
- 15 device trackers for devices in 192.168.1.0/24
- 165 diagnostic sensors (15 devices × 11 sensors)
- 35 devices and 385 sensors automatically removed

## Logging

Cleanup actions are logged with details:
```
INFO: Starting entity cleanup for entry abc123def456
INFO: Marking entity device_tracker.old_device for removal (MAC AA:BB:CC:DD:EE:FF no longer tracked)
INFO: Removing orphaned entity: sensor.old_device_activity_score
INFO: Removing orphaned device: Old Device
INFO: Cleanup completed: removed 385 entities and 35 devices
```

## Benefits

1. **Clean UI**: No orphaned entities cluttering device pages
2. **Accurate Device List**: Only currently relevant devices are shown
3. **Automatic Maintenance**: No manual intervention required
4. **Manual Control**: Users can trigger cleanup when needed
5. **Safe Operation**: Only affects relevant entities, preserves others
6. **Comprehensive Logging**: Full visibility into cleanup actions

This implementation solves the entity management problem while maintaining integration stability and user control.
