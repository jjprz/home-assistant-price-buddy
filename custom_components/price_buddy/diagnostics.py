"""Diagnostics support for Price Buddy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_TOKEN
from .coordinator import PriceBuddyDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return privacy-conscious diagnostics for a Price Buddy entry."""
    coordinator: PriceBuddyDataUpdateCoordinator = entry.runtime_data
    products = []
    for product_id, product in coordinator.data.items():
        products.append(
            {
                "id": product_id,
                "status": product.get("status"),
                "has_title": bool(product.get("title")),
                "has_image": bool(product.get("image")),
                "has_current_price": product.get("current_price") is not None,
                "has_price_cache": isinstance(product.get("price_cache"), list),
            }
        )

    return {
        "config_entry": async_redact_data(dict(entry.data), {CONF_API_TOKEN}),
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "product_count": len(coordinator.data),
        "products": products,
    }
