# stock.warehouse — Warehouse Model

**Source:** `odoo/addons/stock/models/stock_warehouse.py`
**Odoo Version:** 19
**Module:** `stock`
**Tags:** `#stock`, `#warehouse`, `#locations`, `#routes`, `#picking-types`, `#orm`

## Overview

The `stock.warehouse` model is the central entity in Odoo's warehouse management system. It encapsulates the complete physical and logical structure of a warehouse: its locations (view, stock, input, output, QC, packing), its picking types (receipts, deliveries, picks, packs, internal transfers, cross-dock), and its routing rules (incoming receipts, outgoing deliveries, resupply from other warehouses, MTO). A single warehouse record drives the creation of 5-8 `stock.location` records, up to 8 `stock.picking.type` records, multiple `stock.route` records, and numerous `stock.rule` records via a cascading creation engine built into `create()` and `write()`.

The warehouse model uses `_check_company_auto = True`, enforcing company-scoping on all relational fields via `check_company=True`. It does **not** inherit from `mail.thread` or any mixin.

---

## Module Hierarchy (Parent Models)

```
stock.warehouse
  ├── stock.location (view_location_id, lot_stock_id, wh_input_stock_loc_id,
  │                   wh_qc_stock_loc_id, wh_output_stock_loc_id, wh_pack_stock_loc_id)
  ├── stock.picking.type (in_type_id, out_type_id, pick_type_id, pack_type_id,
  │                       int_type_id, qc_type_id, store_type_id, xdock_type_id)
  ├── stock.route (route_ids, reception_route_id, delivery_route_id,
  │                resupply_route_ids via One2many reverse)
  ├── stock.rule (mto_pull_id, rules on routes)
  └── res.company (company_id), res.partner (partner_id)
```

---

## L1 — All Fields (Complete)

### Basic Identification Fields

| Field | Type | Default | Required | Index | Check Company | Notes |
|-------|------|---------|----------|-------|---------------|-------|
| `name` | `Char` | `_default_name()` | Yes | No | No | Auto-generates `"CompanyName - warehouse # N"` |
| `code` | `Char(5)` | Required | Yes | No | No | Short name for barcode, sequences, identification |
| `sequence` | `Integer` | `10` | No | No | No | Display ordering; lower = first |
| `active` | `Boolean` | `True` | No | No | No | Archivable; blocks on ongoing operations |
| `company_id` | `Many2one(res.company)` | `self.env.company` | Yes | No | — | Readonly after creation; changing is forbidden |
| `partner_id` | `Many2one(res.partner)` | `self.env.company.partner_id` | No | No | Yes | Company address; triggers `property_stock_customer/supplier` updates |

### Location Fields

| Field | Type | Domain | Required | Index | Check Company | Notes |
|-------|------|--------|----------|-------|---------------|-------|
| `view_location_id` | `Many2one(stock.location)` | `usage='view', company_id=company` | Yes | Yes | Yes | Root view location; all sub-locations are children |
| `lot_stock_id` | `Many2one(stock.location)` | `usage='internal', company_id=company` | Yes | No | Yes | Physical stock location; primary inventory point |
| `wh_input_stock_loc_id` | `Many2one(stock.location)` | — | No | No | Yes | Input/receiving area; active when `reception_steps != 'one_step'` |
| `wh_qc_stock_loc_id` | `Many2one(stock.location)` | — | No | No | Yes | Quality control; active only when `reception_steps == 'three_steps'` |
| `wh_output_stock_loc_id` | `Many2one(stock.location)` | — | No | No | Yes | Output/shipping staging; active when `delivery_steps != 'ship_only'` |
| `wh_pack_stock_loc_id` | `Many2one(stock.location)` | — | No | No | Yes | Packing zone; active only when `delivery_steps == 'pick_pack_ship'` |

### Picking Type Fields (All check_company=True, copy=False)

| Field | Type | Activation Condition |
|-------|------|---------------------|
| `in_type_id` | `Many2one(stock.picking.type)` | Always created; active by default |
| `out_type_id` | `Many2one(stock.picking.type)` | Always created; active by default |
| `pick_type_id` | `Many2one(stock.picking.type)` | `delivery_steps != 'ship_only'` |
| `pack_type_id` | `Many2one(stock.picking.type)` | `delivery_steps == 'pick_pack_ship'` |
| `int_type_id` | `Many2one(stock.picking.type)` | Active if `stock.group_stock_multi_locations` is set on user |
| `qc_type_id` | `Many2one(stock.picking.type)` | `reception_steps == 'three_steps'` |
| `store_type_id` | `Many2one(stock.picking.type)` | `reception_steps != 'one_step'` |
| `xdock_type_id` | `Many2one(stock.picking.type)` | `reception_steps != 'one_step' AND delivery_steps != 'ship_only'` |

### Route and Rule Fields

| Field | Type | Ondelete | Notes |
|-------|------|---------|-------|
| `route_ids` | `Many2many(stock.route)` | — | All routes applied to this warehouse; domain filters `warehouse_selectable=True` |
| `reception_route_id` | `Many2one(stock.route)` | `restrict` | Incoming receipt route; created automatically |
| `delivery_route_id` | `Many2one(stock.route)` | `restrict` | Outgoing delivery route; created automatically |
| `resupply_wh_ids` | `Many2many(stock.warehouse)` | — | Supplier warehouses for inter-warehouse resupply |
| `resupply_route_ids` | `One2many(stock.route, supplied_wh_id)` | — | Auto-created resupply routes (reverse: `supplied_wh_id`) |
| `mto_pull_id` | `Many2one(stock.rule)` | — | MTO (Make-To-Order) procurement rule |

