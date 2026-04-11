---
Module: website_slides
Version: Odoo 18
Type: Business
Tags: #odoo18, #e-learning, #courses, #quiz, #gamification, #website
---

# website_slides — E-Learning / Course Platform

Extends the Odoo framework to deliver a full-featured e-learning platform: courses (channels), individual lessons (slides), quiz assessments, progress tracking, gamification via karma/badges, and optional e-commerce integration for selling courses.

**Module path:** `addons/website_slides/`
**Key mixins inherited:** `mail.thread`, `image.mixin`, `website.seo.metadata`, `website.published.mixin`, `website.searchable.mixin`, `rating.mixin`, `mail.activity.mixin`, `website.cover_properties.mixin`

---

## Domain Model

```
slide.channel ──────────────────────── 1 ──────── N  slide.channel.partner
     │                                                                   (enrollment)
     │ N slide.slide
     │
     ├─ is_category = True  (organizational grouping node)
     │
     └─ is_category = False (actual content)
            │
            ├── slide_category: article / video / document / infographic / quiz
            ├── N slide.question ── N slide.answer
            ├── N slide.slide.partner  (per-user completion record)
            ├── N slide.slide.resource (downloadable files/links)
            ├── N slide.embed         (external embed tracking)
            └── N slide.tag

slide.channel.tag ──── M ────── 1 slide.channel.tag.group
```

---

## Models

### 1. `slide.channel` — Course / Channel

**Inherits:** `rating.mixin`, `mail.activity.mixin`, `image.mixin`, `website.cover_properties.mixin`, `website.seo.metadata`, `website.published.multi.mixin`, `website.searchable.mixin`
**Table:** `slide_channel`
**Order:** `sequence, id`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Course name (translateable) |
| `active` | Boolean | Archive/unarchive toggle (tracks via `mail.thread`) |
| `description` | Html | Full description at top of course page |
| `description_short` | Html | Short description for course cards |
| `description_html` | Html | Detailed description section |
| `channel_type` | Selection | `training` (default) or `documentation` |
| `sequence` | Integer | Sort order |
| `user_id` | Many2one `res.users` | Responsible/owner |
| `color` | Integer | Kanban color decoration |
| `tag_ids` | Many2many `slide.channel.tag` | Categorization tags |
| `slide_ids` | One2many `slide.slide` | All slides and categories in the channel |
| `slide_content_ids` | One2many (computed) | Non-category slides only |
| `slide_category_ids` | One2many (computed) | Category nodes only |
| `slide_last_update` | Date | Last content update date |
| `slide_partner_ids` | One2many `slide.slide.partner` | Per-user slide data (officer group) |
| `promote_strategy` | Selection | `latest` / `most_voted` / `most_viewed` / `specific` / `none` |
| `promoted_slide_id` | Many2one `slide.slide` | Manually selected featured slide |
| `access_token` | Char | UUID for secure invite links |
| `nbr_document / _video / _infographic / _article / _quiz` | Integer | Count of published slides by type |
| `total_slides` | Integer | Total published non-category slides |
| `total_views` | Integer | Aggregate slide views |
| `total_votes` | Integer | Aggregate slide votes |
| `total_time` | Float | Total duration in hours |
| `rating_avg_stars` | Float | Average rating (stars) |
| `allow_comment` | Boolean | Allow attendees to rate/comment the course |
| `publish_template_id` | Many2one `mail.template` | Notification when new content is published (default: `slide_template_published`) |
| `share_channel_template_id` | Many2one `mail.template` | Email when channel is shared (default: `mail_template_channel_shared`) |
| `share_slide_template_id` | Many2one `mail.template` | Email when a slide is shared (default: `slide_template_shared`) |
| `completed_template_id` | Many2one `mail.template` | Email when attendee completes the course (default: `mail_template_channel_completed`) |
| `enroll` | Selection | `public` (Open) or `invite` (On Invitation) |
| `enroll_msg` | Html | Message explaining enrollment process |
| `enroll_group_ids` | Many2many `res.groups` | Auto-enroll members of these groups |
| `visibility` | Selection | `public` (Everyone) / `connected` (Signed In) / `members` (Course Attendees) |
| `upload_group_ids` | Many2many `res.groups` | Users allowed to publish content (for `documentation` channels) |
| `website_default_background_image_url` | Char (computed) | Static fallback image |
| `channel_partner_ids` | One2many `slide.channel.partner` | Active members (officer) |
| `channel_partner_all_ids` | One2many `slide.channel.partner` | All members including invited (officer) |
| `members_count` | Integer (computed) | Enrolled attendees (`joined` + `ongoing` + `completed`) |
| `members_all_count` | Integer (computed) | All attendees including invited |
| `members_engaged_count` | Integer (computed) | `joined` + `ongoing` status |
| `members_completed_count` | Integer (computed) | `completed` status |
| `members_invited_count` | Integer (computed) | `invited` status |
| `partner_ids` | Many2many `res.partner` (computed/search) | Enrolled partners |
| `completed` | Boolean (computed/user) | Current user has completed the course |
| `completion` | Integer (computed/user) | Current user's % completion |
| `can_upload` | Boolean (computed/user) | Current user can upload slides |
| `has_requested_access` | Boolean (computed/user) | Current user has requested access |
| `is_member` | Boolean (computed/search/user) | User is actively enrolled |
| `is_member_invited` | Boolean (computed/search/user) | User has a pending invitation |
| `partner_has_new_content` | Boolean (computed/user) | New content published in last 7 days not yet completed |
| `karma_gen_channel_rank` | Integer | Karma awarded for ranking the course (default: 5) |
| `karma_gen_channel_finish` | Integer | Karma awarded for completing course (default: 10) |
| `karma_review` | Integer | Karma required to add a review (default: 10) |
| `karma_slide_comment` | Integer | Karma required to comment on a slide (default: 3) |
| `karma_slide_vote` | Integer | Karma required to vote on a slide (default: 3) |
| `can_review / can_comment / can_vote` | Boolean (computed/user) | Per-user action rights |
| `prerequisite_channel_ids` | Many2many `slide.channel` | Courses that must be completed first |
| `prerequisite_of_channel_ids` | Many2many `slide.channel` | Reverse of prerequisite |
| `prerequisite_user_has_completed` | Boolean (computed/user) | User has completed all prerequisites |

