# Stock Rule (`stock.rule`)

**Source:** `odoo/addons/stock/models/stock_rule.py`
**Odoo Version:** 19
**Module:** `stock`
**Tags:** `#stock`, `#stock-rule`, `#procurement`, `#routing`, `#routes`, `#orm`

> `stock.rule` is the core execution engine of Odoo's routing and procurement system. Each rule is an atomic step in a supply chain: it defines what action to take (pull/push/buy/manufacture), from where, to where, and how. Rules are grouped into `stock.route` records, and the system resolves the correct rule via `_get_rule()` before executing procurement via `run()`.

---

## 1. Model Declaration

```python
class StockRule(models.Model):
    _name = 'stock.rule'
    _description = "Stock Rule"
    _order = "sequence, id"
    _check_company_auto = True
```

| Flag | Purpose |
|------|---------|
| `_order = "sequence, id"` | Rules execute in defined sequence order; lower sequence fires first |
| `_check_company_auto = True` | All `check_company=True` relational fields validate company consistency |

---

## 2. Data Structures

### 2.1 `ProcurementException`

```python
class ProcurementException(Exception):
    def __init__(self, procurement_exceptions):
        self.procurement_exceptions = procurement_exceptions  # list of (procurement, error_msg)
```

Raised when one or more procurements cannot be fulfilled. When `raise_user_error=False` in `run()`, the caller catches this to collect all failures before raising a consolidated `UserError`.

### 2.2 `Procurement` NamedTuple

```python
class Procurement(NamedTuple):
    product_id: fields.Many2one      # product.product
    product_qty: fields.Float
    product_uom: fields.Many2one     # uom.uom
    location_id: fields.Many2one     # stock.location — destination
    name: fields.Char
    origin: fields.Char              # e.g. SO name, MPS reference, "Manual Replenishment"
    company_id: fields.Many2one      # res.company
    values: dict                     # extensible metadata bag
```

**Common `values` dict keys:**

| Key | Type | Description |
|-----|------|-------------|
| `date_planned` | `datetime` | Scheduled procurement date (required) |
| `partner_id` | `res.partner` | Preferred vendor/contact |
| `route_ids` | `stock.route` recordset | Routes to consider |
| `warehouse_id` | `stock.warehouse` | Target warehouse |
| `orderpoint_id` | `stock.warehouse.orderpoint` | Ordering point that triggered procurement |
| `move_dest_ids` | `stock.move` recordset | Downstream moves chained to this one |
| `production_group_id` | `procurement.group` | Grouping key for MO batching |
| `bom_id` | `mrp.bom` | Bill of Materials for manufacturing |
| `supplier` | `dict` | Vendor info from seller |
| `propagate_cancel` | `bool` | Propagate cancellation upstream |
| `to_refund` | `bool` | Marks this as a refund (negative qty) |
| `date_deadline` | `datetime` | Hard delivery deadline |
| `packaging_uom_id` | `uom.uom` | Packaging unit for route filtering |
| `never_product_template_attribute_value_ids` | recordset | Attribute exclusions for kit explosion |
| `priority` | `str` | Priority "0"–"9" |
| `reference_ids` | `stock.reference` | Origin tracking (Odoo 19+) |

---

## 3. All Fields (L1–L2 Depth)

### 3.1 Identity & State

| Field | Type | Default | Index | Notes |
|-------|------|---------|-------|-------|
| `name` | `Char` | — | — | Required, translate=True. Fills move name/reference. |
| `active` | `Boolean` | `True` | — | Soft-disable; `write()` with `active=False` archives linked rules |

### 3.2 Action & Sequence

| Field | Type | Default | Index | Notes |
|-------|------|---------|-------|-------|
| `action` | `Selection` | `pull` | `True` | `pull`, `push`, `pull_push` — core; `buy` (purchase_stock), `manufacture` (mrp) |
| `sequence` | `Integer` | `20` | — | Execution order within route; `_order` uses this |
| `route_id` | `Many2one(stock.route)` | Required | `True` | Ondelete cascade; deleting a route deletes its rules |
| `route_company_id` | `Many2one` (related) | — | — | `related='route_id.company_id'`; drives company domain filter |
| `route_sequence` | `Integer` (related, stored, compute_sudo) | — | — | `related='route_id.sequence', store=True, compute_sudo=True`; enables sort by route priority |

