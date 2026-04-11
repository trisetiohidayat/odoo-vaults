---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #purchase
  - #purchase-agreements
  - #blanket-orders
  - #rfq
---

# Purchase Agreements (`purchase_requisition`)

## Module Overview

**Technical Name:** `purchase_requisition`
**Category:** Supply Chain / Purchase
**Depends:** `purchase`
**License:** LGPL-3

The Purchase Agreements module (internally called `purchase.requisition`) enables procurement teams to manage two distinct sourcing strategies:

1. **Blanket Orders** -- fixed-price, fixed-quantity agreements with a single vendor, valid over a defined time window. The blanket order acts as a price/scope commitment; individual Purchase Orders are then created against it as needs arise.
2. **Purchase Templates** -- reusable product catalogs with target vendors but no firm quantity commitment; used to prefill RFQs quickly.

The module also ships a **Call for Tenders / Alternatives** feature (gated behind the `group_purchase_alternatives` group) that lets buyers create multiple competing RFQs for the same product list and compare them side-by-side.

### Odoo 18 to Odoo 19 Changes

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Alternative PO grouping | Used `purchase.group_id` (FK to `procurement.group`) | New `purchase.order.group` technical model replaces `procurement.group` |
| Sequence code | Single sequence `purchase.requisition` | Two separate sequences: `purchase.requisition.blanket.order` and `purchase.requisition.purchase.template` |
| `product.supplierinfo` link | Stored `purchase_requisition_id` directly | New `purchase_requisition_line_id` Many2one chain: `supplierinfo.purchase_requisition_line_id -> purchase.requisition.line` |
| Supplier info creation | Created in `action_confirm` only | Created on both `action_confirm` AND via `purchase.requisition.line.create()` for confirmed blanket orders |
| `requisition_type` field | Existed | Unchanged |
| Alternatives confirmation | Basic warning | Dedicated `purchase.requisition.alternative.warning` wizard with keep/cancel actions |
| `price_total_cc` | Not present | New computed field on `purchase.order.line` for cross-currency comparison of alternatives |
| `analytic.mixin` on line | Not inherited | `purchase.requisition.line` now inherits `analytic.mixin` |
| PO merge override | Not present | `_prepare_grouped_data` and `_merge_alternative_po` added to `purchase.order` |
| Custom frontend widgets | Not present | `many2many_alt_pos` widget and `purchase_order_line_compare` list renderer |

---

## Data Models

### Core Models

| Model | Purpose | Table |
|-------|---------|-------|
| `purchase.requisition` | Parent blanket order / purchase template | `purchase_requisition` |
| `purchase.requisition.line` | Product lines within an agreement | `purchase_requisition_line` |
| `purchase.order.group` | Technical model grouping alternative POs | `purchase_order_group` |

### Extension Models

| Model | Inherits | Purpose |
|-------|----------|---------|
| `purchase.order` | `purchase.order` | Links PO to an agreement; manages alternatives |
| `purchase.order.line` | `purchase.order.line` | Cross-currency price total; auto-fills from requisition |
| `product.supplierinfo` | `product.supplierinfo` | Tracks which supplier info came from which agreement line |
| `product.product` | `product.product` | Filters seller list by requisition |
| `res.config.settings` | `res.config.settings` | Exposes `group_purchase_alternatives` in settings |

### Transient / Wizard Models

| Model | Purpose |
|-------|---------|
| `purchase.requisition.alternative.warning` | Prompted when confirming a PO that still has open alternatives |
| `purchase.requisition.create.alternative` | Presets values for creating alternative RFQs |

---

## `purchase.requisition` -- Blanket Order / Purchase Template

File: `models/purchase_requisition.py`

### Class Declaration

```python
class PurchaseRequisition(models.Model):
    _name = 'purchase.requisition'
    _description = "Purchase Requisition"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"
```

Inherits `mail.thread` and `mail.activity.mixin` for full chatter and activity tracking. The `_order` of `id desc` makes the most recently created agreements appear first.

### Fields

#### `name` -- Agreement Reference

```python
name = fields.Char(
    string='Agreement', copy=False, readonly=True, required=True,
    default=lambda self: _('New'))
```

- **Copy:** `False` -- the name is never duplicated when copying a record.
- **Readonly:** `True` -- assigned by sequence on `create()`.
- **Default:** `'New'` until the sequence assigns the real value during `create()`.
- **Sequence:** Two separate sequences are used based on `requisition_type`:
  - `blanket_order` type uses `purchase.requisition.blanket.order` (prefix `BO`, e.g. `BO00005`)
  - `purchase_template` type uses `purchase.requisition.purchase.template` (prefix `PT`, e.g. `PT00003`)

#### `active` -- Archive Flag

```python
active = fields.Boolean('Active', default=True)
```

Standard active flag. Archived agreements are hidden by default but still accessible via the "Archived" filter.

#### `reference` -- External Reference

```python
reference = fields.Char(string='Reference')
```

Free-text field for the customer's purchase order number, project code, or any external identifier. Not validated; purely informational.

#### `order_count` -- Computed Purchase Order Count

```python
order_count = fields.Integer(
    compute='_compute_orders_number', string='Number of Orders')
```

Computed as `len(requisition.purchase_ids)`. Displayed in the stat button on the form header.

#### `vendor_id` -- Preferred Vendor

```python
vendor_id = fields.Many2one('res.partner', string='Vendor', check_company=True)
```

- **check_company=True:** Enforces company consistency on write.
- **Mandatory for:** `blanket_order` type (required in the form view when type is blanket order).
- **Readonly when:** state is `confirmed` or `done` AND type is `blanket_order` (locked after confirmation).
- **Onchange:** Triggers a warning if the vendor already has an open blanket order in `confirmed` state (`_onchange_vendor`).

#### `requisition_type` -- Agreement Type

```python
requisition_type = fields.Selection([
    ('blanket_order', 'Blanket Order'),
    ('purchase_template', 'Purchase Template')],
    string='Agreement Type', required=True, default='blanket_order')
```

The fundamental type selector. Controls:
- Which sequence code is used for naming.
- Whether validity dates are shown (only for `blanket_order`).
- Whether the status bar is shown in the form header.
- Whether vendor_id must be set.
- Whether the "Close" button appears.
- How PO lines are pre-filled when creating an RFQ (`_onchange_requisition_id`).

**Type differences:**

| Aspect | `blanket_order` | `purchase_template` |
|--------|----------------|---------------------|
| Vendor required | Yes | No |
| Validity dates shown | Yes | No |
| Status bar shown | Yes | No |
| Close button available | Yes | No |
| `qty_ordered` shown on lines | Yes | No |
| Price pre-computed from seller | No (manual) | Yes (auto via `_compute_price_unit`) |
| Supplier info created | Yes, on confirm | No |
| Purpose | Fixed price commitment | Quick RFQ prefilling |

#### `date_start` / `date_end` -- Agreement Validity Window

```python
date_start = fields.Date(string='Start Date', tracking=True)
date_end = fields.Date(string='End Date', tracking=True)
```

- **Tracking:** Enabled for both fields; state changes are logged in chatter.
- **Only shown for:** `blanket_order` type.
- **Constraint:** `_check_dates` ensures `date_end` is not earlier than `date_start`.
- **Effect on PO creation:** When creating a PO from a confirmed blanket order, `date_order` is set to `max(now, date_start)` to prevent backdated ordering.

#### `user_id` -- Purchase Representative

```python
user_id = fields.Many2one(
    'res.users', string='Purchase Representative',
    default=lambda self: self.env.user, check_company=True)
```

Defaults to the current user. Controls the "My Agreements" filter (searched by `uid`).

#### `description` -- Terms and Conditions

```python
description = fields.Html()
```

Free-form HTML field for terms, conditions, delivery instructions, or any other contractual notes. Rendered in the QWeb report.

#### `company_id` -- Company

```python
company_id = fields.Many2one(
    'res.company', string='Company', required=True,
    default=lambda self: self.env.company)
```

All agreements are company-scoped. A multi-company rule (`purchase_requisition_comp_rule`) restricts records to the user's allowed companies.

#### `purchase_ids` -- Linked Purchase Orders

```python
purchase_ids = fields.One2many(
    'purchase.order', 'requisition_id', string='Purchase Orders')
```

The inverse of `purchase.order.requisition_id`. All POs created from or linked to this agreement appear here. Used to compute `order_count`.

#### `line_ids` -- Agreement Product Lines

```python
line_ids = fields.One2many(
    'purchase.requisition.line', 'requisition_id',
    string='Products to Purchase', copy=True)
```

All product lines. `copy=True` means duplicating the agreement also duplicates its lines.

#### `product_id` -- Related Product (Computed/Related)

```python
product_id = fields.Many2one(
    'product.product', related='line_ids.product_id',
    string='Product')
```

