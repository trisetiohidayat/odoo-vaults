---
Module: l10n_es_modelo130
Version: 18.0
Type: l10n/es
Tags: #odoo18 #l10n #accounting
---

# l10n_es_modelo130

## Overview
Spain Modelo 130 tax report module. Extends the Spanish base localization (`l10n_es`) to add the Modelo 130 declaration — a quarterly self-assessment form for self-employed taxpayers in the direct assessment system. Depends entirely on `l10n_es` for the chart of accounts and base tax data.

## Country
[[Modules/Account|Spain]] 🇪🇸

## Dependencies
- [[Modules/Account|l10n_es]]

## Key Models

No custom model classes. Report is defined entirely in XML data.

### AccountChartTemplate
`__init__.py` — `_add_mod130_tax_tags()` post-init hook: searches for Spanish retention (`l10n_es_type = 'retencion'`) sale tax repartition lines, finds `-mod130[06]` and `+mod130[06]` account tags, and adds them to the respective tax repartition lines (invoice or refund side). This links withholding taxes to the Modelo 130 report.

## Data Files
- `data/mod130.xml` — `account.report` definition for Modelo 130

### Modelo 130 Report Structure

**Section I: Economic activities (non-agriculture)**
| Box | Code | Description | Engine | Formula |
|---|---|---|---|---|
| 01 | `aeat_mod_130_01` | Revenue | domain | Income accounts, non-agriculture; -sum |
| 02 | `aeat_mod_130_02` | Supplies | domain | Expense accounts, non-agriculture; sum |
| 03 | `aeat_mod_130_03` | Box 01 - 02 | aggregation | `01.balance - 02.balance` |
| 04 | `aeat_mod_130_04` | 20% on Box 03 | aggregation | `03.balance * 20%`; if_above(EUR 0) |
| 05 | `aeat_mod_130_05` | Prior quarter residual | external | editable; rounding=2 |
| 06 | `aeat_mod_130_06` | Withholdings sum | tax_tags + domain | `-mod130[06]` tag on income; sum |
| 07 | `aeat_mod_130_07` | Net: 04 - 05 - 06 | aggregation | `04.balance - 05.balance - 06.balance` |

**Section II: Agriculture**
| Box | Code | Description | Engine | Formula |
|---|---|---|---|---|
| 08 | `aeat_mod_130_08` | Revenue (agriculture) | domain | Income accounts, industry='Agriculture' |
| 09 | `aeat_mod_130_09` | 2% on Box 08 | aggregation | `08.balance * 2%`; if_above(EUR 0) |
| 10 | `aeat_mod_130_10` | Withholdings (agriculture) | tax_tags + domain | `mod130[06]` tag on agriculture income |
| 11 | `aeat_mod_130_11` | Net: 09 - 10 | aggregation | `09.balance - 10.balance` |

**Section III: Settlement**
| Box | Code | Description |
|---|---|---|
| 12 | `aeat_mod_130_12` | Total: 07 + 11; if_above(EUR 0) |
| 13 | `aeat_mod_130_13` | Prior year net earnings reduction (editable) |
| 14 | `aeat_mod_130_14` | 12 - 13 |
| 15 | `aeat_mod_130_15` | Negative prior self-assessments (editable) |
| 16 | `aeat_mod_130_16` | Loan deduction for housing (editable) |
| 17 | `aeat_mod_130_17` | 14 - 15 - 16 |
| 18 | `aeat_mod_130_18` | Complementary declaration (editable; if_above(EUR 0)) |
| 19 | `aeat_mod_130_19` | Final: 17 - 18 |

Report settings: `filter_multi_company: tax_units` (supports Spanish tax unit consolidation), `filter_journals: True`.

## Chart of Accounts
Inherits from [[Modules/Account|l10n_es]].

## Tax Structure
Withholding taxes (retenciones) in l10n_es carry `-mod130[06]` / `+mod130[06]` tags post-install.

## Fiscal Positions
Inherits from [[Modules/Account|l10n_es]].

## EDI/Fiscal Reporting
AEAT (Agencia Tributaria) Modelo 130 quarterly declaration format.

## Installation
No `auto_install`. Install manually after `l10n_es`.

Post-init hook: `_add_mod130_tax_tags` — runs after l10n_es data is loaded to add mod130 tags to retention tax repartition lines.

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; Modelo 130 report structure has been stable
- Tax tag attachment via post-init hook is an established pattern for Spanish AEAT reports
- Box 06 aggregation via tax_tags engine links withholding taxes to the declaration automatically
- `filter_multi_company: tax_units` support is important for Spanish tax group scenarios

**Performance Notes:**
- Report engine evaluation is on-demand (when user opens report); no background overhead
- Tax tag assignment runs once on install — negligible performance impact