### 3.3 Location & Routing

| Field | Type | Check Company | Index | Notes |
|-------|------|---------------|-------|-------|
| `location_dest_id` | `Many2one(stock.location)` | Yes | `True` | Required. Destination for pull moves; source for push rules. |
| `location_src_id` | `Many2one(stock.location)` | Yes | `True` | Source for pull rules; auto-populated via `_onchange_picking_type()` |
| `location_dest_from_rule` | `Boolean` | — | — | If `True`, move's `location_dest_id` = rule's `location_dest_id`; else from picking type |

### 3.4 Supply Method

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `procure_method` | `Selection` | `make_to_stock` | `make_to_stock`, `make_to_order`, `mts_else_mto` |

**Behavior table:**

| Value | Meaning | Stock check | Creates downstream procurement |
|-------|---------|-------------|-------------------------------|
| `make_to_stock` | Take from available stock | Yes, shortfall allowed | No |
| `make_to_order` | Trigger rule to bring in product | No, ignores stock | Yes, at `location_src_id` |
| `mts_else_mto` | MTS if stock available, else MTO | Yes, triggers MTO if shortfall | Yes, conditionally |

### 3.5 Operation & Timing

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `picking_type_id` | `Many2one(stock.picking.type)` | Required | Determines operation type; auto-fills src/dest locations |
| `picking_type_code_domain` | `Json` (computed) | `[]` | Dynamic domain filter for picking type selection |
| `delay` | `Integer` | `0` | Lead time in days; subtracted from `date_planned` for move date |

**`picking_type_code_domain` values by action:**
- `pull`/`push`/`pull_push`: `[]` (all types)
- `buy`: `['incoming']` (purchase_stock overrides)
- `manufacture`: `['mrp_operation']` (mrp overrides)

### 3.6 Partner & Propagation

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `partner_address_id` | `Many2one(res.partner)` | — | Vendor delivery address for generated moves |
| `propagate_cancel` | `Boolean` | `False` | Cancel downstream moves when this move is cancelled |
| `propagate_carrier` | `Boolean` | `False` | Propagate carrier along the move chain |
| `warehouse_id` | `Many2one(stock.warehouse)` | — | Warehouse context; used in `_search_rule_for_warehouses()` |

### 3.7 Automatic Operation & Display

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `auto` | `Selection` | `manual` | `manual` (create new move) vs `transparent` (replace dest location) — push rules only |
| `rule_message` | `Html` (computed) | — | User-friendly description; computed from `_compute_action_message()` |
| `push_domain` | `Char` | — | Legacy push applicability domain (deprecated) |
| `company_id` | `Many2one(res.company)` | `self.env.company` | Domain: `[('id', '=?', route_company_id)]` |

### 3.8 Constraints

```python
@api.constrains('company_id')
def _check_company_consistency(self):
    for rule in self:
        route = rule.route_id
        if route.company_id and rule.company_id.id != route.company_id.id:
            raise ValidationError(_(
                "Rule %(rule)s belongs to %(rule_company)s while the route belongs to %(route_company)s.",
                rule=rule.display_name,
                rule_company=rule.company_id.display_name,
                route_company=route.company_id.display_name,
            ))
```

---

## 4. Core Methods (L3 Depth)

### 4.1 `run(procurements, raise_user_error=True)`

Main entry point for executing procurement requests.

**Algorithm:**
```
1. For each procurement:
   a. Set defaults: company_id, priority, date_planned
   b. Skip if _skip_procurement() returns True
   c. Find rule via _get_rule()
   d. Group by action type (pull/push/buy/manufacture)
2. For each action group:
   a. Call _run_<action>(procurements)
   b. Catch ProcurementException, accumulate errors
3. Raise UserError or ProcurementException if errors exist
```

**Skip conditions** (`_skip_procurement()`):
- Product type != `"consu"`
- Quantity is zero (`float_is_zero` with UoM rounding)

