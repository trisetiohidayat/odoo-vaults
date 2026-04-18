---
type: module
module: l10n_eg
tags: [odoo, odoo19, localization, egypt, eta, e-invoicing]
created: 2026-04-06
---

# Egypt - Localization

## Overview
| Property | Value |
|----------|-------|
| **Name** | Egypt - Accounting |
| **Technical** | `l10n_eg` |
| **Category** | Localization |
| **Country** | Egypt |

## Description
Localized accounting for Egypt. Activates chart of accounts, taxes, VAT return, withholding tax report, schedule tax report, other taxes report, and fiscal positions.

## Dependencies
- `account`

## Key Models

### `account.tax` (Extended)
Inherits `account.tax` to add Egyptian ETA (Egyptian Tax Authority) codes:

| Field | Type | Description |
|-------|------|-------------|
| `l10n_eg_eta_code` | Selection | ETA code classifying the tax type (e.g., export, exempt, table tax, withholding) |

**ETA Code Categories:**
- T1: Export and exemptions (V001-V010)
- T2/T3: Table taxes (percentage/fixed)
- T4: Withholding (contracting, supplies, services, commissions, etc.)
- T5/T6: Stamping taxes
- T7: Entertainment taxes
- T8-T12: Various fees (resource development, service charges, municipality, medical insurance, other)
- T13-T20: Additional tax variants

## Related
- [Modules/account](Modules/Account.md)
