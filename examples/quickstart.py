"""EnCarAPI Python quickstart. Get a key at https://encarapi.com"""
import os

from encarapi import EnCarAPI

client = EnCarAPI(os.environ["ENCARAPI_KEY"])  # required

# Korean catalog (Encar by default), English values, with total count
kr = client.korea.catalog(manufacturer="Hyundai", lang="en", limit=5, count=True)
print("Korea:", kr.get("Count"), "matches")

# All three Korean marketplaces, deduplicated (plan-dependent, see encarapi.com/#pricing)
# everything = client.korea.catalog(source="all", limit=5, count=True)

# Full detail for one vehicle (Encar id, "kbc:<id>" or "kcar:<id>")
# car = client.korea.vehicle("12345678")

# Chinese listings (ChinaCarAPI key or EnCarAPI key with the China add-on)
# cn = client.china.catalog(make="BYD", limit=5)
