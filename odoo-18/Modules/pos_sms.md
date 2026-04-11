---
Module: pos_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_sms #sms #notification #pos
---

## Overview

Sends SMS receipts to customers after POS orders are paid. Configures an SMS receipt template per POS config; the `pos.order.action_sent_message_on_sms` method triggers the SMS composer.

**Depends:** `point_of_sale`, `sms`

---

## Models

### `pos.config` (Extension)
**Inheritance:** `pos.config`

| Field | Type | Notes |
|---|---|---|
| `sms_receipt_template_id` | Many2one `sms.template` | Domain: `model='pos.order'`. SMS sent to customer based on this template. |

---

### `pos.order` (Extension)
**Inheritance:** `pos.order`

**Methods:**
- `action_sent_message_on_sms(phone, _, basic_image=False)` -> checks `config_id.module_pos_sms` + `config_id.sms_receipt_template_id` + `phone`. Creates `sms.composer` with `composition_mode='comment'`, template_id, number; sets `self.mobile = phone`; calls `action_send_sms()`. Silently does nothing if conditions not met.

---

### `res.config.settings` (Extension)
**Inheritance:** `res.config.settings`

| Field | Type | Notes |
|---|---|---|
| `pos_sms_receipt_template_id` | Many2one related to `pos_config_id.sms_receipt_template_id` | readonly=False |

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Silent no-op:** `action_sent_message_on_sms` returns early without error if SMS module not enabled or no template/phone configured. This prevents breaking the POS flow if SMS is not fully configured.

2. **`basic_image` parameter:** Present in signature for compatibility but not used — the method only handles SMS text via template.

3. **`mobile` field:** The `pos.order.mobile` field is set to the phone number before sending — this allows the SMS template to use `{{object.mobile}}` placeholder.