---
tags: [odoo, odoo17, module, mrp]
research_depth: deep
---

# MRP Module — Deep Research

**Source:** `addons/mrp/models/` (Odoo 17)

| File | Lines | Purpose |
|------|-------|---------|
| `mrp_production.py` | 2850 | Main production order model |
| `mrp_bom.py` | 646 | Bill of Materials |
| `mrp_workorder.py` | 914 | Operation steps |
| `mrp_workcenter.py` | 519 | Capacity management |
| `mrp_routing.py` | 181 | Routing workcenter usage |

## Module Architecture

```
mrp.bom (Bill of Materials)
  ├── mrp.bom.line (components: product_id, product_qty, operation_id)
  ├── mrp.bom.byproduct (co-products: product_id, product_qty, cost_share)
  └── mrp.routing.workcenter (operations: workcenter_id, time_cycle, blocked_by_operation_ids)

mrp.production (Manufacturing Order)
  ├── move_raw_ids     → stock.move (component consumption)
  ├── move_finished_ids → stock.move (finished product + byproducts)
  └── workorder_ids    → mrp.workorder (operation scheduling)

mrp.workorder
  ├── workcenter_id → mrp.workcenter
  ├── operation_id  → mrp.routing.workcenter
  └── leave_id      → resource.calendar.leaves (planned slot)

mrp.workcenter
  ├── time_ids → mrp.workcenter.productivity (time logs)
  └── capacity_ids → mrp.workcenter.capacity (product-specific capacity)
```

---

## mrp.production (2850 lines)

### Class Definition

```python
# mrp_production.py, line 24
class MrpProduction(models.Model):
    """ Manufacturing Orders """
    _name = 'mrp.production'
    _description = 'Production Order'
    _date_name = 'date_start'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_start asc, id'
```

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reference, auto-generated from picking type sequence, e.g. `MO/00123` |
| `priority` | Selection | PROCUREMENT_PRIORITIES: `'0'` normal, `'1'` urgent. Components reserved by highest priority first |
| `backorder_sequence` | Integer | Backorder numbering sequence (0 = no backorder) |
| `origin` | Char | Source document reference |
| `product_id` | Many2one `product.product` | Product to manufacture. Computed from `bom_id` when bom_id changes |
| `product_variant_attributes` | Many2many | Related to product's variant attributes |
| `workcenter_id` | Many2one `mrp.workcenter` | Search-only field for filtering in views |
| `product_tracking` | Selection | Related from product_id: `'none'`, `'serial'`, `'lot'` |
| `product_tmpl_id` | Many2one | Related from product_id.product_tmpl_id |
| `product_qty` | Float | Quantity To Produce. Computed from bom_id on change. In draft, recomputes from BoM |
| `product_uom_id` | Many2one `uom.uom` | Unit of measure. Computed from bom_id.product_uom_id when bom_id changes |
| `lot_producing_id` | Many2one `stock.lot` | Lot/Serial number assigned to finished goods |
| `qty_producing` | Float | Current quantity being produced on this MO |
| `product_uom_category_id` | Many2one | Related from product |
| `product_uom_qty` | Float | Total quantity converted to product's default UoM |
| `picking_type_id` | Many2one `stock.picking.type` | Operation type (`code = 'mrp_operation'`). Defaults to company's default mrp operation type. Can be overridden by BoM's picking_type_id |
| `use_create_components_lots` | Boolean | Related from picking_type_id |
| `use_auto_consume_components_lots` | Boolean | Related from picking_type_id |
| `location_src_id` | Many2one `stock.location` | Components location (internal usage). From picking_type_id.default_location_src_id |
| `warehouse_id` | Many2one | Related to location_src_id.warehouse_id |
| `location_dest_id` | Many2one `stock.location` | Finished products location. From picking_type_id.default_location_dest_id |
| `date_deadline` | Datetime | Informative deadline, computed from move_finished_ids.date_deadline |
| `date_start` | Datetime | Planned/actual start. Default: `Datetime.now()`. If `default_date_deadline` in context, computed as deadline - 1 hour |
| `date_finished` | Datetime | Expected/actual end. Computed from `bom_id.produce_delay` + workorder durations |
| `duration_expected` | Float | Total expected duration in minutes. Sum of all workorder_ids.duration_expected |
| `duration` | Float | Total real duration. Sum of all workorder_ids.duration |
| `bom_id` | Many2one `mrp.bom` | Bill of Material. Domain filters by company, product_id/variant match, type='normal' |
| `state` | Selection | Computed field. Values: `draft → confirmed → progress → to_close → done → cancel` |
| `reservation_state` | Selection | Computed: `confirmed` (waiting), `assigned` (ready), `waiting` (another operation) |
| `move_raw_ids` | One2many `stock.move` | Component consumption moves. `raw_material_production_id`. Computed from bom_id explosion in draft state |
| `move_finished_ids` | One2many `stock.move` | Finished product + byproducts. `production_id`. Computed in draft state |
| `all_move_raw_ids` | One2many | All raw moves including scrapped |
| `all_move_ids` | One2many | All moves including scrapped |
| `move_byproduct_ids` | One2many | Computed: move_finished_ids where product_id != product_id (byproducts only) |
| `finished_move_line_ids` | One2many `stock.move.line` | Move lines on finished product |
| `workorder_ids` | One2many `mrp.workorder` | Work orders from BoM operations. Computed in draft state from bom_id.explode() |
| `move_dest_ids` | One2many `stock.move` | Downstream moves that consume produced goods |
| `unreserve_visible` | Boolean | Technical: whether unreserve button should be shown |
| `reserve_visible` | Boolean | Technical: whether reserve button should be shown |
| `user_id` | Many2one `res.users` | Responsible person. Defaults to current user, domain restricted to mrp.group_mrp_user |
| `company_id` | Many2one `res.company` | Company. Defaults to env.company |
| `qty_produced` | Float | Computed from done finished moves. Sum of picked quantity on moves where product_id == production.product_id |
| `procurement_group_id` | Many2one `procurement.group` | Groups related procurements and moves |
| `product_description_variants` | Char | Custom description on move |
| `orderpoint_id` | Many2one `stock.warehouse.orderpoint` | Link to reordering rule that triggered MO |
| `propagate_cancel` | Boolean | If checked, cancelling upstream move splits downstream move |
| `delay_alert_date` | Datetime | Latest delay alert date from raw moves. Searchable |
| `json_popover` | Char | JSON data for stock rescheduling popover widget |
| `scrap_ids` | One2many `stock.scrap` | Scrapped products from this MO |
| `scrap_count` | Integer | Number of scrap records |
| `unbuild_ids` | One2many `mrp.unbuild` | Unbuild orders linked to this MO |
| `unbuild_count` | Integer | Number of unbuilds |
| `is_locked` | Boolean | Locks MO from editing after done. Default from group: `not group_unlocked_by_default` |
| `is_planned` | Boolean | True if any workorder has date_start and date_finished |
| `show_final_lots` | Boolean | Computed: True if product tracking != 'none' |
| `production_location_id` | Many2one `stock.location` | Production location. `product_id.property_stock_production` or company's `usage=production` location |
| `picking_ids` | Many2many `stock.picking` | Pickings in the same procurement group |
| `delivery_count` | Integer | Number of delivery pickings |
| `confirm_cancel` | Boolean | True if MO has done moves requiring confirmation to cancel |
| `consumption` | Selection | Inherited from BoM: `flexible` (allowed), `warning` (allowed with warning), `strict` (blocked). Read-only, set at confirmation from `bom_id.consumption` |
| `mrp_production_child_count` | Integer | Number of child MOs (sub-assemblies) |
| `mrp_production_source_count` | Integer | Number of source MOs (that this MO feeds into) |
| `mrp_production_backorder_count` | Integer | Number of backorders in procurement group |
| `show_lock` | Boolean | Whether lock/unlock buttons appear |
| `components_availability` | Char | Latest component availability status text: `'Available'`, `'Not Available'`, `'Exp YYYY-MM-DD'` |
| `components_availability_state` | Selection | `available`, `expected`, `late`, `unavailable`. Searchable |
| `production_capacity` | Float | Max quantity producible from current stock of components |
| `show_lot_ids` | Boolean | Display serial number shortcut on moves |
| `forecasted_issue` | Boolean | True if virtual available of product goes negative at date_start |
| `show_serial_mass_produce` | Boolean | Show "mass produce" action for serial-tracked products with qty > 1 |
| `show_allocation` | Boolean | Show "Allocation" button if other MOs/reservations compete for same stock |
| `allow_workorder_dependencies` | Boolean | Set from bom_id.allow_operation_dependencies |
| `show_produce` | Boolean | Show produce button (True if state in confirmed/progress/to_close and qty_producing is neither 0 nor product_qty) |
| `show_produce_all` | Boolean | Show produce all button (True if state ok and qty_producing == 0 or == product_qty) |
| `is_outdated_bom` | Boolean | True when the linked BoM has been updated since MO creation |

