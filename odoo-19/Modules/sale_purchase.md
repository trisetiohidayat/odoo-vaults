---
tags:
  - #odoo19
  - #modules
  - #sale
  - #purchase
  - #service
  - #dropship
---

# sale_purchase

**Module:** `sale_purchase`
**Path:** `odoo/addons/sale_purchase/`
**Dependencies:** `sale`, `purchase`
**Category:** Sales/Sales
**Auto-installs:** `True` — auto-installs when both `sale` and `purchase` are present (no explicit dependency chain, just both in the ir_module_category)
**License:** LGPL-3

---

## Overview

`sale_purchase` is a bridge module that enables **service outsourcing** (the "dropship for services" pattern). When a confirmed `sale.order.line` contains a service product with `service_to_purchase = True` and a configured vendor, the module automatically creates a Purchase Order (PO) or Request for Quotation (RFQ) toward that vendor.

The two orders sit on opposite sides of the margin:
```
Customer-facing:  sale.order  → invoice customer (revenue)
                     ↑
                     |  markup / margin
                     |
Vendor-facing:   purchase.order → pay vendor (cost)
```

The module does **not** automate reinvoicing. Margin is implicit — it is the difference between the SOL sale price and the PO line purchase price.

---

## Dependencies

```
sale_purchase
├── sale         (sale.order, sale.order.line)
└── purchase     (purchase.order, purchase.order.line)
```

No dependency on `project`, `account`, or `sale_timesheet`. The `auto_install: True` flag means this module activates automatically when both `sale` and `purchase` are installed — no manual installation step needed.

---

## Product Configuration

### `product.template` — `service_to_purchase`

**File:** `models/product_template.py`

```python
service_to_purchase = fields.Boolean(
    "Subcontract Service", company_dependent=True, copy=False,
    help="If ticked, each time you sell this product through a SO, a RfQ is "
         "automatically created to buy the product. Tip: don't forget to set "
         "a vendor on the product.")
```

**L2 details:**
- `company_dependent=True` — the boolean value is stored in `ir.property` per company. This is critical for multi-company setups: a product can have `service_to_purchase = True` for Company A and `False` for Company B. Accessing `product_id.service_to_purchase` without a `with_company()` context returns the value for `self.env.company`.
- `copy=False` — when duplicating a product template, the flag does not carry over (intentional: new product should be reviewed before enabling).
- `company_dependent` is the Odoo 18+ pattern. Prior to Odoo 18, this was implemented differently.

**Constraint — `_check_service_to_purchase`:**
```python
@api.constrains('service_to_purchase', 'seller_ids', 'type')
def _check_service_to_purchase(self):
    for template in self:
        if template.service_to_purchase:
            if template.type != 'service':
                raise ValidationError(
                    _("Product that is not a service can not create RFQ."))
            template._check_vendor_for_service_to_purchase(template.seller_ids)
```

Two hard preconditions must be met:
1. `product.type == 'service'` — physical/stock products cannot use this mechanism.
2. At least one `seller_ids` (product.supplierinfo) record exists — vendor must be defined, or a `ValidationError` is raised at product save or SO confirmation time.

**Onchange guard — `_onchange_service_to_purchase`:**
```python
@api.onchange('type', 'expense_policy')
def _onchange_service_to_purchase(self):
    products_template = self.filtered(
        lambda p: p.type != 'service' or p.expense_policy != 'no')
    products_template.service_to_purchase = False
```

If the product type is changed from `service` to something else, or the expense policy is changed away from `no`, the `service_to_purchase` flag is automatically unset. This prevents orphaned configuration.

**UI:** The field appears in the "Reordering" group on `product.template` form view, inside the "Purchase" tab (inherited from `purchase.view_product_supplier_inherit`). It is only visible when `type == 'service'`.

---

## Model Extensions

### `sale.order.line` — `sale_purchase/models/sale_order_line.py`

#### New Fields

