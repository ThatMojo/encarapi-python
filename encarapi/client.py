"""Official Python client for the EnCarAPI — Korean car data API (Encar.com)."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

__all__ = ["EnCarAPI", "EnCarAPIError", "MissingApiKeyError"]

DEFAULT_BASE_URL = "https://api.encarapi.com"
SIGNUP_URL = "https://encarapi.com"


class EnCarAPIError(Exception):
    """Raised when the EnCarAPI returns an error response."""


class MissingApiKeyError(EnCarAPIError):
    """Raised when no API key is provided."""


class EnCarAPI:
    """Client for the EnCarAPI Korean car data API.

    An EnCarAPI key is **required**. Get one (5-day trial available) at
    https://encarapi.com — the API and its data are not free.

        from encarapi import EnCarAPI

        client = EnCarAPI("YOUR_API_KEY")   # or set ENCARAPI_KEY in the environment
        cars = client.catalog(count=True)
        detail = client.vehicle("12345678")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        api_key = api_key or os.environ.get("ENCARAPI_KEY")
        if not api_key:
            raise MissingApiKeyError(
                "An EnCarAPI key is required. Pass it as EnCarAPI('YOUR_KEY') or set "
                f"the ENCARAPI_KEY environment variable. Get a key at {SIGNUP_URL}"
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {"x-api-key": api_key, "Accept": "application/json"}
        )

    # -- low level -------------------------------------------------------
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        resp = self._session.get(
            f"{self.base_url}{path}", params=params, timeout=self.timeout
        )
        if resp.status_code == 401 or resp.status_code == 403:
            raise EnCarAPIError(
                f"EnCarAPI rejected the request ({resp.status_code}). "
                f"Check your key or subscription at {SIGNUP_URL}. Body: {resp.text[:300]}"
            )
        if not resp.ok:
            raise EnCarAPIError(f"EnCarAPI error {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    # -- endpoints -------------------------------------------------------
    def catalog(self, **params: Any) -> Any:
        """Search & filter the Korean car catalog (Encar.com listings)."""
        return self._get("/api/catalog", params or None)

    def nav(self, **params: Any) -> Any:
        """Filter facets / navigation metadata (brands, models, counts)."""
        return self._get("/api/nav", params or None)

    def vehicle(self, vehicle_id: str) -> Any:
        """Full detail for one vehicle: specs, options, inspection, price."""
        return self._get(f"/api/vehicle/{vehicle_id}")
