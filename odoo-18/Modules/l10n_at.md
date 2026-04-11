---
Module: l10n_at
Version: 18.0
Type: l10n/austria
Tags: #odoo18 #l10n #accounting
---

# l10n_at

## Overview
Austrian localization module providing the official Einheitskontenrahmen 2010 (Uniform Chart of Accounts 2010), VAT tax templates, and fiscal position mappings. Auto-installed with country selection.

## Country
Austria

## Dependencies
- account
- base_iban
- base_vat
- l10n_din5008

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_journal.py | `AccountJournal` | (base) |
| template_at.py | `AccountChartTemplate` | (base) |

### AccountChartTemplate (template_at.py)
Configures the Austrian General Chart of Accounts 2010 via CSV data files.

## Data Files
- `data/template/account.account-at.csv` — 232 accounts (Einheitskontenrahmen 2010)
- `data/template/account.tax-at.csv` — VAT tax templates
- `data/template/account.fiscal.position-at.csv` — 22 fiscal positions
- `data/template/account.tax.group-at.csv` — tax groups
- `data/account_account_tag.xml` — account account tags
- `data/account_tax_report_data.xml` — tax report structure
- `data/res.country.state.csv` — Austrian federal states

## Chart of Accounts
Based on **Einheitskontenrahmen 2010 (EKR 2010)** — the standardized Austrian uniform chart of accounts used by businesses of all sizes. 232 nominal accounts covering the complete accounting cycle.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (Ust EX), Zero-rated (0% A), EU exempt |
| 10% | Reduced rate (books, cultural events) |
| 12% | Second reduced rate (W — Wasser) |
| 13% | intermediate rate (on Gas, Electricity) |
| 19% | Standard rate (Umsatzsteuer) |
| 20% | Standard rate VAT on purchases (Vorstecker) |

Tax suffixes indicate scope: `L` = Lieferungen (deliveries), `S` = Sonstiges (other), `R` = Reverse Charge, `EU` = Intra-community, `EX` = Export.

## Fiscal Positions
22 fiscal positions including:
- National (without UID)
- European Union
- Intra-community (EU reverse charge)
- Export third countries

## EDI/Fiscal Reporting
No dedicated EDI module. Standard Odoo tax reporting applies. Austrian VAT returns must be filed via the government's FinanzOnline portal.

## Installation
Auto-installed when "Austria" is selected as the country during Odoo setup. Or install manually via Apps.

## Historical Notes
- Odoo 18 uses the same Einheitskontenrahmen 2010 structure as Odoo 17.
- Austrian specific tax tags (Vst/Vst C-12) for input VAT tracking across multiple cantonal codes.
