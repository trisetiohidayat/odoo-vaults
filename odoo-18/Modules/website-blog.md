---
Module: website_blog
Version: Odoo 18
Type: Business
Tags: #odoo18, #website, #blog, #content-management, #seo
---

# Website Blog Module (`website_blog`)

## Overview

**Category:** Website/Website
**Depends:** `website_mail`, `website_partner`
**Version:** 1.1
**License:** LGPL-3

The `website_blog` module provides full-featured blog management for Odoo websites. It supports multiple blogs, rich blog posts with WYSIWYG editing, tag-based categorization, author attribution, scheduled publishing, SEO metadata, and comment/discussion threads via the mail engine.

This module is the foundational content management system for company blogs, news sections, and article hubs on an Odoo website.

## Module Composition

```
website_blog/
├── models/
│   ├── website_blog.py       # blog.blog, blog.tag, blog.tag.category, blog.post
│   ├── website.py            # Website extension (search, menu, configurator)
│   └── website_snippet_filter.py  # Sample data for snippet preview
├── controllers/
│   └── main.py               # HTTP routes for blog and post pages
├── data/
│   ├── mail_message_subtype_data.xml  # mt_blog_blog_published subtype
│   ├── mail_templates.xml     # blog_post_template_new_post
│   ├── website_blog_data.xml  # Demo blog and posts
│   └── ...
├── views/
│   ├── website_blog_views.xml    # Form, tree, kanban for all models
│   └── website_blog_templates.xml # QWeb templates (blog_post_short, blog_post_complete, blog_feed)
└── static/
    ├── src/js/               # WYSIWYG adapter, tours, systray
    └── src/scss/              # Blog-specific SCSS
```

---

## Models

### `blog.blog`

**File:** `models/website_blog.py`
**Inheritance:** `mail.thread`, `website.seo.metadata`, `website.multi.mixin`, `website.cover_properties.mixin`, `website.searchable.mixin`
**Order:** `name ASC`

Represents a single blog (a container for posts).

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Blog name (translatable) |
| `subtitle` | Char | No | Blog subtitle/tagline (translatable) |
| `active` | Boolean | No | Archive control (default True) |
| `content` | Html | No | Introduction content for the blog landing page |
| `blog_post_ids` | One2many `blog.post` | — | All posts in this blog (`blog_id` inverse) |
| `blog_post_count` | Integer | — | Computed count of posts |

#### Key Methods

**`write(vals)`** — Cascade archiving
- When a blog is archived (`active=False`), all its posts are also archived
- Uses `with_context(active_test=False)` to find all posts including archived ones
- Each post's `active` is synced to the blog's new `active` value

**`message_post(parent_id, subtype_id, **kwargs)`** — Spam workaround
- Special handling: when a reply comes through the "Presentation Published" email notification (i.e., someone replies to the blog publish notification email), the reply is stored as a `note` (`mail.mt_note`) instead of a regular message
- This prevents all blog followers from being notified of an off-topic reply to the publish notification

**`all_tags(join=False, min_limit=1)`** — Raw SQL tag aggregation

This is a performance-critical method that bypasses the ORM for large post counts:

```python
# Raw SQL: GROUP BY blog_id, tag_id, ORDER BY frequency DESC
SELECT p.blog_id, count(*), r.blog_tag_id
FROM blog_post_blog_tag_rel r
JOIN blog_post p ON r.blog_post_id = p.id
WHERE p.blog_id IN %s
GROUP BY p.blog_id, r.blog_tag_id
ORDER BY count(*) DESC
```

- `join=True`: returns all unique tags across all blogs as a single recordset
- `join=False`: returns a dict `{blog_id: [tag_ids]}`
- `min_limit=N`: only returns tags appearing on at least N posts
- Results are used to render the tag sidebar/cloud on the blog listing page

**`_search_get_detail(website, order, options)`** — Website search integration
- Model: `blog.blog`
- Searches `name` and optionally `subtitle`
- Icon: `fa-rss-square`
- URL: `/blog/{id}`

**`_search_render_results(fetch_fields, mapping, icon, limit)`**
- Sets result URL to `/blog/{id}`

---

### `blog.tag`

**File:** `models/website_blog.py`
**Inheritance:** `website.seo.metadata`
**Order:** `name ASC`

Represents a tag for cross-blog/cross-post categorization.

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Tag name (translatable) |
| `category_id` | Many2one `blog.tag.category` | No | Optional tag category grouping |
| `color` | Integer | No | Color index for UI display |
| `post_ids` | Many2many `blog.post` | — | Posts with this tag (relational only, not stored count) |

