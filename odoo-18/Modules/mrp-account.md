# mrp_account — Manufacturing Accounting

**Module:** `mrp_account`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/mrp_account/`
**Depends:** `mrp`, `stock_account`, `analytic`
**Category:** Manufacturing/Manufacturing
**Auto-install:** True

---

## Purpose

`mrp_account` bridges manufacturing orders (MO) with Odoo's accounting and analytic modules. It provides:

1. **Cost calculation** — computes the true cost of finished products from components + labor + overhead
2. **Analytic accounting** — creates `account.analytic.line` records for raw material consumption and workcenter labor time
3. **Labor journal entries** — posts WIP/labor costs to accounting when MO is marked done
4. **Stock valuation overrides** — routes production-related stock moves through correct valuation accounts
5. **WIP accounting** — tracks work-in-progress for real-time valued products
6. **Analytic applicability** — allows analytic distribution to be applied to manufacturing orders as a business domain

---

## Module Structure

```
mrp (base)
  └── mrp_account
        ├── models/
        │   ├── mrp_production.py      # Cost calc, labor posting, WIP
        │   ├── mrp_workorder.py       # Analytic lines from time tracking
        │   ├── mrp_workcenter.py      # Expense account, analytic mixin
        │   ├── analytic_account.py     # Analytic account extensions
        │   ├── stock_move.py           # Production valuation overrides
        │   └── account_move.py         # WIP account.move extensions
        ├── report/                     # Cost structure reports
        └── wizard/                     # WIP accounting wizard

Dependencies chain:
  mrp → stock_account → mrp_account
                   → analytic
```

---

## Model: `mrp.production` (Extended by mrp_account)

**File:** `models/mrp_production.py`

`mrp_account` extends the base `mrp.production` model with cost and valuation fields.

### Fields Added by mrp_account

| Field | Type | Description |
|-------|------|-------------|
| `extra_cost` | `Float` | Extra unit cost added to finished product valuation. Carried to backorders. Copied=False. |
| `show_valuation` | `Boolean` (computed) | True when any finished move is in `done` state. Triggers "View Valuation" button visibility. |

### Key Methods

#### `_cal_price(consumed_moves)`

**When called:** When MO's finished product move is about to be validated.

**Purpose:** Sets `price_unit` on the finished `stock.move` to reflect true cost.

```python
def _cal_price(self, consumed_moves):
    super(MrpProduction, self)._cal_price(consumed_moves)
    work_center_cost = 0
    finished_move = self.move_finished_ids.filtered(
        lambda x: x.product_id == self.product_id
        and x.state not in ('done', 'cancel')
        and x.quantity > 0
    )
    if finished_move:
        finished_move.ensure_one()
        # Sum labor cost from all workorders
        for work_order in self.workorder_ids:
            work_center_cost += work_order._cal_cost()

        quantity = finished_move.product_uom._compute_quantity(
            finished_move.quantity, finished_move.product_id.uom_id)
        extra_cost = self.extra_cost * quantity

        # total_cost = -sum(SVL values for components) + labor + extra
        total_cost = (
            - sum(consumed_moves.sudo().stock_valuation_layer_ids.mapped('value'))
            + work_center_cost
            + extra_cost
        )

        # Byproduct price_unit calculation
        byproduct_moves = self.move_byproduct_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and m.quantity > 0)
        byproduct_cost_share = 0
        for byproduct in byproduct_moves:
            if byproduct.cost_share == 0:
                continue
            byproduct_cost_share += byproduct.cost_share
            if byproduct.product_id.cost_method in ('fifo', 'average'):
                byproduct.price_unit = (
                    total_cost * byproduct.cost_share / 100
                    / byproduct.product_uom._compute_quantity(
                        byproduct.quantity, byproduct.product_id.uom_id)
                )

        # Finished product unit cost
        if finished_move.product_id.cost_method in ('fifo', 'average'):
            finished_move.price_unit = (
                total_cost
                * float_round(1 - byproduct_cost_share / 100, precision_rounding=0.0001)
                / quantity
            )
