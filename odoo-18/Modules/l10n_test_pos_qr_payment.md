---
Module: l10n_test_pos_qr_payment
Version: 1.0
Type: test/hidden
Tags: #odoo18 #test #pos #qr-payment #sepa #swiss-qr #emv
---

# l10n_test_pos_qr_payment

## Overview
Hidden test module containing JavaScript / QUnit tests for Point of Sale QR code payment functionality. Tests the QR code rendering and payment flow for all supported QR payment formats in Odoo POS: SEPA Credit Transfer (SCT), Swiss QR-bill, and EMV QR (Hong Kong and Brazil implementations). This module is marked as `Hidden` category and is only used for automated testing; it should not be installed in production.

## Country
International (tests multiple country-specific QR formats)

## Dependencies
- `point_of_sale` (POS application)
- `account_qr_code_sepa` (SEPA SCT QR)
- `l10n_be` (Belgian QR implementation)
- `l10n_ch` (Swiss QR-bill implementation)
- `l10n_hk` (Hong Kong EMV QR)
- `l10n_br` (Brazil EMV QR)

## Key Models
None. No Python models. All code is JavaScript QUnit tests.

## Data Files
None.

## Test Coverage

### SEPA Credit Transfer (SCT) QR
Tests that the SEPA QR code is correctly generated from POS payment data:
- IBAN, BIC, amount, creditor name, remittance information
- Validates QR code data string against EPC 069 ISO 20022 pain.001 format
- Tests Euro amounts with 2 decimal precision

### Swiss QR-bill
Tests Swiss QR-bill (SPC 0200) QR code generation in POS:
- CDR (Creditor Reference, ISR format)
- Swiss IBAN validation
- VAT amount and tax rate in QR data
- Multiple currencies (CHF, EUR)

### EMV QR (Hong Kong)
Tests HK FPS (Faster Payment System) EMV QR generation:
- FPS identifier, proxy type (mobile/email/UEN)
- HKD amounts
- Merchant information format

### EMV QR (Brazil)
Tests Brazil PIX EMV QR generation:
- PIX BR Code format
- Brazil-specific merchant account identifier
- CPF/CNPJ in QR data
- Merchant city and postal code

## Installation
This is a **test-only** module. Not for production use. Loaded automatically by Odoo's test runner (`--test-tags`) when running JS tests with POS QWeb assets.

## Historical Notes
- Odoo 18: New dedicated test module for POS QR payments
- Prior: QR payment tests were scattered in POS and country-specific modules
