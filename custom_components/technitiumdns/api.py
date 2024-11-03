import asyncio
import logging
import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)


class TechnitiumDNSApi:
    """Class to interact with the TechnitiumDNS API."""

    def __init__(self, api_url, token):
        """Initialize the API with the provided URL and token."""
        self._api_url = api_url.rstrip("/")
        self._token = token

    async def fetch_data(self, endpoint, params=None):
        """Fetch data from the API."""
        url = f"{self._api_url}/{endpoint}"
        retries = 3

        if not params:
            params = {}
        params["token"] = self._token

        for attempt in range(retries):
            async with aiohttp.ClientSession() as session:
                try:
                    with async_timeout.timeout(20):  # Increase timeout to 20 seconds
                        _LOGGER.debug("Requesting URL: %s (Attempt %d)", url, attempt + 1)
                        async with session.get(url, params=params) as response:
                            response.raise_for_status()
                            data = await response.json()
                            _LOGGER.debug("Response: %s", data)
                            if data.get("status") != "ok":
                                raise Exception(f"Error fetching data: {data.get('errorMessage')}")
                            return data
                except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                    _LOGGER.error("Attempt %d: Error fetching data from %s: %s", attempt + 1, endpoint, err)
                    if attempt == retries - 1:  # Raise the exception if final attempt fails
                        raise Exception(
                            f"Error fetching data from {endpoint} after {retries} attempts: {err}"
                        ) from err
                    await asyncio.sleep(5)  # Wait 5 seconds before retrying
                except Exception as e:
                    _LOGGER.error("An error occurred: %s", e)
                    raise Exception(f"An error occurred: {e}") from e

    async def get_statistics(self, stats_duration):
        """Get the statistics from the API."""
        return await self.fetch_data(
            "api/dashboard/stats/get", params={"type": stats_duration, "utc": "true"}
        )

    async def get_top_clients(self, stats_duration):
        """Get the top clients stats from the API."""
        return await self.fetch_data(
            "api/dashboard/stats/getTop",
            params={"type": stats_duration, "statsType": "TopClients", "limit": 1000},
        )

    async def get_top_domains(self, stats_duration):
        """Get the top domains stats from the API."""
        return await self.fetch_data(
            "api/dashboard/stats/getTop",
            params={"type": stats_duration, "statsType": "TopDomains", "limit": 1000},
        )

    async def get_top_blocked_domains(self, stats_duration):
        """Get the top blocked domains stats from the API."""
        return await self.fetch_data(
            "api/dashboard/stats/getTop",
            params={
                "type": stats_duration,
                "statsType": "TopBlockedDomains",
                "limit": 1000,
            },
        )

    async def check_update(self):
        """Check for updates from the API."""
        return await self.fetch_data("api/user/checkForUpdate")

    async def temporary_disable_blocking(self, minutes):
        """Temporarily disable ad blocking."""
        return await self.fetch_data(
            "api/settings/temporaryDisableBlocking", params={"minutes": minutes}
        )

    async def get_dns_settings(self):
        """Get DNS settings from the API."""
        return await self.fetch_data("api/settings/get")

    async def set_ad_blocking(self, enable):
        """Set ad blocking state."""
        params = {"token": self._token, "enableBlocking": str(enable).lower()}
        url = f"{self._api_url}/api/settings/set"

        async with aiohttp.ClientSession() as session:
            try:
                with async_timeout.timeout(10):
                    _LOGGER.debug("Requesting URL: %s", url)
                    async with session.get(url, params=params) as response:
                        response.raise_for_status()
                        data = await response.json()
                        _LOGGER.debug("Response: %s", data)
                        if data.get("status") != "ok":
                            raise Exception(
                                f"Error setting ad blocking: {data.get('errorMessage')}"
                            )
                        return data
            except aiohttp.ClientError as err:
                _LOGGER.error("Error setting ad blocking: %s", err)
                raise Exception(f"Error setting ad blocking: {err}") from err
            except asyncio.TimeoutError as e:
                _LOGGER.error("Timeout error setting ad blocking")
                raise Exception("Timeout error setting ad blocking") from e
            except Exception as e:
                _LOGGER.error("An error occurred: %s", e)
                raise Exception(f"An error occurred: {e}") from e
