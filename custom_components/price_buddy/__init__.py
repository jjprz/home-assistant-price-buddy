"""The Price Buddy integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PriceBuddyApiClient
from .const import CONF_API_TOKEN
from .coordinator import PriceBuddyDataUpdateCoordinator

PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Price Buddy from a config entry."""
    session = async_get_clientsession(
        hass, verify_ssl=bool(entry.data.get(CONF_VERIFY_SSL, True))
    )
    client = PriceBuddyApiClient(
        session,
        entry.data[CONF_URL],
        entry.data[CONF_API_TOKEN],
    )
    coordinator = PriceBuddyDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Price Buddy config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Price Buddy after an options change."""
    await hass.config_entries.async_reload(entry.entry_id)
