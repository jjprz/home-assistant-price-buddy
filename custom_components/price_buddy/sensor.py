"""Sensor platform for Price Buddy products."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import absolute_http_url
from .const import (
    ATTR_CREATED_AT,
    ATTR_FAVORITE,
    ATTR_LAST_SCRAPE,
    ATTR_LAST_SCRAPE_SUCCESSFUL,
    ATTR_OFFERS,
    ATTR_OFFICIAL_ONLY,
    ATTR_PAUSED,
    ATTR_PRICE_FACTOR,
    ATTR_PRODUCT_ID,
    ATTR_PRODUCT_URL,
    ATTR_STATUS,
    ATTR_STOCK_STATUS,
    ATTR_STORE,
    ATTR_TAGS,
    ATTR_TARGET_PERCENTAGE,
    ATTR_TARGET_PRICE,
    ATTR_TARGET_REACHED,
    ATTR_TREND,
    ATTR_UNIT_PRICE,
    ATTR_UPDATED_AT,
    DOMAIN,
    EVENT_PRICE_CHANGED
)
from .coordinator import PriceBuddyDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one sensor for every Price Buddy product."""
    coordinator: PriceBuddyDataUpdateCoordinator = entry.runtime_data
    known_product_ids: set[str] = set()

    @callback
    def async_add_new_products() -> None:
        """Add sensors for products discovered after setup."""
        new_ids = set(coordinator.data) - known_product_ids
        if not new_ids:
            return
        known_product_ids.update(new_ids)
        async_add_entities(
            PriceBuddyProductSensor(coordinator, entry, product_id)
            for product_id in sorted(new_ids, key=_natural_id_sort_key)
        )

    async_add_new_products()
    entry.async_on_unload(
        coordinator.async_add_listener(async_add_new_products)
    )


def _natural_id_sort_key(value: str) -> tuple[int, int | str]:
    """Sort numeric product IDs numerically and other IDs lexically."""
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


