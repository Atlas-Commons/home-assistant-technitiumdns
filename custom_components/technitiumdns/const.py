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
    "queries": {"name": "Total Queries", "state_class": "total_increasing"},
    "blocked_queries": {"name": "Blocked Queries", "state_class": "total_increasing"},
    "clients": {"name": "Clients", "state_class": "measurement"},
    "update_available": {"name": "Update Available", "state_class": None},
    "no_error": {"name": "Total No Error", "state_class": "total_increasing"},
    "server_failure": {"name": "Total Server Failure", "state_class": "total_increasing"},
    "nx_domain": {"name": "Total NX Domain", "state_class": "total_increasing"},
    "refused": {"name": "Total Refused", "state_class": "total_increasing"},
    "authoritative": {"name": "Total Authoritative", "state_class": "total_increasing"},
    "recursive": {"name": "Total Recursive", "state_class": "total_increasing"},
    "cached": {"name": "Total Cached", "state_class": "total_increasing"},
    "dropped": {"name": "Total Dropped", "state_class": "total_increasing"},
    "zones": {"name": "Zones", "state_class": "measurement"},
    "cached_entries": {"name": "Cached Entries", "state_class": "measurement"},
    "allowed_zones": {"name": "Allowed Zones", "state_class": "measurement"},
    "blocked_zones": {"name": "Blocked Zones", "state_class": "measurement"},
    "allow_list_zones": {"name": "Allow List Zones", "state_class": "measurement"},
    "block_list_zones": {"name": "Block List Zones", "state_class": "measurement"},
    "top_clients": {"name": "Top Clients", "state_class": None},
    "top_domains": {"name": "Top Domains", "state_class": None},
    "top_blocked_domains": {"name": "Top Blocked Domains", "state_class": None},
}