```

**L4 — Cost Calculation Breakdown:**

| Component | Source | Sign |
|-----------|--------|------|
| Component SVL values | `consumed_moves.sudo().stock_valuation_layer_ids` | Negative (outgoing) |
| Workcenter labor | `workorder._cal_cost()` = `sum(duration × costs_hour)` | Positive (cost added) |
| Extra cost | `self.extra_cost × quantity` | Positive |
| Byproduct offset | `total_cost × cost_share / 100` | Negative (reduces finished cost) |

The `float_round(1 - byproduct_cost_share/100, precision_rounding=0.0001)` ensures the byproduct and finished product costs sum to exactly `total_cost`.

#### `_post_labour()`

**When called:** By `_post_inventory()` after all stock moves are marked done.

**Precondition:** `mo.product_id.valuation == 'real_time'` (only for real-time products).

```python
def _post_labour(self):
    # Group workorder costs by expense account
    labour_amounts = defaultdict(float)  # {account_id: amount}
    workorders = defaultdict(self.env['mrp.workorder'].browse)

    for wo in mo.workorder_ids:
        # expense_account: workcenter's or fallback to product's expense account
        account = wo.workcenter_id.expense_account_id or product_accounts['expense']
        labour_amounts[account] += wo.company_id.currency_id.round(wo._cal_cost())
        workorders[account] |= wo

    workcenter_cost = sum(labour_amounts.values())

    # Build journal entry lines
    # DR expense_account (per workcenter)  →  CR stock_valuation (for finished product)
    for acc, amt in labour_amounts.items():
        if acc == src_account:
            labour_amounts[acc] -= workcenter_cost  # Avoid double-counting
        line_ids.append((0, 0, {'name': desc, 'balance': -amt, 'account_id': acc.id}))

    account_move = env['account.move'].sudo().create(move_vals)
    account_move._post()

    # Link move lines back to time tracking records
    for line in account_move.line_ids[:-1]:
        workorders[line.account_id].time_ids.write({
            'account_move_line_id': line.id
        })
```

**Journal Entry Created:**

| Account | Debit | Credit |
|---------|-------|--------|
| `workcenter_id.expense_account_id` | Labor cost | — |
| Stock Valuation (finished product's `production` account) | — | Labor cost |

**L4 — WIP (Work In Progress):**

For real-time products, the labor journal entry represents the **labor cost addition to WIP**:
- Before MO done: WIP = value of components consumed (DR WIP, CR Stock)
- After MO done + `_post_labour()`: Labor is added (DR Labor Expense, CR WIP)

The `_post_labour()` also links each `account.move.line` back to the `mrp.workorder.productivity` records (`account_move_line_id`), creating a full audit trail.

#### `_post_inventory()` (override)

Calls `super()._post_inventory()` first (standard SVL creation), then calls `self.filtered(lambda mo: mo.state == 'done')._post_labour()`.

**Note:** `_post_labour()` only runs for MOs that are `state == 'done'` after inventory posting. This prevents labor posting for MOs that are cancelled or have issues.

#### `_get_backorder_mo_vals()` (override)

Carries `extra_cost` forward to backorder MOs:
```python
res = super()._get_backorder_mo_vals()
res['extra_cost'] = self.extra_cost
return res
```

#### `action_view_stock_valuation_layers()`

Opens `stock.valuation.layer` list filtered to this MO's component moves + finished moves + scrap moves:
```python
domain = [('id', 'in',
    (self.move_raw_ids + self.move_finished_ids + self.scrap_ids.move_ids
    ).stock_valuation_layer_ids.ids)]
```

---

## Model: `mrp.workorder` (Extended by mrp_account)

**File:** `models/mrp_workorder.py`

### Fields Added by mrp_account

| Field | Type | Description |
|-------|------|-------------|
| `mo_analytic_account_line_ids` | `Many2many` | Analytic lines from MO-level distribution (mirrors workcenter's WC-level lines) |
| `wc_analytic_account_line_ids` | `Many2many` | Analytic lines created from workcenter time tracking cost |

**Relation table:** `mrp_workorder_mo_analytic_rel` and `mrp_workorder_wc_analytic_rel`

### Key Methods

#### `_create_or_update_analytic_entry()`

Called on every `_compute_duration()` (when time is recorded) and `_set_duration()` (when time is edited manually).

```python
def _create_or_update_analytic_entry(self):
    for wo in self:
        if not wo.id:
            continue
        hours = wo.duration / 60.0
        value = -hours * wo.workcenter_id.costs_hour
        wo._create_or_update_analytic_entry_for_record(value, hours)
