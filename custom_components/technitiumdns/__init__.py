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
    _LOGGER.info("Setting up TechnitiumDNS integration for entry %s", entry.entry_id)
    hass.data.setdefault(DOMAIN, {})
    api = TechnitiumDNSApi(entry.data["api_url"], entry.data["token"])
    
    # Determine which platforms to load based on options
    platforms = ["sensor", "button", "switch"]
    
    # Add device_tracker if DHCP tracking is enabled
    dhcp_enabled = entry.options.get("enable_dhcp_tracking", False)
    _LOGGER.info("DHCP tracking enabled: %s", dhcp_enabled)
    if dhcp_enabled:
        platforms.append("device_tracker")
        _LOGGER.info("Added device_tracker platform to load list")
    
    _LOGGER.debug("Options: %s", entry.options)
    _LOGGER.info("Platforms to load: %s", platforms)
    
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "server_name": entry.data["server_name"],
        "stats_duration": entry.data["stats_duration"],
        "loaded_platforms": platforms,  # Track which platforms were actually loaded
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Technitium",
        name=entry.data["server_name"],
        model="DNS Server",
    )

    # Forward the setup to the appropriate platforms
    _LOGGER.info("Starting platform setup for: %s", platforms)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    _LOGGER.info("All platforms setup completed successfully")
    
    # Set up options flow listener to handle configuration changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    _LOGGER.info("TechnitiumDNS integration setup completed for entry %s", entry.entry_id)
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        # Get the platforms that were actually loaded during setup
        entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
        platforms = entry_data.get("loaded_platforms", ["sensor", "button", "switch"])
        
        # Only unload platforms that were actually loaded
        if platforms:
            await hass.config_entries.async_unload_platforms(entry, platforms)
        
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
        
    except Exception as e:
        _LOGGER.error("Error unloading TechnitiumDNS integration: %s", e)
        # Still try to clean up data even if platform unload failed
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
