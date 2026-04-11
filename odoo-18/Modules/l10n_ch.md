---
Module: l10n_ch
Version: 18.0
Type: l10n/switzerland
Tags: #odoo18 #l10n #accounting
---

# l10n_ch

## Overview
Swiss localization module providing the Swiss PME/KMU 2015 chart of accounts, VAT (MWST) tax templates, and QR-bill generation for invoices. QR-bills are automatically attached when printing or emailing invoices.

## Country
Switzerland

## Dependencies
- account
- base_iban
- l10n_din5008

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_invoice.py | `AccountMove` | (extends) |
| account_journal.py | `AccountJournal` | (extends) |
| account_payment.py | `AccountPayment` | (extends) |
| ir_actions_report.py | `IrActionsReport` | (extends) |
| res_bank.py | `ResPartnerBank` | (extends) |
| template_ch.py | `AccountChartTemplate` | (base) |

### QR-Bill Support
The `ir_actions_report.py` customizes report actions to attach Swiss QR-bills to invoices. The `res_bank.py` extends `ResPartnerBank` to support ISR/QR-Reference format bank accounts. Swiss QR-bills require a QR-IBAN configured on the company bank account.

## Data Files
- `data/template/account.account-ch.csv` — 209 accounts (Swiss PME/KMU 2015)
- `data/template/account.tax-ch.csv` — Swiss MWST taxes
- `data/template/account.fiscal.position-ch.csv` — Swiss fiscal positions
- `data/template/account.tax.group-ch.csv` — tax groups
- `data/account_tax_report_data.xml` — Swiss tax report structure

## Chart of Accounts
Based on **Swiss PME/KMU 2015** (Petites et Moyennes Enterprises / Klein- und Mittelunternehmen) — the recommended Swiss accounting chart for small and medium businesses. 209 accounts organized by the Swiss accounting class structure.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EX, D), Zero-rated (S T) |
| 2.5% | Lower reduced rate (necessaries) |
| 2.6% | Special rate (accommodation, with/without meals) |
| 3.7% | Reduced rate (cultural events, sporting) |
| 3.8% | Special accommodation rate |
| 7.7% | Standard rate (MWST/USt) |
| 8.1% | Standard rate including tip |

Swiss tax suffixes: `I OE` = Input tax for "Others Entities" (public institutions), `R` = Refundable, `D` = Deductible. Negative rates (-7.7%, -8.1%) represent correction/reverse scenarios.

## Fiscal Positions
Swiss-specific fiscal positions covering domestic, EU, and export transactions with appropriate VAT treatment.

## EDI/Fiscal Reporting
No dedicated EDI module. Swiss QR-bill format (SIX Paymit + Swiss QR Code standard) is natively supported. E-invoicing via PEPPOL is supported through the standard `account_edi_ubl_cii` module.

## Installation
Install manually or via country selection. After installation, configure the QR-IBAN on company bank accounts to enable QR-bill generation.

## Historical Notes
- Odoo 17→18: QR-bill attachment to emails is now automatic (previously required manual step).
- Swiss MWST (Mehrwertsteuer) rates are defined inCHF; Odoo handles the currency automatically.
- ISR (Orange slip) reference format deprecated in favor of QR-IBAN/QR-bill standard.
- Three reduced VAT rates (2.5%, 3.7%, 3.8%) remain unchanged from Odoo 17.