**SQL Constraints:**
```python
# line 254-257
_name_uniq = ('name', 'company_id')  # Reference must be unique per company
qty_positive = 'CHECK (product_qty > 0)'
```

### State Machine (Computed via `_compute_state`, line 531–561)

```
draft → confirmed → progress → to_close → done
                ↘           ↗
                 cancel
```

**State transitions logic:**
1. `draft`: Default when no state or no product_uom_id. Also: if `state == 'draft'` and no moves or moves are all draft
2. `cancel`: If state already cancel, OR all finished moves are cancel
3. `done`: If state already done, OR all raw moves are done/cancel AND all finished moves are done/cancel
4. `to_close`: If all workorders are done/cancel; OR (no workorders and qty_producing >= product_qty)
5. `progress`: If any workorder is progress/done; OR qty_producing > 0; OR any raw move is picked
6. `confirmed`: Otherwise (moves exist but not yet in progress)

```python
# mrp_production.py, lines 531–561
def _compute_state(self):
    for production in self:
        if not production.state or not production.product_uom_id:
            production.state = 'draft'
        elif production.state == 'cancel' or (production.move_finished_ids and all(move.state == 'cancel' for move in production.move_finished_ids)):
            production.state = 'cancel'
        elif (
            production.state == 'done'
            or (production.move_raw_ids and all(move.state in ('cancel', 'done') for move in production.move_raw_ids))
            and all(move.state in ('cancel', 'done') for move in production.move_finished_ids)
        ):
            production.state = 'done'
        elif production.workorder_ids and all(wo_state in ('done', 'cancel') for wo_state in production.workorder_ids.mapped('state')):
            production.state = 'to_close'
        elif not production.workorder_ids and float_compare(production.qty_producing, production.product_qty, precision_rounding=production.product_uom_id.rounding) >= 0:
            production.state = 'to_close'
        elif any(wo_state in ('progress', 'done') for wo_state in production.workorder_ids.mapped('state')):
            production.state = 'progress'
        elif production.product_uom_id and not float_is_zero(production.qty_producing, precision_rounding=production.product_uom_id.rounding):
            production.state = 'progress'
        elif any(production.move_raw_ids.mapped('picked')):
            production.state = 'progress'
```

### action_confirm() — Lines 1416–1457

Confirms the MO: creates stock moves for components and finished goods, adjusts procurement method, and confirms workorders. Does NOT automatically reserve components.

