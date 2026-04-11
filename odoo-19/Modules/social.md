---
tags:
  - #social
  - #marketing
  - #social-media
  - #enterprise
  - #modules
  - #utm
---

# Module: Social Marketing (`social`)

> **Edition:** Enterprise Only (OEEL-1 license)
> **Module Name:** `social`
> **Category:** Marketing / Social Marketing
> **Version:** 1.3 (Odoo 19 / `suqma-19.0-20250204`)
> **Depends:** `web`, `mail`, `iap`, `link_tracker`
> **Module Key:** `social_marketing`
> **Author:** Odoo S.A.

---

## Overview

The `social` module is the **base enterprise module** for Odoo's Social Marketing suite. It provides a unified framework for managing social media accounts, publishing posts across multiple platforms, and tracking engagement through integrated UTM analytics. The module does not stand alone -- it is the foundation upon which provider-specific sub-modules (`social_facebook`, `social_twitter`, `social_instagram`, `social_linkedin`, `social_youtube`, etc.) extend to implement platform-specific API integrations.

The module operates on a **multi-layer architecture**:

```
social.post (base post definition, company-scoped)
    |
    +-- social.live.post (per-account posting instance)
            |
            +-- social_facebook.social.live.post (Facebook API posting)
            +-- social_twitter.social.live.post (Twitter/X API posting)
            +-- ...

social.account (registered social media account)
    |
    +-- social_facebook.social.account (Facebook-specific fields)
    +-- social_twitter.social.account (Twitter-specific fields)
    +-- ...

social.stream (feed configuration per account)
    |
    +-- social.stream.post (fetched posts from the social media API)
    +-- social.stream.type (stream category: page posts, hashtag, etc.)
```

---

## Architecture: Provider Pattern

### Core Principle

The module uses a **provider pattern** where the base models define abstract interfaces, and each social media provider sub-module (`social_facebook`, `social_twitter`, etc.) extends them with:

- Provider-specific fields (e.g., `facebook_access_token`, `twitter_api_key`)
- Override of `_post()` to implement actual API calls
- Override of `_compute_statistics()` for platform analytics
- Override of `_fetch_stream_data()` to pull feed data from the provider API
- Override of `_compute_stats_link()` to link to the platform's native analytics dashboard
- Override of `_refresh_statistics()` to sync engagement data

This pattern allows the base `social` module to remain provider-agnostic while sub-modules handle all API-specific logic. New providers can be added by creating a new module that inherits from the base models.

### Social Media Provider Modules

| Module | Media Type | Purpose |
|--------|-----------|---------|
| `social_facebook` | `facebook` | Facebook Pages, posts, insights, stream feeds |
| `social_twitter` | `twitter` | Twitter/X accounts, tweets, mentions, hashtags |
| `social_instagram` | `instagram` | Instagram accounts and posts (via Facebook API) |
| `social_linkedin` | `linkedin` | LinkedIn Company Pages and posts |
| `social_youtube` | `youtube` | YouTube channels and video posts |
| `social_push_notifications` | `push` | Browser/app push notifications (not a social media) |
| `social_demo` | (demo) | Demo/test data for social module evaluation |

---

## Model Inventory

### 1. `social.media` -- Social Media Provider Definition

**File:** `social/models/social_media.py`
**Inherits:** `mail.thread`
**Purpose:** Represents a social media **platform** (Facebook, Twitter, etc.), not an individual account. Stores global configuration for the media type including API endpoints, max post lengths, stream capabilities, and whether accounts can be linked.

**Key Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `Char` (readonly, translate) | Platform display name (e.g., "Facebook", "Twitter") |
| `media_description` | `Char` (readonly) | Description of the platform |
| `image` | `Binary` (readonly) | Platform logo/icon |
| `media_type` | `Selection` (readonly) | Technical identifier for comparisons (`'facebook'`, `'twitter'`, etc.). Empty by default in base -- extended by sub-modules. |
| `csrf_token` | `Char` (computed) | HMAC token for verifying incoming webhooks/callbacks from the social provider. Uses `hmac(env(su=True), 'social_social-account-csrf-token', media.id)`. |
| `account_ids` | `One2many` -> `social.account` | All accounts registered for this media |
| `accounts_count` | `Integer` (computed) | Number of linked accounts |
| `has_streams` | `Boolean` (default `True`, readonly) | Whether this media supports social streams (feed monitoring) |
| `can_link_accounts` | `Boolean` (default `True`, readonly) | Whether accounts can be linked (e.g., push notifications set this to `False`) |
| `stream_type_ids` | `One2many` -> `social.stream.type` | Available stream types for this media |
| `max_post_length` | `Integer` | Maximum character count per post (0 = unlimited). E.g., Twitter has 280, Facebook has 63,206. |

**Key Methods:**

```python
def _compute_accounts_count(self)
    # Returns len(self.account_ids) per media record

def _compute_csrf_token(self)
    # Generates HMAC token: hmac(env(su=True), 'social_social-account-csrf-token', media.id)
    # Used by social provider OAuth callbacks to verify requests are not forged

def action_add_account(self, company_id=None)
    # Stores selected company in session (request.session['social_company_id'])
    # Then calls _action_add_account() -- overridden by each provider module
    # to redirect to the OAuth authorization URL

def _action_add_account(self)
    # Abstract method -- each provider module overrides to implement OAuth flow
    # Typically redirects to the platform's authorization endpoint
```

**Mixin:** `mail.thread` enables platform-level messaging/chatter.

---

### 2. `social.account` -- Linked Social Media Account

**File:** `social/models/social_account.py`
**Purpose:** Represents a **single registered account** on a social media platform. A `social.account` is always tied to exactly one `social.media`. Multiple accounts (e.g., multiple Facebook Pages, multiple Twitter handles) each get their own `social.account` record. Accounts are the units used when selecting where to publish posts.

