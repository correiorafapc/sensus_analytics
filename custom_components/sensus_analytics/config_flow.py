"""Config flow for Sensus Analytics Integration."""

from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ACCOUNT_NUMBER,
    CONF_BASE_URL,
    CONF_METER_NUMBER,
    CONF_METER_TYPE,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    METER_TYPE_ELECTRIC,
    METER_TYPE_WATER,
)

_LOGGER = logging.getLogger(__name__)


class SensusAnalyticsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensus Analytics Integration."""

    VERSION = 1

    def is_matching(self, other_flow):
        return False

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            _LOGGER.debug("User input: %s", user_input)
            unique_id = f"{user_input[CONF_METER_TYPE]}_{user_input[CONF_ACCOUNT_NUMBER]}_{user_input[CONF_METER_NUMBER]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            valid = await self._test_credentials(user_input)
            if valid:
                meter_label = "Water" if user_input[CONF_METER_TYPE] == METER_TYPE_WATER else "Electric"
                return self.async_create_entry(
                    title=f"Sensus Analytics {meter_label}",
                    data=user_input,
                )
            errors["base"] = "auth"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_METER_TYPE, default=METER_TYPE_WATER): vol.In(
                    {METER_TYPE_WATER: "Water", METER_TYPE_ELECTRIC: "Electric"}
                ),
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_ACCOUNT_NUMBER): str,
                vol.Required(CONF_METER_NUMBER): str,
                vol.Required("unit_type", default="gal"): vol.In(["gal", "CCF", "kWh"]),
                vol.Optional("tier1_units"): cv.positive_float,
                vol.Required("tier1_price", default=0.01): cv.positive_float,
                vol.Optional("tier2_units"): cv.positive_float,
                vol.Optional("tier2_price"): cv.positive_float,
                vol.Optional("tier3_price"): cv.positive_float,
                vol.Required("service_fee", default=0.0): cv.positive_float,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _test_credentials(self, user_input) -> bool:
        """Test if the provided credentials are valid."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{user_input[CONF_BASE_URL]}/j_spring_security_check",
                    data={
                        "j_username": user_input[CONF_USERNAME],
                        "j_password": user_input[CONF_PASSWORD],
                    },
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    _LOGGER.debug("Auth response status: %s", response.status)
                    return response.status == 302
        except aiohttp.ClientError as error:
            _LOGGER.error("Error validating credentials: %s", error)
            return False

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry):
        return SensusAnalyticsOptionsFlow()


class SensusAnalyticsOptionsFlow(config_entries.OptionsFlow):
    """Handle Sensus Analytics options."""

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug("User updated options: %s", user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)
            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
            await coordinator.async_request_refresh()
            return self.async_create_entry(title="", data={})

        current = self.config_entry.data

        data_schema = vol.Schema(
            {
                vol.Required(CONF_METER_TYPE, default=current.get(CONF_METER_TYPE, METER_TYPE_WATER)): vol.In(
                    {METER_TYPE_WATER: "Water", METER_TYPE_ELECTRIC: "Electric"}
                ),
                vol.Required(CONF_BASE_URL, default=current.get(CONF_BASE_URL)): str,
                vol.Required(CONF_USERNAME, default=current.get(CONF_USERNAME)): str,
                vol.Required(CONF_PASSWORD, default=current.get(CONF_PASSWORD)): str,
                vol.Required(CONF_ACCOUNT_NUMBER, default=current.get(CONF_ACCOUNT_NUMBER)): str,
                vol.Required(CONF_METER_NUMBER, default=current.get(CONF_METER_NUMBER)): str,
                vol.Required("unit_type", default=current.get("unit_type", "gal")): vol.In(["gal", "CCF", "kWh"]),
                vol.Optional("tier1_units", default=current.get("tier1_units")): cv.positive_float,
                vol.Required("tier1_price", default=current.get("tier1_price", 0.01)): cv.positive_float,
                vol.Optional("tier2_units", default=current.get("tier2_units")): cv.positive_float,
                vol.Optional("tier2_price", default=current.get("tier2_price")): cv.positive_float,
                vol.Optional("tier3_price", default=current.get("tier3_price")): cv.positive_float,
                vol.Required("service_fee", default=current.get("service_fee", 0.0)): cv.positive_float,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
