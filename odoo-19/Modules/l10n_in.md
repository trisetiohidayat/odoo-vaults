# l10n_in - India Accounting

## Overview
- **Name:** Indian - Accounting
- **Country:** India (IN)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 2.0
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `account_tax_python`, `base_vat`, `account_debit_note`, `account`, `iap`
- **Auto-installs:** `account`

## Description
Comprehensive Indian accounting localization supporting:
- Two chart of accounts formats: Standard and Schedule VI (vertical format)
- GST (Goods and Services Tax) with CGST, SGST, IGST, Cess
- TDS (Tax Deducted at Source) and TCS (Tax Collected at Source)
- PAN entity management
- HSN/SAC code validation
- E-invoice and e-Waybill EDI (via companion modules)
- GST return filing (GSTR-1, GSTR-3B)

## Models

### account.account (Inherit)
Extends `account.account`:
- **l10n_in_tds_tcs_section_id:** Many2one to `l10n_in.section.alert` — links account to TDS/TCS section
- **l10n_in_tds_feature_enabled / l10n_in_tcs_feature_enabled:** Computed Booleans based on company settings

### l10n_in.pan.entity (Standalone)
Standalone model with mail tracking:
- **name:** PAN number (uppercase, validated with stdnum.in_.pan)
- **type:** Computed from PAN 4th character — `a` AOP, `b` BoI, `c` Company, `f` Firm, `g` Govt, `h` HUF, `j` AJP, `l` Local Authority, `p` Individual, `t` Trust, `k` Krish
- **partner_ids:** One2many of linked partners
- **tds_deduction:** `normal`, `lower`, `higher`, `no`
- **tds_certificate:** Binary — TDS certificate upload
- **msme_type / msme_number:** MSME/Udyam registration
- **_check_pan_name():** Validates PAN format (stdnum)
- **create():** Auto-uppercases PAN
- **write():** Posts notification when certificate is uploaded

### l10n_in.section.alert (Standalone)
Defines TDS/TCS sections for compliance alerts:
- **name:** Section name (e.g., 194J, 206C)
- **tax_source_type:** `tds` or `tcs`
- **consider_amount:** `untaxed_amount` or `total_amount`
- **is_per_transaction_limit / per_transaction_limit:** Per-transaction threshold
- **is_aggregate_limit / aggregate_limit / aggregate_period:** Aggregate threshold (monthly or FY)
- **l10n_in_section_tax_ids:** One2many of taxes using this section
- **tax_report_line_id:** Link to tax report line
- **_get_warning_message():** Generates alert message for threshold violations

### res.partner (Inherit)
Extends `res.partner` with GST/PAN fields:
- **l10n_in_gst_treatment:** Selection — regular, composition, unregistered, consumer, overseas, SEZ, deemed export, UIN holders
- **l10n_in_pan_entity_id:** Many2one to `l10n_in.pan.entity`
- **l10n_in_tan:** TAN (Tax Deduction Account Number)
- **l10n_in_gstin_verified_status / _date:** GSTIN verification status via GSTN
- **l10n_in_gst_state_warning / display_pan_warning:** Computed warnings
- **l10n_in_is_gst_registered_enabled / l10n_in_gstin_status_feature_enabled:** Feature toggles
- **_set_l10n_in_pan_tan_from_vat():** Extracts PAN/TAN from GSTIN (digits 3-13 of 15-digit GSTIN)
- **_l10n_in_search_create_pan_entity_from_vat():** Searches or creates PAN entity from GSTIN
- **action_l10n_in_verify_gstin_status():** Calls GSTN via IAP to verify partner GSTIN status (active/inactive/provisional)
- **onchange_vat():** Auto-sets state and PAN entity from GSTIN
- **action_update_state_as_per_gstin():** Syncs state from GSTIN
- **check_vat_in():** Overrides to accept test GSTIN `36AABCT1332L011`

### account.journal (Inherit)
Extends `account.journal`:
- **_update_payment_method_lines():** For Indian companies, routes bank payment method accounts to chart template references

