---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #sale
  - #timesheet
  - #margin
module: sale_timesheet_margin
description: Computes accurate margins for service sales by bridging sale_margin and sale_timesheet. When service products are invoiced based on timesheet entries, the actual cost is the employee hourly cost from the timesheet.
odoo_version: "19"
depends:
  - sale_margin
  - sale_timesheet
auto_install: true
category: Sales/Sales
license: LGPL-3
---

# Sale Timesheet Margin

## L1: How Timesheet Affects Sale Margin

### Core Business Logic

`sale_timesheet_margin` is a **bridge module** between `sale_timesheet` (which records billable labor) and `sale_margin` (which computes profitability). Its purpose is to ensure that when a service product is billed based on time spent, the **cost** used in margin calculation is the **actual labor cost** (employee hourly rate), not the product's `standard_price`.

The fundamental problem it solves:

```
Without this module:
  Employee bills 8 hours at $100/hr on a service SOL
  → SOL.purchase_price = product.standard_price = $0 (service product has no cost)
  → margin = (8 * $100) - (8 * $0) = $800  ← INFLATED, doesn't reflect labor cost

With this module:
  Employee bills 8 hours at $100/hr on a service SOL
  → sale_timesheet records account.analytic.line with amount = -(8 * $100) = -$800
  → sale_timesheet_margin reads analytic lines linked to the SOL
  → SOL.purchase_price = sum(timesheet costs) / sum(timesheet hours) = $100/hr
  → margin = (8 * $100) - (8 * $100) = $0  ← ACCURATE, shows zero margin on billed time
```

### Two Delivery Methods for Services

`sale_timesheet` supports two `qty_delivered_method` values on `sale.order.line`:

| Method | Triggered when | How qty_delivered is computed |
|--------|---------------|------------------------------|
| `timesheet` | `product.service_type = 'timesheet'` | Sum of `unit_amount` on linked `account.analytic.line` records |
| `manual` | `product.service_type = 'manual'` or `ordered_prepaid` | Manual entry by user |

`sale_timesheet_margin` only overrides `purchase_price` for lines with `qty_delivered_method == 'timesheet'` and where the product has **no `standard_price`**. If a product has a `standard_price`, that is used instead (the product cost already covers the expense).

### The Margin Formula

```
margin = price_subtotal - (qty_delivered * purchase_price)

Where:
  price_subtotal = price_unit * qty_delivered  (for timesheet services)
  qty_delivered = sum of timesheet entry amounts / |hourly rate|
  purchase_price = |total timesheet cost| / |total timesheet hours|
```

### What "Purchase Price" Means Here

For timesheet-billed services, `purchase_price` on the SOL is the **employee's hourly cost rate**, derived from timesheet entries. This is not a product cost — it is a labor cost. The sign convention in Odoo:

- Timesheet entries record `amount` as a **negative** value (it is an expense/_cost to the project)
- The module takes the **absolute value**: `mapped_sol_timesheet_amount = -amount_sum / unit_amount_sum`

### Currency and UoM Handling

Timesheet costs are recorded in the **company's currency** and measured in **hours**. The SOL may use a different UoM (e.g., days). The module handles two conversions:

1. **Currency**: `line._convert_to_sol_currency(product_cost, line.product_id.cost_currency_id)` — converts the cost to the SOL's currency
2. **UoM**: If the SOL's UoM differs from the company's time-tracking UoM (`project_time_mode_id`), the cost is converted using `product_uom_id._compute_quantity()`

---

## L2: Field Types, Defaults, Constraints

### Extended Model: `sale.order.line`

**File:** `models/sale_order_line.py`

#### Method: `_compute_purchase_price()` — Full Override Analysis

```python
@api.depends('analytic_line_ids.amount', 'qty_delivered_method')
def _compute_purchase_price(self):
    # Filter out SOLs that should NOT be recomputed by this override
    service_non_timesheet_sols = self.filtered(
        lambda sol: not sol.is_expense and sol.is_service and
        sol.product_id.service_policy == 'ordered_prepaid' and
        sol.state == 'sale' and sol.purchase_price != 0
    )
    timesheet_sols = self.filtered(
        lambda sol: sol.qty_delivered_method == 'timesheet' and not sol.product_id.standard_price
    )
    super(SaleOrderLine, self - timesheet_sols - service_non_timesheet_sols)._compute_purchase_price()
    if timesheet_sols:
        group_amount = self.env['account.analytic.line']._read_group(
            [('so_line', 'in', timesheet_sols.ids), ('project_id', '!=', False)],
            ['so_line'],
            ['amount:sum', 'unit_amount:sum']
        )
        mapped_sol_timesheet_amount = {
            so_line.id: - amount_sum / unit_amount_sum if unit_amount_sum else 0.0
            for so_line, amount_sum, unit_amount_sum in group_amount
        }
        for line in timesheet_sols:
            line = line.with_company(line.company_id)
            product_cost = mapped_sol_timesheet_amount.get(line.id, line.product_id.standard_price)
            product_uom = line.product_uom_id or line.product_id.uom_id
            if product_uom != line.company_id.project_time_mode_id:
                product_cost = product_uom._compute_quantity(
                    product_cost, line.company_id.project_time_mode_id
                )
            line.purchase_price = line._convert_to_sol_currency(
                product_cost, line.product_id.cost_currency_id)
```