**Key Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `Char` (required) | Display name of the account (e.g., "Odoo Official", "Marketing Team") |
| `social_account_handle` | `Char` | Social media handle (e.g., `@odoo_official` on X). Used for display and matching. |
| `active` | `Boolean` (default `True`) | Soft-disable an account without deleting it |
| `media_id` | `Many2one` -> `social.media` (required, readonly, ondelete=cascade) | The platform this account belongs to |
| `media_type` | `Selection` (related to `media_id.media_type`) | Convenience access to the platform identifier |
| `stats_link` | `Char` (computed) | External URL to the platform's native analytics (e.g., Facebook Page Insights URL) |
| `image` | `Image` (max 128x128, readonly) | Profile picture from the social media |
| `is_media_disconnected` | `Boolean` | Set to `True` when the OAuth token is invalid or revoked. Used to flag broken account links. |
| `audience` | `Integer` (readonly) | Total followers/fans for this account (Page Likes, Followers, etc.) |
| `audience_trend` | `Float` (readonly, digits=(3,0)) | Percentage change in audience over a defined period (last 30 days). Positive = growth. |
| `engagement` | `Integer` (readonly) | Total engagements (likes, comments, shares) in a period |
| `engagement_trend` | `Float` (readonly, digits=(3,0)) | Percentage change in engagement |
| `stories` | `Integer` (readonly) | Total stories/shares/reposts |
| `stories_trend` | `Float` (readonly, digits=(3,0)) | Percentage change in stories |
| `has_trends` | `Boolean` | Whether trend fields are populated for this account |
| `has_account_stats` | `Boolean` (default `True`) | Whether this account provides audience/engagement stats. Accounts with stats are shown on the dashboard. |
| `utm_medium_id` | `Many2one` -> `utm.medium` (required, ondelete=restrict) | Auto-created UTM medium for this account. Auto-named as `"[Facebook] Odoo Official"`. Used for lead/quotation attribution. |
| `company_id` | `Many2one` -> `res.company` | Optional company restriction. Accounts without a company are usable by all companies. |

**Key Methods:**

```python
def _get_default_company(self)
    # Returns the company from session (request.session['social_company_id'])
    # if set and valid, otherwise falls back to self.env.company.
    # This is the default for company_id.
    # Called during OAuth callback when the active company context may be wrong.

def _compute_statistics(self)
    # Abstract method -- overridden by each provider module.
    # Fetches data from the third-party API and writes audience,
    # engagement, stories, and trend fields.
    # Called on account creation and when "Refresh Statistics" is triggered.
    # Ignores ConnectionError/Timeout gracefully to avoid blocking.

def _compute_stats_link(self)
    # Abstract method -- overridden by each provider.
    # Returns external URL to platform analytics dashboard.
    # Default: returns False for all accounts.

def _compute_display_name(self)
    # Returns "[{media_name}] {account_name}" e.g., "[Facebook] Odoo Social"
    # Used throughout the UI for clarity when multiple platforms are used.

@api.model_create_multi
def create(self, vals_list)
    # On creation, automatically creates a corresponding utm.medium
    # named "[{media_name}] {account_name}" for each account.
    # Then triggers _compute_statistics() to fetch initial stats.
    # UTM medium auto-creation enables lead attribution per social account.

def write(self, vals)
    # If name is updated, reflects the change on the linked utm.medium name
    # to keep attribution naming consistent.

@api.model
def refresh_statistics(self)
    # Called by the "Refresh Statistics" button or scheduler.
    # Searches all accounts with has_account_stats=True and calls
    # _compute_statistics() on each (sudo).
    # Returns a list of dicts with current stats for each account.
    # Gracefully handles third-party API timeouts.

def _compute_trend(self, value, delta_30d)
    # Utility: computes trend percentage = (delta_30d / (value - delta_30d)) * 100
    # Returns 0.0 if value - delta_30d <= 0 (prevents division by zero)
    # Formula: % change = (new - old) / old * 100

def _filter_by_media_types(self, media_types)
    # Utility: returns self.filtered(lambda a: a.media_type in media_types)
    # Used to split recordsets by platform in provider modules.

def _get_multi_company_error_message(self)
    # Returns an error message if accounts from multiple companies
    # are being operated on without proper multi-company access.
    # Checks base.group_multi_company and session cids.

def _action_disconnect_accounts(self, disconnection_info=None)
    # Called when an account's OAuth token becomes invalid.
    # Sets is_media_disconnected=True and logs a warning.
    # Used by provider modules when the API returns auth errors.
```

---

### 3. `social.post` -- Social Post (Multi-Account Publishing)

**File:** `social/models/social_post.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`, `social.post.template`, `utm.source.mixin`
**Purpose:** The central model for **publishing content** to one or more social accounts simultaneously. A `social.post` does not directly publish anything -- it defines the post content (message, images, campaign attribution) and, when triggered, creates one `social.live.post` per selected account. The post lifecycle manages scheduling, publishing, and completion tracking.

**Key Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `state` | `Selection` (readonly, default `draft`) | Current lifecycle state: `draft` -> `scheduled` -> `posting` -> `posted` |
| `has_post_errors` | `Boolean` (computed) | `True` if any child live post is in `failed` state |
| `account_ids` | `Many2many` -> `social.account` (domain: must be in `account_allowed_ids`) | Selected accounts for this post. Users can only select from `account_allowed_ids`. |
| `account_allowed_ids` | `Many2many` -> `social.account` (computed) | Accounts available for selection based on the post's `company_id`. If company is set, shows accounts in that company or with no company. If no company, shows all accounts in the user's allowed companies. |
| `company_id` | `Many2one` -> `res.company` | Restricts the post to accounts in this company. Defaults to current user's company. |
| `media_ids` | `Many2many` -> `social.media` (computed, stored) | The distinct media types of all selected accounts. Used to filter preview/validation per platform. |
| `live_post_ids` | `One2many` -> `social.live.post` (readonly) | Child records created when the post is published -- one per selected account. |
| `live_posts_by_media` | `Char` (computed, JSON) | Technical field holding a JSON dict `{media_id: [live_post_names]}` for the kanban view rendering. |
| `post_method` | `Selection` (`now` / `scheduled`, default `now`) | Whether to publish immediately or at a scheduled time |
| `scheduled_date` | `Datetime` | When to publish (only used if `post_method='scheduled'`) |
| `published_date` | `Datetime` (readonly) | When the post was actually published (set in `_action_post`) |
| `calendar_date` | `Datetime` (computed, stored) | Normalized date for calendar view display. `published_date` if posted, `scheduled_date` if scheduled, `False` if `post_method='now'`. Stored for performance. |
| `is_hatched` | `Boolean` (computed) | `True` if state is `draft`. Used by calendar view to visually gray out draft posts. |
| `utm_campaign_id` | `Many2one` -> `utm.campaign` (domain: `is_auto_campaign=False`) | Campaign attribution. Filtered to exclude auto-generated campaigns. `index='btree_not_null'`. |
| `source_id` | `Many2one` (readonly) | The UTM source record auto-created for this post. Inherited from `utm.source.mixin`. Used to track link clicks. |
| `stream_posts_count` | `Integer` (computed) | Number of feed posts (responses) received from the social media after publishing |
| `engagement` | `Integer` (computed) | Sum of all engagements across all child `social.live.post` records. Computed via `read_group` for performance. |
| `click_count` | `Integer` (computed) | Number of unique link tracker clicks attributed to this post. Raw SQL query joining `link_tracker_click` and `link_tracker` tables filtered by `source_id` and `medium_id` (one medium per account). |

