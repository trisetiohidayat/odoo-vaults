---
Module: l10n_account_edi_ubl_cii_tests
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #accounting
---

# l10n_account_edi_ubl_cii_tests

## Overview
A hidden test module that validates the `account_edi_ubl_cii` module (UBL 2.1 / CII format generation and import) across multiple country localizations. Separated from the main module to avoid loading test dependencies in production, and prefixed with `l10n` so runbot does not flag it as an unknown addon.

## EDI Format / Standard
- **Factur-X** (France, FNFE standard) — import validation
- **PEPPOL BIS Billing 3.0** — import and export validation
- **UBL 2.1** — Odoo-generated files validated against external validators (ecosio, FNFE)

Test files are sourced from:
- FNFE documentation (Factur-X examples)
- PEPOL BIS repository (`peppol-bis-invoice-3/tree/master/rules/examples`)
- Odoo-generated valid files

## Dependencies
- `account_edi_ubl_cii`
- `l10n_fr_account`
- `l10n_be`
- `l10n_de`
- `l10n_nl`
- `l10n_au`

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountMove` | `account.move` | `account.move` | Adds test-specific EDI check/validation methods |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Extends send wizard for test scenarios |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Configuration settings for test environments |
| `ResCompany` | `res.company` | `res.company` | Company-level EDI config for test |
| `ResPartner` | `res.partner` | `res.partner` | Partner EDI fields used in tests |

## Data Files
No data files. This module contains only Python test code and XML view definitions.

## How It Works
The module contains standard Odoo tests (Python unit tests) that:
1. Load external Factur-X and Peppol example XML files
2. Import them into Odoo and verify currency, total amount, and total tax match
3. Generate XML from Odoo with known parameters and compare byte-for-byte against known-good references

## Installation
This is a **Hidden/Tests** module. It is not shown in the Apps list. Install only in test/development databases by explicitly referencing it in the module list or via shell:

```python
self.env['ir.module.module'].search([('name','=','l10n_account_edi_ubl_cii_tests')]).button_install()
```

## Historical Notes
- Odoo 17: Test coverage for `account_edi_ubl_cii` was more fragmented across country-specific test files
- Odoo 18: Consolidated all UBL/CII import/export tests into this single module
- The module name begins with `l10n` specifically to prevent runbot from flagging it as an unclassified addon