```python
def action_confirm(self):
    self._check_company()
    moves_ids_to_confirm = set()
    move_raws_ids_to_adjust = set()
    workorder_ids_to_confirm = set()
    for production in self:
        production_vals = {}
        if production.bom_id:
            production_vals.update({'consumption': production.bom_id.consumption})
        # For serial tracking: force UoM to product's default UoM
        if production.product_tracking == 'serial' and production.product_uom_id != production.product_id.uom_id:
            production_vals.update({
                'product_qty': production.product_uom_id._compute_quantity(production.product_qty, production.product_id.uom_id),
                'product_uom_id': production.product_id.uom_id
            })
            for move_finish in production.move_finished_ids.filtered(lambda m: m.product_id == production.product_id):
                move_finish.write({
                    'product_uom_qty': move_finish.product_uom._compute_quantity(move_finish.product_uom_qty, move_finish.product_id.uom_id),
                    'product_uom': move_finish.product_id.uom_id
                })
        if production_vals:
            production.write(production_vals)
        move_raws_ids_to_adjust.update(production.move_raw_ids.ids)
        moves_ids_to_confirm.update((production.move_raw_ids | production.move_finished_ids).ids)
        workorder_ids_to_confirm.update(production.workorder_ids.ids)

    move_raws_to_adjust = self.env['stock.move'].browse(sorted(move_raws_ids_to_adjust))
    moves_to_confirm = self.env['stock.move'].browse(sorted(moves_ids_to_confirm))
    workorder_to_confirm = self.env['mrp.workorder'].browse(sorted(workorder_ids_to_confirm))

    # Adjust procurement method (make_to_stock vs make_to_order)
    move_raws_to_adjust._adjust_procurement_method()
    # Confirm all moves (draft → confirmed)
    moves_to_confirm._action_confirm(merge=False)
    # Confirm workorders
    workorder_to_confirm._action_confirm()
    # Trigger procurement scheduler for forecasted shortages
    self.move_raw_ids.with_context(ignore_mo_ids=self.ids + self._context.get('ignore_mo_ids', []))._trigger_scheduler()
    # Also confirm internal pickings (PBM/IBM steps)
    self.picking_ids.filtered(lambda p: p.state not in ['cancel', 'done']).action_confirm()
    # Only set to 'confirmed' if currently 'draft'
    self.filtered(lambda mo: mo.state == 'draft').state = 'confirmed'
    return True
```

**Key behaviors:**
- Sets `consumption` field from `bom_id.consumption` on the MO
- For serial tracking, converts product_qty/product_uom_id to the product's default UoM
- Calls `_adjust_procurement_method()` on raw moves to convert `make_to_order` → `make_to_stock` if stock is available
- Calls `_action_confirm()` on moves: creates stock move lines (draft → confirmed), optionally reserved if `at_confirm` reservation
- Calls `_action_confirm()` on workorders: creates dependencies, links moves
- Triggers the procurement scheduler to create pickings or MO for missing components
- Confirms internal pickings (pre-production/intermediate) if warehouse uses manufacturing steps
- Changes MO state from `draft` → `confirmed`

### action_assign() — Lines 1497–1500

Reserves components at the source location. Calls `stock.move._action_assign()` on all raw moves.

```python
def action_assign(self):
    for production in self:
        production.move_raw_ids._action_assign()
    return True
```

### button_plan() — Lines 1502–1509

Plans workorders into the workcenter calendar. Confirms MO if draft, then calls `_plan_workorders()`.

```python
def button_plan(self):
    orders_to_plan = self.filtered(lambda order: not order.is_planned)
    orders_to_confirm = orders_to_plan.filtered(lambda mo: mo.state == 'draft')
    orders_to_confirm.action_confirm()
    for order in orders_to_plan:
        order._plan_workorders()
    return True
```

### _plan_workorders() — Lines 1511–1537

Plugs workorders into the resource calendar. Links workorders to moves, then plans final workorders backwards.

```python
def _plan_workorders(self, replan=False):
    self.ensure_one()
    if not self.workorder_ids:
        return

    self._link_workorders_and_moves()

    # Plan workorders starting from final ones (those with no dependent workorders)
    final_workorders = self.workorder_ids.filtered(lambda wo: not wo.needed_by_workorder_ids)
    for workorder in final_workorders:
        workorder._plan_workorder(replan)

    workorders = self.workorder_ids.filtered(lambda w: w.state not in ['done', 'cancel'])
    if not workorders:
        return

    # Set MO date_start/date_finished to match earliest/latest WO leave
    self.with_context(force_date=True).write({
        'date_start': min([workorder.leave_id.date_from for workorder in workorders]),
        'date_finished': max([workorder.leave_id.date_to for workorder in workorders])
    })
```

**Dependency handling (`_link_workorders_and_moves`, lines 1459–1495):**
- When `bom_id.allow_operation_dependencies = True`: links each workorder to its `operation_id.blocked_by_operation_ids`
- When disabled: links each workorder to the previous one in sequence within the same BoM (sequential)
- Moves with `operation_id` are linked to the matching workorder; moves without are linked to the last workorder of the relevant BoM

### button_mark_done() — Lines 2002–2122

Main production completion flow. Calls `pre_button_mark_done()` first, then:

1. Finishes all workorders (`button_finish`)
2. Splits off backorders (`_split_productions`)
3. Posts inventory (`_post_inventory`)
4. Triggers reception report
5. Auto-reserves backorders if picking type uses `at_confirm` reservation

