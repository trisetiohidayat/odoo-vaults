---
Module: website_event
Version: Odoo 18
Type: Integration
Tags: #odoo18, #events, #website, #registration, #registration-flow, #website-menu, #seo
---

# website_event — Website Event Pages

Extends `event.event` to add full website integration: event pages hosted on the website, public registration flows, website-specific menus, visitor tracking, SEO metadata, and configurable visibility per-user type.

**Module path:** `addons/website_event/`
**Key dependency:** `event` (core event module)
**Inherits on `event.event`:** `website.seo.metadata`, `website.published.multi.mixin`, `website.cover_properties.mixin`, `website.searchable.mixin`

---

## Domain Model

```
event.event ────────────────────── website_event ── N ── website.event.menu
     │                                                      (introduction / location /
     │ N event.registration                                   register / community)
     │     └── website.visitor (linked via visitor_id)        │
     │                                                      ir.ui.view (page template)
     │
     └── N event.tag (website.published.multi.mixin)
     └── N event.tag.category (website.published.multi.mixin)
     └── event.type (website_event extension adds website_menu / community_menu)
```

---

## Models

### 1. `event.event` — Event (Website Extension)

**Inherits:** `event.event`, `website.seo.metadata`, `website.published.multi.mixin`, `website.cover_properties.mixin`, `website.searchable.mixin`
**Table:** `event_event`

#### Website-Specific Fields Added by `website_event`

| Field | Type | Description |
|-------|------|-------------|
| `subtitle` | Char | Short subtitle for SEO and display (translateable) |
| `is_participating` | Boolean (computed/search) | Current user is registered with a confirmed attendee |
| `is_visible_on_website` | Boolean (computed/search) | Event visible given visibility + participation status |
| `event_register_url` | Char (computed) | Full registration URL: `<base>/event/<slug>/register` |
| `website_visibility` | Selection | `public` (default) / `link` (via link only) / `logged_users` |
| `website_published` | Boolean | Publication state (tracked) |
| `website_menu` | Boolean (computed/writable) | Display event-specific menus on website |
| `menu_id` | Many2one `website.menu` | Root website menu for this event |
| `introduction_menu` | Boolean | Show Introduction page/menu |
| `introduction_menu_ids` | One2many `website.event.menu` | Introduction sub-menu records |
| `location_menu` | Boolean | Show Location page/menu |
| `location_menu_ids` | One2many `website.event.menu` | Location sub-menu records |
| `address_name` | Char (related) | Convenience: `address_id.name` |
| `register_menu` | Boolean | Show Info / Registration page/menu |
| `register_menu_ids` | One2many `website.event.menu` | Info sub-menu records |
| `community_menu` | Boolean | Show Community tab (base: always False; extended by sub-modules) |
| `community_menu_ids` | One2many `website.event.menu` | Community sub-menu records |
| `is_ongoing` | Boolean (computed/search) | Event dates include current time |
| `is_done` | Boolean (computed) | Event end date is in the past |
| `start_today` | Boolean (computed) | Event begins today |
| `start_remaining` | Integer (computed) | Minutes until event starts |

#### Key Methods

**Visibility / Participation:**

- `_compute_is_participating()` / `_search_is_participating()` — Determines if the current user/visitor has a confirmed registration (`state in ['open', 'done']`). The search uses a SQL-free domain builder via `_fetch_is_participating_events()` which checks: (a) if user is public with no visitor -> not participating; (b) if visitor exists -> check `visitor_id` link; (c) if partner exists -> check `partner_id` link. Runs under `sudo()` for the registration check.
- `_search_is_visible_on_website()` — Returns event IDs where: `website_visibility='public'` for all, or `(participating OR logged_users)` for authenticated users. Used for public website event searches.
- `_compute_is_visible_on_website()` — Computed version of the search. `public` is always visible; `link` and `logged_users` require additional checks.

**Website Menus:**

