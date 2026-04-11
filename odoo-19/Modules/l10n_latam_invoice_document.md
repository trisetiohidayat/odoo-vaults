---
type: module
module: l10n_latam_invoice_document
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# LATAM Accounting Localization (`l10n_latam_invoice_document`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Functional |
| **Technical** | `l10n_latam_invoice_document` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Functional
----------

In some Latinamerica countries, including Argentina and Chile, some accounting transactions like invoices and vendor bills are classified by a document types defined by the government fiscal authorities (In Argentina case ARCA, Chile case SII).

This module is intended to be extended by localizations in order to manage these document types and is an essential information that needs to be displayed in the printed reports and that needs to be easily identified, within the set of invoices as well of account moves.

Each document type have their own rules and sequence number, this last one is integrated with the invoice number and journal sequence in order to be easy for the localization user. In order to support or not this document types a Journal has a new option that lets to use document or not.

Technical
---------

If your localization needs this logic will then need to add this module as dependency and in your localization module extend:

* extend company's _localization_use_documents() method.
* create the data of the document types that exists for the specific country. The document type has a country field

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `account_debit_note` | Dependency |

## Technical Notes
- Country code: `latam`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, account_journal.py, l10n_latam_document_type.py, account_move_line.py, res_company.py, account_chart_template.py

## Related