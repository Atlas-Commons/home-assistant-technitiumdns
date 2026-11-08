"""TechnitiumDNS integration."""

import logging
import re
import voluptuous as vol

from homeassistant import core
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_DHCP_LOG_TRACKING,
    DEFAULT_DHCP_STALE_THRESHOLD,
    DEFAULT_DHCP_SMART_ACTIVITY,
    DEFAULT_ACTIVITY_SCORE_THRESHOLD,
    DEFAULT_ACTIVITY_ANALYSIS_WINDOW,
)
from .config_flow import CONFIG_VERSION
from .utils import normalize_mac_address
from .client import create_api_client
from .const import KEY_BLOCKING_DISABLED_UNTIL

_LOGGER = logging.getLogger(__name__)

async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry):
    """Migrate the unique_ids of existing sensors to the new format, handling duplicates."""
    _LOGGER.info("Starting unique_id migration for TechnitiumDNS sensors.")
    entity_registry = er.async_get(hass)

    entities_to_check = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    migrated_count = 0
    for entity in entities_to_check:
        # Check if the unique_id matches the OLD format: "Technitiumdns_{type}_{server}"
        if entity.unique_id and entity.unique_id.startswith("Technitiumdns_"):
            try:
                parts = entity.unique_id.split('_', 2)
                if len(parts) != 3:
                    continue

                _, sensor_type, server_name = parts

                # Construct the NEW unique_id that this entity SHOULD have
                new_unique_id = f"{DOMAIN}_dns_stats_{sensor_type}_{server_name.replace(' ', '_').lower()}"

                # --- START OF NEW LOGIC ---
                # Check if another entity (the _2 duplicate) is already using the new unique_id
                conflicting_entity_id = entity_registry.async_get_entity_id(
                    "sensor", DOMAIN, new_unique_id
                )

                if conflicting_entity_id and conflicting_entity_id != entity.entity_id:
                    _LOGGER.warning(
                        "Found conflicting entity %s with the target unique_id. Removing it to resolve duplication.",
                        conflicting_entity_id
                    )
                    entity_registry.async_remove_entity(conflicting_entity_id)
                # --- END OF NEW LOGIC ---

                _LOGGER.debug(
                    "Migrating unique_id for entity %s from '%s' to '%s'",
                    entity.entity_id, entity.unique_id, new_unique_id
                )

                # Now, update the original entity's unique_id
                entity_registry.async_update_entity(
                    entity.entity_id, new_unique_id=new_unique_id
                )
                migrated_count += 1
            except Exception as e:
                _LOGGER.error(
                    "Error migrating unique_id for entity %s: %s", entity.entity_id, e
                )

    if migrated_count > 0:
        _LOGGER.info("Successfully migrated %d sensor unique_ids.", migrated_count)
    else:
        _LOGGER.info("No sensor unique_ids required migration for this entry.")

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old config entry to a new version."""
    _LOGGER.info(
        "Migrating config entry '%s' from version %s to %s",
        config_entry.title,
        config_entry.version,
    )

    # --- Migration from version 1 to 2 ---
    if config_entry.version == 1:
        # --- 1. Migrate Core Data (add 'check_ssl') ---
        new_data = {**config_entry.data, "check_ssl": True}

        # --- 2. Migrate Options (add all new DHCP keys) ---
        new_options = {**config_entry.options}

        # Add DHCP tracking options with defaults
        new_options.setdefault("enable_dhcp_tracking", False)
        new_options.setdefault("dhcp_update_interval", 60)
        new_options.setdefault("dhcp_ip_filter_mode", "disabled")
        new_options.setdefault("dhcp_ip_ranges", "")

        # Add DNS log tracking options with defaults
        new_options.setdefault("dhcp_log_tracking", DEFAULT_DHCP_LOG_TRACKING)
        new_options.setdefault("dhcp_stale_threshold", DEFAULT_DHCP_STALE_THRESHOLD)

        # Add Smart Activity options with defaults
        new_options.setdefault("dhcp_smart_activity", DEFAULT_DHCP_SMART_ACTIVITY)
        new_options.setdefault("activity_score_threshold", DEFAULT_ACTIVITY_SCORE_THRESHOLD)
        new_options.setdefault("activity_analysis_window", DEFAULT_ACTIVITY_ANALYSIS_WINDOW)

        # Update the config entry with new data, options, and version
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options, version=2
        )
        _LOGGER.info("Successfully migrated config entry to version 2.")


    # --- Migration from version 2 to 3 ---
    # This handles users who were on 2.4.0 and need the unique_id fix.
    # It will also run for users who were just migrated from v1.
    if config_entry.version == 2:
        # Only run the unique_id migration
        await _async_migrate_unique_ids(hass, config_entry)

        # Update the version to 3
        hass.config_entries.async_update_entry(config_entry, version=3)
        _LOGGER.info("Successfully migrated config entry to version 3.")

    # --- Migration from version 3 to 4 ---
    if config_entry.version == 3:
        new_data = {**config_entry.data}
        new_data.setdefault("cluster_mode", False)
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=4
        )
        _LOGGER.info("Successfully migrated config entry to version 4.")

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TechnitiumDNS from a config entry."""
    if entry.version < CONFIG_VERSION and not await async_migrate_entry(hass, entry):
        _LOGGER.error("Migration failed for config entry %s. Cannot setup integration.", entry.title)
        return False
    _LOGGER.info("Setting up TechnitiumDNS integration for entry %s", entry.entry_id)
    hass.data.setdefault(DOMAIN, {})

    api = await create_api_client(
        hass,
        api_url=entry.data["api_url"],
        token=entry.data["token"],
        check_ssl=entry.data.get("check_ssl", True),
        cluster_mode=entry.data.get("cluster_mode", False),
    )

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
        "loaded_platforms": platforms,
        KEY_BLOCKING_DISABLED_UNTIL: None,
    }

    device_registry = dr.async_get(hass)
    server_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Technitium",
        name=entry.data["server_name"],
        model="DNS Server",
    )

    hass.data[DOMAIN][entry.entry_id]["server_device_id"] = server_device.id

    # Forward the setup to the appropriate platforms in order
    _LOGGER.info("Starting platform setup for: %s", platforms)

    # Set up all platforms (order is preserved: device_tracker before sensor)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    _LOGGER.info("All platforms setup completed successfully")

    # Set up options flow listener to handle configuration changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Register the report service for manual orphan scans
    await async_register_services(hass)

    _LOGGER.info("TechnitiumDNS integration setup completed for entry %s", entry.entry_id)
    return True

