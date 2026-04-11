# MRP Subcontracting (`mrp_subcontracting`)

## Overview

**Module:** `mrp_subcontracting`
**Depends:** `mrp`
**Category:** Supply Chain/Manufacturing
**License:** LGPL-3
**Odoo Version:** 19 (CE)

The `mrp_subcontracting` module extends the Manufacturing module (`mrp`) to support subcontracting workflows. Subcontracting is a business arrangement where a company (the contracting party) hires an external partner (the subcontractor) to manufacture products or components. The module manages the complete lifecycle: from sending raw materials to the subcontractor, tracking subcontracting manufacturing orders (MOs), to receiving finished goods.

### Key Concepts

- **Subcontracting BOM:** A Bill of Materials of type `subcontract` that defines which subcontractor(s) can produce the product and what raw materials are needed.
- **Subcontractor Partner:** A `res.partner` marked as a subcontractor via `property_stock_subcontractor` (a dedicated stock location) and associated with subcontracting BoMs.
- **Subcontracting Receipt:** An incoming stock picking (`stock.picking`) that represents the finished goods received from the subcontractor.
- **Subcontracting Resupply:** An internal transfer that sends raw materials (components) from the warehouse to the subcontractor's location.
- **Subcontracting MO:** A manufacturing order automatically created when a subcontracting receipt is confirmed. It is linked to the subcontractor partner and uses the subcontractor's location as both source and destination.
- **Subcontracting Location:** A company-specific internal stock location (created automatically on company setup) that serves as the virtual "stock at subcontractor" location.

---

## Architecture

### Module File Tree

```
mrp_subcontracting/
├── __manifest__.py           # Depends: mrp; assets bundle with portal/SCSS
├── data/
│   └── mrp_subcontracting_data.xml  # Global MTO route, _create_missing_subcontracting_location hook
├── models/
│   ├── __init__.py
│   ├── mrp_bom.py            # type='subcontract', subcontractor_ids, _bom_subcontract_find
│   ├── mrp_production.py      # subcontractor_id, portal write, move_line_raw_ids inverse
│   ├── mrp_unbuild.py         # Block unbuild on subcontract MOs
│   ├── product.py             # is_subcontractor on supplierinfo, _prepare_sellers override
│   ├── res_company.py         # subcontracting_location_id auto-creation
│   ├── res_partner.py         # property_stock_subcontractor, is_subcontractor, computed rels
│   ├── stock_location.py     # is_subcontract(), _check_access_putaway, constraint
│   ├── stock_move.py          # is_subcontract, _action_confirm, _sync_subcontracting_productions
│   ├── stock_move_line.py    # _sync_subcontracting_productions triggers, serial onchange
│   ├── stock_picking.py       # _subcontracted_produce, MO auto-creation, _action_done
│   ├── stock_quant.py         # is_subcontract search field
│   ├── stock_rule.py         # Partner propagation on resupply moves
│   └── stock_warehouse.py     # Resupply routes, picking types, global route activation
├── wizard/
│   ├── stock_picking_return.py     # Return to subcontractor location
│   ├── change_production_qty.py   # Skip propagation for subcontract moves
│   └── mrp_production_serial_numbers.py  # Multi-lot registration for subcontract MOs
├── report/
│   └── mrp_report_bom_structure.py  # Subcontracting cost, lead time, availability
├── controllers/
│   └── portal.py             # /my/productions, /my/productions/<id>/subcontracting_portal
├── security/
│   └── mrp_subcontracting_security.xml  # Portal record rules for 14 models
└── views/ + static/src/        # XML views, JS portal controller, SCSS
```

### Extended Models

The module extends fourteen core Odoo models and introduces four wizards plus a report override:

| Extended Model | File | Key Extension |
|---|---|---|
| `mrp.bom` | `models/mrp_bom.py` | `type='subcontract'`, `subcontractor_ids`, `_bom_subcontract_find` |
| `stock.picking` | `models/stock_picking.py` | Subcontract receipt flow, MO auto-creation via `_subcontracted_produce` |
| `stock.move` | `models/stock_move.py` | `is_subcontract` flag, BOM detection, production sync, reservation bypass |
| `stock.move.line` | `models/stock_move_line.py` | Serial number onchange, `_sync_subcontracting_productions` triggers |
| `stock.location` | `models/stock_location.py` | `is_subcontract()`, `_check_access_putaway` sudo, location constraint |
| `stock.warehouse` | `models/stock_warehouse.py` | Resupply route/rules, picking types, global route activation |
| `stock.rule` | `models/stock_rule.py` | `partner_id` propagation on resupply moves |
| `stock.quant` | `models/stock_quant.py` | `is_subcontract` search field |
| `stock.reference` | `models/stock_picking.py` | Traceability link between picking and MO |
| `mrp.production` | `models/mrp_production.py` | `subcontractor_id`, portal field security, move_line_raw_ids inverse, `_rec_names_search` |
| `res.partner` | `models/res_partner.py` | `property_stock_subcontractor`, `is_subcontractor`, `_read_group`-optimized computed relations |
| `res.company` | `models/res_company.py` | `subcontracting_location_id` auto-creation |
| `product.supplierinfo` | `models/product.py` | `is_subcontractor` computed flag |
| `product.product` | `models/product.py` | `_prepare_sellers` with subcontractor filter |
| `stock.return.picking` | `wizard/stock_picking_return.py` | Return to subcontractor location |
| `stock.return.picking.line` | `wizard/stock_picking_return.py` | Return move `is_subcontract = False` |
| `change.production.qty` | `wizard/change_production_qty.py` | Skip quantity propagation to subcontract moves |
| `mrp.production.serials` | `wizard/mrp_production_serial_numbers.py` | Multi-lot registration for subcontract MOs |
| `report.mrp.report_bom_structure` | `report/mrp_report_bom_structure.py` | Subcontracting cost line, lead time, availability |
| `mrp.production` (unbuild) | `models/mrp_unbuild.py` | Block `button_unbuild` on subcontract MOs |

---

## Extended Models Detail

### 1. `mrp.bom` — Subcontracting Bill of Materials

**File:** `models/mrp_bom.py`

```python
class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    type = fields.Selection(selection_add=[
        ('subcontract', 'Subcontracting')
    ], ondelete={'subcontract': lambda recs: recs.write({'type': 'normal', 'active': False})})
    subcontractor_ids = fields.Many2many(
        'res.partner', 'mrp_bom_subcontractor', string='Subcontractors', check_company=True)
```

#### L2: Field Details

**`type` (extended Selection)**
- Added `('subcontract', 'Subcontracting')` to the existing selection (which already has `normal` and `phantom`).
- **`ondelete` behavior:** When a subcontracting BoM is deleted (or its product is deleted via ORM cascade), Odoo does NOT cascade-delete the BoM. Instead, the `ondelete` lambda silently converts the BoM to `type='normal'` and sets `active=False`. This preserves the BoM record for audit/reactivation without triggering a hard delete.
- **Constraint:** Subcontracting BoMs CANNOT have `operation_ids` (routing/work orders) or `byproduct_ids`. Enforced by `_check_subcontracting_no_operation`.

**`subcontractor_ids`**
- A `Many2many` to `res.partner`, stored in the auto-generated `mrp_bom_subcontractor` relation table. `check_company=True` scopes visibility to records within the same company.
- A subcontracting BoM can name multiple subcontractors, enabling the same product to be subcontracted to different partners with potentially different pricing or lead times.

#### L3: `_bom_subcontract_find()` — Subcontracting BOM Lookup

```python
def _bom_subcontract_find(self, product, picking_type=None, company_id=False,
                          bom_type='subcontract', subcontractor=False):
    domain = self._bom_find_domain(product, picking_type=picking_type,
                                   company_id=company_id, bom_type=bom_type)
    if subcontractor:
        domain &= Domain('subcontractor_ids', 'parent_of', subcontractor.ids)
        return self.search(domain, order='sequence, product_id, id', limit=1)
    else:
        return self.env['mrp.bom']
```

- **Domain operator `parent_of`:** Uses the special `parent_of` domain operator against `subcontractor_ids`. This means if a subcontractor contact record has child contacts (e.g., a parent company with multiple delivery-site sub-contacts), the BoM is also valid for all those child contacts. This is critical for multi-site or multi-address subcontractor setups.
- **No `subcontractor` argument:** If called without a `subcontractor` value, returns an empty recordset. Callers must always pass a subcontractor partner for the search to match anything.
- **Order:** `sequence, product_id, id` — ensures deterministic selection when multiple BoMs match.
- **L4 Performance:** The `parent_of` operator translates to a recursive SQL CTE query (the partner hierarchy). For deep contact hierarchies, this can be non-trivial; however subcontractor hierarchies are typically shallow (2-3 levels), so the impact is minimal.

#### L3: `_check_subcontracting_no_operation` — Constraint

```python
@api.constrains('operation_ids', 'byproduct_ids', 'type')
def _check_subcontracting_no_operation(self):
    if self.filtered_domain([('type', '=', 'subcontract'),
                              '|', ('operation_ids', '!=', False),
                                 ('byproduct_ids', '!=', False)]):
        raise ValidationError(_('You can not set a Bill of Material with operations '
                                'or by-product line as subcontracting.'))
```

- **Rationale:** Subcontracting BoMs cannot define work orders because the subcontractor, not the contracting company's work centers, performs the labor. By-products are disallowed because subcontracting assumes a single output; any co-products must be handled via separate vendor agreements.
- **Odoo 17→18 change:** In Odoo 17 and earlier, subcontracting BoMs could technically have operations — but those operations were never executed because the MO used the subcontracting picking type. This constraint formalizes the approach taken since Odoo 18 and prevents future misuse.

---

### 2. `stock.move` — Subcontract Receipts

**File:** `models/stock_move.py`

The `is_subcontract` Boolean field is the central flag marking a stock move as a subcontracting receipt. It is **not stored** — it is a regular non-stored Boolean written directly in `_action_confirm`. The field's value depends on the move's relationship to a picking with a subcontracting BoM vendor.

```python
is_subcontract = fields.Boolean('The move is a subcontract receipt')
show_subcontracting_details_visible = fields.Boolean(
    compute='_compute_show_subcontracting_details_visible'
)
```

#### L2: Field Computations

**`_compute_show_subcontracting_details_visible`**
- Returns `True` when all of: (1) move is subcontract, (2) has move lines, (3) quantity is non-zero, (4) at least one non-cancelled linked production exists.
- Controls the "Show Component Moves" / "Show Subcontracting Details" button visibility on the picking form.

**`_compute_show_info` (override)**
- For subcontract moves where `show_lots_text` would normally be `True`, it forces `show_lots_text = False` and `show_lots_m2o = True`. This switches the UI from a text-based lot display to a proper Many2one dropdown, which is needed for the subcontracting serial number registration wizard flow.

