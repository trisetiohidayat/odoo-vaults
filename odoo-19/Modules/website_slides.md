---
type: module
module: website_slides
tags: [odoo, odoo19, website, elearning, slides, courses, learning, gamification, certification]
created: 2026-04-11
l4: true
---

# website_slides — eLearning Module (L4 Depth)

## Overview

| Property | Value |
|----------|-------|
| **Name** | eLearning |
| **Technical Name** | `website_slides` |
| **Category** | Website/eLearning |
| **Version** | 2.7 (manifest) / 19.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Application** | Yes |

## Description

The `website_slides` module provides a full-featured eLearning platform integrated with the Odoo website. It enables organizations to publish courses with various content types (videos, documents, infographics, quizzes, articles), track learner progress, award karma, issue certificates (via `website_slides_survey`), and foster community engagement through discussions and ratings. The module bridges educational content management with a public-facing course catalog and learner portal.

## Dependencies

| Module | Type | Purpose |
|--------|------|---------|
| `portal_rating` | Hard | Public ratings and reviews |
| `website` | Hard | Website framework, routing |
| `website_mail` | Hard | Email notification templates |
| `website_profile` | Hard | User profile integration |
| `gamification` | Optional | Challenges and badges (installed at runtime) |

### Optional Addon Dependencies

These are declared in `res.config.settings` as installable modules:

| Module | Config Field | Purpose |
|--------|-------------|---------|
| `website_slides_survey` | `module_website_slides_survey` | Certification/survey exams |
| `website_slides_forum` | `module_website_slides_forum` | Discussion forums per course |
| `website_sale_slides` | `module_website_sale_slides` | Paid courses via eCommerce |
| `mass_mailing_slides` | `module_mass_mailing_slides` | Email campaigns to enrolled members |

---

## Module Architecture

### Model Dependency Graph

```
slide.channel (course container)
  ├── slide.slide (lessons/sections)
  │     ├── slide.slide.partner (per-user slide progress)
  │     ├── slide.slide.resource (downloadable files)
  │     ├── slide.question → slide.answer (quiz)
  │     ├── slide.embed (external embed tracking)
  │     └── slide.tag (cross-course tags)
  ├── slide.channel.partner (enrollment)
  │     └── slide.slide.partner (via channel_id/partner_id)
  ├── slide.channel.tag + slide.channel.tag.group (course categorization)
  ├── slide.channel (prerequisites — self-referential m2m)
  ├── res.partner (course counts on partner form)
  ├── res.users (auto-enroll via groups)
  └── mail.activity (access request activities)
```

### Import Order Note

The `models/__init__.py` imports `slide_slide_partner` and `slide_channel_partner` **before** `slide_slide` and `slide_channel` because they participate in decorated Many2many relationships. Changing this order causes SQL foreign-key constraint failures.

---

## Models

### slide.channel — Course

**File:** `models/slide_channel.py`
**Inherits:** `rating.mixin`, `mail.activity.mixin`, `image.mixin`, `website.cover_properties.mixin`, `website.seo.metadata`, `website.published.multi.mixin`, `website.searchable.mixin`

#### Fields

**Identity & Content**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Course name, translateable |
| `description` | Html | — | Top-of-page description, sanitize_attributes=False |
| `description_short` | Html | — | Card/listing description |
| `description_html` | Html | — | Detailed description tab, uses `tools.html_translate` |
| `channel_type` | Selection | `'training'` | `'training'` or `'documentation'` |
| `color` | Integer | `0` | Kanban decoration color |
| `sequence` | Integer | `10` | Display order |
| `user_id` | Many2one `res.users` | `self.env.uid` | Responsible/instructor |
| `active` | Boolean | `True` | Archive flag, tracking=100 |
| `access_token` | Char | `uuid.uuid4()` | Per-record HMAC security token for invitation links |

**Cover & Media**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image_1920` | Binary | — | Course thumbnail (image.mixin) |
| `cover_properties` | Json | Purple gradient, opacity=0 | Overrides mixin default to set consistent slides header look |

`_default_cover_properties()` sets: `background_color_class: "o_cc4"`, linear gradient `#875A7B → #78516F`, `opacity: '0'`, `resize_class: 'cover_auto'`.

**Slides Structure**

| Field | Type | Compute | Description |
|-------|------|---------|-------------|
| `slide_ids` | One2many `slide.slide` | — | All slides and categories (inverse of `channel_id`) |
| `slide_content_ids` | One2many `slide.slide` | `_compute_category_and_slide_ids` | Content slides only (`is_category = False`) |
| `slide_category_ids` | One2many `slide.slide` | `_compute_category_and_slide_ids` | Category/section slides (`is_category = True`) |
| `promote_strategy` | Selection | `'latest'` | `'latest'`, `'most_voted'`, `'most_viewed'`, `'specific'`, `'none'` |
| `promoted_slide_id` | Many2one `slide.slide` | — | Manually selected featured slide |
| `slide_last_update` | Date | `_compute_slide_last_update` | When any slide was last modified |

**Content Statistics (all `store=True`, computed from `slide.slide`)**

| Field | Type | Description |
|-------|------|-------------|
| `nbr_document` | Integer | Published document slides count |
| `nbr_video` | Integer | Published video slides count |
| `nbr_infographic` | Integer | Published infographic/image slides count |
| `nbr_article` | Integer | Published article slides count |
| `nbr_quiz` | Integer | Published quiz slides count |
| `total_slides` | Integer | Total published content slides |
| `total_views` | Integer | Sum of all slide views |
| `total_votes` | Integer | Sum of likes minus dislikes |
| `total_time` | Float | Sum of completion times (hours) |
| `rating_avg_stars` | Float | Alias of `rating_avg` (stars display) |

**Visibility & Access**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `visibility` | Selection | `'public'` | `'public'`, `'connected'`, `'members'`, `'link'` |
| `enroll` | Selection | `'public'` | `'public'`, `'invite'`; auto-set to `'invite'` when `visibility='members'` |
| `enroll_msg` | Html | `'Contact Responsible'` | Custom enrollment message |
| `enroll_group_ids` | Many2many `res.groups` | — | Auto-enroll members of these groups |
| `upload_group_ids` | Many2many `res.groups` | — | Groups allowed to upload to documentation channels |
| `website_default_background_image_url` | Char | computed | `website_slides/static/src/img/channel-{channel_type}-default.jpg` |

Constraint: `CHECK(visibility != 'members' OR enroll = 'invite')` — visibility `'members'` forces enroll to `'invite'`. The computed `_compute_enroll` enforces this automatically.

**Prerequisites**

| Field | Type | Description |
|-------|------|-------------|
| `prerequisite_channel_ids` | Many2many `slide.channel` | Self-referential m2m via `slide_channel_prerequisite_slide_channel_rel` table |
| `prerequisite_of_channel_ids` | Many2many `slide.channel` | Inverse of prerequisites (courses that require this one) |
| `prerequisite_user_has_completed` | Boolean | `True` if current user has completed all prerequisites |