```

The negative value represents a **cost** (resource consumption):
- `amount = -duration_hours × costs_hour` (negative = cost debit to analytic)

#### `_create_or_update_analytic_entry_for_record(value, hours)`

```python
def _create_or_update_analytic_entry_for_record(self, value, hours):
    self.ensure_one()
    if (self.workcenter_id.analytic_distribution
            or self.wc_analytic_account_line_ids
            or self.mo_analytic_account_line_ids):
        # Use workcenter's analytic_distribution to split into multiple lines
        wc_analytic_line_vals = (
            self.env['account.analytic.account']
            ._perform_analytic_distribution(
                self.workcenter_id.analytic_distribution,
                value, hours,
                self.wc_analytic_account_line_ids,
                self  # record for line creation context
            )
        )
        if wc_analytic_line_vals:
            self.wc_analytic_account_line_ids += (
                self.env['account.analytic.line'].sudo().create(wc_analytic_line_vals)
            )
```

**L4 — Analytic Distribution:**
- If `workcenter_id.analytic_distribution` is set (a JSON distribution like `{account_id: percentage}`), the cost is split across multiple analytic accounts.
- `_perform_analytic_distribution()` creates multiple `account.analytic.line` records (one per account in the distribution), each with `amount = value × percentage`.
- If no distribution is set, no analytic lines are created from workorder time — but the `_post_labour()` labor journal entry still runs.

#### `_prepare_analytic_line_values(account_field_values, amount, unit_amount)`

Returns the base values for an analytic line:

```python
{
    'name': _("[WC] %s", self.display_name),   # "[WC] WO/0001"
    'amount': amount,                            # Negative (cost)
    **account_field_values,                      # From analytic_distribution
    'unit_amount': unit_amount,                  # Hours
    'product_id': self.product_id.id,
    'product_uom_id': ref('uom.product_uom_hour'),
    'company_id': self.company_id.id,
    'ref': self.production_id.name,              # MO reference
    'category': 'manufacturing_order',           # Distinguishes from other analytic categories
}
```

#### `action_cancel()` (override)

Deletes both `mo_analytic_account_line_ids` and `wc_analytic_account_line_ids` before cancel:
```python
def action_cancel(self):
    (self.mo_analytic_account_line_ids | self.wc_analytic_account_line_ids).unlink()
    return super().action_cancel()
```

#### `unlink()` (override)

Also deletes analytic lines before unlink.

---

## Model: `mrp.workcenter` (Extended by mrp_account)

**File:** `models/mrp_workcenter.py`

### Fields Added by mrp_account

| Field | Type | Description |
|-------|------|-------------|
| `costs_hour_account_ids` | `Many2many` (computed) | Analytic accounts from `analytic_distribution`. Pre-computed for display. |
| `expense_account_id` | `Many2one` | Account for labor expense posting. If not set, falls back to the finished product's expense account. |

### Inheritance

`mrp.workcenter` also inherits from `analytic.mixin`, which provides the `analytic_distribution` Json field. This enables per-workcenter analytic distribution.

---

## Model: `mrp.workcenter.productivity` (Extended by mrp_account)

**File:** `models/mrp_workcenter.py`

### Fields Added by mrp_account

| Field | Type | Description |
|-------|------|-------------|
| `account_move_line_id` | `Many2one` | Links this time log to the specific `account.move.line` created by `_post_labour()` |

**L4 — Audit Trail:**
When `_post_labour()` creates the labor journal entry, it writes `account_move_line_id` back to each related `mrp.workorder.productivity` record:
```python
for line in account_move.line_ids[:-1]:
    workorders[line.account_id].time_ids.write({
        'account_move_line_id': line.id
    })