**`_compute_is_quantity_done_editable`**
- For subcontract moves: `is_quantity_done_editable = (has_tracking == 'none')`.
- For untracked products: quantity IS directly editable on the move.
- For tracked (lot/serial) products: quantity is NOT directly editable on the move — it must be recorded via the subcontracting MO's "Register" wizard. This prevents a mismatch between the MO's lot tracking and the receipt move's quantity.

#### L3: `_action_confirm` — Subcontracting BOM Detection

This is the **critical method** where Odoo detects that an incoming move should be treated as subcontracting. It is called during picking confirmation:

```python
def _action_confirm(self, merge=True, merge_into=False, create_proc=True):
    subcontract_details_per_picking = defaultdict(list)
    for move in self:
        # Only incoming moves from a supplier location
        if move.location_id.usage != 'supplier' or move.location_dest_id.usage == 'supplier':
            continue
        # Skip if already linked to an upstream production (e.g., from MTO chain)
        if move.move_orig_ids.production_id:
            continue
        bom = move._get_subcontract_bom()
        if not bom:
            continue
        company = move.company_id
        subcontracting_location = (
            move.picking_id.partner_id.with_company(company).property_stock_subcontractor
            or company.subcontracting_location_id)
        move.write({
            'is_subcontract': True,
            'location_id': subcontracting_location.id
        })
        move._action_assign()  # Re-reserve — the location write breaks existing reservation
    res = super()._action_confirm(merge=merge, merge_into=merge_into, create_proc=create_proc)
    for move in res:
        if move.is_subcontract:
            subcontract_details_per_picking[move.picking_id].append((move, move._get_subcontract_bom()))
    for picking, subcontract_details in subcontract_details_per_picking.items():
        picking._subcontracted_produce(subcontract_details)
    if subcontract_details_per_picking:
        self.env['stock.picking'].concat(*list(subcontract_details_per_picking.keys())).action_assign()
    return res
```

**Key behaviors:**
- Only moves from a `supplier` location (incoming) are considered.
- Moves to a `supplier` destination (`location_dest_id.usage == 'supplier'`) are returns — skip.
- Moves already linked to an upstream production (e.g., from a regular MO feeding into this receipt) are skipped to avoid creating duplicate MOs.
- `_get_subcontract_bom()` uses `.sudo()` internally to bypass record rules on `mrp.bom`.
- The `location_id` is updated from `supplier` to the **subcontracting location** (partner-specific override or company default). This is the pivotal moment that transforms a generic supplier receipt into a subcontracting flow.
- After `super()._action_confirm()`, the picking's `_subcontracted_produce()` is called to create the subcontracting MO.
- **Post-confirm `action_assign()` on the picking:** After MO creation, a second `action_assign()` call on the picking (not just the moves) ensures that the subcontract receipt picking is also reserved — without this, the picking might show as unavailable.

#### L3: `_get_subcontract_bom` — BOM Resolution

```python
def _get_subcontract_bom(self):
    self.ensure_one()
    bom = self.env['mrp.bom'].sudo()._bom_subcontract_find(
        self.product_id,
        picking_type=self.picking_type_id,
        company_id=self.company_id.id,
        bom_type='subcontract',
        subcontractor=self.picking_id.partner_id,
    )
    return bom
```

- Uses `.sudo()` to bypass access rights during BOM lookup — BOM record rules may prevent regular users from reading BoM records, but the subcontracting flow must always find the BoM.
- The subcontractor partner is resolved from `self.picking_id.partner_id` — the vendor/supplier on the picking.

#### L3: `_get_subcontract_production` — Production Lookup

```python
def _get_subcontract_production(self):
    return self.filtered(lambda m: m.is_subcontract).move_orig_ids.production_id
```

Returns the linked subcontracting production(s) by traversing `move_orig_ids` (the reverse of the move link created in `_subcontracted_produce`). Note: this returns `production_id` from `move_orig_ids`, which may be multiple MOs in tracked (multi-lot) scenarios.

#### L3: `_is_subcontract_return` — Return Detection

```python
def _is_subcontract_return(self):
    self.ensure_one()
    subcontracting_location = self.picking_id.partner_id.with_company(
        self.company_id).property_stock_subcontractor
    return (
        not self.is_subcontract
        and self.origin_returned_move_id.is_subcontract
        and self.location_dest_id.id == subcontracting_location.id
    )
```

Detects whether a move is a return of a previously received subcontracted product. All three conditions must hold: (1) current move is NOT a subcontract move, (2) the origin return move WAS a subcontract move, (3) destination is the subcontractor's location.

#### L3: `_action_cancel` — Cascade Cancel to Subcontract MOs

```python
def _action_cancel(self):
    productions_to_cancel_ids = OrderedSet()
    for move in self:
        if move.is_subcontract:
            active_productions = move.move_orig_ids.production_id.filtered(
                lambda p: p.state not in ('done', 'cancel'))
            moves_todo = self.env.context.get('moves_todo')
            not_todo_productions = active_productions.filtered(
                lambda p: p not in moves_todo.move_orig_ids.production_id) if moves_todo else active_productions
            if not_todo_productions:
                productions_to_cancel_ids.update(not_todo_productions.ids)
    if productions_to_cancel_ids:
        productions_to_cancel = self.env['mrp.production'].browse(productions_to_cancel_ids)
        productions_to_cancel.with_context(skip_activity=True).action_cancel()
    return super()._action_cancel()
```

- Cancelling a subcontract receipt move cascades to cancel linked subcontracting MOs (that are not already done/cancelled).
- Uses `OrderedSet` to deduplicate MO IDs — a single MO may be linked from multiple moves.
- The `moves_todo` context check prevents double-cancellation when called in a chained context.
- `skip_activity=True` avoids errors from cancelling MOs with active mail activities.

#### L3: `_should_bypass_reservation` — Always Reserved

```python
def _should_bypass_reservation(self, forced_location=False):
    should_bypass_reservation = super()._should_bypass_reservation(forced_location=forced_location)
    if not should_bypass_reservation and self.is_subcontract:
        return True
    return should_bypass_reservation
```

Subcontracting receipt moves always bypass the reservation check — they are treated as "available" regardless of stock state. This is correct because the stock is at the subcontractor's location, which Odoo cannot verify by querying physical quants.

#### L3: `copy_data` — Location Preservation on Duplicate

```python
def copy_data(self, default=None):
    default = dict(default or {})
    vals_list = super().copy_data(default=default)
    for move, vals in zip(self, vals_list):
        if 'location_id' in default or not move.is_subcontract:
            continue
        vals['location_id'] = move.picking_id.location_id.id
    return vals_list
```

When duplicating a subcontracting receipt move, the `location_id` is reset to the picking's source location (typically the warehouse stock), not the current subcontracting location. This ensures that when a copy is made (e.g., for a new receipt of the same product), the source location is set correctly.

#### L3: `_prepare_move_split_vals` — Preserve Location on Split

```python
def _prepare_move_split_vals(self, qty):
    vals = super(StockMove, self)._prepare_move_split_vals(qty)
    vals['location_id'] = self.location_id.id
    return vals
```

When splitting a subcontracting move (e.g., for a partial receipt backorder), the `location_id` is explicitly preserved on the new split move. Without this, the split move would lose its subcontracting location and revert to the picking's default source location.

#### L3: `_prepare_procurement_values` — Warehouse Propagation

```python
def _prepare_procurement_values(self):
    res = super()._prepare_procurement_values()
    if self.raw_material_production_id.subcontractor_id:
        res['warehouse_id'] = self.picking_type_id.warehouse_id
    return res
```

When the component moves of a subcontracting MO trigger procurement rules, the warehouse is propagated into the procurement values. This ensures the resupply picking is created from the correct warehouse even when the subcontracting MO is confirmed in a non-default warehouse context.

#### L3: `_get_available_move_lines` — Exclude from Available Quantities

```python
def _get_available_move_lines(self, assigned_moves_ids, partially_available_moves_ids):
    return super(StockMove, self.filtered(lambda m: not m.is_subcontract))._get_available_move_lines(
        assigned_moves_ids, partially_available_moves_ids)
```

Subcontracting receipt moves are excluded from the "available move lines" computation, which determines which quantities can be partially fulfilled. Subcontracting moves should never be partially assigned because they represent a specific subcontractor receipt.

#### L3: `_can_create_lot` — Allow Lot Creation in Portal Context

```python
def _can_create_lot(self):
    return super()._can_create_lot() or self.env.context.get('force_lot_m2o')
```

Subcontracting needs to create lot records during the portal serial number registration flow. The `force_lot_m2o` context flag (set in `action_show_details` for subcontract moves) allows new lots to be created even when the product is configured to forbid lot creation at receipt.

#### L3: `_generate_serial_numbers` — Subcontract Serial Flow

```python
def _generate_serial_numbers(self, next_serial, next_serial_count=False, location_id=False):
    if self.is_subcontract:
        return super(StockMove, self.with_context(force_lot_m2o=True))._generate_serial_numbers(
            next_serial, next_serial_count, location_id)
    return super()._generate_serial_numbers(next_serial, next_serial_count, location_id)
```

For subcontracting moves, the `force_lot_m2o` context is injected before calling the parent serial number generation method. This ensures the lot creation path works correctly in the subcontracting portal context.

#### L4: `write()` — Date Synchronization with Subcontract MOs

```python
def write(self, vals):
    self._check_access_if_subcontractor(vals)
    res = super().write(vals)
    if 'date' in vals:
        for move in self:
            if move.state in ('done', 'cancel') or not move.is_subcontract:
                continue
            move.move_orig_ids.production_id.with_context(from_subcontract=True).filtered(
                lambda p: p.state not in ('done', 'cancel')).write({
                    'date_start': move.date,
                    'date_finished': move.date,
                })
    return res
```

- Uses `from_subcontract=True` context to prevent recursive calls (the `write` override on `mrp.production` checks for this context and adjusts the date accordingly).
- Only updates MOs that are not done or cancelled.
- Sets both `date_start` and `date_finished` to the same date as the receipt move.

#### L4: `_check_access_if_subcontractor` — Portal Create/Write Guard

```python
def _check_access_if_subcontractor(self, vals):
    if self.env.user._is_portal() and not self.env.su:
        if vals.get('state') == 'done':
            raise AccessError(_("Portal users cannot create a stock move with state 'Done' "
                                "or change the current state to 'Done'."))
```

Portal subcontractors cannot manually set stock moves to `done` state. The subcontracting flow handles marking done via the picking validation, which runs under `sudo()` for the MO. Portal users can only write qty/lot data before validation.

---

### 3. `stock.picking` — Subcontract Receipt Processing

**File:** `models/stock_picking.py`

