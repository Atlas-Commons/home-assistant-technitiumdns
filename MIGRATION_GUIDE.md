"""
Migration Test for TechnitiumDNS Integration

This document explains the config entry migration from version 1 to version 2.
"""

# Migration Logic Overview

## Version 1 -> Version 2 Changes

### What's New in Version 2:
- Added DHCP device tracking functionality
- New configuration options:
  - `enable_dhcp_tracking` (boolean, default: False)
  - `dhcp_update_interval` (integer, default: 60 seconds)

### Migration Process:

1. **Automatic Detection**: Home Assistant detects config entries with version < 2
2. **Safe Migration**: Adds new options with safe defaults without disrupting existing functionality
3. **Logging**: Migration process is logged for troubleshooting
4. **Backward Compatibility**: Existing configurations continue to work unchanged

### Migration Steps:

```python
# Before Migration (Version 1)
config_entry = {
    "version": 1,
    "data": {
        "api_url": "http://192.168.1.1:5380",
        "token": "abc123",
        "server_name": "My DNS Server",
        "username": "admin",
        "stats_duration": "LastDay"
    },
    "options": {}  # Empty or missing
}

# After Migration (Version 2)
config_entry = {
    "version": 2,
    "data": {
        "api_url": "http://192.168.1.1:5380",
        "token": "abc123", 
        "server_name": "My DNS Server",
        "username": "admin",
        "stats_duration": "LastDay"
    },
    "options": {
        "enable_dhcp_tracking": False,    # Default: disabled
        "dhcp_update_interval": 60        # Default: 60 seconds
    }
}
```

### Benefits of This Approach:

1. **No User Intervention Required**: Migration happens automatically
2. **Safe Defaults**: DHCP tracking is disabled by default, so existing installations aren't affected
3. **Configurable Later**: Users can enable DHCP tracking via the options flow when ready
4. **Rollback Safe**: If needed, older versions can still read the config data
5. **Logging**: Clear audit trail of what was migrated

### User Experience:

- **Existing Users**: Integration continues working exactly as before
- **New Users**: Get the full feature set including DHCP tracking options
- **Upgrading Users**: Can enable new features through the integration's Configure button

### Error Handling:

- Migration failures are logged but don't prevent the integration from loading
- If migration fails, the integration falls back to safe defaults
- Users can manually reconfigure if needed

This migration strategy ensures that the addition of DHCP device tracking doesn't break existing installations while making the new functionality easily accessible to users who want it.
