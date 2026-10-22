#!/usr/bin/env bash
# Show what this merchant's MCP server returns, using plain curl (JSON-RPC over HTTP).
# Usage: bash demo.sh [MCP_URL]   — the servers must be running (scripts/start.sh).
set -euo pipefail
URL=${1:-http://localhost:9001/mcp}

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

mcp "Meat in stock" tools/call '{"name":"list_current_arrivals","arguments":{"family":"viande","available_only":true}}'
mcp "Sold-out chicken skewers" tools/call '{"name":"get_arrival_details","arguments":{"arrival_code":"PM-004"}}'
mcp "Unknown product (chips are not sold)" tools/call '{"name":"get_arrival_details","arguments":{"arrival_code":"CHIPS"}}'
mcp "Basket check at 16:30" tools/call '{"name":"check_purchase_feasibility","arguments":{"items":[{"arrival_code":"PM-001","packs":2},{"arrival_code":"PM-004","packs":3},{"arrival_code":"PM-005","packs":2},{"arrival_code":"CHIPS","packs":1}],"shopping_time":"16:30"}}'
mcp "Same basket at 18:30 (store closed)" tools/call '{"name":"check_purchase_feasibility","arguments":{"items":[{"arrival_code":"PM-001","packs":2}],"shopping_time":"18:30"}}'

mcp "Resource: store policy" resources/read '{"uri":"prixmalin://store/policy"}'
mcp "Prompt: find_lowest_cost_meal" prompts/get '{"name":"find_lowest_cost_meal","arguments":{"guests":"10","budget_eur":"40","shopping_time":"16:30"}}'
mcp "Prompt: adapt_to_arrivals" prompts/get '{"name":"adapt_to_arrivals","arguments":{"requested_items":"chicken skewers, fries, chips","shopping_time":"16:30"}}'
