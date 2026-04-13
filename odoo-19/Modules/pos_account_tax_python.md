---
type: module
module: pos_account_tax_python
tags: [odoo, odoo19, pos, tax, python, account, formula]
created: 2026-04-11
---

# Allow Custom Taxes in POS

**Module:** `pos_account_tax_python`  
**Path:** `odoo/addons/pos_account_tax_python/`  
**Category:** Accounting/Accounting  
**Version:** 1.0  
**Depends:** `account_tax_python`, `point_of_sale`  
**Auto-install:** True  
**License:** LGPL-3  
**Author:** Odoo S.A.

Link module that exposes Python-defined custom tax formulas to the Point of Sale client-side JavaScript. Without this module, taxes defined with `amount_type = 'code'` (Custom Formula) in `account_tax_python` would not be available in POS — their `formula` field is not serialized in the POS data load by default. This module adds `formula_decoded_info` to the POS assets bundle and the `_load_pos_data_fields` override.

---

## Architecture

This module contributes one model extension, one multi-inheritance test class, and asset declarations in the manifest. No data files.

```
pos_account_tax_python
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── account_tax.py         # _load_pos_data_fields() override
├── tests/
│   ├── __init__.py
│   └── test_taxes_tax_totals_summary.py  # Hybrid test
└── static/
    └── tests/                 # JS unit tests and tour tests
```

**Dependency chain:**

```
pos_account_tax_python
  ├── account_tax_python     # Provides 'code' amount_type, formula field, formula_decoded_info
  │    └── account           # Base tax model
  │
  └── point_of_sale         # Provides POS data loading infrastructure
       └── web               # Provides asset bundling
```

The `account_tax_python` module defines Python-based taxes with a `formula` field and a computed `formula_decoded_info` JSON field. `point_of_sale` loads tax records into the POS session via `_load_pos_data_fields`. This module bridges them by extending `_load_pos_data_fields` to include `formula_decoded_info`.

---

## L1 — account.tax Extension for Python Tax Formulas in POS

### What `account_tax_python` Provides

Before `pos_account_tax_python` does anything, `account_tax_python/models/account_tax.py` defines:

```python
class AccountTax(models.Model):
    _inherit = "account.tax"

    amount_type = fields.Selection(
        selection_add=[('code', "Custom Formula")],
        ondelete={'code': lambda recs: recs.write({'amount_type': 'percent', 'active': False})},
    )
    formula = fields.Text(
        string="Formula",
        default="price_unit * 0.10",
        help="Compute the amount of the tax.\n\n"
             ":param base: float, actual amount on which the tax is applied\n"
             ":param price_unit: float\n"
             ":param quantity: float\n"
             ":param product: A object representing the product\n"
    )
    formula_decoded_info = fields.Json(compute='_compute_formula_decoded_info')
```

`formula_decoded_info` is the key field. It is a computed JSON object containing:
- `js_formula`: the Python formula transformed to JavaScript-compatible syntax
- `py_formula`: the normalized Python formula
- `product_fields`: list of `product.product` field names accessed by the formula
- `product_uom_fields`: list of `uom.uom` field names accessed by the formula

### What `pos_account_tax_python` Adds

The POS client (JavaScript) needs to compute tax amounts at the PoS terminal without calling the server on every line change. The POS data load includes tax records with the fields in `_load_pos_data_fields(config)`. By default, `point_of_sale` does not include `formula_decoded_info` in its tax field list.

`pos_account_tax_python` overrides `_load_pos_data_fields` on `account.tax`:

```python
class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['formula_decoded_info']
```

This appends `formula_decoded_info` to the list of fields serialized and sent to the POS session. The POS JavaScript code can then read `tax.formula_decoded_info.js_formula` and `tax.formula_decoded_info.product_fields` to evaluate the tax client-side.

### Why Client-Side Tax Computation?

