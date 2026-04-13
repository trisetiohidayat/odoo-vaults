---
type: module
module: account_tax_python
tags: [odoo, odoo19, account, invoicing, tax, python]
created: 2026-04-06
updated: 2026-04-11
---

# Define Taxes as Python Code

## Overview

| Property | Value |
|----------|-------|
| **Name** | Define Taxes as Python Code |
| **Technical** | `account_tax_python` |
| **Category** | Accounting/Accounting |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `account` |
| **Source** | `odoo/addons/account_tax_python/` |

## Description

Adds a `code` option to the `account.tax` `amount_type` selection (labeled **Custom Formula**). When selected, the tax amount is computed by evaluating an arbitrary Python expression rather than a fixed percentage or fixed amount. The formula can reference `price_unit`, `quantity`, `product` (product.product), `uom` (uom.uom), and `base`. Both Python (server-side) and JavaScript (frontend computation preview) implementations must stay in sync; this is enforced by comments and by an AST transformation layer that normalizes `product.field` to `product['field']` subscript notation for cross-language compatibility.

## Architecture

```
account_tax_python/
├── models/
│   └── account_tax.py              # Extends account.tax: amount_type='code', formula
├── tools/
│   └── formula_utils.py           # AST rewriter + validator (shared library)
├── static/src/helpers/
│   └── account_tax.js              # JS-side formula evaluation (mirrors Python)
├── tests/
│   ├── common.py                  # TestTaxCommonAccountTaxPython base class
│   └── test_taxes_computation.py  # Full test suite
└── views/
    └── account_tax_views.xml        # Form extension: shows formula field
```

---

## L1: Module Purpose and Scope

This module enables dynamic, product-driven tax computation. Instead of a flat percentage or fixed amount, the tax amount is computed by a Python expression that can read product attributes. Examples:

```python
# Volume-based tax: price per liter
product.volume * quantity * 0.35

# Tiered tax: minimum of two calculations
max(quantity * price_unit * 0.21, quantity * 4.17)

# Product attribute driven
product.volume > 100 and 10 or 5

# UoM-aware: use the relative conversion factor
uom.relative_factor

# Compound: base amount + per-unit
(base * 0.05) + (quantity * 0.50)
```

The formula is validated at tax creation/update time via AST analysis, ensuring only safe, JS-compatible expressions are stored. Both Python (Odoo server) and JavaScript (web client) evaluate the same normalized formula.

---

## L2: Field Types, Defaults, Constraints

### `account.tax` Extension

**File:** `models/account_tax.py`

```python
class AccountTax(models.Model):
    _inherit = "account.tax"
```

#### New Selection Option for `amount_type`

The `amount_type` field on `account.tax` is extended with a new option:

```python
amount_type = fields.Selection(
    selection_add=[('code', "Custom Formula")],
    ondelete={'code': lambda recs: recs.write({'amount_type': 'percent', 'active': False})},
)
```

**Ondelete behavior:** When a tax with `amount_type='code'` is uninstalled (module upgrade), it is converted to `'percent'` type and deactivated rather than deleted. This preserves the tax record and prevents data loss.

#### New Fields

| Field | Type | Required | Default | Storage | Description |
|-------|------|---------|---------|---------|-------------|
| `amount_type` option `code` | Selection | — | — | DB | Adds "Custom Formula" option |
| `formula` | `Text` | Conditional | `"price_unit * 0.10"` | DB | Python expression; required when `amount_type='code'` |
| `formula_decoded_info` | `Json` | — | `None` | Compute | Normalized formula, accessed product/UoM fields |

#### `formula` Field

```python
formula = fields.Text(
    string="Formula",
    default="price_unit * 0.10",
    help="Compute the amount of the tax.\n\n"
         ":param base: float, actual amount on which the tax is applied\n"
         ":param price_unit: float\n"
         ":param quantity: float\n"
         ":param product: A object representing the product\n"
)
```

#### `formula_decoded_info` — Computed Json

```python
formula_decoded_info = fields.Json(compute='_compute_formula_decoded_info')
```

Computed whenever `formula` changes. Contains:

```python
{
    'js_formula': 'price_unit * 0.10',       # Normalized Python formula
    'py_formula': 'price_unit * 0.10',       # Same (already normalized)
    'product_fields': ['volume', 'weight'],   # product.product fields accessed
    'product_uom_fields': ['relative_factor'], # uom.uom fields accessed
}
```

#### Constraints

```python
@api.constrains('amount_type', 'formula')
def _check_amount_type_code_formula(self):
    for tax in self:
        if tax.amount_type == 'code':
            self._check_and_normalize_formula(tax.formula)
```

Triggered on create/write when `amount_type='code'`. Raises `ValidationError` if the formula fails AST validation.

