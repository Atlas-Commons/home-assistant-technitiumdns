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
    api = hass.data[DOMAIN][entry.entry_id]
    coordinator = TechnetiumDNSCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for sensor_type in SENSOR_TYPES:
        sensors.append(TechnetiumDNSSensor(coordinator, sensor_type))

    async_add_entities(sensors, True)


class TechnetiumDNSCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TechnetiumDNS data."""

    def __init__(self, hass, api):
        """Initialize."""
        self.api = api
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            _LOGGER.debug("Fetching data from TechnetiumDNS API")
            last_day_statistics = await self.api.get_statistics()
            _LOGGER.debug("Fetched last day statistics: %s", last_day_statistics)
            top_clients = await self.api.get_top_clients()
            _LOGGER.debug("Fetched top clients: %s", top_clients)
            top_domains = await self.api.get_top_domains()
            _LOGGER.debug("Fetched top domains: %s", top_domains)
            top_blocked_domains = await self.api.get_top_blocked_domains()
            _LOGGER.debug("Fetched top blocked domains: %s", top_blocked_domains)
            update_info = await self.api.check_update()
            _LOGGER.debug("Fetched update info: %s", update_info)

            def format_list(data_list, max_items=5):
                """Format a list of items as a multiline string within the max length."""
                return "\n".join(data_list[:max_items])

            last_day_stats = last_day_statistics.get("response", {}).get("stats", {})
            data = {
                "queries_last_day": last_day_stats.get("totalQueries"),
                "blocked_queries_last_day": last_day_stats.get("totalBlocked"),
                "clients_last_day": last_day_stats.get("totalClients"),
                "update_available": update_info.get("response", {}).get(
                    "updateAvailable"
                ),
                "no_error_last_day": last_day_stats.get("totalNoError"),
                "server_failure_last_day": last_day_stats.get("totalServerFailure"),
                "nx_domain_last_day": last_day_stats.get("totalNxDomain"),
                "refused_last_day": last_day_stats.get("totalRefused"),
                "authoritative_last_day": last_day_stats.get("totalAuthoritative"),
                "recursive_last_day": last_day_stats.get("totalRecursive"),
                "cached_last_day": last_day_stats.get("totalCached"),
                "dropped_last_day": last_day_stats.get("totalDropped"),
                "zones_last_day": last_day_stats.get("zones"),
                "cached_entries_last_day": last_day_stats.get("cachedEntries"),
                "allowed_zones_last_day": last_day_stats.get("allowedZones"),
                "blocked_zones_last_day": last_day_stats.get("blockedZones"),
                "allow_list_zones_last_day": last_day_stats.get("allowListZones"),
                "block_list_zones_last_day": last_day_stats.get("blockListZones"),
                "top_clients_last_day": format_list(
                    [
                        client["name"]
                        for client in top_clients.get("response", {}).get(
                            "topClients", []
                        )
                    ]
                ),
                "top_domains_last_day": format_list(
                    [
                        domain["name"]
                        for domain in top_domains.get("response", {}).get(
                            "topDomains", []
                        )
                    ]
                ),
                "top_blocked_domains_last_day": format_list(
                    [
                        domain["name"]
                        for domain in top_blocked_domains.get("response", {}).get(
                            "topBlockedDomains", []
                        )
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

    def __init__(self, coordinator, sensor_type):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._name = SENSOR_TYPES[sensor_type]["name"]

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
        return f"technetiumdns_{self._sensor_type}"

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        """No polling needed."""
        return False