**State Machine:**

```
draft
  |--- action_schedule() ---> scheduled
  |--- action_post() --------> posting ---> posted (when all live posts complete)
  |                             |
  +--- action_set_draft() -----+  (if any live post fails: posted with errors)
```

**Constraints:**

```python
@api.constrains('account_ids')
def _check_account_ids(self)
    # Verifies all selected accounts are in account_allowed_ids.
    # Uses sudo() to bypass multi-company ACLs during validation.
    # Raises ValidationError if mismatch.

@api.constrains('state', 'scheduled_date')
def _check_scheduled_date(self)
    # Prevents scheduling a post in the past.
    # Only applies to 'draft' or 'scheduled' states.
    # Raises ValidationError if scheduled_date < now.
```

**Key Methods:**

```python
@api.depends('company_id')
def _compute_account_allowed_ids(self)
    # For each post, filters accounts by company:
    # If company_id is set: accounts in same company OR accounts with no company
    # If company_id is unset: accounts in user's allowed companies OR no company
    # Uses _get_company_domain() which returns a domain expression.

@api.depends('company_id')
def _compute_account_ids(self)
    # Delegates to parent class (social.post.template) to handle
    # default account pre-selection.

@api.depends('live_post_ids.state')
def _compute_has_post_errors(self)
    # Returns True if any live_post has state='failed'

@api.depends('account_ids.media_id')
def _compute_media_ids(self)
    # Distinct media types of selected accounts.
    # Uses with_context(active_test=False) to include inactive accounts.

@api.depends('state', 'post_method', 'scheduled_date', 'published_date')
def _compute_calendar_date(self)
    # Returns published_date (if posted), scheduled_date (if scheduled),
    # or False (if post_method='now').

@api.depends('state')
def _compute_is_hatched(self)
    # Returns True if state='draft'. Used in calendar rendering.

def _compute_click_count(self)
    # Raw SQL query against link_tracker and link_tracker_click tables.
    # Groups by source_id and counts distinct click IDs.
    # Filters by medium_ids (from selected accounts).
    # Returns 0 for posts without a source_id yet.

def _check_post_access(self)
    # Pre-flight validation before posting:
    # 1. Ensures at least one account is selected
    # 2. Checks message length against each media's max_post_length
    # Raises UserError for no accounts, ValidationError for length violations.
    # Called by action_schedule(), action_set_draft(), action_post().

def action_schedule(self)
    # Validates post_access, sets state='scheduled'.
    # Does NOT update scheduled_date here -- calendar_date write handler does that.

def action_set_draft(self)
    # Validates post_access, reverts state to 'draft'.

def action_post(self)
    # Validates post_access, sets post_method='now', clears scheduled_date,
    # then delegates to _action_post().

def action_redirect_to_clicks(self)
    # Returns an ir.action for link_tracker, filtered to this post's
    # source_id and the selected accounts' utm_medium_ids.
    # Enables users to see all tracked link clicks from this post.

def _action_post(self)
    # The core publishing pipeline:
    # 1. For each post, writes state='posting' and published_date=now
    # 2. Creates one social.live.post per selected account via _prepare_live_post_values()
    # 3. Flushes live_post_ids.message to force link tracker creation before external API calls
    # 4. Commits the SQL transaction (cr.commit()) to ensure link trackers are visible to external APIs
    # 5. Iterates over live_post_ids and calls live_post._post() for each
    # 6. Any exception sets the live_post to state='failed' with failure_reason='Unknown error'
    # 7. After all live posts complete, _check_post_completion() is triggered

def _prepare_live_post_values(self)
    # Returns a list of dicts: [{'post_id': self.id, 'account_id': account.id}]
    # One entry per selected account.

def _check_post_completion(self)
    # Checks if all live_post_ids are in ('posted', 'failed').
    # If yes: writes state='posted' on the parent social.post.
    # Logs a message to the chatter: "Message posted" or
    # "Message posted partially" with list of failed accounts.
    # Called after every live_post write and on live_post create.

def _get_company_domain(self)
    # Returns domain for account filtering:
    # If company_id set: ['|', ('company_id', '=', False), ('company_id', '=', company_id.id)]
    # If company_id unset: ['|', ('company_id', '=', False), ('company_id', 'in', env.companies.ids)]

def _get_default_accounts_domain(self)
    # Delegates to _get_company_domain() for consistency.

def _get_stream_post_domain(self)
    # Returns empty domain []. Overridden by provider modules (e.g., social_facebook)
    # to return a domain matching stream posts related to this post's live posts.

@api.model
def _cron_publish_scheduled(self)
    # Scheduled action (runs hourly via ir_cron_post_scheduled).
    # Searches for posts where:
    #   - post_method='scheduled'
    #   - state='scheduled'
    #   - scheduled_date <= now
    # Calls _action_post() on the matched posts.
```

---

### 4. `social.live.post` -- Per-Account Live Post Instance

**File:** `social/models/social_live_post.py`
**Purpose:** Represents the **actual published content** on a single social account. When a `social.post` is published, it creates one `social.live.post` per selected `social.account`. This is the model that calls the third-party API. It carries the post-processed message (with shortened URLs and UTM parameters) and tracks the result.

