---
Module: website_forum
Version: Odoo 18
Type: Business
Tags: #odoo18, #forum, #community, #karma, #moderation, #voting, #website
---

# website_forum — Community Forum

Full-featured public Q&A community forum built on Odoo's website platform. Supports questions and answers with voting, karma-based access control, inline comments, tags, post moderation, and gamification.

**Module path:** `addons/website_forum/`
**Key dependency:** `website`, `gamification`
**Inherits:** `mail.thread`, `website.seo.metadata`, `website.searchable.mixin`, `website.multi.mixin`

---

## Domain Model

```
forum.forum ──── N ──── forum.post ──── N ──── forum.post.vote
     │                      │
     │                      ├── parent_id (self-referential): Question ──► Answers
     │                      │
     │                      └── N forum.post ── (answers can have nested answers in discussions mode)
     │
     └── N forum.tag ──── M forum.post (via forum_tag_rel)

forum.post ──── N ──── forum.post.comment (mail.message)
forum.forum ──── N ──── forum.post ──► forum.post.reason (closing reasons)
forum.forum ──── N ──── forum.tag
```

---

## Models

### 1. `forum.forum` — Forum Configuration

**Inherits:** `mail.thread`, `image.mixin`, `website.seo.metadata`, `website.multi.mixin`, `website.searchable.mixin`
**Table:** `forum_forum`
**Order:** `sequence, id`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Forum name (translateable) |
| `sequence` | Integer | Sort order |
| `mode` | Selection | `questions` (1 answer max) / `discussions` (multiple answers) |
| `privacy` | Selection | `public` / `connected` (signed in) / `private` (group-based) |
| `authorized_group_id` | Many2one `res.groups` | Required group for `private` forums |
| `active` | Boolean | Archive/unarchive |
| `faq` | Html | Guidelines / FAQ content (auto-generated default) |
| `description` | Text | Forum description |
| `teaser` | Text (computed) | First 180 chars of description |
| `welcome_message` | Html | Banner message for non-members |
| `default_order` | Selection | Sort order for forum listing: `create_date desc` / `last_activity_date desc` / `vote_count desc` / `relevancy desc` / `child_count desc` |
| `relevancy_post_vote` | Float | First relevancy parameter (default 0.8). Formula: `copysign(1, votes) * (|votes-1| ** post_vote_param / (days+2) ** time_decay_param)` |
| `relevancy_time_decay` | Float | Second relevancy parameter (default 1.8) |
| `allow_share` | Boolean | Show social sharing option after posting |
| `post_ids` | One2many `forum.post` | All posts in forum |
| `last_post_id` | Many2one `forum.post` (computed) | Most recent active question |
| `total_posts` | Integer (computed) | Count of active/closed questions |
| `total_views` | Integer (computed) | Sum of all question views |
| `total_answers` | Integer (computed) | Sum of all answer counts |
| `total_favorites` | Integer (computed) | Number of favorited questions |
| `count_posts_waiting_validation` | Integer (computed) | Pending posts awaiting moderation |
| `count_flagged_posts` | Integer (computed) | Flagged posts count |
| `karma_gen_question_new` | Integer | Karma for asking a new question (default: 2) |
| `karma_gen_question_upvote` | Integer | Karma awarded to question author when upvoted (default: 5) |
| `karma_gen_question_downvote` | Integer | Karma (negative) for question downvote (default: -2) |
| `karma_gen_answer_upvote` | Integer | Karma awarded to answer author when upvoted (default: 10) |
| `karma_gen_answer_downvote` | Integer | Karma for answer downvote (default: -2) |
| `karma_gen_answer_accept` | Integer | Karma awarded to user who accepts an answer (default: 2) |
| `karma_gen_answer_accepted` | Integer | Karma awarded to answer author when answer is accepted (default: 15) |
| `karma_gen_answer_flagged` | Integer | Karma penalty when answer is flagged as offensive (default: -100) |
| `karma_ask` | Integer | Karma required to ask questions (default: 3) |
| `karma_answer` | Integer | Karma required to answer questions (default: 3) |
| `karma_edit_own` | Integer | Karma to edit own posts (default: 1) |
| `karma_edit_all` | Integer | Karma to edit any post (default: 300) |
| `karma_edit_retag` | Integer | Karma to change question tags (default: 75) |
| `karma_close_own` | Integer | Karma to close own questions (default: 100) |
| `karma_close_all` | Integer | Karma to close any question (default: 500) |
| `karma_unlink_own` | Integer | Karma to delete own posts (default: 500) |
| `karma_unlink_all` | Integer | Karma to delete any post (default: 1000) |
| `karma_tag_create` | Integer | Karma to create new tags (default: 30) |
| `karma_upvote` | Integer | Karma required to upvote (default: 5) |
| `karma_downvote` | Integer | Karma required to downvote (default: 50) |
| `karma_answer_accept_own` | Integer | Karma to accept answer on own question (default: 20) |
| `karma_answer_accept_all` | Integer | Karma to accept any answer (default: 500) |
| `karma_comment_own` | Integer | Karma to comment on own posts (default: 1) |
| `karma_comment_all` | Integer | Karma to comment on any post (default: 1) |
| `karma_comment_convert_own` | Integer | Karma to convert own comments to answers (default: 50) |
| `karma_comment_convert_all` | Integer | Karma to convert any comment to answer (default: 500) |
| `karma_comment_unlink_own` | Integer | Karma to delete own comments (default: 50) |
| `karma_comment_unlink_all` | Integer | Karma to delete any comment (default: 500) |
| `karma_flag` | Integer | Karma required to flag a post (default: 500) |
| `karma_dofollow` | Integer | Karma threshold below which links get `nofollow` (default: 500) |
| `karma_editor` | Integer | Karma for full editor with images and links (default: 30) |
| `karma_user_bio` | Integer | Karma to display detailed user biography (default: 750) |
| `karma_post` | Integer | Karma to post without prior validation (default: 100) |
| `karma_moderate` | Integer | Karma to moderate posts (default: 1000) |
| `has_pending_post` | Boolean (computed/user) | Current user has a pending post |
| `can_moderate` | Boolean (computed/user) | Current user has moderation rights |
| `tag_ids` | One2many `forum.tag` | All tags in forum |
| `tag_most_used_ids` | One2many `forum.tag` (computed) | Top 5 most-used tags |
| `tag_unused_ids` | One2many `forum.tag` (computed) | Tags with zero posts |

