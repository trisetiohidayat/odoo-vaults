---
Module: pos_six
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_six #payment #terminal #six
---

## Overview

Adds SIX payment terminal integration to POS. Extends `pos.payment.method` with `six_terminal_ip` field and adds HTTP enforcement override for SIX terminals (which require HTTP, not HTTPS).

**Depends:** `point_of_sale`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `six_terminal_ip` | Char | SIX terminal IP address |

**Methods:**
- `_get_payment_terminal_selection()` -> adds `('six', 'SIX')` to selection
- `_load_pos_data_fields(config_id)` -> adds `'six_terminal_ip'`

---

### `pos.config` (Extension)
**Inheritance:** `pos.config`

**Methods:**
- `_force_http()` -> returns True (force HTTP) if `enforce_https` config param is not set AND config has a payment method with `use_payment_terminal='six'`. Otherwise delegates to parent.

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **HTTP requirement:** SIX terminals require HTTP (not HTTPS) connections. The `_force_http` override checks for SIX terminal presence before disabling HTTPS enforcement. This is critical: without this override, SIX terminals would fail to communicate.

2. **No dedicated payment methods:** SIX does not add custom methods on `pos.payment` — the terminal communication is handled by the base `point_of_sale` module's terminal proxy system, using the `six_terminal_ip` field.