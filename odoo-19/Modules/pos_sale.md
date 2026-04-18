---
type: module
module: pos_sale
tags: [odoo, odoo19, pos, sale, crm_team, down_payment, order_sync, pos_load_mixin]
created: 2026-04-14
related_links:
  - "[Modules/point_of_sale](point_of_sale.md)"
  - "[Modules/Sale](Sale.md)"
  - "[Modules/pos_sale_loyalty](pos_sale_loyalty.md)"
  - "[Modules/pos_sale_margin](pos_sale_margin.md)"
---

# POS Sale

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `pos_sale` |
| **Category** | Sales/Point of Sale |
| **Depends** | `point_of_sale`, `sale_management` |
| **Auto-install** | True |
| **Sequence** | 6 |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

## Purpose

`pos_sale` is the primary cross-module integration between **Point of Sale** and **Sales**. It enables cashiers to load, pay, and fulfill existing sale orders directly from the POS interface, without the customer needing to go to a separate counter or the back office.

The module's core use cases are:
1. **Loading draft sale orders** into POS so customers can pay outstanding SO balances (e.g., final payment on a special order).
2. **Creating down payments** from POS orders linked to sale orders.
3. **Syncing stock pickings** between what was ordered via sale and what was actually shipped/paid at POS.
4. **Preventing double invoicing** by tracking what has already been paid via POS vs. what must be invoiced.
5. **Assigning sales teams** to POS orders for reporting purposes.

## Architecture: The `pos.load.mixin` Pattern

The central architectural pattern used in `pos_sale` is the **`pos.load.mixin`** -- an abstract model mixin that allows any model to be loaded into the POS interface. Both `sale.order` and `sale.order.line` inherit from this mixin to participate in the POS data loading mechanism.

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'pos.load.mixin']
```

```python
class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'pos.load.mixin']
```

The `pos.load.mixin` provides:
- `_load_pos_data_domain()`: Returns the Odoo domain for records to load (e.g., draft orders only).
- `_load_pos_data_fields()`: Returns the list of field names to include in the POS payload.
- `load_sale_order_from_pos()`: The main method that prepares a sale order and all its related data for POS consumption.

This pattern allows the POS to pull exactly the data it needs -- no more, no less -- in a structured format compatible with the POS JavaScript client.

## Model Extensions

### `sale.order` (Extended)

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `pos_order_line_ids` | One2many (`pos.order.line`) | POS order lines transferred from POS back to this SO |
| `pos_order_count` | Integer (computed) | Count of POS orders linked to this SO |
| `amount_unpaid` | Monetary (computed, stored) | Amount remaining to be paid via POS to avoid double payment |

**`amount_unpaid`** is a critical field that prevents overpayment. It is computed as:

```
amount_unpaid = max(
    amount_total
    - total_invoices_paid
    - total_pos_orders_paid
    - amount_paid_via_so,
    0.0
)
```

Where:
- `total_invoices_paid`: Sum of all posted/draft invoice amounts (even if not yet paid).
- `total_pos_orders_paid`: Sum of all linked POS order totals.
- `amount_paid_via_so`: Sum of payments made directly on the sale order.

#### Key Methods

##### `_load_pos_data_domain(data, config)`

```python
@api.model
def _load_pos_data_domain(self, data, config):
    return [['pos_order_line_ids.order_id.state', '=', 'draft']]
```

Only **draft state** sale orders are loaded into POS. This is a deliberate safety constraint: confirmed, locked, or cancelled orders should not be payable through POS without explicit workflow modifications.

##### `load_sale_order_from_pos(config_id)`

This is the main data preparation method. It returns a structured dictionary containing all related records needed by the POS client:

```python
def load_sale_order_from_pos(self, config_id):
    product_ids = self.order_line.product_id.ids
    product_tmpls = self.env['product.template'].load_product_from_pos(
        config_id,
        [('product_variant_ids.id', 'in', product_ids)]
    )
    sale_order_fields = self._load_pos_data_fields(config_id)
    sale_order_read = self.read(sale_order_fields, load=False)
    sale_order_line_fields = self.order_line._load_pos_data_fields(config_id)
    sale_order_line_read = self.order_line.read(sale_order_line_fields, load=False)
    # ... fiscal position, partner, etc.
    return {
        'sale.order': sale_order_read,
        'sale.order.line': sale_order_line_read,
        'account.fiscal.position': sale_order_fp_read,
        'res.partner': self.partner_id.read(partner_fields, load=False),
        **product_tmpls,
    }
