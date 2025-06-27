![GitHub branch check runs](https://img.shields.io/github/check-runs/Amateur-God/home-assistant-technitiumdns/main?style=plastic)
![GitHub commit activity](https://img.shields.io/github/commit-activity/t/Amateur-God/home-assistant-technitiumdns?style=plastic)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/Amateur-God/home-assistant-technitiumdns?style=plastic)
![GitHub Release](https://img.shields.io/github/v/release/Amateur-God/home-assistant-technitiumdns?display_name=release&style=plastic&label=stable%20Release)
![GitHub Release](https://img.shields.io/github/v/release/Amateur-God/home-assistant-technitiumdns?include_prereleases&display_name=release&style=plastic&label=Beta%20Release)
[![Discord](https://img.shields.io/discord/1032437213100777502)](https://discord.gg/4HcExnCHg2)

# Why Forked ?

This is a fork that seeks to add device_trackers for technitium DHCP leases

# technitiumDNS Integration for Home Assistant

This custom integration allows you to integrate technitiumDNS with Home Assistant, providing sensors for various DNS statistics.

## Installation

### Manual Installation

1. **Download the repository:**
   - Clone the repository or download the ZIP file.
    ```bash
    git clone https://github.com/Amateur-God/home-assistant-technitiumdns.git
    ```
2. **Copy to Home Assistant:**
   - Copy the `custom_components` directory into your Home Assistant configuration directory.
    ```bash
    cp -r home-assistant-technitiumdns/custom_components/technitiumdns /path/to/your/home-assistant/config/custom_components/
    ```

### HACS Installation

1. **Add Custom Repository:**
   - Go to HACS in your Home Assistant.
   - Click on "Integrations".
   - Click on the three dots in the upper right corner and select "Custom repositories".
   - Add the URL to this repository: https://github.com/Amateur-God/home-assistant-technitiumdns and select the category "Integration".

2. **Install the Integration:**
   - Find `technitiumDNS` in HACS and click "Install".

## Configuration

**Add the Integration:**
   - Go to Home Assistant Configuration > Integrations.
   - Click on the "+" button to add a new integration.
   - Search for `technitiumDNS` and follow the configuration steps.

## Usage

This integration provides

Sensors for:

- Total Queries
- Blocked Queries
- Clients
- Top Clients
- Top Domains
- Top Blocked Domains
- Total No Error
- Total Server Failure
- Total NX Domain
- Total Refused
- Total Authoritative
- Total Recursive
- Total Cached
- Total Dropped
- Zones
- Cached Entries
- Allowed Zones
- Blocked Zones
- Allow List Zones
- Block List Zones
- Update Available

Switches for:

- Enable/disable Ad Blocking (will check current ad blocking state on initialization and set the switch to the correct position)

Buttons for:

- Temporarily disable ad blocking for:
   - 5 mins
   - 10 mins
   - 30 mins
   - 60 mins
   - 1 day

Device Trackers (Optional):

- **DHCP Device Tracking**: Monitor devices connected to your Technitium DHCP server
  - Shows connected/disconnected status
  - Displays IP addresses, MAC addresses, and hostnames
  - Tracks lease information and expiration times
  - Can be enabled/disabled in integration options
  - Configurable update interval (30s, 1min, 5min, 10min)
  - **IP Address Filtering**: Control which devices are tracked based on IP addresses
    - **Disabled**: Track all devices (default)
    - **Include Mode**: Only track devices in specified IP ranges
    - **Exclude Mode**: Track all devices except those in specified IP ranges
    - Supports single IPs, CIDR notation, and IP ranges
    - Examples: `192.168.1.100`, `192.168.1.0/24`, `192.168.1.1-192.168.1.50`

- **Device Diagnostic Sensors**: Each tracked device automatically gets dedicated diagnostic sensors:
  - **IP Address Sensor**: Current IP address of the device
  - **MAC Address Sensor**: Hardware MAC address identifier
  - **Hostname Sensor**: Device hostname if available from DHCP
  - **Lease Obtained Sensor**: Timestamp when the DHCP lease was first obtained
  - **Lease Expires Sensor**: Timestamp when the current DHCP lease expires
  - **Last Seen Sensor**: Last DNS activity timestamp (requires DNS logging app)
  - **Is Stale Sensor**: Whether device has been inactive for too long (requires DNS logging)
  - **Minutes Since Seen Sensor**: How many minutes since last DNS activity (requires DNS logging)
  - **Activity Score Sensor**: Intelligent activity score (0-100) distinguishing user activity from background traffic
  - **Is Actively Used Sensor**: Smart determination if device is genuinely being used (eliminates false positives)
  - **Activity Summary Sensor**: Human-readable analysis of device activity patterns
  - All sensors are marked as diagnostic entities for better organization in Home Assistant

- **Smart Activity Analysis**: Advanced feature that solves the "dormant device problem":
  - **Problem**: Devices with only background traffic (NTP, updates, telemetry) were incorrectly shown as active
  - **Solution**: Multi-factor scoring analyzes protocol mix, domain diversity, timing patterns, and background traffic ratio
  - **Background Detection**: Automatically identifies automated traffic vs genuine user activity
  - **Configurable Threshold**: Adjustable sensitivity (default: 25 points) for different network environments
  - **Rich Diagnostics**: Detailed scoring breakdown for troubleshooting device activity patterns

- **DNS Query Logs Tracking** (Advanced):
  - **Requires DNS App Installation**: DNS query logging is only available through DNS apps with logging capability
  - **Not Available by Default**: The Technitium DNS `/api/logs/query` endpoint requires specific DNS app parameters
  - **Enhanced Device Activity**: When available, provides more accurate last-seen timestamps
  - **Automatic Detection**: Integration automatically detects and uses available logging DNS apps
  - **Fallback to DHCP**: When DNS logging is unavailable, uses DHCP leases as primary tracking method

## Configuration Options

After setting up the integration, you can configure additional options by going to:

1. Home Assistant Configuration > Integrations
2. Find your TechnitiumDNS integration and click "Configure"
3. Available options:
   - **Enable DHCP Device Tracking**: Turn on device tracking for DHCP clients
   - **DHCP Update Interval**: How often to check for DHCP lease changes (30-600 seconds)
   - **IP Filter Mode**: Choose how to filter devices by IP address
   - **IP Addresses/Ranges**: Specify which IPs to include or exclude (comma or newline separated)

### IP Filtering Examples

**Include Mode** - Only track specific devices:

```text
192.168.1.100,192.168.1.101,192.168.1.102
```

**Exclude Mode** - Track all except servers:

```text
192.168.1.0/28
10.0.0.1-10.0.0.10
```

**Mixed Format** - Flexible configuration:

```text
192.168.1.100
10.0.0.0/30
172.16.1.1-172.16.1.5
```

## Entity Management

### Automatic Cleanup
When you change IP filtering settings, the integration automatically removes device tracker entities and their associated diagnostic sensors for devices that no longer match the filter criteria. This happens during the next data update cycle.

### Manual Cleanup
If you need to manually clean up orphaned entities:

1. **Using the Cleanup Button**: Go to your TechnitiumDNS device page and click the "Cleanup Devices" button.

2. **Using the Service**: Call the `technitiumdnsdhcp.cleanup_devices` service:
   ```yaml
   service: technitiumdnsdhcp.cleanup_devices
   data:
     config_entry_id: "your_entry_id"  # Optional - if omitted, cleans all entries
   ```

3. **Using Developer Tools**: Go to Developer Tools > Services and search for "Cleanup Devices".

### What Gets Cleaned Up
- Device tracker entities for devices no longer matching IP filters
- All diagnostic sensors associated with removed devices
- Device registry entries for devices with no remaining entities
- Orphaned entity registry entries

**Note**: Only entities belonging to this integration are affected. Other integrations and their entities remain untouched.

## 📚 Documentation

For detailed documentation, troubleshooting guides, and implementation details, see the [docs/](docs/) directory:

- **[Implementation Guides](docs/INDEX.md#implementation-guides)** - DHCP implementation, entity cleanup, and technical summaries
- **[Feature Documentation](docs/INDEX.md#feature-documentation)** - Smart Activity Analysis and diagnostic sensors
- **[Testing & Troubleshooting](docs/INDEX.md#testing--troubleshooting)** - Comprehensive guides for issue resolution
- **[Migration Guides](docs/INDEX.md#migration--updates)** - Upgrading from older versions

Visit [docs/INDEX.md](docs/INDEX.md) for a complete documentation index.

## Contributing

If you want to contribute to this project, feel free to fork the repository and submit a pull request. Issues and feature requests are also welcome.

## License

This project is licensed under the GPL 3.0 License. See the [LICENSE](LICENSE) file for details.

## Disclaimer

The non-English translations for this integration were generated by ChatGPT and may not be perfectly accurate. If you find any errors or improvements, please feel free to contribute.


## TECHNITIUM API DOCUMENTATION

https://github.com/TechnitiumSoftware/DnsServer/blob/master/APIDOCS.md