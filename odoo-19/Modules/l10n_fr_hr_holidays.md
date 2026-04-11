---
type: module
module: l10n_fr_hr_holidays
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# France Accounting Localization (`l10n_fr_hr_holidays`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Management of leaves for part-time workers in France |
| **Technical** | `l10n_fr_hr_holidays` |
| **Category** | Human Resources/Time Off |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Management of leaves for part-time workers in France

## Dependencies
| Module | Purpose |
|--------|---------|
| `hr_holidays` | Dependency |

## Technical Notes
- Country code: `fr` (France)
- Localization type: HR/Time Off (French part-time worker leave management)
- Custom model files: hr_leave.py, res_company.py, res_config_settings.py

## Models

### `hr.leave` (Extended)
Extends leave requests with French-specific rules for part-time workers (RTT - Réduction du Temps de Travail).

### `res.company` (Extended)
French company-specific HR settings.

## Related
- [[Modules/l10n_fr]] — Core French accounting
- [[Modules/hr_holidays]] — Base leave management
- [[Modules/l10n_fr_hr_work_entry_holidays]] — French work entry generation for leaves