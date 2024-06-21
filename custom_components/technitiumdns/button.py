import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, AD_BLOCKING_DURATION_OPTIONS
from .api import TechnitiumDNSApi

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up TechnitiumDNS button entities based on a config entry."""
    api = TechnitiumDNSApi(entry.data["api_url"], entry.data["token"])
    server_name = entry.data["server_name"]

    # Ensure durations are sorted as integers
    sorted_durations = sorted(AD_BLOCKING_DURATION_OPTIONS.keys())

    # Define the buttons using the sorted durations
    buttons = [
        TechnitiumDNSButton(
            hass, api, AD_BLOCKING_DURATION_OPTIONS[duration], duration, server_name
        )
        for duration in sorted_durations
    ]

    # Add entities
    async_add_entities(buttons)


class TechnitiumDNSButton(ButtonEntity):
    """Representation of a TechnitiumDNS button."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: TechnitiumDNSApi,
        name: str,
        duration: int,
        server_name: str,
    ):
        """Initialize the button."""
        self._hass = hass
        self._api = api
        self._attr_name = f"{name} ({server_name})"
        self._duration = duration

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self._api.temporary_disable_blocking(self._duration)
            _LOGGER.info(
                f"Ad blocking disabled for {self._duration} minutes on {self._attr_name}"
            )
        except Exception as e:
            _LOGGER.error(f"Failed to disable ad blocking: {e}")