The picking extension handles the end-to-end subcontracting flow: destination location routing, MO creation at confirmation, MO marking done at validation, and portal/navigation action.

#### L2: `_compute_location_id` Override

```python
@api.depends('picking_type_id', 'partner_id')
def _compute_location_id(self):
    super()._compute_location_id()
    for picking in self:
        subcontracting_resupply_type_id = (
            picking.picking_type_id.warehouse_id.subcontracting_resupply_type_id)
        if (picking.picking_type_id == subcontracting_resupply_type_id
                and picking.partner_id.property_stock_subcontractor):
            picking.location_dest_id = picking.partner_id.property_stock_subcontractor
```

When a picking type matches the warehouse's **Resupply Subcontractor** operation type, the destination location is automatically set to the partner's dedicated `property_stock_subcontractor` location. This is a computed override that fires after the base method — it only applies to resupply pickings, not to subcontracting receipt pickings (those use the company-level `subcontracting_location_id` as their destination after MO confirmation).

#### L2: `_compute_show_lots_text` — Suppress Text Lot Display

```python
@api.depends('move_ids.is_subcontract', 'move_ids.has_tracking')
def _compute_show_lots_text(self):
    super()._compute_show_lots_text()
    for picking in self:
        if any(move.is_subcontract and move.has_tracking != 'none' for move in picking.move_ids):
            picking.show_lots_text = False
```

When any move in the picking is a tracked subcontracting receipt, the picking-level `show_lots_text` is suppressed. This switches the UI from the simple text display to the full lot-management dropdown, which is necessary for the subcontracting serial number flow.

#### L2: `_action_done` — Completing Subcontracting MOs

```python
def _action_done(self):
    res = super(StockPicking, self)._action_done()
    for picking in self:
        productions_to_done = picking._get_subcontract_production().sudo()
        productions_to_done.button_mark_done()
        production_moves = productions_to_done.move_raw_ids | productions_to_done.move_finished_ids
        if production_moves:
            minimum_date = min(picking.move_line_ids.mapped('date'))
            production_moves.write({'date': minimum_date - timedelta(seconds=1)})
            production_moves.move_line_ids.write({'date': minimum_date - timedelta(seconds=1)})
    return res
```

- Calls `sudo()` on productions to bypass portal user access restrictions — subcontractors may be portal users who cannot normally mark MOs done.
- Sets production move dates to 1 second before the picking's minimum move line date. This ensures the **traceability report** correctly orders events: the production's internal component consumption happens BEFORE the subcontracting receipt in the chronological sequence.
- **L4 Date Ordering Concern:** The 1-second offset is a pragmatic fix for the traceability view. In high-precision scenarios or multi-company setups with strict inter-company date sequencing, the offset could theoretically cause the production to appear before its expected date in other reports.
- **L4 Thread Safety:** The `sudo()` call here is safe because it only applies to MOs linked to the picking being validated, and the portal user has legitimate access to these MOs via the record rules.

#### L2: `_subcontracted_produce` — MO Creation at Receipt Confirmation

This is the **MO factory** for subcontracting. It is called from `stock.move._action_confirm()` after the subcontracting BOM is detected:

```python
def _subcontracted_produce(self, subcontract_details):
    self.ensure_one()
    group_by_company = defaultdict(lambda: ([], []))
    for move, bom in subcontract_details:
        if move.move_orig_ids.production_id:
            if len(move.move_orig_ids.move_dest_ids) > 1:
                # Magic spicy sauce: Backorder case for multi-level subcontracting
                production_to_split = move.move_orig_ids[0].production_id
                original_qty = move.move_orig_ids[0].product_qty
                move.move_orig_ids = False
                _, new_mo = production_to_split.with_context(
                    allow_more=True)._split_productions(
                    {production_to_split: [original_qty, move.product_qty]})
                new_mo.move_finished_ids.move_dest_ids = move
                continue
            else:
                return  # do not create extra production for move that has quantity updated
        quantity = move.product_qty or move.quantity
        if move.product_uom.compare(quantity, 0) <= 0:
            continue  # skip negative or zero quantities
        mo_subcontract = self._prepare_subcontract_mo_vals(move, bom)
        group_by_company[move.company_id.id][0].append(mo_subcontract)
        group_by_company[move.company_id.id][1].append(move)

    for company, group in group_by_company.items():
        vals_list, moves = group
        grouped_mo = self.env['mrp.production'].with_company(company).create(vals_list)
        grouped_mo.with_context(self._get_subcontract_mo_confirmation_ctx()).action_confirm()
        for mo, move in zip(grouped_mo, moves):
            mo.date_finished = move.date
            finished_move = mo.move_finished_ids.filtered(
                lambda m: m.product_id == move.product_id)
            finished_move.move_dest_ids = [Command.link(move.id)]
        grouped_mo.action_assign()
```

**Key behaviors:**

1. **MOs batched by company:** Multiple subcontracting MOs across different companies in the same picking are created in separate batches using `with_company()`. This respects Odoo's company isolation.

2. **Multi-level subcontracting backorder case ("Magic spicy sauce"):** When a subcontracted MO itself uses subcontracted components, and that parent MO is backordered, the child subcontracting receipt move enters this branch. The parent MO is split and the resulting backorder MO is explicitly linked to the backorder receipt move via `move_finished_ids.move_dest_ids`. Without this link, the traceability chain breaks.

3. **Skip when quantity already updated:** If `move_orig_ids.production_id` exists and `move_dest_ids <= 1`, the quantity was already handled — skip MO creation entirely.

4. **Negative quantity guard:** If quantity is zero or negative after confirmation, no MO is created, preventing phantom negative-quantity MOs.

5. **`action_assign()` on the picking after MO creation:** The outer `_action_confirm` method calls `action_assign()` on the picking after `_subcontracted_produce` completes. This reserves the subcontract receipt picking's lines.

#### L2: `_prepare_subcontract_mo_vals` — MO Construction

```python
def _prepare_subcontract_mo_vals(self, subcontract_move, bom):
    subcontract_move.ensure_one()
    reference = self.env['stock.reference'].create({
        'name': self.name,
        'move_ids': [Command.link(subcontract_move.id)],
    })
    product = subcontract_move.product_id
    warehouse = self._get_warehouse(subcontract_move)
    subcontracting_location = (
        subcontract_move.picking_id.partner_id.with_company(subcontract_move.company_id)
            .property_stock_subcontractor
        or subcontract_move.company_id.subcontracting_location_id)
    vals = {
        'company_id': subcontract_move.company_id.id,
        'subcontractor_id': subcontract_move.picking_id.partner_id.commercial_partner_id.id,
        'picking_ids': [subcontract_move.picking_id.id],
        'product_id': product.id,
        'product_uom_id': subcontract_move.product_uom.id,
        'bom_id': bom.id,
        'location_src_id': subcontracting_location.id,
        'location_dest_id': subcontracting_location.id,   # same location = no physical move
        'product_qty': subcontract_move.product_uom_qty or subcontract_move.quantity,
        'picking_type_id': warehouse.subcontracting_type_id.id,  # mrp_operation type
        'date_start': subcontract_move.date - relativedelta(days=bom.produce_delay),
        'origin': self.name,
        'reference_ids': [Command.link(reference.id)],
    }
    return vals
```

- Uses `commercial_partner_id` for the `subcontractor_id` — important for subcontractor contacts with multiple child entities; the MO should be associated with the commercial entity.
- `location_src_id == location_dest_id` — the MO operates entirely at the subcontractor's location. Since both source and destination are the same internal location, the MO does not generate any physical stock move for the finished goods (they are received via the picking, not via the MO).
- `date_start` is pre-dated by `bom.produce_delay` days to reflect the subcontractor's lead time. This is a planning estimate, not a hard constraint.
- A `stock.reference` record links the receipt picking to the subcontracting MO for traceability.
- `picking_type_id` uses the **subcontracting operation type** (`code='mrp_operation'`, sequence code `SBC`) — distinct from the regular manufacturing type.

#### L3: `_get_subcontract_mo_confirmation_ctx`

```python
def _get_subcontract_mo_confirmation_ctx(self):
    if self._is_subcontract() and not self.env.context.get('cancel_backorder', True):
        return {'no_procurement': True}
    return {}  # Override point for mrp_subcontracting_purchase
```

When creating a backorder for a subcontract receipt (`cancel_backorder=False`), the `no_procurement` context prevents procurement rules from firing on component moves. The override hook for `mrp_subcontracting_purchase` (enterprise) allows integration with purchase-order-based subcontracting flows to use a different context.

#### L3: `_get_warehouse` — Warehouse Resolution Priority

```python
def _get_warehouse(self, subcontract_move):
    return (subcontract_move.warehouse_id
            or self.picking_type_id.warehouse_id
            or subcontract_move.move_dest_ids.picking_type_id.warehouse_id)
```

Resolves the warehouse from three sources in priority order: (1) the subcontract move's own warehouse_id (rarely set), (2) the picking type's warehouse, (3) the downstream move's picking type's warehouse. The third source handles cross-warehouse scenarios.

---

### 4. `mrp.production` — Subcontracting Manufacturing Orders

**File:** `models/mrp_production.py`

#### L2: Fields

```python
move_line_raw_ids = fields.One2many(
    'stock.move.line', string="Detail Component", readonly=False,
    inverse='_inverse_move_line_raw_ids', compute='_compute_move_line_raw_ids')
subcontracting_has_been_recorded = fields.Boolean("Has been recorded?", copy=False)  # deprecated
subcontractor_id = fields.Many2one('res.partner', string="Subcontractor",
    help="Used to restrict access to the portal user through Record Rules")
bom_product_ids = fields.Many2many('product.product',
    compute="_compute_bom_product_ids",
    help="List of Products used in the BoM, used to filter the product list "
         "in the subcontracting portal view")
incoming_picking = fields.Many2one(related='move_finished_ids.move_dest_ids.picking_id')
_rec_names_search = ['name', 'incoming_picking.name']
```

- **`subcontractor_id`:** Links the MO to the subcontractor partner. Used as the key field in the portal record rule (`subcontractor_rule`). Must be `commercial_partner_id` — never a child contact.
- **`move_line_raw_ids`:** A hybrid computed/inverse `One2many` over `stock.move.line`. The compute syncs from the raw moves' move lines; the inverse allows writing move lines directly from the MO form. This enables portal users to register component consumption directly on the MO form view.
- **`bom_product_ids`:** Computed from `bom_id.bom_line_ids.product_id`. Used in the portal UI to filter the product list to only those components the subcontractor can record.
- **`incoming_picking`:** A reverse link to the subcontracting receipt picking through the finished move's destination. Enables navigation from MO to receipt.
- **`_rec_names_search`:** Extends the name search to include `incoming_picking.name`, so searching for a picking name from the MO list view finds the MO.
- **`subcontracting_has_been_recorded`:** Deprecated (`# TODO: remove in master`). Previously tracked whether the MO had been recorded; replaced by more granular state tracking.

