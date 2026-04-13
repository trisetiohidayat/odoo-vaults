---
type: module
module: pos_event_sale
tags: [odoo, odoo19, pos, event, sale, registration]
created: 2026-04-11
---

# POS Event Sale

**Module:** `pos_event_sale`  
**Path:** `odoo/addons/pos_event_sale/`  
**Category:** Technical  
**Depends:** `pos_event`, `pos_sale`  
**Auto-install:** True  
**License:** LGPL-3  
**Author:** Odoo S.A.

Link module that extends `event.registration` to handle POS-sourced registrations. When an event ticket is sold through Point of Sale (bypassing the website or sale order flow), this module ensures the registration's `sale_status` and `state` are driven by the POS order's payment state instead of the sale order confirmation workflow.

---

## Architecture

This module contributes **one model override** and **one test**. No views, no wizards, no data files.

```
pos_event_sale
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── event_registration.py      # _compute_registration_status() override
└── tests/
    ├── __init__.py
    └── test_frontend.py           # Browser/scenario test
```

**Dependency chain:**

```
pos_event_sale
  ├── pos_event              # Adds pos_order_line_id on event.registration
  │    ├── point_of_sale     # Provides pos.order, pos.order.line
  │    └── event             # Provides event.registration, event.event
  │
  └── pos_sale               # Provides SO linking for POS lines
       ├── point_of_sale
       └── sale
```

The module bridges the POS and event worlds by overriding the POS-side `event.registration` computation — the same registration model that `event_sale` extends with SO linkage. `pos_event_sale` is the POS counterpart: it handles the case where a registration originates from a POS order (linked via `pos_order_line_id`) rather than a sale order.

`pos_event` provides the foundational POS registration linkage (`pos_order_id`, `pos_order_line_id` fields, `_load_pos_data_*` methods), while `pos_sale` would provide the sale order link. `pos_event_sale` combines both by extending the `_compute_registration_status` method.

---

## L1 — event.registration Extension for POS Event Ticket Sales

### Registration Origin Taxonomy

In Odoo 19, an `event.registration` can be created from three distinct entry points:

| Entry Point | Link Fields Set | Driven By | Module |
|---|---|---|---|
| **Website** (public/portal) | None | — | `website_event` |
| **Sale Order** (backend/catalog) | `sale_order_id`, `sale_order_line_id` | SO `state`, `amount_total` | `event_sale` |
| **Point of Sale** (POS UI) | `pos_order_id`, `pos_order_line_id` | POS order `state`, `amount_total` | `pos_event_sale` |

This module handles the POS entry point. It does **not** set `sale_order_id` — POS orders create registrations directly via `pos.order.line`'s `event_registration_ids` one2many.

### What `pos_event` Sets Up

Before `pos_event_sale` does anything, `pos_event/models/event_registration.py` defines the POS linkage on the registration model:

```python
class EventRegistration(models.Model):
    _name = 'event.registration'
    _inherit = ['event.registration', 'pos.load.mixin']

    pos_order_id = fields.Many2one(related='pos_order_line_id.order_id', ...)
    pos_order_line_id = fields.Many2one('pos.order.line', ...)

    def _has_order(self):
        return super()._has_order() or self.pos_order_id

    @api.depends('pos_order_id.state', 'pos_order_id.currency_id',
                 'pos_order_id.amount_total')
    def _compute_registration_status(self):
        if self.pos_order_id:
            for registration in self:
                if registration.pos_order_id.state == 'cancel':
                    registration.state = 'cancel'
                elif float_is_zero(registration.pos_order_id.amount_total,
                                   precision_rounding=registration.pos_order_id.currency_id.rounding):
                    registration.sale_status = 'free'
                    registration.state = 'open'
                else:
                    registration.sale_status = 'sold'
                    registration.state = 'open'
        super()._compute_registration_status()
```

This base-level computation in `pos_event` already handles the POS-to-registration status propagation. `pos_event_sale` overrides `_compute_registration_status` to extend this logic.

### What `pos_event_sale` Overrides

The `pos_event_sale` override handles the case where a POS order transitions to `paid`, which should mark the registration as `sold`:

```python
class EventRegistration(models.Model):
    _inherit = ['event.registration']
    _name = 'event.registration'

    @api.depends('pos_order_id.state')
    def _compute_registration_status(self):
        super()._compute_registration_status()
        for record in self.filtered("pos_order_id.id"):
            if record.pos_order_id.state in ['paid', 'done', 'invoiced']:
                record.sale_status = 'sold'
                record.state = 'open'
            else:
                record.sale_status = 'to_pay'
                record.state = 'draft'
```

