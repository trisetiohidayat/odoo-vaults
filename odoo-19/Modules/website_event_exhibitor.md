# website_event_exhibitor

## Overview

**Path:** `odoo/addons/website_event_exhibitor/`
**Manifest:** `__manifest__.py` v1.1
**Category:** Marketing/Events
**Depends:** `website_event`
**Author:** Odoo S.A.
**License:** LGPL-3

> Enables event organizers to manage **sponsors and exhibitors** with dedicated public pages on the event website. Includes tiered sponsorship levels (Gold/Silver/Bronze), logo management, exhibitor profiles, opening-hours-aware "live" status, and website search integration.

---

## Architecture

### Module Purpose

This module transforms event sponsors from simple logo listings into full exhibitor profiles with public-facing pages on the event website. It creates a new `event.sponsor` model linked to `event.event`, adds sponsorship tiers via `event.sponsor.type`, and provides a complete website exhibitor directory with filtering and search.

### Dependency Chain

```
website_event_exhibitor
└── website_event
    ├── website
    ├── event
    │   └── event.type
    └── event_sale (optional)
```

### Module File Structure

```
website_event_exhibitor/
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── exhibitor.py            # HTTP routes: exhibitors list, exhibitor detail
├── models/
│   ├── __init__.py
│   ├── event_event.py          # sponsor_ids, exhibitor_menu on event.event
│   ├── event_sponsor.py        # Core model: event.sponsor
│   ├── event_sponsor_type.py   # event.sponsor.type (tier levels)
│   ├── event_type.py           # exhibitor_menu on event.type
│   ├── website.py              # Website._search_get_details integration
│   └── website_event_menu.py   # menu_type='exhibitor' selection extension
├── data/
│   ├── event_demo.xml
│   ├── event_sponsor_demo.xml
│   └── event_sponsor_data.xml  # Bronze/Silver/Gold noupdate records
├── report/
│   ├── website_event_exhibitor_reports.xml
│   └── website_event_exhibitor_templates.xml
├── security/
│   ├── security.xml             # ir.rule for public/portal read access
│   └── ir.model.access.csv
└── views/
    ├── event_event_views.xml
    ├── event_exhibitor_templates_list.xml
    ├── event_exhibitor_templates_page.xml
    ├── event_menus.xml
    ├── event_sponsor_views.xml
    ├── event_templates_sponsor.xml
    └── event_type_views.xml
```

---

## Models

### `event.sponsor` — Core Model

**File:** `models/event_sponsor.py`
**Inheritance:** `mail.thread`, `mail.activity.mixin`, `website.published.mixin`, `website.searchable.mixin`
**Order:** `sequence, sponsor_type_id`
**Rec Name:** `name`

#### Field Summary

**Identifiers**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `event_id` | Many2one `event.event` | required | Parent event, **indexed** for performance. Acts as the FK to the event. |
| `sponsor_type_id` | Many2one `event.sponsor.type` | `_default_sponsor_type_id()` (highest sequence) | Sponsorship tier. `bypass_search_access=True` skips ACL checks during name_search — needed because public users browse sponsors on the website. |
| `partner_id` | Many2one `res.partner` | required | Linked company. `bypass_search_access=True` for the same reason. |
| `sequence` | Integer | 0 | Display ordering within a tier. |

**Classification**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `exhibitor_type` | Selection | `"sponsor"` | `"sponsor"` = footer logo only (no public page); `"exhibitor"` = full exhibitor page; `"online"` = online exhibitor page. Only `exhibitor` and `online` appear in website search and the exhibitor directory. |
| `active` | Boolean | `True` | Soft-delete flag. Inactive sponsors are excluded from `_get_event_sponsors_base_domain()`. |

**Contact Information — Computed + Stored, Sync-on-Empty from partner_id**

These fields sync from `partner_id` whenever the sponsor's own value is empty. This is a **one-way pull**: setting a value on the sponsor does NOT write back to the partner. It allows event-specific overrides while still benefiting from partner-level defaults.

| Field | Type | Sync Trigger | Description |
|-------|------|-------------|-------------|
| `name` | Char | `_compute_name` / `@api.depends('partner_id')` | Sponsor display name. Falls back to `partner_id.name`. |
| `email` | Char | `_compute_email` / `@api.depends('partner_id')` | Contact email. Falls back to `partner_id.email`. |
| `phone` | Char | `_compute_phone` / `@api.depends('partner_id')` | Contact phone. Falls back to `partner_id.phone`. |
| `url` | Char | `_compute_url` / `@api.depends('partner_id')`, `store=True`, `readonly=False` | Sponsor website URL. Syncs from `partner_id.website` if the sponsor's `url` is empty OR if `partner_id.website` has a value (even if sponsor url is non-empty). Logic: `if sponsor.partner_id.website or not sponsor.url`. This means clearing the partner's website also clears the sponsor's URL. |
| `partner_name` | Char | Related | `partner_id.name` (read-only related) |
| `partner_email` | Char | Related | `partner_id.email` (read-only related) |
| `partner_phone` | Char | Related | `partner_id.phone` (read-only related) |

