---
Module: l10n_de
Version: 2.0
Type: addon
Tags: #odoo18 #l10n_de #localization #germany #datev #skr03 #skr04
---

## Overview

**Module:** `l10n_de`
**Depends:** `base_iban`, `base_vat`, `l10n_din5008`, `account`
**Auto-install:** `account`
**Location:** `~/odoo/odoo18/odoo/addons/l10n_de/`
**License:** LGPL-3
**Countries:** DE (Germany)
**Post-init hook:** `_post_init_hook` — activates `account_secured` group.
**Purpose:** German accounting localization providing SKR03 and SKR04 chart of accounts, DATEV-compatible tax codes, delivery date support for invoices, GoBD audit trail, and German-specific report layouts.

---

## Models

### `account.move` (models/account_move.py, 1–21)

Inherits: `account.move`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_show_delivery_date()` | `@api.depends('country_code', 'move_type')` | 6 | EXTENDS account. Forces `show_delivery_date=True` for DE sale documents. |
| `_post(soft=True)` | override | 12 | For DE sale documents without a delivery date: auto-sets `delivery_date = invoice_date` or today. |

### `res.company` (models/res_company.py, 1–52)

Inherits: `res.company`

| Field | Type | Line | Description |
|---|---|---|---|
| `l10n_de_stnr` | Char | 14 | "St.-Nr." (Steuernummer) — German tax number; scheme `??FF0BBBUUUUP`; tracked. |
| `l10n_de_widnr` | Char | 16 | "W-IdNr." — Business identification number (Wirtschafts-Identifikationsnummer); tracked. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `write(vals)` | override | 21 | Prevents changing `account_fiscal_country_id` away from DE if the company has any posted account moves. Raises `ValidationError`. |
| `_validate_l10n_de_stnr()` | `@api.constrains('state_id', 'l10n_de_stnr')` | 38 | Triggers validation of Steuernummer on state/country changes. |
| `get_l10n_de_stnr_national()` | regular | 42 | Validates and converts Steuernummer to national format using `stdnum.de.stnr`. Raises `ValidationError` on invalid components or format. Falls back to raw value for non-DE companies. |

### `account.tax` (models/datev.py, 1–7)

Inherits: `account.tax`

| Field | Type | Line | Description |
|---|---|---|---|
| `l10n_de_datev_code` | Char (size=4) | 4 | 4-digit DATEV code for the tax; tracked. Used in DATEV exports. |

### `account.journal` (models/account_journal.py, 1–17)

Inherits: `account.journal`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_prepare_liquidity_account_vals(company, code, vals)` | `@api.model` | 7 | EXTENDS account. For DE companies: adds `tag_de_asset_bs_B_IV` (transfer account tag) to liquidity account tag_ids. |

### `account.account` (models/account_account.py, 1–21)

Inherits: `account.account`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `write(vals)` | override | 5 | For DE companies: prevents changing account code if the account has been used in posted move lines. Raises `UserError`. |

### `product.template` (models/datev.py, 9–39)

Inherits: `product.template`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_get_product_accounts()` | override | 11 | For DE companies: searches for income/expense accounts matching the product's tax IDs, avoiding the constraint that requires taxes and accounts to share the same rate. |

### `ir.attachment` (models/ir_attachment.py, 1–54)

Inherits: `ir.attachment`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_except_audit_trail()` | `@api.ondelete(at_uninstall=True)` | 11 | Prevents deletion of attachments (PDF/XML) linked to posted account moves for DE companies with `check_account_audit_trail=True`. Raises `UserError`. |
| `write(vals)` | override | 24 | Intercepts write calls on audit-trail-attached files; redirects document versioning for document objects to prevent audit trail violation. |
| `unlink()` | override | 38 | For DE audit-trail attachments on invoices: detaches from field (keeps in DB), renames file with `(detached by User on Date)` suffix, then unlinks. |

### `ir.actions.report` (models/ir_actions_report.py, 1–11)

Inherits: `ir.actions.report`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_get_rendering_context(report, docids, data)` | override | 5 | EXTENDS account. Adds `din_header_spacing` from paper format to rendering context for DIN5008 layout compatibility. |

### Chart Templates (models/template_de_skr03.py, models/template_de_skr04.py)

`AccountChartTemplate` inheritance on `account.chart.template`:

**SKR03** — Standardkontenrahmen 03 (traditional German chart):
- 4-digit account codes
- Default accounts: receivable 1410, payable 1610, expense 3400, income 8400
- 19%/7% VAT and input tax
- Reconciliation models: 6 models (discount-EK, discount-VK, loss of receivables at 7% and 19%)
- Default paper format: Euro DIN

**SKR04** — Standardkontenrahmen 04 (DATEV-compatible):
- 4-digit account codes
- Default accounts: receivable 1205, payable 3301, expense 5400, income 4400
- Cash difference income/expense accounts (9991/9994)
- Same reconciliation models structure as SKR03

**Both charts set:**
- `account_fiscal_country_id = base.de`
- External report layout: `l10n_din5008.external_layout_din5008`
- Paper format: `l10n_din5008.paperformat_euro_din`
- Audit trail: `check_account_audit_trail = True` (GoBD compliance)

---

## Post-init Hook

`_post_init_hook(env)`: Calls `env['res.groups']._activate_group_account_secured()` to enable the secured accounting group for all companies.

---

## Data

**XML:** `data/account_account_tags_data.xml` — German account tags (SKR03/SKR04 BS/PL classifications).
**Views:** `views/account_view.xml`, `views/res_company_views.xml` — German-specific fields on forms.
**Wizard:** `wizard/account_secure_entries_wizard.xml` — GoBD audit trail wizard.
**Demo:** `demo/demo_company.xml` — Demo company with SKR03/SKR04.

---

## Critical Notes

- **GoBD Compliance**: `check_account_audit_trail` is auto-enabled. Invoice PDFs and XMLs linked to posted moves cannot be deleted — they are renamed and detached instead.
- **Delivery Date**: Auto-populated on invoice posting for DE sale documents.
- **SKR03 vs SKR04**: SKR04 is preferred for DATEV export compatibility; SKR03 is the traditional German standard.
- **Steuernummer validation**: Uses `stdnum.de.stnr` library to validate German tax numbers against state.
- **W-IdNr**: The 9-digit Wirtschafts-Identifikationsnummer is separate from VAT (USt-IdNr).
- **Account code changes**: Locked for accounts with posted move lines (DE companies).
- v17→v18: GoBD audit trail enhancements; delivery date auto-set behavior added.
