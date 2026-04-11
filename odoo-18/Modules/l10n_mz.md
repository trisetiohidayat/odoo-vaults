---
Module: l10n_mz
Version: 18.0
Type: l10n/mozambique
Tags: #odoo18 #l10n #accounting #southern_africa
---

# l10n_mz

## Overview
Mozambique accounting localization — chart of accounts and tax report for Mozambican companies.

## Country
Republic of Mozambique — country code `mz`

## Dependencies
- base
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'mz'`.

## Data Files
- `data/tax_report.xml` — Mozambique tax report
- `demo/demo_company.xml` — Mozambique demo company

## Chart of Accounts
Mozambique chart of accounts with `mz` prefix. Mozambique follows the Plano Oficial de Contabilidade (POC) — the official accounting plan based on Portuguese/Spanish accounting traditions adapted for Mozambican context.

## Tax Structure
IVA (Imposto sobre o Valor Acrescentado) at 16% standard rate (reduced from 17% in 2016). IMS (Imposto sobre o Rendimento de Pessoas Singulares) for individuals, IRC (Imposto sobre o Rendimento de Pessoas Colectivas) for companies at 32%. Municipal tax on property.

## Fiscal Positions
Defined in `tax_report.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
- Mozambique's tax administration is managed by the Autoridade Tributária de Moçambique (AT)
