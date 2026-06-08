# EnCarAPI — Python client for the Encar API (Korean car data)

Official **Python client** for the [EnCarAPI](https://encarapi.com) — a REST **Encar API** /
**Korean Car API** that gives you real-time Korean used-car data from **Encar.com**:
vehicle listings, photos, full specifications, options, price history and dealer info.

Built for car exporters, dealers and platforms that need reliable **Korean car data**
without scraping, proxies or geo-blocks.

> 🔑 **An EnCarAPI key is required.** The API and its data are a paid service.
> Get a key (5-day trial available) at **[encarapi.com](https://encarapi.com)**.

## Install

```bash
pip install git+https://github.com/ThatMojo/encarapi-python.git
```

(A PyPI release — `pip install encarapi` — is coming soon.)

## Quick start

```python
from encarapi import EnCarAPI

# Get your key at https://encarapi.com
client = EnCarAPI("YOUR_API_KEY")        # or set ENCARAPI_KEY in your environment

# Search & filter the Korean car catalog (Encar.com listings)
cars = client.catalog(count=True)

# Filter facets (brands, models, counts)
facets = client.nav()

# Full detail for one vehicle: specs, options, inspection, price
detail = client.vehicle("12345678")
```

Without a valid key every call raises a clear error pointing you to
[encarapi.com](https://encarapi.com) — there's no free data here, just a clean client
for the paid API.

## Why EnCarAPI?

- **Real-time Encar.com data** — listings, photos, specs, options, price history.
- **Korean → English** field mapping handled for you.
- **One REST API** instead of brittle scrapers, proxies and bot defenses.
- **Plans from €149/month**, with a 5-day trial.

## Methods

| Method | Endpoint | Description |
|---|---|---|
| `client.catalog(**params)` | `GET /api/catalog` | Search & filter Korean car listings |
| `client.nav(**params)` | `GET /api/nav` | Filter facets / navigation metadata |
| `client.vehicle(id)` | `GET /api/vehicle/:id` | Full per-vehicle detail |

## Links

- 🌐 Website & pricing: **https://encarapi.com**
- 📖 API documentation: **https://encarapi.com/documentation**
- 📦 Node.js client: **https://github.com/ThatMojo/encarapi-node**

## License

MIT for this client library. Use of the EnCarAPI service itself requires a valid API
key and is subject to the EnCarAPI terms at [encarapi.com](https://encarapi.com).

---

*Keywords: Encar API, Encar.com API, Korean Car API, Korea car API, Korean used car
data, Korean car data API, car export Korea, vehicle data API, Encar data.*
