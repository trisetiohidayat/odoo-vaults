---
Module: purchase_requisition
Version: Odoo 18
Type: Business
Tags: #odoo18 #purchase #blanket-order #call-for-tenders #rfq #agreements
---

# purchase_requisition — Purchase Agreements / Call for Tenders

**Addon path:** `~/odoo/odoo18/odoo/addons/purchase_requisition/`
**Purpose:** Manages two types of purchase agreements: **Blanket Orders** (long-term pricing agreements with one vendor) and **Purchase Templates / Call for Tenders** (multi-vendor sourcing where the buyer selects winning lines). Also provides the **Alternative POs** system for comparing competing RFQs from different vendors.

## Agreement Types

| Type | Code | Purpose | PO Behaviour |
|------|------|---------|-------------|
| Blanket Order | `blanket_order` | Lock in price/qty with one vendor for a period | Multiple POs can source from the same agreement; qty drawn down per PO; no PO qty limit enforced |
| Purchase Template | `purchase_template` | Request quotes from multiple vendors; select winning lines | One PO created per agreement; only winning lines copied at PO creation |

---

## Model: `purchase.requisition`

The central agreement document. Tracks lines, vendors, validity dates, and state.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Sequence-generated. Code pattern: `purchase.requisition.blanket.order` or `purchase.requisition.purchase.template` |
| `active` | Boolean | Archive vs delete |
| `reference` | Char | Free-text reference from the user |
| `requisition_type` | Selection | `'blanket_order'` or `'purchase_template'` |
| `vendor_id` | Many2one `res.partner` | Fixed vendor for blanket orders. For templates, used as initial suggestion. |
| `date_start` | Date | Agreement start date. Sets `PO.date_order` if future. |
| `date_end` | Date | Agreement end date. Optional validity cutoff. |
| `user_id` | Many2one `res.users` | Purchase representative responsible |
| `description` | Html | Notes/terms on the agreement |
| `company_id` | Many2one `res.company` | Multi-company support |
| `line_ids` | One2many `purchase.requisition.line` | Agreement product lines |
| `purchase_ids` | One2many `purchase.order` | POs sourced from this agreement |
| `order_count` | Integer (compute) | Count of associated POs |
| `state` | Selection | `'draft'`, `'confirmed'`, `'done'`, `'cancel'` |
| `currency_id` | Many2one `res.currency` | Computed: vendor's purchase currency or company currency |

### State Machine

```
draft ──────► confirmed ──────► done
  │               │
  │               └── action_confirm()
  │                   • Blanket order: validates price > 0, qty > 0 per line
  │                   • Purchase template: no line validation
  │                   • For blanket: creates product.supplierinfo per line
  │
  ▼
cancel ←───── action_cancel()
                • Cancels all linked POs
                • Deletes supplier_info records (sudo)
                • Sets state='cancel'
```

**`action_confirm()` constraints** (blanket orders only):
```python
if requisition_line.price_unit <= 0.0:
    raise UserError("You cannot confirm a blanket order with lines missing a price.")
if requisition_line.product_qty <= 0.0:
    raise UserError("You cannot confirm a blanket order with lines missing a quantity.")
```

**`action_done()` constraints**:
```python
if any(po.state in ['draft', 'sent', 'to approve'] for po in self.mapped('purchase_ids')):
    raise UserError("To close this purchase requisition, cancel related Requests for Quotation.")
```
All associated RFQs must be cancelled or purchase-completed before closing the agreement.

### Name Sequences

```python
if requisition_type == 'blanket_order':
    name = self.env['ir.sequence'].with_company(company_id).next_by_code('purchase.requisition.blanket.order')
else:
    name = self.env['ir.sequence'].with_company(company_id).next_by_code('purchase.requisition.purchase.template')
```

### Supplier Info Creation (Blanket Orders Only)

On `action_confirm()` for blanket orders, each line calls `_create_supplier_info()`:

```python
def _create_supplier_info(self):
    # Only for confirmed blanket orders with a vendor
    self.env['product.supplierinfo'].sudo().create({
        'partner_id': purchase_requisition.vendor_id.id,
        'product_id': self.product_id.id,
        'product_tmpl_id': self.product_id.product_tmpl_id.id,
        'price': self.price_unit,
        'currency_id': self.requisition_id.currency_id.id,
        'purchase_requisition_line_id': self.id,
    })
```

This creates a vendor price list entry on the product, linked back to the requisition line. When the PO draws from the blanket order, the vendor's product seller list is updated automatically.

