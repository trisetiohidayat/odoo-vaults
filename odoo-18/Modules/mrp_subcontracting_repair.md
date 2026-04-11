---
Module: mrp_subcontracting_repair
Version: 18.0
Type: addon
Tags: #mrp, #subcontracting, #repair, #security, #bridge
---

# mrp_subcontracting_repair — MRP Subcontracting + Repair Bridge

## Module Overview

**Category:** Hidden
**Depends:** `mrp_subcontracting`, `repair`
**License:** LGPL-3
**Installable:** True
**Auto-install:** True

Pure security/data bridge module. Grants portal users (subcontractors) read access to subcontracting-related `stock.move` records in the repair order context, enabling subcontractors to view moves linked to repair orders involving their supplied components or subcontracted products.

## Data Files

- `security/mrp_subcontracting_repair_security.xml` — ir.rule definitions
- `security/ir.model.access.csv` — ACL for portal group on stock.move
- `views/res_partner_view.xml` — Partner form view showing subcontracting information
- `data/mrp_subcontracting_repair_data.xml` — Default data

## Static Assets

None — no JavaScript or CSS.

## Models

No Python model files. Pure bridge module using only XML security definitions.

---

## Security

### `ir.model.access.csv`

| ID | Name | Model | Group | Perms |
|----|------|-------|-------|-------|
| `subcontracting.portal.repair_move` | Subcontracting Repair Move | `stock.move` | `base.group_portal` | read |

Grants portal users read-only access to `stock.move` for subcontracted repair order moves.

### `ir.rule` — Subcontracting Repair Move

**Model:** `stock.move`
**Name:** `subcontracting.portal.repair_move`
**Groups:** `base.group_portal`

**Domain (OR chain):**
1. `product_id in user.partner_id.bom_ids.product_id.ids` — subcontracted product variants (where the partner is a subcontractor for those products)
2. `product_id in user.partner_id.bom_ids.product_tmpl_id.product_variant_ids.ids` — subcontracted product templates
3. `product_id in user.partner_id.bom_ids.bom_line_ids.product_id.ids` — components used in subcontracted BoMs (where the partner supplies those components)

---

## What It Extends

- `stock.move` — read access for portal group via ir.rule and ir.model.access
- `res.partner` — optional partner form view extension

---

## Key Behavior

- This module has **no Python model files** — it is purely a security/data bridge.
- The ir.rule uses `user.partner_id.bom_ids` to dynamically resolve which products the subcontractor is allowed to see based on their vendor Bill of Materials configuration.
- A partner is treated as a subcontractor when they appear as a subcontractor in any active BoM (i.e., any BoM line with that partner as the subcontractor, or any BoM of type `subcontract` referencing that partner).
- The portal user (subcontractor) can view stock moves linked to repair orders that involve products or components they supply.
- `auto_install: True` — automatically installed when both `mrp_subcontracting` and `repair` are present.

---

## See Also

- [[Modules/MRP Subcontracting]] (`mrp_subcontracting`) — subcontracting BoM support
- [[Modules/Repair]] (`repair`) — repair order management
- [[Modules/Portal]] (`portal`) — portal user access system
