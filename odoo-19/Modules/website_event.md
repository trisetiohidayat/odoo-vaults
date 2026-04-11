---
type: module
module: website_event
tags: [odoo, odoo19, modules, website, events, registration, seo, menu]
created: 2026-04-11
updated: 2026-04-11
---

# website_event (L4)

> **Module:** `website_event` | **Path:** `odoo/addons/website_event/` | **Odoo Version:** 19 | **Manifest version:** 1.4

## Overview

`website_event` transforms `event.event` records into fully public-facing website pages. It bridges back-office event management (`event` module) with the public-facing website, providing event listing pages, individual event pages, online registration forms with seat-verified ticket management, SEO metadata, dynamic website menu generation tied to publishing state, and visitor-to-registration identity chaining. The ICS feed is served by the `event` module's controller — `website_event` only generates the URL to it.

**Core responsibility:** Expose events publicly on the website and handle registration/visitor tracking without requiring backend access.

---

## Manifest and Dependencies

```python
'depends': [
    'event',          # Core event model, registration, ticket, slot
    'website',        # Multi-website, page/menu management, visitors
    'website_partner', # Partner directory integration
    'website_mail',   # Mail/chatter on public pages
    'html_builder',   # HTML content builder
],
'category': 'Marketing/Events',
'sequence': 140,
'application': True,
```

**New in Odoo 19 vs Odoo 18:**
- `website_partner` added as explicit dependency (was implicit)
- `website_mail` added (public page chatter)
- `html_builder` added (QWeb template building)
- Version bump from 1.3 → 1.4

---

## Model Architecture

### Full File Inventory

| File | Model(s) Extended/Created | Role |
|------|--------------------------|------|
| `models/event_event.py` | `event.event` (extend) | Website fields, menu lifecycle, search, SEO |
| `models/event_registration.py` | `event.registration` (extend) | `visitor_id` linkage |
| `models/event_tag.py` | `event.tag` (extend) | `website.published.multi.mixin` |
| `models/event_tag_category.py` | `event.tag.category` (extend) | `website.published.multi.mixin` |
| `models/event_type.py` | `event.type` (extend) | `website_menu` default propagation |
| `models/event_slot.py` | `event.slot` (extend) | `_filter_open_slots()` |
| `models/website_event_menu.py` | `website.event.menu` (new) | Menu-to-page tracking, SEO metadata |
| `models/website_visitor.py` | `website.visitor` (extend) | Registration count, display name chaining |
| `models/website_menu.py` | `website.menu` (extend) | `unlink()` sync, `save()` event menu detection |
| `models/website.py` | `website` (extend) | Event page creation, search integration |
| `models/website_snippet_filter.py` | `website.snippet.filter` (extend) | Event-specific snippet preview data |

---

## Core Model: `event.event` Extension (`EventEvent`)

**File:** `models/event_event.py` | **Inherits:** `event.event`, `website.seo.metadata`, `website.published.multi.mixin`, `website.cover_properties.mixin`, `website.searchable.mixin`, `website.page_visibility_options.mixin`

### L1: Model Overview

The `EventEvent` class extends `event.event` with five mixins providing website-specific capabilities:
- `website.seo.metadata` — SEO title/description/meta tags
- `website.published.multi.mixin` — `is_published` + `website_published` toggles per website
- `website.cover_properties.mixin` — JSON cover image properties
- `website.searchable.mixin` — `_search_get_detail` for global website search
- `website.page_visibility_options.mixin` — `website_visibility` field (`public`, `link`, `logged_users`)

### L2: All Fields with Type, Default, and Constraints

#### Website Visibility Fields

**`website_visibility`** — `Selection`, stored, `required=True`, `default='public'`, `tracking=True`
```
Values: 'public', 'link', 'logged_users'
```
- `'public'`: Event is fully discoverable in listings and search
- `'link'`: Event is hidden from listings and search; only accessible via direct URL. Note: direct URL access works regardless of this setting
- `'logged_users'`: Hidden from public listings, visible to authenticated website users
- **Performance note:** `_compute_is_visible_on_website` short-circuits to `True` for all events if every event in `self` has `website_visibility == 'public'`, avoiding per-record iteration on listing pages

**`is_visible_on_website`** — `Boolean`, computed (search), no stored value
- Recomputes on every access; relies on `_search_is_visible_on_website` for domain filtering
- **Logic:**
  - `public` events: always visible
  - `logged_users`: visible if current user is not public
  - `link`: only visible if `is_participating` is `True` (registered attendee bypass)
