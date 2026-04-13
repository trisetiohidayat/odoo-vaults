---
uuid: website-forum-l4-001
module: website_forum
tags:
  - #odoo
  - #odoo19
  - #modules
  - #website
  - #forum
  - #community
  - #gamification
  - #karma
level: L4
description: Full L4 documentation for website_forum - community Q&A with karma system, voting, moderation, badges, structured data SEO, and Jaccard-based related posts
related_modules:
  - forum
  - gamification
  - website
  - website_profile
depends_on:
  - forum
  - website
  - website_profile
  - gamification
  - auth_signup
created: 2026-04-11
updated: 2026-04-11
---

# website_forum

> **Module:** `website_forum` | **Path:** `~/odoo/odoo19/odoo/addons/website_forum/` | **Odoo Version:** 19
> **Category:** Website/Website | **Sequence:** 265 | **License:** LGPL-3
> **Assets bundle:** `web.assets_frontend` (interactions, components, SCSS, XML templates, tours)

## Overview

`website_forum` layers a public-facing, gamified community Q&A experience on top of the base `forum` module. Every write, vote, close, accept, flag, and comment operation passes through a karma gate. The module ships with 35 pre-configured badges (bronze/silver/gold) tied to gamification challenges, Schema.org structured data for SEO, Jaccard-similarity-based related posts, a per-website forum counter, and a full moderation queue system.

**Key architectural distinction from base `forum` module:** The base `forum` module (`addons/forum`) defines the models without karma thresholds or website integration. `website_forum` extends those models with karma-gated permissions, `mail.thread` followers, website-aware search, SEO metadata, and the gamification bridge.

---

## Dependency Chain

```
auth_signup          → enables public user registration (forum participation)
website_mail         → mail.thread, message_post, follower tracking
website_profile      → user profile pages, avatar, bio display
         ↓
website_forum        → karma, voting, moderation, badges, structured data
```

**`__manifest__.py` data files loaded (in order):**
- `data/ir_config_parameter_data.xml` — system parameters
- `data/forum_forum_template_faq.xml` — FAQ QWeb accordion template
- `data/forum_forum_data.xml` — demo/default forum creation
- `data/forum_post_reason_data.xml` — 12 close/reason records (see Close Reasons section)
- `data/ir_actions_data.xml` — server actions
- `data/mail_message_subtype_data.xml` — mt_question_new, mt_answer_new, mt_question_edit, mt_answer_edit
- `data/mail_templates.xml` — notification templates
- `data/website_menu_data.xml` — Forum menu entry
- `data/website_forum_tour.xml` — guided tour for new users
- `security/ir.model.access.csv` — ACL rules
- `security/ir_rule_data.xml` — record rules
- `data/gamification_badge_data_*.xml` — 4 badge definition files (~35 badges)
- `views/` — 11 XML view files

---

## Model Architecture

| File | Class | Model | L2 Role |
|------|-------|-------|---------|
| `models/forum_forum.py` | `ForumForum` | `forum.forum` | Karma thresholds, statistics, FAQ, welcome message, privacy |
| `models/forum_post.py` | `ForumPost` | `forum.post` | Voting, favorites, karma rights, moderation, SEO, hierarchy |
| `models/forum_tag.py` | `ForumTag` | `forum.tag` | Posts count, website URL, karma-gated creation |
| `models/forum_post_vote.py` | `ForumPostVote` | `forum.post.vote` | Vote record with karma delta on write |
| `models/forum_post_reason.py` | `ForumPostReason` | `forum.post.reason` | Close reason with type: basic vs offensive |
| `models/gamification_karma_tracking.py` | `GamificationKarmaTracking` | `gamification.karma.tracking` | Adds `forum.post` to karma origin selection |
| `models/gamification_challenge.py` | `GamificationChallenge` | `gamification.challenge` | Adds `forum` to challenge_category selection |
| `models/res_users.py` | `ResUsers` | `res.users` | `create_date` field re-expose, forum redirection link |
| `models/ir_attachment.py` | `IrAttachment` | `ir.attachment` | Karma-gated media dialog bypass |
| `models/website.py` | `Website` | `website` | `forum_count`, suggested controller, configurator footer link |

---

## `forum.forum` — `ForumForum`

**Inherits:** `mail.thread`, `image.mixin`, `website.seo.metadata`, `website.multi.mixin`, `website.searchable.mixin`
**Order:** `sequence, id`

### Complete Field Inventory

| Field | Type | Default | Stored | Notes |
|-------|------|---------|--------|-------|
| `name` | Char | required | Yes | `translate=True` |
| `sequence` | Integer | 1 | Yes | Controls ordering in multi-forum listings |
| `mode` | Selection | `'questions'` | Yes | `questions` = 1 answer max; `discussions` = unlimited |
| `privacy` | Selection | `'public'` | Yes | `public` \| `connected` \| `private` |
| `authorized_group_id` | Many2one `res.groups` | False | Yes | Only used when `privacy = 'private'` |
| `active` | Boolean | True | Yes | Archiving cascades to all posts via `write()` override |
| `faq` | Html | auto-generated | Yes | QWeb accordion rendered via `_render_template('website_forum.faq_accordion')` |
| `description` | Text | False | Yes | `translate=True` |
| `welcome_message` | Html | `_get_default_welcome_message()` | Yes | Full-width banner, `sanitize_attributes=False, sanitize_form=False` |
| `default_order` | Selection | `'last_activity_date desc'` | Yes | Visible sort dropdown on forum index |
| `relevancy_post_vote` | Float | `0.8` | Yes | Formula parameter `p` in relevancy sort |
| `relevancy_time_decay` | Float | `1.8` | Yes | Formula parameter `t` in relevancy sort |
| `allow_share` | Boolean | True | Yes | Enables social share prompt after post creation |
| `post_ids` | One2many `forum.post` | — | No | All posts (questions + answers) |
| `last_post_id` | Many2one `forum.post` | computed | Yes | Most recent active question |
| `total_posts` | Integer | computed | No | Questions only (`parent_id = False`, `state in ('active', 'close')`) |
| `total_views` | Integer | computed | No | Sum of `views` on questions |
| `total_answers` | Integer | computed | No | Sum of `child_count` on questions |
| `total_favorites` | Integer | computed | No | Count of questions with `favourite_count > 0` |
| `count_posts_waiting_validation` | Integer | computed | No | `state = 'pending'` count |
| `count_flagged_posts` | Integer | computed | No | `state = 'flagged'` count |
| `has_pending_post` | Boolean | computed | No | `@api.depends_context('uid')` — current user has pending question |
| `can_moderate` | Boolean | computed | No | `@api.depends_context('uid')` — current user karma >= `karma_moderate` |