Domain on `prerequisite_channel_ids`: `[('id', '!=', id), ('visibility', '=', visibility), ('website_published', '=', website_published)]` — only prerequisites of same visibility/publish state.

**Membership — Enrollment**

| Field | Type | Description |
|-------|------|-------------|
| `channel_partner_ids` | One2many `slide.channel.partner` | Active enrolled members only (domain: `member_status != 'invited'`) |
| `channel_partner_all_ids` | One2many `slide.channel.partner` | All members including invited |
| `members_count` | Integer | `joined` + `completed` count |
| `members_all_count` | Integer | All statuses including invited |
| `members_engaged_count` | Integer | `joined` + `ongoing` count |
| `members_completed_count` | Integer | `completed` count |
| `members_invited_count` | Integer | `invited` count |
| `partner_ids` | Many2many `res.partner` | Compute+search hybrid — excludes `active=False` and `member_status='invited'` |

**Per-User Access Fields (computed, `compute_sudo=False`)**

| Field | Type | Description |
|-------|------|-------------|
| `completed` | Boolean | Current user has completed this course |
| `completion` | Integer | Current user's completion % (0–100) |
| `is_member` | Boolean | Actively enrolled (joined/ongoing/completed) |
| `is_member_invited` | Boolean | Invitation pending |
| `is_visible` | Boolean | Course visible to current user based on visibility setting |
| `can_upload` | Boolean | Current user can upload slides |
| `can_review` | Boolean | Current user can post a rating review (karma threshold) |
| `can_comment` | Boolean | Current user can comment on slides (karma threshold) |
| `can_vote` | Boolean | Current user can vote on slides (karma threshold) |
| `has_requested_access` | Boolean | Current user has pending access request activity |
| `partner_has_new_content` | Boolean | New slides published in last 7 days not yet completed |

**Karma System**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `karma_gen_channel_rank` | Integer | `5` | Karma awarded when user ranks the course |
| `karma_gen_channel_finish` | Integer | `10` | Karma awarded when user completes the course |
| `karma_review` | Integer | `10` | Minimum karma to post a review |
| `karma_slide_comment` | Integer | `3` | Minimum karma to comment on a slide |
| `karma_slide_vote` | Integer | `3` | Minimum karma to vote on a slide |

**Email Templates**

| Field | Type | Description |
|-------|------|-------------|
| `publish_template_id` | Many2one `mail.template` | Sent to members when new slide published (model: `slide.slide`) |
| `share_channel_template_id` | Many2one `mail.template` | Used when sharing the channel via email |
| `share_slide_template_id` | Many2one `mail.template` | Used when sharing a slide via email |
| `completed_template_id` | Many2one `mail.template` | Sent to member on course completion (model: `slide.channel.partner`) |
| `allow_comment` | Boolean | Allow likes/comments/reviews (computed from channel_type; `False` for documentation) |

#### Key Methods

**Enrollment (`_action_add_members`)**

```python
def _action_add_members(self, target_partners, member_status='joined', raise_on_access=False):
```

Logic by `member_status`:
- `'joined'`: Creates or re-activates membership as enrolled. Subscribes partners to channel chatter (subtype: `mt_channel_slide_published`). Calls `_recompute_completion()`.
- `'invited'`: Creates membership as invited. Does NOT subscribe to chatter. Does NOT trigger completion recompute. Partner must enroll themselves later.

Re-enrollment of archived partners: `action_unarchive()` is called, `member_status` is updated, and `_recompute_completion()` runs if enrolling as `'joined'`.

```python
def _filter_add_members(self, raise_on_access=False):
```
Returns only channels where `enroll == 'public'`. Controlled channels (`enroll == 'invite'`) require access through `_filtered_access('write')`. Throws `AccessError` if `raise_on_access=True` and user lacks rights.

```python
def _add_groups_members(self):
```
Mapped from `enroll_group_ids.all_user_ids.partner_id` and passed to `_action_add_members`. Triggered on channel create/write when `enroll_group_ids` changes.

```python
def _remove_membership(self, partner_ids):
```
Archives (not deletes) the `slide.channel.partner` record. Karma earned is preserved — reason: re-joining will not re-award karma because progress (`slide.slide.partner`) is deleted by `unlink()` cascade.

**Completion Tracking**

```python
def _recompute_completion(self):
```
Defined on `slide.channel.partner`, not `slide.channel`. Called when slides are completed. Uses `_read_group` on `slide.slide.partner` to count completed published slides per `(channel_id, partner_id)` pair. Status transitions: `0% → 'joined'`, `1-99% → 'ongoing'`, `100% → 'completed'`. Completion = `round(100 * completed_slides_count / total_slides)`. At 100%: calls `_post_completion_update_hook(completed=True)` and `_send_completed_mail()`. At back-from-100%: calls `_post_completion_update_hook(completed=False)`.

**Prerequisite Check**

```python
def _compute_prerequisite_user_has_completed(self):
```
Searches `slide.channel.partner` for current partner + `member_status='completed'` across all prerequisite channels. Returns `True` only if **all** prerequisites are completed.

**Channel Website URL**

```python
def _compute_website_url(self):
```
Sets `website_url = "/slides/{slug(channel)}"`. Depends on `name`.

**Business Actions**

| Method | Returns | Description |
|--------|---------|-------------|
| `action_redirect_to_members(status_filter)` | `ir.actions.act_window` | Opens attendee list filtered by status |
| `action_channel_enroll()` | Wizard action | Opens `slide.channel.invite` wizard in enroll mode |
| `action_channel_invite()` | Wizard action | Opens `slide.channel.invite` wizard in invite mode |
| `action_request_access()` | Dict | Creates `mail.activity` todo for channel responsible |
| `action_grant_access(partner_id)` | — | Adds partner, completes activity |
| `action_refuse_access(partner_id)` | — | Completes activity as refused |
| `action_view_slides()` | `ir.actions.act_window` | Opens slide list for this channel |
| `action_view_ratings()` | `ir.actions.act_window` | Opens rating list for this channel |
| `action_archive()` / `action_unarchive()` | — | Also archives/unarchives all slides; order matters to avoid incorrect completion recalc |
| `copy_data()` | — | Adds ` (copy)` suffix; resets `enroll` to `'invite'` if visibility was `'members'` |

**Mail Thread**

```python
def message_post(self, **kwargs):
```
Special behavior:
1. `comment` message_type without enough karma raises `AccessError`.
2. Replies to `mt_channel_slide_published` email are converted to `mt_note` to avoid spamming followers.
3. Exactly one review (rating) per course per author enforced via `search_count`.
4. Ranking (rating_value) awards `karma_gen_channel_rank` karma via `user._add_karma()`.

