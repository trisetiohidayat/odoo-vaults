# event_sale — Events Sales

> Bridges the event management and sale order flows. Confirms a sale order containing event-ticket products automatically creates `event.registration` records, propagating UTM data and syncing attendee state with the SO lifecycle.

**Category:** Marketing/Events  
**Depends:** `event_product`, `sale_management`  
**Auto-install:** True (when `event` and `sale` are both present)  
**Author:** Odoo S.A.  
**License:** LGPL-3  
**Module root:** `odoo/addons/event_sale/`

---

## Module Dependency Chain

```
event
  ├── event_product         ← adds product_id to event.event.ticket
  │                          adds service_tracking = 'event' selection to product.template
  └── sale_management
        └── event_sale      ← orchestrates SO confirmation → registration creation
```

`event_sale` does **not** depend on `website_sale` — that dependency lives in `website_event_sale`. Both can be installed independently.

---

## File Inventory

| File | Kind | Purpose |
|---|---|---|
| `__manifest__.py` | Manifest | Module metadata, depends, data files, assets |
| `__init__.py` | Bootstrap | Imports `models`, `report`, `wizard` submodules |
| `models/__init__.py` | Bootstrap | Imports 6 model files |
| `models/event_registration.py` | Model | Extends `event.registration` with SO linkage, UTM, state compute |
| `models/event_event.py` | Model | Extends `event.event` with sales analytics fields |
| `models/event_ticket.py` | Model | Extends `event.event.ticket` description override |
| `models/sale_order.py` | Model | Extends `sale.order` with event confirmation flow |
| `models/sale_order_line.py` | Model | Extends `sale.order.line` with event/ticket binding |
| `models/product_template.py` | Model | Extends `product.template` tooltip + onchange |
| `wizard/event_configurator.py` | Wizard | Configures product + event + ticket before SO creation |
| `wizard/event_edit_registration.py` | Wizard | `registration.editor` + `registration.editor.line` — fills attendee details |
| `report/event_sale_report.py` | Report | Auto-created SQL view for sales analysis |
| `security/ir.model.access.csv` | Security | ACL grants for wizard models, implied group |
| `security/ir_rule.xml` | Security | Multi-company record rule on `event_sale_report` |
| `security/event_security.xml` | Security | Implied group: salesmen gain event registration desk |
| `data/event_sale_data.xml` | Data | Sets `invoice_policy = 'order'` on default event product |
| `data/mail_templates.xml` | Data | Activity template for ticket/slot change notifications |

---

## Models

### `event.event` — extended (`models/event_event.py`)

Extends `event.event` with a read-only sales analytics field and a navigation action into confirmed orders.

#### `sale_order_lines_ids` — `One2many('sale.order.line', 'event_id')`

Groups: `sales_team.group_sale_salesman` only.

All SO lines (from any SO in any state) that point to this event via `event_id`. The `state` filter is applied only in `_compute_sale_price_total`, not here. This field is a pure reverse lookup — it accumulates lines from draft, sent, and sale SOs alike.

#### `sale_price_total` — `Monetary`, computed, store=False

Groups: `sales_team.group_sale_salesman` only.

```python
@api.depends('company_id.currency_id',
             'sale_order_lines_ids.price_total', 'sale_order_lines_ids.currency_id',
             'sale_order_lines_ids.company_id', 'sale_order_lines_ids.order_id.date_order')
def _compute_sale_price_total(self):
```

**Logic:** Runs a `_read_group` on `sale.order.line` filtered to `event_id in self.ids`, `state = 'sale'`, `price_total != 0`. For each `(event, currency)` group, converts `sum(price_total)` to the event's `company_id.currency_id` using `fields.Datetime.now()` (today's) rate. The per-group conversion handles multi-currency correctly: all lines in the same currency are summed first, then converted once.

**Performance design decision:** Odoo deliberately uses today's rate instead of the rate at the time each SO was created. Historical rate lookups would require one currency-conversion API call per distinct SO currency — and since every single ticket sold typically creates its own SO, this would be thousands of calls for a popular event. The trade-off is that the reported total drifts with exchange rate fluctuations; it is a point-in-time figure, not an audit-certain sum.

#### `action_view_linked_orders()` → `ir.actions.act_window`

Returns `sale.action_orders` with:
- `domain`: `[('state', '=', 'sale'), ('order_line.event_id', 'in', self.ids)]` — only confirmed orders
- `context`: `{'create': 0}` — prevents creating new SOs from this action

---

### `event.registration` — extended (`models/event_registration.py`)

