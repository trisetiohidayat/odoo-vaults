---
type: module
module: l10n_it_stock_ddt
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Italy Accounting Localization (`l10n_it_stock_ddt`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Documento di Trasporto (DDT) |
| **Technical** | `l10n_it_stock_ddt` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Documento di Trasporto (DDT)

Whenever goods are transferred between A and B, the DDT serves
as a legitimation e.g. when the police would stop you.

When you want to print an outgoing picking in an Italian company,
it will print you the DDT instead.  It is like the delivery
slip, but it also contains the value of the product,
the transportation reason, the carrier, ... which make it a DDT.

We also use a separate sequence for the DDT as the number should not
have any gaps and should only be applied at the moment the goods are sent.

When invoices are related to their sale order and the sale order with the
delivery, the system will automatically calculate the linked DDTs for every
invoice line to export in the FatturaPA XML.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_it_edi` | Dependency |
| `stock_delivery` | Dependency |
| `stock_account` | Dependency |

## Technical Notes
- Country code: `it`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_invoice.py, stock_picking.py

## Related
- [Modules/l10n_it](l10n_it.md) - Core accounting