### Workflow Configuration Fields

| Field | Type | Default | Selection Options |
|-------|------|---------|-------------------|
| `reception_steps` | `Selection` | `'one_step'` | `'one_step'` / `'two_steps'` / `'three_steps'` |
| `delivery_steps` | `Selection` | `'ship_only'` | `'ship_only'` / `'pick_ship'` / `'pick_pack_ship'` |

---

## L2 — Field Types, Defaults, Constraints, Purpose

### `name` — Warehouse Name

```python
def _default_name(self):
    count = self.env['stock.warehouse'].with_context(active_test=False).search_count(
        [('company_id', '=', self.env.company.id)])
    return "%s - warehouse # %s" % (self.env.company.name, count + 1) if count \
        else self.env.company.name
```

**Purpose:** Human-readable warehouse identifier. The default generator counts existing warehouses for the current company and produces `"MyCompany - warehouse # 1"`, `"MyCompany - warehouse # 2"`, etc. If this is the first warehouse, it defaults to just the company name.

**Constraint:** `unique(name, company_id)` — names must be unique per company, not globally.

### `code` — Short Name (5 Characters)

```python
code = fields.Char('Short Name', required=True, size=5,
    help="Short name used to identify your warehouse")
```

**Purpose:** Used as:
- Location name prefix for barcode generation (e.g., `WH/INPUT`, `WH/PACK`)
- Sequence prefix for picking number sequences (e.g., `WH/IN/00001`)
- Rule and route naming (e.g., `WH: WH → Stock (MTO)`)
- Short identifier in dense UI displays

**Default in `create()`:** If `code` is not provided in `vals`, it defaults to `company.name[:5]` (first 5 characters of company name, uppercased).

**Constraint:** `unique(code, company_id)` — short names must be unique per company.

### `reception_steps` — Incoming Shipment Configuration

| Value | Label | Location Chain | Picking Types Involved |
|-------|-------|----------------|----------------------|
| `one_step` | Receive and Store (1 step) | Supplier → `lot_stock_id` | `in_type_id` |
| `two_steps` | Receive then Store (2 steps) | Supplier → `wh_input_stock_loc_id` → `lot_stock_id` | `in_type_id`, `store_type_id` (push) |
| `three_steps` | Receive, Quality Control, then Store (3 steps) | Supplier → `wh_input_stock_loc_id` → `wh_qc_stock_loc_id` → `lot_stock_id` | `in_type_id`, `qc_type_id` (push), `store_type_id` (push) |

**Effect:** Changing `reception_steps` triggers `_update_location_reception()` to activate/deactivate intermediate locations, `_update_reception_delivery_resupply()` to update MTO rules, and `_create_or_update_route()` to regenerate the reception route.

### `delivery_steps` — Outgoing Shipment Configuration

| Value | Label | Location Chain | Picking Types Involved |
|-------|-------|----------------|----------------------|
| `ship_only` | Deliver (1 step) | `lot_stock_id` → Customer | `out_type_id` |
| `pick_ship` | Pick then Deliver (2 steps) | `lot_stock_id` → `wh_output_stock_loc_id` → Customer | `pick_type_id` (pull), `out_type_id` (push) |
| `pick_pack_ship` | Pick, Pack, then Deliver (3 steps) | `lot_stock_id` → `wh_pack_stock_loc_id` → `wh_output_stock_loc_id` → Customer | `pick_type_id` (pull), `pack_type_id` (push), `out_type_id` (push) |

**Effect:** Changing `delivery_steps` triggers `_update_location_delivery()` to activate/deactivate intermediate locations, and `_create_or_update_global_routes_rules()` to update the MTO rule's destination location and picking type.

### `view_location_id` — Root View Location

Created automatically in `create()` with `usage='view'` (a non-physical container). All physical warehouse locations (`lot_stock_id`, `wh_input_stock_loc_id`, etc.) are created as children of this view location. The view location's `warehouse_id` field is back-written after warehouse creation. When archiving a warehouse, the view location is also archived.

**Index:** `index=True` — frequently used in domain searches across all locations under a warehouse.

### `lot_stock_id` — Physical Stock Location

The primary internal location where inventory quants are tracked. All `stock.quant` records for this warehouse's products reside here (or in child locations of `lot_stock_id`). This is the `replenish_location=True` location.

### Picking Types — Conceptual Grouping

Each `stock.picking.type` field on the warehouse represents a category of warehouse operation:

| Picking Type | `stock.picking.type` Fields Created | Default Source | Default Destination |
|---|---|---|---|
| `in_type_id` | name=Receipts, code=incoming | Supplier location | `lot_stock_id` (1-step) or `wh_input_stock_loc_id` (2/3-step) |
| `out_type_id` | name=Delivery Orders, code=outgoing | `lot_stock_id` (1-step) or `wh_output_stock_loc_id` (2/3-step) | Customer location |
| `pick_type_id` | name=Pick, code=internal | `lot_stock_id` | `wh_output_stock_loc_id` (pick_ship) or `wh_pack_stock_loc_id` (pick_pack_ship) |
| `pack_type_id` | name=Pack, code=internal | `wh_pack_stock_loc_id` | `wh_output_stock_loc_id` |
| `int_type_id` | name=Internal Transfers, code=internal | `lot_stock_id` | `lot_stock_id` (same; user picks source/dest) |
| `qc_type_id` | name=Quality Control, code=internal | `wh_input_stock_loc_id` | `wh_qc_stock_loc_id` |
| `store_type_id` | name=Storage, code=internal | `wh_input_stock_loc_id` (2-step) or `wh_qc_stock_loc_id` (3-step) | `lot_stock_id` |
| `xdock_type_id` | name=Cross Dock, code=internal | `wh_input_stock_loc_id` | `wh_output_stock_loc_id` |