**Key difference from `pos_event` base:** The base method checks `amount_total == 0` for `free` status and relies on parent `super()` for the default path. `pos_event_sale` adds a second-pass override that specifically maps POS order states to registration status:

| POS order `state` | Registration `sale_status` | Registration `state` |
|-------------------|---------------------------|---------------------|
| `paid` | `sold` | `open` |
| `done` | `sold` | `open` |
| `invoiced` | `sold` | `open` |
| `draft`, `quotation` | `to_pay` | `draft` |
| `cancel` | (handled by `pos_event` base) | `cancel` |

Note: `pos_event` already sets `state='cancel'` when POS is cancelled. `pos_event_sale` focuses on the paid/done/invoiced path where `sale_status` is set to `sold`.

### Why Two Overrides?

`pos_event` sets the base POS-side logic. `pos_event_sale` adds a **second pass** via `super()._compute_registration_status()` chaining. The order matters:

1. `pos_event`'s `_compute_registration_status` runs first (via `super()` chain from base `event.registration`).
2. `pos_event_sale`'s override calls `super()`, which invokes `pos_event`'s version.
3. Then `pos_event_sale` applies its additional state mapping.

This two-pass design keeps `pos_event` as the foundational POS registration model (usable without `pos_event_sale`), while `pos_event_sale` adds the sale-specific status (`sold`/`to_pay`) on top.

---

## L2 — Field Types, Defaults, Constraints

### Fields Contributed by `pos_event_sale`

**None.** The module adds no fields. The fields it relies on are contributed by `pos_event`:

| Field | Model | Source Module | Type | Purpose |
|-------|-------|--------------|------|---------|
| `pos_order_id` | `event.registration` | `pos_event` | `Many2one` (related to `pos_order_line_id.order_id`) | Points to the POS order |
| `pos_order_line_id` | `event.registration` | `pos_event` | `Many2one` | Points to the POS order line that generated this registration |
| `sale_status` | `event.registration` | `event` (base) | `Selection` | `'free'`, `'to_pay'`, `'sold'`, `'cancel'` — payment-driven status |
| `state` | `event.registration` | `event` (base) | `Selection` | `'draft'`, `'open'`, `'done'`, `'cancel'` — confirmation-driven status |

### Dependency Triggers

The `pos_event` base method depends on three fields:

```python
@api.depends('pos_order_id.state',
             'pos_order_id.currency_id',
             'pos_order_id.amount_total')
def _compute_registration_status(self):
```

The `pos_event_sale` override depends only on:

```python
@api.depends('pos_order_id.state')
def _compute_registration_status(self):
```

The narrower dependency is intentional — once the POS order state is known, `sale_status` can be determined without re-reading `amount_total` (which is only needed for the `free` determination, handled earlier).

### Constraints

There are no SQL or `@api.constrains` in `pos_event_sale`. Constraints are handled upstream:
- `event.registration` base model validates `event_id` and `event_ticket_id` are required.
- `pos_event` validates the POS linkage.
- `pos_sale` ensures `pos.order.line` has proper product/ticket bindings.

### Null Handling

The override uses `self.filtered("pos_order_id.id")` — the string domain `"pos_order_id.id"` filters records where the Many2one field has a non-null ID. This is equivalent to `self.filtered(lambda r: r.pos_order_id.id)` but more concise. Records without a `pos_order_id` are passed through to `super()` unchanged.

---

## L3 — cross_model, Override Pattern, Workflow Trigger

### Cross-Model Data Flow

```
pos.order (state = 'paid')
  │
  ▼ (via pos_order_line_id reverse link)
pos.order.line (event_registration_ids)
  │
  ▼ (at registration creation time, via event_ticket_id)
event.registration (pos_order_line_id set)
  │
  ▼ (recomputed when pos_order_id.state changes)
_compute_registration_status()
  │
  ├─→ sale_status = 'sold' (paid/done/invoiced) or 'to_pay' (draft/quotation)
  └─→ state = 'open' (sold) or 'draft' (to_pay)
```

### Override Pattern

**File:** `models/event_registration.py`

```python
class EventRegistration(models.Model):
    _inherit = ['event.registration']
    _name = 'event.registration'

    @api.depends('pos_order_id.state')
    def _compute_registration_status(self):
        super()._compute_registration_status()
        for record in self.filtered("pos_order_id.id"):
            if record.pos_order_id.state in ['paid', 'done', 'invoiced']:
                record.sale_status = 'sold'
                record.state = 'open'
            else:
                record.sale_status = 'to_pay'
                record.state = 'draft'
```