POS is a disconnected or semi-connected environment. When a cashier adds a line, the POS UI needs to display the tax amount and total without a server round-trip for every keystroke. The JS tax computation engine (in `account_tax_python/static/src/helpers/*.js`, bundled via this module's manifest) reads `formula_decoded_info` and evaluates the formula against the product's field values.

This is particularly important for **dynamic taxes** — taxes whose amount depends on a product attribute like `weight`, `volume`, or a custom field. For example, a shipping tax based on `product.weight * quantity` cannot be computed from a static percentage; it requires reading the product record at the POS.

---

## L2 — Field Types, Defaults, Constraints

### Fields Contributed by `pos_account_tax_python`

**None.** The module adds no new fields. It extends the `_load_pos_data_fields` method to include an existing field in the POS data payload.

### Fields Extended (in account_tax_python)

| Field | Type | Description |
|-------|------|-------------|
| `amount_type` | `Selection` | Adds `'code'` ("Custom Formula") option |
| `formula` | `Text` | Python expression; default `"price_unit * 0.10"` |
| `formula_decoded_info` | `Json` (computed) | Normalized formula + accessed fields for JS/Python eval |

### `formula_decoded_info` Structure

When `amount_type == 'code'` and formula is valid, the computed JSON contains:

```json
{
  "js_formula": "price_unit * 0.10",
  "py_formula": "price_unit * 0.10",
  "product_fields": ["weight", "volume"],
  "product_uom_fields": ["relative_factor"]
}
```

The `product_fields` list is derived from `normalize_formula` in `account_tax_python/tools/formula_utils.py`, which parses the formula's Python AST to extract which `product.` and `uom.` attribute accesses appear.

**Example: weight-based tax**

Formula: `product.weight * quantity * 0.05`

Result:
```json
{
  "js_formula": "product.weight * quantity * 0.05",
  "py_formula": "product.weight * quantity * 0.05",
  "product_fields": ["weight"],
  "product_uom_fields": []
}
```

The POS JS code loads `product.weight` from its cached product data and computes the tax.

### Constraints

`account_tax_python` defines `@api.constrains('amount_type', 'formula')` for formula validation. `pos_account_tax_python` does not add constraints — it only exposes an already-validated field to the POS.

### `_load_pos_data_fields` Override Contract

```python
@api.model
def _load_pos_data_fields(self, config):
    return super()._load_pos_data_fields(config) + ['formula_decoded_info']
```

The base method (from `account` or `account_tax_python`) returns a list of field names. This module appends `formula_decoded_info`. The result is used by `pos.load.mixin` to serialize these fields for the POS session's tax cache.

---

## L3 — cross_model, Override Pattern, Workflow Trigger

### Cross-Module Data Flow

```
account.tax (amount_type='code', formula='product.weight * quantity')
  │
  ▼ @api.depends('formula')
_compute_formula_decoded_info()
  │
  ▼ produces JSON with js_formula, product_fields, product_uom_fields
formula_decoded_info
  │
  ▼ _load_pos_data_fields() override (this module)
  │
  ▼ included in POS tax cache data
POS session (JavaScript)
  │
  ▼ reads tax.formula_decoded_info.js_formula
  ▼ reads product.weight from POS product cache
POS Order Line (client-side tax computation)
  │
  ▼ sends to server on order finalization
pos.order.line (price_subtotal_incl, tax_ids)
```

### Override Pattern

**File:** `models/account_tax.py`

```python
class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['formula_decoded_info']
```

**Inheritance chain for `_load_pos_data_fields`:**

```
account.tax (base, point_of_sale/models/account_tax.py)
  │
  └── account_tax_python/models/account_tax.py
        └── (no _load_pos_data_fields override here)
              │
              └── pos_account_tax_python/models/account_tax.py
                    └── _load_pos_data_fields() → appends formula_decoded_info
```

The base `point_of_sale` defines `_load_pos_data_fields` on `account.tax`. `account_tax_python` doesn't override it. `pos_account_tax_python` extends it.

### What Gets Loaded into POS

The base `_load_pos_data_fields` from `point_of_sale` returns fields like:
- `id`, `name`, `amount`, `amount_type`, `include_base_amount`, `price_include`, ` Sequences of tax lines`, etc.

`pos_account_tax_python` adds `formula_decoded_info`. With this field in the payload, POS can filter for `amount_type == 'code'` taxes and handle them with the JS formula evaluator.

### Manifest Asset Declarations

```python
'assets': {
    'point_of_sale._assets_pos': [
        'account_tax_python/static/src/helpers/*.js',
    ],
    'web.assets_unit_tests': [
        'pos_account_tax_python/static/tests/unit/data/**/*'
    ],
    'web.assets_tests': [
        'pos_account_tax_python/static/tests/tours/**/*',
    ],
},
```

**`point_of_sale._assets_pos`:** Adds `account_tax_python`'s JS helper files (`*.js` in `static/src/helpers/`) to the POS asset bundle. These helpers contain the client-side tax formula evaluator that mirrors `_eval_tax_amount_formula` in Python.

**`web.assets_unit_tests` / `web.assets_tests`:** Standard Odoo asset declarations for JS tests. The `static/tests/` directory contains JS unit tests and tour tests for the tax computation logic in the POS UI.

### Workflow Trigger

There is no button, wizard, or cron. The flow is:

1. **Tax record exists** with `amount_type='code'` and valid `formula`.
2. **POS session opened** → `pos.config` loads tax data via `_load_pos_data_fields`.
3. **Tax included in session** → `formula_decoded_info` JSON is sent to the POS client.
4. **POS order line created** with this tax → JS evaluates `js_formula` against `product.*` and `quantity` from the POS product cache.
5. **Line finalized** → server receives `price_subtotal_incl` from POS, taxes are verified server-side using `_eval_tax_amount_formula`.

---

## L4 — Odoo 18 to 19 Changes

### Changes in `pos_account_tax_python`

There are **no functional code changes** between Odoo 18 and Odoo 19. The model extension file is identical in both versions.

### The JS Helper Files

The `account_tax_python/static/src/helpers/*.js` file referenced in the manifest asset bundle contains the JavaScript mirror of `_eval_tax_amount_formula`. This file is part of `account_tax_python` itself (not `pos_account_tax_python`). The asset declaration in `pos_account_tax_python` is what causes it to be included in the POS frontend bundle.

In Odoo 18, asset bundling may have been structured differently. The explicit addition of these helpers to `point_of_sale._assets_pos` via the manifest is the mechanism that ensures the formula evaluator is available in POS.

### JSON Field for `formula_decoded_info`

The `formula_decoded_info` field uses Odoo's `Json` field type. This is standard in Odoo 16+. The field is:
- **Computed:** recalculated when `formula` changes via `@api.depends('formula')`.
- **Not stored:** The JSON is recomputed on each read, not persisted to the DB.
- **Safe for client:** JSON serialization is safe for transfer to the POS JS engine.

### Tax Computation Synchronization

A critical invariant maintained across Odoo 18→19 is that the Python `_eval_tax_amount_formula` and the JS evaluator in `account_tax_python/static/src/helpers/*.js` produce identical results for the same inputs. `account_tax_python/models/account_tax.py` includes a comment:

```
[!] Mirror of the same method in account_tax.js.
PLZ KEEP BOTH METHODS CONSISTENT WITH EACH OTHERS.
```

This module (`pos_account_tax_python`) does not maintain either side of this mirror — it only ensures the data (`formula_decoded_info`) is available in POS.

### `_load_pos_data_fields` as Extension Point

The `_load_pos_data_fields` pattern in Odoo 19 is the standard way to extend POS data loading for custom tax types. `pos_account_tax_python` demonstrates this pattern: adding a single field name to the returned list.

---

## Tests

### `TestTaxesTaxTotalsSummaryAccountTaxPython`

**File:** `tests/test_taxes_tax_totals_summary.py`

A multi-inheritance test class combining two test mixins:

```python
@tagged('post_install', '-at_install', 'post_install_l10n')
class TestTaxesTaxTotalsSummaryAccountTaxPython(TestTaxCommonPOS, TestTaxesTaxTotalsSummary):
```

- **`TestTaxCommonPOS`** — from `point_of_sale.tests.test_frontend`; provides POS session management, POS order creation, and `start_pos_tour`.
- **`TestTaxesTaxTotalsSummary`** — from `account.tests.test_taxes_tax_totals_summary`; provides `python_tax()` helper and tax totals assertion helpers.

This hybrid design tests the integration end-to-end: POS creates an order with a Python tax, and the resulting `pos.order` and `account.move` (invoice) are verified for correct totals.

### `test_point_of_sale_custom_tax_with_extra_product_field`

```python
def test_point_of_sale_custom_tax_with_extra_product_field(self):
    assert 'weight' not in self.env['product.template']._load_pos_data_fields(self.main_pos_config)
    # Confirms weight is NOT in default POS product fields (not needed for normal taxes)

    tax = self.python_tax('product.weight * quantity')
    # Creates a tax with formula: product.weight * quantity

    document_params = self.init_document(
        lines=[{'price_unit': 200.0, 'quantity': 10.0, 'tax_ids': tax}],
    )
    document = self.populate_document(document_params)

    self.ensure_products_on_document(document, 'product_1')
    product = document['lines'][0]['product_id']
    product.weight = 4.2
    # Sets weight on the product (simulates POS UI product editing)

    expected_values = {
        'base_amount_currency': 2000.00,      # 200.0 * 10.0
        'tax_amount_currency': 42.0,          # 4.2 * 10.0 = 42.0 (weight * qty)
        'total_amount_currency': 2042.0,     # base + tax
    }

    with self.with_new_session(user=self.pos_user) as session:
        self.start_pos_tour('test_point_of_sale_custom_tax_with_extra_product_field')
        order = self.env['pos.order'].search([('session_id', '=', session.id)])
        self.assert_pos_order_totals(order, expected_values)
        self.assertTrue(order.account_move)
        self.assert_invoice_totals(order.account_move, expected_values)
```

**What it tests:**
1. `weight` field is not in the default POS product data load (asserted to confirm it's NOT there by default).
2. A Python tax can reference `product.weight` in its formula.
3. When `weight=4.2` is set on the product, the tax amount becomes `4.2 * 10 = 42` (not a flat percentage).
4. The computed tax matches on the POS order record.
5. The resulting invoice (via `order.account_move`) also has correct totals.

### `test_point_of_sale_custom_tax_with_extra_product_uom_field`

```python
def test_point_of_sale_custom_tax_with_extra_product_uom_field(self):
    assert 'relative_factor' not in self.env['uom.uom']._load_pos_data_fields(self.main_pos_config)
    # Confirms relative_factor is NOT in default POS UoM fields

    tax = self.python_tax('uom.relative_factor * quantity')
    # Formula: uom.relative_factor * quantity

    document_params = self.init_document(...)
    document = self.populate_document(document_params)

    self.ensure_products_on_document(document, 'product_1')
    product = document['lines'][0]['product_id']
    product.uom_id = self.env['uom.uom'].create({
        'name': "test_uom_field",
        'relative_uom_id': self.env.ref('uom.product_uom_unit').id,
        'relative_factor': 4.2,
    })
```

**What it tests:**
- The `relative_factor` field on `uom.uom` is accessed via `uom.relative_factor` in a tax formula.
- A custom UoM with `relative_factor=4.2` produces tax `4.2 * 10 = 42` on a qty-10 order.
- The same pattern as the weight test, but for the UoM model.

**Key assertion `assert 'weight' not in ..._load_pos_data_fields(...)`:** These pre-assertions verify that these fields are NOT part of the default POS product/UoM data load. Without `pos_account_tax_python`, the custom tax formula could not access them because the POS wouldn't have loaded those fields for the product. By including `formula_decoded_info` in `_load_pos_data_fields`, the JS code gets access to the formula's `product_fields` list, which tells it which product attributes to fetch — but only if `account_tax_python` had the `formula_decoded_info` computed correctly.

### Why Two Assertions About Missing Fields?

`'weight' not in _load_pos_data_fields` and `'relative_factor' not in _load_pos_data_fields` confirm that:
1. Without this module, these fields wouldn't be loaded (they're not in default POS product/UoM fields).
2. `formula_decoded_info` carries the `product_fields` list, which tells the JS engine to include `weight` when fetching product data for this tax.
3. The test confirms the integration works end-to-end.

---

## Edge Cases and Failure Modes

### Tax formula references a field not loaded in POS

If a Python tax formula references `product.x_custom_field` but that field is not in the POS product data load, the JS evaluator will get `undefined` for that field value. The formula will likely produce `NaN` or incorrect results.

**Mitigation:** `formula_decoded_info['product_fields']` tells the POS exactly which product fields to load. If the formula references a field, `formula_decoded_info` includes it. The `_load_pos_data_fields` override only exposes `formula_decoded_info` — the field content (including the `product_fields` list) comes from `account_tax_python`'s computation.

### Formula with syntax errors

`account_tax_python`'s `@api.constrains` on `formula` prevents saving invalid Python formulas. The formula is validated server-side before save. If a formula passes Python validation but the JS evaluator has a subtle difference (e.g., Python division vs. JS floating point), the server-side `_eval_tax_amount_formula` would produce a different result than the client-side JS evaluation.

**Mitigation:** The formula normalization (`normalize_formula`) in `account_tax_python/tools/formula_utils.py` ensures both Python and JS evaluate the same expression. Division uses floating-point arithmetic in both environments.

### Multi-company tax with formula

In multi-company environments, tax records are company-specific. The `_load_pos_data_fields` override runs per `account.tax` record and includes `formula_decoded_info` for all taxes matching the POS config's company context. No additional filtering needed.

---

## See Also

- [Modules/account_tax_python](odoo-18/Modules/account_tax_python.md) — Python-defined tax formulas (`amount_type='code'`)
- [Modules/point_of_sale](odoo-18/Modules/point_of_sale.md) — POS data loading infrastructure (`_load_pos_data_fields`)
- [Modules/account](odoo-18/Modules/account.md) — Base tax model (`account.tax`)
- [Modules/pos_sale](odoo-18/Modules/pos_sale.md) — POS sale integration (order lines, tax computation)
- [Modules/account](odoo-18/Modules/account.md) — Tax computation engine (`_eval_tax_amount_formula`)