- `_update_website_menus(menus_update_by_field=None)` — Core menu synchronization. Called on create and write. When `website_menu=True`, creates a root `website.menu` and child menus for each enabled sub-menu (introduction, location, register, community). When `website_menu=False`, deletes all menus in cascade.
- `_get_menu_update_fields()` — Returns `['community_menu', 'introduction_menu', 'location_menu', 'register_menu']` — fields whose changes trigger menu updates.
- `_get_menu_type_field_matching()` — Maps `menu_type` string to boolean field name: `{'community': 'community_menu', 'introduction': 'introduction_menu', 'location': 'location_menu', 'register': 'register_menu'}`.
- `_split_menus_state_by_field()` — Groups events by whether each menu field is True or False before a write. Used to detect which fields actually changed.
- `_get_menus_update_by_field(state_by_field, force_update=None)` — Determines which events need menu updates after a write, comparing current stored values to new values.
- `_get_website_menu_entries()` — Returns menu entries as tuples `(name, url, xml_id, sequence, menu_type)`:
  - `('Introduction', False, 'website_event.template_intro', 1, 'introduction')`
  - `('Location', False, 'website_event.template_location', 50, 'location')`
  - `('Info', '/event/<slug>/register', False, 100, 'register')`
  - `('Community', '/event/<slug>/community', False, 80, 'community')`
- `_update_website_menu_entry(fname_bool, fname_o2m, fmenu_type)` — Creates or deletes a specific menu entry based on the boolean flag.
- `_create_menu(sequence, name, url, xml_id, menu_type)` — Creates a `website.menu` record. If `xml_id` is provided (not a URL), calls `website.new_page()` to create a new `ir.ui.view` page from the template, then links it. Returns the created `website.menu`.

**Time / Live Data:**

- `_compute_time_data()` — All computations in UTC. `start_remaining` = minutes until `date_begin`. `start_today` = `date_begin` date equals today's date.
- `_search_is_ongoing()` — Search domain for events currently in progress.

**SEO / Sharing:**

- `_default_website_meta()` — Sets og:image and twitter:image from `cover_properties` background, og:title from `name`, og:description and twitter:description from `subtitle`, twitter:card to `summary`, meta description from `subtitle`.
- `_get_external_description()` — Appends event registration URL to the description for email invitations.
- `_track_subtype(init_values)` — Returns `mt_event_published` or `mt_event_unpublished` subtype when `is_published` or `website_published` changes.

**Calendar Integration:**

- `_get_event_resource_urls()` — Returns `{'google_url': ..., 'iCal_url': ...}`:
  - Google Calendar URL: `https://www.google.com/calendar/render?action=TEMPLATE&text=...&dates=...&details=...&location=...`
  - iCal URL: `/event/<id>/ics?...` (signed parameters)
- `google_map_link()` / `_google_map_link()` — Delegates to `address_id.google_map_link()` if an address is set.

**Search (Website):**

- `_search_build_dates()` — Returns filter definitions for `upcoming`, `today`, `This month` (localized), `Past events`, `All events`. Dates are converted to UTC for the domain. Supports `get_lang()` localization for month names.
- `_search_get_detail(website, order, options)` — Website search integration. Supports filtering by `date` (upcoming/today/month/past/all), `country` (by `country_id` or `online`/`all`), `tags` (grouped by category for AND-between-groups logic), `event_type`. Includes `no_date_domain` and `no_country_domain` for independent filtering.
- `_search_render_results(fetch_fields, mapping, icon, limit)` — Adds date range HTML rendering to search results using `ir.qweb.field.date`.

#### Constraints

```python
@api.constrains('website_id')
def _check_website_id(self):
    # website_id's company must match event's company
    if event.website_id and event.website_id.company_id != event.company_id:
        raise ValidationError(...)
```

#### L4 Notes

- **Website menus are created in `website` scope (sudo):** `_create_menu()` runs with `check_access('write')` on the event but creates menus via `sudo()`. The menu's `website_id` is set to the event's `website_id`. Pages created from templates (introduction, location) are duplicated as new `ir.ui.view` records per event — each event gets its own copy.
- **`community_menu` is always False in base `website_event`:** Sub-modules like `website_event_meet` (meetup), `website_event_track` (conference tracks), or `website_event_track_quiz` set `community_menu = True` and add their own menu entries via `_compute_community_menu` overrides.
- **Event type defaults:** When an event type is set/changed (`event_type_id`), `website_menu` and `community_menu` are synced from the type's defaults via `_compute_website_menu` and `_compute_community_menu`. After syncing, the fields remain independently writable.
- **`website_visibility='link'`:** The event does not appear in public listings but is always accessible via its direct URL (`/event/<slug>`). This is used for private or invitation-only events.
- **Menu cascade delete:** `website.event.menu.unlink()` calls `view_id.sudo().unlink()` before the normal unlink, ensuring the duplicated page templates are removed when menus are deleted.

