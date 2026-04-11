---
Module: l10n_it_edi_ndd
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #italy #debit-note #ndd
---

# l10n_it_edi_ndd

## Overview
Extends the Italian e-invoicing module with Nota di Debito (NDD) -- Debit Note support. NDDs are used in Italy for corrective invoices in specific scenarios (e.g., agricultural cooperatives, telecommunications). The module adds the necessary document type (`TD19`) and payment method codes required by SDI for NDD processing.

## EDI Format / Standard
FatturaPA XML (same framework as standard Italian e-invoice). Document type code `TD19` for NDD.

## Dependencies
- `l10n_it_edi` -- core Italian e-invoicing

## Key Models

### `account.move` (`l10n_it_edi_ndd.account_move`)
Extends: `account.move`

Adds NDD-specific fields and logic: document type code mapping, NDD reference fields in XML export.

### `account.payment.method.line` (`l10n_it_edi_ndd.account_payment_method_line`)
Extends: `account.payment.method.line`

Adds NDD payment method codes for SDI compatibility.

### `l10n_it.document.type` (`l10n_it_edi_ndd.l10n_it_document_type`)
Stands alone: no `_inherit`.

- `code` -- Char (e.g., `TD19`)
- `name` -- Char
- Internal type: `debit_note`

Master data for Italian document types.

## Data Files
- `data/l10n_it.document.type.csv` -- TD19 Debit Note type definition
- `views/account_payment_method.xml`, `views/l10n_it_document_type.xml` -- UI
- `security/ir.model.access.csv` -- ACL

## How It Works
1. NDD (Debit Note) is a specific invoice type in Italy for specific corrections
2. The module registers `TD19` as a valid document type code
3. When a move with NDD type is exported via `_l10n_it_edi_get_values()`, the document type code `TD19` is written to the XML
4. Payment method lines are extended with NDD-compatible codes

## Installation
Auto-installs with `l10n_it_edi`. Requires Italian company configuration.

## Historical Notes
NDD (Nota di Debito) support was added to Odoo as Italian localization maturity increased. The bridge module `l10n_it_edi_ndd_account_dn` links NDD to the generic account debit note framework for invoice reversal flows.
