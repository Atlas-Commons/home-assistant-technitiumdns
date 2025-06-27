"""
Technitium DNS API Client

IMPORTANT: DNS Query Logging Requirements
========================================
According to the official Technitium DNS API documentation, the /api/logs/query endpoint
is specifically designed for DNS apps, not general DNS server logs.

To use DNS query logging for device tracking, you need to:
1. Install a DNS app that supports query logging (isQueryLogger = true)
2. The app must be properly configured and running
3. The API requires both 'name' and 'classPath' parameters for the specific DNS app

Without a logging DNS app installed, device tracking will rely on:
- DHCP lease information
- Network ping/connectivity checks
- Alternative discovery methods

Popular DNS apps that support logging include various monitoring and analytics apps
available in the Technitium DNS App Store.

API Verification Summary (Based on Official Technitium DNS Documentation)
=========================================================================

VERIFIED FINDINGS:
1. The /api/logs/query endpoint is ONLY for DNS apps, not general DNS server logs
2. Requires mandatory parameters: 'name' (app name) and 'classPath' (app class)
3. General DNS query logs are NOT accessible through the current API
4. DNS apps must have 'isQueryLogger: true' to support query logging

WORKING ENDPOINTS VERIFIED:
- /api/dashboard/stats/get (stats and metrics)
- /api/dashboard/stats/getTop (top clients, domains)  
- /api/dhcp/leases/list (DHCP leases)
- /api/dhcp/scopes/list (DHCP scopes)
- /api/apps/list (installed DNS apps)
- /api/logs/list (log files list)
- /api/settings/get (DNS settings)

DEVICE TRACKING ALTERNATIVES:
1. DHCP lease information (IP to MAC mapping)
2. Top clients from dashboard stats
3. Network connectivity checks (ping)
4. DNS app-based logging (if available)

RECOMMENDATIONS:
1. Install a DNS app that supports query logging for full device tracking
2. Use DHCP leases as primary device discovery method
3. Supplement with dashboard stats for activity monitoring
4. Document these limitations for users
"""

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
                            # _LOGGER.debug("Response: %s", data)
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
        
        NOTE: The /api/logs/query endpoint is specifically for DNS apps, not general DNS logs.
        According to Technitium DNS API documentation, this endpoint requires:
        - name: The name of the installed DNS app
        - classPath: The class path of the DNS app
        
        This method currently cannot access general DNS server query logs through the API.
        
        Args:
            start_date: Start date in ISO format (optional)
            end_date: End date in ISO format (optional) 
            client_ip: Filter by specific client IP (optional)
            query_type: Filter by query type like A, AAAA, etc (optional)
            limit: Maximum number of entries to return (default 1000)
        """
        _LOGGER.warning("DNS logs endpoint (/api/logs/query) is for DNS apps only, not general DNS server logs")
        _LOGGER.warning("General DNS query logs may not be accessible through the current API")
        
        # This endpoint requires DNS app parameters which we don't have
        # Keeping the old implementation for compatibility but it won't work for general logs
        params = {"entriesPerPage": limit, "pageNumber": 1}
        
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date
        if client_ip:
            params["clientIpAddress"] = client_ip
        if query_type:
            params["qtype"] = query_type
            
        try:
            return await self.fetch_data("api/logs/query", params)
        except Exception as e:
            _LOGGER.debug("DNS logs query failed as expected (requires DNS app parameters): %s", e)
            return {"status": "error", "errorMessage": "DNS logs endpoint requires DNS app configuration"}

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
        
        # First, test if DNS logs API is available
        api_test = await self.test_dns_logs_api()
        _LOGGER.debug("DNS logs API test result: %s", api_test)
        
        if not api_test.get("available", False):
            _LOGGER.warning("DNS logs API is not available: %s", api_test.get("message", "Unknown error"))
            _LOGGER.warning("Device last seen times will not be updated from DNS logs")
            _LOGGER.warning("Devices will only show as connected if they have active DHCP leases")
            return {}
        
        try:
            # Dynamic limit based on number of devices and expected activity
            # More devices = higher limit to ensure we capture all activity
            base_limit = 2000
            device_multiplier = max(1, len(ip_addresses) // 10)  # +200 per 10 devices
            dynamic_limit = min(10000, base_limit + (device_multiplier * 200))
            
            _LOGGER.debug("Using dynamic limit of %d entries for %d devices", dynamic_limit, len(ip_addresses))
            _LOGGER.debug("DNS log query time range: %s to %s (%d hours)", 
                         start_time.isoformat() + "Z", end_time.isoformat() + "Z", hours_back)
            
            # First, try to find DNS apps that support logging
            logging_apps = await self.get_dns_logging_apps()
            
            if logging_apps:
                _LOGGER.debug("Found %d DNS apps with logging capability, trying first one", len(logging_apps))
                first_app = logging_apps[0]
                
                # Use DNS app for logging
                logs_response = await self.get_dns_logs_via_app(
                    app_name=first_app["name"],
                    app_class=first_app["classPath"],
                    start_date=start_time.isoformat() + "Z",
                    end_date=end_time.isoformat() + "Z",
                    limit=dynamic_limit
                )
                
                _LOGGER.debug("Using DNS app '%s' for logging", first_app["name"])
            else:
                _LOGGER.debug("No DNS apps with logging found, trying direct API call")
                # Fallback to direct API call (will likely fail but worth trying)
                logs_response = await self.get_dns_logs(
                    start_date=start_time.isoformat() + "Z",
                    end_date=end_time.isoformat() + "Z",
                    limit=dynamic_limit
                )
            
            if logs_response.get("status") != "ok":
                error_msg = logs_response.get("errorMessage", logs_response.get("status", "Unknown error"))
                _LOGGER.debug("DNS logs API returned non-ok status: %s", error_msg)
                _LOGGER.warning("DNS logs query failed: %s", error_msg)
                return {}
            
            entries = logs_response.get("response", {}).get("entries", [])
            _LOGGER.debug("Retrieved %d DNS log entries for batch processing", len(entries))
            
            # Debug: Log the target IPs we're looking for
            _LOGGER.debug("Looking for DNS activity from IPs: %s", ip_addresses)
            
            # Debug: Sample a few entries to see the structure
            if entries:
                _LOGGER.debug("Sample DNS log entry structure: %s", entries[0])
                # Log unique client IPs found in the logs
                unique_client_ips = set()
                for entry in entries[:50]:  # Check first 50 entries
                    client_ip = entry.get("clientIpAddress")
                    if client_ip:
                        unique_client_ips.add(client_ip)
                _LOGGER.debug("Sample client IPs found in DNS logs: %s", sorted(list(unique_client_ips)))
            else:
                _LOGGER.warning("No DNS log entries returned from API - this could indicate:")
                _LOGGER.warning("  1. DNS server is not logging queries")
                _LOGGER.warning("  2. No DNS activity in the last %d hours", hours_back)
                _LOGGER.warning("  3. DNS logging is disabled in Technitium settings")
                _LOGGER.warning("  4. API permissions don't include log access")
                _LOGGER.warning("  5. Different API endpoint or parameters needed")
                return {}
            
            # Create a set for faster IP lookup
            target_ips = set(ip_addresses)
            
            # Dictionary to store last seen times {ip: timestamp}
            last_seen_times = {}
            processed_entries = 0
            matched_entries = 0
            
            # Process entries from newest to oldest (they should already be sorted by timestamp desc)
            for entry in entries:
                processed_entries += 1
                client_ip = entry.get("clientIpAddress")
                timestamp = entry.get("timestamp")
                
                # Debug every 1000th entry to avoid log spam
                if processed_entries % 1000 == 0:
                    _LOGGER.debug("Processed %d entries so far, found %d matches", processed_entries, matched_entries)
                
                if client_ip and timestamp and client_ip in target_ips:
                    matched_entries += 1
                    # Only record if we haven't seen this IP yet (keep the most recent)
                    if client_ip not in last_seen_times:
                        last_seen_times[client_ip] = timestamp
                        _LOGGER.debug("Found last seen for %s: %s", client_ip, timestamp)
                        
                        # If we've found all target IPs, we can break early
                        if len(last_seen_times) == len(target_ips):
                            _LOGGER.debug("Found all %d target IPs, stopping early after processing %d entries", len(target_ips), processed_entries)
                            break
            
            _LOGGER.debug("DNS log processing complete: processed %d entries, found %d matches for %d target IPs", 
                         processed_entries, matched_entries, len(target_ips))
            
            _LOGGER.info("Batch DNS log query completed: found activity for %d/%d devices", 
                        len(last_seen_times), len(ip_addresses))
            
            # If we found no activity, let's try a test query for the first IP to debug
            if not last_seen_times and ip_addresses:
                test_ip = ip_addresses[0]
                _LOGGER.debug("No DNS activity found in batch query, testing individual query for %s", test_ip)
                try:
                    test_response = await self.get_dns_logs(
                        start_date=start_time.isoformat() + "Z",
                        end_date=end_time.isoformat() + "Z",
                        client_ip=test_ip,
                        limit=5
                    )
                    if test_response.get("status") == "ok":
                        test_entries = test_response.get("response", {}).get("entries", [])
                        _LOGGER.debug("Individual IP query for %s returned %d entries: %s", test_ip, len(test_entries), test_entries)
                    else:
                        _LOGGER.debug("Individual IP query failed: %s", test_response)
                except Exception as e:
                    _LOGGER.debug("Individual IP query exception: %s", e)
            
            return last_seen_times
            
        except Exception as e:
            _LOGGER.error("Error in batch DNS log query: %s", e)
            _LOGGER.error("This is expected behavior due to API limitations:")
            _LOGGER.error("  1. /api/logs/query endpoint requires DNS app parameters (name, classPath)")
            _LOGGER.error("  2. General DNS query logs are not accessible via the current API")
            _LOGGER.error("  3. DNS logging may be disabled or require a logging DNS app")
            _LOGGER.error("  4. Consider installing a DNS app that supports query logging")
            _LOGGER.info("Device tracking will use alternative methods (DHCP leases, ping, etc.)")
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

    async def test_dns_logs_api(self):
        """Test if DNS logs API is accessible and working.
        
        Returns:
            dict: Test results with status and details
        """
        try:
            # Based on API documentation, /api/logs/query requires DNS app parameters
            _LOGGER.debug("Checking for DNS apps with logging capability...")
            
            try:
                apps_response = await self.fetch_data("api/apps/list")
                if apps_response.get("status") == "ok":
                    apps = apps_response.get("response", {}).get("apps", [])
                    logging_apps = []
                    
                    for app in apps:
                        dns_apps = app.get("dnsApps", [])
                        for dns_app in dns_apps:
                            if dns_app.get("isQueryLogger", False):
                                logging_apps.append({
                                    "name": app.get("name"),
                                    "classPath": dns_app.get("classPath")
                                })
                    
                    if logging_apps:
                        _LOGGER.info("Found %d DNS apps with logging capability", len(logging_apps))
                        
                        # Try to query logs using the first logging app
                        first_app = logging_apps[0]
                        from datetime import datetime, timedelta
                        
                        end_time = datetime.utcnow()
                        start_time = end_time - timedelta(hours=1)
                        
                        params = {
                            "name": first_app["name"],
                            "classPath": first_app["classPath"],
                            "entriesPerPage": 5,
                            "pageNumber": 1,
                            "start": start_time.isoformat() + "Z",
                            "end": end_time.isoformat() + "Z"
                        }
                        
                        response = await self.fetch_data("api/logs/query", params)
                        
                        if response.get("status") == "ok":
                            entries = response.get("response", {}).get("entries", [])
                            return {
                                "available": True,
                                "method": "dns_app_logging",
                                "app_name": first_app["name"],
                                "app_class": first_app["classPath"],
                                "entries_count": len(entries),
                                "sample_entry": entries[0] if entries else None,
                                "message": f"DNS logs accessible via {first_app['name']} app ({len(entries)} entries found)"
                            }
                        else:
                            return {
                                "available": False,
                                "method": "dns_app_logging",
                                "error": response.get("status"),
                                "message": f"DNS app logs query failed: {response.get('status')}"
                            }
                    else:
                        # Check if we can at least list log files (general logs)
                        _LOGGER.debug("No DNS apps with logging found, checking general log files...")
                        try:
                            list_response = await self.fetch_data("api/logs/list")
                            if list_response.get("status") == "ok":
                                log_files = list_response.get("response", {}).get("logFiles", [])
                                return {
                                    "available": False,
                                    "method": "file_logs_only",
                                    "log_files_count": len(log_files),
                                    "error": "no_query_logging",
                                    "message": f"Found {len(log_files)} log files but no DNS apps with query logging. Install a DNS app that supports query logging to track device activity."
                                }
                            else:
                                return {
                                    "available": False,
                                    "method": "no_access",
                                    "error": "no_logging_access",
                                    "message": "Cannot access DNS logs. Ensure DNS query logging is enabled and you have proper permissions."
                                }
                        except Exception as e2:
                            return {
                                "available": False,
                                "method": "no_access",
                                "error": str(e2),
                                "message": f"Cannot access DNS logs: {e2}"
                            }
                else:
                    return {
                        "available": False,
                        "method": "apps_api_failed",
                        "error": "apps_api_failed",
                        "message": f"Failed to list DNS apps: {apps_response.get('status')}"
                    }
                    
            except Exception as e:
                return {
                    "available": False,
                    "method": "dns_app_check",
                    "error": str(e),
                    "message": f"Error checking DNS apps: {e}"
                }
                
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "message": f"DNS logs API test failed: {e}"
            }

    async def get_dns_logging_apps(self):
        """Get list of DNS apps that support query logging.
        
        Returns:
            list: List of apps with logging capability
        """
        try:
            apps_response = await self.fetch_data("api/apps/list")
            if apps_response.get("status") == "ok":
                apps = apps_response.get("response", {}).get("apps", [])
                logging_apps = []
                
                for app in apps:
                    dns_apps = app.get("dnsApps", [])
                    for dns_app in dns_apps:
                        if dns_app.get("isQueryLogger", False):
                            logging_apps.append({
                                "name": app.get("name"),
                                "classPath": dns_app.get("classPath"),
                                "description": dns_app.get("description", "")
                            })
                
                return logging_apps
            else:
                _LOGGER.warning("Failed to list DNS apps: %s", apps_response.get("status"))
                return []
                
        except Exception as e:
            _LOGGER.debug("Error listing DNS apps: %s", e)
            return []

    async def get_dns_logs_via_app(self, app_name, app_class, start_date=None, end_date=None, client_ip=None, limit=1000):
        """Get DNS logs using a specific DNS app.
        
        Args:
            app_name: Name of the DNS app
            app_class: Class path of the DNS app
            start_date: Start date in ISO format (optional)
            end_date: End date in ISO format (optional) 
            client_ip: Filter by specific client IP (optional)
            limit: Maximum number of entries to return (default 1000)
        """
        params = {
            "name": app_name,
            "classPath": app_class,
            "entriesPerPage": limit,
            "pageNumber": 1
        }
        
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date
        if client_ip:
            params["clientIpAddress"] = client_ip
            
        return await self.fetch_data("api/logs/query", params)

    async def get_dns_logs_for_analysis(self, hours_back=2):
        """Get comprehensive DNS logs for smart activity analysis.
        
        Args:
            hours_back: How many hours back to search (default 2 for analysis window)
            
        Returns:
            list: List of DNS log entries with full details for analysis
        """
        from datetime import datetime, timedelta
        
        # Calculate start time
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        # First, test if DNS logs API is available
        api_test = await self.test_dns_logs_api()
        
        if not api_test.get("available", False):
            _LOGGER.warning("DNS logs API is not available for activity analysis: %s", 
                          api_test.get("message", "Unknown error"))
            return []
        
        try:
            # Use higher limit for analysis (need more comprehensive data)
            analysis_limit = 5000
            
            _LOGGER.debug("Getting DNS logs for activity analysis: %s to %s (%d hours, limit=%d)", 
                         start_time.isoformat() + "Z", end_time.isoformat() + "Z", 
                         hours_back, analysis_limit)
            
            # First, try to find DNS apps that support logging
            logging_apps = await self.get_dns_logging_apps()
            
            if logging_apps:
                _LOGGER.debug("Using DNS app '%s' for activity analysis logs", logging_apps[0]["name"])
                first_app = logging_apps[0]
                
                # Use DNS app for comprehensive logging
                logs_response = await self.get_dns_logs_via_app(
                    app_name=first_app["name"],
                    app_class=first_app["classPath"],
                    start_date=start_time.isoformat() + "Z",
                    end_date=end_time.isoformat() + "Z",
                    limit=analysis_limit
                )
                
                if logs_response.get("status") == "ok":
                    dns_logs = logs_response.get("response", {}).get("entries", [])
                    _LOGGER.info("Retrieved %d DNS log entries for activity analysis", len(dns_logs))
                    
                    # Debug: Show structure of first few entries
                    if dns_logs:
                        _LOGGER.debug("DNS log entry structure sample (first entry):")
                        _LOGGER.debug("Keys: %s", list(dns_logs[0].keys()) if dns_logs else "No entries")
                        _LOGGER.debug("Sample entry: %s", dns_logs[0] if dns_logs else "No entries")
                        
                        # Check for IPs in first 10 entries
                        client_ips = [entry.get('clientIpAddress', 'NO_IP') for entry in dns_logs[:10]]
                        _LOGGER.debug("Sample client IPs from first 10 entries: %s", client_ips)
                    
                    return dns_logs
                else:
                    _LOGGER.warning("DNS app logs query failed: %s", logs_response.get("errorMessage"))
                    return []
            else:
                _LOGGER.warning("No DNS apps with logging capability found for activity analysis")
                return []
                
        except Exception as e:
            _LOGGER.error("Error getting DNS logs for activity analysis: %s", e)
            return []
