"""Constants for the TechnitiumDNSdhcp integration."""

DOMAIN = "technitiumdnsdhcp"

DURATION_OPTIONS = ["LastHour", "LastDay", "LastWeek", "LastMonth"]

AD_BLOCKING_SWITCH = "Enable Ad Blocking"

AD_BLOCKING_DURATION_OPTIONS = {
    5: "Disable Ad Blocking for 5 Minutes",
    10: "Disable Ad Blocking for 10 Minutes",
    30: "Disable Ad Blocking for 30 Minutes",
    60: "Disable Ad Blocking for 60 Minutes",
    1440: "Disable Ad Blocking for 1 Day",
}

# DHCP Device Tracking Options
CONF_ENABLE_DHCP_TRACKING = "enable_dhcp_tracking"
CONF_DHCP_UPDATE_INTERVAL = "dhcp_update_interval"
CONF_DHCP_IP_FILTER_MODE = "dhcp_ip_filter_mode"
CONF_DHCP_IP_RANGES = "dhcp_ip_ranges"

DHCP_UPDATE_INTERVAL_OPTIONS = [30, 60, 180, 300, 600]  # seconds

# IP Filter modes
DHCP_IP_FILTER_MODES = {
    "disabled": "No IP filtering",
    "include": "Include only specified IPs/ranges",
    "exclude": "Exclude specified IPs/ranges"
}

SENSOR_TYPES = {
    "queries": {"name": "Total Queries", "state_class": "measurement", "device_class": "count"},
    "blocked_queries": {"name": "Blocked Queries", "state_class": "measurement", "device_class": "count"},
    "clients": {"name": "Clients", "state_class": "measurement", "device_class": "count"},
    "update_available": {"name": "Update Available", "state_class": None, "device_class": "update"},
    "no_error": {"name": "Total No Error", "state_class": "measurement", "device_class": "count"},
    "server_failure": {"name": "Total Server Failure", "state_class": "measurement", "device_class": "count"},
    "nx_domain": {"name": "Total NX Domain", "state_class": "measurement", "device_class": "count"},
    "refused": {"name": "Total Refused", "state_class": "measurement", "device_class": "count"},
    "authoritative": {"name": "Total Authoritative", "state_class": "measurement", "device_class": "count"},
    "recursive": {"name": "Total Recursive", "state_class": "measurement", "device_class": "count"},
    "cached": {"name": "Total Cached", "state_class": "measurement", "device_class": "count"},
    "dropped": {"name": "Total Dropped", "state_class": "measurement", "device_class": "count"},
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

# DNS Log tracking options
CONF_DHCP_LOG_TRACKING = "dhcp_log_tracking"
CONF_DHCP_STALE_THRESHOLD = "dhcp_stale_threshold"

# Default values for new options
DEFAULT_DHCP_LOG_TRACKING = False
DEFAULT_DHCP_STALE_THRESHOLD = 60  # minutes

# Stale threshold options (in minutes)
DHCP_STALE_THRESHOLD_OPTIONS = {
    5: "5 minutes",
    15: "15 minutes",
    30: "30 minutes", 
    60: "1 hour",
    120: "2 hours",
    240: "4 hours",
    480: "8 hours",
    720: "12 hours",
    1440: "24 hours"
}