**Content**

| Field | Type | Description |
|-------|------|-------------|
| `subtitle` | Char | Slogan or tagline displayed under the company name. |
| `website_description` | Html | Full exhibitor page content. `translate=html_translate` — translatable per language. Falls back to `partner_id.website_description` when empty via `_compute_website_description`. `sanitize_overridable=True` allows custom sanitization overrides. |
| `show_on_ticket` | Boolean | If `True`, sponsor logo is rendered on the event ticket PDF. Default `True`. |

**Image**

| Field | Type | Description |
|-------|------|-------------|
| `image_512` | Image `max_width=512, max_height=512` | Sponsor logo. Computed + stored. Syncs from `partner_id.image_512` when empty via `_synchronize_with_partner`. Stored to avoid recomputation on every public page load. |
| `image_256` | Image `max_width=256, max_height=256` | Related to `image_512`, `store=False` — derived dynamically. |
| `image_128` | Image `max_width=128, max_height=128` | Related to `image_512`, `store=False`. |
| `website_image_url` | Char | Computed (`_compute_website_image_url`), `compute_sudo=True`. Returns a `/web/image` URL pointing to the stored `image_256`. Falls back to `partner_id.image_256` if sponsor image is empty, then to `/website_event_exhibitor/static/src/img/event_sponsor_default.svg`. |

**Opening Hours / Live Mode**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `hour_from` | Float | `8.0` | Opening hour in float format (e.g., `8.5` = 8:30). |
| `hour_to` | Float | `18.0` | Closing hour. `0.0` is a special sentinel meaning "midnight" and is treated as end-of-day+1 (next day at 00:00). |
| `event_date_tz` | Selection | readonly, related | Event timezone. Read from `event_id.date_tz`. Used for all opening-hours calculations. |
| `is_in_opening_hours` | Boolean | computed | Timezone-aware live status. `False` if event is not ongoing. `True` if hours are not set. Otherwise compares current time (in event TZ) against today's localized window, bounded by event start/end. |

**Related / Derived**

| Field | Type | Description |
|-------|------|-------------|
| `country_id` | Many2one `res.country` | Related to `partner_id.country_id`, readonly. Used for country filtering in the exhibitor directory. |
| `country_flag_url` | Char | Computed (`_compute_country_flag_url`), `compute_sudo=True`. Returns `partner_id.country_id.image_url`. |

#### Computed Method Details

**`_synchronize_with_partner(self, fname)`**

```python
def _synchronize_with_partner(self, fname):
    for sponsor in self:
        if not sponsor[fname]:
            sponsor[fname] = sponsor.partner_id[fname]
```

Key design: This is called from `readonly=False, store=True` computed fields. Because the fields are stored, once a value is set (either synced from partner or manually entered), it persists even if the partner value changes later. To re-sync, the sponsor field must be explicitly cleared.

**`_compute_url()` — asymmetric sync logic**

```python
def _compute_url(self):
    for sponsor in self:
        if sponsor.partner_id.website or not sponsor.url:
            sponsor.url = sponsor.partner_id.website
```

This differs from `_synchronize_with_partner`: it overwrites the sponsor's `url` whenever `partner_id.website` is truthy, even if the sponsor already has a URL set. This is a stronger coupling — if a partner's website is updated, the sponsor's URL also updates. However, if the partner's website is cleared (`False`/`''`), the sponsor's URL is preserved (because `or not sponsor.url` evaluates to `False` when sponsor url is truthy).

**`_compute_website_image_url()` — fallback chain**

```
image_512 stored value
  → use website.image_url(model='event.sponsor', field='image_256', size=256)
  → fallback: partner_id.image_256 → website.image_url(model='res.partner', ...)
  → fallback: /website_event_exhibitor/static/src/img/event_sponsor_default.svg
```

The use of `website.image_url()` generates a signed/non-signed URL based on the website's image attachment storage (database or filestore).

**`_compute_is_in_opening_hours()` — full logic**

```python
# Step 1: Event not ongoing
if not sponsor.event_id.is_ongoing:
    is_in_opening_hours = False

# Step 2: Hours not configured
elif sponsor.hour_from is False or sponsor.hour_to is False:
    is_in_opening_hours = True  # always open

# Step 3: Full timezone-aware comparison
event_tz = timezone(sponsor.event_id.date_tz)
dt_begin = sponsor.event_id.date_begin.astimezone(event_tz)
dt_end = sponsor.event_id.date_end.astimezone(event_tz)
now_utc = utc.localize(fields.Datetime.now().replace(microsecond=0))
now_tz = now_utc.astimezone(event_tz)

opening_from_tz = event_tz.localize(datetime.combine(now_tz.date(), float_to_time(sponsor.hour_from)))
opening_to_tz = event_tz.localize(datetime.combine(now_tz.date(), float_to_time(sponsor.hour_to)))

if sponsor.hour_to == 0:
    opening_to_tz += timedelta(days=1)  # midnight = next day 00:00

opening_from = max([dt_begin, opening_from_tz])
opening_to   = min([dt_end, opening_to_tz])

is_in_opening_hours = opening_from <= now_tz < opening_to
```

