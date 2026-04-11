---
Module: account_tax_python
Version: 18.0
Type: addon
Tags: #account, #tax, #python, #formula
---

# account_tax_python — Python Tax Computation

Allows defining tax amounts using arbitrary Python formulas instead of predefined amount types (percent, fixed, etc.). The formula is evaluated in a safe sandbox.

**Depends:** `account`

**Source path:** `~/odoo/odoo18/odoo/addons/account_tax_python/`

## Key Classes

### `AccountTax` — `account.tax` (extends)

**File:** `models/account_tax.py`

Added fields:
- `amount_type` — Selection adds `('code', 'Custom Formula')` (lines 24-27)
- `formula` — Text, default `"price_unit * 0.10"` (lines 28-36)
- `formula_decoded_info` — Json, computed (line 37)

Key methods:
- `_check_amount_type_code_formula()` (lines 39-43) — constrains formula when `amount_type == 'code'`
- `_eval_taxes_computation_prepare_product_fields()` (lines 45-51) — EXTENDS `account`; adds product fields referenced in formula to evaluation context
- `_compute_formula_decoded_info()` (lines 53-76) — Parses formula, extracts `product.xxx` field references, converts to `product['xxx']` dict access syntax
- `_check_formula()` (lines 78-122) — Validates formula token-by-token against `FORMULA_ALLOWED_TOKENS` (lines 12-18) plus dynamic `product['field']` tokens
- `_eval_tax_amount_formula()` (lines 124-155) — Executes formula via `safe_eval()` in sandbox with `price_unit`, `quantity`, `product`, `base`, `min`, `max` globals
- `_eval_tax_amount_fixed_amount()` (lines 157-161) — EXTENDS `account`; intercepts `amount_type == 'code'` to call `_eval_tax_amount_formula()`

## Allowed Tokens

```
( ) + - * / , < > <= >= and or None base quantity price_unit min max
product['field_name']  (dynamic, extracted from formula)
```

Numeric literals are allowed (validated by `get_number_size()` at lines 84-95).

## Product Fields in Formula

The formula can reference any non-relational field on `product.product` via `product.FIELD_NAME` syntax. The module parses these via regex at line 67 to:
1. Add them to the evaluation context
2. Ensure the product fields are loaded during tax computation
3. Validate JS-side formula matches Python formula

## Example Formula

```python
price_unit * 0.10  # 10% of unit price
product['lst_price'] * quantity * 0.05  # 5% of list price * qty
base * (1 + product['taxes_id'].amount / 100)  # compound-like
```
