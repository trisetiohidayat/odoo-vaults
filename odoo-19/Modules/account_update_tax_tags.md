---
type: module
module: account_update_tax_tags
tags: [odoo, odoo19, account, invoicing, tax, accounting]
created: 2026-04-06
---

# Account - Allow Updating Tax Grids

## Overview
| Property | Value |
|----------|-------|
| **Name** | Account - Allow updating tax grids |
| **Technical** | `account_update_tax_tags` |
| **Category** | Accounting/Accounting |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Allows updating tax grids (account tags) on existing accounting journal entries in debug mode. Useful when legal changes to the tax report require a new tax configuration to be applied retroactively to existing entries.

## Dependencies
- `account`

## Key Models
| Model | Type | Description |
|-------|------|-------------|
| `account.update.tax.tags.wizard` | TransientModel | Wizard for batch-updating tax tags |

## `account.update.tax.tags.wizard`
### Fields
| Field | Type | Description |
|-------|------|-------------|
| `company_id` | Many2one | Target company (required) |
| `date_from` | Date | Starting date for update; defaults to day after tax lock date |
| `display_lock_date_warning` | Boolean | Warning if `date_from` precedes tax lock date |

### Methods
| Method | Purpose |
|--------|---------|
| `_compute_date_from` | Sets `date_from` = `tax_lock_date + 1 day`, or today if no lock |
| `_compute_display_lock_date_warning` | Shows warning if date_from < tax_lock_date |
| `update_amls_tax_tags` | Entry point: validates no multi-parent children taxes, then calls SQL |
| `_modify_tag_to_aml_relation` | Raw SQL: deletes old tag relations, inserts new ones based on current tax config |

### `_modify_tag_to_aml_relation` SQL Logic
1. **Base line query** — joins AML to tax, then to repartition line (handles `children_tax_ids`), left-joins to account tags
2. **Tax line query** — direct join from AML to `tax_repartition_line_id`, left-joins to account tags
3. **Delete** old `aml ↔ tag` relations for impacted AMLs
4. **Insert** new relations from current tax configuration
5. **Return** array of impacted AML IDs

Handles document types: invoice, refund, entry (balance-sign logic for entry type moves). Also handles cash basis origin moves via `tax_cash_basis_origin_move_id`.

## Related
- [Modules/account](Modules/Account.md)