Edge cases:
- `hour_to == 0`: interpreted as midnight of the following day, extended by `timedelta(days=1)`.
- `hour_to == 24.0` is not handled specially; `float_to_time(24.0)` may raise or wrap. Use `0.0` for midnight closing.
- The window is clamped to the event's `date_begin` and `date_end`, so exhibitors cannot show "open" outside the event dates.
- `float_to_time` from `odoo.tools.date_utils` handles fractional hours (e.g., `8.5` → `datetime.time(8, 30)`.

#### Mixin Implementations

**`website.published.mixin`** — `_compute_website_url()`, `_compute_website_absolute_url()`, `is_published` (implicit)

The super call in `_compute_website_url()` handles the base `website_url` field assignment, then overrides it with:
```python
sponsor.website_url = f'/event/{slug(event_id)}/exhibitor/{slug(sponsor)}'
```

Only executed when `sponsor.id` is truthy (record is persisted) — avoids slugging unsaved records during onchanges.

`get_base_url()` routes through `event_id.get_base_url()`, making multi-website base URL resolution work correctly.

**`website.searchable.mixin`** — `_search_get_detail()`

Registers `event.sponsor` as a searchable model in the website search bar when `search_type` is `'sponsor'` or `'all'` and an `event` option is present.

```python
base_domain: [('event_id', '=', event_id), ('exhibitor_type', '!=', 'sponsor')]
```

The domain excludes `exhibitor_type='sponsor'` records (logo-only sponsors have no public page to link to).

Search fields: `name`, `website_description`
Fetch fields: `name`, `website_url`, `website_description`
Icon: `fa-black-tie`

#### Performance Considerations

- `image_512` is **stored** to avoid recomputation from partner on every page load.
- `website_image_url` is **not stored** — it calls `website.image_url()` at render time, which generates a fresh URL each request. Signed URLs may change per request.
- `_compute_sponsor_count` on `event.event` uses `_read_group` aggregation rather than `search_count`, which is more efficient for counting across multiple events.
- `_event_exhibitors_get_values` calls `sudo().search()` twice (once with filters, once base domain for counts). The base domain search could be cached or pre-fetched.
- `random.sample()` is called on each exhibitor list load — no server-side caching of the randomization, meaning the order changes on every page refresh. This is intentional UX (fair exposure for lower-tier sponsors).
- `website_published` is indexed implicitly via the `ir.rule` on public/portal groups; internal employees bypass this rule via `event.group_event_registration_desk`.

---

### `event.sponsor.type` — Sponsor Tier Model

**File:** `models/event_sponsor_type.py`
**Inheritance:** `BaseModel` (no mixins)
**Order:** `sequence`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required, translate=True | Tier name: "Gold", "Silver", "Bronze". Translatable for multi-language events. |
| `sequence` | Integer | `_default_sequence()` | Autoincrement from max existing + 1. Determines display order. |
| `display_ribbon_style` | Selection | `"no_ribbon"` | Controls CSS ribbon class rendered on sponsor cards. Options: `no_ribbon`, `Gold`, `Silver`, `Bronze`. |

**Noupdate Demo Data** (loaded once on install):
- `event_sponsor_type1`: Bronze, sequence=3, ribbon=Bronze
- `event_sponsor_type2`: Silver, sequence=2, ribbon=Silver
- `event_sponsor_type3`: Gold, sequence=1, ribbon=Gold

Note: Platinum is **not** included in the base data but is common in custom deployments. The `_default_sponsor_type_id()` on `event.sponsor` returns the **highest sequence** (lowest number = lowest tier, last in order), which means new sponsors default to Bronze by default.

---

### `event.event` — Extended

**File:** `models/event_event.py`
**Inheritance:** `event.event`

| Field | Type | Compute/Store | Description |
|-------|------|---------------|-------------|
| `sponsor_ids` | One2many `event.sponsor` | inverse on `event_id` | All sponsors linked to this event. |
| `sponsor_count` | Integer | computed (not stored) | Count of all sponsors. Uses `_read_group` aggregation. |
| `exhibitor_menu` | Boolean | computed + stored | Whether to show the exhibitor showcase menu on the website. |
| `exhibitor_menu_ids` | One2many `website.event.menu` | inverse on `event_id`, domain `menu_type='exhibitor'` | Auto-generated website menu entries for the exhibitor section. |

**`_compute_exhibitor_menu()` — cascade logic (L3)**

```python
# Priority 1: event_type_id is set and changed
if event.event_type_id and event.event_type_id != event._origin.event_type_id:
    event.exhibitor_menu = event.event_type_id.exhibitor_menu
# Priority 2: website_menu is True and either changed or exhibitor_menu not yet set
elif event.website_menu and (event.website_menu != event._origin.website_menu or not event.exhibitor_menu):
    event.exhibitor_menu = True
# Priority 3: website_menu is False
elif not event.website_menu:
    event.exhibitor_menu = False
```

**Important**: The condition `event.event_type_id != event._origin.event_type_id` uses object identity/comparison on the recordset. If the type is changed to a new one, the computed field cascades the `exhibitor_menu` value from the new type.

**Menu Management Methods**

- `toggle_exhibitor_menu(val)`: Writes `exhibitor_menu` boolean. Used by the website toggle button.
- `_get_menu_update_fields()`: Returns `['exhibitor_menu']` alongside parent fields — ensures exhibitor menu is included in bulk website menu updates.
- `_update_website_menus(...)`: Delegates to `_update_website_menu_entry('exhibitor_menu', 'exhibitor_menu_ids', 'exhibitor')` for each event with a menu.
- `_get_menu_type_field_matching()`: Maps `'exhibitor'` menu type to the `'exhibitor_menu'` field.
- `_get_website_menu_entries()`: Returns menu entry tuple: `(_('Exhibitors list'), '/event/{slug}/exhibitors', False, 60, 'exhibitor', False)`. Position 60 places it after the main event menu items.
- `copy_event_menus(old_events)`: Repoints `exhibitor_menu_ids.menu_id.parent_id` to the new event's `menu_id` after event duplication.

---

### `event.type` — Extended

**File:** `models/event_type.py`
**Inheritance:** `event.type`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `exhibitor_menu` | Boolean | computed from `website_menu`, stored | Template default for new events of this type. Compute: `_compute_exhibitor_menu` → `exhibitor_menu = website_menu`. |

Because `store=True, readonly=False`, this field is both computed and manually editable — an admin can override the type default before creating an event.

---

### `website.event.menu` — Extended

**File:** `models/website_event_menu.py`
**Inheritance:** `website.event.menu`

| Field | Change | Description |
|-------|--------|-------------|
| `menu_type` | `selection_add=[('exhibitor', 'Exhibitors Menus')]` | Adds `'exhibitor'` as a valid menu type. `ondelete='cascade'` means deleting the event (or the exhibitor toggle) cascades to remove the menu record. |

---

### `website` — Extended

**File:** `models/website.py`

`_search_get_details(search_type, order, options)` is extended to append `event.sponsor._search_get_detail()` when `search_type in ['sponsor', 'all']` and `options.get('event')` is present.

---

## Controller — `ExhibitorController`

**File:** `controllers/exhibitor.py`
**Inherits:** `WebsiteEventController` (from `website_event`)

### Route Summary

| Route | Type | Auth | Description |
|-------|------|------|-------------|
| `/event/<event>/exhibitors` | http | public | Exhibitor directory listing page |
| `/event/<event>/exhibitor` | http | public | Backward-compatible alias for the directory |
| `/event/<event>/exhibitor/<sponsor>` | http | public | Individual exhibitor detail page |
| `/event_sponsor/<int:sponsor_id>/read` | jsonrpc | public | Marshalling endpoint for the "not started / not available" modal |

### `_get_event_sponsors_base_domain(event)` — Access Control Logic

```python
search_domain_base = [
    ('event_id', '=', event.id),
    ('exhibitor_type', 'in', ['exhibitor', 'online']),
]
if not request.env.user.has_group('event.group_event_registration_desk'):
    search_domain_base = Domain.AND([search_domain_base, [('is_published', '=', True)]])
```

- Internal staff with `event.group_event_registration_desk` see **all** exhibitors including unpublished (for preview).
- Public/portal users only see published exhibitors.
- `"sponsor"` type is **always excluded** from directory and search (they are footer logo only).
- The `Domain.AND` is used (not plain `&`) because `options` may contain pre-built domain fragments.

### `event_exhibitors` — Directory Listing

**Key behaviors:**

- `search_domain` accumulates filters: text search on `name` and `website_description`, country filter via `partner_id.country_id`, sponsorship type filter via `sponsor_type_id`.
- `sponsors_all` (unfiltered) is fetched separately to populate the filter sidebar without applying search criteria.
- **Randomization**: `random.sample()` shuffles sponsors within each tier on every page load. Event staff see published sponsors first, unpublished last (within tier).
- `event.event_slot_ids._filter_open_slots().grouped('date')` — passes open event slots to the template for rendering alongside sponsors.
- `hide_sponsors=True` passed to template suppresses the default event footer sponsor strip in favor of the full exhibitor page.
- `request.env['event.sponsor'].sudo().search(...)` — `sudo()` is required because public users lack direct read access to sponsors; the `ir.rule` on `event.sponsor` restricts what they can see at the record level.

### `event_exhibitor` — Detail Page

**Access check:**
```python
if not sponsor.has_access('read'):
    raise Forbidden()
```

Uses `has_access()` (from `base` model) rather than `check_access_rights()` — it validates both model-level ACL and record-level rules (the ir.rule that limits public users to `website_published=True`).

**Other exhibitor sidebar** — sorted by:
1. `website_published` desc (published first)
2. `is_in_opening_hours` desc (live exhibitors first)
3. `partner_id.country_id == current_country` (local exhibitors first)
4. `-1 * sponsor_type_id.sequence` (higher tiers first)
5. `randint(0, 20)` (random tiebreaker for fairness)

Returns top 30 in `sponsors_other`.

### `event_sponsor_read` — JSON-RPC Data Endpoint

Returns a flat dict of sponsor + event fields used by frontend JavaScript to render the "event not started" or "exhibitor closed" modal dialog. Called via `jsonrpc` (not `json`) — meaning Odoo's RPC serializer handles type conversion. All values are explicitly extracted via `read()` then augmented with formatted strings (`hour_from_str`, `hour_to_str` via `format_duration`).

---

## Security

### ir.rule — Record-Level Access

**File:** `security/security.xml`

```xml
<field name="domain_force">[('website_published', '=', True)]</field>
<field name="groups" eval="[(4, ref('base.group_public')), (4, ref('base.group_portal'))]"/>
```

Applied to `base.group_public` and `base.group_portal`. Both groups get **read-only** access (`perm_write/create/unlink = False`). Internal employees with `event.group_event_manager` have full access (no rule applies).

This means:
- Public/portal users can only browse published sponsors via the website.
- Unpublished sponsors are **invisible** to public users even if they know the URL (the ORM filters them out).
- No write/create/unlink for public or portal — all sponsor management happens in the backend by event managers.

### ir.model.access.csv — ACL Summary

| ACL Entry | Model | Group | R | W | C | D |
|-----------|-------|-------|---|---|---|---|
| `access_event_sponsor_type_manager` | `event.sponsor.type` | `event.group_event_manager` | 1 | 1 | 1 | 1 |
| `access_event_sponsor_manager` | `event.sponsor` | `event.group_event_manager` | 1 | 1 | 1 | 1 |
| `access_event_sponsor_public_public` | `event.sponsor` | `base.group_public` | 1 | 0 | 0 | 0 |
| `access_event_sponsor_public_portal` | `event.sponsor` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `access_event_sponsor_public_employee` | `event.sponsor` | `base.group_user` | 1 | 0 | 0 | 0 |

`base.group_user` (employees) have read-only access to sponsors even without the event manager group. This allows employees to view sponsors without necessarily managing events.

### Security Considerations

- **`bypass_search_access=True`** on `sponsor_type_id` and `partner_id` Many2one fields: needed because the standard `check_field_access_rights` would block public users from searching/selecting partners or sponsor types during sponsor creation on the website (if a public-facing creation form existed). In practice, sponsors are created from the backend, but this flag future-proofs the field.
- **XSS risk**: `website_description` is an Html field with `sanitize_attributes=False, sanitize_form=True` — this allows rich HTML content (from partners or manually entered) while still sanitizing form input. Custom sanitization overrides may be applied via `sanitize_overridable=True`.
- **Partner data leakage**: Public users can read published sponsors' partner-related fields (`partner_name`, `partner_email` as related fields, `country_id`, `url`) without being logged in. Ensure sponsors linked to partners with sensitive contact information are not published.
- **`get_base_url()` routing**: Returns `event_id.get_base_url()`, correctly routing multi-website scenarios (each website has its own domain/base URL).

---

## URL Structure

```
/event/<event-slug>/exhibitors         → Exhibitor directory listing
/event/<event-slug>/exhibitor/<sponsor-slug>  → Individual exhibitor page
```

Slugs are generated via `ir.http._slug()` on both the event and sponsor records. If the sponsor `name` contains special characters, the slug sanitizes them.

---

## Odoo 18 → 19 Changes

- Version bump `1.0` → `1.1` in manifest.
- **SCSS assets**: The module now ships dedicated `scss` files for sponsor and exhibitor templates, migrated from inline or older asset handling.
- **`event_connect` interactions**: New static interaction files under `static/src/interactions/` and a `exhibitor_connect_closed_dialog` component — indicates real-time or interactive exhibitor features added in 19.
- **`event_full_page_ticket_report.scss`**: New report stylesheet, suggesting ticket PDF now renders sponsor logos in a full-page layout.
- **Website builder assets**: `static/src/website_builder/**` — dedicated snippets for the website builder CMS.
- **`event_sponsor_read` jsonrpc endpoint**: Marshalling endpoint for frontend modals (likely tied to the new interaction system).
- **`event.event` menu management**: `_get_menu_type_field_matching()` and `copy_event_menus()` — improved menu lifecycle management for event duplication.

---

## Extension Points

| Goal | Method/Field to Override |
|------|--------------------------|
| Add a new exhibitor type | Add to `event.sponsor.exhibitor_type` selection + update `_get_event_sponsors_base_domain()` and `_search_get_detail()` |
| Custom partner sync logic | Override `_synchronize_with_partner()` |
| Override URL behavior | Override `_compute_website_url()` after calling `super()` |
| Custom opening hours calculation | Override `_compute_is_in_opening_hours()` |
| Different randomization strategy | Override sorting in `_event_exhibitors_get_values()` |
| Add fields to the jsonrpc response | Extend dict in `event_sponsor_read()` controller |
| Custom ribbon styling | Extend `display_ribbon_style` selection + add SCSS classes |
| Extend exhibitor sidebar sort | Override `sponsors_other` sorted() in `_event_exhibitor_get_values()` |

---

## Related Modules

| Module | Relationship |
|--------|-------------|
| `event` | Base event models (`event.event`, `event.type`) |
| `website_event` | Website event framework; provides `WebsiteEventController`, website menu infrastructure |
| `event_sale` | Booth selling (separate feature, not integrated here) |
| `website_event_booth` | Booth reservation management on website (parallel feature) |
| `mail` | Provides `mail.thread` (chatter) and `mail.activity.mixin` |
| `website` | Provides `website.published.mixin`, `website.searchable.mixin`, `website.image_url()` |

---

## See Also

- [Modules/Event](event.md) — base event module
- [Modules/website_event](website_event.md) — website event integration
- [Modules/website_event_booth](website_event_booth.md) — booth reservation module (parallel feature)
- [Modules/res.partner](res.partner.md) — partner model that sponsors link to
- [Core/Fields](Fields.md) — Image, Html, Selection field types
- [Core/API](API.md) — `@api.depends`, `@api.model`, computed + stored fields
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) — mixin inheritance patterns

