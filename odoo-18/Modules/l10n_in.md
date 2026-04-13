---
Module: l10n_in
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #india #gst
---

# l10n_in — Indian Accounting

## Overview
Core Indian accounting localization for Odoo. The most comprehensive APAC localization module — provides India-specific chart of accounts (both Standard and Schedule VI formats), full GST tax structure (CGST/SGST/IGST/CESS), fiscal positions for inter-state transactions, HSN/SAC product classification, port codes for exports, state-wise TIN data, and India-specific invoice layouts. Required by all other `l10n_in_*` modules.

India uses a dual GST structure where CGST (Central) and SGST (State) apply to intra-state supplies, while IGST (Integrated) applies to inter-state supplies.

## Country
India

## Dependencies
- account_tax_python
- base_vat
- account_debit_note
- account
- iap

## Key Models

### `AccountMove` (`account.move`) — account_invoice.py
- `_inherit = "account.move"`
- `l10n_in_gst_treatment` — Selection: regular, composition, unregistered, consumer, overseas, special_economic_zone, deemed_export, uin_holders. Auto-computed from partner, precomputed.
- `l10n_in_state_id` — Many2one `res.country.state` (Place of Supply), computed for sale/purchase documents
- `l10n_in_gstin` — Char, GST Invoice Number (derived from partner.vat on post)
- `l10n_in_shipping_bill_number` / `l10n_in_shipping_bill_date` — Export shipping fields
- `l10n_in_shipping_port_code_id` — Many2one `l10n_in.port.code`
- `l10n_in_reseller_partner_id` — Reseller for GSTR reports
- `l10n_in_journal_type` — Related to journal type
- `l10n_in_warning` — Json computed warnings (invalid HSN length, etc.)
- Key methods: `_compute_l10n_in_gst_treatment()`, `_compute_l10n_in_state_id()` (determines Place of Supply for sales = shipping address state, purchases = company state), `_compute_fiscal_position_id()` (applies fiscal positions based on GST treatment and intra/inter-state rules; state code `96` maps to foreign_state), `_onchange_name_warning()` (validates invoice sequence: max 16 chars, only `-` and `/`), `_compute_l10n_in_warning()` (warns on missing/invalid HSN codes), `_get_name_invoice_report()` (returns Indian invoice report `l10n_in.l10n_in_report_invoice_document_inherit`), `_post()` (validates state TIN, company address, GSTIN on partners), `_l10n_in_get_warehouse_address()` (overridable hook), `_can_be_unlinked()` (prevents deletion of posted Indian invoices), `_generate_qr_code()` (generates UPI QR code for Indian companies), `_l10n_in_get_hsn_summary_table()` (HSN-wise tax summary)

### `AccountMoveLine` (`account.move.line`) — account_move_line.py
- `_inherit = "account.move.line"`
- Indian-specific line behavior (HSN on product lines)

### `AccountTax` (`account.tax`) — account_tax.py
- `_inherit = 'account.tax'`
- `l10n_in_reverse_charge` — Boolean, marks reverse charge taxes
- `l10n_in_tax_type` — Selection: igst, cgst, sgst, cess. Computed from `invoice_repartition_line_ids.tag_ids`
- `_compute_l10n_in_tax_type()` — reads tax tag to determine CGST/SGST/IGST/CESS
- `_prepare_base_line_for_taxes_computation()` — EXTENDS account; adds `l10n_in_hsn_code` to base line
- `_l10n_in_get_hsn_summary_table(base_lines, display_uom)` — aggregates tax amounts by HSN code, tax type, and rate

### `ResCompany` (`res.company`) — company.py
- `_inherit = 'res.company'`
- `l10n_in_upi_id` — Char, UPI payment ID for QR code generation
- `l10n_in_hsn_code_digit` — Selection: 4 digits (< Rs.5 crore turnover), 6 digits (>5 crore), 8 digits
- `l10n_in_edi_production_env` — Boolean for production/test EDI mode
- `l10n_in_pan` — Char, PAN number (auto-extracted from GSTIN via `gstin.to_pan()`)
- `l10n_in_pan_type` — Computed from PAN validation (individual/company/etc.)
- `l10n_in_gst_state_warning` — Related from partner, warns if state mismatch
- `_compute_l10n_in_hsn_code_digit_and_l10n_in_pan()` — auto-derives HSN digit and PAN from VAT
- `_compute_l10n_in_pan_type()` — uses `stdnum.in_.pan` to get holder type
- `create()` / `write()` — hooks to `_update_l10n_in_fiscal_position()` on state/country change
- `_update_l10n_in_fiscal_position()` — reloads fiscal position data
- `_check_l10n_in_pan()` — constrains PAN to be valid
- `action_update_state_as_per_gstin()` — syncs partner state from GSTIN

### `ResPartner` (`res.partner`) — res_partner.py
- `_inherit = 'res.partner'`
- `l10n_in_gst_treatment` — Same selection as AccountMove
- `l10n_in_pan` — PAN number for partners
- `display_pan_warning` — Boolean, warns if PAN != GSTIN[2:12]
- `l10n_in_gst_state_warning` — Char, warns if partner state doesn't match GSTIN-derived state
- `check_vat_in(vat)` — EXTENDS base; also validates test GST number `36AABCT1332L011`
- `_commercial_fields()` — adds `l10n_in_gst_treatment` and `l10n_in_pan`
- `_l10n_in_get_partner_vals_by_vat(vat)` — calls `enrich_by_gst()` IAP service
- `onchange_vat()` — auto-fills state_id and PAN from GSTIN