#### L2: `_inverse_move_line_raw_ids` — Component Move Line Assignment

```python
def _inverse_move_line_raw_ids(self):
    for production in self:
        line_by_product = defaultdict(lambda: self.env['stock.move.line'])
        for line in production.move_line_raw_ids:
            line_by_product[line.product_id] |= line
        for move in production.move_raw_ids:
            move.move_line_ids = line_by_product.pop(move.product_id, self.env['stock.move.line'])
        for product_id, lines in line_by_product.items():
            qty = sum(line.product_uom_id._compute_quantity(line.quantity, product_id.uom_id)
                      for line in lines)
            move = production._get_move_raw_values(product_id, qty, product_id.uom_id)
            move['additional'] = True
            production.move_raw_ids = [(0, 0, move)]
            production.move_raw_ids.filtered(
                lambda m: m.product_id == product_id)[:1].move_line_ids = lines
```

This inverse method handles the complex case where a portal user assigns move lines to a product that has no existing raw move on the MO. In that case, a new raw move is created (`additional=True`) and the move line is assigned to it. This supports the subcontracting portal flow where the subcontractor may need to record components not originally on the BoM.

#### L2: `write()` — Quantity Sync and Portal Field Security

```python
def write(self, vals):
    # Portal field-level security
    if self.env.user._is_portal() and not self.env.su:
        unauthorized_fields = set(vals.keys()) - set(self._get_writeable_fields_portal_user())
        if unauthorized_fields:
            raise AccessError(_("You cannot write on fields %s in mrp.production.",
                                ', '.join(unauthorized_fields)))

    # Date propagation from subcontract move
    if 'date_start' in vals and self.env.context.get('from_subcontract'):
        date_start = fields.Datetime.to_datetime(vals['date_start'])
        date_start_map = {
            prod: date_start - timedelta(days=prod.bom_id.produce_delay)
            if prod.bom_id else date_start
            for prod in self
        }
        res = True
        for production in self:
            res &= super(MrpProduction, production).write(
                {**vals, 'date_start': date_start_map[production]})
        return res

    old_lots = [mo.lot_producing_ids for mo in self]
    if self.env.context.get('mrp_subcontracting') and 'product_qty' in vals:
        for mo in self:
            self.sudo().env['change.production.qty'].with_context(
                skip_activity=True, mrp_subcontracting=False, no_procurement=True
            ).create([{'mo_id': mo.id, 'product_qty': vals['product_qty']}]).change_prod_qty()
            mo.sudo().action_assign()

    res = super().write(vals)

    # Sync quantity back to subcontract receipt move
    if self.env.context.get('mrp_subcontracting') and ('product_qty' in vals or 'lot_producing_ids' in vals):
        for mo, old_lot in zip(self, old_lots):
            sbc_move = mo._get_subcontract_move()
            if not sbc_move:
                continue
            if mo.product_tracking in ('lot', 'serial'):
                sbc_move_lines = sbc_move.move_line_ids.filtered(lambda m: m.lot_id == old_lot)
                sbc_move_line = sbc_move_lines[0]
                sbc_move_line.quantity = mo.product_qty
                sbc_move_line.lot_id = mo.lot_producing_ids
                sbc_move_lines[1:].unlink()  # Remove duplicate lines for the old lot
            else:
                sbc_move.quantity = mo.product_qty
    return res
```

**Key behaviors:**

1. **Portal field-level security:** White-list approach — portal users can only write to `['move_line_raw_ids', 'lot_producing_ids', 'qty_producing', 'product_qty']`. All other fields raise `AccessError`.
2. **Date propagation:** When `from_subcontract=True` context is set (called from `stock.move.write()`), `date_start` is adjusted by the BoM's `produce_delay` to account for the subcontractor's lead time. This is a per-production map because different products in the same write batch may have different BoMs.
3. **Quantity change via wizard:** When `mrp_subcontracting` context is set and `product_qty` changes, the `change.production.qty` wizard is invoked via `sudo()`. The context flags `skip_activity=True, mrp_subcontracting=False, no_procurement=True` prevent recursive loops.
4. **Quantity sync to receipt move:** After writing, the receipt move quantity is synced back. For tracked products, the lot-specific move line on the receipt is updated and duplicate lines (from the old lot) are removed.

#### L3: `_get_subcontract_move` — Finding the Receipt Move

```python
def _get_subcontract_move(self):
    return self.move_finished_ids.move_dest_ids.filtered(lambda m: m.is_subcontract)
```

Returns the stock move representing the subcontracting receipt (finished goods arriving). This is the reverse of the link created in `_subcontracted_produce` via `finished_move.move_dest_ids = [Command.link(move.id)]`. The `is_subcontract` filter ensures only the actual receipt move is returned, not any other destination moves.

#### L3: `_should_postpone_date_finished`

```python
def _should_postpone_date_finished(self, date_finished):
    return super()._should_postpone_date_finished(date_finished) and not self._get_subcontract_move()
```

