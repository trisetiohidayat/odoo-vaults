---
Module: l10n_es
Version: 5.4
Type: addon
Tags: #odoo18 #l10n_es #localization #spain #sii #verifactu #simplified-invoice
---

## Overview

**Module:** `l10n_es`
**Depends:** `account`, `base_iban`, `base_vat`
**Auto-install:** `account`
**Location:** `~/odoo/odoo18/odoo/addons/l10n_es/`
**License:** LGPL-3
**Countries:** ES (Spain)
**Purpose:** Spanish accounting localization. Provides PGCE 2008 chart of accounts (full/PYMES/association variants), simplified invoice detection, Spanish tax types and exemption codes, fiscal positions, and tax reports (Mod 111, 115, 303, 390, 420). Updated for 2024 VAT changes (BOE-A-2024-12944).

---

## Models

### `account.move` (models/account_move.py, 1–29)

Inherits: `account.move`

| Field | Type | Line | Description |
|---|---|---|---|
| `l10n_es_is_simplified` | Boolean (compute/store) | 7 | `True` if the move is a Spanish simplified invoice (ticket facturas). |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_l10n_es_is_simplified()` | `@api.depends` | 16 | Auto-detects simplified invoices: no partner VAT + amount <= `l10n_es_simplified_invoice_limit` + European partner. Also True for designated simplified-partner moves or receipt-type moves. |
| `_l10n_es_is_dua()` | regular | 28 | Returns True if any invoice line tax has `l10n_es_type == 'dua'` (customs declaration). |

### `account.tax` (models/account_tax.py, 1–80)

Inherits: `account.tax`

| Field | Type | Line | Description |
|---|---|---|---|
| `l10n_es_exempt_reason` | Selection | 8 | Exemption reason: E1 (Art.20), E2 (Art.21), E3 (Art.22), E4 (Art.23/24), E5 (Art.25), E6 (Otros). |
| `l10n_es_type` | Selection | 18 | Tax type: `exento`, `sujeto`, `sujeto_agricultura`, `sujeto_isp`, `no_sujeto`, `no_sujeto_loc`, `no_deducible`, `retencion`, `recargo` (Equivalence surcharge), `dua`, `ignore`. Default `sujeto`. |
| `l10n_es_bien_inversion` | Boolean | 38 | "Bien de Inversion" — capital goods flag for invoices with reverse charge. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_l10n_es_get_regime_code()` | regular | 43 | Returns EDI regime code (ClaveRegimenEspecialOTrascendencia): `'17'` for OSS, `'02'` for E2 exemption, `'01'` otherwise. |
| `_l10n_es_get_sujeto_tax_types()` | `@api.model` | 62 | Returns `['sujeto', 'sujeto_isp', 'sujeto_agricultura']` — taxable subject types. |
| `_l10n_es_get_main_tax_types()` | `@api.model` | 67 | Returns main taxable type set for Spain. |

### `res.partner` (models/res_partner.py, 1–37)

Inherits: `res.partner`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_l10n_es_is_foreign()` | regular | 7 | Returns True if partner is non-Spanish (country not ES or VAT starts with `ESN`). |
| `_l10n_es_edi_get_partner_info()` | regular | 14 | Returns partner info dict for SII/Veri*Factu EDI: `NIF` for Spanish partners, `IDOtro` with IDType per country (02=EU, 04=non-EU with VAT, 06=non-EU no VAT). |

### `res.company` (models/res_company.py, 1–9)

Inherits: `res.company`

| Field | Type | Line | Description |
|---|---|---|---|
| `l10n_es_simplified_invoice_limit` | Float | 6 | Maximum amount for simplified invoices (default: 400 EUR). |

### `res.config.settings` (models/res_config_settings.py, 1–9)

Inherits: `res.config.settings`

| Field | Type | Line | Description |
|---|---|---|---|
| `l10n_es_simplified_invoice_limit` | Float (related) | 6 | Related to company; allows setting simplified invoice limit from settings. |

---

## Chart of Accounts Variants

| Template | Code | Description |
|---|---|---|
| PGCE 2008 Full | `es_full` | Full Spanish general chart (all account types). |
| PGCE 2008 PYMES | `es_pymes` | SME version of Spanish chart. |
| PGCE 2008 Associations | `es_assec` | For non-profit associations. |
| Canary Islands Full | `es_canary_full` | Canary Islands variant (IGIC instead of IVA). |
| Canary Islands PYMES | `es_canary_pymes` | Canary Islands SME. |
| Canary Islands Association | `es_canary_assoc` | Canary Islands non-profits. |
| Cooperatives Full | `es_coop_full` | Full cooperative variant. |
| Cooperatives PYMES | `es_coop_pymes` | Cooperative SME variant. |

**Canary Islands note:** Uses IGIC (Canary Islands General Indirect Tax) instead of IVA. Different tax rates apply.

---

## Tax Reports

- **Mod 111**: Annual summary of withholdings (retentions).
- **Mod 115**: Tax withholdings on rental income.
- **Mod 303**: Quarterly self-assessment VAT return (autoliquidacion).
- **Mod 390**: Annual VAT return (complete version of Mod 303).
- **Mod 420**: Monthly/quarterly tax return for certain regimes.

---

## Critical Notes

- **Simplified Invoices**: Auto-detected when European customer has no VAT and total is within the configured limit.
- **Equivalence Surcharge (Recargo de Equivalencia)**: Special tax added by wholesalers on retail sales — defined via `l10n_es_type = 'recargo'`.
- **DUA (DUAs)**: Customs declarations — `l10n_es_type = 'dua'` for import tax handling.
- **NIF vs IDOtro**: Spanish partners send NIF (VAT without ES prefix); EU partners send IDOtro with type 02; non-EU partners send type 04 (with VAT) or 06 (without).
- **2024 Tax Update**: Tax rates updated per RD 4/2024 (BOE-A-2024-12944).
- **IGIC**: Canary Islands use IGIC (0%, 3%, 7%, 15% rates) instead of IVA (IVA is not applicable in Canary Islands).
- v17→v18: Veri*Factu EDI module (l10n_es_edi_verifactu) added; simplified invoice detection enhanced.