async def async_register_services(hass: HomeAssistant):
    """Register integration services."""
    if hass.services.has_service(DOMAIN, "cleanup_devices"):
        return  # Service already registered

    async def handle_cleanup_devices(call):
        """Report DHCP entities that no longer match current coordinator data."""
        config_entry_id = call.data.get("config_entry_id")
        domain_data = hass.data.get(DOMAIN, {})
        if config_entry_id:
            if config_entry_id not in domain_data:
                _LOGGER.error("Config entry %s is not loaded; no entity report was produced", config_entry_id)
                return
            entries_to_scan = {config_entry_id: domain_data[config_entry_id]}
        else:
            entries_to_scan = domain_data

        for entry_id, entry_data in entries_to_scan.items():
            coordinator = entry_data.get("coordinators", {}).get("dhcp")
            current_macs = None
            if coordinator is not None and coordinator.data is not None:
                current_macs = {
                    normalize_mac_address(lease["mac_address"])
                    for lease in coordinator.data
                    if lease.get("mac_address")
                }

            await async_cleanup_orphaned_entities(hass, entry_id, current_macs)

        _LOGGER.info("DHCP entity orphan report completed for %d config entries", len(entries_to_scan))

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
            leases_data = await api.dhcp.leases_list()
            _LOGGER.debug(
                "DHCP API response received: leases_count=%d",
                len(leases_data) if leases_data else 0,
            )

            if leases_data is None:
                _LOGGER.warning("DHCP leases API returned no result")
                return

            leases = [
                {
                    "address": lease.address,
                    "hardwareAddress": lease.hardware_address,
                    "hostName": lease.host_name,
                    "clientIdentifier": lease.client_identifier,
                    "addressStatus": lease.address_status,
                    "scope": lease.scope,
                    "type": lease.type,
                    "leaseObtained": (
                        lease.lease_obtained.isoformat()
                        if lease.lease_obtained
                        else None
                    ),
                    "leaseExpires": (
                        lease.lease_expires.isoformat()
                        if lease.lease_expires
                        else None
                    ),
                }
                for lease in leases_data
            ]
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
        if platforms := entry_data.get(
            "loaded_platforms", ["button", "switch", "sensor"]
        ):
            await hass.config_entries.async_unload_platforms(entry, platforms)

        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True

    except Exception as e:
        _LOGGER.error("Error unloading TechnitiumDNS integration: %s", e)
        # Still try to clean up data even if platform unload failed
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True