```python
def button_mark_done(self):
    res = self.pre_button_mark_done()  # Runs consumption check + backorder check
    if res is not True:
        return res

    if self._context.get('mo_ids_to_backorder'):
        productions_to_backorder = self.browse(self._context['mo_ids_to_backorder'])
        productions_not_to_backorder = self - productions_to_backorder
    else:
        productions_not_to_backorder = self
        productions_to_backorder = self.env['mrp.production']

    productions_not_to_backorder = productions_not_to_backorder.with_context(no_procurement=True)
    self.workorder_ids.button_finish()

    # Create backorders if needed
    backorders = productions_to_backorder and productions_to_backorder._split_productions()
    backorders = backorders - productions_to_backorder

    # Post inventory for components and finished goods
    productions_not_to_backorder._post_inventory(cancel_backorder=True)
    productions_to_backorder._post_inventory(cancel_backorder=True)

    # Mark remaining moves as done with 0 qty instead of cancelling
    (productions_not_to_backorder.move_raw_ids | productions_not_to_backorder.move_finished_ids).filtered(
        lambda x: x.state not in ('done', 'cancel')).write({'state': 'done', 'product_uom_qty': 0.0})

    for production in self:
        production.write({
            'date_finished': fields.Datetime.now(),
            'priority': '0',
            'is_locked': True,
            'state': 'done',
        })

    # Auto-assign backorder moves if reservation_method == 'at_confirm'
    backorders_to_assign = backorders.filtered(
        lambda order: order.picking_type_id.reservation_method == 'at_confirm')
    for backorder in backorders_to_assign:
        backorder.action_assign()
```

### _post_inventory() — Lines 1695–1735

Called by `button_mark_done`. Posts all component and finished product moves.

```python
def _post_inventory(self, cancel_backorder=False):
    moves_to_do, moves_not_to_do, moves_to_cancel = set(), set(), set()
    for move in self.move_raw_ids:
        if move.state == 'done':
            moves_not_to_do.add(move.id)
        elif not move.picked:
            moves_to_cancel.add(move.id)
        elif move.state != 'cancel':
            moves_to_do.add(move.id)

    # Action done on component moves: consumes stock
    self.with_context(skip_mo_check=True).env['stock.move'].browse(moves_to_do)._action_done(cancel_backorder=cancel_backorder)
    self.with_context(skip_mo_check=True).env['stock.move'].browse(moves_to_cancel)._action_cancel()

    moves_to_do = self.move_raw_ids.filtered(lambda x: x.state == 'done') - self.env['stock.move'].browse(moves_not_to_do)

    # Group moves by production order
    moves_to_do_by_order = defaultdict(...)
    for order in self:
        finish_moves = order.move_finished_ids.filtered(lambda m: m.product_id == order.product_id and m.state not in ('done', 'cancel'))
        # Set quantity on finish move to qty_producing - qty_produced
        for move in finish_moves:
            move.quantity = float_round(order.qty_producing - order.qty_produced, precision_rounding=order.product_uom_id.rounding, rounding_method='HALF-UP')
        # Sync workorder durations
        for workorder in order.workorder_ids:
            if workorder.state not in ('done', 'cancel'):
                workorder.duration_expected = workorder._get_duration_expected()
            if workorder.duration == 0.0:
                workorder.duration = workorder.duration_expected
                workorder.duration_unit = round(workorder.duration / max(workorder.qty_produced, 1), 2)
        order._cal_price(moves_to_do_by_order[order.id])  # Cost calculation hook (returns True by default)

    moves_to_finish = self.move_finished_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
    moves_to_finish.picked = True
    moves_to_finish = moves_to_finish._action_done(cancel_backorder=cancel_backorder)

    # Link consume line to finished product move
    for order in self:
        consume_move_lines = moves_to_do_by_order[order.id].mapped('move_line_ids')
        order.move_finished_ids.move_line_ids.consume_line_ids = [(6, 0, consume_move_lines.ids)]
```

### pre_button_mark_done() — Lines 2124–2156

Pre-flight checks before marking done:

1. Sanity check: quantity must be positive
2. Sets `qty_producing` from `move_finished_ids` if zero (for non-serial tracking)
3. Checks consumption issues (strict/warning BOM): triggers consumption wizard if any
4. Checks quantity issues (partial production): triggers backorder wizard if any

```python
def pre_button_mark_done(self):
    self._button_mark_done_sanity_checks()  # Checks company, SN uniqueness
    for production in self:
        if float_is_zero(production.qty_producing, precision_rounding=production.product_uom_id.rounding):
            production._set_quantities()  # Derive qty_producing from finished move lines

    for production in self:
        if float_is_zero(production.qty_producing, precision_rounding=production.product_uom_id.rounding):
            raise UserError(_('The quantity to produce must be positive!'))

    # Check against BoM expected consumption
    consumption_issues = self._get_consumption_issues()
    if consumption_issues:
        return self._action_generate_consumption_wizard(consumption_issues)

    # Check if quantity produced < product_qty (needs backorder handling)
    quantity_issues = self._get_quantity_produced_issues()
    if quantity_issues:
        # Sort by picking_type.create_backorder: "always", "ask", "never"
        # Creates backorder wizard or auto-backorders
        ...
```

### _get_consumption_issues() — Lines 1553–1592

Compares actual consumed quantities against BoM-expected quantities. Returns issues when:
- Consumption is not `flexible`
- BOM exists with lines
- Consumed qty != expected qty (per product, accounting for UoM conversions and qty_producing ratio)

```python
def _get_consumption_issues(self):
    issues = []
    if self._context.get('skip_consumption', False):
        return issues
    for order in self:
        if order.consumption == 'flexible' or not order.bom_id or not order.bom_id.bom_line_ids:
            continue
        expected_move_values = order._get_moves_raw_values()  # Re-explodes BOM
        expected_qty_by_product = defaultdict(float)
        for move_values in expected_move_values:
            # Convert to product's default UoM and scale by qty_producing/product_qty ratio
            expected_qty_by_product[move_product] += move_product_qty * order.qty_producing / order.product_qty

        done_qty_by_product = defaultdict(float)
        for move in order.move_raw_ids:
            if move.picked:
                done_qty_by_product[move.product_id] += quantity_in_product_uom

        for product, qty_to_consume in expected_qty_by_product.items():
            quantity = done_qty_by_product.get(product, 0.0)
            if float_compare(qty_to_consume, quantity, precision_rounding=product.uom_id.rounding) != 0:
                issues.append((order, product, quantity, qty_to_consume))
```

### _get_moves_raw_values() — Lines 1162–1181

Re-explodes the BoM to get expected component moves. Skips phantom child BoMs and non-storable/consumable products.

