# TechnitiumDNS DHCP Device Tracking Implementation

## Overview
This implementation adds DHCP device tracking functionality to the TechnitiumDNS Home Assistant integration. The feature creates device tracker entities for devices connected to the Technitium DHCP server, allowing users to monitor device presence and connection status.

## Features Added

### 1. DHCP API Integration
- Added `get_dhcp_leases()` method to fetch DHCP lease information
- Added `get_dhcp_scopes()` method for future DHCP scope management
- API calls follow the existing pattern with error handling and retries

### 2. Device Tracker Platform
- Created `device_tracker.py` implementing `DeviceTrackerEntity`
- Tracks devices based on DHCP leases with active status
- Shows connected/disconnected status based on lease presence
- Displays IP addresses, MAC addresses, and hostnames
- Includes additional lease information as entity attributes

### 3. Configuration Options
- Added options flow to enable/disable DHCP tracking
- Configurable update interval (30s, 1min, 5min, 10min)
- Options can be changed without requiring integration reload
- Backward compatible with existing installations
- **IP Address Filtering**: Include/exclude devices based on IP addresses
- **Multiple filter modes**: Disabled, Include only, Exclude specified
- **Flexible IP format support**: Single IPs, CIDR notation, IP ranges

### 4. Integration Updates
- Updated `__init__.py` to conditionally load device_tracker platform
- Added options update listener for dynamic configuration changes
- Updated manifest version to 2.5.2
- Enhanced error handling and logging
- **Added config entry migration from version 1 to 2**
- **Bumped config flow version to handle new options safely**

## Configuration

### Initial Setup
Users configure the integration as before. DHCP tracking is disabled by default.

### Enabling DHCP Tracking
1. Go to Settings > Devices & Services > TechnitiumDNS
2. Click "Configure" 
3. Enable "Enable DHCP Device Tracking"
4. Set desired update interval
5. Save configuration

### Options Available
- **Enable DHCP Device Tracking**: Boolean toggle
- **DHCP Update Interval**: 30, 60, 300, or 600 seconds
- **IP Filter Mode**: Choose filtering strategy (disabled/include/exclude)
- **IP Addresses/Ranges**: Specify IPs to include or exclude

## Device Tracker Behavior

### Device Discovery
- Polls DHCP API at configured interval
- Only tracks devices with active "Dynamic" leases in "InUse" status
- Creates device tracker entities for each active lease
- Uses MAC address as primary identifier when available
- **Applies IP filtering based on user configuration**

### Device Information
- **Name**: Hostname if available, otherwise generated from MAC address
- **Unique ID**: Based on MAC address or IP address
- **Status**: Connected when lease is active, disconnected when lease expires
- **Attributes**: 
  - IP address
  - MAC address  
  - Hostname
  - Client ID
  - Lease expiration time
  - Lease obtained time
  - DHCP scope

### Device Registry
- Each tracked device appears as a separate device in Home Assistant
- Devices are linked to the main TechnitiumDNS server device
- Device information updates automatically as leases change

## API Endpoints Used

### DHCP Leases
```
GET /api/dhcp/leases/list?token={token}
```
Returns list of all DHCP leases with status information.

### Expected Response Format
```json
{
  "status": "ok",
  "response": {
    "leases": [
      {
        "address": "192.168.1.100",
        "type": "Dynamic",
        "addressStatus": "InUse", 
        "hardwareAddress": "AA:BB:CC:DD:EE:FF",
        "hostName": "device-name",
        "clientIdentifier": "client-id",
        "leaseExpires": "2025-06-27T12:00:00Z",
        "leaseObtained": "2025-06-27T11:00:00Z",
        "scope": "192.168.1.0/24"
      }
    ]
  }
}
```

## Translation Support

### Added Strings
- Options flow title and descriptions
- DHCP tracking enable/disable labels
- Update interval selection labels

### Languages Updated
- English (en.json)
- German (de.json) 
- Spanish (es.json)
- French (fr.json)
- Italian (it.json)
- Framework in place for other languages

## Backward Compatibility
- Existing installations continue to work without changes
- DHCP tracking is opt-in via options
- No changes to existing sensors, switches, or buttons
- Graceful degradation if DHCP API is not available
- **Automatic migration from config version 1 to 2**
- **Safe default values for new options during migration**

## Error Handling
- API connection failures are logged but don't break existing functionality
- Invalid or missing DHCP data is handled gracefully
- Configuration validation prevents invalid settings
- Coordinator pattern ensures proper data flow and error recovery

## Future Enhancements
- DHCP scope management
- Static lease configuration
- Wake-on-LAN integration
- Device hostname management
- Additional DHCP statistics sensors

## Files Modified/Added

### New Files
- `device_tracker.py` - Main device tracker implementation

### Modified Files
- `__init__.py` - Added device_tracker platform loading and options listener
- `api.py` - Added DHCP API methods
- `config_flow.py` - Added options flow for DHCP settings
- `const.py` - Added DHCP-related constants
- `manifest.json` - Version bump to 2.5.2
- `strings.json` - Added options flow strings
- `translations/en.json` - Added English translations
- `translations/de.json` - Added German translations
- `translations/es.json` - Added Spanish translations
- `translations/fr.json` - Added French translations
- `translations/it.json` - Added Italian translations
- `README.md` - Updated documentation

## Testing Recommendations
1. Test with active DHCP server and various device types
2. Verify device tracking works with and without hostnames
3. Test options flow configuration changes
4. Verify backward compatibility with existing installations
5. Test API error handling and recovery
6. Validate device tracker entities appear correctly in Home Assistant
7. Test different update intervals for performance impact