### `formula_decoded_info` Computation

```python
@api.depends('formula')
def _compute_formula_decoded_info(self):
    for tax in self:
        if tax.amount_type != 'code':
            tax.formula_decoded_info = None
            continue

        py_formula, accessed_fields = self._check_and_normalize_formula(tax.formula)

        tax.formula_decoded_info = {
            'js_formula': py_formula,
            'py_formula': py_formula,
            'product_fields': list(accessed_fields['product.product']),
            'product_uom_fields': list(accessed_fields['uom.uom']),
        }
```

The formula is parsed, normalized, and validated in a single pass. The normalized form replaces `product.field` with `product['field']` (subscript notation) for cross-language compatibility.

### Formula AST Processing (`tools/formula_utils.py`)

**Two-pass pipeline:**

**Pass 1 — `ProductUomFieldRewriter` (NodeTransformer):**
- Rewrites `product.field` → `product['field']` subscripts
- Rewrites `product['field']` (already subscript) with validation
- Collects all accessed field names per model (`product.product`, `uom.uom`)
- Used for both Python and JavaScript evaluation

**Pass 2 — `TaxFormulaValidator` (NodeVisitor):**
Whitelisted AST node types only:

| Node Type | Allowed |
|-----------|---------|
| `ast.Expression` | Root |
| `ast.Name` | Only: `price_unit`, `quantity`, `base`, `product`, `uom` |
| `ast.Constant` | Only: `int`, `float`, `None` |
| `ast.BinOp` | `+`, `-`, `*`, `/` |
| `ast.BoolOp` | `and`, `or` |
| `ast.Compare` | `<`, `<=`, `>`, `>=`, `==`, `!=` |
| `ast.UnaryOp` | `+`, `-` (unary) |
| `ast.Call` | Only: `min()`, `max()` with positional args |
| `ast.Subscript` | Only: `product['field']` or `uom['field']` with string literal |

**Forbidden:** function calls other than `min`/`max`, string literals outside subscripts, relational field access (`product.product_tmpl_id`), method calls (`product.sudo()`), list/dict/set literals, generators.

**Allowed names:** `price_unit`, `quantity`, `base`, `product`, `uom` (and `min`, `max` functions).

### Formula Evaluation Context

```python
formula_context = {
    'price_unit': evaluation_context['price_unit'],
    'quantity': evaluation_context['quantity'],
    'product': evaluation_context['product'],   # Dict of product.product field values
    'uom': evaluation_context['uom'],           # Dict of uom.uom field values
    'base': raw_base,
}
```

The `product` and `uom` values are **dicts of primitive field values**, not ORM records. This is because the formula must be compatible with both Python (server) and JavaScript (client-side tax preview).

**JSON serialization guard:**
```python
try:
    formula_context = json.loads(json.dumps(formula_context))
except TypeError:
    raise ValidationError(_("Only primitive types are allowed in python tax formula context."))
```

**Division by zero:** Returns `0.0` silently.

---

## L3: Cross-Model, Override Patterns, Workflow Triggers

### Cross-Model Relationships

The `account.tax` extension reads from two additional models during tax computation:

| Model | Accessed Via | Fields | Purpose |
|-------|-------------|--------|---------|
| `product.product` | `product` dict in formula context | Any non-relational field | Product-attribute-driven tax |
| `uom.uom` | `uom` dict in formula context | Any non-relational field | UoM-conversion-aware tax |

The module declares these dependencies through two extension methods:

```python
def _eval_taxes_computation_prepare_product_fields(self):
    # EXTENDS 'account'
    field_names = super()._eval_taxes_computation_prepare_product_fields()
    for tax in self.filtered(lambda tax: tax.amount_type == 'code'):
        field_names.update(tax.formula_decoded_info['product_fields'])
    return field_names

def _eval_taxes_computation_prepare_product_uom_fields(self):
    # EXTENDS 'account'
    field_names = super()._eval_taxes_computation_prepare_product_uom_fields()
    for tax in self.filtered(lambda tax: tax.amount_type == 'code'):
        field_names.update(tax.formula_decoded_info['product_uom_fields'])
    return field_names
```

These hook into the account module's tax computation batch system to eagerly load the necessary product/UoM fields for all taxes with `amount_type='code'`.

### Override Patterns

**`amount_type` field extension:**
```python
# Original in account: percent, fixed, fixed_product, division
# Extended with: code
selection_add=[('code', "Custom Formula")]
ondelete={'code': lambda recs: recs.write({'amount_type': 'percent', 'active': False})}
```

