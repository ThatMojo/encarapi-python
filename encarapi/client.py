"""Official Python client for EnCarAPI: Korean (Encar, KB Chachacha, K Car) and
Chinese (Dongchedi, Che168) used car data."""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Iterator, List, Optional, TypedDict
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
    "DiagnosisItem",
    "DiagnosisReport",
    "DiagnosisResponse",
    "DiagnosisBulkResponse",
]

KOREA_BASE_URL = "https://api.encarapi.com"
CHINA_BASE_URL = "https://api.chinacarapi.com"
DEFAULT_BASE_URL = KOREA_BASE_URL  # 0.x compatibility
SIGNUP_URL = "https://encarapi.com/?utm_source=sdk&utm_medium=encarapi-python&utm_content=error#pricing"
CHINA_SIGNUP_URL = "https://chinacarapi.com/?utm_source=sdk&utm_medium=encarapi-python&utm_content=error#pricing"
# /api/catalog on the China API serves at most this many results per query (page * limit).
CHINA_CATALOG_DEPTH = 10000
# Export headers to pass as ``since`` to /api/catalog/changes (a few minutes before the data snapshot).
KOREA_GENERATED_AT = "X-Encarapi-Generated-At"
CHINA_GENERATED_AT = "x-generated-at"


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


# -- Encar diagnosis (엔카진단) response shapes (typing only, plain dicts at runtime) -----------

class DiagnosisItem(TypedDict):
    """One item of an Encar diagnosis: an outer panel or one of the two inspector comments.

    ``name``: ``FRONT_DOOR_LEFT``, ``FRONT_DOOR_RIGHT``, ``BACK_DOOR_LEFT``, ``BACK_DOOR_RIGHT``,
    ``FRONT_FENDER_LEFT``, ``FRONT_FENDER_RIGHT``, ``HOOD``, ``TRUNK_LID``, ``CHECKER_COMMENT`` or
    ``OUTER_PANEL_COMMENT`` as Encar names them (treat unknown names as additional items).
    ``result``: panels the Korean label (정상 normal, 교환 replaced), comments Korean free text.
    ``resultCode``: panels ``NORMAL`` or ``REPLACEMENT``, comments ``None``."""

    code: Optional[str]
    name: Optional[str]
    result: Optional[str]
    resultCode: Optional[str]


class DiagnosisReport(TypedDict):
    """Encar's own body diagnosis, the ``diagnosisReport`` block of an Encar vehicle detail.
    ``diagnosisDate`` / ``realDiagnosisDate``: Korean time (KST) without an offset. ``items``: the 8
    outer panels plus ``CHECKER_COMMENT`` (the inspector's verdict, incl. the frame result) and
    ``OUTER_PANEL_COMMENT``."""

    diagnosisDate: Optional[str]
    realDiagnosisDate: Optional[str]
    items: List[DiagnosisItem]


class DiagnosisResponse(DiagnosisReport):
    """Result of ``korea.diagnosis()``: the diagnosis plus the listing it resolved to."""

    listingId: str
    vehicleId: int


class _DiagnosisBulkBase(TypedDict):
    results: Dict[str, DiagnosisResponse]
    pending: List[str]
    notFound: List[str]
    noDiagnosis: List[str]
    counts: Dict[str, int]


