---
tags:
  - odoo
  - odoo19
  - modules
  - website_event
---

# website_event_track

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | `website_event_track` |
| **Category** | Marketing |
| **Summary** | Sponsors, Tracks, Agenda, Event News |
| **Version** | 1.3 |
| **Depends** | `website_event` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Source** | `odoo/addons/website_event_track/` |

## Description

Advanced event module that adds talk/session track management to events. Provides a complete pipeline for managing speaker submissions, attendee wishlists, agenda views, and calendar integration. Integrates deeply with the website to expose event tracks publicly.

**Dependency chain**: `event` → `website_event` → `website_event_track`

The module extends `event.track` (from the `event` module) with full website-facing functionality: public track pages, agenda grid, speaker submission forms, wishlist reminders, iCal/Google Calendar export, and PWA support.

---

## Module Structure

```
website_event_track/
├── models/
│   ├── event_track.py              # Central track model (extends event.track)
│   ├── event_track_tag.py          # Tag model
│   ├── event_track_tag_category.py  # Tag categorization
│   ├── event_track_location.py      # Room/venue locations
│   ├── event_track_stage.py         # Kanban pipeline stages (6 stages)
│   ├── event_track_visitor.py        # Track-visitor wishlist linking
│   ├── event_type.py                # Event type extension
│   ├── event_event.py               # Event extension
│   ├── website_visitor.py            # Visitor extension (wishlist tracking)
│   ├── website_menu.py               # Menu unlink synchronization
│   ├── website_event_menu.py        # Track menu type declarations
│   ├── website.py                    # PWA app icon + website search
│   └── res_config_settings.py         # Events app name setting
├── controllers/
│   ├── event_track.py               # Track list, agenda, proposal, reminder
│   ├── event.py                      # Online event controller
│   └── webmanifest.py                # PWA manifest + service worker
├── security/
│   ├── ir.model.access.csv           # Per-group CRUD permissions
│   └── event_track_security.xml      # Record rules for public/portal access
└── data/
    ├── event_track_data.xml          # 6 default pipeline stages
    ├── event_data.xml                # Demo event track configuration
    ├── mail_template_data.xml        # Speaker notification templates
    └── ...
```

---

## Models

### `event.track` — Central Track Model

**Inherits**: `mail.thread`, `mail.activity.mixin`, `website.seo.metadata`, `website.published.mixin`, `website.searchable.mixin`