**`_eval_tax_amount_fixed_amount` — EXTENDS `account`:**
```python
def _eval_tax_amount_fixed_amount(self, batch, raw_base, evaluation_context):
    # EXTENDS 'account'
    if self.amount_type == 'code':
        return self._eval_tax_amount_formula(raw_base, evaluation_context)
    return super()._eval_tax_amount_fixed_amount(batch, raw_base, evaluation_context)
```

The account module's tax computation calls `_eval_tax_amount_fixed_amount` for each tax. The `code` type intercepts this and delegates to `_eval_tax_amount_formula` instead.

### Workflow Trigger

The tax computation workflow:

```
User creates/edits tax with amount_type='code'
  → @api.constrains('_check_amount_type_code_formula')  [validates formula]
  → _compute_formula_decoded_info                      [normalizes + collects fields]
  → _eval_taxes_computation_prepare_product_fields     [registers product field deps]
  → _eval_taxes_computation_prepare_product_uom_fields  [registers UoM field deps]
  → _eval_tax_amount_fixed_amount (inherited)           [routes to _eval_tax_amount_formula]
  → _eval_tax_amount_formula                            [safe_eval with formula context]
```

### JavaScript Mirror (`static/src/helpers/account_tax.js`)

```javascript
patch(accountTaxHelpers, {
    eval_tax_amount_formula(tax, raw_base, evaluation_context) {
        const formula_context = {
            price_unit: evaluation_context.price_unit,
            quantity: evaluation_context.quantity,
            product: evaluation_context.product,
            uom: evaluation_context.uom,
            base: raw_base,
        };
        return evaluateExpr(tax.formula_decoded_info.js_formula, formula_context);
    },

    eval_tax_amount_fixed_amount(tax, batch, raw_base, evaluation_context) {
        if (tax.amount_type === "code") {
            return this.eval_tax_amount_formula(tax, raw_base, evaluation_context);
        }
        return super.eval_tax_amount_fixed_amount(...arguments);
    },
});
```

Loaded in both `web.assets_backend` and `web.assets_frontend`. The JS `evaluateExpr` uses Odoo's Python-in-JS evaluator. The normalization step ensures `product.field` → `product['field']` works identically in both environments.

---

## L4: Version Changes Odoo 18 → 19

### Module-Level

No breaking API changes between Odoo 18 and Odoo 19 for `account_tax_python`. The module structure, AST processing, and formula evaluation pipeline are unchanged.

**Version:** Still `version: '1.0'` in `__manifest__.py`.

### AST Formula Utils — Stability

The `formula_utils.py` AST pipeline (`ProductUomFieldRewriter` + `TaxFormulaValidator`) is a sophisticated, stable mechanism. Key behaviors to note:

**Attribute → Subscript rewriting:**
```python
# Input
product.volume > 100 and 10 or 5
# Normalized
product['volume'] > 100 and 10 or 5
```

This is safe in Python (dict subscript access) and in the JS evaluator (Odoo's `evaluateExpr` supports dict subscript).

**Field name collection:**
The rewriter collects all `product.X` and `uom.X` field names and passes them to `_eval_taxes_computation_prepare_product_fields()`. This ensures the batch computation system pre-loads those fields from `product.product` and `uom.uom` records before tax computation.

### Test Suite (`tests/test_taxes_computation.py`)

The module has a comprehensive test suite with three test classes:

**`TestTaxesComputation`** — Validates formula evaluation:
- Simple formulas with `min`/`max`
- Product attribute access (`product.volume`)
- Product subscript access (`product['volume']`)
- UoM attribute access (`uom.relative_factor`)
- String subscripts for conditional logic
- Division-by-zero returns 0.0
- Python → JS parity

**`test_invalid_formula`** — 20+ invalid formula patterns that must raise `ValidationError`:
- Relational fields (`product.product_tmpl_id`)
- Method calls (`product.sudo()`)
- Arbitrary functions (`tuple`, `set`, `range`)
- String literals outside subscripts
- Non-string subscripts (`product[0]`)
- Non-existent fields

**`test_ast_transformer_normalizes`** — Edge cases in AST rewriting:
- Dunder attributes (`product.__dunders__`)
- Spacing and backslash continuations
- Conditional expressions
- Nested subscripts

### Load-Order Dependency Note

`account_tax_python/models/__init__.py` imports `accounting_assert_test` from `account_test`:
```python
from . import accounting_assert_test
```

This forces `account_test` to be loaded before `account_tax_python`. The `account_tax_python` test module (`tests/test_taxes_computation.py`) inherits from `TestTaxCommonAccountTaxPython` which inherits from `TestTaxCommon` in the `account` module. The import ensures all necessary models are registered in the correct order before the test base classes are resolved.

---

## Related

- [Modules/account](Modules/account.md)
- [Modules/account_test](Modules/account_test.md)
