---
type: module
module: l10n_mt_pos
tags: [odoo, odoo19, l10n, localization, malta, pos, compliance]
created: 2026-04-06
---

# Malta POS (`l10n_mt_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Malta - Point of Sale |
| **Technical** | `l10n_mt_pos` |
| **Category** | Accounting/Localizations/Point of Sale |
| **Country** | Malta |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Malta Compliance Letter for EXO Number. Generates an official compliance letter documenting the POS application's features and controls as required by Maltese fiscal regulations. Provides a formal declaration from Odoo S.A. for compliance purposes.

## Dependencies
| Module | Purpose |
|--------|---------|
| `point_of_sale` | Core POS module |

## Key Models

### `compliance.letter.wizard`
Wizard model for generating compliance letters:

| Field | Type | Description |
|-------|------|-------------|
| `company_id` | Many2one | Company to generate letter for |

**Wizard Methods:**
- `generate_letter()`: Renders and returns the compliance letter report

## Reports

### Compliance Letter Report
QWeb report template `report_compliance_letter_template` containing:
- Odoo POS version declaration
- Company details (name, address, VAT)
- Formal declaration from Odoo S.A. (Belgian company BE0477472701)
- List of POS functions and controls (cash register monitoring, daily sales, payment integration, etc.)

## Security
Access control via `security/ir.model.access.csv`:
- `base.group_user`: Full CRUD on compliance letter wizard
- `base.group_system`: Full CRUD for admin access

## Technical Notes
- Countries: `mt`
- No model Python files - wizard logic lives in `wizards/compliance_letter.py`
- Menu: `point_of_sale.menu_point_rep` -> Malta EXO -> Compliance Letter

## Related
- [Modules/point_of_sale](point_of_sale.md)
- [Modules/l10n_mt](l10n_mt.md)