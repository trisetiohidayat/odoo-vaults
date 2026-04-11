# website_forum - Forum and Community Q&A Platform

## Overview

The `website_forum` module provides a complete forum system for website communities. It enables users to ask questions, provide answers, vote on content, and earn karma through participation. The module integrates with Odoo's gamification system for badges and challenges.

## Module Information

- **Technical Name**: `website_forum`
- **Location**: `addons/website_forum/`
- **Depends**: `website`, `gamification`, `mail`
- **License**: LGPL-3

---

## Models

### forum.forum

**File**: `models/forum_forum.py`

Main forum configuration model:

```python
class Forum(models.Model):
    _name = 'forum.forum'
    _description = 'Forum'
    _inherit = [
        'mail.thread',
        'image.mixin',
        'website.seo.metadata',
        'website.multi.mixin',
        'website.searchable.mixin',
    ]
    _order = "sequence, id"
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Forum name (required, translatable) |
| `sequence` | Integer | Display order |
| `mode` | Selection | 'questions' (1 answer) or 'discussions' (multiple) |
| `privacy` | Selection | 'public', 'connected', 'private' |
| `authorized_group_id` | Many2one | Group for private forums |
| `active` | Boolean | Forum active status |
| `faq` | Html | Guidelines/help text |
| `description` | Text | Forum description |
| `welcome_message` | Html | Landing page message |
| `default_order` | Selection | Default sort order |
| `relevancy_post_vote` | Float | First relevance parameter |
| `relevancy_time_decay` | Float | Second relevance parameter |
| `allow_share` | Boolean | Enable social sharing |

**Post Statistics** (computed):
| Field | Type | Description |
|-------|------|-------------|
| `post_ids` | One2many | All posts in forum |
| `total_posts` | Integer | # Posts |
| `total_views` | Integer | # Views |
| `total_answers` | Integer | # Answers |
| `total_favorites` | Integer | # Favorites |
| `count_posts_waiting_validation` | Integer | Pending posts |
| `count_flagged_posts` | Integer | Flagged posts |

**Karma Generation Fields**:
| Field | Default | Description |
|-------|---------|-------------|
| `karma_gen_question_new` | 2 | Asking a question |
| `karma_gen_question_upvote` | 5 | Question upvoted |
| `karma_gen_question_downvote` | -2 | Question downvoted |
| `karma_gen_answer_upvote` | 10 | Answer upvoted |
| `karma_gen_answer_downvote` | -2 | Answer downvoted |
| `karma_gen_answer_accept` | 2 | Accepting an answer |
| `karma_gen_answer_accepted` | 15 | Answer accepted |
| `karma_gen_answer_flagged` | -100 | Answer flagged as offensive |

**Karma-Based Permission Fields**:
| Field | Default | Description |
|-------|---------|-------------|
| `karma_ask` | 3 | Ask questions |
| `karma_answer` | 3 | Answer questions |
| `karma_edit_own` | 1 | Edit own posts |
| `karma_edit_all` | 300 | Edit all posts |
| `karma_edit_retag` | 75 | Change tags |
| `karma_close_own` | 100 | Close own posts |
| `karma_close_all` | 500 | Close all posts |
| `karma_unlink_own` | 500 | Delete own posts |
| `karma_unlink_all` | 1000 | Delete all posts |
| `karma_tag_create` | 30 | Create tags |
| `karma_upvote` | 5 | Upvote |
| `karma_downvote` | 50 | Downvote |
| `karma_answer_accept_own` | 20 | Accept answer on own questions |
| `karma_answer_accept_all` | 500 | Accept any answer |
| `karma_comment_own` | 1 | Comment own posts |
| `karma_comment_all` | 1 | Comment all posts |
| `karma_flag` | 500 | Flag as offensive |
| `karma_dofollow` | 500 | Nofollow links threshold |
| `karma_editor` | 30 | Use editor features |
| `karma_user_bio` | 750 | Display biography |
| `karma_post` | 100 | Post without validation |
| `karma_moderate` | 1000 | Moderate posts |

**Tag Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `tag_ids` | One2many | Tags in forum |
| `tag_most_used_ids` | One2many | Most used tags (computed) |
| `tag_unused_ids` | One2many | Unused tags (computed) |

**Key Methods**:

```python
# Convert tag string to write vals
def _tag_to_write_vals(self, tags=''):
    """Parse tag string and create new tags if user has karma"""

