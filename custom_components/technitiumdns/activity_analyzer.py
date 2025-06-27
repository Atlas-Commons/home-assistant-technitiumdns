"""Smart Activity Analysis for TechnitiumDNS device tracking.

This module implements intelligent activity scoring that can distinguish between
genuine user activity and automated background traffic patterns.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re

from .const import (
    BACKGROUND_DOMAINS,
    PROTOCOL_WEIGHTS,
    QUERY_TYPE_WEIGHTS,
    DEFAULT_ACTIVITY_SCORE_THRESHOLD,
    DEFAULT_ACTIVITY_ANALYSIS_WINDOW
)

_LOGGER = logging.getLogger(__name__)


class SmartActivityAnalyzer:
    """Analyzes DNS query patterns to determine genuine device activity."""
    
    def __init__(self, score_threshold: int = DEFAULT_ACTIVITY_SCORE_THRESHOLD,
                 analysis_window_minutes: int = DEFAULT_ACTIVITY_ANALYSIS_WINDOW):
        """Initialize the activity analyzer.
        
        Args:
            score_threshold: Minimum score to consider device actively used
            analysis_window_minutes: Time window to analyze for activity patterns
        """
        self.score_threshold = score_threshold
        self.analysis_window_minutes = analysis_window_minutes
        
    def analyze_device_activity(self, dns_logs: List[Dict], ip_address: str) -> Dict:
        """Analyze DNS logs for a device and calculate activity score.
        
        Args:
            dns_logs: List of DNS log entries
            ip_address: IP address of the device to analyze
            
        Returns:
            Dict with activity analysis results
        """
        # Filter logs for this device within analysis window
        device_logs = self._filter_device_logs(dns_logs, ip_address)
        
        if not device_logs:
            return {
                'activity_score': 0,
                'is_actively_used': False,
                'total_queries': 0,
                'background_ratio': 0.0,
                'protocol_diversity': 0,
                'query_rate': 0.0,
                'analysis_summary': 'No DNS activity found'
            }
        
        # Calculate various activity metrics
        total_queries = len(device_logs)
        background_score = self._calculate_background_score(device_logs)
        protocol_score = self._calculate_protocol_score(device_logs)
        diversity_score = self._calculate_diversity_score(device_logs) 
        frequency_score = self._calculate_frequency_score(device_logs)
        timing_score = self._calculate_timing_score(device_logs)
        
        # Weighted final activity score (0-100)
        activity_score = (
            background_score * 0.3 +      # 30% - background vs user content
            protocol_score * 0.25 +       # 25% - protocol mix (TCP vs UDP)
            diversity_score * 0.2 +       # 20% - domain diversity
            frequency_score * 0.15 +      # 15% - query frequency patterns
            timing_score * 0.1            # 10% - timing patterns
        )
        
        # Calculate additional metrics for diagnostics
        background_queries = sum(1 for log in device_logs if self._is_background_query(log))
        background_ratio = background_queries / total_queries if total_queries > 0 else 0
        
        protocols_used = set(log.get('protocol', 'UDP') for log in device_logs)
        protocol_diversity = len(protocols_used)
        
        # Calculate query rate (queries per minute)
        if device_logs:
            time_span = self._get_time_span_minutes(device_logs)
            query_rate = total_queries / max(time_span, 1)
        else:
            query_rate = 0
            
        # Generate human-readable summary
        analysis_summary = self._generate_analysis_summary(
            activity_score, total_queries, background_ratio, protocol_diversity
        )
        
        is_actively_used = activity_score >= self.score_threshold
        
        _LOGGER.debug(
            "Device %s activity analysis: score=%.1f, queries=%d, bg_ratio=%.2f, "
            "protocols=%d, rate=%.1f/min, active=%s",
            ip_address, activity_score, total_queries, background_ratio, 
            protocol_diversity, query_rate, is_actively_used
        )
        
        return {
            'activity_score': round(activity_score, 1),
            'is_actively_used': is_actively_used,
            'total_queries': total_queries,
            'background_ratio': round(background_ratio, 3),
            'protocol_diversity': protocol_diversity,
            'query_rate': round(query_rate, 2),
            'analysis_summary': analysis_summary,
            'score_breakdown': {
                'background_score': round(background_score, 1),
                'protocol_score': round(protocol_score, 1),
                'diversity_score': round(diversity_score, 1),
                'frequency_score': round(frequency_score, 1),
                'timing_score': round(timing_score, 1)
            }
        }
    
    def _filter_device_logs(self, dns_logs: List[Dict], ip_address: str) -> List[Dict]:
        """Filter DNS logs for a specific device within the analysis window."""
        cutoff_time = datetime.now() - timedelta(minutes=self.analysis_window_minutes)
        
        device_logs = []
        for log in dns_logs:
            # Check if log is for this device
            if log.get('clientIpAddress') != ip_address:
                continue
                
            # Check if log is within time window
            log_time_str = log.get('timestamp')
            if log_time_str:
                try:
                    log_time = datetime.fromisoformat(log_time_str.replace('Z', '+00:00'))
                    if log_time.replace(tzinfo=None) >= cutoff_time:
                        device_logs.append(log)
                except (ValueError, AttributeError):
                    continue
                    
        return device_logs
    
    def _calculate_background_score(self, device_logs: List[Dict]) -> float:
        """Calculate score based on background vs user traffic ratio."""
        if not device_logs:
            return 0
            
        user_queries = 0
        background_queries = 0
        
        for log in device_logs:
            if self._is_background_query(log):
                background_queries += 1
            else:
                user_queries += 1
        
        total_queries = len(device_logs)
        user_ratio = user_queries / total_queries if total_queries > 0 else 0
        
        # Score increases with user content ratio
        return min(user_ratio * 100, 100)
    
    def _calculate_protocol_score(self, device_logs: List[Dict]) -> float:
        """Calculate score based on protocol mix (TCP vs UDP)."""
        if not device_logs:
            return 0
            
        protocol_scores = []
        for log in device_logs:
            protocol = log.get('protocol', 'UDP').upper()
            weight = PROTOCOL_WEIGHTS.get(protocol, 0.5)
            protocol_scores.append(weight)
        
        average_protocol_score = sum(protocol_scores) / len(protocol_scores)
        return min(average_protocol_score * 100, 100)
    
    def _calculate_diversity_score(self, device_logs: List[Dict]) -> float:
        """Calculate score based on domain and query type diversity."""
        if not device_logs:
            return 0
            
        # Domain diversity
        domains = set()
        query_types = set()
        
        for log in device_logs:
            domain = log.get('question', {}).get('name', '')
            if domain:
                domains.add(domain.lower())
                
            q_type = log.get('question', {}).get('type', '')
            if q_type:
                query_types.add(q_type)
        
        # More diverse queries suggest interactive usage
        domain_diversity = min(len(domains) / 10, 1.0)  # Max score at 10+ domains
        type_diversity = min(len(query_types) / 5, 1.0)  # Max score at 5+ types
        
        diversity_score = (domain_diversity + type_diversity) / 2 * 100
        return min(diversity_score, 100)
    
    def _calculate_frequency_score(self, device_logs: List[Dict]) -> float:
        """Calculate score based on query frequency patterns."""
        if not device_logs:
            return 0
            
        total_queries = len(device_logs)
        time_span = self._get_time_span_minutes(device_logs)
        
        if time_span <= 0:
            return 50  # Single time point, moderate score
            
        queries_per_minute = total_queries / time_span
        
        # Optimal range: 0.5-5 queries per minute
        # Too low = likely background, too high = likely automated
        if 0.5 <= queries_per_minute <= 5:
            score = 100
        elif queries_per_minute < 0.5:
            score = queries_per_minute * 200  # Linear scale up to 0.5
        else:
            # Decrease score for very high frequencies (likely automated)
            score = max(100 - (queries_per_minute - 5) * 10, 10)
            
        return min(max(score, 0), 100)
    
    def _calculate_timing_score(self, device_logs: List[Dict]) -> float:
        """Calculate score based on timing patterns (human vs automated)."""
        if len(device_logs) < 3:
            return 50  # Not enough data for timing analysis
            
        # Parse timestamps and calculate intervals
        timestamps = []
        for log in device_logs:
            time_str = log.get('timestamp')
            if time_str:
                try:
                    timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    timestamps.append(timestamp)
                except (ValueError, AttributeError):
                    continue
        
        if len(timestamps) < 3:
            return 50
            
        timestamps.sort()
        
        # Calculate intervals between queries
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(interval)
        
        if not intervals:
            return 50
            
        # Analyze interval patterns
        avg_interval = sum(intervals) / len(intervals)
        
        # Calculate coefficient of variation (measure of irregularity)
        if avg_interval > 0:
            variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
            std_dev = variance ** 0.5
            cv = std_dev / avg_interval
        else:
            cv = 0
            
        # Human activity tends to be more irregular
        # Automated activity tends to be very regular or very random
        if 0.3 <= cv <= 2.0:  # Sweet spot for human-like irregularity
            score = 100
        elif cv < 0.3:  # Too regular (automated)
            score = cv * 333  # Linear scale up to 0.3
        else:  # Too random (may be automated burst)
            score = max(100 - (cv - 2.0) * 50, 10)
            
        return min(max(score, 0), 100)
    
    def _is_background_query(self, log: Dict) -> bool:
        """Determine if a DNS query is likely background/automated traffic."""
        domain = log.get('question', {}).get('name', '').lower()
        query_type = log.get('question', {}).get('type', '')
        
        # Check against known background domains
        for bg_domain in BACKGROUND_DOMAINS:
            if bg_domain in domain:
                return True
        
        # Check query type weight (lower weight = more likely background)
        type_weight = QUERY_TYPE_WEIGHTS.get(query_type, 0.5)
        if type_weight <= 0.4:
            return True
            
        # Check for patterns indicating automated queries
        if self._is_automated_pattern(domain):
            return True
            
        return False
    
    def _is_automated_pattern(self, domain: str) -> bool:
        """Check if domain matches automated query patterns."""
        # Long random subdomains (often telemetry)
        if re.search(r'[a-f0-9]{16,}\.', domain):
            return True
            
        # Numbered subdomains (CDN/load balancing)
        if re.search(r'\d+\.[a-z]+\.\w+$', domain):
            return True
            
        # Version/build numbers in domain
        if re.search(r'v\d+\.|version\d+\.', domain):
            return True
            
        return False
    
    def _get_time_span_minutes(self, device_logs: List[Dict]) -> float:
        """Get time span of logs in minutes."""
        timestamps = []
        for log in device_logs:
            time_str = log.get('timestamp')
            if time_str:
                try:
                    timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    timestamps.append(timestamp)
                except (ValueError, AttributeError):
                    continue
        
        if len(timestamps) < 2:
            return 1.0  # Default to 1 minute for single queries
            
        timestamps.sort()
        time_span = (timestamps[-1] - timestamps[0]).total_seconds() / 60
        return max(time_span, 1.0)  # Minimum 1 minute
    
    def _generate_analysis_summary(self, score: float, queries: int, 
                                 bg_ratio: float, protocols: int) -> str:
        """Generate human-readable summary of activity analysis."""
        if score >= 75:
            activity_level = "High user activity"
        elif score >= 50:
            activity_level = "Moderate user activity"
        elif score >= 25:
            activity_level = "Low user activity"
        else:
            activity_level = "Mostly background traffic"
            
        return (f"{activity_level} - {queries} queries, "
                f"{bg_ratio:.0%} background, {protocols} protocols")


def analyze_batch_device_activity(dns_logs: List[Dict], device_ips: List[str],
                                analyzer: SmartActivityAnalyzer) -> Dict[str, Dict]:
    """Analyze activity for multiple devices in batch.
    
    Args:
        dns_logs: Complete DNS logs dataset
        device_ips: List of device IP addresses to analyze
        analyzer: SmartActivityAnalyzer instance
        
    Returns:
        Dict mapping IP addresses to activity analysis results
    """
    results = {}
    
    _LOGGER.info("Performing batch activity analysis for %d devices", len(device_ips))
    
    for ip_address in device_ips:
        try:
            analysis = analyzer.analyze_device_activity(dns_logs, ip_address)
            results[ip_address] = analysis
            
            _LOGGER.debug(
                "Device %s: activity_score=%.1f, active=%s, summary='%s'",
                ip_address, analysis['activity_score'], 
                analysis['is_actively_used'], analysis['analysis_summary']
            )
            
        except Exception as e:
            _LOGGER.error("Error analyzing activity for device %s: %s", ip_address, e)
            results[ip_address] = {
                'activity_score': 0,
                'is_actively_used': False,
                'total_queries': 0,
                'background_ratio': 0.0,
                'protocol_diversity': 0,
                'query_rate': 0.0,
                'analysis_summary': f'Analysis error: {e}'
            }
    
    # Log summary statistics
    active_devices = sum(1 for result in results.values() if result['is_actively_used'])
    avg_score = sum(result['activity_score'] for result in results.values()) / len(results) if results else 0
    
    _LOGGER.info(
        "Batch analysis complete: %d/%d devices actively used, average score: %.1f",
        active_devices, len(device_ips), avg_score
    )
    
    return results
