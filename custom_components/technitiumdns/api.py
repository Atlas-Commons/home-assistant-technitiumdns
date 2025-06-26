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

    @property
    def api_url(self):
        """Return the API URL."""
        return self._api_url

    @property
    def token(self):
        """Return the API token."""
        return self._token

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
                    if attempt == retries - 1:
                        raise Exception(f"Error fetching data from {endpoint} after {retries} attempts: {err}") from err
                    await asyncio.sleep(5)
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
                            raise Exception(f"Error setting ad blocking: {data.get('errorMessage')}")
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

    async def get_dhcp_leases(self):
        """Get DHCP leases from the API."""
        return await self.fetch_data("api/dhcp/leases/list")

    async def get_dhcp_scopes(self):
        """Get DHCP scopes from the API."""
        return await self.fetch_data("api/dhcp/scopes/list")

    async def get_dns_logs(self, start_date=None, end_date=None, client_ip=None, query_type=None, limit=1000):
        """Get DNS query logs from Technitium DNS server.
        
        Args:
            start_date: Start date in ISO format (optional)
            end_date: End date in ISO format (optional) 
            client_ip: Filter by specific client IP (optional)
            query_type: Filter by query type like A, AAAA, etc (optional)
            limit: Maximum number of entries to return (default 1000)
        """
        params = {"entriesPerPage": limit, "pageNumber": 1}
        
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date
        if client_ip:
            params["clientIpAddress"] = client_ip
        if query_type:
            params["qtype"] = query_type
            
        return await self.fetch_data("api/logs/query", params)

    async def get_last_seen_for_multiple_ips(self, ip_addresses, hours_back=24):
        """Get the last seen timestamp for multiple IP addresses from DNS logs in a single call.
        
        Args:
            ip_addresses: List of IP addresses to search for
            hours_back: How many hours back to search (default 24)
            
        Returns:
            dict: {ip_address: last_seen_timestamp} for all IPs found in logs
        """
        from datetime import datetime, timedelta
        
        if not ip_addresses:
            return {}
        
        # Calculate start time (X hours ago)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        try:
            # Dynamic limit based on number of devices and expected activity
            # More devices = higher limit to ensure we capture all activity
            base_limit = 2000
            device_multiplier = max(1, len(ip_addresses) // 10)  # +200 per 10 devices
            dynamic_limit = min(10000, base_limit + (device_multiplier * 200))
            
            _LOGGER.debug("Using dynamic limit of %d entries for %d devices", dynamic_limit, len(ip_addresses))
            
            # Get ALL recent DNS logs (no IP filtering)
            logs_response = await self.get_dns_logs(
                start_date=start_time.isoformat() + "Z",
                end_date=end_time.isoformat() + "Z",
                limit=dynamic_limit
            )
            
            if logs_response.get("status") != "ok":
                _LOGGER.debug("DNS logs API returned non-ok status: %s", logs_response.get("status"))
                return {}
            
            entries = logs_response.get("response", {}).get("entries", [])
            _LOGGER.debug("Retrieved %d DNS log entries for batch processing", len(entries))
            
            # Create a set for faster IP lookup
            target_ips = set(ip_addresses)
            
            # Dictionary to store last seen times {ip: timestamp}
            last_seen_times = {}
            
            # Process entries from newest to oldest (they should already be sorted by timestamp desc)
            for entry in entries:
                client_ip = entry.get("clientIpAddress")
                timestamp = entry.get("timestamp")
                
                if client_ip and timestamp and client_ip in target_ips:
                    # Only record if we haven't seen this IP yet (keep the most recent)
                    if client_ip not in last_seen_times:
                        last_seen_times[client_ip] = timestamp
                        _LOGGER.debug("Found last seen for %s: %s", client_ip, timestamp)
                        
                        # If we've found all target IPs, we can break early
                        if len(last_seen_times) == len(target_ips):
                            _LOGGER.debug("Found all %d target IPs, stopping early", len(target_ips))
                            break
            
            _LOGGER.info("Batch DNS log query completed: found activity for %d/%d devices", 
                        len(last_seen_times), len(ip_addresses))
            return last_seen_times
            
        except Exception as e:
            _LOGGER.debug("Error in batch DNS log query: %s", e)
            return {}

    async def get_last_seen_for_ip(self, ip_address, hours_back=24):
        """Get the last seen timestamp for a specific IP address from DNS logs.
        
        DEPRECATED: Use get_last_seen_for_multiple_ips for better performance.
        
        Args:
            ip_address: The IP address to search for
            hours_back: How many hours back to search (default 24)
            
        Returns:
            datetime string of last seen time, or None if not found
        """
        from datetime import datetime, timedelta
        
        # Calculate start time (X hours ago)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        try:
            logs_response = await self.get_dns_logs(
                start_date=start_time.isoformat() + "Z",
                end_date=end_time.isoformat() + "Z", 
                client_ip=ip_address,
                limit=1  # We only need the most recent entry
            )
            
            if logs_response.get("status") == "ok":
                entries = logs_response.get("response", {}).get("entries", [])
                if entries:
                    # Return the timestamp of the most recent entry
                    return entries[0].get("timestamp")
            
            return None
            
        except Exception as e:
            _LOGGER.debug("Error querying DNS logs for IP %s: %s", ip_address, e)
            return None
