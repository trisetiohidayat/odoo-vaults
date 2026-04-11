---
Module: account_edi_ubl_cii_tax_extension
Version: 18.0
Type: addon
Tags: #account, #edi, #tax, #ubl, #cii
---

# account_edi_ubl_cii_tax_extension — Tax Extension for EDI

Extends `account_edi_ubl_cii` with support for additional tax information in EDI documents. Handles tax categories and exemption reasons that go beyond the standard EN 16931 format.

**Depends:** `account_edi_ubl_cii`

**Source path:** `~/odoo/odoo18/odoo/addons/account_edi_ubl_cii_tax_extension/`

## Key Classes

### `AccountTax` — `account.tax` (extends)

**File:** `models/account_tax.py`

Extends the tax model to expose additional EDI-relevant fields:
- `edi_ubl_peppol_tax_prefix` — used in Bis 3 tax breakdown
- `edi_ubl_cii_tax_exemption_reason` — maps to `TaxExemptionReason` in CII/Factur-X
- `edi_ubl_cii_tax_category` — maps to `TaxCategory` in UBL/CII

These fields are read by the generators in `account_edi_ubl_cii` when building XML documents.

### `AccountEdiCommon` — `account.edi.common` (extends)

**File:** `models/account_edi_common.py`

Overrides the tax serialization logic to include the extended fields when generating XML elements for tax lines.
