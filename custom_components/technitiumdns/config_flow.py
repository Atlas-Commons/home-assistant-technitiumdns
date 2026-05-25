"""Config flow for TechnitiumDNS integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from technitiumdns import InvalidTokenError, TransportError

from homeassistant import config_entries
from homeassistant.core import callback

from .client import create_api_client
from .const import (
    ACTIVITY_ANALYSIS_WINDOWS,
    ACTIVITY_SCORE_THRESHOLDS,
    CONF_ACTIVITY_ANALYSIS_WINDOW,
    CONF_ACTIVITY_SCORE_THRESHOLD,
    CONF_DHCP_LOG_TRACKING,
    CONF_DHCP_SMART_ACTIVITY,
    CONF_DHCP_STALE_THRESHOLD,
    CONF_STATS_UPDATE_INTERVAL,
    DEFAULT_ACTIVITY_ANALYSIS_WINDOW,
    DEFAULT_ACTIVITY_SCORE_THRESHOLD,
    DEFAULT_DHCP_LOG_TRACKING,
    DEFAULT_DHCP_SMART_ACTIVITY,
    DEFAULT_DHCP_STALE_THRESHOLD,
    DEFAULT_STATS_UPDATE_INTERVAL,
    DHCP_IP_FILTER_MODES,
    DHCP_STALE_THRESHOLD_OPTIONS,
    DHCP_UPDATE_INTERVAL_OPTIONS,
    DOMAIN,
    STATS_UPDATE_INTERVAL_OPTIONS,
)

CONFIG_VERSION = 4

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class TechnitiumDNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TechnitiumDNS."""

    VERSION = CONFIG_VERSION

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return TechnitiumDNSOptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                api = await create_api_client(
                    self.hass,
                    api_url=user_input["api_url"],
                    token=user_input["token"],
                    check_ssl=user_input["check_ssl"],
                    cluster_mode=user_input.get("cluster_mode", False),
                )
                await api.dashboard.stats(type=user_input["stats_duration"], utc=True)

                return self.async_create_entry(
                    title=user_input["server_name"], data=user_input
                )
            except InvalidTokenError:
                errors["base"] = "auth"
            except TransportError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required("api_url"): str,
                vol.Required("check_ssl", default=True): bool,
                vol.Optional("cluster_mode", default=False): bool,
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


class TechnitiumDNSOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for TechnitiumDNS."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            if user_input.get("test_dhcp"):
                return await self.async_step_dhcp_test()

            data_to_save = {k: v for k, v in user_input.items() if k != "test_dhcp"}
            return self.async_create_entry(title="", data=data_to_save)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    "enable_dhcp_tracking",
                    default=self.config_entry.options.get("enable_dhcp_tracking", False),
                ): bool,
                vol.Optional(
                    "dhcp_update_interval",
                    default=self.config_entry.options.get("dhcp_update_interval", 60),
                ): vol.In(DHCP_UPDATE_INTERVAL_OPTIONS),
                vol.Optional(
                    CONF_STATS_UPDATE_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_STATS_UPDATE_INTERVAL, DEFAULT_STATS_UPDATE_INTERVAL
                    ),
                ): vol.In(STATS_UPDATE_INTERVAL_OPTIONS),
                vol.Optional(
                    "dhcp_ip_filter_mode",
                    default=self.config_entry.options.get("dhcp_ip_filter_mode", "disabled"),
                ): vol.In(list(DHCP_IP_FILTER_MODES.keys())),
                vol.Optional(
                    "dhcp_ip_ranges",
                    default=self.config_entry.options.get("dhcp_ip_ranges", ""),
                ): str,
                vol.Optional(
                    CONF_DHCP_LOG_TRACKING,
                    default=self.config_entry.options.get(
                        CONF_DHCP_LOG_TRACKING, DEFAULT_DHCP_LOG_TRACKING
                    ),
                ): bool,
                vol.Optional(
                    CONF_DHCP_STALE_THRESHOLD,
                    default=self.config_entry.options.get(
                        CONF_DHCP_STALE_THRESHOLD, DEFAULT_DHCP_STALE_THRESHOLD
                    ),
                ): vol.In(list(DHCP_STALE_THRESHOLD_OPTIONS.keys())),
                vol.Optional(
                    CONF_DHCP_SMART_ACTIVITY,
                    default=self.config_entry.options.get(
                        CONF_DHCP_SMART_ACTIVITY, DEFAULT_DHCP_SMART_ACTIVITY
                    ),
                ): bool,
                vol.Optional(
                    CONF_ACTIVITY_SCORE_THRESHOLD,
                    default=self.config_entry.options.get(
                        CONF_ACTIVITY_SCORE_THRESHOLD, DEFAULT_ACTIVITY_SCORE_THRESHOLD
                    ),
                ): vol.In(list(ACTIVITY_SCORE_THRESHOLDS.keys())),
                vol.Optional(
                    CONF_ACTIVITY_ANALYSIS_WINDOW,
                    default=self.config_entry.options.get(
                        CONF_ACTIVITY_ANALYSIS_WINDOW, DEFAULT_ACTIVITY_ANALYSIS_WINDOW
                    ),
                ): vol.In(list(ACTIVITY_ANALYSIS_WINDOWS.keys())),
                vol.Optional("test_dhcp", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "dhcp_description": (
                    "Enable DHCP device tracking to monitor devices connected to your "
                    "Technitium DHCP server. Update interval determines how often device "
                    "status is checked. Use IP filtering to control which devices are "
                    "tracked based on their IP addresses."
                )
            },
        )

    async def async_step_dhcp_test(self, user_input=None):
        """Test DHCP connection and display results."""
        if user_input is not None:
            return await self.async_step_init()

        errors: dict[str, str] = {}
        dhcp_results = ""

        try:
            config_data = self.config_entry.data
            api = await create_api_client(
                self.hass,
                api_url=config_data["api_url"],
                token=config_data["token"],
                check_ssl=config_data.get("check_ssl", True),
                cluster_mode=config_data.get("cluster_mode", False),
            )
            leases = await api.dhcp.leases_list()

            if leases:
                dhcp_results = f"✅ Successfully retrieved {len(leases)} DHCP leases:\n\n"
                for i, lease in enumerate(leases[:20], 1):
                    dhcp_results += f"Device {i}:\n"
                    dhcp_results += f"  IP: {lease.address or 'N/A'}\n"
                    dhcp_results += f"  MAC: {lease.hardware_address or 'N/A'}\n"
                    dhcp_results += f"  Hostname: {lease.host_name or 'N/A'}\n"
                    dhcp_results += f"  Type: {lease.type or 'N/A'}\n"
                    dhcp_results += f"  Status: {lease.address_status or 'N/A'}\n"
                    dhcp_results += f"  Scope: {lease.scope or 'N/A'}\n"
                    if lease.lease_expires:
                        dhcp_results += f"  Expires: {lease.lease_expires}\n"
                    dhcp_results += "\n"

                if len(leases) > 20:
                    dhcp_results += f"... and {len(leases) - 20} more leases\n"
            else:
                dhcp_results = (
                    "✅ DHCP API connection successful, but no leases found.\n\n"
                    "This could mean:\n"
                    "- No devices are currently connected\n"
                    "- DHCP server is not configured\n"
                    "- DHCP scope is empty"
                )

        except Exception as err:
            dhcp_results = (
                f"❌ Failed to retrieve DHCP leases:\n\nError: {err}\n\n"
                "Please check:\n"
                "- Technitium DNS server is running\n"
                "- API URL is correct\n"
                "- Token has DHCP access permissions\n"
                "- DHCP server is enabled in Technitium"
            )
            errors["base"] = "dhcp_connection_failed"

        test_schema = vol.Schema(
            {
                vol.Optional("dhcp_test_results", default=dhcp_results): str,
            }
        )

        return self.async_show_form(
            step_id="dhcp_test",
            data_schema=test_schema,
            errors=errors,
            description_placeholders={"test_results": dhcp_results},
        )
