"""Config flow for TechnetiumDNS integration."""

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
import aiohttp
import async_timeout
import voluptuous as vol

from .const import DOMAIN
from .api import TechnetiumDNSApi


@config_entries.HANDLERS.register(DOMAIN)
class TechnetiumDNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TechnetiumDNS."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # Validate the input by trying to create the API object
                api = TechnetiumDNSApi(user_input["api_url"], user_input["token"])
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

    async def _test_credentials(self, api_url, token, stats_duration):
        """Test the provided credentials."""
        try:
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
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TechnetiumDNSOptionsFlowHandler(config_entry)


class TechnetiumDNSOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for TechnetiumDNS."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
