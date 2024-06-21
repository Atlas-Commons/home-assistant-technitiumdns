"""Constants for the TechnitiumDNS integration."""

DOMAIN = "Technitiumdns"

DURATION_OPTIONS = ["LastHour", "LastDay", "LastWeek", "LastMonth"]

AD_BLOCKING_DURATION_OPTIONS = {
    5: "Disable Ad Blocking for 5 Minutes",
    10: "Disable Ad Blocking for 10 Minutes",
    30: "Disable Ad Blocking for 30 Minutes",
    60: "Disable Ad Blocking for 60 Minutes",
    1440: "Disable Ad Blocking for 1 Day",
}

SENSOR_TYPES = {
    "queries": {"name": "Total Queries"},
    "blocked_queries": {"name": "Blocked Queries"},
    "clients": {"name": "Clients"},
    "update_available": {"name": "Update Available"},
    "no_error": {"name": "Total No Error"},
    "server_failure": {"name": "Total Server Failure"},
    "nx_domain": {"name": "Total NX Domain"},
    "refused": {"name": "Total Refused"},
    "authoritative": {"name": "Total Authoritative"},
    "recursive": {"name": "Total Recursive"},
    "cached": {"name": "Total Cached"},
    "dropped": {"name": "Total Dropped"},
    "zones": {"name": "Zones"},
    "cached_entries": {"name": "Cached Entries"},
    "allowed_zones": {"name": "Allowed Zones"},
    "blocked_zones": {"name": "Blocked Zones"},
    "allow_list_zones": {"name": "Allow List Zones"},
    "block_list_zones": {"name": "Block List Zones"},
    "top_clients": {"name": "Top Clients"},
    "top_domains": {"name": "Top Domains"},
    "top_blocked_domains": {"name": "Top Blocked Domains"},
}