# Get first letters of available tags
def _get_tags_first_char(self, tags=None):
    """Used for tag browsing navigation"""

# Set default FAQ from template
def _set_default_faq(self):
    """Initialize FAQ from 'website_forum.faq_accordion' template"""

# Website URL computation
def _compute_website_url(self):
    return f'/forum/{self.env["ir.http"]._slug(self)}'
```

---

### forum.post

**File**: `models/forum_post.py`

Forum posts (questions and answers):

```python
class Post(models.Model):
    _name = 'forum.post'
    _description = 'Forum Post'
    _inherit = [
        'mail.thread',
        'website.seo.metadata',
        'website.searchable.mixin',
    ]
    _order = "is_correct DESC, vote_count DESC, last_activity_date DESC"
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Title (for questions only) |
| `forum_id` | Many2one | Parent forum |
| `content` | Html | Post content |
| `plain_content` | Text | Plain text version (computed) |
| `tag_ids` | Many2many | Associated tags |
| `state` | Selection | Status: active/pending/close/offensive/flagged |
| `views` | Integer | View count |
| `active` | Boolean | Active status |
| `last_activity_date` | Datetime | Last activity timestamp |
| `relevancy` | Float | Relevance score (computed) |

**Vote Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `vote_ids` | One2many | All votes on post |
| `user_vote` | Integer | Current user's vote (computed) |
| `vote_count` | Integer | Total vote score (computed) |

**Favorite Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `favourite_ids` | Many2many | Users who favorited |
| `user_favourite` | Boolean | Current user favorited (computed) |
| `favourite_count` | Integer | Favorite count (computed) |

**Hierarchy Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `is_correct` | Boolean | Correct/accepted answer |
| `parent_id` | Many2one | Parent question (for answers) |
| `self_reply` | Boolean | Self-reply flag (computed) |
| `child_ids` | One2many | Answers to this post |
| `child_count` | Integer | Answer count (computed) |
| `uid_has_answered` | Boolean | Current user answered (computed) |
| `has_validated_answer` | Boolean | Has accepted answer (computed) |

**Moderation Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `flag_user_id` | Many2one | User who flagged |
| `moderator_id` | Many2one | Moderator who reviewed |

**Karma Permission Fields** (computed based on forum settings):
- `karma_accept`, `karma_edit`, `karma_close`, `karma_unlink`
- `karma_comment`, `karma_comment_convert`, `karma_flag`
- `can_ask`, `can_answer`, `can_accept`, `can_edit`
- `can_close`, `can_unlink`, `can_upvote`, `can_downvote`
- `can_comment`, `can_comment_convert`, `can_view`
- `can_display_biography`, `can_post`, `can_flag`, `can_moderate`

**Key Methods**:

```python
# Update content with karma-based restrictions
def _update_content(self, content, forum_id):
    """Apply nofollow to links if user lacks karma_dofollow"""
    """Strip images/links if user lacks karma_editor"""

# Notify state changes
def _notify_state_update(self):
    """Post notifications for new questions/answers"""

# Reopen closed post
def reopen(self):
    """Reopen post and reverse karma penalties"""

# Close post
def close(self, reason_id):
    """Close with reason, apply karma penalties for spam/offensive"""

# Validate pending post
def validate(self):
    """Approve pending post, add karma for question"""
```

---

### forum.post.vote

**File**: `models/forum_post_vote.py`

```python
class Vote(models.Model):
    _name = 'forum.post.vote'
    _description = 'Post Vote'
    _order = 'create_date desc, id desc'
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | Many2one | Voted post |
| `user_id` | Many2one | Voting user |
| `vote` | Selection | '1', '-1', or '0' |
| `forum_id` | Many2one | Forum (related) |
| `recipient_id` | Many2one | Post author (related) |

**SQL Constraints**:
```python
_sql_constraints = [
    ('vote_uniq', 'unique (post_id, user_id)', "Vote already exists!"),
]
```

**Key Methods**:

```python
# Get karma change based on vote transition
def _get_karma_value(self, old_vote, new_vote, up_karma, down_karma):
    """Calculate karma to add/remove based on vote change"""

