# Test prompts — verify the MCP servers with an agent

Paste each prompt in Copilot Chat (**Agent** mode) or any MCP-capable agent. Each one has the expected facts from the JSON fixtures, so you can check the answer quickly. Always look at the **tool calls** in the trace: fluent text alone does not prove the integration works.

Before starting: `python scripts/smoke.py` must print `TOTAL tools/resources/prompts = (9, 4, 4)`. To restart the servers, run **Tasks: Run Task → Servers: restart all**.

## Stage 1 — Prix Malin only (`.vscode/mcp.json`)

**1.1 Discovery**
> Which tools, resources and prompts does the prix-malin MCP server expose? Don't call them, just list them.

Expected: 3 tools (`list_current_arrivals`, `get_arrival_details`, `check_purchase_feasibility`), 1 resource (`prixmalin://store/policy`), 2 prompts (`find_lowest_cost_meal`, `adapt_to_arrivals`).

**1.2 Catalog with cents → EUR conversion**
> List the meat Prix Malin currently has, with pack size, price in EUR and stock. Use the tools.

Expected: PM-001 sausages x6 €4.50 (12 packs), PM-002 merguez x6 €5.20 (8), PM-003 steaks x4 €5.90 (6), PM-004 chicken skewers x4 €6.90 **sold out (0)**.

**1.3 Feasibility, out of stock vs not sold**
> At 16:30, can I buy 2 packs of sausages, 3 packs of chicken skewers, 2 packs of fries and 1 pack of chips at Prix Malin? Use check_purchase_feasibility.

Expected: sausages ok, fries ok, skewers `out_of_stock`, chips `not_found` (not sold). Total **€12.60**, status `partially_feasible`.

**1.4 Store closed**
> Same basket but at 18:30.

Expected: status `store_closed`, nothing buyable, total €0 (open 09:00–17:00).

## Stage 2 — add HyperMax (`02-add-hypermax.json`)

**2.1 Price comparison**
> Compare Prix Malin and HyperMax for sausages x6, fries 1 kg and cola 1.5 L. Which is cheaper for each item? Cite the tool results.

Expected: sausages €4.50 vs €6.20 → Prix Malin; fries €1.80 vs €2.70 → Prix Malin; cola €1.30 vs **€1.15 → HyperMax**.

**2.2 Organic**
> Which supplier sells organic meat? List every organic product with price and stock.

Expected: HyperMax only: HMX-005 organic sausages x6 €9.90 (10), HMX-006 organic steaks x4 €11.50 (8). Prix Malin has none.

**2.3 Opening hours**
> At 18:30, which of the two stores is open? And at 07:30?

Expected: 18:30 → HyperMax open, Prix Malin closed. 07:30 → both closed; HyperMax opens the same day at 08:00.

## Stage 3 — add BricoPro (`03-add-bricopro.json`)

**3.1 Equipment for 10 guests**
> Find a charcoal barbecue for 10 guests at BricoPro, with charcoal, firelighters and tongs. Check every accessory's compatibility with the tool.

Expected: BP-101 family charcoal grill (BBQ-F200, 8–12 people) €89.90; BP-103 charcoal €8.90, BP-105 firelighters €2.90, BP-106 tongs €5.90, all `compatible: true`. Total €107.60.

**3.2 Documented incompatibility vs unknown**
> Is the BricoPro charcoal (BP-103) compatible with the gas barbecue BP-102? And is BP-100 usable as an accessory for BP-101?

Expected: BP-102 + BP-103 → `compatible: false` (documented). BP-101 + BP-100 → `compatible: null` (no data; the agent must not guess).

**3.3 Same model, two merchants**
> The compact barbecue model BBQ-C100 is sold by two merchants. Where is it cheaper?

Expected: BricoPro BP-100 €39.90 vs HyperMax HMX-014 €49.90 → BricoPro.

**3.4 Prompts and resources (selected explicitly, not by the agent)**
- Type `/` in chat → `mcp.prix-malin.find_lowest_cost_meal` with 10 · 40 · 16:30, then `mcp.prix-malin.adapt_to_arrivals` with "chicken skewers, fries, chips" · 16:30.
- **Add Context → MCP Resources** → attach `bricopro://guides/barbecue` and `bricopro://guides/compatibilite`, then ask:
> Using the two attached guides, explain the difference between choosing a grill and checking compatibility.

## Capstone check

> Plan a charcoal barbecue for 10 people. Budget: €150 total, including the grill. Shopping time: 16:30 (Europe/Paris). Include at least 10 meat portions with at least one organic pack, fries, chips, drinks, charcoal, firelighters and a cooking tool. Use the three supplier MCPs; check stock, opening hours, pack sizes and compatibility. Give a shopping list per merchant with the arithmetic of the total.

Expected: one valid answer is about **€128.85** (see `REVIEW.md`): BP-101 + BP-103 + BP-105 + BP-106 at BricoPro; HMX-005 + HMX-007 + 3× HMX-011 at HyperMax; PM-001 + PM-005 at Prix Malin. Other baskets are fine if they're under €150, use in-stock items and include the organic pack from HyperMax. Follow-up: "Change the time to 18:30" → Prix Malin is closed.
