# Changelog

## 1.9.2

- `china.spec_fields(lang=...)` (new, API release November 2026): the field dictionary of the `specs` object of
  a vehicle record, `GET /api/specs/fields`. One entry per key with `label`, `unit`, `group` and `type`, in
  English, Russian (`lang="ru"`) or Chinese (`lang="zh"`); keys under `specs.ev` are written `ev.<name>`.
  Label a specification sheet by going through `fields` and reading `specs[key]`.
- China `lang="ru"`: the text values of `specs` (energy type, transmission, drive, aspiration, body type,
  emission standard, warranties, motor and battery type) are now Russian on `vehicle`, `vehicle_by_url`,
  `bulk_vehicles` and in the `summary` of `specs(trim_id)`. A value without a Russian term stays English.
- Dongchedi records: `specs.ev.motorLayout`, `specs.ev.motorType`, `specs.ev.batteryWarranty` and the less common
  `specs.warranty` wordings now come in the same English as on Che168 records (they were transliterated before,
  e.g. "Front Zhi" is now "Front-mounted"). No SDK change needed.

## 1.9.1

- Release note: 1.9.0 was not published to PyPI on its own - 1.9.1 is the first published version with
  `korea.history()` and everything listed under 1.9.0 below.
- `korea.inspection(vehicle_id)` and `korea.bulk_inspections(ids)` also take KB Chachacha ids (`"kbc:<id>"`,
  API release 5 November 2026): the official inspection sheet (성능·상태점검기록부) read from the inspection
  company's website, in the same structure and with the same codes as an Encar report, plus a `source` block
  (`id`, `provider`, `reportUrl`, `sheetUrl`, `fetchedAt`); `vehicleId` is `None`, `images[].path` are absolute
  URLs. About two in five KB Chachacha listings that link a sheet have one; `InspectionAvailable` on the
  `kbc:` vehicle detail, on KB Chachacha items of `changes()` and the `inspection_available` export column tell
  which. Without one it raises `EnCarAPIError` 404: `detailPending: true` (sheet link not read yet, usually
  within an hour) or `inspectionAvailable: false` (no structured sheet, original link in `inspectionReportUrl`).
  In `bulk_inspections()` such ids are listed under `pending` / `noInspection`. No code change, the calls
  already passed the id through.

## 1.9.0

- New: `korea.history(vehicle_id)` (`GET /api/history/{id}`) returns Encar's vehicle history (차량이력) of an
  Encar listing: `{"listingId", "vehicleId", "collectedAt", "listingStatus", "eventCount", "summaryKo",
  "mileageReadings", "ownershipPeriods", "flags", "events"}`. `events` is the timeline in Encar's order
  (inspections, repairs, owner changes, insurance claims, recalls, new-car registration and more);
  `mileageReadings` is every dated odometer reading, oldest first. Encar collects it from the Ministry of Land,
  Infrastructure and Transport (국토교통부) and the Korea Insurance Development Institute (보험개발원); about 8 in 10
  Encar listings have one. Keys and enums are English, Korean source text stays in the `*Ko` fields and is not
  translated with `lang`. Without a history it raises `EnCarAPIError` 404 with a JSON `body`:
  `historyAvailable: false` (Encar shows no public history for the listing), `historyPending: true` (Encar has
  one but we have not collected it yet, retry later) or `Vehicle not found.`; prefixed `kbc:` / `kcar:` ids
  answer 404 with a hint. Encar ids only, no bulk endpoint. A new or changed history does not create an event
  in `changes()`.
- Typing only: `TypedDict`s `VehicleHistory`, `HistoryEvent`, `HistoryMileageReading`,
  `HistoryOwnershipPeriod` and `HistoryFlags` (exported from `encarapi`); responses stay plain dicts.

## 1.8.0

- New: `korea.diagnosis(vehicle_id)` (`GET /api/diagnosis/{id}`) returns Encar's own body diagnosis (엔카진단)
  of an Encar listing: `{"listingId", "vehicleId", "diagnosisDate", "realDiagnosisDate", "items"}`. `items`
  lists the 8 outer panels (`FRONT_DOOR_LEFT` ... `TRUNK_LID`, `resultCode` `NORMAL` / `REPLACEMENT`) plus
  `CHECKER_COMMENT` (the inspector's verdict) and `OUTER_PANEL_COMMENT` (Korean free text, `resultCode`
  `None`); treat unknown names as additional items. About three in four active Encar listings have one.
  Without one it raises `EnCarAPIError` 404 with a JSON `body`: `diagnosisAvailable: false` (Encar has no
  diagnosis for the listing), `detailPending: true` (detail not collected yet, retry later) or
  `Vehicle not found.`; prefixed `kbc:` / `kcar:` ids answer 404 with a hint. All paid plans and trials
  (counts as a detail lookup), not the free dev plan; removed listings follow the archive rules of
  `inspection()`.