A convenience related field pointing to the product from the first line (through the One2many). Useful for search/filters across agreements.

#### `state` -- Status

```python
state = fields.Selection(
    selection=[
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Closed'),
        ('cancel', 'Cancelled')
    ],
    string='Status', tracking=True, required=True,
    copy=False, default='draft')
```

State machine:

```
draft ──(action_confirm)──> confirmed ──(action_done)──> done
  │                                  │
  └──(action_cancel)──> cancel <──────┘
  │
  └──(action_draft)──────────────────────────────────> draft  [only from cancel]
```

- `draft`: Editable; no supplier info created.
- `confirmed`: Lines are locked from structural changes; supplier info exists; POs can be created against it.
- `done`: Closed; all supplier info records deleted; no further PO creation expected.
- `cancel`: Cancelled; can be reset to draft via `action_draft`.

#### `currency_id` -- Currency

```python
currency_id = fields.Many2one(
    'res.currency', 'Currency', required=True, precompute=True,
    compute='_compute_currency_id', store=True, readonly=False)
```

- **Default:** Falls back to `company_id.currency_id` if vendor has no preferred currency.
- **Vendor currency:** If `vendor_id.property_purchase_currency_id` is set, that currency is used instead.
- `readonly=False` allows manual override even after vendor is selected.
- `precompute=True` reduces database round-trips.

### Methods

#### `create(vals_list)` -- Sequence Assignment

```python
@api.model_create_multi
def create(self, vals_list):
    defaults = self.default_get(['requisition_type', 'company_id'])
    for vals in vals_list:
        requisition_type = vals.get('requisition_type', defaults['requisition_type'])
        company_id = vals.get('company_id', defaults['company_id'])
        if requisition_type == 'blanket_order':
            vals['name'] = self.env['ir.sequence'].with_company(company_id).next_by_code(
                'purchase.requisition.blanket.order')
        else:
            vals['name'] = self.env['ir.sequence'].with_company(company_id).next_by_code(
                'purchase.requisition.purchase.template')
    return super().create(vals_list)
```

The sequence is resolved at create time using `with_company()`. If `requisition_type` changes on a draft requisition, `write()` reassigns the name via the correct sequence.

#### `write(vals)` -- State-Aware Name Renaming

```python
def write(self, vals):
    requisitions_to_rename = self.env['purchase.requisition']
    if 'requisition_type' in vals or 'company_id' in vals:
        requisitions_to_rename = self.filtered(lambda r:
            r.requisition_type != vals.get('requisition_type', r.requisition_type) or
            r.company_id.id != vals.get('company_id', r.company_id.id))
    res = super().write(vals)
    for requisition in requisitions_to_rename:
        if requisition.state != 'draft':
            raise UserError(_("You cannot change the Agreement Type or Company of a not draft purchase agreement."))
        if requisition.requisition_type == 'purchase_template':
            requisition.date_start = requisition.date_end = False
        code = (requisition.requisition_type == 'blanket_order'
                and 'purchase.requisition.blanket.order'
                or 'purchase.requisition.purchase.template')
        requisition.name = self.env['ir.sequence'].with_company(requisition.company_id).next_by_code(code)
    return res
```

Key behaviors:
- Changing type or company on a non-draft agreement raises `UserError`.
- Changing to `purchase_template` clears validity dates (templates have no time window).
- The name is regenerated from the correct sequence after a type change.

#### `_check_dates()` -- Date Constraint

```python
@api.constrains('date_start', 'date_end')
def _check_dates(self):
    invalid_requsitions = self.filtered(lambda r: r.date_end and r.date_start and r.date_end < r.date_start)
    if invalid_requsitions:
        raise ValidationError(_(
            "End date cannot be earlier than start date. Please check dates for agreements: %s",
            ', '.join(invalid_requsitions.mapped('name'))))
```

Applied at validation time. Groups all invalid agreements into a single error message.

#### `_onchange_vendor()` -- Duplicate Blanket Order Warning

```python
@api.onchange('vendor_id')
def _onchange_vendor(self):
    requisitions = self.env['purchase.requisition'].search([
        ('vendor_id', '=', self.vendor_id.id),
        ('state', '=', 'confirmed'),
        ('requisition_type', '=', 'blanket_order'),
        ('company_id', '=', self.company_id.id),
    ])
    if any(requisitions):
        title = _("Warning for %s", self.vendor_id.name)
        message = _("There is already an open blanket order for this supplier. "
                    "We suggest you complete this open blanket order, instead of creating a new one.")
        return {'warning': {'title': title, 'message': message}}
```

Searches across all confirmed blanket orders for the same vendor/company. Does not filter out `self` (since the agreement is typically in draft when the vendor is first set). This is a soft warning -- the user can proceed regardless.

#### `action_confirm()` -- Confirm and Lock

```python
def action_confirm(self):
    self.ensure_one()
    if not self.line_ids:
        raise UserError(_("You cannot confirm agreement '%(agreement)s' because it does not contain any product lines.", agreement=self.name))
    if self.requisition_type == 'blanket_order':
        for requisition_line in self.line_ids:
            if requisition_line.price_unit <= 0.0:
                raise UserError(_('You cannot confirm a blanket order with lines missing a price.'))
            if requisition_line.product_qty <= 0.0:
                raise UserError(_('You cannot confirm a blanket order with lines missing a quantity.'))
            requisition_line._create_supplier_info()
    self.state = 'confirmed'
```

Validations enforced on blanket order confirmation:
1. At least one product line must exist.
2. Every line must have `price_unit > 0`.
3. Every line must have `product_qty > 0`.
4. Supplier info records are created for each line.

For `purchase_template`, no supplier info is created and no price/quantity validation occurs (prices are computed from seller data anyway).

#### `action_done()` -- Close Agreement

```python
def action_done(self):
    if any(purchase_order.state in ['draft', 'sent', 'to approve']
           for purchase_order in self.mapped('purchase_ids')):
        raise UserError(_("To close this purchase requisition, cancel related Requests for Quotation.\n\n"
            "Imagine the mess if someone confirms these duplicates: double the order, double the trouble :)"))
    for requisition in self:
        for requisition_line in requisition.line_ids:
            requisition_line.supplier_info_ids.sudo().unlink()
    self.write({'state': 'done'})
```

**Precondition:** All linked POs must be in a final state (`purchase` or `cancel`). On closure, all supplier info records are deleted (sudo). The `done` state is terminal -- there is no action to reopen.

**L4 Edge case:** If a blanket order was created, confirmed, lines added post-confirmation (triggering inline supplier info creation), and then the blanket order is closed -- all supplier_info records are wiped, including those created after confirmation. This is intentional: closing means the agreement is fully consumed or expired.

#### `action_cancel()` -- Cancel Agreement

```python
def action_cancel(self):
    for requisition in self:
        for requisition_line in requisition.line_ids:
            requisition_line.supplier_info_ids.sudo().unlink()
        requisition.purchase_ids.button_cancel()
        for po in requisition.purchase_ids:
            po.message_post(body=_('Cancelled by the agreement associated to this quotation.'))
    self.state = 'cancel'
```

- Supplier info deleted (sudo).
- All linked POs are cancelled via `button_cancel()`.
- Chatter message posted on each PO.
- State set to `cancel`.
- Can be reset to draft via `action_draft`.

#### `action_draft()` -- Reset to Draft

```python
def action_draft(self):
    self.ensure_one()
    self.state = 'draft'
```

Minimal method. Resets a cancelled agreement to draft. No re-validation runs. Supplier info is NOT recreated -- it was already deleted at cancel time.

#### `unlink()` -- Cascade to Lines

```python
def unlink(self):
    # Draft requisitions could have some requisition lines.
    self.line_ids.unlink()
    return super().unlink()
```

Lines are explicitly deleted before the parent record. This bypasses Odoo's default `ondelete='cascade'` behavior to guarantee ordering: lines deleted first, then the parent. For non-draft lines, `purchase.requisition.line.unlink()` will have already deleted the supplier_info records.

#### `_unlink_if_draft_or_cancel()` -- Deletion Guard

```python
@api.ondelete(at_uninstall=False)
def _unlink_if_draft_or_cancel(self):
    if any(requisition.state not in ('draft', 'cancel') for requisition in self):
        raise UserError(_('You can only delete draft or cancelled requisitions.'))
```

Preventive hook that blocks deletion of active agreements. **`@api.ondelete(at_uninstall=False)`** means it is skipped during module uninstall, allowing the ORM to cleanly remove records when the module is removed.

---

## `purchase.requisition.line` -- Agreement Product Line

File: `models/purchase_requisition.py`

### Class Declaration

```python
class PurchaseRequisitionLine(models.Model):
    _name = 'purchase.requisition.line'
    _inherit = ['analytic.mixin']
    _description = "Purchase Requisition Line"
    _rec_name = 'product_id'
```