##### `@api.depends`

```python
@api.depends('analytic_line_ids.amount', 'qty_delivered_method')
```

| Dependency | Reason |
|-----------|--------|
| `analytic_line_ids.amount` | Changing a timesheet entry's amount changes the weighted average cost |
| `qty_delivered_method` | Switching from timesheet to manual delivery triggers/reverts this logic |

##### Filtering Logic

Two filters protect the method from interfering with unrelated SOLs:

**`service_non_timesheet_sols`** — SOLs that:
- Are not expenses (`not sol.is_expense`)
- Are services (`sol.is_service`)
- Use `ordered_prepaid` policy (billed in advance, not timesheet)
- Are in `sale` state with an already-set `purchase_price`

These are explicitly **excluded** from the super() call, preventing their `purchase_price` from being overwritten when unrelated timesheet entries are created.

**`timesheet_sols`** — SOLs where:
- `qty_delivered_method == 'timesheet'` — billed by timesheet
- `not sol.product_id.standard_price` — product has no standard cost (otherwise use product cost)

These are the SOLs this module actually processes.

##### `_read_group` for Performance

```python
group_amount = self.env['account.analytic.line']._read_group(
    [('so_line', 'in', timesheet_sols.ids), ('project_id', '!=', False)],
    ['so_line'],
    ['amount:sum', 'unit_amount:sum']
)
```

| Aspect | Detail |
|--------|--------|
| Domain filter | Only timesheet lines linked to these SOLs, and with a project |
| `project_id != False` | Excludes general analytic lines not associated with a project |
| Aggregations | `amount:sum` = total cost (negative), `unit_amount:sum` = total hours |
| Performance | Single grouped query vs N individual reads |

##### Weighted Average Cost Calculation

```python
mapped_sol_timesheet_amount = {
    so_line.id: - amount_sum / unit_amount_sum if unit_amount_sum else 0.0
    for so_line, amount_sum, unit_amount_sum in group_amount
}
```

For each SOL with timesheet entries:
- `amount_sum` is the sum of all negative costs (e.g., -$800 for 8 hours)
- `unit_amount_sum` is the total hours (e.g., 8)
- `-amount_sum / unit_amount_sum` = $800 / 8 = $100/hour
- If no timesheet entries exist, defaults to `product.standard_price` (which is 0 for services)

##### UoM Conversion

```python
product_uom = line.product_uom_id or line.product_id.uom_id
if product_uom != line.company_id.project_time_mode_id:
    product_cost = product_uom._compute_quantity(
        product_cost, line.company_id.project_time_mode_id
    )
```

If the SOL uses days (`product_uom_id = Days`) but timesheet is tracked in hours (`project_time_mode_id = Hours`), the cost is converted.

---

## L3: Cross-Model Relationships, Override Patterns, and Workflow Triggers

### Cross-Model Chain

```
account.analytic.line
    │
    ├── so_line: Many2one → sale.order.line (billable timesheet)
    ├── project_id: Many2one → project.project (the project tracking time)
    ├── amount: Float (negative = cost, e.g., -800.00)
    └── unit_amount: Float (hours worked, e.g., 8.0)
            │
            ▼ (sale_timesheet updates qty_delivered on SOL)
sale.order.line
    │
    ├── qty_delivered_method = 'timesheet'
    ├── analytic_line_ids: One2many → account.analytic.line
    ├── qty_delivered: computed from analytic lines
    └── purchase_price: computed by sale_timesheet_margin
            │
            ▼ (sale_margin computes)
    margin = price_subtotal - (qty_delivered * purchase_price)
```

### Override Pattern

The override in `sale_timesheet_margin` is more complex than typical because it needs to avoid **circular recomputation** and **overwriting manually-set values**. The pattern used:

```python
# Step 1: Identify SOLs that need special handling
service_non_timesheet = self.filtered(lambda sol: ...)
timesheet_sols = self.filtered(lambda sol: ...)

# Step 2: Call super() for all OTHER SOLs (excludes both groups)
super(SaleOrderLine, self - timesheet_sols - service_non_timesheet)._compute_purchase_price()

# Step 3: Process timesheet SOLs directly
if timesheet_sols:
    # ... compute cost from analytic lines ...
    line.purchase_price = computed_cost
```

This is an **interleaved override** — it partially processes the recordset, delegates the remainder to the parent, then processes a subset again. The `service_non_timesheet_sols` filter is the critical guard: it prevents timesheet entries from triggering a recomputation of purchase prices for `ordered_prepaid` service SOLs that already have a fixed cost.

### Workflow Trigger Sequence

