"""API for interacting with TechnetiumDNS."""

import aiohttp
import async_timeout
import logging

_LOGGER = logging.getLogger(__name__)


class TechnetiumDNSApi:
    """Class to interact with the TechnetiumDNS API."""

    def __init__(self, api_url, token):
        """Initialize the API with the provided URL and token."""
        self._api_url = api_url
        self._token = token

    async def fetch_data(self, endpoint, params=None):
        """Fetch data from the API."""
        url = f"{self._api_url}/{endpoint}?token={self._token}"
        if params:
            for key, value in params.items():
                url += f"&{key}={value}"
        async with aiohttp.ClientSession() as session:
            try:
                with async_timeout.timeout(10):
                    _LOGGER.debug("Requesting URL: %s", url)
                    response = await session.get(url)
                    response.raise_for_status()
                    data = await response.json()
                    _LOGGER.debug("Response: %s", data)
                    if data.get("status") != "ok":
                        raise Exception(
                            f"Error fetching data: {data.get('errorMessage')}"
                        )
                    return data
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.error("Error fetching data from %s: %s", endpoint, err)
                raise Exception(f"Error fetching data from {endpoint}: {err}")

    async def get_statistics(self):
        """Get the statistics from the API."""
        return await self.fetch_data(
            "api/dashboard/stats/get", params={"type": "LastDay", "utc": "true"}
        )

    async def get_top_clients(self):
        """Get the top clients stats from the API."""
        return await self.fetch_data(
            "api/dashboard/stats/getTop",
            params={"type": "LastDay", "statsType": "TopClients", "limit": 1000},
        )

    async def get_top_domains(self):
        """Get the top domains stats from the API."""
        return await self.fetch_data(
            "api/dashboard/stats/getTop",
            params={"type": "LastDay", "statsType": "TopDomains", "limit": 1000},
        )

    async def get_top_blocked_domains(self):
        """Get the top blocked domains stats from the API."""
        return await self.fetch_data(
            "api/dashboard/stats/getTop",
            params={"type": "LastDay", "statsType": "TopBlockedDomains", "limit": 1000},
        )

    async def check_update(self):
        """Check for updates from the API."""
        return await self.fetch_data("api/user/checkForUpdate")
