"""Asynchronous client for the Price Buddy REST API."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_MAX_PAGES, API_PAGE_SIZE

_REQUEST_TIMEOUT = ClientTimeout(total=30)

# Keeping the default response small matters because an unrestricted Price Buddy
# product response may contain up to a year of price history for every store URL.
_SPARSE_PRODUCT_FIELDS = ",".join(
    (
        "id",
        "title",
        "image",
        "status",
        "notify_price",
        "notify_percent",
        "favourite",
        "only_official",
        "current_price",
        "created_at",
        "updated_at",
    )
)


class PriceBuddyError(Exception):
    """Base exception for Price Buddy errors."""


class PriceBuddyCannotConnectError(PriceBuddyError):
    """Raised when Price Buddy cannot be reached."""


class PriceBuddyAuthenticationError(PriceBuddyError):
    """Raised when the API token is invalid."""


class PriceBuddyPermissionError(PriceBuddyError):
    """Raised when the API token lacks a required permission."""


class PriceBuddyInvalidResponseError(PriceBuddyError):
    """Raised when Price Buddy returns an unexpected response."""


class PriceBuddyRequestError(PriceBuddyError):
    """Raised for a non-authentication HTTP error."""


def normalize_api_url(raw_url: str) -> str:
    """Return a normalized Price Buddy API base URL.

    Both the application URL and an URL ending in /api are accepted. A URL
    ending in /api/products is also corrected for convenience.
    """
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("The URL is empty")

    value = raw_url.strip()
    if "://" not in value:
        value = f"http://{value}"

    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported")
    if not parsed.hostname:
        raise ValueError("The URL has no host")
    if parsed.username or parsed.password:
        raise ValueError("Credentials must not be embedded in the URL")

    path = parsed.path.rstrip("/")
    if path.endswith("/api/products"):
        path = path[: -len("/products")]
    elif not path.endswith("/api"):
        path = f"{path}/api" if path else "/api"

    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc, path, "", "")
    ).rstrip("/")


def web_url_from_api_url(api_url: str) -> str:
    """Return the Price Buddy web application URL from its API URL."""
    parsed = urlsplit(api_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        path = path[: -len("/api")]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def absolute_http_url(base_url: str, value: Any) -> str | None:
    """Resolve a possibly relative HTTP(S) URL."""
    if not isinstance(value, str) or not value.strip():
        return None
    resolved = urljoin(f"{base_url.rstrip('/')}/", value.strip())
    parsed = urlsplit(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return resolved


def build_unique_id(api_url: str, api_token: str) -> str:
    """Build a non-secret identifier that also permits multiple server users."""
    return sha256(f"{api_url}\0{api_token}".encode()).hexdigest()


class PriceBuddyApiClient:
    """Minimal asynchronous Price Buddy API client."""

    def __init__(
        self,
        session: ClientSession,
        api_url: str,
        api_token: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.api_url = normalize_api_url(api_url)
        self.web_url = web_url_from_api_url(self.api_url)
        self._headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}",
            "User-Agent": "Home Assistant Price Buddy integration",
        }

    async def async_validate_connection(self) -> int:
        """Validate credentials and return the visible product count."""
        payload = await self._async_request_json(
            "/products",
            params={
                "page": 1,
                "per_page": 1,
                "fields[products]": "id",
            },
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise PriceBuddyInvalidResponseError(
                "The products response does not contain a data list"
            )

        meta = payload.get("meta")
        if isinstance(meta, Mapping):
            total = _as_positive_or_zero_int(meta.get("total"))
            if total is not None:
                return total
        return len(data)

    async def async_get_products(
        self, *, include_details: bool = False
    ) -> dict[str, dict[str, Any]]:
        """Return all products visible to the API token, keyed by product ID."""
        products: dict[str, dict[str, Any]] = {}
        page = 1

        while page <= API_MAX_PAGES:
            params: dict[str, str | int] = {
                "page": page,
                "per_page": API_PAGE_SIZE,
                "include": "tags",
            }
            if not include_details:
                params["fields[products]"] = _SPARSE_PRODUCT_FIELDS

            payload = await self._async_request_json("/products", params=params)
            data = payload.get("data")
            if not isinstance(data, list):
                raise PriceBuddyInvalidResponseError(
                    "The products response does not contain a data list"
                )

            before_count = len(products)
            for item in data:
                if not isinstance(item, Mapping):
                    raise PriceBuddyInvalidResponseError(
                        "A product in the response is not an object"
                    )
                product_id = item.get("id")
                if product_id is None or isinstance(product_id, bool):
                    raise PriceBuddyInvalidResponseError(
                        "A product in the response has no valid ID"
                    )
                products[str(product_id)] = dict(item)

            next_page = _next_page(payload, page, len(data))
            if next_page is None:
                return products

            # Protect against a proxy or incompatible server ignoring the page
            # parameter and returning the same full page forever.
            if len(data) == API_PAGE_SIZE and len(products) == before_count:
                raise PriceBuddyInvalidResponseError(
                    "Price Buddy returned the same product page repeatedly"
                )
            page = next_page

        raise PriceBuddyInvalidResponseError(
            f"Price Buddy returned more than {API_MAX_PAGES} product pages"
        )

    async def _async_request_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """Perform one authenticated API request and validate its JSON envelope."""
        url = f"{self.api_url}/{path.lstrip('/')}"
        try:
            async with self._session.get(
                url,
                headers=self._headers,
                params=params,
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                if response.status == 401:
                    raise PriceBuddyAuthenticationError("The API token is invalid")
                if response.status == 403:
                    raise PriceBuddyPermissionError(
                        "The API token lacks permission to list products"
                    )
                if response.status == 404:
                    raise PriceBuddyInvalidResponseError(
                        "The Price Buddy products API was not found"
                    )
                if response.status >= 400:
                    body = (await response.text())[:300]
                    raise PriceBuddyRequestError(
                        f"Price Buddy returned HTTP {response.status}: {body}"
                    )

                try:
                    payload = await response.json(content_type=None)
                except (TypeError, ValueError) as err:
                    raise PriceBuddyInvalidResponseError(
                        "Price Buddy did not return JSON"
                    ) from err
        except PriceBuddyError:
            raise
        except (ClientError, TimeoutError) as err:
            raise PriceBuddyCannotConnectError(
                f"Could not connect to Price Buddy: {err}"
            ) from err

        if not isinstance(payload, dict):
            raise PriceBuddyInvalidResponseError(
                "Price Buddy returned a JSON value instead of an object"
            )
        return payload


def _as_positive_or_zero_int(value: Any) -> int | None:
    """Convert a value to a non-negative integer when possible."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _next_page(
    payload: Mapping[str, Any], current_page: int, page_item_count: int
) -> int | None:
    """Determine the next Laravel paginator page."""
    meta = payload.get("meta")
    if isinstance(meta, Mapping):
        reported_current = _as_positive_or_zero_int(meta.get("current_page"))
        last_page = _as_positive_or_zero_int(meta.get("last_page"))
        if reported_current is not None and last_page is not None:
            if reported_current >= last_page:
                return None
            return reported_current + 1

    links = payload.get("links")
    if isinstance(links, Mapping) and "next" in links:
        return current_page + 1 if links.get("next") else None

    # Fallback for compatible endpoints that omit Laravel pagination metadata.
    return current_page + 1 if page_item_count >= API_PAGE_SIZE else None
