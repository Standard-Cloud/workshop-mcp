#!/usr/bin/env bash
# Start (or restart) the 3 REST APIs and the 3 MCP servers in the background.
set -euo pipefail
cd "$(dirname "$0")/.."
LOGS=/tmp/workshop-logs
mkdir -p "$LOGS"
SERVICES=(prix-malin-api hypermax-api bricopro-api prix-malin-mcp hypermax-mcp bricopro-mcp)

for name in "${SERVICES[@]}"; do
  pid="$LOGS/$name.pid"
  [ -e "$pid" ] && kill "$(cat "$pid")" 2>/dev/null || true
  rm -f "$pid"
done
sleep 1

start() {  # name, command...
  local name=$1; shift
  setsid nohup "$@" >"$LOGS/$name.log" 2>&1 < /dev/null &
  echo $! > "$LOGS/$name.pid"
}

start prix-malin-api python -m uvicorn api:app --app-dir prix-malin --host 0.0.0.0 --port 8001
start hypermax-api   python -m uvicorn api:app --app-dir hypermax   --host 0.0.0.0 --port 8002
start bricopro-api   python -m uvicorn api:app --app-dir bricopro   --host 0.0.0.0 --port 8003
start prix-malin-mcp python prix-malin/mcp_server.py
start hypermax-mcp   python hypermax/mcp_server.py
start bricopro-mcp   python bricopro/mcp_server.py

for port in 8001 8002 8003 9001 9002 9003; do
  for _ in $(seq 30); do
    (echo > "/dev/tcp/127.0.0.1/$port") 2>/dev/null && break
    sleep 1
  done
  (echo > "/dev/tcp/127.0.0.1/$port") 2>/dev/null || { echo "Port $port not ready, see $LOGS"; exit 1; }
done
sleep 2
for name in "${SERVICES[@]}"; do  # a process that died (e.g. port already taken) means an old server is still answering
  kill -0 "$(cat "$LOGS/$name.pid")" 2>/dev/null || { echo "$name exited, see $LOGS/$name.log"; exit 1; }
done
echo "Workshop servers ready: APIs on 8001-8003, MCP on 9001-9003/mcp (logs in $LOGS)"