#### SQL Constraints

```python
_check_enroll = CHECK(visibility != 'members' OR enroll = 'invite')
# Visibility "members" (Course Attendees) requires enroll = "On Invitation"
```

#### Key Methods

**Enrollment / Membership:**
- `_action_add_members(target_partners, member_status='joined')` — Core enrollment logic. `member_status='joined'` subscribes to channel chatter; `'invited'` sends an invite email with a signed hash link. Returns the `slide.channel.partner` records created or reactivated.
- `_filter_add_members(target_partners)` — Returns only channels where `enroll == 'public'` or user has write access.
- `_add_groups_members()` — Called on `enroll_group_ids` write; auto-enrolls all users in those groups.
- `_action_request_access(partner)` — Schedules a `mail.activity` on the responsible user.
- `_action_channel_open_invite_wizard(mail_template, enroll_mode=False)` — Opens the `slide.channel.invite` wizard.
- `_remove_membership(partner_ids)` — Archives `slide.channel.partner` records; karma earned is preserved (re-joining will not re-grant karma).
- `_recompute_completion()` — On `slide.channel.partner`: recalculates `completion` and `member_status` (joined/ongoing/completed) based on completed slides. Triggers `_post_completion_update_hook` (karma award/revoke) and `_send_completed_mail` when status transitions to `completed`.

**Content Management:**
- `_get_categorized_slides(base_domain, order, ...)` — Returns slides organized by category with uncategorized slides first. Used by both backend kanban and frontend renderer.
- `_move_category_slides(category, new_category)` — Moves all slides from one category to another.
- `_resequence_slides(slide, force_category=False)` — Resequences all slides after a drag-drop reorder.
- `_get_earned_karma(partner_ids)` — Computes total karma earned by partners from quiz rewards and course completion (read-group based, respects `quiz_attempts_count` for actual attempts).

**Publishing:**
- `_post_publication()` — On `slide.slide`: sends `publish_template_id` email to all channel members who have not completed that slide. Called after `is_published=True` on a slide.

**Invitations:**
- `_send_share_email(emails)` — Shares channel via email using `share_channel_template_id`.
- `action_request_access()` — Returns `{'done': True}` or `{'error': ...}` dict.

#### L4 Notes

