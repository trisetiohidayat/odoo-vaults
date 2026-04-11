---
type: module
name: mrp
version: Odoo 18
models_count: ~25
documentation_date: 2026-04-11
tags: [mrp, manufacturing, bom, workorder, production]
---

# MRP

Manufacturing Resource Planning — Bill of Materials, work orders, and production orders.

## Models

### mrp.production

Manufacturing order (MO). States: `draft` → `confirmed` → `planned` → `progress` → `done` → `cancel`.

**Key Fields:**
- `name` — MO reference (auto from sequence)
- `product_id` (`product.product`) — Product to manufacture
- `product_qty` — Quantity to produce
- `product_uom_id` (`uom.uom`) — Unit of measure
- `bom_id` (`mrp.bom`) — Bill of Materials used
- `state` — `draft`, `confirmed`, `planned`, `progress`, `done`, `cancel`
- `date_start`, `date_finished` — Scheduled dates
- `date_deadline` — Due date
- `location_src_id`, `location_dest_id` — Components source / Finished goods destination
- `move_raw_ids` — Component consumption moves (stock.move, auto-created from BoM)
- `move_finished_ids` — Finished goods moves
- `workorder_ids` — Work orders (auto-created from routing)
- `consume_quality_check` (`Boolean`) — Triggers quality checks
- `qty_producing` — Current quantity being produced (for backorders)
- `lot_producing_id` (`stock.lot`) — Serial number for product
- `user_id` — Responsible user
- `company_id`
- `scrap_ids` — Scrap records
- `show_final_lot_button`, `show_allocation` — UI flags

**L3 Workflow:**
`_action_generateManufacturingOrder()` creates MO from sales order line:
1. `_update_bom_lines_and_stock_moves()` — Updates raw material moves from BoM
2. `action_confirm()` — `confirmed` state
3. `action_plan()` — Creates `mrp.workorder` records from routing; `planned` state
4. `button_mark_done()` — `progress` → `done`: calls `_post_inventory()`, `_cal_price()`
5. `_post_inventory()` — Creates accounting entries for consumed components + finished goods
6. `_cal_price()` — Overwrites `product.product.standard_price` with actual cost (uses average of component costs)

**Backorder flow:** `button_mark_done()` with `qty_producing < product_qty` creates backorder MO via `action_generateManufacturingOrder()`.

### mrp.bom

Bill of Materials.

**Key Fields:**
- `name`, `code` — BoM reference
- `product_tmpl_id` OR `product_id` — Applies to template or specific variant
- `type` — `normal` (regular), `phantom` (kit — dissolves into component moves), `subcontract` (subcontracting)
- `ready_to_produce` — `all_available` (start when all components available) or `asap` (start as soon as any available)
- `produce_everything` — Produce full quantity at once
- `capacity` — Number of finished units per production cycle
- `consumption` — `strict` (exact consumption) or `flexible` (allow variances)
- `company_id`
- `bom_line_ids` — Component lines
- `operation_ids` — Routing workcenters

**L3 BoM Explosion:** `explode()` method:
- Recursive for subassemblies (phantom BoM dissolved)
- Respects `allow_mrp_workorder_dependencies` flag
- Generates `mrp.workorder` records for each routing operation

**`_check_bom_cycle()`** — DFS cycle detection in BoM structure.

### mrp.bom.line

**Key Fields:**
- `product_id`, `product_qty`, `product_uom_id`
- `bom_id`, `operation_id` — Optional routing step
- `attachments_flag` (`Boolean`) — Has bom documents attached
- `allow_mrp_workorder_dependencies` — Can this line wait for previous workorder?
- `delay_alert` — Triggers delay warning

### mrp.routing.workcenter (mrp.workcenter.capacity)

Links BoM to workcenters (routing operations).

**Key Fields:**
- `workcenter_id` (`mrp.workcenter`)
- `name` — Operation name
- `workorder_count` (computed)
- `time_cycle` — Time to complete one unit (in hours or minutes)
- `time_mode` — `auto` (from workcenter) or `manual`
- `batch_size` — Units per batch
- `sequence`

**`_check_no_cyclic_dependencies()`** — Validates no circular workorder dependencies.

### mrp.workcenter

**Key Fields:**
- `name`, `capacity` — Simultaneous parallel operations
- `time_start`, `time_stop` — Setup/teardown time
- `time_efficiency` — Efficiency percentage (100=perfect)
- `costs_hour` — Hourly cost
- `categ_id` (`mrp.workcenter.categ`)
- `allow_calendar` (`Boolean`) — Use working hours?
- `resource_calendar_id` (`resource.calendar`) — Working schedule

**L3 OEE (Overall Equipment Effectiveness):**
`oee = availability × performance × quality`
- `availability`: time_running / (time_running + time_losses)
- `performance`: (ideal_cycle_time × total_units) / working_time
- `quality`: good_units / total_units

**`_get_first_available_slot()`** — Finds next available slot using resource calendar, 50-iteration max, 2-hour step.

### mrp.workorder

**Key Fields:**
- `name` — Operation name
- `production_id` (`mrp.production`) — Parent MO
- `workcenter_id`
- `duration` — Total duration (sum of time_ids)
- `state` — `pending`, `ready`, `progress`, `done`, `cancel`
- `time_ids` (`mrp.workcenter.productivity`) — Time tracking lines
- `blocked_by_workorder_ids` — Dependency on previous workorder
- `next_work_order_id` — Next in sequence
- `time_start`, `time_stop` — Setup time
- `operation_id` — Links to `mrp.routing.workcenter`

**L3 Workorder Scheduling:**
- `_compute_state()` — NOT stored; recalculates on demand: pending → ready (when blocked_by done) → done
- `_get_first_available_slot()` — 700-day lookahead; calls `resource.calendar.plan_hours()` with workcenter leaves

**L3 Productivity Tracking:**
`mrp.workcenter.productivity`: records time segments with loss type:
- `productive` (type='production_time')
- `downtime` categories: `availability`, `performance`, `quality`
Loss computation: `duration - (ideal_duration × efficiency)`

### mrp.unbuild

Reverse manufacturing — disassembles a finished MO back into components.

**Key Fields:** `product_id`, `product_qty`, `mo_id` (`mrp.production`), `location_id`, `scrap_location_id`, `lot_id`

**L3:** `_generate_moves()` creates stock moves opposite to original MO: consumes finished product, produces components. Handles byproduct cost share.

### mrp.scrap

Records scrap from production. `product_id`, `production_id`, `workorder_id`, `scrap_qty`, `location_id`, `scrap_location_id`.

### mrp.consumption

Tracks under/consumption during MO. `mrp.consumption.line`: `product_id`, `consumption`, `mrpBomLine`.

## Subcontracting (mrp_subcontracting)

- `mrp.subcontracting.balance` — Tracks subcontracted component quantities per type
- `mrp.subcontracting.account.move` — Links `stock.valuation.layer` to `account.move` for subcontract costs

## Integrations

- **Stock**: Consumes components (`stock.move` from `move_raw_ids`), produces finished goods (`move_finished_ids`)
- **Quality**: `consume_quality_check` triggers quality checks at production
- **Project**: Timesheets linked to workorders
- **Account**: `stock.valuation.layer` + `account.move` for real-time valuation

## Code

- Models: `~/odoo/odoo18/odoo/addons/mrp/models/`
