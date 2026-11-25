#!/usr/bin/env bash
# Pengujian end-to-end semua endpoint CRUD lewat Lambda Function URL.
# Pemakaian:  ./scripts/test_api.sh https://xxxxxx.lambda-url.us-east-1.on.aws
set -euo pipefail

API="${1:?Pemakaian: $0 <FUNCTION_URL>}"
API="${API%/}"

hr() { printf '\n===== %s =====\n' "$1"; }

hr "1. CREATE  POST /tickets"
CREATED=$(curl -sS -X POST "$API/tickets" \
  -H "Content-Type: application/json" \
  -d '{"title":"Wifi lab mati","description":"Tidak bisa connect sejak pagi","priority":"high","reporter":"Nabil"}')
echo "$CREATED"
ID=$(echo "$CREATED" | python3 -c 'import sys,json; print(json.load(sys.stdin)["ticketId"])')
echo "ticketId = $ID"

hr "2. READ ALL  GET /tickets"
curl -sS "$API/tickets"; echo

hr "3. READ ONE  GET /tickets/$ID"
curl -sS "$API/tickets/$ID"; echo

hr "4. UPDATE  PUT /tickets/$ID"
curl -sS -X PUT "$API/tickets/$ID" \
  -H "Content-Type: application/json" \
  -d '{"status":"closed"}'; echo

hr "5. DELETE  DELETE /tickets/$ID"
curl -sS -X DELETE "$API/tickets/$ID"; echo

hr "6. VERIFY  GET /tickets/$ID (harus 404)"
curl -sS -w '\nHTTP %{http_code}\n' "$API/tickets/$ID"