#### Key Methods

- `_set_default_faq()` — Renders `website_forum.faq_accordion` template with forum data on create.
- `_tag_to_write_vals(tags='')` — Parses a comma-separated tag string. Tags prefixed with `_` are new tags to create (requires `karma_tag_create`). Existing tags are looked up by ID. Returns a write-compatible `(6, 0, [existing_ids]) + (0, 0, {new_tag_dicts})` vals list.
- `_compute_website_url()` — Returns `/forum/<slug>`.
- `go_to_website()` — Returns a client action redirecting to the forum's website URL.

#### L4 Notes

- **Privacy:** When `privacy` is set to `public` or `connected`, `authorized_group_id` is cleared. Private forums require membership in `authorized_group_id` to access content.
- **Archiving:** Setting `active=False` on a forum cascades to all its posts.
- **FAQ auto-generation:** `_set_default_faq()` is called on create, not on write. Manually edited FAQs are preserved.
- **Tag most used / unused:** `_compute_tag_ids_usage()` uses `search_read` to sort tags by `posts_count DESC`, then splits into the top 5 most used and all unused. The count is filtered by the field domain `[('state', '=', 'active')]` on the M2M relation.
- **Relevancy formula:** The relevancy score for a post is `copysign(1, vote_count) * (abs(vote_count - 1) ** post_vote / (days_since_creation + 2) ** time_decay)`. Older high-voted posts score lower; recent high-voted posts score highest.

---

### 2. `forum.post` — Question or Answer

