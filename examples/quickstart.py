"""EnCarAPI Python quickstart. Get a key at https://encarapi.com"""
import os

from encarapi import EnCarAPI

client = EnCarAPI(os.environ["ENCARAPI_KEY"])  # required

# Newest listings (count=True returns the total available)
catalog = client.catalog(count=True)
print("catalog keys:", list(catalog)[:5] if hasattr(catalog, "__iter__") else catalog)

# Filter facets
facets = client.nav()
print("facets:", str(facets)[:200])

# One vehicle's full detail
# detail = client.vehicle("12345678")
# print(detail)