```

This links each time-tracking record to the exact journal entry line that captured its cost.

---

## Model: `account.analytic.account` (Extended by mrp_account)

**File:** `models/analytic_account.py`

### Fields Added by mrp_account

| Field | Type | Description |
|-------|------|-------------|
| `production_ids` | `Many2many` | MOs that use this analytic account (via `analytic_distribution` on MO) |
| `production_count` | `Integer` (computed) | Count of linked MOs |
| `bom_ids` | `Many2many` | BoMs that use this analytic account |
| `bom_count` | `Integer` (computed) | Count of linked BoMs |
| `workcenter_ids` | `Many2many` | Workcenters that use this analytic account |
| `workorder_count` | `Integer` (computed) | Count of linked work orders |

**Computed from:**
- `production_count`: depends on `production_ids`
- `bom_count`: depends on `bom_ids`
- `workorder_count`: depends on `workcenter_ids.order_ids` union `production_ids.workorder_ids`

### Actions

| Method | View |
|--------|------|
| `action_view_mrp_production()` | List/form of MOs filtered to this account |
| `action_view_mrp_bom()` | List/form of BoMs filtered to this account |
| `action_view_workorder()` | List of all work orders from both direct workcenter and MO links |

---

## Model: `account.analytic.line` (Extended by mrp_account)

**File:** `models/analytic_account.py`

### Change: `category` Selection

Adds `'manufacturing_order'` to the selection:
```python
category = fields.Selection(selection_add=[('manufacturing_order', 'Manufacturing Order')])
```

This allows filtering analytic lines by manufacturing origin.

---

## Model: `account.analytic.applicability` (Extended by mrp_account)

**File:** `models/analytic_account.py`

Adds `'manufacturing_order'` to `business_domain`:

```python
business_domain = fields.Selection(selection_add=[
    ('manufacturing_order', 'Manufacturing Order'),
], ondelete={'manufacturing_order': 'cascade'})
```

**L4 — Analytic Applicability:**
This allows configuring automatic analytic distribution rules (via `analytic.distribution.model`) that apply specifically to manufacturing orders, just as rules can be configured for sales orders, projects, etc.

---

## Model: `stock.move` (Extended by mrp_account)

**File:** `models/stock_move.py`

### Accounting Account Routing for Production Moves

| Method | Scenario | Returns |
|--------|----------|---------|
| `_get_src_account(accounts_data)` | Move out of production location | `location_id.valuation_out_account_id` or `accounts_data['production']` or `accounts_data['stock_input']` |
| `_get_dest_account(accounts_data)` | Move into production location | `location_dest_id.valuation_in_account_id` or `accounts_data['production']` or `accounts_data['stock_output']` |

**L4 — Production Valuation Accounts:**
The `production` account (configured on product category as `property_stock_valuation_account_id` or `property_stock_production_account_id`) acts as the WIP account:
- **Components consumed** (production out): DR `production` account, CR `stock_output`
- **Finished product received** (production in): DR `stock_valuation`, CR `production`

### `_is_production()` / `_is_production_consumed()`

```python
def _is_production(self):
    # Move out of a 'production' location (components leaving inventory → production)
    return self.location_id.usage == 'production' and self.location_dest_id._should_be_valued()

def _is_production_consumed(self):
    # Move into a 'production' location (components arriving at production location)
    return self.location_dest_id.usage == 'production' and self.location_id._should_be_valued()
```

### Anglo-Saxon Filtering

```python
def _filter_anglo_saxon_moves(self, product):
    res = super()._filter_anglo_saxon_moves(product)
    # Also include moves from phantom BoMs in this MO
    res += self.filtered(lambda m: m.bom_line_id.bom_id.product_tmpl_id.id == product.product_tmpl_id.id)
    return res
```

Ensures kit components from phantom BoMs used in the MO are included in purchase invoice valuation (anglo-saxon mode).

### `_should_force_price_unit()`

```python
def _should_force_price_unit(self):
    return (
        (self.picking_type_id.code == 'mrp_operation' and self.production_id)
        or super()._should_force_price_unit()
    )
```

Forces the move's own `price_unit` (set by `_cal_price()`) to be used instead of the product's standard price in the finished product valuation.

### `_ignore_automatic_valuation()`

```python
def _ignore_automatic_valuation(self):
    return super()._ignore_automatic_valuation() or bool(self.raw_material_production_id)
