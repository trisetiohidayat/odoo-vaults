---
Module: l10n_ca
Version: 18.0
Type: l10n/canada
Tags: #odoo18 #l10n #accounting #tax #gst #hst #pst
---

# l10n_ca — Canada Accounting

## Overview
The Canadian localization module provides a complete accounting chart, provincial GST/HST/PST tax structure, and province-aware fiscal positions. It supports the Canada-specific tax collection model where the delivery destination province determines which taxes apply. The `ca_2023` chart template is the active template as of Odoo 18, replacing older versions.

## Country
Canada (`CA`) — provinces: BC, MB, QC, SK, ON, NB, NL, NS, PE

## Dependencies
- [account](odoo-18/Modules/account.md)
- `base_iban`

## Key Models

### res_partner.py
```python
class ResPartner(models.Model):
    _inherit = 'res.partner'
    l10n_ca_pst = fields.Char(string='PST number')
```
Stores the Provincial Sales Tax (PST) identification number per partner. Displayed on invoices via `report_invoice.xml` extension when the partner has a PST number set. The field is hidden unless the partner's fiscal country is Canada.

### res_company.py
```python
class ResCompany(models.Model):
    _inherit = 'res.company'
    l10n_ca_pst = fields.Char(related='partner_id.l10n_ca_pst', ...)

class BaseDocumentLayout(models.TransientModel):
    _inherit = 'base.document.layout'
    l10n_ca_pst = fields.Char(related='company_id.l10n_ca_pst', readonly=True)
    account_fiscal_country_id = fields.Many2one(related="company_id.account_fiscal_country_id", readonly=True)
```
Company-level PST field (mirrored from partner) plus layout wizard support for displaying PST in the document layout wizard.

### template_ca.py
```python
class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ca_2023')
    def _get_ca_template_data(self): ...

    @template('ca_2023', 'res.company')
    def _get_ca_res_company(self): ...
```
`ca_2023` chart template. Maps default receivable, payable, income, expense, and stock accounts. Sets `anglo_saxon_accounting` to `True`. Company defaults (prefixes, POS receivable, currency exchange, early pay discount accounts) are set here. The default sales/purchase tax is dynamically chosen based on the company's province/state.

Provincial default tax mapping:
| Province | Sales Tax | Purchase Tax |
|---|---|---|
| BC | `gstpst_sale_tax_12_bc` | `gstpst_purchase_tax_12_bc` |
| MB | `gstpst_sale_tax_12_mb` | `gstpst_purchase_tax_12_mb` |
| QC | `gstqst_sale_tax_14975` | `gstqst_purchase_tax_14975` |
| SK | `gstpst_sale_tax_11` | `gstpst_purchase_tax_11` |
| ON | `hst_sale_tax_13` | `hst_purchase_tax_13` |
| NB | `hst_sale_tax_15` | `hst_purchase_tax_15` |
| NL | `hst_sale_tax_15` | `hst_purchase_tax_15` |
| NS | `hst_sale_tax_14` | `hst_purchase_tax_14` |
| PE | `hst_sale_tax_15` | `hst_purchase_tax_15` |
| Default (other) | `gst_sale_tax_5` | `gst_purchase_tax_5` |

Key account codes used by `ca_2023`:
- Receivable: `l10n_ca_112110` (default POS: `l10n_ca_112113`)
- Payable: `l10n_ca_221110`
- Income: `l10n_ca_411100`
- Expense: `l10n_ca_511210`
- Stock input: `l10n_ca_121130` | output: `l10n_ca_121140` | valuation: `l10n_ca_121120`
- Currency exchange gain: `l10n_ca_423100` | loss: `l10n_ca_522100`
- Early pay discount gain: `l10n_ca_423200` | loss: `l10n_ca_522200`

## Data Files
- `data/tax_report.xml` — **GST/HST Report** (`l10n_ca_tr_gsthst`), rooted at `account.generic_tax_report`, country `base.ca`. Lines 90–N covering taxable sales, exports, exempt supplies, GST collected, input tax credits, and provincial components.
- `views/res_partner_view.xml` — adds `l10n_ca_pst` field to `res.partner` form, invisible unless fiscal country is CA.
- `views/res_company_view.xml` — adds PST field to company document layout wizard.
- `views/report_invoice.xml` — extends `account.report_invoice_document` to display partner PST number on printed invoices.
- `views/report_template.xml` — report template views for Canadian invoices.
- `demo/demo_company.xml` — demo company "CA Company" (Yukon territory, `base.state_ca_yt`), loads `ca_2023` chart with demo data.

## Chart of Accounts
The `ca_2023` chart is a full Canadian accounting chart based on CICA (Canadian Institute of Chartered Accountants) standards. It uses 6-digit numeric account codes. The chart is IFRS-aligned with full Anglo-Saxon (periodic inventory) accounting enabled.

## Tax Structure
Canada uses a multi-layer VAT system:

**Federal GST (Goods and Services Tax):** 5% across all provinces (default tax).
**HST (Harmonized Sales Tax):** Provinces that have harmonized with federal GST — ON (13%), NB/NL/PE (15%), NS (14%).
**PST (Provincial Sales Tax):** Applied on top of GST in BC (7%), MB (7%), QC (QST at 9.975%), SK (6%).
**GST+QST combination:** BC, MB, SK — separate GST + PST. Quebec uses GST + QST ( QB QST = 9.975% on pre-tax amount, effectively ~9.975% on the GST-inclusive base).

Fiscal positions determine which tax mapping applies — driven by the delivery province on the partner form. The design principle: "delivery is the responsibility of the vendor and done at the customer location."

## Fiscal Positions
The module implements province-level fiscal positions implicitly through the `_get_ca_res_company` dynamic defaults. When a company is created in a given province, the correct tax pair is auto-selected. Custom fiscal positions can be defined manually for inter-provincial or international scenarios.

## EDI/Fiscal Reporting
No EDI format is defined in this module. The GST/HST tax report (`l10n_ca_tr_gsthst`) is the primary fiscal reporting tool, mapping to the Canada Revenue Agency's GST/HST return format.

## Installation
Install via Apps or automatically when a Canadian company is created. The module is marked `auto_install: ['account']`, meaning it installs automatically when `account` is installed in a Canadian context.

## Historical Notes
- **Odoo 17 → 18:** The `ca_2023` chart template replaces earlier Canadian chart templates (previously `ca` or `ca_standard`). Provincial tax selection logic was enhanced to auto-detect the correct tax based on the company state rather than requiring manual fiscal position assignment.
- Author: Savoir-faire Linux + Odoo SA.
