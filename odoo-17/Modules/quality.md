---
tags: [odoo, odoo17, module, quality, quality_control]
research_depth: confirmed_absent
---

# Quality Module — Deep Reference

**Source:** `addons/quality/` and `addons/quality_control/` — **NOT PRESENT in this Odoo 17 installation**

## Availability in Odoo 17

The `quality` and `quality_control` modules are **not included** in the base Odoo 17 community edition addons at the path:

```
/Users/tri-mac/odoo/odoo17/odoo/addons/
```

A search for `quality*`, `qc*`, `inspect*` in the addons directory returned no results. These modules are typically found in:

1. **Odoo Enterprise** — `quality_control` / `quality` are enterprise addons
2. **Odoo Apps** — available separately in the Odoo Marketplace
3. **Odoo.sh / official docker images** — may be included in the enterprise image

## What Quality Features Exist in Community Odoo 17

In the community edition, quality-related functionality is built into the `stock` module itself:

### Stock Move Quality Controls

`stock.move` in community Odoo 17 has quality-related fields:

| Field | Type | Description |
|-------|------|-------------|
| `quality_check_ids` | One2many | Linked quality checks |
| `quality_alert_ids` | One2many | Linked quality alerts |
| `quality_state` | Selection | `none` / `pass` / `fail` |

The quality state is set when a quality check is performed on a move.

### stock.picking Integration

Picking types (`stock.picking.type`) have quality-related settings:
- `count_packages_agagrid` — whether to count packages
- Quality checks can be triggered on `button_validate()` for incoming pickings

## If Installed (Enterprise / Apps)

When `quality_control` is available, it provides:

### quality.point

Defines inspection checkpoints:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Check name |
| `product_ids` | Many2many | Products to check |
| `picking_type_ids` | Many2many | Operations that trigger this check |
| `test_type_id` | Many2one | Type of check (pass/fail, measure, etc.) |
| `company_id` | Many2one | Company |
| `team_id` | Many2one | Quality team |

**Trigger types:**
- `operation` — triggers when a picking is validated
- `move_line` — triggers on specific move lines
- `product_product` — triggers on product receipt

### quality.alert

Records a quality issue:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Alert reference |
| `description` | Text | Issue description |
| `product_id` | Many2one | Affected product |
| `picking_id` | Many2one | Related picking |
| `lot_id` | Many2one | Lot/serial affected |
| `partner_id` | Many2one | Vendor/customer |
| `stage_id` | Many2one | Alert stage |
| `team_id` | Many2one | Quality team |
| `priority` | Selection | Priority level |

**Alert stages:** `draft` → `in_progress` → `done` / `cancel`

### quality.check

Individual inspection record:

| Field | Type | Description |
|-------|------|-------------|
| `point_id` | Many2one | Quality point |
| `control_date` | Datetime | When check was done |
| `product_id` | Many2one | Product checked |
| `lot_id` | Many2one | Lot/serial |
| `picking_id` | Many2one | Related operation |
| `result` | Selection | `pass` / `fail` |
| `measure` | Char | Actual measurement recorded |
| `note` | Text | Inspector comments |

## Quality Check Flow (Enterprise / Apps)

### At Receipt (Incoming)
1. Supplier delivers goods
2. Quality point triggers on `picking_type_id`
3. `quality.alert` created automatically on failure
4. QC team inspects
5. Pass → proceed with receipt; Fail → hold goods

### At Delivery (Outgoing)
1. Goods prepared for delivery
2. Quality check before shipping
3. Pass → validate picking; Fail → hold, create alert

### At Manufacturing
1. MO created
2. Quality check at production
3. Pass → continue; Fail → create alert, stop line

## Vault Note

Since the quality module is not present in this Odoo 17 installation, this page documents what the module provides when installed. For full quality documentation, either:

- Install the `quality_control` module from Odoo Enterprise / Apps
- Reference Odoo 18+ where quality modules are included in community

## See Also

- [Modules/stock](Modules/stock.md) — picking types, stock moves (includes quality fields in community)
- [Modules/mrp](Modules/mrp.md) — production quality integration