### Karma Generation Fields

| Field | Default | Karma Effect | Recipient |
|-------|---------|-------------|-----------|
| `karma_gen_question_new` | 2 | +2 | Question author |
| `karma_gen_question_upvote` | 5 | +5 | Question author |
| `karma_gen_question_downvote` | -2 | -2 | Question author |
| `karma_gen_answer_upvote` | 10 | +10 | Answer author |
| `karma_gen_answer_downvote` | -2 | -2 | Answer author |
| `karma_gen_answer_accept` | 2 | +2 | Question author (for accepting) |
| `karma_gen_answer_accepted` | 15 | +15 | Answer author (when accepted) |
| `karma_gen_answer_flagged` | -100 | -100 | Post author (when marked offensive/spam) |

### Karma-Gated Action Thresholds

| Field | Own Threshold | All Threshold | Purpose |
|-------|-------------|--------------|---------|
| `karma_ask` | — | 3 | Post new questions |
| `karma_answer` | — | 3 | Post answers |
| `karma_edit_own` | 1 | 300 | Edit own / all posts |
| `karma_edit_retag` | — | 75 | Change question tags |
| `karma_close_own` | 100 | 500 | Close own / all posts |
| `karma_unlink_own` | 500 | 1000 | Delete own / all posts |
| `karma_tag_create` | — | 30 | Create new tags |
| `karma_upvote` | — | 5 | Upvote a post |
| `karma_downvote` | — | 50 | Downvote a post |
| `karma_answer_accept_own` | 20 | 500 | Accept answers on own / all questions |
| `karma_comment_own` | 1 | 1 | Comment on own / all posts |
| `karma_comment_convert_own` | 50 | 500 | Convert own / all comments to answers |
| `karma_comment_unlink_own` | 50 | 500 | Delete own / all comments |
| `karma_flag` | — | 500 | Flag a post as offensive |
| `karma_dofollow` | — | 500 | Remove `rel="nofollow"` from links |
| `karma_editor` | — | 30 | Post images and links in content |
| `karma_user_bio` | — | 750 | Display detailed user biography |
| `karma_post` | — | 100 | Auto-publish without pending moderation |
| `karma_moderate` | — | 1000 | Full moderation queue access |

### Computed Statistics — `_compute_forum_statistics`

Uses `_read_group` on `forum.post`:

```python
domain = [('forum_id', 'in', self.ids),
          ('state', 'in', ('active', 'close')),
          ('parent_id', '=', False)]
aggregates = ['__count', 'views:sum', 'child_count:sum', 'favourite_count:sum']
```

**Performance note:** This is a single SQL query per forum batch. `total_favorites` is incremented only when `favourite_count_sum > 0` to avoid false positives.

### Tag Usage — `_compute_tag_ids_usage`

Uses `search_read` ordered by `forum_id, posts_count DESC, name, id` and iterates once through the result set with a `defaultdict`. For each forum:
- Collects top `MOST_USED_TAGS_COUNT = 5` tags by `posts_count`
- Collects all tags where `posts_count in (0, None)` as unused

This avoids N+1 queries. The `MOST_USED_TAGS_COUNT` constant is a module-level guard against UI overflow.

### FAQ Auto-Generation — `_set_default_faq`

Called on `create()`:

```python
def _set_default_faq(self):
    for forum in self:
        forum.faq = self.env['ir.ui.view']._render_template(
            'website_forum.faq_accordion', {"forum": forum}
        )
```

The template renders the forum's `karma_*` field values into the FAQ accordion, making the karma requirements visible to all users.

### Privacy Transition — `write()`

```python
if 'privacy' in vals:
    if vals['privacy'] in ('public', 'connected'):
        vals['authorized_group_id'] = False
```

When a forum switches from `private` to public/connected, `authorized_group_id` is nullified. This is an automatic cascade — the group reference is invalidated immediately.

### Active Cascade — `write()`

```python
if 'active' in vals:
    self.env['forum.post'].with_context(active_test=False).search(
        [('forum_id', 'in', self.ids)]
    ).write({'active': vals['active']})
```

Forum archival/unarchival cascades to ALL posts (questions and answers) including inactive ones (`active_test=False`).

### Tag Parsing — `_tag_to_write_vals()`

Input format: comma-separated list where:
- `_tagname` (underscore prefix) = create new tag if user has `karma_tag_create` karma
- bare integer = existing tag ID to attach

Returns a write-compatible `[6, 0, [existing_ids]], [0, 0, {new_tag_dict}]]` structure.

### `_compute_website_url`

```python
return f'/forum/{self.env["ir.http"]._slug(self)}'
```

Returns the canonical forum URL. The forum slug is used as the primary route segment.

---

## `forum.post` — `ForumPost`

**Inherits:** `mail.thread`, `website.seo.metadata`, `website.searchable.mixin`
**Order:** `is_correct DESC, vote_count DESC, last_activity_date DESC`
**Mail headers:** `_CUSTOMER_HEADERS_LIMIT_COUNT = 0` — suppresses X-Msg-To mass mailing headers on forum posts (posts are not routed through the customer-mail system)

### Complete Field Inventory

