---
Module: account_update_tax_tags
Version: 18.0
Type: addon
Tags: #account, #tax
---

# account_update_tax_tags — Allow updating tax grids on existing entries

## Module Overview

**Category:** Accounting/Accounting
**Depends:** `account`
**License:** LGPL-3
**Installable:** True

Enables updating of tax tags/grids on existing accounting journal entries. In debug mode, a button appears in **Accounting Settings** to trigger the wizard. Useful after legal changes to the tax report requiring new tax grid configurations.

## Data Files

- `security/ir.model.access.csv` — ACL for wizard
- `views/res_config_settings_views.xml` — Settings button to open wizard
- `wizard/account_update_tax_tags_wizard.xml` — Wizard form view

## Models

### `account.update.tax.tags.wizard` (`account.update.tax.tags.wizard`)

Transient wizard for updating tax tags on existing journal items.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `company_id` | Many2one (res.company) | Target company (required, readonly, default: current company) |
| `date_from` | Date | Start date for updates; computed as `tax_lock_date + 1 day` if lock date set |
| `display_lock_date_warning` | Boolean | Computed flag: True if `date_from` is before the tax lock date |

**Compute Methods:**

**`_compute_date_from`**
Sets `date_from` to the day after the company's tax lock date, or today if no lock date is set.

**`_compute_display_lock_date_warning`**
True when `date_from` precedes the tax lock date.

**Business Methods:**

**`_modify_tag_to_aml_relation(company_id, date_from)`**
Low-level SQL method that rebuilds the tax-tag relations for all `account.move.line` records matching the company and date threshold. The SQL logic:
1. Queries base lines (via `account_move_line_account_tax_rel` + tax children traversal)
2. Queries tax lines (via `tax_repartition_line_id`)
3. UNIONs both into `base_and_tax_aml_tag_id`
4. DELETEs existing `account_account_tag_account_move_line_rel` entries
5. INSERTs new relations based on current tax repartition line tags
6. Returns array of affected AML IDs

Handles all document types (invoice, refund, entry), cash basis moves, and complex tax filiation trees.

**`update_amls_tax_tags()`**
Action method called from the wizard button. Validates no children taxes belong to multiple parents, then calls `_modify_tag_to_aml_relation`.

## What It Extends

- Extends `account` with a tool to retroactively update tax tag relationships on posted journal entries after tax configuration changes.

## Key Behavior

- Only affects entries on or after `date_from`.
- Respects the company's tax lock date with a warning.
- Children taxes must belong to exactly one parent (no multi-parent trees in the update).
- Uses raw SQL for performance across large datasets.

## See Also

- [Modules/Account](modules/account.md) — the base accounting module
- [Core/API](core/api.md) — `@api.depends`, `@api.constrains`
