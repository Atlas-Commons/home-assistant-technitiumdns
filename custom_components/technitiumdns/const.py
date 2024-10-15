"""Constants for the TechnitiumDNS integration."""

DOMAIN = "technitiumdns"

DURATION_OPTIONS = ["LastHour", "LastDay", "LastWeek", "LastMonth"]

AD_BLOCKING_SWITCH = "Enable Ad Blocking"

AD_BLOCKING_DURATION_OPTIONS = {
    5: "Disable Ad Blocking for 5 Minutes",
    10: "Disable Ad Blocking for 10 Minutes",
    30: "Disable Ad Blocking for 30 Minutes",
    60: "Disable Ad Blocking for 60 Minutes",
    1440: "Disable Ad Blocking for 1 Day",
}

SENSOR_TYPES = {
    "queries": {"name": "Total Queries", "state_class": "total_increasing", "device_class": "count"},
    "blocked_queries": {"name": "Blocked Queries", "state_class": "total_increasing", "device_class": "count"},
    "clients": {"name": "Clients", "state_class": "measurement", "device_class": "count"},
    "update_available": {"name": "Update Available", "state_class": None, "device_class": "update"},
    "no_error": {"name": "Total No Error", "state_class": "total_increasing", "device_class": "count"},
    "server_failure": {"name": "Total Server Failure", "state_class": "total_increasing", "device_class": "count"},
    "nx_domain": {"name": "Total NX Domain", "state_class": "total_increasing", "device_class": "count"},
    "refused": {"name": "Total Refused", "state_class": "total_increasing", "device_class": "count"},
    "authoritative": {"name": "Total Authoritative", "state_class": "total_increasing", "device_class": "count"},
    "recursive": {"name": "Total Recursive", "state_class": "total_increasing", "device_class": "count"},
    "cached": {"name": "Total Cached", "state_class": "total_increasing", "device_class": "count"},
    "dropped": {"name": "Total Dropped", "state_class": "total_increasing", "device_class": "count"},
    "zones": {"name": "Zones", "state_class": "measurement", "device_class": "count"},
    "cached_entries": {"name": "Cached Entries", "state_class": "measurement", "device_class": "count"},
    "allowed_zones": {"name": "Allowed Zones", "state_class": "measurement", "device_class": "count"},
    "blocked_zones": {"name": "Blocked Zones", "state_class": "measurement", "device_class": "count"},
    "allow_list_zones": {"name": "Allow List Zones", "state_class": "measurement", "device_class": "count"},
    "block_list_zones": {"name": "Block List Zones", "state_class": "measurement", "device_class": "count"},
    "top_clients": {"name": "Top Clients", "state_class": None, "device_class": None},
    "top_domains": {"name": "Top Domains", "state_class": None, "device_class": None},
    "top_blocked_domains": {"name": "Top Blocked Domains", "state_class": None, "device_class": None},
}
