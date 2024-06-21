from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)

from .const import DOMAIN, SENSOR_TYPES
from .api import TechnetiumDNSApi

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TechnetiumDNS sensor based on a config entry."""
    config_entry = hass.data[DOMAIN][entry.entry_id]
    api = config_entry["api"]
    server_name = config_entry["server_name"]
    stats_duration = config_entry["stats_duration"]

    coordinator = TechnetiumDNSCoordinator(hass, api, stats_duration)
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for sensor_type in SENSOR_TYPES:
        sensors.append(TechnetiumDNSSensor(coordinator, sensor_type, server_name))

    async_add_entities(sensors, True)


class TechnetiumDNSCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TechnetiumDNS data."""

    def __init__(self, hass, api, stats_duration):
        """Initialize."""
        self.api = api
        self.stats_duration = stats_duration
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            _LOGGER.debug("Fetching data from TechnetiumDNS API")
            technetiumdns_statistics = await self.api.get_statistics(
                self.stats_duration
            )
            _LOGGER.debug(
                "Fetched technetiumdns_statistics: %s", technetiumdns_statistics
            )
            technetiumdns_top_clients = await self.api.get_top_clients(
                self.stats_duration
            )
            _LOGGER.debug(
                "Fetched technetiumdns_top_clients: %s", technetiumdns_top_clients
            )
            technetiumdns_top_domains = await self.api.get_top_domains(
                self.stats_duration
            )
            _LOGGER.debug(
                "Fetched technetiumdns_top_domains: %s", technetiumdns_top_domains
            )
            technetiumdns_top_blocked_domains = await self.api.get_top_blocked_domains(
                self.stats_duration
            )
            _LOGGER.debug(
                "Fetched technetiumdns_top_blocked_domains: %s",
                technetiumdns_top_blocked_domains,
            )
            technetiumdns_update_info = await self.api.check_update()
            _LOGGER.debug(
                "Fetched technetiumdns_update_info: %s", technetiumdns_update_info
            )

            # Add more logging to debug empty response issue
            _LOGGER.debug(
                "technetiumdns_statistics response content: %s",
                technetiumdns_statistics,
            )
            _LOGGER.debug(
                "technetiumdns_top_clients response content: %s",
                technetiumdns_top_clients,
            )
            _LOGGER.debug(
                "technetiumdns_top_domains response content: %s",
                technetiumdns_top_domains,
            )
            _LOGGER.debug(
                "technetiumdns_top_blocked_domains response content: %s",
                technetiumdns_top_blocked_domains,
            )
            _LOGGER.debug(
                "technetiumdns_update_info response content: %s",
                technetiumdns_update_info,
            )

            technetiumdns_stats = technetiumdns_statistics.get("response", {}).get(
                "stats", {}
            )
            data = {
                "queries": technetiumdns_stats.get("totalQueries"),
                "blocked_queries": technetiumdns_stats.get("totalBlocked"),
                "clients": technetiumdns_stats.get("totalClients"),
                "update_available": technetiumdns_update_info.get("response", {}).get(
                    "updateAvailable"
                ),
                "no_error": technetiumdns_stats.get("totalNoError"),
                "server_failure": technetiumdns_stats.get("totalServerFailure"),
                "nx_domain": technetiumdns_stats.get("totalNxDomain"),
                "refused": technetiumdns_stats.get("totalRefused"),
                "authoritative": technetiumdns_stats.get("totalAuthoritative"),
                "recursive": technetiumdns_stats.get("totalRecursive"),
                "cached": technetiumdns_stats.get("totalCached"),
                "dropped": technetiumdns_stats.get("totalDropped"),
                "zones": technetiumdns_stats.get("zones"),
                "cached_entries": technetiumdns_stats.get("cachedEntries"),
                "allowed_zones": technetiumdns_stats.get("allowedZones"),
                "blocked_zones": technetiumdns_stats.get("blockedZones"),
                "allow_list_zones": technetiumdns_stats.get("allowListZones"),
                "block_list_zones": technetiumdns_stats.get("blockListZones"),
                "top_clients": "\n".join(
                    [
                        f"{client['name']} ({client['hits']})"
                        for client in technetiumdns_top_clients.get("response", {}).get(
                            "topClients", []
                        )[:5]
                    ]
                ),
                "top_domains": "\n".join(
                    [
                        f"{domain['name']} ({domain['hits']})"
                        for domain in technetiumdns_top_domains.get("response", {}).get(
                            "topDomains", []
                        )[:5]
                    ]
                ),
                "top_blocked_domains": "\n".join(
                    [
                        f"{domain['name']} ({domain['hits']})"
                        for domain in technetiumdns_top_blocked_domains.get(
                            "response", {}
                        ).get("topBlockedDomains", [])[:5]
                    ]
                ),
            }
            _LOGGER.debug("Data combined: %s", data)
            return data
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}")


class TechnetiumDNSSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TechnetiumDNS sensor."""

    def __init__(self, coordinator, sensor_type, server_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._server_name = server_name
        self._name = (
            f"technetiumdns_{SENSOR_TYPES[sensor_type]['name']} ({server_name})"
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        state_value = self.coordinator.data.get(self._sensor_type)
        _LOGGER.debug("State value for %s: %s", self._sensor_type, state_value)

        # Ensure the state value is within the allowable length
        if isinstance(state_value, str) and len(state_value) > 255:
            _LOGGER.error(
                "State value for %s exceeds 255 characters", self._sensor_type
            )
            return state_value[:255]

        if isinstance(state_value, (list, dict)):
            # Convert complex types to string representation and ensure it is within the limit
            state_value = len(state_value)

        return state_value

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"technetiumdns_{self._sensor_type}_{self._server_name}"

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        """No polling needed."""
        return False