- **Prerequisite channels:** Users must complete all `prerequisite_channel_ids` before they can enroll. The `prerequisite_user_has_completed` computed field aggregates the `slide.channel.partner` records with `member_status='completed'`.
- **Auto-enrollment via groups:** When a `res.users` is created or their `groups_id` is updated, `res.users.create()` / `res.users.write()` trigger `_action_add_members` for all channels matching the user's groups. This is implemented in `res_users.py` using the `__api.model_create_multi` decorator on user write.
- **Invitation hash:** `_get_invitation_hash()` uses `tools.hmac(self.env(su=True), 'website_slides-channel-invite', (partner_id, channel_id))` — a timed HMAC signature. The invite link (`/slides/<id>/invite?invite_partner_id=...&invite_hash=...`) is verified server-side on access.
- **Channel type `documentation` vs `training`:** In `documentation` mode, content is collaborative — members of `upload_group_ids` can publish directly without the responsible user's approval. In `training` mode, only the `user_id` responsible (or `group_website_slides_manager`) can publish.
- **Completion email:** `completed_template_id` is rendered per record via `_generate_template`. The email is created as `mail.mail` records (not sent immediately) and stored in the chatter of each `slide.channel.partner`.
- **Access token:** `access_token` is generated as a UUID per channel on first use. Used for invite link validation via `_generate_signed_token(partner_id)` + `_sign_token()`.

---

### 2. `slide.channel.partner` — Enrollment / Member Record

**Table:** `slide_channel_partner`
**Rec_name:** `partner_id`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Soft-delete (archive) support |
| `channel_id` | Many2one `slide.channel` | Course reference |
| `member_status` | Selection | `invited` / `joined` / `ongoing` / `completed` (readonly) |
| `completion` | Integer | % of published slides completed (0-100) |
| `completed_slides_count` | Integer | Absolute count of completed slides |
| `partner_id` | Many2one `res.partner` | Enrolled user |
| `partner_email` | Char (related) | Convenience |
| `channel_user_id` | Many2one `res.users` (related) | Channel responsible |
| `channel_type` | Selection (related) | Channel type |
| `channel_visibility` | Selection (related) | Channel visibility |
| `channel_enroll` | Selection (related) | Channel enroll policy |
| `channel_website_id` | Many2one `website` (related) | Channel website |
| `next_slide_id` | Many2one `slide.slide` (computed) | Next uncompleted published slide |
| `invitation_link` | Char (computed) | Full invitation URL with HMAC hash |
| `last_invitation_date` | Datetime | For GC of expired invites |

#### SQL Constraints

```python
channel_partner_uniq = UNIQUE(channel_id, partner_id)
check_completion = CHECK(completion >= 0 and completion <= 100)
```

#### Key Methods

- `_compute_next_slide_id()` — Raw SQL query (`DISTINCT ON (SCP.id)`) finds the first unpublished `slide.slide` where `slide_slide_partner.completed != TRUE` for this partner. Avoids ORM overhead for performance.
- `_recompute_completion()` — Core completion logic: counts `slide.slide.partner` records where `completed=True` and `slide_id.is_published=True`. Sets `member_status` to `completed` when `completed_slides_count >= total_slides`, `ongoing` when > 0, `joined` when 0. Triggers karma hooks.
- `_post_completion_update_hook(completed=True/False)` — Awards or revokes `channel.karma_gen_channel_finish` karma using `_add_karma_batch`.
- `_send_completed_mail()` — Batch-renders `completed_template_id` per template and creates `mail.mail` records.
- `unlink()` — Cascade-deletes related `slide.slide.partner` records via domain before calling super.
- `_gc_slide_channel_partner()` — `@api.autovacuum` cron: deletes `invited` members with `completion=0` and `last_invitation_date` older than 3 months.

#### L4 Notes

- **Status transitions:** `invited` never transitions via `_recompute_completion` — the member must actively enroll via the invite link (which calls `_action_add_members` with `member_status='joined'`). Archived records are reactivated and updated if the user re-enrolls.
- **Completion granularity:** Completion is based on published, non-category slides only. The denominator is `channel.total_slides` (which itself only counts published, non-category slides).
- **Karma preservation on removal:** `_remove_membership` only archives the record. The partner keeps their karma because re-joining won't re-trigger quiz completion karma (karma is only granted on the first completion of each slide).

---