#### SQL Constraints

```python
_sql_constraints = [
    ('name_uniq', 'unique (name)', "Tag name already exists!"),
]
```

#### Key Methods

**`write(*args, **kwargs)`** — Cache invalidation workaround
- For every tag record written, `post_ids.write({})` is called
- This forces a template re-render for all posts using the tag
- **Purpose:** In stable versions (pre-v19), Odoo's t-cache system does not invalidate when tag attributes (like `color`) change. Writing to all linked posts forces the cache to refresh on next render
- **TODO note in code:** This workaround is marked for removal in v19.0 when the t-cache system is replaced

---

### `blog.tag.category`

**File:** `models/website_blog.py`
**Order:** `name ASC`

Groups tags into hierarchical categories (e.g., "Industry", "Product", "Region").

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Category name (translatable) |
| `tag_ids` | One2many `blog.tag` | — | Tags in this category |

#### SQL Constraints

```python
_sql_constraints = [
    ('name_uniq', 'unique (name)', "Tag category already exists!"),
]
```

---

### `blog.post`

**File:** `models/website_blog.py`
**Inheritance:** `mail.thread`, `website.seo.metadata`, `website.published.multi.mixin`, `website.cover_properties.mixin`, `website.searchable.mixin`
**Order:** `id DESC` (newest first)
**Mail post access:** `read` (public can read comments without login)

Represents a single blog article.

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Post title (translatable, default empty string) |
| `subtitle` | Char | No | Subtitle/teaser headline (translatable) |
| `author_id` | Many2one `res.partner` | No | Author (defaults to `self.env.user.partner_id`, indexed `btree_not_null`) |
| `author_avatar` | Binary | — | Avatar image (related to `author_id.image_128`, readonly=False) |
| `author_name` | Char | — | Related display name of author (stored for search) |
| `active` | Boolean | No | Archive status |
| `blog_id` | Many2one `blog.blog` | Yes | Parent blog (cascade delete, defaults to first available blog) |
| `tag_ids` | Many2many `blog.tag` | No | Tags for this post |
| `content` | Html | No | Post body (default: "Start writing here...", translatable, sanitize=False) |
| `teaser` | Text | — | Short excerpt (computed from content or manual, translatable) |
| `teaser_manual` | Text | — | Manually set teaser for translations |
| `published_date` | Datetime | No | Scheduled publication datetime |
| `post_date` | Datetime | — | Effective published date (stored, compute+inverse of `published_date`) |
| `visits` | Integer | — | View counter (default 0, not copied on duplicate) |
| `website_id` | Many2one `website` | — | Computed from `blog_id.website_id`, stored |
| `website_message_ids` | One2many | — | Discussion/comment thread (see Comment System below) |
| `create_date`, `create_uid` | Datetime/User | — | Creation audit |
| `write_date`, `write_uid` | Datetime/User | — | Last modification audit |

#### Computed Fields

**`_compute_website_url()`** — Inherited from `website.published.multi.mixin`
- URL pattern: `/blog/{blog_slug}/{post_slug}`
- Uses `ir.http._slug()` for URL-safe slugs

**`_compute_teaser()`** — Computed text teaser
```
if teaser_manual is set:
    teaser = teaser_manual
else:
    teaser = strip_html(content)[:200] + '...'
```

**`_compute_post_date()`** — Published date logic
```
if published_date is set:
    post_date = published_date
else:
    post_date = create_date
```

#### Inverse Fields

**`_set_teaser()`** — Inverse for `teaser`
- Writes to `teaser_manual`
- Special translation handling: if `teaser_manual` is not set in `en_US`, it clears it before writing the new value
- This prevents automatic teaser content from leaking into manual translations

**`_set_post_date()`** — Inverse for `post_date`
- Writes back to `published_date`
- If `published_date` is falsy, uses `create_date` as fallback

#### Key Methods

**`_check_for_publication(vals)`** — Publication notification
```python
if vals.get('is_published'):
    for post in self.filtered(lambda p: p.active):
        post.blog_id.message_post_with_source(
            'website_blog.blog_post_template_new_post',
            subject=post.name,
            render_values={'post': post},
            subtype_xmlid='website_blog.mt_blog_blog_published',
        )
```
- Fires when `is_published` is set to True
- Sends a notification email to all blog followers
- Uses `blog_post_template_new_post` email template
- Subtype: `website_blog.mt_blog_blog_published` (defined in `data/mail_message_subtype_data.xml`)

**`create(vals_list)`** — Multi-create with publication check
- Uses `mail_create_nolog=True` context to suppress automatic chatter messages at creation
- Calls `_check_for_publication()` for each post in the batch