```python
def _get_moves_raw_values(self):
    moves = []
    for production in self:
        if not production.bom_id:
            continue
        # factor = (product_qty in MO UoM → BoM UoM) / BoM product_qty
        factor = (production.product_uom_id._compute_quantity(production.product_qty, production.bom_id.product_uom_id)
                  / production.bom_id.product_qty)
        boms, lines = production.bom_id.explode(production.product_id, factor, picking_type=production.bom_id.picking_type_id)
        for bom_line, line_data in lines:
            # Skip phantom BOM lines and services/consumables without BoM
            if (bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom') or \
                    bom_line.product_id.type not in ['product', 'consu']:
                continue
            operation = bom_line.operation_id.id or line_data['parent_line'] and line_data['parent_line'].operation_id.id
            moves.append(production._get_move_raw_values(bom_line.product_id, line_data['qty'], bom_line.product_uom_id, operation, bom_line))
```

### _split_productions() — Lines 1763–1997

Creates backorders. Maintains move line splitting proportionally. Handles workorder quantities across backorders.

### action_cancel() → _action_cancel() — Lines 1635–1686

Cancels the MO:
1. Cancels unfinished workorders
2. Cancels unfinished raw and finished moves
3. Cancels related pickings
4. For flexible BOM MOs stuck in progress with all moves done/cancel: sets state to `'done'`

### Components Availability (_compute_components_availability, lines 343–365)

- `available`: All raw moves have `forecast_availability >= 0` (or are draft with 0 demand)
- `unavailable`: Any raw move has insufficient stock (`forecast_availability < 0`)
- `expected`: Expected date known but not late
- `late`: Expected date past `date_start`

---

## mrp.bom (646 lines)

### Class: MrpBom (line 13)

```python
class MrpBom(models.Model):
    _name = 'mrp.bom'
    _description = 'Bill of Material'
    _inherit = ['mail.thread']
    _rec_name = 'product_tmpl_id'  # Display name uses product_tmpl_id
```

**All Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `code` | Char | Reference code, optional. Display name shows `code: product_tmpl_id` |
| `active` | Boolean | Archive BOMs instead of deleting |
| `type` | Selection | `'normal'` (manufacture this product) / `'phantom'` (Kit — explodes into component moves) |
| `product_tmpl_id` | Many2one `product.template` | The product being manufactured. Domain: type in `['product', 'consu']` |
| `product_id` | Many2one `product.product` | Specific variant. If set, BOM applies only to that variant. `product_id` takes priority over `product_tmpl_id` |
| `bom_line_ids` | One2many `mrp.bom.line` | Component lines |
| `byproduct_ids` | One2many `mrp.bom.byproduct` | Co-products with cost share |
| `product_qty` | Float | Base quantity produced. Smallest qty this product can be made in |
| `product_uom_id` | Many2one `uom.uom` | Unit for product_qty |
| `product_uom_category_id` | Many2one | Related from product_tmpl_id |
| `sequence` | Integer | BoM priority when multiple BoMs exist for same product |
| `operation_ids` | One2many `mrp.routing.workcenter` | Work center operations |
| `ready_to_produce` | Selection | `'all_available'` (when all components ready) / `'asap'` (when 1st operation components ready) |
| `picking_type_id` | Many2one `stock.picking.type` | Operation type for manufacturing moves |
| `company_id` | Many2one `res.company` | Company. Defaults to env.company. Index=True |
| `consumption` | Selection | `'flexible'` / `'warning'` / `'strict'`. Controls whether component qty deviations are allowed when closing MO |
| `possible_product_template_attribute_value_ids` | Many2many | Computed from product_tmpl_id valid variant lines |
| `allow_operation_dependencies` | Boolean | If True, operations have `blocked_by_operation_ids` field |
| `produce_delay` | Integer | Manufacturing lead time in days. Added to `date_start` to compute `date_finished` |
| `days_to_prepare_mo` | Integer | Days in advance to create/confirm MO to have enough time for components. `action_compute_bom_days()` computes this |

**SQL Constraints:**
```python
# line 94-96
qty_positive = 'CHECK (product_qty > 0)'
```

### Class: MrpBomLine (line 450)

```python
class MrpBomLine(models.Model):
    _name = 'mrp.bom.line'
    _rec_name = "product_id"
```

**All Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one `product.product` | Component product |
| `product_tmpl_id` | Many2one | Related from product_id |
| `company_id` | Many2one | Related from bom_id.company_id |
| `product_qty` | Float | Quantity of this component per BOM's product_qty |
| `product_uom_id` | Many2one `uom.uom` | UoM for product_qty |
| `product_uom_category_id` | Many2one | Related from product_id.uom_id.category_id |
| `sequence` | Integer | Display order |
| `bom_id` | Many2one `mrp.bom` | Parent BOM, ondelete=cascade |
| `parent_product_tmpl_id` | Many2one | Related from bom_id.product_tmpl_id |
| `possible_bom_product_template_attribute_value_ids` | Many2many | Related from BOM |
| `bom_product_template_attribute_value_ids` | Many2many | Variant restrictions — only apply this line for specific variants |
| `allowed_operation_ids` | One2many | Related from bom_id.operation_ids |
| `operation_id` | Many2one `mrp.routing.workcenter` | Work step where this component is consumed |
| `child_bom_id` | Many2one `mrp.bom` | Computed: find BOM for this component (for multi-level explosion) |
| `child_line_ids` | One2many | Computed: bom_line_ids of child_bom_id |
| `attachments_count` | Integer | Count of documents attached to component product |
| `tracking` | Selection | Related from product_id: `'none'`, `'serial'`, `'lot'` |
| `manual_consumption` | Boolean | Computed: True if `tracking != 'none'` or `operation_id` is set. When True, consumption must be registered manually |
| `manual_consumption_readonly` | Boolean | True when tracking != 'none' or operation_id is set |