```

The POS client uses this data to render the sale order in its UI, allowing the cashier to see the order lines, pricing, and customer details before processing payment.

##### `_prepare_down_payment_line_values_from_base_line(base_line)`

When a POS order is processed with a down payment line linked to a sale order, this method is called (via `sale` module's down payment mechanism) to create the corresponding down payment line on the sale order:

```python
def _prepare_down_payment_line_values_from_base_line(self, base_line):
    so_line_values = super()._prepare_down_payment_line_values_from_base_line(base_line)
    if (
        base_line
        and base_line['record']
        and isinstance(base_line['record'], models.Model)
        and base_line['record']._name == 'pos.order.line'
    ):
        pos_order_line = base_line['record']
        so_line_values['name'] = _(
            "Down payment (ref: %(order_reference)s on \n %(date)s)",
            order_reference=pos_order_line.name,
            date=format_date(pos_order_line.env, pos_order_line.order_id.date_order),
        )
        so_line_values['pos_order_line_ids'] = [Command.set(pos_order_line.ids)]
    return so_line_values
```

The down payment name is customized to reference the POS order that created it, making it traceable in the sale order's line history.

##### `_count_pos_order()`

Counts POS orders linked to this sale order by traversing `pos_order_line_ids` → `order_id`:

```python
def _count_pos_order(self):
    for order in self:
        linked_orders = order.pos_order_line_ids.mapped('order_id')
        order.pos_order_count = len(linked_orders)
```

### `sale.order.line` (Extended)

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `pos_order_line_ids` | One2many (`pos.order.line`) | POS order lines linked to this SO line |

#### Key Methods

##### `_compute_qty_delivered()`

Overrides the sale order line's delivery quantity computation to include quantities delivered via POS:

```python
def _prepare_qty_delivered(self):
    delivered_qties = super()._prepare_qty_delivered()
    def _get_pos_delivered_qty(sale_line, pos_lines):
        if all(picking.state == "done" for picking in pos_lines.order_id.picking_ids):
            return sum(self._convert_qty(sale_line, pos_line.qty, "p2s") for pos_line in pos_lines)
        return 0

    for sale_line in self.filtered(lambda line: line.product_id.type != "service"):
        pos_line_ids = sale_line.sudo().pos_order_line_ids
        pos_qty = _get_pos_delivered_qty(sale_line, pos_line_ids.filtered(
            lambda line: line.order_id.state not in ["cancel", "draft"]
        ))
        if pos_qty != 0:
            delivered_qties[sale_line] += pos_qty
    return delivered_qties
```

**Key behavior**: POS quantities are only counted as delivered if the related POS order's stock pickings are in `done` state. This prevents prematurely counting POS-reserved quantities as delivered.

##### `_compute_qty_invoiced()`

Includes POS down payment quantities in the invoiced quantity calculation:

```python
def _prepare_qty_invoiced(self):
    invoiced_qties = super()._prepare_qty_invoiced()
    for sale_line in self:
        pos_lines = sale_line.sudo().pos_order_line_ids.filtered(
            lambda order_line: order_line.order_id.state not in ['cancel', 'draft']
        )
        invoiced_qties[sale_line] += sum((
            self._convert_qty(sale_line, pos_line.qty, 'p2s')
            for pos_line in pos_lines
        ), 0)
    return invoiced_qties
```

##### `_convert_qty(sale_line, qty, direction)`

Central UoM conversion helper used throughout the module:

```python
@api.model
def _convert_qty(self, sale_line, qty, direction):
    """
    Converts the given QTY based on the given SALE_LINE and DIR.
    - DIR='s2p': convert from sale line UoM to product UoM
    - DIR='p2s': convert from product UoM to sale line UoM
    """
    product_uom = sale_line.product_id.uom_id
    sale_line_uom = sale_line.product_uom_id
    if direction == 's2p':
        return sale_line_uom._compute_quantity(qty, product_uom, False)
    elif direction == 'p2s':
        return product_uom._compute_quantity(qty, sale_line_uom, False)
```

##### `unlink()`

Prevents deletion of down payment lines that were created from POS:

```python
def unlink(self):
    # do not delete downpayment lines created from pos
    pos_downpayment_lines = self.filtered(
        lambda line: line.is_downpayment and line.sudo().pos_order_line_ids
    )
    return super(SaleOrderLine, self - pos_downpayment_lines).unlink()
```

### `pos.order` (Extended)

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `crm_team_id` | Many2one (`crm.team`) | Sales team for reporting |
| `sale_order_count` | Integer (computed) | Count of linked sale orders |
| `currency_rate` | Float (computed, stored) | Conversion rate to POS session currency |

#### Key Methods

##### `_complete_values_from_session(session, values)`

When a POS order is closed and converted to a session, this method assigns the session's configured sales team to the order:

```python
@api.model
def _complete_values_from_session(self, session, values):
    values = super()._complete_values_from_session(session, values)
    values['crm_team_id'] = (
        values.get('crm_team_id')
        if values.get('crm_team_id')
        else session.config_id.crm_team_id.id
    )
    return values