---

## L4: Security Deep Analysis

### `ir.rule` Domain Force — Access Control Design

The record rule on `event.sponsor` uses a single condition:

```xml
<field name="domain_force">[('website_published', '=', True)]</field>
```

This rule is applied to `base.group_public` and `base.group_portal`. Both groups have **read-only ACL** for `event.sponsor`.

**Interaction with `website.published.mixin`**: The `website_published` field is a boolean on `event.sponsor` (inherited from the mixin). The mixin's `_synchronize_with_stage()` is NOT called on `event.sponsor` — sponsorship publication is managed manually by event staff. The `website_published` flag is the sole gate.

**Portal vs. Public distinction**: Both groups receive the same rule. However, portal users can have additional context — they may be associated with the sponsor partner via a `partner_id` relationship. The record rule does not account for this — a portal user can only see published sponsors, even if they are listed as the sponsor contact.

**Internal employee access**: Employees with `event.group_event_manager` have no rule applied (no `groups` on the record rule). They bypass the rule entirely and see all sponsors (published and unpublished), which is the intended behavior for event management staff.

### `bypass_search_access=True` Security Rationale

Both `sponsor_type_id` and `partner_id` on `event.sponsor` have `bypass_search_access=True`:

```python
sponsor_type_id = fields.Many2one(
    'event.sponsor.type', 'Sponsorship Level',
    default=lambda self: self._default_sponsor_type_id(),
    required=True, bypass_search_access=True)

partner_id = fields.Many2one('res.partner', 'Partner',
    required=True, bypass_search_access=True)
```