### 3. `slide.slide` — Lesson / Content Item

**Inherits:** `mail.thread`, `image.mixin`, `website.seo.metadata`, `website.published.mixin`, `website.searchable.mixin`
**Table:** `slide_slide`
**Order:** `sequence asc, is_category asc, id asc`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Slide title (translateable) |
| `active` | Boolean | Archive toggle |
| `sequence` | Integer | Sort order within channel |
| `user_id` | Many2one `res.users` | Uploaded by |
| `description` | Html | Slide description |
| `channel_id` | Many2one `slide.channel` | Parent course |
| `tag_ids` | Many2many `slide.tag` | Tags across channels |
| `is_preview` | Boolean | Accessible without joining the channel |
| `is_new_slide` | Boolean (computed) | Published within last 7 days |
| `completion_time` | Float | Duration in hours (recursive compute for categories) |
| `is_category` | Boolean | True = organizational section header, not actual content |
| `category_id` | Many2one `slide.slide` (computed) | Parent category for this slide |
| `slide_ids` | One2many `slide.slide` | Child slides when `is_category=True` |
| `partner_ids` | Many2many `res.partner` | Subscribers (officer view) |
| `slide_partner_ids` | One2many `slide.slide.partner` | Per-user completion data |
| `user_membership_id` | Many2one `slide.slide.partner` (computed/user) | Current user's membership record |
| `user_vote` | Integer (computed/user) | Current user's vote: 1 / 0 / -1 |
| `user_has_completed` | Boolean (computed/user) | Current user has completed |
| `user_has_completed_category` | Boolean (computed/user) | All slides in category are completed |
| `question_ids` | One2many `slide.question` | Quiz questions |
| `questions_count` | Integer (computed) | Number of quiz questions |
| `quiz_first_attempt_reward` | Integer | Karma for first quiz attempt (default: 10) |
| `quiz_second_attempt_reward` | Integer | Karma for second attempt (default: 7) |
| `quiz_third_attempt_reward` | Integer | Karma for third attempt (default: 5) |
| `quiz_fourth_attempt_reward` | Integer | Karma for 4th+ attempts (default: 2) |
| `can_self_mark_completed` | Boolean (computed/user) | Can mark as completed without opening |
| `can_self_mark_uncompleted` | Boolean (computed/user) | Can mark as uncompleted |
| `slide_category` | Selection | `infographic` / `article` / `document` / `video` / `quiz` |
| `source_type` | Selection | `local_file` / `external` (Google Drive) |
| `url` | Char | External URL (video or Google Drive file) |
| `binary_content` | Binary | Uploaded file content (attachment=True) |
| `slide_resource_ids` | One2many `slide.slide.resource` | Additional downloadable files |
| `slide_resource_downloadable` | Boolean | Allow downloading slide content |
| `google_drive_id` | Char (computed) | Extracted Google Drive file ID |
| `html_content` | Html | Custom HTML for `article` category slides |
| `slide_icon_class` | Char (computed) | Font-awesome icon class per slide type |
| `slide_type` | Selection (computed/stored) | `image` / `article` / `quiz` / `pdf` / `sheet` / `doc` / `slides` / `youtube_video` / `google_drive_video` / `vimeo_video` |
| `video_source_type` | Selection (computed) | `youtube` / `google_drive` / `vimeo` |
| `youtube_id` | Char (computed) | Extracted YouTube video ID |
| `vimeo_id` | Char (computed) | Extracted Vimeo video ID |
| `embed_code` | Html (computed) | iFrame embed for website use |
| `embed_code_external` | Html (computed) | iFrame embed for external websites |
| `website_share_url` | Char (computed) | Share URL `.../slide/<id>/share` |
| `embed_ids` | One2many `slide.embed` | External embed tracking records |
| `embed_count` | Integer (computed) | Number of external sites embedding this slide |
| `slide_views` | Integer (stored/computed) | Count of registered (logged-in) views |
| `public_views` | Integer | Anonymous views (from embed) |
| `total_views` | Integer (computed/stored) | `slide_views + public_views` |
| `likes / dislikes` | Integer (computed/stored) | Vote tallies |
| `comments_count` | Integer (computed) | Chatter comments count |
| `date_published` | Datetime | When slide was first published |
| `nbr_document / _video / _infographic / _article / _quiz` | Integer (computed, category only) | Counts of published slides in this category |
| `total_slides` | Integer (computed, category only) | Total slides in this category |
| `is_published` | Boolean | Publication state (tracked) |
| `website_published` | Boolean | Alias via mixin (tracking=False) |

