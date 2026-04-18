---
tags:
  - odoo
  - odoo19
  - mrp
  - purchase
  - stock
  - subcontracting
  - supply_chain
  - modules
  - cross-module
summary: "Bridges MRP subcontracting and purchase management by adding smart buttons for cross-navigation between subcontracting pickings and their source/destination purchase orders, plus enhanced lead time computation for subcontracted manufacturing."
description: |
  `mrp_subcontracting_purchase` is a bidirectional bridge module between the MRP subcontracting workflow and the purchase management system. It serves three distinct purposes:

  1. **Smart buttons on Purchase Orders**: A "Resupply" button shows the count of subcontracting resupply pickings linked to a PO's order lines.
  2. **Smart buttons on Stock Pickings**: A "Source PO" button on subcontracting pickings links back to the purchase order that initiated the subcontract.
  3. **Lead time computation**: The module overrides `stock.rule._get_lead_days()` to correctly calculate procurement lead times for subcontracted products, accounting for both the vendor lead time and the manufacturing (BOM produce) lead time.
---

# MRP Subcontracting Purchase (`mrp_subcontracting_purchase`)

## Overview

| Property | Value |
|----------|-------|
| **Module** | `mrp_subcontracting_purchase` |
| **Category** | Supply Chain / Purchase |
| **Depends** | `mrp_subcontracting`, `purchase_mrp` |
| **Auto-install** | `True` |
| **Version** | `0.1` |
| **License** | LGPL-3 |
| **Odoo** | 19.0 |

`mrp_subcontracting_purchase` connects two subcontracting workflows — the MRP subcontracting BoM flow and the purchase order flow — through smart buttons and enhanced lead time computation. Without this module, navigating between subcontracting pickings and their associated purchase orders requires manual lookup. With this module, users can jump directly from a PO to its subcontracting resupply pickings and from a picking to its source PO.

## Architecture

### Dependency Chain

```
base
  └── stock (stock.picking, stock.rule, stock.warehouse)
        └── mrp (mrp.bom, mrp.production, mrp.workorder)
              └── mrp_subcontracting (subcontract BoM, subcontract stock flow)
                    └── purchase_mrp (PO ↔ MO linkage)
                          └── mrp_subcontracting_purchase  ← this module
                                (crosses back into stock)
```

The module crosses the boundary between `mrp_subcontracting` (which owns the subcontracting manufacturing flow) and `purchase_mrp` (which links POs to MOs). It extends both the `purchase.order` model (from `purchase_mrp`) and the `stock.picking` model (from `stock`), while also providing its own `stock.rule` override.

## Model Changes

### 1. `purchase.order` (Extended from `purchase_mrp`)

```python
# Source: odoo/addons/mrp_subcontracting_purchase/models/purchase_order.py
class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    subcontracting_resupply_picking_count = fields.Integer(
        "Count of Subcontracting Resupply",
        compute='_compute_subcontracting_resupply_picking_count',
        help="Count of Subcontracting Resupply for component")

    def _compute_subcontracting_resupply_picking_count(self):
        for purchase in self:
            purchase.subcontracting_resupply_picking_count = len(
                purchase._get_subcontracting_resupplies()
            )

    def action_view_subcontracting_resupply(self):
        return self._get_action_view_picking(
            self._get_subcontracting_resupplies()
        )

    def _get_subcontracting_resupplies(self):
        # Follow: PO line → stock move → MO → picking (resupply)
        moves_subcontracted = self.order_line.move_ids.filtered(
            lambda m: m.is_subcontract
        )
        subcontracted_productions = moves_subcontracted.move_orig_ids.production_id
        return subcontracted_productions.picking_ids
```

#### Navigation Chain: PO to Resupply Picking

```
purchase.order
  └── purchase.order.line
        └── stock.move (where is_subcontract = True)
              └── stock.move (move_orig_ids) — the "stock move"
                    └── mrp.production (production_id) — the MO
                          └── stock.picking (picking_ids) — the resupply picking
```

The `_get_subcontracting_resupplies()` method navigates this chain backwards: from PO line moves, it finds the subcontracted moves, then their origin production orders, then those productions' pickings.

### 2. `stock.picking` (Extended from `mrp_subcontracting`)