Extends the base `event.registration` with bidirectional SO linkage, UTM propagation, sale-status tracking, and mail scheduler triggering on confirmation.

#### Field Definitions

| Field | Type | Args | Purpose |
|---|---|---|---|
| `sale_order_id` | `Many2one` | `ondelete='cascade'`, `copy=False` | Points back to the originating SO. Cascade-delete: if the SO row is deleted, registrations are deleted too. `copy=False` prevents registration duplication when the SO line is duplicated. |
| `sale_order_line_id` | `Many2one` | `ondelete='cascade'`, `index='btree_not_null'` | Points to the specific SO line. `btree_not_null` index excludes NULLs (SO lines without events) for compact, efficient filtered searches. |
| `state` | `Selection` | `default=None`, `compute`, `store`, `precompute`, `readonly=False` | Overrides the parent field (`default='draft'`). Starts as `None` so `_compute_registration_status` can set it correctly without fighting an ORM default. Precomputed to guarantee the field is always populated. |
| `utm_campaign_id` | `Many2one` | `compute`, `store`, `readonly=False`, `ondelete='set null'` | Propagated from `sale_order_id.campaign_id`. |
| `utm_source_id` | `Many2one` | same pattern | Propagated from `sale_order_id.source_id`. |
| `utm_medium_id` | `Many2one` | same pattern | Propagated from `sale_order_id.medium_id`. |

#### `_has_order()` — override

```python
def _has_order(self):
    return super()._has_order() or self.sale_order_id
```

Both the parent `event.registration` check (for manually created registrations) and the new SO link are evaluated. Used by the event app to decide whether to show sale-related UI badges.

#### `_compute_registration_status()` — override

This is the central state machine. It runs on every write to `sale_order_id`, `currency_id`, or `amount_total` of the linked SO.

```python
for sale_order, registrations in self.filtered('sale_order_id').grouped('sale_order_id').items():
```

**Step 1 — Cancelled SO:** Any registration whose SO has `state == 'cancel'` gets `state = 'cancel'` unconditionally.

**Step 2 — Free orders** (`float_is_zero(amount_total)`):
- `sale_status = 'free'`
- Registrations that are unset, draft, or to_pay → `state = 'open'` (immediately confirmed)

**Step 3 — Paid orders** (non-zero total):
- Split: `sold_registrations` = those whose SO has `state == 'sale'` (confirmed SO)
- `sold_registrations`: `sale_status = 'sold'`; if unset/draft/cancel → `state = 'open'` (trigger confirmation emails via `_compute_field_value`)
- Non-sold registrations (sent, draft, etc.): `sale_status = 'to_pay'`; state remains unset/draft

**Step 4 — Call `super()`:** Lets the parent apply its own state logic (e.g., handling manually created registrations not linked to any SO).

**Step 5 — Orphan fallback:** Registrations with no `sale_order_id` that reach the end of the loop without a `sale_status` get `sale_status = 'free'` and `state = 'open'`.

#### `_compute_utm_*_id()` — three methods

Each UTM field follows the same pattern:
```python
if registration.sale_order_id.{utm_field}:
    registration.utm_{field} = registration.sale_order_id.{utm_field}
elif not registration.utm_{field}:  # only clear if currently unset
    registration.utm_{field} = False
```

The `elif not registration.utm_field` guard is key: it preserves externally-set UTM values when the SO link is broken. Setting to `False` only when the field is currently unset avoids overwriting an intentional manual attribution.

#### `create(vals_list)` — override

For each vals dict that has a `sale_order_line_id`:
1. Calls `_synchronize_so_line_values(browse(vals['sale_order_line_id']))` to inject all linkage fields.
2. After super-create, if `sale_order_id` is set, posts a `mail.message_origin_link` note linking the registration to its SO.

The `sale_order_line_id` is the pivot — if it's present, sync happens. If not (e.g., manual creation from the event app), no sync occurs.

#### `write(vals)` — override

Two side effects on write:

1. **SO-line sync:** If `sale_order_line_id` is in `vals`, call `_synchronize_so_line_values` to update all linkage fields.

2. **Change notification:** If `event_slot_id` or `event_ticket_id` is being changed, schedule a `mail.mail_activity_data_warning` on the SO:
   ```python
   for registration in self.filtered(lambda r: r[field] and r[field].id != vals[field]):
       registration._sale_order_registration_data_change_notify(field, new_record)
   ```
   The notification is rendered from `event_sale.event_registration_change_exception` template, showing old value, new value, and a "Manual actions may be needed" warning. Responsible user is `event_id.user_id`, falling back to `sale_order_id.user_id`, then `base.user_admin`.

