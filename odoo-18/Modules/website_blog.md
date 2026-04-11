# Website Blog Module (website_blog)

## Overview

The `website_blog` module provides blogging functionality integrated with the Odoo website framework. It supports multiple blogs, blog posts with full SEO metadata, tag categorization, and social sharing.

## Key Models

### blog.blog

Represents a blog (a collection of blog posts).

**Inherits:** `mail.thread`, `website.seo.metadata`, `website.multi.mixin`, `website.cover_properties.mixin`, `website.searchable.mixin`

**Fields:**
- `name`: Char - Blog name (required, translatable)
- `subtitle`: Char - Blog subtitle (translatable)
- `active`: Boolean - Active status
- `content`: Html - Blog introduction content
- `blog_post_ids`: One2many - Posts in this blog
- `blog_post_count`: Integer - Number of posts (computed)

**Key Methods:**

- `write(vals)`: When archiving/unarchiving a blog, the same operation cascades to all its blog posts.
- `message_post()`: Temporary workaround to prevent spam notifications: when a reply comes through the "Presentation Published" email, it is stored as a note rather than a regular message.
- `all_tags(join, min_limit)`: Returns tags used across posts in this blog.
  - If `join=True`: returns all unique tags across all posts (as a recordset)
  - If `join=False`: returns a dict mapping each blog ID to its tag recordset
  - Filters by `min_limit` frequency (only tags appearing at least `min_limit` times)
  - Uses a raw SQL query for performance with many posts
- `_search_get_detail(website, order, options)`: Integrates with website search, returning `blog.blog` model with domain filtered by website.
- `_search_render_results(fetch_fields, mapping, icon, limit)`: Renders search results with blog URL `/blog/{id}`.

### blog.tag

Represents a tag for categorizing blog posts within and across blogs.

**Inherits:** `website.seo.metadata`

**Fields:**
- `name`: Char - Tag name (required, unique)
- `category_id`: Many2one - Tag category grouping
- `color`: Integer - Color for UI display
- `post_ids`: Many2many - Posts with this tag

**SQL Constraints:**
- `name_uniq`: Tag names are unique across all blogs

**Key Methods:**
- `write()`: Writes to tag fields also mark linked posts as updated by calling `post_ids.write({})`. This is a workaround for stable-version t-cache issues where tag changes were not reflected in post caches.

### blog.tag.category

Groups blog tags into categories.

**Fields:**
- `name`: Char - Category name (required, unique)
- `tag_ids`: One2many - Tags in this category

### blog.post

Represents a single blog post.

**Inherits:** `mail.thread`, `website.seo.metadata`, `website.published.multi.mixin`, `website.cover_properties.mixin`, `website.searchable.mixin`

**Fields:**
- `name`: Char - Post title (required, translatable, default empty)
- `subtitle`: Char - Post subtitle (translatable)
- `author_id`: Many2one - Author partner (defaults to current user)
- `author_avatar`: Binary - Author's avatar image
- `author_name`: Char - Computed from author (stored for search)
- `active`: Boolean - Active status
- `blog_id`: Many2one - Parent blog (required, cascade delete)
- `tag_ids`: Many2many - Tags for this post
- `content`: Html - Post body content (default: "Start writing here...")
- `teaser`: Text - Short teaser/excerpt (computed from content if manual teaser not set)
- `teaser_manual`: Text - Manually set teaser (for translations)
- `published_date`: Datetime - Scheduled publication date
- `post_date`: Datetime - Effective publishing date (stored, computed inverse of `published_date`)
- `visits`: Integer - View counter (default 0, copy=False)
- `website_id`: Many2one - Website (computed from blog, stored)
- `website_message_ids`: One2many - Discussion threads (comments)
- `create_date`, `create_uid`, `write_date`, `write_uid`: Standard audit fields

**Key Computed Fields:**

