# Stock Account Module (Inventory Valuation)

**Path:** `odoo/addons/stock_account/`
**Manifest:** `__manifest__.py` with `depends: ['stock', 'account']`, `auto_install: True`
**Category:** Supply Chain/Inventory
**Application:** No (framework module)

> The `stock_account` module connects stock movements to accounting. It creates journal entries for inventory valuation, tracks stock value in real-time, and provides valuation reports. It auto-installs when both `stock` and `account` are installed.

---

## Models

### Extended Models (14 files)

| Model | Extends | File | Key Addition |
|-------|---------|------|-------------|
| `product.template` | `_inherit` | `models/product.py` | `cost_method`, `valuation`, `lot_valuated` fields |
| `product.product` | `_inherit` | `models/product.py` | `avg_cost`, `total_value` computed fields |
| `stock.quant` | `_inherit` | `models/stock_quant.py` | `value`, `currency_id`, `accounting_date` |
| `stock.move` | `_inherit` | `models/stock_move.py` | `value`, `value_manual`, `account_move_id` |
| `stock.move.line` | `_inherit` | `models/stock_move_line.py` | (extensible hook) |
| `stock.picking` | `_inherit` | `models/stock_picking.py` | (extensible hook) |
| `stock.lot` | `_inherit` | `models/stock_lot.py` | `total_value` |
| `stock.location` | `_inherit` | `models/stock_location.py` | `_should_be_valued()` |
| `account.move` | `_inherit` | `models/account_move.py` | `stock_valuation_layer_ids` |
| `account.move.line` | `_inherit` | `models/account_move_line.py` | `stock_valuation_layer_ids` |
| `account.account` | `_inherit` | `models/account_account.py` | `asset_model` for stock valuation |
| `res.company` | `_inherit` | `models/res_company.py` | Valuation accounts, cost method |
| `res.config.settings` | `_inherit` | `models/res_config_settings.py` | Valuation configuration |
| `account.chart.template` | `_inherit` | `models/account_chart_template.py` | Valuation account setup |

### New Models

| Model | File | Purpose |
|-------|------|---------|
| `stock.valuation.layer` | `models/stock_valuation_layer.py` | Tracks each inventory valuation change (AVCO/FIFO) |
| `product.value` | `models/product_value.py` | Manual valuation adjustments |
| `stock_account.stock.valuation.report` | `report/stock_valuation_report.py` | Stock valuation PDF report |
| `stock_account.stock.avco.audit.report` | `report/stock_avco_audit_report.py` | AVCO audit trail |
| `stock_account.stock.forecasted` | `report/stock_forecasted.py` | Valuation-aware forecast |

---

## L1: Valuation Fields, Move Line Creation

### Product Valuation Configuration

**On `product.template`:**

```python
cost_method = fields.Selection(
    string="Cost Method",
    selection=[
        ('standard', "Standard Price"),
        ('fifo', "First In First Out (FIFO)"),
        ('average', "Average Cost (AVCO)"),
    ],
    compute='_compute_cost_method',
    # Resolved from: product.categ_id.property_cost_method
    # or company cost_method fallback
)

valuation = fields.Selection(
    string="Valuation",
    selection=[
        ('periodic', 'Periodic (at closing)'),
        ('real_time', 'Perpetual (at invoicing)'),
    ],
    compute='_compute_valuation',
    # Resolved from: product.categ_id.property_valuation
    # or company.inventory_valuation fallback
)

lot_valuated = fields.Boolean(
    string="Valuation by Lot/Serial",
    compute='_compute_lot_valuated', store=True,
    # If True, valuation is computed per-lot rather than per-product
)
```

**On `product.product`:**

```python
avg_cost = fields.Monetary(
    string="Average Cost",
    compute='_compute_value',
    compute_sudo=True,
    currency_field='company_currency_id')

total_value = fields.Monetary(
    string="Total Value",
    compute='_compute_value',
    compute_sudo=True,
    currency_field='company_currency_id')
```

### Cost Method Resolution Hierarchy

```
product.categ_id.property_cost_method
    OR
company.cost_method (res.company default)
```

```
product.categ_id.property_valuation
    OR
company.inventory_valuation (res.company default)
```

### Company-Level Configuration (res.company)