#### SQL Constraints

```python
exclusion_html_content_and_url = CHECK(
    html_content IS NULL OR url IS NULL
)
# Article slides use html_content; all others use url or binary_content
```

#### Key Methods

**Views / Completion tracking:**
- `action_set_viewed(quiz_attempts_inc=False)` — Validates membership, calls `_action_set_viewed()` which creates or updates `slide.slide.partner`. If `quiz_attempts_inc=True`, increments `quiz_attempts_count` via `sql.increment_fields_skiplock` (prevents race conditions).
- `action_mark_completed()` — Calls `_action_mark_completed()` which: (1) calls `_action_set_quiz_done()` to award karma for quiz slides, (2) sets `completed=True` on `slide.slide.partner`. Raises `UserError` if `can_self_mark_completed` is False (quiz slides cannot be self-marked).
- `action_mark_uncompleted()` — Resets quiz karma (negative reward), sets `completed=False`.
- `_action_set_quiz_done(completed=True)` — Awards karma based on `quiz_attempts_count`. Uses a lookup table `[first, second, third, fourth_reward]` and indexes by `min(attempts_count, 4) - 1`. Karma is added via `res.users._add_karma()`. Called on both completion and un-completion (with negative values).

**Voting:**
- `_action_vote(upvote=True/False)` — Creates or updates `slide.slide.partner.vote` as 1 / 0 / -1. Does not grant karma (voting karma is per-channel for ranking, not per-slide voting).

**Embed tracking:**
- `_embed_increment(url)` — Increments `slide.embed.count_views` for the given external URL. If no record exists for that URL, creates one. Used by the `/slides/embed_external/<id>` controller endpoint.

**Metadata fetching (external URLs):**
- `_fetch_external_metadata(image_url_only=False)` — Dispatches to `_fetch_youtube_metadata`, `_fetch_google_drive_metadata`, or `_fetch_vimeo_metadata` based on `slide_category` and `video_source_type`.
- `_fetch_youtube_metadata()` — Calls YouTube Data API v3 (`/videos` endpoint) using the website's `website_slide_google_app_key`. Extracts title, description, thumbnail (base64), and parses ISO 8601 duration (`PT1H2M3S` format) into hours.
- `_fetch_google_drive_metadata()` — Calls Google Drive API v2. Extracts title, thumbnail, and for PDFs downloads content to count pages (via `_get_completion_time_pdf`: 5 min/page). Determines `slide_type` from mimeType mapping.
- `_fetch_vimeo_metadata()` — Calls Vimeo oEmbed API (`/api/oembed.json`). Extracts title, description, duration (seconds), thumbnail.
- `_get_completion_time_pdf(data_bytes)` — Counts PDF pages via `PdfFileReader` and returns `5 * pages / 60` hours. Fails silently.

**Quiz:**
- `_compute_quiz_info(target_partner, quiz_done=False)` — Returns a dict per slide ID: `quiz_karma_max` (first-attempt reward), `quiz_karma_gain` (next attempt reward), `quiz_karma_won` (karma actually earned), `quiz_attempts_count`.

#### L4 Notes

- **Category slides:** When `is_category=True`, the slide is always `is_preview=True` and `is_published=True`. Categories aggregate `completion_time` from their child slides via `_compute_category_completion_time`.
- **Article slides:** The only slide type that uses `html_content` (not `url`). Setting `slide_category` to `article` clears `url`; setting to any other category clears `html_content`. This satisfies the SQL exclusion constraint.
- **Slide type vs slide category:** `slide_category` is the high-level classification (article, video, document, infographic, quiz). `slide_type` is a subtype (e.g., for `document`: pdf/sheet/doc/slides; for `video`: youtube_video/google_drive_video/vimeo_video). Both are stored for performance.
- **Preview vs membership:** `is_preview=True` allows public (non-member) access to the slide content. The channel itself may still require login (`visibility='connected'`) but the preview slide is always accessible if the channel is published.
- **External metadata on create/write:** `create()` and `write()` both call `_fetch_external_metadata()` when a URL field is set. Keys are only updated if they are not already in vals and if the current field value is falsy — this prevents overwriting user-set values.