**`purchase_line_ids`** — `One2many('purchase.order.line', 'sale_line_id')`
Links back from PO lines to the originating SOL. Inverse of `purchase.order.line.sale_line_id`.

**`purchase_line_count`** — computed `Integer`
```python
@api.depends('purchase_line_ids')
def _compute_purchase_count(self):
    database_data = self.env['purchase.order.line'].sudo()._read_group(
        [('sale_line_id', 'in', self.ids)],
        ['sale_line_id'],
        ['__count']
    )
    mapped_data = {sale_line.id: count for sale_line, count in database_data}
    for line in self:
        line.purchase_line_count = mapped_data.get(line.id, 0)
```

Uses `sudo()` + `_read_group` instead of a simple `search_count` to avoid AccessError in multi-company scenarios where a sale user may not have read access to PO lines belonging to another company.

---

### `purchase.order.line` — `sale_purchase/models/purchase_order.py`

```python
sale_order_id = fields.Many2one(
    related='sale_line_id.order_id',
    string="Sale Order")

sale_line_id = fields.Many2one(
    'sale.order.line',
    string="Origin Sale Item",
    index='btree_not_null',
    copy=False)
```

**L3 details:**
- `index='btree_not_null'` — creates a partial index that only indexes non-NULL `sale_line_id` values. This is more efficient than a standard index for the common query pattern `WHERE sale_line_id IS NOT NULL`, since NULL values are excluded. This index is critical for the `_purchase_service_match_purchase_order` search and the `sale_order_count` compute on `purchase.order`.
- `copy=False` — PO lines created from SOL should not be duplicated via SOL copy (prevents accidental PO duplication).
- `sale_order_id` is a convenience related field that traverses `sale_line_id → order_id` in a single hop.

---

### `purchase.order` — `sale_purchase/models/purchase_order.py`

#### New Fields

| Field | Type | Compute | Groups | Description |
|-------|------|---------|--------|-------------|
| `sale_order_count` | Integer | `_compute_sale_order_count` | `sales_team.group_sale_salesman` | Count of distinct SO linked via `order_line.sale_order_id` |
| `has_sale_order` | Boolean | `_compute_sale_order_count` | `sales_team.group_sale_salesman` | True if at least one SO is linked |

#### `_compute_dest_address_id` Override

```python
@api.depends('order_line.sale_order_id.partner_shipping_id')
def _compute_dest_address_id(self):
    super()._compute_dest_address_id()
    po_with_address = self.filtered(
        lambda po: po.dest_address_id
        and len(po._get_sale_orders().partner_shipping_id) == 1)
    for order in po_with_address:
        order.dest_address_id = order._get_sale_orders().partner_shipping_id
```

When all linked SOs share the same `partner_shipping_id`, the PO's `dest_address_id` is automatically populated from those SOs. This is relevant for service deliveries that have a physical destination. The condition `len(...) == 1` ensures the address is unambiguous.

---

### `sale.order` — `sale_purchase/models/sale_order.py`

#### New Fields

| Field | Type | Compute | Groups | Description |
|-------|------|---------|--------|-------------|
| `purchase_order_count` | Integer | `_compute_purchase_order_count` | `purchase.group_purchase_user` | Count of distinct PO linked via `order_line.purchase_line_ids.order_id` |

The button to access PO from SO form view is gated behind `purchase.group_purchase_user`; the count field is invisible when zero.

---

## Core Workflow — PO Generation Pipeline

```
sale.order  [action_confirm]
    └─→ _action_confirm()
          └─→ _purchase_service_generation()  [sudo(), per company]
                └─→ for each SOL where service_to_purchase=True and purchase_line_count=0
                      └─→ _purchase_service_create()
                            ├─→ _purchase_service_match_supplier()
                            │     └─→ product_id._select_seller()
                            ├─→ _match_or_create_purchase_order()
                            │     ├─→ _purchase_service_match_purchase_order()  [search draft PO]
                            │     └─→ _create_purchase_order()                   [if no match]
                            └─→ _purchase_service_prepare_line_values()
                                  └─→ purchase.order.line.create()
```

