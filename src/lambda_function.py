"""
Ticketing API - handler AWS Lambda (Track C: Serverless, versi sandbox ACF)

Satu fungsi Lambda menangani semua endpoint CRUD. Request masuk melalui
Lambda Function URL (pengganti API Gateway) dan data tiket disimpan sebagai
file JSON di Amazon S3 (pengganti DynamoDB), dengan key: tickets/{ticketId}.json

Endpoint:
    POST   /tickets          -> create_ticket
    GET    /tickets          -> list_tickets
    GET    /tickets/{id}     -> get_ticket
    PUT    /tickets/{id}     -> update_ticket
    DELETE /tickets/{id}     -> delete_ticket

Environment variable:
    BUCKET_NAME  nama bucket S3 tempat data tiket disimpan (wajib)
"""

import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3

BUCKET = os.environ.get("BUCKET_NAME", "")
PREFIX = "tickets/"
s3 = boto3.client("s3")

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"open", "in_progress", "closed"}
UPDATABLE_FIELDS = {"title", "description", "priority", "status", "reporter"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class NotFound(Exception):
    pass


# ---------- helper ----------

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _parse_body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("Body harus berupa JSON yang valid")
    if not isinstance(data, dict):
        raise ValueError("Body harus berupa JSON object")
    return data


def _validate(data, partial=False):
    if not partial and not str(data.get("title", "")).strip():
        raise ValueError("Field 'title' wajib diisi")
    if "priority" in data and data["priority"] not in VALID_PRIORITIES:
        raise ValueError(f"'priority' harus salah satu dari {sorted(VALID_PRIORITIES)}")
    if "status" in data and data["status"] not in VALID_STATUSES:
        raise ValueError(f"'status' harus salah satu dari {sorted(VALID_STATUSES)}")


# ---------- akses S3 ----------

def _key(ticket_id):
    if not ID_PATTERN.match(ticket_id or ""):
        raise NotFound(ticket_id)
    return f"{PREFIX}{ticket_id}.json"


def _save(item):
    s3.put_object(
        Bucket=BUCKET,
        Key=_key(item["ticketId"]),
        Body=json.dumps(item).encode("utf-8"),
        ContentType="application/json",
    )


def _load(ticket_id):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=_key(ticket_id))
    except s3.exceptions.NoSuchKey:
        raise NotFound(ticket_id)
    return json.loads(obj["Body"].read())


# ---------- operasi CRUD ----------

def create_ticket(event):
    data = _parse_body(event)
    _validate(data)
    now = _now()
    item = {
        "ticketId": str(uuid.uuid4()),
        "title": data["title"].strip(),
        "description": data.get("description", ""),
        "priority": data.get("priority", "medium"),
        "status": "open",
        "reporter": data.get("reporter", "anonymous"),
        "createdAt": now,
        "updatedAt": now,
    }
    _save(item)
    return _response(201, item)


def list_tickets():
    items = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read()
            items.append(json.loads(body))
    items.sort(key=lambda t: t.get("createdAt", ""), reverse=True)
    return _response(200, {"count": len(items), "items": items})


def get_ticket(ticket_id):
    return _response(200, _load(ticket_id))


def update_ticket(ticket_id, event):
    data = _parse_body(event)
    fields = {k: v for k, v in data.items() if k in UPDATABLE_FIELDS}
    if not fields:
        raise ValueError(f"Tidak ada field yang bisa diupdate. Gunakan: {sorted(UPDATABLE_FIELDS)}")
    _validate(fields, partial=True)
    item = _load(ticket_id)
    item.update(fields)
    item["updatedAt"] = _now()
    _save(item)
    return _response(200, item)


def delete_ticket(ticket_id):
    _load(ticket_id)  # memastikan tiket ada, jika tidak -> 404
    s3.delete_object(Bucket=BUCKET, Key=_key(ticket_id))
    return _response(200, {"message": f"Ticket {ticket_id} berhasil dihapus"})


# ---------- router ----------

def _route(event):
    """Ambil method dan path dari event Function URL (payload format 2.0)."""
    http = (event.get("requestContext") or {}).get("http") or {}
    method = http.get("method", "").upper()
    path = (event.get("rawPath") or http.get("path") or "/").rstrip("/") or "/"
    return method, path


def lambda_handler(event, context):
    method, path = _route(event)
    parts = [p for p in path.split("/") if p]
    print(json.dumps({"method": method, "path": path}))  # -> CloudWatch Logs

    try:
        if parts == ["tickets"]:
            if method == "POST":
                return create_ticket(event)
            if method == "GET":
                return list_tickets()
        elif len(parts) == 2 and parts[0] == "tickets":
            ticket_id = parts[1]
            if method == "GET":
                return get_ticket(ticket_id)
            if method == "PUT":
                return update_ticket(ticket_id, event)
            if method == "DELETE":
                return delete_ticket(ticket_id)
        return _response(404, {"message": f"Endpoint '{method} {path}' tidak dikenal"})
    except NotFound as e:
        return _response(404, {"message": f"Ticket {e} tidak ditemukan"})
    except ValueError as e:
        return _response(400, {"message": str(e)})
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e!r}")
        return _response(500, {"message": "Internal server error"})