**What it does**: The flag disables Odoo's field-level access right checks during name_search and direct `search()` operations on these fields. Normally, a public user attempting to search `res.partner` via a name search would be denied by field access rights. With `bypass_search_access=True`, the search proceeds.

**Security implication**: This flag allows public users (via the website form, if any) or the backend staff to search and select any partner or sponsor type without explicit read ACL on those models. For `partner_id`, this is safe because the partner search is always constrained to the current record's partner set. For `sponsor_type_id`, there is no sensitive data in the sponsor type model.

**Risk**: If a future update adds a public-facing sponsor creation form on the website, the `bypass_search_access=True` on `partner_id` would allow searching any partner in the system, not just the sponsor's own partner. The current module has no such form — sponsors are created in the backend only.

### XSS in `website_description`

```python
website_description = fields.Html(
    'Description',
    compute='_compute_website_description',
    sanitize_overridable=True,
    sanitize_attributes=False, sanitize_form=True,
    translate=html_translate,
    readonly=False, store=True)
```

`sanitize_attributes=False` means HTML attributes (e.g., `onclick`, `onerror`, `style` with expressions) are not stripped from the stored HTML. `sanitize_overridable=True` allows integrators to register custom sanitizers via `html_sanitize` overrides.

**Risk**: If a sponsor with malicious HTML in their `website_description` is published, that HTML is rendered on the exhibitor page without attribute sanitization. The `sanitize_form=True` means the form editor's input is sanitized, but stored values can contain attributes.