```

This ensures that POS orders appear under the correct sales team in reporting, even if the POS session has a default team assigned.

##### `sync_from_ui(orders)`

This is the most complex method in `pos_sale`. It processes POS orders sent from the frontend after payment, synchronizing data back to the linked sale orders:

```python
@api.model
def sync_from_ui(self, orders):
    data = super().sync_from_ui(orders)
    # ... for each POS order:
    # 1. Identify linked sale orders
    # 2. Create down payment lines on SO from POS down payment lines
    # 3. Confirm unconfirmed SOs
    # 4. Update stock move quantities (demand qty)
    # 5. Cancel or reassign pickings with zero demand
    return data
```

The key operations within `sync_from_ui` are:

**Down payment creation**: Groups POS lines by their `sale_order_origin_id`, then calls `sale_order._create_down_payment_lines_from_base_lines()` for each group.

**Sale order confirmation**: If the POS order state is not `draft`, any linked draft or sent sale orders are automatically confirmed via `sale_order.action_confirm()`.

**Stock move demand update**: Updates the `product_uom_qty` on stock moves linked to sale order lines, accounting for quantities already delivered via POS. If all quantities are zero, the picking is cancelled.

### `pos.order.line` (Extended)

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `sale_order_origin_id` | Many2one (`sale.order`) | Source sale order |
| `sale_order_line_id` | Many2one (`sale.order.line`) | Source sale order line |
| `down_payment_details` | Text | Down payment reference details |
| `qty_delivered` | Float (computed) | Quantity delivered via POS |

#### `_compute_qty_delivered` for POS Lines

When a POS order is in `paid` or `done` state, this computes how much of the line quantity was actually delivered:

```python
@api.depends('order_id.state', 'order_id.picking_ids', 'order_id.picking_ids.state',
            'order_id.picking_ids.move_ids.quantity')
def _compute_qty_delivered(self):
    for order_line in self:
        if order_line.order_id.state in ['paid', 'done']:
            outgoing_pickings = order_line.order_id.picking_ids.filtered(
                lambda pick: pick.state == 'done'
                             and pick.picking_type_code == 'outgoing')
            if outgoing_pickings and order_line.order_id.shipping_date:
                # Use shipping_date-aware delivery logic
                ...
            elif outgoing_pickings:
                order_line.qty_delivered = order_line.qty
            else:
                order_line.qty_delivered = 0
```

## Data Flow

```
Sale Order SO-001 created (draft)
   - Customer orders 10x Product A, 5x Product B
   - Some items shipped immediately, some pending
         │
         ▼ (SO loaded into POS session)
Cashier loads SO-001 in POS
   → load_sale_order_from_pos() prepares payload
   → POS client renders order lines
         │
         ▼ (Customer pays remaining balance at POS)
POS order PO-001 created with down payment
   → sync_from_ui() called after payment
     → Creates down payment section on SO-001
     → Updates stock move demand (remaining qty)
     → Cancels pickings with zero demand
         │
         ▼
SO-001 state updated
   - Down payment recorded
   - Picking demand synced
   - amount_unpaid recalculated
```

## Accounting Implications

When a POS order is linked to a sale order:

1. **Invoice vs. POS payment distinction**: The module carefully tracks `amount_unpaid` to ensure that:
   - An invoice created from the SO only bills the unpaid balance (not the amount already paid via POS).
   - The `amount_to_invoice` and `amount_invoiced` computed fields account for POS payments.

2. **Down payment tax handling**: When creating down payment lines from POS, the tax details are computed via `AccountTax._add_tax_details_in_base_lines()` and `AccountTax._round_base_lines_tax_details()` to ensure correct tax treatment.

3. **Fiscal position**: If the sale order has a fiscal position, it is applied to the POS order's invoice via `_prepare_invoice_vals()`.

## Data Files

| File | Purpose |
|------|---------|
| `data/pos_sale_data.xml` | Activates the POS Sales Team and creates a default "Down Payment (POS)" product (service type, $0 price, not available in POS) |
| `security/ir.model.access.csv` | Access control for all extended models |
| `security/pos_sale_security.xml` | Record rules for POS-Sale access |

## Post-Init Hook

```python
post_init_hook: '_pos_sale_post_init'
```

This hook activates the POS Sales Team (`sales_team.pos_sales_team`) and sets it as active when the module is installed on an existing database that already has sale data.

## Related

- [Modules/point_of_sale](point_of_sale.md) -- Base POS module
- [Modules/Sale](Sale.md) -- Sale order management
- [Modules/pos_sale_loyalty](pos_sale_loyalty.md) -- POS Sale + Loyalty program integration
- [Modules/pos_sale_margin](pos_sale_margin.md) -- POS Sale + Margin tracking