**`write(vals)`** — Cascade and publication logic
- If archiving (`active=False` is set), also unpublishes: `is_published = False`
- If publishing without a `published_date`, auto-sets `published_date = now()`
- Handles scheduled future publication: only sets `published_date` if the current value is empty or in the past
- Calls `_check_for_publication()` at the end for notification
- Returns combined result via `&=` accumulation

**`copy_data(default=None)`** — Duplicate with rename
- Appends ` (copy)` to the title on duplicate (using `blog.name` for context)

**`_get_access_action(access_uid, force_website)`** — Public access redirect
```
if user is employee OR post is published:
    → redirect to /blog/{blog_slug}/{post_slug}
else (share link, post not published):
    → standard form view
```

**`_notify_get_recipients_groups(message, model_description, msg_vals)`**
- For published posts: sets `has_button_access = True` on all recipient groups
- This gives notification recipients an "Open on Website" button

**`_notify_thread_by_inbox(message, recipients_data, msg_vals)`**
- Suppresses inbox (needaction/unread count) notifications for `comment` message types
- Comments only trigger email notifications, not inbox badges
- Rationale: blog comment threads can be large; inbox noise is avoided

**`_default_website_meta()`** — OpenGraph / Twitter Card defaults
```python
res['default_opengraph'] = {
    'og:type': 'article',
    'og:title': self.name,
    'og:description': self.subtitle,
    'article:published_time': self.post_date,
    'article:modified_time': self.write_date,
    'article:tag': [tag.name for tag in self.tag_ids],
    'og:image': cover_properties['background-image'],
}
```

**`_search_get_detail(website, order, options)`** — Full search integration
- Filters: `blog`, `tag` (comma-separated), `date_begin`/`date_end`, `state` (published/unpublished for designers)
- Search fields: `name`, `author_name`; with description: `content`
- `search_extra`: tag name fuzzy search → `[('tag_ids', 'in', matching_tag_ids)]`
- Icon: `fa-rss`
- Visibility: non-designers see only `post_date <= now()`

---

## Comment / Discussion System

Blog comments are powered by the mail engine. The `blog.post` model inherits `mail.thread` and uses the `website_message_ids` One2many field to hold discussion messages.

### `mail.message` — Extended by `website_blog`

The `website_message_ids` field on `blog.post` has a domain:
```python
domain=lambda self: [
    ('model', '=', self._name),  # 'blog.post'
    ('message_type', '=', 'comment')
]
```

This means only messages with `message_type = 'comment'` appear as blog comments. Other message types (notifications, notes) are hidden from the public comment thread but still tracked in chatter.

### Comment Posting Flow

1. Visitor or user posts a comment on the website `/blog/{blog}/{post}` page
2. A `mail.message` record is created:
   - `model = 'blog.post'`
   - `res_id = blog_post.id`
   - `message_type = 'comment'`
   - `author_id = visitor.partner_id` (or portal user)
3. `_notify_thread_by_inbox()` fires — only email is sent, not inbox notification
4. The post author (and blog followers) receive email notification

### Comment Moderation

Moderation is handled through the standard mail thread mechanisms:

- **Portal users / public visitors**: Can post comments. These may require moderation depending on `mail.catchall.domain` settings and website configuration.
- **Email replies**: When someone replies to the comment notification email, the reply becomes a `mail.message` on the post. The `blog.blog.message_post()` method intercepts replies to the "Published Post" notification email and stores them as notes (`mail.mt_note`) rather than comments — this prevents noise from out-of-office replies going to all followers.
- **Chatter access**: Blog post access for `mail.message` is set to `read` (`_mail_post_access = 'read'`), meaning public visitors can read comments without needing to log in.
- **Delete comments**: Blog managers can delete comments through the backend's message tree view.

### Mail Message Subtype

Defined in `data/mail_message_subtype_data.xml`:
```xml
<record id="mt_blog_blog_published" model="mail.message.subtype">
    <field name="name">Published Post</field>
    <field name="res_model">blog.blog</field>
    <field name="default" eval="True"/>
    <field name="description">Published Post</field>
</record>
```

This subtype is used by `_check_for_publication()` when sending publish notifications to blog followers.

---

## SEO

### `website.seo.metadata` Mixin (inherited by `blog.blog`, `blog.tag`, `blog.post`)

Provides standard SEO fields:
- `seo_name` — meta title override
- `seo_description` — meta description override
- `website_meta_title`, `website_meta_description` — alternative fields used by the website framework
- `website_meta_og_img` — OpenGraph image override

### `blog.post` Additional SEO

