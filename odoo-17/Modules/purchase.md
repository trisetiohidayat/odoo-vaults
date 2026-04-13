---
tags: [odoo, odoo17, module, purchase]
research_depth: deep
---

# Purchase Module — Deep Research

**Source:** `addons/purchase/models/`

**Files in module:**
- `purchase_order.py` (~800+ lines) — Core purchase.order model
- `purchase_order_line.py` (~600+ lines) — purchase.order.line model

---

## purchase.order

**Class definition:** `PurchaseOrder(models.Model)` — Line 18
**Inherits:** `portal.mixin`, `product.catalog.mixin`, `mail.thread`, `mail.activity.mixin`
**Model name:** `_name = 'purchase.order'`
**Order:** `_order = 'priority desc, id desc'`
**Names search:** `_rec_names_search = ['name', 'partner_ref']`

### All Fields (complete)

| Field | Type | Line | Description |
|-------|------|------|-------------|
| `name` | Char | 78 | Order Reference — required, trigram index, copy=False, default='New' |
| `priority` | Selection | 79 | '0' Normal / '1' Urgent — default='0', index=True |
| `origin` | Char | 81 | Source document (e.g. linked sale order) — copy=False |
| `partner_ref` | Char | 84 | Vendor reference — used to match vendor delivery orders (copy=False) |
| `date_order` | Datetime | 89 | Order deadline — required, default=Datetime.now, index, copy=False |
| `date_approve` | Datetime | 91 | Confirmation date — readonly, index, copy=False (set on PO confirm) |
| `partner_id` | Many2one(res.partner) | 92 | Vendor — required, change_default, tracking=True, check_company |
| `dest_address_id` | Many2one(res.partner) | 93 | Dropship address — check_company, for direct vendor-to-customer delivery |
| `currency_id` | Many2one(res.currency) | 96 | Currency — required, default from env.company.currency_id |
| `state` | Selection | 98 | Status: draft/sent/to approve/purchase/done/cancel — default='draft', readonly |
| `order_line` | One2many | 106 | purchase.order.line records — copy=True |
| `notes` | Html | 107 | Terms and conditions |
| `invoice_count` | Integer | 109 | Number of vendor bills — computed via _compute_invoice |
| `invoice_ids` | Many2many | 110 | Vendor bills — computed via _compute_invoice |
| `invoice_status` | Selection | 111 | Billing status: no/to invoice/invoiced — computed via _get_invoiced |
| `date_planned` | Datetime | 116 | Expected arrival — computed as min(date_planned) of all lines |
| `date_calendar_start` | Datetime | 119 | Calendar view start — date_approve if confirmed, else date_order |
| `amount_untaxed` | Monetary | 121 | Untaxed total — stored, computed via _amount_all |
| `tax_totals` | Binary | 122 | JSON tax totals for frontend |
| `amount_tax` | Monetary | 123 | Tax total — stored, computed via _amount_all |
| `amount_total` | Monetary | 124 | Grand total — stored, computed via _amount_all |
| `fiscal_position_id` | Many2one | 126 | Fiscal position — domain allows any company or matching company |
| `tax_country_id` | Many2one(res.country) | 127 | Fiscal country for tax filtering — computed, compute_sudo=True |
| `tax_calculation_rounding_method` | Selection | 133 | Related to company (readonly) |
| `payment_term_id` | Many2one | 136 | Payment terms — domain allows any company or matching company |
| `incoterm_id` | Many2one | 137 | Incoterm for international trade |
| `product_id` | Many2one | 139 | Related to order_line.product_id (for search/filters) |
| `user_id` | Many2one(res.users) | 140 | Buyer — default from env.user, index, tracking, check_company |
| `company_id` | Many2one(res.company) | 143 | Company — required, index, default from env.company.id |
| `country_code` | Char | 144 | Related company country code (readonly) |
| `currency_rate` | Float | 145 | Rate: currency / company currency, computed, compute_sudo=True, store=True |
| `mail_reminder_confirmed` | Boolean | 147 | Vendor confirmed receipt reminder email (readonly, copy=False) |
| `mail_reception_confirmed` | Boolean | 148 | Vendor confirmed goods reception (readonly, copy=False) |
| `receipt_reminder_email` | Boolean | 150 | Send reminder email — computed from partner |
| `reminder_date_before_receipt` | Integer | 151 | Days before receipt to send reminder — computed from partner |