`analytic.mixin` provides the `analytic_distribution` field, allowing each line to carry analytic accounts for PO line forwarding. `_rec_name = 'product_id'` means the product's name is used when displaying the line in a list context.

### Fields

#### `product_id` -- Product

```python
product_id = fields.Many2one(
    'product.product', string='Product',
    domain=[('purchase_ok', '=', True)], required=True)
```

Filtered to only `purchase_ok=True` products. This domain is also enforced in the form view XML.

#### `product_uom_id` -- Unit of Measure

```python
product_uom_id = fields.Many2one(
    'uom.uom', 'Unit',
    compute='_compute_product_uom_id', store=True, readonly=False, precompute=True)
```

Computed from `product_id.uom_id` whenever the product changes. `store=True, readonly=False` means it can be manually overridden after auto-fill, and the manual value is persisted. `precompute=True` avoids a read-before-write on create.

#### `product_qty` -- Target Quantity

```python
product_qty = fields.Float(string='Quantity', digits='Product Unit')
```

The agreed maximum quantity for a blanket order. For `purchase_template`, this field is informational or zero (prices are still needed but quantities are not committed).

#### `product_description_variants` -- Variant Description

```python
product_description_variants = fields.Char('Description')
```

Stores variant-specific notes (e.g., color, size, grade) appended to the product name when generating PO lines. Displayed as a separate column in the line list (hidden when blank in the form view).

#### `price_unit` -- Agreed Unit Price

```python
price_unit = fields.Float(
    string='Unit Price', min_display_digits='Product Price', default=0.0,
    compute="_compute_price_unit", readonly=False, store=True)
```

For blanket orders: manually entered. For purchase templates: computed from the vendor's seller data. `readonly=False` on a computed field means it can be manually overridden after auto-fill, and the manual value is then stored (standard Odoo computed field override pattern).

#### `qty_ordered` -- Total Ordered Against Line

```python
qty_ordered = fields.Float(compute='_compute_ordered_qty', string='Ordered')
```

Sums the `product_qty` from all confirmed Purchase Order lines (state `purchase`) that reference the same product, converted to the line's UoM.

#### `requisition_id` -- Parent Agreement

```python
requisition_id = fields.Many2one(
    'purchase.requisition', required=True,
    string='Purchase Agreement', ondelete='cascade', index=True)
```

Cascade delete: deleting the agreement cascades to all its lines (though `purchase.requisition.unlink()` also explicitly unlinks lines first, making this redundant but safe).

#### `company_id` -- Company (Stored Related)

```python
company_id = fields.Many2one(
    'res.company', related='requisition_id.company_id',
    string='Company', store=True, readonly=True)
```

Stored for efficient filtering; tracks through `requisition_id.company_id`.

#### `supplier_info_ids` -- Linked Supplier Info Records

```python
supplier_info_ids = fields.One2many(
    'product.supplierinfo', 'purchase_requisition_line_id')
```

Created when a blanket order is confirmed. Each record links the vendor's price list entry back to this line. When a line is deleted from a non-draft agreement, the corresponding supplier info is also deleted.

### Methods

#### `_compute_ordered_qty()` -- Aggregate Ordered Quantities

```python
@api.depends('requisition_id.purchase_ids.state')
def _compute_ordered_qty(self):
    line_found = defaultdict(set)
    for line in self:
        total = 0.0
        for po in line.requisition_id.purchase_ids.filtered(
                lambda purchase_order: purchase_order.state == 'purchase'):
            for po_line in po.order_line.filtered(
                    lambda order_line: order_line.product_id == line.product_id):
                if po_line.product_uom_id != line.product_uom_id:
                    total += po_line.product_uom_id._compute_quantity(
                        po_line.product_qty, line.product_uom_id)
                else:
                    total += po_line.product_qty
        if line.product_id not in line_found[line.requisition_id]:
            line.qty_ordered = total
            line_found[line.requisition_id].add(line.product_id)
        else:
            line.qty_ordered = 0  # Avoid double-counting same product on same agreement
```

**Important behaviors:**
- Only POs in `purchase` state count (not draft, not done/cancel).
- UoM conversion is applied if PO line UoM differs from agreement line UoM.
- Uses `defaultdict(set)` to detect and zero out duplicate products on the same agreement (the first occurrence gets the full total; subsequent same-product lines on the same agreement get 0).

**L4 Edge case:** The `defaultdict(set)` logic means that if you add the same product twice to a single blanket order, the second line's `qty_ordered` will always show `0`, even after POs are confirmed. This is an intentional design to avoid confusion on over-ordering. The total ordered quantity across both lines is still correct; only the per-line display is zeroed for duplicates.

#### `_compute_price_unit()` -- Template Price Auto-Fill

```python
@api.depends('product_id', 'company_id', 'requisition_id.date_start',
             'product_qty', 'product_uom_id', 'requisition_id.vendor_id',
             'requisition_id.requisition_type')
def _compute_price_unit(self):
    for line in self:
        if (line.requisition_id.state != 'draft'
                or line.requisition_id.requisition_type != 'purchase_template'
                or not line.requisition_id.vendor_id
                or not line.product_id):
            continue
        seller = line.product_id._select_seller(
            partner_id=line.requisition_id.vendor_id,
            quantity=line.product_qty,
            date=line.requisition_id.date_start,
            uom_id=line.product_uom_id)
        line.price_unit = seller.price if seller else line.product_id.standard_price
```

Only fires for `purchase_template` agreements in `draft` state. Uses `_select_seller` with the quantity and validity date to pick the correct price tier. Falls back to the product's `standard_price` if no seller record exists for the vendor.

**L4 Edge case:** If a purchase template is confirmed (state moves from draft), `_compute_price_unit` stops updating -- prices become locked. To change prices after confirmation, you must reset to draft.

#### `create(vals_list)` -- Supplier Info for Confirmed Blanket Orders

```python
@api.model_create_multi
def create(self, vals_list):
    lines = super().create(vals_list)
    for line, vals in zip(lines, vals_list):
        if (line.requisition_id.requisition_type == 'blanket_order'
                and line.requisition_id.state not in ['draft', 'cancel', 'done']):
            # Confirmed blanket order: validate price, create supplier info if needed
            if vals['price_unit'] <= 0.0:
                raise UserError(_("You cannot have a negative or unit price of 0 "
                                  "for an already confirmed blanket order."))
            supplier_infos = self.env['product.supplierinfo'].search([
                ('product_id', '=', vals.get('product_id')),
                ('partner_id', '=', line.requisition_id.vendor_id.id),
            ])
            if not any(s.purchase_requisition_id for s in supplier_infos):
                line._create_supplier_info()
    return lines
```

**Key behavior:** Supplier info creation is not only in `action_confirm` but also in `create()` for lines added to already-confirmed blanket orders. It checks whether a supplier info already links to a requisition before creating a duplicate. The `vals['price_unit']` check is against the input data (pre-computed fill), not `line.price_unit` (which may be 0 if the product was changed after creation).

#### `write(vals)` -- Supplier Info Sync

```python
def write(self, vals):
    res = super().write(vals)
    if 'price_unit' not in vals:
        return res
    # Validate price on confirmed blanket orders
    if vals['price_unit'] <= 0.0 and any(
            requisition.requisition_type == 'blanket_order' and
            requisition.state not in ['draft', 'cancel', 'done']
            for requisition in self.mapped('requisition_id')):
        raise UserError(_("You cannot have a negative or unit price of 0 "
                          "for an already confirmed blanket order."))
    # Sync price to supplier info
    self.supplier_info_ids.write({'price': vals['price_unit']})
    return res
```

When the price is updated on a confirmed blanket order line, the linked supplier info price is updated in lockstep. Note: `self.supplier_info_ids` may contain multiple records if the same product/vendor was added multiple times.

#### `unlink()` -- Supplier Info Cleanup

```python
def unlink(self):
    to_unlink = self.filtered(lambda r: r.requisition_id.state not in ['draft', 'cancel', 'done'])
    to_unlink.supplier_info_ids.unlink()
    return super().unlink()
```

For lines on confirmed blanket orders, supplier info records are deleted before the line is removed. For draft/cancelled lines, supplier info records do not exist, so this is a no-op. This is **not** called sudo() here -- it runs with the user's access rights (typically the purchase manager who can manage blanket orders).

**L4 Security consideration:** The `unlink()` without `sudo()` here means that a user who can delete a line from a confirmed blanket order must also have write access to the related `product.supplierinfo` records. This is typically a purchase manager. In contrast, `_create_supplier_info()` uses `sudo()` because line creation often happens by a buyer who may not have direct supplierinfo write access.

#### `_create_supplier_info()` -- Create Vendor Price List Entry