**OpenGraph type:** `article`
**OpenGraph tags set:** `article:published_time`, `article:modified_time`, `article:tag` (from tag names), `og:image` (from cover properties background-image)

**Twitter Card:** Uses same `og:title`, `og:description`, `og:image` as fallback

### Sitemap

Blog post routes have `sitemap=True`, meaning they are included in the `/sitemap.xml` index.

**Bot handling (SEO):** When a bot (detected via `ir.http.is_a_bot()`) requests a multi-tag URL (e.g., `/blog/1/tag/tag1,tag2`), Odoo redirects to the first tag only (301) to prevent combinatorial explosion in search indexes.

---

## Controller Routes (`controllers/main.py`)

### `WebsiteBlog` Controller

All routes require `auth="public"` and `website=True`.

#### `GET /blog[/page/<int:page>][/tag/<string:tag>]`
**Route:** `/blog`, `/blog/page/<int:page>`, `/blog/tag/<string:tag>`, `/blog/tag/<string:tag>/page/<int:page>`

Lists all blog posts across all blogs (blog index). Single-blog redirect: if only one blog exists, redirects to `/blog/{blog_slug}`.

#### `GET /blog/<blog:blog>`
**Route:** `/blog/<model("blog.blog"):blog>`, `/blog/<blog>/page/<int:page>`, `/blog/<blog>/tag/<string:tag>`

Lists posts for a specific blog. Supports tag filtering and pagination.

**Paging:** `_blog_post_per_page = 12` (multiple of 2,3,4 for grid layouts)

#### `_prepare_blog_values()` — Core value preparer

Called by all listing routes. Builds the complete values dict including:
- Domain (website filter + blog filter + tag filter + date range + publication state)
- Paginated posts via `website._search_with_fuzzy()` for typo-tolerant search
- `nav_list`: archive navigation grouped by year/month (via `nav_list()` method)
- `all_tags`: aggregated tag list via `blogs.all_tags(join=True)` (lazy loaded)
- `pager`: pagination object
- `state_info`: `{published: N, unpublished: N}` for website designers

#### `GET /blog/<blog:blog>/feed`
**Route:** `/blog/<blog:blog>/feed`
**Auth:** public
**Sitemap:** True

Returns Atom feed (`application/atom+xml`) via `website_blog.blog_feed` template. Limit: 15 (or up to 50).

#### `GET /blog/<blog>/<post:post>`
**Route:** `/blog/<model("blog.blog"):blog>/<model("blog.post", "[('blog_id','=',blog.id)]"):blog_post>`
**Auth:** public
**Sitemap:** True

Renders the full blog post page. Logic:
1. Verifies the post belongs to the requested blog (301 redirect if mismatched)
2. Finds the next post in sequence (wraps around to first)
3. Tracks `visits` via `sql.increment_fields_skiplock()` (skip-locking for concurrent access)
4. Stores viewed post IDs in session to avoid double-counting

**Visits tracking:**
```python
if blog_post.id not in request.session.get('posts_viewed', []):
    sql.increment_fields_skiplock(blog_post, 'visits')  # atomic increment
    request.session['posts_viewed'].append(blog_post.id)
```

#### `GET /blog/<blog>/post/<post>` (deprecated)
**Route:** `/blog/<blog:blog>/post/<model("blog.post"):blog_post>`
Redirects (301) to the canonical URL.

---

## Website Extension (`models/website.py`)

### `Website` — Extended

**`get_suggested_controllers()`** — Adds Blog to the website footer menu:
```python
suggested_controllers.append((_('Blog'), '/blog', 'website_blog'))
```

**`configurator_set_menu_links(menu_company, module_data)`** — Creates blog menus during website setup:
- Reads `#blog` from the configurator module data (list of blog definitions)
- Creates `blog.blog` records for each blog in the config
- Creates `website.menu` entries for each blog
- The first blog menu updates the existing `/blog` menu; subsequent blogs create new menu items

**`_search_get_details(search_type, order, options)`** — Registers both `blog.blog` and `blog.post` in website-wide search:
- When `search_type in ['blogs', 'blogs_only', 'all']`: adds `blog.blog` search
- When `search_type in ['blogs', 'blog_posts_only', 'all']`: adds `blog.post` search

---

## Snippet Filter Extension (`models/website_snippet_filter.py`)

### `website.snippet.filter` — Extended

**`_get_hardcoded_sample(model)`** — Provides sample blog posts for the WYSIWYG editor snippet palette

