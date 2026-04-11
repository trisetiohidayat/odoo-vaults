---
type: module
module: l10n_qa
tags: [odoo, odoo19, l10n, localization, qatar, gcc]
created: 2026-04-06
---

# Qatar Localization (`l10n_qa`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Qatar - Accounting |
| **Technical** | `l10n_qa` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Qatar |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Localized accounting for Qatar. Activates chart of accounts for companies based in Qatar. Depends on `l10n_gcc_invoice` for Arabic bilingual invoice support.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Core accounting module |
| `l10n_gcc_invoice` | GCC Arabic bilingual invoice support |

## Technical Notes
- Country code: `qa`
- Localization type: accounting chart (taxes via GCC invoice)
- Template file: `models/template_qa.py` (Qatari chart of accounts)
- Demo data: `demo/demo_company.xml`

## Related
- [[Modules/account]]
- [[Modules/l10n_gcc_invoice]]
- [[Modules/l10n_sa]]
- [[Modules/l10n_kw]]
- [[Modules/l10n_om]]