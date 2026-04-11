# Account Peppol Advanced Fields

**Module:** `account_peppol_advanced_fields`
**Category:** Accounting/Accounting
**Depends:** `account`, `account_edi_ubl_cii`
**License:** LGPL-3
**Status:** DEPRECATED

## Overview

**[DEPRECATED]** This module was merged prematurely and does not work correctly. A better solution is planned.

Adds advanced Peppol-specific fields to invoices for extended Peppol BIS Billing 3.0 compliance.

## Models

### `account.move` (inherited)

Extends `account.move` with:

| Field | Type | Description |
|-------|------|-------------|
| `peppol_contract_document_reference` | Char | Reference to the contract document |
| `peppol_project_reference` | Char | Reference to the project |
| `peppol_originator_document_reference` | Char | Reference to the originating document |
| `peppol_despatch_document_reference` | Char | Reference to the despatch document |
| `peppol_additional_document_reference` | Char | Reference to an additional supporting document |
| `peppol_accounting_cost` | Char | Accounting cost identifier or description |
| `peppol_delivery_location_id` | Char | GLN of the delivery location |

## Technical Notes

- Do not use in production.
- Provides views for the additional fields on invoice forms.
