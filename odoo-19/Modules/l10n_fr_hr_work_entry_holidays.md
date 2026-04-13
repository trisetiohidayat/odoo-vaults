---
type: module
module: l10n_fr_hr_work_entry_holidays
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# France Accounting Localization (`l10n_fr_hr_work_entry_holidays`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Management of leaves for part-time workers in France |
| **Technical** | `l10n_fr_hr_work_entry_holidays` |
| **Category** |  |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Management of leaves for part-time workers in France

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_fr_hr_holidays` | Dependency |
| `hr_work_entry_holidays` | Dependency |

## Technical Notes
- Country code: `fr` (France)
- Localization type: HR/Time Off (French work entry generation for leaves)
- Custom model files: hr_version.py, hr_work_entry.py

## Models

### `hr.version` (Extended)
French-specific work entry version generation for leave requests.

### `hr.work.entry` (Extended)
French work entry handling for leave types (part-time RTT, public holidays).

## Related
- [Modules/l10n_fr](modules/l10n_fr.md) — Core French accounting
- [Modules/l10n_fr_hr_holidays](modules/l10n_fr_hr_holidays.md) — French leave management
- [Modules/hr_work_entry_holidays](modules/hr_work_entry_holidays.md) — Work entry generation for leaves