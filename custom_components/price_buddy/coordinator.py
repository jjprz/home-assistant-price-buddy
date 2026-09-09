"""Data update coordinator for Price Buddy."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PriceBuddyApiClient,
    PriceBuddyAuthenticationError,
    PriceBuddyCannotConnectError,
    PriceBuddyInvalidResponseError,
    PriceBuddyPermissionError,
    PriceBuddyRequestError,
)
from .const import (
    CONF_CURRENCY,
    CONF_INCLUDE_DETAILS,
    CONF_SCAN_INTERVAL,
    DEFAULT_INCLUDE_DETAILS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class PriceBuddyDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, dict[str, Any]]]
):
    """Coordinate polling of all Price Buddy products."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: PriceBuddyApiClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.entry = entry
        self.currency = str(
            entry.options.get(CONF_CURRENCY, hass.config.currency)
        ).upper()
        self.include_details = bool(
            entry.options.get(CONF_INCLUDE_DETAILS, DEFAULT_INCLUDE_DETAILS)
        )
        interval = int(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=interval),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch all products from Price Buddy."""
        try:
            return await self.client.async_get_products(
                include_details=self.include_details
            )
        except (PriceBuddyAuthenticationError, PriceBuddyPermissionError) as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (
            PriceBuddyCannotConnectError,
            PriceBuddyInvalidResponseError,
            PriceBuddyRequestError,
        ) as err:
            raise UpdateFailed(str(err)) from err