**Error handling:**
- If `raise_user_error=True`: raises `UserError` with concatenated error messages
- If `raise_user_error=False`: raises `ProcurementException` with list of `(procurement, error)` tuples

### 4.2 `_get_rule(product_id, location_id, values)`

Find the most applicable pull rule for a procurement at a location.

**Algorithm:**
```
1. Build location hierarchy: location_id → parent → grandparent (until root)
2. Call _search_rule_for_warehouses() to build (location_id, route_id) → warehouse_id → rule dict
3. Walk through location hierarchy:
   a. For each location:
      i. Call get_rule_for_routes() to find best matching rule
      ii. If inter-company transit, add stock_location_customers to candidates
   b. Break on first match
   c. If no match, move to parent location
4. Return first matching rule or empty recordset
```

**Rule resolution priority within a location:**
```
route_ids (from values)
  → packaging_uom_id.package_type_id.route_ids
  → product_id.route_ids | product_id.categ_id.total_route_ids
  → warehouse_id.route_ids
```

**Within each route level:**
1. Exact warehouse match preferred over `False`
2. Then by `route_sequence` (ascending)
3. Then by `sequence` (ascending)

### 4.3 `_search_rule_for_warehouses(route_ids, packaging_uom_id, product_id, warehouse_ids, domain)`

Batch-read all applicable rules grouped by `(location_dest_id, route_id, warehouse_id)`.

**Returns:** `defaultdict(OrderedDict)` mapping `(location_dest_id.id, route_id.id) → {warehouse_id.id: rule}`.

Uses `_read_group()` with aggregates to batch-query all rules in one shot — key performance optimization.

### 4.4 `_search_rule(route_ids, packaging_uom_id, product_id, warehouse_id, domain)`

Search for a rule with cascading fallback strategies. Called from `_search_rule_for_warehouses()` for each location-route-warehouse combination.

**Search cascade:**
```
1. Search rules from route_ids, ordered by route_sequence, sequence, limit=1
2. If not found and packaging_uom_id: search packaging package type routes
3. If not found: search product routes + category total routes
4. If not found and warehouse_id: search warehouse routes
5. Return first match or empty recordset
```

### 4.5 `_run_pull(procurements)`

Execute pull rules by creating stock moves.

**Algorithm:**
```
1. Sanity check: ensure all procurements have location_src_id, raise ProcurementException if missing
2. Sort procurements: negative qty first (using product_uom.compare)
3. For each (procurement, rule):
   a. If procure_method == 'mts_else_mto': set to 'make_to_stock' initially
   b. Call _get_stock_move_values() to build move dict
   c. Override procure_method back to rule.procure_method
   d. Group by company_id in moves_values_by_company defaultdict
4. For each company:
   a. Batch-create all moves via sudo().with_company(company_id).create()
   b. Call _action_confirm() on created moves
5. Return True
```

**Key behaviors:**
- Creates as SUPERUSER to bypass access rights
- Negative qty sets `values['to_refund'] = True`
- Inter-warehouse: sets `partner_id` from warehouse partner

### 4.6 `_get_stock_move_values(product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values)`

Build dictionary for `stock.move.create()`.

**Core computed values:**

| Key | Source | Notes |
|-----|--------|-------|
| `company_id` | `self.company_id` → `location_src_id.company_id` → `location_dest_id.company_id` → `company_id` | Cascade fallback |
| `location_id` | `self.location_src_id.id` | Source for pull moves |
| `location_final_id` | `location_dest_id.id` | Ultimate destination |
| `location_dest_id` | `self.location_dest_id.id` if `location_dest_from_rule` else `location_dest_id` | |
| `partner_id` | `self.partner_address_id` or `values['partner_id']`; inter-warehouse: from warehouse partner | |
| `rule_id` | `self.id` | Link back to source rule |
| `date` | `values['date_planned'] - relativedelta(days=self.delay)` | |
| `date_deadline` | `values['date_deadline'] - relativedelta(days=self.delay)` | |
| `procurement_values` | `_serialize_procurement_values(values)` | JSON-serializable |
| `route_ids` | Clear + link from `values['route_ids']` | `[Command.clear()] + [Command.link(route.id) for ...]` |
| `reference_ids` | `[Command.set(values.get('reference_ids', ...).ids)]` | Odoo 19+ |
| `procure_method` | `self.procure_method` | Set after override |
| `procure_method` (override) | `make_to_stock` for `mts_else_mto` | Reset by `_run_pull()` |