```python
inventory_valuation = fields.Selection([
    ('periodic', 'Periodic (at closing)'),
    ('real_time', 'Perpetual (at invoicing)'),
], default='periodic')

cost_method = fields.Selection([
    ('standard', "Standard Price"),
    ('fifo', "First In First Out (FIFO)"),
    ('average', "Average Cost (AVCO)"),
], default='standard')

account_stock_valuation_id = fields.Many2one(
    'account.account', string='Stock Valuation Account')
account_stock_journal_id = fields.Many2one(
    'account.journal', string='Stock Journal')
account_production_wip_account_id = fields.Many2one(
    'account.account', string='Production WIP Account')
```

---

## L2: AVCO/FIFO/Standard Price, Valuation at Delivery vs Receipt, Anglo-Saxon

### Costing Methods

#### Standard Price

- Fixed cost per unit defined on `product.product.standard_price`
- All receipts and issues valued at this fixed price
- Variance tracked separately
- Best for: stable, predictable products

#### FIFO (First In First Out)

- Issues valued at the cost of the oldest receipt
- Layers tracked per `stock.valuation.layer`
- Remaining quantity valued at most recent receipts
- Best for: perishable goods, products with expiry

#### AVCO (Average Cost / Average)

- Issue price = weighted average of all receipts
- `avg_cost` = total_value / quantity
- Recalculated on every receipt
- Best for: commodities, products with fluctuating costs

### Valuation at Receipt vs Delivery

**Incoming Moves (Receipts):**

| Cost Method | Effect |
|-------------|--------|
| Standard | Value = `product.standard_price` × qty |
| FIFO | Creates valuation layer at receipt price |
| AVCO | Updates `avg_cost`, creates layer at receipt price |

**Outgoing Moves (Deliveries):**

| Cost Method | Effect |
|-------------|--------|
| Standard | Value = `product.standard_price` × qty |
| FIFO | Consumes oldest layers, remaining_value decreases |
| AVCO | Value = `avg_cost` × qty, layer consumed |

### Anglo-Saxon (Real-Time Valuation)

When `inventory_valuation = 'real_time'`:

```
Receipt (PO received) → Creates account.move immediately
  Debit:  Stock Valuation Account
  Credit: AP/Pending Bill Account

Delivery (SO delivered) → Creates account.move immediately
  Debit:  COGS Account
  Credit: Stock Valuation Account
```

When `inventory_valuation = 'periodic'`:

```
No entries until period close
Period close → action_close_stock_valuation()
  Creates closing entries for remaining stock value
```

### Valuation Layer (stock.valuation.layer)

Tracks each inventory movement's value:

```python
class StockValuationLayer(models.Model):
    _name = 'stock.valuation.layer'
    _description = 'Stock Valuation Layer'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', 'Product')
    quantity = fields.Float('Quantity')
    unit_cost = fields.Float('Unit Cost')
    value = fields.Float('Value')
    remaining_qty = fields.Float('Remaining Quantity')
    remaining_value = fields.Float('Remaining Value')
    account_move_id = fields.Many2one('account.move')
    stock_move_id = fields.Many2one('stock.move')
    company_id = fields.Many2one('res.company')
    description = fields.Char()
    create_date = fields.Datetime()
```

**Layer Flow for AVCO:**

```
Receipt 100 units @ $10:
  Layer 1: qty=100, unit_cost=10, value=1000, remaining_qty=100

Receipt 100 units @ $12:
  AVCO = (1000 + 1200) / 200 = $11
  Layer 2: qty=100, unit_cost=11, value=1100, remaining_qty=100

Delivery 150 units:
  Consume Layer 1: 100 units @ $10 = $1000
  Consume Layer 2: 50 units @ $11 = $550
  Total delivery value: $1550
  Remaining: 50 units @ $11 = $550
```

**Layer Flow for FIFO:**

```
Receipt 100 units @ $10:
  Layer 1: qty=100, unit_cost=10, value=1000, remaining_qty=100

Delivery 50 units:
  Consume Layer 1: 50 units @ $10 = $500
  Layer 1 updated: qty=100, remaining_qty=50
  Remaining: 50 units @ $10 = $500
```

---

## L3: Automatic Valuation Entries, Cost Layer Management

### Automatic Valuation Entry Creation

Valuation entries are created when `stock.move` is validated (`action_done()`).

**Entry Creation Flow:**

```
stock.move.action_done()
  → _action_done()
      → _create_valuation_entry()
          → account.move.create({
                'ref': move.reference,
                'line_ids': [
                    ('debit', stock_valuation_account, amount),
                    ('credit', stock_input/output_account, amount),
                ]
            })
          → stock.valuation.layer.create({...})
```

**Journal Entry Lines:**