For subcontracting MOs, the `date_finished` should NOT be postponed beyond the current value (because the date is driven by the subcontract receipt picking's date, not the normal MO scheduling logic). If a subcontract move is found, postponement is blocked.

#### L2: `pre_button_mark_done` — Skip Consumption Validation

```python
def pre_button_mark_done(self):
    if self._get_subcontract_move():
        return super(MrpProduction, self.with_context(skip_consumption=True)).pre_button_mark_done()
    return super().pre_button_mark_done()
```

Subcontracting MOs skip the normal consumption validation (`skip_consumption=True`). The subcontractor may consume components differently than the BoM specifies; the actual consumption recorded on the MO is authoritative.

#### L2: `_has_workorders` — No Work Orders for Subcontract

```python
def _has_workorders(self):
    if self.subcontractor_id:
        return False
    return super()._has_workorders()
```

Subcontracting MOs always return `False` for work order existence. This hides the Work Orders tab and related buttons on subcontracting MOs — the subcontractor, not the contracting company, performs the labor.

#### L2: `action_merge` — MO Merge Blocked

```python
def action_merge(self):
    if any(production._get_subcontract_move() for production in self):
        raise ValidationError(_("Subcontracted manufacturing orders cannot be merged."))
    return super().action_merge()
```

Subcontracting MOs cannot be merged because each MO is tied to a specific subcontractor partner, picking, and location. Merging would break these associations.

#### L2: `action_split_subcontracting` — Add Lots to Open Receipt

```python
def action_split_subcontracting(self):
    self.ensure_one()
    if not self.lot_producing_ids:
        raise UserError(_("Please set a lot/serial for the currently opened subcontracting MO first."))
    move = self._get_subcontract_move()
    if not move:
        return False
    if move.state == 'done':
        raise UserError(_("The subcontracted goods have already been received."))
    if all(l.lot_id for l in move.move_line_ids):
        move.move_line_ids.create({
            'product_id': move.product_id.id,
            'move_id': move.id,
            'quantity': 1,
            'lot_id': False,
        })
    return move.action_show_subcontract_details(lot_id=False)
```

Allows the subcontractor to add additional lots to an open (not-yet-done) subcontracting receipt. If all existing move lines already have lots, a new blank lot move line is created. Navigates to the subcontract detail view filtered to show the unassigned lot.

#### L2: `_get_writeable_fields_portal_user`

```python
def _get_writeable_fields_portal_user(self):
    return ['move_line_raw_ids', 'lot_producing_ids', 'qty_producing', 'product_qty']
```

The explicit white-list of portal-writable fields. This method is the single point of truth for portal field access control on subcontracting MOs.

---

### 5. `res.partner` — Subcontractor Partners

**File:** `models/res_partner.py`

#### L2: Fields

```python
property_stock_subcontractor = fields.Many2one(
    'stock.location', string="Subcontractor Location", company_dependent=True,
    help="The stock location used as source and destination when sending "
         "goods to this contact during a subcontracting process.")
is_subcontractor = fields.Boolean(
    string="Subcontractor", store=False, search='_search_is_subcontractor',
    compute='_compute_is_subcontractor')
bom_ids = fields.Many2many('mrp.bom', compute='_compute_bom_ids',
    string="BoMs for which the Partner is one of the subcontractors")
production_ids = fields.Many2many('mrp.production', compute='_compute_production_ids',
    string="MRP Productions for which the Partner is the subcontractor")
picking_ids = fields.Many2many('stock.picking', compute='_compute_picking_ids',
    string="Stock Pickings for which the Partner is the subcontractor")
```

- **`property_stock_subcontractor`:** Company-dependent property — each company can have a different subcontractor location for the same partner. This is how multi-company setups handle the same partner as a subcontractor in different companies.
- **`is_subcontractor`:** Non-stored computed field with custom search. Only `True` for partners who are both (a) associated with a portal user AND (b) listed in at least one active subcontracting BoM.
- **`bom_ids`, `production_ids`, `picking_ids`:** Non-stored computed Many2many fields. These drive the portal record rules by providing the list of accessible record IDs.

#### L3: `_compute_bom_ids` / `_compute_production_ids` / `_compute_picking_ids` — `_read_group` Optimization

```python
def _compute_bom_ids(self):
    results = self.env['mrp.bom']._read_group(
        [('subcontractor_ids.commercial_partner_id', 'in', self.commercial_partner_id.ids)],
        ['subcontractor_ids'], ['id:array_agg'])
    for partner in self:
        bom_ids = []
        for subcontractor, ids in results:
            if partner.id == subcontractor.id or subcontractor.id in partner.child_ids.ids:
                bom_ids += ids
        partner.bom_ids = bom_ids
```

**Why `_read_group` instead of naive `search`?**
- `_read_group` performs a single SQL `GROUP BY` query to fetch all BoM IDs grouped by subcontractor in one round-trip. A naive `for partner in self: partner.bom_ids = search([...])` would execute N queries for N partners.
- The `commercial_partner_id` domain ensures that child contacts of a company are also matched — a subcontractor's delivery contact should show the same BoMs as the parent company.
- **L4 Performance:** These fields are computed (not stored), so they recompute on every access. For a partner with many child contacts and many BoMs, the Python-side loop over `_read_group` results adds overhead, but the SQL query itself is efficient. In a portal context with many subcontractors, consider storing these fields if performance becomes an issue.

#### L3: `_search_is_subcontractor` — Portal Access Predicate

```python
def _search_is_subcontractor(self, operator, value):
    if operator != 'in':
        return NotImplemented
    subcontractor_ids = self.env['mrp.bom'].search(
        [('type', '=', 'subcontract')]).subcontractor_ids.ids
    return [('id', 'in', subcontractor_ids)]
```

Only supports the `in` operator. Returns all partner IDs that appear in any subcontracting BoM's `subcontractor_ids`. This search is used by record rules to grant portal users read access to subcontractors' picking records.

#### L3: `_compute_is_subcontractor` — Dual-Condition Subcontractor Status

```python
def _compute_is_subcontractor(self):
    for partner in self:
        partner.is_subcontractor = (
            any(user._is_portal() for user in partner.user_ids)
            and partner.env['mrp.bom'].search_count([
                ('type', '=', 'subcontract'),
                ('subcontractor_ids', 'in', (partner | partner.commercial_partner_id).ids),
            ], limit=1)
        )
```

- **Condition 1:** The partner must have at least one portal user associated.
- **Condition 2:** There must be at least one active subcontracting BoM referencing this partner (or its commercial partner).
- This dual check prevents giving subcontractor-like access (via the portal UI) to regular vendors who happen to have a contact user but no actual subcontracting BoM.

---

### 6. `stock.location` — Subcontracting Locations

**File:** `models/stock_location.py`

```python
subcontractor_ids = fields.One2many('res.partner', 'property_stock_subcontractor')

@api.constrains('usage', 'location_id')
def _check_subcontracting_location(self):
    for location in self:
        if location == location.company_id.subcontracting_location_id:
            raise ValidationError(_("You cannot alter the company's subcontracting location"))
        if location.is_subcontract() and location.usage != 'internal':
            raise ValidationError(_("In order to manage stock accurately, subcontracting locations "
                                    "must be type Internal, linked to the appropriate company."))

def _check_access_putaway(self):
    if self.env.user.partner_id.is_subcontractor:
        return self.sudo()
    return super()._check_access_putaway()

def is_subcontract(self):
    subcontracting_location = self.company_id.subcontracting_location_id
    return subcontracting_location and self._child_of(subcontracting_location)
```

- **`is_subcontract()`:** Returns `True` if the location is a descendant of the company's main subcontracting location. This uses the internal `_child_of` method which translates to a recursive SQL query. Used throughout the module to identify all subcontracting-related locations — both the company-level default AND any partner-specific overrides.
- **`_check_access_putaway()`:** Grants `sudo()` access to subcontractors when they access the putaway view. This allows subcontractors to manage putaway rules for their own locations without needing internal user permissions.
- **`_check_subcontracting_location` constraint:** Two rules: (1) the company-level subcontracting location cannot be deleted or modified, (2) subcontracting locations (descendants of the company location) must have `usage='internal'`. Non-internal subcontracting locations would break stock valuation.
- **`subcontractor_ids`:** One2many in the reverse direction — every partner with `property_stock_subcontractor` pointing to this location appears here. Useful for auditing which partners share a location.

---

### 7. `stock.warehouse` — Subcontracting Routes and Rules

**File:** `models/stock_warehouse.py`

#### L2: Fields

```python
subcontracting_to_resupply = fields.Boolean('Resupply Subcontractors', default=True)
subcontracting_mto_pull_id = fields.Many2one('stock.rule', 'Subcontracting MTO Rule', copy=False)
subcontracting_pull_id = fields.Many2one('stock.rule', 'Subcontracting MTS Rule', copy=False)
subcontracting_route_id = fields.Many2one('stock.route', 'Resupply Subcontractor', ondelete='restrict', copy=False)
subcontracting_type_id = fields.Many2one(
    'stock.picking.type', 'Subcontracting Operation Type',
    domain=[('code', '=', 'mrp_operation')], copy=False)
subcontracting_resupply_type_id = fields.Many2one(
    'stock.picking.type', 'Subcontracting Resupply Operation Type',
    domain=[('code', '=', 'internal')], copy=False)
```

- **`subcontracting_to_resupply = True`** by default: Every new warehouse created after module installation automatically enables the resupply feature. On module install, a `noupdate="1"` function writes `True` to all existing warehouses.
- **`subcontracting_type_id`:** The `mrp_operation` picking type used for the subcontracting MO. Sequence code `SBC`.
- **`subcontracting_resupply_type_id`:** The `internal` picking type for component resupply transfers. Sequence code `RES`. Has `print_label=True` for generating shipping labels.

#### L3: `_get_picking_type_create_values` — Picking Type Setup

```python
'subcontracting_type_id': {
    'name': _('Subcontracting'),
    'code': 'mrp_operation',
    'use_create_components_lots': True,  # Can create lots for components
    'sequence': next_sequence + 2,
    'sequence_code': 'SBC',
    'company_id': self.company_id.id,
},
'subcontracting_resupply_type_id': {
    'name': _('Resupply Subcontractor'),
    'code': 'internal',
    'use_create_lots': False,
    'use_existing_lots': True,
    'default_location_dest_id': self._get_subcontracting_location().id,
    'sequence': next_sequence + 3,
    'sequence_code': 'RES',
    'print_label': True,  # Generate shipping labels
    'company_id': self.company_id.id,
}
```

The resupply picking type has `use_create_lots=False` (the subcontractor receives generic components, no need to create lots at resupply) and `print_label=True` (shipping labels are needed for the subcontractor shipment).

#### L3: `_generate_global_route_rules_values` — Two Pull Rules

**MTO Pull Rule — `subcontracting_mto_pull_id`:**
- Source: `lot_stock_id` (warehouse stock)
- Destination: `subcontracting_location`
- Action: `pull`
- Procure method: `make_to_order`
- Route: `stock.route_warehouse0_mto` (global MTO route)
- Triggered when: the subcontracting receipt move is created. Creates a **resupply picking** to deliver components from warehouse stock to the subcontractor.

**Subcontracting Pull Rule — `subcontracting_pull_id`:**
- Source: `subcontracting_location` (goods at subcontractor, consumed)
- Destination: `production_location` (where the MO expects components)
- Action: `pull`
- Procure method: `make_to_order`
- Route: `mrp_subcontracting.route_resupply_subcontractor_mto` (subcontracting-specific global route)
- Triggered when: the subcontracting MO's component moves are confirmed. Creates a **consumption transfer** from the subcontractor location to mark the components as consumed.

#### L3: `_update_global_route_resupply_subcontractor` — Route Activation Logic

```python
def _update_global_route_resupply_subcontractor(self):
    route_id = self._find_or_create_global_route(
        'mrp_subcontracting.route_resupply_subcontractor_mto',
        _('Resupply Subcontractor on Order'))
    if not route_id.sudo().rule_ids.filtered(lambda r: r.active):
        route_id.active = False
    else:
        route_id.active = True
        self.route_ids = [Command.link(route_id.id)]
```

The global resupply route (`route_resupply_subcontractor_mto`) is activated only when at least one warehouse has `subcontracting_to_resupply=True`. If all warehouses disable resupply, the global route is deactivated. This keeps the route catalog clean.

#### L3: `_update_resupply_rules` — Rule Archival on Disable

```python
def _update_resupply_rules(self):
    subcontracting_locations = self._get_subcontracting_locations()
    warehouses_to_resupply = self.filtered(lambda w: w.subcontracting_to_resupply and w.active)
    if warehouses_to_resupply:
        self.env['stock.rule'].with_context(active_test=False).search([
            '&', ('picking_type_id', 'in', warehouses_to_resupply.subcontracting_resupply_type_id.ids),
            '|', ('location_src_id', 'in', subcontracting_locations.ids),
               ('location_dest_id', 'in', subcontracting_locations.ids)]).action_unarchive()
    warehouses_not_to_resupply = self - warehouses_to_resupply
    if warehouses_not_to_resupply:
        self.env['stock.rule'].search([
            '&', ('picking_type_id', 'in', warehouses_not_to_resupply.subcontracting_resupply_type_id.ids),
            '|', ('location_src_id', 'in', subcontracting_locations.ids),
               ('location_dest_id', 'in', subcontracting_locations.ids)]).action_archive()
```

When `subcontracting_to_resupply` is toggled off, all resupply rules for that warehouse's picking type are archived. The search includes rules whose source OR destination is a subcontracting location (handles both the MTO pull and the consumption pull rules).

---

### 8. `stock.rule` — Resupply Rule Values

**File:** `models/stock_rule.py`

#### L3: `_push_prepare_move_copy_values` — Reset Subcontract Flag

```python
def _push_prepare_move_copy_values(self, move_to_copy, new_date):
    new_move_vals = super()._push_prepare_move_copy_values(move_to_copy, new_date)
    new_move_vals["is_subcontract"] = False
    return new_move_vals
```

When stock push rules copy a move (e.g., in a drop-ship or cross-dock scenario), the `is_subcontract` flag is explicitly reset to `False`. This ensures that moves created by push rules are never mistaken for subcontracting receipts.

#### L3: `_get_stock_move_values` — Partner Propagation

```python
def _get_stock_move_values(self, product_id, product_qty, product_uom, location_dest_id,
                           name, origin, company_id, values):
    move_values = super()._get_stock_move_values(...)
    if not move_values.get('partner_id'):
        if values.get('move_dest_ids') and values['move_dest_ids'].raw_material_production_id.subcontractor_id:
            move_values['partner_id'] = values['move_dest_ids'].raw_material_production_id.subcontractor_id.id
    return move_values
```

When creating resupply moves (component deliveries to the subcontractor), if no `partner_id` is already set, the system looks at the destination move's linked MO (`raw_material_production_id`) and propagates the `subcontractor_id` as the `partner_id` on the resupply move. This enables the resupply picking to be addressed to the correct subcontractor contact.

---

### 9. `stock.move.line` — Component Registration Triggers

**File:** `models/stock_move_line.py`

The move line extension is the **triggering layer** for keeping subcontracting MOs in sync with the receipt move's lot/quantity data.

#### L3: `_onchange_serial_number` — Warning for Subcontract Location

```python
@api.onchange('lot_name', 'lot_id')
def _onchange_serial_number(self):
    current_location_id = self.location_id
    res = super()._onchange_serial_number()
    if res and not self.lot_name and current_location_id.is_subcontract():
        self.location_id = current_location_id  # preserve location
        res['warning']['message'] = (
            res['warning']['message'].split("\n\n", 1)[0]
            + "\n\n"
            + _("Make sure you validate or adapt the related resupply picking to your "
                "subcontractor in order to avoid inconsistencies in your stock."))
    return res
```

When a subcontractor removes a serial number in the subcontracting location context, the base `super()` warning about changing the source location is preserved and augmented with an additional warning message reminding the user to validate the related resupply picking.

#### L3: `write` / `create` / `unlink` Triggers — `_sync_subcontracting_productions`

```python
def write(self, vals):
    res = super().write(vals)
    if not self.env.context.get('mrp_subcontracting') and ('quantity' in vals or 'lot_id' in vals):
        self.move_id.filtered(lambda m: m.is_subcontract).with_context(
            no_procurement=True)._sync_subcontracting_productions()
    return res

def unlink(self):
    moves_to_sync = self.move_id.filtered(lambda m: m.is_subcontract)
    res = super().unlink()
    moves_to_sync._sync_subcontracting_productions()
    return res

@api.model_create_multi
def create(self, vals_list):
    res = super().create(vals_list)
    res.move_id.filtered(lambda m: m.is_subcontract)._sync_subcontracting_productions()
    return res
```

- **`write`:** Triggers sync when `quantity` or `lot_id` changes outside of the `mrp_subcontracting` context (to prevent recursive calls when the sync itself writes to move lines).
- **`create`:** New move lines trigger sync immediately after creation.
- **`unlink`:** After deletion, sync is called to clean up any MOs that lost their lot link.
- The `no_procurement=True` context prevents procurement rules from firing as a side effect of the quantity sync.

#### L3: `_sync_subcontracting_productions` — Tracked Component Sync

See `models/stock_move.py` for the full three-step logic: (1) match existing MOs to lots, update quantities via wizard; (2) create new MOs via `_split_productions` for lots without MOs; (3) delete orphan MOs whose lots were removed.

---

### 10. `stock.quant` — Subcontracting Quant Search

**File:** `models/stock_quant.py`

```python
is_subcontract = fields.Boolean(store=False, search='_search_is_subcontract')

def _search_is_subcontract(self, operator, value):
    if operator != 'in':
        return NotImplemented
    subcontracting_location_ids = (
        self.env.companies.subcontracting_location_id.child_internal_location_ids.ids)
    return [('location_id', operator, subcontracting_location_ids)]
```

The `is_subcontract` search field allows filtering quants that reside in any subcontracting location — the company-level location and all its child internal locations (which includes `property_stock_subcontractor` locations for each subcontractor partner). This supports inventory reporting and valuation views that want to show "stock at subcontractors" separately from regular stock. The search uses `self.env.companies` (multi-company aware) to scope the location list.

---

### 11. `res.company` — Subcontracting Location Auto-Creation

**File:** `models/res_company.py`

```python
subcontracting_location_id = fields.Many2one('stock.location')

@api.model
def _create_missing_subcontracting_location(self):
    company_without_subcontracting_loc = (
        self.env['res.company'].with_context(active_test=False).search(
            [('subcontracting_location_id', '=', False)]))
    company_without_subcontracting_loc._create_subcontracting_location()

def _create_per_company_locations(self):
    super()._create_per_company_locations()
    self._create_subcontracting_location()

def _create_subcontracting_location(self):
    for company in self:
        subcontracting_location = self.env['stock.location'].create({
            'name': _('Subcontracting'),
            'usage': 'internal',
            'company_id': company.id,
        })
        self.env['ir.default'].set(
            "res.partner", "property_stock_subcontractor",
            subcontracting_location.id, company_id=company.id)
        company.subcontracting_location_id = subcontracting_location
```

- **`_create_per_company_locations`:** Called during company creation via the ORM `__init__` hook. The `_create_subcontracting_location` runs after the base locations (warehouse, production location, etc.) are created.
- **`_create_missing_subcontracting_location`:** An `@api.model` hook called via the data file's noupdate function on module install. Ensures companies that existed before the module was installed get a subcontracting location retroactively.
- **`ir.default` set:** Sets the newly created location as the default value for all partners' `property_stock_subcontractor` via `ir.default`. New partners automatically inherit the company subcontracting location; existing partners are unchanged unless they had no value set.

---

### 12. `product.product` / `product.supplierinfo` — Subcontractor in Purchase Pricing

**File:** `models/product.py`

```python
class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    is_subcontractor = fields.Boolean(
        'Subcontracted', compute='_compute_is_subcontractor',
        help="Choose a vendor of type subcontractor if you want to subcontract the product")

    @api.depends('partner_id', 'product_id', 'product_tmpl_id')
    def _compute_is_subcontractor(self):
        for supplier in self:
            boms = supplier.product_id.variant_bom_ids
            boms |= supplier.product_tmpl_id.bom_ids.filtered(
                lambda b: not b.product_id or b.product_id in
                          (supplier.product_id or supplier.product_tmpl_id.product_variant_ids))
            supplier.is_subcontractor = supplier.partner_id in boms.subcontractor_ids


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _prepare_sellers(self, params=False):
        if params and params.get('subcontractor_ids'):
            return super()._prepare_sellers(params=params).filtered(
                lambda s: s.partner_id in params.get('subcontractor_ids'))
        return super()._prepare_sellers(params=params)
```

- **`is_subcontractor`:** On `product.supplierinfo`, computed from whether the vendor appears in any subcontracting BoM for the product (variant or template level). Helps purchasing users identify and filter subcontracted products.
- **`_prepare_sellers` override:** Allows filtering seller records by subcontractor when looking up purchase pricing for a subcontracted product. The `subcontractor_ids` parameter comes from the BoM report's call to `_select_seller(..., params={'subcontractor_ids': bom.subcontractor_ids})`.

---

### 13. `stock.return.picking` — Return to Subcontractor

**File:** `wizard/stock_picking_return.py`

```python
class StockReturnPicking(models.TransientModel):
    def _prepare_picking_default_values(self):
        vals = super()._prepare_picking_default_values()
        if all(return_line.quantity > 0 and return_line.move_id.is_subcontract
               for return_line in self.product_return_moves):
            vals['location_dest_id'] = (
                self.picking_id.partner_id.with_company(self.picking_id.company_id)
                    .property_stock_subcontractor.id)
        return vals

class StockReturnPickingLine(models.TransientModel):
    def _prepare_move_default_values(self, new_picking):
        vals = super()._prepare_move_default_values(new_picking)
        if self.move_id.is_subcontract:
            vals['location_dest_id'] = (
                new_picking.partner_id.with_company(new_picking.company_id)
                    .property_stock_subcontractor.id)
            vals['is_subcontract'] = False  # Return move is NOT a subcontract move
        return vals
```

- The return picking's destination is set to the **subcontractor's location** when ALL selected return lines are subcontract moves with positive quantity.
- The return move has `is_subcontract = False` — a return is a regular internal/return move, not a new subcontracting receipt.
- If the subcontractor has no `property_stock_subcontractor` set, the company-level `subcontracting_location_id` is used as a fallback.

---

### 14. `change.production.qty` — Skip Propagation for Subcontract

**File:** `wizard/change_production_qty.py`

```python
@api.model
def _need_quantity_propagation(self, move, qty):
    res = super()._need_quantity_propagation(move, qty)
    return res and not any(m.is_subcontract for m in move.move_dest_ids)
```

When changing a non-subcontracting MO's quantity, the wizard normally propagates the change downstream through move chains. However, if a downstream move is a subcontracting receipt (`is_subcontract=True`), propagation is blocked. This is because the subcontracting receipt quantity is managed through the subcontracting workflow (via the MO's `product_qty` change which syncs to the receipt move), not through normal procurement propagation.

