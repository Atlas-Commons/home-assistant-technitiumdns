"""Constants for the TechnitiumDNS integration."""

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

# Smart Activity Scoring Options
CONF_DHCP_SMART_ACTIVITY = "dhcp_smart_activity"
CONF_ACTIVITY_SCORE_THRESHOLD = "activity_score_threshold"
CONF_ACTIVITY_ANALYSIS_WINDOW = "activity_analysis_window"

# Default values for smart activity
DEFAULT_DHCP_SMART_ACTIVITY = True
DEFAULT_ACTIVITY_SCORE_THRESHOLD = 25  # Score needed to consider device "actively used"
DEFAULT_ACTIVITY_ANALYSIS_WINDOW = 120  # Minutes to analyze for activity patterns (2 hours)

# Activity scoring thresholds
ACTIVITY_SCORE_THRESHOLDS = {
    10: "Very Low (mostly background)",
    33: "Low (some user activity)", 
    55: "Medium (regular usage)",
    76: "High (active usage)",
    100: "Very High (heavy usage)"
}

# Analysis window options (in minutes)
ACTIVITY_ANALYSIS_WINDOWS = {
    15: "15 minutes",
    30: "30 minutes",
    60: "1 hour",
    120: "2 hours",
    240: "4 hours"
}

# Background traffic patterns (domains that indicate automated activity)
BACKGROUND_DOMAINS = {
    # Time/NTP services
    'time.', 'ntp.', 'pool.ntp.org', 'time.windows.com', 'time.apple.com',
    'time.nist.gov', 'time.cloudflare.com', 'ntp.ubuntu.com',
    
    # Software updates and package managers
    'update.', 'updates.', 'download.', 'windowsupdate.com', 'apple.com/updates',
    'software-update', 'swupdate', 'autoupdate', 'chrome-devtools-frontend',
    'packages.', 'repo.', 'repository.', 'dl.google.com', 'releases.ubuntu.com',
    
    # Telemetry and analytics (comprehensive list)
    'telemetry.', 'analytics.', 'metrics.', 'stats.', 'tracking.', 'beacon.',
    'google-analytics.com', 'googletagmanager.com', 'facebook.com/tr',
    'amplitude.com', 'mixpanel.com', 'segment.', 'hotjar.com', 'fullstory.com',
    'newrelic.com', 'datadog.com', 'sentry.io', 'bugsnag.com', 'crashlytics.',
    'flurry.com', 'countly.', 'umeng.com', 'adjust.com', 'appsflyer.com',
    'branch.io', 'kochava.com', 'singular.net', 'tune.com', 'apsalar.com',
    
    # Certificate/Security/OCSP
    'ocsp.', 'crl.', 'certificate.', 'ssl.', 'security.', 'pki.',
    'certs.', 'ca-', 'revocation.', 'validation.',
    
    # Cloud and CDN infrastructure
    'amazonaws.com', 'googleapi.', 'icloud.com', 'live.com', 'outlook.com',
    'cloudfront.net', 'akamai.', 'fastly.com', 'cloudflare.com',
    'azureedge.net', 'msecnd.net', 'edge.', 'cdn.', 'static.',
    
    # DNS infrastructure and connectivity
    'root-servers.net', 'gtld-servers.net', 'dns.', 'resolver.',
    'connectivity-check.', 'captive.apple.com', 'msftconnecttest.com',
    'connectivitycheck.', 'generate_204', 'clients1.google.com',
    
    # Operating system background services
    'wpad.', 'isatap.', 'teredo.', 'ipv6.', 'localhost.',
    'safebrowsing.', 'phishing-protection.', 'malware-check.',
    
    # Error reporting and crash dumps
    'crash.', 'crashdump.', 'watson.', 'error-report.', 'dump.',
    'feedback.', 'report.', 'diagnostic.',
    
    # Location and geolocation services
    'location.', 'geoip.', 'geolocation.', 'whereami.', 'ipinfo.',
    'maxmind.com', 'geonames.org', 'ip-api.com',
    
    # Push notification services
    'push.', 'notification.', 'fcm.googleapis.com', 'apple-push.',
    'pusher.', 'pushwoosh.', 'onesignal.com', 'urbanairship.com',
    
    # Sync services (automatic data synchronization)
    'sync.', 'backup.', 'cloud-sync.', 'dropbox-sync.', 'onedrive.',
    'googlesync.', 'icloud-sync.', 'account-sync.',
    
    # Smart TV and IoT device communication
    'samsung.', 'lg.com', 'sony.', 'roku.', 'netflix.', 'hulu.',
    'amazonvideo.', 'smart-tv.', 'iot.', 'alexa.', 'googlehome.',
    
    # Gaming platform background services
    'steam.', 'origin.', 'uplay.', 'battlenet.', 'epicgames.',
    'xbox.', 'playstation.', 'nintendo.', 'gamepass.',
    
    # Browser background processes
    'safebrowsing.googleapis.com', 'chrome-variations.',
    'firefox-settings.', 'edge-enterprise.', 'browser-update.',
    'extension-update.', 'addon-update.',
    
    # Ad/tracking domains (background activity)
    'doubleclick.', 'googleadservices.', 'googlesyndication.',
    'facebook.com/tr', 'twitter.com/i/', 'linkedin.com/px/',
    'pinterest.com/ct/', 'bing.com/th', 'yahoo.com/p',
    
    # System monitoring and health checks
    'monitor.', 'health-check.', 'status.', 'ping.', 'heartbeat.',
    'uptime.', 'availability.', 'probe.',
    
    # Configuration and settings synchronization
    'config.', 'settings.', 'preferences.', 'profile-sync.',
    'user-data.', 'account-info.',
    
    # License verification and activation
    'license.', 'activation.', 'verify.', 'validate.', 'auth.',
    'activation-server.', 'product-key.',
    
    # Weather services (often background updates)
    'weather.', 'forecast.', 'openweathermap.', 'accuweather.',
    'weather-api.', 'meteo.',
    
    # News and content feeds (RSS, etc.)
    'feed.', 'rss.', 'news-feed.', 'content-update.',
    'headlines.', 'breaking-news.',
    
    # VPN and proxy detection
    'vpn-detect.', 'proxy-check.', 'tor-check.', 'anonymizer-detect.',
    
    # Version checks and compatibility
    'version.', 'compatibility.', 'support-check.', 'feature-flag.',
    'experiment.', 'a-b-test.',
}

# Protocol scoring weights
PROTOCOL_WEIGHTS = {
    'UDP': 0.3,  # Lower weight for UDP (often background)
    'TCP': 1.0,  # Full weight for TCP (usually interactive)
    'HTTPS': 1.2,  # Higher weight for HTTPS (user browsing)
    'HTTP': 0.8   # Medium weight for HTTP
}

# Query type scoring weights  
QUERY_TYPE_WEIGHTS = {
    'A': 1.0,      # Standard domain lookup
    'AAAA': 1.0,   # IPv6 lookup
    'CNAME': 0.8,  # Alias lookup
    'MX': 0.6,     # Mail exchange (often background)
    'TXT': 0.5,    # Text records (often automated)
    'SRV': 0.4,    # Service discovery (often background)
    'PTR': 0.3,    # Reverse lookup (often automated)
    'SOA': 0.2,    # Zone transfer (automated)
    'NS': 0.2      # Name server lookup (automated)
}
