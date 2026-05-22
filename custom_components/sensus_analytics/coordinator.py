"""DataUpdateCoordinator for Sensus Analytics Integration."""

import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACCOUNT_NUMBER,
    CONF_BASE_URL,
    CONF_METER_NUMBER,
    CONF_METER_TYPE,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    METER_TYPE_WATER,
)

_LOGGER = logging.getLogger(__name__)


class SensusAnalyticsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Sensus Analytics API."""

    def __init__(self, hass: HomeAssistant, config_entry):
        """Initialize."""
        self.hass = hass
        self.base_url = config_entry.data[CONF_BASE_URL]
        self.username = config_entry.data[CONF_USERNAME]
        self.password = config_entry.data[CONF_PASSWORD]
        self.account_number = config_entry.data[CONF_ACCOUNT_NUMBER]
        self.meter_number = config_entry.data[CONF_METER_NUMBER]
        self.meter_type = config_entry.data.get(CONF_METER_TYPE, METER_TYPE_WATER)
        self.config_entry = config_entry

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.meter_type}",
            update_interval=timedelta(minutes=30),
        )

    @property
    def _url_prefix(self):
        """Return the API URL prefix for this meter type."""
        return "water" if self.meter_type == METER_TYPE_WATER else "electric"

    async def _async_update_data(self):
        """Fetch data from the API."""
        _LOGGER.debug("Async update started for %s meter", self.meter_type)
        try:
            jar = aiohttp.CookieJar(unsafe=True)  # Required: default jar rejects cookies from non-public domains
            async with aiohttp.ClientSession(cookie_jar=jar) as session:
                await self._authenticate(session)

                data = await self._fetch_daily_data(session)

                today_hourly, yesterday_hourly = await self._fetch_hourly_data(session)

                if today_hourly:
                    data["today_hourly_data"] = today_hourly
                else:
                    data["today_hourly_data"] = []

                if yesterday_hourly:
                    data["hourly_usage_data"] = yesterday_hourly
                else:
                    _LOGGER.warning("Failed to fetch yesterday hourly data for %s meter", self.meter_type)

                return data

        except UpdateFailed:
            raise
        except Exception as error:
            _LOGGER.error("Unexpected error fetching %s data: %s", self.meter_type, error)
            raise UpdateFailed(f"Unexpected error: {error}") from error

    async def _authenticate(self, session: aiohttp.ClientSession):
        """Authenticate and store session cookie."""
        login_url = urljoin(self.base_url, "j_spring_security_check")
        _LOGGER.debug("Authenticating at: %s", login_url)
        async with session.post(
            login_url,
            data={"j_username": self.username, "j_password": self.password},
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status != 302:
                _LOGGER.error("Authentication failed with status %s", response.status)
                raise UpdateFailed("Authentication failed")
            _LOGGER.debug("Authentication successful")

    async def _fetch_daily_data(self, session: aiohttp.ClientSession):
        """Fetch daily meter data from the widget API."""
        widget_url = urljoin(self.base_url, f"{self._url_prefix}/widget/byPage")
        _LOGGER.debug("Widget URL: %s", widget_url)
        async with session.post(
            widget_url,
            json={
                "group": "meters",
                "accountNumber": self.account_number,
                "deviceId": self.meter_number,
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            response.raise_for_status()
            data = await response.json()

        _LOGGER.debug("Raw widget response: %s", data)
        data = data.get("widgetList")[0].get("data").get("devices")[0]
        _LOGGER.debug("Parsed device data: %s", data)
        return data

    async def _fetch_hourly_data(self, session: aiohttp.ClientSession):
        """Fetch today's and yesterday's hourly usage data.

        Returns (today_entries, yesterday_entries). today_entries is None if
        the API reports today's data is not yet available (showToday=False).
        """
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        now_local = datetime.now(local_tz)

        # Try today first — use showToday flag to confirm data is available
        today_raw = await self._fetch_hourly_data_for_date(session, now_local)
        today_entries = None
        if today_raw and today_raw.get("showToday"):
            today_entries = self._process_hourly_data_response(today_raw)
            _LOGGER.debug("Today hourly data available: %s entries", len(today_entries) if today_entries else 0)
        else:
            _LOGGER.debug("Today hourly data not yet available (showToday=False)")

        # Always fetch yesterday for comparison sensors
        yesterday_raw = await self._fetch_hourly_data_for_date(session, now_local - timedelta(days=1))
        yesterday_entries = self._process_hourly_data_response(yesterday_raw) if yesterday_raw else None

        return today_entries, yesterday_entries

    async def _fetch_hourly_data_for_date(self, session: aiohttp.ClientSession, target_date: datetime):
        """Fetch raw hourly JSON for a specific date."""
        start_ts, end_ts = self._get_start_end_timestamps(target_date)
        usage_url = urljoin(
            self.base_url,
            f"{self._url_prefix}/usage/{self.account_number}/{self.meter_number}",
        )

        # Note: "page" param intentionally omitted — sending "null" caused 400 Bad Request
        params = {
            "start": start_ts,
            "end": end_ts,
            "zoom": "day",
            "weather": "1",
        }

        _LOGGER.debug("Hourly data URL: %s, params: %s", usage_url, params)

        try:
            async with session.get(
                usage_url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                data = await response.json()
            _LOGGER.debug("Hourly data response: %s", data)
            return data
        except aiohttp.ClientError as e:
            _LOGGER.error("Hourly data request failed: %s", e)
            return None
        except (KeyError, TypeError, ValueError) as e:
            _LOGGER.error("Error processing hourly data response: %s", e)
            return None

    def _get_start_end_timestamps(self, target_date):
        """Get start and end timestamps in milliseconds for a given date."""
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        start_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=local_tz)
        end_dt = datetime.combine(target_date, datetime.max.time(), tzinfo=local_tz)
        return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)

    def _process_hourly_data_response(self, hourly_data):
        """Process and structure the hourly data response."""
        if not isinstance(hourly_data, dict):
            _LOGGER.error("Unexpected response format for hourly data.")
            return None

        if not hourly_data.get("operationSuccess", False):
            _LOGGER.error("API returned errors: %s", hourly_data.get("errors", []))
            return None

        usage_list = hourly_data.get("data", {}).get("usage", [])
        if not usage_list or len(usage_list) < 2:
            _LOGGER.error("Hourly usage data is missing or incomplete.")
            return None

        # First element contains units
        units = usage_list[0]
        usage_unit = units[0]
        rain_unit = units[1]
        temp_unit = units[2]

        hourly_entries = []
        for entry in usage_list[1:]:
            # Note: water API returns [timestamp, usage, rain, temp]
            #       electric API returns [timestamp, usage, temp, rain]
            if self.meter_type == METER_TYPE_WATER:
                timestamp, usage, rain, temp = entry[:4]
            else:
                timestamp, usage, temp, rain = entry[:4]

            hourly_entries.append({
                "timestamp": timestamp,
                "usage": usage,
                "rain": rain,
                "temp": temp,
                "usage_unit": usage_unit,
                "rain_unit": rain_unit,
                "temp_unit": temp_unit,
            })

        return hourly_entries