| Field | Type | Default | Stored | Computed | Notes |
|-------|------|---------|--------|----------|-------|
| `name` | Char | False | Yes | — | Question title only |
| `forum_id` | Many2one | required | Yes | — | `index=True` |
| `content` | Html | False | Yes | — | `strip_style=True` on field; `sanitize=True` in view |
| `plain_content` | Text | computed | Yes | store | First 500 chars of stripped HTML |
| `tag_ids` | Many2many `forum.tag` | — | Yes | — | Via `forum_tag_rel` |
| `state` | Selection | `'active'` | Yes | — | active/pending/close/offensive/flagged |
| `views` | Integer | 0 | Yes | — | `readonly=True, copy=False` |
| `active` | Boolean | True | Yes | — | Soft delete flag |
| `website_message_ids` | One2many | — | No | — | `domain=[('model','=',self._name), ('message_type','in',['email','comment','email_outgoing'])]` |
| `website_url` | Char | computed | No | Yes | Q&A page URL |
| `website_id` | Many2one `website` | computed | No | Yes | `related='forum_id.website_id', store=True` |
| `create_date` | Datetime | now | Yes | — | `index=True` |
| `create_uid` | Many2one `res.users` | — | Yes | — | `index=True` |
| `write_date` | Datetime | — | Yes | — | `index=True` |
| `last_activity_date` | Datetime | `fields.Datetime.now` | Yes | — | Updated on answer/comment; `required=True` |
| `write_uid` | Many2one `res.users` | — | Yes | — | `index=True` |
| `relevancy` | Float | computed | Yes | store | Time-decay formula; used for default sort |
| `vote_ids` | One2many `forum.post.vote` | — | No | — | |
| `user_vote` | Integer | computed | No | Yes | Current user's vote: -1, 0, +1 |
| `vote_count` | Integer | computed | Yes | store | Net sum of votes |
| `favourite_ids` | Many2many `res.users` | — | Yes | — | Favorited-by users |
| `user_favourite` | Boolean | computed | No | Yes | Current user favorited |
| `favourite_count` | Integer | computed | Yes | store | |
| `is_correct` | Boolean | False | Yes | — | Accepted answer flag |
| `parent_id` | Many2one `forum.post` | False | Yes | — | `ondelete='cascade'`, `index=True`; `False` = question |
| `self_reply` | Boolean | computed | Yes | store | `create_uid == parent_id.create_uid` |
| `child_ids` | One2many `forum.post` | — | No | — | Answers; domain `forum_id=forum_id` |
| `child_count` | Integer | computed | Yes | store | |
| `uid_has_answered` | Boolean | computed | No | Yes | Current user posted an answer |
| `has_validated_answer` | Boolean | computed | Yes | store | Any `is_correct` among children |
| `flag_user_id` | Many2one `res.users` | — | Yes | — | Who flagged this post |
| `moderator_id` | Many2one `res.users` | — | Yes | — | Who reviewed (validated/offensive) |
| `closed_reason_id` | Many2one `forum.post.reason` | — | Yes | — | Why closed |
| `closed_uid` | Many2one `res.users` | — | Yes | — | Who closed |
| `closed_date` | Datetime | — | Yes | — | When closed |
| `karma_accept` | Integer | computed | No | No | Karma threshold for accept (own/all) |
| `karma_edit` | Integer | computed | No | No | Karma threshold for edit (own/all) |
| `karma_close` | Integer | computed | No | No | Karma threshold for close (own/all) |
| `karma_unlink` | Integer | computed | No | No | Karma threshold for unlink (own/all) |
| `karma_comment` | Integer | computed | No | No | Karma threshold for comment (own/all) |
| `karma_comment_convert` | Integer | computed | No | No | Karma threshold for comment conversion |
| `karma_flag` | Integer | computed | No | No | Karma threshold for flag |
| `can_ask` | Boolean | computed | No | No | |
| `can_answer` | Boolean | computed | No | No | |
| `can_accept` | Boolean | computed | No | No | |
| `can_edit` | Boolean | computed | No | No | |
| `can_close` | Boolean | computed | No | No | |
| `can_unlink` | Boolean | computed | No | No | |
| `can_upvote` | Boolean | computed | No | No | |
| `can_downvote` | Boolean | computed | No | No | |
| `can_comment` | Boolean | computed | No | No | |
| `can_comment_convert` | Boolean | computed | No | No | |
| `can_view` | Boolean | computed | No | No | Has custom search `_search_can_view` |
| `can_display_biography` | Boolean | computed | No | No | |
| `can_post` | Boolean | computed | No | No | |
| `can_flag` | Boolean | computed | No | No | |
| `can_moderate` | Boolean | computed | No | No | |
| `can_use_full_editor` | Boolean | computed | No | No | |

### Relevancy Formula — `_compute_relevancy`

```
relevancy = sign(vote_count) * (|vote_count - 1| ^ p) / (days + 2) ^ t
```

- `p = forum_id.relevancy_post_vote` (default 0.8)
- `t = forum_id.relevancy_time_decay` (default 1.8)
- `sign(vote_count)` = +1 if positive, -1 if negative, 0 if zero
- `(days + 2)` means at least 2-day denominator, preventing division by small numbers for new posts
- A 1-vote post scores 0; a 2-vote post scores 1 / (days+2)^t

This is a time-decay formula favoring both votes and recency. The non-integer exponents make the decay gradual rather than exponential.

### Vote Count Computation — `_compute_vote_count`

Uses `_read_group`:

```python
_groupby = ['post_id', 'vote']
aggregates = ['__count']
# Result: [(post, '1', 3), (post, '-1', 1)] for 3 upvotes, 1 downvote
# vote_count = 3*1 + 1*(-1) = 2
```

### Karma Rights — `_compute_post_karma_rights`

**Pattern:** Iterates over `self` (non-sudo) paired with `self.sudo()` for access to post content.

```python
for post, post_sudo in zip(self, self.sudo()):
    is_creator = post.create_uid == user
    post.karma_accept = post.forum_id.karma_answer_accept_own if post.parent_id.create_uid == user else post.forum_id.karma_answer_accept_all
    post.karma_edit = post.forum_id.karma_edit_own if is_creator else post.forum_id.karma_edit_all
    # ... etc
    post.can_upvote = is_admin or user.karma >= post.forum_id.karma_upvote or post.user_vote == -1
    post.can_downvote = is_admin or user.karma >= post.forum_id.karma_downvote or post.user_vote == 1
```

**Key logic:**
- `can_upvote`: Always True if user previously downvoted (letting them undo); same for `can_downvote` if previously upvoted.
- `can_view`: Complex SQL domain — allows viewing if the user can close (moderator), or if the post is active with a non-negative-karma author, or if the user is the author.
- `can_display_biography`: Requires author's karma >= forum's `karma_user_bio` AND author's `website_published = True`.