```python
def _create_supplier_info(self):
    self.ensure_one()
    purchase_requisition = self.requisition_id
    if purchase_requisition.requisition_type == 'blanket_order' and purchase_requisition.vendor_id:
        self.env['product.supplierinfo'].sudo().create({
            'partner_id': purchase_requisition.vendor_id.id,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom_id.id,
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'price': self.price_unit,
            'currency_id': self.requisition_id.currency_id.id,
            'purchase_requisition_line_id': self.id,
        })
```

Creates a vendor price list entry (`product.supplierinfo`) with:
- `purchase_requisition_line_id` linking back to this line (Odoo 19 addition, replacing the old direct `purchase_requisition_id` field).
- The agreed price and currency.
- The product template and UoM.

`sudo()` is used because regular users may not have write access to supplier info, but creating a price record as part of confirming a blanket order should always succeed.

#### `_prepare_purchase_order_line()` -- Generate PO Line Values

```python
def _prepare_purchase_order_line(self, name, product_qty=0.0, price_unit=0.0, taxes_ids=False):
    self.ensure_one()
    if self.product_description_variants:
        name += '\n' + self.product_description_variants
    date_planned = fields.Datetime.now()
    if self.requisition_id.date_start:
        date_planned = max(date_planned, fields.Datetime.to_datetime(
            self.requisition_id.date_start))
    return {
        'name': name,
        'product_id': self.product_id.id,
        'product_uom_id': self.product_uom_id.id,
        'product_qty': product_qty,
        'price_unit': price_unit,
        'tax_ids': [(6, 0, taxes_ids)],
        'date_planned': date_planned,
        'analytic_distribution': self.analytic_distribution,
    }
```

Called from `purchase.order._onchange_requisition_id()`. Handles:
- Appending variant description to product name.
- Setting `date_planned` to `max(now, date_start)` to prevent backdating.
- Carrying forward analytic distribution from the agreement line.

---

## `purchase.order` -- Extended with Agreement and Alternatives

File: `models/purchase.py`

### New Fields on `purchase.order`

#### `requisition_id` -- Linked Agreement

```python
requisition_id = fields.Many2one(
    'purchase.requisition', string='Agreement',
    copy=False, index='btree_not_null')
```

- `copy=False`: Creating a duplicate PO does not carry the agreement link.
- `index='btree_not_null'`: Creates a partial index (only on non-null values) for efficient filtering.

#### `requisition_type` -- Agreement Type (Related)

```python
requisition_type = fields.Selection(related='requisition_id.requisition_type')
```

Mirrors the parent agreement's type for use in domain filters and view conditions without traversing the relation.

#### `purchase_group_id` -- Alternatives Group

```python
purchase_group_id = fields.Many2one(
    'purchase.order.group', index='btree_not_null')
```

The `purchase.order.group` that groups this PO with its alternatives. The `purchase.order.group` model replaces the deprecated `procurement.group` used in Odoo 18.

#### `alternative_po_ids` -- Alternative POs (Related One2many)

```python
alternative_po_ids = fields.One2many(
    'purchase.order', related='purchase_group_id.order_ids',
    readonly=False,
    domain="[('id', '!=', id), ('state', 'in', ['draft', 'sent', 'to approve'])]",
    string="Alternative POs", check_company=True)
```

All POs in the same group except `self`. The domain limits visible alternatives to RFQs that are still open (not confirmed, cancelled, or done). The `readonly=False` is an ORM quirk -- it allows setting `alternative_po_ids` via `write()` even though it is technically a related field.

### Methods

#### `_onchange_requisition_id()` -- Auto-Fill from Agreement

```python
@api.onchange('requisition_id')
def _onchange_requisition_id(self):
    if not self.requisition_id:
        return
    self = self.with_company(self.company_id)
    requisition = self.requisition_id
    if self.partner_id:
        partner = self.partner_id
    else:
        partner = requisition.vendor_id
    payment_term = partner.property_supplier_payment_term_id

    FiscalPosition = self.env['account.fiscal.position']
    fpos = FiscalPosition.with_company(self.company_id)._get_fiscal_position(partner)

    self.partner_id = partner.id
    self.fiscal_position_id = fpos.id
    self.payment_term_id = payment_term.id
    self.company_id = requisition.company_id.id
    self.currency_id = requisition.currency_id.id
    if not self.origin or requisition.name not in self.origin.split(', '):
        if self.origin:
            if requisition.name:
                self.origin = self.origin + ', ' + requisition.name
        else:
            self.origin = requisition.name
    self.note = requisition.description
    if requisition.date_start:
        self.date_order = max(fields.Datetime.now(),
                               fields.Datetime.to_datetime(requisition.date_start))
    else:
        self.date_order = fields.Datetime.now()

    # Create PO lines if necessary
    if self.state != 'draft':
        return
    order_lines = []
    for line in requisition.line_ids:
        product_lang = line.product_id.with_context(
            lang=partner.lang or self.env.user.lang,
            partner_id=partner.id
        )
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        taxes_ids = fpos.map_tax(
            line.product_id.supplier_taxes_id.filtered(
                lambda tax: tax.company_id in requisition.company_id.parent_ids)
        ).ids

        product_qty = (line.product_qty
                       if requisition.requisition_type == 'purchase_template'
                       else 0)
        order_line_values = line._prepare_purchase_order_line(
            name=name, product_qty=product_qty,
            price_unit=line.price_unit, taxes_ids=taxes_ids)
        order_lines.append((0, 0, order_line_values))
    self.order_line = order_lines
```

**Key behaviors:**
- If `partner_id` is already set, it is preserved; otherwise falls back to `requisition.vendor_id`.
- Origin field is appended (not overwritten) with the agreement name, using a split-on-`, ` guard to avoid duplicate entries.
- For `blanket_order`: product quantities are set to 0 (blanket order is a price reference, not a quantity commitment).
- For `purchase_template`: product quantities are copied from the template lines.
- The `state != 'draft'` guard prevents clobbering lines on confirmed POs.
- Company check (`with_company`) ensures fiscal position resolution uses the correct fiscal country.

#### `button_confirm()` -- Alternatives Warning Interception

```python
def button_confirm(self):
    if self.alternative_po_ids and not self.env.context.get('skip_alternative_check', False):
        alternative_po_ids = self.alternative_po_ids.filtered(
            lambda po: po.state in ['draft', 'sent', 'to approve'] and po.id not in self.ids)
        if alternative_po_ids:
            view = self.env.ref(
                'purchase_requisition.purchase_requisition_alternative_warning_form')
            return {
                'name': _("What about the alternative Requests for Quotations?"),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'purchase.requisition.alternative.warning',
                'views': [(view.id, 'form')],
                'target': 'new',
                'context': dict(self.env.context,
                    default_alternative_po_ids=alternative_po_ids.ids,
                    default_po_ids=self.ids),
            }
    res = super(PurchaseOrder, self).button_confirm()
    return res
```

Before confirming, if the PO has open alternative RFQs, a wizard is shown. The `skip_alternative_check` context key bypasses this when called from the wizard's `_action_done`.

#### `create(vals_list)` -- Group Linking and Chatter

```python
@api.model_create_multi
def create(self, vals_list):
    orders = super().create(vals_list)
    if self.env.context.get('origin_po_id'):
        origin_po_id = self.env['purchase.order'].browse(
            self.env.context.get('origin_po_id'))
        if origin_po_id.purchase_group_id:
            origin_po_id.purchase_group_id.order_ids |= orders
        else:
            self.env['purchase.order.group'].create({
                'order_ids': [Command.set(origin_po_id.ids + orders.ids)]})
    for order in orders:
        if order.requisition_id:
            order.message_post_with_source(
                'mail.message_origin_link',
                render_values={'self': order, 'origin': order.requisition_id},
                subtype_xmlid='mail.mt_note',
            )
    return orders
```

- When a PO is created as an alternative to another (via `origin_po_id` context, set by the create-alternative wizard), it is added to the existing `purchase.order.group` or a new group is created.
- A chatter message is posted linking the PO back to its agreement.
- The `origin_po_id` context is also used to set `default_requisition_id=False` in the wizard to prevent carrying the agreement link to the alternative POs.

#### `write(vals)` -- Group Management Lifecycle