### account.move (Inherit)
Extends `account.move` with comprehensive GST support:
- **l10n_in_gst_treatment:** GST treatment (computed from partner, store=True)
- **l10n_in_state_id:** Place of Supply (Many2one to state)
- **l10n_in_gstin:** GSTIN of customer (populated on posting)
- **l10n_in_shipping_bill_number / _date / _port_code_id:** Export fields
- **l10n_in_reseller_partner_id:** Reseller for GSTR-2B
- **l10n_in_warning:** JSON — computed warnings for HSN digit length and TDS/TCS thresholds
- **l10n_in_is_withholding / l10n_in_withholding_ref_move_id/payment_id:** TDS withholding journal entries
- **l10n_in_withholding_line_ids / l10n_in_total_withholding_amount:** TDS line tracking
- **l10n_in_display_higher_tcs_button:** Show "apply higher TCS rate" action
- **l10n_in_partner_gstin_status / _date:** GSTIN verification status on invoice
- **l10n_in_tds_deduction:** Related TDS deduction level
- **_compute_l10n_in_gst_treatment():** Auto-sets from partner or infers from country/GSTIN presence
- **_compute_l10n_in_state_id():** Determines Place of Supply — for exports sets to "Other Territory" (state_in_oc)
- **_compute_fiscal_position_id():** Complex logic for inter-state vs. intra-state GST:
  - Intra-state: uses company state (groups all states together)
  - Inter-state: uses partner state
  - SEZ: uses SEZ fiscal position
- **_onchange_name_warning():** Validates invoice name <= 16 chars, only `-` and `/` as special chars
- **_compute_l10n_in_warning():** Raises warnings for invalid HSN/SAC codes, TCS/TDS threshold breaches
- **action_l10n_in_withholding_entries():** Opens TDS journal entries
- **action_l10n_in_apply_higher_tax():** Updates TCS lines to highest rate in section
- **_get_l10n_in_invalid_tax_lines():** Finds lines with wrong TCS rate (when PAN missing)
- **_get_sections_aggregate_sum_by_pan():** Computes per-PAN, per-section aggregate amounts
- **_l10n_in_is_warning_applicable():** Checks if TDS/TCS warning should fire for section
- **_get_l10n_in_tds_tcs_applicable_sections():** Collects sections with threshold breaches
- **l10n_in_verify_partner_gstin_status():** Verifies partner GSTIN from invoice
- **_post():** Validates GSTIN presence, company state, place of supply TIN
- **_generate_qr_code():** Generates UPI QR code for Indian companies with `l10n_in_upi_id`
- **_l10n_in_get_hsn_summary_table():** HSN-wise tax summary for GSTR-1
- **_l10n_in_prepare_tax_details():** GST tax grouping — separates cgst/sgst/igst/cess/state_cess by rate and reverse-charge flag
- **_get_l10n_in_invoice_label():** Returns "Tax Invoice", "Bill of Supply", or "Invoice-cum-Bill of Supply" based on GST treatment and tax types

## Data Files
- `data/account.account.tag.csv` — HSN/SAC-linked account tags
- `data/l10n_in_chart_data.xml` — Indian chart of accounts
- `data/res_country_state_data.xml` — Indian states with TIN codes
- `data/uom_data.xml` — Indian UoMs
- `data/account_tax_report_tcs_data.xml` / `data/account_tax_report_tds_data.xml` — TDS/TCS reports
- `wizard/l10n_in_withhold_wizard.xml` — TDS withholding wizard
- Extensive views: account, invoice, journal, payment, partner, company, tax, product

## Companion EDI Modules
- **l10n_in_edi** — GST e-invoice (IRN generation via NIC/GSTN API)
- **l10n_in_ewaybill / l10n_in_ewaybill_irn** — e-Waybill
- **l10n_in_pos** — Indian POS
- **l10n_in_withholding** — Indian withholding taxes
