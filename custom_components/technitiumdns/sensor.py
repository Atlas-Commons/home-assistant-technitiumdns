from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, SENSOR_TYPES
from .api import TechnitiumDNSApi

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TechnitiumDNS sensor based on a config entry."""
    try:
        config_entry = hass.data[DOMAIN][entry.entry_id]
        api = config_entry["api"]
        server_name = config_entry["server_name"]
        stats_duration = config_entry["stats_duration"]

        coordinator = TechnitiumDNSCoordinator(hass, api, stats_duration)
        await coordinator.async_config_entry_first_refresh()

        sensors = [
            TechnitiumDNSSensor(coordinator, sensor_type, server_name, entry.entry_id)
            for sensor_type in SENSOR_TYPES
        ]
        async_add_entities(sensors, True)
    except Exception as e:
        _LOGGER.error("Could not initialize TechnitiumDNS: %s", e)
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
            Technitiumdns_top_clients = await self.api.get_top_clients(self.stats_duration)
            Technitiumdns_top_domains = await self.api.get_top_domains(self.stats_duration)
            Technitiumdns_top_blocked_domains = await self.api.get_top_blocked_domains(self.stats_duration)
            Technitiumdns_update_info = await self.api.check_update()

            # Add more logging to debug empty response issue
            _LOGGER.debug("Technitiumdns_statistics response content: %s", Technitiumdns_statistics)
            _LOGGER.debug("Technitiumdns_top_clients response content: %s", Technitiumdns_top_clients)
            _LOGGER.debug("Technitiumdns_top_domains response content: %s", Technitiumdns_top_domains)
            _LOGGER.debug("Technitiumdns_top_blocked_domains response content: %s", Technitiumdns_top_blocked_domains)
            _LOGGER.debug("Technitiumdns_update_info response content: %s", Technitiumdns_update_info)

            Technitiumdns_stats = Technitiumdns_statistics.get("response", {}).get("stats", {})
            data = {
                "queries": Technitiumdns_stats.get("totalQueries"),
                "blocked_queries": Technitiumdns_stats.get("totalBlocked"),
                "clients": Technitiumdns_stats.get("totalClients"),
                "update_available": Technitiumdns_update_info.get("response", {}).get("updateAvailable"),
                "no_error": Technitiumdns_stats.get("totalNoError"),
                "server_failure": Technitiumdns_stats.get("totalServerFailure"),
                "nx_domain": Technitiumdns_stats.get("totalNxDomain"),
                "refused": Technitiumdns_stats.get("totalRefused"),
                "authoritative": Technitiumdns_stats.get("totalAuthoritative"),
                "recursive": Technitiumdns_stats.get("totalRecursive"),
                "cached": Technitiumdns_stats.get("totalCached"),
                "dropped": Technitiumdns_stats.get("totalDropped"),
                "zones": Technitiumdns_stats.get("zones"),
                "cached_entries": Technitiumdns_stats.get("cachedEntries"),
                "allowed_zones": Technitiumdns_stats.get("allowedZones"),
                "blocked_zones": Technitiumdns_stats.get("blockedZones"),
                "allow_list_zones": Technitiumdns_stats.get("allowListZones"),
                "block_list_zones": Technitiumdns_stats.get("blockListZones"),
                "top_clients": "\n".join(
                    [f"{client['name']} ({client['hits']})" for client in Technitiumdns_top_clients.get("response", {}).get("topClients", [])[:5]]
                ),
                "top_domains": "\n".join(
                    [f"{domain['name']} ({domain['hits']})" for domain in Technitiumdns_top_domains.get("response", {}).get("topDomains", [])[:5]]
                ),
                "top_blocked_domains": "\n".join(
                    [f"{domain['name']} ({domain['hits']})" for domain in Technitiumdns_top_blocked_domains.get("response", {}).get("topBlockedDomains", [])[:5]]
                ),
            }
            _LOGGER.debug("Data combined: %s", data)
            return data
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}")

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
            # Convert complex types to string representation and ensure it is within the limit
            state_value = len(state_value)

        return state_value

    @property
    def extra_state_attributes(self):
        """Return additional attributes in a table-friendly format based on sensor type."""
        attributes = {}

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