```python
def write(self, vals):
    if vals.get('purchase_group_id', False):
        orig_purchase_group = self.purchase_group_id
    result = super(PurchaseOrder, self).write(vals)
    if vals.get('requisition_id'):
        for order in self:
            order.message_post_with_source(
                'mail.message_origin_link',
                render_values={'self': order, 'origin': order.requisition_id, 'edit': True},
                subtype_xmlid='mail.mt_note',
            )
    if vals.get('alternative_po_ids', False):
        if not self.purchase_group_id and len(self.alternative_po_ids + self) > len(self):
            self.env['purchase.order.group'].create({
                'order_ids': [Command.set(self.ids + self.alternative_po_ids.ids)]})
        elif self.purchase_group_id and len(self.alternative_po_ids + self) <= 1:
            self.purchase_group_id.unlink()
    if vals.get('purchase_group_id', False):
        additional_groups = orig_purchase_group - self.purchase_group_id
        if additional_groups:
            additional_pos = (additional_groups.order_ids
                            - self.purchase_group_id.order_ids)
            additional_groups.unlink()
            if additional_pos:
                self.purchase_group_id.order_ids |= additional_pos
    return result
```

Handles the complex group lifecycle:
1. Assigning `alternative_po_ids` creates or joins a group.
2. Clearing alternatives (making the PO the sole member) triggers group self-deletion via `purchase.order.group.write`.
3. Moving a PO to a different group merges orphaned POs from the old group into the new one.

#### `_prepare_grouped_data()` -- Include Requisition in PO Merge Key

```python
def _prepare_grouped_data(self, rfq):
    match_fields = super()._prepare_grouped_data(rfq)
    return match_fields + (rfq.requisition_id.id,)
```

Overrides the core purchase merge logic (from `purchase` module) to include `requisition_id.id` in the grouping key. This ensures that RFQs linked to different blanket orders are **never merged together** -- the blanket order commitment must be tracked per agreement.

#### `_merge_alternative_po()` -- Absorb Alternatives Into Self on Merge

```python
def _merge_alternative_po(self, rfqs):
    if self.alternative_po_ids:
        super()._merge_alternative_po(rfqs)
        self.alternative_po_ids += rfqs.mapped('alternative_po_ids')
```

When an RFQ with alternatives is merged into another PO (via the PO merge action), the alternatives of the absorbed POs are also transferred to `self`. This ensures that no alternatives are lost during the merge operation.

#### `action_create_alternative()` -- Wizard Launcher

```python
def action_create_alternative(self):
    ctx = dict(**self.env.context, default_origin_po_id=self.id)
    return {
        'name': _('Create alternative'),
        'type': 'ir.actions.act_window',
        'view_mode': 'form',
        'res_model': 'purchase.requisition.create.alternative',
        'view_id': self.env.ref(
            'purchase_requisition.purchase_requisition_create_alternative_form').id,
        'target': 'new',
        'context': ctx,
    }
```

Opens the create-alternative wizard pre-seeded with the current PO as `origin_po_id`. Note: this button is shown only when `group_purchase_alternatives` is active.

#### `action_compare_alternative_lines()` -- Line Comparison View

```python
def action_compare_alternative_lines(self):
    ctx = dict(
        self.env.context,
        search_default_groupby_product=True,
        purchase_order_id=self.id,
    )
    view_id = self.env.ref(
        'purchase_requisition.purchase_order_line_compare_tree').id
    return {
        'name': _('Compare Order Lines'),
        'type': 'ir.actions.act_window',
        'view_mode': 'list',
        'res_model': 'purchase.order.line',
        'views': [(view_id, "list")],
        'domain': [('order_id', 'in', (self | self.alternative_po_ids).ids),
                   ('display_type', '=', False)],
        'context': ctx,
    }
```

Opens a flat list view of all lines across the current PO and its alternatives, grouped by product. The `purchase_order_line_compare` JS widget highlights the best price, best date, and best unit price lines in green.

#### `get_tender_best_lines()` -- Tendering Comparison Logic

```python
def get_tender_best_lines(self):
    product_to_best_price_line = defaultdict(
        lambda: self.env['purchase.order.line'])
    product_to_best_date_line = defaultdict(
        lambda: self.env['purchase.order.line'])
    product_to_best_price_unit = defaultdict(
        lambda: self.env['purchase.order.line'])
    po_alternatives = self | self.alternative_po_ids

    for line in po_alternatives.order_line:
        if (not line.product_qty or not line.price_total_cc
                or line.state in ['cancel', 'purchase']):
            continue

        if not product_to_best_price_line[line.product_id]:
            product_to_best_price_line[line.product_id] = line
            product_to_best_price_unit[line.product_id] = line
        else:
            price_subtotal = line.price_total_cc
            price_unit = line.price_total_cc / line.product_qty
            current = product_to_best_price_line[line.product_id][0]
            current_price_subtotal = current.price_total_cc
            current_price_unit = (current.price_total_cc
                                  / current.product_qty)

            if current_price_subtotal > price_subtotal:
                product_to_best_price_line[line.product_id] = line
            elif current_price_subtotal == price_subtotal:
                product_to_best_price_line[line.product_id] |= line
            if current_price_unit > price_unit:
                product_to_best_price_unit[line.product_id] = line
            elif current_price_unit == price_unit:
                product_to_best_price_unit[line.product_id] |= line

        if not product_to_best_date_line[line.product_id] \
                or (product_to_best_date_line[line.product_id][0].date_planned
                    > line.date_planned):
            product_to_best_date_line[line.product_id] = line
        elif product_to_best_date_line[line.product_id][0].date_planned \
                == line.date_planned:
            product_to_best_date_line[line.product_id] |= line

    best_price_ids = set()
    best_date_ids = set()
    best_price_unit_ids = set()
    for lines in product_to_best_price_line.values():
        best_price_ids.update(lines.ids)
    for lines in product_to_best_date_line.values():
        best_date_ids.update(lines.ids)
    for lines in product_to_best_price_unit.values():
        best_price_unit_ids.update(lines.ids)
    return list(best_price_ids), list(best_date_ids), list(best_price_unit_ids)
```

Returns three lists of line IDs:
1. **Best total** (lowest `price_total_cc`): the line(s) with the cheapest total cost per product.
2. **Best date** (earliest `date_planned`): the line(s) with the fastest delivery per product.
3. **Best unit price** (lowest unit price): the line(s) with the lowest per-unit price per product.

Ties are stored as recordset unions (multiple vendors can be equally best). Called by the frontend `purchase_order_line_compare_list_renderer.js` on view load and after any button click.

---

## `purchase.order.line` -- Extended with Cross-Currency Comparison

File: `models/purchase.py`

### New Fields

#### `price_total_cc` -- Company Currency Subtotal

```python
price_total_cc = fields.Monetary(
    compute='_compute_price_total_cc',
    string="Company Subtotal",
    currency_field="company_currency_id", store=True)
company_currency_id = fields.Many2one(
    related="company_id.currency_id", string="Company Currency")
```

Converts each line's subtotal from the PO's currency to the company's currency using the PO's `currency_rate`. Essential for fair side-by-side comparison of alternative POs in different currencies.

#### `_compute_price_total_cc()`

```python
@api.depends('price_subtotal', 'order_id.currency_rate')
def _compute_price_total_cc(self):
    for line in self:
        line.price_total_cc = line.price_subtotal / line.order_id.currency_rate
```

**L4 Edge case / division-by-zero:** If `order_id.currency_rate` is `0` (which can happen if the rate is not set on a PO), this will raise a `ZeroDivisionError`. The `currency_rate` field in Odoo 19 is typically pre-filled from the company's currency conversion rates, but for exotic currencies or newly created currencies it might be absent. This is a known Odoo 19 risk.

### `_compute_price_unit_and_date_planned_and_name()` -- Requisition-Aware Auto-Fill

```python
def _compute_price_unit_and_date_planned_and_name(self):
    po_lines_without_requisition = self.env['purchase.order.line']
    for pol in self:
        if pol.product_id.id not in pol.order_id.requisition_id.line_ids.product_id.ids:
            po_lines_without_requisition |= pol
            continue

        line = None
        # Exact UoM match first, then product-only fallback
        for req_line in pol.order_id.requisition_id.line_ids:
            if req_line.product_id == pol.product_id:
                line = req_line
                if req_line.product_uom_id == pol.product_uom_id:
                    break

        pol.price_unit = line.product_uom_id._compute_price(
            line.price_unit, pol.product_uom_id)
        partner = pol.order_id.partner_id or pol.order_id.requisition_id.vendor_id
        params = {'order_id': pol.order_id}
        seller = pol.product_id._select_seller(
            partner_id=partner, quantity=pol.product_qty,
            date=pol.order_id.date_order
                and pol.order_id.date_order.date(),
            uom_id=line.product_uom_id, params=params)
        if not pol.date_planned:
            pol.date_planned = pol._get_date_planned(seller).strftime(
                DEFAULT_SERVER_DATETIME_FORMAT)
        product_ctx = {'seller_id': seller.id,
                       'lang': get_lang(pol.env, partner.lang).code}
        name = pol._get_product_purchase_description(
            pol.product_id.with_context(product_ctx))
        if line.product_description_variants:
            name += '\n' + line.product_description_variants
        pol.name = name
    super(PurchaseOrderLine, po_lines_without_requisition)._compute_price_unit_and_date_planned_and_name()
```