**Mitigation**: `translate=html_translate` means the field is stored per-language. A sponsor's malicious content is only visible in languages where the sponsor has explicitly entered translated content. The default (fallback) description from `partner_id.website_description` may also be HTML-clean depending on how that field was stored.

### `get_base_url()` Multi-Website Routing

```python
def get_base_url(self):
    """As website_id is not defined on this record, we rely on event website_id for base URL."""
    return self.event_id.get_base_url()
```

`event.sponsor` does not define `website_id` directly. The sponsor's `get_base_url()` delegates to the event's website. This ensures that when `website.published.mixin` generates `website_absolute_url`, it uses the correct website domain.

**Multi-website scenario**: An event is associated with website A (company.com/events). Sponsors of that event have URLs like `https://company.com/event/.../exhibitor/...`. If the event is duplicated to website B (company.fr/events), the same sponsors now appear under the French website with correct French domain URLs.

---

## L4: Odoo 18 → 19 Specific Changes

### `event_sponsor_read` JSON-RPC Endpoint

The `/event_sponsor/<int:sponsor_id>/read` endpoint was likely introduced or significantly modified in Odoo 19. It serves as a data marshalling endpoint for the new interaction system (`event_connect`):

```python
@http.route('/event_sponsor/<int:sponsor_id>/read', type='jsonrpc', auth='public', website=True)
def event_sponsor_read(self, sponsor_id):
    sponsor = request.env['event.sponsor'].browse(sponsor_id)
    sponsor_data = sponsor.read([...fields...])[0]
    # ... augment with sponsor_type_name, event_name, event dates, formatted hours
    return sponsor_data
```

