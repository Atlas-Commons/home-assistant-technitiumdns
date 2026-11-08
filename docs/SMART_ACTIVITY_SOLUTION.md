# Smart Activity Analysis Solution

## Problem Statement
DNS query logs contain both routine and interactive traffic, and a short or old sample cannot establish current activity. This analysis classifies observed DNS traffic only; it does not determine whether a device is reachable, whether a person is present, or who caused a query.

## Solution: Multi-Factor Activity Scoring System

### Overview
The **Smart Activity Analyzer** calculates a heuristic score (0-100) from DNS records when there is enough recent evidence. The score is a traffic classification, not a probability or a claim about a person's activity.

#### Evidence and score contract
- A sample is scoreable only when at least **3 DNS log records** fall within the newest **30 minutes**.
- Scores and `is_actively_used` are `None` when evidence is insufficient; an empty analysis window has status `no_data`, while a sparse or old sample has status `insufficient_evidence`.
- `activity_evidence` reports the required and observed recent counts, the recent window, the total records in the configured analysis window, and the newest record age when available.
- A numeric score is calculated only from the recent records that passed the evidence gate. The configured threshold compares that heuristic score; it does not assert presence or connectivity.
- `score_breakdown` is carried with the analyzed lease data and exposed by the activity summary diagnostic sensor for inspection.
- The count is a count of log records, not guaranteed independent user actions. Missing, truncated, cached, or unattributed logs can still limit interpretation.
- This heuristic cannot guarantee elimination of false positives or false negatives.

### Key Features

#### 1. **Multi-Factor Scoring Algorithm** (Weighted Score Components)
- **Background Content Analysis (30%)**: Matches configured DNS suffixes and label prefixes
- **Protocol Mix Analysis (25%)**: Applies configured transport weights
- **Domain Diversity (20%)**: Scores diversity in the observed DNS names
- **Query Frequency Patterns (15%)**: Scores query rate within the recent sample
- **Timing Irregularity (10%)**: Scores variation in observed query intervals

#### 2. **Background Traffic Detection**
Automatically identifies background domains including:
- Time/NTP services (`time.`, `ntp.`, `pool.ntp.org`)
- Software updates (`update.`, `windowsupdate.com`)
- Telemetry (`analytics.`, `metrics.`, `google-analytics.com`)
- Certificate checks (`ocsp.`, `crl.`)
- IoT background services (`amazonaws.com`, `icloud.com`)

#### 3. **Protocol Intelligence**
- **HTTPS**: 1.2x configured weight
- **TCP**: 1.0x configured weight
- **HTTP**: 0.8x configured weight
- **UDP**: 0.3x configured weight

#### 4. **Query Type Analysis**
- **A/AAAA records**: Full weight (normal browsing)
- **TXT/SRV records**: Lower weight (often automated)
- **PTR/SOA records**: Minimal weight (infrastructure)

### Configuration Options

#### New Settings Added:
- **DNS Log Tracking**: Off by default; enables retrieval and analysis of DNS query records
- **Smart Activity Analysis**: On by default; scores remain unknown unless DNS log tracking is enabled and enough recent records are available
- **Activity Score Threshold**: Minimum score for the `is_actively_used` heuristic (default: 55)
- **Analysis Window**: Time window for pattern analysis (15min - 4hrs, default: 120min); the scoreable evidence must still be in the newest 30 minutes
- **Option changes**: Saving integration options reloads the config entry so the coordinator uses the new settings.

#### Threshold Levels:
- **0-10**: Very Low (mostly background)
- **10-25**: Low DNS activity score
- **25-50**: Medium DNS score
- **50-75**: High DNS score (the default threshold is 55)
- **75-100**: Very high DNS score

### Implementation Details

#### New Components:
1. **`activity_analyzer.py`**: Core analysis engine with sophisticated algorithms
2. **Enhanced device tracker**: Keeps DHCP lease presence separate from DNS activity classification
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
# Irregular interval pattern: 0.3-2.0 CV
# Other interval patterns: <0.3 CV or >2.0 CV
```

**Frequency Scoring:**
```python
# Preferred query-rate range: 0.5-5 queries/minute
# Below: likely background only
# Above: likely automated bursts
```

### Usage Examples

#### Example 1: Recent Above-Threshold DNS Sample
```
Activity Score: 78.5
- 45 queries total
- 15% background traffic
- Mixed TCP/HTTPS protocols
- High domain diversity
- Irregular timing patterns
Result: The recent DNS score exceeds the configured threshold; this does not establish reachability or person presence.
```

#### Example 2: Low-Scoring DNS Sample
```
Activity Score: 12.3
- 8 queries total
- 87% background traffic (NTP, updates)
- Mostly UDP protocols
- Low domain diversity
- Regular timing (every 15 minutes)
Result: The observed DNS traffic scores below the configured threshold; this does not establish disconnection.
```

#### Example 3: Mixed DNS Sample
```
Activity Score: 34.1
- 23 queries total
- 35% background traffic
- Some TCP queries
- Moderate domain diversity
Result: The recent DNS score is below the default threshold of 55; the records do not identify their cause.
```

### Benefits

1. **Explicit Evidence State**: Sparse and old samples remain unknown instead of being assigned a boolean.
2. **Inspectable Heuristic**: Recent query evidence is exposed for diagnostics.
3. **Configurable Sensitivity**: Adjustable threshold for different network environments
4. **Rich Diagnostics**: Detailed scoring breakdown for troubleshooting
5. **Independent Lease State**: DHCP lease presence remains available independently; DNS analysis failures do not produce an activity score

### Diagnostic Information

Each device now provides:
- **Activity Score**: Numeric DNS traffic score (0-100), or unknown when evidence is insufficient
- **Is Actively Used**: Nullable heuristic classification based on the configured score threshold
- **Activity Summary**: DNS traffic summary (for example, "High DNS activity score - 45 queries, 15% background, 3 protocols")

### Performance Optimizations

- **Batch Processing**: Analyzes devices from one shared query-log request
- **Bounded Retrieval**: Requests up to 5,000 log entries; busy installations may have incomplete coverage
- **Configurable Windows**: The selected analysis window limits candidate records before the recent-evidence gate
- **Graceful Failure State**: DNS errors and missing evidence remain explicit; lease-based tracker state is independent

This heuristic summarizes DNS traffic patterns. It cannot reliably identify human activity, device reachability, or complete activity when logs are missing or truncated.