**Performance note:** Prefetching via `sudo()` on the batch prevents per-record sudo/switching overhead. All 14 karma fields compute in one pass per batch.

### `_search_can_view` — Custom Search Method

Returns raw SQL to avoid domain limitations:

```sql
SELECT p.id FROM forum_post p
  LEFT JOIN res_users u ON p.create_uid = u.id
  LEFT JOIN forum_forum f ON p.forum_id = f.id
WHERE
  (p.create_uid = %(uid)s AND f.karma_close_own <= %(karma)s)
  OR (p.create_uid != %(uid)s AND f.karma_close_all <= %(karma)s)
  OR (u.karma > 0 AND (p.active OR p.create_uid = %(uid)s))
```

This SQL implements the `can_view` logic for search queries and sitemaps, bypassing the ORM's normal access rules.

### `create()` — Karma-Gated Post Creation

```python
for post in posts:
    if post.parent_id and (post.parent_id.state == 'close' or ...):
        raise UserError  # cannot answer closed questions
    if not post.parent_id and not post.can_ask:
        raise AccessError  # need karma_ask to ask
    elif post.parent_id and not post.can_answer:
        raise AccessError  # need karma_answer to answer
    if not post.parent_id and not post.can_post:
        post.sudo().state = 'pending'  # needs moderation
    if not post.parent_id and post.state == 'active':
        post.create_uid.sudo()._add_karma(karma_gen_question_new, post, 'Ask a new question')
```

**Edge case:** If a question starts pending and is later validated, `_add_karma` is called in `validate()` (not double-called). The check `post.state == 'active'` at creation time gates immediate karma.

### `write()` — Trusted Keys and Multi-State Logic

```python
trusted_keys = ['active', 'is_correct', 'tag_ids']  # always allowed if can_* passes
# state transition checks add to trusted_keys:
if vals['state'] in ['active', 'close']:
    trusted_keys += ['state', 'closed_uid', 'closed_date', 'closed_reason_id']
elif vals['state'] == 'flagged':
    trusted_keys += ['state', 'flag_user_id']
```

**Moderation flow for is_correct:**
```python
if vals['is_correct'] != post.is_correct and post.create_uid.id != self.env.uid:
    # Not self-acceptance
    post.create_uid.sudo()._add_karma(karma_gen_answer_accepted * mult, post, ...)
    self.env.user.sudo()._add_karma(karma_gen_answer_accept * mult, post, ...)
```

Self-acceptance grants no karma (to prevent karma farming). The `mult` is +1 for accept, -1 for un-accept.

### `_update_content()` — Content Filtering

```python
# Layer 1: Nofollow
if user.karma < forum.karma_dofollow:
    for match in re.findall(r'<a\s.*href=".*?">', content):
        content = re.sub(escaped_match, f'<a rel="nofollow" href="{url}">', content)

# Layer 2: Block images and styled links
if user.karma < forum.karma_editor:
    filter_regexp = r'(<img.*?>)|(<a[^>]*?href[^>]*?>)|(<[a-z|A-Z]+[^>]*style\s*=\s*[\'"][^\'"]*\s*background[^:]*:[^url;]*url)'
    if re.search(filter_regexp, content, re.I):
        raise AccessError  # 30 karma to use images/links
```

**Security note:** The `strip_style=True` on the field definition strips inline styles at ORM level, but `_update_content` is called before storage and handles the runtime enforcement of the karma gate.

### Vote Acceptance Toggle — `vote(upvote=True)`

```python
# Toggle logic:
if existing_vote:
    if upvote:
        new_vote_value = '0' if existing_vote.vote == '-1' else '1'  # undo or reinforce
    else:
        new_vote_value = '0' if existing_vote.vote == '1' else '-1'
else:
    new_vote_value = '1' if upvote else '-1'
```

**Key behavior:** Voting the same direction again removes the vote (value = '0'). Voting the opposite direction switches it. This is important for karma: switching from upvote to downvote means `karma_gen_answer_downvote - karma_gen_answer_upvote` (net -12 by default).

### Convert Answer to Comment — `convert_answer_to_comment()`

Uses the post's original author (via `sudo`) to create the `mail.message` record, ensuring `create_uid` on the message is set correctly:

```python
new_message = question.with_user(self_sudo.create_uid.id)\
    .with_context(mail_post_autofollow_author_skip=True)\
    .sudo().message_post(**values).sudo(False)
```

The post is then `sudo().unlink()` via SUPERUSER_ID to bypass karma checks.

### Convert Comment to Answer — `convert_comment_to_answer(message_id)`

**Edge cases handled:**
- Returns `False` if comment has no author or author has no user account
- Returns `False` if comment author already answered the question (no duplicate answers)
- Karma check distinguishes own vs all comments (`karma_comment_convert_own` vs `_all`)

The `comment_sudo.body` (raw HTML from the message) becomes the new post's content.

### `_notify_state_update()` — Mail Notifications

| Post state | Notification target | Template | Subtype |
|-----------|-------------------|---------|---------|
| `active` + question | Followers + tagged partners | `website_forum.forum_post_template_new_question` | `website_forum.mt_question_new` |
| `active` + answer | Question followers + tagged partners | `website_forum.forum_post_template_new_answer` | `website_forum.mt_answer_new` |
| `pending` + question | Moderators (partners with karma >= `karma_moderate`) | `website_forum.forum_post_template_validation` | `mail.mt_note` |

**Note:** Pending answers are never notified — only questions go to the validation queue.

### Close and Reopen — Karma Penalties

```python
# On close as spam/offensive (reason_7, reason_8):
karma = karma_gen_answer_flagged  # -100
if reason_id == reason_spam and count_post == 1:
    karma *= 10  # first post: -1000 karma
post.create_uid.sudo()._add_karma(karma, post, message)

# On reopen:
karma = karma_gen_answer_flagged * -1  # +100
if reason_id == reason_spam and count_post == 1:
    karma *= 10  # was first spam: +1000
post.create_uid.sudo()._add_karma(karma * -1, ...)  # reverses the penalty
```