```python
# Source: odoo/addons/mrp_subcontracting_purchase/models/stock_picking.py
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    subcontracting_source_purchase_count = fields.Integer(
        "Number of subcontracting PO Source",
        compute='_compute_subcontracting_source_purchase_count',
        help="Number of subcontracting Purchase Order Source")

    def _compute_subcontracting_source_purchase_count(self):
        for picking in self:
            picking.subcontracting_source_purchase_count = len(
                picking._get_subcontracting_source_purchase()
            )

    def action_view_subcontracting_source_purchase(self):
        purchase_order_ids = self._get_subcontracting_source_purchase().ids
        action = {'res_model': 'purchase.order', 'type': 'ir.actions.act_window'}
        if len(purchase_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': purchase_order_ids[0],
            })
        else:
            action.update({
                'name': _("Source PO of %s", self.name),
                'domain': [('id', 'in', purchase_order_ids)],
                'view_mode': 'list,form',
            })
        return action

    def _get_subcontracting_source_purchase(self):
        # Follow: picking → stock.move → finished move → dest move → purchase line → PO
        moves_subcontracted = (
            self.move_ids.move_dest_ids.raw_material_production_id
            .move_finished_ids.move_dest_ids
            .filtered(lambda m: m.is_subcontract)
        )
        return moves_subcontracted.purchase_line_id.order_id
```

#### Navigation Chain: Picking to Source PO

```
stock.picking (subcontracting receipt)
  └── stock.move (move_dest_ids) — the moves that consumed this picking's output
        └── mrp.production (raw_material_production_id) — MO that consumed goods
              └── stock.move (move_finished_ids) — finished goods moves of that MO
                    └── stock.move (move_dest_ids) — downstream moves
                          └── is_subcontract = True → purchase_line_id.order_id → purchase.order
```

### 3. `stock.rule` (Extended from `stock`)

```python
# Source: odoo/addons/mrp_subcontracting_purchase/models/stock_rule.py
class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_lead_days(self, product, **values):
        """Calculate procurement lead time for subcontracted products.
        Subcontracting delay =
            max(Vendor lead time, Manufacturing lead time + DTPMO) + Days to Purchase
        """
        buy_rule = self.filtered(lambda r: r.action == 'buy')
        seller = (
            'supplierinfo' in values and values['supplierinfo']
            or product.with_company(buy_rule.company_id)._select_seller(quantity=None)
        )
        if not buy_rule or not seller:
            return super()._get_lead_days(product, **values)
        seller = seller[0]
        bom = self.env['mrp.bom'].sudo()._bom_subcontract_find(
            product,
            company_id=buy_rule.picking_type_id.company_id.id,
            bom_type='subcontract',
            subcontractor=seller.partner_id)
        if not bom:
            return super()._get_lead_days(product, **values)

        delays, delay_description = (
            super(StockRule, self - buy_rule)._get_lead_days(product, **values)
        )
        extra_delays, extra_delay_description = (
            super(StockRule, buy_rule.with_context(
                ignore_vendor_lead_time=True, global_horizon_days=0
            ))._get_lead_days(product, **values)
        )

        # Use whichever is longer: vendor lead time vs (manufacture + DTPMO)
        if seller.delay >= bom.produce_delay + bom.days_to_prepare_mo:
            delays['total_delay'] += seller.delay
            delays['purchase_delay'] += seller.delay
            delay_description.append((_('Receipt Date'), int(seller.delay)))
            delay_description.append((_('Vendor Lead Time'), _('+ %d day(s)', seller.delay)))
        else:
            manufacture_delay = bom.produce_delay
            delays['total_delay'] += manufacture_delay
            delays['purchase_delay'] += manufacture_delay
            delay_description.append((_('Receipt Date'), manufacture_delay))
            delay_description.append(
                (_('Manufacturing Lead Time'), _('+ %d day(s)', manufacture_delay))
            )
            days_to_order = bom.days_to_prepare_mo
            delays['total_delay'] += days_to_order
            delays['purchase_delay'] += days_to_order
            delay_description.append((_('Production Start Date'), days_to_order))
            delay_description.append(
                (_('Days to Supply Components'), _('+ %d day(s)', days_to_order))
            )

        for key, value in extra_delays.items():
            delays[key] += value
        return delays, delay_description + extra_delay_description
```

#### Lead Time Formula

The key logic for determining the subcontracting delay:

```
Subcontracting Delay = max(vendor_delay, produce_delay + days_to_prepare_mo) + extra_delays
```

Where:
- `vendor_delay` — Lead time from the subcontractor/supplier info on the product.
- `produce_delay` — The BOM's manufacturing lead time (how long the subcontractor takes to produce the goods).
- `days_to_prepare_mo` — Days to Prepare MO (DTPMO), the internal preparation time before manufacturing starts.
- `extra_delays` — Additional delays from the parent `_get_lead_days` call (e.g., security lead time, warehouse transit).

### 4. `stock.rule` — Vendor Notification

```python
# Source: odoo/addons/mrp_subcontracting_purchase/models/stock_rule.py
def _notify_responsible(self, procurement):
    super()._notify_responsible(procurement)
    origin_order = self.env.context.get('po_to_notify')
    if origin_order:
        notified_users = (
            procurement.product_id.responsible_id.partner_id
            | origin_order.user_id.partner_id
        )
        self._post_vendor_notification(
            origin_order, notified_users, procurement.product_id
        )
```

