---
tags: [odoo, odoo17, module, l10n, localization, usa]
research_depth: medium
---

# L10N US — United States Localization

**Source:** `addons/l10n_us/models/`

## Overview

United States country localization. Adds US-specific bank account fields and data for configuring US companies. Acts as the base module for US-specific accounting, tax, and reporting needs.

## Key Models

### res.partner.bank — ABA Routing Number

Extends `res.partner.bank` with the US routing number (ABA/routing transit number).

| Field | Type | Description |
|-------|------|-------------|
| `aba_routing` | Char | ABA/Routing number (1–9 digits) |

**Validation:** `_check_aba_routing()` constrains `aba_routing` to digits only, max 9 characters. Used for ACH transfers and wire payments in US bank accounts.

## Data

### res_company_data.xml

Loads US-specific demo data for the `base.us` demo company, including chart of accounts configured for US GAAP.

## See Also

- [Modules/account](modules/account.md) — accounting framework
- [Modules/l10n_generic_coa](modules/l10n_generic_coa.md) — generic chart of accounts template