**What changed**: In Odoo 18, the exhibitor page likely loaded all data from the page render context. In Odoo 19, this endpoint provides a JSON-RPC interface for the frontend JavaScript to fetch sponsor data dynamically, likely for modal dialogs ("event not started / sponsor not available") in the interaction system.

**Version note**: The `type='jsonrpc'` declaration means Odoo uses its own JSON-RPC protocol (via `JsonRPC` in web client). This differs from `type='json'` which uses plain JSON POST/RPC.

### SCSS Asset Migration

In Odoo 18, sponsor/exhibitor styling may have been inline or handled through older asset mechanisms. In Odoo 19, the module ships dedicated `scss` files (`exhibitor.scss`, `sponsor.scss`) under `static/src/scss/`. This aligns with Odoo's ongoing SCSS migration across all website modules.

**Impact**: Custom overrides that patch inline CSS may break. The recommended approach is to override SCSS variables or use `website_asset_common` to extend the stylesheet.

### Menu Management — `_get_menu_type_field_matching()` and `copy_event_menus()`

The exhibitor module added proper implementations of these menu lifecycle methods in Odoo 19:

```python
def _get_menu_type_field_matching(self):
    res = super()._get_menu_type_field_matching()
    res['exhibitor'] = 'exhibitor_menu'
    return res

def copy_event_menus(self, old_events):
    super().copy_event_menus(old_events)
    for new_event in self:
        new_event.exhibitor_menu_ids.menu_id.parent_id = new_event.menu_id
```

In Odoo 18, the exhibitor menu entry may have been handled through a generic fallback. The explicit implementation ensures that when an event is duplicated, the exhibitor menu entry is correctly re-parented under the new event's main menu, with the correct sequence (60) and anchor behavior.

---

## L4: Exhibitor Randomization and Fairness Algorithm

The exhibitor list page uses a randomization strategy within each tier to provide fair exposure:

```python
for sponsor_category, sponsors in sponsor_categories_dict.items():
    if is_event_user:
        published_sponsors = sponsors.filtered(lambda s: s.website_published)
        unpublished_sponsors = sponsors - published_sponsors
        random_sponsors = (
            sample(published_sponsors, len(published_sponsors)) +
            sample(unpublished_sponsors, len(unpublished_sponsors))
        )
    else:
        random_sponsors = sample(sponsors, len(sponsors))
```

**Design rationale**:
- Published and unpublished sponsors are shuffled **separately**. Within a tier, published sponsors appear first in random order, then unpublished sponsors appear in random order. This means published sponsors always appear above unpublished ones within a tier, but their internal order changes on every page load.
- For non-event users (public), all sponsors are shuffled together (no published/unpublished split, since unpublished sponsors are already excluded by the domain).
- `random.sample()` without replacement ensures each sponsor appears exactly once per tier.

