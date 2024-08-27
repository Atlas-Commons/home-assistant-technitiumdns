import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, AD_BLOCKING_DURATION_OPTIONS
from .api import TechnitiumDNSApi

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up TechnitiumDNS button entities based on a config entry."""
    config_entry = hass.data[DOMAIN][entry.entry_id]
    api = config_entry["api"]
    server_name = config_entry["server_name"]

    # Ensure durations are sorted as integers
    sorted_durations = sorted(AD_BLOCKING_DURATION_OPTIONS.keys())

    # Define the buttons using the sorted durations
    buttons = [
        TechnitiumDNSButton(
            api, AD_BLOCKING_DURATION_OPTIONS[duration], duration, server_name, entry.entry_id
        )
        for duration in sorted_durations
    ]

    # Add entities
    async_add_entities(buttons)

class TechnitiumDNSButton(ButtonEntity):
    """Representation of a TechnitiumDNS button."""

    def __init__(self, api: TechnitiumDNSApi, name: str,  duration: int, server_name: str, entry_id: str):
        """Initialize the switch."""
        self._api = api
        self._attr_name = f"{name} ({server_name})"
        self._duration = duration
        self._is_on = False
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_{duration}"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self._api.temporary_disable_blocking(self._duration)
            _LOGGER.info(f"Ad blocking disabled for {self._duration} minutes on {self._attr_name}")
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