#### `_synchronize_so_line_values(so_line)` → `dict`

```python
def _synchronize_so_line_values(self, so_line):
    if so_line:
        return {
            'partner_id': False if self.env.user._is_public()
                           and self.env.user.partner_id == so_line.order_id.partner_id
                           else so_line.order_id.partner_id.id,
            'event_id': so_line.event_id.id,
            'event_slot_id': so_line.event_slot_id.id,
            'event_ticket_id': so_line.event_ticket_id.id,
            'sale_order_id': so_line.order_id.id,
            'sale_order_line_id': so_line.id,
        }
    return {}
```

**Public-user exception:** If the current user is public AND their partner matches the SO's partner (typical in website guest checkout), `partner_id` is set to `False` instead of the partner ID. This prevents registering the anonymous public contact. Portal users are not `_is_public()` and follow normal flow.

#### `_compute_field_value(field)` — override

Intercepts writes to the `state` field. When `state` transitions to `'open'` (confirmed) on a registration that was previously `draft` or `cancel`, calls `_update_mail_schedulers()` to fire any waiting email triggers (confirmation emails, reminder emails) at the moment of confirmation — not at SO creation time. This decouples the email timing from the sales flow.

#### `_get_registration_summary()` — override

Extends the parent summary dict with:
- `sale_status`: the current `sale_status` value
- `sale_status_value`: human-readable label from `selection` description
- `has_to_pay`: boolean (`sale_status == 'to_pay'`)

#### `_get_event_registration_ids_from_order()` → `list[int]`

```python
def _get_event_registration_ids_from_order(self):
    return self.sale_order_id.order_line.filtered(
        lambda line: line.event_id == self.event_id
    ).registration_ids.ids
```

Returns all registration IDs on the same SO that belong to the same event. Used by the event app for "group registration" operations (e.g., cancelling all attendees from one event in one order).

#### `action_view_sale_order()` → `ir.actions.act_window`

Opens the linked `sale.order` in form view using `sale.action_orders`.

---

### `event.event.ticket` — extended (`models/event_ticket.py`)

Extends `event.event.ticket` (from `event_product`) to give product sale descriptions priority in SO line descriptions.

#### `_get_ticket_multiline_description()` — override

```python
def _get_ticket_multiline_description(self):
    self.ensure_one()
    if self.product_id.description_sale:
        return '%s\n%s' % (self.product_id.description_sale, self.event_id.display_name)
    return super()._get_ticket_multiline_description()
```

If a sale description is set on the ticket's linked product, that description is returned (appended with the event display name), superseding the ticket's own name. This allows event organizers to write rich, formatted ticket descriptions for the SO confirmation email and order document. HTML in `description_sale` is stripped by the ORM before display.

---

### `sale.order` — extended (`models/sale_order.py`)

Extends `sale.order` with event-specific confirmation logic, attendee counting, and catalog exclusion.

#### `attendee_count` — `Integer`, computed, store=False

```python
def _compute_attendee_count(self):
    sale_orders_data = self.env['event.registration']._read_group(
        [('sale_order_id', 'in', self.ids), ('state', '!=', 'cancel')],
        ['sale_order_id'], ['__count'],
    )
```

Uses `_read_group` on `event.registration` (not `event_sale` models). Counts only non-cancelled registrations. The count includes draft-state registrations (from unpaid SOs), open registrations, and done registrations. Excludes only cancelled ones.

#### `write(vals)` — override

If `partner_id` is being changed AND any line has `service_tracking == 'event'`:
```python
registrations_toupdate = self.env['event.registration'].sudo().search(
    [('sale_order_id', 'in', self.ids)]
)
registrations_toupdate.write({'partner_id': vals['partner_id']})
```
The `sudo()` is required because the current user (salesperson) may not have direct read rights on all registrations. This handles the website checkout flow where a guest completes as public user then logs in — the registrations follow the now-authenticated partner.

#### `action_confirm()` — override

```python
def action_confirm(self):
    res = super().action_confirm()  # handles stock picking creation

    for so in self:
        if not any(line.service_tracking == 'event' for line in so.order_line):
            continue
        so_lines_missing_events = so.order_line.filtered(
            lambda line: line.service_tracking == 'event' and not line.event_id
        )
        if so_lines_missing_events:
            so_lines_descriptions = "".join(
                f"\n- {so_line_description.name}"
                for so_line_description in so_lines_missing_events
            )
            raise ValidationError(_(
                "Please make sure all your event related lines are configured before confirming this order:%s",
                so_lines_descriptions
            ))
        so.order_line._init_registrations()
        if len(self) == 1:  # single-SO confirmation only
            return self.env['ir.actions.act_window'].with_context(
                default_sale_order_id=so.id
            )._for_xml_id('event_sale.action_sale_order_event_registration')
    return res
```

