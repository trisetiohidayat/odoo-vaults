---
tags: [odoo, odoo19, module, website, event, booth, registration]
description: L4 documentation for website_event_booth module — public booth registration portal on event website
---

# website_event_booth

> Public-facing booth registration portal for event websites. Enables exhibitors to browse booth categories, select booths, fill contact details, and confirm reservations — without going through a sale order or payment flow. Depends on `event_booth` for the data model.

---

## Module Overview

| Attribute | Value |
|---|---|
| **Category** | Marketing/Events |
| **Version** | 1.0 |
| **Depends** | `website_event`, `event_booth` |
| **Auto-install** | `True` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

**Path:** `odoo/addons/website_event_booth/`

**Purpose:** This module makes booths discoverable and reservable through the event website. It provides no pricing, no invoicing, and no sale order — the free/public booth registration flow ends in a confirmed `event.booth` reservation with contact details captured. For paid booth rentals, see `event_booth_sale` and `website_event_booth_sale`.

**Dependency chain:**

```
website_event_booth
├── website_event          → event
│   └── event             → base
└── event_booth           → event
    └── event
```

---

## L1: Models, Fields, and Methods

### `event.event` — Extended (booth menu)

**File:** `models/event_event.py`

```python
class EventEvent(models.Model):
    _inherit = 'event.event'

    booth_menu = fields.Boolean(
        string='Booth Register',
        compute='_compute_booth_menu',
        readonly=False,
        store=True)
    booth_menu_ids = fields.One2many(
        'website.event.menu', 'event_id',
        string='Event Booths Menus',
        domain=[('menu_type', '=', 'booth')])
    exhibition_map = fields.Image(
        string='Exhibition Map',
        max_width=1024, max_height=1024)
```

**`booth_menu` field — behavior:**

```python
@api.depends('event_type_id', 'website_menu')
def _compute_booth_menu(self):
    for event in self:
        if event.event_type_id and event.event_type_id != event._origin.event_type_id:
            # Event type changed → inherit from event type
            event.booth_menu = event.event_type_id.booth_menu
        elif event.website_menu and (event.website_menu != event._origin.website_menu
                                     or not event.booth_menu):
            # Website menu enabled → enable booth menu (or keep existing)
            event.booth_menu = True
        elif not event.website_menu:
            # Website menu disabled → disable booth menu
            event.booth_menu = False
```

| Condition | Result |
|---|---|
| Event type changed | Inherits `booth_menu` from event type |
| `website_menu` turned on | `booth_menu = True` |
| `website_menu` turned off | `booth_menu = False` |
| No website menu, no type change | Booth menu unchanged |

**`booth_menu_ids`** is the inverse of `website.event.menu.menu_type = 'booth'`. It stores the "Become exhibitor" menu entry per event website.

---

### `event.type` — Extended

**File:** `models/event_type.py`

```python
class EventType(models.Model):
    _inherit = 'event.type'

    booth_menu = fields.Boolean(
        string='Booths on Website',
        compute='_compute_booth_menu',
        readonly=False,
        store=True)

    @api.depends('website_menu')
    def _compute_booth_menu(self):
        for event_type in self:
            event_type.booth_menu = event_type.website_menu
```

**Logic:** Booth registration on the website is enabled by default whenever the website menu is enabled on the event type. Changing the website menu flag on the type automatically propagates to all events created from that type.

---

### `website.event.menu` — Extended

**File:** `models/website_event_menu.py`

```python
class WebsiteEventMenu(models.Model):
    _inherit = "website.event.menu"

    menu_type = fields.Selection(
        selection_add=[('booth', 'Event Booth Menus')],
        ondelete={'booth': 'cascade'})
```

Adds `'booth'` to the menu type selection. When a "Become exhibitor" menu entry is created for an event, it is stored as a `website.event.menu` record with `menu_type = 'booth'`. `ondelete='cascade'` means deleting the menu entry automatically deletes the booth menu.

---

## L2: Field Types, Defaults, Constraints, State Machine

### Booth Menu State Machine

The booth menu visibility has no explicit `state` field on the model — it is a boolean `booth_menu` field whose value is derived from two other booleans (`event_type_id.booth_menu` and `event.website_menu`).

The state of the "Become exhibitor" menu entry itself is managed by the website menu engine:

| Event state | `website_menu` | `booth_menu` | Menu visible? |
|---|---|---|---|
| Published with website | `True` | `True` | Yes |
| Published with website | `True` | `False` | No |
| Not published | `False` | `False` | No |
| Draft | `False` | `False` | No |

### Booth Registration States (handled by `event.booth` model)

The `event.booth` model (in `event_booth`) tracks booth reservation state:

| State | Meaning | Allowed transitions |
|---|---|---|
| `available` | Booth is free | Set to `unavailable` via `action_confirm()` |
| `unavailable` | Booth is booked | Set back to `available` via `write({'state': 'available'})` |

