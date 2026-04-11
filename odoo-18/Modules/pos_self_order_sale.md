---
Module: pos_self_order_sale
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_self_order_sale #self_order #sale
---

## Overview

Links kiosk self-order POS to CRM/Sales functionality. Auto-assigns a "Kiosk Sale Team" CRM team to kiosk POS configs during onboarding, enabling sales pipeline tracking for self-order transactions.

**Depends:** `pos_self_order`, `pos_sale`

---

## Models

### `res.config.settings` (Extension)
**Inheritance:** `res.config.settings`

**Methods:**
- `_onchange_pos_self_order_kiosk()` -> extends parent (from `pos_self_order`). For kiosk mode, auto-sets `pos_crm_team_id` to `pos_self_order_sale.pos_sales_team` (external ref to "Kiosk Sale Team" data record) if not already set.

---

## Security / Data

**Data files:**
- `data/kiosk_sale_team.xml` (noupdate): Creates `crm.team` record with `name='Kiosk Sale Team'` and xmlid `pos_self_order_sale.pos_sales_team`

---

## Critical Notes

1. **CRM integration:** When a POS order is created in kiosk mode, it can be linked to the "Kiosk Sale Team" for reporting. The `pos_sale` module links orders to CRM teams for pipeline tracking.

2. **Onboarding only:** The auto-assignment only triggers during the `_onchange_pos_self_order_kiosk` call when kiosk mode is set in the settings wizard — not on every write.

3. **Auto-install:** `auto_install=True`. Automatically activates when both `pos_self_order` and `pos_sale` are installed together.