**Custom field injection via `_get_custom_move_fields()`:**
```python
for field in self._get_custom_move_fields():  # Override returns list of field names
    if field in values:
        move_values[field] = values.get(field)
```
Extensions (e.g., `purchase_stock`) override `_get_custom_move_fields()` to inject fields from procurement `values` into the move record.

### 4.7 `_serialize_procurement_values(values)`

Convert procurement values to JSON-serializable format for storage in `procurement_values` JSON field.

| Input type | Output |
|-----------|--------|
| `models.BaseModel` (record) | `value.ids` |
| `datetime.datetime` | ISO string via `isoformat()` |
| `datetime.date` | ISO string via `isoformat()` |
| `fields.Datetime` | `to_string()` |
| `fields.Date` | `to_string()` |
| Other | As-is |

### 4.8 `_run_push(move)`

Apply a push rule on a stock move. Called explicitly from `stock.move._push_apply()`.

**`auto == 'transparent'` mode:**
1. Compute new date: `move.date + relativedelta(days=self.delay)`
2. Write `{date: new_date, location_dest_id: self.location_dest_id.id}`
3. Apply putaway strategy to move lines
4. If destination changed: recursively call `move._push_apply()`

**`auto == 'manual'` mode:**
1. Call `_push_prepare_move_copy_values()` to build move copy dict
2. Copy move as SUPERUSER with new vals
3. If `location_final_id` set and not child of dest: set as final dest
4. If source bypasses reservation: set `procure_method = 'make_to_stock'`
5. Link source move to new move via `move_dest_ids`
6. Return new move

**`_push_prepare_move_copy_values` key transforms:**
- `location_id` = move's `location_dest_id` (push forward)
- `location_dest_id` = rule's destination or move's `location_final_id`
- `location_final_id` = move's `location_final_id` if outside destination
- `procure_method` = `'make_to_order'` (push chain is always MTO)
- `picking_id` = `False` (no picking on intermediate push moves)
- `rule_id` = `self.id`

### 4.9 `_get_lead_days(product, **values)`

Calculate cumulative procurement delay across all applicable rules.

**Returns:** `(delays_dict, delay_description_list)`

**`delays_dict` structure:**
```python
{
    'total_delay': 5.0,        # Sum of all rule delays
    'horizon_time': 30.0,      # Global horizon days from orderpoint
    'purchase_delay': 7.0,    # purchase_stock adds vendor lead time + days_to_purchase
    'manufacture_delay': 3.0,  # mrp adds production lead time
    'no_bom_found_delay': 365.0,   # If no BoM found (purchase_stock/mrp)
    'no_vendor_found_delay': 365.0, # If no vendor found (purchase_stock)
}
```

**Context variables:**
- `bypass_delay_description`: Skip description generation (for calculation only)
- `bypass_global_horizon_days`: Skip horizon calculation

### 4.10 `_run_scheduler_tasks(use_new_cursor=False, company_id=False)`

Periodic scheduler entry point. Called by `ir.cron`.

**Tasks in order:**
1. **Orderpoint procurement:** Search `stock.warehouse.orderpoint` with `trigger='auto'`, compute qty, create procurements via `_procure_orderpoint_confirm()`
2. **Move assignment:** Find confirmed/partially available moves (`_get_moves_to_assign_domain`), batch-assign via `_action_assign()` in chunks of 1000
3. **Quant tasks:** Run `_quant_tasks()` for duplicate quant merging

**Batch processing pattern:**
```python
for moves_chunk in split_every(1000, moves_to_assign.ids):
    self.env['stock.move'].browse(moves_chunk).sudo()._action_assign()
    if use_new_cursor:
        self.env.cr.commit()
```