The `website_event_booth` controller calls `booths.action_confirm()` which sets `state='unavailable'` along with the contact details. This is the only normal flow through the state machine in the website context.

### Field Defaults and Constraints

| Field | Type | Default | Constraint |
|---|---|---|---|
| `booth_menu` | Boolean | Computed (from type/website) | `store=True`, `readonly=False` |
| `menu_type` | Selection | — | `'booth'` added to existing selection |
| `exhibition_map` | Image | `False` | `max_width=1024`, `max_height=1024` |

---

## L3: Cross-Model, Override Patterns, Workflow Triggers

### Cross-Model Relationships

```
website_event_booth module:

event.event (this module)
  ├─ booth_menu (boolean) ─────────────────┐
  ├─ booth_menu_ids (1-M → website.event.menu)─┐
  │                                           │ Controls visibility of menu entry
  │                                           │ that links to /event/<slug>/booth
  └─ exhibition_map (image) ──────────────→ Displayed on the booth registration page

website.event.menu (this module)
  └─ menu_type = 'booth' ───────────────→ Identifies "Become exhibitor" menu entry
       └─ event_id ─────────────────────→ Back to event.event

event.booth (event_booth)
  └─ event_id ──────────────────────────→ Booths belong to event
       └─ partner_id, contact_* ──────────→ Set by _prepare_booth_registration_values()
```

### Controller Override Patterns

**File:** `controllers/event_booth.py`

All routes extend `WebsiteEventController` from `website_event`. The module defines or overrides 6 routes:

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/event/<event>/booth` | GET | public | Booth browsing page |
| `/event/<event>/booth/register` | POST | public | Collect selected booth IDs |
| `/event/<event>/booth/register_form` | GET | public | Contact details form |
| `/event/<event>/booth/confirm` | POST | public | Confirm registration |
| `/event/booth/check_availability` | JSON-RPC | public | Real-time availability check |
| `/event/booth_category/get_available_booths` | JSON-RPC | public | Category tab AJAX |

### Workflow Trigger: Registration Confirmation

```
Visitor POSTs to /event/<event>/booth/confirm
  ├─ _get_requested_booths()          → Validates booth IDs exist and are available
  ├─ _check_booth_registration_values() → Validates email, prevents duplicate partners
  ├─ _prepare_booth_registration_partner_values() → Resolves partner or creates new
  ├─ booths.action_confirm(booth_values) → Sets state=unavailable + contact fields
  │     └─ write({'state': 'unavailable', ...})
  │         └─ _action_post_confirm() → Posts chatter message on event
  └─ _prepare_booth_registration_success_values() → Returns JSON with contact info
```

### Key Override Points

#### 1. `_check_booth_registration_values()` — email and partner validation

```python
def _check_booth_registration_values(self, booths, contact_email, booth_category=False):
    if not booths:
        return 'boothError'
    if booth_category and not booth_category.exists():
        return 'boothCategoryError'
    email_normalized = tools.email_normalize(contact_email)
    if request.env.user._is_public() and email_normalized:
        partner = request.env['res.partner'].sudo().search([
            ('email_normalized', '=', email_normalized)
        ], limit=1)
        if partner:
            return 'existingPartnerError'
    return False
```

**Error codes:** `'boothError'`, `'boothCategoryError'`, `'existingPartnerError'`. Public users with an existing partner account cannot self-register — they must log in. This prevents account hijacking.

#### 2. `_prepare_booth_registration_partner_values()` — partner resolution

```python
def _prepare_booth_registration_partner_values(self, event, kwargs):
    if request.env.user._is_public():
        # Anonymous: find or create partner from email
        contact_email_normalized = tools.email_normalize(kwargs['contact_email'])
        if contact_email_normalized:
            partner = event.sudo()._partner_find_from_emails_single(...)
        else:
            partner = request.env['res.partner']
    else:
        # Authenticated: use logged-in user's partner
        partner = request.env.user.partner_id
    return {
        'partner_id': partner.id,
        'contact_name': kwargs.get('contact_name') or partner.name,
        'contact_email': kwargs.get('contact_email') or partner.email,
        'contact_phone': kwargs.get('contact_phone') or partner.phone,
    }
```

#### 3. `_prepare_booth_main_values()` — booth page data preparation

```python
def _prepare_booth_main_values(self, event, booth_category_id=False, booth_ids=False):
    event_sudo = event.sudo()
    available_booth_categories = event_sudo.event_booth_category_available_ids
    # Only shows categories that have at least one available booth
    return {
        'available_booth_category_ids': available_booth_categories,
        'event': event_sudo,
        'event_booths': event_sudo.event_booth_ids,
        'selected_booth_category_id': ...,
        'selected_booth_ids': booth_ids if same category else False,
    }