```

Raw material consumption moves from MOs bypass automatic valuation because their price_unit is set explicitly from the MO's component cost calculation.

---

## Model: `account.move` (Extended by mrp_account)

**File:** `models/account_move.py`

### Fields Added by mrp_account

| Field | Type | Description |
|-------|------|-------------|
| `wip_production_ids` | `Many2many` | Manufacturing orders that this WIP journal entry was based on |
| `wip_production_count` | `Integer` (computed) | Count of linked MOs |

### `action_view_wip_production()`

Opens the related MOs from a WIP journal entry — enables drill-down from accounting to manufacturing.

---

## Model: `account.move.line` (Extended by mrp_account)

**File:** `models/account_move.py`

### `_get_invoiced_qty_per_product()` (override)

Replaces kit-type (phantom BoM) products with their actual components when computing quantities for invoicing:

```python
def _get_invoiced_qty_per_product(self):
    qties = defaultdict(float)
    res = super()._get_invoiced_qty_per_product()
    invoiced_products = self.env['product.product'].concat(*res.keys())

    # Resolve phantom BoM kits
    bom_kits = self.env['mrp.bom']._bom_find(
        invoiced_products, company_id=self.company_id[:1].id, bom_type='phantom')

    for product, qty in res.items():
        bom_kit = bom_kits[product]
        if bom_kit:
            # Explode the kit qty into components
            invoiced_qty = product.uom_id._compute_quantity(qty, bom_kit.product_uom_id, round=False)
            factor = invoiced_qty / bom_kit.product_qty
            dummy, bom_sub_lines = bom_kit.explode(product, factor)
            for bom_line, bom_line_data in bom_sub_lines:
                qties[bom_line.product_id] += bom_line.product_uom_id._compute_quantity(
                    bom_line_data['qty'], bom_line.product_id.uom_id)
        else:
            qties[product] += qty
    return qties
```

**L4 — Use Case:**
When a company invoices a customer for a kit product (phantom BoM), the quantity needs to be exploded into components to correctly match the consumed quantities for COGS reporting. This ensures that if you bill 5 "Computer Kits", the COGS correctly reflects 5 motherboards, 5 CPUs, 5 RAM sticks, etc.

---

## Cost Calculation Summary

### Standard vs Actual Cost

| Aspect | Standard Cost | Average/FIFO |
|--------|--------------|--------------|
| Component cost | Product's `standard_price` | Real-time from SVL |
| Labor cost | `workcenter_id.costs_hour × duration` | Same |
| Byproduct | `cost_share` deduction | Same |
| Extra cost | `extra_cost` field | Same |
| `finished_move.price_unit` | Set by `_cal_price()` | Set by `_cal_price()` |
| SVL value | `price_unit × qty` | `price_unit × qty` (matches avg cost) |

### MO Done — Full Journal Entry Sequence

```
1. Components consumed:
   DR WIP (production account)    100
     CR Stock (components)                 100

2. MO marked done — finished product received:
   DR Stock (finished)         130
     CR WIP (production)                  130

3. Labor posted via _post_labour():
   DR Labor Expense              30
     CR WIP (production)                   30

Net effect: Stock has 130, Labor Expense is 30,
WIP is 0 (components 100 + labor 30 = finished 130)
```

---

## Configuration: `property_stock_account_production_cost_id`

Set via `_configure_journals()` (auto-installed with chart of accounts):
- Points to the WIP/production cost account
- Used as the `production` account in `_get_src_account()` / `_get_dest_account()`

---

## Verified Source Files

| File | Key Elements Verified |
|------|----------------------|
| `addons/mrp_account/models/mrp_production.py` | Full `_cal_price()`, `_post_labour()`, `_post_inventory()`, `_get_backorder_mo_vals()`, `action_view_stock_valuation_layers()` |
| `addons/mrp_account/models/mrp_workorder.py` | `_create_or_update_analytic_entry()`, `_prepare_analytic_line_values()`, `_create_or_update_analytic_entry_for_record()`, cancel/unlink |
| `addons/mrp_account/models/mrp_workcenter.py` | `expense_account_id`, `costs_hour_account_ids` compute, `account_move_line_id` on productivity |
| `addons/mrp_account/models/analytic_account.py` | Full `account.analytic.account` + `account.analytic.line` + `account.analytic.applicability` extensions |
| `addons/mrp_account/models/stock_move.py` | `_is_production()`, `_is_production_consumed()`, `_get_src_account()`, `_get_dest_account()`, `_filter_anglo_saxon_moves()`, `_should_force_price_unit()`, `_ignore_automatic_valuation()` |
| `addons/mrp_account/models/account_move.py` | `wip_production_ids`, `action_view_wip_production()`, `_get_invoiced_qty_per_product()` override |
| `addons/mrp_account/__init__.py` | `_configure_journals()` function for auto-setup |

---

## Tags

`#odoo18` `#modules` `#mrp` `#accounting` `#analytic` `#wip` `#valuation` `#cost-calculation`
