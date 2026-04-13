---
description: YouTube live streaming integration for event tracks — video URL parsing, replay detection, chat availability, and widescreen layout.
tags:
  - odoo
  - odoo19
  - modules
  - website
  - events
  - streaming
---

# website_event_track_live — Live Event Track Streaming

## Module Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `website_event_track_live` |
| **Category** | Marketing/Events |
| **Depends** | `website_event_track` |
| **License** | LGPL-3 |
| **Odoo Version** | 19.0 CE |

`website_event_track_live` extends `website_event_track` with YouTube-based live streaming support for event tracks. It parses YouTube video URLs to extract video IDs, computes replay/live/soon/done states, fetches chat availability, manages widescreen layouts, and provides a "next track suggestion" feature that recommends another YouTube-enabled track from the same event.

## Architecture

### Module Structure

```
website_event_track_live/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── track_live.py     # EventTrackLiveController (JSON-RPC endpoint)
│   └── session.py        # WebsiteEventSessionLiveController (page values)
├── models/
│   ├── __init__.py
│   └── event_track.py    # event.track field extensions
├── views/
│   ├── event_track_templates_list.xml
│   ├── event_track_templates_page.xml
│   └── event_track_views.xml
├── static/
│   ├── src/
│   │   ├── interactions/*.js  # Frontend interactions
│   │   ├── xml/*.xml          # QWeb templates
│   │   └── scss/*.scss
│   └── description/
├── data/
│   └── event_track_demo.xml
└── tests/
```

### Key Design Principles

1. **YouTube-first** — the module assumes all streaming goes through YouTube (no generic RTMP/HLS support). Video IDs are extracted from URLs using regex, then used for embeds and thumbnails.
2. **State-driven** — track streaming states (`is_track_soon`, `is_track_live`, `is_track_done`, `is_youtube_replay`) are computed from the event date fields and an explicit `is_youtube_replay` boolean on the track.
3. **Controller injection** — the module overrides `EventTrackController` methods rather than creating a standalone controller, preserving all parent functionality.

---

## L1 — How Live Event Track Streaming Works

### Streaming Flow

```
Event manager enters YouTube URL on event.track form
    ↓
_youtube_video_id is computed via regex
    ↓
Track state is derived from date fields + is_youtube_replay flag
    ↓
Website visitor navigates to track page
    ↓
track_live.py controller returns page values
    ↓
Widescreen layout activated if track has YouTube video + is live/replay/soon/done
    ↓
YouTube iframe embedded with correct video ID
    ↓
Live chat available if: has video URL AND NOT is_youtube_replay AND (is_track_soon OR is_track_live)
    ↓
Mobile chat disabled via user-agent detection (Android/iPad/iPhone)
```

### Track States

| State | Condition |
|-------|-----------|
| **Live** | `is_track_live` (track date is within the live window) |
| **Soon** | `is_track_soon` (track date is approaching but not yet live) |
| **Replay** | `is_youtube_replay == True` |
| **Done** | `is_track_done == True` |
| **No Video** | `youtube_video_url` is empty |

### Next Track Suggestion

The `/event_track/get_track_suggestion` JSON-RPC endpoint returns the next track in the same event that also has a YouTube URL. This drives the "Up Next" suggestion shown after a track ends.

---

## L2 — Field Types, Defaults, Constraints

### `event.track` Fields Added by `website_event_track_live`

| Field | Odoo Type | Stored | Default | Notes |
|-------|-----------|--------|---------|-------|
| `youtube_video_url` | Char | Yes | — | Full YouTube URL input by event manager |
| `youtube_video_id` | Char | No (compute) | — | 11-character YouTube video ID extracted from URL |
| `is_youtube_replay` | Boolean | Yes | — | Checkbox: "video is already on YouTube, skip live-only features" |
| `is_youtube_chat_available` | Boolean | No (compute) | — | `True` when chat embed should be shown |

### Computed Field Dependencies

#### `_compute_youtube_video_id`
- **Depends:** `youtube_video_url`
- **Logic:** Applies regex `^.*(youtu.be\/|v\/|u/\w\/|embed\/|live\/|watch\?v=|&v=)([^#&?]*).*` and extracts group(2). The 11-character constraint filters out most malformed URLs.
- **Side effect:** Sets `youtube_video_id = False` if URL is empty or regex fails.

#### `_compute_website_image_url`
- **Depends:** `youtube_video_id`, `is_youtube_replay`, `date_end`, `is_track_done`
- **Logic:** For tracks with `youtube_video_id` but no custom `website_image`, sets `website_image_url` to `https://img.youtube.com/vi/{id}/maxresdefault.jpg`
- **Pattern:** Uses `super()` for non-YouTube tracks, then applies thumbnail URL only to YouTube tracks.

#### `_compute_is_youtube_chat_available`
- **Depends:** `youtube_video_url`, `is_youtube_replay`, `date`, `date_end`, `is_track_upcoming`, `is_track_live`
- **Logic:** `True` if the track has a YouTube URL, is NOT a replay, AND is in "soon" or "live" state. During replay mode, chat is disabled.

### Constraints

There are **no explicit Python constraints** (`@api.constrains`, `_sql_constraints`) in this module. Validation is implicit:
- The regex pattern rejects malformed URLs at the compute stage (resulting in `youtube_video_id = False`)
- The template layer conditionally renders the chat widget based on `is_youtube_chat_available`

### Controller Method: `_event_track_page_get_values`

Overrides the parent `EventTrackController._event_track_page_get_values()`:

```python
def _event_track_page_get_values(self, event, track, **options):
    if 'widescreen' not in options:
        options['widescreen'] = track.youtube_video_url and (
            track.is_youtube_replay or track.is_track_soon
            or track.is_track_live or track.is_track_done
        )
    values = super()._event_track_page_get_values(event, track, **options)
    values['is_mobile_chat_disabled'] = bool(re.match(
        r'^.*(Android|iPad|iPhone).*',
        request.httprequest.headers.get('User-Agent', '')))
    return values
```

Key behaviors:
- Widescreen is enabled for any track with a YouTube URL in replay/soon/live/done states
- Mobile chat is disabled for Android/iPad/iPhone based on User-Agent regex

---

## L3 — Cross-Model Relationships, Override Patterns, Workflow Triggers

### Cross-Model Relationships

| Related Model | Relationship | Direction | Purpose |
|---------------|-------------|-----------|---------|
| `event.track` | Field extension | Extends | Adds all YouTube-related fields and computed states |
| `event.event` | Via `track.event_id` | Accessed read-only | Used to find next suggestion track from same event |
| `website.visitor` | Via `_get_visitor_from_request()` | Accessed in controller | Used to personalize suggestions |

### Override Patterns

**Pattern: Prepend-override of `_event_track_page_get_values`**

The module inherits `EventTrackController` from `website_event_track` and overrides the `_event_track_page_get_values` method. It first sets `widescreen` in `options` before calling `super()`, then appends `is_mobile_chat_disabled` to the returned values dict.

```python
# controllers/track_live.py
class EventTrackLiveController(EventTrackController):

    def _event_track_page_get_values(self, event, track, **options):
        # 1. Set widescreen option
        if 'widescreen' not in options:
            options['widescreen'] = track.youtube_video_url and (...)
        # 2. Call parent (which may use options)
        values = super()._event_track_page_get_values(event, track, **options)
        # 3. Append mobile detection result
        values['is_mobile_chat_disabled'] = bool(...)
        return values
```

### Workflow Triggers

| Trigger | Mechanism | Result |
|---------|-----------|--------|
| **Track page load** | HTTP GET to `/event/<id>/track/<track_id>` | Triggers `_event_track_page_get_values` → sets widescreen + mobile flags |
| **Next track button** | JS calls `/event_track/get_track_suggestion` JSON-RPC | Returns next YouTube-enabled track in same event |
| **Track state change (date-based)** | Computed fields re-evaluate when `date`/`date_end` change | `is_track_soon`/`is_track_live`/`is_track_done` update automatically |
| **Replay mode toggle** | Event manager toggles `is_youtube_replay` | `is_youtube_chat_available` recalculates; widescreen persists |

### Error Handling

- If `youtube_video_url` regex fails to extract an 11-char ID: `youtube_video_id = False` and no video embed renders
- If no next suggestion track exists: `/event_track/get_track_suggestion` returns `False` (not an error)
- Mobile User-Agent regex is intentionally naive — it matches the most common cases but may miss some edge-case mobile browsers

---

## L4 — Odoo 18 → 19 Changes, Performance

### Odoo 18 → 19 Changes

Based on source analysis, no breaking changes are visible between Odoo 18 and 19 for this module. Key observations:

| Aspect | Status in Odoo 19 |
|--------|------------------|
| YouTube URL parsing regex | Unchanged |
| `_compute_youtube_video_id` compute method | Unchanged |
| `is_youtube_chat_available` compute | Unchanged |
| `widescreen` logic | Unchanged |
| Mobile detection | Unchanged |
| Next track suggestion JSON-RPC | Unchanged |
| `Domain` from `odoo.fields` (vs legacy tuple domain) | Used in Odoo 19 (was already used in 18) |

The `Domain` import from `odoo.fields` for constructing search domains was already present in the Odoo 18 version of this module.

### Performance Considerations

| Area | Analysis |
|------|----------|
| **YouTube regex on every track browse** | `_compute_youtube_video_id` is a regular `@api.depends` compute (not stored). It re-runs every time a track recordset is accessed without a cached value. For list views with many tracks, this could be expensive. Recommendation: consider `store=True` if performance issues arise. |
| **Mobile User-Agent regex** | `re.match()` is executed on every track page load. This is a single regex match against a short string — negligible cost. |
| **Next suggestion query** | The `/event_track/get_track_suggestion` endpoint executes a `read_group` or `search` on `event.track` filtered by the same event. This is a targeted query with proper domain index usage — acceptable performance. |
| **Thumbnail URL** | `maxresdefault.jpg` is the highest-resolution YouTube thumbnail. YouTube CDN handles this; no server-side image processing occurs. |
| **Widescreen option** | The `options` dict is a simple Python dict — no database I/O. |

### Security Notes

| Aspect | Implementation |
|--------|----------------|
| **Public access** | The `/event_track/get_track_suggestion` endpoint uses `type='jsonrpc', auth='public', website=True` — unauthenticated users can call it |
| **Input sanitization** | No user input is written to the database in this module; all fields are controlled by event managers via form |
| **Sudo on track read** | `track_suggestion_sudo = track_suggestion.sudo()` is used to fetch suggestion details without access restrictions being applied to the track data |
| **XSS** | No user-supplied string is rendered raw in templates without Odoo's standard HTML sanitization |

---

## Related Models

| Model | Module | Relationship |
|-------|--------|--------------|
| `event.track` | `website_event_track` | Extended with YouTube fields |
| `event.event` | `event` | Accessed via `track.event_id` for next-track suggestion |
| `website.visitor` | `website_livechat` / `website` | Used for visitor-aware next-track suggestion |

## See Also

- [Modules/website_event_track](modules/website_event_track.md) — Base event track module (parent of this module)
- [Modules/website_event_track_quiz](modules/website_event_track_quiz.md) — Quiz module layered on top of event tracks
- [Modules/event](modules/event.md) — Event management core
- [Core/Fields](core/fields.md) — Char, Boolean, Computed field patterns