```

The key design choice is that `event_booth_category_available_ids` filters categories to only those with available booths — sold-out categories are hidden from the public page.

---

## L4: Version Changes Odoo 18→19, Security

### Odoo 18 → 19 Changes

The `website_event_booth` module had minimal structural changes between Odoo 18 and 19. The core architecture — controller routes, helper methods, and booth menu management — remained consistent.

**New in Odoo 19:**
- The `website_event_booth_exhibitor` companion module was split out separately in Odoo 19 (if it existed as part of the same module in Odoo 18).
- The `exhibition_map` field on `event.event` (added in this module) stores the venue floor plan as an image, shown on the booth registration page.
- `booth_menu_ids` field on `event.event` provides a stable inverse relation for managing the "Become exhibitor" website menu entries per event.

**Stability:** This module is architecturally stable. Changes are unlikely because the booth registration workflow (browse → select → contact form → confirm) has been consistent across multiple Odoo versions.

### Security Analysis

#### Authentication and Authorization

| Route | Auth type | Access control |
|---|---|---|
| `/event/<event>/booth` (GET) | `auth='public'` | Odoo checks `event.has_access('read')` — only published events |
| `/event/<event>/booth/register` (POST) | `auth='public'` | Same as above, plus booth existence check |
| `/event/<event>/booth/register_form` (GET) | `auth='public'` | Requires valid `booth_ids` and `booth_category_id` in query string |
| `/event/<event>/booth/confirm` (POST) | `auth='public'` | Validates booth availability, email, and partner |
| `/event/booth/check_availability` | JSON-RPC, `auth='public'` | Uses `sudo()` to browse booths |
| `/event/booth_category/get_available_booths` | JSON-RPC, `auth='public'` | Uses `sudo()` to search booths |

#### Information Disclosure Risks

**Risk 1: Availability enumeration**
`/event/booth/check_availability` and `/event/booth_category/get_available_booths` use `sudo()` to browse/search booths. Any visitor can enumerate which booth IDs are available or unavailable for any published event.

*Mitigation:* This is intentional — the public-facing registration page must reveal availability to work. Booth booking requires a contact email, so anonymous enumeration of availability without booking is not a significant threat.

**Risk 2: Booth details disclosure**
The booth confirmation response (`_prepare_booth_registration_success_values`) returns contact details (name, email, phone). These are only returned for the booths the confirmed user just booked, not for arbitrary booths.

**Risk 3: Email enumeration via `existingPartnerError`**
`_check_booth_registration_values` returns `'existingPartnerError'` when a public user provides an email that matches an existing partner. This allows an attacker to probe whether an email is registered in the system.

*Mitigation:* The error is returned without revealing whether the account belongs to a customer, vendor, or employee. However, for high-security deployments, this behavior should be audited. The fix would be to return a generic error for all cases where registration cannot proceed.

#### CSRF Protection

All form routes use `auth='public'` with the default Odoo CSRF protection (enabled for `type='http'` routes). JSON-RPC routes (`type='json'`) bypass CSRF by design — they use session-based authentication via the Odoo session cookie.

### Performance Considerations

| Operation | Performance concern |
|---|---|
| Booth browsing page (`/event/<slug>/booth`) | Loads `event_booth_category_available_ids` (computed M2M) and all booth records. For events with hundreds of booths, this can be slow. |
| `check_availability` JSON-RPC | Single `sudo().browse()` — O(1) query, fast. |
| `get_available_booths` JSON-RPC | `sudo().search()` with domain on `event_id`, `booth_category_id`, `state` — uses indexes on all three fields, fast. |
| Booth confirmation | One `write()` per booth, plus one `message_post` per booth. Bulk confirmation of many booths at once could generate many chatter messages. |

### Extension Points

| Extension point | Method to override | Description |
|---|---|---|
| Add extra fields to registration | `_prepare_booth_registration_values()` | Add fields beyond `partner_id`, `contact_name`, `contact_email`, `contact_phone` |
| Custom validation before booking | `_check_booth_registration_values()` | Add custom error codes and validation rules |
| Different partner resolution | `_prepare_booth_registration_partner_values()` | Change how the renting partner is found or created |
| Post-confirmation action | `_post_confirmation_message()` in `event_booth` module | Add additional side effects after confirmation |
| Custom booth availability logic | `_get_requested_booths()` | Filter or validate which booths can be booked |
| Modify success response | `_prepare_booth_registration_success_values()` | Change the JSON response structure |

---

## See Also

- [Modules/Event](modules/event.md) — base event module
- [Modules/event_booth](modules/event_booth.md) — core booth data model (`event.booth`, `event.booth.category`)
- [Modules/event_booth_sale](modules/event_booth_sale.md) — pricing and sale order integration for booths
- [Modules/website_event](modules/website_event.md) — website event integration
- [Modules/website_event_booth_sale](modules/website_event_booth_sale.md) — e-commerce cart integration for paid booth sales
- [Modules/website_event_exhibitor](modules/website_event_exhibitor.md) — sponsor/exhibitor website pages companion module
- [Core/HTTP Controller](core/http-controller.md) — @http.route decorator patterns

---

**Tags:** `#module` `#booth-registration` `#website` `#event-registration` `#public-portal` `#json-rpc`
