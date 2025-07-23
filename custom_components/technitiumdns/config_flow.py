"""Config flow for TechnitiumDNS integration."""

import asyncio
import logging
import json
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
import aiohttp
import async_timeout
import contextlib
import voluptuous as vol

from .const import (
    DOMAIN, 
    DHCP_UPDATE_INTERVAL_OPTIONS, 
    DHCP_IP_FILTER_MODES,
    DHCP_STALE_THRESHOLD_OPTIONS,
    DEFAULT_DHCP_LOG_TRACKING,
    DEFAULT_DHCP_STALE_THRESHOLD,
    CONF_DHCP_LOG_TRACKING,
    CONF_DHCP_STALE_THRESHOLD,
    ACTIVITY_SCORE_THRESHOLDS,
    ACTIVITY_ANALYSIS_WINDOWS,
    DEFAULT_DHCP_SMART_ACTIVITY,
    DEFAULT_ACTIVITY_SCORE_THRESHOLD,
    DEFAULT_ACTIVITY_ANALYSIS_WINDOW,
    CONF_DHCP_SMART_ACTIVITY,
    CONF_ACTIVITY_SCORE_THRESHOLD,
    CONF_ACTIVITY_ANALYSIS_WINDOW
)
from .api import TechnitiumDNSApi


@config_entries.HANDLERS.register(DOMAIN)
class TechnitiumDNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TechnitiumDNS."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TechnitiumDNSOptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # Validate the input by trying to create the API object
                api = TechnitiumDNSApi(user_input["api_url"], user_input["check_ssl"], user_input["token"])
                await api.get_statistics(user_input["stats_duration"])

                return self.async_create_entry(
                    title=user_input["server_name"], data=user_input
                )
            except Exception as e:
                errors["base"] = "auth"

        data_schema = vol.Schema(
            {
                vol.Required("api_url"): str,
                vol.Required("check_ssl", default=True): bool,
                vol.Required("token"): str,
                vol.Required("server_name"): str,
                vol.Required("username"): str,
                vol.Required("stats_duration"): vol.In(
                    ["LastHour", "LastDay", "LastWeek", "LastMonth"]
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import from config migration."""
        return await self.async_step_user(user_input)

    @staticmethod
    async def async_migrate_entry(hass, config_entry):
        """Migrate old entry."""
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug("Migrating configuration from version %s", config_entry.version)

        if config_entry.version == 1:
            # Version 1 -> 2: Add default DHCP tracking options
            new_options = dict(config_entry.options)
            if "enable_dhcp_tracking" not in new_options:
                new_options["enable_dhcp_tracking"] = False
            if "dhcp_update_interval" not in new_options:
                new_options["dhcp_update_interval"] = 60
            if "dhcp_ip_filter_mode" not in new_options:
                new_options["dhcp_ip_filter_mode"] = "disabled"
            if "dhcp_ip_ranges" not in new_options:
                new_options["dhcp_ip_ranges"] = ""

            hass.config_entries.async_update_entry(
                config_entry, 
                options=new_options,
                version=2
            )
            _LOGGER.info("Migration to version 2 complete")

        return True

    async def _test_credentials(self, api_url, token, stats_duration):
        """Test the provided credentials."""
        with contextlib.suppress(aiohttp.ClientError, asyncio.TimeoutError):
            session = aiohttp_client.async_get_clientsession(self.hass)
            with async_timeout.timeout(10):
                response = await session.get(
                    f"{api_url}/api/dashboard/stats/get?token={token}&type={stats_duration}&utc=true"
                )
                if (
                    response.status == 200
                    and (await response.json()).get("status") == "ok"
                ):
                    return True
        return False


class TechnitiumDNSOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for TechnitiumDNS."""

    def __init__(self, config_entry=None):
        """Initialize options flow handler."""
        # For compatibility with different HA versions
        if config_entry is not None:
            self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Check if test DHCP button was clicked
            if user_input.get("test_dhcp"):
                return await self.async_step_dhcp_test()
            
            # Remove test_dhcp from user_input before saving
            data_to_save = {k: v for k, v in user_input.items() if k != "test_dhcp"}
            return self.async_create_entry(title="", data=data_to_save)

        options_schema = vol.Schema({
            vol.Optional(
                "enable_dhcp_tracking", 
                default=self.config_entry.options.get("enable_dhcp_tracking", False)
            ): bool,
            vol.Optional(
                "dhcp_update_interval",
                default=self.config_entry.options.get("dhcp_update_interval", 60)
            ): vol.In(DHCP_UPDATE_INTERVAL_OPTIONS),
            vol.Optional(
                "dhcp_ip_filter_mode",
                default=self.config_entry.options.get("dhcp_ip_filter_mode", "disabled")
            ): vol.In(list(DHCP_IP_FILTER_MODES.keys())),
            vol.Optional(
                "dhcp_ip_ranges",
                default=self.config_entry.options.get("dhcp_ip_ranges", "")
            ): str,
            vol.Optional(
                CONF_DHCP_LOG_TRACKING,
                default=self.config_entry.options.get(CONF_DHCP_LOG_TRACKING, DEFAULT_DHCP_LOG_TRACKING)
            ): bool,
            vol.Optional(
                CONF_DHCP_STALE_THRESHOLD,
                default=self.config_entry.options.get(CONF_DHCP_STALE_THRESHOLD, DEFAULT_DHCP_STALE_THRESHOLD)
            ): vol.In(list(DHCP_STALE_THRESHOLD_OPTIONS.keys())),
            vol.Optional(
                CONF_DHCP_SMART_ACTIVITY,
                default=self.config_entry.options.get(CONF_DHCP_SMART_ACTIVITY, DEFAULT_DHCP_SMART_ACTIVITY)
            ): bool,
            vol.Optional(
                CONF_ACTIVITY_SCORE_THRESHOLD,
                default=self.config_entry.options.get(CONF_ACTIVITY_SCORE_THRESHOLD, DEFAULT_ACTIVITY_SCORE_THRESHOLD)
            ): vol.In(list(ACTIVITY_SCORE_THRESHOLDS.keys())),
            vol.Optional(
                CONF_ACTIVITY_ANALYSIS_WINDOW,
                default=self.config_entry.options.get(CONF_ACTIVITY_ANALYSIS_WINDOW, DEFAULT_ACTIVITY_ANALYSIS_WINDOW)
            ): vol.In(list(ACTIVITY_ANALYSIS_WINDOWS.keys())),
            vol.Optional("test_dhcp", default=False): bool,
        })

        return self.async_show_form(
            step_id="init", 
            data_schema=options_schema,
            description_placeholders={
                "dhcp_description": "Enable DHCP device tracking to monitor devices connected to your Technitium DHCP server. Update interval determines how often device status is checked. Use IP filtering to control which devices are tracked based on their IP addresses."
            }
        )

    async def async_step_dhcp_test(self, user_input=None):
        """Test DHCP connection and display results."""
        if user_input is not None:
            # User clicked back or save, return to main options
            return await self.async_step_init()

        errors = {}
        dhcp_results = ""
        
        try:
            # Get API instance from config entry data
            from .api import TechnitiumDNSApi
            
            config_data = self.config_entry.data
            api = TechnitiumDNSApi(config_data["api_url"], config_data["token"])
            
            # Test DHCP connection
            dhcp_response = await api.get_dhcp_leases()
            
            if dhcp_response.get("status") == "ok":
                leases = dhcp_response.get("response", {}).get("leases", [])
                
                if leases:
                    dhcp_results = f"✅ Successfully retrieved {len(leases)} DHCP leases:\n\n"
                    
                    for i, lease in enumerate(leases[:20], 1):  # Show first 20 leases
                        dhcp_results += f"Device {i}:\n"
                        dhcp_results += f"  IP: {lease.get('address', 'N/A')}\n"
                        dhcp_results += f"  MAC: {lease.get('hardwareAddress', 'N/A')}\n"
                        dhcp_results += f"  Hostname: {lease.get('hostName', 'N/A')}\n"
                        dhcp_results += f"  Type: {lease.get('type', 'N/A')}\n"
                        dhcp_results += f"  Status: {lease.get('addressStatus', 'N/A')}\n"
                        dhcp_results += f"  Scope: {lease.get('scope', 'N/A')}\n"
                        if lease.get('leaseExpires'):
                            dhcp_results += f"  Expires: {lease.get('leaseExpires')}\n"
                        dhcp_results += "\n"
                    
                    if len(leases) > 20:
                        dhcp_results += f"... and {len(leases) - 20} more leases\n"
                        
                    dhcp_results += f"\nRaw API Response:\n{json.dumps(dhcp_response, indent=2)}"
                else:
                    dhcp_results = "✅ DHCP API connection successful, but no leases found.\n\nThis could mean:\n- No devices are currently connected\n- DHCP server is not configured\n- DHCP scope is empty\n\nRaw API Response:\n" + json.dumps(dhcp_response, indent=2)
            else:
                dhcp_results = f"❌ DHCP API returned error status: {dhcp_response.get('status')}\n\nResponse: {json.dumps(dhcp_response, indent=2)}"
                errors["base"] = "dhcp_error"
                
        except Exception as e:
            dhcp_results = f"❌ Failed to retrieve DHCP leases:\n\nError: {str(e)}\n\nPlease check:\n- Technitium DNS server is running\n- API URL is correct\n- Token has DHCP access permissions\n- DHCP server is enabled in Technitium"
            errors["base"] = "dhcp_connection_failed"

        test_schema = vol.Schema({
            vol.Optional("dhcp_test_results", default=dhcp_results): str,
        })

        return self.async_show_form(
            step_id="dhcp_test",
            data_schema=test_schema,
            errors=errors,
            description_placeholders={
                "test_results": dhcp_results
            }
        )