**SQL Constraints:**
```python
# line 505-509
bom_qty_zero = 'CHECK (product_qty >= 0)'  # Zero-qty lines = optional components
```

### Class: MrpByProduct (line 601)

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one | Co-product |
| `company_id` | Many2one | Related from bom_id.company_id |
| `product_qty` | Float | Quantity of by-product per main product_qty |
| `product_uom_id` | Many2one `uom.uom` | Auto-computed from product_id.uom_id |
| `bom_id` | Many2one `mrp.bom` | Parent BOM |
| `operation_id` | Many2one `mrp.routing.workcenter` | Work step where by-product is produced |
| `bom_product_template_attribute_value_ids` | Many2many | Variant restriction |
| `sequence` | Integer | Display order |
| `cost_share` | Float | Percentage of production cost allocated to this by-product. Must be positive, total ≤ 100 |

### explode() — Lines 369–423

Recursively explodes a BOM and all sub-BOMs (phantom or normal) into flat lists of component lines. This is the core BOM explosion engine used by both `mrp.production` and procurement.

```python
def explode(self, product, quantity, picking_type=False):
    """
    Args:
        product: product.product record (variant to produce)
        quantity: number of BoM "sets" to explode (already in BoM UoM)
        picking_type: stock.picking.type for finding phantom BoMs

    Returns:
        boms_done: list of (bom, bom_data) tuples for all nested BoMs
        lines_done: list of (bom_line, line_data) tuples for leaf components
    """
    product_ids = set()
    product_boms = {}
    def update_product_boms():
        products = self.env['product.product'].browse(product_ids)
        product_boms.update(self._bom_find(products, picking_type=picking_type or self.picking_type_id,
            company_id=self.company_id.id, bom_type='phantom'))  # Only look for phantom BoMs
        for product in products:
            product_boms.setdefault(product, self.env['mrp.bom'])

    boms_done = [(self, {'qty': quantity, 'product': product, 'original_qty': quantity, 'parent_line': False})]
    lines_done = []
    bom_lines = []

    for bom_line in self.bom_line_ids:
        product_id = bom_line.product_id
        bom_lines.append((bom_line, product, quantity, False))
        product_ids.add(product_id.id)
    update_product_boms()
    product_ids.clear()

    while bom_lines:
        current_line, current_product, current_qty, parent_line = bom_lines.pop(0)

        # Check variant matching: skip if product doesn't match bom_line's attribute values
        if current_line._skip_bom_line(current_product):
            continue

        line_quantity = current_qty * current_line.product_qty

        # Look for a phantom BoM for this component
        if current_line.product_id not in product_boms:
            update_product_boms()
            product_ids.clear()
        bom = product_boms.get(current_line.product_id)

        if bom:
            # Phantom BoM found: convert quantity to child's BoM UoM and recurse
            converted_line_quantity = current_line.product_uom_id._compute_quantity(
                line_quantity / bom.product_qty, bom.product_uom_id, round=False)
            bom_lines += [(line, current_line.product_id, converted_line_quantity, current_line)
                          for line in bom.bom_line_ids]
            for bom_line in bom.bom_line_ids:
                if not bom_line.product_id in product_boms:
                    product_ids.add(bom_line.product_id.id)
            boms_done.append((bom, {'qty': converted_line_quantity, 'product': current_product,
                                     'original_qty': quantity, 'parent_line': current_line}))
        else:
            # No phantom BoM: this is a leaf component
            # Round UP to avoid partial UoM consumption issues
            rounding = current_line.product_uom_id.rounding
            line_quantity = float_round(line_quantity, precision_rounding=rounding, rounding_method='UP')
            lines_done.append((current_line, {
                'qty': line_quantity,
                'product': current_product,
                'original_qty': quantity,
                'parent_line': parent_line
            }))

    return boms_done, lines_done
```

**Key behaviors:**
- Recursively descends into phantom BoMs only (normal BoMs are not recursively exploded here)
- Skips BOM lines where `bom_product_template_attribute_value_ids` doesn't match the product's variant attributes
- Rounds UP leaf quantities to avoid partial UoM consumption issues
- Returns both the nested BoM structure (`boms_done`) and the flat component lines (`lines_done`)

### _bom_find() — Lines 337–367

Finds the first active BoM for each product based on company, picking_type, and sequence.

**BoM Selection Priority:** `sequence` (lower first), then `product_id` set over False, then first created.

### BoM Cycle Detection (_check_bom_cycle, lines 115–164)

Prevents infinite recursion in phantom BoMs. Walks the BOM tree and raises `ValidationError` if a component's BoM includes the finished product (directly or transitively).

### Consumption Mode

The `consumption` field on `mrp.bom` controls component consumption validation:

| Value | Behavior | At Close |
|-------|----------|----------|
| `flexible` | No check — any qty allowed | MO marked done regardless |
| `warning` | Issues warning summary | Can still close MO |
| `strict` | Blocks close | Manager only can override |

Also respects `manual_consumption` flag on `mrp.bom.line`: when `True`, Odoo does NOT auto-fill the quantity done on that component's move, requiring manual entry.

---

## mrp.routing.workcenter (181 lines, embedded in `mrp_routing.py`)

Represents a work step in a BoM's routing.

```python
class MrpRoutingWorkcenter(models.Model):
    _name = 'mrp.routing.workcenter'
    _description = 'Work Center Usage'
    _order = 'bom_id, sequence, id'
```

