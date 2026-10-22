# EnCarAPI: Python client for Korean and Chinese used car data

Official **Python client** for [EnCarAPI](https://encarapi.com/?utm_source=readme&utm_medium=encarapi-python), the REST **Encar API** and
**Korean Car API**. One package for:

- **Korea:** Encar.com, KB Chachacha (`source="kbc"`) and K Car (`source="kcar"`), with
  photos, specs, options, inspection reports, accident and ownership records, condition
  reports, price history, a change feed and full catalog export.
- **China:** Dongchedi and Che168 in English via [ChinaCarAPI](https://chinacarapi.com/?utm_source=readme&utm_medium=encarapi-python)
  (separate key or the China add-on for EnCarAPI keys).

Built for car exporters, dealers and marketplaces that need reliable used car data without
scraping, proxies or geo-blocks.

> **An API key is required.** The data is a paid service. Get a key (5-day trial) at
> **[encarapi.com](https://encarapi.com/?utm_source=readme&utm_medium=encarapi-python)**.

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

### Russian and German values

Every Korea call that takes `lang="en"` also takes `lang="ru"` or `lang="de"`: fuel, transmission, colors,
body class, sell type, regions and options come in Russian or German (with `"de"` also model and trim names,
e.g. `C-Klasse`, `5er`). Ids, codes and numbers stay the same, and the filters accept these values too.

```python
ru = client.korea.catalog(fuel="дизель", lang="ru", limit=10)
de = client.korea.catalog(model_group="C-Klasse", fuel="Benzin", lang="de", limit=10)
enums_de = client.korea.enums(lang="de")  # nameDe per value
```

China calls take `lang="zh"` (original Chinese values) or `lang="ru"`: Russian values for the fixed fields
(fuel, transmission, drivetrain, colours, seller type, condition, vehicle class), city names and equipment
names on `catalog`, `vehicle`, `vehicle_by_url`, `bulk_vehicles` and `specs`. Make, model and trim names stay
Latin. `enums(lang="ru")` adds `nameRu` to fuels and cities, `export_csv(lang="ru")` /
`export_to_file(path, lang="ru")` return the label columns in Russian.

```python
cn = client.china.catalog(make="BYD", lang="ru", limit=10)
```

## Keep a local copy in sync (Business / Scale)

Three steps: export to a file, start the change feed at the export's timestamp, then keep the cursor.

```python
# 1) Baseline: stream the full catalog to a file (not held in memory)
export = client.korea.export_to_file("catalog.csv")   # {"path", "bytes", "generated_at"}
import_csv(export["path"])                             # your import: upsert by listing_id

# 2) First sync: start the change feed at the export's generated_at
#    (X-Encarapi-Generated-At, not the time of your download)
for change in client.korea.iterate_changes(since=export["generated_at"]):
    # change["type"]: "added" | "updated" | "reappeared" | "removed"; apply idempotently
    ...
save_cursor(client.korea.last_cursor)

# 3) Every later sync: continue from the saved cursor
for change in client.korea.iterate_changes(cursor=load_cursor()):
    ...
save_cursor(client.korea.last_cursor)
```

`generated_at` lies a few minutes before the file's data snapshot, so the first feed page can repeat a few
events that are already in the file: apply them as upserts. Use the same `source` / `sell_type` for the
export and the feed (e.g. `export_to_file("kbc.csv", source="kbc")`, then
`iterate_changes(source="kbc", since=...)`). `export_csv()` still returns the CSV as one string, but without
the timestamp; for large catalogs use `export_to_file()`. Trucks and excavators work the same way with
`export_trucks_to_file()` / `export_equipment_to_file()` and `source="truck"` / `"equipment"` on the feed.
The file is written to `<path>.part` first and renamed when complete, so an aborted download never leaves
a truncated file under the final name.

The China API works the same way (`client.china`, header `x-generated-at`); its events are
`{"id", "source", "vehicleId", "type": "new" | "price" | "removed" | "relisted", "oldPrice", "newPrice", "at"}`:

```python
export = client.china.export_to_file("china-catalog.csv")
for change in client.china.iterate_changes(since=export["generated_at"]):
    # change["type"]: "new" | "price" | "removed" | "relisted"
    ...
save_cursor(client.china.last_cursor)   # later: iterate_changes(cursor=load_cursor())
```

## Korea API (`client.korea`)

| Method | Endpoint | Notes |
|---|---|---|
| `catalog(**params)` | `GET /api/catalog` | Search & list. `source`: `encar` (default), `kbc`, `kcar`, `all` |
| `iterate_catalog(**params)` | `GET /api/catalog` | Generator over all pages |
| `iterate_catalog_by_id(**params)` | `GET /api/catalog?sort=id` | Complete, stable traversal (keyset cursor, nothing repeated or skipped) |
| `leasing(**params)` | `GET /api/catalog/leasing` | Lease takeovers and rentals |
| `iterate_leasing_by_id(**params)` | `GET /api/catalog/leasing?sort=id` | Complete, stable traversal of lease/rental listings |
| `vehicle_by_vin(vin)` | `GET /api/vehicle/by-vin/{vin}` | All listings of one VIN incl. removed ones (Business/Scale) |
| `trucks(**params)` | `GET /api/catalog/trucks` | Trucks, buses and special vehicles (Business/Scale) |
| `truck(id)` | `GET /api/catalog/trucks/{id}` | One truck with detail, inspection report, cargo box, VIN and plate |
| `truck_enums()` | `GET /api/catalog/trucks/enums` | Truck filter values with counts |
| `trucks_csv()` | `GET /api/catalog/trucks/export` | Full truck inventory CSV (Business/Scale) |
| `export_trucks_to_file(path, **params)` | `GET /api/catalog/trucks/export` | Same, streamed to a file: `{"path", "bytes", "generated_at"}` |
| `iterate_trucks_by_id(**params)` | `GET /api/catalog/trucks?sort=id` | Complete, stable traversal of the truck catalog |
| `equipment(**params)` | `GET /api/catalog/equipment` | Used excavators (Business/Scale) |
| `equipment_enums()` | `GET /api/catalog/equipment/enums` | Equipment filter values with counts |
| `equipment_csv()` | `GET /api/catalog/equipment/export` | Full equipment inventory CSV (Business/Scale) |
| `export_equipment_to_file(path, **params)` | `GET /api/catalog/equipment/export` | Same, streamed to a file: `{"path", "bytes", "generated_at"}` |
| `iterate_equipment_by_id(**params)` | `GET /api/catalog/equipment?sort=id` | Complete, stable traversal of the equipment catalog |
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
| `export_csv(**params)` | `GET /api/catalog/export` | Full catalog CSV (Business/Scale); `sell_type="lease,rental"` for lease/rental |
| `export_to_file(path, **params)` | `GET /api/catalog/export` | Same export streamed to a file: `{"path", "bytes", "generated_at"}` (start of the change feed) |
| `makes_csv()` / `models_csv()` / `badges_csv()` | `GET /api/taxonomy/*.csv` | Reference data |

## China API (`client.china`)

| Method | Endpoint | Notes |
|---|---|---|
| `catalog(**params)` | `GET /api/catalog` | `make`, `price_min/max` (CNY), `power_min/max` (hp), `export_ready`, `sort`, `lang` (`zh`, `ru`), ... |
| `iterate_catalog(**params)` | `GET /api/catalog` | Generator over all pages (up to the 10,000-result depth limit) |
| `vehicle(id)` | `GET /api/vehicle/{id}` | Price history, photos, seller, export status |
| `vehicle_by_url(url)` | `GET /api/vehicle/by-url` | Same record by Che168/Dongchedi listing link (desktop, mobile or app) |
| `inspection(id)` | `GET /api/inspection/{id}` | Accident, flood and fire checks, EV battery data |
| `specs(trim_id, **params)` | `GET /api/specs/{trimId}` | Autohome trim sheet of a Che168 car: cc, kW, hp, torque, emission standard, weights, EV battery |
| `bulk_vehicles(ids)` | `POST /api/vehicle/bulk` | Up to 500 ids |
| `changes(**params)` / `iterate_changes(**params)` | `GET /api/catalog/changes` | Change feed (Business/Scale) |
| `export_csv(**params)` | `GET /api/catalog/export` | Full catalog CSV; `lang="ru"` for Russian label columns |
| `export_to_file(path, **params)` | `GET /api/catalog/export` | Same export streamed to a file: `{"path", "bytes", "generated_at"}` (start of the change feed) |
| `enums(**params)` / `models(make)` | `GET /api/enums`, `/api/models` | Filter values (`lang="ru"` adds `nameRu`), models per make |

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

- Website and pricing: [encarapi.com](https://encarapi.com/?utm_source=readme&utm_medium=encarapi-python)
- Documentation: [encarapi.com/documentation](https://encarapi.com/documentation?utm_source=readme&utm_medium=encarapi-python)
- OpenAPI reference: https://api.encarapi.com/reference
- China data: [chinacarapi.com](https://chinacarapi.com/?utm_source=readme&utm_medium=encarapi-python)
- Node.js client: https://github.com/ThatMojo/encarapi-node

EnCarAPI is an independent service and not affiliated with Encar, KB Chachacha, K Car,
Dongchedi or Che168.

## License

MIT
