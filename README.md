# EnCarAPI: Python client for Korean and Chinese used car data

Official **Python client** for [EnCarAPI](https://encarapi.com), the REST **Encar API** and
**Korean Car API**. One package for:

- **Korea:** Encar.com, KB Chachacha (`source="kbc"`) and K Car (`source="kcar"`), with
  photos, specs, options, inspection reports, accident and ownership records, condition
  reports, price history, a change feed and full catalog export.
- **China:** Dongchedi and Che168 in English via [ChinaCarAPI](https://chinacarapi.com/?utm_source=github&utm_medium=encarapi_sdk_python)
  (separate key or the China add-on for EnCarAPI keys).

Built for car exporters, dealers and marketplaces that need reliable used car data without
scraping, proxies or geo-blocks.

> **An API key is required.** The data is a paid service. Get a key (5-day trial) at
> **[encarapi.com](https://encarapi.com)**.

## Install

```bash
pip install encarapi
```

Requires Python 3.8+ and `requests`.

## Quick start

```python
from encarapi import EnCarAPI

client = EnCarAPI("YOUR_API_KEY")  # or set ENCARAPI_KEY

# Search Korean listings with flat English filters
cars = client.korea.catalog(
    manufacturer="Hyundai",
    max_mileage=60000,
    frame_clean=True,   # accident-free chassis only
    lang="en",
    count=True,
)
print(cars["Count"], cars["SearchResults"][0])

# Full detail, inspection report and insurance record for one car
detail = client.korea.vehicle("12345678")
inspection = client.korea.inspection("12345678")
record = client.korea.record("12345678")

# KB Chachacha and K Car listings, or all three marketplaces deduplicated
kbc = client.korea.catalog(source="kbc", limit=20)
everything = client.korea.catalog(source="all", count=True)

# Chinese listings (Dongchedi + Che168)
byd = client.china.catalog(make="BYD", export_ready=True, limit=25)
```

## Keep a local copy in sync (Business / Scale)

```python
csv_text = client.korea.export_csv()          # 1) baseline

for change in client.korea.iterate_changes(cursor=saved_cursor or 0):   # 2) deltas
    # change["type"]: "added" | "updated" | "reappeared" | "removed"
    ...
save_cursor(client.korea.last_cursor)
```

The China API works the same way (`client.china`); its events are
`{"id", "source", "vehicleId", "type": "new" | "price" | "removed" | "relisted", "oldPrice", "newPrice", "at"}`:

```python
for change in client.china.iterate_changes(cursor=saved_cursor or 0):
    # change["type"]: "new" | "price" | "removed" | "relisted"
    ...
save_cursor(client.china.last_cursor)
```

## Korea API (`client.korea`)

| Method | Endpoint | Notes |
|---|---|---|
| `catalog(**params)` | `GET /api/catalog` | Search & list. `source`: `encar` (default), `kbc`, `kcar`, `all` |
| `iterate_catalog(**params)` | `GET /api/catalog` | Generator over all pages |
| `leasing(**params)` | `GET /api/catalog/leasing` | Lease takeovers and rentals |
| `nav(**params)` | `GET /api/nav` | Filter facets with counts |
| `enums(**params)` | `GET /api/enums` | Valid values for the flat filters |
| `model_search(search, **params)` | `GET /api/model-search` | Model autocomplete |
| `vehicle(id)` | `GET /api/vehicle/{id}` | Ids: Encar id, `kbc:<id>`, `kcar:<id>` |
| `inspection(id)` | `GET /api/inspection/{id}` | Official inspection report |
| `record(id)` | `GET /api/record/{id}` | Accident & ownership record |
| `refresh(id)` | `POST /api/vehicle/{id}/refresh` | On-demand refresh (daily quota) |
| `price_check(id)` | `GET /api/price-check/{id}` | Market estimate (beta, Scale) |
| `bulk_vehicles(ids)` / `bulk_inspections(ids)` / `bulk_records(ids)` | `POST /api/.../bulk` | Up to 500 ids (Business/Scale) |
| `inspection_versions(id)` / `record_versions(id)` | `GET /api/.../versions` | Report history (Business/Scale) |
| `changes(**params)` / `iterate_changes(**params)` | `GET /api/catalog/changes` | Incremental sync (Business/Scale) |
| `export_csv()` | `GET /api/catalog/export` | Full catalog CSV (Business/Scale) |
| `makes_csv()` / `models_csv()` / `badges_csv()` | `GET /api/taxonomy/*.csv` | Reference data |

## China API (`client.china`)

| Method | Endpoint | Notes |
|---|---|---|
| `catalog(**params)` | `GET /api/catalog` | `make`, `price_min/max` (CNY), `export_ready`, `sort`, ... |
| `iterate_catalog(**params)` | `GET /api/catalog` | Generator over all pages (up to the 10,000-result depth limit) |
| `vehicle(id)` | `GET /api/vehicle/{id}` | Price history, photos, seller, export status |
| `inspection(id)` | `GET /api/inspection/{id}` | Accident, flood and fire checks, EV battery data |
| `bulk_vehicles(ids)` | `POST /api/vehicle/bulk` | Up to 500 ids |
| `changes(**params)` / `iterate_changes(**params)` | `GET /api/catalog/changes` | Change feed (Business/Scale) |
| `export_csv()` | `GET /api/catalog/export` | Full catalog CSV |
| `enums()` / `models(make)` | `GET /api/enums`, `/api/models` | Filter values, models per make |

China only? `from encarapi import ChinaCarAPI` (also available as the
[`chinacarapi`](https://pypi.org/project/chinacarapi/) package).

## Errors

Every failed request raises `EnCarAPIError` with `status` and the raw `body`. A `403` on a
plan-gated endpoint includes an upgrade hint from the API.

```python
from encarapi import EnCarAPIError

try:
    client.korea.changes(cursor=0)
except EnCarAPIError as e:
    if e.status == 403:
        print("Plan does not include this endpoint:", e.body)
```

## Links

- Website and pricing: https://encarapi.com
- Documentation: https://encarapi.com/documentation
- OpenAPI reference: https://api.encarapi.com/reference
- China data: https://chinacarapi.com/?utm_source=github&utm_medium=encarapi_sdk_python
- Node.js client: https://github.com/ThatMojo/encarapi-node

EnCarAPI is an independent service and not affiliated with Encar, KB Chachacha, K Car,
Dongchedi or Che168.

## License

MIT