---

## 5. Cross-Module Patterns (L3)

### 5.1 Rule Resolution Cascade (Stock Rule ↔ All Procurement Models)

```
procurement trigger (sale order, orderpoint, manual)
    │
    ▼
stock.rule.run(procurements)
    │
    ├──► _get_rule(product, location, values)      ← finds rule
    ├──► action = 'pull'/'push'/'buy'/'manufacture'
    │
    ▼
_run_pull(procurements)     ← stock.rule
    └──► stock.move.create() → stock.move._action_confirm()

_run_buy(procurements)      ← purchase_stock
    └──► purchase.order.create() / write()

_run_manufacture(procurements)  ← mrp
    └──► mrp.production.create()
```

### 5.2 Override Pattern: `_get_custom_move_fields()`

Used by extensions to inject procurement values into stock moves without modifying core `_get_stock_move_values()` signature:

```python
# purchase_stock overrides:
def _get_custom_move_fields(self):
    return ['supplier', 'supplier_info_id', 'po_order_id', 'po_line_id']
```

This allows custom fields to be passed through the procurement chain without core modification.

### 5.3 Override Pattern: `_prepare_mo_vals()` (mrp)

MRP extension builds manufacturing order values with custom logic:
- Batch size splitting
- BoM variant selection
- Workorder planning
- Scrap location mapping

### 5.4 Workflow Trigger: Procurement Group → Rule Action → Move Creation

```
1. sale.order.action_confirm()
   └─► _action_launch_stock_rule()
       └─► stock.rule.run(procurements)

   OR

1. stock.warehouse.orderpoint._procure_orderpoint_confirm()
   └─► stock.rule.run(procurements)

   OR

1. Manual procurement via stock.warehouse.orderpoint or _procure()
```

Each `run()` call dispatches to the appropriate `_run_<action>()` method based on rule action.

### 5.5 Failure Mode

| Failure | Behavior | User Feedback |
|---------|----------|---------------|
| No rule found | `ProcurementException` or `UserError` | "No rule has been found to replenish X in Y" |
| No source location | `ProcurementException` in `_run_pull()` | "No source location defined on stock rule: X!" |
| Consu product with qty=0 | Skipped via `_skip_procurement()` | Silent skip |
| Vendor not found (orderpoint) | `ProcurementException` from `_run_buy()` | "No vendor found for product X" |
| No BoM found | Delay added via `_get_lead_days()` | 365-day delay penalty |

---

## 6. Version Changes: Odoo 18 → 19

### 6.1 `Domain` Class Usage

Odoo 19 replaces raw tuple domains with `odoo.fields.Domain` objects:

```python
# Odoo 18
domain = [('location_dest_id', 'in', location_ids)]

# Odoo 19
domain = Domain('location_dest_id', 'in', location_ids)
domain &= Domain('action', '!=', 'push')
domain = domain.optimize(Rule)  # Optimizes for SQL
```

All rule search methods (`_search_rule`, `_search_rule_for_warehouses`, `_get_rule_domain`, `_get_push_rule`) now use `Domain` objects.

### 6.2 `stock.reference` Model

Odoo 19 introduces `stock.reference` for origin tracking. Rule-created moves now include:

```python
'reference_ids': [Command.set(values.get('reference_ids', self.env['stock.reference']).ids)]
```

This replaces ad-hoc origin string tracking with a proper relational model.

### 6.3 `ProcurementGroup` Deprecation

`stock.procurement.group` is no longer referenced in `stock_rule.py`. Procurement grouping is now handled via:
- `stock.reference` for origin tracking
- `move_dest_ids` for move chaining
- `production_group_id` for MO batching

### 6.4 `route_sequence` Storage

```python
# Odoo 19 — stored + compute_sudo
route_sequence = fields.Integer(
    'Route Sequence',
    related='route_id.sequence',
    store=True,
    compute_sudo=True
)
```

### 6.5 `date_deadline` Propagation

Odoo 19 properly propagates `date_deadline` through the procurement chain:

```python
date_deadline = values.get('date_deadline') and (
    fields.Datetime.from_string(values['date_deadline']) - relativedelta(days=self.delay or 0)
) or False
```

---

## 7. Performance (L4)

### 7.1 Batch Move Creation

`_run_pull()` groups moves by company and creates them in a single `create()` call per company:

```python
moves_values_by_company[procurement.company_id.id].append(move_values)
...
for company_id, moves_values in moves_values_by_company.items():
    moves = self.env['stock.move'].sudo().with_company(company_id).create(moves_values)
    moves._action_confirm()
```

### 7.2 Rule Lookup Optimization

`_search_rule_for_warehouses()` uses `_read_group()` to batch-read all applicable rules in one query, grouped by `(location_dest_id, route_id, warehouse_id)`:

```python
res = self.env["stock.rule"]._read_group(
    domain,
    groupby=["location_dest_id", "warehouse_id", "route_id"],
    aggregates=["id:recordset"],
    order="route_sequence:min, sequence:min",
)
```

The result is an `OrderedDict` allowing O(1) lookups during rule resolution.

### 7.3 Scheduler Chunk Processing

Scheduler processes moves in batches of 1000 to prevent memory exhaustion on large databases:

```python
for moves_chunk in split_every(1000, moves_to_assign.ids):
    self.env['stock.move'].browse(moves_chunk).sudo()._action_assign()
    if use_new_cursor:
        self.env.cr.commit()
        _logger.info("A batch of %d moves are assigned and committed", len(moves_chunk))
```

### 7.4 Indexes

Key fields are indexed for fast rule lookup: `action`, `company_id`, `location_dest_id`, `location_src_id`, `route_id`, `warehouse_id`, `picking_type_id`, `sequence`. Additionally, `stock.location` has a composite index on `(parent_path, id)` via `_parent_path_id_idx`.

### 7.5 Domain Optimization

`Domain.optimize(Rule)` converts the Domain object to an optimized SQL expression before searching, reducing query planning overhead on large rule tables.

---

## 8. Security (L4)

### 8.1 Access Rights

- Procurement execution uses `sudo()` to bypass access rights — a sale order launched by a regular user may trigger procurement requiring warehouse manager permissions
- Scheduler runs as SUPERUSER to handle cross-company operations
- Rule company filtering in `_get_rule_domain()` uses the `su` context:
```python
if self.env.su and values.get('company_id'):
    domain_company = ['|', ('company_id', '=', False), ('company_id', 'child_of', list(company_ids))]
    domain &= Domain(domain_company)
```

### 8.2 Data Consistency

- `@api.constrains('company_id')` ensures rule company matches route company
- `_onchange_route()` prevents misaligned picking types (picking type warehouse must match route company)
- `_onchange_picking_type()` auto-fills `location_src_id` and `location_dest_id` to prevent mismatched locations

---

## 9. Related Models

| Model | Purpose |
|-------|---------|
| `stock.route` | Groups rules into logical routing chains |
| `stock.location` | Source and destination locations |
| `stock.picking.type` | Operation types for generated pickings |
| `stock.warehouse` | Warehouse context for rule selection |
| `stock.move` | Stock moves created by pull rules |
| `stock.warehouse.orderpoint` | Triggers automatic procurement |
| `stock.reference` | Tracks procurement origins (Odoo 19+) |
| `stock.putaway.rule` | Driven by location putaway strategy |
| `mrp.production` | Manufacturing orders (via mrp extension) |
| `purchase.order` | Purchase orders (via purchase_stock extension) |

---

## Related Documentation

- [Modules/Stock](Modules/Stock.md) — Full stock module overview
- [Modules/stock_warehouse](Modules/stock_warehouse.md) — Warehouse configuration
- [Modules/stock_location](Modules/stock_location.md) — Location hierarchy
- [Modules/stock_move](Modules/stock_move.md) — Stock move model
- [Modules/stock_rule](Modules/stock_rule.md) — Automatic procurement
- [Modules/Purchase](Modules/Purchase.md) — Purchase order lifecycle
- [Modules/MRP](Modules/MRP.md) — Manufacturing orders
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — Route and procurement workflow patterns