### Trigger: `_action_confirm()` on `sale.order`

```python
def _action_confirm(self):
    result = super(SaleOrder, self)._action_confirm()
    for order in self:
        order.order_line.sudo()._purchase_service_generation()
    return result
```

Called with `sudo()` because a sale user may not have write access on PO records — the module must create PO records under a purchase-appropriate context. However, the `sale.order` state change itself respects normal sale access rules.

### Generation guard: `_purchase_service_generation()`

```python
def _purchase_service_generation(self):
    for line in self:
        line = line.with_company(line._purchase_service_get_company())
        # Idempotency: skip if already generated
        if line.product_id.service_to_purchase and not line.purchase_line_count:
            result = line._purchase_service_create()
```

**Idempotency:** If `purchase_line_count > 0`, the SOL has already generated PO lines (SO was previously confirmed, then possibly cancelled and re-confirmed). Re-confirmation does NOT create duplicate PO lines — this is tested in `test_reconfirm_sale_order`. The existing PO lines remain in place.

**Company context:** `with_company()` ensures the `service_to_purchase` check uses the correct company's property value.

### Vendor matching: `_purchase_service_match_supplier()`

```python
def _purchase_service_match_supplier(self, warning=True):
    suppliers = self.product_id._select_seller(
        partner_id=self._retrieve_purchase_partner(),
        quantity=self.product_uom_qty,
        uom_id=self.product_uom_id
    )
    if warning and not suppliers:
        raise UserError(_("There is no vendor associated to the product %s. "
                          "Please define a vendor for this product.",
                          self.product_id.display_name))
    return suppliers[0]
```

Uses `product_id._select_seller()` — the same vendor selection logic used throughout the purchase module. Selection criteria (in priority order):
1. `partner_id` match from `_retrieve_purchase_partner()` override (default returns `False`)
2. Quantity-based matching against `product.supplierinfo.min_qty`
3. Date validity (`date_start` / `date_end` on supplierinfo)
4. Sequence priority

If no supplier is found and `warning=True`, a `UserError` is raised. This halts SO confirmation.

### PO grouping: `_match_or_create_purchase_order()`

```python
def _match_or_create_purchase_order(self, supplierinfo):
    purchase_order = self._purchase_service_match_purchase_order(
        supplierinfo.partner_id)[:1]
    if not purchase_order:
        purchase_order = self._create_purchase_order(supplierinfo)
    return purchase_order
```

The search in `_purchase_service_match_purchase_order`:
```python
def _purchase_service_match_purchase_order(self, partner, company=False):
    return self.env['purchase.order.line'].search(
        Domain.AND([
            [
                ('partner_id', '=', partner.id),
                ('state', '=', 'draft'),
                ('company_id', '=', (company and company or self.env.company).id),
            ],
            self._get_additional_domain_for_purchase_order_line(),  # sale_order_id = self.order_id.id
        ]),
        order='order_id',
        limit=1,
    ).order_id
```

**Grouping rule:** Multiple SOLs from the **same SO** targeting the **same vendor** → share one draft PO. This is how `sale_order_id = self.order_id.id` in the domain works — it restricts matches to draft POs that originated from the same SO.

**Implication:** If the same vendor appears on two different SOs, each SO creates its own draft PO (no cross-SO merging).

### PO order values: `_purchase_service_prepare_order_values()`

```python
def _purchase_service_prepare_order_values(self, supplierinfo):
    self.ensure_one()
    partner_supplier = supplierinfo.partner_id
    fpos = self.env['account.fiscal.position'].sudo()._get_fiscal_position(partner_supplier)
    date_order = self._purchase_get_date_order(supplierinfo)
    return {
        'partner_id': partner_supplier.id,
        'partner_ref': partner_supplier.ref,
        'company_id': self._purchase_service_get_company().id,
        'currency_id': (partner_supplier.property_purchase_currency_id.id
                        or self.env.company.currency_id.id),
        'dest_address_id': False,  # only supported in stock
        'origin': self.order_id.name,
        'payment_term_id': partner_supplier.property_supplier_payment_term_id.id,
        'date_order': date_order,
        'fiscal_position_id': fpos.id,
    }
```