---

### 4. `slide.slide.partner` — Per-User Slide Record

**Table:** `slide_slide_partner`
**Rec_name:** `partner_id`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `slide_id` | Many2one `slide.slide` | Slide reference |
| `slide_category` | Selection (related) | Slide category |
| `channel_id` | Many2one `slide.channel` (related/stored) | Channel reference |
| `partner_id` | Many2one `res.partner` | User reference |
| `vote` | Integer | Vote: 1 (like), 0 (none), -1 (dislike) |
| `completed` | Boolean | Slide completion status |
| `quiz_attempts_count` | Integer | Number of quiz attempts |

#### SQL Constraints

```python
slide_partner_uniq = UNIQUE(slide_id, partner_id)
check_vote = CHECK(vote IN (-1, 0, 1))
```

#### Key Methods

- `create()` — On create with `completed=True`, triggers `_recompute_completion()` on the channel partner.
- `write()` — If `completed` value changes, triggers `_recompute_completion()`.
- `_recompute_completion()` — Delegates to `slide.channel.partner._recompute_completion()` for the relevant `(channel_id, partner_id)` pairs.

---

### 5. `slide.tag` — Cross-Channel Slide Tags

**Table:** `slide_tag`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (translateable, unique) |

#### SQL Constraints

```python
slide_tag_unique = UNIQUE(name)
```

---

### 6. `slide.question` — Quiz Question

**Table:** `slide_question`
**Order:** `sequence`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Display order |
| `question` | Char | Question text (translateable) |
| `slide_id` | Many2one `slide.slide` | Parent slide (cascade delete) |
| `answer_ids` | One2many `slide.answer` | Answer options |
| `answers_validation_error` | Char (computed) | Error if missing correct/incorrect answers |
| `attempts_count` | Integer (computed, officer) | Total quiz attempts for this question |
| `attempts_avg` | Float (computed, officer) | Average attempts per unique user |
| `done_count` | Integer (computed, officer) | Number of users who completed the slide |

#### Constraints

```python
@api.constrains('answer_ids')
def _check_answers_integrity(self):
    # Raises ValidationError if any question lacks at least one
    # correct answer AND at least one incorrect answer
```

---

### 7. `slide.answer` — Quiz Answer Option

**Table:** `slide_answer`
**Order:** `question_id, sequence, id`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Display order |
| `question_id` | Many2one `slide.question` | Parent question |
| `text_value` | Char | Answer text (translateable) |
| `is_correct` | Boolean | Marks this as the correct answer |
| `comment` | Text | Feedback shown if user selects this answer |

---

### 8. `slide.channel.tag` — Channel Category Tags

**Table:** `slide_channel_tag`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (translateable) |
| `sequence` | Integer | Sort order |
| `group_id` | Many2one `slide.channel.tag.group` | Parent group |
| `group_sequence` | Integer (related/stored) | Group's sequence for sorting |
| `channel_ids` | Many2many `slide.channel` | Channels using this tag |
| `color` | Integer | Color for kanban display (1-11 random default) |

---

### 9. `slide.channel.tag.group` — Tag Groups

**Inherits:** `website.published.mixin`
**Table:** `slide_channel_tag_group`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Group name (translateable) |
| `sequence` | Integer | Sort order |
| `tag_ids` | One2many `slide.channel.tag` | Tags in this group |

---

### 10. `slide.slide.resource` — Additional Slide Resources

**Table:** `slide_slide_resource`

| Field | Type | Description |
|-------|------|-------------|
| `slide_id` | Many2one `slide.slide` | Parent slide |
| `resource_type` | Selection | `file` or `url` |
| `name` | Char (computed) | Auto-set from filename or URL |
| `data` | Binary | File content |
| `file_name` | Char | Original filename |
| `link` | Char | External URL |
| `download_url` | Char (computed) | `/web/content/slide.slide.resource/<id>/data?download=true` |
| `sequence` | Integer | Display order |

#### Constraints

```python
check_url = CHECK(resource_type != 'url' OR link IS NOT NULL)
check_file_type = CHECK(resource_type != 'file' OR link IS NULL)
```

---

### 11. `slide.embed` — External Embed Tracking

**Table:** `slide_embed`