- `_compute_website_url()`: Sets URL to `/blog/{blog_slug}/{post_slug}` using `ir.http._slug()`.
- `_compute_teaser()`: Returns `teaser_manual` if set; otherwise extracts the first 200 characters of stripped HTML content.
- `_compute_post_date()`: Returns `published_date` if set, otherwise `create_date`.

**Key Methods:**

- `_check_for_publication(vals)`: When a post is being published (either now or scheduled), sends a notification message to blog followers via `blog_id.message_post_with_source()` using the `blog_post_template_new_post` template.
- `create(vals_list)`: Uses `mail_create_nolog=True` context to suppress automatic chatter messages at creation. Calls `_check_for_publication()` for each post.
- `write(vals)`: Special handling for publication state changes:
  - Archiving a post also unpublished it (`is_published = False`)
  - When publishing (if `is_published` set to True) without a `published_date`, sets `published_date = now()`
  - Calls `_check_for_publication()` to send notifications
- `copy_data(default)`: Appends " (copy)" to the post name when duplicating.
- `_get_access_action(access_uid, force_website)`: For employees or published posts, redirects to the website URL instead of the backend form. For shareable links to unpublished posts, returns the standard form view.
- `_notify_get_recipients_groups(msg)`: Adds an access button to all notification groups for published posts.
- `_notify_thread_by_inbox(msg)`: Suppresses inbox (needaction) notifications for comments on blog posts; only email is sent.
- `_default_website_meta()`: Extends the base method with OpenGraph tags: `og:type = article`, `article:published_time`, `article:modified_time`, `article:tag` from post tags, and og image from cover properties.
- `_search_get_detail(website, order, options)`: Full website search integration with support for:
  - Filtering by blog (`blog` option)
  - Filtering by tags (`tag` option, supports multiple comma-separated tags)
  - Date range filtering (`date_begin`/`date_end`)
  - Designer state filtering (`published`/`unpublished` for website designers)
  - Full-text search in title, author name, and content
  - Tag-based search via `search_extra` callback

**Publication Workflow:**
1. Post is created with `is_published=False` (draft)
2. Editor sets `is_published=True` and optionally a future `published_date`
3. If `published_date` is in the past or empty, the post is immediately visible
4. `_check_for_publication()` sends a blog notification email to followers
5. Visitors see the post at `/blog/{blog_slug}/{post_slug}`

## Cross-Module Relationships

- **website**: Provides multi-website scoping (`website.multi.mixin`), SEO metadata, cover properties, search integration, and page URL generation
- **mail**: Discussion threads via `mail.thread`, notification emails
- **website_blog**: Self-referential Many2one (post belongs to blog)

## Edge Cases

1. **Tag Color Cache Invalidation**: When a tag's color is changed, all posts using that tag are touched (written with empty dict) to force template re-rendering with the new color. This works around t-cache limitations in stable versions.
2. **Teaser Translation**: When setting a manual teaser in one language, if there is no source value in `en_US`, the source is cleared. This prevents the automatic teaser from leaking into translations.
3. **Scheduled Publication**: Posts can have a future `published_date`. They are created as `is_published=True` but only become visible on the website after the date passes (handled by `website.published.mixin`'s `is_visible` logic).
4. **Visitor Tracking**: Blog posts track `visits` as an integer counter incremented on each view (distinct from the more sophisticated `website.visitor`/`website.track` system).
5. **Multi-Blog Tags**: Tags can be used across multiple blogs (tag_id is not scoped to a single blog). The `all_tags()` method aggregates tag usage per blog via SQL for performance.
6. **Author Avatar**: Uses `image_128` of the partner record as the author avatar.
7. **Cover Image for SEO**: The `website.cover_properties.mixin` provides a `cover_properties` JSON field storing background image, opacity, and resize class. This image is used in the OpenGraph `og:image` and Twitter `twitter:image` meta tags.
8. **Unpublished Posts**: Non-designers only see posts where `post_date <= now()`. Designers can see both published (with date filter) and unpublished posts.
