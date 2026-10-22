#!/usr/bin/env bash
# Show what this merchant's MCP server returns, using plain curl (JSON-RPC over HTTP).
# Usage: bash demo.sh [MCP_URL]   — the servers must be running (scripts/start.sh).
set -euo pipefail
URL=${1:-http://localhost:9003/mcp}

mcp() {  # title, method, params
  echo
  echo "=== $1"
  echo "--> $2 $3"
  curl -s "$URL" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -H 'MCP-Protocol-Version: 2025-06-18' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$2\",\"params\":$3}" |
    python3 -c '
import json, sys
r = json.load(sys.stdin)
res = r.get("result", r)
if "content" in res:  # tool result: the payload is JSON text
    print("is_error:", res.get("isError", False))
    text = res["content"][0]["text"]
    try:
        res = json.loads(text)
    except ValueError:
        res = text
print(json.dumps(res, indent=2, ensure_ascii=False))'
}

mcp "Discovery: tools" tools/list '{}'
mcp "Discovery: resources" resources/list '{}'
mcp "Discovery: prompts" prompts/list '{}'

mcp "Charcoal barbecues" tools/call '{"name":"find_barbecue_equipment","arguments":{"category":"barbecues","fuel_type":"charbon"}}'
mcp "Equipment specs: family barbecue" tools/call '{"name":"get_equipment_specs","arguments":{"reference":"BP-101"}}'
mcp "Compatible: charcoal + family barbecue" tools/call '{"name":"check_accessory_compatibility","arguments":{"barbecue_reference":"BP-101","accessory_reference":"BP-103"}}'
mcp "Documented incompatible: charcoal + gas barbecue" tools/call '{"name":"check_accessory_compatibility","arguments":{"barbecue_reference":"BP-102","accessory_reference":"BP-103"}}'
mcp "Unknown: no compatibility data" tools/call '{"name":"check_accessory_compatibility","arguments":{"barbecue_reference":"BP-101","accessory_reference":"BP-100"}}'
mcp "Unknown reference" tools/call '{"name":"get_equipment_specs","arguments":{"reference":"BP-999"}}'

mcp "Resource: barbecue guide" resources/read '{"uri":"bricopro://guides/barbecue"}'
mcp "Resource: compatibility guide" resources/read '{"uri":"bricopro://guides/compatibilite"}'
mcp "Prompt: choose_barbecue_setup" prompts/get '{"name":"choose_barbecue_setup","arguments":{"guests":"10","budget_eur":"120","fuel_preference":"charbon"}}'
