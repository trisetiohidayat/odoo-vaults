---
type: module
module: l10n_kw
tags: [odoo, odoo19, l10n, localization, kuwait, gcc]
created: 2026-04-06
---

# Kuwait Localization (`l10n_kw`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Kuwait - Accounting |
| **Technical** | `l10n_kw` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Kuwait |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Localized accounting for Kuwait. Activates chart of accounts for companies based in Kuwait. Depends on `l10n_gcc_invoice` for Arabic bilingual invoice support.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Core accounting module |
| `l10n_gcc_invoice` | GCC Arabic bilingual invoice support |

## Technical Notes
- Country code: `kw`
- Localization type: accounting chart (taxes via GCC invoice)
- Template file: `models/template_kw.py` (Kuwaiti chart of accounts)
- Demo data: `demo/demo_company.xml`

## Related
- [Modules/account](Modules/Account.md)
- [Modules/l10n_gcc_invoice](Modules/l10n_gcc_invoice.md)
- [Modules/l10n_sa](Modules/l10n_sa.md)
- [Modules/l10n_om](Modules/l10n_om.md)
- [Modules/l10n_qa](Modules/l10n_qa.md)