---

### 15. `mrp.production.serials` — Multi-Lot Registration

**File:** `wizard/mrp_production_serial_numbers.py`

```python
def action_apply(self):
    self.ensure_one()
    sbc_move = self.production_id._get_subcontract_move()
    if not sbc_move:
        return super().action_apply()

    lots = list(filter(
        lambda serial_number: len(serial_number.strip()) > 0,
        self.serial_numbers.split('\n'))) if self.serial_numbers else []
    existing_lots = self.env['stock.lot'].search([
        '|', ('company_id', '=', False),
            ('company_id', '=', self.production_id.company_id.id),
        ('product_id', '=', self.production_id.product_id.id),
        ('name', 'in', lots),
    ])
    # ... reuse existing lots, create new ones ...
    all_lots = existing_lots + self.env['stock.lot'].create(new_lots)
    self.production_id.with_context(mrp_subcontracting=True).write({
        'lot_producing_ids': all_lots[0],
        'product_qty': 1,
    })
    sbc_move.move_line_ids.create([
        {'product_id': lot.product_id.id, 'lot_id': lot.id,
         'move_id': sbc_move.id, 'quantity': 1}
        for lot in all_lots[1:]
    ])
    return sbc_move.picking_id.action_show_subcontract_details()
```

For subcontracting MOs with serial number tracking, this wizard allows **batch registration of multiple serial numbers** in one operation. The wizard:
1. Parses newline-separated serial number strings.
2. Reuses existing lots (company_id=None or matching) or creates new `stock.lot` records.
3. Writes the first lot to the MO via `lot_producing_ids` and `product_qty=1`.
4. Creates additional `stock.move.line` records on the subcontract receipt move for extra lots.
5. Updates the lot sequence's `number_next_actual` counter if the new lot matches the next expected sequence value.
6. Navigates back to the subcontracting MO detail view.

---

### 16. `mrp.unbuild` — Unbuild Blocked

**File:** `models/mrp_unbuild.py`

```python
def button_unbuild(self):
    if self.subcontractor_id:
        raise UserError(_("You can't unbuild a subcontracted Manufacturing Order."))
    return super().button_unbuild()
```

Unbuild is blocked for all subcontracting MOs (`subcontractor_id` is set). The rationale is that unbuilding (disassembling) a subcontracted product would require returning components to the subcontractor, which involves complex accounting, stock handling, and vendor relationship scenarios not covered by the standard unbuild flow. Returns should be handled via the `stock.return.picking` flow.

---

### 17. Report: `report.mrp.report_bom_structure` — Subcontracting in BoM Cost Analysis

**File:** `report/mrp_report_bom_structure.py`

The BoM cost structure report is extended with six method overrides covering subcontracting cost display, route availability, lead time calculation, and stock availability.

#### L3: `_get_bom_data` — Subcontracting Cost Line

```python
def _get_bom_data(self, bom, warehouse, product=False, ...):
    res = super()._get_bom_data(...)
    if bom.type == 'subcontract' and not self.env.context.get('minimized', False):
        seller = res['product']._select_seller(
            quantity=res['quantity'], uom_id=bom.product_uom_id,
            params={'subcontractor_ids': bom.subcontractor_ids})
        if seller:
            res['subcontracting'] = self._get_subcontracting_line(bom, seller, level + 1, res['quantity'])
            if not self.env.context.get('minimized', False):
                res['bom_cost'] += res['subcontracting']['bom_cost']
    return res
```

The subcontracting cost uses the **vendor price** from `product.supplierinfo`, not component costs. The `_select_seller` call passes `params={'subcontractor_ids': bom.subcontractor_ids}` to filter sellers to only subcontractors of the BoM, ensuring the correct price is used. If no `product` is passed (BoM-level report without a specific variant), a fallback seller lookup uses `seller_ids.filtered()` directly on the template.

#### L3: `_get_subcontracting_line` — Cost Line Format

