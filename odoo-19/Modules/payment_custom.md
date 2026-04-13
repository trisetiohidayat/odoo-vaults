# Payment Custom

## Overview
- **Name:** Payment Provider: Custom Payment Modes
- **Category:** Accounting/Payment Providers
- **Depends:** `payment`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
A payment provider for custom flows like wire transfers (bank transfer). Allows businesses to configure a custom payment method where customers are given bank account details to make direct transfers.

## Models

### `payment.provider` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `code` | Selection | Added: `custom` |
| `custom_mode` | Selection | `wire_transfer` (required when code=`custom`) |
| `qr_code` | Boolean | Enable QR codes for wire transfer |

## Key Features
- **Wire Transfer:** Displays company's bank account details on the payment page
- **QR Code Support:** Generate QR codes for easier bank transfer
- **Pending Message:** Customizable pending message until transfer is confirmed manually
- **Auto-clear pending:** When `wire_transfer`, pending message is auto-nulled (forces recompute)

## Key Methods
- `action_recompute_pending_msg()` — Recomputes pending message with actual bank accounts from `account.journal` (bank type)
- `_transfer_ensure_pending_msg_is_set()` — Cron/job helper to ensure all transfer providers have a pending msg

## Default Payment Method
- Wire transfer: `payment_method_wire_transfer` (default method added via data)

## Related
- [Modules/payment](payment.md) — Base payment engine
