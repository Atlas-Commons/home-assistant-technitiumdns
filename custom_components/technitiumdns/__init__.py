"""TechnitiumDNS integration."""

import logging
import voluptuous as vol

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .api import TechnitiumDNSApi

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TechnitiumDNS from a config entry."""
    _LOGGER.info("Setting up TechnitiumDNS integration for entry %s", entry.entry_id)
    hass.data.setdefault(DOMAIN, {})
    api = TechnitiumDNSApi(entry.data["api_url"], entry.data["token"])
    
    # Determine which platforms to load based on options
    platforms = ["button", "switch"]
    
    # Add device_tracker if DHCP tracking is enabled (load before sensor)
    dhcp_enabled = entry.options.get("enable_dhcp_tracking", False)
    _LOGGER.info("DHCP tracking enabled: %s", dhcp_enabled)
    if dhcp_enabled:
        platforms.append("device_tracker")
        _LOGGER.info("Added device_tracker platform to load list")
    
    # Always add sensor platform last so it can access other coordinators
    platforms.append("sensor")
    
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

    # Forward the setup to the appropriate platforms in order
    _LOGGER.info("Starting platform setup for: %s", platforms)
    
    # Set up all platforms (order is preserved: device_tracker before sensor)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    
    _LOGGER.info("All platforms setup completed successfully")
    
    # Set up options flow listener to handle configuration changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    # Register cleanup service for manual entity cleanup
    await async_register_services(hass)
    
    _LOGGER.info("TechnitiumDNS integration setup completed for entry %s", entry.entry_id)
    return True

async def async_register_services(hass: HomeAssistant):
    """Register integration services."""
    if hass.services.has_service(DOMAIN, "cleanup_devices"):
        return  # Service already registered
    
    async def handle_cleanup_devices(call):
        """Handle cleanup_devices service call."""
        config_entry_id = call.data.get("config_entry_id")
        
        if config_entry_id:
            # Clean up specific entry
            entry_data = hass.data.get(DOMAIN, {}).get(config_entry_id)
            if entry_data:
                dhcp_coordinator = entry_data.get("coordinators", {}).get("dhcp")
                if dhcp_coordinator and dhcp_coordinator.data:
                    current_macs = {lease.get("mac_address") for lease in dhcp_coordinator.data if lease.get("mac_address")}
                    await async_cleanup_orphaned_entities(hass, config_entry_id, current_macs)
                    _LOGGER.info("Manual cleanup completed for entry %s", config_entry_id)
                else:
                    _LOGGER.warning("No DHCP coordinator found for entry %s", config_entry_id)
            else:
                _LOGGER.error("Config entry %s not found", config_entry_id)
        else:
            # Clean up all entries
            for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
                dhcp_coordinator = entry_data.get("coordinators", {}).get("dhcp")
                if dhcp_coordinator and dhcp_coordinator.data:
                    current_macs = {lease.get("mac_address") for lease in dhcp_coordinator.data if lease.get("mac_address")}
                    await async_cleanup_orphaned_entities(hass, entry_id, current_macs)
                    _LOGGER.info("Manual cleanup completed for entry %s", entry_id)
    
    hass.services.async_register(
        DOMAIN,
        "cleanup_devices", 
        handle_cleanup_devices,
        schema=vol.Schema({
            vol.Optional("config_entry_id"): cv.string,
        })
    )
    _LOGGER.info("Registered cleanup_devices service")

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        # Get the platforms that were actually loaded during setup
        entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
        platforms = entry_data.get("loaded_platforms", ["button", "switch", "sensor"])
        
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

async def async_cleanup_orphaned_entities(hass: HomeAssistant, entry_id: str, current_devices: set):
    """Clean up entities for devices that no longer match IP filter criteria.
    
    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
        current_devices: Set of MAC addresses for devices that should exist
    """
    _LOGGER.info("Starting entity cleanup for entry %s", entry_id)
    
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    
    # Find all entities belonging to this integration
    entities_to_remove = []
    devices_to_check = set()
    
    for entity_id, entity in entity_registry.entities.items():
        if entity.config_entry_id == entry_id:
            # Check if this is a DHCP device entity (has MAC in unique_id)
            if ("dhcp_device_" in str(entity.unique_id) or 
                "technitiumdns_dhcp_" in str(entity.unique_id)):
                
                # Extract MAC address from unique_id
                mac_from_entity = None
                if "dhcp_device_" in str(entity.unique_id):
                    # Device tracker format: dhcp_device_{mac_clean}
                    parts = str(entity.unique_id).split("dhcp_device_")
                    if len(parts) > 1:
                        mac_clean = parts[1].split("_")[0]  # Handle sensor suffixes
                        # Convert back to MAC format (add colons)
                        if len(mac_clean) == 12:
                            mac_from_entity = ":".join([mac_clean[i:i+2] for i in range(0, 12, 2)]).upper()
                
                elif "technitiumdns_dhcp_" in str(entity.unique_id):
                    # Sensor format: technitiumdns_dhcp_{mac_clean}_{sensor_type}
                    parts = str(entity.unique_id).split("technitiumdns_dhcp_")
                    if len(parts) > 1:
                        mac_clean = parts[1].split("_")[0]
                        if len(mac_clean) == 12:
                            mac_from_entity = ":".join([mac_clean[i:i+2] for i in range(0, 12, 2)]).upper()
                
                # Check if this device should still exist
                if mac_from_entity and mac_from_entity not in current_devices:
                    _LOGGER.info("Marking entity %s for removal (MAC %s no longer tracked)", 
                               entity_id, mac_from_entity)
                    entities_to_remove.append(entity_id)
                    
                    # Track device for potential cleanup
                    if entity.device_id:
                        devices_to_check.add(entity.device_id)
    
    # Remove orphaned entities
    for entity_id in entities_to_remove:
        _LOGGER.info("Removing orphaned entity: %s", entity_id)
        entity_registry.async_remove(entity_id)
    
    # Clean up devices that have no remaining entities
    devices_to_remove = []
    for device_id in devices_to_check:
        device = device_registry.async_get(device_id)
        if device:
            # Check if device has any remaining entities
            remaining_entities = [
                e for e in entity_registry.entities.values() 
                if e.device_id == device_id and e.config_entry_id == entry_id
            ]
            
            if not remaining_entities:
                _LOGGER.info("Marking device %s for removal (no remaining entities)", device.name)
                devices_to_remove.append(device_id)
    
    # Remove orphaned devices
    for device_id in devices_to_remove:
        _LOGGER.info("Removing orphaned device: %s", device_id)
        device_registry.async_remove_device(device_id)
    
    if entities_to_remove or devices_to_remove:
        _LOGGER.info("Cleanup completed: removed %d entities and %d devices", 
                   len(entities_to_remove), len(devices_to_remove))
    else:
        _LOGGER.debug("No orphaned entities or devices found")
