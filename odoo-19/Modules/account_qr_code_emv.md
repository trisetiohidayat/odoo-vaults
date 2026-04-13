---
type: module
module: account_qr_code_emv
tags: [odoo, odoo19, account, invoicing, qr-code, payment, emv]
created: 2026-04-06
---

# Account EMV QR Code

## Overview
| Property | Value |
|----------|-------|
| **Name** | Account EMV QR Code |
| **Technical** | `account_qr_code_emv` |
| **Category** | Accounting/Payment |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Bridge module adding support for EMV Merchant-Presented QR-code generation for Payment System. Used for generating QR codes on invoices that follow the EMVCo merchant-presented QR specification. Registered as QR method `emv_qr`.

## Dependencies
- `account`

## Key Models
| Model | Type | Description |
|-------|------|-------------|
| `res.partner.bank` | Extension | EMV QR code generation on bank accounts |

## `res.partner.bank` (Extension)
### Fields
| Field | Type | Description |
|-------|------|-------------|
| `display_qr_setting` | Boolean | Computed; controls QR settings visibility |
| `include_reference` | Boolean | Include payment reference in the QR code |
| `proxy_type` | Selection | Currently `none`; extended by country-specific modules |
| `country_proxy_keys` | Char | Computed; country-specific proxy key definitions |
| `proxy_value` | Char | Proxy value (e.g., phone number, national ID) |

### QR Code Generation Methods
| Method | Purpose |
|--------|---------|
| `_get_merchant_account_info` | Returns `(tag, merchant_account_info)`; stub returning `None, None`; overridden per country |
| `_get_additional_data_field` | Returns additional data field; stub returning `None` |
| `_get_merchant_category_code` | Returns MCC; default `'0000'` |
| `_get_qr_code_vals_list` | Builds EMV TLV list: PFI, merchant info, currency, amount, country, name, city, additional data |
| `_get_qr_vals` | Serializes TLV list + CRC16 into final QR string |
| `_get_qr_code_generation_params` | Returns barcode params dict for report rendering |
| `_check_for_qr_code_errors` | Validates required fields for EMV QR generation |

### CRC16
- Polynomial: `0x1021`, initial value: `0xFFFF`
- Final 4 hex digits appended as `6304` + CRC

### EMV QR Structure (Tag Map)
| Tag | Field |
|-----|-------|
| 0 | Payload Format Indicator (`01`) |
| 1 | Point of Initiation Method (`12` = Dynamic) |
| tag | Merchant Account Information |
| 52 | Merchant Category Code |
| 53 | Transaction Currency (ISO 4217 numeric) |
| 54 | Transaction Amount |
| 58 | Country Code |
| 59 | Merchant Name (max 25 chars, accents removed) |
| 60 | Merchant City (max 15 chars, accents removed) |
| 62 | Additional Data Field |

### Validation Errors
- Missing merchant account information
- Missing city on partner
- Missing proxy type
- Missing proxy value

## Country-Specific Extensions
This module is a bridge. Country-specific modules (e.g., `l10n_*_account_qr_code_emv`) override `_get_merchant_account_info` and `_get_additional_data_field` to provide actual proxy types (e.g., `phone`, `epc`, `national_id`).

## Related
- [Modules/account_qr_code_sepa](account_qr_code_sepa.md)
- [Modules/account](Account.md)
- [Modules/payment](payment.md)
