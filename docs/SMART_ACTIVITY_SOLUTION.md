# Smart Activity Analysis Solution

## Problem Statement
Some devices make automatic background calls (mostly UDP), causing the current implementation to consider them active when they're actually dormant. The goal is to distinguish between genuine user activity and background noise.

## Solution: Multi-Factor Activity Scoring System

### Overview
Implemented a comprehensive **Smart Activity Analyzer** that calculates an activity score (0-100) based on multiple factors to determine if a device is genuinely being used by a person or just making automated background calls.

### Key Features

#### 1. **Multi-Factor Scoring Algorithm** (Weighted Score Components)
- **Background Content Analysis (30%)**: Identifies known background domains (NTP, updates, telemetry)
- **Protocol Mix Analysis (25%)**: TCP traffic scores higher than UDP (user browsing vs automated checks)
- **Domain Diversity (20%)**: More diverse domains indicate interactive usage
- **Query Frequency Patterns (15%)**: Human-like frequency vs automated bursts
- **Timing Irregularity (10%)**: Human behavior is irregular, automation is regular

#### 2. **Background Traffic Detection**
Automatically identifies background domains including:
- Time/NTP services (`time.`, `ntp.`, `pool.ntp.org`)
- Software updates (`update.`, `windowsupdate.com`)
- Telemetry (`analytics.`, `metrics.`, `google-analytics.com`)
- Certificate checks (`ocsp.`, `crl.`)
- IoT background services (`amazonaws.com`, `icloud.com`)

#### 3. **Protocol Intelligence**
- **HTTPS**: 1.2x weight (user browsing)
- **TCP**: 1.0x weight (interactive)
- **HTTP**: 0.8x weight (mixed usage)
- **UDP**: 0.3x weight (often background)

#### 4. **Query Type Analysis**
- **A/AAAA records**: Full weight (normal browsing)
- **TXT/SRV records**: Lower weight (often automated)
- **PTR/SOA records**: Minimal weight (infrastructure)

### Configuration Options

#### New Settings Added:
- **Smart Activity Analysis**: Enable/disable intelligent activity detection
- **Activity Score Threshold**: Minimum score to consider device "actively used" (default: 25)
- **Analysis Window**: Time window for pattern analysis (15min - 4hrs, default: 30min)

#### Threshold Levels:
- **0-10**: Very Low (mostly background)
- **10-25**: Low (some user activity)
- **25-50**: Medium (regular usage) ← Default threshold
- **50-75**: High (active usage)
- **75-100**: Very High (heavy usage)

### Implementation Details

#### New Components:
1. **`activity_analyzer.py`**: Core analysis engine with sophisticated algorithms
2. **Enhanced device tracker**: Integrates smart activity into connection status
3. **New diagnostic sensors**: Activity Score, Is Actively Used, Activity Summary
4. **Updated API**: Methods for comprehensive DNS log retrieval

#### Smart Detection Algorithms:

**Background Pattern Detection:**
```python
# Detects automation patterns like:
- Long random subdomains (telemetry)
- Numbered subdomains (CDN)
- Version strings in domains
- Known background service domains
```

**Timing Analysis:**
```python
# Calculates coefficient of variation for query intervals
# Human activity: 0.3-2.0 CV (irregular but not random)
# Automated: <0.3 CV (too regular) or >2.0 CV (too random)
```

**Frequency Scoring:**
```python
# Optimal human range: 0.5-5 queries/minute
# Below: likely background only
# Above: likely automated bursts
```

### Usage Examples

#### Example 1: Active User Device
```
Activity Score: 78.5
- 45 queries total
- 15% background traffic
- Mixed TCP/HTTPS protocols
- High domain diversity
- Irregular timing patterns
Result: CONNECTED (actively used)
```

#### Example 2: Background-Only Device
```
Activity Score: 12.3
- 8 queries total
- 87% background traffic (NTP, updates)
- Mostly UDP protocols
- Low domain diversity
- Regular timing (every 15 minutes)
Result: DISCONNECTED (dormant)
```

#### Example 3: Mixed Usage Device
```
Activity Score: 34.1
- 23 queries total
- 35% background traffic
- Some TCP browsing activity
- Moderate domain diversity
Result: CONNECTED (some user activity above threshold)
```

### Benefits

1. **Eliminates False Positives**: Devices with only background traffic show as disconnected
2. **Maintains True Positives**: Genuine user activity still detected accurately
3. **Configurable Sensitivity**: Adjustable threshold for different network environments
4. **Rich Diagnostics**: Detailed scoring breakdown for troubleshooting
5. **Backwards Compatible**: Falls back to traditional methods if analysis fails

### Diagnostic Information

Each device now provides:
- **Activity Score**: Numerical intelligence score (0-100)
- **Is Actively Used**: Binary determination based on threshold
- **Activity Summary**: Human-readable analysis ("High user activity - 45 queries, 15% background, 3 protocols")
- **Score Breakdown**: Individual component scores for debugging

### Performance Optimizations

- **Batch Processing**: Analyzes all devices in single API call
- **Dynamic Limits**: Adjusts log retrieval based on device count
- **Configurable Windows**: Shorter analysis windows for better performance
- **Graceful Fallback**: Reverts to DHCP-only tracking if DNS analysis fails

This solution effectively solves the dormant device problem by providing intelligent, multi-factor analysis that can distinguish between genuine user activity and automated background processes.
