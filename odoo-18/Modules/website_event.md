# Website Event Module (website_event)

## Overview

The `website_event` module integrates event management with the Odoo website. It provides event publishing, registration forms, website menus, visitor registration tracking, and search integration.

## Key Models

### event.event (website_event Extension)

Extends `event.event` with website-specific fields, menus, and visibility controls.

**Inherits:** `event.event`, `website.seo.metadata`, `website.published.multi.mixin`, `website.cover_properties.mixin`, `website.searchable.mixin`

**Website Fields:**
- `website_visibility`: Selection - Who can see the event on the website:
  - `public`: Anyone
  - `link`: Only via direct link (hidden from public searches)
  - `logged_users`: Only logged-in users
  - Default: `public`
- `website_published`: Boolean - Publication status (tracked)
- `website_menu`: Boolean - Whether to display event-specific menus on the website
- `menu_id`: Many2one - The main `website.menu` entry for this event
- `introduction_menu`, `location_menu`, `register_menu`: Boolean - Individual menu toggles (computed from `website_menu` unless manually overridden)
- `community_menu`: Boolean - Display community tab (computed False by default, overridden by `event_meet`/`event_track_quiz` modules)
- `introduction_menu_ids`, `location_menu_ids`, `register_menu_ids`, `community_menu_ids`: One2many - Per-website menu entries (via `website.event.menu`)

**Live Information Fields (all computed):**
- `is_ongoing`: Boolean - Event has started but not ended (searchable)
- `is_done`: Boolean - Event has ended
- `start_today`: Boolean - Event starts today
- `start_remaining`: Integer - Minutes remaining before start

**Registration Fields:**
- `is_participating`: Boolean - Current visitor/user is registered for this event (computed, searchable)
- `event_register_url`: Char - Full registration URL (computed)

**Description Fields:**
- `subtitle`: Char - Event subtitle (translatable)

**Key Computed Methods:**

- `_compute_website_url()`: Sets URL to `/event/{slug}` using `ir.http._slug()`.
- `_compute_event_register_url()`: Computes full registration URL as `{base_url}{website_url}/register`.
- `_compute_is_participating()`: Determines if the current visitor or logged-in partner has a confirmed/attended registration for this event.
- `_search_is_participating(operator, value)`: Search domain builder for `is_participating` field.
- `_fetch_is_participating_events()`: The core heuristic for participation detection:
  - Public + no visitor: not participating (no data)
  - Public + visitor: checks visitor's registrations (public users)
  - Logged + visitor: checks both visitor and partner registrations
  - Considers only confirmed (`open`) and attended (`done`) registrations, not drafts
- `_compute_is_visible_on_website()`: Determines website visibility considering `website_visibility` and `is_participating`.
- `_search_is_visible_on_website(operator, value)`: Search domain builder for `is_visible_on_website`.
- `_compute_website_menu()`: Syncs `website_menu` from the event type template if not manually set.
- `_compute_community_menu()`: Returns False in base module; overridden by `event_meet` and `event_track_quiz` for community features.
- `_compute_website_menu_data()`: Syncs `introduction_menu`, `location_menu`, `register_menu` from `website_menu` (allows per-field overrides afterward).
- `_compute_time_data()`: Computes `is_ongoing`, `is_done`, `start_today`, `start_remaining` using UTC-normalized datetime comparisons.

**Key CRUD Methods:**

- `create(vals_list)`: After creation, automatically calls `_update_website_menus()` to create the website navigation structure.
- `write(vals)`: Before writing, captures the current menu state via `_split_menus_state_by_field()`. After writing, determines which menus need updating via `_get_menus_update_by_field()` and calls `_update_website_menus()`.

**Website Menu Management:**

- `toggle_website_menu(val)`: Toggles the `website_menu` boolean.
- `_get_menu_update_fields()`: Returns the list of fields that trigger menu updates: `community_menu`, `introduction_menu`, `location_menu`, `register_menu`.
- `_get_menu_type_field_matching()`: Maps menu types to their controlling fields.
- `_split_menus_state_by_field()`: For each menu-triggering field, determines which events have it activated vs deactivated.
- `_get_menus_update_by_field(menus_state_by_field, force_update)`: Determines which events need menu activation/deactivation based on value changes.
- `_get_website_menu_entries()`: Returns the list of menu entries to create:
  - `Introduction`: renders `website_event.template_intro` template
  - `Location`: renders `website_event.template_location` template
  - `Info/Register`: URL `/event/{slug}/register`
  - `Community`: URL `/event/{slug}/community` (if `community_menu` enabled)
- `_update_website_menus(menus_update_by_field)`: Creates or deletes `website.menu` and `website.event.menu` records based on the event state.

**Constraint:**
- `_check_website_id()`: Prevents assigning an event to a website belonging to a different company than the event's company.

**Search Integration:**
- Inherits `website.searchable.mixin` for website search integration (see `event.event` base model for `_search_get_detail`)

### event.registration (website_event Extension)

Extends `event.registration` with website visitor tracking.

**Additional Fields:**
- `visitor_id`: Many2one - Website visitor who registered (set null on delete)

**Key Methods:**

- `_get_website_registration_allowed_fields()`: Returns the set of fields allowed to be set from website registration forms: `name`, `phone`, `email`, `company_name`, `event_id`, `partner_id`, `event_ticket_id`.

### website.event.menu

Links event-specific submenus to the website menu structure.

**Fields:**
- `event_id`: Many2one - Parent event
- `menu_id`: Many2one - The `website.menu` record
- `menu_type`: Selection - Type of menu entry: `introduction`, `location`, `register`, `community`

## Cross-Module Relationships

- **event**: Base event model providing `event.event` and `event.registration` core fields and methods
- **website**: Multi-website scoping, menu management, SEO metadata, cover properties, search integration
- **website_track**: Visitor page tracking (for page view counting on event pages)

## Edge Cases

1. **Event Type Template Sync**: When an event is created from an event type, the type's `website_menu` value syncs to the event's `website_menu` field. This sync only happens when the type changes; manual overrides are preserved.
2. **Menu Split Management**: The `_split_menus_state_by_field` / `_get_menus_update_by_field` pattern allows granular control: each menu field (`introduction_menu`, etc.) can be independently toggled after being synced from `website_menu`, and only changed fields trigger menu updates.
3. **Participation Detection and Visitor Merging**: `_fetch_is_participating_events` uses the top-level parent visitor. Even if a visitor was merged during their session, the current visitor check is sufficient because merge consolidates all child visitor data.
4. **Logged-In User Without Visitor**: If a user is logged in but has no visitor record, the system checks the partner's registrations directly. This handles the case where a user registered before the website visitor tracking was active.
5. **Visibility vs Participation**: `is_participating` and `is_visible_on_website` are related but distinct. A user can participate without the event being visible in public website searches (e.g., `link`-visibility events are only accessible via direct URL).
6. **Time Zone Handling**: All time computations in `_compute_time_data` are performed in UTC to ensure consistency regardless of server timezone.
7. **Community Menu**: The base module computes `community_menu = False`. It is overridden by the `event_meet` module (for event meetups with chat) and `event_track_quiz` (for quizzes during tracks) to enable community features.
8. **Registration URL**: The `event_register_url` is the frontend registration form URL, distinct from the `website_url` (which is the event detail page). This URL is shown on event listing pages.
9. **Multi-Company Events**: An event's website must belong to the same company as the event itself. This is enforced by `_check_website_id`.