**SEO implication**: The randomized order means the same sponsor appears at different positions on successive page loads. Search engines crawling the exhibitor page will see different orderings, which is acceptable — the content is the same, only the presentation order varies.

**Performance**: `sample()` on a list of sponsors (typically tens to low hundreds per tier) is O(n). For large events with hundreds of sponsors, this is negligible compared to the search query itself.

---

## L4: Failure Modes and Error Handling

### Sudo Fallback in Controller

All controller methods that read sponsor data use `.sudo()`:

```python
sorted_sponsors = request.env['event.sponsor'].sudo().search(search_domain)
sponsors_all = request.env['event.sponsor'].sudo().search(search_domain_base)
```

**Why**: Public users (and portal users with read-only ACL) cannot directly `search()` or `read()` `event.sponsor` records due to model-level ACL restrictions. The `.sudo()` bypasses these restrictions at the controller level.

**Risk**: Using `sudo()` without scoping means the controller has full access to all sponsors (including unpublished) and all partner data. The domain filter in the search call constrains the visible set. However, if the domain is accidentally removed or malformed, `.sudo().search([])` would return ALL sponsors in the system.

**Mitigation**: The domain is constructed from `_get_event_sponsors_base_domain()` which is a separate method. If the method changes, the controller is isolated from the change. The domain always includes `event_id` restriction, which prevents cross-event data leakage.

### `has_access('read')` Check on Detail Page

```python
def event_exhibitor(self, event, sponsor, **options):
    if not sponsor.has_access('read'):
        raise Forbidden()
    sponsor = sponsor.sudo()
```

The `has_access('read')` check validates both model-level ACL and record-level `ir.rule`. For unpublished sponsors, `has_access('read')` returns `False` for public users (since the record rule filters them out). The `Forbidden()` exception is raised before any template rendering.

**Edge case**: A sponsor that is visible to the user (e.g., logged-in employee with event manager rights) will pass the check. After `sudo()`, the employee can see all sponsor data. This is intentional — event managers need full access.

### Opening Hours Edge Cases

`hour_to == 0` is handled as "midnight of the next day":

```python
if sponsor.hour_to == 0:
    opening_to_tz = opening_to_tz + timedelta(days=1)
```

**What happens with `hour_to == 24`**: `float_to_time(24.0)` converts to `time(0, 0)` — midnight of the current day, not the next day. This is different from `hour_to == 0`. If a sponsor sets `hour_to = 24.0` (24-hour format), the condition `sponsor.hour_to == 0` is `False`, so the "midnight extension" does not apply. The exhibitor will show as "closed" at midnight rather than open through the night.

**Recommendation**: Document `hour_to = 0.0` as the correct way to indicate "open until end of event day." The UI should guide users to use 0.0 rather than 24.0.

### Empty Partner State

If a sponsor's `partner_id` is deleted while the sponsor record still exists:
- `partner_id.name` raises an AccessError in display contexts
- All computed fields that sync from partner (`name`, `email`, `phone`, `image_512`) return `False` because the partner is empty
- `website_description` falls back to empty string (since `partner_id.website_description` on a deleted record returns `False`)
- The sponsor page still renders but shows empty data

The `partner_id` field has `ondelete='restrict'` by default (from the Many2one). Deleting a partner that is linked to a sponsor should raise a database constraint error, preventing deletion. If the deletion was done manually via SQL (bypassing ORM), the record enters this invalid state.

---

## L4: Extension Points and Override Strategy

| Extension Goal | Override Location | Notes |
|----------------|-------------------|-------|
| Add custom exhibitor type | `event.sponsor.exhibitor_type` selection + `_get_event_sponsors_base_domain()` domain + `_search_get_detail()` base_domain | Also update controller filtering in `_event_exhibitors_get_values()` if needed |
| Custom sponsor sorting (not random) | Override `sponsor_categories` construction in `_event_exhibitors_get_values()` | Remove `sample()` calls, apply custom sort |
| Custom partner sync logic | Override `_synchronize_with_partner(fname)` | Called for name, email, phone, image_512 |
| Override URL slug pattern | Override `_compute_website_url()` after `super()` call | Ensure slug does not conflict with exhibitor list page |
| Custom ribbon CSS | Add SCSS override targeting `.s_ribbonstyle_{ribbon_style}` | Ribbon is rendered as `<div class="s_ribbon_style_{style}">` in templates |
| Add booth integration | Extend `event.sponsor` with One2many to `event.booth` | `website_event_booth` module provides booth models |
| Custom opening hours logic | Override `_compute_is_in_opening_hours()` | Consider caching result if timezone computation is expensive |
| Sponsor landing page redesign | Override QWeb template `event_exhibitor_main` | Use `t-call` pattern to include custom snippet |
