---
Module: event_booth_sale
Version: Odoo 18
Type: Integration
Tags: #odoo #odoo18 #event #booth #sale #crm
---

# event_booth_sale — Event Booth Sales

**Module:** `event_booth_sale`
**Addon Path:** `odoo/addons/event_booth_sale/`
**Depends:** `event_booth`, `event_sale`
**Category:** Marketing/Events
**Auto-install:** Yes
**License:** LGPL-3

Enables selling physical or virtual booths at events through the sale order workflow. Booths are linked to `product.product` with `service_tracking='event_booth'`. When a sale order is confirmed (or its invoice is paid), booth registrations are automatically created and the booth's state is set to `unavailable`.

---

## Dependency Chain

```
event
  event.event
  event.event.ticket        (event_sale dependency)
  event.registration        (event_sale dependency)
  event.booth               ← core booth model (event_booth)
  event.booth.category      ← booth category (event_booth)
  event.type.booth          ← booth template (event_booth)

event_sale
  sale.order                + attendee_count, event_id→registration sync
  sale.order.line           + event_id, event_ticket_id, registration_ids

event_booth
  event.booth               + state=available/unavailable, partner_id
  event.booth.category      + image, description, sequence
  event.type.booth          + name, booth_category_id

event_booth_sale (THIS MODULE)
  event.booth               + sale_order_line_id, sale_order_id, is_paid
  event.booth.category      + product_id, price, price_incl, price_reduce
  sale.order                + event_booth_ids, event_booth_count
  sale.order.line           + event_booth_*, is_event_booth
  event.type.booth          + product_id, price (from category)
  event.booth.registration  ← NEW MODEL: links SO line to booth
  account.move              + invoice_paid_hook triggers booth confirmation
  product.product           + onchange: invoice_policy='order' if event_booth
  product.template          + service_tracking option: 'event_booth'
```

---

## New Model: `event.booth.registration`

**File:** `models/event_booth_registration.py`
**Inherits:** None (stand-alone)
**Description:** A join table between `sale.order.line` and `event.booth` that enables multiple partners to reserve the same booth (pending state) before payment. When one partner pays, the others are cancelled.

#### Fields

| Field | Type | Relation | Description |
|-------|------|----------|-------------|
| `sale_order_line_id` | Many2one | `sale.order.line` | Required. Ondelete: `cascade`. The SO line that initiated the booth reservation. |
| `event_booth_id` | Many2one | `event.booth` | Required. The booth being reserved. |
| `partner_id` | Many2one | `res.partner` | Related to `sale_order_line_id.order_partner_id`. `store=True`. |
| `contact_name` | Char | — | Computed from `partner_id.name`, writable. |
| `contact_email` | Char | — | Computed from `partner_id.email`, writable. |
| `contact_phone` | Char | — | Computed from `partner_id.phone` or `mobile`, writable. |

#### SQL Constraints

```python
_sql_constraints = [
    ('unique_registration', 'unique(sale_order_line_id, event_booth_id)',
     'There can be only one registration for a booth by sale order line')
]
```

Enforces one registration record per (SO line, booth) pair.

#### Methods

**`_compute_contact_name/email/phone()`** — `api.depends('partner_id')`
- Auto-fills contact fields from `partner_id` if not already set
- Because `readonly=False`, these can be manually overridden per registration

**`_get_fields_for_booth_confirmation()`** — `api.model`
- Returns `['sale_order_line_id', 'partner_id', 'contact_name', 'contact_email', 'contact_phone']`
- Used by `action_confirm()` to extract field values to pass to `event_booth.action_confirm()`

**`action_confirm()`** — `api.multi`

```python
def action_confirm(self):
    for registration in self:
        values = {
            field: registration[field].id if isinstance(registration[field], models.BaseModel) else registration[field]
            for field in self._get_fields_for_booth_confirmation()
        }
        registration.event_booth_id.action_confirm(values)
    self._cancel_pending_registrations()
```