---

### All Methods (with line numbers)

| Method | Line | Description |
|--------|------|-------------|
| `_amount_all()` | 25 | Computes amount_untaxed, amount_tax, amount_total (round_globally aware) |
| `_get_invoiced()` | 47 | Computes invoice_status from line qty_to_invoice |
| `_compute_invoice()` | 71 | Aggregates invoice_ids and invoice_count from order lines |
| `_compute_date_calendar_start()` | 175 | Sets date_calendar_start = date_approve if purchase/done else date_order |
| `_compute_currency_rate()` | 180 | Ratio between PO currency and company currency |
| `_compute_date_planned()` | 185 | Sets date_planned = min(date_planned from lines) |
| `_compute_display_name()` | 195 | Returns name + partner_ref (+ total if context show_total_amount) |
| `_compute_receipt_reminder_email()` | 206 | Copies from partner.receipt_reminder_email and reminder_date_before_receipt |
| `_compute_tax_totals()` | 212 | Prepares tax totals JSON via account.tax._prepare_tax_totals |
| `_compute_tax_country_id()` | 222 | fiscal_position foreign_vat country else company.account_fiscal_country_id |
| `onchange_date_planned()` | 230 | Propagates date_planned change to all non-display lines |
| `write()` | 235 | Writes partner values (split between PO and partner records) |
| `create()` | 242 | Creates PO with sequence, handles partner values in sudo |
| `_unlink_if_cancelled()` | 263 | Only cancelled POs can be deleted |
| `copy()` | 269 | Copies PO, re-fetches seller info for each line |
| `_must_delete_date_planned()` | 282 | Returns True for 'order_line' field (to suppress cascade date_planned changes) |
| `onchange()` | 286 | Override to prevent cascading date_planned on line date_planned changes |
| `_get_report_base_filename()` | 298 | Returns 'Purchase Order-%s' % name |
| `onchange_partner_id()` | 302 | Sets fiscal_position_id, payment_term_id, currency_id, user_id from partner |
| `_compute_tax_id()` | 320 | Onchange trigger: recomputes taxes on all lines |
| `onchange_partner_id_warning()` | 327 | Shows partner purchase warnings (block/no-message) |
| `message_post()` | 357 | Auto-sets state to 'sent' if mark_rfq_as_sent context |
| `_notify_get_recipients_groups()` | 366 | Customizes portal button for confirm/reception/update-dates |
| `_notify_by_email_prepare_rendering_context()` | 396 | Adds amount+date subtitle for non-draft/non-sent POs |
| `_track_subtype()` | 415 | Returns mt_rfq_ confirmed/approved/done/sent events |
| `action_rfq_send()` | 433 | Opens email composer for RFQ/PO |
| `print_quotation()` | 487 | Sets state='sent', prints report |
| `button_approve()` | 491 | Sets state='purchase', date_approve=now; if po_lock='lock': sets 'done' |
| `button_draft()` | 497 | Resets state='draft' |
| `button_confirm()` | 501 | Main confirmation: validates, adds supplier, routes to approve or purchase |
| `button_cancel()` | 516 | Cancels PO (fails if non-draft/cancelled invoices exist) |
| `button_unlock()` | 524 | Resets state='purchase' (unlock) |
| `button_done()` | 527 | Sets state='done', priority='0' |
| `_prepare_supplier_info()` | 530 | Returns supplierinfo dict from PO line data |
| `_add_supplier_to_product()` | 542 | Adds vendor to product.supplierinfo if not already present |
| `action_create_invoice()` | 576 | Creates vendor bill from PO (invoice_status='to invoice') |
| `_prepare_invoice()` | 649 | Returns dict of invoice values for vendor bill |
| `action_view_invoice()` | 674 | Opens vendor bill list/form action |
| `retrieve_dashboard()` | 700 | Returns dashboard stats (SQL queries) |
| `_send_reminder_mail()` | 767 | Sends receipt reminder email to vendor |
| `send_reminder_preview()` | 786 | Previews reminder email to current user |

---

