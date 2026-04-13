# Purchase — Purchase Orders

Dokumentasi Odoo 15 untuk Purchase module. Source: `addons/purchase/models/`

## Models

| Model | File | Description |
|---|---|---|
| `purchase.order` | `purchase.py` | Purchase Order / RFQ |
| `purchase.order.line` | `purchase.py` | PO Line Items |
| `purchase.agreement` | `purchase_requisition.py` | Purchase Agreement |
| `product.supplierinfo` | `product.py` | Vendor Pricelist |

## PurchaseOrder Fields

```python
class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Purchase Order"
    _order = "priority desc, id desc"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Order Reference (auto: PROC/XXXX/XXXX) |
| `origin` | Char | Source Document |
| `partner_id` | Many2one(res.partner) | Vendor |
| `partner_ref` | Char | Vendor Reference |
| `state` | Selection | draft/sent/to approve/purchase/done/cancel |
| `date_order` | Datetime | Order Date |
| `date_approve` | Datetime | Approval Date |
| `date_planned` | Datetime | Planned Date |
| `priority` | Selection | Normal/High |
| `notes` | Text | Internal notes |
| `picking_type_id` | Many2one(stock.picking.type) | Operation Type |
| `incoterm_id` | Many2one(account.incoterms) | Incoterm |

### Partner Address

| Field | Type | Description |
|---|---|---|
| `dest_address_id` | Many2one(res.partner) | Delivery Address |
| `partner_id` | Many2one(res.partner) | Vendor |

### Commercial Fields

| Field | Type | Description |
|---|---|---|
| `user_id` | Many2one(res.users) | Buyer |
| `fiscal_position_id` | Many2one(account.fiscal.position) | Fiscal Position |
| `payment_term_id` | Many2one(account.payment.term) | Payment Terms |
| `currency_id` | Many2one(res.currency) | Currency |

### Financial Fields

| Field | Type | Description |
|---|---|---|
| `amount_untaxed` | Monetary | Untaxed amount |
| `amount_tax` | Monetary | Tax amount |
| `amount_total` | Monetary | Grand total |
| `tax_totals_json` | Char | Tax breakdown JSON |

### Lines & Invoicing

| Field | Type | Description |
|---|---|---|
| `order_line` | One2many(purchase.order.line) | Order lines |
| `invoice_count` | Integer | Bill count |
| `invoice_ids` | Many2many(account.move) | Linked bills |

### Warehouse & Config

| Field | Type | Description |
|---|---|---|
| `picking_type_id` | Many2one(stock.picking.type) | Receipt type |
| `company_id` | Many2one(res.company) | Company |
| `mail_reminder_confirmed` | Boolean | Reminder confirmed |
| `mail_partner_id` | Many2one(res.partner) | Email contact |

### Access & Signature

| Field | Type | Description |
|---|---|---|
| `signature` | Binary | Signature |
| `signed_by` | Char | Signed by |
| `signed_on` | Datetime | Signed on |

## PurchaseOrder State Machine

```
draft (Request for Quotation) → sent (RFQ Sent) → to approve → purchase (Purchase Order) → done (Locked)
       ↓                            ↓                   ↓              ↓                    ↓
    cancel                       cancel              cancel       cancel               done (no cancel)
       ↓                            ↓                   ↓              ↓
    draft (Reset)               draft (Reset)      draft (Reset)    purchase
```

**State Values:**
| State | Description |
|---|---|
| `draft` | RFQ (not sent) |
| `sent` | RFQ Sent to vendor |
| `to approve` | Waiting approval |
| `purchase` | PO Confirmed |
| `done` | Locked (completed) |
| `cancel` | Cancelled |

## PurchaseOrderLine Fields

```python
class PurchaseOrderLine(models.Model):
    _name = "purchase.order.line"
    _description = "Purchase Order Line"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `order_id` | Many2one(purchase.order) | Parent PO |
| `name` | Char | Description |
| `product_id` | Many2one(product.product) | Product |
| `product_qty` | Float | Ordered quantity |
| `product_uom` | Many2one(uom.uom) | Unit of measure |
| `price_unit` | Float | Unit price |
| `price_subtotal` | Monetary | Subtotal |
| `taxes_id` | Many2many(account.tax) | Taxes |
| `date_planned` | Datetime | Scheduled delivery |
| `state` | Selection | draft/confirmed/done/cancel |

### Product/Supplier Fields

| Field | Type | Description |
|---|---|---|
| `product_id` | Many2one(product.product) | Product |
| `product_template_id` | Many2one(product.template) | Product template |
| `partner_id` | Many2one(res.partner) | Vendor (from PO) |
| `date_planned` | Datetime | Expected delivery |

### Qty/Invoice Fields

| Field | Type | Description |
|---|---|---|
| `qty_received` | Float | Received quantity |
| `qty_received_manual` | Float | Manual received qty |
| `qty_invoiced` | Float | Invoiced quantity |
| `account_analytic_id` | Many2one(account.analytic.account) | Analytic account |
| `analytic_tag_ids` | Many2many(account.analytic.tag) | Analytic tags |

## Computed Fields

```python
# Amount totals
@api.depends('order_line.price_total')
def _compute_amount(self):
    for order in self:
        amount_untaxed = sum(order.order_line.mapped('price_subtotal'))
        amount_tax = sum(order.order_line.mapped('amount_tax'))
        order.update({
            'amount_untaxed': amount_untaxed,
            'amount_tax': amount_tax,
            'amount_total': amount_untaxed + amount_tax,
        })

# Incoming shipment count
def _compute_picking_ids(self):
    for order in self:
        pickings = self.env['stock.picking'].search([
            ('origin', '=', order.name),
        ])
        order.inbound_picking_count = len(pickings)
        order.picking_ids = pickings
```

## Action Methods

```python
def button_confirm(self):
    """Confirm PO (draft → purchase)"""
    for order in self:
        if order.state not in ('draft', 'sent'):
            continue
        order._add_supplier_info()
        order.write({'state': 'purchase'})
    return True

def button_cancel(self):
    """Cancel PO"""
    for order in self:
        for move in order.picking_ids.move_ids:
            if move.state == 'done':
                raise UserError(_('Cannot cancel PO with done moves'))
        order.picking_ids.action_cancel()
        order.order_line.write({'state': 'cancel'})
    self.write({'state': 'cancel'})

def action_rfq_send(self):
    """Send RFQ by email"""
    ...

def action_view_picking(self):
    """Open incoming shipments"""
    return {
        'name': _('Incoming Shipment'),
        'type': 'ir.actions.act_window',
        'res_model': 'stock.picking',
        'view_mode': 'tree,form',
        'domain': [('id', 'in', self.picking_ids.ids)],
    }

def action_view_invoice(self):
    """Open vendor bills"""
    return {
        'name': _('Vendor Bills'),
        'type': 'ir.actions.act_window',
        'res_model': 'account.move',
        'view_mode': 'tree,form',
        'domain': [('id', 'in', self.invoice_ids.ids)],
    }
```

## Incoming Move Generation

PO confirmation creates stock moves:
```
PO Confirm → Stock Move (vendor → WH) → Stock Picking (Receipt)
```

## See Also
- [Modules/Stock](Stock.md) — Receipt picking
- [Modules/Account](Account.md) — Vendor bill
- [Modules/Product](Product.md) — Product supplier info
- [Modules/Sale](Sale.md) — Sale vs Purchase flow