### Onchange: Vendor Warning

```python
@api.onchange('vendor_id')
def _onchange_vendor(self):
    existing = self.env['purchase.requisition'].search([
        ('vendor_id', '=', self.vendor_id.id),
        ('state', '=', 'confirmed'),
        ('requisition_type', '=', 'blanket_order'),
        ('company_id', '=', self.company_id.id),
    ])
    if existing:
        return {
            'warning': {
                'title': "Warning for {vendor}",
                'message': "There is already an open blanket order for this supplier..."
            }
        }
```

### Currency Compute

```python
@api.depends('vendor_id')
def _compute_currency_id(self):
    if self.vendor_id and self.vendor_id.property_purchase_currency_id:
        self.currency_id = self.vendor_id.property_purchase_currency_id
    else:
        self.currency_id = self.company_id.currency_id
```

### Date Constraint

```python
@api.constrains('date_start', 'date_end')
def _check_dates(self):
    if r.date_end and r.date_start and r.date_end < r.date_start:
        raise ValidationError("End date cannot be earlier than start date...")
```

### Unlink Protection

```python
@api.ondelete(at_uninstall=False)
def _unlink_if_draft_or_cancel(self):
    if any(requisition.state not in ('draft', 'cancel') for requisition in self):
        raise UserError("You can only delete draft or cancelled requisitions.")
```

---

## Model: `purchase.requisition.line`

Individual product line on an agreement.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `product_id` | Many2one `product.product` | Domain: `purchase_ok=True` |
| `product_uom_id` | Many2one `uom.uom` | Defaults to product's purchase UoM |
| `product_uom_category_id` | Many2one (related) | For UoM domain filtering |
| `product_qty` | Float | Quantity covered by the agreement |
| `product_description_variants` | Char | Variant description added to PO line name |
| `price_unit` | Float | Unit price (computed for templates, manual for blankets) |
| `qty_ordered` | Float (compute) | Total quantity already ordered across all POs from this agreement |
| `requisition_id` | Many2one `purchase.requisition` | Parent agreement, cascade delete |
| `company_id` | Many2one (related) | From requisition |
| `supplier_info_ids` | One2many `product.supplierinfo` | Created on blanket order confirmation |

### `qty_ordered` Compute

```python
@api.depends('requisition_id.purchase_ids.state')
def _compute_ordered_qty(self):
    for line in self:
        total = 0.0
        for po in line.requisition_id.purchase_ids.filtered(
                lambda po: po.state in ['purchase', 'done']):
            for po_line in po.order_line.filtered(
                    lambda ol: ol.product_id == line.product_id):
                if po_line.product_uom != line.product_uom_id:
                    total += po_line.product_uom._compute_quantity(
                        po_line.product_qty, line.product_uom_id)
                else:
                    total += po_line.product_qty
        line.qty_ordered = total
```

Note: `qty_ordered` is deduplicated per `(requisition, product_id)` pair — only the first matching line in document order gets the computed total; subsequent lines for the same product get `qty_ordered = 0`.

### `price_unit` Compute

```python
@api.depends('product_id', 'company_id', 'requisition_id.date_start',
             'product_qty', 'product_uom_id', 'requisition_id.vendor_id',
             'requisition_id.requisition_type')
def _compute_price_unit(self):
    for line in self:
        # Only auto-computes for DRAFT purchase_templates with a vendor
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

### `_prepare_purchase_order_line()` — Key Method

Used by both blanket order PO creation and template-to-PO conversion:

```python
def _prepare_purchase_order_line(self, name, product_qty=0.0, price_unit=0.0, taxes_ids=False):
    date_planned = fields.Datetime.now()
    if self.requisition_id.date_start:
        date_planned = max(date_planned, fields.Datetime.to_datetime(self.requisition_id.date_start))
    return {
        'name': name + ('\n' + self.product_description_variants if self.product_description_variants else ''),
        'product_id': self.product_id.id,
        'product_uom': self.product_id.uom_po_id.id,
        'product_qty': product_qty,
        'price_unit': price_unit,
        'taxes_id': [(6, 0, taxes_ids)],
        'date_planned': date_planned,
        'analytic_distribution': self.analytic_distribution,
    }
```

### Write Logic: Supplier Info Sync

When a confirmed blanket order line's price is updated:
```python
def write(self, vals):
    if 'price_unit' in vals:
        # Sync price to product.supplierinfo
        self.supplier_info_ids.write({'price': vals['price_unit']})