### `ProductTemplate` (`product.template`) — product_template.py
- `_inherit = 'product.template'`
- Adds `l10n_in_hsn_code` field on products

### `PortCode` (`l10n_in.port.code`)
- `_name = 'l10n_in.port.code'`
- `code` — Char (required, unique), `name` — Char, `state_id` — Many2one `res.country.state`
- Used for export/import shipping documents

### `ResCountryState` (`res.country.state`)
- `_inherit = 'res.country.state'`
- Indian state-specific extensions (TIN/l10n_in_tin field)

### `IapAccount` (`iap.account`)
- `_inherit = 'iap.account'`
- India EDI and IAP service account extensions

### `UoM` (`uom.uom`)
- `_inherit = "uom.uom"`
- Adds `l10n_in_code` field for Indian UoM codes (used in EDI)

### `AccountChartTemplate` (AbstractModel) — template_in.py
- `_inherit = 'account.chart.template'`
- 6-digit account code digits, receivable `p10040`, payable `p11211`, expense `p2107`, income `p20011`
- Fiscal year: last month March (3)
- Sale tax: `sgst_sale_5`, Purchase: `sgst_purchase_5`
- Deferred expense `p10084`, deferred revenue `p10085`
- `_get_in_account_fiscal_position()` — creates 6 fiscal positions:
  1. **Intra State** (`fiscal_position_in_intra_state`) — SGST+CGST split, auto-applied by state
  2. **Inter State** (`fiscal_position_in_inter_state`) — IGST only, auto-applied
  3. **Export** (`fiscal_position_in_export_sez_in`) — SEZ export with IGST
  4. **SEZ** (`fiscal_position_in_sez`) — SEZ unit supply, state=Odisha (OC)
  5. **Export - LUT (WOP)** — export under LUT without payment
  6. **SEZ - LUT (WOP)** — SEZ under LUT without payment
- `_get_l10n_in_fiscal_tax_vals()` — maps SGST→IGST for all rates (1, 2, 5, 12, 18, 28%)

## Data Files
- `data/l10n_in_chart_data.xml` — Full chart of accounts (Schedule VI format)
- `data/l10n_in.port.code.csv` — Port codes for customs
- `data/res_country_state_data.xml` — Indian states with 2-digit TIN codes
- `data/account.account.tag.csv` — GST classification tags (igst, cgst, sgst, cess, zero_rated, exempt, nil_rated, etc.)
- `data/account_cash_rounding.xml` — Cash rounding (l10n_in.cash_rounding_in_half_up)
- `data/uom_data.xml` — Indian UOM codes
- `data/res_partner_industry.xml` — Indian industry classifications
- `data/iap_service_data.xml` — IAP service config
- `views/account_invoice_views.xml`, `views/account_tax_views.xml`, `views/product_template_view.xml`, `views/port_code_views.xml`
- `security/l10n_in_security.xml`, `security/ir.model.access.csv`
- `demo/demo_company.xml`, `demo/product_demo.xml`

## Chart of Accounts
6-digit account codes in Schedule VI format (MCA-mandated vertical format for balance sheets after March 31, 2011). Supports both Standard and Schedule VI variants.

- **Assets**: 10040 Receivables, 10041 POS Receivable, 10084 Deferred Expense, 10085 Deferred Revenue
- **Liabilities**: 11211 Payables
- **Income**: 20011 Sales Revenue
- **Expenses**: 2107 Direct Costs, 2117 Currency Exchange Loss

## Tax Structure
Full GST cascade (4-tier):
- **CGST** (Central GST) — intra-state supplies
- **SGST** (State GST) — intra-state supplies
- **IGST** (Integrated GST) — inter-state supplies
- **Cess** — additional levy on specific goods (tobacco, luxury cars, etc.)

Rates: 0%, 0.25%, 1%, 2%, 5%, 12%, 18%, 28% (slab structure)
Special: 3% (textiles), 5% (manufactured food), 12% (processed food), 18% (most services), 28% (luxury goods)

HSN summary aggregation via `_l10n_in_get_hsn_summary_table()`.

## Fiscal Positions
Six auto-applied fiscal positions (driven by GST treatment + state):
1. **Intra State** — CGST+SGST (state-matched)
2. **Inter State** — IGST (state-mismatched)
3. **Export SEZ** — IGST 0% with payment
4. **SEZ** — IGST 0% (Odisha virtual state)
5. **Export LUT** — zero-rated IGST under LUT
6. **SEZ LUT** — zero-rated IGST with bond

## EDI/Fiscal Reporting
EDI handled by [Modules/l10n_in_edi](odoo-18/Modules/l10n_in_edi.md) (e-invoice v1.03). GSTR reporting via separate `l10n_in_reports` (enterprise). E-Waybill integration via IAP service.

## Historical Notes
Version 2.0 in Odoo 18 (vs 1.x in Odoo 17). Schedule VI format fully revised per MCA updates. Fiscal positions expanded from 2 to 6 to cover SEZ and LUT export scenarios. HSN validation tightened with configurable digit requirements. UPI QR code generation added for customer payments. Company-level PAN auto-extraction from GSTIN. State TIN (l10n_in_tin) standardized as 2-digit codes for EDI compatibility.