1. Extracts contact info from the registration
2. Calls `event_booth.action_confirm(values)` which sets `state='unavailable'` + partner info on the booth
3. Calls `_cancel_pending_registrations()` to cancel competing registrations

**`_cancel_pending_registrations()`** — `api.multi`

```python
def _cancel_pending_registrations(self):
    body = Markup('<p>%(message)s: <ul>%(booth_names)s</ul></p>') % {...}
    other_registrations = self.search([
        ('event_booth_id', 'in', self.event_booth_id.ids),
        ('id', 'not in', self.ids)
    ])
    for order in other_registrations.sale_order_line_id.order_id:
        order.sudo().message_post(body=body, partner_ids=order.user_id.partner_id.ids)
        order.sudo()._action_cancel()
    other_registrations.unlink()
```

- Finds all other pending registrations for the same booths
- Posts a cancellation message to the sales order's chatter
- Cancels the sale order via `_action_cancel()`
- Deletes the orphaned registration records

---

## Models Extended

### `event.booth` — Event Booth (EXTENDED)

Inherits from `event.booth.event.booth` (`event_booth/models/event_booth.py`), which inherits from `event.type.booth`.

#### Fields Added

| Field | Type | Relation | Description |
|-------|------|----------|-------------|
| `event_booth_registration_ids` | One2many | `event.booth.registration` → `event_booth_id` | Pending/reserved booth registrations |
| `sale_order_line_registration_ids` | Many2many | `sale.order.line` (via `event_booth_registration` link table) | All SO lines with reservations for this booth. Groups: `sales_team.group_sale_salesman` |
| `sale_order_line_id` | Many2one | `sale.order.line` | **Final confirmed** SO line. Set when the booth is fully booked (paid). Ondelete: `set null`. |
| `sale_order_id` | Many2one | `sale.order` | Related to `sale_order_line_id.order_id`. `store=True`. Groups: `sales_team.group_sale_salesman`. |
| `is_paid` | Boolean | — | Set to `True` when invoice is paid. `copy=False`. |

#### Constraints

**`_unlink_except_linked_sale_order()`** — `@api.ondelete(at_uninstall=False)`

```python
def _unlink_except_linked_sale_order(self):
    booth_with_so = self.sudo().filtered('sale_order_id')
    if booth_with_so:
        raise UserError(_("You can't delete the following booths as they are linked to sales orders: %(booths)s", ...))
```

Prevents booth deletion if a confirmed sale order is linked. The booth must first be freed (SO cancelled or booth released).

#### Methods

**`action_set_paid()`** — `api.multi`
- Writes `is_paid = True` on the booth
- Called by `account.move._invoice_paid_hook()` when the invoice is paid

**`action_view_sale_order()`** — `ir.actions`
- Returns a form action to open the linked `sale.order`

**`_get_booth_multiline_description()`** — inherited from `event_booth` but extended in this module to include event context

```python
def _get_booth_multiline_description(self):
    return '%s : \n%s' % (
        self.event_id.display_name,
        '\n'.join(['- %s' % booth.name for booth in self])
    )
```

---

### `event.booth.category` — Booth Category (EXTENDED)

Inherits from `event.booth.category` (`event_booth/models/event_booth_category.py`). Groups booths by type and links them to a product for pricing.

#### Fields Added / Overridden

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one `product.product` | **Required.** Domain: `service_tracking == 'event_booth'`. Groups: `event.group_event_registration_desk`. Defaults to `product_product_event_booth`. |
| `price` | Float | **Compute** from `product_id.list_price + product_id.price_extra`. `store=True`. Groups: registration desk. |
| `price_incl` | Float (computed) | Price including taxes. |
| `price_reduce` | Float (computed) | Price after contextual discount. `compute_sudo=True`. Groups: registration desk. |
| `price_reduce_taxinc` | Float (computed) | Price after discount, tax included. `compute_sudo=True`. |
| `currency_id` | Many2one `res.currency` | Related to `product_id.currency_id`. |
| `image_1920` | Image | Computed: falls back to product image if no category image is set. |