### button_confirm() — Full Implementation (Lines 501–514)

```python
def button_confirm(self):
    for order in self:
        if order.state not in ['draft', 'sent']:          # (1) Skip if not draft/sent
            continue
        order.order_line._validate_analytic_distribution()  # (2) Validate analytic
        order._add_supplier_to_product()                  # (3) Register vendor on product
        # Deal with double validation process
        if order._approval_allowed():                     # (4) Check approval threshold
            order.button_approve()                        # (5a) Auto-approve if allowed
        else:
            order.write({'state': 'to approve'})          # (5b) Route to approval queue
        if order.partner_id not in order.message_partner_ids:
            order.message_subscribe([order.partner_id.id])  # (6) Subscribe vendor
    return True
```

**Step-by-step breakdown:**
1. If state is not `draft` or `sent`, skip (already confirmed/cancelled)
2. Validate analytic distribution on all order lines (raises if distribution is invalid)
3. `_add_supplier_to_product()` — adds this vendor to each product's supplier list (so future POs auto-populate)
4. `_approval_allowed()` — checks if order amount is under the user's approval limit (via `purchase.group_purchase_manager`)
5. If allowed: calls `button_approve()` directly — sets state='purchase', date_approve=now
6. If not allowed: sets state='to approve' — waits for manager approval
7. Subscribes vendor partner to PO chatter

---

### button_approve() — Implementation (Lines 491–495)

```python
def button_approve(self, force=False):
    self = self.filtered(lambda order: order._approval_allowed())
    self.write({'state': 'purchase', 'date_approve': fields.Datetime.now()})
    self.filtered(lambda p: p.company_id.po_lock == 'lock').write({'state': 'done'})
    return {}
```

**Key behavior:**
- Filters to only orders where `_approval_allowed()` returns True
- Sets `state='purchase'` and `date_approve=now()`
- If company's `po_lock == 'lock'`: immediately sets `state='done'` (auto-lock after approval)
- Returns empty dict (no action window returned)

---

### button_cancel() — Full Implementation (Lines 516–522)

```python
def button_cancel(self):
    for order in self:
        for inv in order.invoice_ids:
            if inv and inv.state not in ('cancel', 'draft'):   # (1) Check all invoices
                raise UserError(_(
                    "Unable to cancel this purchase order. "
                    "You must first cancel the related vendor bills."))

    self.write({'state': 'cancel', 'mail_reminder_confirmed': False})  # (2) Cancel
```

**Critical behavior:**
- Iterates all linked invoices; if ANY is posted (not draft or cancel), raises UserError
- Must cancel all vendor bills BEFORE cancelling the PO
- Sets `mail_reminder_confirmed = False`

**Contrast with sale:**
- `sale.order` cancels draft invoices automatically in `_action_cancel()`
- `purchase.order` raises an error — user must manually cancel bills first

---

### _add_supplier_to_product() — Vendor Registration (Lines 542–574)

```python
def _add_supplier_to_product(self):
    for line in self.order_line:
        # Use parent company if partner is a contact
        partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
        already_seller = (partner | self.partner_id) & line.product_id.seller_ids.mapped('partner_id')
        if line.product_id and not already_seller and len(line.product_id.seller_ids) <= 10:
            # Convert price to supplier's currency and UoM
            currency = partner.property_purchase_currency_id or self.env.company.currency_id
            price = self.currency_id._convert(line.price_unit, currency, line.company_id,
                                              line.date_order or fields.Date.today(), round=False)
            # Convert to template's purchase UoM if different from line UoM
            if line.product_id.product_tmpl_id.uom_po_id != line.product_uom:
                default_uom = line.product_id.product_tmpl_id.uom_po_id
                price = line.product_uom._compute_price(price, default_uom)

            supplierinfo = self._prepare_supplier_info(partner, line, price, currency)
            # Preserve existing product_name/product_code from seller
            seller = line.product_id._select_seller(...)
            if seller:
                supplierinfo['product_name'] = seller.product_name
                supplierinfo['product_code'] = seller.product_code
            # Write via sudo to bypass access rights
            line.product_id.product_tmpl_id.sudo().write({'seller_ids': [(0, 0, supplierinfo)]})
```

