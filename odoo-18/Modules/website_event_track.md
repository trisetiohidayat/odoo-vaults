---
Module: website_event_track
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_track
---

## Overview

Core track/talk management for website events. Adds the full track scheduling system including talk proposals, speaker management, wishlist/visitors tracking, tags, locations, stages, and SEO metadata. Tracks can have CTA (Call To Action) buttons shown during live sessions.

**Key Dependencies:** `website_event`, `mail`, `event`, `website_blog`

**Python Files:** 11 model files

---

## Models

### event_track_tag_category.py — TrackTagCategory

**Inheritance:** Base (standalone `_name = 'event.track.tag.category'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required, translated |
| `sequence` | Integer | Yes | Default 10 |
| `tag_ids` | One2many | Yes | `event.track.tag` records |

---

### event_track_tag.py — TrackTag

**Inheritance:** Base (standalone `_name = 'event.track.tag'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required, unique |
| `track_ids` | Many2many | Yes | `event.track` |
| `color` | Integer | Yes | Color index (0 = unpublished), default random 1-11 |
| `sequence` | Integer | Yes | Default 10 |
| `category_id` | Many2one | Yes | `event.track.tag.category`, ondelete=set null |

**SQL Constraints:**
- `name_uniq`: `unique(name)` — tag names must be unique

---

### event_track_location.py — TrackLocation

**Inheritance:** Base (standalone `_name = 'event.track.location'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required |
| `sequence` | Integer | Yes | Default 10 |

---

### event_track_stage.py — TrackStage

**Inheritance:** Base (standalone `_name = 'event.track.stage'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required, translated |
| `sequence` | Integer | Yes | Default 1 |
| `mail_template_id` | Many2one | Yes | `mail.template` for stage change notifications |
| `color` | Integer | Yes | Kanban color |
| `description` | Text | Yes | Translated |
| `legend_blocked` | Char | Yes | Red kanban label, default _('Blocked') |
| `legend_done` | Char | Yes | Green kanban label, default _('Ready for Next Stage') |
| `legend_normal` | Char | Yes | Grey kanban label, default _('In Progress') |
| `fold` | Boolean | Yes | Folded in kanban view |
| `is_visible_in_agenda` | Boolean | Yes | Auto-set: False if cancelled, True if fully accessible |
| `is_fully_accessible` | Boolean | Yes | Auto-set: False if cancelled or not visible |
| `is_cancel` | Boolean | Yes | Cancelled stage flag |

**Compute Methods:**
- `_compute_is_visible_in_agenda()`: `is_cancel=False` AND (`is_fully_accessible` OR not cancelled)
- `_compute_is_fully_accessible()`: `is_cancel=False` AND `is_visible_in_agenda=True`

---

### event_track.py — EventTrack

**Inheritance:** `mail.thread`, `mail.activity.mixin`, `website.seo.metadata`, `website.published.mixin`

**Model:** `_name = 'event.track'`, `_order = 'priority, date'`

**Key Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Title, required, translated |
| `event_id` | Many2one | Yes | `event.event`, required |
| `active` | Boolean | Yes | Default True |
| `user_id` | Many2one | Yes | Responsible, default=`env.user` |
| `company_id` | Many2one | No | Related `event_id.company_id` |
| `tag_ids` | Many2many | Yes | `event.track.tag` |
| `description` | Html | Yes | Translated, sanitize_form=False |
| `color` | Integer | Yes | Agenda color |
| `priority` | Selection | Yes | `'0'` (Low) to `'3'` (Highest), default `'1'` |
| `stage_id` | Many2one | Yes | `event.track.stage`, default=`_get_default_stage_id`, required, tracking |
| `kanban_state` | Selection | Yes | `'normal'`, `'done'`, `'blocked'`, default `'normal'`, tracking |
| `kanban_state_label` | Char | Yes | Computed label from stage legends |
| `partner_id` | Many2one | Yes | Contact speaker |
| `partner_name` | Char | Yes | Computed from partner, writable |
| `partner_email` | Char | Yes | Computed from partner, writable |
| `partner_phone` | Char | Yes | Computed from partner, writable |
| `partner_biography` | Html | Yes | Computed from partner, writable |
| `partner_function` | Char | Yes | Computed from partner, writable |
| `partner_company_name` | Char | Yes | Computed from partner, writable |
| `partner_tag_line` | Char | No | Computed: name, function at company |
| `image` | Image | Yes | Speaker photo, max 256x256 |
| `contact_email` | Char | Yes | Computed from partner, writable |
| `contact_phone` | Char | Yes | Computed from partner, writable |
| `location_id` | Many2one | Yes | `event.track.location` |
| `date` | Datetime | Yes | Track start |
| `date_end` | Datetime | Yes | Computed from `date + duration` |
| `duration` | Float | Yes | Default 0.5 hours |
| `is_track_live` | Boolean | No | Currently in progress |
| `is_track_soon` | Boolean | No | Starting within 30 minutes |
| `is_track_today` | Boolean | No | Scheduled for today |
| `is_track_upcoming` | Boolean | No | Scheduled in the future |
| `is_track_done` | Boolean | No | Finished |
| `track_start_remaining` | Integer | No | Seconds until start |
| `track_start_relative` | Integer | No | Relative seconds (negative if started) |
| `website_image` | Image | Yes | Max 1024x1024px |
| `website_image_url` | Char | No | Computed image URL |
| `event_track_visitor_ids` | One2many | Yes | `event.track.visitor`, groups restricted |
| `is_reminder_on` | Boolean | No | Visitor wishlist status |
| `wishlist_visitor_ids` | Many2many | No | Computed, sudo, searchable |
| `wishlist_visitor_count` | Integer | No | Count of wishlisted visitors |
| `wishlisted_by_default` | Boolean | Yes | Always wishlisted for registered attendees |
| `website_cta` | Boolean | Yes | Enable Call To Action button |
| `website_cta_title` | Char | Yes | CTA button label |
| `website_cta_url` | Char | Yes | CTA target URL, cleaned |
| `website_cta_delay` | Integer | Yes | Minutes after start to show CTA |
| `is_website_cta_live` | Boolean | No | CTA is currently visible |
| `website_cta_start_remaining` | Integer | No | Seconds until CTA shows |

**Stage Methods:**
- `_synchronize_with_stage(stage)`: If stage `is_fully_accessible` → sets `is_published=True`; if `is_cancel` → `is_published=False`

**Time Compute Methods:**
- `_compute_end_date()`: `date + timedelta(hours=duration*60)`
- `_compute_track_time_data()`: All live/soon/today/upcoming/done flags using UTC comparison
- `_compute_cta_time_data()`: CTA visibility based on `date + delay` and `date_end`
- `_compute_kanban_state_label()`: Maps kanban_state to stage legend string

**Visitor/Wishlist Methods:**
- `_compute_is_reminder_on()`: Checks `event.track.visitor` for current user/visitor
- `_compute_wishlist_visitor_ids()`: Uses `_read_group` with `visitor_id:array_agg`
- `_search_wishlist_visitor_ids()`: Search support for wishlist
- `_get_event_track_visitors(force_create=False)`: Gets or creates track visitor records

**CRUD:**
- `create(vals_list)`: Cleans CTA URL, sends notification, synchronizes stage
- `write(vals)`: Cleans CTA URL, resets kanban_state on stage change, synchronizes stage

**Messaging:**
- `_message_get_default_recipients()`: Returns email_to from contact_email or partner_email
- `_message_get_suggested_recipients()`: Adds partner and email contacts
- `_message_post_after_hook()`: Auto-links created partners from chatter to tracks
- `_track_template()`: Sends mail.template on stage change
- `_track_subtype()`: Returns `mt_track_blocked` or `mt_track_ready` subtypes

**Actions:**
- `open_track_speakers_list()`: Opens kanban of all speakers
- `get_backend_menu_id()`: Returns event main menu
- `_get_track_suggestions()`: Returns related tracks using multi-factor sorting

---

### event_track_visitor.py — TrackVisitor

**Inheritance:** Base (standalone `_name = 'event.track.visitor'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `partner_id` | Many2one | Yes | Computed from visitor_id |
| `visitor_id` | Many2one | Yes | `website.visitor`, cascade delete |
| `track_id` | Many2one | Yes | `event.track`, cascade delete, required |
| `is_wishlisted` | Boolean | Yes | User marked as favorite |
| `is_blacklisted` | Boolean | Yes | User opted out of reminders for key tracks |

---

### event_event.py — Event

**Inheritance:** `event.event`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `track_ids` | One2many | Yes | Tracks in this event |
| `track_count` | Integer | No | Non-cancelled track count |
| `website_track` | Boolean | Yes | Show tracks on website |
| `website_track_proposal` | Boolean | Yes | Show talk proposal form |
| `track_menu_ids` | One2many | Yes | Tracks menus |
| `track_proposal_menu_ids` | One2many | Yes | Proposal menus |
| `allowed_track_tag_ids` | Many2many | Yes | Available tags for proposals |
| `tracks_tag_ids` | Many2many | Yes | Tags actually used (color != 0) |

**Menu Methods:**
- `_get_website_menu_entries()`: Adds Talks (`/event/{slug}/track`), Agenda (`/event/{slug}/agenda`), Talk Proposals (`/event/{slug}/track_proposal`)

---

### event_type.py — EventType

**Inheritance:** `event.type`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `website_track` | Boolean | Yes | From `website_menu` |
| `website_track_proposal` | Boolean | Yes | From `website_menu` |

---

### website_visitor.py — WebsiteVisitor

**Inheritance:** `website.visitor`

| Field | Type | Store | Groups | Notes |
|-------|------|-------|--------|-------|
| `event_track_visitor_ids` | One2many | Yes | Event User | Track/visitor links |
| `event_track_wishlisted_ids` | Many2many | No | Event User | Wishlisted tracks |
| `event_track_wishlisted_count` | Integer | No | Event User | Wishlisted count |

**Methods:**
- `_compute_event_track_wishlisted_ids()`: Uses `_read_group` with array_agg
- `_search_event_track_wishlisted_ids()`: Search support
- `_inactive_visitors_domain()`: Excludes visitors with active push subscriptions
- `_merge_visitor(target)`: Merges track visitor links to target

---

### website.py — Website

**Inheritance:** `website`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `app_icon` | Image | Yes | PWA mobile app icon (512x512 PNG), computed from favicon |
| `events_app_name` | Char | Yes | PWA app name, computed from website name if empty |

**Methods:**
- `_compute_events_app_name()`: `'{website.name} Events'` if empty
- `_check_events_app_name()`: `@api.constrains` — must not be empty
- `_compute_app_icon()`: Crops and resizes favicon to 512x512 PNG

---

### website_event_menu.py — EventMenu

**Inheritance:** `website.event.menu`

| Field | Type | Notes |
|-------|------|-------|
| `menu_type` | Selection | Adds `'track'` and `'track_proposal'` to selection, ondelete cascade |

---

### website_menu.py — WebsiteMenu

**Inheritance:** `website.menu`

| Method | Description |
|--------|-------------|
| `unlink()` | Overrides to sync event track fields when `/track` menu items are deleted |

---

### res_config_settings.py — ResConfigSettings

**Inheritance:** `res.config.settings`

| Field | Type | Notes |
|-------|------|-------|
| `events_app_name` | Char | Related `website_id.events_app_name`, readonly=False |

---

## Security / Data

**Security Files:**

`security/event_track_security.xml`:
- `event_track_public`: Public/portal read only where `website_published=True`
- `ir_rule_event_track_tag_public`: Public/portal read tags with `color != 0`

`security/ir.model.access.csv`:
- Tracks: Public/Portal read, Employee read, User (event group) CRUD, Manager CRUD
- Tags: Public read, User (event) write, Manager CRUD
- Locations: Event user write, Manager CRUD
- Stages: Public read, Manager write
- `event.track.visitor`: No public access, Manager full access
- Tag categories: Event user write, Manager CRUD

**Data Files:**
- `data/event_data.xml`, `event_track_data.xml`: Stage and tag data
- `data/event_demo.xml`, `event_track_demo.xml`: Demo tracks
- `data/mail_message_subtype_data.xml`, `mail_template_data.xml`: Messaging

---

## Critical Notes

- Stage auto-publishing: when `stage_id.is_fully_accessible=True`, track auto-publishes; when `stage_id.is_cancel=True`, track is unpublished
- `_synchronize_with_stage` is called on both create and write (when stage changes)
- Wishlist search: `_search_wishlist_visitor_ids` raises `NotImplementedError` for `not in` operator
- `is_reminder_on` respects both explicit wishlist and `wishlisted_by_default` for tracks; `is_blacklisted` allows opting out of default wishlist
- `_get_track_suggestions` uses a multi-factor sort: live first, then by time proximity, then wishlisted, tag match, location match, and random
- CTA URL is cleaned via `res.partner._clean_website()` on write
- `website_image_url` falls back to a default image based on `id % 2` (alternating defaults)
- `app_icon` is derived from the website favicon — requires favicon to be set for the PWA to work
- v17→v18: Quiz models moved to `website_event_track_quiz`; CTA (Magic Button) feature was added in v17 and enhanced in v18