- New: `korea.bulk_diagnoses(ids)` (`POST /api/diagnosis/bulk`, Business/Scale; trials 1,000 ids per day): up
  to 500 ids, same envelope as `bulk_vehicles()` plus `noDiagnosis` (listings without a diagnosis); prefixed
  ids are listed under `encarOnly`.
- API release 3 November 2026: Encar payloads of `vehicle()` and `bulk_vehicles()` end with `diagnosisReport`
  (`{"diagnosisDate", "realDiagnosisDate", "items"}`, `None` = no diagnosis). Not on KB Chachacha / K Car
  payloads, not translated with `lang`. A new or changed diagnosis does not create an event in `changes()`:
  fetch it when a listing first appears and re-check with `bulk_diagnoses()` on your own schedule.
- Typing only: `TypedDict`s `DiagnosisItem`, `DiagnosisReport`, `DiagnosisResponse` and
  `DiagnosisBulkResponse` (exported from `encarapi`); responses stay plain dicts.

## 1.7.0

- New: `korea.export_to_file(path, **params)` and `china.export_to_file(path, **params)` stream the full
  catalog export to a file in chunks instead of holding it in memory and return
  `{"path", "bytes", "generated_at"}`. `generated_at` is the export's timestamp header (Korea
  `X-Encarapi-Generated-At`, China `x-generated-at`; `None` if absent): pass it as `since` to `changes()` /
  `iterate_changes()` for the first sync, then continue with the cursor. The file is written to
  `<path>.part` and renamed when complete. Same for the Korea truck and equipment exports:
  `korea.export_trucks_to_file()` and `korea.export_equipment_to_file()`. `export_csv()`, `trucks_csv()`
  and `equipment_csv()` are unchanged.
- China: Russian values (API release 22 October 2026). `catalog`, `vehicle`, `vehicle_by_url`,
  `bulk_vehicles` and `specs` take `lang="ru"`: fuel, transmission, drivetrain, colours, seller type,
  condition, vehicle class, city names and equipment names in Russian; make, model and trim names stay
  Latin. `enums(lang="ru")` adds `nameRu` to fuels and cities, `export_csv(lang="ru")` returns the label
  columns in Russian.
- `china.specs(trim_id, **params)` now passes params (`lang`); before, it took none.

## 1.6.0

- Russian and German values (API release 22 October 2026): every Korea call that takes `lang="en"` now also
  takes `lang="ru"` or `lang="de"`. Display values (fuel, transmission, colors, body class, sell type,
  regions, options; with `"de"` also model and trim names) come in Russian or German, ids and codes stay the
  same, and the filters accept these values as well. `enums(lang=...)` adds `nameRu` / `nameDe`, the
  reference CSVs get an extra `*_ru` / `*_de` column, `export_csv(lang=...)` has the label columns translated.
- `korea.bulk_vehicles(ids, lang=...)` passes `lang` like `vehicle()` (before, it took no options).

## 1.5.1

- Docs only, no runtime change. API release 22 October 2026: Encar items of the change feed
  (`korea.changes()` / `iterate_changes()`) carry `Accident`, `SimpleRepair` and `InspectionAvailable`
  (accident status from Encar's performance inspection; `None` = not known yet), and `export_csv()` has the
  same data in the new last columns `accident`, `simple_repair` and `inspection_available` (empty = not
  known, `inspection_available=false` = no inspection report at our last detail fetch).
- When a listing's detail is collected for the first time, the change feed sends one extra `updated` event
  with `inspection` in `changedFields` (about one per new listing), so a local copy learns the accident
  status. A change to the simple-repair flag alone now arrives with `accident`. Existing local copies:
  pull `export_csv()` once to fill the new columns for listings that get no event.

## 1.5.0

- China: `china.vehicle_by_url(url)` (`GET /api/vehicle/by-url`) returns the full record for a Che168 or
  Dongchedi listing link - desktop, mobile site (e.g. `m.che168.com/cardetail/index?infoid=...`) or app,
  also inside a pasted share text. Short links are not resolved.
- China: `catalog()` accepts `power_min` / `power_max` (hp). With either set, cars without a known power
  figure are left out.

## 1.4.1

- Korea change feed: every entry now carries `eventId` (its position in the log, same scale as `nextCursor`)
  and `occurredAt`. `iterate_changes()` yields the entries of a page in event order across the groups, so a
  later event for the same listing always comes last (e.g. `removed` after `updated`).

## 1.4.0

- `china.specs(trim_id)`: Autohome specification sheet of a Che168 trim (displacement in cc, power in kW
  and hp also for EVs, torque, emission standard, wheelbase, weights, tank, gears, drive type, EV battery).
- China vehicle records now carry `manufactureDate` (Che168, month of manufacture where published) and a
  `specs` object with the key figures of the trim sheet; the CSV export gained `manufacture_date`,
  `displacement_cc` and `power_kw`.

## 1.3.1

- `korea.truck(id)`: one truck with detail page, inspection report, cargo box dimensions, VIN and plate.

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