Key behaviors:
- Lines whose product is not in the agreement are skipped and handled by the parent class.
- Matching is first by product + exact UoM; falls back to product-only (non-UoM-specific match).
- Unit price is converted from the agreement line's UoM to the PO line's UoM.
- Seller selection is filtered to only the requisition's vendor via `_prepare_sellers` override on `product.product`.
- Variant descriptions are appended to the product description.
- `seller_id` is injected into context so `_get_product_purchase_description` renders the vendor's product name/code.

### `action_clear_quantities()` -- Reset Line Quantities

```python
def action_clear_quantities(self):
    zeroed_lines = self.filtered(lambda l: l.state not in ['cancel', 'purchase'])
    zeroed_lines.write({'product_qty': 0})
    if len(self) > len(zeroed_lines):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Some not cleared"),
                'message': _("Some quantities were not cleared because "
                             "their status is not a RFQ status."),
                'sticky': False,
            }
        }
    return False
```

Used in the line comparison view to reset selected lines. Only operates on RFQ-state lines. Returns a notification if some lines were skipped.

### `action_choose()` -- Keep This Line, Clear Others

```python
def action_choose(self):
    order_lines = (self.order_id | self.order_id.alternative_po_ids).mapped(
        'order_line')
    order_lines = order_lines.filtered(
        lambda l: l.product_qty and l.product_id.id in self.product_id.ids
        and l.id not in self.ids)
    if order_lines:
        return order_lines.action_clear_quantities()
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': _("Nothing to clear"),
            'message': _("There are no quantities to clear."),
            'sticky': False,
        }
    }
```

When a buyer selects a specific line as the preferred choice, this clears quantities for the same product on all other alternative POs, effectively "awarding" that product to the chosen vendor. This is a pure client-side quantity adjustment; it does not trigger PO confirmation.

---

## `purchase.order.group` -- Alternatives Grouping Model

File: `models/purchase.py`

```python
class PurchaseOrderGroup(models.Model):
    _name = 'purchase.order.group'
    _description = "Technical model to group PO for call to tenders"

    order_ids = fields.One2many('purchase.order', 'purchase_group_id')

    def write(self, vals):
        res = super().write(vals)
        # When len(POs) == 1, only linking PO to itself at this point
        # => self implode (delete) group
        self.filtered(lambda g: len(g.order_ids) <= 1).unlink()
        return res
```

A lightweight container model. When a write operation leaves a group with only one PO (or zero POs), the group self-destructs via `unlink()`. This avoids orphaned groups and keeps the `purchase.order.group` table lean.

**L4 Lifecycle:**
1. PO created as alternative: `create()` checks if origin PO has a group. If yes, new POs are added via `|=`. If no, a new group is created with `Command.set(origin + new)`.
2. Alternative removed: `write()` detects `len <= 1`, calls `unlink()`.
3. Group reassigned: `purchase.order.write()` merges orphaned POs from the old group into the new group.
4. Self-destruct: `PurchaseOrderGroup.write()` is called by the ORM after any write; if the group now has 0 or 1 orders, it is deleted.

---

## `product.supplierinfo` Extension

File: `models/product.py`

```python
class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    purchase_requisition_id = fields.Many2one(
        'purchase.requisition',
        related='purchase_requisition_line_id.requisition_id',
        string='Agreement')
    purchase_requisition_line_id = fields.Many2one(
        'purchase.requisition.line',
        index='btree_not_null')
```

The two-field chain enables:
- Tracing any supplier price entry back to its source agreement and line.
- Filtering the seller list on `product.product` by agreement.
- Displaying the agreement on the supplier info tree/form views (via XML extensions).

`purchase_requisition_id` is a **related** field (not stored), computing the parent agreement through the line. `purchase_requisition_line_id` is the **manually stored** inverse link that makes the chain possible.

---

## `product.product` Extension

File: `models/product.py`

```python
class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _prepare_sellers(self, params=False):
        sellers = super()._prepare_sellers(params=params)
        if (params and params.get('order_id')
                and params['order_id']._fields.get('requisition_id')):
            return sellers.filtered(
                lambda s: (not s.purchase_requisition_id
                          or s.purchase_requisition_id
                          == params['order_id'].requisition_id))
        return sellers
```

When `product.product._select_seller` is called with an `order_id` that has a `requisition_id`, this override filters the seller list to only those whose `purchase_requisition_id` either:
- Is not set (general seller), OR
- Matches the PO's `requisition_id` (seller tied to this specific blanket order)

This ensures that when creating a PO from a blanket order, only the pre-negotiated vendor's seller data is used, not other vendors' prices.

**L4 Edge case:** If a blanket order is cancelled (supplier info deleted) but the PO created from it still exists, `_prepare_sellers` will no longer find the blanket-order-specific seller. The PO line prices already filled from the agreement remain unchanged, but if the buyer runs the "Fill with vendor" action, they will get the wrong seller. This is an architectural limitation.

---

## `res.config.settings` Extension

File: `models/res_config_settings.py`

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_purchase_alternatives = fields.Boolean(
        "Purchase Alternatives",
        implied_group='purchase_requisition.group_purchase_alternatives')
```

Exposes the `group_purchase_alternatives` toggle in the Purchase settings page. Uses `implied_group` so that enabling it adds the group to the current user automatically. This group controls visibility of:
- The "Alternatives" tab on `purchase.order` form
- The "Create Alternative" button
- The "Compare Product Lines" button

---

## Wizards

### `purchase.requisition.alternative.warning`

File: `wizard/purchase_requisition_alternative_warning.py`

Triggered when confirming a PO that still has open alternatives. Presents the user with two actions.

#### Fields

```python
po_ids = fields.Many2many(
    'purchase.order', 'warning_purchase_order_rel',
    string="POs to Confirm")
alternative_po_ids = fields.Many2many(
    'purchase.order', 'warning_purchase_order_alternative_rel',
    string="Alternative POs")
```

Two separate many2many relation tables (`warning_purchase_order_rel` and `warning_purchase_order_alternative_rel`) are used for clarity, though in practice `po_ids` typically contains only one PO.

#### `action_keep_alternatives()` -- Keep Alternatives

```python
def action_keep_alternatives(self):
    return self._action_done()
```

Confirms the current PO while leaving alternatives open.

#### `action_cancel_alternatives()` -- Cancel Alternatives

```python
def action_cancel_alternatives(self):
    self.alternative_po_ids.filtered(
        lambda po: po.state in ['draft', 'sent', 'to approve']
        and po.id not in self.po_ids.ids).button_cancel()
    return self._action_done()
```

Cancels all open alternatives first, then confirms the current PO. The `po.id not in self.po_ids.ids` guard prevents accidentally cancelling the PO being confirmed (theoretically impossible via the domain but safe against data corruption).

#### `_action_done()` -- Proceed with Confirmation

```python
def _action_done(self):
    return self.po_ids.with_context({'skip_alternative_check': True}).button_confirm()
```

Calls `button_confirm` with `skip_alternative_check=True` to bypass the wizard on recursive calls.

---

### `purchase.requisition.create.alternative`

File: `wizard/purchase_requisition_create_alternative.py`

Presets and creates one or more alternative POs based on the origin PO.

#### Fields

```python
origin_po_id = fields.Many2one(
    'purchase.order',
    help="The original PO that this alternative PO is being created for.")

partner_ids = fields.Many2many(
    'res.partner', string='Vendor', required=True,
    help="Choose a vendor for alternative PO")

purchase_warn_msg = fields.Text(
    compute="_compute_purchase_warn_msg",
    groups="purchase.group_warning_purchase")

copy_products = fields.Boolean(
    "Copy Products", default=True,
    help="If this is checked, the product quantities of the original PO will be copied")
```

- `purchase_warn_msg` is computed and aggregates all partner and product-level purchase warnings across selected vendors.
- `copy_products=True` means all order lines from the origin PO are replicated.

#### `_compute_purchase_warn_msg()` -- Aggregate Purchase Warnings

```python
def _compute_purchase_warn_msg(self):
    self.purchase_warn_msg = ''
    if not self.env.user.has_group('purchase.group_warning_purchase'):
        return
    for partner in self.partner_ids:
        if not partner.purchase_warn_msg:
            partner = partner.parent_id
        if partner and partner.purchase_warn_msg:
            self.purchase_warn_msg += _("Warning for %(partner)s:\n%(warning_message)s\n",
                partner=partner.name, warning_message=partner.purchase_warn_msg)
        if self.copy_products and self.origin_po_id.order_line:
            for line in self.origin_po_id.order_line:
                if line.product_id.purchase_line_warn_msg:
                    self.purchase_warn_msg += _("Warning for %(product)s:\n%(warning_message)s\n",
                        product=line.product_id.name,
                        warning_message=line.product_id.purchase_line_warn_msg)
