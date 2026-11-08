"""Support for TechnitiumDNS DHCP device tracking.

This module provides device tracker entities that monitor DHCP lease status.
Diagnostic sensor entities for each tracked device are created by the sensor platform
and are automatically linked to the device through proper device grouping.
"""
from datetime import timedelta, datetime, timezone
import logging

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN, 
    CONF_DHCP_LOG_TRACKING, 
    CONF_DHCP_STALE_THRESHOLD, 
    DEFAULT_DHCP_LOG_TRACKING,
    DEFAULT_DHCP_STALE_THRESHOLD,
    CONF_DHCP_SMART_ACTIVITY,
    CONF_ACTIVITY_SCORE_THRESHOLD,
    CONF_ACTIVITY_ANALYSIS_WINDOW,
    DEFAULT_DHCP_SMART_ACTIVITY,
    DEFAULT_ACTIVITY_SCORE_THRESHOLD,
    DEFAULT_ACTIVITY_ANALYSIS_WINDOW,
)
from .dns_logs import (
    DNSLogsUnavailableError,
    get_dns_logs_for_analysis,
    get_last_seen_for_multiple_ips,
    test_dns_logs_api,
)
from .utils import (
    should_track_ip,
    normalize_mac_address,
    normalize_hostname,
    parse_timestamp,
)
from .activity_analyzer import (
    SmartActivityAnalyzer,
    _normalize_log_entry,
    analyze_batch_device_activity,
)

# Import cleanup functionality
async def async_cleanup_orphaned_entities(hass, entry_id, current_devices):
    """Import cleanup function from __init__.py"""
    from . import async_cleanup_orphaned_entities as cleanup_func
    return await cleanup_func(hass, entry_id, current_devices)

_LOGGER = logging.getLogger(__name__)


def _latest_activity_timestamp(dns_logs, ip_address):
    """Return the latest valid DNS timestamp for an analyzed device."""
    timestamps = []
    for log in dns_logs:
        normalized_log = _normalize_log_entry(log)
        if not normalized_log or normalized_log["clientIpAddress"] != ip_address:
            continue
        timestamp = normalized_log["_timestamp"]
        now = datetime.now(timestamp.tzinfo)
        if timestamp <= now + timedelta(minutes=2):
            timestamps.append(timestamp)
    return max(timestamps, default=None)


def _logs_for_current_leases(dns_logs, ip_to_lease_map):
    """Keep only valid DNS records at or after their current lease start."""
    current_logs = []
    for log in dns_logs:
        normalized_log = _normalize_log_entry(log)
        if not normalized_log:
            continue
        lease = ip_to_lease_map.get(normalized_log["clientIpAddress"])
        if lease is None:
            continue
        lease_obtained = parse_timestamp(lease.get("lease_obtained"))
        if lease_obtained is not None and normalized_log["_timestamp"] >= lease_obtained:
            current_logs.append(normalized_log)
    return current_logs