The first-post multiplier means a user's very first spam/offensive post results in a -1000 karma swing (making them effectively banned from participating).

### `_set_viewed()` — View Counter

```python
def _set_viewed(self):
    self.ensure_one()
    return sql.increment_fields_skiplock(self, 'views')
```

Uses `FOR UPDATE SKIP LOCKED` for atomic concurrent increment without row locks. Multiple simultaneous visitors do not block each other — each request skips the lock if held and proceeds.

### Structured Data (SEO) — `_get_microdata()` and `_get_structured_data()`

Returns a JSON-LD `QAPage` schema (Schema.org) when:
1. The post is a question (`parent_id = False`)
2. There is at least one suggested answer or accepted answer

```python
structured_data = {
    "@context": "https://schema.org",
    "@type": "QAPage",
    "mainEntity": { "@type": "Question", "name": ..., "text": ..., "answerCount": ... }
}
if correct_posts:
    structured_data["mainEntity"]["acceptedAnswer"] = { "@type": "Answer", ... }
if suggested_posts[:5]:
    structured_data["mainEntity"]["suggestedAnswer"] = [...]  # max 5
```

Author URL is only included if `website_published = True`.

### Related Posts — `_get_related_posts()`

Uses raw SQL with Jaccard similarity:

```sql
SELECT forum_post.id,
  COUNT(DISTINCT intersection_tag_rel.forum_tag_id)::DECIMAL
  / COUNT(DISTINCT union_tag_rel.forum_tag_id)::DECIMAL AS similarity
FROM forum_post
JOIN forum_tag_rel AS intersection_tag_rel
  ON intersection_tag_rel.forum_post_id = forum_post.id
  AND intersection_tag_rel.forum_tag_id = ANY(%(tag_ids)s)
RIGHT JOIN forum_tag_rel AS union_tag_rel
  ON union_tag_rel.forum_post_id = forum_post.id
  OR union_tag_rel.forum_post_id = %(current_post_id)s
WHERE id != %(current_post_id)s
GROUP BY forum_post.id
ORDER BY similarity DESC, last_activity_date DESC
LIMIT 5
```

**Jaccard formula:** `|tags_A ∩ tags_B| / |tags_A ∪ tags_B|`. Tags are forum-specific so intersection is always within the same forum. Returns empty recordset if post has no tags.

### Messaging Overrides

