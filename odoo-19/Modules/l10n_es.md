# l10n_es - Spain Accounting (PGCE 2008)

## Overview
- **Name:** Spain - Accounting (PGCE 2008)
- **Country:** Spain (ES)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 5.4
- **Author:** Spanish Localization Team
- **License:** LGPL-3
- **Dependencies:** `account`, `base_iban`, `base_vat`, `account_edi_ubl_cii`
- **Auto-installs:** `account`

## Description
Full Spanish accounting chart based on Plan General de Contabilidad (PGCE) 2008. Includes:
- Multiple chart templates (full, PyMEs/SME, associations, cooperatives)
- VAT tax templates
- Fiscal positions for Spanish legislation
- Tax report modules: Mod 111, 115, 130, 303, 390, 420

## Models

### account.tax (Inherit)
Extends `account.tax` with Spain-specific fields:
- **l10n_es_exempt_reason:** Exemption reason selection (E1-E6 per Art. 20-25)
- **l10n_es_type:** Tax type: `exento`, `sujeto`, `sujeto_agricultura`, `sujeto_isp`, `no_sujeto`, `no_sujeto_loc`, `no_deducible`, `retencion`, `recargo` (Equivalence surcharge), `dua`, `ignore`
- **l10n_es_bien_inversion:** Capital goods flag (Boolean)
- **_l10n_es_get_regime_code():** Returns EDI regime code (01, 02, 17 for OSS)
- **_l10n_es_get_sujeto_tax_types() / _get_main_tax_types():** Helpers for tax classification

### account.move (Inherit)
Extends `account.move`:
- **l10n_es_is_simplified:** Computed Boolean — invoice is simplified if partner is "Consumidor Final" or amount <= limit with EU partner
- **_compute_l10n_es_is_simplified():** Auto-detects based on partner, VAT, and `l10n_es_simplified_invoice_limit` (default EUR 400)
- **_l10n_es_is_dua():** Checks if any line has a DUA tax type

### res.partner (Inherit)
Extends `res.partner`:
- **_l10n_es_is_foreign():** True if country != ES or VAT starts with "ESN"
- **_l10n_es_edi_get_partner_info():** Returns NIF/IDOtro dict for SII and Veri*factu EDI — handles Spanish, EU, and foreign partners

### res.company (Inherit)
Extends `res.company`:
- **l10n_es_simplified_invoice_limit:** Float (default 400 EUR) — threshold for simplified invoices

### res.config.settings (Inherit)
Extends `res.config.settings`:
- **l10n_es_simplified_invoice_limit:** Related field to company setting

## Chart Templates
- `template_es_full` — Full PGCE 2008
- `template_es_pymes` — SME variant
- `template_es_common` / `template_es_common_mainland` — Common accounts
- `template_es_canary_*` — Canary Islands variants
- `template_es_coop_*` — Cooperative variants
- `template_es_assec` — Associations

## Tax Reports
- **Mod 111** — IRPF withholding (data/mod111.xml)
- **Mod 115** — IRPF rental withholding
- **Mod 130** — IRPF professional self-assessment
- **Mod 303** — VAT quarterly return
- **Mod 390** — Annual VAT summary (7 sections)
- **Mod 420** — VAT for Canary Islands

## EDI Modules
- **l10n_es_edi_sii** — Immediate Supply of Information (SII)
- **l10n_es_edi_facturae** — Facturae format
- **l10n_es_edi_tbai** — Basque country (TicketBAI)
- **l10n_es_edi_verifactu** — Veri*factu (mandatory from 2024)