**Guard:** `so_lines_missing_events` is a last-chance validation — `_check_event_registration_ticket` on the SO line should already catch this. But `action_confirm` can be called in contexts where that constraint may not have fired (e.g., direct API calls).

**Wizard return:** Only returned when `len(self) == 1`. Batch confirmation (e.g., via multi-edit or API) skips the wizard and creates all registrations in `draft` state (handled in `_init_registrations`).

#### `action_view_attendee_list()` → `ir.actions.act_window`

Returns `event.event_registration_action_tree` filtered to `sale_order_id in self.ids`. Shows all registrations regardless of state.

#### `_get_product_catalog_domain()` → `Domain`

```python
def _get_product_catalog_domain(self):
    return super()._get_product_catalog_domain() & Domain('service_tracking', '!=', 'event')
```

Excludes event-ticket products from the product catalog picker (used in the sale app's "Add Product" dialog). Event tickets are selected via the event ticket configurator, not the generic product picker.

---

### `sale.order.line` — extended (`models/sale_order_line.py`)

Extends `sale.order.line` with event binding, automatic registration creation, and ticket-driven pricing.

#### Field Definitions

| Field | Type | Args | Purpose |
|---|---|---|---|
| `event_id` | `Many2one` | `compute`, `store`, `precompute`, `index='btree_not_null'` | Auto-set from product when `service_tracking == 'event'`. `btree_not_null` for the same reason as `sale_order_line_id`: field is nullable, index excludes NULLs. |
| `event_slot_id` | `Many2one` | `compute`, `store`, `precompute` | Auto-set when `event_id` is set and slot belongs to event. Cleared by `_compute_event_related` if it no longer belongs. |
| `event_ticket_id` | `Many2one` | `compute`, `store`, `precompute` | Same as above. Cleared if it does not belong to `event_id`. |
| `is_multi_slots` | `Boolean` | `related='event_id.is_multi_slots'` | Convenience accessor for constraint checks. |
| `registration_ids` | `One2many` | `'event.registration', 'sale_order_line_id'` | Registrations created from this line. Deleting a registration does NOT reduce `product_uom_qty`. |

#### `_compute_event_id()` — trigger on `product_id` change

```python
@api.depends('product_id')
def _compute_event_id(self):
    event_lines = self.filtered(lambda line: line.product_id and line.product_id.service_tracking == 'event')
    (self - event_lines).event_id = False
    for line in event_lines:
        if line.product_id not in line.event_id.event_ticket_ids.product_id:
            line.event_id = False
```

The second check (`product_id not in event_id.event_ticket_ids.product_id`) handles the case where `event_id` was previously set but the product has changed to one not linked to any ticket for that event. In practice, this also fires when `event_id` changes: if `event_id` changes, the old `event_ticket_id` is checked against the new event and cleared via `_compute_event_related`.

#### `_compute_event_related()` — runs after `_compute_event_id`

Clears `event_slot_id` and `event_ticket_id` if they no longer belong to `event_id`. This prevents orphaned references when the event is changed on a line.

#### `_check_event_registration_ticket()` — `@api.constrains`

```python
@api.constrains('event_id', 'event_slot_id', 'event_ticket_id', 'product_id')
def _check_event_registration_ticket(self):
    for so_line in self:
        if so_line.product_id.service_tracking == "event" and (
            not so_line.event_id or
            not so_line.event_ticket_id or
            (so_line.is_multi_slots and not so_line.event_slot_id)
        ):
            raise ValidationError(...)
```

Validates on every `create()` and `write()`. The three-part check is: event required, ticket required, and (if multi-slot) slot required.

#### `_compute_product_uom_readonly()` — override

Sets `product_uom_readonly = True` for all event lines. The unit of measure for event tickets is always the default (units) — seat counts are driven by `product_uom_qty`, not by changing the UoM.

#### `_init_registrations()` — core factory, called from `sale.order.action_confirm()`

```python
def _init_registrations(self):
    registrations_vals = []
    for so_line in self:
        if so_line.service_tracking != 'event':
            continue
        for _count in range(int(so_line.product_uom_qty) - len(so_line.registration_ids)):
            values = {
                'sale_order_line_id': so_line.id,
                'sale_order_id': so_line.order_id.id,
            }
            # When confirming a single SO with non-zero price_total, keep in draft
            if len(self.order_id) == 1 and not so_line.currency_id.is_zero(so_line.price_total):
                values['state'] = 'draft'
            registrations_vals.append(values)
    if registrations_vals:
        self.env['event.registration'].sudo().create(registrations_vals)
```

**Delta creation:** Only creates registrations when `product_uom_qty > existing_registration_count`. Does not delete registrations when qty is reduced.

**State logic:** When `len(self.order_id) == 1` and `price_total != 0`, registrations are created in `state='draft'` — the `registration.editor` wizard is shown immediately so sales staff can fill in attendee details. Free registrations (zero total) skip draft and go directly to `open`.

**Batch confirm:** When confirming multiple SOs at once, `len(self.order_id) > 1` so all registrations are created with default state (`None`, which `_compute_registration_status` resolves based on the free/paid split).

**`sudo()`:** Uses elevated privileges because the confirming user may not have `event.registration` create rights. ACL is granted via the implied group (`group_event_registration_desk`) given to all salesmen.

#### `_get_display_price()` — override

```python
def _get_display_price(self):
    if self.event_ticket_id and self.event_id:
        event_ticket = self.event_ticket_id
        company = event_ticket.company_id or self.env.company
        if not self.pricelist_item_id._show_discount():
            price = event_ticket.with_context(**self._get_pricelist_price_context()).price_reduce
        else:
            price = event_ticket.price
        return self._convert_to_sol_currency(price, company.currency_id)
    return super()._get_display_price()
```

Returns `event_ticket.price` (or `price_reduce` if a discount applies), converted to the SO line's currency. This overrides the product's `lst_price` — the SO always shows the price set on the event ticket.

#### `_get_sale_order_line_multiline_description_sale()` — override

```python
if self.event_ticket_id:
    return self.event_ticket_id._get_ticket_multiline_description() \
        + ('\n%s' % self.event_slot_id.display_name if self.event_slot_id else '') \
        + self._get_sale_order_line_multiline_description_variants()
```

Returns the ticket's multiline description (from `event.event.ticket._get_ticket_multiline_description()`), appending the slot name if applicable, and variant descriptions. Variant descriptions are appended via `_get_sale_order_line_multiline_description_variants()` from the base `sale.order.line`.

#### `_use_template_name()` — override

Returns `False` when `event_ticket_id` is set, preventing the product template's configured name from overwriting the ticket-derived description.

---

### `product.template` — extended (`models/product_template.py`)

#### `_prepare_service_tracking_tooltip()` — override

When `service_tracking == 'event'`, returns: `"Create an Attendee for the selected Event."` (translated). This overrides the generic tooltip for the event tracking mode.

#### `_onchange_type_event()` — `@api.onchange('service_tracking')`

```python
@api.onchange('service_tracking')
def _onchange_type_event(self):
    if self.service_tracking == 'event':
        self.invoice_policy = 'order'
```

Auto-sets `invoice_policy = 'order'`. Event tickets are consumed at order confirmation (the moment registration is created), not at delivery (the event date). Billing at order time ensures revenue recognition aligns with the sales transaction.

---

## Report

### `event.sale.report` — Auto SQL View (`report/event_sale_report.py`)

**`_name = 'event.sale.report'`** — A non-stored model backed by a `CREATE OR REPLACE VIEW` SQL view. Provides a flat, denormalized table for sales analysis.

#### Schema

```sql
CREATE OR REPLACE VIEW event_sale_report AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY event_registration.id) AS id,
        event_registration.id AS event_registration_id,
        event_registration.company_id AS company_id,
        event_registration.event_id AS event_id,
        event_registration.event_slot_id AS event_slot_id,
        event_registration.event_ticket_id AS event_ticket_id,
        event_registration.create_date AS event_registration_create_date,
        event_registration.name AS event_registration_name,
        event_registration.state AS event_registration_state,
        event_registration.active AS active,
        event_registration.sale_order_id AS sale_order_id,
        event_registration.sale_order_line_id AS sale_order_line_id,
        event_registration.sale_status AS sale_status,
        event_event.event_type_id AS event_type_id,
        event_event.date_begin AS event_date_begin,
        event_event.date_end AS event_date_end,
        event_event_ticket.price AS event_ticket_price,
        sale_order.date_order AS sale_order_date,
        sale_order.partner_invoice_id AS invoice_partner_id,
        sale_order.partner_id AS sale_order_partner_id,
        sale_order.state AS sale_order_state,
        sale_order.user_id AS sale_order_user_id,
        sale_order_line.product_id AS product_id,
        -- sale_price = price_total / currency_rate / product_uom_qty
        CASE WHEN product_uom_qty = 0 THEN 0
             ELSE price_total / COALESCE(currency_rate, 1) / product_uom_qty
        END AS sale_price,
        -- same pattern for sale_price_untaxed
        CASE WHEN product_uom_qty = 0 THEN 0
             ELSE price_subtotal / COALESCE(currency_rate, 1) / product_uom_qty
        END AS sale_price_untaxed
    FROM event_registration
    LEFT JOIN event_event ON ...
    LEFT JOIN event_slot ON ...
    LEFT JOIN event_event_ticket ON ...
    LEFT JOIN sale_order ON ...
    LEFT JOIN sale_order_line ON ...
)
```

**Revenue normalization:** `sale_price` and `sale_price_untaxed` are divided by `currency_rate` and `product_uom_qty` to produce a per-ticket, base-currency figure. This enables meaningful comparison across orders in different currencies and with different quantities.

**Multi-company:** `company_id` is included; the `ir_rule` in `security/ir_rule.xml` restricts access to permitted companies.

---

## Wizards

### `event.event.configurator` — TransientModel (`wizard/event_configurator.py`)

**Purpose:** Triggered when an event-ticket product is added to a cart without an event selected. Used in both the website cart flow and the backend sale order creation.

#### Fields

| Field | Type | Notes |
|---|---|---|
| `product_id` | `Many2one` | `readonly` — the product being configured |
| `event_id` | `Many2one` | Required — the target event |
| `event_slot_id` | `Many2one` | Computed; `domain=[('event_id', '=', event_id)]` |
| `event_ticket_id` | `Many2one` | Computed; `domain=[('event_id', '=', event_id)]` |
| `is_multi_slots` | `Boolean` | `related='event_id.is_multi_slots'` |
| `has_available_tickets` | `Boolean` | `compute` — True if any future-dated tickets exist for the product |

**`_compute_has_available_tickets`:**
```python
product_ticket_data = self.env['event.event.ticket']._read_group(
    [('product_id', 'in', self.product_id.ids),
     ('event_id.date_end', '>=', fields.Date.today())],
    ['product_id'], ['__count'])
```
Checks for any ticket for this product whose event has not ended. Excludes expired events even if tickets are still configured.

**`_compute_event_slot_id`:**
```python
event_slot_ids = self.env['event.slot'].search([('event_id', '=', event_id)], limit=2)
configurator.event_slot_id = event_slot_ids if len(event_slot_ids) == 1 else False
```
Pre-selects the slot only if the event has exactly one slot. Otherwise leaves it blank so the user must choose.

**`_compute_event_ticket_id`:**
```python
event_ticket_ids = self.env['event.event.ticket'].search(
    [('event_id', '=', event_id), ('product_id', '=', product_id)], limit=2)
configurator.event_ticket_id = event_ticket_ids if len(event_ticket_ids) == 1 else False
```
Pre-selects the ticket only if the event has exactly one ticket for the given product.

#### `check_event_id()` — `@api.constrains`

```python
@api.constrains('event_id', 'event_slot_id', 'event_ticket_id')
def check_event_id(self):
    error_messages = []
    for record in self:
        if record.event_id.id != record.event_ticket_id.event_id.id:
            error_messages.append(_('Invalid ticket choice ...'))
        if record.event_slot_id and record.event_id.id != record.event_slot_id.event_id.id:
            error_messages.append(_('Invalid slot choice ...'))
    if error_messages:
        raise ValidationError('\n'.join(error_messages))
```

Validates that both ticket and slot belong to the selected event. The error message aggregates all violations into a single `ValidationError`.

---

### `registration.editor` — TransientModel (`wizard/event_edit_registration.py`)

**Purpose:** Shown immediately after SO confirmation (single-order only) to let the sales team fill in attendee details before registrations are finalized.

#### `default_get(fields)` — wizard population

```python
# Searches existing non-cancelled registrations on this SO
registrations = self.env['event.registration'].search([
    ('sale_order_id', '=', sale_order.id),
    ('event_slot_id', 'in', sale_order.mapped('order_line.event_slot_id').ids or [False]),
    ('event_ticket_id', 'in', sale_order.mapped('order_line.event_ticket_id').ids),
    ('state', '!=', 'cancel')
])
so_lines = sale_order.order_line.filtered('event_ticket_id')
so_line_to_reg = registrations.grouped('sale_order_line_id')

for so_line in so_lines:
    registrations = so_line_to_reg.get(so_line, self.env['event.registration'])
    # Add existing registrations with registration_id populated
    # Add new ones with qty = product_uom_qty - existing_count, pre-filled with SO partner info
```

**Pre-filling logic:** New registrations are pre-filled with `so_line.order_partner_id.name/email/phone` but these are editable — allows ordering on behalf of someone else.

#### `action_make_registration()` — commit

```python
for registration_line in self.event_registration_ids:
    if registration_line.registration_id:
        registration_line.registration_id.write(registration_line._prepare_registration_data())
    else:
        registrations_to_create.append(registration_line._prepare_registration_data(include_event_values=True))
self.env['event.registration'].create(registrations_to_create)
self.event_registration_ids.registration_id._compute_registration_status()
return {'type': 'ir.actions.act_window_close'}
```

- Existing registrations are updated (partner info only; event linkage unchanged).
- New registrations are created with full event linkage (`include_event_values=True`).
- After the wizard closes, `_compute_registration_status()` is called on all modified registrations to trigger state transitions and mail schedulers.

### `registration.editor.line` — TransientModel

#### `_prepare_registration_data(include_event_values=False)`

```python
def _prepare_registration_data(self, include_event_values=False):
    registration_data = {
        'partner_id': self.editor_id.sale_order_id.partner_id.id,
        'name': self.name or self.editor_id.sale_order_id.partner_id.name,
        'phone': self.phone or self.editor_id.sale_order_id.partner_id.phone,
        'email': self.email or self.editor_id.sale_order_id.partner_id.email,
    }
    if include_event_values:
        registration_data.update({
            'event_id': self.event_id.id,
            'event_slot_id': self.event_slot_id.id,
            'event_ticket_id': self.event_ticket_id.id,
            'sale_order_id': self.editor_id.sale_order_id.id,
            'sale_order_line_id': self.sale_order_line_id.id,
        })
    return registration_data
```

`include_event_values=True` is used for new registrations (includes all event linkage fields). `include_event_values=False` (default) is used when editing existing registrations — only partner info is updated, leaving the event linkage unchanged.

---

## Security

### Access Control (`security/ir.model.access.csv`)

| ID | Model | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_registration_editor` | `model_registration_editor` | `group_sale_salesman` | 1 | 1 | 1 | 0 |
| `access_registration_editor_line` | `model_registration_editor_line` | `group_sale_salesman` | 1 | 1 | 1 | 1 |
| `access_event_event_configurator` | `model_event_event_configurator` | `group_sale_salesman` | 1 | 1 | 1 | 0 |
| `access_event_sale_report_manager` | `model_event_sale_report` | `event.group_event_manager` | 1 | 0 | 0 | 0 |

- Editor models are writable but not deletable by salesmen (prevents accidental data loss).
- `event_sale_report` is read-only for event managers (no write/unlink needed).
- `event.registration` ACLs are managed by the `event` module's own ACL file.

### Implied Group (`security/event_security.xml`)

```xml
<record id="sales_team.group_sale_salesman" model="res.groups">
    <field name="implied_ids" eval="[(4, ref('event.group_event_registration_desk'))]"/>
</record>
```

Every user in `group_sale_salesman` automatically gains `event.group_event_registration_desk`. This is a one-line security file that gives all salespeople the ability to view and edit event registrations from the event app without requiring separate role assignment.

### Record Rule (`security/ir_rule.xml`)

`event_sale_report_comp_rule` on `event_sale_report`:
```python
domain_force = [('company_id', 'in', company_ids + [False])]
```
Multi-company rule: users see only reports for their permitted companies. Falls back to records with no company (`False`) — typically demo data.

---

## Data

### `data/event_sale_data.xml`

Sets `invoice_policy = 'order'` on `product_product_event` (the generic registration product from `event_product`). Ensures the default event product bills at order time, not delivery.

### `data/mail_templates.xml`

Provides `event_registration_change_exception` — a QWeb template rendered by `_sale_order_registration_data_change_notify` when a registration's ticket or slot is changed after SO confirmation. Displays: registration name, old value, new value, and a warning that manual actions may be needed.

---

## Performance Considerations

1. **`_compute_sale_price_total`:** Uses `_read_group` aggregation. Single query regardless of number of events. Currency conversion uses today's rate (see performance trade-off note above).

2. **`_init_registrations`:** Batch creation via `sudo().create(registrations_vals)` — one SQL INSERT regardless of quantity. Does not loop individual writes.

3. **`sale_order_line_id` index:** `btree_not_null` is specifically chosen because the field is nullable (SO lines without events have `NULL`). This creates a compact, efficient index that excludes NULLs.

4. **`_compute_attendee_count`:** Uses `_read_group` on `event.registration`, not on `sale.order.line`. This is the correct direction because registrations track cancellation state.

---

## Odoo 18 → 19 Changes

| Change | Detail |
|---|---|
| **`event.event.ticket` restructuring** | In Odoo 18, `event.event.ticket` and `event.type.ticket` were separate with complex `_inherits` inheritance. Now a single `event.event.ticket` model (inheriting from `event.type.ticket` via `_inherit`) holds `product_id`, `price`, and `seats_*` fields. The `_order` on `event.event.ticket` was added in 19: `event_id, sequence, price, name, id`. |
| **`event_slot_id` addition** | Multi-slot events introduce `event.slot` and `event_slot_id` throughout the SO flow. The configurator pre-selects slots, the editor groups registrations per slot, and the confirmation page shows per-slot calendar links. |
| **`_cart_find_product_line` override** | Website event sale needed explicit `(slot, ticket)` filtering in addition to product filtering for multi-slot events where the same ticket type can exist across multiple slots. |
| **`sale_price_total` conversion** | The `_read_group` approach with per-event company currency conversion replaced a previous per-SO-currency iteration that caused performance issues at scale. |
| **`_prepare_order_line_values` ticket validation** | In Odoo 19, the `_prepare_order_line_values` call in `website_event_sale` explicitly validates `ticket.product_id.id == product_id` to prevent ticket/product spoofing via crafted POST parameters. |
| **`service_tracking` check in pricelist onchange** | The `product_pricelist.py` `_onchange_event_sale_warning` checks `service_tracking == 'event'` to detect event-ticket products — aligns with the product-service tracking feature refactor. |
| **`is_published` on `event.sale.report`** | Added in 19 in `website_event_sale` to allow filtering the sales report by publication status. |

---

## Edge Cases and Failure Modes

### Orphaned registrations when SO qty is reduced

`_init_registrations` does **not** delete excess registrations. If an SO is confirmed with qty=5 (5 registrations created), then qty is changed to 3, 2 registrations remain orphaned. The event manager must manually cancel them. This is deliberate — reducing qty on a confirmed SO is an administrative action that should require explicit cancellation.

### SO cancelled after registration creation

`ondelete='cascade'` on `sale_order_id` only fires when the SO row is deleted from the database. SO cancellation is a `write({'state': 'cancel'})` operation, not a delete. `_compute_registration_status` detects the cancelled SO and sets registration `state='cancel'`.

### Public user checkout partner sync

`_synchronize_so_line_values` sets `partner_id = False` when the current user is public AND their partner matches the SO's partner. This prevents registering the anonymous public contact. Portal users follow normal flow (their partner is set correctly).

### Currency mismatch between SO and event company

`_compute_sale_price_total` converts using today's rate. The reported total on the event form may differ from actual paid amounts (historical rates needed for audit accuracy). This is documented as an intentional trade-off.

### Ticket deleted after SO line is created

`_check_event_registration_ticket` only validates on write. A confirmed SO with a deleted ticket is invalid but not auto-corrected — the event manager must handle it manually.

### Zero-amount SO confirmation

Free registrations (price=0) go directly to `state='open'` from `_compute_registration_status`, skipping the draft waiting-for-payment state. This allows free event sign-ups to be immediately confirmed without payment processing.

### Multi-company

`event_sale_report` has an explicit multi-company `ir_rule`. Other models rely on standard company-folding from their respective base modules. Ensure event companies match the company of the products and SOs used.

### Manual SO line event reassignment

If a user changes `event_id` on an SO line in the backend after the SO was confirmed, the old registrations remain linked to the original event via their `event_id` field. The `_compute_event_id` override may clear `event_ticket_id` and `event_slot_id`, but existing registrations are not automatically reassigned or cancelled.

---

## See Also

- [Modules/event](Modules/event.md) — Base event module (`event.event`, `event.registration`, `event.event.ticket`)
- [Modules/event_product](Modules/event_product.md) — Product-event linking (`service_tracking = 'event'`, `product_id` on tickets)
- [Modules/sale](Modules/Sale.md) — Sale order flow (`sale.order`, `sale.order.line`)
- [Modules/website_event_sale](Modules/website_event_sale.md) — E-commerce integration (depends on `event_sale`)
- [Modules/website_event](Modules/website_event.md) — Event website pages and registration forms