```

Aggregates all purchase warnings from selected partners and all products in the origin PO. Skipped entirely if the user lacks `purchase.group_warning_purchase`.

#### `action_create_alternative()` -- Create and Return

```python
def action_create_alternative(self):
    vals = self._get_alternative_values()
    alt_purchase_orders = self.env['purchase.order'].with_context(
        origin_po_id=self.origin_po_id.id,
        default_requisition_id=False
    ).create(vals)
    alt_purchase_orders.order_line._compute_tax_id()
    action = {
        'type': 'ir.actions.act_window',
        'view_mode': 'list,kanban,form,calendar',
        'res_model': 'purchase.order',
    }
    if len(alt_purchase_orders) == 1:
        action['res_id'] = alt_purchase_orders.id
        action['view_mode'] = 'form'
    else:
        action['name'] = _('Alternative Purchase Orders')
        action['domain'] = [('id', 'in', alt_purchase_orders.ids)]
    return action
```

Key: `default_requisition_id=False` in context ensures alternative POs do not inherit the blanket order link from the origin PO (alternatives should not be tied to the same blanket order, as each is a competitive bid). The `origin_po_id` context tells `purchase.order.create()` to join the same `purchase.order.group`.

#### `_get_alternative_values()` -- Build PO Values

```python
def _get_alternative_values(self):
    vals = []
    origin_po = self.origin_po_id
    partner_product_tmpl_dict = {}
    if self.copy_products and origin_po:
        supplierinfo = self.env['product.supplierinfo'].search([
            ('product_tmpl_id', 'in',
             origin_po.order_line.product_id.product_tmpl_id.ids),
            ('partner_id', 'in', self.partner_ids.ids),
            '|', ('product_code', '!=', False), ('product_name', '!=', False)
        ])
        for info in supplierinfo:
            partner_product_tmpl_dict.setdefault(
                info.partner_id.id, set()).add(info.product_tmpl_id.id)

    for partner in self.partner_ids:
        product_tmpl_ids_with_description = partner_product_tmpl_dict.get(partner.id, set())
        val = {
            'date_order': origin_po.date_order,
            'partner_id': partner.id,
            'user_id': origin_po.user_id.id,
            'dest_address_id': origin_po.dest_address_id.id,
            'origin': origin_po.origin,
            'currency_id': (partner.property_purchase_currency_id.id
                            or self.env.company.currency_id.id),
            'payment_term_id': partner.property_supplier_payment_term_id.id,
        }
        if self.copy_products and origin_po:
            val['order_line'] = [
                Command.create(self._get_alternative_line_value(
                    line, product_tmpl_ids_with_description))
                for line in origin_po.order_line]
        vals.append(val)
    return vals
```

Key behaviors:
- Creates one PO per selected vendor.
- Uses each vendor's preferred currency (`property_purchase_currency_id`).
- Copies product lines only if `copy_products=True`.
- Vendor-specific product codes/names from supplierinfo are detected and the line name is left empty for those products (allowing the vendor's info to populate the name on PO confirmation via `_compute_price_unit_and_date_planned_and_name`).

#### `_get_alternative_line_value()` -- Build Single Line Values

```python
@api.model
def _get_alternative_line_value(self, order_line, product_tmpl_ids_with_description):
    has_product_description = order_line.product_id.product_tmpl_id.id in product_tmpl_ids_with_description
    return {
        'product_id': order_line.product_id.id,
        'product_qty': order_line.product_qty,
        'product_uom_id': order_line.product_uom_id.id,
        'display_type': order_line.display_type,
        'analytic_distribution': order_line.analytic_distribution,
        **({'name': order_line.name} if order_line.display_type in
           ('line_section', 'line_subsection', 'line_note') or
           not has_product_description else {}),
    }
```

For section/note lines (display types), the name is always preserved. For product lines, the name is left blank if the vendor has a `product_name` or `product_code` in supplierinfo -- this allows `_compute_price_unit_and_date_planned_and_name()` on PO confirmation to fill the correct vendor-specific name.

---

## Views

### Agreement Form (`view_purchase_requisition_form`)

**Key visibility conditions:**
- `New Quotation` button: only visible when `state == 'confirmed'`
- `Confirm` button: only when `state == 'draft'`
- `Close` button: only when `state == 'confirmed'` AND `requisition_type != 'purchase_template'` (templates cannot be closed)
- `Reset to Draft` button: only when `state == 'cancel'`
- `Cancel` button: only when `state in ('draft', 'confirmed')`
- `qty_ordered` column: invisible when `requisition_type == 'purchase_template'`
- `vendor_id`: readonly when `state in ('confirmed', 'done')` AND `requisition_type == 'blanket_order'`
- `date_start`/`date_end`: shown only for `blanket_order` type
- Status bar: invisible for `purchase_template` (templates have no state progression)
- `line_ids`: readonly when `state == 'done'`

### PO Form Extension (`purchase_order_form_inherit`)

**Key fields:**
- `partner_id`: readonly when `requisition_type == 'blanket_order'` (once linked to a blanket order, vendor cannot be changed) or when `state in ['purchase', 'cancel']`
- `requisition_id`: domain `[('state', '=', 'confirmed'), ('vendor_id', 'in', (partner_id, False)), ('company_id', '=', company_id)]` -- only confirmed agreements, with vendor filter
- `alternative_po_ids`: widget `many2many_alt_pos`, domain limits alternatives to `['draft', 'sent', 'to approve']`; shown only with `group_purchase_alternatives`

### Line Comparison View (`purchase_order_line_compare_tree`)

Registered as view type `purchase_order_line_compare`. Key features:
- Read-only, non-creatable, non-deletable list view.
- Custom `js_class="purchase_order_line_compare"` attaches `PurchaseOrderLineCompareListRenderer`.
- Header button `action_clear_quantities` (Clear Selected).
- Per-row buttons: `action_choose` (bullseye icon) and `action_clear_quantities` (X icon) -- both hidden when `product_qty <= 0`.
- The renderer calls `get_tender_best_lines()` on load and after every button click.
- Best-price cells get `text-success` CSS class (green highlighting).
- Default ordered by: `amount_total_cc`, then `date_planned`, then `id`.

### Alternatives M2M Widget (`many2many_alt_pos`)

Registered as field widget `many2many_alt_pos`. Custom renderer `FieldMany2ManyAltPOsRenderer`:
- `isCurrentRecord()`: prevents linking a PO to itself as an alternative.
- `openRecord()`: overridden to avoid reopening the currently open PO and to open alternatives in the same window with an extended breadcrumb.

---

## Security

### Access Groups and Approval Rights

There is **no dedicated approval workflow** for purchase agreements. The same Odoo purchase group that creates a requisition also confirms it. Manager-level users have a read-only role on the agreement model itself.

| Group | Role on `purchase.requisition` | Role on `purchase.requisition.line` | Notes |
|---|---|---|---|
| `purchase.group_purchase_user` | **Full CRUD** | **Full CRUD** | Can create, confirm, close, cancel |
| `purchase.group_purchase_manager` | **Read-only** | **Read-only** | Cannot create or modify agreements |
| `purchase.group_purchase_alternatives` (adds to user) | No direct model rights | No direct model rights | Gates UI buttons only |

This is an intentional design: the blanket order lifecycle (create → confirm → done) does not require a second person to approve. All validation is code-enforced (qty > 0, price > 0, dates required for blanket orders) rather than role-enforced.

**Approval implication**: Because the same user can create and confirm an agreement, organizations requiring dual-control must enforce this via ir.rule overrides, server actions, or a custom approval sub-module. The module provides no built-in separation of duties for blanket order confirmation.

### Access Rights (`ir.model.access.csv`)

File: `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_purchase_requisition,purchase.requisition,model_purchase_requisition,purchase.group_purchase_user,1,1,1,1
access_purchase_requisition_line_purchase_user,purchase.requisition.line,model_purchase_requisition_line,purchase.group_purchase_user,1,1,1,1
access_purchase_requisition_manager,purchase.requisition manager,model_purchase_requisition,purchase.group_purchase_manager,1,0,0,0
access_purchase_requisition_line_manager,purchase.requisition.line manager,model_purchase_requisition_line,purchase.group_purchase_manager,1,0,0,0
access_purchase_requisition_alternative_warning, purchase.requisition.alternative.warning,model_purchase_requisition_alternative_warning,purchase.group_purchase_user,1,1,1,1
access_purchase_requisition_create_alternative, purchase.requisition.create.alternative,model_purchase_requisition_create_alternative,purchase.group_purchase_user,1,1,1,1
access_purchase_requisition_purchase_order_group, purchase.order.group,model_purchase_order_group,purchase.group_purchase_user,1,1,1,1
```

Key observations:

- **Manager has W=0, C=0, D=0 on both requisition and line**: The `purchase.group_purchase_manager` ACL grants only `perm_read = 1`. This makes the manager a read-only consumer of agreements. If the manager needs to edit or close an agreement, they must be added to `group_purchase_user` as well (multiple groups are allowed).
- **Wizards have full CRUD for users**: Both `purchase.requisition.alternative.warning` and `purchase.requisition.create.alternative` have full CRUD for `purchase.group_purchase_user`. This is necessary because users need to create wizard records when confirming POs with alternatives.
- **`purchase.order.group` is a technical model**: The `purchase.order.group` record (`access_purchase_requisition_purchase_order_group`) grants full CRUD to users. This allows user-level access to manage PO grouping via `write()` and the self-destruct pattern.

### Record Rules (Multi-Company)

File: `security/purchase_requisition_security.xml`

```xml
<record model="ir.rule" id="purchase_requisition_comp_rule">
    <field name="name">Purchase Requisition multi-company</field>
    <field name="model_id" ref="model_purchase_requisition"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>