**Content Navigation**

```python
def _get_categorized_slides(self, base_domain, order, force_void=True, limit=False, offset=False):
```
Returns a list of dicts: `{'category': slide.recordset, 'name': str, 'slug_name': str, 'total_slides': int, 'slides': slide.recordset}`. Uncategorized slides are inserted at index 0. Categories are traversed in sequence order.

```python
def _move_category_slides(self, category, new_category):
```
Moves all slides from one category to another, respecting sequence positions.

```python
def _resequence_slides(self, slide, force_category=False):
```
Used after drag-and-drop reordering. Handles wrapping slides across category boundaries.

**Karma Computation**

```python
def _get_earned_karma(self, partner_ids):
```
Returns a `defaultdict(list)` of `{partner_id: [{'karma': int, 'channel_id': record}, ...]}`. Used for historical karma reporting. Recomputes from actual completions, not stored totals. Only counts quiz slides with attempts > 0. Quiz karma: indexed by attempt count (1st→`quiz_first_attempt_reward`, 2nd→`quiz_second_attempt_reward`, 3rd→`quiz_third_attempt_reward`, 4th+→`quiz_fourth_attempt_reward`).

**Website Search**

```python
@api.model
def _search_get_detail(self, website, order, options):
```
Integrates with `website` global search. Supports: tag filtering (OR inside group, AND between groups), slide category filtering (`nbr_{category} > 0`), `"my"` filter (member courses only). Icon: `fa-graduation-cap`.

**ORM Overrides**

```python
def unlink(self):
```
**Critical**: Explicitly calls `self.slide_ids.unlink()` **before** `super().unlink()`. This is a workaround for an ORM bug where SQL cascade deletion of slides triggers `_compute_slides_statistics` which tries to flush `category_id` on already-deleted slides, causing a "Could not find all values of slide.slide.category_id to flush" error.

```python
def write(self, vals):
```
- If `description_short` was implicitly linked to `description` (equal values), syncs them.
- If `user_id` changes: adds new user as member, reschedules activities.
- If `enroll_group_ids` changes: calls `_add_groups_members()`.

---

### slide.slide — Lesson / Content

**File:** `models/slide_slide.py`
**Inherits:** `mail.thread`, `image.mixin`, `website.seo.metadata`, `website.published.mixin`, `website.searchable.mixin`
**Table:** `slide_slide`
**Order:** `sequence asc, is_category asc, id asc`
**_mail_post_access:** `'read'` — commenting requires `read` access, not `write`

#### Slide Category Values (Content Types)

| Value | Label | Notes |
|-------|-------|-------|
| `infographic` | Image | Related: `image_binary_content`, `image_google_url` |
| `article` | Article | Stores content in `html_content` |
| `document` | Document | PDF or Google Drive file |
| `video` | Video | YouTube, Google Drive, or Vimeo |
| `quiz` | Quiz | Has `question_ids`; cannot be self-marked complete |

**Note:** Unlike earlier versions, `slide_category` here does **not** include `'category'` — category/section slides are identified by `is_category=True` boolean field.

#### Slide Type (Sub-type, `store=True`)

Derived from `slide_category` + source type:

| `slide_type` | Derivation |
|-------------|-----------|
| `image` | `slide_category='infographic'` |
| `article` | `slide_category='article'` |
| `quiz` | `slide_category='quiz'` |
| `pdf` | `slide_category='document'` + `source_type='local_file'` |
| `sheet` | GDrive mimeType matching Excel/spreadsheet |
| `doc` | GDrive mimeType matching Word/document |
| `slides` | GDrive mimeType matching PowerPoint/presentation |
| `youtube_video` | `slide_category='video'` + `video_source_type='youtube'` |
| `google_drive_video` | `slide_category='video'` + `video_source_type='google_drive'` |
| `vimeo_video` | `slide_category='video'` + `video_source_type='vimeo'` |

#### Fields

**Identity & Content**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Slide title, translateable |
| `description` | Html | — | Slide description, `sanitize_attributes=False`, `sanitize_overridable=True` |
| `active` | Boolean | `True` | Archive flag, tracking=100 |
| `sequence` | Integer | `0` | Order within channel |
| `user_id` | Many2one `res.users` | `self.env.uid` | Uploader/author |

**Classification**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `channel_id` | Many2one `slide.channel` | required | Parent course, `ondelete='cascade'` |
| `category_id` | Many2one `slide.slide` | computed | Parent section/category slide (indexed `btree_not_null`) |
| `slide_ids` | One2many `slide.slide` | — | Slides under this category (inverse of `category_id`) |
| `is_category` | Boolean | `False` | If `True`, this is a section header, not content |
| `tag_ids` | Many2many `slide.tag` | — | Cross-course tags |
| `is_preview` | Boolean | `False` | Available without enrollment |
| `is_new_slide` | Boolean | computed | Published within last 7 days |

`is_preview` is the **only mechanism** for non-members to access content. Setting `is_preview=True` on a published slide exposes it in the channel preview regardless of enrollment.

`_compute_category_id`: Iterates all channel slides sorted by sequence, tracking the current category. A slide belongs to a category if it appears after that category's sequence and before the next category's sequence.

**Quiz System**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `question_ids` | One2many `slide.question` | — | Quiz questions on this slide |
| `questions_count` | Integer | computed | Number of questions |
| `quiz_first_attempt_reward` | Integer | `10` | Karma for passing quiz on 1st attempt |
| `quiz_second_attempt_reward` | Integer | `7` | Karma for passing on 2nd attempt |
| `quiz_third_attempt_reward` | Integer | `5` | Karma for passing on 3rd attempt |
| `quiz_fourth_attempt_reward` | Integer | `2` | Karma for passing on 4th+ attempt |

**Content Media**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `slide_category` | Selection | `'document'` | Primary content type |
| `source_type` | Selection | `'local_file'` | `'local_file'` or `'external'` (Google Drive) |
| `url` | Char | — | Generic external URL (GDrive or YouTube) |
| `binary_content` | Binary | — | Uploaded file content, `attachment=True` |
| `html_content` | Html | — | Article content; `sanitize_attributes=False`, `sanitize_form=False` |
| `completion_time` | Float | computed | Estimated duration in hours (`digits=(10,4)`); recursive compute for categories |
| `slide_icon_class` | Char | computed | FontAwesome icon class per slide type |

**Document Sub-fields**

| Field | Type | Description |
|-------|------|-------------|
| `document_google_url` | Char | Google Drive URL for documents (related to `url`) |
| `document_binary_content` | Binary | Uploaded PDF file |

**Image Sub-fields**

| Field | Type | Description |
|-------|------|-------------|
| `image_binary_content` | Binary | Uploaded image file (filters to images only) |
| `image_google_url` | Char | Google Drive URL for images |

**Video Sub-fields**

