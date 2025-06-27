"""TechnitiumDNS integration."""

import logging
import voluptuous as vol

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .utils import normalize_mac_address
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
        _LOGGER.debug("Cleanup service called with config_entry_id: %s", config_entry_id)
        
        if config_entry_id:
            # Clean up specific entry
            _LOGGER.debug("Cleaning up specific entry: %s", config_entry_id)
            entry_data = hass.data.get(DOMAIN, {}).get(config_entry_id)
            if entry_data:
                # Get the actual config entry to check if DHCP is enabled
                config_entry = None
                for entry in hass.config_entries.async_entries(DOMAIN):
                    if entry.entry_id == config_entry_id:
                        config_entry = entry
                        break
                
                if config_entry:
                    dhcp_enabled = config_entry.options.get("enable_dhcp_tracking", False)
                    _LOGGER.debug("Config entry %s DHCP tracking enabled: %s", config_entry_id, dhcp_enabled)
                    _LOGGER.debug("Config entry options: %s", config_entry.options)
                
                _LOGGER.debug("Found entry data for %s: %s", config_entry_id, list(entry_data.keys()))
                dhcp_coordinator = entry_data.get("coordinators", {}).get("dhcp")
                _LOGGER.debug("DHCP coordinator status for %s: coordinator=%s, has_data=%s", 
                            config_entry_id, dhcp_coordinator is not None, 
                            dhcp_coordinator.data is not None if dhcp_coordinator else False)
                if dhcp_coordinator and dhcp_coordinator.data:
                    # Normalize MAC addresses to uppercase with colons for consistent comparison
                    current_macs = set()
                    for lease in dhcp_coordinator.data:
                        mac = lease.get("mac_address")
                        if mac:
                            normalized_mac = normalize_mac_address(mac)
                            current_macs.add(normalized_mac)
                            _LOGGER.debug("Normalized MAC %s -> %s", mac, normalized_mac)
                    _LOGGER.debug("Found %d current MAC addresses for entry %s: %s", 
                                len(current_macs), config_entry_id, sorted(current_macs))
                    await async_cleanup_orphaned_entities(hass, config_entry_id, current_macs)
                    _LOGGER.info("Manual cleanup completed for entry %s", config_entry_id)
                else:
                    _LOGGER.warning("No DHCP coordinator found for entry %s (coordinator: %s, data: %s). "
                                  "DHCP tracking may not be enabled for this entry.", 
                                  config_entry_id, dhcp_coordinator is not None, 
                                  dhcp_coordinator.data if dhcp_coordinator else None)
                    # Still attempt cleanup with empty MAC set to remove any orphaned entities
                    _LOGGER.info("Attempting cleanup with empty device set to remove any orphaned DHCP entities")
                    await async_cleanup_orphaned_entities(hass, config_entry_id, set())
            else:
                _LOGGER.error("Config entry %s not found. Available entries: %s", 
                            config_entry_id, list(hass.data.get(DOMAIN, {}).keys()))
        else:
            # Clean up all entries
            domain_data = hass.data.get(DOMAIN, {})
            _LOGGER.debug("Cleaning up all entries. Found %d total entries: %s", 
                        len(domain_data), list(domain_data.keys()))
            cleaned_entries = 0
            for entry_id, entry_data in domain_data.items():
                _LOGGER.debug("Processing entry %s with data keys: %s", entry_id, list(entry_data.keys()))
                dhcp_coordinator = entry_data.get("coordinators", {}).get("dhcp")
                _LOGGER.debug("DHCP coordinator status for %s: coordinator=%s, has_data=%s", 
                            entry_id, dhcp_coordinator is not None, 
                            dhcp_coordinator.data is not None if dhcp_coordinator else False)
                if dhcp_coordinator and dhcp_coordinator.data:
                    # Normalize MAC addresses to uppercase with colons for consistent comparison
                    current_macs = set()
                    for lease in dhcp_coordinator.data:
                        mac = lease.get("mac_address")
                        if mac:
                            normalized_mac = normalize_mac_address(mac)
                            current_macs.add(normalized_mac)
                            _LOGGER.debug("Normalized MAC %s -> %s", mac, normalized_mac)
                    _LOGGER.debug("Found %d current MAC addresses for entry %s: %s", 
                                len(current_macs), entry_id, sorted(current_macs))
                    await async_cleanup_orphaned_entities(hass, entry_id, current_macs)
                    _LOGGER.info("Manual cleanup completed for entry %s", entry_id)
                    cleaned_entries += 1
                else:
                    _LOGGER.debug("Entry %s has no DHCP coordinator or data (coordinator: %s, data: %s). "
                                "DHCP tracking may not be enabled for this entry.", 
                                entry_id, dhcp_coordinator is not None, 
                                dhcp_coordinator.data if dhcp_coordinator else None)
                    # Still attempt cleanup with empty MAC set to remove any orphaned entities
                    _LOGGER.debug("Attempting cleanup for entry %s with empty device set", entry_id)
                    await async_cleanup_orphaned_entities(hass, entry_id, set())
                    cleaned_entries += 1
            _LOGGER.debug("Cleanup completed for %d out of %d entries", cleaned_entries, len(domain_data))
    
    async def handle_get_dhcp_leases(call):
        """Handle get_dhcp_leases service call."""
        config_entry_id = call.data.get("config_entry_id")
        include_inactive = call.data.get("include_inactive", False)
        filter_scope = call.data.get("filter_scope")
        
        _LOGGER.debug("DHCP leases service called with config_entry_id: %s, include_inactive: %s, filter_scope: %s", 
                    config_entry_id, include_inactive, filter_scope)
        
        # Find the appropriate config entry
        target_entry_id = config_entry_id
        if not target_entry_id:
            # Use the first available entry if none specified
            domain_data = hass.data.get(DOMAIN, {})
            _LOGGER.debug("No config_entry_id specified, searching available entries: %s", list(domain_data.keys()))
            if domain_data:
                target_entry_id = next(iter(domain_data.keys()))
                _LOGGER.debug("Using first available entry: %s", target_entry_id)
        
        if not target_entry_id:
            _LOGGER.error("No TechnitiumDNS config entries found")
            return
            
        _LOGGER.debug("Using target entry ID: %s", target_entry_id)
        entry_data = hass.data.get(DOMAIN, {}).get(target_entry_id)
        if not entry_data:
            _LOGGER.error("Config entry %s not found. Available entries: %s", 
                        target_entry_id, list(hass.data.get(DOMAIN, {}).keys()))
            return
            
        _LOGGER.debug("Found entry data with keys: %s", list(entry_data.keys()))
        
        # Get the API instance
        api = entry_data.get("api")
        if not api:
            _LOGGER.error("No API instance found for entry %s", target_entry_id)
            return
            
        _LOGGER.debug("API instance found, making DHCP leases request")
        
        try:
            # Fetch DHCP leases
            leases_data = await api.get_dhcp_leases()
            _LOGGER.debug("DHCP API response received: %s", 
                        f"leases_data present: {leases_data is not None}, "
                        f"type: {type(leases_data)}, "
                        f"keys: {list(leases_data.keys()) if isinstance(leases_data, dict) else 'N/A'}")
            
            if not leases_data:
                _LOGGER.warning("No DHCP leases data returned from API (None or empty)")
                return
                
            if not isinstance(leases_data, dict):
                _LOGGER.warning("DHCP leases data is not a dictionary: %s", type(leases_data))
                return
                
            # Check for different possible response structures
            leases = None
            if "leases" in leases_data:
                leases = leases_data["leases"]
                _LOGGER.debug("Found 'leases' key with %d items", len(leases) if isinstance(leases, list) else 0)
            elif "response" in leases_data and isinstance(leases_data["response"], dict):
                if "leases" in leases_data["response"]:
                    leases = leases_data["response"]["leases"]
                    _LOGGER.debug("Found 'response.leases' key with %d items", len(leases) if isinstance(leases, list) else 0)
                else:
                    _LOGGER.debug("Response structure: %s", list(leases_data["response"].keys()))
            
            if leases is None:
                _LOGGER.warning("No 'leases' key found in API response. Available keys: %s", 
                              list(leases_data.keys()))
                _LOGGER.debug("Full API response: %s", leases_data)
                return
            original_count = len(leases)
            _LOGGER.debug("Retrieved %d total leases from API", original_count)
            
            # Filter leases if requested
            if not include_inactive:
                active_leases = [lease for lease in leases if lease.get("addressStatus") == "InUse"]
                _LOGGER.debug("Filtered to %d active leases (was %d total)", len(active_leases), len(leases))
                leases = active_leases
                
            if filter_scope:
                scope_filtered = [lease for lease in leases if lease.get("scope") == filter_scope]
                _LOGGER.debug("Filtered to %d leases matching scope '%s' (was %d)", 
                            len(scope_filtered), filter_scope, len(leases))
                leases = scope_filtered
            
            _LOGGER.debug("Final lease count after filtering: %d", len(leases))
            if leases:
                _LOGGER.debug("Sample lease data: %s", 
                            {k: v for k, v in leases[0].items() if k in ['address', 'hostName', 'addressStatus', 'scope']})
            
            # Fire event with the lease data
            event_data = {
                "config_entry_id": target_entry_id,
                "total_leases": len(leases),
                "leases": leases,
                "include_inactive": include_inactive,
                "filter_scope": filter_scope,
            }
            _LOGGER.debug("Firing event %s_dhcp_leases_retrieved with %d leases", DOMAIN, len(leases))
            hass.bus.async_fire(f"{DOMAIN}_dhcp_leases_retrieved", event_data)
            
            _LOGGER.info(
                "Retrieved %d DHCP leases for entry %s (include_inactive=%s, filter_scope=%s)",
                len(leases), target_entry_id, include_inactive, filter_scope
            )
            
        except Exception as e:
            _LOGGER.error("Failed to retrieve DHCP leases: %s", e)
            _LOGGER.debug("DHCP leases retrieval exception details", exc_info=True)

    hass.services.async_register(
        DOMAIN,
        "cleanup_devices", 
        handle_cleanup_devices,
        schema=vol.Schema({
            vol.Optional("config_entry_id"): cv.string,
        })
    )
    _LOGGER.info("Registered cleanup_devices service")
    
    hass.services.async_register(
        DOMAIN,
        "get_dhcp_leases",
        handle_get_dhcp_leases,
        schema=vol.Schema({
            vol.Optional("config_entry_id"): cv.string,
            vol.Optional("include_inactive", default=False): cv.boolean,
            vol.Optional("filter_scope"): cv.string,
        })
    )
    _LOGGER.info("Registered get_dhcp_leases service")

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
    _LOGGER.debug("Current devices to keep: %s (%d total)", sorted(current_devices), len(current_devices))
    
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    
    # Find all entities belonging to this integration
    entities_to_remove = []
    devices_to_check = set()
    total_entities_checked = 0
    dhcp_entities_found = 0
    
    _LOGGER.debug("Scanning entity registry for entities belonging to entry %s", entry_id)
    
    for entity_id, entity in entity_registry.entities.items():
        if entity.config_entry_id == entry_id:
            total_entities_checked += 1
            _LOGGER.debug("Checking entity %s (unique_id: %s, platform: %s)", 
                        entity_id, entity.unique_id, entity.platform)
            
            # Check if this is a DHCP device entity (has MAC in unique_id)
            if ("dhcp_device_" in str(entity.unique_id) or 
                "technitiumdns_dhcp_" in str(entity.unique_id)):
                dhcp_entities_found += 1
                _LOGGER.debug("Found DHCP entity: %s with unique_id: %s", entity_id, entity.unique_id)
                
                # Extract MAC address from unique_id
                mac_from_entity = None
                if "dhcp_device_" in str(entity.unique_id):
                    # Device tracker format: dhcp_device_{mac_address}
                    parts = str(entity.unique_id).split("dhcp_device_")
                    if len(parts) > 1:
                        mac_raw = parts[1].split("_")[0]  # Handle any suffixes
                        _LOGGER.debug("Extracted MAC raw from device tracker: %s", mac_raw)
                        
                        # Normalize MAC address to uppercase with colons
                        mac_from_entity = normalize_mac_address(mac_raw)
                        _LOGGER.debug("Normalized MAC %s -> %s", mac_raw, mac_from_entity)
                
                elif "technitiumdns_dhcp_" in str(entity.unique_id):
                    # Sensor format: technitiumdns_dhcp_{mac_address}_{sensor_type}
                    parts = str(entity.unique_id).split("technitiumdns_dhcp_")
                    if len(parts) > 1:
                        mac_raw = parts[1].split("_")[0]  # Get MAC part before any sensor suffix
                        _LOGGER.debug("Extracted MAC raw from sensor: %s", mac_raw)
                        
                        # Normalize MAC address to uppercase with colons
                        mac_from_entity = normalize_mac_address(mac_raw)
                        _LOGGER.debug("Normalized MAC %s -> %s", mac_raw, mac_from_entity)
                
                # Check if this device should still exist
                if mac_from_entity:
                    if mac_from_entity not in current_devices:
                        _LOGGER.debug("MAC %s not in current devices - marking entity %s for removal", 
                                    mac_from_entity, entity_id)
                        _LOGGER.info("Marking entity %s for removal (MAC %s no longer tracked)", 
                                   entity_id, mac_from_entity)
                        entities_to_remove.append(entity_id)
                        
                        # Track device for potential cleanup
                        if entity.device_id:
                            devices_to_check.add(entity.device_id)
                            _LOGGER.debug("Added device %s to cleanup check list", entity.device_id)
                    else:
                        _LOGGER.debug("MAC %s found in current devices - keeping entity %s", 
                                    mac_from_entity, entity_id)
                else:
                    _LOGGER.debug("Could not extract MAC address from entity %s", entity_id)
            else:
                _LOGGER.debug("Entity %s is not a DHCP entity - skipping", entity_id)
    
    _LOGGER.debug("Entity scan complete: checked %d total entities, found %d DHCP entities, marked %d for removal", 
                total_entities_checked, dhcp_entities_found, len(entities_to_remove))
    
    # Remove orphaned entities
    for entity_id in entities_to_remove:
        _LOGGER.debug("Removing orphaned entity: %s", entity_id)
        _LOGGER.info("Removing orphaned entity: %s", entity_id)
        entity_registry.async_remove(entity_id)
    
    _LOGGER.debug("Checking %d devices for potential cleanup", len(devices_to_check))
    
    # Clean up devices that have no remaining entities
    devices_to_remove = []
    for device_id in devices_to_check:
        device = device_registry.async_get(device_id)
        if device:
            _LOGGER.debug("Checking device %s (%s) for remaining entities", device_id, device.name)
            # Check if device has any remaining entities
            remaining_entities = [
                e for e in entity_registry.entities.values() 
                if e.device_id == device_id and e.config_entry_id == entry_id
            ]
            _LOGGER.debug("Device %s has %d remaining entities: %s", 
                        device.name, len(remaining_entities), 
                        [e.entity_id for e in remaining_entities])
            
            if not remaining_entities:
                _LOGGER.debug("Device %s has no remaining entities - marking for removal", device.name)
                _LOGGER.info("Marking device %s for removal (no remaining entities)", device.name)
                devices_to_remove.append(device_id)
            else:
                _LOGGER.debug("Device %s has remaining entities - keeping", device.name)
        else:
            _LOGGER.debug("Device %s not found in registry - may have been removed already", device_id)
    
    # Remove orphaned devices
    for device_id in devices_to_remove:
        device = device_registry.async_get(device_id)
        device_name = device.name if device else f"device_{device_id}"
        _LOGGER.debug("Removing orphaned device: %s (%s)", device_id, device_name)
        _LOGGER.info("Removing orphaned device: %s", device_name)
        device_registry.async_remove_device(device_id)
    
    if entities_to_remove or devices_to_remove:
        _LOGGER.info("Cleanup completed: removed %d entities and %d devices", 
                   len(entities_to_remove), len(devices_to_remove))
        _LOGGER.debug("Removed entities: %s", entities_to_remove)
        _LOGGER.debug("Removed devices: %s", [device_registry.async_get(d).name if device_registry.async_get(d) else f"device_{d}" for d in devices_to_remove])
    else:
        _LOGGER.debug("No orphaned entities or devices found")
        _LOGGER.info("No orphaned entities or devices found")
