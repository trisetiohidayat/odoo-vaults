---
tags:
  - odoo
  - odoo19
  - modules
  - mrp
  - repair
  - subcontracting
  - security
---

# MRP Subcontracting Repair

## Overview

| Property | Value |
|----------|-------|
| **Module** | `mrp_subcontracting_repair` |
| **Edition** | Community Edition |
| **Category** | Supply Chain / Repair |
| **Summary** | Bridge module: allows portal subcontractors to access repair order stock moves |
| **Version** | `19.0.1.0.0` (manifest: `1.0`) |
| **Depends** | `mrp_subcontracting`, `repair` |
| **Auto-install** | `True` — installs automatically when both dependencies are present |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## L1 — How Landed Costs Apply to Subcontracting

> **Note:** Despite the name suggesting landed costs, this module has **nothing to do with landed costs**. It is a portal access / security bridge module for the repair-subcontracting integration. The name is slightly misleading; it is the counterpart to `mrp_subcontracting_landed_costs` (which does deal with landed costs), but `mrp_subcontracting_repair` focuses entirely on **repair order stock moves and portal user access**.

### The Business Scenario

When a company uses **subcontracting** with the **repair** workflow, the following situation arises:

1. A subcontractor receives materials for repair work
2. The repair order creates `stock.move` records (to consume parts, to receive repaired goods)
3. The subcontractor (as a **portal user** linked to a `res.partner`) needs to **view** those stock moves to know what parts to use and what to return
4. By default, a portal user has **no access** to `stock.move` records

The `mrp_subcontracting_repair` module bridges this gap by granting **read-only portal access** to `stock.move` records that are relevant to the subcontractor's repair work.

### Model Extension: `stock.move`

The module does **not define a new model**. Instead, it:
1. **Extends** the `stock.move` model's security via an `ir.rule`
2. **Grants ACL** for portal access to `stock.move` (which normally is not portal-accessible)

The underlying `stock.move` extensions (fields like `repair_id`, `repair_line_type`, computed locations) are provided by the `repair` module itself — specifically in `repair/models/stock_move.py`. This bridge module only adds the security layer.

## L2 — Field Types, Defaults, Constraints

### Extended Model: `stock.move` (from `repair` module)

The `repair` module adds these fields to `stock.move`:

| Field | Type | Description |
|-------|------|-------------|
| `repair_id` | `Many2one` (`repair.order`) | Link to the parent repair order; cascade delete |
| `repair_line_type` | `Selection` (`add`, `remove`, `recycle`) | Type of repair operation for this move |

These fields are defined in `repair/models/stock_move.py` and are **not created by** `mrp_subcontracting_repair` — they are part of the `repair` module's contribution to `stock.move`.

### ACL Record: `ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_subcontracting_portal_repair_move,subcontracting.portal.repair_move,
  repair.model_stock_move,base.group_portal,1,0,0,0
```

| Column | Value | Meaning |
|--------|-------|---------|
| `model_id:id` | `repair.model_stock_move` | External ID of the `stock.move` model in the `repair` module's namespace |
| `group_id:id` | `base.group_portal` | Applied to all portal users |
| `perm_read` | `1` | Portal users **can read** `stock.move` |
| `perm_write` | `0` | Portal users **cannot write** `stock.move` |
| `perm_create` | `0` | Portal users **cannot create** `stock.move` |
| `perm_unlink` | `0` | Portal users **cannot delete** `stock.move` |

This ACL is a **read-only grant** — the only permission enabled is `perm_read`. The portal user can see stock moves but cannot modify them.

### Record Rule: `ir.rule`

```xml
<record id="repair_line_subcontracting_rule" model="ir.rule">
    <field name="name">Repair Line Subcontractor</field>
    <field name="model_id" ref="repair.model_stock_move"/>
    <field name="domain_force">[
        '|',
            '|',
                ('product_id', 'in', user.partner_id.bom_ids.product_id.ids),
                ('product_id', 'in', user.partner_id.bom_ids.product_tmpl_id.product_variant_ids.ids),
            ('product_id', 'in', user.partner_id.bom_ids.bom_line_ids.product_id.ids),
    ]</field>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
</record>
```

#### Domain Force Analysis

```python
'|',                                                       # OR
    '|',                                                   #   OR
        ('product_id', 'in', user.partner_id.bom_ids.product_id.ids),             # Product variant from subcontractor's BoM
        ('product_id', 'in', user.partner_id.bom_ids.product_tmpl_id.product_variant_ids.ids),  # Product template variants
    ('product_id', 'in', user.partner_id.bom_ids.bom_line_ids.product_id.ids),    # Component in subcontractor's BoM
```

**What this domain means**: A portal user (who is a subcontractor contact linked to `user.partner_id`) can only see `stock.move` records where the `product_id` matches any product in the subcontractor's Bill of Materials.

The `user.partner_id.bom_ids` collection contains the **subcontracted BoMs** where this partner is listed as the subcontractor vendor. This is the standard Odoo subcontracting BoM configuration:
- `product_id` on the BoM header = the finished product the subcontractor manufactures
- `bom_line_ids` = the raw components the subcontractor receives

**Effect**: A portal subcontractor can see stock moves for:
1. The **finished product** of any subcontracting BoM where they are the subcontractor
2. **Any component** in those BoMs (parts they receive and must use)

### SQL Constraints

None — no new models or tables created.

### Default Values

None — all security records apply universally to all portal users (the `ir.rule` is per-user via `user.partner_id`).

## L3 — Cross-Module, Override Pattern, Workflow Trigger

### Cross-Module Dependency Chain

```
mrp_subcontracting_repair
├── mrp_subcontracting          (provides subcontracting BoM concept)
│   └── mrp                     (BoM, manufacturing orders)
└── repair                      (provides repair.order, stock.move extensions)
    └── stock                   (stock.move base model)
