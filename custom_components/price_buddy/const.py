"""Constants for the Price Buddy integration."""

from __future__ import annotations

DOMAIN = "price_buddy"
NAME = "Price Buddy"

CONF_API_TOKEN = "api_token"
CONF_CURRENCY = "currency"
CONF_INCLUDE_DETAILS = "include_details"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 1440
DEFAULT_INCLUDE_DETAILS = False

API_PAGE_SIZE = 100
API_MAX_PAGES = 1000

ATTR_PRODUCT_ID = "product_id"
ATTR_STATUS = "status"
ATTR_TARGET_PRICE = "target_price"
ATTR_TARGET_PERCENTAGE = "target_percentage"
ATTR_TARGET_REACHED = "target_reached"
ATTR_FAVORITE = "favorite"
ATTR_OFFICIAL_ONLY = "official_only"
ATTR_PAUSED = "paused"
ATTR_TAGS = "tags"
ATTR_CREATED_AT = "created_at"
ATTR_UPDATED_AT = "updated_at"
ATTR_STORE = "store"
ATTR_PRODUCT_URL = "product_url"
ATTR_STOCK_STATUS = "stock_status"
ATTR_TREND = "trend"
ATTR_LAST_SCRAPE = "last_scrape"
ATTR_LAST_SCRAPE_SUCCESSFUL = "last_scrape_successful"
ATTR_OFFERS = "offers"
ATTR_UNIT_PRICE = "unit_price"
ATTR_PRICE_FACTOR = "price_factor"

EVENT_PRICE_CHANGED = "price_buddy_price_changed"
