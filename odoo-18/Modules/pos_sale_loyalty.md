---
Module: pos_sale_loyalty
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_sale_loyalty #sale #loyalty
---

## Overview

Link module between `pos_sale` and `pos_loyalty`. Ensures that loyalty reward fields are properly included in sale order line data transmitted from POS to the CRM/Sales pipeline.

**Depends:** `pos_sale`, `pos_loyalty`

---

## Models

### `sale.order.line` (Extension)
**Inheritance:** `sale.order.line`

**Methods:**
- `_get_sale_order_fields()` -> extends parent to include `reward_id` in the list of fields transmitted from POS order lines to sale order lines. This ensures that lines carrying loyalty rewards are properly flagged when a POS order is linked to a sale order.

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Auto-install:** `auto_install=True`. Automatically activates when both `pos_sale` and `pos_loyalty` are installed together.

2. **Reward field propagation:** When a POS order with loyalty rewards is converted to a sale order (via `pos_sale`), the `reward_id` field must travel with the order line to maintain loyalty program integrity in the downstream sale/CRM flow.

3. **Minimal extension:** This module has a single, targeted override. The JS layer (`static/src/overrides/models/pos_order_line.js`) handles the frontend loyalty display changes in the POS order line.