```

The `repair.model_stock_move` external ID resolves to `stock.move` in the `repair` module's namespace. The actual model definition is in `repair/models/stock_move.py`:

```python
class StockMove(models.Model):
    _inherit = 'stock.move'

    repair_id = fields.Many2one('repair.order', ...)
    repair_line_type = fields.Selection([('add', ...), ...])
```

### Override Pattern

This module uses **two distinct Odoo security mechanisms** simultaneously:

1. **ACL** (`ir.model.access.csv`): Grants the base permission (read) at the model level for the `stock.move` model to `base.group_portal`.
2. **Record Rule** (`ir.rule`): Restricts *which* records the portal user can see — filtering to only moves involving the subcontractor's own products.

Without both, access would either be fully denied (no ACL) or fully open (ACL without record rule).

### Key Technical Detail: `repair.model_stock_move`

The `model_id:id` in the ACL and ir.rule uses the external ID `repair.model_stock_move`, not `stock.model_stock_move`. This is a namespaced external ID created by the `repair` module when it registers the `stock.move` model. In Odoo, when a module extends an existing model, it gets a namespaced external ID like `module.model_name`.

### Workflow Trigger

The trigger for this module is **access-based** — it activates when:

1. A portal user (subcontractor) logs in to the Odoo portal
2. They navigate to a repair order page in the portal (provided by the `repair` module's portal controller)
3. The portal page attempts to display related `stock.move` records
4. Without this module: the stock moves are **hidden** (access denied)
5. With this module: the stock moves **appear** if they match the subcontractor's BoM products

The `repair` module's portal controller (`repair/controllers/portal.py`) renders the repair order page with the subcontractor's stock move details. The record rule is evaluated server-side on every `read()` call.

### Extension Points

| Extension Point | How to Extend |
|----------------|---------------|
| Allow write access | Change `perm_write` to `1` in the ACL CSV |
| Expand visible moves | Modify the `domain_force` to include additional conditions (e.g., by location, by state) |
| Apply to internal users | Add additional group entries in the ir.rule `groups` field |
| Add new products filter | Add additional `('product_id', 'in', ...)` OR conditions to the domain |

## L4 — Version Change: Odoo 18 to 19

### Changes Identified

#### Module Name / Version

| | Odoo 18 | Odoo 19 |
|--|---------|---------|
| Manifest version | `1.0` | `1.0` |
| Module name | `mrp_subcontracting_repair` | Same |

No version change. The module's implementation is identical between versions.

#### ACL and Record Rule Stability

The ACL (`access_subcontracting_portal_repair_move`) and ir.rule (`repair_line_subcontracting_rule`) are stable. The underlying `stock.move` model has not changed in a way that affects this security configuration in Odoo 19.

#### `repair` Module's `stock.move` Extension

The `repair` module's extensions to `stock.move` (fields, methods) are stable in Odoo 19. Key additions from `repair/models/stock_move.py`:

| Addition | Odoo 18 | Odoo 19 | Change |
|---------|---------|---------|--------|
| `repair_id` field | Present | Present | None |
| `repair_line_type` field | Present | Present | None |
| `_compute_forecast_information` | Present | Present | None |
| `_compute_picking_type_id` | Present | Present | None |
| `_compute_location_id` | Present | Present | None |
| `create()` override | Present | Present | Minor refactor |
| `_action_cancel` override | Present | Present | None |

The `create()` method in Odoo 19 includes this new behavior:
```python
# Odoo 19 addition
move.reference_ids = [Command.link(r.id) for r in move.repair_id.reference_ids]
```

This links repair references to the stock move's `reference_ids` — relevant to the portal view but does not affect the record rule.

#### Portal Portal Access

The portal repair order page (`/my/repair/<id>`) is provided by the `repair` module's portal controller. In Odoo 19, this controller and the related QWeb templates are stable. The `stock.move` records visible through this page are now accessible to portal subcontractors via the ACL and record rule added by this module.

#### Migration Notes

- **No data migration needed** — security-only module.
- **No Python changes needed** — no Python models or logic.
- **Verify `repair.model_stock_move` external ID** still resolves correctly after upgrading. This external ID is created by the `repair` module at installation time and should be stable.
- The `auto_install: True` flag combined with both dependencies means this module is automatically installed whenever `mrp_subcontracting` and `repair` are present — unchanged behavior from Odoo 18.

## Security Summary

| Aspect | Detail |
|--------|--------|
| **Portal read** | Allowed — via ACL `perm_read=1` |
| **Portal write** | Denied — via ACL `perm_write=0` |
| **Portal create** | Denied — via ACL `perm_create=0` |
| **Portal delete** | Denied — via ACL `perm_unlink=0` |
| **Record-level filter** | Only moves involving products from the subcontractor's BoM |
| **Subcontractor BoM resolution** | `user.partner_id.bom_ids` — all subcontracting BoMs where the partner is the subcontractor vendor |

## Related

- [Modules/repair](Modules/repair.md) — Repair orders and stock.move extensions
- [Modules/mrp_subcontracting](Modules/mrp_subcontracting.md) — Subcontracting BoM and production orders
- [Modules/Stock](Modules/stock.md) — Stock move base model
- [Modules/portal](Modules/portal.md) — Portal user access framework