---

### 2. `event.type` — Event Type (Website Extension)

**Inherits:** `event.type`
**Table:** `event_type`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `website_menu` | Boolean | Default value for `event.event.website_menu` |
| `community_menu` | Boolean (computed) | Defaults to same value as `website_menu` |

---

### 3. `event.registration` — Registration (Website Extension)

**Inherits:** `event.registration`
**Table:** `event_registration`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `visitor_id` | Many2one `website.visitor` | Link to anonymous or identified website visitor |

#### Key Method

- `_get_website_registration_allowed_fields()` — Returns `{'name', 'phone', 'email', 'company_name', 'event_id', 'partner_id', 'event_ticket_id'}` — the fields that can be submitted via the public website registration form.

#### L4 Notes

- The `visitor_id` link is established by the website controller when a public user registers. The controller creates or matches a `website.visitor` record and links it to the registration. When a public visitor later logs in or is identified, the visitor may be merged (`_merge_visitor` on `website.visitor`), which also updates the `partner_id` on registrations without a partner.
- Registration from the website does not require authentication. The controller creates the registration and may optionally create a `website.visitor` for anonymous tracking.

---

### 4. `event.tag` — Event Tags (Website Extension)

**Inherits:** `event.tag`, `website.published.multi.mixin`

#### Notes

- Inherits `website.published.multi.mixin` which adds `website_published` and `website_id` fields with multi-website publication support.
- `default_get()` sets `website_id` from context if `default_website_id` is provided.

---

### 5. `event.tag.category` — Tag Categories (Website Extension)

**Inherits:** `event.tag.category`, `website.published.multi.mixin`

#### Notes

- Same pattern as `event.tag`: adds multi-website publication via `website.published.multi.mixin`.
- Default `is_published = True` for tag categories.

---

### 6. `website.event.menu` — Event Website Menu Record

**Table:** `website_event_menu`
**Rec_name:** `menu_id`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `menu_id` | Many2one `website.menu` | The actual website menu entry |
| `event_id` | Many2one `event.event` | Parent event |
| `view_id` | Many2one `ir.ui.view` | Page template (used for xml_id-based menus, not URL menus) |
| `menu_type` | Selection | `community` / `introduction` / `location` / `register` |

#### Notes

- `unlink()` cascades to `view_id` (deleted via sudo) before the normal unlink, ensuring duplicated page templates are removed.
- This model does not have direct ORM logic — it is the through table linking events to their website menus. It is created by `event.event._create_menu()` and deleted by the menu cascade.

---

### 7. `website.visitor` — Website Visitor (Event Extension)

**Inherits:** `website.visitor`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `event_registration_ids` | One2many `event.registration` | Registrations made by this visitor |
| `event_registration_count` | Integer (computed) | Number of registrations |
| `event_registered_ids` | Many2many `event.event` (computed/search) | Events the visitor is registered for |

#### Key Methods

- `_compute_display_name()` — For anonymous visitors with no partner but with registrations, uses the registration's `name` as the visitor display name.
- `_compute_email_phone()` — Inherited: fills `email` and `mobile` from linked registrations if not already set.
- `_search_event_registered_ids(operator, operand)` — Supports searching visitors by their registered events, e.g., `[('event_registered_ids', 'in', [1, 2])]`. Returns visitor IDs matching registrations with `event_id in [...]`. Does not support `not in` operator.
- `_inactive_visitors_domain()` — Override: visitors with event registrations are always considered active and are excluded from the inactive-visitor cleanup cron. Normal visitors are cleaned up after the standard inactivity period.
- `_merge_visitor(target)` — Override: when two visitors are merged, their `event_registration_ids` are linked to the target. Registrations without a `partner_id` have their `partner_id` set to the target's partner.