#### Methods

**`_compute_price()`** — `api.depends('product_id')`
- `price = product_id.list_price + product_id.price_extra` (price extra is variants-based extra price)

**`_compute_price_incl()`** — `api.depends('product_id', 'product_id.taxes_id', 'price')`
- `taxes.compute_all(price, currency, 1.0, product)` → `total_included`

**`_compute_price_reduce()`** — `api.depends('product_id', 'price')` + `PRICE_CONTEXT_KEYS`
- Uses `product_id._get_contextual_discount()` for pricelist-aware pricing

**`_compute_price_reduce_taxinc()`** — `api.depends('product_id', 'price_reduce')`
- Same tax computation as `price_incl` but applied to `price_reduce`

**`_compute_image_1920()`** — `api.depends('product_id')`
- Falls back to `product_id.image_1920` if no category image is set

**`_init_column(column_name)`** — Migration helper
- Creates a generic "Generic Event Booth Product" with `service_tracking='event_booth'`, `invoice_policy='order'`, `list_price=100` if no default product exists
- Backfills null `product_id` columns

---

### `sale.order` — Sale Order (EXTENDED)

Inherits from `sale.sale.order` (from `sale`).

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `event_booth_ids` | One2many | `event.booth` → `sale_order_id`. Aggregates all confirmed booths linked to this SO. |
| `event_booth_count` | Integer (computed) | Count of `event_booth_ids`. `_compute_event_booth_count`. |

#### Methods

**`_compute_event_booth_count()`** — `api.depends('event_booth_ids')`
- Uses `_read_group` on `event.booth` for efficient count

**`action_confirm()`** — Override

```python
def action_confirm(self):
    res = super().action_confirm()
    for so in self:
        if not any(line.service_tracking == 'event_booth' for line in so.order_line):
            continue
        so_lines_missing_booth = so.order_line.filtered(
            lambda line: line.service_tracking == 'event_booth' and not line.event_booth_pending_ids
        )
        if so_lines_missing_booth:
            raise ValidationError(_("Please make sure all your event-booth related lines are configured before confirming this order:..."))
        so.order_line._update_event_booths()
    return res
```

- Validates that all booth SO lines have at least one pending booth selected
- Calls `sale.order.line._update_event_booths()` to confirm booths and create `event.booth.registration` records

**`action_view_booth_list()`** — `ir.actions`
- Opens the list view of `event.booth` filtered to this SO

**`_get_product_catalog_domain()`** — Override

```python
def _get_product_catalog_domain(self):
    domain = super()._get_product_catalog_domain()
    return expression.AND([domain, [('service_tracking', '!=', 'event_booth')]])
```

- Hides `service_tracking == 'event_booth'` products from the standard product picker on the SO
- Booths are selected via a dedicated event booth configurator wizard instead

---

### `sale.order.line` — Sale Order Line (EXTENDED)

Inherits from `sale.order.line` (`event_sale/models/sale_order_line.py`), which already extends with `event_id`, `event_ticket_id`, `registration_ids`.

#### Fields Added

| Field | Type | Relation | Description |
|-------|------|----------|-------------|
| `event_booth_category_id` | Many2one | `event.booth.category` | Ondelete: `set null`. Allows filtering/categorizing booth lines. |
| `event_booth_pending_ids` | Many2many | `event.booth` | Selected booths in "pending" (reserved) state. Managed via `_inverse_event_booth_pending_ids`. |
| `event_booth_registration_ids` | One2many | `event.booth.registration` → `sale_order_line_id` | Confirmed registration records linking this SO line to booths. |
| `event_booth_ids` | One2many | `event.booth` → `sale_order_line_id` | Confirmed booths (those with `state='unavailable'` and a confirmed SO). |
| `is_event_booth` | Boolean (computed) | `product_id.service_tracking == 'event_booth'` |

