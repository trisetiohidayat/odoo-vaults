---
Module: pos_event_sale
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_event_sale #event #sale #registration
---

## Overview

Synchronizes `event.registration` sale status with POS order payment state. When a POS order (selling event tickets) transitions to `paid/done/invoiced`, the corresponding event registrations are automatically set to `open` state with `sale_status='sold'`. When POS order is draft/cancel, registrations go back to `draft` with `sale_status='to_pay'`.

**Depends:** `pos_event`, `sale_event`

---

## Models

### `event.registration` (Extension)
**Inheritance:** `event.registration`

**Methods:**
- `_compute_registration_status()` -> `@api.depends('pos_order_id.state')`:
  - If `pos_order_id` exists and state in `['paid', 'done', 'invoiced']`: `sale_status='sold'`, `state='open'`
  - Otherwise: `sale_status='to_pay'`, `state='draft'`

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Sale status synchronization:** This module bridges the `pos.order` payment state and `event.registration` lifecycle. It extends the base `_compute_registration_status` from `sale_event` (which handles website/eCommerce sales) to also account for POS order state.

2. **Dependency order:** Requires both `pos_event` (which provides the `pos_order_id` field on `event.registration`) and `sale_event` (which provides the base `_compute_registration_status`).

3. **No explicit write:** The synchronization is automatic — it is a computed field dependent on `pos_order_id.state`. When POS order payment state changes, the registration status updates immediately.