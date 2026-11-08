# TechnitiumDNS DHCP Tracking

## Defaults and Options

- DHCP device tracking is disabled until enabled in the integration options.
- DNS log tracking defaults to off; Smart Activity Analysis defaults to on. Smart Activity Analysis cannot produce scores without DNS log tracking and sufficient query evidence.
- The activity score threshold defaults to 55, and the analysis window defaults to 120 minutes.
- DHCP update interval options are 30, 60, 180, 300, and 600 seconds.
- Saving options reloads the config entry so platforms and coordinators use the new values.

## Lease Tracking

The coordinator polls Technitium's DHCP lease API at the configured interval. A connected tracker requires an IP address and hardware address. An explicit status other than `InUse` is excluded. When status is missing, a valid future lease expiry is required. Dynamic and Reserved lease types are both accepted; other types are retained rather than rejected. A lease with a valid `lease_expires` timestamp at or before the current UTC time is excluded. With explicit `InUse` status, missing or invalid expiry is not treated as evidence of expiration. Included lease diagnostics retain address status, type, and expiry.

DNS activity and last-seen are attributed only when the current IP occurs on one eligible lease and that lease has a valid `lease_obtained` timestamp. Duplicate current IPs, missing/invalid lease start times, and their activity states are marked `ambiguous`; score, connected-use classification, stale state, and last-seen remain unknown. Records older than the current lease start are excluded from both smart activity and basic last-seen. Naive ISO timestamps and naive datetime values are interpreted as UTC; aware values are normalized to UTC.

IP filtering is disabled by default. Include mode retains addresses matching configured ranges; exclude mode retains addresses outside those ranges. The parser accepts IPv4 single addresses, CIDR networks, and inclusive IPv4 ranges separated by commas, semicolons, or newlines. If filtering is enabled, an invalid address or range configuration, an empty range set, or more than 10,000 configured addresses fails closed.

Trackers are created for eligible leases at startup and added dynamically when new eligible leases appear. Their unique IDs use normalized MAC addresses. A tracker is connected while the matching MAC is present in the latest coordinator data and disconnected otherwise. Lease presence is only a connectivity proxy; it does not prove that the device is reachable. Per-device diagnostic sensors are created for discovered devices and may remain in Home Assistant after a lease disappears.

## DNS Activity

When DNS log tracking and Smart Activity Analysis are enabled, a score is calculated only with at least 3 query-log records from the newest 30 minutes. Sparse, old, missing, or unavailable evidence leaves the score and `is_actively_used` unknown. The 120-minute analysis window does not change the 30-minute evidence gate. `activity_evidence` and `score_breakdown` are propagated to the Activity Summary sensor attributes.

The score and boolean classification are heuristics over observed DNS records. They do not establish device reachability, human presence, or the cause of queries, and do not guarantee elimination of false positives or false negatives.

## DHCP Entity Orphan Report

The `technitiumdns.cleanup_devices` service and **Scan for Orphaned DHCP Entities** button request a non-destructive scan. It checks entities owned by the selected config entry and integration platform, recognizing tracker IDs shaped like `technitiumdns_device_tracker_<12-hex-MAC>` and per-device sensor IDs shaped like `technitiumdns_dhcp_<12-hex-MAC>_<sensor-field>`; IP-only tracker IDs are also identified. Reports include counts and up to 20 individual entries per category.

The scan logs MAC-based candidates that are absent from current coordinator data. IP-only trackers cannot be compared to the MAC set, and unavailable coordinator data makes orphan status unknown. No entity or device registry entries are removed or modified. See [ENTITY_CLEANUP.md](ENTITY_CLEANUP.md) for the scan details.

## DHCP Leases Service

The `technitiumdns.get_dhcp_leases` service fires a `technitiumdns_dhcp_leases_retrieved` event containing the filtered lease data. By default, only leases with `addressStatus` equal to `InUse` are included. Set `include_inactive: true` to include other statuses, or provide `filter_scope` to select a DHCP scope. A successful empty API list fires the event with `leases: []` and `total_leases: 0`; a `None` result or raised API error does not.