| Field | Type | Description |
|-------|------|-------------|
| `video_url` | Char | Full video URL (related to `url`) |
| `video_source_type` | Selection | Computed: `'youtube'`, `'google_drive'`, `'vimeo'` |
| `youtube_id` | Char | Computed YouTube video ID (11 chars) |
| `vimeo_id` | Char | Computed Vimeo ID (may include token `id/token`) |
| `google_drive_id` | Char | Computed Google Drive file ID |

**Completion & Progress**

| Field | Type | Compute | Description |
|-------|------|---------|-------------|
| `can_self_mark_completed` | Boolean | `_compute_mark_complete_actions` | User can click "Mark Complete" |
| `can_self_mark_uncompleted` | Boolean | `_compute_mark_complete_actions` | User can click "Mark Uncomplete" |
| `user_has_completed` | Boolean | `_compute_user_membership_id` | Current user has completed this slide |
| `user_has_completed_category` | Boolean | `_compute_category_completed` | All slides in category are completed |
| `user_vote` | Integer | `_compute_user_membership_id` | Current user's vote: -1, 0, or 1 |
| `user_membership_id` | Many2one `slide.slide.partner` | `_compute_user_membership_id` | Current user's slide.partner record |

`can_self_mark_completed` is `True` only when: `website_published` AND `is_member` AND `slide_category != 'quiz'` AND no `question_ids`. Quiz slides must be completed by submitting correct answers, not by manual click.

**Resources**

| Field | Type | Description |
|-------|------|-------------|
| `slide_resource_ids` | One2many `slide.slide.resource` | Downloadable files/links |
| `slide_resource_downloadable` | Boolean | Allow batch download of all resources |

**Statistics (store=True)**

| Field | Type | Compute | Description |
|-------|------|---------|-------------|
| `likes` | Integer | `_compute_like_info` | Count of `vote = 1` |
| `dislikes` | Integer | `_compute_like_info` | Count of `vote = -1` |
| `slide_views` | Integer | `_compute_slide_views` | Member views (from `slide.slide.partner`) |
| `public_views` | Integer | — | Non-member views (session-tracked), default=0, readonly |
| `total_views` | Integer | `_compute_total` | `slide_views + public_views` |
| `embed_count` | Integer | `_compute_embed_counts` | Number of external websites embedding this slide |
| `comments_count` | Integer | `_compute_comments_count` | Chatter message count |
| `nbr_document/video/infographic/article/quiz` | Integer | `_compute_slides_statistics` | Per-category count for category slides |
| `total_slides` | Integer | `_compute_slides_statistics` | Total content slides under this category |

**Embed & Share**

| Field | Type | Compute | Description |
|-------|------|---------|-------------|
| `embed_code` | Html | `_compute_embed_code` | iframe embed code for the Odoo site |
| `embed_code_external` | Html | `_compute_embed_code` | iframe embed code for external websites |
| `embed_ids` | One2many `slide.embed` | — | External embed tracking records |
| `website_share_url` | Char | `_compute_website_share_url` | `/slides/slide/{id}/share` |
| `date_published` | Datetime | — | When slide was first published |

**Relationship Fields**

| Field | Type | Description |
|-------|------|-------------|
| `partner_ids` | Many2many `res.partner` | Via `slide_slide_partner` table; officer-only |
| `slide_partner_ids` | One2many `slide.slide.partner` | Per-user progress records; officer-only |
| `channel_type` | Selection | Related `channel_id.channel_type` |
| `channel_allow_comment` | Boolean | Related `channel_id.allow_comment` |
| `website_id` | Many2one `website` | Related `channel_id.website_id` |

**SQL Constraints**

```python
CHECK(html_content IS NULL OR url IS NULL)
"A slide is either filled with a url or HTML content. Not both."
```

This constraint enforces mutual exclusion between article slides (which use `html_content`) and slides with external URLs. When `slide_category` changes to `'article'`, the write override sets `url = False`. When changed away from `'article'`, it sets `html_content = False`.

#### Key Methods

**Video URL Parsing**

```python
YOUTUBE_VIDEO_ID_REGEX = r'^(?:(?:https?:)?//)?(?:www\.|m\.)?(?:youtu\.be/|youtube(-nocookie)?\.com/(?:embed/|v/|shorts/|live/|watch\?v=|watch\?.+&v=))((?:\w|-){11})\S*$'
GOOGLE_DRIVE_DOCUMENT_ID_REGEX = r'(^https:\/\/docs.google.com|^https:\/\/drive.google.com).*\/d\/([^\/]*)'
VIMEO_VIDEO_ID_REGEX = r'\/\/(player.)?vimeo.com\/(?:[a-z]*\/)*([0-9]{6,11})\/?([0-9a-z]{6,11})?[?]?.*'
```

Order of detection: YouTube first (regex check), then Google Drive (regex check), then Vimeo (regex search). Only one source is set per video.

`_compute_embed_code`:
- YouTube: `www.youtube-nocookie.com/embed/{youtube_id}?theme=light&...` (uses nocookie for privacy compliance)
- Vimeo (with token): `player.vimeo.com/video/{id}?h={token}&badge=0&autopause=0`
- Vimeo (without token): `player.vimeo.com/video/{vimeo_id}?badge=0&autopause=0`
- Google Drive: `drive.google.com/file/d/{google_drive_id}/preview`
- Local PDF: `/slides/embed/{id}?page=1` → served via PDF viewer controller
- External PDF: Google Drive embed

**External Metadata Fetching**

```python
def _fetch_external_metadata(self, image_url_only=False):
```
Dispatches to `_fetch_youtube_metadata`, `_fetch_google_drive_metadata`, or `_fetch_vimeo_metadata` based on `slide_category` and `video_source_type`. Called on create/write when a URL is set and `install_mode` context is not set.

```python
def _fetch_youtube_metadata(self, image_url_only=False):
```
- Calls `GET https://www.googleapis.com/youtube/v3/videos` with `key` from `website_id.website_slide_google_app_key`.
- Extracts: `name` (title), `description` (snippet), `image_1920` (thumbnail), `completion_time` (from `contentDetails.duration` ISO 8601 → hours).
- Graceful failure: returns `{}` with error message on 404 or network failure.