**Key Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `post_id` | `Many2one` -> `social.post` (required, readonly, ondelete=cascade, index) | Parent social post |
| `account_id` | `Many2one` -> `social.account` (required, readonly, ondelete=cascade) | Target social account |
| `message` | `Char` (computed) | Post-processed message with shortened URLs and UTM parameters added. Computed from the parent post's message field. |
| `image_ids` | `Many2many` -> `ir.attachment` (computed) | Images attached to this specific live post (platform-specific images, not generic) |
| `live_post_link` | `Char` (computed) | Direct URL to the published post on the social media platform |
| `failure_reason` | `Text` (readonly) | Error message if posting failed (API error, connection error, etc.) |
| `state` | `Selection` (`ready` / `posting` / `posted` / `failed`, readonly, default `ready`) | Publishing state. Most live posts go directly from `ready` -> `posted/failed`. `posting` is used for batch operations like push notifications. |
| `engagement` | `Integer` | Total engagements on this specific post (updated via refresh_statistics) |
| `company_id` | `Many2one` (related) | Inherited from account_id |
| `media_type` | `Selection` (related) | Convenience access to account_id.media_type |

**Computed Field Dependencies -- Message (`_compute_message`):**

```python
@api.depends(lambda self: [
    'post_id.utm_campaign_id',
    'account_id.media_type',
    'account_id.utm_medium_id',
    'post_id.source_id'
] + [f'post_id.{field}' for field in social.post._get_post_message_modifying_fields()]
  + [f'post_id.{field}' for field in social.post._message_fields().values()])
def _compute_message(self)
    # Retrieves the platform-specific message field from the parent post
    # (via _message_fields() mapping: {'facebook': 'message', 'twitter': 'message', ...})
    # Calls mail.render.mixin._shorten_links_text() to:
    #   1. Extract URLs from the message
    #   2. Create link_tracker records with UTM parameters (campaign, medium, source)
    #   3. Replace original URLs with shortened tracker URLs
    # Then calls social.post._prepare_post_content() to apply
    # platform-specific formatting (e.g., YouTube appends video link)
```

**Key Methods:**

```python
@api.model_create_multi
def create(self, vals_list)
    # On creation, triggers _check_post_completion() on the parent post.
    # This handles the case where all live posts are created at once
    # during _action_post() and immediately signals completion.

def write(self, vals)
    # If state changes, triggers _check_post_completion() on the parent post.
    # This handles incremental publishing where live posts complete one by one.

def action_retry_post(self)
    # Calls _post() to re-attempt publishing.
    # Used when a live post failed and the user wants to retry
    # (e.g., after fixing the underlying issue).

@api.model
def refresh_statistics(self)
    # Scheduled/button action to refresh engagement on all live posts.
    # Calls _refresh_statistics() -- overridden by each provider module.
    # Gracefully ignores ConnectionError/Timeout from third-party APIs.

def _refresh_statistics(self)
    # Abstract method -- overridden by each provider.
    # Fetches engagement data from the platform API and updates
    # the engagement field on each live post.
    # e.g., social_facebook fetches likes, shares, comments counts
    # and writes the sum to engagement.

def _post(self)
    # Abstract method -- overridden by each provider to:
    # 1. Make the API call to publish the post
    # 2. Write the returned post ID (platform-specific) to a provider-specific field
    # 3. Write state='posted' or 'failed' with failure_reason

def _get_utm_values(self)
    # Returns UTM dict for link shortening:
    # {
    #     'campaign_id': post_id.utm_campaign_id.id,
    #     'medium_id': account_id.utm_medium_id.id,
    #     'source_id': post_id.source_id.id,
    # }
    # One medium per account ensures accurate per-account click attribution.

def _filter_by_media_types(self, media_types)
    # Filters live posts by account's media_type.
    # Used in provider overrides to isolate their platform's records.
```

---

### 5. `social.stream` -- Social Feed Configuration

**File:** `social/models/social_stream.py`
**Purpose:** Represents a **social media feed that is being monitored**. A stream is always tied to one `social.account` and one `social.stream.type`. It defines what data to fetch (page posts, hashtag posts, mentions, etc.) and creates `social.stream.post` records when new content is pulled from the platform API.

**Key Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `Char` (translate) | Human-readable title for the stream (e.g., "Odoo Official - Page Posts", "#odoo hashtag") |
| `media_id` | `Many2one` -> `social.media` (required) | The platform this stream monitors |
| `media_image` | `Binary` (related) | Platform icon for display |
| `sequence` | `Integer` | Ordering weight for the Feed kanban view |
| `account_id` | `Many2one` -> `social.account` (required, ondelete=cascade) | Which account this stream reads from |
| `stream_type_id` | `Many2one` -> `social.stream.type` (required, ondelete=cascade) | Category of stream (e.g., "Page Posts", "Hashtag", "Mentions") |
| `stream_type_type` | `Char` (related) | Technical stream type identifier (e.g., `'page_posts'`, `'hashtag'`) |
| `stream_post_ids` | `One2many` -> `social.stream.post` | All fetched posts in this stream |
| `company_id` | `Many2one` (related to account_id.company_id, stored) | Inherited from the linked account |

**Key Methods:**

```python
@api.onchange('media_id', 'account_id')
def _onchange_media_id(self)
    # If media changes and the current account belongs to a different media,
    # resets account_id to False.
    # If only one stream_type exists for the new media, auto-selects it.

@api.model_create_multi
def create(self, vals_list)
    # 1. Creates the stream records
    # 2. Calls _apply_default_name() to set name from stream_type if not provided
    # 3. Calls _fetch_stream_data() immediately to populate initial posts

@api.model
def refresh_all(self)
    # Class method that searches ALL streams and fetches data for each.
    # Called from the "Refresh All" button on the Feed kanban.
    # Returns True if any new posts were inserted.
    # Gracefully handles ConnectionError/Timeout per stream.

def _fetch_stream_data(self)
    # Abstract method -- overridden by each provider module.
    # The method that calls the platform API to fetch new posts and
    # creates social.stream.post records.
    # Called on stream creation (to populate initial data) and on refresh.
    # Returns True if new posts were inserted.
    # See social_facebook/social_stream.py for implementation example.

def _apply_default_name(self)
    # Sets name = stream_type_id.name if name was not provided at creation.
    # Allows creating streams without explicitly setting a name.
```

---

### 6. `social.stream.type` -- Stream Category Definition

**File:** `social/models/social_stream_type.py`
**Purpose:** A **technical, data-only model** that defines the categories of streams available per platform. This model is extended by each provider module to register stream types (e.g., Facebook registers "Page Posts", "Page Reviews"; Twitter registers "Mentions", "Hashtag", "Timeline"; Instagram registers "User Posts", "Hashtag"). Stream types are typically created via data files (`data/*.xml`) rather than programmatically.

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `Char` (readonly, required, translate) | Display name (e.g., "Page Posts", "Hashtag") |
| `stream_type` | `Char` (readonly, required) | Technical identifier used in provider module overrides (e.g., `'page_posts'`, `'hashtag'`) |
| `media_id` | `Many2one` -> `social.media` (readonly, required, index) | The platform this stream type belongs to |