**Purpose:** When a PO is confirmed, the vendor is automatically added to the product's vendor list (supplierinfo) if not already present. This enables:
- Faster PO creation for the same vendor in the future
- Default price/lead time pulled from vendor's existing info

**Key constraints:**
- Maximum 10 suppliers per product (prevents "miscellaneous" product pollution)
- Converts price to supplier's preferred currency
- Converts price to product's purchase UoM (uom_po_id) if different

---

### _prepare_invoice() — Vendor Bill Generation (Lines 649–671)

```python
def _prepare_invoice(self):
    """Prepare the dict of values to create the new invoice for a purchase order."""
    self.ensure_one()
    move_type = self._context.get('default_move_type', 'in_invoice')

    partner_invoice = self.env['res.partner'].browse(
        self.partner_id.address_get(['invoice'])['invoice'])
    partner_bank_id = self.partner_id.commercial_partner_id.bank_ids\
        .filtered_domain(['|', ('company_id', '=', False),
                          ('company_id', '=', self.company_id.id)])[:1]

    invoice_vals = {
        'ref': self.partner_ref or '',
        'move_type': move_type,
        'narration': self.notes,
        'currency_id': self.currency_id.id,
        'partner_id': partner_invoice.id,
        'fiscal_position_id': (self.fiscal_position_id or
            self.fiscal_position_id._get_fiscal_position(partner_invoice)).id,
        'payment_reference': self.partner_ref or '',
        'partner_bank_id': partner_bank_id.id,
        'invoice_origin': self.name,
        'invoice_payment_term_id': self.payment_term_id.id,
        'invoice_line_ids': [],
        'company_id': self.company_id.id,
    }
    return invoice_vals
```