Key behaviors:
- `currency_id` — vendor's purchase currency, falling back to company currency. This enables multi-currency: you sell in EUR, vendor bills in USD, PO is in USD.
- `origin` — set to SO name. Updated via `split(', ')` logic in `_purchase_service_create` to append multiple SO names when the same PO is shared.
- `dest_address_id` is hardcoded to `False` here. Delivery address handling requires the `stock` module (dropship/pickup path).
- `fiscal_position` is computed via `sudo()` to avoid access errors when the sale user runs confirmation.

### PO line values: `_purchase_service_prepare_line_values()`

```python
def _purchase_service_prepare_line_values(self, purchase_order, quantity=False):
    self.ensure_one()
    product_quantity = self.product_uom_qty
    if quantity:
        product_quantity = quantity

    purchase_qty_uom = self.product_uom_id._compute_quantity(
        product_quantity, self.product_id.uom_id)

    supplierinfo = self.product_id._select_seller(
        partner_id=purchase_order.partner_id,
        quantity=purchase_qty_uom,
        date=purchase_order.date_order.date(),
        uom_id=self.product_id.uom_id
    )
    if supplierinfo and supplierinfo.product_uom_id != self.product_id.uom_id:
        purchase_qty_uom = self.product_id.uom_id._compute_quantity(
            purchase_qty_uom, supplierinfo.product_uom_id)

    price_unit, taxes = self._purchase_service_get_price_unit_and_taxes(
        supplierinfo, purchase_order)
    name = self._purchase_service_get_product_name(supplierinfo, purchase_order, quantity)
    line_description = self.with_context(
        lang=self.order_id.partner_id.lang)._get_sale_order_line_multiline_description_variants()
    if line_description:
        name += line_description

    purchase_line_vals = {
        'name': name,
        'product_qty': purchase_qty_uom,
        'product_id': self.product_id.id,
        'product_uom_id': supplierinfo.product_uom_id.id or self.product_id.uom_id.id,
        'price_unit': price_unit,
        'date_planned': purchase_order.date_order + relativedelta(
            days=int(supplierinfo.delay)),
        'tax_ids': [(6, 0, taxes.ids)],
        'order_id': purchase_order.id,
        'sale_line_id': self.id,          # ← bidirectional link
        'discount': supplierinfo.discount,
    }
    if self.analytic_distribution:
        purchase_line_vals['analytic_distribution'] = self.analytic_distribution
    return purchase_line_vals
```

**UoM conversion:** Two-step conversion — first from SOL UoM to product's default UoM, then (if vendor UoM differs) from product UoM to vendor UoM. This is tested in `test_uom_conversion` where SOL uses "dozen" and vendor uses "unit".

