---
Module: l10n_pl
Version: 18.0
Type: l10n/pl
Tags: #odoo18 #l10n #accounting
---

# l10n_pl

## Overview
Poland accounting localization. Provides full Polish chart of accounts (8-digit), tax structure, fiscal positions, tax office registry, and product GTU codes for SAF-T/JPK VAT reporting. Uses Storno (negative posting) accounting. Authored by Odoo SA and Grzegorz Grzelak (OpenGLOBE).

## Country
Poland

## Dependencies
- base_iban
- base_vat
- account

## Key Models

### l10n_pl.l10n_pl_tax_office
`models/l10n_pl_tax_office.py` — custom model
- `_name = 'l10n_pl.l10n_pl_tax_office'` — Tax Office registry
- Fields: `code` (Char), `name` (Char)
- `_rec_names_search = ['name', 'code']`; `_compute_display_name` — formats as `"code name"`
- SQL constraint: code unique per company
- Purpose: associates company with its assigned tax office for JPK filings

### ResCompany
`models/res_company.py` — extends `res.company`
- `l10n_pl_reports_tax_office_id` (Many2one `l10n_pl.l10n_pl_tax_office`) — assigned tax office for VAT reporting

### ResConfigSettings
`models/res_config_settings.py` — extends `res.config.settings`
- `l10n_pl_reports_tax_office_id` — related field to company, editable from settings

### ResPartner
`models/res_partner.py` — extends `res.partner`
- `l10n_pl_links_with_customer` (Boolean) — TP flag: "Links With Company" — indicates related-party relationship for transfer pricing (JPK reporting)

### ProductTemplate
`models/product.py` — extends `product.template`
- `l10n_pl_vat_gtu` (Selection) — GTU (Goods/Tax Types) codes required for Polish SAF-T JPK VAT declaration:
  - `GTU_01` — Alcoholic beverages
  - `GTU_02` — Fuel oil, lubricating oils
  - `GTU_03` — Tobacco products, e-liquid
  - `GTU_04` — Goods under Art. 103 sec 5aa
  - `GTU_05` — Wastes
  - `GTU_06` — Electronic devices and parts
  - `GTU_07` — Vehicles and vehicle parts
  - `GTU_08` — Precious and base metals
  - `GTU_09` — Medicaments and medical devices
  - `GTU_10` — Buildings, structures, land
  - `GTU_11` — Greenhouse gas emission allowance services
  - `GTU_12` — Intangible services
  - `GTU_13` — Transport and warehouse services

### AccountMove
`models/account_move.py` — extends `account.move`
- `l10n_pl_vat_b_spv` (Boolean) — B_SPV: Transfer of single-purpose voucher by taxable person acting on own behalf
- `l10n_pl_vat_b_spv_dostawa` (Boolean) — B_SPV_Dostawa: Supply of SPV goods/services to taxpayer
- `l10n_pl_vat_b_mpv_prowizja` (Boolean) — B_MPV_Prowizja: Agency/commission services for SPV transfer

### AccountChartTemplate
`models/template_pl.py`
- `_get_pl_template_data()` — code_digits=8, Storno accounting enabled, maps to Polish PCKZ 2019 account codes
- `_get_pl_res_company()` — sets fiscal country Poland, bank prefix `11.000.00`, cash `12.000.00`, transfer `11.090.00`, currency exchange accounts, cash difference accounts

## Data Files
- `data/l10n_pl.l10n_pl_tax_office.csv` — tax office registry data
- `data/res.country.state.csv` — Polish voivodeship/county data
- `data/account.account.tag.csv` — account tags for Polish reporting
- `data/account_tax_report_data.xml` — Polish VAT/JPK tax report structure
- `data/template/` — full 8-digit chart of accounts
- `security/ir.model.access.csv` — access control for `l10n_pl.l10n_pl_tax_office`
- `views/account_move_views.xml`, `views/product_views.xml`, `views/res_partner_views.xml`, `views/res_config_settings_views.xml`
- `demo/demo_company.xml`

## Chart of Accounts
8-digit Polish PCKZ 2019 (accounting plan). Storno accounting enabled (reversal/negative posting).

| Account | Code | Purpose |
|---|---|---|
| Receivable | chart20000100 | Customer AR |
| Payable | chart21000100 | Supplier AP |
| Income | chart73000100 | Sales revenue |
| Expense | chart70010100 | COGS |
| Bank | prefix 11.000.00 | Bank accounts |
| Cash | prefix 12.000.00 | Cash accounts |
| Transfer | 11.090.00 | Internal transfers |
| FX Gain | chart75000600 | Currency gains |
| FX Loss | chart75010400 | Currency losses |
| Cash Diff. Income | chart75000700 | Cash over/short |
| Cash Diff. Expense | chart75010500 | Cash over/short |
| Early Pay Discount Loss | chart75010900 | Supplier discounts |
| Early Pay Discount Gain | chart75000900 | Customer discounts |

## Tax Structure
Standard Polish VAT rates via template:
- 23% standard rate (default mapped)
- Reduced rates defined in `data/template/account.tax.csv`

Tax report: JPK_FA ( SAF-T structured reporting), VAT-7/9 via `account_tax_report_data.xml`.

## Fiscal Positions
Standard: B2C, B2B EU intra-community, export/import fiscal positions defined in template data.

## EDI/Fiscal Reporting
JPK (SAF-T) structured format — supported by Odoo's standard tax report engine.
GTU codes on products for JPK_V7M reporting.
SPV/MPS fields on invoices for special transaction types.

## Installation
`auto_install: ['account']`
Post-init hook: `_preserve_tag_on_taxes`

## Historical Notes
**Odoo 17 → 18 changes:**
- Version 2.0 (was 1.x in older versions)
- Polish chart completely restructured to PCKZ 2019 (8-digit) format
- Storno accounting explicitly enabled in Odoo 16+; continues in 18
- GTU product codes and SPV invoice flags added more recently (2023+) for JPK compliance
- Tax office model (`l10n_pl.l10n_pl_tax_office`) is a newer addition for proper JPK_ VAT filing

**Performance Notes:**
- 8-digit chart is large; installation is slower than 4-digit charts
- Storno accounting doubles write operations per transaction