<record model="ir.rule" id="purchase_requisition_line_comp_rule">
    <field name="name">Purchase requisition Line multi-company</field>
    <field name="model_id" ref="model_purchase_requisition_line"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>
```

Both models use `company_id` multi-company scoping. There are no `global` rules. This means a user working in company A cannot read, write, or access requisitions belonging to company B. Note that `purchase.order` itself has its own multi-company rule (from the `purchase` module) — when a PO is created from a requisition, the PO's company must match the requisition's company, which Odoo enforces via `check_company=True` on the `requisition_id` field.

### Wizard Access Analysis

| Wizard | Access Group | Operations | Notes |
|---|---|---|---|
| `purchase.requisition.alternative.warning` | `purchase.group_purchase_user` | Read/Create/Write/Unlink | Shown when confirming PO with existing alternatives |
| `purchase.requisition.create.alternative` | `purchase.group_purchase_user` | Read/Create/Write/Unlink | Shown when user clicks "Create Alternative" |

Both wizards are accessible only to `purchase.group_purchase_user`. The warning wizard's `action_keep_alternatives` and `action_cancel_alternatives` methods both write to `purchase.order.group` records (which the user also has full CRUD on). No elevated sudo calls are made in wizard methods — all operations respect current user ACLs.

### `group_purchase_alternatives` (UI Gating Only)

```xml
<record id="group_purchase_alternatives" model="res.groups">
    <field name="name">Manage Purchase Alternatives</field>
</record>
```

This group does **not** grant any model-level ACL. It is used purely for UI gating:

- ` Alternatives` tab on the PO form (`<field name="alternative_po_ids" ... groups="purchase.group_purchase_alternatives">`)
- `Create Alternative` button (`groups="purchase.group_purchase_alternatives"`)
- `Compare Product Lines` button (`groups="purchase.group_purchase_alternatives"`)

Users without this group see no alternatives UI at all. They can still create and manage blanket orders and purchase templates normally.

---

## Sequences

File: `data/purchase_requisition_data.xml`

| Code | Prefix | Padding | Company-Scoped | Example |
|------|--------|---------|----------------|---------|
| `purchase.requisition.blanket.order` | `BO` | 5 | No (`False`) | `BO00005` |
| `purchase.requisition.purchase.template` | `PT` | 5 | No (`False`) | `PT00003` |

Both sequences have `company_id = False` (global), allowing per-company sequence overrides via Settings > Sequences if needed. Global sequences use `with_company()` to pick the right sequence at create time.

---

## QWeb Report

File: `report/report_purchaserequisition.xml`

Template: `purchase_requisition.report_purchaserequisition_document`

Renders:
- Vendor contact block with VAT (using `o.vendor_id.lang` for translated vendor contact)
- Agreement type label + name
- Agreement validity end date (blanket orders only)
- Contact person (the `user_id` / Buyer)
- Reference field
- Products table with: Product (with variant description), Quantity, Ordered (conditional -- only shown if any line has `qty_ordered != 0`), Unit, Unit Price
- Orders table with: Reference, Date, Buyer, Expected on, Total, Status
- Terms and conditions HTML (`description`)

Report action: `action_report_purchase_requisitions` (PDF, QWeb) bound to `purchase.requisition`.

---

## Static Assets

### `purchase_order_line_compare_list_renderer.js`

OWL-based list renderer. On `onWillStart`, calls `purchase.order.get_tender_best_lines()` to fetch the three best-line ID sets. Subclass of `ListRenderer`. Uses `useSubEnv` to hook into `onClickViewButton` (button clicks) to refresh best-line highlighting after any state change.

### `many2many_alt_pos` Widget (`purchase_order_alternatives_widget.js`)

Custom X2Many field widget registered in `web.fields`. Key behavior: `openRecord()` is overridden to prevent re-opening the current record (avoids a loop) and to open alternative POs in the same window with an extended breadcrumb.

---

## Workflow Summary: Blanket Order to PO

```
1. Create blanket order (draft)
   └─ name assigned via sequence (BO prefix)

2. Add product lines with quantities and unit prices

3. Confirm blanket order (action_confirm)
   └─ validates: all lines have qty > 0 AND price > 0
   └─ creates product.supplierinfo for each line
   └─ state -> 'confirmed'

4. From confirmed blanket order:
   ├─ Select vendor on draft PO
   │  └─ Select agreement via requisition_id onchange
   │     └─ vendor, currency, payment terms, origin auto-filled
   │     └─ product lines pre-filled (qty = 0 for blanket order)
   │     └─ requisition_id set on PO
   │
   └─ Multiple RFQs can be created for same agreement

5. On PO confirmation (if alternatives exist):
   └─ Wizard prompts: Keep or Cancel alternatives
   └─ Alternatives linked via purchase.order.group

6. Compare lines: action_compare_alternative_lines
   └─ get_tender_best_lines() called per product
   └─ Green highlights on best-price, best-date, best-unit lines
   └─ action_choose() awards product to selected vendor

7. When blanket order is closed (action_done):
   └─ All supplier info records deleted
   └─ state -> 'done' (terminal)
```

---

## L4 Edge Cases and Failure Modes

| Scenario | Failure Mode | Mitigation |
|----------|-------------|------------|
| `currency_rate = 0` on PO | `price_total_cc` raises `ZeroDivisionError` | Ensure currency rates are configured before creating multi-currency POs |
| Same product added twice to one blanket order | Second line's `qty_ordered` always shows `0` | Intentional design; total ordered qty is still correct (first line carries the full total) |
| Blanket order cancelled: PO still open | PO loses its price reference but prices already filled remain | Buyer must re-select or re-negotiate |
| `action_done` with open RFQs | Raises `UserError` with the "double the order, double the trouble" message | All RFQs must be cancelled or confirmed before closing |
| Changing type/company on non-draft agreement | Raises `UserError` | Must reset to draft first |
| PO created as alternative: vendor has no `property_purchase_currency_id` | Falls back to company currency | Configured at partner level |
| Alternative PO merge | Alternatives absorbed into the surviving PO's group | `_merge_alternative_po()` transfers all alternative_po_ids |
| `purchase_template` confirmed then prices need updating | `_compute_price_unit` stops firing after confirmation | Must reset to draft to update prices |
| Line deleted from confirmed blanket order | `purchase.requisition.line.unlink()` calls `supplierinfo.unlink()` **without sudo** | User must have direct write access to `product.supplierinfo` to delete a blanket order line in confirmed state — the ACL is not bypassed |

---

## Performance Considerations

| Area | Concern | Mitigation |
|------|---------|------------|
| `_compute_ordered_qty` | Double-nested loop: for each line, iterate all POs then all PO lines | `state == 'purchase'` domain filter limits scope; `defaultdict(set)` avoids re-reading already-counted lines |
| `get_tender_best_lines` | Iterates all lines across all alternatives per comparison | Called only on-demand from comparison view; `defaultdict` minimizes repeated comparisons |
| `supplier_info_ids` deletion in `action_done` / `action_cancel` | Uses `sudo().unlink()` | Necessary for access rights; runs only on closed/cancelled agreements |
| `purchase.order.line` price/name compute | Overrides core method | Uses `po_lines_without_requisition` to call parent only for non-requisition lines |
| `alternative_po_ids` (related O2M) | Recomputes on every group write | Intended; alternatives are a core business concept, not a frequent operation |
| `purchase.order.create()` | Checks `origin_po_id` context on every PO creation | Single record browse; negligible overhead |
| `purchase_order_line_compare_list_renderer` | Calls `get_tender_best_lines` via ORM on every `onWillStart` and button click | Single RPC call; acceptable for small sets of alternatives |
