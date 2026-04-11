---
Module: l10n_it
Version: 0.7
Type: addon
Tags: #odoo18 #l10n_it #localization #italy #exoneration #split-payment #edi
---

## Overview

**Module:** `l10n_it`
**Depends:** `account`, `base_iban`, `base_vat`
**Auto-install:** `account`
**Location:** `~/odoo/odoo18/odoo/addons/l10n_it/`
**License:** LGPL-3
**Countries:** IT (Italy)
**Purpose:** Italian accounting localization. Provides Italian chart of accounts (PC), VAT/exempt exoneration codes, split payment support, reverse charge, monthly and annual tax reports (Liquidazione IVA, Dichiarazione IVA), and SdI EDI compatibility.

---

## Models

### `account.move` (models/account_move.py, 1–10)

Inherits: `account.move`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_message_set_main_attachment_id(attachments, force=False, filter_xml=True)` | override | 5 | For pkcs7-mime attachments: forces attachment as main to support Italian digital signature flow. |

### `account.tax` (models/account_tax.py, 1–78)

Inherits: `account.tax`

| Field | Type | Line | Description |
|---|---|---|---|
| `l10n_it_exempt_reason` | Selection | 8 | Italian exoneration code (N1–N7 series). Required for 0% taxes. See selection values: N1 (Art.15), N2 (Non soggette), N3 (Non imponibili), N4 (Esenti), N5 (Margine), N6 (Reverse charge), N7 (IVA assolta altrove). |
| `l10n_it_law_reference` | Char (size=100) | 54 | Law reference for exoneration. Required when `l10n_it_exempt_reason` is set. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_l10n_it_edi_check_exoneration_with_no_tax()` | `@api.constrains` | 57 | For IT companies: requires both exoneration code AND law reference when tax amount is 0%. Also blocks N6 + split payment combination. |
| `_l10n_it_filter_kind(kind)` | regular | 68 | Filters taxes by kind for EDI: returns only non-negative amounts for 'vat'. |
| `_l10n_it_is_split_payment()` | regular | 77 | Checks if tax is tagged for split payment via VE38 tax report line. Split payment means Public Administration pays VAT directly to tax agency. |

### `account.report.expression` (models/account_report.py, 1–15)

Inherits: `account.report.expression`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_get_carryover_target_expression(options)` | override | 6 | For VP14b line in December: redirects carryover to VP9 instead of VP8 (end-of-year adjustment). |

### Chart Template (models/template_it.py)

`AccountChartTemplate` (abstract, `account.chart.template`):

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_get_it_template_data()` | `@template('it')` | — | Sets Italian PC chart defaults: receivable 1501, payable 2501, expense 4101, income 3101, 4 code digits. |
| `_get_it_res_company()` | `@template('it', 'res.company')` | — | Sets IT fiscal country, bank prefix 182, cash 180, transfer 183, 22% VAT default, `round_globally` tax rounding. |

---

## Data

**XML:** `data/account_account_tag.xml` — Italian account classification tags.
**Tax Reports:** Monthly (VP lines) and annual (VA, VE, VF, VH, VJ, VL sections) IVA reports.
**Views:** `views/account_tax_views.xml`.

---

## Critical Notes

- **Split Payment**: Italian mechanism where Public Administration buyers pay VAT directly to the tax agency instead of the vendor. N6 exoneration is incompatible with split payment.
- **0% Tax Validation**: Zero-rated Italian taxes MUST have both exoneration code and law reference.
- **Exoneration codes**: N1–N7 cover all Italian fiscal exoneration scenarios (Art.15 exclusions, reverse charge, extra-UE, etc.).
- **Tax Rounding**: Italy uses `round_globally` — all taxes computed globally before rounding, not per line.
- **Monthly Tax Report (Liquidazione IVA)**: VP lines for periodic IVA declaration.
- **Annual Tax Report (Dichiarazione IVA)**: VA (operations by rate), VE (exports), VF (non-resident), VH/VJ/VL (special cases).
- v17→v18: No breaking changes.
