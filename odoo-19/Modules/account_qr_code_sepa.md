---
type: module
module: account_qr_code_sepa
tags: [odoo, odoo19, account, invoicing, qr-code, sepa, payment]
created: 2026-04-06
---

# Account SEPA QR Code

## Overview
| Property | Value |
|----------|-------|
| **Name** | Account SEPA QR Code |
| **Technical** | `account_qr_code_sepa` |
| **Category** | Accounting/Payment |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Adds support for SEPA Credit Transfer QR-code generation. Generates QR codes following the European Payments Council SEPA Credit Transfer QR Code specification. Registered as QR method `sct_qr`. Auto-installs with `account`.

## Dependencies
- `account`
- `base_iban`

## Key Models
| Model | Type | Description |
|-------|------|-------------|
| `res.partner.bank` | Extension | SEPA QR code generation on IBAN bank accounts |

## `res.partner.bank` (Extension)
### QR Method: `sct_qr`

### Methods
| Method | Purpose |
|--------|---------|
| `_get_qr_vals` | Builds SEPA QR payload: Service Tag, Version, Charset, SCT identifier, BIC, name, IBAN, currency+amount, purpose, remittance (structured or unstructured), beneficiary info |
| `_get_qr_code_generation_params` | Returns barcode params for report rendering |
| `_get_error_messages_for_qr` | Validates: EUR currency, IBAN account type, SEPA country IBAN prefix |
| `_check_for_qr_code_errors` | Validates account holder name or partner name is set |
| `_get_available_qr_methods` | Registers `sct_qr` method at priority 20 |

### SEPA QR Payload Format
```
BCD          — Service Tag
002          — Version
1            — Character Set (UTF-8)
SCT          — Identification Code (SEPA Credit Transfer)
<BIC>        — BIC of Beneficiary Bank
<Name>       — Name of Beneficiary (max 71 chars)
<IBAN>       — Account Number (IBAN)
<EUR><Amount> — Currency + Amount
<Purpose>    — Purpose code (optional)
<Remittance> — Structured OR unstructured remittance info
<Beneficiary> — Beneficiary to Originator info (optional)
```

### Validation Rules
- Currency must be **EUR**
- Account type must be **IBAN**
- IBAN must belong to a **SEPA country** (excludes AX, NC, YT, TF, BL, RE, MF, GP, PM, PF, GF, MQ, JE, GG, IM)
- Account holder name or partner name must be set

## Related
- [Modules/account_qr_code_emv](account_qr_code_emv.md)
- [Modules/account](Account.md)
- [Modules/base_iban](base_iban.md)