---

### 8. `website.snippet.filter` (Extension)

Overrides `_get_hardcoded_sample()` to inject event sample data (cover images, names, dates) into merged snippet filter samples for the `event.event` model, used in website editor snippet panels.

---

## How Website Events Differ from Backend Events (L4)

| Aspect | Backend `event` | Website `website_event` |
|--------|-----------------|------------------------|
| Registration | Backend staff creates registrations | Public form on `/event/<slug>/register` (auth not required) |
| Attendee identity | Staff selects/creates partner | Anonymous visitor + optional partner |
| Event listing | Full calendar + kanban in backend | Public website listing with filters |
| Communication | Manual email from registration | Automated template emails via `event.registration` workflow |
| Progress tracking | `state` field: `draft/open/close/done` | Same state machine, plus website-specific menus |
| Visibility | Not applicable | `website_visibility` controls who sees the listing |
| Tracking | No visitor model | `website.visitor` linked via `event.registration.visitor_id` |
| Content pages | None | Introduction, Location, Info pages as `ir.ui.view` copies |

---

## SEO for Events (L4)

`event.event._default_website_meta()` sets:
- `og:title` / `twitter:title` = `event.name`
- `og:description` / `twitter:description` = `event.subtitle` (or first line of description if no subtitle)
- `og:image` / `twitter:image` = cover image from `cover_properties` JSON (background-image field)
- `twitter:card` = `summary`
- `default_meta_description` = `subtitle`

The cover image is parsed from the `cover_properties` JSON field (which stores CSS URL strings like `url('/website_event/static/src/img/event_cover_4.jpg')`).

---

## Event Page Menu Structure (L4)

Each event with `website_menu=True` gets a root `website.menu` (child of the main website menu). Child menus are:

1. **Introduction** (`introduction_menu=True`): Creates a new page from `website_event.template_intro` (Qweb template). URL: `/event/<slug>/page/<page_key>`. The view is duplicated per event via `new_page()` so each event has its own editable copy.

2. **Location** (`location_menu=True`): Same as Introduction but from `website_event.template_location`. Contains map, address, and contact info. Uses `event.address_id` for location data.

3. **Info** (`register_menu=True`): URL-based menu: `/event/<slug>/register`. Points to the event registration page with ticket selection.

4. **Community** (`community_menu=True`): URL-based menu: `/event/<slug>/community`. Base module sets this to False; extended by `website_event_meet`, `website_event_track` sub-modules for attendee networking and track/speaker pages.

Menu creation is transactional: if any menu fails, the entire `_update_website_menus()` operation rolls back. The `website.event.menu` record stores the `view_id` for page-type menus to enable template deletion on cleanup.

---

## Track/Booth Integration with Website (L4)

The base `website_event` module does not include track or booth management. These are provided by sub-modules:

- **`website_event_track`** — Adds conference talk tracks, speakers, and agenda pages. Extends `_get_website_menu_entries()` to add Track Agenda menu entries. Adds `website_track` boolean flag and `track.tag` / `event.track` / `event.speaker` models.
- **`website_event_meet`** — Adds meeting room / booth functionality. Extends the community menu with meeting room registration.
- **`website_event_sale`** — Links event tickets to products for paid registration, integrating with `sale` and `website_sale` modules.

The `event.sponsor` and `event.sponsor.type` models referenced in the brief are part of the **`event`** core module (not `website_event`). They represent event sponsors with tier levels (platinum/gold/silver) and are displayed on the event's website page via the community or sponsor menu.

---

## File Locations

- Models: `addons/website_event/models/`
  - `event_event.py` — `event.event` website extension, menu management, search
  - `event_type.py` — `event.type` website defaults
  - `event_registration.py` — `event.registration` visitor link
  - `event_tag.py` — `event.tag` publication mixin
  - `event_tag_category.py` — `event.tag.category` publication mixin
  - `website_event_menu.py` — `website.event.menu` through table
  - `website_visitor.py` — `website.visitor` event extension
  - `website.py` — Website controller hook for events in search
  - `website_snippet_filter.py` — Editor snippet sample data for events
