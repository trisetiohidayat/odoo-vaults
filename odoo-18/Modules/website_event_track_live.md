---
Module: website_event_track_live
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_track_live
---

## Overview

Adds YouTube live streaming integration to event tracks. Allows embedding YouTube videos into track pages, with automatic thumbnail extraction, replay detection, and chat availability logic based on track timing.

**Key Dependencies:** `website_event_track`

**Python Files:** 1 model file

---

## Models

### event_track.py — EventTrack

**Inheritance:** `event.track`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `youtube_video_url` | Char | Yes | YouTube video URL |
| `youtube_video_id` | Char | No | Extracted 11-char video ID from URL |
| `is_youtube_replay` | Boolean | Yes | Marks video as replay (disables live chat) |
| `is_youtube_chat_available` | Boolean | No | True if live stream + (is_track_soon OR is_track_live) |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_youtube_video_id()` | `@api.depends('youtube_video_url')` | Parses URL with regex `^.*(youtu.be\/\|v\/\|u\/\w\/\|embed\/\|live\/\|watch\?v=\|&v=)([^#&?]*).*` — extracts 11-char ID |
| `_compute_website_image_url()` | `@api.depends('youtube_video_id', ...)` | Extends parent to use `https://img.youtube.com/vi/{id}/maxresdefault.jpg` as thumbnail |
| `_compute_is_youtube_chat_available()` | `@api.depends('youtube_video_url', 'is_youtube_replay', ...)` | True when: has video URL AND not replay AND (soon OR live) |

---

## Security / Data

No dedicated security XML or data files.

---

## Critical Notes

- YouTube video ID regex handles: `youtu.be/ID`, `v/ID`, `u/\w/ID`, `embed/ID`, `live/ID`, `watch?v=ID&...`, `&v=ID`
- YouTube thumbnails are used as the track image when no custom `website_image` is set
- `is_youtube_chat_available` is False for replays — YouTube embed hides live chat in replay mode
- `is_youtube_replay` is a manual flag set by the event organizer to indicate the video is a recording
- v17→v18: No major changes to this module's structure