**All Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Operation name (e.g., "Cutting", "Assembly") |
| `active` | Boolean | Archive to hide from active BoMs |
| `workcenter_id` | Many2one `mrp.workcenter` | The work center where this operation runs |
| `sequence` | Integer | Display order. Default=100 |
| `bom_id` | Many2one `mrp.bom` | Parent BoM |
| `company_id` | Many2one | Related from bom_id.company_id |
| `worksheet_type` | Selection | `'pdf'`, `'google_slide'`, `'text'` |
| `note` | Html | Rich text instructions/description |
| `worksheet` | Binary | PDF file attachment |
| `worksheet_google_slide` | Char | Google Slide URL (public access required) |
| `time_mode` | Selection | `'auto'` (compute from tracked times) / `'manual'` (use time_cycle_manual). Default=`manual` |
| `time_mode_batch` | Integer | Number of recent done WOs to average for auto time. Default=10 |
| `time_computed_on` | Char | Display string: "Based on last N work orders" or False if manual |
| `time_cycle_manual` | Float | Manual duration in minutes. Default=60 |
| `time_cycle` | Float | Computed effective duration. In auto mode: `total_duration / cycle_number`. In manual mode: = `time_cycle_manual` |
| `workorder_count` | Integer | Number of completed work orders using this operation |
| `workorder_ids` | One2many `mrp.workorder` | All work orders for this operation |
| `bom_product_template_attribute_value_ids` | Many2many | Variant restriction for this operation |
| `allow_operation_dependencies` | Boolean | Related from bom_id |
| `blocked_by_operation_ids` | Many2many `mrp.routing.workcenter` | Operations that must complete before this one starts |
| `needed_by_operation_ids` | Many2many | Inverse of blocked_by |

**Key Methods:**

- `_compute_time_cycle()` (lines 67–94): Averages duration of last N done work orders. Divides total_duration by cycle_number (which accounts for capacity > 1). Falls back to manual if no data.
- `_check_no_cyclic_dependencies()` (lines 104–107): Validates that `blocked_by_operation_ids` has no cycles using `self._check_m2m_recursion()`
- `_skip_operation_line()` (lines 164–174): Checks if archived or variant mismatches — used during workorder generation from BoM

---

## mrp.workorder (914 lines)

Represents a scheduled operation on a specific production order.

```python
class MrpWorkorder(models.Model):
    _name = 'mrp.workorder'
    _description = 'Work Order'
    _order = 'leave_id, date_start, id'
```

**State Machine:** `pending → waiting → ready → progress → done` / `cancel`

States mean:
- `pending`: Waiting for another WO (dependency not satisfied)
- `waiting`: Waiting for components (stock not available at source location)
- `ready`: Components available, not yet started
- `progress`: Running at work center
- `done`: Finished
- `cancel`: Cancelled

**All Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Work order name (from operation name) |
| `barcode` | Char | Computed barcode string |
| `workcenter_id` | Many2one `mrp.workcenter` | Assigned work center |
| `working_state` | Selection | Related from workcenter: `'normal'`, `'blocked'`, `'done'` |
| `product_id` | Many2one | Related from production_id.product_id |
| `product_tracking` | Selection | Related from product |
| `product_uom_id` | Many2one `uom.uom` | Unit from production |
| `production_id` | Many2one `mrp.production` | Parent MO |
| `production_availability` | Selection | Related from production.reservation_state |
| `production_state` | Selection | Related from production.state |
| `production_bom_id` | Many2one `mrp.bom` | Related from production |
| `qty_production` | Float | Original production quantity |
| `company_id` | Many2one | Related from production |
| `qty_producing` | Float | Quantity being produced in this work order |
| `qty_remaining` | Float | qty_production - qty_produced |
| `qty_produced` | Float | Quantity completed by this WO |
| `is_produced` | Boolean | True when qty_produced >= qty_production |
| `state` | Selection | Computed: `pending / waiting / ready / progress / done / cancel` |
| `leave_id` | Many2one `resource.calendar.leaves` | Gantt slot in workcenter calendar |
| `date_start` | Datetime | Planned/actual start. Computed from leave_id |
| `date_finished` | Datetime | Planned/actual end. Computed from leave_id |
| `duration_expected` | Float | Expected duration in minutes. Computed: `_get_duration_expected()` |
| `duration` | Float | Actual duration. Computed from productivity logs |
| `duration_unit` | Float | Duration per unit. `duration / max(qty_produced, 1)` |
| `duration_percent` | Integer | Deviation %: `(duration - duration_expected) / duration_expected * 100` |
| `progress` | Float | Progress percentage 0–100 |
| `operation_id` | Many2one `mrp.routing.workcenter` | Source operation in BoM |
| `has_worksheet` | Boolean | True if worksheet_type is set |
| `worksheet` | Binary | Worksheet PDF |
| `blocked_by_workorder_ids` | Many2many `mrp.workorder` | WOs that must complete first |
| `needed_by_workorder_ids` | Many2many | WOs that depend on this one |
| `allow_workorder_dependencies` | Boolean | From production.bom_id |
| `move_line_ids` | One2many | Stock move lines for components consumed at this operation |
| `time_ids` | One2many `mrp.workcenter.productivity` | Time tracking logs (start/stop timers) |
| `is_adjusted` | Boolean | True if user manually changed duration |
| `cost_already_accounted` | Boolean | Prevents double-costing from WoS |

### Workorder Dependencies

When `allow_workorder_dependencies = True`, the production's `_link_workorders_and_moves()` (lines 1459–1495 in `mrp_production.py`) sets `blocked_by_workorder_ids` from `operation_id.blocked_by_operation_ids` (the routing dependencies).

When disabled, each workorder is blocked by the previous one in sequence within the same BoM.

### Key Methods

- `_plan_workorder()`: Books a slot in the workcenter calendar using `_get_first_available_slot()`, creates `resource.calendar.leaves` record
- `button_start()` / `button_pause()` / `button_done()`: Control the work order lifecycle
- `_get_duration_expected()`: Calculates expected duration based on workcenter's time_cycle, efficiency, capacity, and setup/cleanup times
- `_get_first_available_slot()` (on workcenter, lines 250–295): Finds first gap in workcenter calendar up to 700 days ahead

---

## mrp.workcenter (519 lines)

Represents a production resource (machine or labor group).

