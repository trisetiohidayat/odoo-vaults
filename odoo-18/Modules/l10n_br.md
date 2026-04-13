---
Module: l10n_br
Version: 18.0
Type: l10n/brazil
Tags: #odoo18 #l10n #accounting #brazil
---

# l10n_br — Brazilian Accounting

## Overview
Core Brazilian localization module. Provides the Brazilian chart of accounts (SPED/PCMG-aligned), Brazilian tax fields on taxes (IPI, ICMS, PIS, COFINS, ISS, IR, CSLL), document types (NFC-e, NFS-e, etc.), fiscal position logic for interstate commerce, and partner tax identification fields (IE, IM, SUFRAMA). Maintained by Akretion and Odoo Brasil community. Requires [Modules/l10n_latam_base](odoo-18/Modules/l10n_latam_base.md) and [Modules/l10n_latam_invoice_document](odoo-18/Modules/l10n_latam_invoice_document.md).

Also includes Pix QR code support via extended `res.partner.bank` (proxy_type selection_add with email, mobile, br_cpf_cnpj, br_random key types) and `res.city` with CEP zip range mapping.

## Country/Region
Brazil (country code: BR)

## Dependencies
- account
- account_qr_code_emv
- base_address_extended
- l10n_latam_base
- l10n_latam_invoice_document

## Key Models

### `account.tax` (Extended)
Inherits: `account.tax`
Added fields:
- `tax_discount` (Boolean): Indicates the tax is deducted from price (ICMS, PIS, etc.)
- `base_reduction` (Float): Decimal percentage (0-1) for tax base reduction
- `amount_mva` (Float): MVA (Margem de Valor Agregado) percentage for ICMS-ST, decimal 0-1

### `account.fiscal.position` (Extended)
Inherits: `account.fiscal.position`
Added field:
- `l10n_br_fp_type` (Selection): internal | ss_nnm (South/Southeast→North/Northeast/Midwest) | interstate

Method:
- `_get_fiscal_position()`: Overrides super to auto-detect Brazilian fiscal position based on company state vs. delivery state. South/Southeast companies selling to North/Northeast/Midwest get ss_nnm; same-state = internal; other = interstate.

### `res.partner` (Extended)
Inherits: `res.partner`
Added fields:
- `l10n_br_ie_code` (Char): Inscricao Estadual (state tax ID), 9-14 digits
- `l10n_br_im_code` (Char): Inscricao Municipal (municipal tax ID)
- `l10n_br_isuf_code` (Char): SUFRAMA registration number for Manaus Free Trade Zone

### `res.partner.bank` (Extended)
Inherits: `res.partner.bank`
Added `proxy_type` selection options:
- `email`: Email Address Pix proxy
- `mobile`: Mobile Number Pix proxy (+55 prefix, 14 chars)
- `br_cpf_cnpj`: CPF/CNPJ Pix proxy
- `br_random`: Random Key Pix (UUID format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

Methods:
- `_check_br_proxy()`: Validates Pix proxy format (email, CPF/CNPJ numeric, mobile +55 prefix, random UUID)
- `_compute_display_qr_setting()`: Forces QR settings on for Brazilian banks
- `_get_qr_code_vals_list()`: BR-specific: 2-decimal amount, uppercases merchant name/city
- `_get_merchant_account_info()`: Returns Pix GUI `br.gov.bcb.pix` + key
- `_get_error_messages_for_qr()`: Only BRL currency allowed
- `_check_for_qr_code_errors()`: Requires valid Pix proxy type

### `res.city` (Extended)
Inherits: `res.city`
Added fields:
- `l10n_br_zip_range_ids` (One2many): Maps city to CEP zip code ranges
- `l10n_br_zip_ranges` (Char, computed): Frontend-formatted zip ranges as `[start end]` strings

Method `_compute_l10n_br_zip_ranges()`: Formats zip ranges for display.

### `account.chart.template` (Extended)
Method `_template_br()`: Loads Brazilian chart of accounts and tax templates.

## Chart of Accounts
Brazilian chart based on SPED/PCMG (Plano de Contas das Micros e Pequenas Empresas). 5-digit codes: 1-Ativo, 2-Passivo, 3-Patrimonio Liquido, 4-Receitas, 5-Despesas, 6-Custos, 7-Custos Produtos Vendidos.

## Tax Structure
- **ICMS**: State VAT, with ICMS-ST (Substituicao Tributaria) using MVA for downstream states
- **IPI**: Federal excise tax on manufactured goods
- **PIS/COFINS**: Federal social contributions on revenue
- **ISS**: Municipal services tax
- **IR/CSLL**: Federal income taxes
- Interstate fiscal positions: South/Southeast → North/Northeast/Midwest (ss_nnm type with ICMS differential), other interstate, internal
- Each tax carries `tax_discount`, `base_reduction`, `amount_mva` for ICMS-ST

## Fiscal Positions
Three automatic fiscal positions:
- **Internal**: Same state operation
- **South/Southeast → North/Northeast/Midwest**: ICMS reduction (ss_nnm)
- **Other Interstate**: Standard interstate commerce

## EDI/Fiscal Reporting
No EDI in core. Complementary modules:
- `l10n_br_reports`: Tax report, P&L, Balance Sheet for Brazilian market
- `l10n_br_avatax` / `l10n_br_avatax_sale`: Avatax tax calculation
- `l10n_br_edi`: Electronic invoicing via Avatax (NFe format)
- Pix QR codes via `account_qr_code_emv`

## Data Files
- `security/ir.model.access.csv`
- `views/res_partner_views.xml`: IE/IM/SUFRAMA fields on partner form
- `data/account_tax_report_data.xml`: Tax report structure
- `data/res_country_data.xml`: BR country configuration
- `data/res.city.csv`: Brazilian cities with codes
- `data/l10n_br.zip.range.csv`: City-to-zip-range mapping
- `data/l10n_latam.identification.type.csv`: CNPJ, CPF identification types
- `data/l10n_latam.document.type.csv`: NFC-e, NFS-e, etc.
- `views/account_fiscal_position_views.xml`: Interstate fiscal position types
- `demo/demo_company.xml`

## Installation
Install with accounting. Chart of accounts and taxes loaded via demo data.

## Historical Notes
Odoo 18 v1.0. Key changes from Odoo 17: ICMS-ST fiscal position logic improved; new `l10n_br_fp_type` field on fiscal position; SUFRAMA field added; Pix QR code support added via `account_qr_code_emv` integration.

