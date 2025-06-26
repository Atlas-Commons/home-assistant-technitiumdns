"""Config flow for TechnitiumDNS integration."""

import asyncio
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
import aiohttp
import async_timeout
import contextlib
import voluptuous as vol

from .const import DOMAIN, DHCP_UPDATE_INTERVAL_OPTIONS, DHCP_IP_FILTER_MODES
from .api import TechnitiumDNSApi


@config_entries.HANDLERS.register(DOMAIN)
class TechnitiumDNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TechnitiumDNS."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TechnitiumDNSOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # Validate the input by trying to create the API object
                api = TechnitiumDNSApi(user_input["api_url"], user_input["token"])
                await api.get_statistics(user_input["stats_duration"])

                return self.async_create_entry(
                    title=user_input["server_name"], data=user_input
                )
            except Exception as e:
                errors["base"] = "auth"

        data_schema = vol.Schema(
            {
                vol.Required("api_url"): str,
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

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

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
        })

        return self.async_show_form(
            step_id="init", 
            data_schema=options_schema,
            description_placeholders={
                "dhcp_description": "Enable DHCP device tracking to monitor devices connected to your Technitium DHCP server. Update interval determines how often device status is checked. Use IP filtering to control which devices are tracked based on their IP addresses."
            }
        )
