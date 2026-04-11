---
tags: [odoo, odoo17, flow, purchase, stock, account]
---

# Full Purchase-to-Payment Flow — Complete

Complete end-to-end business flow from RFQ to cash disbursement, covering Odoo 17 source code.

**Source:** `odoo/addons/purchase/models/purchase_order.py`, `odoo/addons/purchase_stock/models/purchase_order.py`

## Flow Diagram

```
Request for Quotation (draft)
    ↓ send / button_confirm
RFQ (sent) ── email to vendor
    ↓ button_confirm / button_approve
Purchase Order (to approve) ── needs manager approval (if double validation)
    ↓ button_approve
Purchase Order (purchase) ── creates receipt picking (via purchase_stock)
    ↓
Stock Picking IN (draft) ── receipt created
    ↓ validate / _action_done
Stock Picking IN (done) ── stock.quant updated
    ↓
Vendor Bill (draft) ── action_create_invoice
    ↓ action_post
Vendor Bill (posted) ── posted to ledger
    ↓ register_payment
Account Payment ── outbound payment created
    ↓ reconcile
Fully Reconciled
```

## State Definitions

**purchase.order states** (`purchase_order.py` line 98-105):
```python
state = fields.Selection([
    ('draft', 'RFQ'),
    ('sent', 'RFQ Sent'),
    ('to approve', 'To Approve'),
    ('purchase', 'Purchase Order'),
    ('done', 'Locked'),
    ('cancel', 'Cancelled')
])
```

## Step-by-Step Detail

### Step 1: RFQ Creation

**State:** `draft`

**Model:** `purchase.order`

**Trigger:** User creates new purchase order via UI or `_create()` method

**What happens:**
1. PO created with `state = 'draft'`, `name = 'New'`
2. Vendor selected via `partner_id` field
3. Lines added via `order_line` One2many (`purchase.order.line`)
4. **`onchange_product_id()`** cascades on line when product is selected:
   - `name` — product name / description
   - `price_unit` — from supplierinfo (or list price fallback)
   - `taxes_id` — taxes from supplierinfo
   - `product_uom` — product's purchase UoM
   - `date_planned` — expected delivery date
5. `date_order` set to now (order deadline)

**Invoiceability computed** (`_get_invoiced`, line 47):
- `invoice_status = 'to invoice'` when `state == 'purchase'` and any line has `qty_to_invoice > 0`
- `invoice_status = 'invoiced'` when all lines have `qty_to_invoice == 0` and `invoice_ids` exist

---

### Step 2: RFQ Sending

**State:** `draft` → `sent`

**Trigger:** "Send by Email" button → `action_rfq_send()` (line ~455)

**What happens:**
1. Email composer opened with PO rendered as PDF
2. On confirm/send: `state → 'sent'`
3. Email dispatched to vendor with PDF attachment
4. Vendor can reply / quote referencing `partner_ref`

**`print_quotation()`** (line 487) also sets state to `sent` without email.

---

### Step 3: PO Confirmation — Two-Step Process

#### Step 3a: `button_confirm()` (line 501)

**States:** `draft`/`sent` → `to approve` OR `purchase`

```python
def button_confirm(self):
    for order in self:
        if order.state not in ['draft', 'sent']:
            continue
        order.order_line._validate_analytic_distribution()
        order._add_supplier_to_product()          # critical side effect
        if order._approval_allowed():              # check double validation
            order.button_approve()
        else:
            order.write({'state': 'to approve'})
```

**`_approval_allowed()`** (line 957) — Returns `True` if ANY:
- `po_double_validation == 'one_step'` in company settings
- `po_double_validation == 'two_step'` AND `amount_total < po_double_validation_amount` threshold
- User is in `purchase.group_purchase_manager`

**If `_approval_allowed()` is True:** immediately calls `button_approve()`

**If False:** `state → 'to approve'` — waits for manager approval

#### Step 3b: `button_approve()` (line 491)

**State:** `to approve` → `purchase` (or directly from `button_confirm`)

```python
def button_approve(self, force=False):
    self = self.filtered(lambda order: order._approval_allowed())
    self.write({'state': 'purchase', 'date_approve': fields.Datetime.now()})
    # If company lock is set: also write state = 'done' (locked)
    self.filtered(lambda p: p.company_id.po_lock == 'lock').write({'state': 'done'})
```

**In `purchase_stock` override** (`purchase_stock/models/purchase_order.py`, line 112):
```python
def button_approve(self, force=False):
    result = super().button_approve(force=force)
    self._create_picking()   # <-- receipt created HERE
    return result
```

