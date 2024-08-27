import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, AD_BLOCKING_SWITCH
from .api import TechnitiumDNSApi

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up TechnitiumDNS switch entities based on a config entry."""
    config_entry = hass.data[DOMAIN][entry.entry_id]
    api = config_entry["api"]
    server_name = config_entry["server_name"]

    # Define the switch
    switches = [TechnitiumDNSSwitch(api, AD_BLOCKING_SWITCH, server_name, entry.entry_id)]

    # Add entities
    async_add_entities(switches)

class TechnitiumDNSSwitch(SwitchEntity):
    """Representation of a TechnitiumDNS switch."""

    def __init__(self, api: TechnitiumDNSApi, name: str, server_name: str, entry_id: str):
        """Initialize the switch."""
        self._api = api
        self._attr_name = f"{name} ({server_name})"
        self._is_on = False
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_{name}"

    @property
    def name(self):
        """Return the name of the switch."""
        return self._attr_name

    @property
    def is_on(self):
        """Return the state of the switch."""
        return self._is_on

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await self._fetch_state()

    async def _fetch_state(self):
        """Fetch the current state of ad blocking."""
        try:
            response = await self._api.get_dns_settings()
            self._is_on = response["response"].get("enableBlocking", False)
            _LOGGER.info(f"Fetched ad blocking state: {self._is_on} for {self._attr_name}")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to fetch ad blocking state: {e}")

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        try:
            await self._api.set_ad_blocking(True)
            self._is_on = True
            _LOGGER.info(f"Ad blocking enabled on {self._attr_name}")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to enable ad blocking: {e}")

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        try:
            await self._api.set_ad_blocking(False)
            self._is_on = False
            _LOGGER.info(f"Ad blocking disabled on {self._attr_name}")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to disable ad blocking: {e}")

    @property
    def device_info(self):
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._attr_name,
            manufacturer="Technitium",
            model="DNS Server",
        )