class PriceBuddyProductSensor(
    CoordinatorEntity[PriceBuddyDataUpdateCoordinator], SensorEntity
):
    """Representation of one Price Buddy product."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: PriceBuddyDataUpdateCoordinator,
        entry: ConfigEntry,
        product_id: str,
    ) -> None:
        """Initialize a Price Buddy product sensor."""
        super().__init__(coordinator)
        self._product_id = product_id
        self._attr_unique_id = f"{entry.entry_id}_product_{product_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Price Buddy",
            model="Self-hosted price tracker",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.client.web_url,
        )

    async def async_added_to_hass(self) -> None:
        """Store the initial price when the entity is added."""
        await super().async_added_to_hass()
        self._last_price = self.native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator updates and fire an event on price changes."""
        previous_price = getattr(self, "_last_price", None)
        current_price = self.native_value

        if (
            previous_price is not None
            and current_price is not None
            and previous_price != current_price
        ):
            product = self._product or {}
            listing = self._best_listing

            self.hass.bus.async_fire(
                EVENT_PRICE_CHANGED,
                {
                    "entity_id": self.entity_id,
                    "product_id": product.get("id", self._product_id),
                    "name": self.name,
                    "old_price": float(previous_price),
                    "new_price": float(current_price),
                    "currency": self.native_unit_of_measurement,
                    "target_price": _number(product.get("notify_price")),
                    "target_reached": self._target_reached,
                    "store": listing.get("store_name") if listing else None,
                    "url": (
                        absolute_http_url(
                            self.coordinator.client.web_url,
                            listing.get("url"),
                        )
                        if listing
                        else None
                    ),
                },
            )

        self._last_price = current_price
        super()._handle_coordinator_update()

    @property
    def _product(self) -> dict[str, Any] | None:
        """Return the latest product payload."""
        return self.coordinator.data.get(self._product_id)

    @property
    def available(self) -> bool:
        """Return whether the product still exists and data is current."""
        return super().available and self._product is not None

    @property
    def name(self) -> str:
        """Return the product title."""
        product = self._product
        if product and product.get("title"):
            return str(product["title"])
        return f"Product {self._product_id}"

    @property
    def native_value(self) -> Decimal | None:
        """Return the current product price."""
        product = self._product
        if product is None:
            return None
        value = _decimal(product.get("current_price"))
        return value if value is not None and value > 0 else None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the product currency."""
        listing = self._best_listing
        if listing:
            currency = listing.get("currency")
            if isinstance(currency, str) and len(currency.strip()) == 3:
                return currency.strip().upper()
        return self.coordinator.currency

    @property
    def entity_picture(self) -> str | None:
        """Return the product image."""
        product = self._product
        if product is None:
            return None
        return absolute_http_url(
            self.coordinator.client.web_url, product.get("image")
        )

    @property
    def icon(self) -> str:
        """Return an icon reflecting price availability and target status."""
        if self.native_value is None:
            return "mdi:tag-off-outline"
        if self._target_reached:
            return "mdi:tag-check-outline"
        return "mdi:tag-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return stable, compact product metadata without price history."""
        product = self._product
        if product is None:
            return {ATTR_PRODUCT_ID: self._product_id}

        attributes: dict[str, Any] = {
            ATTR_PRODUCT_ID: product.get("id", self._product_id),
            ATTR_STATUS: _enum_value(product.get("status")),
            ATTR_TARGET_PRICE: _number(product.get("notify_price")),
            ATTR_TARGET_PERCENTAGE: _number(product.get("notify_percent")),
            ATTR_TARGET_REACHED: self._target_reached,
            ATTR_FAVORITE: _bool_or_none(product.get("favourite")),
            ATTR_OFFICIAL_ONLY: _bool_or_none(product.get("only_official")),
            ATTR_PAUSED: _bool_or_none(product.get("paused")),
            ATTR_TAGS: _tag_names(product.get("tags")),
            ATTR_CREATED_AT: product.get("created_at"),
            ATTR_UPDATED_AT: product.get("updated_at"),
        }

        listing = self._best_listing
        if listing is not None:
            attributes.update(
                {
                    ATTR_STORE: listing.get("store_name"),
                    ATTR_PRODUCT_URL: absolute_http_url(
                        self.coordinator.client.web_url, listing.get("url")
                    ),
                    ATTR_STOCK_STATUS: _stock_status(listing),
                    ATTR_TREND: _enum_value(listing.get("trend")),
                    ATTR_LAST_SCRAPE: listing.get("last_scrape"),
                    ATTR_LAST_SCRAPE_SUCCESSFUL: _bool_or_none(
                        listing.get("successful_last_scrape")
                    ),
                    ATTR_UNIT_PRICE: _number(listing.get("unit_price")),
                    ATTR_PRICE_FACTOR: _number(listing.get("price_factor")),
                }
            )

        price_cache = product.get("price_cache")
        if isinstance(price_cache, list):
            attributes[ATTR_OFFERS] = len(price_cache)

        return {key: value for key, value in attributes.items() if value is not None}

    @property
    def _target_reached(self) -> bool | None:
        """Return whether the current price is at or below the target."""
        product = self._product
        current = self.native_value
        if product is None or current is None:
            return None
        target = _decimal(product.get("notify_price"))
        if target is None or target <= 0:
            return None
        return current <= target

    @property
    def _best_listing(self) -> Mapping[str, Any] | None:
        """Return the currently cheapest in-stock listing when available."""
        product = self._product
        if product is None:
            return None
        cache = product.get("price_cache")
        if not isinstance(cache, list):
            return None

        listings = [item for item in cache if isinstance(item, Mapping)]
        if not listings:
            return None

        in_stock = [item for item in listings if _stock_status(item) == "in_stock"]
        candidates = in_stock or listings
        return min(candidates, key=_listing_price_sort_key)


def _listing_price_sort_key(listing: Mapping[str, Any]) -> Decimal:
    """Return a sortable listing price, putting missing prices last."""
    value = _decimal(listing.get("unit_price"))
    if value is None:
        value = _decimal(listing.get("price"))
    return value if value is not None and value > 0 else Decimal("Infinity")


def _decimal(value: Any) -> Decimal | None:
    """Convert API numeric data to a finite Decimal."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _number(value: Any) -> int | float | None:
    """Return a JSON-safe number."""
    result = _decimal(value)
    if result is None:
        return None
    if result == result.to_integral_value():
        return int(result)
    float_result = float(result)
    return float_result if isfinite(float_result) else None


def _bool_or_none(value: Any) -> bool | None:
    """Normalize common API boolean representations."""
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True"):
        return True
    if value in (0, "0", "false", "False"):
        return False
    return None


def _enum_value(value: Any) -> str | None:
    """Normalize scalar or enum-like JSON values."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        nested = value.get("value")
        return str(nested) if nested is not None else None
    return str(value)


def _tag_names(value: Any) -> list[str] | None:
    """Extract tag names from the optional included relationship."""
    if not isinstance(value, list):
        return None
    names: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            name = item.get("name") or item.get("title") or item.get("label")
            if name is not None:
                names.append(str(name))
        elif isinstance(item, str):
            names.append(item)
    return names or None


def _stock_status(listing: Mapping[str, Any]) -> str:
    """Normalize Price Buddy's null-means-in-stock representation."""
    value = listing.get("availability")
    if value is None or value == "":
        return "in_stock"
    normalized = _enum_value(value)
    return normalized or "out_of_stock"
