---
Module: pos_hr_restaurant
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_hr_restaurant #hr #restaurant
---

## Overview

Link module between `pos_hr` and `pos_restaurant`. Adapts POS HR behavior (employee badge-in, PIN login) for restaurant contexts, enabling waiter badge login and per-employee order tracking in restaurant mode.

**Depends:** `pos_hr`, `pos_restaurant`

**Has no Python models.** Pure JS/asset extension module.

---

## Static Assets / JS Overrides

Extends `point_of_sale._assets_pos` with:
- `pos_hr_restaurant/static/src/overrides/components/navbar/navbar.js` — adapts the POS navbar for restaurant floor/table view with HR elements
- `pos_hr_restaurant/static/src/overrides/models/pos_store.js` — extends the POS store model to handle employee session state in restaurant mode

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Auto-install:** `auto_install=True`. Automatically activates when both `pos_hr` and `pos_restaurant` are installed together.

2. **Restaurant HR scenario:** In restaurant POS, each order should be attributable to the serving employee. This module bridges `pos_hr`'s employee PIN/badge login system with `pos_restaurant`'s table order workflow.

3. **Pure JS extension:** No Python models. All behavioral changes are in JavaScript overrides that adapt the POS frontend's navbar and store models for the combined HR+restaurant context.