# Update karma when vote changes
def _vote_update_karma(self, old_vote, new_vote):
    """Add/remove karma from post author"""

# Check general rights (not voting own post)
def _check_general_rights(self, vals=None):

# Check karma requirements for upvote/downvote
def _check_karma_rights(self, upvote=False):
```

---

### forum.tag

**File**: `models/forum_tag.py`

```python
class Tags(models.Model):
    _name = "forum.tag"
    _description = "Forum Tag"
    _inherit = [
        'mail.thread',
        'website.searchable.mixin',
        'website.seo.metadata',
    ]
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (required) |
| `color` | Integer | Color index |
| `forum_id` | Many2one | Parent forum |
| `post_ids` | Many2many | Posts with this tag |
| `posts_count` | Integer | Post count (computed) |
| `website_url` | Char | Tag questions URL (computed) |

**SQL Constraints**:
```python
_sql_constraints = [
    ('name_uniq', 'unique (name, forum_id)', "Tag name already exists!"),
]
```

---

### forum.post.reason

**File**: `models/forum_post_reason.py`

```python
class Reason(models.Model):
    _name = "forum.post.reason"
    _description = "Post close reason"
```

Closure reasons for posts (Offensive, Spam, Off-topic, Duplicate, etc.)

---

## Gamification Integration

**File**: `models/gamification_challenge.py`

Extends `gamification.challenge` to add forum category:

```python
class Challenge(models.Model):
    _inherit = 'gamification.challenge'

    challenge_category = fields.Selection(selection_add=[
        ('forum', 'Website / Forum')
    ], ondelete={'forum': 'set default'})
```

---

## Karma System Summary

### Earning Karma
| Action | Points |
|--------|--------|
| Ask question | +2 |
| Question upvoted | +5 |
| Question downvoted | -2 |
| Answer upvoted | +10 |
| Answer downvoted | -2 |
| Accepting an answer | +2 |
| Answer accepted | +15 |
| Answer flagged | -100 |

### Required Karma for Actions
| Action | Own | All |
|--------|-----|-----|
| Ask questions | 3 | - |
| Answer questions | 3 | - |
| Edit own posts | 1 | 300 |
| Edit all posts | - | 300 |
| Change tags | - | 75 |
| Close own posts | - | 100 |
| Delete own posts | - | 500 |
| Create tags | 30 | - |
| Upvote | 5 | - |
| Downvote | 50 | - |
| Accept answer | 20 | 500 |
| Flag as offensive | 500 | - |
| Moderate posts | 1000 | - |

---

## Post State Workflow

```
pending -> active -> close/offensive/flagged
                    -> reopen -> active
```

**State Transitions**:
- `pending`: New posts from users with low karma (awaiting validation)
- `active`: Published and visible to all
- `close`: Closed by author or moderator
- `offensive`: Marked as offensive content
- `flagged`: Pending moderator review

---

## Website URL Patterns

| Resource | URL Pattern |
|----------|-------------|
| Forum | `/forum/{forum_slug}` |
| Question | `/forum/{forum_slug}/{question_slug}` |
| Answer | `/forum/{forum_slug}/{question_slug}#answer_{id}` |
| Tag Questions | `/forum/{forum_slug}/tag/{tag_slug}/questions` |
| User Profile | `/forum/{forum_slug}/user/{user_id}` |

---

## Key Features

1. **Karma-Based Access Control**: All actions require sufficient karma
2. **Content Moderation**: Pending posts, flagging, offensive detection
3. **Relevancy Scoring**: Time-decay algorithm for sorting
4. **Tag Management**: User-created tags with karma requirements
5. **Voting System**: Upvote/downvote with karma costs
6. **Favorite Posts**: Bookmark posts for later
7. **Email Notifications**: New answer, post edited alerts
8. **Privacy Controls**: Public, authenticated, or group-restricted forums