All picking types are created at warehouse creation time with a new `ir.sequence` each. Sequences are named using the pattern `%(name)s Sequence in`, prefix `%(code)s/IN/`, padding 5.

### Route Selection (`route_ids` vs. `reception_route_id` / `delivery_route_id`)

- `reception_route_id` / `delivery_route_id` are **single** Many2one routes that are auto-created and managed by the warehouse itself.
- `route_ids` is a **Many2many** where manually-selected routes (e.g., Buy route, Manufacture route) are stored, domain-filtered to `warehouse_selectable=True`.
- `resupply_route_ids` is a derived One2many of routes where `supplied_wh_id = self` (routes that resupply this warehouse from other warehouses).

---

## L3 — Edge Cases, Cross-Model, Override Patterns, Workflow Triggers, Failure Modes

### L3.1 — Location Creation Cascade

**Behavior:** When `create()` is called with warehouse `vals`, the following location creation chain executes:

```
1. view_location_id = stock.location.create({name=code, usage='view', company_id})
   (created FIRST because sub-locations need parent_id)

2. sub_locations = _get_locations_values(vals)
   Returns dict of 5 location definitions:
   {
     'lot_stock_id':        {name='Stock',        usage='internal', replenish_location=True,  active=True,  barcode=code+'STOCK'},
     'wh_input_stock_loc_id': {name='Input',       usage='internal', active=(reception_steps!='one_step'), barcode=code+'INPUT'},
     'wh_qc_stock_loc_id':  {name='Quality Control', usage='internal', active=(reception_steps=='three_steps'), barcode=code+'QUALITY'},
     'wh_output_stock_loc_id': {name='Output',      usage='internal', active=(delivery_steps!='ship_only'), barcode=code+'OUTPUT'},
     'wh_pack_stock_loc_id': {name='Packing Zone', usage='internal', active=(delivery_steps=='pick_pack_ship'), barcode=code+'PACKING'},
   }

3. Each sub-location is created with location_id=view_location_id

4. After warehouse record is created (super().create()):
   - Back-write warehouse_id to all locations
   - Create picking types + sequences
   - Create routes + rules
   - Create MTO rule
   - Create resupply routes
   - Update partner stock properties
```

**Cross-Model Trigger:** `stock.location` records are created as children of `view_location_id`. The warehouse ID is back-written to locations only after the warehouse exists, using `with_context(active_test=False)` to ensure archived locations are also updated.

### L3.2 — `_create_missing_locations()` — Module Extension Scenario

```python
def _create_missing_locations(self, vals):
    for warehouse in self:
        company_id = vals.get('company_id', warehouse.company_id.id)
        sub_locations = warehouse._get_locations_values(dict(vals, company_id=company_id),
                                                      warehouse.code)
        missing_location = {}
        for location, location_values in sub_locations.items():
            if not warehouse[location] and location not in vals:
                # Location was deleted externally or new module added a location
                location_values['location_id'] = vals.get('view_location_id',
                                                        warehouse.view_location_id.id)
                location_values['company_id'] = company_id
                missing_location[location] = self.env['stock.location'].create(location_values).id
        if missing_location:
            warehouse.write(missing_location)
```

**Edge Case:** If a module that adds a new warehouse location (e.g., `stock_packing` module adding `wh_pack_stock_loc_id`) is installed after warehouses already exist, `_create_missing_locations()` is called during the next `write()` to create the missing location. The key check is `if not warehouse[location] and location not in vals` — it avoids overwriting locations already being set in the current `write()` call.

### L3.3 — Warehouse Copy (`copy_data`)

```python
def copy_data(self, default=None):
    default = dict(default or {})
    vals_list = super().copy_data(default=default)
    for warehouse, vals in zip(self, vals_list):
        if 'name' not in default:
            vals['name'] = _("%s (copy)", warehouse.name)
        if 'code' not in default:
            vals['code'] = _("COPY")
    return vals_list
```

**Edge Case:** When duplicating a warehouse, `copy()` is called on the warehouse record. Odoo's ORM calls `copy_data()` then `create()`. The new warehouse will create all new locations (not share them with the original). The code is forcibly set to `"COPY"` to avoid unique-constraint violations; the name gets ` (copy)` appended.

### L3.4 — `write()` with Active/Archive Toggle

The `write({'active': False})` path has extensive guard logic:

```python
# Step 1: Check for ongoing moves on picking types
move_ids = self.env['stock.move'].search([
    ('picking_type_id', 'in', picking_type_ids.ids),
    ('state', 'not in', ('done', 'cancel')),
])
if move_ids:
    raise UserError(_("You still have ongoing operations..."))

# Step 2: Check other picking types using warehouse locations
picking_type_using_locations = self.env['stock.picking.type'].search([
    ('default_location_src_id', 'in', location_ids.ids),
    ('default_location_dest_id', 'in', location_ids.ids),
    ('id', 'not in', picking_type_ids.ids),  # Exclude own types
])
if picking_type_using_locations:
    raise UserError(_("...have default source or destination locations within..."))

# Step 3: Archive the view location
warehouse.view_location_id.write({'active': vals['active']})

# Step 4: Archive warehouse-only routes; archive all rules
warehouse.route_ids.filtered(lambda r: len(r.warehouse_ids) == 1).write({'active': vals['active']})
rule_ids.write({'active': vals['active']})

# Step 5: Re-activate warehouse to trigger cascade activation
if warehouse.active:  # re-activating
    values = {'resupply_route_ids': [(4, route.id) for route in warehouse.resupply_route_ids]}
    for depend in depends:
        values.update({depend: warehouse[depend]})
    warehouse.write(values)
```