**Inherits:** `mail.thread`, `website.seo.metadata`, `website.searchable.mixin`
**Table:** `forum_post`
**Order:** `is_correct DESC, vote_count DESC, last_activity_date DESC`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Question title (only for root posts / questions) |
| `forum_id` | Many2one `forum.forum` | Parent forum |
| `content` | Html | Post body (stripped of inline styles) |
| `plain_content` | Text (computed/stored) | Plain text first 500 chars of content |
| `tag_ids` | Many2many `forum.tag` | Tags for questions |
| `state` | Selection | `active` / `pending` (waiting validation) / `close` / `offensive` / `flagged` |
| `views` | Integer | View count (readonly, copy=False) |
| `active` | Boolean | Soft-delete support |
| `website_message_ids` | One2many | Mail thread comments (domain: message_type in email/comment/email_outgoing) |
| `website_url` | Char (computed) | `/forum/<slug>/<slug>/<id>#answer_<id>` for answers |
| `website_id` | Many2one (related) | Forum's website |
| `create_date` | Datetime | Asked/answered on (indexed) |
| `create_uid` | Many2one `res.users` | Author |
| `write_date` | Datetime | Last edit time |
| `last_activity_date` | Datetime | Last activity (answers, comments, edits) — updated on any of these |
| `write_uid` | Many2one `res.users` | Last editor |
| `relevancy` | Float (computed/stored) | Relevancy score |
| `vote_ids` | One2many `forum.post.vote` | All votes on this post |
| `user_vote` | Integer (computed/user) | Current user's vote: 1 / 0 / -1 |
| `vote_count` | Integer (computed/stored) | Net vote count (ups minus downs) |
| `favourite_ids` | Many2many `res.users` | Users who favorited this post |
| `user_favourite` | Boolean (computed/user) | Current user has favorited |
| `favourite_count` | Integer (computed/stored) | Number of favorites |
| `is_correct` | Boolean | Answer accepted as correct (questions only, child posts) |
| `parent_id` | Many2one `forum.post` (readonly) | Parent question (null for questions) |
| `self_reply` | Boolean (computed/stored) | Author replied to their own question |
| `child_ids` | One2many `forum.post` | Answers (filtered by `forum_id`) |
| `child_count` | Integer (computed/stored) | Number of answers |
| `uid_has_answered` | Boolean (computed/user) | Current user has posted an answer |
| `has_validated_answer` | Boolean (computed/stored) | Question has an accepted answer |
| `flag_user_id` | Many2one `res.users` | User who flagged this post |
| `moderator_id` | Many2one `res.users` | Moderator who reviewed this post |
| `closed_reason_id` | Many2one `forum.post.reason` | Reason for closing |
| `closed_uid` | Many2one `res.users` | User who closed the post |
| `closed_date` | Datetime | When the post was closed |

**Karma action fields** (all `compute_sudo=False`, depend on `karma_*` forum settings):

| Field | Type |
|-------|------|
| `karma_accept` | Integer |
| `karma_edit` | Integer |
| `karma_close` | Integer |
| `karma_unlink` | Integer |
| `karma_comment` | Integer |
| `karma_comment_convert` | Integer |
| `karma_flag` | Integer |
| `can_ask / can_answer / can_accept / can_edit / can_close / can_unlink` | Boolean |
| `can_upvote / can_downvote / can_comment / can_comment_convert` | Boolean |
| `can_view / can_display_biography / can_post / can_flag / can_moderate / can_use_full_editor` | Boolean |

#### SQL Constraints

```python
@api.constrains('parent_id')
def _check_parent_id(self):
    if self._has_cycle():  # Prevents recursive post chains
        raise ValidationError(_('You cannot create recursive forum posts.'))
```

#### Key Methods

**Karma rights computation (`_compute_post_karma_rights`):**
- `can_ask`: `user.karma >= forum.karma_ask` (or admin)
- `can_answer`: `user.karma >= forum.karma_answer`
- `can_accept`: `user.karma >= karma_accept` where `karma_accept = karma_answer_accept_own` if current user is question author, else `karma_answer_accept_all`
- `can_edit`: `user.karma >= karma_edit` where `karma_edit = karma_edit_own` if own post, else `karma_edit_all`
- `can_upvote`: `user.karma >= karma_upvote` OR user has already downvoted (`user_vote == -1`)
- `can_downvote`: `user.karma >= karma_downvote` OR user has already upvoted (`user_vote == 1`)
- `can_view`: `can_close` OR (post is active AND (author has karma > 0 OR is current user))
- `can_display_biography`: author has `karma >= karma_user_bio` AND `website_published = True`
- `can_moderate`: `user.karma >= karma_moderate`

**State transitions (in `write()`):**
- `state -> active/close`: requires `can_close`. Grants `trusted_keys` write access.
- `state -> flagged`: requires `can_flag`. Sets `flag_user_id`.
- `active -> False` (delete): requires `can_unlink`.
- `is_correct` change: requires `can_accept`. Awards karma to answer author and accepts user's karma reward, except when user accepts their own answer.

**Content update:**
- `_update_content(content, forum_id)` — Sanitizes HTML content. Adds `rel="nofollow"` to links if author's karma is below `forum.karma_dofollow`.

**Notifications:**
- `_notify_state_update()` — Called after create. Notifies followers of state changes.

#### L4 Notes

