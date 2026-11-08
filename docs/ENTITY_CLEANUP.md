# DHCP Entity Orphan Report

## Purpose

Home Assistant entity and device registry entries are not automatically deleted when a DHCP lease disappears or an IP filter changes. The integration provides a non-destructive scan to help identify DHCP tracker and per-device sensor entities whose MAC address is no longer present in coordinator data.

The scan does not remove or modify entities, entity-registry entries, or device-registry entries. Review any reported candidates and remove entries manually through Home Assistant only when appropriate.

## Candidate Scope

The scan requires both the selected config-entry ownership and the TechnitiumDNS integration platform. It recognizes:

- Device trackers with IDs shaped like `technitiumdns_device_tracker_<12-hex-MAC>`
- IP-only device trackers with IDs shaped like `technitiumdns_device_tracker_ip_<IPv4>`
- Per-device diagnostic sensors with IDs shaped like `technitiumdns_dhcp_<12-hex-MAC>_<sensor-field>`

The sensor pattern matches the IDs used by the concrete sensor classes, which override the base diagnostic sensor ID. Main DNS statistics, buttons, switches, entities owned by other config entries, and entities from other integrations are ignored.

MAC-based candidates are compared with the current DHCP coordinator data. IP-only trackers cannot be matched to the MAC set, so they are reported with unknown status. If coordinator data is unavailable, all candidate orphan statuses are unknown rather than being treated as orphaned.

## Run a Scan

When DHCP tracking is enabled, use the device button **Scan for Orphaned DHCP Entities**. The legacy service name remains available for compatibility:

```yaml
service: technitiumdns.cleanup_devices
data:
  config_entry_id: "your_entry_id"  # Optional; omitted scans all loaded entries
```

The requested scan writes aggregate counts to the integration log and creates a persistent notification with up to 20 entity IDs per category. MAC addresses and entity IDs are not written to the log. It does not run on every coordinator update. Despite its legacy name, `cleanup_devices` is report-only and does not perform cleanup or deletion.

## Related DHCP Behavior

- DHCP option changes reload the config entry.
- IP filters support single IPv4 addresses, CIDR networks, and inclusive IPv4 ranges. Include mode retains matching addresses; exclude mode retains non-matching addresses. Invalid or over-limit active filters fail closed.
- A device tracker is connected while its MAC has a lease in current coordinator data. Lease presence is only a connectivity proxy.
- Dynamic trackers and per-device sensors are added when eligible leases are discovered. An entity may remain in Home Assistant after its lease disappears; the orphan report does not remove it.
