# Payment Demo

## Overview
- **Name:** Payment Provider: Demo
- **Category:** Accounting/Accounting
- **Depends:** `payment`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
A payment provider for running fake payment flows for demo and testing purposes. Simulates the full payment lifecycle (authorize, capture, refund) without real financial transactions.

## Models

### `payment.provider` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `code` | Selection | Added: `demo` |

### Feature Support (computed)
- Express checkout: supported
- Manual capture: `partial` (full and partial)
- Refund: `partial` (full and partial)
- Tokenization: supported

## Constraints
- `demo` providers must always be in `test` or `disabled` state (never `enabled`)

## Related
- [Modules/payment](odoo-18/Modules/payment.md) — Base payment engine