#### Side Effects of Confirmation

**1. `_add_supplier_to_product()` (line 542)**

This is the most critical automatic side effect:

```python
def _add_supplier_to_product(self):
    for line in self.order_line:
        partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
        already_seller = (partner | self.partner_id) & line.product_id.seller_ids.mapped('partner_id')
        if line.product_id and not already_seller and len(line.product_id.seller_ids) <= 10:
            # Convert price to company's purchase currency
            currency = partner.property_purchase_currency_id or self.env.company.currency_id
            price = self.currency_id._convert(line.price_unit, currency, ...)
            # Convert price to template's UoM if needed
            if line.product_id.product_tmpl_id.uom_po_id != line.product_uom:
                default_uom = line.product_id.product_tmpl_id.uom_po_id
                price = line.product_uom._compute_price(price, default_uom)
            vals = {'seller_ids': [(0, 0, supplierinfo)]}
            line.product_id.product_tmpl_id.sudo().write(vals)  # no access check
```

**Key rules:**
- Max 10 suppliers per product (prevents "miscellaneous" product pollution)
- Vendor added as `product.supplierinfo` record
- Price converted to purchase currency
- UoM conversion applied if PO line UoM differs from product's `uom_po_id`
- Runs as **sudo** — bypasses access rights (line 574)

**2. Receipt Picking Created** — via `purchase_stock._create_picking()`

`button_approve()` in `purchase_stock` calls `self._create_picking()`:

```python
def _create_picking(self):
    for order in self.filtered(lambda po: po.state in ('purchase', 'done')):
        if any(product.type in ['product', 'consu'] for product in order.order_line.product_id):
            pickings = order.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            if not pickings:
                res = order._prepare_picking()
                picking = StockPicking.create(res)
                pickings = picking
            moves = order.order_line._create_stock_moves(picking)
            moves = moves.filtered(...)._action_confirm()
            moves._action_assign()   # attempt immediate reservation
```

`_prepare_picking()` returns (line 217):
```python
{
    'picking_type_id': self.picking_type_id.id,   # incoming
    'partner_id': self.partner_id.id,
    'location_id': self.partner_id.property_stock_supplier.id,  # supplier location
    'location_dest_id': self._get_destination_location(),       # WH/Input
    'origin': self.name,
    'date': self.date_order,
    'state': 'draft',
}
```

**3. PO Locked** — if `company_id.po_lock == 'lock'`, state goes straight to `done` (no edits allowed)

---

### Step 4: Receipt Validation (Stock Picking IN)

**State:** `draft` → `assigned` → `done`

**Trigger:** Validate button on `stock.picking`

**Same chain as sale delivery:**

```
button_validate()
  → _action_done()
    → stock.move._action_done()
      → stock.quant._update_available_quantity()   # quants updated
      → stock.valuation.layer created              # (if stock_account)
      → account.move.line created                   # (if automated valuation)
```

**Purchase-specific details:**
- Products received into `partner_id.property_stock_supplier` (vendor location) initially
- Then flow to `WH/Stock` via `_get_destination_location()` which returns `picking_type_id.default_location_dest_id` (typically `Stock`)
- `effective_date` on PO updated to first receipt `date_done`

**`purchase_stock` overrides `button_cancel()`** (line 117): Raises `UserError` if any `move_ids` are already `done`:
```python
if move.state == 'done':
    raise UserError(_('Unable to cancel purchase order %s as some receptions have already been done.'))
```
This prevents cancelling a PO after partial or full receipt.

---

### Step 5: Vendor Bill Creation

**Trigger:** "Create Bill" button → `action_create_invoice()` (line 576)

```python
def action_create_invoice(self):
    precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    for order in self:
        if order.invoice_status != 'to invoice':
            continue
        invoice_vals = order._prepare_invoice()
        for line in order.order_line:
            if not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                line_vals = line._prepare_account_move_line()
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
        # creates in self.env['account.move'] via batch create
```

**`_prepare_invoice()`** (line 649) — builds invoice dict:
```python
{
    'ref': self.partner_ref or '',
    'move_type': 'in_invoice',        # vendor bill
    'partner_id': partner_invoice.id,
    'invoice_origin': self.name,       # links back to PO
    'payment_reference': self.partner_ref or '',
    'fiscal_position_id': ...,
    'invoice_payment_term_id': self.payment_term_id.id,
    'currency_id': self.currency_id.id,
    'invoice_line_ids': [],
    'company_id': self.company_id.id,
}
```

**In `purchase_stock`**, `_prepare_invoice()` is extended (line 166):
```python
invoice_vals['invoice_incoterm_id'] = self.incoterm_id.id
```