**Design pattern:** This is a **second-pass extension**. The method calls `super()` first (which invokes `pos_event`'s `_compute_registration_status`, which in turn calls `event.registration`'s base implementation). After the parent chain completes, this override applies the POS-specific sale status mapping.

The `for record in self.filtered(...)` pattern iterates over records that have a `pos_order_id`. Records from website or SO origin skip this block.

### POS Order State Lifecycle

A POS order transitions through these states during a typical POS session:

| State | Trigger | Registration Effect |
|-------|---------|---------------------|
| `draft` | Order created in POS UI | `sale_status='to_pay'`, `state='draft'` |
| `paid` | Payment completed, session validated | `sale_status='sold'`, `state='open'` |
| `done` | End-of-day session reconciled | `sale_status='sold'`, `state='open'` |
| `invoiced` | POS order invoiced to customer | `sale_status='sold'`, `state='open'` |
| `cancel` | Order cancelled in POS | `state='cancel'` (from `pos_event` base) |

### Workflow Trigger: POS Order Payment

When a POS order moves to `paid` state:
1. Odoo calls `pos.order` write with `state='paid'`.
2. The `_compute_registration_status` on `event.registration` is triggered via `@api.depends('pos_order_id.state')`.
3. `pos_event`'s base method checks cancellation and free-order cases.
4. `pos_event_sale`'s override maps `paid/done/invoiced` → `sale_status='sold'`.
5. The registration state becomes `'open'` — the event app shows it as confirmed.
6. Email schedulers (from `event` module) fire based on the state → `'open'` transition.

### Relationship Between `pos_event_sale` and `event_sale`

Both modules extend the same registration model for different sales channels. They operate independently and both call `super()`:

```
event.registration._compute_registration_status() [base]
  │
  ├─ event_sale: sale_order_id branch → sale_status from SO state
  │
  └─ pos_event: pos_order_id branch → state/cancel from POS state
         │
         └─ pos_event_sale: second pass → sale_status from POS state
```

A registration can have both `sale_order_id` (from `event_sale`) and `pos_order_id` (from `pos_event`) if the POS order was linked to a SO. In that case, both modules' overrides contribute — the exact behavior depends on the order of inheritance in `_inherit`.

---

## L4 — Odoo 18 to 19 Changes

### Changes in `pos_event_sale`

There are **no functional code changes** between Odoo 18 and Odoo 19 for this module. The source file `models/event_registration.py` is identical in both versions.

### Changes in Upstream Modules

The capability of this module depends on structural changes in `pos_event` and `event`:

| Upstream module | Odoo 18 → 19 change | Impact on pos_event_sale |
|-----------------|---------------------|--------------------------|
| `pos_event` | No structural change to `pos_order_id`/`pos_order_line_id` fields | Fields still available |
| `event` | `state` on `event.registration` changed from `'done'` to `'confirm'` in some paths? Actually `'open'` remains | No impact |
| `event` | `sale_status` selection — `'to_pay'` value added to selection in Odoo 19 | The `sale_status='to_pay'` branch is valid |
| `pos_sale` | `_fill_pos_fields` hook introduced (Odoo 18) | No direct impact on registration |
| `point_of_sale` | `paid` state for POS orders — unchanged | Continues to work as-is |

### Registration State Machine Change (Odoo 18 → 19)

In Odoo 18, `event.registration` had a `done` state. In Odoo 19, the state values were streamlined — `'open'` is the confirmed state, and `'done'` has been removed or consolidated. The `pos_event_sale` override sets `state = 'open'` unconditionally for paid registrations, which aligns with Odoo 19's state model.

### `pos.load.mixin` Integration

`pos_event` applies `pos.load.mixin` to `event.registration`. The mixin provides `_load_pos_data_*` methods for syncing registrations to the POS cache. This is unchanged between Odoo 18 and 19.

---

## Tests

### `TestPoSEventSale`

**File:** `tests/test_frontend.py`

Inherits from `TestUi` (inherited from `pos_event.tests.test_frontend`). Runs as a post-install browser test using the POS tour system.

```python
@tagged('post_install', '-at_install')
class TestPoSEventSale(TestUi):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
```

### `test_sale_status_event_in_pos`