```

---

## Model: `purchase.order` (Extension)

Links POs to requisition agreements and manages the alternative POs system.

### Added Fields

| Field | Type | Notes |
|-------|------|-------|
| `requisition_id` | Many2one `purchase.requisition` | Source agreement |
| `requisition_type` | Selection (related) | `'blanket_order'` or `'purchase_template'` |
| `purchase_group_id` | Many2one `purchase.order.group` | Groups alternative POs together |
| `alternative_po_ids` | One2many `purchase.order` | Other POs in the same group |
| `has_alternatives` | Boolean (compute) | True if in a group with other POs; gated by `group_purchase_alternatives` |

### Alternative POs System

POs can be grouped into a "purchase order group". Any PO in the group is an alternative to every other. The group is represented by the `purchase.order.group` model (a technical model).

```python
class PurchaseOrderGroup(models.Model):
    order_ids = fields.One2many('purchase.order', 'purchase_group_id')

    def write(self, vals):
        res = super().write(vals)
        # Auto-implode group when only 1 PO remains
        self.filtered(lambda g: len(g.order_ids) <= 1).unlink()
        return res
```

### Creating an Alternative PO

```python
def action_create_alternative(self):
    # Opens purchase.requisition.create.alternative wizard
    # Sets context: default_origin_po_id = self.id
    return {
        'name': 'Create alternative',
        'res_model': 'purchase.requisition.create.alternative',
        'context': {'default_origin_po_id': self.id},
    }
```

When the wizard creates the PO, it sets `context: {'origin_po_id': self.id}`:

```python
@api.model_create_multi
def create(self, vals_list):
    orders = super().create(vals_list)
    if self.env.context.get('origin_po_id'):
        origin_po = self.env['purchase.order'].browse(self.env.context['origin_po_id'])
        if origin_po.purchase_group_id:
            origin_po.purchase_group_id.order_ids |= orders
        else:
            self.env['purchase.order.group'].create({'order_ids': [Command.set(origin_po.ids + orders.ids)]})
    return orders
```

### Confirming a PO with Alternatives

```python
def button_confirm(self):
    if self.alternative_po_ids and not self.env.context.get('skip_alternative_check'):
        alternative_po_ids = self.alternative_po_ids.filtered(
            lambda po: po.state in ['draft', 'sent', 'to approve'] and po.id not in self.ids)
        if alternative_po_ids:
            # Block confirm; show wizard asking what to do with alternatives
            return {
                'name': "What about the alternative Requests for Quotation?",
                'res_model': 'purchase.requisition.alternative.warning',
            }
    return super().button_confirm()
```

**`purchase.requisition.alternative.warning` wizard:**

| Button | Action |
|--------|--------|
| `action_keep_alternatives` | Confirm this PO only; leave alternatives open |
| `action_cancel_alternatives` | Cancel all open alternative POs, then confirm this one |
| (auto after wizard) | `button_confirm()` called with `skip_alternative_check=True` |

### Comparing Alternative Lines

```python
def action_compare_alternative_lines(self):
    # Opens tree view of all PO lines across self + alternative POs
    # Grouped by product_id via context: search_default_groupby_product=True
    return {
        'domain': [('order_id', 'in', (self | self.alternative_po_ids).ids),
                   ('display_type', '=', False)],
        'context': {'purchase_order_id': self.id},
    }
```

### `get_tender_best_lines()` — Tender Best-Per-Line Algorithm

Used for "call for tenders" (purchase_template type). For each product across all alternative POs, finds:

```python
best_price_ids      # Line(s) with lowest total (price_total_cc)
best_date_ids        # Line(s) with earliest date_planned
best_price_unit_ids  # Line(s) with lowest unit price
```

Lines are excluded if: `product_qty=0`, `price_total_cc=0` (no price), or `state in ['cancel', 'purchase', 'done']`.

### `_onchange_requisition_id()` — Drawing from Agreement

When a PO is linked to a requisition (blanket order or template):

```python
@api.onchange('requisition_id')
def _onchange_requisition_id(self):
    if not self.requisition_id:
        return
    requisition = self.requisition_id
    # Sets: partner_id, fiscal_position_id, payment_term_id,
    #       company_id, currency_id, origin, notes, date_order
    self.partner_id = requisition.vendor_id or self.partner_id
    self.currency_id = requisition.currency_id
    if requisition.date_start:
        self.date_order = max(now, requisition.date_start)
    # Creates PO lines:
    for line in requisition.line_ids:
        # Maps taxes via fiscal position
        taxes_ids = fpos.map_tax(line.product_id.supplier_taxes_id).ids
        # For templates: product_qty=0 (quantities entered manually)
        # For blankets: product_qty stays as-is (full agreement qty available)
        if requisition.requisition_type != 'purchase_template':
            product_qty = 0  # quantities specified per PO, not blanket total
        order_line_values = line._prepare_purchase_order_line(
            name=name, product_qty=product_qty,
            price_unit=price_unit, taxes_ids=taxes_ids)
        order_lines.append((0, 0, order_line_values))
    self.order_line = order_lines
