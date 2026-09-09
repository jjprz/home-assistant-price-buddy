"""Config flow for Price Buddy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    PriceBuddyApiClient,
    PriceBuddyAuthenticationError,
    PriceBuddyCannotConnectError,
    PriceBuddyInvalidResponseError,
    PriceBuddyPermissionError,
    PriceBuddyRequestError,
    build_unique_id,
    normalize_api_url,
)
from .const import (
    CONF_API_TOKEN,
    CONF_CURRENCY,
    CONF_INCLUDE_DETAILS,
    CONF_SCAN_INTERVAL,
    DEFAULT_INCLUDE_DETAILS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


def _currency(value: Any) -> str:
    """Validate and normalize an ISO 4217-style currency code."""
    result = str(value).strip().upper()
    if len(result) != 3 or not result.isalpha() or not result.isascii():
        raise vol.Invalid("Currency must contain three ASCII letters")
    return result


def _connection_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Return the connection form schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_URL, default=defaults.get(CONF_URL, "http://pricebuddy.local")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            vol.Required(
                CONF_API_TOKEN, default=defaults.get(CONF_API_TOKEN, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Required(
                CONF_CURRENCY, default=defaults.get(CONF_CURRENCY, "EUR")
            ): selector.TextSelector(),
            vol.Required(
                CONF_INCLUDE_DETAILS,
                default=defaults.get(
                    CONF_INCLUDE_DETAILS, DEFAULT_INCLUDE_DETAILS
                ),
            ): selector.BooleanSelector(),
        }
    )


def _options_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Return the options form schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Required(
                CONF_CURRENCY, default=defaults.get(CONF_CURRENCY, "EUR")
            ): selector.TextSelector(),
            vol.Required(
                CONF_INCLUDE_DETAILS,
                default=defaults.get(
                    CONF_INCLUDE_DETAILS, DEFAULT_INCLUDE_DETAILS
                ),
            ): selector.BooleanSelector(),
        }
    )


async def _async_validate(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> str:
    """Validate user input and return the normalized API URL."""
    api_url = normalize_api_url(str(data[CONF_URL]))
    session = async_get_clientsession(
        hass, verify_ssl=bool(data.get(CONF_VERIFY_SSL, True))
    )
    client = PriceBuddyApiClient(
        session, api_url, str(data[CONF_API_TOKEN]).strip()
    )
    await client.async_validate_connection()
    return api_url


class PriceBuddyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Price Buddy."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: ConfigEntry) -> OptionsFlow:
        """Return the Price Buddy options flow."""
        return PriceBuddyOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}
        defaults: dict[str, Any] = {
            CONF_CURRENCY: self.hass.config.currency,
        }
        if user_input is not None:
            defaults.update(user_input)
            try:
                currency = _currency(user_input[CONF_CURRENCY])
                api_url = await _async_validate(self.hass, user_input)
            except vol.Invalid:
                errors[CONF_CURRENCY] = "invalid_currency"
            except ValueError:
                errors[CONF_URL] = "invalid_url"
            except PriceBuddyAuthenticationError:
                errors["base"] = "invalid_auth"
            except PriceBuddyPermissionError:
                errors["base"] = "insufficient_permissions"
            except PriceBuddyCannotConnectError:
                errors["base"] = "cannot_connect"
            except PriceBuddyInvalidResponseError:
                errors["base"] = "invalid_response"
            except PriceBuddyRequestError:
                errors["base"] = "unknown"
            else:
                token = str(user_input[CONF_API_TOKEN]).strip()
                await self.async_set_unique_id(build_unique_id(api_url, token))
                self._abort_if_unique_id_configured()

                hostname = urlsplit(api_url).hostname or "Price Buddy"
                return self.async_create_entry(
                    title=f"Price Buddy ({hostname})",
                    data={
                        CONF_URL: api_url,
                        CONF_API_TOKEN: token,
                        CONF_VERIFY_SSL: bool(user_input[CONF_VERIFY_SSL]),
                    },
                    options={
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                        CONF_CURRENCY: currency,
                        CONF_INCLUDE_DETAILS: bool(
                            user_input[CONF_INCLUDE_DETAILS]
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(defaults),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and replace an expired API token."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = {
                **entry.data,
                CONF_API_TOKEN: str(user_input[CONF_API_TOKEN]).strip(),
            }
            try:
                await _async_validate(self.hass, candidate)
            except PriceBuddyAuthenticationError:
                errors["base"] = "invalid_auth"
            except PriceBuddyPermissionError:
                errors["base"] = "insufficient_permissions"
            except PriceBuddyCannotConnectError:
                errors["base"] = "cannot_connect"
            except (PriceBuddyInvalidResponseError, PriceBuddyRequestError):
                errors["base"] = "invalid_response"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_API_TOKEN: candidate[CONF_API_TOKEN]
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
        )


class PriceBuddyOptionsFlow(OptionsFlow):
    """Handle Price Buddy options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Price Buddy options."""
        errors: dict[str, str] = {}
        defaults = {
            CONF_SCAN_INTERVAL: self.config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
            CONF_CURRENCY: self.config_entry.options.get(
                CONF_CURRENCY, self.hass.config.currency
            ),
            CONF_INCLUDE_DETAILS: self.config_entry.options.get(
                CONF_INCLUDE_DETAILS, DEFAULT_INCLUDE_DETAILS
            ),
        }
        if user_input is not None:
            defaults.update(user_input)
            try:
                currency = _currency(user_input[CONF_CURRENCY])
            except vol.Invalid:
                errors[CONF_CURRENCY] = "invalid_currency"
            else:
                return self.async_create_entry(
                    data={
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                        CONF_CURRENCY: currency,
                        CONF_INCLUDE_DETAILS: bool(
                            user_input[CONF_INCLUDE_DETAILS]
                        ),
                    }
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(defaults),
            errors=errors,
        )
