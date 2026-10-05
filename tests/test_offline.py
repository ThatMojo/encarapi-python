"""Offline tests: key gating, request shape and iterators via a fake session.
Run: python -m unittest discover tests"""
import json
import os
import unittest
from unittest import mock

from encarapi import ChinaCarAPI, EnCarAPI, EnCarAPIError, MissingApiKeyError


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self.ok = status < 400
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        return json.loads(self.text)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, params=None, json=None, timeout=None, headers=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json, "headers": headers})
        status, payload = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return FakeResponse(status, payload)


def patch_session(client_http, responses):
    fake = FakeSession(responses)
    fake.headers.update(client_http.session.headers)
    client_http.session = fake
    return fake


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("ENCARAPI_KEY", None)
        os.environ.pop("CHINACARAPI_KEY", None)

    def tearDown(self):
        self.env.stop()

    def test_key_required(self):
        with self.assertRaises(MissingApiKeyError) as ctx:
            EnCarAPI()
        self.assertIn("encarapi.com", str(ctx.exception))
        with self.assertRaises(MissingApiKeyError) as ctx:
            ChinaCarAPI()
        self.assertIn("chinacarapi.com", str(ctx.exception))

    def test_korea_catalog_params(self):
        client = EnCarAPI("kr_key", china_key="cn_key")
        fake = patch_session(client.korea._http, [(200, {"Count": 1, "SearchResults": [{"Id": "1"}]})])
        res = client.korea.catalog(manufacturer="BMW", frame_clean=True, options=["a", "b"], page=None)
        self.assertEqual(res["Count"], 1)
        call = fake.calls[-1]
        self.assertEqual(call["url"], "https://api.encarapi.com/api/catalog")
        self.assertEqual(call["params"], {"manufacturer": "BMW", "frame_clean": "true", "options": "a,b"})
        self.assertEqual(fake.headers["x-api-key"], "kr_key")

    def test_prefixed_id_and_bulk(self):
        client = EnCarAPI("kr_key")
        fake = patch_session(client.korea._http, [(200, {})])
        client.korea.vehicle("kbc:123")
        self.assertTrue(fake.calls[-1]["url"].endswith("/api/vehicle/kbc%3A123"))
        client.korea.bulk_vehicles(["1", "2"])
        self.assertEqual(fake.calls[-1]["method"], "POST")
        self.assertEqual(fake.calls[-1]["json"], {"ids": ["1", "2"]})

    def test_china_uses_china_key_and_host(self):
        client = EnCarAPI("kr_key", china_key="cn_key")
        fake = patch_session(client.china._http, [(200, {"total": 0, "results": []})])
        client.china.catalog(make="BYD")
        self.assertTrue(fake.calls[-1]["url"].startswith("https://api.chinacarapi.com/"))
        self.assertEqual(fake.headers["x-api-key"], "cn_key")

    def test_iterate_changes(self):
        client = EnCarAPI("kr_key")
        fake = patch_session(client.korea._http, [
            (200, {"nextCursor": 10, "hasMore": True, "added": [{"Id": "a"}], "removed": [{"Id": "b"}]}),
            (200, {"nextCursor": 12, "hasMore": False, "updated": [{"Id": "c"}]}),
        ])
        events = list(client.korea.iterate_changes(since="2026-10-01T00:00:00Z"))
        self.assertEqual([f'{e["type"]}:{e["Id"]}' for e in events], ["added:a", "removed:b", "updated:c"])
        self.assertEqual(fake.calls[1]["params"], {"cursor": 10})
        self.assertEqual(client.korea.last_cursor, 12)

    def test_iterate_catalog_stops_on_short_page(self):
        client = EnCarAPI("kr_key")
        patch_session(client.korea._http, [(200, {"SearchResults": [{"Id": "1"}]})])
        self.assertEqual(len(list(client.korea.iterate_catalog(limit=5))), 1)

    def test_china_iterate_catalog(self):
        client = EnCarAPI("kr_key", china_key="cn_key")
        fake = patch_session(client.china._http, [
            (200, {"results": [{"id": "1"}, {"id": "2"}]}),
            (200, {"results": [{"id": "3"}]}),
        ])
        ids = [c["id"] for c in client.china.iterate_catalog(make="BYD", limit=2)]
        self.assertEqual(ids, ["1", "2", "3"])
        self.assertEqual(fake.calls[1]["params"], {"make": "BYD", "limit": 2, "page": 2})

    def test_china_iterate_catalog_depth_limit(self):
        client = ChinaCarAPI("cn_key")
        full_page = (200, {"results": [{"id": str(i)} for i in range(100)]})
        fake = patch_session(client._http, [full_page] * 5)
        self.assertEqual(len(list(client.iterate_catalog(page=99))), 200)
        self.assertEqual([c["params"]["page"] for c in fake.calls], [99, 100])

    def test_china_iterate_changes(self):
        client = EnCarAPI("kr_key", china_key="cn_key")
        fake = patch_session(client.china._http, [
            (200, {"cursor": 0, "nextCursor": 7, "hasMore": True, "changes": [{"id": 5, "vehicleId": "a", "type": "new"}, {"id": 7, "vehicleId": "b", "type": "price"}]}),
            (200, {"cursor": 7, "nextCursor": 9, "hasMore": False, "changes": [{"id": 9, "vehicleId": "c", "type": "removed"}]}),
        ])
        events = list(client.china.iterate_changes(since="2026-10-01T00:00:00Z", source="che168"))
        self.assertEqual([f'{e["type"]}:{e["vehicleId"]}' for e in events], ["new:a", "price:b", "removed:c"])
        self.assertEqual(fake.calls[0]["url"], "https://api.chinacarapi.com/api/catalog/changes")
        self.assertEqual(fake.calls[1]["params"], {"source": "che168", "cursor": 7})
        self.assertEqual(client.china.last_cursor, 9)

    def test_403_carries_body(self):
        client = EnCarAPI("kr_key")
        patch_session(client.korea._http, [(403, {"error": "Upgrade to Business"})])
        with self.assertRaises(EnCarAPIError) as ctx:
            client.korea.changes(cursor=0)
        self.assertEqual(ctx.exception.status, 403)
        self.assertIn("Upgrade to Business", ctx.exception.body)

    def test_legacy_shortcuts(self):
        client = EnCarAPI("kr_key")
        patch_session(client.korea._http, [(200, {"Count": 3, "SearchResults": []})])
        self.assertEqual(client.catalog()["Count"], 3)


if __name__ == "__main__":
    unittest.main()