| Field | Type | Description |
|-------|------|-------------|
| `slide_id` | Many2one `slide.slide` | Embedded slide |
| `url` | Char | Third-party website URL (False = direct) |
| `website_name` | Char (computed) | Domain or "Unknown Website" |
| `count_views` | Integer | Number of views from this site |

---

### 12. `gamification.challenge` (extension)

Adds `challenge_category = 'slides'` to the gamification challenge types, enabling badge/challenge-based gamification for course completion.

---

### 13. `gamification.karma.tracking` (extension)

Extends karma tracking to include `slide.slide` (Course Quiz) and `slide.channel` (Course Finished) as karma origin types, alongside the base gamification origins.

---

## Karma System

| Trigger | Karma |
|---------|-------|
| Complete a slide (non-quiz) | 0 (no automatic karma; just completion tracking) |
| Pass a quiz (first attempt) | `quiz_first_attempt_reward` (default 10) |
| Pass a quiz (second attempt) | `quiz_second_attempt_reward` (default 7) |
| Pass a quiz (third attempt) | `quiz_third_attempt_reward` (default 5) |
| Pass a quiz (fourth+ attempt) | `quiz_fourth_attempt_reward` (default 2) |
| Uncomplete a quiz | Negative of current reward (karma revoked) |
| Complete entire course | `karma_gen_channel_finish` (default 10) |
| Rank a course | `karma_gen_channel_rank` (default 5) |

Karma is stored in `res.users` and tracked in `gamification.karma.tracking` with origin types `slide.slide` and `slide.channel`.

---

## Quiz Scoring (L4)

1. A user opens a quiz slide. Backend calls `_compute_quiz_info(target_partner)` to return `quiz_karma_max`, `quiz_karma_gain`, `quiz_karma_won`, `quiz_attempts_count`.
2. User submits answers. Controller calls `action_set_viewed(quiz_attempts_inc=True)` which increments `quiz_attempts_count` using `sql.increment_fields_skiplock` (prevents race conditions on concurrent tab opens).
3. Backend evaluates answers: for each `slide.answer` with `is_correct=True`, the answer is correct. The quiz is passed if all questions have at least one correct answer and the user selected at least one correct per question (exact scoring model).
4. `action_mark_completed()` calls `_action_set_quiz_done(completed=True)` which reads `quiz_attempts_count` (already incremented in step 2) to determine which reward tier applies.
5. Karma is awarded via `res.users._add_karma(points, slide, 'Quiz Completed')` or revoked via negative points.
6. `_recompute_completion()` on `slide.channel.partner` is called, which may transition the member to `completed` and trigger course-completion karma.

**Note:** `can_self_mark_completed` is `False` for quiz slides — they must be completed through the quiz mechanism, not by direct "Mark Complete" button.

---

## E-Commerce Integration

Course monetization is handled by the `sale` module. Courses can be linked to `product.product` records. When a course is configured with a product:
- `slide.channel` may have a `enroll` policy of `public` with paid enrollment
- The actual product/payment flow is managed by `sale` + `website_sale` modules
- Enrollment is triggered by the sale order being confirmed (via `_action_add_members` called from sale order workflow)

---

## SEO (L4)

`slide.channel` and `slide.slide` both inherit `website.seo.metadata`:

- **Channel:** Meta title = channel name, meta description = `description_short`, og:image from cover properties.
- **Slide:** Meta title = slide name, meta description from `html2plaintext(description)`, og:image from `image_1024` field on the slide. Twitter card set to `summary`.

The `_default_website_meta()` method on `slide.slide` overrides the mixin to use slide-specific fields.

---

## File Locations

- Models: `addons/website_slides/models/`
  - `slide_channel.py` — `slide.channel`, `slide.channel.partner`, `slide.slide` entity logic
  - `slide_slide.py` — `slide.slide` model and `slide.slide.partner` relation
  - `slide_question.py` — `slide.question`, `slide.answer`
  - `slide_channel_tag.py` — `slide.channel.tag`, `slide.channel.tag.group`
  - `slide_slide_resource.py` — `slide.slide.resource`
  - `slide_embed.py` — `slide.embed`
  - `res_partner.py` — Partner extension for course counts
  - `res_users.py` — Auto-enrollment on user/group create
  - `gamification_challenge.py` — Gamification challenge extension
  - `gamification_karma_tracking.py` — Karma tracking extension
