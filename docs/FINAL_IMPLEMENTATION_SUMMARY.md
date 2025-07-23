# TechnitiumDNS Integration - Technical Architecture

## Current Status: PRODUCTION READY

The TechnitiumDNS Home Assistant integration provides comprehensive DNS server monitoring and DHCP device tracking with intelligent activity analysis.

## Core Components

### 1. Smart Activity Analyzer
- **File**: `custom_components/technitiumdns/activity_analyzer.py`
- **Purpose**: Analyzes DNS query patterns to distinguish between genuine user activity and background/automated traffic
- **Features**:
  - Configurable activity score threshold (default: 25)
  - Configurable analysis window (default: 30 minutes)
  - Multiple activity indicators: query volume, timing patterns, query diversity
  - Background traffic filtering (updates, sync, telemetry)

### 2. Device Tracker Platform
- **File**: `custom_components/technitiumdns/device_tracker.py`
- **Features**:
  - DHCP device tracking with IP filtering
  - Smart Activity Analyzer integration
  - Comprehensive configuration options
  - Enhanced DNS log analysis with timezone handling
  - Automatic entity cleanup for configuration changes

### 3. Sensor Platform
- **File**: `custom_components/technitiumdns/sensor.py`
- **Features**:
  - Main DNS statistics sensors (queries, top clients, domains)
  - 11 diagnostic sensors per DHCP device:
    1. **IP Address** - Current IP assignment
    2. **MAC Address** - Hardware identifier
    3. **Hostname** - Device name
    4. **Lease Obtained** - When DHCP lease was obtained
    5. **Lease Expires** - When DHCP lease expires
    6. **Last Seen** - Last DNS activity timestamp
    7. **Is Stale** - Whether device appears inactive
    8. **Minutes Since Seen** - Time since last activity
    9. **Activity Score** - Smart activity analysis score (0-100)
    10. **Is Actively Used** - Boolean based on activity threshold
    11. **Activity Summary** - Human-readable activity description

### 4. Entity Cleanup System
- **File**: `custom_components/technitiumdns/__init__.py`
- **Features**:
  - Automatic cleanup of orphaned entities when IP filtering changes
  - Manual cleanup service: `technitiumdnsdhcp.cleanup_devices`
  - DHCP data retrieval service: `technitiumdnsdhcp.get_dhcp_leases`
  - Safe removal that only affects integration entities
  - Comprehensive logging of cleanup actions

### 5. Configuration Options
- **DHCP Tracking**: Enable/disable device tracking
- **IP Address Filtering**: Include/exclude devices by IP ranges
- **Smart Activity**: Enable/disable intelligent activity analysis
- **Activity Threshold**: Configurable score threshold (default: 25)
- **Analysis Window**: Time window for analysis (default: 30 minutes)
- **DNS Log Tracking**: Enhanced DNS query analysis
- **Stale Threshold**: Time before device considered stale (default: 60 minutes)

### 6. Button Platform
- **File**: `custom_components/technitiumdns/button.py`
- **Features**:
  - Ad blocking disable buttons (5min, 10min, 30min, 60min, 1 day)
  - Manual entity cleanup button for DHCP devices
  - Integration with cleanup service

## Platform Architecture

### Platform Loading Order
The integration loads platforms in a specific order to ensure proper coordination:
1. **Button** - Ad blocking controls
2. **Switch** - Ad blocking toggle
3. **Device Tracker** - DHCP device tracking (creates coordinators)
4. **Sensor** - DNS statistics and device diagnostic sensors

### Coordinator Pattern
- **DNS Coordinator**: Handles DNS statistics queries
- **DHCP Coordinator**: Handles device tracking and smart activity analysis
- Coordinators are shared between platforms via `hass.data`

### Entity Categories
- **Main DNS Sensors**: Regular entities on the main DNS server device
- **Device Trackers**: Source type "router" for DHCP-tracked devices
- **Diagnostic Sensors**: Category "diagnostic" linked to tracked devices
- **Buttons/Switches**: Controls on the main DNS server device

## Configuration Options

### DHCP Device Tracking
- **Enable DHCP Tracking**: Boolean toggle for device tracking
- **Update Interval**: 30s, 1min, 5min, 10min (default: 60s)
- **IP Filtering**: Disabled, Include Mode, Exclude Mode
- **IP Ranges**: Flexible format (single IPs, CIDR, ranges)

### Smart Activity Analysis
- **Enable Smart Activity**: Boolean toggle for intelligent analysis
- **Activity Threshold**: 0-100 score threshold (default: 25)
- **Analysis Window**: 15min-4hrs time window (default: 30min)
- **DNS Log Tracking**: Enhanced activity detection via DNS logs
- **Stale Threshold**: Minutes before device considered stale (default: 60)

## Integration Features

### Device Management
- Automatic device discovery via DHCP leases
- Intelligent activity scoring to distinguish real usage from background traffic
- Automatic entity cleanup when IP filtering changes
- Manual cleanup via service call or button

### Monitoring Capabilities
- Real-time DNS query statistics and top clients/domains
- Per-device diagnostic information including lease details
- Activity scoring and stale device detection
- Timezone-aware timestamp handling

### User Experience
- Clean device organization in Home Assistant UI
- Diagnostic sensors properly categorized
- Comprehensive configuration options
- Manual controls for ad blocking and device cleanup