For **incoming** (receipt):
```
Debit:  Stock Valuation Account     (asset increases)
Credit: Stock Interim Account        (pending receipt)
```

For **outgoing** (delivery):
```
Debit:  COGS / Cost of Delivery     (expense)
Credit: Stock Valuation Account       (asset decreases)
```

### Cost Layer Management

The `stock.valuation.layer` model manages cost layers:

```python
# Key methods:
layer._consume(layer, quantity_to_consume)
# Decrements remaining_qty, creates counterpart layer

layer._run_valuation(move)
# Creates valuation entry for a stock.move

product._update_standard_price()
# Recomputes standard price and creates adjustment layer
```

**Adjustment Entries:**

When manual valuation is changed:

```python
# Via stock.move action_adjust_valuation()
move._create_valuation_entry(
    move.product_id.standard_price * move.quantity,
    'Manual adjustment'
)
```

### Stock Location Valuation Filter

`stock.location._should_be_valued()` determines whether a location is included in valuation:

```python
def _should_be_valued(self):
    """Locations with usage internal/inventory/production are valued"""
    return self.usage in ('internal', 'inventory', 'production')
```

**Exclusions:**
- `supplier` locations (vendor side)
- `customer` locations (already delivered)
- `view` locations (virtual)
- `transit` locations (inter-company, handled separately)

### Accounting Date Control

```python
# On stock.quant (stock_account extension)
accounting_date = fields.Date(
    'Accounting Date',
    help="Date at which the accounting entries will be created "
         "in case of automated inventory valuation. "
         "If empty, the inventory date will be used."
)
```

This allows backdating valuation entries during inventory counts.

---

## L4: Performance, Landed Costs, Odoo 18→19 Changes

### Valuation Performance

**Batched Entry Creation:**

Instead of creating one `account.move` per line, Odoo 19 batches valuation entries:

```python
# In _create_valuation_entry, grouped by:
# - product_id
# - stock_move_id
# - company_id
# Reduces number of journal entries
```

**Layer Consolidation:**

When multiple moves affect the same product at the same price, layers are consolidated:
```python
if layer.remaining_qty == 0:
    layer.unlink()  # Clean up fully consumed layers
```

**Read Group Optimization:**

`stock.quant._read_group_select` and `_read_group_postprocess_aggregate` are overridden to aggregate `value` across quants efficiently, avoiding N+1 queries on valuation reports.

### Landed Costs (stock_landed_costs module)

Landed costs (shipping, duties, insurance) can be allocated to product costs:

```python
# In stock_landed_cost (separate module):
class StockLandedCost(models.Model):
    _name = 'stock.landed.cost'

    picking_ids = fields.Many2many('stock.picking')
    cost_lines = fields.One2many('stock.landed.cost.lines', 'cost_id')
    valuation_adjustment_lines = fields.One2many(...)
    account_move_id = fields.Many2one('account.move')

    def button_validate(self):
        # Creates valuation entries for landed costs
        self._create_account_move()
```

**Landed Cost Methods:**
- Equal quantity split
- By quantity (volume/weight)
- By current cost
- By custom formula

### Odoo 18 → 19 Changes in Stock Account

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Valuation layers | Basic layer tracking | Enhanced with `lot_valuated` per-product |
| AVCO calculation | Per-product | Per-lot when `lot_valuated=True` |
| Stock valuation report | `stock.valuation.report` | Enhanced with accounting date |
| Account move links | Direct on move | Via `stock_valuation_layer_ids` m2m |
| Product value | `product.product` fields | Extended with `product.value` model |
| Periodic close | Basic | `action_close_stock_valuation()` with full GL reconciliation |
| Cost method display | On template | Resolved from category/company with search support |

### Stock Valuation Report

The `stock_account.stock.valuation.report` generates a PDF showing:

```python
# Report sections:
- Company header
- Ending Stock value (by account)
- Initial Balance (at start of period)
- Inventory Loss (adjustments)
- Period movements

# Data sources:
company.stock_value()           # Current inventory value
company.stock_accounting_value() # GL balance at period start
company._get_location_valuation_vals()  # Inventory loss account
```

---

## Account Configuration

### Required Accounts

| Account | Purpose | Direction |
|---------|---------|-----------|
| Stock Valuation | Values inventory | Entry point |
| Stock Interim (Receipt) | Pending receipt | Credit on receipt |
| Stock Interim (Delivery) | Pending delivery | Debit on delivery |
| COGS | Cost of goods sold | Debit on delivery |
| Production WIP | Work in progress | Manufacturing |
| Price Difference | STD vs actual | Variance tracking |