- **`is_correct` is only meaningful on answer posts** (where `parent_id` is set). It represents "accepted answer" in questions mode.
- **`self_reply` computed field:** Determines if the answer author is the same as the question author. Used for UI differentiation (e.g., badge showing "Author").
- **One answer per forum mode:** When `forum.mode == 'questions'`, the constraint is enforced by the UI (the "Post an Answer" form is hidden after an answer is posted) and `can_answer` logic, not by a hard database constraint.
- **Comments vs Answers:** Comments are stored as `mail.message` records on `forum.post` via `website_message_ids` (mail.thread mixin). Answers are `forum.post` records with `parent_id` set. Converting a comment to an answer changes its model from `mail.message` to `forum.post` — this is a moderation action that requires karma.
- **View counting:** `views` is incremented directly in the ORM (no tracking of unique views). It is `copy=False` so duplicating a post does not copy view counts.
- **Last activity date:** Updated whenever an answer is posted, a comment is added, or the post is edited.
- **Moderation workflow:** Posts from users with karma below `forum.karma_post` are created with `state='pending'`. Moderators (`karma >= karma_moderate`) can activate them via `write({'state': 'active'})`.

---

### 3. `forum.post.vote` — Vote Record

**Table:** `forum_post_vote`
**Order:** `create_date desc, id desc`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | Many2one `forum.post` | Voted post |
| `user_id` | Many2one `res.users` | Voter (default: current user) |
| `vote` | Selection | `'1'` (upvote), `'-1'` (downvote), `'0'` (removed/abstain) |
| `create_date` | Datetime | When vote was cast (indexed, readonly) |
| `forum_id` | Many2one `forum.forum` (related/stored) | Forum |
| `recipient_id` | Many2one `res.users` (related/stored) | Post author |

#### SQL Constraints

```python
vote_uniq = UNIQUE(post_id, user_id)  # One vote per user per post
```

#### Key Methods

- `_get_karma_value(old_vote, new_vote, up_karma, down_karma)` — Computes karma delta. Karma change = `new_karma - old_karma`. Returns `(karma_delta, reason_string)`.
- `_vote_update_karma(old_vote, new_vote)` — Dispatches to `karma_gen_question_upvote/downvote` or `karma_gen_answer_upvote/downvote` based on whether `post.parent_id` exists. Calls `recipient_id.sudo()._add_karma(karma, post, source)`.
- `_check_general_rights()` — Prevents: (1) voting on own post, (2) editing another user's vote.
- `_check_karma_rights(upvote=False)` — Checks `can_upvote` or `can_downvote` based on forum's `karma_upvote` / `karma_downvote` thresholds.

#### L4 Notes

- **Vote toggling:** In the forum UI, clicking the same vote button again removes the vote (changes to `'0'`). The `_vote_update_karma` logic handles the reversal correctly via the `old_vote -> new_vote` delta.
- **Karma is awarded to the post author, not the voter.** The voter loses no karma for voting (unless they downvote, which may have a karma cost in some configurations — but the current implementation only deducts karma from downvote receivers, not voters).
- **Vote is stored as string** (`'1'`, `'-1'`, `'0'`) not integer. The SQL constraint uses string values.
- **Karma delta example:** If a question is upvoted (new_vote=`'1'`, old_vote=`'0'`): `+5` karma for author. If changed to downvote: `+5 - (-2) = +7` net change. If removed (new_vote=`'0'`): `-5` karma removed.

---

### 4. `forum.tag` — Forum Tag

**Inherits:** `mail.thread`, `website.searchable.mixin`, `website.seo.metadata`
**Table:** `forum_tag`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (unique within a forum) |
| `color` | Integer | Color index for UI |
| `forum_id` | Many2one `forum.forum` | Parent forum (required, indexed) |
| `post_ids` | Many2many `forum.post` | Posts using this tag (domain: `state='active'`) |
| `posts_count` | Integer (computed/stored) | Number of posts with this tag |
| `website_url` | Char (computed) | `/forum/<slug>/tag/<slug>/questions` |

#### SQL Constraints

```python
name_uniq = UNIQUE(name, forum_id)  # Same tag name can exist in different forums
```

#### Key Methods

- `create()` — Checks `karma_tag_create` threshold for non-admin users.

---

### 5. `forum.post.reason` — Post Closing Reason

**Table:** `forum_post_reason`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reason name (translateable) |
| `reason_type` | Selection | `basic` or `offensive` |

---

### 6. `gamification.challenge` (Extension)

Adds `challenge_category = 'forum'` to enable forum-specific challenges and badges in the gamification system.

---

### 7. `gamification.karma.tracking` (Extension)