```python
class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _description = 'Work Center'
    _inherit = ['resource.mixin']  # Gets resource_id, time_efficiency, active, resource_calendar_id
```

**Inherited from `resource.mixin`:**
- `name`: From resource_id.name
- `time_efficiency`: Default 100%, affects duration computation
- `active`: From resource_id
- `resource_calendar_id`: Working hours calendar
- `company_id`: From resource

**All Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `code` | Char | Work center code |
| `note` | Html | Description |
| `default_capacity` | Float | Number of units produced in parallel (capacity per cycle). Default=1. Default must be > 0 |
| `sequence` | Integer | Display order |
| `color` | Integer | Kanban color |
| `currency_id` | Many2one `res.currency` | Related from company |
| `costs_hour` | Float | Hourly processing cost for analytic accounting |
| `time_start` | Float | Setup time in minutes (before production starts) |
| `time_stop` | Float | Cleanup time in minutes (after production ends) |
| `routing_line_ids` | One2many | Operations that use this work center |
| `has_routing_lines` | Boolean | True if any routing lines reference this WC |
| `order_ids` | One2many `mrp.workorder` | Work orders assigned here |
| `workorder_count` | Integer | Total non-cancelled WOs |
| `workorder_ready_count` | Integer | WOs in 'ready' state |
| `workorder_progress_count` | Integer | WOs in 'progress' state |
| `workorder_pending_count` | Integer | WOs in 'pending' state |
| `workorder_late_count` | Integer | Late WOs (date_start < now and state in pending/waiting/ready) |
| `time_ids` | One2many `mrp.workcenter.productivity` | Time log entries |
| `working_state` | Selection | `'normal'` / `'blocked'` / `'done'` (in progress). Computed from open productivity logs |
| `blocked_time` | Float | Blocked hours in last 30 days |
| `productive_time` | Float | Productive hours in last 30 days |
| `oee` | Float | Overall Equipment Effectiveness % over last 30 days. `productive_time * 100 / (productive_time + blocked_time)` |
| `oee_target` | Float | Target OEE %. Default=90 |
| `performance` | Integer | % of expected vs actual duration over last 30 days |
| `workcenter_load` | Float | Total expected duration of pending/waiting/ready/confirmed WOs |
| `alternative_workcenter_ids` | Many2many `mrp.workcenter` | Substitutes for this WC. Cannot include self |
| `tag_ids` | Many2many `mrp.workcenter.tag` | Categorization |
| `capacity_ids` | One2many `mrp.workcenter.capacity` | Product-specific capacity override |

**Key Methods:**

- `_get_capacity(product)` (lines 314–316): Returns `capacity_ids.capacity` for the product, or `default_capacity`
- `_get_expected_duration(product_id)` (lines 318–323): Returns setup+cleanup time from product-specific capacity or from workcenter defaults
- `_get_first_available_slot()` (lines 250–295): Finds the next free calendar slot for a given duration, checking working hours, existing WO leaves, and unavailability. Searches up to 700 days ahead.

### Time Calculation

**Duration expected per WO:**
```
duration = time_start + time_stop  [setup/cleanup overhead]
         + (qty_to_produce / capacity) * time_cycle * (100 / time_efficiency)
```
Where `time_cycle` comes from the routing operation (`operation_id.time_cycle`), which itself can be auto-computed from past WOs or set manually.

**OEE formula (lines 156–179):**
```
OEE = productive_time * 100 / (productive_time + blocked_time)
```
Productive time = time logs with `loss_type = 'productive'`
Blocked time = time logs with `loss_type != 'productive'`

---

## Production → Stock Flow

### Confirmation (action_confirm)

```
mrp.production.action_confirm()
  ├── Sets consumption from bom_id.consumption
  ├── Converts serial tracking UoM
  ├── move_raws_to_adjust._adjust_procurement_method()
  │     └── For each raw move: if product has enough stock → 'make_to_stock'
  │                             else → 'make_to_order' (triggers procurement)
  ├── moves_to_confirm._action_confirm(merge=False)
  │     └── stock.move: draft → confirmed
  │           Creates stock move lines (reserved if at_confirm reservation)
  ├── workorder_to_confirm._action_confirm()
  │     └── Links WO to moves via operation_id
  ├── move_raw_ids._trigger_scheduler()
  │     └── For moves with insufficient stock: creates procurement orders
  │           which may create Pick/OP/MO for sub-assemblies
  └── picking_ids.action_confirm()
        └── Confirms internal pickings (PBM/IBM if mrp_two_steps)
```

### Stock Move Structure

**Raw moves** (`move_raw_ids`):
- `raw_material_production_id` = self.id
- `location_id` = location_src_id (components warehouse location)
- `location_dest_id` = production_location_id (product's `property_stock_production`)
- `bom_line_id` = the source BOM line
- `operation_id` = the work step (if component consumed at specific operation)
- `picking_type_id` = mrp_operation
- `state`: draft → confirmed → assigned → done

**Finished moves** (`move_finished_ids`):
- `production_id` = self.id
- `location_id` = production_location_id
- `location_dest_id` = location_dest_id (stock location)
- `bom_line_id` = False (for main product)
- `byproduct_id` = set for co-products

### Reservation States

| State | MO Readiness Meaning |
|-------|---------------------|
| `confirmed` | Components not fully reserved — raw moves in `assigned` state |
| `assigned` | All components reserved — raw moves all in `assigned` state |
| `waiting` | Waiting for first operation components (when `bom_id.ready_to_produce = 'asap'`) |

---

## See Also

- `[Modules/Stock](stock.md)` — stock.move, stock.picking, stock.quant structure
- `[Core/API](API.md)` — @api.depends, @api.constrains decorators
- `[Patterns/Workflow Patterns](Workflow Patterns.md)` — state machine design pattern
- `addons/mrp/models/mrp_unbuild.py` — unbuild/disassembly orders
- `addons/mrp/models/stock_move.py` — move confirmation and reservation logic