**Price:** Comes from `supplierinfo.price` (vendor's list price), not from the SOL sale price. Tax treatment uses the vendor's supplier taxes, mapped through the fiscal position.

**Analytic distribution:** Propagated from SOL to PO line if set, enabling cost tracking against projects/accounts.

---

## Quantity Change Handling

### Increase — `_purchase_increase_ordered_qty()`

```python
def _purchase_increase_ordered_qty(self, new_qty, origin_values):
    for line in self:
        last_purchase_line = self.env['purchase.order.line'].search(
            [('sale_line_id', '=', line.id)],
            order='create_date DESC', limit=1)
        if last_purchase_line.state in ['draft', 'sent', 'to approve']:
            # Update existing PO line qty directly
            quantity = line.product_uom_id._compute_quantity(
                new_qty, last_purchase_line.product_uom_id)
            last_purchase_line.write({'product_qty': quantity})
        elif last_purchase_line.state in ['purchase', 'cancel']:
            # Create NEW PO line with delta quantity
            quantity = line.product_uom_id._compute_quantity(
                new_qty - origin_values.get(line.id, 0.0),
                last_purchase_line.product_uom_id)
            line._purchase_service_create(quantity=quantity)
```

**Decision table:**

| PO state | Action |
|----------|--------|
| `draft`, `sent`, `to approve` | Update `product_qty` on the existing line to `new_qty` |
| `purchase`, `cancel` | Create a **new** PO line for the **delta** (increase above original value) |

When a confirmed PO exists, Odoo's purchase workflow prevents line modification. The workaround is to create a supplementary PO line for the additional quantity. This results in **two PO lines** from a single SOL (visible in `test_update_ordered_sale_quantity`).

### Decrease — `_purchase_decrease_ordered_qty()`

```python
def _purchase_decrease_ordered_qty(self, new_qty, origin_values):
    purchase_to_notify_map = {}
    last_purchase_lines = self.env['purchase.order.line'].search(
        [('sale_line_id', 'in', self.ids)])
    for purchase_line in last_purchase_lines:
        purchase_to_notify_map.setdefault(
            purchase_line.order_id, self.env['sale.order.line'])
        purchase_to_notify_map[purchase_line.order_id] |= purchase_line.sale_line_id

    for purchase_order, sale_lines in purchase_to_notify_map.items():
        render_context = {
            'sale_lines': sale_lines,
            'sale_orders': sale_lines.mapped('order_id'),
            'origin_values': origin_values,
        }
        purchase_order._activity_schedule_with_view(
            'mail.mail_activity_data_warning',
            user_id=purchase_order.user_id.id or self.env.uid,
            views_or_xmlid='sale_purchase.exception_purchase_on_sale_quantity_decreased',
            render_context=render_context)
```

**Decrease is never auto-applied.** A `mail.activity` of type `warning` is created on the PO with a rendering of all affected SOLs, old vs. new quantities, and links back to the SO. The activity is assigned to `purchase_order.user_id` (the PO responsible), not the sale user.

**Guard:** In `_onchange_service_product_uom_qty`, if decreasing below `qty_delivered`, a user-facing warning is shown on the SO form — the write is allowed to proceed, but the PO quantity is not auto-reduced.

---

## Cancellation Flows

### SO Cancellation → PO Notification

```python
def _action_cancel(self):
    result = super()._action_cancel()
    self.sudo()._activity_cancel_on_purchase()
    return result
```

```python
def _activity_cancel_on_purchase(self):
    purchase_order_lines = self.env['purchase.order.line'].search([
        ('sale_line_id', 'in', self.mapped('order_line').ids),
        ('state', '!=', 'cancel'),
        ('product_id.service_to_purchase', '=', True),
    ])
    for purchase_line in purchase_order_lines:
        purchase_to_notify_map.setdefault(
            purchase_line.order_id, self.env['sale.order.line'])
        purchase_to_notify_map[purchase_line.order_id] |= purchase_line.sale_line_id
    for purchase_order, sale_order_lines in purchase_to_notify_map.items():
        purchase_order._activity_schedule_with_view(...)
```

Only non-cancelled PO lines trigger notifications. The `sudo()` is critical here — a sales person cancelling an SO may not have write access to PO records, but the activity creation must proceed.

### PO Cancellation → SO Notification

```python
def button_cancel(self):
    result = super(PurchaseOrder, self).button_cancel()
    self.sudo()._activity_cancel_on_sale()
    return result
```

```python
def _activity_cancel_on_sale(self):
    for order in self:
        for purchase_line in order.order_line:
            if purchase_line.sale_line_id:
                sale_order = purchase_line.sale_line_id.order_id
                sale_to_notify_map.setdefault(
                    sale_order, self.env['purchase.order.line'])
                sale_to_notify_map[sale_order] |= purchase_line
    for sale_order, purchase_order_lines in sale_to_notify_map.items():
        sale_order._activity_schedule_with_view(
            'mail.mail_activity_data_warning',
            views_or_xmlid='sale_purchase.exception_sale_on_purchase_cancellation',
            ...)
```

Activity is assigned to `sale_order.user_id` (the sale person responsible for the SO).

---

## Mail Activity Templates

Three QWeb templates in `data/mail_templates.xml`:

| Template ID | Trigger | Render context |
|-------------|---------|----------------|
| `sale_purchase.exception_purchase_on_sale_quantity_decreased` | SO qty decreased | `sale_orders`, `sale_lines`, `origin_values` |
| `sale_purchase.exception_purchase_on_sale_cancellation` | SO cancelled | `sale_orders`, `sale_order_lines` |
| `sale_purchase.exception_sale_on_purchase_cancellation` | PO cancelled | `purchase_orders`, `purchase_order_lines` |

All three use `mail.mail_activity_data_warning` (red/alert styling) because they represent exception conditions requiring manual intervention.

---

## Security Considerations

### `sudo()` Usage — Intent and Risk

Three explicit `sudo()` calls exist:

1. **`sale_order_line.py` line 20:** `self.env['purchase.order.line'].sudo()._read_group(...)` in `_compute_purchase_count`
   - Reason: sale users compute a count on PO lines they may not have explicit read access to (different company or record rule).
   - Risk: Mild information exposure — only the count (integer) is returned, not field values.

2. **`sale_order_line.py line 48:** `order.order_line.sudo()._purchase_service_generation()` in `_action_confirm`
   - Reason: sale user confirms SO, which must create PO records the sale user has no `create` permission on.
   - Risk: This is the intended design. A sale user can trigger PO creation without purchase rights. The PO is created in `draft` state, requiring a purchase user to confirm it — so no financial commitment is made automatically.

3. **`sale_order.py line 31:** `self.sudo()._activity_cancel_on_purchase()` in `_action_cancel`
   - Reason: sale user cancelling an SO must write an activity onto a PO they have no access to.
   - Risk: Low — activity creation only.

### Access Rights Test (`test_access_rights.py`)

The test `test_access_saleperson` confirms:
- A sales person **can** confirm an SO and trigger PO creation (via `sudo()`).
- A sales person **cannot** read `purchase_line_ids` on their own SOL (raises `AccessError`).
- A purchase person **can** read the PO and the SOL's linked PO lines.
- `purchase_order_count` on `sale.order` is only visible to `purchase.group_purchase_user`.
- `sale_order_count` on `purchase.order` is only visible to `sales_team.group_sale_salesman`.

### Record Rules

No `ir.rule` is defined by this module. Cross-model access is governed by the standard `sale` and `purchase` record rules. The `sudo()` calls deliberately bypass those rules at specific, intentional points.

### `is_expense` Guard

```python
# In SaleOrderLine.create():
lines.filtered(
    lambda line: line.state == 'sale' and not line.is_expense
)._purchase_service_generation()
```

SOLs with `is_expense = True` (expense SOs created from vendor bills) skip PO generation because the product is already delivered/invoiced by the vendor. Generating a PO for an already-received expense would double-count the cost.

---

## Performance Implications

### `_purchase_service_create()` — loop without batch

```python
for line in self:
    line = line.with_company(line._purchase_service_get_company())
    supplierinfo = line._purchase_service_match_supplier()
    ...
```

When confirming a large SO with many SOLs, each SOL is processed sequentially with its own `with_company()` call and individual `search()` calls for PO matching. For N SOLs, this can result in O(N) database queries. Batching the PO lookup and creation per (vendor, company, SO) tuple would reduce this.

### `_purchase_service_match_purchase_order` — unsoptimized search

```python
return self.env['purchase.order.line'].search(
    Domain.AND([...]),
    order='order_id',
    limit=1,
).order_id
```

The `order='order_id'` forces sorting on the PO ID. Combined with `limit=1`, this is a minor overhead but unnecessary since any matching draft PO is equivalent. Removing the `order` clause would avoid the sort.

### `_compute_purchase_count` — `_read_group` vs. `search_count`

Using `_read_group` with `sudo()` is the right choice here over a direct SQL or `search_count`, because it correctly groups by `sale_line_id` in a single pass. However, for very large datasets, the `sudo()` access could be a concern.

### `index='btree_not_null'` on `sale_line_id`

This is an optimization. A standard btree index includes NULL values, but since `sale_line_id` is NULL for most PO lines (only PO lines created from `sale_purchase` have it set), the partial index `WHERE sale_line_id IS NOT NULL` is significantly smaller. Query performance on `_purchase_service_match_purchase_order` and the PO form's SO count badge benefits from this.

---

## Multi-Company Behavior

### `service_to_purchase` Per-Company

Because the field is `company_dependent=True`, the same product has independent `service_to_purchase` values per company. The test `test_service_to_purchase_multi_company` demonstrates this with `company_1` having the flag True and `company_2` having it False.

The check uses `product_id.with_company(self._purchase_service_get_company()).service_to_purchase`, which evaluates the property against the SOL's company (not the current user's company).