class DiagnosisBulkResponse(_DiagnosisBulkBase, total=False):
    """Result of ``korea.bulk_diagnoses()``. ``results``: id (as sent) -> diagnosis; ``pending``:
    detail not collected yet; ``notFound``: unknown ids; ``noDiagnosis``: listings without an Encar
    diagnosis; ``counts``: ``requested``, ``found``, ``pending``, ``notFound``, ``noDiagnosis`` (and
    ``encarOnly`` when present). Optional: ``encarOnly`` / ``encarOnlyHint`` (prefixed kbc:/kcar: ids)
    and ``archived`` (trials: removed listings beyond the daily archive preview)."""

    encarOnly: List[str]
    encarOnlyHint: str
    archived: List[str]


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

    def _check(self, resp: Any) -> None:
        if resp.status_code in (401, 403):
            raise EnCarAPIError(
                f"{self.product} rejected the request ({resp.status_code}). Check your key or plan at "
                f"{self.signup_url}. Body: {resp.text[:300]}",
                resp.status_code, resp.text,
            )
        if not resp.ok:
            raise EnCarAPIError(f"{self.product} error {resp.status_code}: {resp.text[:300]}", resp.status_code, resp.text)

    def request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json: Any = None, text: bool = False) -> Any:
        resp = self.session.request(
            method, f"{self.base_url}{path}", params=self._clean(params), json=json, timeout=self.timeout,
            headers={"Accept": "text/csv"} if text else None,
        )
        self._check(resp)
        if text:
            return resp.text
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def download(self, path: str, dest: Any, params: Optional[Dict[str, Any]], generated_at_header: str) -> Dict[str, Any]:
        """Streams a GET response (a CSV export) to the file ``dest`` in chunks instead of holding
        it in memory. The data goes to ``<dest>.part`` first and is renamed when complete, so an
        aborted download never leaves a truncated file under the final name."""
        dest = os.fspath(dest)
        tmp = f"{dest}.part"
        resp = self.session.request(
            "GET", f"{self.base_url}{path}", params=self._clean(params), timeout=self.timeout,
            headers={"Accept": "text/csv"}, stream=True,
        )
        try:
            self._check(resp)
            written = 0
            try:
                with open(tmp, "wb") as fh:
                    # iter_content undoes a gzip/deflate transfer encoding (compress=true).
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        fh.write(chunk)
                        written += len(chunk)
                # urllib3 1.x ends a body that is shorter than Content-Length without an error;
                # raw.tell() counts the bytes on the wire (before gzip decoding).
                length = resp.headers.get("Content-Length")
                received = resp.raw.tell() if hasattr(resp.raw, "tell") else None
                if length is not None and length.isdigit() and received is not None and received != int(length):
                    raise EnCarAPIError(
                        f"{self.product} export ended early ({received} of {length} bytes); retry the download",
                        resp.status_code, None,
                    )
                os.replace(tmp, dest)
            except BaseException:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
            return {"path": dest, "bytes": written, "generated_at": resp.headers.get(generated_at_header)}
        finally:
            resp.close()


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
        ``catalog(manufacturer="BMW", max_mileage=50000, frame_clean=True, lang="en")``.
        ``lang="ru"`` / ``"de"`` returns Russian / German display values; filters accept them too."""
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

    def iterate_catalog_by_id(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Complete, stable traversal via ``sort=id`` + ``after`` (keyset cursor):
        listings never shift between pages while the catalog changes, so nothing is
        repeated or skipped. ``for car in korea.iterate_catalog_by_id(manufacturer="Kia"): ...``"""
        yield from self._iterate_by_id("/api/catalog", params)

    def iterate_leasing_by_id(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Same as ``iterate_catalog_by_id`` for lease-takeover and rental listings."""
        yield from self._iterate_by_id("/api/catalog/leasing", params)

    def vehicle_by_vin(self, vin: str) -> Any:
        """Every Encar / K Car listing of one VIN, active and removed (Business/Scale)."""
        return self._get(f"/api/vehicle/by-vin/{quote(str(vin), safe='')}", {})

    # -- trucks, buses, special vehicles (Business/Scale) -------------------
    def trucks(self, **params: Any) -> Any:
        """Encar trucks & buses, e.g. ``trucks(form="cargo", max_tons=1, lang="en")``. Values from ``truck_enums()``."""
        return self._get("/api/catalog/trucks", params)

    def truck(self, truck_id: str, **params: Any) -> Any:
        """One truck with detail page, inspection report, cargo box dimensions, VIN and plate (Business/Scale)."""
        return self._get(f"/api/catalog/trucks/{quote(str(truck_id), safe='')}", params)

    def truck_enums(self) -> Any:
        """Valid truck filter values with counts."""
        return self._get("/api/catalog/trucks/enums", {})

    def trucks_csv(self, **params: Any) -> str:
        """Full truck inventory as CSV text (Business/Scale)."""
        return self._get("/api/catalog/trucks/export", params, text=True)

    def export_trucks_to_file(self, path: Any, **params: Any) -> Dict[str, Any]:
        """Streams the truck export to a file (not held in memory). Returns
        ``{"path", "bytes", "generated_at"}``; continue with
        ``changes(source="truck", since=generated_at)``."""
        return self._http.download("/api/catalog/trucks/export", path, params, KOREA_GENERATED_AT)

    def iterate_trucks_by_id(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Complete, stable traversal of the truck catalog (``sort=id`` + ``after``)."""
        yield from self._iterate_by_id("/api/catalog/trucks", params)

    # -- construction equipment / excavators (Business/Scale) ---------------
    def equipment(self, **params: Any) -> Any:
        """Used excavators from 굴삭기나라, e.g. ``equipment(sub_type="crawler", max_hours=5000)``."""
        return self._get("/api/catalog/equipment", params)

    def equipment_enums(self) -> Any:
        """Valid equipment filter values with counts."""
        return self._get("/api/catalog/equipment/enums", {})

    def equipment_csv(self, **params: Any) -> str:
        """Full equipment inventory as CSV text (Business/Scale)."""
        return self._get("/api/catalog/equipment/export", params, text=True)

    def export_equipment_to_file(self, path: Any, **params: Any) -> Dict[str, Any]:
        """Streams the equipment export to a file (not held in memory). Returns
        ``{"path", "bytes", "generated_at"}``; continue with
        ``changes(source="equipment", since=generated_at)``."""
        return self._http.download("/api/catalog/equipment/export", path, params, KOREA_GENERATED_AT)

    def iterate_equipment_by_id(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Complete, stable traversal of the equipment catalog (``sort=id`` + ``after``)."""
        yield from self._iterate_by_id("/api/catalog/equipment", params)

    def _iterate_by_id(self, path: str, params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        params = dict(params)
        params.pop("page", None)
        query = {**params, "sort": "id", "limit": params.get("limit", 1000)}
        while True:
            res = self._get(path, query)
            yield from res.get("SearchResults") or []
            if not res.get("hasMore") or not res.get("nextAfter"):
                return
            query = {**query, "after": res["nextAfter"]}

    # -- one vehicle ---------------------------------------------------------
    def vehicle(self, vehicle_id: str, **params: Any) -> Any:
        """Full vehicle detail. Ids: Encar id, ``kbc:<id>`` or ``kcar:<id>``. Encar payloads end with
        ``diagnosisReport`` (see ``DiagnosisReport``; ``None`` = Encar has no diagnosis for the car)."""
        return self._get(f"/api/vehicle/{_enc(vehicle_id)}", params)

    def inspection(self, vehicle_id: str) -> Any:
        """Official inspection report."""
        return self._get(f"/api/inspection/{_enc(vehicle_id)}")

    def record(self, vehicle_id: str) -> Any:
        """Insurance accident & ownership record."""
        return self._get(f"/api/record/{_enc(vehicle_id)}")

    def diagnosis(self, vehicle_id: str) -> DiagnosisResponse:
        """Encar diagnosis (엔카진단), Encar ids only: the 8 outer panels (``resultCode`` ``NORMAL`` /
        ``REPLACEMENT``) plus ``CHECKER_COMMENT`` and ``OUTER_PANEL_COMMENT``. Without one it raises
        ``EnCarAPIError`` with status 404; the JSON ``body`` has ``diagnosisAvailable: false`` (Encar has
        no diagnosis for the listing) or ``detailPending: true`` (detail not collected yet, retry later)."""
        return self._get(f"/api/diagnosis/{_enc(vehicle_id)}")

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
    def bulk_vehicles(self, ids: Iterable[str], **params: Any) -> Any:
        """Up to 500 vehicle details in one call. ``lang="en"``, ``"ru"`` or ``"de"`` as on ``vehicle()``."""
        return self._http.request("POST", "/api/vehicle/bulk", params, json={"ids": list(ids)})

    def bulk_inspections(self, ids: Iterable[str]) -> Any:
        """Up to 500 inspection reports in one call."""
        return self._post("/api/inspection/bulk", {"ids": list(ids)})

    def bulk_records(self, ids: Iterable[str]) -> Any:
        """Up to 500 insurance records in one call."""
        return self._post("/api/record/bulk", {"ids": list(ids)})

    def bulk_diagnoses(self, ids: Iterable[str]) -> DiagnosisBulkResponse:
        """Up to 500 Encar diagnoses in one call (``noDiagnosis`` = listings without one,
        ``encarOnly`` = kbc:/kcar: ids)."""
        return self._post("/api/diagnosis/bulk", {"ids": list(ids)})

    def changes(self, **params: Any) -> Any:
        """Incremental change feed: ``cursor`` from the previous call, or ``since`` = ``generated_at``
        of an export (``export_to_file()``)."""
        return self._get("/api/catalog/changes", params)

    def iterate_changes(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Follows the change feed until drained and yields each change once as
        ``{"type": "added" | "updated" | "reappeared" | "removed", **item}``.
        Afterwards ``korea.last_cursor`` is the cursor to resume from."""
        query = dict(params)
        while True:
            res = self.changes(**query)
            page = [{"type": kind, **item} for kind in ("added", "updated", "reappeared", "removed") for item in res.get(kind) or []]
            # Entries carry eventId (API since 2026-10-17): yield them in event order
            # across the groups, so a later event for the same listing always comes last.
            if all(e.get("eventId") is not None for e in page):
                page.sort(key=lambda e: int(e["eventId"]))
            yield from page
            if res.get("nextCursor") is not None:
                self.last_cursor = res["nextCursor"]
            if not (res.get("hasMore") or res.get("truncated")) or res.get("nextCursor") is None:
                return
            query = {k: v for k, v in params.items() if k != "since"}
            query["cursor"] = res["nextCursor"]

    def export_csv(self, **params: Any) -> str:
        """Full catalog as CSV text. ``sell_type="lease,rental"`` for the lease/rental
        inventory, ``source="kbc"`` etc. for other marketplaces."""
        return self._get("/api/catalog/export", params, text=True)

    def export_to_file(self, path: Any, **params: Any) -> Dict[str, Any]:
        """Streams the full catalog export to a file instead of holding it in memory (same
        params as ``export_csv``). Returns ``{"path", "bytes", "generated_at"}``;
        ``generated_at`` is the X-Encarapi-Generated-At header (``None`` if absent): start the
        change feed with ``iterate_changes(since=generated_at)``."""
        return self._http.download("/api/catalog/export", path, params, KOREA_GENERATED_AT)

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
        self.last_cursor: Optional[int] = None

    def catalog(self, **params: Any) -> Any:
        """Search listings. Filters: source, make, model, year_min/max, price_min/max (CNY),
        mileage_max, power_min/max (hp), city, fuel, has_report, export_ready, sort, page, limit,
        lang (``"zh"`` = original Chinese values, ``"ru"`` = Russian values for the fixed fields
        (fuel, transmission, drivetrain, colours, seller type, condition, vehicle class), city names
        and equipment names; make, model and trim names stay Latin)."""
        return self._http.request("GET", "/api/catalog", params)

    def iterate_catalog(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Yields every listing across all pages: ``for car in china.iterate_catalog(make="BYD"): ...``
        Stops at the API's 10,000-result depth limit; for the whole catalog use
        ``export_to_file()`` plus ``iterate_changes()``."""
        limit = min(params.pop("limit", 100), 100)
        page = params.pop("page", 1)
        while True:
            res = self.catalog(**params, limit=limit, page=page)
            items = res.get("results") or []
            yield from items
            if len(items) < limit or (page + 1) * limit > CHINA_CATALOG_DEPTH:
                return
            page += 1

    def vehicle(self, vehicle_id: str, **params: Any) -> Any:
        """Full record: price history, photos, seller, export status, alsoListedOn.
        ``lang="zh"`` or ``"ru"`` as on ``catalog()``."""
        return self._http.request("GET", f"/api/vehicle/{_enc(vehicle_id)}", params)

    def vehicle_by_url(self, url: str, **params: Any) -> Any:
        """Same full record, looked up by a Che168 or Dongchedi listing link (desktop, mobile or
        app; a pasted share text works too). ``lang="zh"`` or ``"ru"`` as on ``catalog()``."""
        return self._http.request("GET", "/api/vehicle/by-url", {**params, "url": url})

    def inspection(self, vehicle_id: str, **params: Any) -> Any:
        """Inspection report: accident, flood and fire checks, battery data for EVs."""
        return self._http.request("GET", f"/api/inspection/{_enc(vehicle_id)}", params)

    def specs(self, trim_id: Any, **params: Any) -> Any:
        """Autohome specification sheet of a Che168 trim (``trim.id`` of a vehicle record):
        cc, kW, hp, torque, emission standard, weights, EV battery. ``lang="zh"`` or ``"ru"``
        for the equipment names."""
        return self._http.request("GET", f"/api/specs/{_enc(str(trim_id))}", params)

    def bulk_vehicles(self, ids: Iterable[str], **params: Any) -> Any:
        """Up to 500 full records in one call (Business/Scale). ``lang="zh"`` or ``"ru"`` as on ``catalog()``."""
        return self._http.request("POST", "/api/vehicle/bulk", params, json={"ids": list(ids)})

    # 0.x name used by the standalone chinacarapi client
    bulk = bulk_vehicles

    def changes(self, **params: Any) -> Any:
        """Change feed: ``since`` once (the ``generated_at`` of an export), then ``cursor=nextCursor``
        (Business/Scale)."""
        return self._http.request("GET", "/api/catalog/changes", params)

    def iterate_changes(self, **params: Any) -> Iterator[Dict[str, Any]]:
        """Follows the change feed until drained and yields each event once as
        ``{"id", "source", "vehicleId", "type": "new" | "price" | "removed" | "relisted", "oldPrice", "newPrice", "at"}``.
        Afterwards ``china.last_cursor`` is the cursor to resume from."""
        query = dict(params)
        while True:
            res = self.changes(**query)
            yield from res.get("changes") or []
            if res.get("nextCursor") is not None:
                self.last_cursor = res["nextCursor"]
            if not res.get("hasMore") or res.get("nextCursor") is None:
                return
            query = {k: v for k, v in params.items() if k != "since"}
            query["cursor"] = res["nextCursor"]

    def export_csv(self, **params: Any) -> str:
        """Full catalog as CSV text (Business/Scale). ``lang="ru"``: the label columns in Russian."""
        return self._http.request("GET", "/api/catalog/export", params, text=True)

    def export_to_file(self, path: Any, **params: Any) -> Dict[str, Any]:
        """Streams the full catalog export to a file instead of holding it in memory (same
        params as ``export_csv``). Returns ``{"path", "bytes", "generated_at"}``;
        ``generated_at`` is the x-generated-at header (``None`` if absent): start the change
        feed with ``iterate_changes(since=generated_at)``."""
        return self._http.download("/api/catalog/export", path, params, CHINA_GENERATED_AT)

    def enums(self, **params: Any) -> Any:
        """Filter values with counts: makes, fuels, cities, sources, sorts. ``lang="ru"`` adds
        ``nameRu`` to fuels and cities."""
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