**Bill-Picking Matching:**
- `invoice_origin` = PO `name` enables cross-referencing
- `purchase_stock` links: `order_line.move_ids.picking_id` tracks which receipt each PO line delivered to
- `invoice_ids` computed from `order_line.invoice_lines.move_id` (line 71)

---

### Step 6: Bill Validation

**State:** `draft` → `posted`

**Trigger:** "Confirm" button → `action_post()` on `account.move`

**What happens:**
1. Validate accounts and taxes configured
2. Check against fiscal lock dates
3. Post to general ledger
4. Update vendor (partner) account balance
5. PO `invoice_status` → `'invoiced'` when all lines fully billed

---

### Step 7: Payment to Vendor

**Trigger:** "Register Payment" button → creates `account.payment`

```python
payment_type = 'outbound'          # money going out
partner_type = 'supplier'          # to vendor
destination_account_id = vendor's payable account
amount = bill amount (or partial)
```

Payment `state = 'posted'` immediately upon creation.

---

### Step 8: Reconciliation

**Automatic** when:
- Payment's `destination_account_id` matches bill's receivable/payable account
- Amount matches (full reconciliation) or partially matches (partial reconciliation)

**Creates:** `account.partial.reconcile` → `account.full.reconcile`

**Partial payment case:** Multiple payments against one bill, or one payment against multiple bills from same vendor.

---

## Receipt Status Tracking

**`purchase_stock` adds** (line 30):

```python
receipt_status = fields.Selection([
    ('pending', 'Not Received'),
    ('partial', 'Partially Received'),
    ('full', 'Fully Received'),
])
```

Computed from `picking_ids` states:
- `'pending'` — all pickings not started
- `'partial'` — some pickings `done`, others pending
- `'full'` — all pickings `done` or `cancel`

---

## Double Validation Configuration

**Company-level settings** (`res.company`):

| Setting | Value | Behavior |
|---------|-------|----------|
| `po_double_validation` | `one_step` | Single user approves any amount |
| `po_double_validation` | `two_step` | Manager required above threshold |
| `po_double_validation_amount` | e.g. 5000 | Threshold in company currency |
| `po_lock` | `lock` | PO locked after approval (`state='done'`) |

---

## Key Differences: Purchase vs. Sale Flow

| Aspect | Sale | Purchase |
|--------|------|----------|
| Confirmation trigger | `action_confirm()` | `button_approve()` → `_create_picking()` |
| Picking type | OUT (delivery order) | IN (receipt) |
| Bill creation | Manual or from SO | `action_create_invoice()` from PO |
| Picking-Bill link | None by default | `invoice_origin` = PO name |
| Payment direction | Receive from customer | Pay to vendor |
| Supplier auto-registration | N/A | `_add_supplier_to_product()` |
| 2-step approval | Optional | Optional via `po_double_validation` |
| PO line qty changes | Creates procurement | `_log_decrease_ordered_quantity()` |
| Cancel after receipt | Not possible | Raises `UserError` if moves `done` |

---

## State Summary Table

| Stage | Document | State Field Value |
|-------|----------|-------------------|
| 1 | purchase.order | `draft` |
| 2 | purchase.order | `sent` |
| 3 | purchase.order | `to approve` (if double validation) |
| 4 | purchase.order | `purchase` |
| 4b | stock.picking | `draft` → `assigned` → `done` |
| 5 | account.move | `draft` |
| 6 | account.move | `posted` |
| 7 | account.payment | `posted` |
| 8 | account.move.line | `reconciled` |

---

## Related Source Files

- `odoo/addons/purchase/models/purchase_order.py` — main PO model, states, `button_confirm`, `button_approve`, `_add_supplier_to_product`, `action_create_invoice`
- `odoo/addons/purchase/models/purchase_order_line.py` — `_create_stock_moves()`, invoice line generation
- `odoo/addons/purchase_stock/models/purchase_order.py` — `_create_picking()`, receipt tracking, `receipt_status`
- `odoo/addons/stock/models/stock_move.py` — `_action_done()`, quant updates
- `odoo/addons/account/models/account_move.py` — `action_post()`, reconciliation

---

## See Also

- [[Modules/purchase]] — `purchase.order` model, `purchase.order.line`
- [[Modules/stock]] — `stock.picking` receipt, `stock.move`
- [[Modules/account]] — vendor bills, `account.move`
- [[Flows/Stock/receipt-flow]] — detailed receipt validation flow
- [[Patterns/Workflow Patterns]] — state machine patterns in Odoo