### Branch / Subsidiary Tax Propagation

`test_service_to_purchase_branch_tax_propagation` verifies that when a branch company (with `parent_id`) is used, the PO correctly picks up the root company's supplier taxes (`supplier_taxes_id`). The filtering:
```python
supplier_taxes = self.product_id.supplier_taxes_id.filtered(
    lambda t: t.company_id in purchase_order.company_id.parent_ids)
```
ensures taxes from any ancestor company are included, not just the immediate branch.

---

## Extension Points

All key methods are designed to be overridable. The module follows the Odoo "template method" pattern.

| Method | Location | Purpose | Override use case |
|--------|----------|---------|-------------------|
| `_purchase_service_get_company()` | `sale_order_line.py` | Returns company for PO creation | Multi-company routing |
| `_retrieve_purchase_partner()` | `sale_order_line.py` | Returns forced vendor partner | Custom vendor selection |
| `_purchase_service_match_supplier()` | `sale_order_line.py` | Selects supplierinfo record | Custom supplier ranking |
| `_purchase_service_match_purchase_order()` | `sale_order_line.py` | Finds existing draft PO | Different grouping rules |
| `_purchase_service_prepare_order_values()` | `sale_order_line.py` | PO header values | Add custom fields to PO |
| `_purchase_service_prepare_line_values()` | `sale_order_line.py` | PO line values | Add custom fields to POL |
| `_purchase_service_get_price_unit_and_taxes()` | `sale_order_line.py` | Computes cost price | Dynamic pricing |
| `_purchase_get_date_order()` | `sale_order_line.py` | PO date_order scheduling | Custom lead time |
| `_get_additional_domain_for_purchase_order_line()` | `sale_order_line.py` | Extra domain for PO match | Cross-SO PO sharing |
| `_check_vendor_for_service_to_purchase()` | `product_template.py` | Vendor existence check | Custom vendor validation |
| `_compute_dest_address_id()` | `purchase_order.py` | PO destination address | Dropship routing |

