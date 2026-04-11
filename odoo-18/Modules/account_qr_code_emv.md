---
Module: account_qr_code_emv
Version: 18.0
Type: addon
Tags: #account, #qr_code, #emv, #payment
---

# account_qr_code_emv — EMV QR Code for Accounting

Implements EMV Co-Merchant-Presented QR codes for invoices. Used in countries like India (UPI), Singapore (PayNow), Malaysia (DuitNow), etc.

**Depends:** `account`

**Source path:** `~/odoo/odoo18/odoo/addons/account_qr_code_emv/`

## Architecture

Extends `res.partner.bank` with EMV QR code generation. Country-specific modules (e.g., `account_qr_code_in`) implement `_get_merchant_account_info()` to provide the proxy type/value fields populated per-country.

## Key Classes

### `ResPartnerBank` — `res.partner.bank` (extends)

**File:** `models/res_bank.py`

Added fields (lines 13-16):
- `display_qr_setting` — Boolean, computed (line 13)
- `include_reference` — Boolean, whether to include reference in QR (line 14)
- `proxy_type` — Selection `[('none', 'None')]`, default 'none' (line 15) — overridden by country-specific modules
- `proxy_value` — Char (line 16)

Key methods:
- `_serialize(header, value)` (line 18-23) — EMV TLV-like serialization: `header` (2 digits) + length + value
- `_remove_accents(string)` (line 26-27) — removes diacritics, replaces `đ`/`Đ`
- `_get_crc16(data)` (lines 35-44) — CRC16 with polynomial 0x1021, init 0xFFFF; used for trailer checksum
- `_get_merchant_account_info()` (line 46-47) — Returns `(tag, value)`; **must be overridden** by country modules; base returns `None, None`
- `_get_additional_data_field(comment)` (line 49-50) — Returns additional field TLV; base returns None
- `_get_merchant_category_code()` (line 52-53) — Returns `'0000'` default
- `_get_qr_code_vals_list()` (line 55-79) — Builds EMV QR data objects (TLV list):
  - `(0, '01')` — Payload Format Indicator (always)
  - `(1, '12')` — Dynamic QR
  - `(tag, merchant_account_info)` — from `_get_merchant_account_info()`
  - `(52, MCC)` — Merchant Category Code
  - `(53, currency_code)` — Transaction Currency
  - `(54, amount)` — Transaction Amount
  - `(58, country_code)` — Country Code
  - `(59, merchant_name)` — max 25 chars
  - `(60, merchant_city)` — max 15 chars
  - `(62, additional_data_field)` — optional
- `_get_qr_vals()` (lines 81-90) — Serializes vals list, appends `6304` CRC16 trailer
- `_get_qr_code_generation_params()` (lines 92-101) — Returns barcode params dict for `reportModels`
- `_check_for_qr_code_errors()` (lines 103-113) — Validates merchant account, city, proxy fields are set
- `_get_error_messages_for_qr()` (lines 121-128) — Returns country-specific error if no EMV method found for account's country
- `_get_available_qr_methods()` (lines 115-118) — Registers `emv_qr` method with priority 30

### Constants

**File:** `const.py` — `CURRENCY_MAPPING`: maps currency names (e.g., `'INR'`, `'SGD'`) to EMV currency codes.

## EMV QR Code Structure

```
[Payload Format Indicator]01
[Point of Initiation Method]12 (= dynamic)
[Merchant Account Information]  (tag+len from _get_merchant_account_info)
[Merchant Category Code]52000000
[Transaction Currency]5303SGD
[Transaction Amount]54[amount]
[Country Code]5802SG
[Merchant Name]59[25 chars]
[Merchant City]60[15 chars]
[Additional Data Field]  (optional, tag 62)
[CRC16]6304
```

CRC16 computed over entire string including `6304` but not the checksum itself.
