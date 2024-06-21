"""Support for TechnetiumDNS sensors."""

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
            statistics = await self.api.get_statistics(self.stats_duration)
            _LOGGER.debug("Fetched statistics: %s", statistics)
            top_clients = await self.api.get_top_clients(self.stats_duration)
            _LOGGER.debug("Fetched top clients: %s", top_clients)
            top_domains = await self.api.get_top_domains(self.stats_duration)
            _LOGGER.debug("Fetched top domains: %s", top_domains)
            top_blocked_domains = await self.api.get_top_blocked_domains(
                self.stats_duration
            )
            _LOGGER.debug("Fetched top blocked domains: %s", top_blocked_domains)
            update_info = await self.api.check_update()
            _LOGGER.debug("Fetched update info: %s", update_info)

            stats = statistics.get("response", {}).get("stats", {})
            data = {
                "queries": stats.get("totalQueries"),
                "blocked_queries": stats.get("totalBlocked"),
                "clients": stats.get("totalClients"),
                "update_available": update_info.get("response", {}).get(
                    "updateAvailable"
                ),
                "no_error": stats.get("totalNoError"),
                "server_failure": stats.get("totalServerFailure"),
                "nx_domain": stats.get("totalNxDomain"),
                "refused": stats.get("totalRefused"),
                "authoritative": stats.get("totalAuthoritative"),
                "recursive": stats.get("totalRecursive"),
                "cached": stats.get("totalCached"),
                "dropped": stats.get("totalDropped"),
                "zones": stats.get("zones"),
                "cached_entries": stats.get("cachedEntries"),
                "allowed_zones": stats.get("allowedZones"),
                "blocked_zones": stats.get("blockedZones"),
                "allow_list_zones": stats.get("allowListZones"),
                "block_list_zones": stats.get("blockListZones"),
                "top_clients": "\n".join(
                    [
                        f"{client['name']} ({client['hits']})"
                        for client in top_clients.get("response", {}).get(
                            "topClients", []
                        )[:5]
                    ]
                ),
                "top_domains": "\n".join(
                    [
                        f"{domain['name']} ({domain['hits']})"
                        for domain in top_domains.get("response", {}).get(
                            "topDomains", []
                        )[:5]
                    ]
                ),
                "top_blocked_domains": "\n".join(
                    [
                        f"{domain['name']} ({domain['hits']})"
                        for domain in top_blocked_domains.get("response", {}).get(
                            "topBlockedDomains", []
                        )[:5]
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
        self._name = f"{SENSOR_TYPES[sensor_type]['name']} ({server_name})"

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