**Key observations:**
- `move_type` defaults to `in_invoice` but is context-dependent (supports refunds via `default_move_type='in_refund'`)
- `partner_id` is the vendor's invoice address (from `address_get(['invoice'])`)
- `ref` and `payment_reference` both default to `self.partner_ref` (vendor's reference)
- `partner_bank_id` is taken from commercial partner's bank accounts
- `fiscal_position_id` resolved if not set
- No `user_id`, `team_id`, or UTM fields (unlike sale's `_prepare_invoice`)

---

### action_create_invoice() — Vendor Bill Creation (Lines 576–647)

This is the main method that creates vendor bills from POs:

```python
def action_create_invoice(self):
    precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    invoice_vals_list = []
    sequence = 10

    for order in self:
        if order.invoice_status != 'to invoice':   # Skip if nothing to invoice
            continue

        order = order.with_company(order.company_id)
        pending_section = None

        invoice_vals = order._prepare_invoice()     # Get base invoice dict

        for line in order.order_line:
            if line.display_type == 'line_section':
                pending_section = line
                continue
            if not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                if pending_section:
                    line_vals = pending_section._prepare_account_move_line()
                    line_vals.update({'sequence': sequence})
                    invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                    sequence += 1
                    pending_section = None
                line_vals = line._prepare_account_move_line()  # Key: builds AML values
                line_vals.update({'sequence': sequence})
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                sequence += 1
        invoice_vals_list.append(invoice_vals)

    if not invoice_vals_list:
        raise UserError(_('There is no invoiceable line...'))

    # Group by (company_id, partner_id, currency_id)
    new_invoice_vals_list = []
    for grouping_keys, invoices in groupby(invoice_vals_list,
        key=lambda x: (x.get('company_id'), x.get('partner_id'), x.get('currency_id'))):
        origins = set()
        payment_refs = set()
        refs = set()
        ref_invoice_vals = None
        for invoice_vals in invoices:
            if not ref_invoice_vals:
                ref_invoice_vals = invoice_vals
            else:
                ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
            origins.add(invoice_vals['invoice_origin'])
            payment_refs.add(invoice_vals['payment_reference'])
            refs.add(invoice_vals['ref'])
        ref_invoice_vals.update({
            'ref': ', '.join(refs)[:2000],
            'invoice_origin': ', '.join(origins),
            'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
        })
        new_invoice_vals_list.append(ref_invoice_vals)

    # Create all invoices
    moves = self.env['account.move']
    AccountMove = self.env['account.move'].with_context(default_move_type='in_invoice')
    for vals in invoice_vals_list:
        moves |= AccountMove.with_company(vals['company_id']).create(vals)

    # Convert negative-total moves to refunds
    moves.filtered(lambda m: m.currency_id.round(m.amount_total) < 0)\
        .action_switch_move_type()

    return self.action_view_invoice(moves)
```

**Key behavior:**
- Only processes orders with `invoice_status == 'to invoice'`
- Groups lines with sections (sections are included if they precede invoiceable lines)
- Groups invoices by (company_id, partner_id, currency_id) — same as sale's `_get_invoice_grouping_keys`
- Converts negative-total invoices to refunds automatically
- Returns action to view the created invoices

---

## Purchase Order States

```
draft → sent → to approve → purchase → done
                         ↘ cancel
```

| State | Label | Trigger | Behavior |
|-------|-------|---------|----------|
| `draft` | RFQ | Creation, `button_draft()` | Editable, not invoiceable, not billable |
| `sent` | RFQ Sent | Email sent, `print_quotation()` | Vendor acknowledged, can be confirmed |
| `to approve` | To Approve | `button_confirm()` when over approval limit | Waiting for manager approval |
| `purchase` | Purchase Order | `button_approve()` or auto-approved | Confirmed, can receive goods, can bill |
| `done` | Locked | `button_done()` or auto-lock on confirm (if po_lock='lock') | Read-only |
| `cancel` | Cancelled | `button_cancel()` | No further action |

**State selection (lines 98-105):**
```python
state = fields.Selection([
    ('draft', 'RFQ'),
    ('sent', 'RFQ Sent'),
    ('to approve', 'To Approve'),
    ('purchase', 'Purchase Order'),
    ('done', 'Locked'),
    ('cancel', 'Cancelled')
], string='Status', readonly=True, index=True, copy=False,
    default='draft', tracking=True)
```

**Approval flow:**
- `button_confirm()` checks `_approval_allowed()` — based on purchase manager group membership
- If allowed: `button_approve()` directly
- If not allowed: state becomes `to approve` — manager must call `button_approve()` manually
- In `to approve` state, anyone with purchase manager rights can approve

---

## purchase.order.line

**Class definition:** `PurchaseOrderLine(models.Model)` — Line 12
**Inherits:** `analytic.mixin`
**Model name:** `_name = 'purchase.order.line'`
**Order:** `_order = 'order_id, sequence, id'`

### SQL Constraints

```python
# Lines 80-87
('accountable_required_fields',
    "CHECK(display_type IS NOT NULL OR (product_id IS NOT NULL AND product_uom IS NOT NULL AND date_planned IS NOT NULL))",
    "Missing required fields on accountable purchase order line.")
('non_accountable_null_fields',
    "CHECK(display_type IS NULL OR (product_id IS NULL AND price_unit = 0 AND product_uom_qty = 0 AND product_uom IS NULL AND date_planned is NULL))",
    "Forbidden values on non-accountable purchase order line")
```

Key difference from sale: `date_planned` is required for accountable lines.

---

### All Fields (complete)

| Field | Type | Line | Description |
|-------|------|------|-------------|
| `name` | Text | 18 | Description — required, computed from product + seller info (stored, editable) |
| `sequence` | Integer | 20 | Line order, default=10 |
| `product_qty` | Float | 21 | Quantity in product's purchase UoM — required, computed from packaging |
| `product_uom_qty` | Float | 23 | Quantity in line UoM — computed from product_qty and UoM conversion |
| `date_planned` | Datetime | 24 | Expected arrival — required for accountable lines, computed from seller.delay |
| `discount` | Float | 28 | Discount percentage — computed from vendor seller |
| `taxes_id` | Many2many | 33 | Taxes — from product.supplier_taxes_id + fiscal position |
| `product_uom` | Many2one | 34 | Unit of measure — domain filtered by product_uom_category_id |
| `product_uom_category_id` | Many2one | 35 | Related to product.uom_id.category_id |
| `product_id` | Many2one | 36 | product.product (domain: purchase_ok=True), index='btree_not_null' |
| `product_type` | Selection | 37 | Related product.detailed_type (readonly) |
| `price_unit` | Float | 38 | Unit price — required, computed from seller pricelist or standard price |
| `price_unit_discounted` | Float | 41 | price_unit * (1 - discount/100), computed |
| `price_subtotal` | Monetary | 43 | Untaxed amount — computed, stored |
| `price_total` | Monetary | 44 | Taxed amount — computed, stored |
| `price_tax` | Float | 45 | Tax amount — computed, stored |
| `order_id` | Many2one | 47 | Parent purchase.order — index, required, ondelete='cascade' |
| `company_id` | Many2one | 49 | Related order.company_id (stored, readonly) |
| `state` | Selection | 50 | Related order.state (stored) |
| `invoice_lines` | One2many | 52 | account.move.line records — purchase_line_id link, readonly |
| `qty_invoiced` | Float | 55 | Billed quantity — computed from invoice_lines |
| `qty_received_method` | Selection | 57 | 'manual' or False — computed from product type |
| `qty_received` | Float | 61 | Received quantity — computed or manual (manual only in base) |
| `qty_received_manual` | Float | 62 | Manual received qty storage (written via inverse) |
| `qty_to_invoice` | Float | 63 | To invoice quantity — computed |
| `partner_id` | Many2one | 66 | Related order.partner_id (stored, index) |
| `currency_id` | Many2one | 67 | Related order.currency_id (stored, readonly) |
| `date_order` | Datetime | 68 | Related order.date_order (readonly) |
| `date_approve` | Datetime | 69 | Related order.date_approve (readonly) |
| `product_packaging_id` | Many2one | 70 | Packaging — domain purchase=True, product match |
| `product_packaging_qty` | Float | 72 | Packaging quantity — computed |
| `tax_calculation_rounding_method` | Selection | 73 | Related company (readonly) |
| `display_type` | Selection | 76 | line_section/line_note or False — for UI-only lines |

---

### Key Methods

| Method | Line | Description |
|--------|------|-------------|
| `_compute_amount()` | 89 | Computes price_subtotal, price_tax, price_total via account.tax._compute_taxes |
| `_convert_to_tax_base_line_dict()` | 103 | Adapter for generic tax computation |
| `_compute_tax_id()` | 122 | Maps product.supplier_taxes_id via fiscal position |
| `_compute_price_unit_discounted()` | 130 | price_unit * (1 - discount/100) |
| `_compute_qty_invoiced()` | 135 | Sums invoice/refund quantities (respects accrual_entry_date context) |
| `_get_invoice_lines()` | 157 | Filters invoice_lines by accrual_entry_date if in context |
| `_compute_qty_received_method()` | 166 | Sets 'manual' for consu/service products |
| `_compute_qty_received()` | 174 | Uses qty_received_manual if qty_received_method='manual' |
| `_inverse_qty_received()` | 182 | Writes to qty_received_manual when qty_received is set |
| `create()` | 194 | Initializes missing fields, posts message for extra lines on confirmed PO |
| `write()` | 209 | Prevents display_type change; posts message on qty change for purchase/done POs |
| `_unlink_except_purchase_or_done()` | 231 | Cannot delete lines in purchase/done state |
| `_get_date_planned()` | 238 | date_order + seller.delay (or today's date + delay) |
| `_compute_analytic_distribution()` | 257 | From account.analytic.distribution.model |
| `onchange_product_id()` | 270 | Resets price/qty, calls _product_id_change, _suggest_quantity |
| `_product_id_change()` | 283 | Sets product_uom, name, tax_id from product |
| `onchange_product_id_warning()` | 297 | Shows product.purchase_line_warn warnings |
| `_compute_price_unit_and_date_planned_and_name()` | 318 | Main onchange: sets price from seller/standard cost, date from delay, name |
| `_compute_product_packaging_id()` | 377 | Suggests packaging matching PO's company |
| `_onchange_product_packaging_id()` | 390 | Warns if product_qty doesn't match packaging |
| `_compute_product_packaging_qty()` | 408 | Converts product_qty to packaging qty |
| `_compute_product_qty()` | 416 | Converts from packaging quantity to product_qty |
| `_compute_product_uom_qty()` | 426 | Converts product_qty to product's UoM (for display) |
| `_get_gross_price_unit()` | 434 | Price including tax and discount, in product's UoM |
| `action_add_from_catalog()` | 447 | Delegates to order.action_add_from_catalog() |
| `action_purchase_history()` | 451 | Opens purchase history for same product/vendor |
| `_suggest_quantity()` | 462 | Sets product_qty from seller's min_qty |
| `_get_product_catalog_lines_data()` | 481 | Returns catalog data (quantity, price, readOnly, uom, packaging, warning) |
| `_get_product_purchase_description()` | 547 | Returns product.display_name + description_purchase |
| `_prepare_account_move_line()` | 555 | Builds account.move.line vals for vendor bill |
| `_prepare_add_missing_fields()` | 574 | Deduces missing fields by simulating onchange |
| `_prepare_purchase_order_line()` | 588 | Factory method for PO line creation from product+supplier |
| `_get_select_sellers_params()` | 547 | Returns context for _select_seller call |

---

### product_id change effects (onchange equivalent)

In Odoo 17, there is no single `product_id_change`. Instead, `onchange_product_id()` (line 270) is the entry point:

```python
@api.onchange('product_id')
def onchange_product_id(self):
    # TODO: Remove when onchanges are replaced with computes
    if not self.product_id or (self.env.context.get('origin_po_id') and self.product_qty):
        return

    # Reset date, price and quantity since _onchange_quantity will provide default values
    self.price_unit = self.product_qty = 0.0

    self._product_id_change()
    self._suggest_quantity()
```

Which calls `_product_id_change()` (line 283):
```python
def _product_id_change(self):
    if not self.product_id:
        return
    self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
    product_lang = self.product_id.with_context(lang=get_lang(...))
    self.name = self._get_product_purchase_description(product_lang)
    self._compute_tax_id()
```

**Cascade of field updates on product change:**

| Field | Source | Effect |
|-------|--------|--------|
| `product_uom` | product.uom_po_id or product.uom_id | Purchase UoM from product |
| `name` | product.display_name + description_purchase | Translated description |
| `taxes_id` | product.supplier_taxes_id mapped via fiscal position | Vendor taxes |
| `product_qty` | `_suggest_quantity()` — seller's min_qty | Suggested from vendor |
| `price_unit` | `_compute_price_unit_and_date_planned_and_name()` — from seller or standard cost | Vendor price |
| `discount` | From seller.discount | Vendor discount |
| `date_planned` | From seller.delay + date_order | Delivery lead time |
| `product_packaging_id` | Suggested based on product_qty and company | Packaging suggestion |

---

### _prepare_account_move_line() — Invoice Line Values (Lines 555–572)

```python
def _prepare_account_move_line(self, move=False):
    self.ensure_one()
    aml_currency = move and move.currency_id or self.currency_id
    date = move and move.date or fields.Date.today()
    res = {
        'display_type': self.display_type or 'product',
        'name': '%s: %s' % (self.order_id.name, self.name),
        'product_id': self.product_id.id,
        'product_uom_id': self.product_uom.id,
        'quantity': self.qty_to_invoice,          # Uses qty_to_invoice, not product_qty
        'discount': self.discount,
        'price_unit': self.currency_id._convert(
            self.price_unit, aml_currency, self.company_id, date, round=False),
        'tax_ids': [(6, 0, self.taxes_id.ids)],
        'purchase_line_id': self.id,              # Back-link to POL
    }
    if self.analytic_distribution and not self.display_type:
        res['analytic_distribution'] = self.analytic_distribution
    return res
```

**Key differences from sale line:**
- `purchase_line_id` link back to POL (not `sale_line_ids` Many2many)
- No `is_downpayment` field — PO downpayment is a separate mechanism
- Price is currency-converted at invoice date (not invoice line date)

---

### qty_to_invoice computation (Lines 135–155)

```python
@api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity',
             'qty_received', 'product_uom_qty', 'order_id.state')
def _compute_qty_invoiced(self):
    for line in self:
        # compute qty_invoiced
        qty = 0.0
        for inv_line in line._get_invoice_lines():
            if inv_line.move_id.state not in ['cancel'] or inv_line.move_id.payment_state == 'invoicing_legacy':
                if inv_line.move_id.move_type == 'in_invoice':
                    qty += inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
                elif inv_line.move_id.move_type == 'in_refund':
                    qty -= inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
        line.qty_invoiced = qty

        # compute qty_to_invoice
        if line.order_id.state in ['purchase', 'done']:
            if line.product_id.purchase_method == 'purchase':
                line.qty_to_invoice = line.product_qty - line.qty_invoiced
            else:  # 'delivery' policy
                line.qty_to_invoice = line.qty_received - line.qty_invoiced
        else:
            line.qty_to_invoice = 0
```

**Invoice policy (product.purchase_method):**
- `'purchase'`: invoice based on ordered quantity (`product_qty`)
- `'delivery'`: invoice based on received quantity (`qty_received`)

---

### _compute_price_unit_and_date_planned_and_name() — The Core Price/Date Onchange (Lines 318–375)

This is the most complex method in `purchase_order_line.py`. It handles:

1. **Get seller info** (lines 322–328):
   ```python
   seller = line.product_id._select_seller(
       partner_id=line.partner_id,
       quantity=line.product_qty,
       date=line.order_id.date_order and line.order_id.date_order.date() or fields.Date.context_today(line),
       uom_id=line.product_uom,
       params=params)
   ```

2. **Set date_planned** (line 330):
   ```python
   if seller or not line.date_planned:
       line.date_planned = line._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
   ```

3. **Price from seller** (lines 358–363):
   ```python
   if seller:
       price_unit = line.env['account.tax']._fix_tax_included_price_company(
           seller.price, line.product_id.supplier_taxes_id, line.taxes_id, line.company_id)
       price_unit = seller.currency_id._convert(price_unit, line.currency_id, ...)
       price_unit = float_round(price_unit, ...)
       line.price_unit = seller.product_uom._compute_price(price_unit, line.product_uom)
       line.discount = seller.discount or 0.0
   ```

4. **Fallback: standard cost** (lines 334–356):
   - Uses `product.standard_price`
   - Converts via `_fix_tax_included_price_company`
   - Currency converts to PO currency
   - Skips if line already has a price and no seller found for this partner

5. **Name from seller** (lines 365–375):
   - Preserves custom names by checking if current name matches default names
   - If current name is a default name, updates it using the seller's language context

---

## Purchase → Picking → Bill Flow

```
[Vendors create Products with Supplier Info]
         ↓
[Create PO] — partner_id, order_line (product, qty, price)
         ↓
[button_confirm()] — state: draft → sent (or to approve)
         ↓
[button_approve()] — state: sent/to_approve → purchase
         ↓              date_approve = now
         ↓              _add_supplier_to_product()
         ↓
[Stock Receipt] — created by purchase_stock module (stock.picking type='incoming')
         ↓              qty_received updated on POLs
         ↓
[Register Bill] — action_create_invoice() via purchase module
         ↓              or manual from account
         ↓
[Vendor Bill Posted] — payment matching → PO invoice_status = 'invoiced'
```

**Key differences from Sale flow:**

| Aspect | Sale | Purchase |
|--------|------|----------|
| Picking creation | `sale_stock` module | `purchase_stock` module |
| Billing trigger | Manual via `_create_invoices()` | `action_create_invoice()` or manual |
| Invoice creation | Customer invoice (`out_invoice`) | Vendor bill (`in_invoice`) |
| Cancel invoice on cancel | Auto-cancels draft invoices | Raises error (must cancel manually) |
| Down payment | Supported via `is_downpayment` flag | Not supported in same way |
| Locking | `locked` field + `group_auto_done_setting` | `po_lock` setting on company (`lock` or `open`) |
| Confirmation | `action_confirm()` | `button_confirm()` + `button_approve()` |

---

## See Also

- [Modules/purchase_stock](purchase_stock.md) — Receipt picking creation on PO confirmation
- [Modules/account](account.md) — Vendor bill posting and payment
- [Modules/purchase_requisition](purchase_requisition.md) — Purchase tenders and competitive bidding
- [Modules/purchase_mrp](purchase_mrp.md) — Manufacturing component procurement
- [Modules/product](product.md) — Vendor supplier info and purchase UoM configuration
- [Modules/purchase_product_matrix](purchase_product_matrix.md) — Matrix/grid product entry for PO