# website_event_track_live_quiz

> Bridge module: surfaces the `website_event_track_quiz` quiz widget inside the live streaming player (`website_event_track_live`). Auto-installs when both dependencies are present.

**Module**: `website_event_track_live_quiz`
**Category**: Marketing/Events
**Depends**: `website_event_track_live`, `website_event_track_quiz`
**Auto-install**: `True`
**Version**: 1.0
**License**: LGPL-3
**Source**: `odoo/addons/website_event_track_live_quiz/`

---

## Overview

This is a pure extension module — it ships no models or security records of its own. It contributes two things:

1. A **controller method override** that injects `show_quiz` into track suggestion data passed to the live player JS.
2. A **QWeb template override** that suppresses the "Take the Quiz" button during active live streaming, while restoring it for replays and non-YouTube tracks.

---

## Architecture

```
website_event_track_live_quiz/
├── controllers/
│   ├── __init__.py
│   └── track_live_quiz.py    # EventTrackLiveQuizController
└── views/
    └── event_track_templates_page.xml  # QWeb template inherit
```

No `security/`, no `models/`, no `data/`. The module's entire purpose is to wire two existing systems together.

**Dependency note**: `auto_install=True` means if a server has both `website_event_track_live` and `website_event_track_quiz` installed (even as dependencies of other modules), this module is automatically installed. This ensures the live-quiz integration is always active when both features are available — no manual activation required.

---

## Controller

### `EventTrackLiveQuizController` (`controllers/track_live_quiz.py`)

Inherits: `EventTrackLiveController` from `website_event_track_live`

Inherited route: `/event_track/get_track_suggestion` (JSON) — returns a track suggestion for the "up next" player widget shown during live streaming or between videos.

#### `_prepare_track_suggestion_values` — Override

```python
def _prepare_track_suggestion_values(self, track, track_suggestion):
    res = super(EventTrackLiveQuizController, self)._prepare_track_suggestion_values(track, track_suggestion)
    res['current_track']['show_quiz'] = bool(track.quiz_id) and not track.is_quiz_completed
    return res
```

**Parent method** (`EventTrackLiveController._prepare_track_suggestion_values`): Builds the suggestion data dict including `id`, `name`, `youtube_video_id`, `is_track_live`, `is_youtube_replay`, and other track metadata.

**This override**: Adds `show_quiz` boolean to `res['current_track']`. The value is `True` only when:
- `track.quiz_id` exists (track has a quiz attached)
- `track.is_quiz_completed` is `False` (current visitor has not yet completed the quiz)

**Consumer**: The live player JS (`website_event_track_live` static JS) reads `show_quiz` and conditionally renders a "Show Quiz" button or widget overlay. The frontend code is in `static/src/interactions/` (JavaScript) and `static/src/xml/` (QWeb snippets for the quiz widget inside the player).

**Performance implication**: `_compute_quiz_data` (from `website_event_track_quiz`) is invoked on the `track` record when `track.is_quiz_completed` is accessed. This adds one `search_read` per suggested track to the suggestion query. The suggestion endpoint returns 1–3 tracks, so this is at most 3 additional DB queries per suggestion poll.

---

## QWeb Template Override

### `website_event_track_live_quiz.event_track_content`

Inherits: `website_event_track_quiz.event_track_content`

**Original condition** (from `website_event_track_quiz/views/event_track_templates_page.xml`):
```xml
t-if="track.quiz_id and not track.is_quiz_completed and not track.is_track_upcoming"
```

**Overridden condition**:
```xml
t-if="track.quiz_id and not track.is_quiz_completed
      and not track.is_track_upcoming
      and (not track.is_track_live
           or track.is_youtube_replay
           or not track.youtube_video_id)"
```

**Condition breakdown**:

| Clause | Meaning |
|---|---|
| `track.quiz_id` | Track has a quiz attached |
| `not track.is_quiz_completed` | Visitor has not completed the quiz |
| `not track.is_track_upcoming` | Track has started (no quiz before the session) |
| `not track.is_track_live` | Track is not currently live |
| OR `track.is_youtube_replay` | Track is a YouTube replay (not live) |
| OR `not track.youtube_video_id` | No YouTube video configured at all |

**The quiz button is hidden during live streaming** because:
- The live player takes the full viewport.
- The "Show Quiz" button handled by the JS (via `show_quiz` from the suggestion API) takes over the quiz presentation inside the player.
- Showing both the full-page player and the standard track page quiz container simultaneously would be redundant and confusing.

**The quiz button reappears on replay** because:
- The live player shows the replay video but does not take exclusive control.
- The standard track page quiz container is the appropriate UX for on-demand content.
- `is_youtube_replay = True` when the track's YouTube video is explicitly marked as replay (vs. live).

---

## Security

No ACLs defined — this module adds no models. The permission model is entirely inherited from `website_event_track_quiz` and `website_event_track_live`. Both parent modules use `auth="public"` on their JSON-RPC endpoints, so the combined module also allows public access to quiz submission and suggestion endpoints.

---

## Odoo 18 → 19 Changes

No structural changes detected. The module's two-extension design (controller + template) was stable across the version boundary.

---

## Interaction with `website_event_track_quiz`

The full quiz submission flow is handled by `website_event_track_quiz.controllers.event_track_quiz.WebsiteEventTrackQuiz.event_track_quiz_submit()`. This bridge module only controls *visibility* of the quiz in the live player context — it does not intercept or modify the submission logic.

The `show_quiz` flag in the suggestion API is consumed by the live player's JavaScript to decide whether to render a quiz button. When clicked, the user's action is handled by the standard quiz submission route in the parent module.

---

## Related Documentation

- [Modules/website_event_track_quiz](modules/website_event_track_quiz.md) — Full quiz model, leaderboard, submit/reset endpoints
- [Modules/website_event_track_live](modules/website_event_track_live.md) — Live streaming controller, YouTube integration, track suggestions
- [Modules/website_event_track](modules/website_event_track.md) — Base track model
- [Modules/website_profile](modules/website_profile.md) — Visitor identity and karma