```

**Key difference**: For blanket orders, the full `product_qty` from the agreement line is pre-filled on the PO. For purchase templates, `product_qty=0` — the buyer must manually enter quantities per line (supports multi-vendor comparison where you may not order the full quantity from each vendor).

---

## Model: `purchase.order.line` (Extension)

### Added Fields

| Field | Type | Notes |
|-------|------|-------|
| `price_total_cc` | Monetary (compute, store) | Subtotal in company currency (`price_subtotal / currency_rate`) |
| `company_currency_id` | Many2one (related) | `company_id.currency_id` |

### `_compute_price_unit_and_date_planned_and_name()` (Override)

When a PO line's product is in the requisition's line_ids, the price and description are auto-filled from the requisition line:

```python
for pol in self:
    if pol.product_id.id in pol.order_id.requisition_id.line_ids.product_id.ids:
        for line in pol.order_id.requisition_id.line_ids:
            if line.product_id == pol.product_id:
                # Unit price in requisition UoM, converted to PO UoM
                pol.price_unit = line.product_uom_id._compute_price(
                    line.price_unit, pol.product_uom)
                # Date from requisition start or now
                pol.date_planned = pol._get_date_planned(seller)
                # Description from product + variant description
                pol.name = product_description + variant_description
```

### `action_clear_quantities()` and `action_choose()`

Used in the alternative PO comparison view:
- `action_clear_quantities()`: Sets `product_qty=0` on selected lines
- `action_choose()`: Called from the "Choose" button. Clears quantities on lines for the same products in OTHER alternative POs, keeping only the selected lines

---

## Model: `product.supplierinfo` (Extension)

Links supplier info records back to a requisition line:

| Field | Type | Notes |
|-------|------|-------|
| `purchase_requisition_id` | Many2one `purchase.requisition` (related) | Via `purchase_requisition_line_id` |
| `purchase_requisition_line_id` | Many2one `purchase.requisition.line` | Set when blanket order is confirmed |

This enables filtering seller prices by requisition in `_prepare_sellers()`.

---

## Model: `product.product` (Extension)

### `_prepare_sellers(params=False) -> recordset`

Filters the seller's partner list when creating a PO from a requisition:

```python
def _prepare_sellers(self, params=False):
    sellers = super()._prepare_sellers(params=params)
    if (params and params.get('order_id')
            and params['order_id']._fields.get("requisition_id")):
        # Only show sellers linked to this specific blanket order
        # OR no requisition at all (free sellers)
        return sellers.filtered(
            lambda s: not s.purchase_requisition_id
            or s.purchase_requisition_id == params['order_id'].requisition_id)
    return sellers
```

This ensures that when creating a PO from a blanket order, only the blanket order's vendor (and non-requisition sellers) appear in the seller list.

---

## Wizard: `purchase.requisition.create.alternative`

Creates a new RFQ as an alternative to an existing PO.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `origin_po_id` | Many2one `purchase.order` | The PO being compared against |
| `partner_id` | Many2one `res.partner` | New vendor for the alternative |
| `copy_products` | Boolean | If True, copies product lines from origin PO |
| `creation_blocked` | Boolean (compute) | True if partner or any copied product has a blocking warning |
| `purchase_warn_msg` | Text (compute) | Accumulated warning messages |

### Line Copy: `_get_alternative_line_value()`

```python
@api.model
def _get_alternative_line_value(self, order_line):
    return {
        'product_id': order_line.product_id.id,
        'product_qty': order_line.product_qty,
        'product_uom': order_line.product_uom.id,
        'display_type': order_line.display_type,
        # Section/note display_types preserve their name
        **({'name': order_line.name} if order_line.display_type in ('line_section', 'line_note') else {}),
    }
