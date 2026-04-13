---
type: module
module: l10n_dk
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Denmark Accounting Localization (`l10n_dk`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Localization Module for Denmark |
| **Technical** | `l10n_dk` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Localization Module for Denmark
===============================

This is the module to manage the **accounting chart for Denmark**. Cover both one-man business as well as I/S, IVS, ApS and A/S

**Modulet opsætter:**

- **Dansk kontoplan**

- Dansk moms
        - 25 % moms
        - Restaurationsmoms 6,25 %
        - Omvendt betalingspligt

- Konteringsgrupper
        - EU (Virksomhed)
        - EU (Privat)
        - Tredjelande

- Finansrapporter
        - Resultatopgørelse
        - Balance
        - Momsafregning
            - Afregning
            - Rubrik A, B og C

- **Anglo-saksisk regnskabsmetode**

.

Produktopsætning:
=================

**Vare**

**Salgsmoms:**      Salgsmoms 25 %

**Salgskonto:**     1.010 Salg af varer inkl. moms

**Købsmoms:**       Købsmoms 25 %

**Købskonto:**      2.010 Direkte vareomkostninger inkl. moms

.

**Ydelse**

**Salgsmoms:**      Salgsmoms 25 %, ydelser

**Salgskonto:**     1.011 Salg af ydelser inkl. moms

**Købsmoms:**       Købsmoms 25 %, ydelser

**Købskonto:**      2.011 Direkte omkostninger ydelser inkl. moms

.

**Vare med omvendt betalingspligt**

**Salgsmoms:**      Salg med omvendt betalingspligt

**Salgskonto:**     1.012 Salg af varer ekskl. moms

**Købsmoms:**       Køb med omvendt betalingspligt

**Købskonto:**      2.012 Direkte vareomkostninger ekskl. moms


.

**Restauration**

**Købsmoms:**       Restaurationsmoms 6,25 %, købsmoms

**Købskonto:**      4010 Restaurationsbesøg

## Dependencies
| Module | Purpose |
|--------|---------|
| `base_iban` | Dependency |
| `base_vat` | Dependency |
| `account` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `dk`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_journal.py, account_account.py, template_dk.py, res_partner.py

## Related
- [Modules/l10n_dk](odoo-18/Modules/l10n_dk.md) - Core accounting