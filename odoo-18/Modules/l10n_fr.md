---
Module: l10n_fr
Version: 2.1
Type: addon
Tags: #odoo18 #l10n_fr #localization #france #siret #securalisation
---

## Overview

**Module:** `l10n_fr`
**Depends:** `base`
**Location:** `~/odoo/odoo18/odoo/addons/l10n_fr/`
**License:** LGPL-3
**Countries:** FR (France), MF, MQ, NC, PF, RE, GF, GP, TF, BL, PM, YT, WF (DOM-TOM)
**Purpose:** French localization. Adds SIRET/SIREN on partners and companies, French accounting secu alerisation sequence, and France/DOM-TOM country code detection. Does not provide a full chart of accounts (that is in `l10n_fr_account`).

---

## Models

### `res.partner` (models/res_partner.py, 1–14)

Inherits: `res.partner`

| Field | Type | Line | Description |
|---|---|---|---|
| `siret` | Char (size=14) | 7 | French SIRET number (14 digits: 9-digit SIREN + 5-digit NIC). |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_deduce_country_code()` | override | 9 | Returns `'FR'` if `siret` is set, regardless of address country. Used for tax jurisdiction detection. |
| `_peppol_eas_endpoint_depends()` | override | 13 | Adds `siret` to PEPPOL EAS endpoint dependencies for French EDI. |

### `res.company` (models/res_company.py, 1–72)

Inherits: `res.company`

| Field | Type | Line | Description |
|---|---|---|---|
| `l10n_fr_closing_sequence_id` | Many2one (`ir.sequence`) | 10 | Sequence for sale closings (unbreakable). |
| `siret` | Char (related to `partner_id.siret`, size=14) | 12 | SIRET (related). |
| `ape` | Char | 13 | APE code (Activity Main Code, code NAF). |
| `is_france_country` | Boolean (compute) | 15 | True for France and all DOM-TOM country codes. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_is_france_country()` | `@api.depends('country_code')` | 22 | Sets True if `country_code in ['FR', 'MF', 'MQ', 'NC', 'PF', 'RE', 'GF', 'GP', 'TF', 'BL', 'PM', 'YT', 'WF']`. |
| `_get_france_country_codes()` | `@api.model` | 29 | Returns all France/DOM-TOM country codes. |
| `_is_accounting_unalterable()` | override | 37 | Returns True for French companies (has VAT or country in France/DOM-TOM). Determines if secu alerisation is required. |
| `create(vals_list)` | `@api.model_create_multi` | 44 | Creates secu alerisation sequence for French companies on creation. |
| `write(vals)` | override | 57 | Creates secu alerisation sequence when country changes to France. |
| `_create_secure_sequence(sequence_fields)` | private | 63 | Creates a `no_gap` sequence (no gaps allowed) named `FRSECURE{company_id}-{field}` to ensure continuous numbering for audit compliance. |

---

## Security / Data

`data/res_country_data.xml`: France and DOM-TOM country records.
`views/res_partner_views.xml`, `views/res_company_views.xml`: SIRET/APE fields.
`demo/l10n_fr_demo.xml`: Demo data.

---

## Critical Notes

- French companies are marked as "unalterable accounting" — they require the no-gap secu alerisation sequence for posted moves.
- SIRET derivation: SIREN (9 digits, company-level) + NIC (5 digits, establishment-level) = 14 digits total.
- APE code: Activite Principale de l'Entreprise — industry classification code.
- `_is_accounting_unalterable()` check is used by account module for secu alerisation rules.
- v17→v18: No breaking changes.
