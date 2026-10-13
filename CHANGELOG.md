# Changelog

## 1.3.0

- Trucks, buses and special vehicles (Encar Truck, Business/Scale): `korea.trucks(**params)`,
  `korea.truck_enums()`, `korea.trucks_csv()`, `korea.iterate_trucks_by_id(**params)`.
- Used excavators (굴삭기나라, Business/Scale): `korea.equipment(**params)`, `korea.equipment_enums()`,
  `korea.equipment_csv()`, `korea.iterate_equipment_by_id(**params)`.
- `korea.vehicle_by_vin(vin)`: every Encar / K Car listing of one VIN, active and removed (Business/Scale).
- The catalog `region` filter now also works with a single other source (`source="kbc"` or `"kcar"`).

## 1.2.0

- `korea.iterate_catalog_by_id(**params)` / `korea.iterate_leasing_by_id(**params)`: complete,
  stable traversal via `sort=id` + `after` (keyset cursor). Listings never shift between pages
  while the catalog changes, so nothing is repeated or skipped.
- `korea.export_csv(sell_type="lease,rental")` for the lease and rental inventory (any API
  parameter passes through, e.g. `region`, `city`, `after`).
- Catalog items now carry `Region` and `City`; `removed` change events carry `removalReason`
  (API release October 2026, no SDK change needed to receive them).

## 1.1.0

- `china.iterate_catalog(**params)`: generator over all China catalog pages. Stops at the
  API's 10,000-result depth limit; use `export_csv()` plus `iterate_changes()` for the full catalog.
- `china.iterate_changes(**params)`: follows the China change feed until it is drained and yields
  every event once. `china.last_cursor` holds the cursor to resume from.

## 1.0.0

- One client for Korea (Encar, KB Chachacha, K Car) and China (Dongchedi, Che168), all endpoints.