```python
def _fetch_google_drive_metadata(self, image_url_only=False):
```
- Uses `BASIC` projection. Attempts OAuth token from `google.drive.config` first, falls back to `website_slide_google_app_key`.
- Returns: `name`, thumbnail (from `thumbnailLink` with `=s220` stripped), `completion_time` (PDF page count/12 hours; video duration from `videoMediaMetadata`).
- Detects mimeType to set slide_type: `application/pdf` → `pdf`, Excel-family → `sheet`, Word-family → `doc`, PowerPoint-family → `slides`, image/* → `image`, video/* → `google_drive_video`.

```python
def _fetch_vimeo_metadata(self, image_url_only=False):
```
- Calls `GET https://vimeo.com/api/oembed.json?url=...` (oEmbed endpoint, no API key required).
- Returns: `name`, `description`, thumbnail, `completion_time` (duration in seconds converted to hours).

**PDF Completion Time**

```python
def _get_completion_time_pdf(self, data_bytes):
```
Assumes 5 minutes per page: `(5 * num_pages) / 60` hours. Detects `b'%PDF-'` magic bytes. Fails silently, returns `False` on any exception (corrupt PDF, etc.).

**Slide Completion Actions**

```python
def action_mark_completed(self):
```
Checks `can_self_mark_completed` before delegating to `_action_mark_completed()`. Raises `UserError` if not a member.

```python
def _action_mark_completed(self):
```
1. Calls `_action_set_quiz_done()` on all uncompleted slides (resets quiz karma if applicable).
2. Writes `completed=True` on existing `slide.slide.partner` records.
3. Creates new `slide.slide.partner` records with `completed=True` for slides without existing records.
4. The `slide.slide.partner` write override triggers `_recompute_completion()` on the channel.

```python
def action_mark_uncompleted(self):
```
1. Checks `can_self_mark_uncompleted`.
2. Calls `_action_set_quiz_done(completed=False)` to reverse karma.
3. Sets `completed=False` on matching `slide.slide.partner`.

```python
def _action_set_quiz_done(self, completed=True):
```
Awards or reverses karma for quiz completion. Karma amount depends on `quiz_attempts_count` at the time of completion:
- 1st attempt successful: `quiz_first_attempt_reward`
- 2nd: `quiz_second_attempt_reward`
- 3rd: `quiz_third_attempt_reward`
- 4th+: `quiz_fourth_attempt_reward`

Called from both `_action_mark_completed()` (when manually marking a non-quiz slide) and from quiz submission logic. Does nothing if user is not a member, slide is unpublished, has no questions, has no attempts, or state already matches.

**Voting**

```python
def _action_vote(self, upvote=True):
```
- Existing `slide.slide.partner` record: toggles vote between 1/0 (like) or -1/0 (dislike). Does NOT allow changing from like to dislike directly (must toggle through 0).
- New slide: creates `slide.slide.partner` with `vote=1` or `vote=-1`.

```python
def action_like(self) / action_dislike(self):
```
Calls `check_access('read')` first, then delegates to `_action_vote()`.

**View Tracking**

```python
def _action_set_viewed(self, target_partner, quiz_attempts_inc=False):
```
- If `quiz_attempts_inc=True`: increments `quiz_attempts_count` using `increment_fields_skiplock` (prevents deadlocks, non-blocking).
- Creates `slide.slide.partner` records for newly viewed slides.
- `sql.increment_fields_skiplock` on `public_views` in the session-based (non-member) path uses raw SQL to avoid write conflicts.

```python
def action_set_viewed(self, quiz_attempts_inc=False):
```
Calls `check_access('read')` first. For non-members, delegates to session-based tracking via `_set_viewed_slide` in the controller.

**Slide Embed**

```python
def _embed_increment(self, url):
```
Increments `slide.embed.count_views` for the given external URL. Creates a new `slide.embed` record if none exists for that URL+slide combination. If URL has no netloc (i.e., same-site), stores `False` as URL to aggregate same-site views.

**Quiz Info**

```python
def _compute_quiz_info(self, target_partner, quiz_done=False):
```
Returns a dict per slide ID:
```python
{
    'quiz_karma_max': int,       # max achievable (first attempt reward)
    'quiz_karma_gain': int,      # what next attempt would give
    'quiz_karma_won': int,       # what was actually awarded
    'quiz_attempts_count': int,  # number of attempts made
}
```

**ORM Overrides**

```python
def write(self, vals):
```
- `is_category=True`: auto-sets `is_preview=True`, `is_published=True`.
- `slide_category` change: enforces constraint by clearing `url` (→article) or `html_content` (→non-article).
- URL changes trigger `_fetch_external_metadata()` on write.
- `is_published` or `active` changes trigger `channel_id.channel_partner_ids._recompute_completion()`.

```python
def copy_data(self, default=None):
```
Sets `sequence=0` (puts copy at beginning of uncategorized slides). Uses `__copy_data_seen` context key to avoid double-reset when copying entire channel trees.

```python
def unlink(self):
```
1. Moves child slides out of deleted category via `_move_category_slides(category, False)`.
2. Calls `channel_id.channel_partner_ids._recompute_completion()` after super unlink.

```python
def _can_return_content(self, field_name=None, access_token=None):
```
Override of `website.published.mixin` behavior. Returns `True` (content downloadable) if `website_published=True` AND `has_access("read")`. This allows content of published slides to be downloaded by members even if the channel itself is not accessible by the general public.

**Next Category Navigation**

```python
def _get_next_category(self):
```
Returns the next category slide to display after completing the current one. Logic:
1. If current slide is uncategorized and all uncategorized slides are done → return first category.
2. If current category is completed and not the last → return next category.
3. Otherwise → return empty recordset.

---

### slide.channel.partner — Enrollment

**File:** `models/slide_channel_partner.py`
**Table:** `slide_channel_partner`
**Unique constraint:** `unique(channel_id, partner_id)`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `channel_id` | Many2one `slide.channel` | required | Course reference, `ondelete='cascade'` |
| `partner_id` | Many2one `res.partner` | required | User partner, `ondelete='cascade'` |
| `member_status` | Selection | `'joined'` | `'invited'`, `'joined'`, `'ongoing'`, `'completed'`; readonly |
| `completion` | Integer | `0` | Percentage 0–100, `aggregator="avg"` for graph views |
| `completed_slides_count` | Integer | `0` | Count of completed published slides |
| `active` | Boolean | `True` | Archive flag for re-enrollment support |
| `next_slide_id` | Many2one `slide.slide` | computed | Next uncompleted published content slide |
| `invitation_link` | Char | computed | Full invitation URL with HMAC hash |
| `last_invitation_date` | Datetime | — | When the last invitation was sent |

**Readonly related fields (UX):** `partner_email`, `channel_user_id`, `channel_type`, `channel_visibility`, `channel_enroll`, `channel_website_id`.

**SQL Constraints**

```sql
CHECK(completion >= 0 AND completion <= 100)
UNIQUE(channel_id, partner_id)
```

**`_compute_next_slide_id` SQL query:**

```sql
SELECT DISTINCT ON (SCP.id)
    SCP.id AS id,
    SS.id AS slide_id
FROM slide_channel_partner SCP
JOIN slide_slide SS
    ON SS.channel_id = SCP.channel_id
    AND SS.is_published = TRUE
    AND SS.active = TRUE
    AND SS.is_category = FALSE   -- only content slides, not sections
    AND NOT EXISTS (
        SELECT 1 FROM slide_slide_partner
        WHERE slide_id = SS.id
          AND partner_id = SCP.partner_id
          AND completed = TRUE
    )
WHERE SCP.id IN %s
ORDER BY SCP.id, SS.sequence, SS.id
LIMIT 1
```

Uses `DISTINCT ON (SCP.id)` to get one slide per membership. The `NOT EXISTS` subquery ensures only slides not yet completed by this partner are considered.

**`_recompute_completion` bypass rules:**
- `member_status='completed'`: never recomputed; preserves completed state even if slides are unpublished or archived.
- `member_status='invited'`: never recomputed; invitation must first be converted to `'joined'`.

**Invitation System**

```python
def _get_invitation_hash(self):
```
HMAC-SHA256 using `website_slides-channel-invite` secret. Token = `(partner_id, channel_id)`. Returns URL-safe base64-encoded hash. The controller validates this hash to allow invited partners to join.

**Garbage Collection**

```python
@api.autovacuum
def _gc_slide_channel_partner(self):
```
Runs via autovacuum. Deletes `slide.channel.partner` records where:
- `member_status = 'invited'`
- `completion = 0` (never enrolled)
- `last_invitation_date` is null OR older than 3 months

Prevents accumulation of expired invitation records.

**`unlink()` override:**
Removes all `slide.slide.partner` records for the partner+channel combination before deleting the enrollment. Uses `Domain.OR` for safe multi-record deletion.

---

### slide.slide.partner — Per-User Slide Progress

**File:** `models/slide_slide_partner.py`
**Table:** `slide_slide_partner`
**Unique constraint:** `unique(slide_id, partner_id)`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `slide_id` | Many2one `slide.slide` | required | Slide reference, `ondelete='cascade'` |
| `channel_id` | Many2one `slide.channel` | stored, related | Cached from `slide_id.channel_id`, `store=True`, `index=True` |
| `partner_id` | Many2one `res.partner` | required | User partner, `ondelete='cascade'` |
| `vote` | Integer | `0` | Vote: `-1` (dislike), `0` (none), `1` (like) |
| `completed` | Boolean | `False` | Slide completion status |
| `quiz_attempts_count` | Integer | `0` | Number of quiz attempts |

**SQL Constraints**

```sql
CHECK(vote IN (-1, 0, 1))
UNIQUE(slide_id, partner_id)
```

**Performance note:** `channel_id` is stored explicitly (not just related) because `_recompute_completion` on `slide.channel.partner` is called frequently and needs to search by `channel_id`. Storing it avoids repeated joins.

**Lifecycle hooks:**

```python
@api.model_create_multi
def create(self, vals_list):
    super().create(vals_list)
    # After create: if any record has completed=True → call _recompute_completion
    # (which finds the slide.channel.partner and triggers completion chain)
```

```python
def write(self, vals):
    # If 'completed' value is changing: call _recompute_completion
    # Important: only triggers when state actually changes (filtered by self.completed != vals['completed'])
```

```python
def _recompute_completion(self):
    self.env['slide.channel.partner'].search([
        ('channel_id', 'in', self.channel_id.ids),
        ('partner_id', 'in', self.partner_id.ids),
        ('member_status', 'not in', ('completed', 'invited'))
    ])._recompute_completion()
```
Searches for `slide.channel.partner` records and delegates to their `_recompute_completion()`.

---

### slide.question — Quiz Question

**File:** `models/slide_question.py`
**Order:** `sequence asc`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sequence` | Integer | — | Display order |
| `question` | Char | required, translate | Question text |
| `slide_id` | Many2one `slide.slide` | required, `ondelete='cascade'` | Parent slide |
| `answer_ids` | One2many `slide.answer` | — | Possible answers, `copy=True` |
| `answers_validation_error` | Char | computed | Error message if validation fails |
| `attempts_count` | Integer | computed | Total quiz attempts across all users |
| `attempts_avg` | Float | computed | Average attempts per user (6,2 digits) |
| `done_count` | Integer | computed | Users who completed this question |

All statistics fields have `groups='website_slides.group_website_slides_officer'`.

**Constraint (`@api.constrains`)**

```python
@api.constrains('answer_ids')
def _check_answers_integrity(self):
    # Raises ValidationError if:
    # - No correct answer (is_correct=True), OR
    # - All answers are correct (is_correct == answer_ids)
    # Both conditions are checked via answers_validation_error
```

`_compute_answers_validation_error`: Sets error if no correct answer OR all answers are correct. Used in form view to prevent invalid question configurations.

**_compute_statistics**: Uses `sudo()` to aggregate `slide.slide.partner` records. `attempts_avg = total_attempts / unique_users`. This bypasses ACL since officers need aggregate stats without individual record access.

---

### slide.answer — Quiz Answer Option

**File:** `models/slide_question.py` (same file as `slide.question`)
**Order:** `question_id, sequence, id`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sequence` | Integer | — | Display order |
| `question_id` | Many2one `slide.question` | required, `ondelete='cascade'` | Parent question |
| `text_value` | Char | required, translate | Answer text |
| `is_correct` | Boolean | `False` | Correct answer flag |
| `comment` | Text | — | Feedback shown when user selects this answer, translateable |

**Design note:** `is_correct` is a simple boolean. If multiple answers have `is_correct=True`, all must be selected by the user for the question to be counted correct (multi-select quiz support).

---

### slide.slide.resource — Downloadable Resources

**File:** `models/slide_slide_resource.py`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `slide_id` | Many2one `slide.slide` | required, `ondelete='cascade'` | Parent slide |
| `resource_type` | Selection | required | `'file'` or `'url'` |
| `name` | Char | computed | Auto-named from file/link; editable |
| `data` | Binary | computed-reset | File content; reset when switching to URL type |
| `file_name` | Char | stored | Original uploaded filename |
| `link` | Char | computed-reset | External URL; reset when switching to file type |
| `download_url` | Char | computed | `/web/content/slide.slide.resource/{id}/data?download=true&filename={name}` |
| `sequence` | Integer | — | Display order |

**`_compute_reset_resources`:** When `resource_type` changes to `'file'`: clears `link`, preserves `data`. When changes to `'url'`: clears `data`, preserves `link`. This prevents stale data from accumulating.

**`_compute_download_url`:** Appends `filename` with detected extension. Extension is extracted using `get_extension(resource.file_name)`.

**`_compute_name`:** Auto-populates `name` from `file_name` (for files) or `link` (for URLs) if name is unset or equals `"Resource"`.

**SQL Constraints**

```sql
CHECK(resource_type != 'url' OR link IS NOT NULL)
CHECK(resource_type != 'file' OR link IS NULL)
```

---

### slide.embed — External Embed Tracking

**File:** `models/slide_embed.py`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `slide_id` | Many2one `slide.slide` | required, `ondelete='cascade'` | Slide being embedded |
| `url` | Char | — | Third-party website URL (or `False` for same-site) |
| `website_name` | Char | computed | Display name for the third-party site |
| `count_views` | Integer | `1` | Total views from this embed location |

**`_compute_website_name`:** Returns `url` or `'Unknown Website'`.

---

### slide.channel.tag.group — Tag Groups

**File:** `models/slide_channel_tag.py`
**Inherits:** `website.published.mixin`
**Order:** `sequence asc`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required, translate | Group name |
| `sequence` | Integer | `10` | Display order |
| `tag_ids` | One2many `slide.channel.tag` | — | Tags in this group |

**`_default_is_published`:** Returns `True` — tag groups are published by default.

---

### slide.channel.tag — Course Tags

**File:** `models/slide_channel_tag.py`
**Order:** `group_sequence asc, sequence asc`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required, translate | Tag name |
| `sequence` | Integer | `10` | Order within group |
| `group_id` | Many2one `slide.channel.tag.group` | required, `ondelete='cascade'` | Parent group |
| `group_sequence` | Integer | related `group_id.sequence`, `store=True` | Group display order |
| `channel_ids` | Many2many `slide.channel` | — | Courses with this tag (via `slide_channel_tag_rel`) |
| `color` | Integer | `randint(1, 11)` | Tag color; `0 or False` = invisible to public (internal tag) |

**Tag group filtering (search):** Tags without a `color` set are not visible to public/portal users (`website_slides_security.xml` rule: `color != False AND color != 0`).

---

### slide.tag — Cross-Course Tags

**File:** `models/slide_tag.py`

| Field | Type | Constraint |
|-------|------|-------------|
| `name` | Char | `UNIQUE(name)` |

Used to tag slides across courses for cross-navigation and related content discovery.

---

### gamification.karma.tracking (Extension)

**File:** `models/gamification_karma_tracking.py`

```python
def _get_origin_selection_values(self):
    return super()._get_origin_selection_values() + [
        ('slide.slide', _('Course Quiz')),
        ('slide.channel', <display_name of slide.channel>)
    ]
```
Adds `slide.slide` and `slide.channel` as karma tracking origin options. This allows karma movements to be attributed to quiz completions and course completions in the gamification reporting.

---

### res.partner (Extension)

**File:** `models/res_partner.py`

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `slide_channel_ids` | Many2many `slide.channel` | Officer | All enrolled courses (joined/ongoing/completed) |
| `slide_channel_completed_ids` | One2many `slide.channel` | Officer | Completed courses only |
| `slide_channel_count` | Integer | Officer | Total enrolled course count |
| `slide_channel_company_count` | Integer | Officer | Courses enrolled by company contacts |

All are compute/search hybrids. `slide_channel_company_count` is computed only for companies (`is_company=True`), counting enrollments of all `child_ids` contacts.

**`action_view_courses()`:** Returns the attendee/action window filtered to this partner. In singleton company mode, shows all child contact enrollments.

---

### mail.activity (Extension)

**File:** `models/mail_activity.py`

| Field | Type | Description |
|-------|------|-------------|
| `request_partner_id` | Many2one `res.partner` | Partner who requested course access |

Added to `MailActivity` to support the course access request workflow. When a user requests access to an invite-only course, a `mail.activity` todo is created on the channel with `request_partner_id` set.

---

### res.users (Extension)

**File:** `models/res_users.py`

**`create()` override:** After user creation, searches channels where `enroll_group_ids` includes any of the user's groups, and auto-enrolls the user via `_action_add_members()`.

**`write()` override:** When `group_ids` changes, computes `added_group_ids` (including implied groups via `all_implied_ids`), then auto-enrolls user to channels matching those groups.

**`get_gamification_redirection_data()`:** Appends `{url: '/slides', label: 'See our eLearning'}` for gamification badge/challenge redirection.

---

### res.groups (Extension)

**File:** `models/res_groups.py`

**`write()` override:** When `user_ids` changes (new users added to group), calls `_add_groups_members()` on all channels linked to this group via `enroll_group_ids`. This ensures newly added group members are enrolled automatically.

---

## Security Model

### Groups

| Group | Privilege | Implied Groups | Key Permissions |
|-------|-----------|----------------|-----------------|
| `website_slides.group_website_slides_officer` | Officer | `website.group_website_restricted_editor` | CRUD own channels/slides; read all; manage members of own channels |
| `website_slides.group_website_slides_manager` | Manager | Officer | Full CRUD on all records; delete channels |
| `base.group_public` | Public | — | Read published channels; read preview slides of published channels |
| `base.group_portal` | Portal | — | Read published channels if signed in; read preview slides |
| `base.group_user` | Internal | — | Same as portal for reads |

### ir.rule Domain Summary

**`slide.channel`**

| Rule | Groups | Domain | Ops |
|------|--------|--------|-----|
| Global | (all) | `[(1, '=', 1)]` | Read |
| Public user | `base.group_public` | `website_published=True AND visibility IN ('public','link')` | Read |
| Signed-in user | `base.group_portal`, `base.group_user` | `website_published=True AND visibility IN ('public','connected','link') OR is_member_invited OR is_member` | Read |
| Officer | Officer | `[(1, '=', 1)]` | Read |
| Officer | Officer | `user_id = user.id` | Create/Write |
| Manager | Manager | `[(1, '=', 1)]` | Full CRUD |

**`slide.slide`**

| Rule | Groups | Domain | Ops |
|------|--------|--------|-----|
| Public user | `base.group_public` | `channel_published AND slide_published AND channel_visibility IN ('public','link') AND (is_category OR is_preview=True)` | Read |
| Signed-in user | `base.group_portal`, `base.group_user` | Complex: `user_id=self OR (slide_published AND channel_published AND (channel_visibility IN public/connected/link OR is_member_invited OR is_member) AND (is_category OR is_preview OR is_member))` | Read |
| Officer | Officer | `[(1, '=', 1)]` | Read |
| Officer | Officer | `channel_id.user_id = user.id` | Create/Write/Unlink |
| Manager | Manager | `[(1, '=', 1)]` | Full CRUD |

**`slide.channel.partner`** — No public/portal access. Officer: write own channels. Manager: full CRUD.

**`slide.slide.partner`** — No public/portal access. Officer: write own channels. Manager: full CRUD.

**`slide.slide.resource`** — For portal/user: `channel.is_member=True` required. Officer: read all, CRUD own channels.

### Access Rights (ir.model.access.csv)

All access is managed via `ir.rule`; `ir.model.access.csv` grants broad model-level permissions to Officer/Manager groups only. Public users rely entirely on `ir.rule` for record-level filtering.

---

## Karma System — Complete Reference

Karma is the gamification currency. All karma operations go through `res.users._add_karma()` (for positive/negative karma awards).

### Karma Award Table

| Trigger | Source Field | Method | Notes |
|---------|-------------|--------|-------|
| Course ranked (rated) | `slide.channel.karma_gen_channel_rank` | `message_post()` when `rating_value` is set | One award per rating |
| Course completed | `slide.channel.karma_gen_channel_finish` | `_post_completion_update_hook()` | Awarded once per course completion; reversed if uncompleted |
| Quiz passed (1st attempt) | `slide.slide.quiz_first_attempt_reward` | `_action_set_quiz_done()` | Only if attempts count matches at completion time |
| Quiz passed (2nd attempt) | `slide.slide.quiz_second_attempt_reward` | `_action_set_quiz_done()` | — |
| Quiz passed (3rd attempt) | `slide.slide.quiz_third_attempt_reward` | `_action_set_quiz_done()` | — |
| Quiz passed (4th+ attempt) | `slide.slide.quiz_fourth_attempt_reward` | `_action_set_quiz_done()` | Capped at 4th reward level |
| Karma reversal | Same fields, negated | `_action_set_quiz_done(completed=False)`, `_post_completion_update_hook(completed=False)` | Undoing completions reverses karma |

**Karma tracking origin:** Extended `gamification.karma.tracking._get_origin_selection_values()` includes `'slide.slide'` (quiz) and `'slide.channel'` (completion).

---

## Controller Endpoints (controllers/main.py)

**Class:** `WebsiteSlides` (inherits `WebsiteProfile`)

| Route | Description |
|-------|-------------|
| `/slides` | Course catalog |
| `/slides/<slug>` | Course detail / enrollment |
| `/slides/<slug>/invite` | Invitation acceptance (checks HMAC hash) |
| `/slides/<slug>/<slug>` | Slide detail (lesson page) |
| `/slides/slide/<id>/share` | Slide share endpoint |
| `/slides/embed/<id>` | Embed iframe endpoint (internal) |
| `/slides/embed_external/<id>` | External embed iframe |

**Session-based view tracking:** Non-member public views are stored in `request.session['viewed_slides']` as a dict `{slide_id_str: 1}`. Uses `increment_fields_skiplock` for non-blocking concurrent writes.

**Error handling:** `handle_wslide_error()` redirects access denied to `/slides?invite_error=no_rights`.

---

## Performance Considerations

1. **`_compute_next_slide_id`**: Uses raw SQL with `DISTINCT ON` — avoids ORM overhead for the most frequent per-user query on the course progress page.

2. **`slide.slide.partner` write tracking**: Only triggers `_recompute_completion` when `completed` value actually changes (filtered diff check). Avoids cascading recomputes on unrelated field updates.

3. **`increment_fields_skiplock`**: Used for both session-based view increment and quiz attempt count. Non-blocking, prevents row-level lock contention under high concurrency.

4. **`sudo()` in statistics computes**: `_compute_statistics` on `slide.question` and `_compute_like_info` on `slide.slide` both use `sudo()` because the data is aggregated and ACL on individual records is not relevant.

5. **`image_url_only` parameter**: Metadata fetching for previews uses external image URLs rather than downloading+encoding binary thumbnails, avoiding HTTP round-trips and base64 encoding overhead.

6. **`install_mode` and `website_slides_skip_fetch_metadata` context keys**: Prevent costly external API calls during module installation or data imports.

7. **Category `completion_time` recursion**: Uses iterative sum instead of `read_group()` to avoid recursive flush deadlocks (completion_time is recursive and category-time = sum of child slide times).

---

## Odoo 18 → 19 Changes

Key differences from the Odoo 18 `website_slides` module:

1. **Four-tier quiz rewards**: Odoo 18 had `quiz_first_attempt_reward` and `quiz_total_attempt_reward`. Odoo 19 splits into four tiers (`quiz_fourth_attempt_reward` for 4th+ attempts).

2. **`karma_gen_channel_rank`**: Separated from completion karma. Odoo 18 may have conflated these.

3. **Prerequisite courses**: `prerequisite_channel_ids` m2m self-referential field with `_compute_prerequisite_user_has_completed` was likely introduced or enhanced in 19.

4. **`partner_unfollow_enabled = True`**: Set on both `slide.channel` and `slide.slide` models, allowing partners to unfollow courses/slides from the website.

5. **`website.published.multi.mixin`**: Odoo 18 may have used the single-website version; Odoo 19 upgrades to the multi-website mixin.

6. **Session `viewed_slides` dict**: Odoo 18 stored as list; Odoo 19 converts to dict on session load for O(1) lookup and automatic deduplication.

7. **`mail.activity.request_partner_id`**: Access request activities use a dedicated field rather than generic activity notes.

8. **`slide.channel.tag.group` → `website.published.mixin`**: Tag groups can now be unpublished individually via the mixin.

---

## Edge Cases

1. **Invited partner re-enrolling**: When an invited partner clicks the invitation link and enrolls, their existing `slide.channel.partner` record (with `member_status='invited'`) is unarchived and `member_status` updated to `'joined'`. `_recompute_completion()` is called, preserving any previously completed slides (since `completed_slides_count` comes from `slide.slide.partner` which was NOT deleted on archive).

2. **Channel archive order**: `action_archive()` writes `is_published=False` on the channel first (before archiving slides) to prevent the completion recompute from miscounting slides_total as 0.

3. **Quiz completion without attempts**: `_action_set_quiz_done` checks `quiz_attempts_count` before awarding karma. A user who manually marks a quiz slide complete without taking the quiz gets no karma.

4. **Like/dislike toggle**: `_action_vote` toggles through 0 (removing vote) rather than directly swapping like↔dislike. Users must go through neutral state.

5. **Category slide deletion**: `unlink()` moves child slides to uncategorized before deletion to preserve their `category_id` reference during the cascade.

6. **HMAC invitation hash**: Uses `tools.hmac(self.env(su=True), 'website_slides-channel-invite', token)` with superuser env — invitation hashes cannot be forged by regular users.

7. **Description sync on write**: If `description_short` was implicitly set equal to `description`, they are kept in sync. Explicitly changing only `description` will not update `description_short` (the reverse sync check uses `is_html_empty` to detect intentional clearing).

8. **PDF completion time on upload**: `_on_change_document_binary_content` triggers when `document_binary_content` changes, computing completion time from page count. `_get_completion_time_pdf` handles this on create as well.

---

## Related

- [Modules/website](modules/website.md)
- [Modules/website_blog](modules/website_blog.md)
- [Modules/portal](modules/portal.md)
- [Modules/rating](modules/rating.md)
- [Modules/gamification](modules/gamification.md)
- [Modules/website_profile](modules/website_profile.md)
- [Modules/website_mail](modules/website_mail.md)
- [Core/API](core/api.md) — `@api.depends`, computed fields
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — state machines vs. action methods
- [Tools/ORM Operations](tools/orm-operations.md) — `search()`, `write()`, domain operators