- `_mail_get_operation_for_mail_message_operation`: For `write`/`unlink` operations on messages attached to forum posts, only posts where `can_edit = True` are included.
- `_notify_thread_by_inbox`: Comments (`message_type == 'comment'`) do not generate inbox notifications — only emails (prevents notification spam on high-traffic posts).
- `message_post`: When posting a comment, question followers are explicitly added to `partner_ids` (bypassing the parent post's follower subscription) so comment authors get notified.

### `_constrains` and Cycle Detection

```python
@api.constrains('parent_id')
def _check_parent_id(self):
    if self._has_cycle():
        raise ValidationError(_('You cannot create recursive forum posts.'))
```

Enforced via `_has_cycle()` (standard Odoo mechanism for self-referential Many2one). Maximum nesting depth is 1 level (question -> answers only, no answer -> sub-answers).

---

## `forum.post.vote` — `ForumPostVote`

**Inherits:** None

| Field | Type | Default | Stored | Notes |
|-------|------|---------|--------|-------|
| `post_id` | Many2one `forum.post` | required | Yes | `ondelete='cascade'`, `index=True` |
| `user_id` | Many2one `res.users` | `self.env.uid` | Yes | Cannot be changed by non-admin |
| `vote` | Selection `[('1','1'),('-1','-1'),('0','0')]` | `'1'` | Yes | |
| `create_date` | Datetime | now | Yes | `index=True` |
| `forum_id` | Many2one `forum.forum` | related | Yes | `index='btree_not_null'` |
| `recipient_id` | Many2one `res.users` | related | Yes | `post_id.create_uid` |

**Unique constraint:** `unique(post_id, user_id)` — one vote per user per post.

### Karma Update — `_vote_update_karma()`

Distinguishes question vs answer by `post_id.parent_id`:

```python
if self.post_id.parent_id:  # is an answer
    karma, reason = self._get_karma_value(
        old_vote, new_vote,
        self.forum_id.karma_gen_answer_upvote,    # +10
        self.forum_id.karma_gen_answer_downvote)  # -2
else:  # is a question
    karma, reason = self._get_karma_value(
        old_vote, new_vote,
        self.forum_id.karma_gen_question_upvote,   # +5
        self.forum_id.karma_gen_question_downvote) # -2
```

**Karma delta formula:**
```
delta = karma_values[new_vote] - karma_values[old_vote]
```
Example: switching from upvote to downvote on an answer: `(−2) − (+10) = −12`.

### Rights Checks

- **Own post:** Cannot vote on own post (checked in `_check_general_rights`)
- **Vote ownership:** Cannot modify another user's vote
- **Karma gate:** Upvote requires `can_upvote`, downvote requires `can_downvote`

---

## `forum.tag` — `ForumTag`

**Inherits:** `mail.thread`, `website.searchable.mixin`, `website.seo.metadata`

| Field | Type | Default | Stored | Notes |
|-------|------|---------|--------|-------|
| `name` | Char | required | Yes | `unique(name, forum_id)` constraint |
| `color` | Integer | False | Yes | Color index for UI |
| `forum_id` | Many2one `forum.forum` | required | Yes | `index=True` |
| `post_ids` | Many2many `forum.post` | — | No | Domain: `state='active'` |
| `posts_count` | Integer | computed | Yes | store; `depends: post_ids, post_ids.tag_ids, post_ids.state, post_ids.active` |
| `website_url` | Char | computed | No | `/forum/{forum}/tag/{tag}/questions` |

**Constraint:** `unique(name, forum_id)` — same tag name can exist in different forums.

**Karma-gated creation:** `create()` checks `user.karma >= forum.karma_tag_create` (default 30) before allowing creation.

**`website.searchable.mixin`:** Enables tag search via the website search bar with type `forum_tags_only`.

---

## `forum.post.reason` — `ForumPostReason`

**Inherits:** None

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | required | `translate=True` |
| `reason_type` | Selection `[('basic','Basic'),('offensive','Offensive')]` | `'basic'` | Controls which close UI is shown |

**12 pre-seeded reasons:**

| XML ID | Name | Type |
|--------|------|------|
| `reason_1` | Duplicate post | basic |
| `reason_2` | Off-topic or not relevant | basic |
| `reason_3` | Too subjective and argumentative | basic |
| `reason_4` | Not a real post | basic |
| `reason_6` | Not relevant or outdated | basic |
| `reason_7` | Contains offensive or malicious remarks | basic (but used as offensive threshold in code) |
| `reason_8` | Spam or advertising | basic (also used as spam threshold in `mark_as_offensive_batch`) |
| `reason_9` | Too localized | basic |
| `reason_11` | Insulting and offensive language | offensive |
| `reason_12` | Violent language | offensive |
| `reason_13` | Inappropriate and unacceptable statements | offensive |
| `reason_14` | Threatening language | offensive |
| `reason_15` | Racist and hate speech | offensive |

**Note:** `reason_5` and `reason_10` are missing from the data file (presumably deleted or reserved).

---

## Gamification — Badge System

All challenges use `period = 'once'` (one-time award), `visibility_mode = 'personal'`, `report_message_frequency = 'never'`, `reward_realtime = True` (instant award), and `user_domain = [('karma', '>', 0)]`.

### Question Badges (`gamification_badge_data_question.xml`)

| Badge | Level | Goal | Condition |
|-------|-------|------|-----------|
| Popular Question | bronze | 1 | `parent_id = False`, `views >= 150` |
| Notable Question | silver | 1 | `parent_id = False`, `views >= 250` |
| Famous Question | gold | 1 | `parent_id = False`, `views >= 500` |
| Credible Question | bronze | 1 | `parent_id = False`, `favourite_count >= 1` |
| Favorite Question | silver | 1 | `parent_id = False`, `favourite_count >= 5` |
| Stellar Question | bronze | 1 | `parent_id = False`, `favourite_count >= 25` |
| Student | gold | 1 | `parent_id = False`, `vote_count >= 1` |
| Nice Question | bronze | 1 | `parent_id = False`, `vote_count >= 4` |
| Good Question | silver | 1 | `parent_id = False`, `vote_count >= 6` |
| Great Question | gold | 1 | `parent_id = False`, `vote_count >= 15` |
| Scholar | gold | 1 | `parent_id = False`, `has_validated_answer = True` |

### Answer Badges (`gamification_badge_data_answer.xml`)

| Badge | Level | Goal | Condition |
|-------|-------|------|-----------|
| Teacher | bronze | 1 | `parent_id != False`, `vote_count >= 3` |
| Nice Answer | bronze | 1 | `parent_id != False`, `vote_count >= 4` |
| Good Answer | silver | 1 | `parent_id != False`, `vote_count >= 6` |
| Great Answer | gold | 1 | `parent_id != False`, `vote_count >= 15` |
| Enlightened | silver | 1 | `parent_id != False`, `vote_count >= 3`, `is_correct = True` |
| Guru | silver | 1 | `parent_id != False`, `vote_count >= 15`, `is_correct = True` |
| Self-Learner | gold | 1 | `self_reply = True`, `vote_count >= 4` |

### Participation Badges (`gamification_badge_data_participation.xml`)

| Badge | Level | Goal | Source |
|-------|-------|------|--------|
| Autobiographer | bronze | 1 | Profile: country + city + email set |
| Commentator | bronze | 10 | `mail.message` type=comment, model=forum.post |
| Pundit | silver | 10 | forum.post answers with vote_count >= 10 |
| Chief Commentator | silver | 100 | Same as Commentator, goal=100 |
| Taxonomist | silver | 1 | forum.tag `posts_count >= 15` (tag created by user) |

### Moderation Badges (`gamification_badge_data_moderation.xml`)

| Badge | Level | Goal | Condition |
|-------|-------|------|-----------|
| Supporter | gold | 1 | First upvote on any post |
| Critic | bronze | 1 | First downvote on any post |
| Disciplined | bronze | 1 | Deleted own post with vote_count >= 3 |
| Editor | gold | 1 | First edit on any forum post |
| Peer Pressure | gold | 1 | Deleted own post with vote_count <= -3 |

### Karma Tracking — `GamificationKarmaTracking`

```python
def _get_origin_selection_values(self):
    return super()._get_origin_selection_values() + [
        ('forum.post', self.env['ir.model']._get('forum.post').display_name)
    ]
```

This registers `forum.post` as a karma origin type, so every `_add_karma` call sourced from a forum post records the post's ID in `gamification.karma.tracking.origin_id`.

### Challenge Category — `GamificationChallenge`

```python
challenge_category = fields.Selection(selection_add=[('forum', 'Website / Forum')], ...)
```

Adds 'forum' as a valid challenge category, enabling gamification administrators to create forum-specific challenge groups in Gamification > Challenges.

---

## `res.users` Extension — `ResUsers`

| Addition | Purpose |
|----------|---------|
| `create_date` field re-expose | Displayed on forum user profile pages |
| `open_website_url()` | Wrapper calling `partner_id.open_website_url()` |
| `get_gamification_redirection_data()` | Appends `{'label': 'See our Forum', 'url': '/forum'}` to badge notification links |

---

## `ir.attachment` Extension — `IrAttachment`

```python
def _can_bypass_rights_on_media_dialog(self, **attachment_data):
    if (res_model == 'forum.post' and res_id
        and self.env['forum.post'].browse(res_id).can_use_full_editor):
        return True
    return super()._can_bypass_rights_on_media_dialog(...)
```

Enables the media dialog (image upload via the WYSIWYG editor) for forum posts when the user has `karma_editor` (30). Without this, the standard attachment ACL would block the upload even if the user has edit rights on the post.

---

## `website` Extension — `Website`

| Addition | Purpose |
|----------|---------|
| `forum_count` field | Cached count of forums visible to this website |
| `_update_forum_count()` | Called on forum `create()`/`write()`/`unlink()` and website `create()` |
| `get_suggested_controllers()` | Adds Forum link to website configurator |
| `configurator_get_footer_links()` | Adds Forum to configurator footer |
| `configurator_set_menu_links()` | Removes Forum from top menu (footer only) |
| `_search_get_details()` | Registers forums, posts, tags in website search |

```python
def _update_forum_count(self):
    forums_all = self.env['forum.forum'].search([])
    for website in websites:
        website.forum_count = len(forums_all.filtered_domain(website.website_domain()))
```

**Performance note:** Uses `filtered_domain` on the full forum set rather than `search_count` per website, reducing the number of SQL queries when multiple websites are updated simultaneously.

---

## Controller — `WebsiteForum`

**Extends:** `WebsiteProfile`
**Constants:** `_post_per_page = 10`, `_user_per_page = 30`

### Route Map

| Route | Auth | Method | Purpose |
|-------|------|--------|---------|
| `GET /forum` | public | `forum()` | Redirect to single forum or render `forum_all` |
| `GET /forum/all[/page/N]` | public | `questions()` | All forums, paginated |
| `GET /forum/<forum>[/page/N]` | public | `questions()` | Single forum questions |
| `GET /forum/<forum>/tag/<tag>/questions` | public | `questions()` | Tag-filtered questions |
| `GET /forum/<forum>/faq` | public | `forum_faq()` | Forum guidelines |
| `GET /forum/<forum>/faq/karma` | public | `forum_faq_karma()` | Karma requirement details |
| `GET /forum/<forum>/ask` | user | `forum_post()` | New question form (requires valid email) |
| `POST /forum/<forum>/new` | user | `post_create()` | Create question |
| `POST /forum/<forum>/<parent>/reply` | user | `post_create()` | Post answer |
| `GET /forum/<forum>/post/<post>/edit` | user | `post_edit()` | Edit form |
| `POST /forum/<forum>/post/<post>/save` | user | `post_save()` | Save edit |
| `POST /forum/<forum>/post/<post>/comment` | user | `post_comment()` | Post comment |
| `GET/POST /forum/<forum>/post/<post>/delete` | user | `post_delete()` | Delete (soft) |
| `JSON /forum/<forum>/post/<post>/upvote` | user | `post_upvote()` | Upvote toggle |
| `JSON /forum/<forum>/post/<post>/downvote` | user | `post_downvote()` | Downvote toggle |
| `JSON /forum/<forum>/post/<post>/toggle_correct` | user | `post_toggle_correct()` | Accept/unaccept answer |
| `GET /forum/<forum>/question/<q>/ask_for_close` | user | `question_ask_for_close()` | Close form |
| `POST /forum/<forum>/question/<q>/close` | user | `question_close()` | Execute close |
| `POST /forum/<forum>/question/<q>/reopen` | user | `question_reopen()` | Reopen |
| `POST /forum/<forum>/question/<q>/delete` | user | `question_delete()` | Soft delete |
| `POST /forum/<forum>/question/<q>/undelete` | user | `question_undelete()` | Restore |
| `JSON /forum/<forum>/post/<post>/flag` | user | `post_flag()` | Flag as offensive |
| `GET /forum/<forum>/post/<post>/ask_for_mark_as_offensive` | user | `post_http_ask_for_mark_as_offensive()` | Offensive form |
| `POST /forum/<forum>/post/<post>/mark_as_offensive` | user | `post_mark_as_offensive()` | Mark offensive |
| `GET /forum/<forum>/validation_queue` | user+karma | `validation_queue()` | Pending posts |
| `GET /forum/<forum>/flagged_queue` | user+karma | `flagged_queue()` | Flagged posts |
| `GET /forum/<forum>/offensive_posts` | user+karma | `offensive_posts()` | Offensive archive |
| `GET /forum/<forum>/closed_posts` | user+karma | `closed_posts()` | Closed posts |
| `GET /forum/<forum>/post/<post>/validate` | user+karma | `post_accept()` | Approve post |
| `GET /forum/<forum>/post/<post>/refuse` | user+karma | `post_refuse()` | Refuse post |
| `GET /forum/<forum>/partner/<int:pid>` | public | `open_partner()` | Redirect to user profile |
| `GET /forum/get_tags` | public | `tag_read()` | Autocomplete for tag input |

### Search Options — `_get_forum_post_search_options()`

Controls which domain filters are applied during question listing and search:

| Option | Values | Effect |
|--------|--------|--------|
| `filters` | `all`, `unanswered`, `solved`, `unsolved` | Domain on child_ids, has_validated_answer |
| `my` | `mine`, `followed`, `tagged`, `favourites`, `upvoted` | Domain on create_uid, message_partner_ids, favourite_ids, vote_ids |
| `tag` | tag ID string | Domain on tag_ids |
| `forum` | forum ID string | Domain on forum_id |
| `include_answers` | bool | If True, removes `parent_id = False` domain (shows answers too) |
| `create_uid` | user ID | Domain on create_uid (for "user's posts" view) |

### Profile Page — `_prepare_open_forum_user()`

Shows:
- User's questions and answers (capped at 20 for non-moderators)
- Questions the user is following
- Favorite questions
- Votes received (up/down breakdown)
- Votes given
- Recent activity (comments/edits via mail.message)

**Performance note:** The `activity` query joins `mail.message` against a pre-filtered `forum.post` domain. Without the cap at 20 for non-moderators, this could return thousands of records for active users.

### Batch Offensive Marking — `mark_as_offensive_batch()`

Filters posts by `key` (grouping criterion) and marks all matching posts as offensive with reason `reason_8` (spam):

```python
if key == 'create_uid':
    spams = self.filtered(lambda x: x.create_uid.id in values)
elif key == 'country_id':
    spams = self.filtered(lambda x: x.create_uid.country_id.id in values)
elif key == 'post_id':
    spams = self.filtered(lambda x: x.id in values)
return spams._mark_as_offensive(reason_id)
```

Used by moderators to ban/spam users or specific posts in bulk.

---

## Cross-Module Integration

| Integration Point | Module | Mechanism |
|------------------|--------|-----------|
| User karma | `website_profile` | `_add_karma()` on `res.users` via `sudo()` |
| Mail notifications | `mail` | `mail.thread`, `message_post`, `mail_followers` |
| Badges | `gamification` | Challenges with `challenge_category = 'forum'` |
| Karma tracking | `gamification` | `gamification.karma.tracking` origin registration |
| Images/attachments | `web` | `_can_bypass_rights_on_media_dialog` hook |
| Website routing | `website` | `website.multi.mixin`, `website.seo.metadata`, `website.searchable.mixin` |
| User registration | `auth_signup` | Email validation before posting |
| OAuth | `auth_oauth` / `auth_google` | Handled upstream via `website_profile` |

---

## Performance Considerations

1. **`_compute_forum_statistics`**: Single `_read_group` per forum batch — O(1) query regardless of post count.
2. **`_set_viewed()`**: `increment_fields_skiplock` avoids lock contention under concurrent load.
3. **`_get_related_posts()`**: Raw SQL with Jaccard similarity avoids Python-side tag comparisons and uses a single `GROUP BY` query.
4. **`_compute_tag_ids_usage`**: Single `search_read` call instead of N `search_count` calls per tag.
5. **`post_display_limit = 20`**: Non-moderator profile pages cap visible posts to prevent N+1 on the activity timeline.
6. **`forum_count`**: Cached on website; updated only on forum CRUD, not on every page load.
7. **Vote count**: Stored (`store=True`) so sorting by vote count does not require re-aggregation.
8. **`has_validated_answer`**: Stored so filtering by "solved" questions avoids scanning answers.
9. **`relevancy`**: Stored so relevance sorting is a simple index-ordered read, not a formula recomputation.

---

## Security Considerations

1. **Karma as capability system**: Every write on `forum.post` checks computed karma rights before allowing the operation. Admin bypasses all checks via `is_admin()`.
2. **Vote ownership immutability**: `create()` and `write()` on `forum.post.vote` strip `user_id` for non-admins, preventing vote impersonation.
3. **Content sanitization**: `_update_content()` enforces `karma_editor` before images/links are accepted, stopping spam at the source.
4. **Nofollow injection**: Links by users below `karma_dofollow` get `rel="nofollow"` injected regardless of original markup.
5. **Moderator-only visibility**: Posts with `state = 'flagged'` and authors with negative karma are hidden from non-moderators via `_search_can_view`.
6. **Attachment ACL bypass**: The `_can_bypass_rights_on_media_dialog` override is scoped to `forum.post` records only, not a blanket bypass.
7. **Closed post locking**: Answers cannot be posted to closed or deleted questions — enforced in `create()` with `UserError`.
8. **Self-acceptance prevention**: Answer acceptance grants karma only when `create_uid != self.env.uid` — prevents karma farming.

---

## Edge Cases and Failure Modes

1. **Tag name uniqueness**: `unique(name, forum_id)` allows duplicate tag names across forums. Users might confuse tags if forum names are similar.
2. **First spam post = 10x karma penalty**: A user's first spam/offensive post results in -1000 karma (via `karma_gen_answer_flagged * 10`), likely making them unable to post further.
3. **Reopening does not cascade**: `reopen()` only reopens the question. Answers remain in their current state (offensive/closed).
4. **Answer deactivation does not cascade**: Archiving/unarchiving a post via `active` toggle cascades to answers, but reactivation via `undelete` does NOT cascade to answers.
5. **Self-reply detection**: `self_reply` is computed at write time and stored. If a question's author changes, existing self-replies are not retroactively updated.
6. **Moderator email routing**: Pending question notifications go to all moderators via `partner_ids` filtered by karma threshold. If a moderator has no user account, they won't be notified.
7. **Duplicate answer prevention**: `convert_comment_to_answer()` returns `False` if the author already has an answer on the question. The UI handles this silently.
8. **Anonymous user vote**: `user_vote` computes as 0 for anonymous/public users (no `uid`), which correctly prevents voting without authentication.
9. **Relevancy formula**: The formula can produce very small float values for old zero-vote posts due to `(days+2)^t` in the denominator. Not an error, just visually near-zero.
10. **Forum slug collisions**: If two forums have identical `name` slugs, routing may be ambiguous. `website.multi.mixin` scope should disambiguate by website.

---

## Odoo 18 → 19 Changes

Key changes from Odoo 18 to 19 in `website_forum`:

| Area | Change | Impact |
|------|--------|--------|
| Structured data | `_get_microdata()` added for Schema.org QAPage | SEO improvement; new method |
| Related posts | `_get_related_posts()` with Jaccard similarity added | New feature replacing simple tag filter |
| View counter | `_set_viewed()` uses `increment_fields_skiplock` | Reduced lock contention on high-traffic posts |
| Vote toggle | Vote value now `'1'`/`'-1'`/`'0'` (string selection) | Consistent with stored representation |
| Karma rights | `can_use_full_editor` field added | Separates image/link permission from edit |
| Mail notification | `_notify_thread_by_inbox` override | Comments no longer generate inbox notifications |
| Badge challenges | All challenges use `period='once'` | Badge system fully migrated to instant reward |
| Website forum count | `_update_forum_count()` on website model | Multi-website forum visibility tracking |
| Content filtering | `_update_content()` uses `sanitize_attributes=False` + runtime nofollow injection | More flexible content with karma-based nofollow |
| Message operation filtering | `_mail_get_operation_for_mail_message_operation` override | Only `can_edit` users can write/unlink messages |
| Comment→answer conversion | `convert_comment_to_answer()` handles pre-existing answer check | Prevents duplicate answers from comment conversion |
| Badge category | `gamification_challenge` adds `'forum'` category | Forum-specific challenges now manageable via standard UI |

---

## Related Documentation

- [Modules/forum](Modules/forum.md) — Base forum models (forum.forum, forum.post, forum.tag, forum.post.vote) — no karma/website layer
- [Modules/Gamification](Modules/gamification.md) — Challenge and badge awarding system
- [Modules/Website](Modules/website.md) — Multi-website support, page routing, SEO metadata
- [Modules/website_profile](Modules/website_profile.md) — User profile, karma display, avatar
- [Core/API](Core/API.md) — `@api.depends_context('uid')` for per-user karma rights
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine: active → pending → close/flagged/offensive
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — Karma as ACL replacement for public communities
