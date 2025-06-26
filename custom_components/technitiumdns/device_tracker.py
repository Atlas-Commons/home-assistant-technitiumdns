"""Support for TechnitiumDNS DHCP device tracking."""
from datetime import timedelta
import logging

from homeassistant.components.device_tracker import DeviceTrackerEntity, SourceType
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
    try:
        config_entry = hass.data[DOMAIN][entry.entry_id]
        api = config_entry["api"]
        server_name = config_entry["server_name"]
        
        # Get update interval from options, default to 60 seconds
        update_interval = entry.options.get("dhcp_update_interval", 60)
        
        # Get IP filtering options
        ip_filter_mode = entry.options.get("dhcp_ip_filter_mode", "disabled")
        ip_ranges = entry.options.get("dhcp_ip_ranges", "")
        
        coordinator = TechnitiumDHCPCoordinator(hass, api, update_interval, ip_filter_mode, ip_ranges)
        await coordinator.async_config_entry_first_refresh()

        # Create device trackers for each DHCP lease
        device_trackers = []
        if coordinator.data:
            for lease in coordinator.data:
                device_trackers.append(
                    TechnitiumDHCPDeviceTracker(coordinator, lease, server_name, entry.entry_id)
                )
        
        async_add_entities(device_trackers, True)
        
    except Exception as e:
        _LOGGER.error("Could not initialize TechnitiumDNS DHCP tracking: %s", e)
        raise ConfigEntryNotReady from e


class TechnitiumDHCPCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TechnitiumDNS DHCP data."""

    def __init__(self, hass, api, update_interval, ip_filter_mode="disabled", ip_ranges=""):
        """Initialize."""
        self.api = api
        self.ip_filter_mode = ip_filter_mode
        self.ip_ranges = ip_ranges
        scan_interval = timedelta(seconds=update_interval)
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_dhcp", update_interval=scan_interval)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            _LOGGER.debug("Fetching DHCP leases from TechnitiumDNS API")
            dhcp_response = await self.api.get_dhcp_leases()
            
            _LOGGER.debug("DHCP leases response: %s", dhcp_response)
            
            leases = dhcp_response.get("response", {}).get("leases", [])
            
            # Process and clean up lease data
            processed_leases = []
            filtered_count = 0
            
            for lease in leases:
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
            
            if filtered_count > 0:
                _LOGGER.info("Filtered out %d devices based on IP filter settings", filtered_count)
            
            _LOGGER.debug("Processed DHCP leases: %s", processed_leases)
            return processed_leases
            
        except Exception as err:
            _LOGGER.error("Error fetching DHCP data: %s", err)
            raise UpdateFailed(f"Error fetching DHCP data: {err}") from err


class TechnitiumDHCPDeviceTracker(CoordinatorEntity, DeviceTrackerEntity):
    """Representation of a TechnitiumDNS DHCP device tracker."""

    def __init__(self, coordinator, lease_data, server_name, entry_id):
        """Initialize the device tracker."""
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