- **Security implication:** This field bypasses the standard ORM `website_id` domain by using `website.website_domain()` inside `_search_get_detail`, not at the record-level compute

**`is_participating`** — `Boolean`, computed (search), no stored value
- **Heuristic (executed in `_fetch_is_participating_events`):**
  1. If public user with no visitor cookie: returns empty recordset (not participating)
  2. Checks only `state in ['open', 'done']` registrations (draft registrations do not count)
  3. Anonymous visitors (cookie-based): matches on `visitor_id`
  4. Authenticated users: matches on `partner_id`
  5. Both can coexist: visitor may have no partner, or may have a linked partner; the domain uses OR: `visitor_id = X OR partner_id = Y`
- **Search override only supports `operator == 'in'`** — other operators return `NotImplemented`

**`website_published`** — `Boolean`, stored, `tracking=True`
- Mirrors the `is_published` field from `website.published.multi.mixin` for per-website toggle
- Both fields together drive the `_track_subtype` publishing notification

**`is_published`** — Provided by `website.published.multi.mixin`, stored, drives publication on website

#### Registration Fields

**`event_register_url`** — `Char`, computed, no stored value
- Depends on `website_url`; computes `urljoin(base_url, website_url + '/register')`
- `tools.urls.urljoin` handles HTTPS/HTTP scheme correctly across base URLs

**`subtitle`** — `Char`, stored, `translate=True`
- Used in OpenGraph description and Twitter description in `_default_website_meta`
- Also used as `default_meta_description`

#### Menu Fields (all stored editable)

| Field | Type | Computed From | Notes |
|-------|------|--------------|-------|
| `website_menu` | Boolean | `_compute_website_menu` (precompute) | Syncs from `event_type_id.website_menu`; `store=True` |
| `menu_id` | Many2one `website.menu` | — | Root menu for this event; cascade-delete drives full menu removal |
| `introduction_menu` | Boolean | `_compute_website_menu_data` | Syncs from `website_menu` on event type change |
| `register_menu` | Boolean | `_compute_website_menu_data` | Same |
| `community_menu` | Boolean | `_compute_community_menu` | Always `False` in base module; submodules override |
| `introduction_menu_ids` | One2many | — | `domain=[("menu_type", "=", "introduction")]` |
| `register_menu_ids` | One2many | — | `domain=[("menu_type", "=", "register")]` |
| `community_menu_ids` | One2many | — | `domain=[("menu_type", "=", "community")]` |
| `other_menu_ids` | One2many | — | `domain=[("menu_type", "=", "other")]` |

#### Timing Fields (all computed, not stored)

| Field | Type | Logic |
|-------|------|-------|
| `is_ongoing` | Boolean | `date_begin_utc <= now_utc <= date_end_utc` |
| `is_done` | Boolean | `now_utc > date_end_utc` |
| `start_today` | Boolean | `date_begin_utc.date() == now_utc.date()` |
| `start_remaining` | Integer (minutes) | Minutes until `date_begin`; `0` if already started |

**Timezone note:** All time computations are done in UTC. `date_begin`/`date_end` are naive datetimes in DB; they are localized using `is_dst=False`. `date_tz` from event configuration is used for Google Calendar URL generation, not for the `is_ongoing` computation.

#### Cover and SEO Fields

**`cover_properties`** — Provided by `website.cover_properties.mixin`; defaults to `website_event/static/src/img/event_cover_4.jpg` at 40% opacity with `cover_auto` resize class.

**`website_url`** — Override of mixin computation, forces `/event/{slug}` prefix path.

---

## Mixin Inheritance Chain

```
event.event
  └── website.seo.metadata
        └── website.published.multi.mixin  (is_published, website_published)
  └── website.cover_properties.mixin  (cover_properties JSON)
  └── website.searchable.mixin  (_search_get_detail, _search_render_results)
  └── website.page_visibility_options.mixin  (website_visibility)
```

### `website.published.multi.mixin` Behavior

- Provides `is_published` (Boolean, stored) and `website_published` (Boolean, stored)
- `_track_subtype` in `EventEvent` fires `mt_event_published` / `mt_event_unpublished` when either `is_published` or `website_published` changes
- **Security:** `website_event` adds an `ir.rule` (`event_event_public`) that allows `base.group_public` and `base.group_portal` to read `event.event` records only if `website_published = True` — but this is a read-only rule; write access is always denied for public/portal users

---

## Website Menu Lifecycle

### Menu State Machine