```python
def _get_subcontracting_line(self, bom, seller, level, bom_quantity):
    ratio_uom_seller = seller.product_uom_id.factor / bom.product_uom_id.factor
    price = seller.currency_id._convert(
        seller.price, self.env.company.currency_id, bom.company_id or self.env.company,
        fields.Date.today())
    return {
        'name': seller.partner_id.display_name,
        'partner_id': seller.partner_id.id,
        'quantity': bom_quantity,
        'uom': bom.product_uom_id.name,
        'bom_cost': price / ratio_uom_seller * bom_quantity,
        'level': level or 0
    }
```

- `ratio_uom_seller`: Converts the seller's price unit (which may differ from the BoM's uom) to the BoM's uom.
- Currency conversion uses today's exchange rate.

#### L3: `_get_resupply_availability` — Lead Time Computation

```python
def _get_resupply_availability(self, route_info, components):
    resupply_state, resupply_delay = super()._get_resupply_availability(route_info, components)
    if route_info.get('route_type') == 'subcontract':
        max_component_delay = self._get_max_component_delay(components)
        if max_component_delay is False:
            return ('unavailable', False)
        vendor_lead_time = route_info['supplier'].delay
        manufacture_lead_time = route_info['bom'].produce_delay
        subcontract_delay = resupply_delay if resupply_delay else 0
        subcontract_delay += max(vendor_lead_time, manufacture_lead_time) + max_component_delay
        route_info['manufacture_delay'] = route_info['lead_time'] + max(vendor_lead_time, manufacture_lead_time)
        route_info['lead_time'] += max(vendor_lead_time, manufacture_lead_time + route_info['bom'].days_to_prepare_mo)
        return ('estimated', subcontract_delay)
    return (resupply_state, resupply_delay)
```

Total lead time = resupply_delay + max(vendor_lead_time, manufacture_lead_time) + max_component_delay. The `max(vendor_lead_time, manufacture_lead_time)` accounts for whether the subcontractor procures components themselves (vendor lead time) or already has them (manufacture lead time only). The `days_to_prepare_mo` is added to the final lead time for scheduling.

#### L3: `_find_special_rules` — Subcontract Location Rule Resolution

When a component is being routed from a subcontracted product, the rule resolution looks at the **subcontractor's location** rather than the warehouse stock location. This ensures component availability is checked at the right place.

#### L3: `_get_quantities_info` — Subcontract Location Stock Levels

For components used in a subcontracted product, their stock levels are fetched from the **subcontractor's location** (`property_stock_subcontractor`) rather than the regular warehouse. The `stock_loc` key is prefixed with `subcontract_` to separate the consumption calculation.

---


### 18. `stock.reference` — Picking-to-MO Traceability Link

**File:** `models/stock_picking.py` (created via `stock.reference` model)

The `stock.reference` model (introduced in Odoo 19) provides a formal traceability link between a receipt picking and the subcontracting MO it spawns. Each subcontracting MO carries one or more `reference_ids` pointing back to the originating picking.

```python
reference = self.env['stock.reference'].create({
    'name': self.name,
    'move_ids': [Command.link(subcontract_move.id)],
})
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | Char | Copy of the picking's `name` field for display purposes |
| `move_ids` | Many2many `stock.move` | The subcontract receipt `stock.move` records linked to this reference |

**L3: Traceability purpose:**
- Enables the traceability report to navigate from a receipt picking to the associated subcontracting MO and back.
- The reference is stored in `mrp.production.reference_ids` via `Command.link(reference.id)`.
- Multiple picking references can exist for a single MO when the MO has been split (e.g., partial receipts/create backorder scenario).
- The `name` field is a denormalized copy of `picking_id.name`; if the picking's name changes, the reference name does not automatically update. This is intentional — the reference preserves the historical context at the time of MO creation.

**L4: Model origin:**
- `stock.reference` is a core Odoo model (not introduced by `mrp_subcontracting`). The module is the primary consumer, creating reference records in `_prepare_subcontract_mo_vals`.
- Other modules (e.g., `stock_account`) also create `stock.reference` records for different traceability contexts (e.g., landed costs linked to receipts).


## Portal Controller (`controllers/portal.py`)

**File:** `controllers/portal.py`

The module provides a dedicated portal interface for subcontractors to view and manage their subcontracting work, embedded within the Odoo backend.

### Endpoints

**`/my/productions`** and **`/my/productions/page/<int:page>`**
- List view of all subcontracting pickings for the current portal user.
- Domain: `partner_id.commercial_partner_id = user.partner_id.commercial_partner_id` AND `move_ids.is_subcontract = True`.
- Supports state filtering (all/done/ready) and sorting (date or name).
- Paginated with the standard portal pager.

**`/my/productions/<int:picking_id>`**
- Detail view rendering `mrp_subcontracting.subcontracting_portal` template with picking context.
- Raises 404 if the user cannot access the picking (record rule enforced).

**`/my/productions/<int:picking_id>/subcontracting_portal`**
- Embeds the Odoo backend form view for the subcontracting MO within the portal page.
- Overrides `session_info` to restrict the session to only the picking's company (`user_companies` updated to single-company access).
- Uses the custom action `subcontracting_portal_view_production_action` to render the backend view with portal-appropriate access and fields.

### `_prepare_home_portal_values`

Adds `production_count` to the portal dashboard by counting subcontracting pickings for the current user. Uses the same domain as the list endpoint.

---


## `uninstall_hook` — Module Cleanup on Uninstall

**File:** `__init__.py`

```python
def uninstall_hook(env):
    warehouses = env["stock.warehouse"].search([])
    subcontracting_routes = warehouses.mapped("subcontracting_route_id")
    warehouses.write({"subcontracting_route_id": False})
    companies = env["res.company"].search([])
    subcontracting_locations = companies.mapped("subcontracting_location_id")
    subcontracting_locations.active = False
    companies.write({"subcontracting_location_id": False})
    operations_type_to_remove = (warehouses.subcontracting_resupply_type_id | warehouses.subcontracting_type_id)
    operations_type_to_remove.active = False
    try:
        with env.cr.savepoint():
            subcontracting_routes.unlink()
            operations_type_to_remove.unlink()
    except:
        pass