---

## Edge Cases

### SOL created in `sale` state (already confirmed)

```python
# In SaleOrderLine.create():
lines.filtered(
    lambda line: line.state == 'sale' and not line.is_expense
)._purchase_service_generation()
```

When a SOL is created programmatically in `state='sale'` (e.g., during an import or via a workflow), PO generation fires immediately on `create()`. This means SO confirmation can be simulated by directly writing `state = 'sale'` on a SOL — but this bypasses the `_action_confirm` hook on `sale.order`.

### UoM mismatch between SOL and vendor

```python
purchase_qty_uom = self.product_uom_id._compute_quantity(
    product_quantity, self.product_id.uom_id)
# ... then later ...
if supplierinfo.product_uom_id != self.product_id.uom_id:
    purchase_qty_uom = self.product_id.uom_id._compute_quantity(
        purchase_qty_uom, supplierinfo.product_uom_id)
```

Two-step conversion handles the case where SOL UoM, product default UoM, and vendor UoM are all different (e.g., SOL="hours", product default="days", vendor="weeks").

### SO → PO name in origin field

```python
origins = (purchase_order.origin or '').split(', ')
if so_name not in origins:
    purchase_order.write({'origin': ', '.join(origins + [so_name])})
```

Avoids duplicating SO names in `origin` if a SOL's PO is regenerated (re-confirm scenario). The split-on-comma is fragile if SO names contain commas — this is a known minor edge case.