def dhcp_entity_mac(entity):
    """Return a DHCP entity's MAC, an empty string for IP-only trackers, or None."""
    if entity.platform != DOMAIN:
        return None

    entity_domain = entity.entity_id.partition(".")[0]
    unique_id = str(entity.unique_id)
    if entity_domain == "device_tracker":
        prefix = f"{DOMAIN}_device_tracker_"
        if not unique_id.startswith(prefix):
            return None
        identifier = unique_id.removeprefix(prefix)
        if re.fullmatch(r"[0-9a-f]{12}", identifier):
            return normalize_mac_address(identifier)
        if re.fullmatch(r"ip_(?:\d{1,3}_){3}\d{1,3}", identifier):
            return ""
        return None

    if entity_domain == "sensor":
        prefix = f"{DOMAIN}_dhcp_"
        if not unique_id.startswith(prefix):
            return None
        match = re.fullmatch(r"([0-9a-f]{12})_[a-z0-9_]+", unique_id.removeprefix(prefix))
        if match:
            return normalize_mac_address(match.group(1))

    return None


async def async_cleanup_orphaned_entities(
    hass: HomeAssistant, entry_id: str, current_devices: set[str] | None
):
    """Log a non-destructive report of DHCP entities missing from current data.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
        current_devices: Current MAC addresses, or None when coordinator data is unavailable
    """
    entity_registry = er.async_get(hass)
    orphaned_entities = []
    current_entities = []
    unknown_entities = []

    for entity_id, entity in entity_registry.entities.items():
        if entity.config_entry_id != entry_id:
            continue
        mac_address = dhcp_entity_mac(entity)
        if mac_address is None:
            continue
        if current_devices is None or not mac_address:
            unknown_entities.append((entity_id, entity.platform))
        elif mac_address in current_devices:
            current_entities.append((entity_id, mac_address, entity.platform))
        else:
            orphaned_entities.append((entity_id, mac_address, entity.platform))

    _LOGGER.info(
        "DHCP entity report for entry %s: %d tracker/sensor candidates",
        entry_id,
        len(orphaned_entities) + len(current_entities) + len(unknown_entities),
    )
    if current_devices is None:
        _LOGGER.info("Current DHCP coordinator data is unavailable; orphan status is unknown")

    if orphaned_entities:
        _LOGGER.info("Found %d DHCP entities whose MAC is absent from current coordinator data:", len(orphaned_entities))
        if len(orphaned_entities) > 20:
            _LOGGER.info("  - %d additional candidates omitted", len(orphaned_entities) - 20)
    else:
        _LOGGER.info("No DHCP entity candidates were confirmed as orphaned")

    if current_entities:
        _LOGGER.debug("Found %d DHCP entities matching current coordinator data:", len(current_entities))

    if unknown_entities:
        _LOGGER.info("Found %d DHCP entities with unknown orphan status:", len(unknown_entities))
        if len(unknown_entities) > 20:
            _LOGGER.info("  - %d additional candidates omitted", len(unknown_entities) - 20)

    report_lines = []
    if current_devices is None:
        report_lines.append("Current DHCP data is unavailable; orphan status is unknown.")
    if orphaned_entities:
        report_lines.append("Orphaned entities (MAC absent from current DHCP data):")
        report_lines.extend(
            f"- `{entity_id}` ({platform})"
            for entity_id, _, platform in orphaned_entities[:20]
        )
        if len(orphaned_entities) > 20:
            report_lines.append(
                f"- {len(orphaned_entities) - 20} additional candidates omitted"
            )
    else:
        report_lines.append("No entities were confirmed as orphaned.")
    if unknown_entities:
        report_lines.append("Entities with unknown orphan status:")
        report_lines.extend(
            f"- `{entity_id}` ({platform})"
            for entity_id, platform in unknown_entities[:20]
        )
        if len(unknown_entities) > 20:
            report_lines.append(
                f"- {len(unknown_entities) - 20} additional candidates omitted"
            )

    persistent_notification.async_create(
        hass,
        "\n".join(report_lines),
        title="TechnitiumDNS DHCP entity report",
        notification_id=f"{DOMAIN}_dhcp_entity_report_{entry_id}",
    )
