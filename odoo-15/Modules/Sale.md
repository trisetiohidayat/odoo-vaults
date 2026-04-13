# Sale — Sales Order

Dokumentasi Odoo 15 untuk Sale module. Source: `addons/sale/models/`

## Models

| Model | File | Description |
|---|---|---|
| `sale.order` | `sale_order.py` | Sales Order / Quotation |
| `sale.order.line` | `sale_order_line.py` | Order Line Items |
| `sale.advancesettle` | `sale_advance_payment.py` | Advance Payment Wizard |
| `saleportal.mixin` | `portal.py` | Portal access mixin |

## SaleOrder Fields

```python
class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Order Reference (readonly, auto-generated) |
| `origin` | Char | Source Document reference |
| `client_order_ref` | Char | Customer Reference |
| `state` | Selection | Status: draft/sent/sale/done/cancel |
| `date_order` | Datetime | Order Date |
| `validity_date` | Date | Expiration date |
| `is_expired` | Boolean | Computed expired status |

### Partner Fields

| Field | Type | Description |
|---|---|---|
| `partner_id` | Many2one(res.partner) | Customer |
| `partner_invoice_id` | Many2one(res.partner) | Invoice Address |
| `partner_shipping_id` | Many2one(res.partner) | Delivery Address |

### Commercial Fields

| Field | Type | Description |
|---|---|---|
| `user_id` | Many2one(res.users) | Salesperson |
| `team_id` | Many2one(crm.team) | Sales Team |
| `pricelist_id` | Many2one(product.pricelist) | Price List |
| `currency_id` | Many2one(res.currency) | Currency (from pricelist) |
| `analytic_account_id` | Many2one(account.analytic.account) | Analytic Account |

### Financial Fields

| Field | Type | Description |
|---|---|---|
| `amount_untaxed` | Monetary | Untaxed total |
| `amount_tax` | Monetary | Tax amount |
| `amount_total` | Monetary | Grand total |
| `amount_undiscounted` | Float | Before discount |
| `currency_rate` | Float | Currency conversion rate |
| `tax_totals_json` | Char | Tax breakdown JSON |

### Lines & Invoicing

| Field | Type | Description |
|---|---|---|
| `order_line` | One2many(sale.order.line) | Order lines |
| `invoice_count` | Integer | Number of invoices |
| `invoice_ids` | Many2many(account.move) | Linked invoices |
| `invoice_status` | Selection | Invoice status |
| `transaction_ids` | Many2many(payment.transaction) | Payment transactions |

### Portal & Signature

| Field | Type | Description |
|---|---|---|
| `signature` | Binary | Customer signature |
| `signed_by` | Char | Signer name |
| `signed_on` | Datetime | Sign date |
| `require_signature` | Boolean | Require online signature |
| `require_payment` | Boolean | Require online payment |

### Other Fields

| Field | Type | Description |
|---|---|---|
| `payment_term_id` | Many2one(account.payment.term) | Payment Terms |
| `fiscal_position_id` | Many2one(account.fiscal.position) | Fiscal Position |
| `company_id` | Many2one(res.company) | Company |
| `commitment_date` | Datetime | Promised delivery date |
| `expected_date` | Datetime | Computed expected delivery |
| `note` | Html | Terms and conditions |
| `tag_ids` | Many2many(crm.tag) | Tags |

## SaleOrder State Machine

```
draft (Quotation) → sent (Quotation Sent) → sale (Sales Order) → done (Locked)
       ↓                    ↓                     ↓
    cancel              cancel               cancel
       ↓                   ↓                    ↓
    draft (Reset)       draft (Reset)        done (Locked, no reset)
```

## Key Computed Fields

```python
# Amount totals (depends on order_line.price_total)
@api.depends('order_line.price_total')
def _amount_all(self):
    for order in self:
        amount_untaxed = amount_tax = 0.0
        for line in order.order_line:
            amount_untaxed += line.price_subtotal
            amount_tax += line.price_tax
        order.update({
            'amount_untaxed': amount_untaxed,
            'amount_tax': amount_tax,
            'amount_total': amount_untaxed + amount_tax,
        })

# Invoice status (depends on order_line.invoice_status)
@api.depends('state', 'order_line.invoice_status')
def _get_invoice_status(self):
    # unconfirmed_orders -> 'no'
    # to invoice -> 'to invoice'
    # all invoiced -> 'invoiced'
    # all upselling -> 'upselling'

# Currency rate
@api.depends('pricelist_id', 'date_order', 'company_id')
def _compute_currency_rate(self):
    # Rate to company currency at date_order
```

## Action Methods

```python
def action_quotation_send(self):
    """Send quotation by email"""
    self.action_confirm()  # Confirm first
    ...

def action_confirm(self):
    """Confirm order (draft/quotation → sale)"""
    for order in self:
        if order.state not in ('draft', 'sent'):
            continue
        order.write({'state': 'sale'})
        # Create procurement
    return True

def action_lock(self):
    """Lock order (sale → done)"""
    self.write({'state': 'done'})

def action_unlock(self):
    """Unlock order (done → sale)"""
    self.write({'state': 'sale'})

def action_cancel(self):
    """Cancel order"""
    self.write({'state': 'cancel'})

def action_draft(self):
    """Reset to draft"""
    self.write({'state': 'draft'})
```

## SaleOrderLine Fields

```python
class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _description = "Sales Order Line"
    _order = "sequence, id"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `order_id` | Many2one(sale.order) | Parent order |
| `sequence` | Integer | Display order |
| `name` | Char | Description |
| `product_id` | Many2one(product.product) | Product |
| `product_template_id` | Many2one(product.template) | Product template |
| `product_uom_qty` | Float | Ordered quantity |
| `product_uom` | Many2one(uom.uom) | Unit of measure |
| `qty_delivered` | Float | Delivered quantity |
| `qty_invoiced` | Float | Invoiced quantity |
| `qty_to_invoice` | Float | Quantity to invoice |
| `price_unit` | Float | Unit price |
| `price_subtotal` | Monetary | Subtotal (untaxed) |
| `price_tax` | Monetary | Tax amount |
| `price_total` | Monetary | Total (taxed) |
| `discount` | Float | Discount (%) |
| `tax_id` | Many2many(account.tax) | Taxes |
| `is_downpayment` | Boolean | Is downpayment/advance |
| `invoice_lines` | Many2many(account.move.line) | Linked invoice lines |
| `state` | Selection | Line state |
| `product_type` | Selection | Product type |

## Workflow

1. **Create quotation** (draft)
2. **Send quotation** (draft → sent)
3. **Confirm order** (sent → sale) → creates procurement
4. **Lock order** (sale → done)
5. **Create invoice** from order lines
6. **Deliver goods** (stock.picking linked)

## Inheritance / Extension Points

```python
# Extend sale.order
class SaleOrderExt(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    # Add custom field
    x_custom_field = fields.Char('Custom Field')

    # Override compute
    @api.depends('order_line.price_total')
    def _amount_all(self):
        super()._amount_all()
        for order in self:
            order.amount_total += order.x_custom_charge
```

## See Also
- [[Modules/Stock]] — Delivery order (stock.picking)
- [[Modules/Account]] — Invoice (account.move)
- [[Modules/Project]] — Sale + Project integration
- [[Modules/Product]] — Product, Pricelist