#### Methods

**`_compute_is_event_booth()`** — `api.depends('product_id.type')`
- Checks if the product's `service_tracking == 'event_booth'`

**`_compute_event_booth_pending_ids()`** — `api.depends('event_booth_registration_ids')`
- `event_booth_pending_ids = event_booth_registration_ids.event_booth_id`
- Reflects confirmed registrations (not just the SO line's pending booth selection)

**`_inverse_event_booth_pending_ids()`** — `api.multi` (write-through inverse)

```python
def _inverse_event_booth_pending_ids(self):
    for so_line in self:
        existing_booths = so_line.event_booth_registration_ids.event_booth_id or self.env['event.booth']
        selected_booths = so_line.event_booth_pending_ids

        # Unlink registrations for de-selected booths
        so_line.event_booth_registration_ids.filtered(
            lambda reg: reg.event_booth_id not in selected_booths).unlink()

        # Create registrations for newly-selected booths
        self.env['event.booth.registration'].create([{
            'event_booth_id': booth.id,
            'sale_order_line_id': so_line.id,
            'partner_id': so_line.order_id.partner_id.id
        } for booth in selected_booths - existing_booths])
```

- Called when the user changes `event_booth_pending_ids` on the SO line (e.g., in the booth configurator wizard)
- Maintains `event_booth_registration_ids`: creates new registrations for added booths, deletes for removed ones
- Each `event.booth.registration` is created with `partner_id = so_line.order_id.partner_id`

**`_search_event_booth_pending_ids(operator, value)`** — `api.model`
- Enables `domain` filtering on the computed `Many2many` field

**`_check_event_booth_registration_ids()`** — `@api.constrains`
- Raises `ValidationError` if registrations on the same SO line belong to more than one event
- All booths on a single SO line must be from a single event

**`_onchange_product_id_booth()`** — `@api.onchange('product_id')`
- If the product changes to one not in the current pending booths, clears `event_id`

**`_onchange_event_id_booth()`** — `@api.onchange('event_id')`
- If the event changes, clears pending booths (booths are event-specific)

**`_compute_name()`** — Override
- Adds dependency on `event_booth_pending_ids` (normally handled by `_get_sale_order_line_multiline_description_sale`)

**`_update_event_booths(set_paid=False)`** — `api.multi`

```python
def _update_event_booths(self, set_paid=False):
    for so_line in self.filtered('is_event_booth'):
        if so_line.event_booth_pending_ids and not so_line.event_booth_ids:
            unavailable = so_line.event_booth_pending_ids.filtered(lambda booth: not booth.is_available)
            if unavailable:
                raise ValidationError(_("The following booths are unavailable: %(booth_names)s", ...))
            so_line.event_booth_registration_ids.sudo().action_confirm()
        if so_line.event_booth_ids and set_paid:
            so_line.event_booth_ids.sudo().action_set_paid()
    return True
```

- Called by `sale.order.action_confirm()` (SO confirmation) or `account.move._invoice_paid_hook()` (invoice payment)
- Confirms pending booth registrations via `action_confirm()` → sets booths to `unavailable`
- When `set_paid=True` (invoice paid): marks booths as paid via `action_set_paid()`

**`_get_sale_order_line_multiline_description_sale()`** — Override
- If `event_booth_pending_ids` is set, returns `event_booth_pending_ids._get_booth_multiline_description()` (the event + booth names)
- Otherwise falls through to the parent (ticket) description

**`_use_template_name()`** — Override
- Returns `False` if `event_booth_pending_ids` is set (prevents template description from overwriting the booth-specific description)

**`_get_display_price()`** — Override

```python
def _get_display_price(self):
    if self.event_booth_pending_ids and self.event_id:
        company = self.event_id.company_id or self.env.company
        if not self.pricelist_item_id._show_discount():
            event_booths = self.event_booth_pending_ids.with_context(...)
            total_price = sum(booth.booth_category_id.price_reduce for booth in event_booths)
        else:
            total_price = sum(booth.price for booth in self.event_booth_pending_ids)
        return self._convert_to_sol_currency(total_price, company.currency_id)
    return super()._get_display_price()
```

- Computes total display price for booth lines as the sum of booth prices (from category)
- Supports both discounted (`price_reduce`) and full (`price`) display modes

---

### `event.type.booth` — Event Type Booth Template (EXTENDED)

Inherits from `event.type.booth` (`event_booth/models/event_type_booth.py`).

#### Fields Added (All Related)

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one | Related: `booth_category_id.product_id` |
| `price` | Float | Related: `booth_category_id.price`. `store=True`. |
| `currency_id` | Many2one | Related: `booth_category_id.currency_id` |

#### Methods

**`_get_event_booth_fields_whitelist()`** — `api.model`
- Returns `['name', 'booth_category_id']` + `['product_id', 'price']`
- Extends parent whitelist so `product_id` and `price` are copied from the event type booth template to the event booth

---

### `account.move` — Account Move / Invoice (EXTENDED)

Inherits from `account.move`.

#### Methods

**`_invoice_paid_hook()`** — `api.returns('account.move')`

```python
def _invoice_paid_hook(self):
    res = super()._invoice_paid_hook()
    self.mapped('line_ids.sale_line_ids')._update_event_booths(set_paid=True)
    return res
```

- Called by `account.payment`'s `_reconcile_payment_lines()` when an invoice is fully paid
- Maps all `sale_line_ids` from the invoice's move lines
- Calls `_update_event_booths(set_paid=True)` which confirms pending registrations and marks booths as paid
- This is the key integration point: **booths are booked when the invoice is paid**, not when the SO is confirmed

---

## L4: Booth Reservation and Invoicing Flow

```
Step 1: SO Creation
  sale.order.line (service_tracking='event_booth')
    └─ event_booth_pending_ids = [booth_A, booth_B]   [user selects booths via wizard]
          └─ event_booth_registration.create() for each booth
                └─ partner_id = so_line.order_partner_id
                └─ state: pending (not yet on event.booth)

Step 2: SO Confirmation
  sale.order.action_confirm()
    └─ _update_event_booths()
          └─ event_booth_registration.action_confirm()
                └─ event.booth.action_confirm(values)
                      └─ booth.state = 'unavailable'
                      └─ booth.partner_id = partner
                      └─ booth.sale_order_line_id = so_line
                └─ _cancel_pending_registrations()
                      └─ cancels + unlinks competing registrations
                      └─ cancels competing SOs

Step 3: Invoice Creation & Payment
  account.move.create() from sale.order
    └─ account.payment created
          └─ _reconcile_payment_lines()
                └─ _invoice_paid_hook()
                      └─ sale.order.line._update_event_booths(set_paid=True)
                            └─ booth.action_set_paid()
                                  └─ booth.is_paid = True
```

### Key Design Decision: Booth Booked on Invoice Payment

Unlike ticket registrations (which are created on SO confirmation via `event_sale`), booths are only confirmed when:
1. The SO is confirmed (booths become `unavailable`, partner assigned)
2. The invoice is paid (booths become `is_paid = True`)

This models the real-world behavior where a booth reservation is held but not fully confirmed until payment. The `event.booth.registration` acts as a "tentative hold" during the pending phase.

### Multiple Registrations per Booth

The `event.booth.registration` model allows multiple pending registrations for the same booth from different SO lines (different partners). The `action_confirm()` call by the first paying customer triggers `_cancel_pending_registrations()`, which cancels and unlinks all other pending registrations and cancels their SOs.

---

## See Also

- [Core/API](core/api.md) — @api.depends, @api.onchange, @api.constrains
- `event_booth` — base booth management
- `event_sale` — event ticket sales (sale order integration)
- `event_crm_sale` — CRM lead creation from event registrations
