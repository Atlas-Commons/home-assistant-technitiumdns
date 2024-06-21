"""Config flow for TechnetiumDNS integration."""

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
import aiohttp
import async_timeout
import voluptuous as vol

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class TechnetiumDNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TechnetiumDNS."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            valid = await self._test_credentials(
                user_input["api_url"], user_input["token"]
            )
            if valid:
                return self.async_create_entry(title="TechnetiumDNS", data=user_input)
            else:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("api_url"): str,
                    vol.Required("token"): str,
                    vol.Required("username"): str,
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, api_url, token):
        """Test the provided credentials."""
        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            with async_timeout.timeout(10):
                response = await session.get(
                    f"{api_url}/api/dashboard/stats/get?token={token}"
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