```python
def test_sale_status_event_in_pos(self):
    # Grant event_user rights to the POS user
    self.pos_user.write({
        'group_ids': [
            (4, self.env.ref('event.group_event_user').id),
        ]
    })
    self.main_pos_config.with_user(self.pos_user).open_ui()

    order_data = {
        "amount_paid": 100,
        "amount_tax": 0,
        "amount_return": 0,
        "amount_total": 100,
        "date_order": fields.Datetime.to_string(fields.Datetime.now()),
        "fiscal_position_id": False,
        "lines": [Command.create({
            "product_id": self.product_event.id,
            "price_unit": 100.0,
            "price_subtotal": 100.0,
            "price_subtotal_incl": 100.0,
            "tax_ids": [],
            "qty": 1,
            "event_ticket_id": self.test_event.event_ticket_ids[0].id,
            "event_registration_ids": [
                (0, 0, {
                    "event_id": self.test_event.id,
                    "event_ticket_id": self.test_event.event_ticket_ids[0].id,
                    "name": "Test Name",
                    "email": "Test Email",
                    "phone": "047123123198",
                }),
            ],
        })],
        "name": "Order 12345-123-1234",
        "partner_id": self.partner_a.id,
        "session_id": self.main_pos_config.current_session_id.id,
        "sequence_number": 2,
        "payment_ids": [Command.create({
            "amount": 100,
            "name": fields.Datetime.now(),
            "payment_method_id": self.bank_payment_method.id,
        })],
        "uuid": "12345-123-1234",
        "last_order_preparation_change": "{}",
        "user_id": self.env.uid,
        "to_invoice": False,
    }

    order_data_2 = {
        # ... similar but with amount_paid=0, payment_ids=[],
        # state='draft', and no payment
    }

    self.env['pos.order'].sync_from_ui([order_data, order_data_2])
    sale_status = self.env['event.registration'].search([]).mapped("sale_status")
    self.assertEqual(len(sale_status), 2)
    self.assertIn('sold', sale_status)
    self.assertIn('to_pay', sale_status)
```

**Scenario:** Two POS orders are synced — one fully paid (`amount_paid=100`, with payment), one unpaid draft (`amount_paid=0`, no payment). After sync, registrations should have mixed `sale_status`: the paid order produces `sold`, the unpaid produces `to_pay`.

**Key assertions:**
- `len(sale_status) == 2` — confirms two registrations were created
- `'sold' in sale_status` — confirms paid POS order maps to `sold`
- `'to_pay' in sale_status` — confirms unpaid draft POS order maps to `to_pay`

**What the test verifies:**
1. POS order with payment → registration has `sale_status='sold'`
2. POS order without payment (draft) → registration has `sale_status='to_pay'`
3. The override correctly splits registrations based on their linked POS order's payment state

### Test Data Setup

The test uses `TestUi` from `pos_event.tests.test_frontend`, which provides:
- `self.product_event` — event-ticket product
- `self.test_event` — event with at least one ticket
- `self.partner_a` — test customer
- `self.main_pos_config` — POS configuration
- `self.pos_user` — POS user with event rights
- `self.bank_payment_method` — bank payment method

The `setUpClass` in `TestUi` creates the event, product, and ticket fixtures. `pos_event_sale`'s test just adds the event group to the POS user and runs the scenario.

---

## Edge Cases and Failure Modes

### Registration has both SO and POS links

If a POS order is linked to a SO (via `pos_sale`), the registration may have both `sale_order_id` and `pos_order_id`. `event_sale`'s `sale_status` override runs on the SO branch, while `pos_event_sale` runs on the POS branch. The final `sale_status` depends on which override executes last in the MRO chain. This is an unlikely configuration.

### POS order state changes after closing session

If a POS session is closed and the order state is `done`, the registration is confirmed (`sale_status='sold'`). If the session is later reopened and the order is cancelled, the registration does **not** automatically revert — `_compute_registration_status` only fires on writes to `pos_order_id.state`. Manual cancellation is needed.

### Event seats availability

`pos_event` sets up `_update_available_seat` on write to registration. When a POS registration is created and `state` transitions to `'open'`, `pos_event`'s write hook calls `_update_available_seat`, which updates the event's available seat count for all open POS sessions. This ensures seat availability shown in POS reflects confirmed registrations.

### Multiple registrations per POS order

A POS order line with `qty > 1` and `event_ticket_id` generates multiple `event_registration` records (one per unit). The `sale_status` computation runs per-record, so all registrations linked to a paid POS order get `sale_status='sold'` together.

---

## See Also

- [Modules/pos_event](Modules/pos_event.md) — POS event integration (pos_order_id, pos_order_line_id on registration)
- [Modules/pos_sale](Modules/pos_sale.md) — POS sale order linking (sale_order_line_id on POS lines)
- [Modules/event_sale](Modules/event_sale.md) — SO-to-registration bridge (sale_order_id on registration)
- [Modules/event](Modules/event.md) — Base event module (event.registration model, state machine)
- [Modules/point_of_sale](Modules/point_of_sale.md) — POS base (pos.order, pos.order.line)
- [Modules/pos_sale_margin](Modules/pos_sale_margin.md) — Another POS link module (sale.report margin)
