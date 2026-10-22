# MCP Business Workshop — Three independent suppliers

**Student-facing entry point:** [Workshop flow and copy/paste challenges](WORKSHOP_FLOW.md)  
**Organizer / implementer:** [GitHub Codespaces workspace specification](GITHUB_WORKSPACE_SPEC.md)  
**Quality review:** [Review and external-agent handoff](REVIEW.md)  
**Verification:** [Reusable test prompts with expected answers](TEST_PROMPTS.md)  
**Instructor demo:** [MCP Agent Inspector](agent-inspector/README.md) — shows step by step what an agent harness does (not used by students)

| Supplier | Business role | Data | REST + MCP spec |
|---|---|---|---|
| Prix Malin | Discount food · 09:00–17:00 | [JSON](prix-malin/donnees.json) | [README](prix-malin/README.md) |
| HyperMax | General hypermarket · 08:00–21:00 | [JSON](hypermax/donnees.json) | [README](hypermax/README.md) |
| BricoPro | DIY and barbecue · 07:00–19:00 | [JSON](bricopro/donnees.json) | [README](bricopro/README.md) |

**Status:** the 3 REST APIs and the 3 MCP servers are implemented (Python, FastAPI, MCP SDK) and start automatically in the Codespace. Merchant technical specifications remain in French; the workshop and the MCP surface are in English.

## Run it

**In a Codespace:** nothing to do. `postStartCommand` runs `scripts/start.sh`, and `.vscode/mcp.json` already points to the Prix Malin MCP server (stage 1).

**Locally:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                  # API + MCP tests, no network
bash scripts/start.sh      # starts the 6 servers in the background (logs: /tmp/workshop-logs)
python scripts/smoke.py    # real HTTP check: 9 tools / 4 resources / 4 prompts
```

| Merchant | REST API (browser: `/docs`) | MCP endpoint |
|---|---|---|
| Prix Malin | http://localhost:8001/docs | http://localhost:9001/mcp |
| HyperMax | http://localhost:8002/docs | http://localhost:9002/mcp |
| BricoPro | http://localhost:8003/docs | http://localhost:9003/mcp |

Try: `curl "http://localhost:8001/magasin/arrivages?famille=viande&disponible=true"`.

To see the raw output of each MCP server (discovery, tools, resources, prompts) with plain `curl`: `bash prix-malin/demo.sh`, `bash hypermax/demo.sh`, `bash bricopro/demo.sh`.

Each MCP server only calls its own merchant's API; the API address can be overridden with `PRIX_MALIN_API_URL`, `HYPERMAX_API_URL` or `BRICOPRO_API_URL`.

**VS Code tasks** (**Terminal → Run Task…**):

| Task | What it does |
|---|---|
| `Servers: restart all` / `stop all` / `show logs` | Manage the 6 background services |
| `MCP: check all servers (smoke test)` | Expect `(9, 4, 4)` |
| `MCP demo: Prix Malin` / `HyperMax` / `BricoPro` | Run the merchant's `demo.sh` |
| `Stage 1` / `Stage 2` / `Stage 3` | Copy the stage snapshot over `.vscode/mcp.json` |
| `Inspector: start (instructor)` | Start the [agent inspector](agent-inspector/README.md) on port 8090 |
| `Tests: run pytest` | Run the test suite |

![Browser API explorer illustration](assets/browser-api-explorer.png)

*Illustrative teaching screenshot, not a real Chrome DevTools capture.*
