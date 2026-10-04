"""Official Python client for EnCarAPI: Korean (Encar, KB Chachacha, K Car) and
Chinese (Dongchedi, Che168) used car data."""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Iterator, List, Optional
from urllib.parse import quote

import requests

__all__ = [
    "EnCarAPI",
    "ChinaCarAPI",
    "KoreaClient",
    "ChinaClient",
    "EnCarAPIError",
    "ChinaCarAPIError",
    "MissingApiKeyError",
]

KOREA_BASE_URL = "https://api.encarapi.com"
CHINA_BASE_URL = "https://api.chinacarapi.com"
DEFAULT_BASE_URL = KOREA_BASE_URL  # 0.x compatibility
SIGNUP_URL = "https://encarapi.com"
CHINA_SIGNUP_URL = "https://chinacarapi.com"


class EnCarAPIError(Exception):
    """Raised when the API returns an error. ``status`` and ``body`` hold the response."""

    def __init__(self, message: str, status: Optional[int] = None, body: Optional[str] = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


ChinaCarAPIError = EnCarAPIError


class MissingApiKeyError(EnCarAPIError):
    """Raised when no API key is provided."""


def _enc(value: str) -> str:
    return quote(str(value), safe="")


class _Http:
    """Shared requests session: x-api-key header, bool/list params, readable errors."""

    def __init__(self, api_key: str, base_url: str, signup_url: str, product: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.signup_url = signup_url
        self.product = product
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": api_key, "Accept": "application/json"})

    @staticmethod
    def _clean(params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not params:
            return None
        out: Dict[str, Any] = {}
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, bool):
                v = "true" if v else "false"
            elif isinstance(v, (list, tuple, set)):
                v = ",".join(str(x) for x in v)
            out[k] = v
        return out

    def request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json: Any = None, text: bool = False) -> Any:
        resp = self.session.request(
            method, f"{self.base_url}{path}", params=self._clean(params), json=json, timeout=self.timeout,
            headers={"Accept": "text/csv"} if text else None,
        )
        if resp.status_code in (401, 403):
            raise EnCarAPIError(
                f"{self.product} rejected the request ({resp.status_code}). Check your key or plan at "
                f"{self.signup_url}. Body: {resp.text[:300]}",
                resp.status_code, resp.text,
            )
        if not resp.ok:
            raise EnCarAPIError(f"{self.product} error {resp.status_code}: {resp.text[:300]}", resp.status_code, resp.text)
        if text:
            return resp.text
        try:
            return resp.json()
        except ValueError:
            return resp.text


class KoreaClient:
    """Korean used car data: Encar (default), KB Chachacha (``source="kbc"``) and
    K Car (``source="kcar"``); ``source="all"`` is the deduplicated union.
    Endpoints marked Business/Scale return 403 with an upgrade hint on smaller plans."""

    def __init__(self, api_key: str, *, base_url: str = KOREA_BASE_URL, timeout: float = 30.0) -> None:
        self._http = _Http(api_key, base_url, SIGNUP_URL, "EnCarAPI", timeout)
        self.last_cursor: Optional[int] = None

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, text: bool = False) -> Any:
        return self._http.request("GET", path, params, text=text)

    def _post(self, path: str, json: Any = None) -> Any:
        return self._http.request("POST", path, json=json)

    # -- search ------------------------------------------------------------
    def catalog(self, **params: Any) -> Any:
        """Search & list vehicles with flat English filters, e.g.
        ``catalog(manufacturer="BMW", max_mileage=50000, frame_clean=True, lang="en")``."""
        return self._get("/api/catalog", params)

    def leasing(self, **params: Any) -> Any:
        """Lease-takeover and rental listings (same filters as catalog)."""
        return self._get("/api/catalog/leasing", params)

    def nav(self, **params: Any) -> Any:
        """Filter facets with counts (the navigation tree)."""
        return self._get("/api/nav", params)

    def enums(self, **params: Any) -> Any:
        """Valid values for the flat filter parameters."""
        return self._get("/api/enums", params)

    def model_search(self, search: str, **params: Any) -> Any:
        """Model autocomplete across brands."""
        return self._get("/api/model-search", {**params, "search": search})

    def iterate_catalog(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Yields every listing across all pages: ``for car in korea.iterate_catalog(manufacturer="Kia"): ...``"""
        limit = params.pop("limit", 100)
        page = params.pop("page", 1)
        while True:
            res = self.catalog(**params, limit=limit, page=page)
            items = res.get("SearchResults") or []
            yield from items
            if len(items) < limit:
                return
            page += 1

    # -- one vehicle ---------------------------------------------------------
    def vehicle(self, vehicle_id: str, **params: Any) -> Any:
        """Full vehicle detail. Ids: Encar id, ``kbc:<id>`` or ``kcar:<id>``."""
        return self._get(f"/api/vehicle/{_enc(vehicle_id)}", params)

    def inspection(self, vehicle_id: str) -> Any:
        """Official inspection report."""
        return self._get(f"/api/inspection/{_enc(vehicle_id)}")

    def record(self, vehicle_id: str) -> Any:
        """Insurance accident & ownership record."""
        return self._get(f"/api/record/{_enc(vehicle_id)}")

    def refresh(self, vehicle_id: str) -> Any:
        """Request a fresh copy of one listing (daily quota per plan)."""
        return self._post(f"/api/vehicle/{_enc(vehicle_id)}/refresh")

    def price_check(self, vehicle_id: str) -> Any:
        """Price check (beta, Scale): below / in line with / above the market."""
        return self._get(f"/api/price-check/{_enc(vehicle_id)}")

    def inspection_versions(self, vehicle_id: str) -> Any:
        """Inspection report versions (Business/Scale)."""
        return self._get(f"/api/inspection/{_enc(vehicle_id)}/versions")

    def record_versions(self, vehicle_id: str) -> Any:
        """Insurance record versions (Business/Scale)."""
        return self._get(f"/api/record/{_enc(vehicle_id)}/versions")

    # -- bulk & sync (Business/Scale) ---------------------------------------
    def bulk_vehicles(self, ids: Iterable[str]) -> Any:
        """Up to 500 vehicle details in one call."""
        return self._post("/api/vehicle/bulk", {"ids": list(ids)})

    def bulk_inspections(self, ids: Iterable[str]) -> Any:
        """Up to 500 inspection reports in one call."""
        return self._post("/api/inspection/bulk", {"ids": list(ids)})

    def bulk_records(self, ids: Iterable[str]) -> Any:
        """Up to 500 insurance records in one call."""
        return self._post("/api/record/bulk", {"ids": list(ids)})

    def changes(self, **params: Any) -> Any:
        """Incremental change feed: ``cursor`` from the previous call, or ``since`` right after an export."""
        return self._get("/api/catalog/changes", params)

    def iterate_changes(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Follows the change feed until drained and yields each change once as
        ``{"type": "added" | "updated" | "reappeared" | "removed", **item}``.
        Afterwards ``korea.last_cursor`` is the cursor to resume from."""
        query = dict(params)
        while True:
            res = self.changes(**query)
            for kind in ("added", "updated", "reappeared", "removed"):
                for item in res.get(kind) or []:
                    yield {"type": kind, **item}
            if res.get("nextCursor") is not None:
                self.last_cursor = res["nextCursor"]
            if not (res.get("hasMore") or res.get("truncated")) or res.get("nextCursor") is None:
                return
            query = {k: v for k, v in params.items() if k != "since"}
            query["cursor"] = res["nextCursor"]

    def export_csv(self, **params: Any) -> str:
        """Full catalog as CSV text."""
        return self._get("/api/catalog/export", params, text=True)

    # -- reference data -------------------------------------------------------
    def makes_csv(self, **params: Any) -> str:
        """All makes as CSV."""
        return self._get("/api/taxonomy/makes.csv", params, text=True)

    def models_csv(self, **params: Any) -> str:
        """All models as CSV."""
        return self._get("/api/taxonomy/models.csv", params, text=True)

    def badges_csv(self, **params: Any) -> str:
        """All badges (trims) as CSV."""
        return self._get("/api/taxonomy/badges.csv", params, text=True)


class ChinaClient:
    """Chinese used car data (Dongchedi and Che168) in English. Works with a
    ChinaCarAPI key or an EnCarAPI key that has the China add-on."""

    def __init__(self, api_key: str, *, base_url: str = CHINA_BASE_URL, timeout: float = 30.0) -> None:
        self._http = _Http(api_key, base_url, CHINA_SIGNUP_URL, "ChinaCarAPI", timeout)

    def catalog(self, **params: Any) -> Any:
        """Search listings. Filters: source, make, model, year_min/max, price_min/max (CNY),
        mileage_max, city, fuel, has_report, export_ready, sort, page, limit, lang ('zh' = original)."""
        return self._http.request("GET", "/api/catalog", params)

    def vehicle(self, vehicle_id: str, **params: Any) -> Any:
        """Full record: price history, photos, seller, export status, alsoListedOn."""
        return self._http.request("GET", f"/api/vehicle/{_enc(vehicle_id)}", params)

    def inspection(self, vehicle_id: str, **params: Any) -> Any:
        """Inspection report: accident, flood and fire checks, battery data for EVs."""
        return self._http.request("GET", f"/api/inspection/{_enc(vehicle_id)}", params)

    def bulk_vehicles(self, ids: Iterable[str], **params: Any) -> Any:
        """Up to 500 full records in one call (Business/Scale)."""
        return self._http.request("POST", "/api/vehicle/bulk", params, json={"ids": list(ids)})

    # 0.x name used by the standalone chinacarapi client
    bulk = bulk_vehicles

    def changes(self, **params: Any) -> Any:
        """Change feed: ``since`` once, then ``cursor=nextCursor`` (Business/Scale)."""
        return self._http.request("GET", "/api/catalog/changes", params)

    def export_csv(self, **params: Any) -> str:
        """Full catalog as CSV text (Business/Scale)."""
        return self._http.request("GET", "/api/catalog/export", params, text=True)

    def enums(self, **params: Any) -> Any:
        """Filter values with counts: makes, fuels, cities, sources, sorts."""
        return self._http.request("GET", "/api/enums", params)

    def models(self, make: str) -> Any:
        """Models of one make (id or English name) with counts."""
        return self._http.request("GET", "/api/models", {"make": make})


class EnCarAPI:
    """One client for both markets.

        from encarapi import EnCarAPI

        client = EnCarAPI("YOUR_API_KEY")          # or set ENCARAPI_KEY
        kr = client.korea.catalog(manufacturer="Hyundai", lang="en", count=True)
        cn = client.china.catalog(make="BYD", limit=25)

    An API key is **required**: https://encarapi.com (Korea) or https://chinacarapi.com (China).
    EnCarAPI keys with the China add-on work for both. Pass ``china_key`` (or set
    CHINACARAPI_KEY) to use a separate ChinaCarAPI key.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        china_key: Optional[str] = None,
        base_url: str = KOREA_BASE_URL,
        china_base_url: str = CHINA_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        api_key = api_key or os.environ.get("ENCARAPI_KEY")
        china_key = china_key or os.environ.get("CHINACARAPI_KEY") or api_key
        if not api_key and not china_key:
            raise MissingApiKeyError(
                "An API key is required. Pass it as EnCarAPI('YOUR_KEY') or set ENCARAPI_KEY "
                f"(Korea) / CHINACARAPI_KEY (China). Get a key at {SIGNUP_URL}"
            )
        self._api_key = api_key
        self._china_key = china_key
        self._base_url = base_url
        self._china_base_url = china_base_url
        self._timeout = timeout
        self._korea: Optional[KoreaClient] = None
        self._china: Optional[ChinaClient] = None

    @property
    def korea(self) -> KoreaClient:
        """Korean data: Encar (default), KB Chachacha (``kbc``), K Car (``kcar``)."""
        if self._korea is None:
            if not self._api_key:
                raise MissingApiKeyError(f"An EnCarAPI key is required for Korean data. Get one at {SIGNUP_URL}")
            self._korea = KoreaClient(self._api_key, base_url=self._base_url, timeout=self._timeout)
        return self._korea

    @property
    def china(self) -> ChinaClient:
        """Chinese data: Dongchedi and Che168."""
        if self._china is None:
            self._china = ChinaClient(self._china_key, base_url=self._china_base_url, timeout=self._timeout)  # type: ignore[arg-type]
        return self._china

    # 0.x shortcuts (Korean catalog)
    def catalog(self, **params: Any) -> Any:
        return self.korea.catalog(**params)

    def nav(self, **params: Any) -> Any:
        return self.korea.nav(**params)

    def vehicle(self, vehicle_id: str, **params: Any) -> Any:
        return self.korea.vehicle(vehicle_id, **params)


class ChinaCarAPI(ChinaClient):
    """China-only client (also published as the ``chinacarapi`` package).

        from encarapi import ChinaCarAPI
        client = ChinaCarAPI("YOUR_KEY")   # or set CHINACARAPI_KEY
    """

    def __init__(self, api_key: Optional[str] = None, *, base_url: str = CHINA_BASE_URL, timeout: float = 30.0) -> None:
        api_key = api_key or os.environ.get("CHINACARAPI_KEY")
        if not api_key:
            raise MissingApiKeyError(
                "A ChinaCarAPI key is required. Pass it as ChinaCarAPI('YOUR_KEY') or set CHINACARAPI_KEY. "
                f"Get a key at {CHINA_SIGNUP_URL}"
            )
        super().__init__(api_key, base_url=base_url, timeout=timeout)
