---
Module: l10n_it_edi_doi
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #italy #declaration-of-intent
---

# l10n_it_edi_doi

## Overview
Adds support for Dichiarazione di Intento (Declaration of Intent) to the Italian e-invoicing workflow. A DOI is a document issued by a taxable customer declaring their intent to receive invoices without VAT for certain threshold amounts (mainly in the professional services and agricultural sectors). This module tracks DOI issuance, remaining thresholds, and enforces VAT-exempt invoicing within the declared limits.

## EDI Format / Standard
Not an EDI format itself. The DOI concept affects which taxes are applied and how they are declared in the FatturaPA XML. With a valid active DOI, the invoice uses exemption reason `N2.1` or `N3.2` (reverse charge or non-taxable) and the VAT amount is zero-rated up to the declared threshold.

## Dependencies
- `l10n_it_edi` -- core Italian e-invoicing
- `sale` -- sales order tracking for "not yet invoiced" amounts

## Key Models

### `l10n_it_edi_doi.declaration_of_intent` (`l10n_it_edi_doi.declaration_of_intent`)
Stands alone: no `_inherit`.

Inherits `mail.thread.main.attachment` and `mail.activity.mixin`.

Fields:
- `state` -- Selection: `draft | active | revoked | terminated`
- `company_id` / `partner_id` -- Company and partner (must be commercial partner)
- `currency_id` -- EUR (default)
- `issue_date` -- Date of issue
- `start_date` / `end_date` -- Validity period
- `threshold` -- Monetary: maximum total amount allowed without VAT
- `invoiced` -- Monetary (computed): total from posted invoices using this DOI
- `not_yet_invoiced` -- Monetary (computed): total from confirmed sale orders
- `remaining` -- Monetary (computed): threshold - invoiced - not_yet_invoiced
- `protocol_number_part1` / `protocol_number_part2` -- Two-part protocol number (displayed as `part1-part2`)
- `invoice_ids` / `sale_order_ids` -- Linked invoices and sale orders

SQL constraints:
- `protocol_number_unique` on `(protocol_number_part1, protocol_number_part2)`
- `threshold_positive` on `threshold`

Key methods:
- `_compute_invoiced()` -- Sums `l10n_it_edi_doi_amount` from posted invoices
- `_compute_not_yet_invoiced()` -- Sums `l10n_it_edi_doi_not_yet_invoiced` from confirmed sale orders
- `_compute_remaining()` -- threshold - invoiced - not_yet_invoiced
- `_build_threshold_warning_message()` -- Returns yellow-banner message if remaining < 0
- `_get_validity_errors()` / `_get_validity_warnings()` -- Validation for company, currency, partner, date, state
- `_fetch_valid_declaration_of_intent()` -- Search for a valid, active, non-expired DOI for given company/partner/currency/date
- `_unlink_except_linked_to_document()` -- Prevents deletion of used DOIs
- `action_validate()` / `action_reset_to_draft()` / `action_reactivate()` / `action_revoke()` / `action_terminate()` -- Workflow actions
- `action_open_invoice_ids()` / `action_open_sale_order_ids()` -- Navigation actions

### `account.move` / `account.move.line` / `account.fiscal.position` / `account.tax` / `res.company` / `res.partner` / `sale.order`
Extensions to wire DOI amounts into invoices, apply fiscal positions with DOI exemption reasons, and configure tax rules.

## Data Files
- `security/ir.model.access.csv` -- ACL
- `views/l10n_it_edi_doi_declaration_of_intent_views.xml`, `views/account_move_views.xml`, `views/res_partner_views.xml`, `views/sale_order_views.xml`, `views/sale_ir_actions_report_templates.xml`, `views/report_invoice.xml` -- UI
- `data/invoice_it_template.xml` -- FatturaPA template with DOI note section

## How It Works
1. Company creates a DOI for a partner: set threshold, issue date, validity period
2. DOI is validated → state becomes `active`
3. Sales order is created for that partner; `l10n_it_edi_doi_not_yet_invoiced` is computed
4. When invoice is created: `_fetch_valid_declaration_of_intent()` finds active DOI; applies DOI fiscal position (VAT-exempt or reverse charge)
5. `l10n_it_edi_doi_amount` on the move is updated; `invoiced` on the DOI is recomputed
6. Yellow warning banner shown if threshold is exceeded or DOI is revoked
7. When DOI is revoked/terminated, existing invoices are not reversed; threshold exceeded warnings appear

## Installation
Install after `l10n_it_edi` and `sale`. The `post_init_hook` `_l10n_it_edi_doi_post_init` configures initial DOI fiscal positions. Requires Italian company.

## Historical Notes
Dichiarazione di Intento is a longstanding Italian tax mechanism (Article 1, para 100, Finance Law 2007) allowing professionals and certain businesses to receive invoices without VAT up to a declared threshold. The threshold is tracked cumulatively across all invoices using the same DOI. The Odoo implementation tracks both invoiced amounts (from posted moves) and not-yet-invoiced amounts (from confirmed sale orders), providing a forward-looking view of remaining threshold. DOIs are separate from the FatturaPA XML but influence the exemption reason (N2.1 or N3.2) used in the XML.
