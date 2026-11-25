"""
Unit test lokal untuk lambda_function.py tanpa koneksi AWS.
boto3 diganti dengan client S3 tiruan yang menyimpan data di memori.

Jalankan:  python3 -m unittest discover -s tests -v
"""

import io
import json
import os
import sys
import types
import unittest


# ---------- S3 tiruan ----------

class NoSuchKey(Exception):
    pass


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.exceptions = types.SimpleNamespace(NoSuchKey=NoSuchKey)

    def put_object(self, Bucket, Key, Body, **_):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise NoSuchKey(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def get_paginator(self, _name):
        fake = self

        class Paginator:
            def paginate(self, Bucket, Prefix):
                keys = [k for k in fake.objects if k.startswith(Prefix)]
                yield {"Contents": [{"Key": k} for k in keys]} if keys else {}

        return Paginator()


fake_s3 = FakeS3()
fake_boto3 = types.ModuleType("boto3")
fake_boto3.client = lambda _name: fake_s3
sys.modules["boto3"] = fake_boto3
os.environ["BUCKET_NAME"] = "test-bucket"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import lambda_function as lf  # noqa: E402


def call(method, path, body=None):
    event = {"rawPath": path, "requestContext": {"http": {"method": method, "path": path}}}
    if body is not None:
        event["body"] = body if isinstance(body, str) else json.dumps(body)
    resp = lf.lambda_handler(event, None)
    return resp["statusCode"], json.loads(resp["body"])


class TicketApiTest(unittest.TestCase):
    def setUp(self):
        fake_s3.objects.clear()

    def test_alur_crud_lengkap(self):
        code, t = call("POST", "/tickets", {"title": "Wifi lab mati", "priority": "high", "reporter": "Nabil"})
        self.assertEqual(code, 201)
        self.assertEqual(t["status"], "open")
        tid = t["ticketId"]
        self.assertIn(f"tickets/{tid}.json", fake_s3.objects)

        code, lst = call("GET", "/tickets")
        self.assertEqual((code, lst["count"]), (200, 1))
        code, one = call("GET", f"/tickets/{tid}")
        self.assertEqual((code, one["title"]), (200, "Wifi lab mati"))

        code, upd = call("PUT", f"/tickets/{tid}", {"status": "closed"})
        self.assertEqual((code, upd["status"]), (200, "closed"))

        code, _ = call("DELETE", f"/tickets/{tid}")
        self.assertEqual(code, 200)
        self.assertEqual(call("GET", f"/tickets/{tid}")[0], 404)

    def test_title_wajib(self):
        code, body = call("POST", "/tickets", {"priority": "low"})
        self.assertEqual(code, 400)
        self.assertIn("title", body["message"])

    def test_priority_dan_status_tidak_valid(self):
        self.assertEqual(call("POST", "/tickets", {"title": "x", "priority": "urgent"})[0], 400)
        tid = call("POST", "/tickets", {"title": "x"})[1]["ticketId"]
        self.assertEqual(call("PUT", f"/tickets/{tid}", {"status": "done"})[0], 400)

    def test_json_tidak_valid(self):
        self.assertEqual(call("POST", "/tickets", "{bukan json")[0], 400)

    def test_tiket_tidak_ada(self):
        self.assertEqual(call("GET", "/tickets/tidak-ada")[0], 404)
        self.assertEqual(call("PUT", "/tickets/tidak-ada", {"status": "closed"})[0], 404)
        self.assertEqual(call("DELETE", "/tickets/tidak-ada")[0], 404)

    def test_id_tidak_aman_ditolak(self):
        self.assertEqual(call("GET", "/tickets/..%2Fsecret")[0], 404)

    def test_endpoint_tidak_dikenal(self):
        self.assertEqual(call("PATCH", "/tickets")[0], 404)
        self.assertEqual(call("GET", "/users")[0], 404)

    def test_trailing_slash(self):
        self.assertEqual(call("GET", "/tickets/")[0], 200)


if __name__ == "__main__":
    unittest.main()
