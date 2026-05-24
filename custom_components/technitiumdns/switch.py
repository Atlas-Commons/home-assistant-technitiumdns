"""TechnitiumDNS ad blocking switch."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import AD_BLOCKING_SWITCH, DOMAIN, KEY_BLOCKING_DISABLED_UNTIL

_LOGGER = logging.getLogger(__name__)

BLOCKING_POLL_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up TechnitiumDNS switch entities based on a config entry."""
    config_entry = hass.data[DOMAIN][entry.entry_id]
    api = config_entry["api"]
    server_name = config_entry["server_name"]

    switches = [
        TechnitiumDNSSwitch(api, AD_BLOCKING_SWITCH, server_name, entry.entry_id, hass)
    ]
    async_add_entities(switches)


class TechnitiumDNSSwitch(SwitchEntity):
    """Representation of a TechnitiumDNS switch."""

    def __init__(self, api, name: str, server_name: str, entry_id: str, hass):
        """Initialize the switch."""
        self._api = api
        self._hass = hass
        self._entry_id = entry_id
        self._attr_name = f"{name} ({server_name})"
        self._is_on = False
        self._temporary_disable_until: datetime | None = None
        self._attr_unique_id = f"{entry_id}_{name}"
        self._unsub_poll = None

    @property
    def is_on(self):
        """Return the state of the switch."""
        return self._is_on

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {}
        if self._temporary_disable_until:
            attrs["temporary_disable_until"] = self._temporary_disable_until.isoformat()
        return attrs

    def _get_entry_data(self):
        """Return hass.data entry for this config entry."""
        return self._hass.data.get(DOMAIN, {}).get(self._entry_id, {})

    def _is_temporarily_disabled(self) -> bool:
        """Return True if ad blocking is temporarily disabled."""
        until = self._get_entry_data().get(KEY_BLOCKING_DISABLED_UNTIL)
        if until is None:
            return False
        if isinstance(until, str):
            until = dt_util.parse_datetime(until)
        if until is None:
            return False
        now = dt_util.utcnow()
        if until.tzinfo is not None:
            now = dt_util.as_utc(now)
        if now >= until:
            entry_data = self._get_entry_data()
            if entry_data:
                entry_data[KEY_BLOCKING_DISABLED_UNTIL] = None
            return False
        self._temporary_disable_until = until
        return True

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await self._fetch_state()
        self._unsub_poll = async_track_time_interval(
            self.hass,
            self._async_poll_blocking_state,
            BLOCKING_POLL_INTERVAL,
        )
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_blocking_changed",
                self._async_handle_blocking_changed,
            )
        )

    async def _async_handle_blocking_changed(self, event):
        """Refresh when a temporary-disable button is pressed."""
        if event.data.get("config_entry_id") == self._entry_id:
            await self._fetch_state()

    async def async_will_remove_from_hass(self):
        """Cancel polling when removed."""
        if self._unsub_poll:
            self._unsub_poll()
            self._unsub_poll = None

    async def _async_poll_blocking_state(self, _now=None):
        """Periodically refresh blocking state from the server."""
        await self._fetch_state()

    async def _fetch_state(self):
        """Fetch the current effective ad blocking state."""
        try:
            settings = await self._api.settings.get()
            until = self._get_entry_data().get(KEY_BLOCKING_DISABLED_UNTIL)
            if until and isinstance(until, str):
                until = dt_util.parse_datetime(until)
            self._temporary_disable_until = until if self._is_temporarily_disabled() else None

            effective_on = settings.enable_blocking and not self._is_temporarily_disabled()
            if self._is_on != effective_on:
                self._is_on = effective_on
                self.async_write_ha_state()
            elif self._temporary_disable_until:
                self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to fetch ad blocking state: %s", err)

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        try:
            await self._api.settings.set(settings={"enableBlocking": True})
            entry_data = self._get_entry_data()
            if entry_data:
                entry_data[KEY_BLOCKING_DISABLED_UNTIL] = None
            self._temporary_disable_until = None
            self._is_on = True
            _LOGGER.info("Ad blocking enabled on %s", self._attr_name)
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to enable ad blocking: %s", err)

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        try:
            await self._api.settings.set(settings={"enableBlocking": False})
            entry_data = self._get_entry_data()
            if entry_data:
                entry_data[KEY_BLOCKING_DISABLED_UNTIL] = None
            self._temporary_disable_until = None
            self._is_on = False
            _LOGGER.info("Ad blocking disabled on %s", self._attr_name)
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to disable ad blocking: %s", err)

    @property
    def device_info(self):
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._attr_name,
            manufacturer="Technitium",
            model="DNS Server",
        )
