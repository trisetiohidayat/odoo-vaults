---
type: module
module: l10n_sa
tags: [odoo, odoo19, localization, saudi-arabia, zatca, e-invoicing]
created: 2026-04-06
---

# Saudi Arabia - Localization

## Overview
| Property | Value |
|----------|-------|
| **Name** | Saudi Arabia - Accounting |
| **Technical** | `l10n_sa` |
| **Category** | Localization |
| **Country** | Saudi Arabia |

## Description
Localized accounting for Saudi Arabia. Activates chart of accounts, taxes, VAT return, withholding return, and fiscal positions. Implements ZATCA e-invoicing requirements with QR code generation.

## Dependencies
- `l10n_gcc_invoice`
- `account`
- `account_debit_note`

## Key Models

### `account.move` (Extended)
Inherits `account.move` to add Saudi Arabia-specific e-invoicing fields:

| Field | Type | Description |
|-------|------|-------------|
| `l10n_sa_qr_code_str` | Char (computed) | ZATCA QR code string for e-invoicing |
| `l10n_sa_show_reason` | Boolean (computed) | Shows adjustment reason for refunds/credit notes |
| `l10n_sa_reason` | Selection | ZATCA adjustment reason (e.g., cancellation, amendment) |
| `l10n_sa_confirmation_datetime` | Datetime | ZATCA issue date (set on posting) |

**Key Methods:**
- `_compute_qr_code_str()`: Generates ZATCA QR code based on seller name, VAT number, timestamp, total, and tax amount.
- `_post()`: Sets confirmation datetime and delivery date on posting.
- `_l10n_sa_is_simplified()`: Returns True if invoice is B2C (customer is an individual).
- `_l10n_sa_is_legal()`: Checks if document is legally valid in Saudi Arabia.

## Related
- [Modules/account](Account.md)
- [Modules/l10n_gcc_invoice](l10n_gcc_invoice.md)
