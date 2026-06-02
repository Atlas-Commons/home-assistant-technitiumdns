"""TechnitiumDNS button entities."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from .const import AD_BLOCKING_DURATION_OPTIONS, DOMAIN, KEY_BLOCKING_DISABLED_UNTIL
from .utils import server_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up TechnitiumDNS button entities based on a config entry."""
    config_entry = hass.data[DOMAIN][entry.entry_id]
    api = config_entry["api"]
    server_name = config_entry["server_name"]

    sorted_durations = sorted(AD_BLOCKING_DURATION_OPTIONS.keys())

    buttons = [
        TechnitiumDNSButton(
            api,
            AD_BLOCKING_DURATION_OPTIONS[duration],
            duration,
            server_name,
            entry.entry_id,
            hass,
        )
        for duration in sorted_durations
    ]

    dhcp_enabled = entry.options.get("enable_dhcp_tracking", False)
    if dhcp_enabled:
        buttons.append(TechnitiumDNSCleanupButton(server_name, entry.entry_id, hass))

    async_add_entities(buttons)


class TechnitiumDNSButton(ButtonEntity):
    """Representation of a TechnitiumDNS button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api,
        name: str,
        duration: int,
        server_name: str,
        entry_id: str,
        hass,
    ):
        """Initialize the button."""
        self._api = api
        self._hass = hass
        self._entry_id = entry_id
        self._server_name = server_name
        self._attr_name = name
        self._duration = duration
        self._attr_unique_id = f"{entry_id}_{duration}"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            result = await self._api.settings.temporary_disable_blocking(
                minutes=self._duration
            )
            until = result.temporary_disable_blocking_till
            entry_data = self._hass.data.get(DOMAIN, {}).get(self._entry_id)
            if entry_data is not None:
                entry_data[KEY_BLOCKING_DISABLED_UNTIL] = until

            _LOGGER.info(
                "Ad blocking disabled for %d minutes on %s (until %s)",
                self._duration,
                self._attr_name,
                until,
            )

            self._hass.bus.async_fire(
                f"{DOMAIN}_blocking_changed",
                {"config_entry_id": self._entry_id},
            )
        except Exception as err:
            _LOGGER.error("Failed to disable ad blocking: %s", err)

    @property
    def device_info(self):
        """Return device information for this entity."""
        return server_device_info(self._entry_id, self._server_name)


class TechnitiumDNSCleanupButton(ButtonEntity):
    """Button to cleanup orphaned DHCP device entities."""

    _attr_has_entity_name = True

    def __init__(self, server_name: str, entry_id: str, hass):
        """Initialize the cleanup button."""
        self._server_name = server_name
        self._attr_name = "Cleanup Devices"
        self._entry_id = entry_id
        self._hass = hass
        self._attr_unique_id = f"{entry_id}_cleanup_devices"
        self._attr_icon = "mdi:delete-sweep"

    async def async_press(self) -> None:
        """Handle the button press to cleanup orphaned entities."""
        try:
            await self._hass.services.async_call(
                DOMAIN,
                "cleanup_devices",
                {"config_entry_id": self._entry_id},
            )
            _LOGGER.info("Manual device cleanup triggered for %s", self._attr_name)
        except Exception as err:
            _LOGGER.error("Failed to trigger device cleanup: %s", err)

    @property
    def device_info(self):
        """Return device information for this entity."""
        return server_device_info(self._entry_id, self._server_name)