```
Project Manager        Employee           System
    │                     │                  │
    │                     ├─ Log timesheet ──►│
    │                     │  (8 hrs, $10/hr)  │
    │                     │                   ├── Creates account.analytic.line
    │                     │                   │    amount = -80.00 (negative)
    │                     │                   │    unit_amount = 8.0
    │                     │                   │
    │                     │                   ├── sale_timesheet updates SOL:
    │                     │                   │    qty_delivered = 8.0
    │                     │                   │
    │                     │                   └── sale_timesheet_margin._compute_purchase_price()
    │                     │                        │
    │                     │                        ├── Reads analytic lines via _read_group
    │                     │                        ├── Computes: -(-80) / 8 = 10.0
    │                     │                        └── Sets: SOL.purchase_price = 10.0
    │                     │                        │
    │                     │                   └── sale_margin recomputes:
    │                     │                        margin = (8 * 100) - (8 * 10) = 720
```

### Filtering Rationale: `ordered_prepaid` Guard

The `service_non_timesheet_sols` filter exists because `ordered_prepaid` services have a different billing model:

- Customer pays upfront (e.g., 10 days billed in advance)
- `qty_delivered` is updated from timesheet entries
- But `purchase_price` should remain the product's `standard_price` (the prepaid rate)
- Timesheet entries should **not** change the cost for these SOLs

Without this filter, adding a timesheet entry to an `ordered_prepaid` SOL would overwrite the cost, which is wrong.

### Test Scenarios

**File:** `tests/test_sale_timesheet_margin.py`

**Test 1: `test_sale_timesheet_margin`**

- Creates a service product with `uom = Days`, `list_price = 1.0`, `service_type = timesheet`
- Sets `employee_manager.hourly_cost = 10`
- Logs 2 hours of timesheet on a confirmed SO
- Validates that `purchase_price` reflects the employee's hourly cost converted to the SOL's UoM (day)
- Expected cost: `uom_day._compute_quantity(10, company.project_time_mode_id)` — the employee's hourly rate converted to days

**Test 2: `test_no_recompute_purchase_price_not_timesheet`**

- Creates a project with a service product using `ordered_prepaid` policy
- Sets `standard_price = 2` on the product
- Manually sets `purchase_price = 3` on the SOL
- Confirms the SO, adds a timesheet entry with amount = 1
- Validates that `purchase_price` remains `3` (not overwritten)
- Also validates that a newly added SOL without timesheet correctly picks up `standard_price = 5`

---

## L4: Version Changes — Odoo 18 to Odoo 19

### Summary of Changes

`sale_timesheet_margin` has **minor implementation changes** in Odoo 19 related to UoM handling and company-scoped computation, but the functional behavior is preserved.

### Key Changes

#### 1. Company Scope in Compute Loop

```python
# Odoo 18 (inferred from context):
for line in timesheet_sols:
    # Uses whatever company context is active

# Odoo 19:
for line in timesheet_sols:
    line = line.with_company(line.company_id)
    # ... computes using line's specific company
```

In Odoo 19, the loop explicitly calls `with_company(line.company_id)` for each SOL. This ensures UoM conversion uses the correct company's time-tracking UoM (`project_time_mode_id`) and currency. This is a correctness fix for multi-company environments.

#### 2. UoM Conversion Logic

The UoM comparison logic:

```python
if product_uom != line.company_id.project_time_mode_id:
    product_cost = product_uom._compute_quantity(
        product_cost,
        line.company_id.project_time_mode_id
    )
```

This comparison and conversion is consistent with the Odoo 18→19 direction of making UoM and company-specific settings more explicit in computed fields.

### Unchanged Aspects

| Aspect | Status |
|--------|--------|
| `@api.depends` | `('analytic_line_ids.amount', 'qty_delivered_method')` — unchanged |
| `_read_group` approach | Still uses grouping for performance — unchanged |
| Weighted average formula | `-amount_sum / unit_amount_sum` — unchanged |
| `ordered_prepaid` guard | `service_non_timesheet_sols` filter — unchanged |
| Currency conversion call | `_convert_to_sol_currency()` — unchanged |
| Test scenarios | Both test cases remain valid |

### Filter Refinement in Odoo 19

The `service_non_timesheet_sols` filter added the `sol.purchase_price != 0` condition in newer versions. This prevents the case where an `ordered_prepaid` SOL with `purchase_price = 0` (never set) would incorrectly get recomputed. This is a defensive guard that improves edge-case handling.

### Dependency Compatibility

| Dependency | Odoo 18 | Odoo 19 | Notes |
|-----------|---------|---------|-------|
| `sale_margin` | Required | Required | `_compute_purchase_price` API unchanged |
| `sale_timesheet` | Required | Required | `analytic_line_ids` relation unchanged |
| `account.analytic.line` | Indirect | Indirect | `_read_group` API unchanged |

### Overall Assessment

`sale_timesheet_margin` is **largely stable** across Odoo 18→19. The one meaningful change is the explicit `with_company()` scoping in the compute loop, which is an improvement for multi-company setups. No migration work is required for existing data.