```
Event Created with website_menu = True
  → write() triggers _split_menus_state_by_field()
  → _get_menus_update_by_field() finds all menu fields are toggled from False → True
  → _update_website_menus() called
  → Creates root website.menu (name=event.name, website_id=event.website_id)
  → For each enabled menu type (introduction/register/community):
      → _update_website_menu_entry() → _create_menu()
        → If xml_id (e.g. template_intro): calls website.new_page() to create ir.ui.view + website.page
        → Creates website.menu with parent=menu_id
        → Creates website.event.menu linking menu + event + menu_type
  → Copy event (copy_event_menus): duplicates all menus, reassigns parent_id
  → website_menu = False: SQL cascade unlink of root menu + all children (via _update_website_menus)

Event Created with website_menu = False
  → No menus created (early return in _update_website_menus when menu_id is falsy)
  → Toggle website_menu = True later: creates menus from scratch
```

### Menu Type Field Matching

| `menu_type` value | Boolean flag field | O2M tracking field |
|-------------------|--------------------|--------------------|
| `'introduction'` | `introduction_menu` | `introduction_menu_ids` |
| `'register'` | `register_menu` | `register_menu_ids` |
| `'community'` | `community_menu` | `community_menu_ids` |
| `'other'` | (no boolean) | `other_menu_ids` |

**Sub-menu creation:** `_get_website_menu_entries` returns a 6-tuple: `(Name, url, xml_id, sequence, menu_type, parent_menu_type)`. The `parent_menu_type` parameter enables creating child menus under an existing menu entry.

### Custom Page Creation via Website Editor

When a designer adds a menu inside an event via the website editor:
1. `website.menu.save()` is called (overridden in `website_event`)
2. New menu IDs (string keys) are identified before `super().save()`
3. `super().save()` creates the menu records
4. Code walks up parent menus to find the event root
5. If a `website.event.menu` exists for the parent, the new menu is treated as an event sub-menu
6. URL is rewritten from `/mypage` → `/event/my-event/page/mypage`
7. A `website.event.menu` record is created with `menu_type='other'`
8. The view is attached to the `website.event.menu` for editor binding

### Cascade Delete Chain

```
website.event.menu.unlink()
  → unlink() calls view_id.sudo().unlink()
    → ir.ui.view.unlink() cascades to website.page
      → website.page.unlink() cascades to website.menu
  → super().unlink() (website.event.menu)
```

When a root `website.menu` is unlinked:
- `website.menu.unlink()` is overridden; it finds all `website.event.menu` records linked to those menus
- For each `website.event.menu`, it finds the matching boolean field and sets it to `False`
- Then it explicitly unlinks `website.event.menu` records (triggering the cascade above)
- Finally calls `super().unlink()` on remaining menus

---

## Registration Pipeline

### Full Request Flow

```
1. GET /event/my-event/register
   → WebsiteEventController.event_register()
   → _prepare_event_register_values(): loads event, slots, visitor timezone
   → Renders registration form (with tickets visible)

2. POST /event/<id>/registration/new (JSONRPC)
   → _process_tickets_form(): parses form_details for nb_register-{ticket_id} keys
     - Validates tickets belong to this event
     - Calls ticket._get_current_limit_per_order() per ticket
   → Availability check: event.seats_available vs ordered_seats
   → Returns rendered registration_attendee_details template

3. POST /event/<id>/registration/slot/<slot_id>/tickets (JSONRPC)
   → After slot selection, returns modal with slot-specific ticket availability
   → Calls event._get_seats_availability(slot_tickets) for seat availability

4. POST /event/<id>/registration/confirm
   → reCAPTCHA verification: ir.http._verify_request_recaptcha_token('website_event_registration')
     - On failure: redirect to register?registration_error_code=recaptcha_failed
   → _process_attendees_form():
     - Parses form fields: '{index}-{field}' for core fields, '{index}-{type}-{qid}' for questions
     - type: 'simple_choice' or 'text_box'
     - index=0 means "general answer" (applies to all registrations in the order)
     - General identification fields (name/email/phone/company_name) also use index=0
     - Validates ticket_id belongs to this event's ticket set
   → Counter (Counter from collections) collapses registrations by (slot_id, ticket_id)
   → event._verify_seats_availability(): raises ValidationError if insufficient seats
     - On failure: redirect to register?registration_error_code=insufficient_seats
   → _create_attendees_from_registration_post():
     - Gets or creates visitor via _get_visitor_from_request(force_create=True)
     - For each registration:
       - Sets partner_id: visitor.partner_id if available, else request.env.user.partner_id (if not public)
       - Sets visitor_id: always set to current visitor (even if partner_id is set)
       - Appends to registrations_to_create list
     - sudo().create() — bypasses ACL because public users create registrations
   → Redirect to /event/<id>/registration/success?registration_ids=...

5. GET /event/<id>/registration/success
   → Validates visitor exists (raises NotFound if not)
   → Searches registrations by id IN list AND event_id AND visitor_id (strict triple-match)
   → Returns confirmation page with Google Calendar and iCal links
```

