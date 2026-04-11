---
Module: l10n_in_withholding
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #india #tds #tcs #withholding
---

# l10n_in_withholding — Indian TDS and TCS

## Overview
Implements Indian TDS (Tax Deducted at Source) and TCS (Tax Collected at Source) tax structures. Adds withholding tax tracking on invoices, TDS/TCS section codes, deduction certificates, and dedicated tax reports for FBR/TDS compliance. TDS is deducted by the payer on payments to vendors; TCS is collected by the seller on sale of specific goods.

## Country
India

## Dependencies
- l10n_in

## Key Models

### `AccountTax` (`account.tax`) — account_tax.py
- `_inherit = 'account.tax'`
- TDS/TCS tax type overrides

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = "account.move"`
- `_compute_l10n_in_withholding_line_ids()` — computes TDS/TCS lines linked to move
- `_compute_l10n_in_total_withholding_amount()` — sums withholding amounts
- `_get_l10n_in_invalid_tax_lines()` — validates withholding tax application
- `_compute_l10n_in_warning()` — warns about withholding issues
- `_compute_l10n_in_display_higher_tcs_button()` — TCS higher rate button
- `_get_sections_aggregate_sum_by_pan(section_alert, commercial_partner_id)` — aggregates by PAN
- `_l10n_in_is_warning_applicable(section_id)` — checks section applicability
- `_compute_l10n_in_tcs_tds_warning()` — TCS/TDS warning on invoices

### `L10nInSectionAlert` (`l10n_in.section.alert`) — l10n_in_section_alert.py
- `_name = "l10n_in.section.alert"`
- TDS/TCS section master data: codes like 192 (Salary), 192A (PF), 193 (Securities), 194 (Dividend), 194A (Interest), 194B (Horse racing), 194C (Contractor), 194D (Insurance), 194E (HRA), 194EE (NRE), 194F (MFP), 194G (Lottery), 194H (Commission), 194I (Rent), 194J (Professional), 194K (FDB), 206C(1) (TCS: Alcohol, Tobacco, etc.), 206C(1F) (Tendu), 206C(1G) (Foreign exchange), etc.
- Fields: `name`, `tax_source_type` (tds/tcs), `rate`, `threshold_amount`, `company_id`
- Display name: `"%s %s" % (tax_source_type.upper(), name)` e.g., "TCS 196"

### `AccountMoveLine` (`account.move.line`) — account_move_line.py
- `_inherit = 'account.move.line'`
- TDS/TCS line-level tracking

### `AccountAccount` (`account.account`) — account_account.py
- `_inherit = 'account.account'`
- TDS receivable/payable account fields

### `AccountPayment` (`account.payment`) — account_payment.py
- `_inherit = 'account.payment'`
- TDS deduction tracking on payments

### `ResCompany` (`res.company`) — res_company.py
- `_inherit = 'res.company'`
- TDS receivable account (`l10n_in_tds_account_id`)
- TDS payable account (`l10n_in_tds_payable_account_id`)

### `AccountChartTemplate` (AbstractModel) — account_chart_template.py
- `_inherit = 'account.chart.template'`
- TDS/TCS account template loading

### `ResConfigSettings` (`res.config.settings`)
- `_inherit = "res.config.settings"`
- TDS/TCS configuration (default accounts, section codes)

## Data Files
- `security/ir.model.access.csv`
- `data/l10n_in.section.alert.csv` — Section codes master data
- `data/account_tax_report_tcs_data.xml` — TCS report (Section 206C(1): Alcoholic Liquor, Tendu leaves, Timber, Auto rickshaw, T0/F0 rate, Scrap, Minerals, Motor vehicle, Tobacco, Charcoal, Iron ore, Alcoholic liquor for human consumption)
- `data/account_tax_report_tds_data.xml` — TDS report (Sections 192–194ZB and more)
- `wizard/l10n_in_withhold_wizard.xml` — TDS deduction wizard
- `views/l10n_in_section_alert_views.xml`
- `views/account_account_views.xml`, `views/account_move_views.xml`, `views/account_move_line_views.xml`
- `views/account_payment_views.xml`, `views/account_tax_views.xml`, `views/res_config_settings_views.xml`

## Tax Structure

### TDS Sections (Income Tax Act)
| Section | Nature of Payment |
|---|---|
| 192 | Salary (regular employment) |
| 192A | Accumulated PF balance |
| 193 | Interest on securities |
| 194 | Dividend |
| 194A | Interest (other than securities) |
| 194B | Horse racing |
| 194C | Contractor/HFW (0.5%–2%) |
| 194D | Insurance commission |
| 194E | HRA to directors |
| 194EE | NRE deposits |
| 194F | Shares/MF units |
| 194G | Lottery/betting |
| 194H | Commission/brokerage (5%) |
| 194I | Rent (2%–10%) |
| 194J | Professional/royalty (2%–10%) |
| 194K | FDB/ securities |
| 194LA | Compensation for land |

### TCS Sections
| Section | Goods |
|---|---|
| 206C(1) | Alcoholic liquor for human consumption |
| 206C(1) | Tendu leaves |
| 206C(1) | Timber obtained under forest lease |
| 206C(1) | Charcoal |
| 206C(1F) | Tendu tobacco |
| 206C(1G) | Foreign exchange |
| 206C(1H) | Motor vehicle > Rs. 10L |

## Installation
Install via Apps. TDS/TCS section codes loaded from data. Post-init hook `_l10n_in_withholding_post_init`.

## Historical Notes
New in Odoo 18. TDS and TCS module was significantly expanded in Odoo 18 with dedicated section alert models, payment-level tracking, and reconciliation reports. Section codes match current Income Tax Act provisions.