### Account Configuration via Product Category

```python
# product.category fields (stock_account extension):
property_stock_valuation_account_id  # Stock Valuation Account
property_stock_journal              # Stock Journal for entries
property_cost_method                # Per-category costing
property_valuation                  # Per-category valuation method
```

### Configuration Order

1. **Company level** (`res.company`):
   - `inventory_valuation`: real_time or periodic
   - `cost_method`: standard, fifo, average
   - Default accounts

2. **Category level** (`product.category`):
   - Override `cost_method` per category
   - Override `valuation` per category
   - Specific valuation account

3. **Product level** (`product.product`):
   - `standard_price` for standard cost
   - Inherits cost_method and valuation from category/company

---

## Key Methods

### Stock Move Valuation

```python
class StockMove(models.Model):
    _inherit = "stock.move"

    def _create_valuation_entry(self, credit_account, debit_account):
        """Creates account.move for this stock move valuation"""
        # Standard debit/credit entry to valuation accounts

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, ...):
        """Prepares vals dict for account.move.create()"""

    def _should_be_valued(self):
        """Check if this move should create valuation entries"""
        # Respects location usage (internal/inventory/production)

    def _is_in(self):
        """Is this an incoming (valued) move?"""
        # Uses location_dest_id usage

    def _is_out(self):
        """Is this an outgoing (valued) move?"""
        # Uses location_id usage
```

### Stock Quant Valuation

```python
class StockQuant(models.Model):
    _inherit = "stock.quant"

    value = fields.Monetary(
        'Value', compute='_compute_value',
        groups='stock.group_stock_manager')

    def _should_exclude_for_valuation(self):
        """Returns True for quants owned by third parties"""
        return self.owner_id and self.owner_id != self.company_id.partner_id

    def _compute_value(self):
        """Computes quant value based on costing method"""
        # For lot_valuated products: lot.total_value / lot.product_qty
        # Otherwise: product.total_value / product.qty_available
```

### Periodic Valuation Close

```python
class ResCompany(models.Model):
    _inherit = "res.company"

    def action_close_stock_valuation(self, at_date=None, auto_post=False):
        """Creates closing entries for periodic valuation"""
        # Debit: Stock Valuation (current value)
        # Credit: P&L ending inventory
        # At period start: reverse
```

---

## Related Modules

| Module | Dependency | Purpose |
|--------|-----------|---------|
| `stock_account` | `stock` + `account` | Core valuation |
| `stock_landed_costs` | `stock_account` | Allocate shipping/duties to cost |
| `stock_accountant` | `stock_account` | Accountant dashboard integration |
| `sale_stock` | `stock` + `sale` | Sale delivery valuation |
| `purchase_stock` | `stock` + `purchase` | Purchase receipt valuation |
| `mrp_stock` | `stock` + `mrp` | Production consumption valuation |
| `l10n_*` | (localization) | Country-specific valuation accounts |

---

## Reports

| Report | Model | Purpose |
|--------|-------|---------|
| Stock Valuation | `stock_account.stock.valuation.report` | PDF: opening/closing value by account |
| AVCO Audit | `stock_account.stock.avco.audit.report` | AVCO layer audit trail |
| Stock Forecasted | `stock_account.stock.forecasted` | Valuation-aware forecast |
| Invoice Report | Standard account | Invoice with stock reference |

---

## Odoo 18 → 19: Key Valuation Architecture Changes

### 1. Lot-Valuated Products

Odoo 19 introduces per-lot valuation for products where `lot_valuated=True`:

```python
# Before (Odoo 18): All products valued per-product
quant.value = quant.quantity * product.avg_cost

# After (Odoo 19): Lot-valuted products valued per-lot
if quant.product_id.lot_valuated:
    quant.value = quant.quantity * quant.lot_id.avg_cost
```

### 2. Valuation Layer Refinements

- `stock.valuation.layer` now tracks `remaining_value` explicitly
- Layers for the same product/cost are consolidated automatically
- Manual valuation adjustments via `product.value` model

### 3. Accounting Date on Quants

The `accounting_date` field on `stock.quant` allows backdating valuation entries:

```
Physical count date: Jan 5, 2024
Accounting date: Dec 31, 2023
→ Valuation entry dated Dec 31, 2023
```

### 4. Periodic Close Enhanced

```python
action_close_stock_valuation(at_date)
# Now supports:
# - Multi-company: entries per company
# - GL reconciliation: matches to inventory GL account
# - Draft posting: allows review before posting
```
