---
Module: account_qr_code_sepa
Version: 18.0
Type: addon
Tags: #account, #qr_code, #sepa, #payment, #europe
---

# account_qr_code_sepa — SEPA QR Code

Implements the SEPA Credit Transfer QR code (European standard, also known as European Payments Council QR). Used for consumer-to-business payments in the SEPA zone.

**Depends:** `account`, `base_iban`

**Source path:** `~/odoo/odoo18/odoo/addons/account_qr_code_sepa/`

## Key Classes

### `ResPartnerBank` — `res.partner.bank` (extends)

**File:** `models/res_bank.py`

Key methods:
- `_get_qr_vals()` (lines 10-34) — Builds SEPA QR data:
  - `BCD` — Service Tag
  - `002` — Version
  - `1` — Character Set (UTF-8)
  - `SCT` — Identification Code
  - `BIC` — Beneficiary bank BIC
  - Name — max 71 chars
  - IBAN — sanitized account number
  - Amount + Currency
  - Purpose (empty)
  - Structured remittance (from `structured_communication` if valid ISR reference)
  - Unstructured remittance (from `free_communication` or `comment`)
  - Beneficiary-to-originator info (empty)
- `_get_qr_code_generation_params()` (lines 36-45) — Returns `barcode_type='QR'`, 128x128, humanreadable
- `_get_error_messages_for_qr()` (lines 47-64) — Validates:
  - Currency must be EUR
  - Account type must be IBAN
  - IBAN country code must be in SEPA zone (excludes AX, NC, YT, TF, BL, RE, MF, GP, PM, PF, GF, MQ, JE, GG, IM)
- `_check_for_qr_code_errors()` (lines 66-71) — Checks account holder name is set
- `_get_available_qr_methods()` (lines 73-77) — Registers `sct_qr` method with priority 20

### `AccountQrCodeSePaTest`

**File:** `tests/test_sepa_qr.py`

Tests SEPA QR code generation for valid/invalid configurations.

## SEPA QR Format

```
BCD\n002\n1\nSCT\n[BIC]\n[Name]\n[IBAN]\nEUR[Amount]\n\n\n[StructuredRef]\n[UnstructuredRef]\n\n
```