This ensures that when a procurement rule is triggered for a subcontracted product, both the product's responsible person and the PO's responsible user receive the notification.

## View Changes

### Smart Button on Purchase Order Form

```xml
<!-- Source: odoo/addons/mrp_subcontracting_purchase/views/purchase_order_views.xml -->
<xpath expr="//div[hasclass('oe_button_box')]/button[@name='action_view_picking']" position="before">
    <button
        class="oe_stat_button" name="action_view_subcontracting_resupply"
        type="object" icon="fa-truck"
        invisible="subcontracting_resupply_picking_count == 0"
        groups="stock.group_stock_user">
        <div class="o_field_widget o_stat_info">
            <span class="o_stat_value">
                <field name="subcontracting_resupply_picking_count"/>
            </span>
            <span class="o_stat_text">Resupply</span>
        </div>
    </button>
</xpath>
```

The button is placed **before** the standard "Receipts" button and is invisible when the count is zero.

### Smart Button on Stock Picking Form

```xml
<!-- Source: odoo/addons/mrp_subcontracting_purchase/views/stock_picking_views.xml -->
<xpath expr="//div[hasclass('oe_button_box')]" position="inside">
    <button
        class="oe_stat_button" name="action_view_subcontracting_source_purchase"
        type="object" icon="fa-credit-card"
        invisible="subcontracting_source_purchase_count == 0"
        groups="stock.group_stock_user">
        <div class="o_field_widget o_stat_info">
            <span class="o_stat_value">
                <field name="subcontracting_source_purchase_count"/>
            </span>
            <span class="o_stat_text">Source PO</span>
        </div>
    </button>
</xpath>
```

## Practical Usage Scenarios

### Scenario 1: Full Traceability from PO to Finished Goods

A procurement manager receives a PO for subcontracted goods. They want to:
1. See which subcontracting pickings (component resupply to subcontractor) are linked to this PO.
2. Check whether the subcontractor has received the components.
3. Track the manufacturing order progress.
4. Know when to expect the finished goods receipt.

With this module:
- The "Resupply" smart button on the PO shows the resupply picking count.
- Clicking the button opens the picking list showing components shipped to the subcontractor.
- From the picking, the "Source PO" button navigates back to the originating PO.

### Scenario 2: Correct Delivery Date for Subcontracted Products

A sales team wants to promise a delivery date to a customer for a product that includes a subcontracted component.

Without this module: The standard purchase lead time (vendor delay) might be used, ignoring the manufacturing time.

With this module: The `_get_lead_days()` override calculates:
```
subcontracting_delay = max(vendor_delay, produce_delay + dtpmo) + extra_delays
```
This gives an accurate promised date based on when the subcontractor can actually deliver, which considers both the vendor's lead time and the manufacturing time.

### Scenario 3: Subcontracting Resupply Workflow

The full subcontracting resupply flow:
1. MO is created for a product with a subcontract BoM.
2. Odoo creates a **resupply picking** (type: Subcontracting) to ship components from the warehouse to the subcontractor.
3. Odoo creates a **subcontract receipt** to receive finished goods from the subcontractor back to the warehouse.
4. A **purchase order** is created for the subcontracting service.

This module links the PO (step 4) to the resupply picking (step 2), enabling the procurement team to monitor component deliveries alongside the finished goods receipt.

## Technical Notes

### `_get_subcontracting_resupplies()` Return Value

The method returns a `stock.picking` recordset. An empty recordset is returned if:
- The PO has no subcontracted order lines.
- The subcontracted moves have no linked production orders.
- The production orders have no pickings yet.

### `_get_subcontracting_source_purchase()` Return Value

The method returns a `purchase.order` recordset. It may return multiple POs if multiple subcontracting moves on the picking are linked to different POs (though in practice, a single subcontracting receipt is typically linked to one PO).

### Visibility Conditions

Both smart buttons use `invisible` attribute in XML rather than `attrs` or `states` — this is the modern Odoo 13+ approach for dynamic visibility:
```xml
invisible="subcontracting_resupply_picking_count == 0"
```
The count field is computed on every read, so the button automatically appears/disappears as data changes.

### Security

The smart buttons respect Odoo's standard access control:
- `stock.group_stock_user` is required to see the buttons.
- The target action (opening the picking list or PO form) respects the user's record rules on those models.

## Related Documentation

- [Modules/mrp_subcontracting](mrp_subcontracting.md) — Subcontract BoM and MO tracking
- [Modules/purchase_mrp](purchase_mrp.md) — PO to MO linkage (this module extends it)
- [Modules/mrp](mrp.md) — Manufacturing module
- [Modules/purchase](Purchase.md) — Purchase management
- [Modules/stock](Stock.md) — Warehouse management
- [Patterns/Cross-Module-Integration](Patterns/Cross-Module-Integration.md) — Cross-module integration patterns