```

When the module is uninstalled, `uninstall_hook` performs a multi-step cleanup:

1. **Routes disconnected first:** All warehouses have their `subcontracting_route_id` set to `False`. This unlinks the route without deleting it.
2. **Subcontracting locations deactivated:** Both company-level `subcontracting_location_id` and all partner `property_stock_subcontractor` locations are set to `active=False`. The locations are preserved (not deleted) so that stock quants still reference valid locations after uninstall.
3. **Operation types deactivated:** The subcontracting and resupply operation types (`subcontracting_type_id`, `subcontracting_resupply_type_id`) are archived.
4. **Routes and operation types deleted:** Using `savepoint()` to safely attempt deletion. If other modules have created records depending on these routes or operation types, the `try/except` silently catches the error and leaves them in the database.

**Why not delete locations?** Deleting `stock.location` records would break `stock.quant` and `stock.move.line` records that reference those locations. By setting `active=False`, the locations remain in the database for historical data integrity but are excluded from normal operations.


## Security

### Record Rules (`security/mrp_subcontracting_security.xml`)

Subcontractors are portal users. The module defines 14 portal record rules granting read access (and for some models, write access via the model's own ACL) to:

| Model | Rule Domain | Access via |
|---|---|---|
| `mrp.production` | `subcontractor_id = user.partner_id.commercial_partner_id` | Portal record rule |
| `mrp.bom` | `id in user.partner_id.commercial_partner_id.bom_ids.ids` | Portal record rule |
| `mrp.bom.line` | `id in user.partner_id.commercial_partner_id.bom_ids.bom_line_ids.ids` | Portal record rule |
| `mrp.consumption.warning` | `mrp_production_ids in user.partner_id.commercial_partner_id.production_ids` | Portal record rule |
| `mrp.consumption.warning.line` | `mrp_production_id in user.partner_id.commercial_partner_id.production_ids` | Portal record rule |
| `stock.move` | `production_id.subcontractor_id`, `move_orig_ids.production_id.subcontractor_id`, `raw_material_production_id.subcontractor_id` | Portal record rule |
| `stock.move.line` | `move_id.production_id.subcontractor_id`, etc. | Portal record rule |
| `stock.picking` | `partner_id.commercial_partner_id = user.partner_id.commercial_partner_id` | Portal record rule |
| `stock.picking.type` | `id in picking_ids.picking_type_id` or `production_ids.picking_type_id` | Portal record rule |
| `stock.location` | `child_ids` / `id in picking_ids.location_id`, etc. | Portal record rule |
| `stock.warehouse` | `id in picking_ids.picking_type_id.warehouse_id` | Portal record rule |
| `stock.lot` | `product_id in bom_ids.product_id` or `product_id in bom_ids.bom_line_ids.product_id` | Portal record rule |
| `product.template` | `id in bom_ids.product_id.product_tmpl_id` or `bom_ids.bom_line_ids.product_id.product_tmpl_id` | Portal record rule |

#### L3: Portal Access Flow

1. Portal user accesses `/my/productions` — controller queries `stock.picking` with the commercial partner domain.
2. Record rules on `stock.picking` (via `picking_subcontractor_rule`) ensure the user only sees their own pickings.
3. The picking detail page renders the subcontracting portal template.
4. The embedded backend view (`/my/productions/<id>/subcontracting_portal`) passes a restricted `session_info` with only the picking's company, preventing the portal user from accessing other companies' data.
5. On the MO form, the `_get_writeable_fields_portal_user()` white-list on `mrp.production.write()` ensures portal users can only modify `move_line_raw_ids`, `lot_producing_ids`, `qty_producing`, and `product_qty`.

#### L4: Security Considerations

- **`sudo()` usage:** `productions_to_done.sudo()` in `_action_done` and `production_to_split.sudo()` in `_sync_subcontracting_productions` are necessary for portal workflows. The operations are scoped to records the portal user has legitimate access to (via record rules), and `sudo()` only bypasses the ACL check for the specific MO records being validated.
- **`is_subcontractor` dual condition:** The `is_subcontractor` computed field on `res.partner` requires both a portal user and an active subcontracting BoM. Without this check, any partner with a portal user (even a customer) would be marked as a subcontractor, potentially exposing picking data.

---

## Workflow: Complete Subcontracting Flow

### Step 1: BoM Definition
- Create a BoM with `type = 'subcontract'`.
- Add the subcontractor partner(s) to `subcontractor_ids`.
- Add all component lines (raw materials). Operations and by-products are not allowed.

### Step 2: Subcontracting Receipt Creation (Incoming Picking)
- Create a receipt (incoming picking) for the finished product from the subcontractor vendor.
- When the picking is **confirmed** (`_action_confirm` on `stock.move`):
  1. Odoo searches for a matching subcontracting BoM via `_get_subcontract_bom()`.
  2. The stock move is marked `is_subcontract = True`.
  3. `location_id` changes from `supplier` to the **subcontracting location**.
  4. A **subcontracting MO** is automatically created via `_subcontracted_produce()`.
  5. The MO is confirmed and component moves are reserved.
  6. The MTO procurement rule fires and creates a **resupply picking** (if `subcontracting_to_resupply` is enabled).

### Step 3: Component Resupply
- The internal transfer (resupply) delivers raw materials from warehouse stock to the subcontractor's `property_stock_subcontractor` location.
- The subcontractor receives these components to manufacture the product.

### Step 4: Production at Subcontractor (Portal)
- The subcontractor (portal user) accesses the MO via the customer portal at `/my/productions/<id>`.
- The embedded backend view allows the subcontractor to register component consumption (`move_line_raw_ids`) and record lot/serial numbers for the finished product.
- For tracked products with multiple lots, `action_split_subcontracting` or the `mrp.production.serials` wizard handles multi-lot registration.

### Step 5: Receipt Validation
- When the receipt picking is **validated** (`_action_done` on `stock.picking`):
  1. `sudo()` marks the subcontracting MO done.
  2. Production move dates are set to 1 second before the picking date.
  3. Finished goods quant is created in the warehouse stock location.

### Step 6: Valuation
- Finished product is valued at the **subcontracting cost** (from `product.supplierinfo` price).
- Component consumption reduces stock at the subcontracting location at component cost.
- `stock_landed_costs` can add freight, duties, and other landing costs to the subcontracted product valuation.

---

## L4: Performance, Historical Changes, and Edge Cases

### Performance Considerations

1. **`_read_group` in computed partner relations:**
   - `_compute_bom_ids`, `_compute_production_ids`, `_compute_picking_ids` use a single SQL `GROUP BY` query instead of N `search` calls. This scales well for bulk partner imports.
   - The Python-side loop over `_read_group` results is O(partners × results per partner). For a partner with many child contacts and many BoMs, this can add up.
   - These fields are computed (not stored), so they recompute on every access. For large partner lists in the subcontractor master, consider storing them if performance degrades.

2. **`_sync_subcontracting_productions` with lot-based splitting:**
   - The lot quantity aggregation via `_read_group` is efficient (single SQL query).
   - However, calling `change.production.qty` wizard and `action_assign` per lot is expensive. For a receipt with 100+ lots, this creates 100+ wizard instances and MO reservation calls.
   - The orphan MO deletion (`unlink()`) via `sudo()` with `skip_activity=True` avoids errors but still incurs SQL DELETE cost proportional to orphan count.

3. **`sudo()` usage throughout:**
   - `productions_to_done.sudo()` in `_action_done` and `production_to_split.sudo()` in `_sync_subcontracting_productions` bypass ACL checks. These are safe because they only operate on records the current user has legitimate access to via record rules.
   - The BOM lookup in `_get_subcontract_bom` uses `.sudo()` to bypass `mrp.bom` record rules. This is safe because the BOM is already validated as accessible via the partner matching logic.

4. **`_action_confirm` double-loop on `res`:**
   - The method iterates over `self` to find subcontracting moves, then calls `super()._action_confirm()`, then iterates again over `res` to identify which ones ended up with `is_subcontract=True`. The double iteration is necessary because `super()` may merge or transform moves, changing the final set.

5. **`is_subcontract` as non-stored Boolean:**
   - The field is not stored, meaning it is recomputed on every read. For the picking list view (which may read `is_subcontract` for many rows), this could incur repeated computation. However, since the field is a simple check (`is_subcontract = True` set directly in `_action_confirm`), the cost is minimal.

6. **`_bom_subcontract_find` with `parent_of` operator:**
   - Translates to a recursive SQL CTE for the partner hierarchy. Partner hierarchies in typical Odoo setups are shallow (2-3 levels), so the recursive query overhead is minimal.

### Odoo 17 → 18 → 19 Changes

**Odoo 17 → 18:**
- Subcontracting BoMs previously allowed work orders (operations). In Odoo 18, this was formally prohibited via `_check_subcontracting_no_operation`.
- The `subcontracting_has_been_recorded` field (now marked deprecated) was the predecessor to the more precise MO state management.
- The `property_stock_subcontractor` on `res.partner` moved from being a simple field to a company-dependent property with `ir.default` initialization.

**Odoo 18 → 19:**
- The `_subcontracted_produce` method received significant refactoring for the backorder case in multi-level subcontracting ("Magic spicy sauce"). The previous implementation failed to preserve component move reservations when splitting a subcontracted parent MO with a backorder.
- The `stock.reference` record system was introduced to create a proper traceability link between the receipt picking and the subcontracting MO.
- The `_get_subcontract_mo_confirmation_ctx` hook was added to support integration with `mrp_subcontracting_purchase` (enterprise module) for PO-based subcontracting flows where the context behavior differs.
- Portal record rules were significantly expanded to cover more models (`stock.lot`, `product.template`, `stock.picking.type`, `stock.warehouse`, `stock.location`) enabling a richer portal experience.
- The `bom_product_ids` field on `mrp.production` was added to support portal filtering of products in the subcontracting portal view.
- The `incoming_picking` related field and `_rec_names_search` extension were added for improved searchability from MO list views.

### Stock Valuation Impact

- **Finished goods valuation:** When a subcontracting receipt is validated, the finished product is received into stock at the **subcontracting cost** (from `product.supplierinfo` price for the specific subcontractor). The journal entry debits the inventory valuation account and credits the subcontractor payable account.
- **Component stock:** Components consumed by the subcontracting MO reduce stock at the subcontracting location at their own cost (`standard_price`). The value flows through the subcontracting location as an internal transfer.
- **Landed costs:** The `stock_landed_costs` module can add additional costs (freight, handling, duties) to the subcontracted product, updating valuation after receipt.
- **Multi-currency:** Subcontracting costs in foreign currencies are converted using the exchange rate at the receipt date via `_convert` on the currency.

### Edge Cases

1. **No subcontracting BoM found:** If an incoming picking for a subcontracted product has no matching BoM (e.g., the vendor is not in `subcontractor_ids`), the move is created as a regular incoming receipt. No MO is created. This is silent — no error is raised.

2. **Multiple subcontractors on one BoM:** `_bom_subcontract_find` uses `parent_of` matching and returns the first matching BoM by `sequence, product_id, id`. The subcontracting location is resolved from `picking_id.partner_id` — if a generic BoM (no specific subcontractor) is used, the partner's location is still correctly applied.

3. **Negative subcontracting quantity:** If the receipt quantity is decreased to zero or negative after initial confirmation, `_subcontracted_produce` skips MO creation. If an MO was already created and the quantity is later reduced, the `change.production.qty` wizard handles the adjustment.

4. **Portal user without partner location:** If a subcontractor partner does not have `property_stock_subcontractor` set, the company-level `subcontracting_location_id` is used as a fallback in both `_action_confirm` and `_prepare_subcontract_mo_vals`.

5. **Multi-company subcontracting:** The subcontracting location is company-specific. If the same partner is a subcontractor for multiple companies, each company has its own subcontracting location, and picking flows are company-isolated. The `property_stock_subcontractor` is company-dependent.

6. **Unbuild blocked:** `button_unbuild()` raises `UserError` for subcontracting MOs. Unbuild is not supported because it would require returning components to the subcontractor, which is a complex accounting scenario.

7. **MO merge blocked:** `action_merge()` on `mrp.production` raises `ValidationError` for subcontracting MOs — each MO is tied to a specific subcontractor partner and picking.

8. **Multi-level subcontracting (backorder case):** When a subcontracted parent MO with subcontracted components is partially received, the "Magic spicy sauce" code in `_subcontracted_produce` explicitly links the backorder MO to the backorder receipt move via `new_mo.move_finished_ids.move_dest_ids = move`. Without this, traceability breaks.

9. **MO `date_start` pre-dating:** `date_start` is set to `subcontract_move.date - relativedelta(days=bom.produce_delay)`. If the receipt date is set in the past (e.g., backdating a receipt), the MO's `date_start` could also be in the past, potentially creating an inconsistent scheduling state.

10. **`_action_cancel` with portal user:** When cancelling a subcontract receipt move as a portal user, the `_action_cancel` override uses `with_context(skip_activity=True)` and calls `action_cancel()` on the MO. Portal users have write access to `product_qty` but not to `state` directly; the `action_cancel()` method may have its own access check. The `sudo()` is applied to the productions in `_action_done`, but not in `_action_cancel`. This is a potential edge case for portal-only environments.

---

## Related Modules

| Module | Relationship |
|---|---|
| `mrp_subcontracting_purchase` (Enterprise) | Integrates subcontracting with Purchase Orders — subcontracting receipts can be linked to PO lines, with PO-specific `no_procurement` behavior in `_get_subcontract_mo_confirmation_ctx`. |
| `mrp_subcontracting_account` (Enterprise) | Adds analytic accounting, cost computation, and bill-of-materials cost rollup for subcontracting operations. |
| `stock_landed_costs` | Used to add landing costs (freight, handling, duties, insurance) to subcontracted product valuations after receipt. |
| `quality` | Quality checks can be configured on the subcontracting receipt operation type to enforce incoming quality control on subcontracted products. |
| `mrp` | Core dependency — all subcontracting is built on top of the Manufacturing module. |

---

## Data: Module Initialization (`data/mrp_subcontracting_data.xml`)

```xml
<data noupdate="0">
    <!-- Retroactively creates subcontracting locations for existing companies -->
    <function model="res.company" name="_create_missing_subcontracting_location"/>
</data>
<data noupdate="1">
    <!-- Global MTO route for resupplying subcontractors -->
    <record id="route_resupply_subcontractor_mto" model='stock.route'>
        <field name="name">Resupply Subcontractor on Order</field>
        <field name="company_id"></field>  <!-- Global (no company) -->
        <field name="product_selectable" eval="False"/>
        <field name="warehouse_selectable" eval="True"/>
        <field name="warehouse_ids" eval="[(4, ref('stock.warehouse0'))]"/>
    </record>
    <!-- Enable resupply on ALL existing warehouses on module install -->
    <function model="stock.warehouse" name="write">
        <value model="stock.warehouse" eval="obj().env['stock.warehouse'].search([]).ids"/>
        <value eval="{'subcontracting_to_resupply': True}"/>
    </function>
</data>
```

The `noupdate="1"` on the route and warehouse write means these are only applied on initial module install, not on subsequent upgrades. The `_create_missing_subcontracting_location` function runs on every upgrade (noupdate="0"), ensuring new companies get a location.

---

## Tags

#modules #mrp #subcontracting #stock #supply-chain #manufacturing #portal #odoo19