def _mark_ambiguous_activity(lease):
    """Leave activity unknown when DNS records cannot be tied to this lease."""
    lease["activity_status"] = "ambiguous"
    lease["activity_summary"] = "DNS activity attribution is ambiguous"
    lease["activity_score"] = None
    lease["is_actively_used"] = None
    lease["is_stale"] = None
    lease["last_seen"] = None
    lease["minutes_since_seen"] = None
    lease["activity_evidence"] = None
    lease["score_breakdown"] = None


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up TechnitiumDNS DHCP device trackers."""
    _LOGGER.info("Starting TechnitiumDNS DHCP device tracker setup for entry %s", entry.entry_id)
    
    try:
        config_entry = hass.data[DOMAIN][entry.entry_id]
        api = config_entry["api"]
        server_name = config_entry["server_name"]
        server_device_id = config_entry["server_device_id"]
        
        # Get update interval from options, default to 60 seconds
        update_interval = entry.options.get("dhcp_update_interval", 60)
        
        # Get IP filtering options
        ip_filter_mode = entry.options.get("dhcp_ip_filter_mode", "disabled")
        ip_ranges = entry.options.get("dhcp_ip_ranges", "")
        
        # Get DNS log tracking options
        log_tracking = entry.options.get(CONF_DHCP_LOG_TRACKING, DEFAULT_DHCP_LOG_TRACKING)
        stale_threshold = entry.options.get(CONF_DHCP_STALE_THRESHOLD, DEFAULT_DHCP_STALE_THRESHOLD)
        
        # Get smart activity options
        smart_activity = entry.options.get(CONF_DHCP_SMART_ACTIVITY, DEFAULT_DHCP_SMART_ACTIVITY)
        activity_threshold = entry.options.get(CONF_ACTIVITY_SCORE_THRESHOLD, DEFAULT_ACTIVITY_SCORE_THRESHOLD)
        analysis_window = entry.options.get(CONF_ACTIVITY_ANALYSIS_WINDOW, DEFAULT_ACTIVITY_ANALYSIS_WINDOW)
        
        _LOGGER.info("DHCP tracking configuration: interval=%s seconds, filter_mode=%s, ip_ranges=%s, log_tracking=%s, stale_threshold=%s min, smart_activity=%s, activity_threshold=%s, analysis_window=%s min", 
                    update_interval, ip_filter_mode, ip_ranges, log_tracking, stale_threshold, smart_activity, activity_threshold, analysis_window)
        
        coordinator = TechnitiumDHCPCoordinator(
            hass, api, update_interval, ip_filter_mode, ip_ranges, log_tracking, stale_threshold,
            smart_activity, activity_threshold, analysis_window
        )
        _LOGGER.debug("Created TechnitiumDHCPCoordinator: %s", coordinator)
        
        # Store coordinator in hass.data early so sensor platform can access it
        if "coordinators" not in hass.data[DOMAIN][entry.entry_id]:
            hass.data[DOMAIN][entry.entry_id]["coordinators"] = {}
        hass.data[DOMAIN][entry.entry_id]["coordinators"]["dhcp"] = coordinator
        _LOGGER.debug("Stored DHCP coordinator in hass.data for sensor platform access")
        
        _LOGGER.info("Performing initial DHCP data refresh...")
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial DHCP data refresh completed successfully")

        # Create device trackers only (sensors will be created by sensor platform)
        device_trackers = []
        if coordinator.data:
            _LOGGER.info("Processing %d DHCP leases to create device trackers", len(coordinator.data))
            for i, lease in enumerate(coordinator.data):
                # Create device tracker
                device_tracker = TechnitiumDHCPDeviceTracker(
                    coordinator, lease, server_name, entry.entry_id, server_device_id
                )
                device_trackers.append(device_tracker)
                
            _LOGGER.info("Created %d device trackers", len(device_trackers))
        else:
            _LOGGER.info("""No DHCP lease data available yet 
                         - device trackers will be created when leases are discovered""")
        
        _LOGGER.info("Adding %d device tracker entities to Home Assistant", len(device_trackers))
        async_add_entities(device_trackers, True)

        registered_devices = {
            normalize_mac_address(lease["mac_address"])
            if lease.get("mac_address")
            else f"ip:{lease.get('ip_address', '')}"
            for lease in coordinator.data or []
        }

        def _handle_coordinator_update():
            """Add trackers for leases discovered after initial setup."""
            new_trackers = []
            new_device_keys = set()
            for lease in coordinator.data or []:
                mac_address = lease.get("mac_address")
                device_key = (
                    normalize_mac_address(mac_address)
                    if mac_address
                    else f"ip:{lease.get('ip_address', '')}"
                )
                if device_key in registered_devices or device_key in new_device_keys:
                    continue
                new_device_keys.add(device_key)
                new_trackers.append(
                    TechnitiumDHCPDeviceTracker(
                        coordinator,
                        lease,
                        server_name,
                        entry.entry_id,
                        server_device_id,
                    )
                )

            if not new_trackers:
                return

            try:
                async_add_entities(new_trackers, True)
            except Exception:
                _LOGGER.exception("Failed to add trackers for newly discovered DHCP leases")
                return

            registered_devices.update(new_device_keys)

        remove_listener = coordinator.async_add_listener(_handle_coordinator_update)
        entry_data = hass.data[DOMAIN][entry.entry_id]
        previous_remove_listener = entry_data.pop("device_tracker_listener", None)
        if previous_remove_listener:
            previous_remove_listener()
        entry_data["device_tracker_listener"] = remove_listener

        _LOGGER.info("TechnitiumDNS DHCP device tracker setup completed successfully: %d device trackers", len(device_trackers))

    except Exception as e:
        _LOGGER.error("Could not initialize TechnitiumDNS DHCP tracking: %s", e, exc_info=True)
        raise ConfigEntryNotReady from e


async def async_unload_entry(hass, entry):
    """Remove the DHCP coordinator listener when unloading the tracker platform."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    remove_listener = entry_data.pop("device_tracker_listener", None)
    if remove_listener:
        remove_listener()
    return True


class TechnitiumDHCPCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TechnitiumDNS DHCP data."""

    def __init__(self, hass, api, update_interval, ip_filter_mode="disabled", ip_ranges="", log_tracking=False, stale_threshold=60, smart_activity=True, activity_threshold=25, analysis_window=30):
        """Initialize."""
        _LOGGER.info("Initializing TechnitiumDHCPCoordinator with interval=%s, filter_mode=%s, log_tracking=%s, stale_threshold=%s, smart_activity=%s, activity_threshold=%s, analysis_window=%s", 
                    update_interval, ip_filter_mode, log_tracking, stale_threshold, smart_activity, activity_threshold, analysis_window)
        self.api = api
        self.ip_filter_mode = ip_filter_mode
        self.ip_ranges = ip_ranges
        self.log_tracking = log_tracking
        self.stale_threshold_minutes = stale_threshold
        self.smart_activity_enabled = smart_activity
        self.activity_analyzer = SmartActivityAnalyzer(activity_threshold, analysis_window) if smart_activity else None
        scan_interval = timedelta(seconds=update_interval)
        _LOGGER.debug("Setting coordinator update interval to %s", scan_interval)
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_dhcp", update_interval=scan_interval)
        _LOGGER.info("TechnitiumDHCPCoordinator initialized successfully")

    async def _cleanup_orphaned_entities(self, current_macs: set):
        """Clean up entities for devices that no longer match current criteria."""
        try:
            # Get config entry ID from hass data
            entry_id = None
            for eid, data in self.hass.data.get(DOMAIN, {}).items():
                if data.get("coordinators", {}).get("dhcp") == self:
                    entry_id = eid
                    break
            
            if entry_id:
                await async_cleanup_orphaned_entities(self.hass, entry_id, current_macs)
            else:
                _LOGGER.warning("Could not find config entry ID for entity cleanup")
        except Exception as e:
            _LOGGER.error("Error during entity cleanup: %s", e, exc_info=True)

    async def _async_update_data(self):
        """Update data via library."""
        _LOGGER.info("Starting DHCP data update cycle")
        try:
            _LOGGER.debug("Fetching DHCP leases from TechnitiumDNS API")
            leases = await self.api.dhcp.leases_list()

            _LOGGER.info("Retrieved %d total DHCP leases from API", len(leases))
            
            # Log summary of lease types found
            if leases:
                types_found = set()
                for lease in leases:
                    lease_type = lease.type
                    if lease_type:
                        types_found.add(lease_type)
                _LOGGER.info("Lease types found: %s", sorted(types_found))
            
            # Process and clean up lease data
            processed_leases = []
            filtered_count = 0
            skipped_count = 0
            
            for i, lease in enumerate(leases):
                lease_type = getattr(lease, "type", None)
                ip_address = getattr(lease, "address", None)
                mac_address = getattr(lease, "hardware_address", None) or ""
                address_status = getattr(lease, "address_status", None)
                lease_expires_value = getattr(lease, "lease_expires", None)
                lease_obtained_value = getattr(lease, "lease_obtained", None)
                lease_expires = parse_timestamp(lease_expires_value)
                lease_obtained = parse_timestamp(lease_obtained_value)
                
                # Filter leases based on the official Technitium DNS API specification
                should_include = False
                skip_reason = ""
                
                # Check if we have basic required data
                if not ip_address:
                    skip_reason = "no IP address"
                elif not mac_address:
                    skip_reason = "no MAC address"
                elif address_status and address_status != "InUse":
                    skip_reason = f"address status is {address_status}"
                elif lease_expires is not None and lease_expires <= datetime.now(timezone.utc):
                    skip_reason = "lease has expired"
                elif not address_status and lease_expires is None:
                    skip_reason = "missing address status and valid lease expiry"
                else:
                    should_include = True
                
                if should_include:
                    # Normalize hostname to ensure it's always a string
                    hostname = normalize_hostname(lease.host_name)
                    # Apply IP filtering
                    if not should_track_ip(ip_address, self.ip_filter_mode, self.ip_ranges):
                        filtered_count += 1
                        # _LOGGER.debug("Filtering out IP %s based on filter mode %s", ip_address, self.ip_filter_mode)
                        continue
                    
                    # Get datetime fields and convert to ISO format strings for sensors
                    lease_expires_diagnostic = (
                        lease_expires.isoformat()
                        if lease_expires is not None
                        else lease_expires_value
                        if isinstance(lease_expires_value, str)
                        else None
                    )
                    lease_obtained_diagnostic = (
                        lease_obtained.isoformat()
                        if lease_obtained is not None
                        else lease_obtained_value
                        if isinstance(lease_obtained_value, str)
                        else None
                    )
                    
                    processed_lease = {
                        "ip_address": ip_address,
                        "mac_address": normalize_mac_address(mac_address),
                        "hostname": hostname,
                        "client_id": getattr(lease, "client_identifier", "") or "",
                        "lease_expires": lease_expires_diagnostic,
                        "lease_obtained": lease_obtained_diagnostic,
                        "scope": getattr(lease, "scope", "") or "",
                        "type": lease_type,
                        "address_status": address_status,
                        "last_seen": None,  # Will be populated by DNS log query
                        "is_stale": None,
                        "minutes_since_seen": None,
                        "activity_score": None,
                        "is_actively_used": None,
                        "activity_evidence": None,
                        "score_breakdown": None,
                        "activity_status": (
                            "disabled"
                            if not self.log_tracking or not self.smart_activity_enabled
                            else "unavailable"
                        ),
                        "activity_summary": "",  # Human-readable activity summary
                    }
                    processed_leases.append(processed_lease)
                else:
                    skipped_count += 1
            
            # Query DNS logs for last seen times if enabled
            processed_leases = await self._get_last_seen_for_devices(processed_leases)
            
            # Log stale device summary if log tracking is enabled
            if self.log_tracking:
                stale_count = sum(1 for lease in processed_leases if lease.get("is_stale", False))
                _LOGGER.info("DNS activity summary: %d devices total, %d are stale (>%d min since last seen)", len(processed_leases), stale_count, self.stale_threshold_minutes)
            
            _LOGGER.info("DHCP data processing complete: %d active leases, %d filtered, %d skipped", 
                        len(processed_leases), filtered_count, skipped_count)
            
            if filtered_count > 0:
                _LOGGER.info("Filtered out %d devices based on IP filter settings", filtered_count)
            
            _LOGGER.info("DHCP update cycle completed successfully with %d trackable devices", len(processed_leases))
            
            return processed_leases
            
        except Exception as err:
            _LOGGER.error("Error fetching DHCP data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error fetching DHCP data: {err}") from err

    async def _get_last_seen_for_devices(self, processed_leases):
        """Query DNS logs to get last seen times and activity analysis for devices."""
        if not self.log_tracking:
            for lease in processed_leases:
                lease["activity_status"] = "disabled"
            return processed_leases
            
        # Extract all IP addresses for batch query
        ip_addresses = []
        ip_to_lease_map = {}
        leases_by_ip = {}
        
        for lease in processed_leases:
            ip_address = lease.get("ip_address")
            if ip_address:
                leases_by_ip.setdefault(ip_address, []).append(lease)

        for ip_address, leases in leases_by_ip.items():
            if len(leases) != 1:
                for lease in leases:
                    _mark_ambiguous_activity(lease)
                continue

            lease = leases[0]
            lease_start = parse_timestamp(lease.get("lease_obtained"))
            if lease_start is None:
                _mark_ambiguous_activity(lease)
                continue

            ip_addresses.append(ip_address)
            ip_to_lease_map[ip_address] = lease
        
        if not ip_addresses:
            return processed_leases
            
        _LOGGER.info("Performing batch DNS log query for %d devices", len(ip_addresses))
        
        try:
            # First, test if DNS logs API is working at all
            api_test = await test_dns_logs_api(self.api)
            
            if not api_test.get("available"):
                _LOGGER.warning("DNS logs API is not available: %s", api_test.get("message"))
                _LOGGER.warning("Disabling DNS log tracking for this update cycle")
                for lease in ip_to_lease_map.values():
                    lease["activity_status"] = "unavailable"
                    lease["last_seen"] = None
                    lease["minutes_since_seen"] = None
                    lease["activity_score"] = None
                    lease["is_actively_used"] = None
                    lease["activity_evidence"] = None
                    lease["score_breakdown"] = None
                return processed_leases
            
            # Get DNS logs for smart activity analysis
            if self.smart_activity_enabled and self.activity_analyzer:
                _LOGGER.info("Performing smart activity analysis for %d devices", len(ip_addresses))
                
                # Get comprehensive DNS logs for activity analysis
                # Use a longer window to capture more activity (at least 4 hours)
                analysis_window_hours = max(4, self.activity_analyzer.analysis_window_minutes / 60)
                dns_logs = await get_dns_logs_for_analysis(
                    self.api,
                    hours_back=analysis_window_hours,
                    raise_on_error=True,
                )
                dns_logs = _logs_for_current_leases(dns_logs, ip_to_lease_map)
                
                if dns_logs:
                    # Perform batch activity analysis
                    activity_results = analyze_batch_device_activity(
                        dns_logs, ip_addresses, self.activity_analyzer
                    )
                    
                    # Update leases with activity analysis
                    for ip_address, lease in ip_to_lease_map.items():
                        activity_data = activity_results.get(ip_address, {})

                        if activity_data.get("status") == "error":
                            lease["activity_status"] = "error"
                            lease["activity_summary"] = activity_data.get(
                                "analysis_summary", "Activity analysis failed"
                            )
                            lease["activity_score"] = None
                            lease["is_actively_used"] = None
                            lease["is_stale"] = None
                            lease["last_seen"] = None
                            lease["minutes_since_seen"] = None
                            lease["activity_evidence"] = None
                            lease["score_breakdown"] = None
                            continue

                        analysis_status = activity_data.get("status")
                        if analysis_status in ("no_data", "insufficient_evidence") or not activity_data.get("total_queries", 0):
                            lease["activity_status"] = (
                                analysis_status
                                if analysis_status in ("no_data", "insufficient_evidence")
                                else "no_data"
                            )
                            lease["activity_summary"] = activity_data.get(
                                "analysis_summary", "No DNS activity found"
                            )
                            lease["activity_score"] = None
                            lease["is_actively_used"] = None
                            lease["is_stale"] = None
                            lease["last_seen"] = None
                            lease["minutes_since_seen"] = None
                            lease["score_breakdown"] = None
                            lease["activity_evidence"] = activity_data.get(
                                "activity_evidence"
                            )
                            continue
                        
                        lease["activity_score"] = activity_data.get("activity_score", 0)
                        lease["is_actively_used"] = activity_data.get("is_actively_used", False)
                        lease["activity_status"] = "analyzed"
                        lease["activity_evidence"] = activity_data.get(
                            "activity_evidence"
                        )
                        lease["score_breakdown"] = activity_data.get("score_breakdown")
                        lease["activity_summary"] = activity_data.get("analysis_summary", "No analysis")
                        latest_timestamp = _latest_activity_timestamp(
                            dns_logs, ip_address
                        )
                        if latest_timestamp is not None:
                            lease["last_seen"] = latest_timestamp.isoformat()
                            minutes_since_seen = max(
                                0,
                                int(
                                    (
                                        datetime.now(latest_timestamp.tzinfo)
                                        - latest_timestamp
                                    ).total_seconds()
                                    / 60
                                ),
                            )
                            lease["minutes_since_seen"] = minutes_since_seen
                        
                        lease["is_stale"] = (
                            not lease["is_actively_used"]
                            if lease["is_actively_used"] is not None
                            else None
                        )
                    _LOGGER.info(
                        "Smart activity analysis completed for %d devices",
                        len(ip_addresses),
                    )
                else:
                    _LOGGER.warning("No DNS logs available for smart activity analysis")
                    for lease in ip_to_lease_map.values():
                        lease["activity_status"] = "no_data"
                        lease["activity_summary"] = "No DNS activity found"
                        lease["activity_score"] = None
                        lease["is_actively_used"] = None
                        lease["is_stale"] = None
                        lease["activity_evidence"] = None
                        lease["last_seen"] = None
                        lease["minutes_since_seen"] = None
                        lease["score_breakdown"] = None
            else:
                for lease in ip_to_lease_map.values():
                    lease["activity_status"] = "disabled"
                await self._perform_basic_last_seen_tracking(
                    ip_addresses, ip_to_lease_map
                )
        except DNSLogsUnavailableError as err:
            _LOGGER.warning("DNS logs became unavailable during processing: %s", err)
            for lease in ip_to_lease_map.values():
                lease["activity_status"] = "unavailable"
                lease["last_seen"] = None
                lease["is_stale"] = None
                lease["minutes_since_seen"] = None
                lease["activity_score"] = None
                lease["is_actively_used"] = None
                lease["score_breakdown"] = None
                lease["activity_summary"] = ""
        except Exception as err:
            _LOGGER.error("Error in DNS log processing: %s", err, exc_info=True)
            for lease in ip_to_lease_map.values():
                lease["activity_status"] = "error"
                lease["last_seen"] = None
                lease["is_stale"] = None
                lease["minutes_since_seen"] = None
                lease["activity_score"] = None
                lease["is_actively_used"] = None
                lease["score_breakdown"] = None
                lease["activity_evidence"] = None
                lease["activity_summary"] = ""

        # Log summary statistics
        if self.smart_activity_enabled:
            analyzed_leases = [
                lease for lease in processed_leases
                if lease.get("activity_status") == "analyzed"
            ]
            if analyzed_leases:
                active_count = sum(
                    1 for lease in analyzed_leases if lease["is_actively_used"]
                )
                avg_score = sum(
                    lease["activity_score"] for lease in analyzed_leases
                ) / len(analyzed_leases)
                _LOGGER.info(
                    "Activity analysis summary: %d/%d devices actively used, average score: %.1f",
                    active_count, len(analyzed_leases), avg_score
                )
            else:
                _LOGGER.info("Activity analysis returned no analyzed device data")
        
        return processed_leases
    
    async def _perform_basic_last_seen_tracking(self, ip_addresses, ip_to_lease_map):
        """Perform basic last seen tracking without smart activity analysis."""
        _LOGGER.info("Performing basic last seen tracking for %d devices", len(ip_addresses))
        
        # Single batch call to get last seen times for all devices
        # Start with a shorter time window (6 hours) for better performance
        last_seen_times = await get_last_seen_for_multiple_ips(
            self.api,
            ip_addresses,
            hours_back=6,
            raise_on_error=True,
            lease_obtained_by_ip={
                ip_address: parse_timestamp(lease.get("lease_obtained"))
                for ip_address, lease in ip_to_lease_map.items()
            },
        )
        
        # Update all leases with the results
        for ip_address, lease in ip_to_lease_map.items():
            last_seen = last_seen_times.get(ip_address)
            
            if last_seen:
                lease["last_seen"] = last_seen
                # Calculate if device is stale based on time threshold
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                    now = datetime.now(last_seen_dt.tzinfo)
                    minutes_since_seen = (now - last_seen_dt).total_seconds() / 60
                    lease["is_stale"] = minutes_since_seen > self.stale_threshold_minutes
                    lease["minutes_since_seen"] = int(minutes_since_seen)
                    lease["activity_summary"] = f"Last seen {int(minutes_since_seen)} minutes ago"
                except Exception as e:
                    _LOGGER.warning("Could not parse last-seen time for DHCP client %s", ip_address)
                    lease["is_stale"] = False
                    lease["minutes_since_seen"] = 0
                    lease["activity_summary"] = "Recent DHCP activity"
            else:
                lease["last_seen"] = None
                lease["is_stale"] = True  # No DNS activity = stale
                lease["minutes_since_seen"] = 9999
                lease["activity_summary"] = "No recent DNS activity"


class TechnitiumDHCPDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Representation of a TechnitiumDNS DHCP device tracker."""

    def __init__(self, coordinator, lease_data, server_name, entry_id, server_device_id):
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._lease_data = lease_data
        self._server_device_id = server_device_id
        self._server_name = server_name
        self._entry_id = entry_id
        self._mac_address = lease_data.get("mac_address", "")
        # Normalize hostname to ensure it's always a string
        self._hostname = normalize_hostname(lease_data.get("hostname", ""))
        
        # Create a friendly name based on hostname first, then MAC
        if self._hostname and self._hostname.strip():
            self._name = self._hostname.replace('.home.internal', '').replace('.local', '')
        elif self._mac_address:
            self._name = f"Device_{self._mac_address.replace(':', '')[-6:]}"
        else:
            self._name = f"Device_{lease_data.get('ip_address', '').replace('.', '_')}"
        
    @property
    def name(self):
        """Return the name of the device tracker."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        # Use normalized MAC address for consistent unique_id format
        if self._mac_address:
            normalized_mac = normalize_mac_address(self._mac_address)
            mac_clean = normalized_mac.replace(':', '').lower()
            return f"{DOMAIN}_device_tracker_{mac_clean}"
        
        # Fallback to IP if no MAC available (shouldn't happen in DHCP context)
        ip_clean = self._lease_data.get('ip_address', '').replace('.', '_')
        return f"{DOMAIN}_device_tracker_ip_{ip_clean}"

    @property
    def source_type(self):
        """Return the source type of the device tracker."""
        return SourceType.ROUTER

    @property
    def is_connected(self):
        """Return whether the current DHCP lease is present, a connectivity proxy."""
        if self.coordinator.data is None:
            return False
            
        for lease in self.coordinator.data:
            if lease.get("mac_address") == self._mac_address:
                return True
        
        return False

    @property
    def ip_address(self):
        """Return the IP address of the device."""
        if not self.coordinator.data:
            return None
            
        for lease in self.coordinator.data:
            if lease.get("mac_address") == self._mac_address:
                return lease.get("ip_address")
        return None

    @property
    def mac_address(self):
        """Return the MAC address of the device."""
        return self._mac_address

    @property
    def hostname(self):
        """Return the hostname of the device."""
        if not self.coordinator.data:
            return self._hostname
            
        for lease in self.coordinator.data:
            if lease.get("mac_address") == self._mac_address:
                return lease.get("hostname", self._hostname)
        return self._hostname

    @property
    def extra_state_attributes(self):
        """Return additional lease attributes."""
        attributes = {"source": "TechnitiumDNS DHCP"}
        if self.coordinator.data:
            for lease in self.coordinator.data:
                if lease.get("mac_address") == self._mac_address:
                    attributes.update({
                        "scope": lease.get("scope", ""),
                        "lease_type": lease.get("type", ""),
                        "address_status": lease.get("address_status"),
                        "lease_expires": lease.get("lease_expires"),
                        "lease_obtained": lease.get("lease_obtained"),
                        "activity_status": lease.get("activity_status", "unknown"),
                        "activity_evidence": lease.get("activity_evidence"),
                    })
                    break
        return attributes

    @property
    def device_info(self):
        """Return device information for this DHCP client."""
        if self._mac_address and self._mac_address.strip():
            normalized_mac = normalize_mac_address(self._mac_address)
            mac_clean = normalized_mac.replace(":", "").lower()
            device_id = f"{DOMAIN}_dhcp_device_{mac_clean}"
        else:
            ip_clean = self._lease_data.get("ip_address", "").replace(".", "_")
            device_id = f"{DOMAIN}_dhcp_device_ip_{ip_clean}"

        manufacturer = "Unknown"
        if self._mac_address:
            mac_prefix = self._mac_address.replace(":", "").upper()[:6]
            oui_map = {
                "00215A": "Apple",
                "3C0754": "Apple",
                "F0F61C": "Apple",
                "DC86D8": "Raspberry Pi Foundation",
                "B827EB": "Raspberry Pi Foundation",
                "E45F01": "Raspberry Pi Foundation",
                "00E04C": "Realtek",
                "EC086B": "Intel",
                "3417EB": "Intel",
                "000C29": "VMware",
                "005056": "VMware",
            }
            manufacturer = oui_map.get(mac_prefix, "Unknown")

        hostname_lower = (self._hostname or "").lower()
        if "raspberry" in hostname_lower or "rpi" in hostname_lower:
            model = "Raspberry Pi"
        elif "iphone" in hostname_lower or "ipad" in hostname_lower:
            model = "iOS Device"
        elif "android" in hostname_lower:
            model = "Android Device"
        elif "windows" in hostname_lower or "pc" in hostname_lower:
            model = "Windows PC"
        elif "mac" in hostname_lower:
            model = "Mac Computer"
        else:
            model = "Network Device"

        return DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self._name,
            manufacturer=manufacturer,
            model=model,
            via_device_id=self._server_device_id,
            configuration_url=None,
        )

    @property
    def available(self):
        """Return whether the coordinator has a current DHCP snapshot."""
        return (
            self.coordinator.data is not None
            and self.coordinator.last_update_success
        )

