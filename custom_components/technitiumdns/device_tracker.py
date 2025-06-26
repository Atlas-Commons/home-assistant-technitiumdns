"""Support for TechnitiumDNS DHCP device tracking."""
from datetime import timedelta
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
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
        
        _LOGGER.info("DHCP tracking configuration: interval=%s seconds, filter_mode=%s, ip_ranges=%s", 
                    update_interval, ip_filter_mode, ip_ranges)
        
        coordinator = TechnitiumDHCPCoordinator(hass, api, update_interval, ip_filter_mode, ip_ranges)
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
        
    except Exception as e:
        _LOGGER.error("Could not initialize TechnitiumDNS DHCP tracking: %s", e, exc_info=True)
        raise ConfigEntryNotReady from e


class TechnitiumDHCPCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TechnitiumDNS DHCP data."""

    def __init__(self, hass, api, update_interval, ip_filter_mode="disabled", ip_ranges=""):
        """Initialize."""
        _LOGGER.info("Initializing TechnitiumDHCPCoordinator with interval=%s, filter_mode=%s", 
                    update_interval, ip_filter_mode)
        self.api = api
        self.ip_filter_mode = ip_filter_mode
        self.ip_ranges = ip_ranges
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
            
            # Process and clean up lease data
            processed_leases = []
            filtered_count = 0
            skipped_count = 0
            
            for i, lease in enumerate(leases):
                lease_type = lease.get("type")
                lease_status = lease.get("addressStatus")
                _LOGGER.debug("Processing lease %d: type=%s, status=%s, address=%s", 
                             i+1, lease_type, lease_status, lease.get("address"))
                
                # Only include active leases
                if lease.get("type") == "Dynamic" and lease.get("addressStatus") == "InUse":
                    ip_address = lease.get("address")
                    
                    # Apply IP filtering
                    if not should_track_ip(ip_address, self.ip_filter_mode, self.ip_ranges):
                        filtered_count += 1
                        _LOGGER.debug("Filtering out IP %s based on filter mode %s", ip_address, self.ip_filter_mode)
                        continue
                    
                    processed_lease = {
                        "ip_address": ip_address,
                        "mac_address": lease.get("hardwareAddress", "").upper(),
                        "hostname": lease.get("hostName", ""),
                        "client_id": lease.get("clientIdentifier", ""),
                        "lease_expires": lease.get("leaseExpires"),
                        "lease_obtained": lease.get("leaseObtained"),
                        "scope": lease.get("scope", ""),
                    }
                    # Use MAC address as unique identifier if available
                    if processed_lease["mac_address"]:
                        processed_leases.append(processed_lease)
                        _LOGGER.debug("Added lease for tracking: IP=%s, MAC=%s, hostname=%s", 
                                     ip_address, processed_lease["mac_address"], processed_lease["hostname"])
                    else:
                        _LOGGER.debug("Skipping lease without MAC address: %s", lease)
                        skipped_count += 1
                else:
                    _LOGGER.debug("Skipping non-active lease: type=%s, status=%s", lease_type, lease_status)
                    skipped_count += 1
            
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
                _LOGGER.debug("Device %s: found active lease - marking as connected", self._name)
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
            "mac_address": self._mac_address,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "source": "TechnitiumDNS DHCP",
        }
        
        # Add lease-specific information if available
        if self.coordinator.data:
            for lease in self.coordinator.data:
                if lease.get("mac_address") == self._mac_address:
                    attributes.update({
                        "client_id": lease.get("client_id", ""),
                        "lease_expires": lease.get("lease_expires", ""),
                        "lease_obtained": lease.get("lease_obtained", ""),
                        "scope": lease.get("scope", ""),
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