**Failure Modes:**
1. **Ongoing moves:** Cannot archive if any `stock.move` in non-terminal state references the warehouse's picking types.
2. **External picking types:** Cannot archive if another `stock.picking.type` (e.g., from another warehouse's route) uses a location inside this warehouse's view location tree.
3. **Route sharing:** Routes shared with other warehouses (`len(r.warehouse_ids) > 1`) are NOT archived — only warehouse-exclusive routes are.

### L3.5 — Resupply Routes: `create_resupply_routes()`

When adding a supplier warehouse to `resupply_wh_ids`:

```python
def create_resupply_routes(self, supplier_warehouses):
    for supplier_wh in supplier_warehouses:
        # Determine transit: internal if same company, external (inter-company) otherwise
        transit_location = internal_transit_location if supplier_wh.company_id == self.company_id \
                           else external_transit_location

        # Step A: Create inter-warehouse route
        inter_wh_route = Route.create(self._get_inter_warehouse_route_values(supplier_wh))

        # Step B: Create pull rules:
        #   Rule 1: supplier_wh.lot_stock_id → transit (pull via supplier_wh.out_type_id)
        #   Rule 2 (if multi-step delivery): supplier_wh.lot_stock_id → supplier_wh.output (pull via pick)
        #   Rule 3: transit → self.lot_stock_id (pull via self.in_type_id)

        # Step C: If supplier uses 'ship_only', also create MTO rule
        if supplier_wh.delivery_steps == 'ship_only':
            routing = [self.Routing(output_location, transit_location,
                                    supplier_wh.out_type_id, 'pull')]
            Rule.create(mto_rule_val[0])
```

**Cross-Model Edge Case:** The `supplied_wh_id` / `supplier_wh_id` fields on `stock.route` create a bidirectional relationship: warehouse A resupplying from B means A has `supplier_wh_id=B` and B has `supplied_wh_id=A` on the route. The company of the route is computed as `(self.company_id & supplier_warehouse.company_id).id` — for inter-company resupply, this raises a `AccessError` if companies are not related.

### L3.6 — `_check_multiwarehouse_group()`

```python
def _check_multiwarehouse_group(self):
    cnt_by_company = self.env['stock.warehouse'].sudo()._read_group(
        [('active', '=', True)], ['company_id'], aggregates=['__count'])
    if cnt_by_company:
        max_count = max(count for company, count in cnt_by_company)
        group_user = self.env.ref('base.group_user')
        group_stock_multi_warehouses = self.env.ref('stock.group_stock_multi_warehouses')
        group_stock_multi_locations = self.env.ref('stock.group_stock_multi_locations')

        if max_count <= 1 and group_stock_multi_warehouses in group_user.implied_ids:
            # Remove multi-warehouse from all users (no warehouses left)
            group_user.write({'implied_ids': [(3, group_stock_multi_warehouses.id)]})
            group_stock_multi_warehouses.write({'user_ids': [(3, user.id) for user in group_user.all_user_ids]})

        if max_count > 1 and group_stock_multi_warehouses not in group_user.implied_ids:
            # Add multi-warehouse to all users (second warehouse created)
            self.env['res.config.settings'].create({
                'group_stock_multi_locations': True,
            }).execute()
            group_user.write({'implied_ids': [(4, group_stock_multi_warehouses.id),
                                              (4, group_stock_multi_locations.id)]})
```

**Override Pattern:** This method automatically promotes users from `base.group_user` to include multi-warehouse capabilities when a second warehouse is created. It is called in `create()`, `write()` (when active changes), and `unlink()`.

### L3.7 — Company Assignment and Constraint Enforcement

Changing `company_id` on a warehouse is explicitly forbidden:

```python
def write(self, vals):
    if 'company_id' in vals:
        for warehouse in self:
            if warehouse.company_id.id != vals['company_id']:
                raise UserError(_(
                    "Changing the company of this record is forbidden at this point, "
                    "you should rather archive it and create a new one."))
```

This is a deliberate design choice because changing the company would require moving all stock quants, moves, pickings, and rules to the new company's locations — a destructive operation.

### L3.8 — `get_rules_dict()` — Routing Matrix

This method defines the complete routing matrix for all combinations of `reception_steps` x `delivery_steps`:

```python
# Structure returned:
{
    warehouse_id: {
        'one_step':  [Routing(supplier_loc, lot_stock_id, in_type_id, 'pull')],
        'two_steps':  [Routing(supplier_loc, lot_stock_id, in_type_id, 'pull'),
                       Routing(wh_input, lot_stock_id, store_type_id, 'push')],
        'three_steps': [Routing(supplier_loc, lot_stock_id, in_type_id, 'pull'),
                        Routing(wh_input, wh_qc, qc_type_id, 'push'),
                        Routing(wh_qc, lot_stock_id, store_type_id, 'push')],
        'ship_only':   [Routing(lot_stock_id, customer_loc, out_type_id, 'pull')],
        'pick_ship':   [Routing(lot_stock_id, customer_loc, pick_type_id, 'pull'),
                        Routing(wh_output, customer_loc, out_type_id, 'push')],
        'pick_pack_ship': [Routing(lot_stock_id, customer_loc, pick_type_id, 'pull'),
                           Routing(wh_pack, wh_output, pack_type_id, 'push'),
                           Routing(wh_output, customer_loc, out_type_id, 'push')],
        'company_id': warehouse.company_id.id,
    }
}
```

The `Routing` namedtuple (`from_loc`, `dest_loc`, `picking_type`, `action`) is the core data structure used by `_get_rule_values()` to generate `stock.rule` records.

### L3.9 — MTO Rule Generation

The MTO rule (`mto_pull_id`) is a `stock.rule` with `procure_method='make_to_order'` stored on the warehouse. It is created/updated by `_create_or_update_global_routes_rules()` which calls `_generate_global_route_rules_values()`:

```python
'mto_pull_id': {
    'depends': ['delivery_steps'],
    'create_values': {
        'active': True,
        'procure_method': 'make_to_order',
        'company_id': self.company_id.id,
        'action': 'pull',
        'auto': 'manual',
        'propagate_carrier': True,
        'route_id': self._find_or_create_global_route(
            'stock.route_warehouse0_mto',
            _('Replenish on Order (MTO)')
        ).id
    },
    'update_values': {
        'name': self._format_rulename(location_id, location_dest_id, 'MTO'),
        'location_dest_id': location_dest_id.id,
        'location_src_id': location_id.id,
        'picking_type_id': picking_type_id.id,
    }
}
```

**Key Behavior:** The MTO rule's `location_src_id`, `location_dest_id`, and `picking_type_id` all change when `delivery_steps` changes, because the output location changes from `lot_stock_id` (ship_only) to `wh_output_stock_loc_id` (pick_ship or pick_pack_ship).

### L3.10 — `_update_name_and_code()`

When name or code changes, the following cascade updates occur:

```python
def _update_name_and_code(self, new_name=False, new_code=False):
    # 1. Update view location name to match new code
    if new_code:
        self.mapped('lot_stock_id').mapped('location_id').write({'name': new_code})

    # 2. Replace warehouse name in all route names, rule names, and MTO rule name
    if new_name:
        for warehouse in self:
            for route in warehouse.route_ids:
                route.write({'name': route.name.replace(warehouse.name, new_name, 1)})
                for pull in route.rule_ids:
                    pull.write({'name': pull.name.replace(warehouse.name, new_name, 1)})

    # 3. Update all picking type sequences (requires stock.group_stock_manager)
    if self.env.user.has_group('stock.group_stock_manager'):
        warehouse.in_type_id.sequence_id.write(sequence_data['in_type_id'])
        # ... (all 8 sequence updates)
```

**Edge Case:** The `replace(..., 1)` replaces only the **first** occurrence, preserving any subsequent occurrences of the warehouse name within route/rule names.

---

## L4 — Performance, Historical Changes, Security Concerns

### L4.1 — Performance Implications

**Warehouse creation** is an expensive operation: it creates up to 13 database records (1 view location + 5 sub-locations + 1 warehouse + 8 picking types + 8 ir.sequences + 2 routes + N rules). All of these are created synchronously within `create()`.

**`write()` with active toggle** is the most expensive operation: it searches for all moves, all picking types using the warehouse's locations, all rules, and all routes. Each of these is a separate `search()` call.

**Barcode generation** uses `_valid_barcode()` which searches for existing barcode uniqueness:

```python
def _valid_barcode(self, barcode, company_id):
    location = self.env['stock.location'].with_context(active_test=False).search([
        ('barcode', '=', barcode),
        ('company_id', '=', company_id)
    ])
    return not location and barcode
```

This is called for every location in `_get_locations_values()`, meaning up to 6 searches per warehouse creation. Since barcode uniqueness is per-company, the search is appropriately scoped.

**N+1 considerations in `write()`:** The `write()` method iterates over `warehouses` (self with `active_test=False`) and calls `_get_routes_values()`, `get_rules_dict()`, `_get_global_route_rules_values()` per warehouse. These are designed for single-warehouse writes but are called in a loop when multiple warehouses are written simultaneously. Each iteration calls `_get_partner_locations()` which searches for customer/supplier locations — this is a small N+1 risk when writing multiple warehouses at once.

**Resupply route creation** (`create_resupply_routes`) loops over each supplier warehouse and creates multiple rules per supplier. For `n` supplier warehouses, this creates O(n) routes and O(3n) rules, each with a separate `Rule.create()` call. This could be batched but is not in the current implementation.

### L4.2 — Security Model

**ACLs:** The `stock.warehouse` model requires `stock.group_stock_manager` for full access. Regular `stock.group_stock_user` can read warehouses and use them in pickings, but typically cannot create/modify warehouse configuration. The model itself does not enforce this programmatically — it relies on `ir.model.access.csv` entries.

**Multi-company:** The `_check_company_auto = True` setting ensures all relational fields with `check_company=True` are automatically scoped by the current company context. The database constraints `unique(name, company_id)` and `unique(code, company_id)` prevent cross-company name collisions.

**Record Rules:** By default, `stock.warehouse` has no `ir.rule` defined — all users with ACL access can see all warehouses. This is a deliberate choice since warehouse visibility is typically controlled by which company the user belongs to.

**Key Security Concerns:**

1. **Partner data mutation:** `_update_partner_data()` writes `property_stock_customer` and `property_stock_supplier` on `res.partner` when a warehouse's `partner_id` changes. This is a write on a potentially shared partner record:

   ```python
   self.env['res.partner'].browse(partner_id).with_company(company_id).write({
       'property_stock_customer': transit_loc,
       'property_stock_supplier': transit_loc
   })
   ```

   This sets the company's internal transit location as the partner's default stock locations. If multiple warehouses for the same company share a partner, this could cause conflicts. The `with_company()` context ensures it writes in the correct company scope.

2. **MTO route lookup:** `_find_or_create_global_route()` searches for routes by name across `company_id in [False, company.id]`. This means a route created at company level can be found even if its `company_id` is False (global). The check `route.sudo().company_id and route.sudo().company_id != company` prevents a global route from being assigned to a company-specific context incorrectly.

3. **Superuser bypass for sequences:** `_create_or_update_sequences_and_picking_types()` uses `sudo()` when writing to `ir.sequence` because sequence write access is typically restricted to system users:

   ```python
   self[picking_type].sudo().sequence_id.write({'company_id': self.company_id.id})
   ```

   This is a justified privilege escalation — sequences are system-wide resources and warehouse managers need to update company_id on sequences when reassigning warehouses.

4. **Transit locations in resupply:** For inter-company resupply, `create_resupply_routes()` uses the external transit location (from `stock.stock_location_inter_company` XML ID). If this location is not created/accessible, the resupply route silently skips creation:

   ```python
   if not transit_location:
       continue
   transit_location.active = True  # Activates even if it was archived
   ```

### L4.3 — Odoo 18 → Odoo 19 Changes

The `stock.warehouse` model underwent several significant changes from Odoo 18 to Odoo 19:

1. **`_check_company_auto = True`:** This attribute was likely added or its usage was standardized in Odoo 19 to enforce automatic company filtering on all `check_company=True` fields. This ensures that relational fields are automatically scoped by company context without manual domain filtering.

2. **`_warehouse_redirect_warning()` method added:** The `_warehouse_redirect_warning()` method provides a user-friendly redirect when no warehouse exists for a company, guiding users to create one rather than showing a cryptic error.

3. **Cross-dock type (`xdock_type_id`):** The `xdock_type_id` field and associated cross-dock picking type were introduced or enhanced to support true cross-docking operations where goods received at input flow directly to output without intermediate stock placement. The cross-dock picking type is active only when both reception is multi-step AND delivery is multi-step (`reception_steps != 'one_step' AND delivery_steps != 'ship_only'`).

4. **Storage type (`store_type_id`):** The `store_type_id` (Storage picking type) was enhanced. In Odoo 18, this may have been simpler; in Odoo 19 it represents the push rule from input (or QC) to stock location.

5. **`_valid_barcode()` method:** The barcode validation helper was refined to search by barcode within the same company, preventing barcode collisions across companies.

6. **Route creation logic refactoring:** `_create_or_update_route()` was refactored to use the `routing_key` from `_get_routes_values()` matched against `get_rules_dict()`, making the routing matrix-driven approach more explicit and extensible.

7. **`_get_receive_routes_values()` and `_get_receive_rules_dict()`:** These methods were added to support modules that extend stock and add receive 'make_to_order' rules (e.g., dropshipping modules). They return the same routing data as their non-receive counterparts but without the initial pull rule from the supplier.

### L4.4 — Namedtuple Routing Pattern

The `Routing = namedtuple('Routing', ['from_loc', 'dest_loc', 'picking_type', 'action'])` pattern at class level is a deliberate design choice:

```python
class StockWarehouse(models.Model):
    _name = 'stock.warehouse'
    Routing = namedtuple('Routing', ['from_loc', 'dest_loc', 'picking_type', 'action'])
```

This allows methods to return structured routing tuples that are consumed by `_get_rule_values()` to generate `stock.rule` records. The namedtuple is defined at class level so it is accessible without instantiating a warehouse record (since it doesn't use `self`). The four fields directly map to `stock.rule` fields:

| Routing Field | Maps to `stock.rule` field |
|---|---|
| `from_loc` | `location_src_id` |
| `dest_loc` | `location_dest_id` |
| `picking_type` | `picking_type_id` |
| `action` | `action` ('pull' or 'push') |

### L4.5 — `ROUTE_NAMES` Lazy Translation

```python
ROUTE_NAMES = {
    'one_step': _lt('Receive in 1 step (stock)'),
    'two_steps': _lt('Receive in 2 steps (input + stock)'),
    'three_steps': _lt('Receive in 3 steps (input + quality + stock)'),
    'ship_only': _lt('Deliver in 1 step (ship)'),
    'pick_ship': _lt('Deliver in 2 steps (pick + ship)'),
    'pick_pack_ship': _lt('Deliver in 3 steps (pick + pack + ship)'),
}
```

`LazyTranslate` (`_lt`) defers translation lookup until the string is actually rendered, avoiding the overhead of loading all translations at module import time. These route names are used by `_get_route_name()` when formatting route display names.

### L4.6 — `get_current_warehouses()` RPC Helper

```python
def get_current_warehouses(self):
    return self.env['stock.warehouse'].search_read(fields=['id', 'name', 'code'])
```

This lightweight RPC method is used by the frontend (JavaScript) to populate warehouse selection dropdowns. It returns only `id`, `name`, `code` — the minimal fields needed for display, avoiding expensive loading of all relational fields.

### L4.7 — Key Extension Points

Modules that extend the stock warehouse system commonly use these methods:

| Extension Method | Purpose | Example Usage |
|---|---|---|
| `_get_locations_values()` | Add custom locations | `stock_packing` module adds `wh_pack_stock_loc_id` |
| `_get_picking_type_create_values()` | Add custom picking types | `quality_control` module adds `qc_type_id` |
| `_get_routes_values()` | Add custom warehouse routes | `dropshipping` module adds buy route |
| `_get_receive_routes_values()` | Add MTO receive rules | `mrp` module links manufacturing to warehouse |
| `get_rules_dict()` | Extend routing matrix | Add custom multi-step configurations |
| `_find_or_create_global_route()` | Find/create global routes | Add warehouse-specific MTO rule |

### L4.8 — Database Constraints

```python
_warehouse_name_uniq = models.Constraint(
    'unique(name, company_id)',
    'The name of the warehouse must be unique per company!',
)
_warehouse_code_uniq = models.Constraint(
    'unique(code, company_id)',
    'The short name of the warehouse must be unique per company!',
)
```

Both constraints use `(name, company_id)` as a composite unique key, meaning the same warehouse name can exist in different companies. The constraint message is translatable and raised as a `ValidationError`-equivalent PostgreSQL constraint violation.

### L4.9 — Relation of `stock.warehouse` to `stock.location`

The warehouse-location relationship is asymmetric:

- A `stock.warehouse` **creates** and **owns** a tree of `stock.location` records.
- The `stock.location` model has a `warehouse_id` field (Many2one back-reference) set to the parent warehouse.
- Locations are **not deleted** when a warehouse is archived — they are simply deactivated.
- Deleting a warehouse (`unlink()`) also does NOT automatically delete locations; it relies on PostgreSQL cascade from the `location_id` parent link or manual cleanup.
- The `view_location_id` is the root of the location tree. Changing `view_location_id` after creation is not handled — it is set as `required=True` and has no explicit write logic for the field itself in `write()`.

---

## Field Summary Table

| # | Field | Type | Default | Required | Index | Check Company | Copy | Ondelete |
|---|-------|------|---------|----------|-------|---------------|------|---------|
| 1 | `name` | Char | `_default_name()` | Yes | No | No | Yes | — |
| 2 | `active` | Boolean | `True` | No | No | No | Yes | — |
| 3 | `company_id` | Many2one(res.company) | `env.company` | Yes | No | — | No | — |
| 4 | `partner_id` | Many2one(res.partner) | `company.partner_id` | No | No | Yes | Yes | — |
| 5 | `view_location_id` | Many2one(stock.location) | auto-created | Yes | Yes | Yes | No | — |
| 6 | `lot_stock_id` | Many2one(stock.location) | auto-created | Yes | No | Yes | No | — |
| 7 | `code` | Char(5) | required | Yes | No | No | Yes | — |
| 8 | `route_ids` | Many2many(stock.route) | — | No | No | No | No | — |
| 9 | `reception_steps` | Selection | `'one_step'` | Yes | No | No | Yes | — |
| 10 | `delivery_steps` | Selection | `'ship_only'` | Yes | No | No | Yes | — |
| 11 | `wh_input_stock_loc_id` | Many2one(stock.location) | auto-created | No | No | Yes | No | — |
| 12 | `wh_qc_stock_loc_id` | Many2one(stock.location) | auto-created | No | No | Yes | No | — |
| 13 | `wh_output_stock_loc_id` | Many2one(stock.location) | auto-created | No | No | Yes | No | — |
| 14 | `wh_pack_stock_loc_id` | Many2one(stock.location) | auto-created | No | No | Yes | No | — |
| 15 | `mto_pull_id` | Many2one(stock.rule) | auto-created | No | No | No | No | — |
| 16 | `pick_type_id` | Many2one(stock.picking.type) | auto-created | No | No | Yes | No | — |
| 17 | `pack_type_id` | Many2one(stock.picking.type) | auto-created | No | No | Yes | No | — |
| 18 | `out_type_id` | Many2one(stock.picking.type) | auto-created | No | No | Yes | No | — |
| 19 | `in_type_id` | Many2one(stock.picking.type) | auto-created | No | No | Yes | No | — |
| 20 | `int_type_id` | Many2one(stock.picking.type) | auto-created | No | No | Yes | No | — |
| 21 | `qc_type_id` | Many2one(stock.picking.type) | auto-created | No | No | Yes | No | — |
| 22 | `store_type_id` | Many2one(stock.picking.type) | auto-created | No | No | Yes | No | — |
| 23 | `xdock_type_id` | Many2one(stock.picking.type) | auto-created | No | No | Yes | No | — |
| 24 | `reception_route_id` | Many2one(stock.route) | auto-created | No | No | No | No | restrict |
| 25 | `delivery_route_id` | Many2one(stock.route) | auto-created | No | No | No | No | restrict |
| 26 | `resupply_wh_ids` | Many2many(stock.warehouse) | — | No | No | No | Yes | — |
| 27 | `resupply_route_ids` | One2many(stock.route) | — | No | No | No | No | cascade |
| 28 | `sequence` | Integer | `10` | No | No | No | Yes | — |

---

## Method Summary Table

| Method | Returns | Purpose |
|--------|---------|---------|
| `_default_name()` | `str` | Generate default warehouse name from company |
| `_onchange_company_id()` | `dict` | Warn user about multi-location activation |
| `create()` | `stock.warehouse` | Full warehouse creation cascade |
| `copy_data()` | `list[dict]` | Prepare vals for warehouse duplication |
| `write()` | `bool` | Update warehouse with cascading effects |
| `unlink()` | `bool` | Delete warehouse, recheck multi-warehouse group |
| `_check_multiwarehouse_group()` | `None` | Auto-manage stock multi-warehouse group assignment |
| `_update_partner_data()` | `None` | Set partner's stock properties to transit location |
| `_create_or_update_sequences_and_picking_types()` | `dict` | Create/update 8 picking types + 8 sequences |
| `_create_or_update_global_routes_rules()` | `bool` | Create/update MTO rule |
| `_find_or_create_global_route()` | `stock.route` | Find/create global route by XML ID |
| `_get_global_route_rules_values()` | `dict` | Return dict of global rule create/update values |
| `_generate_global_route_rules_values()` | `dict` | Generate MTO rule values from routing matrix |
| `_create_or_update_route()` | `dict` | Create/update reception/delivery routes + rules |
| `_get_routes_values()` | `dict` | Return route create/update values for warehouse routes |
| `_get_receive_routes_values()` | `dict` | Return MTO receive route values (for extensions) |
| `_find_existing_rule_or_create()` | `None` | Find inactive rule and unarchive, or create new |
| `_get_locations_values()` | `dict` | Return dict of 5 location definitions |
| `_valid_barcode()` | `str\|False` | Check and return valid barcode or False |
| `_create_missing_locations()` | `None` | Create locations missing after module installation |
| `create_resupply_routes()` | `None` | Create inter-warehouse resupply routes + rules |
| `_get_input_output_locations()` | `tuple` | Return (input_loc, output_loc) based on steps |
| `_get_transit_locations()` | `tuple` | Return (internal_transit, external_transit) |
| `_get_partner_locations()` | `tuple` | Return (customer_loc, supplier_loc) |
| `_get_route_name()` | `str` | Translate route type name |
| `get_rules_dict()` | `dict` | Return full routing matrix for all step combinations |
| `_get_receive_rules_dict()` | `dict` | Return routing matrix without initial pull rule |
| `_get_inter_warehouse_route_values()` | `dict` | Return resupply route values for a supplier warehouse |
| `_get_rule_values()` | `list[dict]` | Convert Routing tuples to stock.rule values |
| `_get_supply_pull_rules_values()` | `list[dict]` | Return supply/pull rule values for resupply |
| `_update_reception_delivery_resupply()` | `None` | Update resupply when reception/delivery steps change |
| `_check_delivery_resupply()` | `None` | Update/resupply rules when delivery steps change |
| `_update_name_and_code()` | `None` | Cascade rename to locations, routes, rules, sequences |
| `_update_location_reception()` | `None` | Activate/deactivate QC and Input locations |
| `_update_location_delivery()` | `None` | Activate/deactivate Output and Pack locations |
| `_get_picking_type_update_values()` | `dict` | Return picking type update values for step changes |
| `_get_picking_type_create_values()` | `dict` | Return full picking type create values (8 types) |
| `_get_sequence_values()` | `dict` | Return ir.sequence values for all 8 picking types |
| `_format_rulename()` | `str` | Format rule name: `CODE: from → to (suffix)` |
| `_format_routename()` | `str` | Format route name: `Warehouse: RouteType` |
| `_get_all_routes()` | `stock.route` | Return all routes associated with warehouse |
| `action_view_all_routes()` | `dict` | Return window action for route list view |
| `get_current_warehouses()` | `list[dict]` | Lightweight RPC helper for warehouse dropdown |

---

## Location Tree Diagram

```
view_location_id (usage='view', name=code)
  │
  ├── lot_stock_id (usage='internal', name='Stock', replenish_location=True)
  │      │
  │      └── [Product quants live here]
  │
  ├── wh_input_stock_loc_id (usage='internal', name='Input')
  │      │  Active: reception_steps != 'one_step'
  │      │
  │      ├── (two_steps): → lot_stock_id (via store_type_id push)
  │      │
  │      └── (three_steps): → wh_qc_stock_loc_id (via qc_type_id push)
  │                               │
  │                               └── → lot_stock_id (via store_type_id push)
  │
  ├── wh_output_stock_loc_id (usage='internal', name='Output')
  │      Active: delivery_steps != 'ship_only'
  │      │
  │      ├── (pick_ship): ← lot_stock_id (via pick_type_id pull)
  │      │                  └── → customer (via out_type_id push)
  │      │
  │      └── (pick_pack_ship): ← wh_pack_stock_loc_id (via pack_type_id push)
  │                               │
  │                               └── → customer (via out_type_id push)
  │
  └── wh_pack_stock_loc_id (usage='internal', name='Packing Zone')
         Active: delivery_steps == 'pick_pack_ship'
         │
         └── ← lot_stock_id (via pick_type_id pull)
```

---

## Picking Type Color Assignment

When creating picking types, `_create_or_update_sequences_and_picking_types()` assigns colors to distinguish warehouse operations:

```python
# choose the next available color for the operation types of this warehouse
all_used_colors = [res['color'] for res in
    PickingType.search_read([('warehouse_id', '!=', False), ('color', '!=', False)],
                             ['color'], order='color')]
available_colors = [zef for zef in range(0, 12) if zef not in all_used_colors]
color = available_colors[0] if available_colors else 0
```

All 8 picking types for a given warehouse share the same color, cycling through colors 0-11 across warehouses. Colors are reused if fewer than 12 warehouses exist. The color appears in the kanban board of picking types.

---

## Cascading Update Map (write() Triggers)

```
write(vals)
  │
  ├── 'company_id' change → raise UserError (forbidden)
  │
  ├── (any write) → _create_missing_locations()
  │
  ├── 'reception_steps' change → _update_location_reception()
  │                           → _update_reception_delivery_resupply()
  │
  ├── 'delivery_steps' change → _update_location_delivery()
  │                           → _update_reception_delivery_resupply()
  │
  ├── 'reception_steps' OR 'delivery_steps' change → _create_or_update_route()
  │                                                  → _create_or_update_global_routes_rules()
  │
  ├── 'partner_id' change → _update_partner_data()
  │
  ├── 'code' OR 'name' change → _update_name_and_code()
  │                            → _create_or_update_sequences_and_picking_types()
  │                            → _create_or_update_route()
  │
  ├── 'active' change → (guard: ongoing moves check)
  │                  → archive picking types
  │                  → archive view location
  │                  → archive warehouse-only routes
  │                  → archive all rules
  │                  → if reactivating: cascade reactivate
  │
  └── 'resupply_wh_ids' change → create_resupply_routes(to_add)
                              → archive routes(to_remove)
```
