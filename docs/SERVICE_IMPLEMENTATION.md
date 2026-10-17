# Service Implementation

## Available Services

The TechnitiumDNS integration exposes the following services for automation and scripting.

## 1. Cleanup Orphaned Devices

**Service Name**: `technitiumdns.cleanup_devices`

Removes device tracker entities and diagnostic sensors for devices that no longer match the current IP filter criteria.

### Parameters

- **config_entry_id** (optional)
  - Type: string
  - Description: Specific configuration entry ID to clean. If not provided, cleans all entries.
  - Required: No

### Use Cases

1. **Configuration Changes**: After changing IP filter settings
2. **Manual Cleanup**: Remove orphaned entities from previous configurations
3. **Network Changes**: Clean up devices from decommissioned network segments

### Example Service Calls

#### Clean All Entries
```yaml
service: technitiumdns.cleanup_devices
```

#### Clean Specific Entry
```yaml
service: technitiumdns.cleanup_devices
data:
  config_entry_id: "abc123def456"
```

#### In an Automation
```yaml
automation:
  - alias: "Cleanup DHCP Devices After Config Change"
    trigger:
      - platform: state
        entity_id: input_boolean.dhcp_config_changed
        to: "on"
    action:
      - service: technitiumdns.cleanup_devices
      - service: input_boolean.turn_off
        entity_id: input_boolean.dhcp_config_changed
```

### How It Works

The cleanup process:
1. Identifies all device tracker and diagnostic sensor entities for DHCP devices
2. Compares current filtering configuration
3. Removes entities for devices no longer matching filter criteria
4. Removes associated devices from the device registry if no entities remain
5. Logs results to `custom_components.technitiumdns`

### Debug Output

Enable debug logging to see cleanup details:

```yaml
logger:
  logs:
    custom_components.technitiumdns: debug
```

Debug output includes:
- Target entries being cleaned
- MAC addresses being evaluated
- Entity identification and matching
- Entities successfully removed
- Devices cleaned from registry

---

## 2. Get DHCP Leases

**Service Name**: `technitiumdns.get_dhcp_leases`

Retrieves DHCP lease information from the Technitium DNS server programmatically.

### Parameters

1. **config_entry_id** (optional)
   - Type: string
   - Description: Target specific integration entry. If not provided, uses first available entry.
   - Required: No

2. **include_inactive** (optional)
   - Type: boolean
   - Description: Include expired/inactive leases in results
   - Default: false
   - Required: No

3. **filter_scope** (optional)
   - Type: string
   - Description: Filter leases by DHCP scope (e.g., "192.168.1.0/24")
   - Example: "192.168.1.0/24"
   - Required: No

### Response Event

The service fires a Home Assistant event containing the results:

**Event Type**: `technitiumdns_dhcp_leases_retrieved`

**Event Data**:
```json
{
  "config_entry_id": "abc123def456",
  "total_leases": 15,
  "include_inactive": false,
  "filter_scope": null,
  "leases": [
    {
      "address": "192.168.1.100",
      "hardwareAddress": "AA:BB:CC:DD:EE:FF",
      "type": "Dynamic",
      "addressStatus": "InUse",
      "hostName": "device-name",
      "clientId": null,
      "leaseObtained": "2024-01-15T10:30:00Z",
      "leaseExpires": "2024-01-15T11:30:00Z",
      "scope": "192.168.1.0/24"
    }
  ]
}
```

### Use Cases

1. **Automation Triggers**: Monitor DHCP lease status
2. **Network Monitoring**: Get real-time DHCP information
3. **Custom Dashboards**: Display DHCP data in custom lovelace cards
4. **Scripting**: Access lease data for advanced automations
5. **Diagnostics**: Troubleshoot device connectivity issues

### Example Service Calls

#### Get All Active Leases
```yaml
service: technitiumdns.get_dhcp_leases
```

#### Include Inactive Leases
```yaml
service: technitiumdns.get_dhcp_leases
data:
  include_inactive: true
```

#### Filter by Scope
```yaml
service: technitiumdns.get_dhcp_leases
data:
  filter_scope: "192.168.1.0/24"
```

#### Specific Configuration Entry
```yaml
service: technitiumdns.get_dhcp_leases
data:
  config_entry_id: "abc123def456"
  include_inactive: false
```

### Event Listener Example

```yaml
automation:
  - alias: "Monitor DHCP Leases"
    trigger:
      - platform: event
        event_type: technitiumdns_dhcp_leases_retrieved
    action:
      - service: persistent_notification.create
        data:
          title: "DHCP Lease Status"
          message: "Active leases: {{ trigger.event.data.total_leases }}"
          notification_id: "dhcp_status"
```

### Script Example

```yaml
script:
  check_device_on_network:
    description: Check if a specific device is currently on the network
    fields:
      device_mac:
        description: MAC address of the device to check
        example: "AA:BB:CC:DD:EE:FF"
    sequence:
      - service: technitiumdns.get_dhcp_leases
      - variables:
          device_found: "{{ trigger.event.data.leases | selectattr('hardwareAddress', 'equalto', device_mac) | list | length > 0 }}"
      - service: notify.persistent_notification
        data:
          title: "Device Status"
          message: "Device {{ device_mac }} is {{ 'online' if device_found else 'offline' }}"
```

### Debug Logging

Enable debug logging to see service details:

```yaml
logger:
  logs:
    custom_components.technitiumdns: debug
```

Debug output includes:
- Service call parameters
- Target entry selection logic
- API request details
- Lease filtering and processing
- Event data preparation

---

## Integration Notes

- Both services use existing API infrastructure
- Leverage the same configuration entries as device tracking
- Follow standard Home Assistant service patterns
- Support comprehensive debug logging
- Provide error handling and validation
