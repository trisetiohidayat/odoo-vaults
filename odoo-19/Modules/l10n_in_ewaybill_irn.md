---
type: module
module: l10n_in_ewaybill_irn
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# India Accounting Localization (`l10n_in_ewaybill_irn`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Indian - E-waybill thru IRN |
| **Technical** | `l10n_in_ewaybill_irn` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Indian - E-waybill thru IRN
====================================
This module enables to generate E-waybill through IRN.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_in_ewaybill` | Dependency |
| `l10n_in_edi` | Dependency |

## Technical Notes
- Country code: `in` (India)
- Localization type: e-waybill via IRN
- Custom model files: l10n_in_ewaybill.py

## Models

### `l10n.in.ewaybill` (Extended)
Extends e-waybill to generate via IRN (Invoice Registration Number) from GST portal.

## Related
- [Modules/l10n_in](modules/l10n_in.md) — Core Indian accounting
- [Modules/l10n_in_edi](modules/l10n_in_edi.md) — Indian e-invoice (IRN/e-invoice)
- [Modules/l10n_in_ewaybill](modules/l10n_in_ewaybill.md) — Indian e-waybill base