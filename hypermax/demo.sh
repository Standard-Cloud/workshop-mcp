#!/usr/bin/env bash
# Show what this merchant's MCP server returns, using plain curl (JSON-RPC over HTTP).
# Usage: bash demo.sh [MCP_URL]   — the servers must be running (scripts/start.sh).
set -euo pipefail
URL=${1:-http://localhost:9002/mcp}

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

mcp "Organic products only" tools/call '{"name":"search_catalog","arguments":{"organic_only":true}}'
mcp "Text search: cola" tools/call '{"name":"search_catalog","arguments":{"query":"cola"}}'
mcp "Barbecue equipment under 10 EUR" tools/call '{"name":"search_catalog","arguments":{"department":"plein_air","max_price_eur":10}}'
mcp "Product sheet: compact barbecue" tools/call '{"name":"get_product_information","arguments":{"sku":"HMX-014"}}'
mcp "Unknown SKU" tools/call '{"name":"get_product_information","arguments":{"sku":"HMX-999"}}'
mcp "Open at 18:30?" tools/call '{"name":"get_store_opening_status","arguments":{"shopping_time":"18:30"}}'
mcp "Open at 07:15?" tools/call '{"name":"get_store_opening_status","arguments":{"shopping_time":"07:15"}}'

mcp "Resource: categories" resources/read '{"uri":"hypermax://catalog/categories"}'
mcp "Prompt: prepare_organic_barbecue" prompts/get '{"name":"prepare_organic_barbecue","arguments":{"guests":"6","budget_eur":"60","shopping_time":"18:30"}}'
