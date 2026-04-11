---
Module: l10n_it_edi_ndd_account_dn
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #italy #debit-note
---

# l10n_it_edi_ndd_account_dn

## Overview
Bridge module linking the Italian NDD (Nota di Debito) e-invoicing module to Odoo's generic account debit note framework (`account_debit_note`). This allows NDD documents created via the account debit note reverse wizard to also carry the correct SDI document type codes.

## EDI Format / Standard
Same FatturaPA XML as `l10n_it_edi`. Uses document type code `TD19`.

## Dependencies
- `l10n_it_edi_ndd` -- NDD document type definitions
- `account_debit_note` -- generic debit note reversal wizard

## Key Models

### `account.move` (`l10n_it_edi_ndd_account_dn.account_move`)
Extends: `account.move`

Adds debit note fields required by the SDI NDD profile. Minimal extension bridging the account debit note wizard output to the NDD EDI fields.

## Data Files
- `data/invoice_it_template.xml` -- NDD XML template extension (inherits parent)

## How It Works
1. User creates a debit note via Accounting > Customers > Debit Note
2. The wizard creates a new move reversing the original
3. This module ensures the resulting move has NDD fields (`TD19` document type)
4. The move is sent via SDI as a debit note

## Installation
Auto-installs with `l10n_it_edi_ndd`. Requires `account_debit_note` installed.

## Historical Notes
Bridge modules like this one are common in the Italian localization stack, where the generic Odoo reversal mechanism (from `account_debit_note`) needs to be wired to country-specific SDI document types.
