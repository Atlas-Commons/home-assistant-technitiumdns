# Service Implementation Summary

## New Service Added: get_dhcp_leases

### Service Details
- **Service Name**: `technitiumdnsdhcp.get_dhcp_leases`
- **Purpose**: Retrieve DHCP lease information programmatically
- **Location**: Implemented in `custom_components/technitiumdns/__init__.py`

### Parameters
1. **config_entry_id** (optional)
   - Type: string
   - Description: Target specific integration entry
   - If not provided: Uses first available entry

2. **include_inactive** (optional, default: false)
   - Type: boolean  
   - Description: Include expired/inactive leases in results

3. **filter_scope** (optional)
   - Type: string
   - Description: Filter leases by DHCP scope (e.g., "192.168.1.0/24")

### Output
- Fires Home Assistant event: `technitiumdnsdhcp_dhcp_leases_retrieved`
- Event data includes:
  - `config_entry_id`: The integration entry used
  - `total_leases`: Number of leases returned
  - `leases`: Array of lease objects
  - `include_inactive`: Whether inactive leases were included
  - `filter_scope`: Scope filter applied (if any)

### Use Cases
1. **Automation Triggers**: Monitor when new devices join/leave network
2. **Network Monitoring**: Get comprehensive DHCP lease status
3. **Custom Dashboards**: Display DHCP information in custom cards
4. **Scripting**: Access lease data for advanced automations

### Example Service Calls

#### Basic Usage
```yaml
service: technitiumdnsdhcp.get_dhcp_leases
```

#### Include Inactive Leases
```yaml
service: technitiumdnsdhcp.get_dhcp_leases
data:
  include_inactive: true
```

#### Filter by Scope
```yaml
service: technitiumdnsdhcp.get_dhcp_leases
data:
  filter_scope: "192.168.1.0/24"
```

### Event Listener Example
```yaml
automation:
  - alias: "Monitor DHCP Leases"
    trigger:
      - platform: event
        event_type: technitiumdnsdhcp_dhcp_leases_retrieved
    action:
      - service: notify.persistent_notification
        data:
          title: "DHCP Lease Update"
          message: "Found {{ trigger.event.data.total_leases }} active leases"
```

### Integration with Existing Features
- Uses existing API infrastructure (`api.get_dhcp_leases()`)
- Leverages same configuration entries as device tracking
- Consistent with other service implementations
- Error handling and logging follow integration patterns

### Debug Logging
Both services support comprehensive debug logging when enabled:

```yaml
logger:
  logs:
    custom_components.technitiumdns: debug
```

#### Cleanup Service Debug Output
- Service call parameters and configuration validation
- MAC address extraction and entity identification
- Device cleanup decision making process
- Complete lists of entities and devices processed

#### DHCP Leases Service Debug Output
- Service call parameters and target entry selection
- API request details and response validation
- Lease filtering and processing logic
- Event data preparation and firing

This service provides users with programmatic access to DHCP lease data, enabling advanced automation and monitoring scenarios beyond the built-in device tracking features.