When the website editor shows a "dynamic snippet" (e.g., "Blog Posts" dynamic snippet), this method returns sample posts. For `blog.post` model, it returns 6 hardcoded sample posts with:
- Cover images from theme assets (`/website_blog/static/src/img/cover_2.jpg` through `cover_7.jpg`)
- Titles: Islands, With a View, Skies, Satellites, Viewpoints, Jungle
- Subtitles and `post_date` values (today minus 1-6 days)
- These are merged with generic snippet filter samples for the dynamic snippet preview

---

## L4: Blog vs. Website Slides — Key Differences

| Feature | `website_blog` | `website_slides` |
|---------|---------------|-----------------|
| Content type | Articles/posts | Courses, slides, documents |
| Structure | Blog → Posts | Course → Section → Slide |
| Completion tracking | No | Yes (slide completion %) |
| Quizzes/Assessments | No | Yes (`slide.slide` with question types) |
| Certifications | No | Yes (`slide.channel` with certification) |
| Gamification | No | Badges, ranks |
| Content access | Public / portal | Public / enrolled / members |
| File attachments | Inline only | Dedicated document slides |
| Video hosting | Embed (YouTube/Vimeo) | Odoo-specific video CDN + embed |
| SEO focus | Article SEO, OpenGraph | Course SEO |
| Comments | Yes (mail.thread) | Yes (mail.thread on slides) |
| Publication scheduling | Yes (published_date) | Yes (date_begin/date_end) |

The two modules serve fundamentally different purposes:
- **Blog**: editorial/content marketing, news, announcements — optimized for readability and social sharing
- **Slides**: structured learning content with progression tracking, assessments, and certifications — optimized for course delivery

They share the `mail.thread` for comments and `website.seo.metadata` for SEO, but diverge sharply in content structure and engagement mechanics.

---

## L4: Comment Moderation Deeper

### What Happens When a Visitor Comments

```
Visitor submits comment form on /blog/{blog}/{post}
  → website_blog controller (or mail.message create from portal)
  → mail.message created with message_type='comment'
  → author_id = visitor.partner_id (from website session)
  → If website has moderation enabled (mail.mt_new_comment_subtype + portal post):
      → message goes to moderator queue (not immediately visible)
  → Else:
      → message appears immediately on the post page
```

### Email Notification Suppression for Comments

The `_notify_thread_by_inbox()` override specifically prevents the comment from incrementing the inbox unread counter:
```python
if msg_vals.get('message_type', message.message_type) == 'comment':
    return  # skips inbox notification
```

This means blog comment email notifications arrive in email without marking the Odoo inbox as unread. This reduces noise for authors who receive many comments.

### Reply-to-Email Spam Prevention

The `blog.blog.message_post()` override catches a specific edge case:
- When a follower receives the "Blog Published" notification email and clicks Reply in their email client
- Without this override, the reply would be stored as a comment with subtype `mt_blog_blog_published`
- That would trigger notifications to all blog followers (spam)
- The override detects this and converts the reply to a `note` (`mt_note`) — visible in the blog's chatter but not triggering follower notifications

---

## L4: Scheduled Publication and Publication States

```
is_published = False          → Draft (only editors/admins see it)
is_published = True
  + published_date in future  → Scheduled (visible to editors, hidden from public)
  + published_date in past/null → Published (visible to everyone)
```

The `website.published.multi.mixin` provides the `is_visible` computed field that combines `is_published` and `published_date <= now()` for the actual visibility check on the website.

For website designers in the backend, the search includes:
- `state='published'`: only visible published posts
- `state='unpublished'`: draft + scheduled posts
- No state: all posts (but search respects `post_date <= now()` for non-designers)

---

## Edge Cases

1. **Tag Color Cache Invalidation (pre-v19)**: Tag `write()` touches all linked posts to force t-cache invalidation
2. **Multi-tag Bot Redirect**: Bots requesting multi-tag URLs get redirected (301) to single-tag URL
3. **Author Avatar Fallback**: If `author_id.image_128` is empty, the avatar field is blank (no default placeholder)
4. **Cover Image for SEO**: `cover_properties` JSON field stores `background-image` as `url('/...')` — this is parsed and extracted for `og:image`
5. **Visit Counter Concurrency**: Uses `sql.increment_fields_skiplock()` to atomically increment `visits` without row locking conflicts
6. **Copy Post Name**: `copy_data()` uses `blog.name` from the current record's context to construct the "(copy)" suffix
7. **Teaser Translation**: When setting `teaser_manual` in a non-English translation, the English source value is cleared to prevent the auto-teaser from appearing in English
8. **Empty Blog Default**: New `blog.post` records default `blog_id` to the first available blog (`self.env['blog.blog'].search([], limit=1)`)