### `_process_attendees_form` Key Parsing Logic

| Form key format | Meaning |
|-----------------|---------|
| `'{n}-name'`, `'{n}-email'` | Core field for attendee index n; n=0 = general (applies to all) |
| `'{n}-simple_choice-{qid}'` | Multiple choice answer for question qid, attendee n; n=0 = general |
| `'{n}-text_box-{qid}'` | Free-text answer for question qid, attendee n; n=0 = general |

**Failure modes:**
- If `event_ticket_id` ticket is not in `event.event_ticket_ids`: raises `UserError`
- If `current_limit_per_order` exceeded: `limit_check = False` returned to template (blocks submission)
- If `seats_available < ordered_seats`: `ValidationError` from `_verify_seats_availability` (redirects back)

### reCAPTCHA Integration

- Token verified via `ir.http._verify_request_recaptcha_token('website_event_registration')`
- Token is submitted as `recaptcha_token_response` in the form POST
- If verification fails, user is redirected back to registration page with `registration_error_code=recaptcha_failed`
- **Performance note:** reCAPTCHA check happens before any seat availability check, avoiding wasted seat reservation on bot submissions

---

## Website Visitor Extension (`WebsiteVisitor`)

**File:** `models/website_visitor.py`

### Identity Chaining Logic

**`_compute_display_name` override:**
- Runs after `super()` result is computed
- For anonymous visitors (no `partner_id`) with registrations: `display_name = last registration's name`
- Uses `sudo()` to bypass ACL on `event_registration_ids`
- Sorted by `(create_date, id)` ascending — so the most recent non-last-one is used (Python's `[-1]`)

**`_compute_email_phone` override:**
- After `super()` (which propagates from partner), falls back to registrations
- Registrations sorted by `(create_date, id)` ascending (oldest first)
- Takes first registration with non-empty email/mobile
- **Edge case:** If visitor has a partner, `super()` already set email/phone from partner; the registration fallback only fires if those are still empty

**`event_registration_count`:** Uses `_read_group` for efficient counting instead of `search_count`, avoiding full recordset fetch.

**`_inactive_visitors_domain` — Permanent Activity Rule:**
```python
return super()._inactive_visitors_domain() & Domain('event_registration_ids', '=', False)
```
- Standard inactive rule (last visit > 1 year ago) is AND-ed with `no event registrations`
- **Implication:** Any visitor with at least one draft/open/done registration is permanently immune to inactivity cleanup — even if they haven't visited in years
- **Security note:** Prevents accidental deletion of visitor records that have business-critical registration data

**Visitor Merge (`_merge_visitor`):**
1. Reassigns all `event_registration_ids.visitor_id` to target
2. For registrations without a partner: copies `target.partner_id`
3. Then calls `super()` (which merges tracking/tracking lines)
4. **Note:** Registration reassignment happens BEFORE the standard visitor merge (which handles partner merging, access rights, etc.)

---

## Security Model

### `ir.rule` Summary (from `event_security.xml`)

| Rule | Model | Condition | Groups |
|------|-------|-----------|--------|
| `event_event_public` | `event.event` | `website_published = True` | `base.group_public`, `base.group_portal` |
| `ir_rule_event_tag_public` | `event.tag` | `category.website_published AND color != False AND color != 0` | public, portal |
| `ir_rule_event_event_ticket_public` | `event.event.ticket` | `event_id.website_published = True` | public, portal |
| `ir_rule_event_slot_public` | `event.slot` | `event_id.website_published = True` | public, portal |
| `ir_rule_event_question_published` | `event.question` | `event_ids` has any `is_published = True` | public, portal, user |
| `ir_rule_event_question_event_user` | `event.question` | `(1, '=', 1)` (no filter) | `event.group_event_registration_desk` |
| `ir_rule_event_question_answer_*` | `event.question.answer` | Same pattern as question | Same groups |

### ACL CSV Summary (from `ir.model.access.csv`)

| ACL Entry | Model | Groups | R | W | C | D |
|-----------|-------|--------|---|---|---|---|
| `access_event_event_public` | `event.event` | `base.group_public` | 1 | 0 | 0 | 0 |
| `access_event_event_portal` | `event.event` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `access_event_event_employee` | `event.event` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_website_event_menu_public` | `website.event.menu` | `base.group_public` | 1 | 0 | 0 | 0 |
| `access_website_event_menu_user` | `website.event.menu` | `event.group_event_user` | 1 | 1 | 1 | 1 |

**Key insight:** `event.group_event_manager` gets `implied_ids` of `website.group_website_restricted_editor` — this means event managers can use the website editor to customize event pages.

### Public Search Domain Bypass

In `_search_get_detail`, the `search_in_address` function:
```python
def search_in_address(env, search_term):
    ret = env['event.event'].sudo()._search([
       ('address_search', 'ilike', search_term),
    ])
    return [('id', 'in', ret)]
```
Uses `sudo()` to bypass partner ACL when searching event locations. This is safe because the final domain is `[('id', 'in', ret)]` which applies the standard record-level ir.rule afterward.

---

## Search and Filtering (`_search_get_detail`)

### Domain Construction Order

1. `website.website_domain()` — limits to current website
2. `is_visible_on_website = True` — visibility filter
3. `event_type_id` filter (if not 'all')
4. Per-category tag AND groups (within each category, tags are OR; across categories, they are AND)
5. Country filter: `'online'` → `country_id = False`; numeric → specific country; `'all'` → no filter
6. Date filter (from `_search_build_dates`): appended based on selected date tab

### Tag Filter AND/OR Logic

```python
for tags in search_tags.grouped('category_id').values():
    domain.append([('tag_ids', 'in', tags.ids)])
```
- Groups tags by their `category_id`
- Each group creates one `('tag_ids', 'in', [tag_ids_in_group])` clause
- All groups are AND-ed together
- Within a group, `('tag_ids', 'in', [ids])` means OR (any tag in the group matches)
- **Example:** Tags `[age:10-12, age:12-15, football]` with categories `[age, activity]` produces:
  - `('tag_ids', 'in', [age:10-12_id, age:12-15_id])` AND `('tag_ids', 'in', [football_id])`
  - Meaning: (age 10-12 OR age 12-15) AND (activity = football)

### Date Filter Construction

| Filter | Domain |
|--------|--------|
| `scheduled` | `date_end >= now` |
| `today` | `date_end > now AND date_begin < today_end_utc` |
| `This month` (month 0) | `date_end >= now AND date_begin < next_month_begin` |
| `Past Events` (old) | `date_end < now` |
| `All` | no date filter |

The `today` end is computed in the user's tz then converted to UTC for comparison against naive UTC datetimes in DB.

### Fuzzy Search

- `allowFuzzy: not post.get('noFuzzy')` passed as option
- `website._search_with_fuzzy("events", search, limit=page*step, ...)` does fuzzy matching on `name` field
- Returns `(count, details, fuzzy_term)` — the fuzzy term replaces the original search term in the pager

---

## SEO for Events

### `_default_website_meta` Field Priority

```python
res = super()._default_website_meta()  # pulls from mixin chain
# Then overrides:
event_cover_properties = json.loads(self.cover_properties)
og:image = background-image[4:-1].strip("'")  # strips url('...')$
og:title = self.name
og:description = self.subtitle
twitter:title = self.name
twitter:description = self.subtitle
twitter:card = 'summary'
default_meta_description = self.subtitle
```

**OpenGraph/Twitter image:** Extracted from the event's cover image (stored in `cover_properties` as a JSON string with `background-image` key). The string slicing `background-image[4:-1].strip("'")` handles both single-quoted (`url('/path')`) and double-quoted (`url("/path")`) formats.

**Twitter card type:** Always `'summary'` — not `'summary_large_image'`. Events do not get the larger image treatment on Twitter.

**Odoo 18 → 19 change:** The `og:image` extraction logic changed from a direct regex extraction to string slicing. The current approach is fragile if the JSON field format changes but supports both quote styles.

### SEO Title and Meta Description

- `og:title` and `twitter:title` both use `self.name` (the event title)
- `og:description`, `twitter:description`, and `default_meta_description` all use `self.subtitle`
- If `subtitle` is empty, OpenGraph and Twitter descriptions are empty strings
- The `website.seo.metadata` mixin provides `name` and `subtitle` for the `<title>` tag and meta description

---

## Event-specific_page Mechanism

### How Event Pages Work

Events use a combination of QWeb templates and `website.event.menu` records to create pages:

1. **Root event page** (`/`): Rendered by the main controller, not a stored `website.page`. The event listing/landing page is a dynamic route.

2. **Sub-pages**: Created via `_create_menu()` which calls `website.new_page()` for template-based menus (e.g., `template_intro`). This creates:
   - An `ir.ui.view` record from the QWeb template
   - A `website.page` record linked to the view
   - A `website.menu` entry pointing to the page URL
   - A `website.event.menu` linking all three to the event

3. **Page URL format**: `/event/{event-slug}/page/{view-key}`
   - The view key is prefixed with `website_event.` (e.g., `website_event.template_intro`)
   - When duplicated via the website editor, the key gets a `-t{timestamp}` suffix for uniqueness

4. **Custom editor pages**: When a designer creates a custom page via the website editor inside an event:
   - `website.menu.save()` detects the event parent menu
   - Creates `website.event.menu` with `menu_type='other'`
   - Links the page's `ir.ui.view` to the menu
   - URL is rewritten to fit the event's URL structure

5. **`view_id` on `website.event.menu`**: Used to bind the page's view to the menu for WYSIWYG editor activation. When the editor opens a page, it looks up the `website.event.menu` record by URL to find the event context.

### Page Visibility

Event pages respect `website_visibility` and `is_participating`:
- `website.event` ir.rule controls access to `event.event`
- Individual pages are served by the `website_event` controller which checks the event's visibility before rendering
- Pages linked to unpublished events return 404 via the controller's event lookup

---

## Google Calendar / iCal Integration

### `_get_event_resource_urls(slot=False)`

- `slot` parameter allows generating calendar links for a specific sub-event slot
- When `slot` is provided: uses `slot.start_datetime` and `slot.end_datetime` for the date range
- `date_tz` (event's timezone setting) is passed as the `ctz` parameter to Google Calendar
- `location` is taken from `address_inline` (multi-line formatted address), not `address_id.name`
- ICS URL: `/event/{id:d}/ics` — note the `d` format specifier forces integer formatting even if event was a recordset
- When `slot_id` is provided as a query param: `iCal_url += '?slot_id={slot_id}'`

**ICS route handler** is in `event/controllers/main.py` (the `event` module), not in `website_event`. The `website_event` module only generates the URL.

---

## Snippet Filter Architecture

### `website_snippet_filter` Data Records

Two predefined snippet filters installed via `data/website_snippet_data.xml`:

**`Upcoming Events`** (`ir_filters_event_list_snippet`):
- Domain: `[('date_begin', '>=', 'now'), ('is_visible_on_website', '=', True)]`
- Sort: `date_begin asc`
- Limit: 16

**`Upcoming and Ongoing Events`** (`ir_filters_event_list_snippet_unfinished`):
- Domain: `[('is_finished', '=', False), ('is_visible_on_website', '=', True)]`
- Uses the `is_finished` computed field from `event.event`

### Hardcoded Sample Merging

`_get_hardcoded_sample` merges generic website snippet samples with event-specific data:
- Cycle through both sample lists using modulo indexing
- Merges dictionaries: `{**generic_sample, **event_sample}` — event data overrides generic fields
- Field names used: `name`, `subtitle`, `cover_properties`, `date_begin`, `date_end`
- Used in the website editor when no real events match the filter

### Default Field Names Override

When `model == 'event.event'`:
```python
defaults['field_names'] = 'name,subtitle'
```
Overrides the generic snippet filter's default `field_names` (which would include body text fields that don't exist on `event.event`).

---

## Website Model Extension (`models/website.py`)

### Event Page Creation Override

`new_page()` is overridden to detect event page creation:

1. Only activates when `template == 'website.default_page'` and `name.startswith('event/')`
2. Searches `website.event.menu` for a menu with that URL
3. If found: switches template to `website_event.layout` (the event wrapper)
4. After `super().new_page()` creates the page:
   - Links the created `view_id` to the `website.event.menu`
   - Rewrites the view key to `website_event.{event-name}-{page-name}` for uniqueness
   - Modifies the QWeb arch to move sections from `wrap` to `oe_structure_website_event_layout_1`
   - Strips editor sub-message attributes from the container

### `_search_get_details` Extension

Appends `event.event._search_get_detail(self, order, options)` to the website's global search results when `search_type in ['events', 'all']`. This enables the website's top-right search bar to return event results alongside pages and blog posts.

### Suggested Controllers

`get_suggested_controllers` adds the Events entry pointing to `/event`, appearing in the website editor's "Add page" suggestions.

### CTA Data

`get_cta_data()` returns `{'cta_btn_text': 'Next Events', 'cta_btn_href': '/event'}` when `website_purpose == 'sell_more'` and `website_type == 'event'`. This drives the website's call-to-action button on event-related pages.

---

## `website.event.menu` Model

**File:** `models/website_event_menu.py` | **Inherits:** `website.seo.metadata` | **_rec_name:** `menu_id`

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `menu_id` | Many2one `website.menu` | `ondelete='cascade'` |
| `event_id` | Many2one `event.event` | `index='btree_not_null'`, `ondelete='cascade'` |
| `view_id` | Many2one `ir.ui.view` | `ondelete='cascade'`, used for QWeb-template menus |
| `menu_type` | Selection | `'community'`, `'introduction'`, `'register'`, `'other'` |

### `copy()` Method

- Duplicates the linked `view_id` with a new key: `old_key + '-t{timestamp}'`
- The timestamp suffix ensures `_is_active()` slug parsing gets a unique integer, preventing multiple menus from being incorrectly marked active simultaneously
- Copies child view inheritance chain recursively
- Creates a new `website.page` record if the original had one
- Creates a new `website.menu` with the rewritten URL

### `unlink()` Cascade

```python
def unlink(self):
    self.view_id.sudo().unlink()  # cascades to website.page → website.menu
    return super().unlink()
```
The explicit `sudo().unlink()` of `view_id` ensures that even if the view was already deleted by a cascade from `website.menu` deletion, the unlink method handles it gracefully.

---

## Event Type Extension

**File:** `models/event_type.py`

### `community_menu` Compute Override

```python
def _compute_community_menu(self):
    for event_type in self:
        event_type.community_menu = event_type.website_menu
```

- `community_menu` is `readonly=False, store=True` on `event.type`
- Its compute is not `@api.depends('community_menu')` but rather a one-way sync: `community_menu` always mirrors `website_menu` when `website_menu` changes
- Once set, `community_menu` on the type is independent — changing `website_menu` on the type after initial creation does NOT automatically update `community_menu`
- This is because the compute only triggers on `website_menu` dependency

---

## `event_slot` Extension

**File:** `models/event_slot.py`

### `_filter_open_slots()`

Filters slots to only those:
1. With `start_datetime > now` (future slots only)
2. Where at least one ticket has available seats (or the ticket has no limit — `availability is None`)

Calls `event_id._get_seats_availability([(slot, ticket) ...])` which is a method on `event.event` that returns a list of seat counts per (slot, ticket) pair.

**Performance note:** `_filter_open_slots` is a Python `filter()` — it runs in-memory on already-fetched records, not as a database filter. It is called in the controller via `event.event_slot_ids._filter_open_slots()`.

---

## Event Tag Extensions

**Files:** `models/event_tag.py`, `models/event_tag_category.py`

Both `event.tag` and `event.tag.category` inherit `website.published.multi.mixin`, giving them `website_published` and `is_published` fields. Tags default to `is_published=True` via `_default_is_published()` on the category.

Public visibility of tags is controlled by the `ir_rule_event_tag_public` rule which requires:
- `category.website_published = True`
- `color != False AND color != 0` — uncolored tags are hidden from public listings

---

## `website.menu` Override Details

### `save()` Override — Event Sub-Menu Detection

The method must identify newly created menus BEFORE calling `super()` because `super()` replaces string IDs with integer IDs:

```python
old_menu_ids = [menu['id'] for menu in data['data'] if isinstance(menu['id'], int)]
has_new_menus = any(isinstance(menu['id'], str) for menu in data['data'])
res = super().save(website_id, data)  # string IDs → integer IDs
```

Then it walks up `parent_id` chain to find the event root menu, detects the `website.event.menu` of the parent, and rewrites child menu URLs.

**Edge case:** If a user creates a blank URL (`#`), the code prefixes with `'t{int(timestamp})'` to avoid slug parsing issues — the `'t'` prefix prevents the URL from being interpreted as a record slug.

**Security note:** `website.event.menu` records are created with `sudo()` after the `super().save()` because the website editor user may not have `event.group_event_user` permissions, but as a website designer they should be able to create event sub-pages.

### `unlink()` Override — Synchronized Boolean Reset

Before unlinking menus, the override identifies all `website.event.menu` records linked to those menus and resets their corresponding boolean fields to `False`. This keeps the event's menu state synchronized with what's actually deleted at the menu level.

---

## Performance Considerations

| Area | Issue | Mitigation |
|------|-------|------------|
| `is_visible_on_website` compute | Re-evaluates `is_participating` on every call | Short-circuit for all-public events |
| Menu creation on event write | `_update_website_menus()` runs on every `write()` | Only creates/deletes menus for fields that changed via `_get_menus_update_by_field` diffing |
| `_compute_display_name` on visitors | `sudo()` on entire recordset | Only sudo'd for the subset that needs it |
| Event listing page | `_search_with_fuzzy` with `limit=page*step` | Pages load only 12 events; fuzzy runs on full dataset for suggestions |
| `event_registration_count` | Uses `_read_group` | Returns aggregated counts without fetching individual records |
| Tag search | `grouped('category_id')` | Python grouping, not SQL — acceptable for small tag sets |
| ICS file generation | Handled by `event` module | Large events can generate large ICS; `event` module handles streaming |

### N+1 Query Risks

- `is_participating` computation uses `_read_group` which is efficient for the visitor/partner matching
- The `_search_is_participating` domain filter is applied server-side and uses the ORM correctly
- Menu field updates use `mapped()` to collect related records before bulk operations

---

## Odoo 18 → 19 Migration Changes

| Change | Before (Odoo 18) | After (Odoo 19) | Impact |
|--------|-----------------|-----------------|--------|
| `website_partner` dep | Implicit via event | Explicit dependency | Module loading order guaranteed |
| `website_mail` dep | Not present | Added | Chatter on event pages |
| `html_builder` dep | Not present | Added | Better QWeb editing |
| Tag filter URL handling | Pure GET | POST + 301 redirect for multi-tag | Reduces crawler load |
| `community_menu` on `event.type` | Stored, no compute | `@api.depends('website_menu')` compute | Syncs from type on creation |
| `is_finished` field usage | Not in snippet filter | Added to `Upcoming and Ongoing` filter | More accurate ongoing event display |
| `website.event.menu` copy | Simple copy | Copies view + children views + page + menu with URL rewrite | Full event duplication works correctly |
| Visitor display name | `super()` only | Override checks registration name for anonymous visitors | Better anonymous visitor identification |
| ICS URL format | `{id}` string slug | `{id:d}` integer format | Prevents float formatting on edge cases |
| `event_register_url` | Not computed from `website_url` | Uses `urljoin` | Handles HTTPS correctly |
| `event.event` search | Standard domain | `_search_is_visible_on_website` | Public users only see public/link+participating |
| `website.event.menu.unlink()` | Implicit cascade | Explicit `sudo().unlink()` of view_id | More reliable cleanup |

---

## Related Sub-Modules

| Module | What It Adds |
|--------|-------------|
| `website_event_track` | Tracks (sessions), speakers, agenda menu entry, quiz questions, community forum |
| `website_event_meet` | Physical meeting rooms, QR code check-in, attendee map |
| `website_event_sale` | Ticket sales via `sale.order`, payment integration |
| `website_event_blog` | Blog posts linked to events |
| `website_partner` | Partner directory on event pages (pulled in as dependency) |

The `community_menu` boolean is always `False` in `website_event` base. Sub-modules set it to `True` and populate the community page with their own content. The `EventCommunityController.community()` route returns `website.page_404` by default — submodules override this with their own route.

---

## Key File Paths

- Model: `~/odoo/odoo19/odoo/addons/website_event/models/event_event.py`
- Controller: `~/odoo/odoo19/odoo/addons/website_event/controllers/main.py`
- Community stub: `~/odoo/odoo19/odoo/addons/website_event/controllers/community.py`
- Security: `~/odoo/odoo19/odoo/addons/website_event/security/ir.model.access.csv`
- Event security rules: `~/odoo/odoo19/odoo/addons/website_event/security/event_security.xml`
- ICS route (event module): `~/odoo/odoo19/odoo/addons/event/controllers/main.py`

---

## Related Documentation

- [[Modules/Event]] — Core event module (event.event, event.registration, event.event.ticket, event.slot)
- [[Modules/Website]] — Website framework (website.menu, website.visitor, website.page)
- [[Core/API]] — `@api.depends`, `@api.depends_context`, computed fields with search
- [[Core/Fields]] — Field types, translate=True, store behavior, index='btree_not_null'
- [[Patterns/Security Patterns]] — ir.rule, ACL CSV, record-level security
- [[Patterns/Workflow Patterns]] — State machine and tracking patterns