### Delta-only PO line for confirmed PO

When a confirmed PO's quantity is increased, the new PO line's `product_qty` is the **delta** (new_total - original), not the new total. This means the PO will have two lines with quantities that sum to the current SOL qty. Invoice matching must account for this.

### Custom product attributes on SOL → PO

```python
line_description = self.with_context(
    lang=self.order_id.partner_id.lang)._get_sale_order_line_multiline_description_variants()
if line_description:
    name += line_description
```

Custom attribute values (e.g., "Color: Blue") from the SOL are appended to the PO line name, so the vendor can see exactly which variant was ordered. Tested in `test_pol_custom_attribute`.

### No activity on SO for quantity decrease

Unlike quantity decrease on PO (which creates an activity on the PO), when the SO quantity is decreased, only a PO activity is created — no activity is placed on the SO itself. The sale person already knows about the change.

---

## Odoo 18 → 19 Changes

| Area | Change | Impact |
|------|--------|--------|
| `service_to_purchase` field | `company_dependent=True` was present in Odoo 18; behavior fully established in 19 | Multi-company is a first-class concern |
| `Domain.AND()` usage | In `_purchase_service_match_purchase_order`, uses `Domain.AND()` from `odoo.fields` | More explicit domain composition, safer than nested lists |
| `index='btree_not_null'` on `sale_line_id` | Partial index added | Performance improvement for PO line queries |
| `relativedelta` from `dateutil` | Used for date arithmetic (`date_order - delay days`) | Consistent with purchase module patterns |
| `mail.activity` template rendering | Uses `render_context` dict pattern | Standard Odoo 17+ activity scheduling |
| `is_expense` guard | Present in create hook | Prevents duplicate PO for expense-annotated SOLs |

---

## File Structure

```
sale_purchase/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── product_template.py    # service_to_purchase field + constraints
│   ├── sale_order_line.py     # PO generation engine (largest file)
│   ├── sale_order.py          # _action_confirm hook, SO-level fields
│   └── purchase_order.py      # PO-level fields, SO count, cancel hook
├── views/
│   ├── product_views.xml      # service_to_purchase checkbox in product form
│   ├── sale_order_views.xml   # "Purchase" button on SO form (purchase.group_purchase_user)
│   └── purchase_order_views.xml  # "Sale" button on PO form (sales_team.group_sale_salesman)
├── data/
│   └── mail_templates.xml      # QWeb activity templates (3 exception alerts)
└── tests/
    ├── __init__.py
    ├── common.py               # Test product + vendor setup (2 service products)
    ├── test_sale_purchase.py   # 8 test cases covering core flows
    └── test_access_rights.py   # 1 test case for ACL boundaries
```

---

## See Also

- [[Modules/sale]] — Base `sale.order` model
- [[Modules/purchase]] — Base `purchase.order` model
- [[Modules/sale_expense]] — Vendor bill reinvoicing via SO (different from `sale_purchase`)
- [[Modules/sale_timesheet]] — Time-based service billing (may coexist with `sale_purchase`)
- [[Modules/project]] — Project/task management for delivered services
- [[Core/API]] — `@api.depends`, `@api.onchange`, `@api.constrains` decorators used throughout
- [[Patterns/Workflow Patterns]] — State machine pattern on `sale.order`, `purchase.order`
