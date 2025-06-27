from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, SENSOR_TYPES
from .api import TechnitiumDNSApi

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up TechnitiumDNS sensors: main DNS statistics and device diagnostic sensors."""
    try:
        _LOGGER.info("Setting up TechnitiumDNS sensor platform for entry %s", entry.entry_id)
        config_entry = hass.data[DOMAIN][entry.entry_id]
        api = config_entry["api"]
        server_name = config_entry["server_name"]
        stats_duration = config_entry["stats_duration"]

        # Create main DNS statistics coordinator and sensors
        coordinator = TechnitiumDNSCoordinator(hass, api, stats_duration)
        await coordinator.async_config_entry_first_refresh()

        sensors = [
            TechnitiumDNSSensor(coordinator, sensor_type, server_name, entry.entry_id)
            for sensor_type in SENSOR_TYPES
        ]
        _LOGGER.info("Created %d main DNS statistics sensors", len(sensors))
        
        # Create device diagnostic sensors if DHCP coordinator is available
        dhcp_coordinator = None
        coordinators = hass.data[DOMAIN][entry.entry_id].get("coordinators", {})
        if "dhcp" in coordinators:
            dhcp_coordinator = coordinators["dhcp"]
            _LOGGER.info("DHCP coordinator found, creating device diagnostic sensors")
            
            # Create diagnostic sensors for each tracked device
            if dhcp_coordinator.data:
                for lease in dhcp_coordinator.data:
                    mac_address = lease.get("mac_address", "")
                    hostname = lease.get("hostname", "")
                    ip_address = lease.get("ip_address", "")
                    
                    # Create a device name consistent with device tracker
                    if hostname:
                        device_name = hostname
                    elif mac_address:
                        device_name = f"Device_{mac_address.replace(':', '')[-6:]}"
                    else:
                        device_name = f"Unknown_Device_{ip_address}"
                    
                    _LOGGER.debug("Creating diagnostic sensors for device: %s (MAC: %s)", device_name, mac_address)
                    
                    diagnostic_sensors = [
                        TechnitiumDHCPDeviceIPSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceMaCSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceHostnameSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceLeaseObtainedSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceLeaseExpiresSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceLastSeenSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceIsStaleSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceMinutesSinceSeenSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceActivityScoreSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceIsActivelyUsedSensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                        TechnitiumDHCPDeviceActivitySummarySensor(dhcp_coordinator, mac_address, server_name, entry.entry_id, device_name),
                    ]
                    
                    sensors.extend(diagnostic_sensors)
                    _LOGGER.debug("Created %d diagnostic sensors for device %s", len(diagnostic_sensors), device_name)
                
                _LOGGER.info("Created %d device diagnostic sensors for %d devices", 
                           len(sensors) - len(SENSOR_TYPES), len(dhcp_coordinator.data))
        else:
            _LOGGER.info("DHCP coordinator not available yet, only creating main DNS sensors")
        
        _LOGGER.info("Total sensors to register: %d", len(sensors))
        async_add_entities(sensors, True)
        _LOGGER.info("All sensors registered successfully with Home Assistant")
        
    except Exception as e:
        _LOGGER.error("Could not initialize TechnitiumDNS sensor platform: %s", e, exc_info=True)
        raise ConfigEntryNotReady from e

class TechnitiumDNSCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TechnitiumDNS data."""

    def __init__(self, hass, api, stats_duration):
        """Initialize."""
        self.api = api
        self.stats_duration = stats_duration
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            _LOGGER.debug("Fetching data from TechnitiumDNS API")
            Technitiumdns_statistics = await self.api.get_statistics(self.stats_duration)
            Technitiumdns_update_info = await self.api.check_update()

            # Add logging to debug response content
            _LOGGER.debug("Technitiumdns_statistics response content: %s", Technitiumdns_statistics)
            _LOGGER.debug("Technitiumdns_update_info response content: %s", Technitiumdns_update_info)

            Technitiumdns_stats = Technitiumdns_statistics.get("response", {}).get("stats", {})
            data = {
                "queries": Technitiumdns_stats.get("totalQueries", 0),
                "blocked_queries": Technitiumdns_stats.get("totalBlocked", 0),
                "clients": Technitiumdns_stats.get("totalClients", 0),
                "update_available": Technitiumdns_update_info.get("response", {}).get("updateAvailable", False),
                "no_error": Technitiumdns_stats.get("totalNoError", 0),
                "server_failure": Technitiumdns_stats.get("totalServerFailure", 0),
                "nx_domain": Technitiumdns_stats.get("totalNxDomain", 0),
                "refused": Technitiumdns_stats.get("totalRefused", 0),
                "authoritative": Technitiumdns_stats.get("totalAuthoritative", 0),
                "recursive": Technitiumdns_stats.get("totalRecursive", 0),
                "cached": Technitiumdns_stats.get("totalCached", 0),
                "dropped": Technitiumdns_stats.get("totalDropped", 0),
                "zones": Technitiumdns_stats.get("zones", 0),
                "cached_entries": Technitiumdns_stats.get("cachedEntries", 0),
                "allowed_zones": Technitiumdns_stats.get("allowedZones", 0),
                "blocked_zones": Technitiumdns_stats.get("blockedZones", 0),
                "allow_list_zones": Technitiumdns_stats.get("allowListZones", 0),
                "block_list_zones": Technitiumdns_stats.get("blockListZones", 0),
                "top_clients": [
                    {"name": client.get("name", "Unknown"), "hits": client.get("hits", 0)}
                    for client in Technitiumdns_statistics.get("response", {}).get("topClients", [])[:5]
                ],
                "top_domains": [
                    {"name": domain.get("name", "Unknown"), "hits": domain.get("hits", 0)}
                    for domain in Technitiumdns_statistics.get("response", {}).get("topDomains", [])[:5]
                ],
                "top_blocked_domains": [
                    {"name": domain.get("name", "Unknown"), "hits": domain.get("hits", 0)}
                    for domain in Technitiumdns_statistics.get("response", {}).get("topBlockedDomains", [])[:5]
                ],
            }
            _LOGGER.debug("Data combined: %s", data)
            return data
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}") from err

class TechnitiumDNSSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TechnitiumDNS sensor."""

    def __init__(self, coordinator, sensor_type, server_name, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._server_name = server_name
        self._entry_id = entry_id
        self._name = f"Technitiumdns_{SENSOR_TYPES[sensor_type]['name']} ({server_name})"
        self._state_class = SENSOR_TYPES[sensor_type].get('state_class', 'measurement')

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return self._state_class

    @property
    def state(self):
        """Return the state of the sensor."""
        state_value = self.coordinator.data.get(self._sensor_type)
        _LOGGER.debug("State value for %s: %s", self._sensor_type, state_value)

        # Ensure the state value is within the allowable length
        if isinstance(state_value, str) and len(state_value) > 255:
            _LOGGER.error("State value for %s exceeds 255 characters", self._sensor_type)
            return state_value[:255]

        if isinstance(state_value, (list, dict)):
            state_value = len(state_value)  # Return length if complex

        return state_value

    @property
    def extra_state_attributes(self):
        """Return additional attributes in a table-friendly format based on sensor type."""
        attributes = {
            "queries": self.coordinator.data.get("queries", 0),
            "blocked_queries": self.coordinator.data.get("blocked_queries", 0),
            "clients": self.coordinator.data.get("clients", 0),
            "update_available": self.coordinator.data.get("update_available", False),
        }

        if self._sensor_type == 'top_clients':
            attributes["top_clients_table"] = [
                {"Client": client.get('name', 'Unknown'), "Hits": client.get('hits', 0)}
                for client in self.coordinator.data.get("top_clients", [])
            ]
        elif self._sensor_type == 'top_domains':
            attributes["top_domains_table"] = [
                {"Domain": domain.get('name', 'Unknown'), "Hits": domain.get('hits', 0)}
                for domain in self.coordinator.data.get("top_domains", [])
            ]
        elif self._sensor_type == 'top_blocked_domains':
            attributes["top_blocked_domains_table"] = [
                {"Blocked Domain": domain.get('name', 'Unknown'), "Hits": domain.get('hits', 0)}
                for domain in self.coordinator.data.get("top_blocked_domains", [])
            ]

        return attributes

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"Technitiumdns_{self._sensor_type}_{self._server_name}"

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._server_name,
            manufacturer="Technitium",
            model="DNS Server",
        )

# Diagnostic sensor base class for DHCP devices
class TechnitiumDHCPDeviceDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """Base class for DHCP device diagnostic sensors."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, sensor_type, device_name):
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self._mac_address = mac_address.upper()
        self._server_name = server_name
        self._entry_id = entry_id
        self._sensor_type = sensor_type
        self._device_name = device_name

    def _get_device_data(self):
        """Get device data from coordinator."""
        if not self.coordinator.data:
            return None
        
        for device in self.coordinator.data:
            if device.get("mac_address", "").upper() == self._mac_address:
                return device
        return None

    @property
    def device_info(self):
        """Return device information for this entity."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return DeviceInfo(
            identifiers={(DOMAIN, f"dhcp_device_{mac_clean}")},
            name=self._device_name,
            manufacturer="Network Device",
            model="DHCP Client",
            via_device=(DOMAIN, self._entry_id),
        )

    @property
    def entity_category(self):
        """Return the entity category."""
        return EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.last_update_success and self._get_device_data() is not None

    @property
    def should_poll(self):
        """No polling needed."""
        return False


class TechnitiumDHCPDeviceIPSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """IP Address diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the IP sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "ip_address", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} IP Address"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_ip_address"

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
        """Initialize the MAC sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "mac_address", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} MAC Address"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_mac_address"

    @property
    def native_value(self):
        """Return the MAC address."""
        device_data = self._get_device_data()
        return device_data.get("mac_address") if device_data else None

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
        hostname = device_data.get("hostname") if device_data else None
        return hostname if hostname else "Unknown"

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:dns"


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
        return "timestamp"

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
        return "timestamp"

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
        return "timestamp"

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:eye-outline"


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
            return "mdi:account-off"
        return "mdi:account-check"


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


class TechnitiumDHCPDeviceActivityScoreSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Activity Score diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the activity score sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "activity_score", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Activity Score"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_activity_score"

    @property
    def native_value(self):
        """Return the activity score."""
        device_data = self._get_device_data()
        return device_data.get("activity_score", 0) if device_data else None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return "points"

    @property
    def icon(self):
        """Return the icon for this sensor."""
        device_data = self._get_device_data()
        if device_data:
            score = device_data.get("activity_score", 0)
            if score >= 75:
                return "mdi:account-check"
            elif score >= 50:
                return "mdi:account"
            elif score >= 25:
                return "mdi:account-outline"
            else:
                return "mdi:account-off"
        return "mdi:account-question"

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        device_data = self._get_device_data()
        if device_data and device_data.get("activity_score", 0) > 0:
            return {
                "activity_summary": device_data.get("activity_summary", ""),
                "is_actively_used": device_data.get("is_actively_used", False),
                "score_breakdown": device_data.get("score_breakdown", {}),
                "threshold": getattr(self.coordinator, 'activity_analyzer', {}).get('score_threshold', "N/A") if hasattr(self.coordinator, 'activity_analyzer') else "N/A"
            }
        return {}


class TechnitiumDHCPDeviceIsActivelyUsedSensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Is Actively Used diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the actively used sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "is_actively_used", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Is Actively Used"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_is_actively_used"

    @property
    def native_value(self):
        """Return whether the device is actively used."""
        device_data = self._get_device_data()
        if device_data:
            return "Yes" if device_data.get("is_actively_used", False) else "No"
        return None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        device_data = self._get_device_data()
        if device_data and device_data.get("is_actively_used", False):
            return "mdi:account-check"
        return "mdi:account-off"


class TechnitiumDHCPDeviceActivitySummarySensor(TechnitiumDHCPDeviceDiagnosticSensor):
    """Activity Summary diagnostic sensor for a DHCP device."""

    def __init__(self, coordinator, mac_address, server_name, entry_id, device_name):
        """Initialize the activity summary sensor."""
        super().__init__(coordinator, mac_address, server_name, entry_id, "activity_summary", device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_name} Activity Summary"

    @property
    def unique_id(self):
        """Return a unique ID."""
        mac_clean = self._mac_address.replace(':', '').lower()
        return f"technitiumdns_dhcp_{mac_clean}_activity_summary"

    @property
    def native_value(self):
        """Return the activity summary."""
        device_data = self._get_device_data()
        return device_data.get("activity_summary", "No activity data") if device_data else None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:text-box-outline"