**Table**: `event_track` (managed by `event` module's `event.track`)

**Order**: `priority desc, date`

**Primary email** (for mail tracking): `contact_email`

The main model representing a talk or session within an event. This model extends the `event.track` model already defined in the `event` module — `website_event_track` adds the website-facing layer (wishlists, CTAs, publication, SEO) on top of the core track management.

#### Core Identification Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | required | Talk title, translateable |
| `event_id` | Many2one(`event.event`) | required, indexed | Parent event |
| `active` | Boolean | `True` | |
| `user_id` | Many2one(`res.users`) | `self.env.user` | Responsible person, `tracking=True` |
| `company_id` | Many2one(`res.company`) | related → `event_id.company_id` | |
| `stage_id` | Many2one(`event.track.stage`) | first stage via `_get_default_stage_id` | Kanban pipeline stage, `tracking=True`, `group_expand` all stages |
| `kanban_state` | Selection(`normal/done/blocked`) | `normal` | Kanban column indicator |
| `kanban_state_label` | Char | computed, stored | Human-readable kanban state label |
| `color` | Integer | — | Agenda display color |
| `priority` | Selection(`0/1/2/3`) | `1` (Medium) | 0=Low, 1=Medium, 2=High, 3=Highest |
| `tag_ids` | Many2many(`event.track.tag`) | — | Category tags |

**`_get_default_stage_id`**: Returns the first record from `event.track.stage` ordered by `sequence`. If no stages exist at module install time (e.g., during demo data creation before stage XML loads), returns `False` — this can cause a `ValidationError` on track creation if the stage is required and no default exists.

**`kanban_state_label`**: Stored computed field. Resolved from `stage_id.legend_normal/blocked/done` based on `kanban_state` value. Triggers mail tracking when state changes.

#### Speaker / Partner Information

All `partner_*` fields (except `partner_tag_line`) are **stored** and **editable** but **computed** from `partner_id**. The compute methods only populate the stored value if the field is currently empty (`not field_value`). This means manual edits are preserved and only auto-fill when the field is blank. Tracking is enabled for the editable fields (name:10, email:20, phone:30).

| Field | Type | Compute Method | Notes |
|-------|------|---------------|-------|
| `partner_id` | Many2one(`res.partner`) | — | Speaker contact |
| `partner_name` | Char | `_compute_partner_name` | Falls back to `partner_id.name` |
| `partner_email` | Char | `_compute_partner_email` | Falls back to `partner_id.email` |
| `partner_phone` | Char | `_compute_partner_phone` | Falls back to `partner_id.phone` |
| `partner_function` | Char | `_compute_partner_function` | Falls back to `partner_id.function` |
| `partner_biography` | Html | `_compute_partner_biography` | Falls back to `partner_id.website_description`. Also re-fills if current biography is HTML-empty but partner has content. |
| `partner_company_name` | Char | `_compute_partner_company_name` | Uses `partner_id.name` if `company_type == 'company'`, else `partner_id.parent_id.name` |
| `partner_tag_line` | Char | `_compute_partner_tag_line` | Format: `"Name, Function at Company"`, `"Name, Function"`, or `"Name from Company"`. Not stored. |
| `image` | Image | `_compute_partner_image` | Max 256x256. Falls back to `partner_id.image_256` |

**`_compute_partner_biography` edge case**: If a user clears the biography field (sets it to HTML-empty) after it was populated, and the partner then gains a `website_description`, the biography will be silently re-populated on the next write or recompute. This is a one-way sync — manual biography content is never overwritten.

#### Contact Information

| Field | Type | Compute | Notes |
|-------|------|---------|-------|
| `contact_email` | Char | `_compute_contact_email` | `partner_id.email`, `tracking=20` |
| `contact_phone` | Char | `_compute_contact_email` | `partner_id.phone`, `tracking=30` |

#### Location and Time

| Field | Type | Default | Compute | Notes |
|-------|------|---------|---------|-------|
| `location_id` | Many2one(`event.track.location`) | — | — | Room/venue |
| `date` | Datetime | — | `_compute_date` / `_inverse_date` | Track start. **Invertible** with `date_end` and `duration`. Stored. |
| `date_end` | Datetime | — | `_compute_end_date` / `_inverse_end_date` | Track end. **Invertible** with `date` and `duration`. Stored. |
| `duration` | Float | `0.5` | — | Hours |

**Date invertibility logic**: Both `date` and `date_end` are stored computed fields with inverses:
- `_inverse_date`: recomputes `duration = (date_end - date).total_seconds() / 3600`
- `_inverse_end_date`: recomputes `duration = (date_end - date).total_seconds() / 3600`
- `_compute_date`: recomputes `date = date_end - timedelta(hours=duration)`
- `_compute_end_date`: recomputes `date_end = date + timedelta(hours=duration)`

Setting any two of the three fields (date, date_end, duration) will correctly resolve the third. Setting all three may cause inconsistency depending on field write order — Odoo evaluates stored compute fields after inverse fields.

#### Time State Computed Fields (`_compute_track_time_data`)

All computed from `date` and `date_end`, **evaluated in UTC**. Uses `fields.Datetime.now().replace(microsecond=0)` localized to UTC for stable comparisons.

| Field | Type | Logic |
|-------|------|-------|
| `is_track_live` | Boolean | `date_begin_utc <= now_utc < date_end_utc` |
| `is_track_soon` | Boolean | Starts within 30 minutes (`< 30*60 seconds`) AND in the future |
| `is_track_today` | Boolean | `date_begin_utc.date() == now_utc.date()` |
| `is_track_upcoming` | Boolean | `date_begin_utc > now_utc` |
| `is_track_done` | Boolean | `date_end_utc <= now_utc` |
| `track_start_remaining` | Integer | Seconds until start. `0` if already started. |
| `track_start_relative` | Integer | Seconds relative to start (positive=future, negative=past) |

**`_compute_field_is_one_day`**: Uses the event's timezone (`event_id.date_tz`) via `fields.Datetime.context_timestamp()` to determine if a track spans a single calendar day. A track that starts at 23:00 in event TZ and ends at 01:00 the next day (crossing midnight) is correctly identified as NOT one day.

#### CTA Magic Button

The CTA (Call-to-Action) button appears during track playback on the website.

| Field | Type | Notes |
|-------|------|-------|
| `website_cta` | Boolean | Master toggle |
| `website_cta_title` | Char | Button label |
| `website_cta_url` | Char | Cleaned via `res.partner._clean_website()` on write |
| `website_cta_delay` | Integer | Minutes after track start to show button |
| `is_website_cta_live` | Boolean | `website_cta` is active and current time is within window |
| `website_cta_start_remaining` | Integer | Seconds until CTA appears |

**CTA timing**: The CTA window starts at `track.date + website_cta_delay` and ends at `track.date_end`. The button is live only within that window. `_compute_cta_time_data` uses UTC throughout.

#### Wishlist / Visitor Management

| Field | Type | Group | Notes |
|-------|------|-------|-------|
| `event_track_visitor_ids` | One2many(`event.track.visitor`) | `event.group_event_user` | Back-link |
| `is_reminder_on` | Boolean | — | Context-dependent reminder state |
| `wishlist_visitor_ids` | Many2many(`website.visitor`) | `event.group_event_user` | Stored via `_read_group` + `array_agg`, `sudo`, `compute_sudo` |
| `wishlist_visitor_count` | Integer | `event.group_event_user` | Count of wishlisted visitors |
| `wishlisted_by_default` | Boolean | — | Auto-wishlist all event registrants |

**`_compute_is_reminder_on`** (context-aware):
- Public visitor without record: returns `wishlisted_by_default`
- Public visitor with record: searches `event.track.visitor` on `visitor_id`
- Logged visitor with visitor record: searches `event.track.visitor` on `partner_id OR visitor_id`
- Logged visitor without visitor record: searches `event.track.visitor` on `partner_id` only

**Key edge case**: A logged-in user who has never visited the website has no `website.visitor` record. Their wishlist is tracked purely via `partner_id` on `event.track.visitor`. If such a user later visits the site and a visitor record is created, the OR condition `partner_id OR visitor_id` ensures continuity.

**`_compute_wishlist_visitor_ids`**: Uses `_read_group` with `array_agg` on `visitor_id` — efficient for large wishlists. The `visitor_id:array_agg` aggregation is performed server-side. Result is stored as a Many2many set.

**`_search_wishlist_visitor_ids`**: Supports `in` and `any` operators only. Raises `UserError` for `not in` and `not any` (Odoo limitation for Many2many search methods).

#### Website / SEO / Images

| Field | Type | Notes |
|-------|------|-------|
| `website_image` | Image | Max 1024x1024. Custom per-track image. |
| `website_image_url` | Char | Computed `sudo`. Returns custom image URL or `/website_event_track/static/src/img/event_track_default_{id%2}.jpeg` (alternates between 2 default images based on track ID parity). |
| `website_url` | Char | Computed: `/event/{event_slug}/track/{track_slug}` |
| `header_visible` | Boolean | Related from `event_id` |
| `footer_visible` | Boolean | Related from `event_id` |

#### Key Methods

| Method | Signature | Notes |
|--------|-----------|-------|
| `_compute_website_url()` | `super()` + slug composition | Uses `ir.http._slug()` for URL-safe slugs |
| `_search_get_detail()` | `(website, order, options)` | Implements `website.searchable.mixin`; searches `event_id` from options slug, filters on `is_published OR stage_id.is_visible_in_agenda` |
| `_synchronize_with_stage()` | `(stage)` | Auto-publishes if `stage.is_fully_accessible`, unpublishes if `stage.is_cancel`. Called on create and stage change. |
| `create()` | `vals_list` | Cleans CTA URL, posts notification to event chatter, calls `_synchronize_with_stage`. Skips `email_from` if user has no email (falls back to company catchall). |
| `write()` | `vals` | Cleans CTA URL, resets `kanban_state='normal'` on stage change (only if `kanban_state` not in vals), calls `_synchronize_with_stage`. |
| `_get_event_track_visitors()` | `(force_create=False)` | Returns `event.track.visitor` records. Handles public vs. logged-in via domain OR condition. Creates missing associations if `force_create=True`. |
| `_get_track_suggestions()` | `(restrict_domain, limit)` | Returns up to `limit` tracks from same event. Sorted by: published, live (< 10 min ago, not done), soon, upcoming (by start time), wishlisted, tag match count, location match, random. |
| `_get_ics_file()` | `()` | Returns dict `{track_id: bytes}`. Requires `vobject` library. Gracefully returns `False` if library missing. |
| `_get_track_calendar_urls()` | `()` | Google Calendar URL (URL-encoded params) + iCal download URL |
| `_get_track_calendar_description()` | `()` | Returns HTML with track link + truncated description (1900 chars) |
| `_get_track_calendar_reminder_dates()` | `()` | Returns track dates or falls back to event dates |
| `_get_track_calendar_reminder_times_warning()` | `()` | Returns warning markup if event dates are used instead of track dates |
| `open_track_speakers_list()` | `()` | Opens a partner kanban/form for all speakers of selected tracks |
| `get_backend_menu_id()` | `()` | Returns `event.event_main_menu` ID |

#### Mail Tracking Overrides

- **`_track_template`**: When `stage_id` changes and the new stage has a `mail_template_id`, sends that template as a comment with `mail_notification_light` layout. `auto_delete_keep_log=False` means the email is deleted after sending (not kept in the chatter log).
- **`_track_subtype`**: Kanban state `blocked` → `mt_track_blocked` subtype; `done` → `mt_track_ready`; otherwise falls back to `mail.thread` default.
- **`_message_post_after_hook`**: Auto-links partner created from chatter's "Suggested Recipients" to the track. Matches by normalized email.
- **`_mail_get_timezone`**: Delegates to `event_id._mail_get_timezone()` for proper email datetime formatting.

---

### `event.track.stage` — Kanban Pipeline Stage

**Table**: `event_track_stage`

**Order**: `sequence, id`

Six stages are created by `data/event_track_data.xml`:

| Stage ID | Name | `is_visible_in_agenda` | `is_fully_accessible` | `is_cancel` | Mail Template |
|----------|------|----------------------|----------------------|-------------|----------------|
| stage0 | Proposal | `False` (default) | `False` | `False` | — |
| stage1 | Confirmed | `False` (default) | `False` | `False` | `mail_template_data_track_confirmation` |
| stage2 | Announced | `True` (explicit) | `False` | `False` | — |
| stage3 | Published | `True` (explicit) | `True` (explicit) | `False` | — |
| stage4 | Refused | `False` (default) | `False` | `False` | — |
| stage5 | Cancelled | `False` (from `is_cancel=True`) | `False` (from `is_cancel=True`) | `True` | — |

**`is_visible_in_agenda` compute** (stored, `api.depends('is_cancel', 'is_fully_accessible')`):
```python
if is_cancel: is_visible = False
elif is_fully_accessible: is_visible = True
```

**`is_fully_accessible` compute** (stored, `api.depends('is_cancel', 'is_visible_in_agenda')`):
```python
if is_cancel or not is_visible_in_agenda: is_fully_accessible = False
```

**Design tension**: These two fields are mutually dependent (each depends on the other plus `is_cancel`). Odoo resolves this using stored compute field reordering — the database stores the last-computed value, and re-computation is triggered on any write. The `is_cancel` field is the single source of truth: setting it True cascades both computed fields to False.

**`fold`**: Stage folds in the kanban view when empty. Default False for proposal/confirmed/announced/published; True for refused/cancelled.

---

### `event.track.tag` — Track Tags

**Table**: `event_track_tag`

**Order**: `category_id, sequence, name`

| Field | Type | Default | Constraint | Notes |
|-------|------|---------|------------|-------|
| `name` | Char | required | `unique(name)` | Tag display name |
| `track_ids` | Many2many(`event.track`) | — | — | Inverse of tag assignment |
| `color` | Integer | random 1-11 | — | **Colorless tags (0) are hidden from the website.** See security note. |
| `sequence` | Integer | 10 | — | Display order within category |
| `category_id` | Many2one(`event.track.tag.category`) | — | — | `ondelete=set null`, `index btree_not_null` |

**`_default_color`**: Returns `randint(1, 11)` — each new tag gets a random color.

---

### `event.track.tag.category` — Tag Categories

**Table**: `event_track_tag_category`

**Order**: `sequence`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | required, translateable | |
| `sequence` | Integer | 10 | |
| `tag_ids` | One2many(`event.track.tag`) | — | Inverse of `category_id` |

Tags without a category are listed first (due to `category_id, sequence, name` ordering with `btree_not_null` index — nulls sort first in Postgres).

---

### `event.track.location` — Track Locations (Rooms)

**Table**: `event_track_location`

**Order**: `sequence, id`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | required | Room/venue name |
| `sequence` | Integer | 10 | Agenda display order |

Locations without a sequence value sort last within the same sequence rank.

---

### `event.track.visitor` — Track-Visitor Wishlist Link

**Table**: `event_track_visitor` (custom table name)

**RecName**: `track_id`

| Field | Type | Notes |
|-------|------|-------|
| `track_id` | Many2one(`event.track`) | `required`, `cascade delete` |
| `visitor_id` | Many2one(`website.visitor`) | `cascade delete` |
| `partner_id` | Many2one(`res.partner`) | Computed from `visitor_id`, `ondelete=set null`, stored |
| `is_wishlisted` | Boolean | Manual wishlist toggle |
| `is_blacklisted` | Boolean | User opted out of `wishlisted_by_default` tracks |

**`_compute_partner_id`**: Sets `partner_id = visitor_id.partner_id` only if `visitor_id` exists AND `partner_id` is currently unset. Once set, `partner_id` is never auto-updated. This is intentional — it preserves the partner association even if the visitor's linked partner changes.

**Cascade delete behavior**: When a track is deleted, all its `event.track.visitor` records are cascade-deleted. When a visitor is deleted, associated records are cascade-deleted (removing wishlist entries). `partner_id` is set to null rather than cascading.

---

### `event.event` — Event Extension

| Field | Type | Notes |
|-------|------|-------|
| `track_ids` | One2many(`event.track`) | All tracks in this event |
| `track_count` | Integer | Non-cancelled track count via `_read_group` |
| `website_track` | Boolean | Show tracks page on website (computed, stored) |
| `website_track_proposal` | Boolean | Allow talk proposal form (computed, stored) |
| `track_menu_ids` | One2many(`website.event.menu`) | Tracks menus (domain: `menu_type='track'`) |
| `track_proposal_menu_ids` | One2many(`website.event.menu`) | Proposal menus (domain: `menu_type='track_proposal'`) |
| `allowed_track_tag_ids` | Many2many(`event.track.tag`) | Tags available for this event (manual selection) |
| `tracks_tag_ids` | Many2many(`event.track.tag`) | All tags used by event's tracks, computed, filtered (color != 0) |

**`_compute_website_track`** dependencies: `event_type_id`, `website_menu`. Logic:
- If `event_type_id` changed: inherit from `event_type_id.website_track`
- If `website_menu` was toggled on: set `website_track=True`
- If `website_menu` was toggled off: set `website_track=False`

**`_compute_website_track_proposal`** dependencies: `event_type_id`, `website_track`. Logic:
- If `event_type_id` changed: inherit from `event_type_id.website_track_proposal`
- Otherwise: sync with `website_track` (proposal follows track toggle)

**`copy_event_menus()`**: After copying an event's menus, re-parents the new event's `track_menu_ids` and `track_proposal_menu_ids` menu entries to the new event's `menu_id`. This ensures the copied event's track menus are correctly positioned in the menu tree.

**`_get_website_menu_entries()`**: Returns 4 menu entries:
1. `('Talks', '#', False, 10, 'track', False)` — placeholder anchor for nav
2. `('Talks', '/event/{slug}/track', False, 10, 'track', 'track')` — actual track listing
3. `('Agenda', '/event/{slug}/agenda', False, 15, 'track', 'track')` — agenda view
4. `('Propose a talk', '/event/{slug}/track_proposal', False, 20, 'track_proposal', 'track')` — submission form

The 5th parameter is the `menu_type`; the 6th is the `ref_menu_type` used to match and update the correct menu entry.

---

### `website.visitor` — Visitor Extension

| Field | Type | Group | Notes |
|-------|------|-------|-------|
| `event_track_visitor_ids` | One2many | `event.group_event_user` | Back-link |
| `event_track_wishlisted_ids` | Many2many(`event.track`) | `event.group_event_user` | Computed `sudo`, `search` supported |
| `event_track_wishlisted_count` | Integer | `event.group_event_user` | |

**`_inactive_visitors_domain()`**: Adds `event_track_visitor_ids = False` to the parent's inactivity domain. This means visitors who have any `event.track.visitor` record (i.e., have wishlisted or interacted with tracks) are **never** considered inactive and are protected from the automatic visitor cleanup cron. This prevents accidental deletion of active event participants.

**`_merge_visitor()`**: When merging visitors, all `event_track_visitor_ids` are re-linked to the target visitor. For unlinked records (`partner_id` is False), the target's `partner_id` is assigned — this handles the case where a visitor was created without an associated partner.

---

### `website.menu` — Menu Unlink Synchronization

Overrides `unlink()` to detect track-related menu deletions and auto-uncheck the `website_track` flag on the event.

```python
if event_menu.menu_type == 'track' and '/track' in event_menu.menu_id.url:
    to_update.append('website_track')
```

**Critical edge case handled**: The `/track` substring check prevents false positives — the agenda page also has `menu_type='track'` but its URL is `/event/{slug}/agenda` (no `/track`). Only the track listing page (`/event/{slug}/track`) triggers the uncheck. This distinction is important because the agenda page can exist independently of the track listing page.

---

### `website.event.menu` — Event Menu Type Extension

Adds `selection_add` to `website.event.menu`:
- `'track'`: Event Tracks Menus — cascades on delete
- `'track_proposal'`: Event Proposals Menus — cascades on delete

Cascade delete means that deleting a menu of either type automatically deletes the `website.event.menu` record, which then triggers the event's `_update_website_menus` logic.

---

### `event.type` — Event Type Extension

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `website_track` | Boolean | from `website_menu` | Stored |
| `website_track_proposal` | Boolean | from `website_menu` | Stored |

Both fields are `compute`/`readonly=False`/`store=True`. They mirror the `website_menu` toggle: when `website_menu` is enabled on a type, both track features are enabled on new events created from that type.

---

### `website` — PWA and Search Extension

| Field | Type | Notes |
|-------|------|-------|
| `app_icon` | Image | 512x512 PNG computed from favicon. Skipped if favicon is SVG. |
| `events_app_name` | Char | PWA display name. Defaults to `"{Website Name} Events"`. Constrained non-empty. |

**`_compute_app_icon`**: Uses `ImageProcess` to crop-resize the favicon to a 512x512 square PNG. Skipped entirely if favicon is SVG (returns False). Each image operation increments `operationsCount` (Odoo's image pipeline tracking).

**`_search_get_details`**: Appends `event.track` search results when `search_type` is `'track'` or `'all'` and an `event` option is present.

---

### `res.config.settings` — Settings Extension

Single field: `events_app_name` (related to `website_id.events_app_name`, `readonly=False`). Allows setting the PWA name from the website settings form.

---

## Controllers

### `EventTrackController` (`controllers/event_track.py`)

#### Route: Track List

```
/event/<event>/track
/event/<event>/track/tag/<tag>  (deprecated)
```
- **Auth**: Public
- **Type**: HTTP, `sitemap=False`, `readonly=True`
- **Render**: `website_event_track.tracks_session`

**Bot mitigation (301 redirect)**: If a GET request contains multiple tags (detected by counting commas in the `tags` JSON array parameter), a permanent 301 redirect to the same path without tags is issued. This prevents crawler combinatorial explosion. Single-tag GET requests are allowed to maintain search index continuity.

**Tag search grouping**: Tags are grouped by `category_id`. Within a category, tags form an OR condition; across categories, they form AND. Example: selecting tags A and B in category "Topic" AND tag C in category "Level" generates `('tag_ids', 'in', [A, B]) AND ('tag_ids', 'in', [C])`.

**Wishlist filtering**: `search_wishlist` filtering is applied as post-processing (`filtered()`) after the search, not as a domain condition. This is because `is_reminder_on` is a complex context-dependent computed field that cannot be safely used in a domain.

**Day grouping with collapse**: Tracks are grouped by day. If there are any upcoming or ongoing tracks across all groups, days where ALL tracks are done are collapsed by default (`default_collapsed=True`).

#### Route: Agenda

```
/event/<event>/agenda
```
- **Auth**: Public
- **Type**: HTTP, `sitemap=False`
- **Render**: `website_event_track.agenda_online`

**`_prepare_calendar_values()`**: Builds a 15-minute time slot grid per day in the event timezone. For each track:
- Computes `rowspan = ceil(duration / 15_min)`
- Rounds start/end times to nearest 15-minute boundary via `time_slot_rounder()`
- Handles multi-day tracks by splitting across day boundaries
- Builds `tracks_by_rounded_times[time_slot][location][track]` with row/col spanning info

**`_split_track_by_days()`**: A track starting at 22:00 with 3-hour duration spanning midnight generates:
```python
{
    datetime(2000, 1, 1, 22, 0): 8,   # 2h = 8 slots on day 1
    datetime(2000, 1, 2, 0, 0): 4     # 1h = 4 slots on day 2
}
```

**`_get_occupied_cells()`**: Returns `(time_slot, location)` tuples for every 15-minute slot the track occupies. If `location_id` is not set, reserves all locations for each time slot — this prevents overlapping tracks from filling the same cell.

#### Route: Track Page

```
/event/<event>/track/<track>
```
- **Auth**: Public
- **Type**: HTTP, `sitemap=True`, `readonly=True`
- **Render**: `website_event_track.event_track_main`
- **Model constraint**: `event.website_track == True` and `track.event_id == event` enforced by ORM

**`_event_track_page_get_values()`**: Uses `track.sudo()` for all data fetching. Calls `_get_track_suggestions()` with `limit=10` for the "Up Next" sidebar. The sidebar is gated on `is_event_user` and `user_event_manager` flags for backend-specific UI.

#### Route: Proposal Form

```
/event/<event>/track_proposal          GET (display)
/event/<event>/track_proposal/post     POST (submit)
```
- **Auth**: Public
- Creates speaker contact and track via `sudo()`

**Proposal creation flow**:
1. Validates tag IDs by searching the database (ACL-filtered — public users only get color-assigned tags)
2. Checks for duplicate: if the submitter is logged in and their email normalized matches an existing partner, reuses that partner
3. Otherwise creates a new `res.partner` with submitted contact info
4. Creates `event.track` in draft stage (Proposal stage) via sudo
5. If user is logged in (not the website robot), subscribes them to track notifications

**Email normalization**: Uses `email_normalize()` throughout — validates format before creating contacts. Invalid email without phone triggers `'invalidFormInputs'` error.

#### JSON-RPC Endpoints

| Route | Method | Auth | Notes |
|-------|--------|------|-------|
| `/event/track/toggle_reminder` | `track_reminder_toggle(track_id, set_reminder_on)` | Public | Returns `{'error': 'ignored'}` if state unchanged |
| `/event/track/send_email_reminder` | `send_email_reminder(track_id, email_to)` | Public | Validates track not done, not started. Uses template `mail_template_data_track_reminder` |
| `/event/track_tag/search_read` | `website_event_track_fetch_tags(domain, fields)` | Public | **ACL workaround**: allows public users to search tags via RPC, bypassing direct model access restrictions |

#### Helper Routes

| Route | Method | Notes |
|-------|--------|-------|
| `/event/<event>/track/<track>/ics` | `event_track_ics_file` | Sets Content-Disposition to `{event.name}-{track.name}.ics`. Language from cookie/context. |

#### Internal Methods

| Method | Notes |
|--------|-------|
| `_fetch_track(track_id, allow_sudo)` | Access check chain: track exists → `has_access('read')` → sudo fallback → event website check → event access check |
| `_get_event_tracks_agenda_domain(event)` | `event_id = event` AND (`is_published` OR `stage_id.is_visible_in_agenda`) |
| `_get_event_tracks_domain(event)` | Adds `is_published=True` unless user has `group_event_registration_desk` |
| `_get_dt_in_event_tz(datetimes, event)` | Converts UTC datetimes to event timezone |

---

### `EventOnlineController` (`controllers/event.py`)

Extends `WebsiteEventController` from `website_event`. Overrides `_get_registration_confirm_values()` to set `hide_sponsors=True`. This removes sponsor display from the event registration confirmation page when the advanced events module is installed.

---

### `TrackManifest` (`controllers/webmanifest.py`)

#### Route: WebManifest

```
/event/manifest.webmanifest
```
- **Auth**: Public
- **Type**: HTTP, `readonly=True`
- Returns `application/manifest+json` with name, scope (`/event`), icons at 192x192 and 512x512, `display: standalone`

#### Route: Service Worker

```
/event/service-worker.js
```
- **Auth**: Public
- Returns JavaScript with CDN URL substitution if `website.cdn_activated`
- `Service-Worker-Allowed` header scoped to `/event`

#### Route: Offline Page

```
/event/offline
```
- **Auth**: Public
- Renders `website_event_track.pwa_offline`

---

## Stage Pipeline (6 Stages)

```
Proposal → Confirmed → Announced → Published
                      ↘ Refused ↗     ↘ Cancelled ↗
```

| Stage | Auto-Publish | Agenda Visible | Notes |
|-------|-------------|----------------|-------|
| Proposal | No | No | Initial submission |
| Confirmed | No | No | Speaker confirmed, email sent |
| Announced | No | **Yes** | Publicly visible but not linked |
| Published | **Yes** | **Yes** | Fully accessible, access links work |
| Refused | No | No | Folded in kanban |
| Cancelled | No | No | `is_cancel=True`, cascades to both flags |

**Stage → Publication sync** (`_synchronize_with_stage`): Automatically called on track create and write (when `stage_id` changes):
- Moving to a stage with `is_fully_accessible=True` → `is_published=True`
- Moving to a stage with `is_cancel=True` → `is_published=False`
- The `website.published.mixin` then handles the actual `website_published` field and URL routing

---

## Wishlist / Reminder System (Three Layers)

1. **Manual wishlist**: Visitor clicks to add track → `event.track.visitor` with `is_wishlisted=True`
2. **Default wishlist (key tracks)**: Tracks with `wishlisted_by_default=True` → auto-added for all event registrants. Users can opt out via `is_blacklisted=True`.
3. **`is_reminder_on`**: The displayed state considers all three signals:
   - Public visitor: shows `wishlisted_by_default` only
   - Logged visitor with visitor record: `partner_id OR visitor_id` search
   - Logged visitor without visitor: `partner_id` search only

**Key track cannot be un-favorited**: Because `wishlisted_by_default` is a property of the track, users cannot fully remove such tracks from their wishlist — only suppress the reminder via `is_blacklisted`. This is intentional for must-attend tracks.

**Visitor never deleted**: `_inactive_visitors_domain()` ensures any visitor with `event_track_visitor_ids` is excluded from inactivity, protecting wishlist data from Odoo's periodic visitor cleanup.

---

## iCal and Google Calendar Integration

Each track generates two calendar entries:

**iCal (`.ics`)**: Generated server-side using `vobject`. Requires the `vobject` Python library. If missing, `_get_ics_file()` returns `False` for all tracks. The `vobject` library is not a core Odoo dependency.

**Google Calendar**: Client-side URL construction with URL-encoded parameters. The `description` field includes the track URL and a shortened HTML-to-text description (1900 char max).

**Track dates vs. event dates**: If a track has no `date` set, the event's dates are used instead. A warning message is embedded in the calendar description to inform attendees that track-specific times were not available at the time the invitation was created.

---

## PWA (Progressive Web App)

The module enables full PWA installation for event websites:

- **App icon**: Auto-generated from website favicon (512x512 PNG, square crop)
- **App name**: Configurable per website via `events_app_name` (default: `{Website Name} Events`)
- **Service Worker**: Handles caching for offline access via `/event/service-worker.js`
- **Offline page**: `/event/offline` renders a user-friendly offline state

**App icon generation edge case**: If the favicon is SVG, `_compute_app_icon` skips processing and sets `app_icon=False`. The PWA will fall back to no icon rather than displaying a broken image.

---

## Security

### Record Rules (`security/event_track_security.xml`)

| Rule | Model | Force | Groups | Effect |
|------|-------|-------|--------|--------|
| `event_track_public` | `event.track` | `website_published = True` | Public + Portal | Read-only access to published tracks |
| `ir_rule_event_track_tag_public` | `event.track.tag` | `color != 0 AND color != False` | Public + Portal | Tags without a color are hidden from public |

**Tag color security**: Tags with `color == 0` or no color are completely hidden from public/portal users via record rules. This is the mechanism for "internal" tags that should not appear on the website without authentication.

### Access Control (`security/ir.model.access.csv`)

| ID | Model | Group | R | W | C | D |
|----|-------|-------|---|---|---|---|
| `access_event_track_public` | `event.track` | `base.group_public` | 1 | 0 | 0 | 0 |
| `access_event_track_portal` | `event.track` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `access_event_track_employee` | `event.track` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_event_track_user` | `event.track.user` | `event.group_event_user` | 1 | 1 | 1 | 0 |
| `access_event_track_manager` | `event.track.manager` | `event.group_event_manager` | 1 | 1 | 1 | 1 |
| `access_event_track_visitor` | `event.track.visitor` | (none — no access) | 0 | 0 | 0 | 0 |
| `access_event_track_visitor_manager` | `event.track.visitor.manager` | `event.group_event_manager` | 1 | 1 | 1 | 1 |

**`event.track.visitor`**: No public or portal access. Only managers can read/write. The wishlist is accessed via computed fields on `event.track` (with `sudo()` in computes) and `website.visitor`. Public wishlist toggling works through the JSON-RPC controller which uses `sudo()` internally.

**`event.track.tag.stage`**: Public has read-only access (allows listing stages in the kanban view). Only managers can write.

---

## Performance Considerations

| Concern | Detail |
|---------|--------|
| `_compute_track_time_data` | Called on every track page render. No database access — purely in-memory datetime arithmetic. Fast but triggers on any datetime change. |
| `_compute_is_reminder_on` | Uses `search_read()` (not `search()`) to fetch all track-visitor states in one query, then maps in Python. More efficient than N queries for N tracks. |
| `_compute_wishlist_visitor_ids` | Uses `_read_group` with `array_agg` — single aggregate query instead of N lookups. |
| `_prepare_calendar_values` | Builds full agenda grid in memory. For events with hundreds of tracks across many locations/days, this can be memory-intensive. No pagination. |
| `_event_tracks_get_values` | `sudo().search()` fetches all matching tracks, then Python `filtered()` applies wishlist filter post-query. For large events, consider indexing on `event_id, date, is_published`. |
| Tag search via `/event/track_tag/search_read` | This route exists specifically to work around RPC ACL limitations for public users. Each tag search still performs a `search_read` — for large tag sets, this could be slow. |
| `website_image_url` compute | Calls `website.image_url()` which generates a unique signed URL per image. Called with `compute_sudo=True`. |

---

## Odoo 18 → 19 Changes

The `website_event_track` module had the following notable changes between Odoo 18 and 19:

| Area | Change |
|------|--------|
| **Visitor tracking** | The `_compute_is_reminder_on` logic was refined to handle more edge cases around partner + visitor OR matching |
| **Bot mitigation** | The 301 redirect for multi-tag GET requests was added to prevent crawler combinatorial explosion on tag pages |
| **Stage pipeline** | `is_visible_in_agenda` and `is_fully_accessible` are now stored computed fields (previously not stored) — faster kanban loading |
| **Calendar generation** | `_get_ics_file()` uses `vobject` iCalendar 3.0 serialization; gracefully degrades if library absent |
| **PWA manifest** | The `/event/manifest.webmanifest` route and app icon generation from favicon were introduced or enhanced in recent versions |
| **Tag ACL workaround** | The `/event/track_tag/search_read` JSON-RPC route was added to expose tags to public users without granting direct model read access |
| **`website.published.mixin`** | Stage synchronization (`_synchronize_with_stage`) was enhanced to properly handle the `is_published` ↔ `is_fully_accessible` / `is_cancel` relationships |

---

## Cross-Module Dependencies

| Module | Integration Point |
|--------|-------------------|
| `event` | Defines base `event.track` model; `website_event_track` extends it |
| `website_event` | Defines `website.event.menu`, event website controller; provides base website event routing |
| `mail` | Mail thread, activity mixin, email templates, notification layouts |
| `website` | SEO metadata, published mixin, searchable mixin, website menus, PWA support |
| `website_slides` | (via `website.event` indirectly) event slides integration |
| `website_event_track_live` | Adds live streaming to tracks (`website_event_track_live` extends track with livestream fields) |
| `website_event_track_quiz` | Adds quiz functionality to tracks |
| `event_track` | Note: no separate `event_track` module in Odoo 19 — functionality is split between `event` and `website_event_track` |

---

## Edge Cases

1. **No stages exist at track creation time**: `_get_default_stage_id()` returns `False` if `event.track.stage` is empty. This causes a `ValidationError` because `stage_id` is `required=True`. Occurs in test/demo scenarios where stage XML hasn't loaded.

2. **Both `date` and `date_end` are False**: All time-state computed fields (`is_track_live`, `is_track_soon`, etc.) return `False`. `_get_track_calendar_reminder_dates()` falls back to event dates. Track appears in "Coming Soon" section on the listing page.

3. **Tag without color**: Completely hidden from public/portal users via `ir.rule_event_track_tag_public`. Internal staff can still assign colorless tags to tracks — the tags simply don't render on the website.

4. **Public user toggling wishlist**: Creates a `website.visitor` record via `_get_visitor_from_request(force_create=True)`. The visitor is created without a `partner_id`. Wishlist is tracked purely by `visitor_id`.

5. **Track without location**: In the agenda grid, unlocated tracks reserve ALL locations at their time slot to prevent overlaps. This is visually correct (unlocated tracks span all rooms) but can consume significant grid space.

6. **Crawler visiting share URLs**: The social network crawler detection (from `website_event`) sets share status to `'shared'` when crawlers visit card URLs. The crawler detection is inherited from `website.published.mixin` behavior.

7. **Visitor merge**: When two visitors are merged, all `event_track_visitor_ids` are re-linked to the target. Unlinked records (`partner_id=False`) get the target's `partner_id` assigned. This prevents orphaned wishlist entries.

8. **Website menu deletion**: The `website.menu.unlink()` override is called during normal menu deletion. The `'/track' in menu_id.url` check is specific enough to avoid false positives from agenda menus.

---

## Related

- [Modules/event](Modules/event.md) — Base event management
- [Modules/website_event](Modules/website_event.md) — Event on website
- [Modules/website_event_track_live](Modules/website_event_track_live.md) — Live streaming integration
- [Modules/website_event_track_quiz](Modules/website_event_track_quiz.md) — Quiz during tracks
- [Modules/website_event_track_live_quiz](Modules/website_event_track_live_quiz.md) — Combined live + quiz
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine patterns in Odoo

---

## L4: Performance Analysis

### Wishlist Visitor Computation — `_compute_wishlist_visitor_ids`

The `wishlist_visitor_ids` Many2many and `wishlist_visitor_count` Integer are both computed by `_compute_wishlist_visitor_ids` using `_read_group` with `array_agg`:

```python
results = self.env['event.track.visitor']._read_group(
    [('track_id', 'in', self.ids), ('is_wishlisted', '=', True)],
    ['track_id'],
    ['visitor_id:array_agg'],
)
visitor_ids_map = {track.id: visitor_ids for track, visitor_ids in results}
for track in self:
    track.wishlist_visitor_ids = visitor_ids_map.get(track.id, [])
    track.wishlist_visitor_count = len(visitor_ids_map.get(track.id, []))
```

**Performance profile:**
- **Single query** for all tracks: the `_read_group` aggregates across `self.ids` in one pass, producing `len(self.ids)` rows maximum.
- **`array_agg`**: PostgreSQL aggregates all `visitor_id` values into a single array per track. For tracks with thousands of wishlist entries, this array can grow large — Odoo materializes the whole array in memory before assigning to the Many2many set.
- **No post-query filtering**: all visitors in the array are accepted as wishlist entries. A visitor who is later deactivated is still counted until the next recompute.
- **`compute_sudo=True`**: the computation runs as superuser, bypassing record rules. This avoids the overhead of applying `ir.rule` filters but means all visitor IDs are exposed to any user who can compute the field (typically restricted to `event.group_event_user` via group controls on the field definition).

**Optimization note**: For events with >10,000 registered visitors, `array_agg` can cause memory pressure on the PostgreSQL side. An alternative would be to store only the count (`wishlist_visitor_count`) as a direct `_count` aggregate, and drop `wishlist_visitor_ids` unless the visitor list is actually rendered. The field remains in the codebase for list/form display in the backend.

### Reminder State Computation — `_compute_is_reminder_on`

This is the most contextually complex compute in the module. The full flow:

```
_current_visitor = _get_visitor_from_request()
  → if public, no visitor record: return wishlisted_by_default
  → if public, has visitor record: domain = [('visitor_id', '=', current_visitor.id)]
  → if logged + has visitor record: domain = [('partner_id', '=', uid.partner_id) OR ('visitor_id', '=', current_visitor.id)]
  → if logged, no visitor record: domain = [('partner_id', '=', uid.partner_id)]

search_read(event_track_visitor_ids, fields=['track_id', 'is_wishlisted', 'is_blacklisted'])
  → builds wishlist_map {track_id: {is_wishlisted, is_blacklisted}}
  → for each track: is_reminder_on = is_wishlisted OR (wishlisted_by_default AND NOT is_blacklisted)
```

**Query cost**: `search_read` fetches ALL track-visitor associations for the current user across ALL tracks being displayed in a single query. For a track listing page with 50 tracks, this is 1 query. For a kanban view with 200 tracks, this is still 1 query. The `search_read` approach is correct and efficient.

**False-negative risk**: If a user has `wishlisted_by_default` tracks but has never had a visitor record created (e.g., they are logged in via the backend, not the website), they will not appear in the `event.track.visitor` table and `_get_event_track_visitors()` will not auto-create one for them (because `force_create=False` by default in `_compute_is_reminder_on`). In this case, `is_reminder_on` falls back to `wishlisted_by_default` — which is correct behavior.

### Calendar Grid Building — `_prepare_calendar_values`

The agenda grid is built entirely in-memory with no pagination:

```python
tracks_sudo = request.env['event.track'].sudo().search(base_track_domain)  # NO limit
time_slots_by_tracks = {track: self._split_track_by_days(track, local_tz) for track in tracks_sudo}
```

For an event with 500 tracks across 3 days and 10 locations:
- `tracks_sudo` loads all 500 track records in a single query.
- `time_slots_by_tracks` builds a dict with 500 keys, each containing a dict of time slots.
- `tracks_by_rounded_times` builds a 3D structure: `day → time_slot (15-min) → location → track`.
- The final `global_time_slots_by_day` is a dict of dicts with potentially thousands of entries.

**Memory ceiling**: A large enterprise event could generate hundreds of MB of Python objects for the agenda grid. The module provides no server-side pagination or lazy loading for the agenda. The recommended mitigation is to use the track list page (`/event/{slug}/track`) for large events, which does not build a grid.

### Image URL Generation

```python
def _compute_website_image_url(self):
    for track in self:
        if track.website_image:
            track.website_image_url = self.env['website'].image_url(track, 'website_image', size=1024)
        else:
            track.website_image_url = '/website_event_track/static/src/img/event_track_default_%d.jpeg' % (track.id % 2)
```

`website.image_url()` is called with `compute_sudo=True`. For published tracks on a public listing page, this generates a signed URL on every render. The signature is based on the attachment's write date — it changes every time the image is updated. Signed URLs are not cached by the browser across sessions.

**Optimization**: If track images are mostly static (uploaded once, rarely changed), consider storing `website_image_url` as a stored computed field to avoid recomputing the URL on every page load.

---

## L4: Odoo 18 → 19 Specific Changes

### Stage Pipeline — Stored Computed Flags

In Odoo 18, `is_visible_in_agenda` and `is_fully_accessible` on `event.track.stage` were **non-stored computed fields**. Every kanban render triggered a recompute of all 6 stage records to determine visibility.

In Odoo 19, both are stored computed fields:
```python
@api.depends('is_cancel', 'is_fully_accessible')
def _compute_is_visible_in_agenda(self):
    for record in self:
        if record.is_cancel:
            record.is_visible_in_agenda = False
        elif record.is_fully_accessible:
            record.is_visible_in_agenda = True

@api.depends('is_cancel', 'is_visible_in_agenda')
def _compute_is_fully_accessible(self):
    for record in self:
        if record.is_cancel or not record.is_visible_in_agenda:
            record.is_fully_accessible = False
```

**Migration impact**: After upgrading, the stored values may not reflect the current `is_cancel` state until the first write triggers recomputation. A migration script should either write to each stage to force recompute, or directly update the stored columns based on `is_cancel`.

### `_primary_email` Declaration

`website_event_track` declares `_primary_email = 'contact_email'` on `event.track`. This is used by `mail.thread` to determine which field is the primary email for threading. In Odoo 18, this field may not have been explicitly declared — the parent `event.track` model had its own `_primary_email` set to `partner_email`. The explicit declaration in the extension ensures that when a track's contact email is set independently of the partner, mail threading uses the right address.

### iCal `vobject` Import Guard

```python
try:
    import vobject
except ImportError:
    _logger.warning("`vobject` Python module not found, iCal file generation disabled...")
    vobject = None
```

In Odoo 19, the import is guarded at module load time. If `vobject` is absent, `_get_ics_file()` returns `False` for all tracks. In earlier versions, the module may have crashed on import if `vobject` was not installed. The current pattern is a soft degrade.

### Bot Mitigation Addition

The 301 redirect for multi-tag GET requests was introduced specifically to prevent search engine crawlers from generating combinatorial URL explosion:

```python
if searches.get('tags', '[]').count(',') > 0 and request.httprequest.method == 'GET':
    return request.redirect(f'/event/{slug(event)}/track', code=301)
```

This targets crawlers that index paginated tag pages. The redirect tells crawlers the tagged page has moved permanently to the unfiltered track list. The `prevent_redirect` parameter in templates allows internal links to bypass this check.

---

## L4: SEO for Event Tracks

### `website.seo.metadata` Mixin Inheritance

`event.track` inherits from `website.seo.metadata` which provides:
- `website_meta_title`, `website_meta_description`, `website_meta_keywords` — editable SEO meta fields
- `seo_name` — URL-safe variant of the track name
- Automatic rendering of `<title>` and `<meta name="description">` tags on the track page via the QWeb template

The mixin's `_default_website_meta()` method is called at render time to populate missing meta fields with track/event data.

### Canonical URL

`website.published.mixin` provides the base `website_url` field. The track's `_compute_website_url()` appends the event slug and track slug:

```python
sponsor.website_url = f'/event/{ir.http._slug(event_id)}/track/{ir.http._slug(track)}'
```

The `sitemap=True` on the track page route (`/event/<event>/track/<track>`) ensures the track URL is included in the XML sitemap for the event.

### Robots and Sitemap

Tracks in `stage0` (Proposal) and `stage4` (Refused) stages have `is_visible_in_agenda=False` and `is_fully_accessible=False`. They are not published (`is_published=False`). They will not appear in the sitemap or be indexed.

Tracks in `stage1` (Confirmed) are visible in the agenda but not published. They appear in the sitemap if the event sitemap includes track pages — which is controlled by the event's website page configuration.

The stage-based publication gating provides a natural SEO gating mechanism: proposals and refused talks are never indexed.

### OG (Open Graph) Tags

The QWeb template `website_event_track.event_track_main` renders OG meta tags using `website_meta_*` fields. These are populated via the `website.seo.metadata` mixin and can be customized per-track in the backend form.

---

## L4: Security Deep Analysis

### Tag Color as Access Control Mechanism

The `ir.rule` on `event.track.tag` uses `color != 0 AND color != False`:

```xml
<field name="domain_force">[('color', '!=', False), ('color', '!=', 0)]</field>
```

This is a **display-level security mechanism**, not a write protection. An event manager can assign a colorless tag to a track, and the track is not affected. The colorless tag simply does not appear in the website frontend's tag filter or tag list.

**Security implication**: The color check in the record rule filters public/portal access to tags with `color > 0`. However, internal staff (event managers) can freely assign any tag to any track. The tag name and description are not redacted — only the tag's presence in the filter UI is hidden.

**Bypass**: If a public user knows the ID of a colorless tag, they can construct a search that includes it (via the `/event/track_tag/search_read` JSON-RPC route, which does a `search_read` directly). The JSON-RPC route bypasses the record rule because it does not apply to RPC-level `search_read` calls in the same way. However, since the tag's color is not returned in the `search_read` output by default (unless explicitly requested), the user gets no visible benefit from the tag.

### Wishlist ACL via JSON-RPC `sudo()`

The wishlist toggle endpoint `track_reminder_toggle` uses `sudo()` internally when fetching track visitors:

```python
def track_reminder_toggle(self, track_id, set_reminder_on):
    track = self._fetch_track(track_id, allow_sudo=True)  # allows sudo fallback
    event_track_partner = track._get_event_track_visitors(force_create=force_create)
```

Inside `_get_event_track_visitors()`:
```python
track_visitors = self.env['event.track.visitor'].sudo().search(...)
```

**Security analysis**: The `sudo()` on `event.track.visitor` allows public users to create and modify their own wishlist entries through the JSON-RPC endpoint. The `event.track.visitor` model has no ACL entry for `base.group_public` — only `event.group_event_manager` has access. However, the controller circumvents this by using `sudo()` on the model's search and create calls directly, not through ORM access rights.

This is a **by-design** bypass for the public-facing wishlist feature. The security assumption is that the controller's business logic (checking `track_id` belongs to the visitor, validating state changes) is sufficient. The risk is that a malformed or malicious request to `/event/track/toggle_reminder` could create orphan `event.track.visitor` records.

**Mitigation**: The controller uses `_get_visitor_from_request()` to obtain the current visitor, and the domain in `_get_event_track_visitors()` filters on `visitor_id` or `partner_id`. A crafted request cannot target another user's wishlist because the domain restricts the search to the current visitor/partner.

---

## L4: Wishlist Visitor Count Performance — `_compute_wishlist_visitor_ids` Deep Dive

The `_read_group` with `array_agg` pattern is used here instead of a simple `search_count` because the template needs the actual visitor IDs for rendering a "wishlisted by" list on the track page. However, for most display contexts, only the count is needed.

**Array aggregation behavior**: In PostgreSQL, `array_agg()` returns `NULL` for empty sets rather than an empty array. The code handles this:

```python
visitor_ids_map = {track.id: visitor_ids for track, visitor_ids in results}
for track in self:
    track.wishlist_visitor_ids = visitor_ids_map.get(track.id, [])
```

If a track has no wishlist entries, the `results` set has no row for that track — the `visitor_ids_map` entry is missing, and `.get(track.id, [])` returns the empty list. Correct.

**PostgreSQL group by behavior with array_agg**: When `_read_group` is called with a Many2many/One2many relational field (`visitor_id`), Odoo generates a subquery join. For large datasets, this can produce a plan that is a sequential scan on `event_track_visitor` rather than an indexed lookup. Adding an index on `(track_id, is_wishlisted)` would improve performance for events with many tracks but fewer wishlist entries.

---

## L4: Cross-Module Integration — `website_event_track` ↔ `event_sale`

When `event_sale` is installed alongside `website_event_track`, event registration creates attendee records. The `wishlisted_by_default` feature interacts with registration as follows:

1. A user registers for an event via the website cart/checkout (from `event_sale`).
2. The registration confirmation triggers `_update_visitor_last_visit()` on the visitor record.
3. The visitor's wishlist is not automatically populated at registration time — `wishlisted_by_default` tracks are only added to the wishlist **when the visitor first views the track page** (via `_get_event_track_visitors(force_create=True)`).
4. For tracks with `wishlisted_by_default=True`, the `is_reminder_on` field returns `True` even if no `event.track.visitor` record exists yet.

This means a registered attendee who never visits the track listing page will not have any `event.track.visitor` records created. Their reminder appears active based on the track's `wishlisted_by_default` flag alone.

---

## L4: Failure Modes and Error Handling

### Stage Synchronization Failures

`_synchronize_with_stage()` is called on every track `create()` and `write()` (when stage changes). If the stage's `is_fully_accessible` and `is_cancel` flags are misconfigured:

- **Both True**: Both conditions are evaluated. `is_cancel=True` takes precedence (first `if` block), so `is_published=False`. This is correct — cancelled tracks cannot be published regardless of accessibility.
- **Neither True nor False**: The fields are `False` by default. New stages with no explicit flags set will have `is_visible_in_agenda=False` and `is_fully_accessible=False`. Tracks in such stages are never published and never visible on the website.

### CTA URL Cleaning Failures

`create()` and `write()` both call `res.partner._clean_website()` on the CTA URL:

```python
if values.get('website_cta_url'):
    values['website_cta_url'] = self.env['res.partner']._clean_website(values['website_cta_url'])
```

If `_clean_website` returns an empty string for an invalid URL, the CTA button's `is_website_cta_live` compute still runs. An empty URL makes the button non-functional but does not raise an error.

### Missing `vobject` — iCal Failure

```python
def _get_ics_file(self):
    result = dict.fromkeys(self.ids, False)
    if not vobject:
        return result
    # ... generate ICS
```

When `vobject` is missing, the ICS download returns a 404 from the controller (`NotFound()`). The template may still show a "Add to Calendar" button — it has no server-side guard. Clicking the button produces a 404 response.

### Proposal Form — Email Normalization

The proposal POST endpoint uses `email_normalize()` for validation:

```python
valid_speaker_email = tools.email_normalize(post['partner_email'])
if not valid_speaker_email:
    # raises 'invalidFormInputs' error
```

The `email_normalize()` function from `odoo.tools.mail` handles Unicode normalization, domain validation (MX record check not performed), and address format validation. Invalid emails without a phone number trigger the error. This is correct.

---

## L4: Track Suggestion Algorithm — `_get_track_suggestions`

The heuristic for "Up Next" suggestions is a multi-key sort:

```python
track_candidates = track_candidates.sorted(
    lambda track: (
        track.is_published,                          # 1. published first
        track.track_start_remaining == 0              # 2. started < 10min ago, not done
           and track.track_start_relative < (10 * 60)
           and not track.is_track_done,
        track.track_start_remaining > 0,             # 3. soonest upcoming first
        -1 * track.track_start_remaining,
        track.is_reminder_on,                        # 4. wishlisted
        not track.wishlisted_by_default,             # 5. manually wishlisted > default
        len(track.tag_ids & self.tag_ids),           # 6. tag overlap count
        track.location_id == self.location_id,       # 7. same location
        randint(0, 20),                              # 8. random factor
    ), reverse=True
)
```

**Key design decisions**:
- Sort keys 1-3 implement a temporal priority: live → soon → upcoming.
- Key 5 (`not wishlisted_by_default`): manually wishlisted tracks rank above default-wishlisted tracks. This is intentional — manually curated tracks signal higher user interest.
- Key 8 (random): a randint between 0 and 20 introduces entropy for equal-rank tracks, preventing the same suggestions from appearing in the same order on every page load.
- The `limit=10` is applied after sorting. If there are fewer than 10 candidates, all are returned.
