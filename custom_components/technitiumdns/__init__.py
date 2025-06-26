"""TechnitiumDNS integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .api import TechnitiumDNSApi

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TechnitiumDNS from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    api = TechnitiumDNSApi(entry.data["api_url"], entry.data["token"])
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "server_name": entry.data["server_name"],
        "stats_duration": entry.data["stats_duration"],
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Technitium",
        name=entry.data["server_name"],
        model="DNS Server",
    )

    # Determine which platforms to load based on options
    platforms = ["sensor", "button", "switch"]
    
    # Add device_tracker if DHCP tracking is enabled
    if entry.options.get("enable_dhcp_tracking", False):
        platforms.append("device_tracker")

    # Forward the setup to the appropriate platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    
    # Set up options flow listener to handle configuration changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms = ["sensor", "button", "switch"]
    
    # Add device_tracker if DHCP tracking was enabled
    if entry.options.get("enable_dhcp_tracking", False):
        platforms.append("device_tracker")
        
    await hass.config_entries.async_unload_platforms(entry, platforms)
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
