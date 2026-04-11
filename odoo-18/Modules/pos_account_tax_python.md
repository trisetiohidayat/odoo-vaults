---
Module: pos_account_tax_python
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_account_tax_python #account #tax #python
---

## Overview

Enables Python-defined (code-based) taxes in the Point of Sale. The `account_tax_python` module allows defining taxes with Python computation code; this bridge module loads those taxes into the POS assets bundle so the POS frontend can compute tax amounts dynamically.

**Depends:** `account_tax_python`, `point_of_sale`

---

## Models

### `account.tax` (Extension)
**Inheritance:** `account.tax`

**Methods:**
- `_load_pos_data_fields(config_id)` -> extends parent fields list with `formula_decoded_info`. This ensures that Python-defined taxes carry their decoded formula information into the POS frontend, where the JS tax computation engine evaluates the formula for each order line.

---

## Static Assets

**Auto-install:** `auto_install=True` (depends on both `account_tax_python` and `point_of_sale`).

The `account_tax_python` module provides JS helpers at `account_tax_python/static/src/helpers/*.js` (included via `point_of_sale._assets_pos` bundle).

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Python tax formula:** `account_tax_python` allows taxes to be defined with arbitrary Python code (stored in `amount_python_compute`). The `formula_decoded_info` field exposes this formula to the frontend in a format the POS JS engine can evaluate.

2. **Tax computation in POS:** Without this bridge, Python-defined taxes would not be sent to the POS client, causing incorrect tax totals for products using these taxes. This module ensures `formula_decoded_info` is included in the POS tax data load.

3. **Auto-install pattern:** The `auto_install=True` with `depends: ['account_tax_python', 'point_of_sale']` means Odoo installs this automatically whenever both dependencies are selected, with no manual activation needed.
