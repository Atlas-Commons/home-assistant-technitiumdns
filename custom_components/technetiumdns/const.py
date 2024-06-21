"""Constants for the TechnetiumDNS integration."""

DOMAIN = "technetiumdns"

SENSOR_TYPES = {
    "queries_last_day": {"name": "Total Queries (Last Day)"},
    "blocked_queries_last_day": {"name": "Blocked Queries (Last Day)"},
    "clients_last_day": {"name": "Clients (Last Day)"},
    "update_available": {"name": "Update Available"},
    "no_error_last_day": {"name": "Total No Error (Last Day)"},
    "server_failure_last_day": {"name": "Total Server Failure (Last Day)"},
    "nx_domain_last_day": {"name": "Total NX Domain (Last Day)"},
    "refused_last_day": {"name": "Total Refused (Last Day)"},
    "authoritative_last_day": {"name": "Total Authoritative (Last Day)"},
    "recursive_last_day": {"name": "Total Recursive (Last Day)"},
    "cached_last_day": {"name": "Total Cached (Last Day)"},
    "dropped_last_day": {"name": "Total Dropped (Last Day)"},
    "zones_last_day": {"name": "Zones (Last Day)"},
    "cached_entries_last_day": {"name": "Cached Entries (Last Day)"},
    "allowed_zones_last_day": {"name": "Allowed Zones (Last Day)"},
    "blocked_zones_last_day": {"name": "Blocked Zones (Last Day)"},
    "allow_list_zones_last_day": {"name": "Allow List Zones (Last Day)"},
    "block_list_zones_last_day": {"name": "Block List Zones (Last Day)"},
    "top_clients_last_day": {"name": "Top Clients (Last Day)"},
    "top_domains_last_day": {"name": "Top Domains (Last Day)"},
    "top_blocked_domains_last_day": {"name": "Top Blocked Domains (Last Day)"},
}
