"""Support for TechnitiumDNS DHCP device tracking.

This module provides:
1. Device tracker entities that monitor DHCP lease status
2. Diagnostic sensor entities for each tracked device that provide detailed information:
   - IP Address, MAC Address, Hostname
   - Lease Obtained/Expires timestamps
   - Last Seen timestamp (requires DNS logging app)
   - Staleness indicators (requires DNS logging app)

The diagnostic sensors are automatically created for each tracked device and are marked
as diagnostic entities for better organization in Home Assistant.
"""
from datetime import timedelta, datetime
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import EntityCategory
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
    DEFAULT_DHCP_STALE_THRESHOLD
)
from .api import TechnitiumDNSApi
from .utils import should_track_ip

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up TechnitiumDNS DHCP device trackers."""
    _LOGGER.info("Starting TechnitiumDNS DHCP device tracker setup for entry %s", entry.entry_id)
    
    try:
        config_entry = hass.data[DOMAIN][entry.entry_id]
        api = config_entry["api"]
        server_name = config_entry["server_name"]
        
        _LOGGER.debug("Retrieved config entry data: api=%s, server_name=%s", api, server_name)
        
        # Get update interval from options, default to 60 seconds
        update_interval = entry.options.get("dhcp_update_interval", 60)
        
        # Get IP filtering options
        ip_filter_mode = entry.options.get("dhcp_ip_filter_mode", "disabled")
        ip_ranges = entry.options.get("dhcp_ip_ranges", "")
        
        # Get DNS log tracking options
        log_tracking = entry.options.get(CONF_DHCP_LOG_TRACKING, DEFAULT_DHCP_LOG_TRACKING)
        stale_threshold = entry.options.get(CONF_DHCP_STALE_THRESHOLD, DEFAULT_DHCP_STALE_THRESHOLD)
        
        _LOGGER.info("DHCP tracking configuration: interval=%s seconds, filter_mode=%s, ip_ranges=%s, log_tracking=%s, stale_threshold=%s min", 
                    update_interval, ip_filter_mode, ip_ranges, log_tracking, stale_threshold)
        
        coordinator = TechnitiumDHCPCoordinator(
            hass, api, update_interval, ip_filter_mode, ip_ranges, log_tracking, stale_threshold
        )
        _LOGGER.debug("Created TechnitiumDHCPCoordinator: %s", coordinator)
        
        _LOGGER.info("Performing initial DHCP data refresh...")
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial DHCP data refresh completed successfully")

        # Create device trackers for each DHCP lease
        device_trackers = []
        if coordinator.data:
            _LOGGER.info("Processing %d DHCP leases to create device trackers", len(coordinator.data))
            for i, lease in enumerate(coordinator.data):
                _LOGGER.debug("Creating device tracker %d for lease: %s", i+1, lease)
                device_trackers.append(
                    TechnitiumDHCPDeviceTracker(coordinator, lease, server_name, entry.entry_id)
                )
            _LOGGER.info("Created %d device tracker entities", len(device_trackers))
        else:
            _LOGGER.warning("No DHCP lease data available - no device trackers will be created")
        
        _LOGGER.info("Adding %d device tracker entities to Home Assistant", len(device_trackers))
        async_add_entities(device_trackers, True)
        _LOGGER.info("TechnitiumDNS DHCP device tracker setup completed successfully")
        
        # Store coordinator in hass.data for sensor platform to access
        if "coordinators" not in hass.data[DOMAIN][entry.entry_id]:
            hass.data[DOMAIN][entry.entry_id]["coordinators"] = {}
        hass.data[DOMAIN][entry.entry_id]["coordinators"]["dhcp"] = coordinator
        
    except Exception as e:
        _LOGGER.error("Could not initialize TechnitiumDNS DHCP tracking: %s", e, exc_info=True)
        raise ConfigEntryNotReady from e


class TechnitiumDHCPCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TechnitiumDNS DHCP data."""

    def __init__(self, hass, api, update_interval, ip_filter_mode="disabled", ip_ranges="", 
                 log_tracking=False, stale_threshold=60):
        """Initialize."""
        _LOGGER.info("Initializing TechnitiumDHCPCoordinator with interval=%s, filter_mode=%s, log_tracking=%s, stale_threshold=%s", 
                    update_interval, ip_filter_mode, log_tracking, stale_threshold)
        self.api = api
        self.ip_filter_mode = ip_filter_mode
        self.ip_ranges = ip_ranges
        self.log_tracking = log_tracking
        self.stale_threshold_minutes = stale_threshold
        scan_interval = timedelta(seconds=update_interval)
        _LOGGER.debug("Setting coordinator update interval to %s", scan_interval)
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_dhcp", update_interval=scan_interval)
        _LOGGER.info("TechnitiumDHCPCoordinator initialized successfully")

    async def _async_update_data(self):
        """Update data via library."""
        _LOGGER.info("Starting DHCP data update cycle")
        try:
            _LOGGER.debug("Fetching DHCP leases from TechnitiumDNS API using %s", self.api)
            dhcp_response = await self.api.get_dhcp_leases()
            
            _LOGGER.debug("DHCP leases response status: %s", dhcp_response.get("status"))
            _LOGGER.debug("Raw DHCP leases response: %s", dhcp_response)
            
            if dhcp_response.get("status") != "ok":
                _LOGGER.error("DHCP API returned error status: %s", dhcp_response.get("status"))
                raise UpdateFailed(f"DHCP API error: {dhcp_response.get('status')}")
            
            leases = dhcp_response.get("response", {}).get("leases", [])
            _LOGGER.info("Retrieved %d total DHCP leases from API", len(leases))
            
            # Log summary of lease types found
            if leases:
                types_found = set()
                for lease in leases:
                    lease_type = lease.get("type")
                    if lease_type:
                        types_found.add(lease_type)
                _LOGGER.info("Lease types found: %s", sorted(types_found))
            
            # Process and clean up lease data
            processed_leases = []
            filtered_count = 0
            skipped_count = 0
            
            for i, lease in enumerate(leases):
                lease_type = lease.get("type")
                ip_address = lease.get("address")
                mac_address = lease.get("hardwareAddress", "")
                _LOGGER.debug("Processing lease %d: type=%s, address=%s, mac=%s", i+1, lease_type, ip_address, mac_address)
                
                # Filter leases based on the official Technitium DNS API specification
                should_include = False
                skip_reason = ""
                
                # Check if we have basic required data
                if not ip_address:
                    skip_reason = "no IP address"
                elif not mac_address:
                    skip_reason = "no MAC address"
                else:
                    # Accept lease types according to Technitium DNS API docs
                    if lease_type == "Dynamic":
                        should_include = True
                        _LOGGER.debug("Including Dynamic lease")
                    elif lease_type == "Reserved":
                        should_include = True
                        _LOGGER.debug("Including Reserved lease")
                    elif not lease_type:  # Type might be empty/null
                        should_include = True
                        _LOGGER.debug("Including lease with empty type (assuming dynamic)")
                    else:
                        # Log but still include unknown lease types to be flexible
                        should_include = True
                        _LOGGER.debug("Including lease with unknown type '%s'", lease_type)
                
                if should_include:
                    # Apply IP filtering
                    if not should_track_ip(ip_address, self.ip_filter_mode, self.ip_ranges):
                        filtered_count += 1
                        _LOGGER.debug("Filtering out IP %s based on filter mode %s", ip_address, self.ip_filter_mode)
                        continue
                    
                    processed_lease = {
                        "ip_address": ip_address,
                        "mac_address": mac_address.upper(),
                        "hostname": lease.get("hostName", ""),
                        "client_id": lease.get("clientIdentifier", ""),
                        "lease_expires": lease.get("leaseExpires"),
                        "lease_obtained": lease.get("leaseObtained"),
                        "scope": lease.get("scope", ""),
                        "type": lease_type,
                        "last_seen": None,  # Will be populated by DNS log query
                        "is_stale": False,  # Will be calculated based on last_seen
                        "minutes_since_seen": 0,  # Minutes since last DNS activity
                    }
                    processed_leases.append(processed_lease)
                    _LOGGER.debug("Added lease for tracking: IP=%s, MAC=%s, hostname=%s, type=%s", 
                                 ip_address, processed_lease["mac_address"], processed_lease["hostname"], 
                                 lease_type)
                else:
                    _LOGGER.debug("Skipping lease: %s", skip_reason)
                    skipped_count += 1
            
            # Query DNS logs for last seen times if enabled
            processed_leases = await self._get_last_seen_for_devices(processed_leases)
            
            # Log stale device summary if log tracking is enabled
            if self.log_tracking:
                stale_count = sum(1 for lease in processed_leases if lease.get("is_stale", False))
                _LOGGER.info("DNS activity summary: %d devices total, %d are stale (>%d min since last seen)", 
                           len(processed_leases), stale_count, self.stale_threshold_minutes)
            
            _LOGGER.info("DHCP data processing complete: %d active leases, %d filtered, %d skipped", 
                        len(processed_leases), filtered_count, skipped_count)
            
            if filtered_count > 0:
                _LOGGER.info("Filtered out %d devices based on IP filter settings", filtered_count)
            
            _LOGGER.debug("Final processed DHCP leases: %s", processed_leases)
            _LOGGER.info("DHCP update cycle completed successfully with %d trackable devices", len(processed_leases))
            return processed_leases
            
        except Exception as err:
            _LOGGER.error("Error fetching DHCP data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error fetching DHCP data: {err}") from err

    async def _get_last_seen_for_devices(self, processed_leases):
        """Query DNS logs to get last seen times for devices using batch processing."""
        if not self.log_tracking:
            _LOGGER.debug("DNS log tracking disabled, skipping last seen queries")
            return processed_leases
            
        # Extract all IP addresses for batch query
        ip_addresses = []
        ip_to_lease_map = {}
        
        for lease in processed_leases:
            ip_address = lease.get("ip_address")
            if ip_address:
                ip_addresses.append(ip_address)
                # Map IP to lease for easier lookup
                ip_to_lease_map[ip_address] = lease
        
        if not ip_addresses:
            _LOGGER.debug("No IP addresses to query for DNS logs")
            return processed_leases
            
        _LOGGER.info("Performing batch DNS log query for %d devices", len(ip_addresses))
        
        try:
            # First, test if DNS logs API is working at all
            api_test = await self.api.test_dns_logs_api()
            _LOGGER.debug("DNS logs API test result: %s", api_test)
            
            if not api_test.get("available"):
                _LOGGER.warning("DNS logs API is not available: %s", api_test.get("message"))
                _LOGGER.warning("Disabling DNS log tracking for this update cycle")
                # Return early, leaving all devices with default values
                return processed_leases
            
            # Single batch call to get last seen times for all devices
            # Start with a shorter time window (6 hours) for better performance
            last_seen_times = await self.api.get_last_seen_for_multiple_ips(ip_addresses, hours_back=6)
            
            # Update all leases with the results
            for ip_address, lease in ip_to_lease_map.items():
                last_seen = last_seen_times.get(ip_address)
                
                if last_seen:
                    lease["last_seen"] = last_seen
                    _LOGGER.debug("Device %s last seen at %s", ip_address, last_seen)
                    
                    # Calculate if device is stale
                    try:
                        last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                        now = datetime.now(last_seen_dt.tzinfo)
                        minutes_since_seen = (now - last_seen_dt).total_seconds() / 60
                        lease["is_stale"] = minutes_since_seen > self.stale_threshold_minutes
                        lease["minutes_since_seen"] = int(minutes_since_seen)
                        _LOGGER.debug("Device %s: %d minutes since last seen, stale=%s", 
                                    ip_address, int(minutes_since_seen), lease["is_stale"])
                    except Exception as e:
                        _LOGGER.debug("Error parsing last seen time for %s: %s", ip_address, e)
                        lease["is_stale"] = False
                        lease["minutes_since_seen"] = 0
                else:
                    _LOGGER.debug("No DNS log entries found for device %s", ip_address)
                    lease["last_seen"] = None
                    lease["is_stale"] = True  # No DNS activity = stale
                    lease["minutes_since_seen"] = 9999
            
            _LOGGER.info("Batch DNS log processing completed successfully for %d devices", len(ip_addresses))
            
        except Exception as e:
            _LOGGER.error("Error in batch DNS log query: %s", e, exc_info=True)
            # Fall back to marking all devices as not stale on error
            for lease in processed_leases:
                lease["last_seen"] = None
                lease["is_stale"] = False
                lease["minutes_since_seen"] = 0
        
        return processed_leases


class TechnitiumDHCPDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Representation of a TechnitiumDNS DHCP device tracker."""

    def __init__(self, coordinator, lease_data, server_name, entry_id):
        """Initialize the device tracker."""
        _LOGGER.debug("Initializing device tracker for lease: %s", lease_data)
        super().__init__(coordinator)
        self._lease_data = lease_data
        self._server_name = server_name
        self._entry_id = entry_id
        self._mac_address = lease_data.get("mac_address", "")
        self._hostname = lease_data.get("hostname", "")
        
        # Create a friendly name
        if self._hostname:
            self._name = f"{self._hostname}"
        elif self._mac_address:
            self._name = f"Device_{self._mac_address.replace(':', '')[-6:]}"
        else:
            self._name = f"Unknown_Device_{lease_data.get('ip_address', '')}"
        
        _LOGGER.info("Created device tracker '%s' for MAC %s (IP: %s)", 
                    self._name, self._mac_address, lease_data.get('ip_address'))

    @property
    def name(self):
        """Return the name of the device tracker."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower() if self._mac_address else ""
        ip_clean = self._lease_data.get('ip_address', '').replace('.', '_') if not mac_clean else ""
        identifier = mac_clean or ip_clean or "unknown"
        return f"technitiumdns_dhcp_{identifier}"

    @property
    def source_type(self):
        """Return the source type of the device tracker."""
        return SourceType.ROUTER

    @property
    def is_connected(self):
        """Return if the device is connected."""
        # Check if the device still exists in the current coordinator data
        if not self.coordinator.data:
            _LOGGER.debug("Device %s: no coordinator data available - marking as disconnected", self._name)
            return False
            
        for lease in self.coordinator.data:
            if lease.get("mac_address") == self._mac_address:
                # If DNS log tracking is enabled, consider staleness
                if lease.get("is_stale") is not None:
                    is_stale = lease.get("is_stale", False)
                    _LOGGER.debug("Device %s: found lease, is_stale=%s - marking as %s", 
                                self._name, is_stale, "disconnected" if is_stale else "connected")
                    return not is_stale
                else:
                    _LOGGER.debug("Device %s: found active lease (no staleness check) - marking as connected", self._name)
                    return True
        
        _LOGGER.debug("Device %s: no active lease found - marking as disconnected", self._name)
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
        """Return additional attributes."""
        attributes = {
            "source": "TechnitiumDNS DHCP",
        }
        
        # Add minimal lease-specific information
        if self.coordinator.data:
            for lease in self.coordinator.data:
                if lease.get("mac_address") == self._mac_address:
                    attributes.update({
                        "scope": lease.get("scope", ""),
                        "lease_type": lease.get("type", ""),
                    })
                    break
        
        return attributes

    @property
    def device_info(self):
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"dhcp_device_{self._mac_address.replace(':', '').lower()}")},
            name=self._name,
            manufacturer="Unknown",
            model="DHCP Client",
            via_device=(DOMAIN, self._entry_id),
        )

    @property
    def available(self):
        """Return if the device tracker is available."""
        return self.coordinator.last_update_success


class TechnitiumDHCPDeviceDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """Base class for TechnitiumDNS DHCP device diagnostic sensors."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, sensor_type, device_name):
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self._mac_address = mac_address
        self._server_name = server_name
        self._entry_id = entry_id
        self._sensor_type = sensor_type
        self._device_name = device_name
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"dhcp_device_{self._mac_address.replace(':', '').lower()}")},
            name=self._device_name,
            manufacturer="Unknown",
            model="DHCP Client",
            via_device=(DOMAIN, self._entry_id),
        )

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.last_update_success

    def _get_device_data(self):
        """Get the current device data from coordinator."""
        if not self.coordinator.data:
            return None
            
        for lease in self.coordinator.data:
            if lease.get("mac_address") == self._mac_address:
                return lease
        return None


class TechnitiumDHCPDeviceIPSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """IP Address diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the IP address sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "ip_address", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} IP Address"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_ip"

    @property
    def native_value(self):
        """Return the IP address."""
        device_data = self._get_device_data()
        return device_data.get("ip_address") if device_data else None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:ip-network"


class TechnitiumDHCPDeviceMaCSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """MAC Address diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the MAC address sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "mac_address", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} MAC Address"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_mac"

    @property
    def native_value(self):
        """Return the MAC address."""
        return self._mac_address

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:network-outline"


class TechnitiumDHCPDeviceHostnameSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Hostname diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the hostname sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "hostname", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Hostname"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_hostname"

    @property
    def native_value(self):
        """Return the hostname."""
        device_data = self._get_device_data()
        return device_data.get("hostname") if device_data else None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:card-account-details-outline"


class TechnitiumDHCPDeviceLeaseObtainedSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Lease Obtained diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the lease obtained sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "lease_obtained", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Lease Obtained"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_lease_obtained"

    @property
    def native_value(self):
        """Return the lease obtained time."""
        device_data = self._get_device_data()
        return device_data.get("lease_obtained") if device_data else None

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:calendar-clock"


class TechnitiumDHCPDeviceLeaseExpiresSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Lease Expires diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the lease expires sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "lease_expires", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Lease Expires"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_lease_expires"

    @property
    def native_value(self):
        """Return the lease expires time."""
        device_data = self._get_device_data()
        return device_data.get("lease_expires") if device_data else None

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:calendar-remove"


class TechnitiumDHCPDeviceLastSeenSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Last Seen diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the last seen sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "last_seen", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Last Seen"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_last_seen"

    @property
    def native_value(self):
        """Return the last seen time."""
        device_data = self._get_device_data()
        return device_data.get("last_seen") if device_data else None

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:clock-outline"


class TechnitiumDHCPDeviceIsStaleSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Is Stale diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the is stale sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "is_stale", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Is Stale"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_is_stale"

    @property
    def native_value(self):
        """Return whether the device is stale."""
        device_data = self._get_device_data()
        if device_data:
            return "Yes" if device_data.get("is_stale", False) else "No"
        return None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        device_data = self._get_device_data()
        if device_data and device_data.get("is_stale", False):
            return "mdi:wifi-off"
        return "mdi:wifi"


class TechnitiumDHCPDeviceMinutesSinceSeenSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Minutes Since Seen diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the minutes since seen sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "minutes_since_seen", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Minutes Since Seen"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_minutes_since_seen"

    @property
    def native_value(self):
        """Return the minutes since last seen."""
        device_data = self._get_device_data()
        return device_data.get("minutes_since_seen", 0) if device_data else None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return "min"

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:timer-outline"