Extends karma tracking to include `forum.post` as a karma origin type alongside the base gamification origins.

---

## Karma System (Complete Reference)

### Earning Karma

| Action | Karma to Recipient | Karma to Actor |
|--------|-------------------|----------------|
| Ask a new question (state=active) | — | +`karma_gen_question_new` (default +2) |
| Question upvoted | +`karma_gen_question_upvote` (default +5) | — |
| Question downvoted | +`karma_gen_question_downvote` (default -2) | — |
| Answer upvoted | +`karma_gen_answer_upvote` (default +10) | — |
| Answer downvoted | +`karma_gen_answer_downvote` (default -2) | — |
| Accept an answer (on own question) | — | +`karma_gen_answer_accept` (default +2) |
| Answer accepted (as author) | +`karma_gen_answer_accepted` (default +15) | — |
| Accept own answer | No karma awarded | No karma awarded |
| Remove accepted answer | Reverse accepted karma | Reverse accept karma |
| Rank a course (slides module) | — | +`karma_gen_channel_rank` |

### Karma Thresholds (Feature Gating)

| Feature | Default Karma Required |
|---------|-----------------------|
| Ask a question | 3 |
| Answer a question | 3 |
| Upvote | 5 |
| Downvote | 50 |
| Edit own posts | 1 |
| Comment on any post | 1 |
| Full editor (images + links) | 30 |
| Create new tag | 30 |
| Convert comment to answer (own) | 50 |
| Delete own comment | 50 |
| Retag question | 75 |
| Accept answer on own question | 20 |
| Accept answer on any question | 500 |
| Edit any post | 300 |
| Close own post | 100 |
| Delete own post | 500 |
| Close any post | 500 |
| Delete any post | 1000 |
| Flag post as offensive | 500 |
| Nofollow on links (below = nofollow) | 500 |
| Display biography on profile | 750 |
| Post without validation | 100 |
| Moderate posts | 1000 |

---

## Comments vs Answers (L4)

| Aspect | Comments | Answers |
|--------|---------|---------|
| Storage model | `mail.message` (via `mail.thread`) | `forum.post` (self-referential with `parent_id`) |
| Access | Inline on question or answer | Listed below question as separate posts |
| Karma to add | `karma_comment_own` (own) / `karma_comment_all` (any) | `karma_answer` |
| Karma to convert | `karma_comment_convert_own` / `karma_comment_convert_all` | N/A (reverse operation) |
| Karma on upvote | N/A | `karma_gen_answer_upvote` |
| Has accepted state | No | Yes (`is_correct`) |
| Notification to followers | Via mail.thread | Via mail.thread + special subtype |
| Can be nested | No | No (flat answers only) |

Comments are displayed inline below the post content. Answers are rendered in a separate section, ordered by `is_correct DESC`, then `vote_count DESC`.

Converting a comment to an answer requires the `karma_comment_convert` threshold and changes the record from a `mail.message` to a `forum.post` with `parent_id` set.

---

## Accepted Answer Workflow (L4)

1. The question author (or anyone with sufficient karma) clicks "Accept" on an answer.
2. `write({'is_correct': True})` is called. The `can_accept` check requires `user.karma >= karma_accept` where `karma_accept = karma_answer_accept_own` if the user is the question author, otherwise `karma_answer_accept_all`.
3. **Karma awarded (if not self-acceptance):**
   - Answer author: `+karma_gen_answer_accepted` (default +15)
   - Accepting user: `+karma_gen_answer_accept` (default +2)
4. **Self-acceptance:** No karma is awarded when `create_uid == self._uid`. The UI hides the "Accept" button on your own answers.
5. **Removing acceptance:** Sets `is_correct=False`, reversing both karma amounts (negative delta).
6. **Only one accepted answer:** In `questions` mode, only one answer can be `is_correct=True`. In `discussions` mode, multiple answers can be marked correct.

---

## File Locations

- Models: `addons/website_forum/models/`
  - `forum_forum.py` — `forum.forum` with all karma thresholds
  - `forum_post.py` — `forum.post` with voting, moderation, state machine
  - `forum_post_vote.py` — `forum.post.vote` karma calculations
  - `forum_tag.py` — `forum.tag` with creation karma check
  - `forum_post_reason.py` — `forum.post.reason` closing reasons
  - `gamification_challenge.py` — Gamification challenge extension
  - `gamification_karma_tracking.py` — Karma tracking extension
  - `res_users.py` — User extension: redirection data, forum CTA
  - `website.py` — Website extension: forum count, search integration
