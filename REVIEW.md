# Quality review — workshop package

**Review date:** 2026-10-21  
**Scope:** workspace brief, interactive teaching flow, three supplier REST/MCP specifications, three static JSON fixtures, browser API illustration.

## Review outcome

**Overall: suitable as a design package; not yet ready to run live.** That is intentional: API/MCP backends and Codespaces configs are scheduled for later implementation.

### Confirmed by a separate consistency-check pass

- [x] The three merchants retain **different REST API contracts**. Each has its own independent MCP adapter.
- [x] MCP discovery showcases **9 tools, 4 resources, 4 prompts**.
- [x] **Two prompts** appear at Prix Malin; **two resources** appear at BricoPro.
- [x] `WORKSHOP_FLOW.md` is in English, interactive and based on business decisions, not coding exercises.
- [x] The workspace brief requires **browser only**, no local software, no `git clone`, no checkout or mutable inventory.
- [x] API refresher includes an *explicitly marked illustrative* browser/Network screenshot.
- [x] The capstone uses **10 guests**, minimum **10 portions**, family equipment, an organic pack, shops open at 16:30, and a feasible **€150** budget.
- [x] The 18:30 variant tests store hours rather than fabricated real-time inventory changes.

### Instructor-only arithmetic sanity check

One valid basket for the €150 / 16:30 capstone, using the existing fixtures (not an assertion that this is the only optimum):

| Merchant | SKU | Description | Price |
|---|---|---|---:|
| BricoPro | BP-101 | Family charcoal barbecue (8–12 guests) | €89.90 |
| BricoPro | BP-103 | Charcoal 5 kg | €8.90 |
| BricoPro | BP-105 | Firelighters | €2.90 |
| BricoPro | BP-106 | BBQ tongs | €5.90 |
| HyperMax | HMX-005 | Organic sausages x6 | €9.90 |
| Prix Malin | PM-001 | Regular sausages x6 | €4.50 |
| Prix Malin | PM-005 | Fries 1 kg | €1.80 |
| HyperMax | HMX-007 | Chips 200 g | €1.60 |
| HyperMax | HMX-011 ×3 | Cola 1.5 L ×3 | €3.45 |
| | | **Total** | **€128.85** |

**Conditions satisfied:** 12 meat portions, six organic; fries + chips + 4.5 L drinks; grill for 10; fuel + firelighters + tongs with documented model compatibility. All three stores are open at 16:30; no missing stock for these quantities. The minimal portion requirement is a teaching convention, not a catering recommendation.

## Remaining risks / open implementation tasks

| Priority | Finding | Required action before class |
|---|---|---|
| ~~Blocking~~ Done | REST APIs and MCP servers implemented, run inside the Codespace. | 87 pytest tests; `scripts/smoke.py` checks 9 tools / 4 resources / 4 prompts over HTTP; agent-verified with `TEST_PROMPTS.md`. |
| ~~Blocking~~ Done | Codespaces files and staged MCP configs committed. | `.devcontainer/`, `.vscode/mcp.json`, `.workshop/mcp-stages/01–03` (localhost URLs). |
| **Blocking** | End-to-end browser Codespaces + Copilot Agent + local HTTP MCP, including resources/prompts, has not been proven with a clean GitHub Free account. | Full dress rehearsal with a new personal account: services auto-start, MCP trust prompt, slash-command prompts, resource attachment. |
| **Medium** | Supplier technical READMEs are in French, while the participant workshop is in English. | Translate the technical docs before asking students to read them; otherwise keep them organizer-facing and direct students to the English workshop page. |
| **Medium** | The browser screenshot is a teaching *mock-up* of a Network inspector, not an authentic Chrome DevTools screenshot. | Keep its clear label. If an authentic capture is mandatory, take one from a real demo site during implementation. |
| **Medium** | Feasibility depends on a model calling the right tools. The model may guess instead. | Require a visible tool trace, grounded line items and explicit uncertainty; provide sample expected result. |
| **Low** | No travel distance or delivery data are present. | Treat the shopping time as a common check time, not a claim that all visits can occur simultaneously. |
| **Low** | Merchant stocks and prices are fixed in JSON. | Say clearly that this is a static scenario, not a live commerce system. |

## Independent-agent review handoff

**A second autonomous reviewer is not available inside this session.** The assessment above is a separate consistency-check pass, **not** a claim that another AI agent reviewed it. To commission a genuinely independent agent later, provide the unpacked repository with the following review request:

> Review this repository as a skeptical workshop designer and MCP integration engineer. Do not assume the author is correct. Check: (1) browser-only beginner setup on a fresh GitHub Free account, (2) accurate VS Code / MCP behavior for tools, prompts and resources, (3) three independent merchant API contracts, (4) staged discovery that begins with one visible MCP, (5) validity of all student exercises against the source JSON (price, stock, hours, organic, equipment capacity/compatibility), (6) distinction between mocked screenshots and live execution, and (7) minimum, English-language teaching support for master’s-level business/tech students. Return blocking, important and cosmetic findings, plus precise file edits. Do not invent deployed URLs or pretend the APIs exist. Where behavior is version-dependent, demand a real smoke test.

### Practical re-review gate

Re-run this review **after** the backends are deployed and the staged config files exist. A separate agent should challenge runtime assumptions, not just read the static documentation.
