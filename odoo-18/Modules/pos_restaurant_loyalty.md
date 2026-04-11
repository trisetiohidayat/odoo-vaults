---
Module: pos_restaurant_loyalty
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_restaurant_loyalty #restaurant #loyalty
---

## Overview

Link module between `pos_restaurant` and `pos_loyalty`. Corrects loyalty behavior when restaurant table orders participate in loyalty programs.

**Depends:** `pos_restaurant`, `pos_loyalty`

**Has no Python models.** Pure extension module via JS assets.

---

## Static Assets

Extends `point_of_sale._assets_pos` with:
- `pos_restaurant_loyalty/static/src/**/*`

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Auto-install:** `auto_install=True`. Triggers automatically when both `pos_restaurant` and `pos_loyalty` are installed together.

2. **Loyalty in restaurant mode:** Restaurant orders (with `table_id`) participate in loyalty programs the same as regular POS orders. The `pos_loyalty` module tracks points per partner on `pos.order`.

3. **Pure extension module:** No Python models. Behavior is modified exclusively through JavaScript asset overrides.
