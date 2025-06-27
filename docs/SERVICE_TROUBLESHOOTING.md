# Service Troubleshooting Guide

## Common Service Issues and Solutions

### Issue 1: "No DHCP coordinator found for entry"

#### Cause
This warning appears when the cleanup service is called but DHCP tracking is not enabled for the integration entry.

#### Diagnosis Steps
1. **Check DHCP Tracking Status**:
   ```yaml
   # Enable debug logging first
   logger:
     logs:
       custom_components.technitiumdns: debug
   ```
   
2. **Look for these debug messages**:
   ```
   DEBUG: Config entry [ID] DHCP tracking enabled: false
   DEBUG: Config entry options: {'enable_dhcp_tracking': False}
   ```

#### Solutions
1. **Enable DHCP Tracking**:
   - Go to Settings → Devices & Services → TechnitiumDNS
   - Click "Configure" on your integration
   - Enable "Enable DHCP Device Tracking"
   - Set desired update interval
   - Save configuration

2. **Verify DHCP Server is Running**:
   - Check that your Technitium DNS server has DHCP service enabled
   - Verify DHCP leases exist on the server

3. **Manual Cleanup (Even Without DHCP)**:
   - The service will still run and clean up any orphaned DHCP entities
   - This is useful if you previously had DHCP tracking enabled

### Issue 2: "No DHCP leases data returned"

#### Cause
The DHCP leases API call succeeds but returns no data or unexpected data structure.

#### Diagnosis Steps
1. **Check API Response Structure**:
   Look for debug messages like:
   ```
   DEBUG: DHCP leases API response: {'status': 'ok', 'response': {...}}
   DEBUG: Response keys: ['status', 'response']
   DEBUG: Found 'response.leases' key with 0 items
   ```

2. **Verify DHCP Server Status**:
   - Check if DHCP service is running on Technitium DNS
   - Verify there are active DHCP leases

#### Solutions
1. **Check Technitium DNS DHCP Configuration**:
   - Log into Technitium DNS web interface
   - Go to DHCP → Leases to verify leases exist
   - Ensure DHCP service is enabled and running

2. **API Response Structure Variations**:
   The enhanced debug logging will show the actual API response structure:
   ```
   DEBUG: No 'leases' key found in API response. Available keys: ['status', 'response']
   DEBUG: Full API response: {'status': 'ok', 'response': {'scopes': []}}
   ```

3. **Test API Endpoint Manually**:
   ```bash
   curl "http://your-dns-server:5380/api/dhcp/leases/list?token=your-token"
   ```

### Issue 3: Empty or Malformed API Responses

#### Enhanced Debug Information
The updated services now provide detailed debugging:

#### For Cleanup Service:
```
DEBUG: Cleanup service called with config_entry_id: 01JYQYQ6FA0VGA4KP4XGGQV6Q5
DEBUG: Config entry 01JYQYQ6FA0VGA4KP4XGGQV6Q5 DHCP tracking enabled: true
DEBUG: DHCP coordinator status: coordinator=True, has_data=False
```

#### For DHCP Leases Service:
```
DEBUG: DHCP leases service called with config_entry_id: None, include_inactive: false
DEBUG: Calling DHCP leases API endpoint: api/dhcp/leases/list
DEBUG: DHCP leases API response: {'status': 'ok', 'response': {}}
DEBUG: Response keys: ['status', 'response']
DEBUG: No 'leases' key found in API response. Available keys: ['status', 'response']
```

## Testing Steps

### 1. Test with Debug Logging
```yaml
# In configuration.yaml
logger:
  logs:
    custom_components.technitiumdns: debug
```

### 2. Test Cleanup Service
```yaml
# In Developer Tools → Services
service: technitiumdnsdhcp.cleanup_devices
data: {}
```

### 3. Test DHCP Leases Service
```yaml
# In Developer Tools → Services
service: technitiumdnsdhcp.get_dhcp_leases
data:
  include_inactive: true
```

### 4. Check Integration Configuration
- Verify DHCP tracking is enabled in integration options
- Check that coordinators are properly loaded
- Ensure API credentials are correct

## Expected Behavior

### When DHCP Tracking is Enabled:
- Cleanup service finds DHCP coordinator with data
- DHCP leases service returns lease information
- Debug logs show MAC addresses and device counts

### When DHCP Tracking is Disabled:
- Cleanup service runs but finds no DHCP coordinator
- Service still cleans up any orphaned DHCP entities
- DHCP leases service may still work if DHCP server has leases

### When DHCP Server has No Leases:
- API returns empty leases array
- Services handle empty data gracefully
- No entities created or maintained

## Recovery Steps

1. **Restart Integration**: Sometimes coordinator initialization issues resolve with restart
2. **Reconfigure Integration**: Remove and re-add if persistent issues
3. **Check Server Status**: Verify Technitium DNS DHCP service is running
4. **Validate API Access**: Test API endpoints manually with curl/browser

This enhanced debugging should help identify exactly where the issue occurs in the service call chain.
