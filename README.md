<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/price_buddy/brand/dark_logo.png">
    <img src="custom_components/price_buddy/brand/logo.png" alt="Price Buddy" width="420">
  </picture>
</p>

# Price Buddy for Home Assistant

**English** · [Español](README.es.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Validate](https://github.com/jjprz/home-assistant-price-buddy/actions/workflows/validate.yml/badge.svg)](https://github.com/jjprz/home-assistant-price-buddy/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant custom integration for **[PriceBuddy](https://github.com/jez500/pricebuddy)** (`jez500/pricebuddy`), the self-hosted price tracker. It creates one sensor per product visible to your API token, so you can chart prices, build dashboards and get notified when a price drops or an item is back in stock.

## Features

Each product becomes an entity with:

- **State:** current price (`current_price`).
- **Unit:** the currency configured in Home Assistant, or the one set in the options.
- **Picture:** the product image, when available.
- **Attributes:** ID, status, target price, target percentage, favourite, tags and dates.
- **Detailed mode (optional):** cheapest store, purchase URL, stock status (`stock_status`), trend, last check, number of offers and the store's real currency.

New products are added without restarting Home Assistant. When a product is deleted in PriceBuddy, its entity becomes unavailable so its history is kept; you can remove it later from the entity registry.

No external Python dependencies: it uses Home Assistant's shared HTTP session.

## Installation

### HACS (recommended)

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/jjprz/home-assistant-price-buddy` with type **Integration**.
3. Search for **Price Buddy**, download it and restart Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jjprz&repository=home-assistant-price-buddy&category=integration)

### Manual

1. Copy `custom_components/price_buddy` to `/config/custom_components/price_buddy`.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services → Add integration** and search for **Price Buddy**.

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=price_buddy)

2. Enter your PriceBuddy URL and an API token.

### API token

In PriceBuddy, open the user menu (top right) → **API tokens** and create a token with permission to list/read products.

### URL

Any of these forms is accepted:

```text
http://192.168.1.50:8080
http://192.168.1.50:8080/api
https://pricebuddy.example.com
```

Do not include `/products`; if you add `/api/products` by mistake, the integration fixes it.

### Options

From **Configure** on the integration you can change:

- **Update interval:** 1–1440 minutes (default 15).
- **Currency:** fallback three-letter code; defaults to Home Assistant's currency.
- **Load detailed product data:** off by default to reduce traffic. When enabled, PriceBuddy also returns `price_cache`, which can include a lot of history.

## Price change event

Whenever a product's price changes, the integration fires `price_buddy_price_changed` with:

| Field | Description |
|---|---|
| `entity_id` | Sensor entity |
| `product_id` | PriceBuddy product ID |
| `name` | Product name |
| `old_price` / `new_price` | Previous and current price |
| `currency` | Currency |
| `target_price` | Target price set in PriceBuddy |
| `target_reached` | `true` if the new price meets the target |
| `store` / `url` | Cheapest store and its link (detailed mode) |

### Example automation

```yaml
automation:
  - alias: "Notify Price Buddy price changes"
    triggers:
      - trigger: event
        event_type: price_buddy_price_changed
    actions:
      - action: notify.notify
        data:
          title: "{{ trigger.event.data.name }}"
          message: >-
            {{ trigger.event.data.old_price }} → {{ trigger.event.data.new_price }}
            {{ trigger.event.data.currency }}
            {% if trigger.event.data.store %}at {{ trigger.event.data.store }}{% endif %}
```

## Example entity

A product called "Coffee maker" creates an entity similar to:

```text
sensor.price_buddy_192_168_1_50_coffee_maker
```

Home Assistant assigns the exact ID, and you can rename it from the UI.

## Requirements

- Home Assistant 2025.1 or newer.
- PriceBuddy with the products REST API available at `/api/products`.

## Troubleshooting

- **Invalid token:** create a new one and make sure you copy it in full.
- **Insufficient permissions:** grant the token product read/list permission.
- **Incompatible response:** check the URL points to `jez500/pricebuddy` and not to another app with the same name.
- **Self-signed certificate:** disable SSL verification only on a trusted network.

Diagnostics can be downloaded from the integration page (sensitive data is redacted). Please attach them when [opening an issue](https://github.com/jjprz/home-assistant-price-buddy/issues).

## Disclaimer

This is a community integration, not affiliated with the PriceBuddy project.

## License

[MIT](LICENSE)
