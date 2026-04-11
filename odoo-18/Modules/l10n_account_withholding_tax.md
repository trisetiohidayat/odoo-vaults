---
Module: l10n_account_withholding_tax
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #accounting #withholding #payment
---

# l10n_account_withholding_tax

## Overview
Enables **withholding tax on payment** — a localized accounting pattern common in many countries (India, Italy, Brazil, etc.) where the buyer withholds a percentage of the invoice amount and pays it directly to the tax authority on behalf of the seller. The seller records the full invoice receivable but the actual cash received is net of withholding. This module adds withholding capability to the payment registration workflow.

## EDI Format / Standard
Not an EDI module. This is a **localization extension** for the payment flow. It enables tax withheld at payment time (not at invoice time), with the withheld amount posted to a specific liability account for later remittance.

## Dependencies
- `account` — Core accounting module

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountTax` | `account.tax` | `account.tax` | Adds `is_withholding_tax_on_payment` boolean, `withholding_sequence_id` for auto-numbering withholding entries |
| `AccountPayment` | `account.payment` | `account.payment` | Adds `should_withhold_tax`, `withholding_line_ids`, `display_withholding`, `withholding_hide_tax_base_account` fields; withholding computation at payment registration |
| `AccountPaymentWithholdingLine` | `account.payment.withholding.line` | `base` | Individual withholding lines on a payment: tax, base amount, withholding amount |
| `AccountWithholdingLine` | `account.withholding.line` | `base` | Abstract model for withholding line domain computation |
| `ProductTemplate` | `product.template` | `product.template` | Product-level withholding tax default |
| `ResCompany` | `res.company` | `res.company` | Company-level withholding configuration |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form for withholding defaults |

## Data Files
- `security/ir.model.access.csv` — Access control
- `views/account_payment_views.xml` — Payment form with withholding section
- `views/account_tax_views.xml` — Tax form with withholding options
- `views/report_payment_receipt_templates.xml` — Payment receipt with withholding detail
- `views/res_config_settings.xml` — Settings view
- `wizards/account_payment_register_views.xml` — Payment registration wizard with withholding

## How It Works

### Tax Configuration
On `account.tax`:
1. Set `is_withholding_tax_on_payment = True`
2. Amount must be **negative** (e.g., -20% means 20% withholding)
3. `tax_exigibility` forced to `on_invoice` ( withholding ≠ cash basis)
4. Cannot be used with `group` or `division` amount_type
5. Optionally assign a `withholding_sequence_id` for auto-numbering withholding entries

### Payment Registration
When registering a payment with `should_withhold_tax = True`:
1. Withholding taxes detected from invoice lines and supplier
2. For each withholding tax: compute amount based on payment amount proportionally
3. Withholding lines created with: tax, base amount, withholding amount
4. Payment amount = invoice amount - withholding amounts
5. Withholding amounts posted to the tax's `cash_basis_account` or configured withholding account

### Display Logic
`display_withholding` computed: only shown if company has any withholding taxes matching the payment type (inbound/outbound).

### Tax Computation Override
`AccountTax._add_tax_details_in_base_line()` is overridden to exclude withholding taxes from normal invoice tax computation unless explicitly requested via `calculate_withholding_taxes` key in base_line dict.

### Withholding Line Domain
`account.withholding.line._get_withholding_tax_domain(company, payment_type)` determines which taxes apply based on company and payment direction.

## Installation
Standard module install. Post-init hook `_l10n_account_wth_post_init` initializes default configurations.

## Historical Notes
- **Odoo 17**: Withholding tax on payment existed in `l10n_*` modules but as scattered country-specific patches
- **Odoo 18**: Consolidated withholding tax logic into a generic `l10n_account_withholding_tax` module that can work with any country's chart. Proper abstract model for withholding lines, cleaner tax computation, and improved payment wizard integration.