```

### Blocked Warning Logic

Checks partner purchase_warn (blocks if `'block'`) and each product's `purchase_line_warn` (blocks if `'block'`). Advisory warnings are accumulated but do not block.

---

## Wizard: `purchase.requisition.alternative.warning`

Shown when confirming a PO that has open alternative RFQs.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `po_ids` | Many2many `purchase.order` | POs to confirm |
| `alternative_po_ids` | Many2many `purchase.order` | Open alternatives |

### Actions

| Method | Behaviour |
|--------|-----------|
| `action_keep_alternatives()` | Confirm `po_ids`; leave alternatives open |
| `action_cancel_alternatives()` | Cancel open alternatives first, then confirm `po_ids` |
| `_action_done()` | Calls `po_ids.with_context(skip_alternative_check=True).button_confirm()` |

---

## Res Config Settings

| Field | Type | Group | Notes |
|-------|------|-------|-------|
| `group_purchase_alternatives` | Boolean | `purchase_requisition.group_purchase_alternatives` | Enables Alternative POs UI |

---

## L4: How Blanket Orders Work (End-to-End)

```
1. Create blanket order (draft)
   └─> name = "Call for Bids / PNRO/..." (sequence: purchase.requisition.blanket.order)
   └─> Set vendor_id, date_start, date_end, line_ids (product, qty, price_unit)

2. Confirm blanket order (action_confirm)
   └─> Validates all lines have price_unit > 0 and product_qty > 0
   └─> For each line: _create_supplier_info()
           └─> Creates product.supplierinfo:
                   partner_id = vendor, price = agreement price,
                   currency_id = agreement currency,
                   purchase_requisition_line_id = line.id
   └─> state = 'confirmed'

3. Create PO from blanket order
   └─> requisition_id = blanket_order
   └─> _onchange_requisition_id() fills: vendor, currency, origin, date_order
   └─> PO lines created with full product_qty from blanket line
   └─> vendor_id.seller_ids filtered by purchase_requisition_id

4. Multiple POs from same blanket order
   └─> Each PO draws down qty_ordered on the blanket line
   └─> No enforcement that total PO qty <= blanket qty
   └─> Buyer manages quantity discipline manually

5. Close blanket order (action_done)
   └─> Requires all POs to be cancelled, purchase-confirmed, or done
   └─> Deletes all supplier_info records
   └─> state = 'done'

6. Cancel blanket order
   └─> Cancels all associated POs
   └─> Deletes supplier_info records
   └─> state = 'cancel'
```

---

## L4: How Call for Tenders / Purchase Templates Work

```
1. Create purchase_template
   └─> name = sequence: purchase.requisition.purchase.template
   └─> Set vendor_id (optional — suggestion only), date_start, date_end
   └─> Add line_ids (product, product_qty for reference, price_unit auto-looked-up)

2. No confirmation step for purchase_template
   └─> Can create POs directly; no supplier_info created

3. Create POs from template
   └─> For each vendor you want to quote:
           purchase.order + _onchange_requisition_id()
           └─> Sets PO vendor, currency
           └─> Creates PO lines with product_qty=0 (buyer enters manually)
           └─> Templates can be assigned to template type requisition
               to create multiple POs (one per vendor)

4. Compare alternatives
   └─> action_compare_alternative_lines() on any PO
           └─> Tree view of all lines across POs
           └─> Color coding: best price (green), best date (blue), best unit price (orange)
           └─> get_tender_best_lines() returns sets of best line IDs

5. Select winning lines
   └─> Use "Choose" button to clear quantities on non-winning lines across alternatives
   └─> Confirm winning PO
           └─> action_keep_alternatives() — leave alternatives open for audit
           or └─> action_cancel_alternatives() — cancel all other POs

6. Close template
   └─> No supplier_info to delete
   └─> state = 'done'
```

---

## L4: Vendor Pricing Integration

Blanket order pricing creates `product.supplierinfo` records. These integrate with the standard seller price lookup:

```
product_id._select_seller()
    └─> filters by: partner_id, quantity, date, uom_id
    └─> purchase_requisition._prepare_sellers() further filters
            └─> keeps: sellers with no requisition OR matching blanket order
```

When PO line is created from blanket: `product_id.uom_po_id` is used as `product_uom`, with price converted from `line.product_uom_id` to `product_id.uom_po_id`.

---

## See Also

- [Modules/Purchase](purchase.md) — `purchase.order` base model, RFQ lifecycle
- [Modules/Stock](stock.md) — Incoming receipts from POs
- [Modules/Product](product.md) — `product.product`, `product.supplierinfo`
- [Patterns/Workflow Patterns](Workflow Patterns.md) — State machine, action methods
- [Core/API](API.md) — `@api.depends`, `@api.onchange`, `@api.constrains`