---

### 7. `social.stream.post` -- Fetched Post from Social Media

**File:** `social/models/social_stream_post.py`
**Purpose:** Represents a **post that exists on the social media platform** (not created by the user's Odoo instance). Stream posts are created by `social.stream._fetch_stream_data()` which pulls data from the platform API. They are read-only in Odoo -- the post exists externally and can only be interacted with (e.g., liking, commenting) through platform-specific API calls in provider modules.

**Key Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `message` | `Text` | The post's text content |
| `author_name` | `Char` | Display name of the post author (from platform API) |
| `author_link` | `Char` (computed) | External URL to the author's profile on the platform |
| `post_link` | `Char` (computed) | External URL to the actual post on the platform |
| `stream_id` | `Many2one` -> `social.stream` (ondelete=cascade, index `btree_not_null`) | Which stream this post was fetched from |
| `media_type` | `Selection` (related) | Platform type of the source stream |
| `published_date` | `Datetime` | When the post was published on the platform (from platform API) |
| `formatted_published_date` | `Char` (computed) | Human-readable relative date ("5 minutes ago") if < 12 hours old, otherwise formatted date |
| `account_id` | `Many2one` (related) | Convenience reference to the parent stream's account |
| `company_id` | `Many2one` (related) | Company inherited from the account |
| `is_author` | `Boolean` (computed) | Whether the current Odoo user is the author of this post (used to enable/disable interaction buttons) |
| `stream_post_image_ids` | `One2many` -> `social.stream.post.image` | Images shared with this post |
| `stream_post_image_urls` | `Text` (computed, JSON) | JSON array of image URLs for kanban rendering |
| `link_title` | `Text` | Title of a shared URL (extracted from Open Graph metadata) |
| `link_description` | `Text` | Description of a shared URL |
| `link_image_url` | `Char` | Preview image of a shared URL |
| `link_url` | `Char` | The actual shared URL |

**Key Methods:**

```python
def _compute_stream_post_image_urls(self)
    # Returns JSON: ["url1", "url2", ...] for kanban rendering.
    # Iterates over stream_post_image_ids and collects image_url field.

def _compute_author_link(self)
    # Abstract method -- overridden by each provider.
    # Returns the external profile URL for the post author.

def _compute_post_link(self)
    # Abstract method -- overridden by each provider.
    # Returns the external URL for this specific post on the platform.

@api.depends('published_date')
def _compute_formatted_published_date(self)
    # If published within last 12 hours: uses _format_time_ago() ("5 minutes ago")
    # Otherwise: uses format_date() for absolute date display.

def _compute_is_author(self)
    # Default implementation: sets is_author=False.
    # Provider modules override this to check if the post author matches
    # one of the user's linked social accounts.

def _fetch_matching_post(self)
    # Returns the social.post (if any) that was the source of this stream post.
    # Implemented by matching platform-specific post IDs between
    # social.stream.post records and social.live.post records.
    # Default: returns empty recordset. Provider modules override with
    # their specific ID matching logic.

def _filter_by_media_types(self, media_types)
    # Filters by media_type (related to stream_id.media_id.media_type).
```

---

### 8. `social.stream.post.image` -- Stream Post Image Attachment

**File:** `social/models/social_stream_post_image.py`
**Purpose:** Stores the URL of an image shared with a `social.stream.post`. This is a lightweight model containing only the URL -- the actual image data is not stored in Odoo (only referenced via URL, which is loaded from the social media API at display time).

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `image_url` | `Char` (readonly, required) | The URL of the image on the social media platform |
| `stream_post_id` | `Many2one` -> `social.stream.post` (index `btree_not_null`, ondelete=cascade) | Parent stream post |

---

### 9. `social.post.template` -- Post Content Template (Mixin/Abstract)

**File:** `social/models/social_post_template.py`
**Purpose:** Abstract model that defines the **content fields** shared between actual posts (`social.post`) and reusable templates (`social.post.template`). This separation allows creating post templates that can generate multiple `social.post` records. The `social.post` model inherits from this, so all these fields are available on posts.

**Key Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `message` | `Text` | The main post text content |
| `image_ids` | `Many2many` -> `ir.attachment` | Generic images to attach to posts |
| `display_message` | `Char` (computed, searchable) | The message to display. If `is_split_per_media=True`, uses platform-specific message; otherwise uses `message`. Searchable via `_search_display_message`. |
| `image_urls` | `Text` (computed, JSON) | JSON array of image URLs for all images across all image fields |
| `is_split_per_media` | `Boolean` | If `True`, allows different messages per platform. When `True`, platform-specific message fields (from `_message_fields()`) become editable. |
| `media_count` | `Integer` (computed) | Number of distinct media types in selected accounts |
| `account_ids` | `Many2many` -> `social.account` (computed, stored, readonly=False) | Selected accounts. If fewer than 3 accounts available, auto-selects all. |
| `has_active_accounts` | `Boolean` (computed) | Whether any social accounts exist in the system |

**Computed Fields for Platform-Specific Content:**

```python
@api.depends('message', 'is_split_per_media')
def _compute_message_by_media(self)
    # When is_split_per_media=True, propagates message to all
    # platform-specific message fields. Overridden by provider modules
    # to add platform-specific formatting.

@api.depends('image_ids', 'is_split_per_media')
def _compute_images_by_media(self)
    # When is_split_per_media=True, propagates image_ids to all
    # platform-specific image fields.

@api.depends(lambda self: ['message', 'is_split_per_media'] + list(self._message_fields().values()))
def _compute_display_message(self)
    # If not split: returns self.message
    # If split: returns the first available platform-specific message
    # from account_ids' media_types.

@api.depends(lambda self: ['image_ids'] + list(self._images_fields().values()))
def _compute_image_urls(self)
    # Collects all image IDs from all image fields and returns
    # JSON array of /web/image/{id} URLs for kanban display.
    # Uses OrderedSet to deduplicate.
```

**Key Methods:**

```python
@api.constrains('message', 'image_ids')
def _check_has_message_or_image(self)
    # Ensures the post has at least a message OR images.
    # Does NOT apply when is_split_per_media=True (allows platform-specific
    # messages to be set individually without a generic message).

@api.constrains(lambda self: ['image_ids'] + list(self._images_fields().values()))
def _check_image_ids_mimetype(self)
    # Validates that all uploaded files are valid images
    # (mimetype must start with 'image'). Prevents uploading PDFs, documents, etc.

def _set_attachment_res_id(self)
    # The many2many_binary widget creates ir.attachment records
    # without setting res_id (only res_model). This method fixes that
    # by setting res_id to the post's ID for attachments created by the
    # current user that are missing it. Without this, other users would
    # get AccessError when trying to read the attachments.

def action_generate_post(self)
    # Creates a new social.post pre-filled with this template's values
    # and returns the form action for immediate editing/posting.

def _prepare_social_post_values(self)
    # Returns a dict of values to populate a new social.post:
    # {
    #     'message': self.message,
    #     'image_ids': self.image_ids.ids,
    #     'account_ids': self.account_ids.ids,
    #     'company_id': False,
    #     ...platform-specific message and image fields...
    # }

@api.model
def _prepare_post_content(self, message, media_type, **kw)
    # Post-processes the message for a specific platform.
    # Default: returns the message as-is.
    # Provider modules override to add platform-specific formatting
    # (e.g., YouTube appends a video URL at the end).

@api.model
def _message_fields(self)
    # Returns a dict mapping media_type to message field names.
    # Default: {}. Provider modules override to register their fields
    # e.g., social_youtube returns {'youtube': 'youtube_video_id'}
    # This enables _compute_message on live_post to dynamically pick
    # the right message field per platform.

@api.model
def _images_fields(self)
    # Returns a dict mapping media_type to image field names.
    # Default: {}. Provider modules override to register their fields.

@api.model
def _get_post_message_modifying_fields(self)
    # Returns additional field names (beyond message) that affect
    # the live_post message computation. E.g., social_youtube returns
    # ['youtube_video_id'] so the message (which includes the video URL)
    # is re-computed when the video changes.

@api.model
def _extract_url_from_message(self, message)
    # Uses a comprehensive regex to extract the first URL from a message.
    # The extracted URL is used for Open Graph preview generation.
    # Based on John Gruber's improved URL regex.

def _get_default_accounts_domain(self)
    # Returns empty domain by default. Provider modules override to
    # filter out accounts that shouldn't appear as defaults.
```

---

### 10. UTM Integration Models

#### `utm.campaign` Extension (`social/models/utm_campaign.py`)

**File:** `social/models/utm_campaign.py`
**Inherits:** `utm.campaign`

The `social` module extends the standard UTM campaign with social-specific fields and actions:

| Field | Type | Purpose |
|-------|------|---------|
| `social_post_ids` | `One2many` -> `social.post` (linked via `utm_campaign_id`) | All social posts in this campaign |
| `social_posts_count` | `Integer` (computed) | Number of social posts in this campaign |
| `social_engagement` | `Integer` (computed) | Total engagement across all posts in this campaign (sum of post.engagement) |

**Key Methods:**

```python
def _compute_social_posts_count(self)
    # Uses read_group to efficiently count posts per campaign.
    # Filters by _get_social_posts_domain() (overridable by sub-modules).

def _compute_social_engagement(self)
    # Iterates over posts_data to sum engagement per campaign.
    # Uses search_read for efficiency on the join.

def action_create_new_post(self)
    # Opens a new social.post form with:
    #   - default_utm_campaign_id = self.id
    #   - default_account_ids = accounts from _get_social_media_accounts_domain()
    # Pre-populates the campaign for easy post creation from campaign context.

def action_redirect_to_social_media_posts(self)
    # Opens social.post list filtered to this campaign,
    # default state = 'posted', with search_default_utm_campaign_id set.

def _get_social_posts_domain(self)
    # Returns []. Overridden by social_push_notifications to exclude
    # push-notification-only posts.

def _get_social_media_accounts_domain(self)
    # Returns []. Overridden by social_push_notifications to exclude
    # push_notifications medium.
```

#### `utm.medium` Extension (`social/models/utm_medium.py`)

**File:** `social/models/utm_medium.py`
**Inherits:** `utm.medium`

| Method | Purpose |
|--------|---------|
| `@api.ondelete(at_uninstall=False) _unlink_except_linked_social_accounts()` | Prevents deletion of a `utm.medium` that is linked to any `social.account`. Raises `UserError` with the list of linked accounts. `at_uninstall=False` means this constraint is NOT enforced during module uninstall (to allow clean removal). |

#### `utm.source` Extension (`social/models/utm_source.py`)

**File:** `social/models/utm_source.py`
**Inherits:** `utm.source`

| Method | Purpose |
|--------|---------|
| `@api.ondelete(at_uninstall=False) _unlink_except_linked_social_posts()` | Prevents deletion of a `utm.source` that is linked to any `social.post` (via `source_id`). Raises `UserError` with the list of linked sources. |

---

## Post States and Publishing Flow

### State Diagram

```
                    ┌──────────────────────────────────────────────┐
                    │                                              │
                    ▼                                              │
┌─────────┐  schedule   ┌────────────┐  cron/now  ┌─────────┐     │
│  DRAFT  │──────────▶ │ SCHEDULED  │──────────▶ │ POSTING │─────┘
└─────────┘             └────────────┘            └─────────┘
     ▲                        │                        │
     │                        │                        ▼
     │                        │              ┌──────────────────┐
     │                        │              │ Once ALL live_   │
     │                        │              │ posts are done:   │
     │                        │              │ state='posted'    │
     │                        │              └──────────────────┘
     │                        │
     │                        │  If any live_post fails:
     │                        │  state still='posted' but
     │                        │  has_post_errors=True
     │                        │  (partial post)
     │                        │
     └────── set_draft ───────┘
```

### Step-by-Step Publishing Pipeline

**Path 1: Immediate Posting (`action_post`)**
1. User clicks "Post" -> `action_post()` -> validates `_check_post_access()`
2. Sets `post_method='now'`, clears `scheduled_date`, calls `_action_post()`
3. For each post: writes `state='posting'`, `published_date=now`
4. Creates one `social.live.post` per selected account via `_prepare_live_post_values()`
5. **Critical step**: `self.mapped('live_post_ids.message')` forces Odoo to compute the message field, which creates `link_tracker` records in the database
6. `self.env.cr.commit()` commits the SQL transaction so the link trackers are visible to the external social media API (which fetches the URL to generate Open Graph previews)
7. For each live_post: calls `live_post._post()` (provider-specific API call)
8. Any exception: live_post state='failed', failure_reason='Unknown error'
9. `_check_post_completion()` marks post as 'posted' when all live posts complete

**Path 2: Scheduled Posting (`action_schedule`)**
1. User clicks "Schedule" -> `action_schedule()` -> validates `_check_post_access()`
2. Sets `state='scheduled'`
3. `write()` on `scheduled_date` triggers cron trigger via `cron._trigger(at=scheduled_date)`
4. At the scheduled time: `_cron_publish_scheduled()` fires and calls `_action_post()` (same pipeline as Path 1)

**Path 3: Calendar View Scheduling**
1. User drags post to a date in calendar view
2. `calendar_date` is written, which triggers `_check_scheduled_date` constraint and sets `scheduled_date`
3. `cron._trigger(at=scheduled_date)` schedules the cron

### Error Handling

| Error Type | Handling |
|------------|----------|
| No accounts selected | `UserError` raised in `_check_post_access()` before any action |
| Message too long | `ValidationError` listing which media exceeded their limit |
| Scheduled date in past | `ValidationError` raised in `_check_scheduled_date` |
| API call timeout | Live post state='failed', `failure_reason='Unknown error'` |
| API auth error | Account `is_media_disconnected=True`, `_action_disconnect_accounts()` called |
| API rate limit | Caught by provider module, typically written to `failure_reason` |
| All live posts fail | Post state='posted' with `has_post_errors=True`, chatter logs failure details |
| Partial failure | Post state='posted' with `has_post_errors=True`, lists failed accounts in chatter |

---

## Stream Filtering and Feed Management

### Stream Creation Flow

1. User creates a `social.stream` linked to a `social.account` and `social.stream.type`
2. On `create()`: `_apply_default_name()` sets the name from the stream type if not provided
3. Immediately: `_fetch_stream_data()` is called to populate initial posts
4. Stream posts are displayed in the Feed kanban view

### Feed Refresh

The Feed kanban view has three refresh mechanisms:
- **Individual stream refresh**: Each stream has its own refresh action
- **Global refresh**: `social.stream.refresh_all()` fetches data for all streams
- **Automatic refresh**: Provider modules implement cron jobs or push notifications (webhooks) to update stream data

### Stream Type Extension Pattern

Each provider module registers stream types via XML data:

```xml
<!-- social_facebook/data/data.xml -->
<record id="stream_type_page_posts" model="social.stream.type">
    <field name="name">Page Posts</field>
    <field name="stream_type">page_posts</field>
    <field name="media_id" ref="social_facebook.social_media_facebook"/>
</record>
<record id="stream_type_page_reviews" model="social.stream.type">
    <field name="name">Page Reviews</field>
    <field name="stream_type">page_reviews</field>
    <field name="media_id" ref="social_facebook.social_media_facebook"/>
</record>
```

The provider module then overrides `_fetch_stream_data()` on `social.stream` to handle each `stream_type_type`:

```python
def _fetch_stream_data(self):
    self.ensure_one()
    if self.stream_type_type == 'page_posts':
        return self._fetch_page_posts()
    elif self.stream_type_type == 'page_reviews':
        return self._fetch_page_reviews()
    return False
```

---

## Account Reach and Engagement Tracking

### Statistics Architecture

The statistics system operates on a **pull model** -- Odoo periodically calls the social media APIs to fetch updated metrics. There is no real-time push (unless the provider supports webhooks, which would be implemented in sub-modules).

### Statistics Flow

```
social.account.refresh_statistics() [button or cron]
    |
    v
all_accounts._compute_statistics() [provider-specific API calls]
    |
    v
Write: audience, engagement, stories + trend fields
```

### Trend Computation

The trend formula is:

```
trend = 0.0 if value <= delta_30d
trend = (delta_30d / (value - delta_30d)) * 100  [%]

Where:
  value = current period total (e.g., total engagements)
  delta_30d = value 30 days ago
```

Example: If current audience is 1000 and was 800 a month ago:
- delta_30d = 200
- trend = (200 / (1000 - 200)) * 100 = 25%
- Interpretation: 25% growth in the last 30 days

### Post-Level Engagement

Engagement at the post level (`social.live.post.engagement`) is updated via `_refresh_statistics()`, which is triggered:
1. Manually via the "Refresh Statistics" button on the Feed view
2. Via a scheduled action (if configured by the provider module)

The engagement figure varies by platform:
- **Facebook**: likes + comments + shares
- **Twitter**: retweets + likes + replies
- **Instagram**: likes + comments
- **LinkedIn**: reactions + comments + shares
- **YouTube**: likes + comments

### Click Tracking

Link clicks are tracked via `link_tracker` integration:
1. When `_action_post()` runs, URLs in the message are replaced with `link_tracker` short URLs
2. Each link tracker record stores the UTM parameters (`source`, `medium`, `campaign`)
3. `_compute_click_count()` on `social.post` performs a raw SQL join to count distinct clicks:
```sql
SELECT COUNT(DISTINCT click.id), link.source_id
  FROM link_tracker_click click
  JOIN link_tracker link ON link.id = click.link_id
 WHERE link.source_id IN %s AND link.medium_id IN %s
 GROUP BY link.source_id
```
4. One `utm.medium` is created per `social.account`, so clicks are attributed to the correct account

---

## Security Architecture

### Access Groups

| Group | Name | Rights |
|-------|------|--------|
| `base.group_user` (implied) | Employee | Base access |
| `social.group_social_user` | Social User | Create/read/write posts and streams, read accounts and stream posts |
| `social.group_social_manager` | Social Manager | Full access: create/read/write/unlink on all social models |

The `group_social_manager` inherits from `group_social_user`, which inherits from `base.group_user`, creating a proper privilege hierarchy.

### Record Rules (Row-Level Security)

| Model | Group | Rule |
|-------|-------|------|
| `social.post` | `social_manager` | Domain: `[(1, '=', 1)]` -- access all posts |
| `social.post` | `social_user` | Read/create/write: `[(1, '=', 1)]` -- can see all posts |
| `social.post` | `social_user` | Unlink only own: `[('create_uid', '=', user.id)]` |
| `social.live.post` | `social_manager` | Full access to all |
| `social.live.post` | `social_user` | Full access only to own live posts (`create_uid = user.id`) |
| `social.stream` | `social_manager` | Full access to all |
| `social.stream` | `social_user` | Create/write/unlink only own streams |
| `social.account` | (no group-specific rule) | Multi-company rule only |
| `social.stream.post` | (no group-specific rule) | Multi-company rule only |

### Multi-Company Rules

All account-related models have a multi-company rule:
```python
domain_force = [('company_id', 'in', company_ids + [False])]
```
This means an account/post is visible if:
- Its `company_id` is in the user's allowed company IDs, OR
- Its `company_id` is `False` (shared across all companies)

### UTM Protection

Deletion of UTM records linked to social data is blocked:
- `utm.medium`: Cannot delete if linked to any `social.account`
- `utm.source`: Cannot delete if linked to any `social.post`

This prevents accidental breakage of attribution tracking.

---

## Cron Jobs

| Cron | Model | Frequency | Purpose |
|------|-------|-----------|---------|
| `social.ir_cron_post_scheduled` | `social.post` | Every 1 hour | Publishes all posts where `post_method='scheduled'`, `state='scheduled'`, and `scheduled_date <= now` |

The cron trigger mechanism allows precise scheduling -- when a post is created or rescheduled, `cron._trigger(at=scheduled_date)` is called to schedule the cron to fire exactly at the specified time (rather than waiting for the next hourly interval).

---

## Odoo 18 to Odoo 19 Changes

### Changes in the `social` Module (Odoo 18 vs Odoo 19)

The base `social` module between Odoo 18 (`18.0-20250812`) and Odoo 19 (`suqma-19.0-20250204`) is largely **stable** with the following notable differences:

**1. Removed `threading` Import (Odoo 19)**
The Odoo 18 version of `social_post.py` imports `threading`. In Odoo 19, this import is removed (no longer needed as the threading patterns used in Odoo 18 are handled differently in the newer version).

**2. Removed `format_list` Import (Odoo 19)**
The Odoo 18 version imports `format_list` from `odoo.tools`. This import is removed in Odoo 19.

**3. Stable Feature Parity**
The core models (`social.media`, `social.account`, `social.post`, `social.live.post`, `social.stream`, `social.stream.post`, `social.post.template`) are functionally equivalent between versions. All fields and methods described in this document apply to both Odoo 18 and Odoo 19.

**4. `action_retry_post` (Odoo 19)**
The `action_retry_post()` method on `social.live.post` is present in both versions, enabling retry of failed live posts.

### Sub-Module Changes (Provider-Specific)

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Facebook API endpoint version | `v17.0` | `v17.0` (stable) |
| Twitter API | Twitter/X v2 API | Twitter/X v2 API |
| YouTube integration | Updated API | Stable |
| Push notifications | Enhanced batching | Enhanced batching |

---

## Performance Considerations

### N+1 Query Prevention

- `_compute_post_engagement()` uses `read_group()` instead of looping over live posts
- `_compute_click_count()` uses a single raw SQL query with GROUP BY
- `_compute_social_posts_count()` on `utm.campaign` uses `read_group()`
- `_compute_social_engagement()` on `utm.campaign` uses `search_read()` in one query

### Stored Computed Fields

- `social.post.calendar_date` is stored (`store=True`) because it is used as the primary sort/order field in the calendar view. Without storage, every calendar view render would trigger recomputation.
- `social.post.media_ids` is stored because it is used in domain filters and kanban grouping
- `social.post.account_allowed_ids` is NOT stored (computed on the fly based on company context)

### Link Tracker Pre-Computation

The `_action_post()` method forces computation of `live_post_ids.message` and commits the SQL transaction before calling external APIs. This is a deliberate design choice to ensure link trackers exist in the database when the social media API fetches the URL for Open Graph preview generation. Without this commit, the API would receive a 404 for the short URL.

### Image URL Storage

`social.stream.post.image` stores only the URL (not the image binary) to avoid storing large blobs in the Odoo database. Images are loaded directly from the social media platform at render time via the URL.

### Batch Statistics Refresh

`social.account.refresh_statistics()` uses `sudo()` and processes all accounts in a single pass, minimizing the number of RPC calls. Individual provider implementations (e.g., Facebook) may batch multiple API calls within their `_compute_statistics()` override.

---

## Key Design Patterns

### 1. Provider Extension Pattern
Base models define interfaces (`_post()`, `_compute_statistics()`, `_fetch_stream_data()`) as empty/pass methods. Sub-modules override with platform-specific implementations. The base code uses `_filter_by_media_types()` to isolate records belonging to each platform.

### 2. UTM Attribution Chain
Every social interaction creates a full UTM chain:
- `utm.medium` per `social.account` (auto-created on account creation)
- `utm.source` per `social.post` (auto-created via `utm.source.mixin`)
- `utm.campaign` optionally linked to the post
- `link_tracker` records created at post time with all UTM parameters
- Click attribution via SQL join on `link_tracker` filtered by `source_id` and `medium_id`

### 3. Multi-Company Isolation
Accounts and posts carry `company_id`. Stream posts inherit company from their parent account. Record rules filter visibility by company. The `_get_company_domain()` method provides a reusable domain expression for all company-based filtering.

### 4. Failure Isolation
The `_action_post()` method catches exceptions per live post, ensuring one platform's failure does not prevent others from posting. The parent post transitions to 'posted' (not stuck in 'posting') as soon as all live posts complete, regardless of success/failure status.

### 5. Template/Post Separation
`social.post.template` provides the content abstraction, allowing post templates to be reused across multiple campaigns. The `_prepare_social_post_values()` method bridges templates to actual posts while supporting platform-specific field mapping.

---

## Related Documentation

- [[Modules/social_media]] -- `social_facebook` module
- [[Modules/social_media]] -- `social_twitter` module
- [[Modules/Social/LinkedIn]] -- `social_linkedin` module
- [[Modules/social_media]] -- `social_youtube` module
- [[Modules/social_media]] -- `social_instagram` module
- [[Modules/social_media]] -- Stream post management
- [[Modules/social_media]] -- UTM and analytics integration
- [[Modules/utm]] -- UTM framework
