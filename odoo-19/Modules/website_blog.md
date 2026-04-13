---
type: module
module: website_blog
tags: [odoo, odoo19, website, blog, cms, content, publishing, seo]
created: 2026-04-11
updated: 2026-04-11
---

# Blog Module (`website_blog`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Blog |
| **Technical Name** | `website_blog` |
| **Category** | Website/Website |
| **Version** | 1.1 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module Path** | `odoo/addons/website_blog/` |
| **Sequence** | 200 |

## Description

Publish blog posts, announcements, and news articles. Supports multiple blogs per website, hierarchical tags, author management, featured images, scheduled publication, social sharing, comments, archive browsing, and full SEO integration. Blog posts are the primary content type for content marketing strategies in Odoo's CMS.

## Dependencies

```python
'depends': [
    'website_mail',     # Comment/discussion integration (mail.thread inheritance)
    'website_partner',  # Author partner profiles (image_128 avatar)
    'html_builder',     # HTML content building (html_translate)
]
```

`website` is a transitive dependency through the above three. No explicit `depends: ['website']` is declared in the manifest, but the models import from `website` mixins and the controller uses `request.website`.

---

## Architecture Overview

### Model Hierarchy

```
blog.blog              # Blog (section/container)
  └── blog.post        # Blog post (article)
        ├── blog.tag   # Tags (M2M via blog_post_blog_tag_rel)
        └── blog.tag.category  # Tag categories
```

### Key Design Patterns

1. **Multi-mixin inheritance** -- `blog.post` inherits 6 mixins for publishing, SEO, cover images, page visibility, and search
2. **Scheduled publication** -- `published_date` + `post_date` bi-directional compute for auto-publishing
3. **Teaser auto-generation** -- Computed from HTML content if `teaser_manual` is not set; handles i18n edge case
4. **Author as partner** -- `author_id` is a `res.partner` record, enabling full partner features (avatar via `image_128`, display name)
5. **Raw SQL tag aggregation** -- `all_tags()` uses direct SQL to avoid N+1 when computing tag frequency per blog
6. **Session-based visit deduplication** -- `visits` counter increments once per session per post, using `sql.increment_fields_skiplock` to avoid row locks
7. **Spam-resistant email replies** -- Replies to "Published Post" notification emails are converted to internal notes rather than公开发布 comments
8. **Multi-tag URL normalization** -- Slug mismatches in multi-tag URLs cause a 301 redirect to the corrected URL

---

## Module Structure

```
website_blog/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── website_blog.py     # BlogBlog, BlogPost, BlogTag, BlogTagCategory
│   ├── website.py          # Website controller hooks + configurator
│   └── website_snippet_filter.py  # Snippet filter defaults
├── controllers/
│   ├── __init__.py
│   └── main.py             # Blog HTTP routes
├── data/
│   ├── website_blog_data.xml        # Default blog, menu, mail subtype
│   ├── mail_templates.xml           # blog_post_template_new_post
│   ├── mail_message_subtype_data.xml
│   ├── website_blog_demo.xml
│   ├── blog_snippet_template_data.xml
│   └── website_blog_tour.xml
├── security/
│   ├── ir.model.access.csv  # Per-group CRUD ACLs
│   └── website_blog_security.xml  # ir.rule records
└── views/
    ├── website_blog_views.xml
    ├── website_blog_components.xml
    ├── website_blog_posts_loop.xml
    ├── website_blog_templates.xml
    ├── website_pages_views.xml
    ├── blog_post_add.xml
    └── snippets/
        ├── snippets.xml
        ├── s_blog_posts.xml
        └── s_dynamic_snippet_blog_posts_preview_data.xml
```

---

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `blog.blog` | `models/website_blog.py` | Blog (a section/category of posts) |
| `blog.post` | `models/website_blog.py` | Blog post (article) |
| `blog.tag` | `models/website_blog.py` | Tag for posts |
| `blog.tag.category` | `models/website_blog.py` | Tag category/group |

---

## `blog.blog`

**File:** `models/website_blog.py`

Represents a blog -- a section or category containing multiple posts. Multiple blogs allow separate editorial spaces (e.g., "Product News" vs "Company Updates"). The default blog at install is named "Our blog" with subtitle "We are a team of passionate people whose goal is to improve everyone's life."

### Inherits

```python
_inherit = [
    'mail.thread',                    # Comments and followers
    'website.seo.metadata',           # seo_name, website_meta_* fields
    'website.multi.mixin',             # website_id per-record scoping
    'website.cover_properties.mixin',  # cover_properties (JSON)
    'website.searchable.mixin',        # Full-text search integration
]
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `sequence` | Integer | No | `_default_sequence()` | Sort order. Computed as `max(existing sequence) + 1`. Used in blog ordering. |
| `name` | Char | Yes | -- | Blog display name. `translate=True`. |
| `subtitle` | Char | No | -- | Short description. `translate=True`. Shown in search descriptions. |
| `active` | Boolean | No | `True` | Archive/unarchive the blog. Cascades to all child posts. |
| `content` | Html | No | -- | Introductory content shown at top of blog page. `sanitize=False`, `translate=True`. |
| `blog_post_ids` | One2many | Auto | -- | Posts belonging to this blog. Related model: `blog.post.blog_id`. |
| `blog_post_count` | Integer | Auto | -- | Count of `blog_post_ids`. Computed via `_compute_blog_post_count`. |
| `cover_properties` | Text | Auto | JSON dict | Inherited from `website.cover_properties.mixin`. Default: `{"background_color_class": "o_cc3", "background-image": "none", "opacity": "0.2", "resize_class": "o_half_screen_height"}`. |
| `website_id` | Many2one | No | -- | Inherited from `website.multi.mixin`. Restricts blog to a specific website. |
| `is_seo_optimized` | Boolean | Auto | -- | Inherited from `website.seo.metadata`. `True` only when `website_meta_title`, `website_meta_description`, and `website_meta_keywords` are all set. |

### Key Methods

#### `write(vals)` -- Cascade active state

```python
def write(self, vals):
    res = super().write(vals)
    if 'active' in vals:
        post_ids = self.env['blog.post'].with_context(active_test=False).search([
            ('blog_id', 'in', self.ids)
        ])
        for blog_post in post_ids:
            blog_post.active = vals['active']
    return res
```

**Behavior:** Archiving/unarchiving a blog archives/unarchives all its posts. Uses `active_test=False` to ensure archived posts are also caught. Note: archiving sets `is_published=False` on posts via `BlogPost.write()`.

#### `all_tags(join=False, min_limit=1)`

```python
def all_tags(self, join=False, min_limit=1):
    # Raw SQL - bypasses ORM for performance
    req = """
        SELECT p.blog_id, count(*), r.blog_tag_id
        FROM blog_post_blog_tag_rel r
            JOIN blog_post p ON r.blog_post_id = p.id
        WHERE p.blog_id IN %s
        GROUP BY p.blog_id, r.blog_tag_id
        ORDER BY count(*) DESC
    """
```

**L4 -- Performance:** Raw SQL to avoid O(n) ORM overhead when aggregating tag frequencies across all posts. When `join=True`, returns the union of all tags across all blogs (used in the "All Blogs" index). `min_limit` filters out tags appearing fewer than N times. The `ORDER BY count(*) DESC` prioritizes popular tags for display.

**L4 -- Edge case:** If a tag is deleted after being assigned to posts, `tag_id` will reference a deleted row -- the `exists()` call on `BlogTag.browse(...)` in the controller handles this gracefully.

#### `message_post()` -- Spam workaround

```python
def message_post(self, *, parent_id=False, subtype_id=False, **kwargs):
    self.ensure_one()
    if parent_id:
        parent_message = self.env['mail.message'].sudo().browse(parent_id)
        if parent_message.subtype_id == self.env.ref('website_blog.mt_blog_blog_published'):
            subtype_id = self.env.ref('mail.mt_note').id
    return super().message_post(parent_id=parent_id, subtype_id=subtype_id, **kwargs)
```

**L4 -- Edge case:** When a user replies to the "Published Post" email notification (which has `mt_blog_blog_published` subtype), their reply would normally notify all blog followers. This override catches that case and demotes the reply to a private note (`mt_note`), preventing notification spam. Uses `sudo()` because the parent message may belong to another user.

#### `_search_get_detail(website, order, options)` -- Searchable mixin

Searches `name` and `subtitle` fields. Returns mapping with `website_url: '/blog/{id}'`. Orders by `name` (respects `desc` in order param) then `id desc` for stable pagination. Base domain applies `website.website_domain()`.

#### `_search_render_results(fetch_fields, mapping, icon, limit)` -- URL construction

Appends `/blog/{id}` to each search result. Overrides base implementation which would use generic `_url_for`.

#### `_CUSTOMER_HEADERS_LIMIT_COUNT = 0`

**L4 -- Mail thread behavior:** Setting this to `0` on the blog model (and `mail.thread` level) prevents Odoo from generating `X-Msg-To` and `X-Mailfolder` custom email headers in outgoing mail. These headers can cause deliverability issues with some mail servers and are unnecessary for blog notification emails.

---

## `blog.post`

**File:** `models/website_blog.py`

Represents a single blog article. This is the primary content model of the module.

### Inherits

```python
_inherit = [
    'mail.thread',                        # message_ids, followers, rating_ids
    'website.seo.metadata',               # seo_name, website_meta_* fields
    'website.published.multi.mixin',       # is_published, website_published, website_id
    'website.page_visibility_options.mixin',  # header_visible, footer_visible
    'website.cover_properties.mixin',      # cover_properties (JSON featured image)
    'website.searchable.mixin',             # Full-text search
]
_mail_post_access = 'read'  # Non-followers can read published posts without following
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | Char | Yes | `''` | Post title. `translate=True`. |
| `subtitle` | Char | No | -- | Short subtitle/teaser heading. `translate=True`. Used as OG description. |
| `author_id` | Many2one `res.partner` | No | `env.user.partner_id` | Author partner record. `index='btree_not_null'` for efficient author queries. |
| `author_avatar` | Binary | Auto | related `image_128` | Avatar image. `readonly=False` so it can be overridden per-post. |
| `author_name` | Char | Auto | related `display_name` | Author display name. Stored for search/sort performance. |
| `active` | Boolean | No | `True` | Draft/archive flag. |
| `blog_id` | Many2one `blog.blog` | Yes | first blog found | Parent blog. `ondelete='cascade'` if blog is deleted. Default falls back to `search([], limit=1)`. |
| `tag_ids` | Many2many `blog.tag` | No | -- | Tags via `blog_post_blog_tag_rel`. |
| `content` | Html | No | `"<p>Start writing here...</p>"` | Full post HTML. `sanitize=False`, `translate=True`. |
| `teaser` | Text | Auto | -- | Short teaser. Computed from `content` or `teaser_manual`. |
| `teaser_manual` | Text | No | -- | Manually entered teaser, bypassing auto-compute. |
| `published_date` | Datetime | No | -- | Scheduled publication datetime. Set automatically by `write()`. |
| `post_date` | Datetime | Auto | computed | Effective publication date. Computed from `published_date` or `create_date`. Bidirectional with `published_date`. |
| `visits` | Integer | Auto | `0` | View counter. Incremented by controller using `sql.increment_fields_skiplock`. |
| `website_id` | Many2one | Auto | related `blog_id.website_id` | Stored. Enables fast domain filtering. |
| `website_message_ids` | One2many | Auto | -- | Comments via lambda domain `[('model','=',self._name), ('message_type','=','comment')]`. |
| `is_published` | Boolean | No | `False` | Inherited from `website.published.multi.mixin`. Controls website visibility. |
| `website_published` | Boolean | No | computed | Inherited from `website.published.multi.mixin`. Context-aware version of `is_published`. |
| `website_url` | Char | Auto | computed | Inherited. URL: `/blog/{blog_slug}/{post_slug}`. |
| `header_visible` | Boolean | Auto | `True` | Inherited. Controls page header rendering. |
| `footer_visible` | Boolean | Auto | `True` | Inherited. Controls page footer rendering. |
| `cover_properties` | Text | Auto | JSON dict | Inherited from mixin. Used for featured image styling. |

### Computed Fields Detail

#### `teaser` -- Summary/Excerpt

```python
@api.depends('content', 'teaser_manual')
def _compute_teaser(self):
    for blog_post in self:
        if blog_post.teaser_manual:
            blog_post.teaser = blog_post.teaser_manual
        else:
            content = text_from_html(blog_post.content, True)
            blog_post.teaser = content[:200] + '...'

def _set_teaser(self):
    for blog_post in self:
        if not blog_post.with_context(lang='en_US').teaser_manual:
            # Clear source value when setting a translation to avoid
            # ORM silently copying the translated value back to the source
            blog_post.update_field_translations('teaser_manual', {'en_US': ''})
        blog_post.teaser_manual = blog_post.teaser
```

**L4 -- Translation edge case:** The inverse setter checks `with_context(lang='en_US')` to detect when the user is writing a translation for a post whose source (English) has no manual teaser. Without this check, the ORM would copy the translated teaser value into the source field, breaking the auto-compute for all other languages. The `update_field_translations` call clears the source field value explicitly.

#### `post_date` -- Effective Publishing Date

```python
@api.depends('create_date', 'published_date')
def _compute_post_date(self):
    for blog_post in self:
        if blog_post.published_date:
            blog_post.post_date = blog_post.published_date
        else:
            blog_post.post_date = blog_post.create_date

def _set_post_date(self):
    for blog_post in self:
        blog_post.published_date = blog_post.post_date
        if not blog_post.published_date:
            blog_post.post_date = blog_post.create_date
```

**L4 -- Bidirectional flow:** Setting `post_date` writes to `published_date`, but setting `published_date` does NOT automatically trigger a write-back to `post_date` (that happens via the `@api.depends`). If `published_date` is cleared, `post_date` recomputes from `create_date`.

### Publishing Workflow

```
Draft (is_published=False)
    ↓
write({'is_published': True})
    ↓
write() loop: sets published_date=NOW() if not already set and either
              already past or not set at all
    ↓
_check_for_publication(vals) called after super().write()
    ↓
If is_published=True AND post.active:
  → blog_id.message_post_with_source(
      'website_blog.blog_post_template_new_post',
      subject=post.name,
      render_values={'post': post},
      subtype_xmlid='website_blog.mt_blog_blog_published',
    )
  → Notifies all blog followers
    ↓
Published post visible on website
```

**L4 -- Published date auto-set logic:**

```python
# In write(), per post:
published_in_vals = set(vals.keys()) & {'is_published', 'website_published'}
if (published_in_vals and 'published_date' not in vals and
        (not post.published_date or post.published_date <= fields.Datetime.now())):
    copy_vals['published_date'] = vals[list(published_in_vals)[0]] and fields.Datetime.now() or False
```

Key conditions:
- Only auto-sets if publishing is in the vals (True or False)
- Does NOT auto-set `published_date` if it's already in `vals`
- Only sets to `now()` if `published_date` is not already set, OR if it's already in the past (allowing future scheduling to stand)
- If unpublishing (`= False`), sets `published_date = False`

### Key Methods

#### `_check_for_publication(vals)`

Called after `create()` and `write()`. Only fires a notification when transitioning to published. Uses `filteread(lambda p: p.active)` to skip notification for archived posts being published (draft state).

#### `_compute_website_url()`

```python
def _compute_website_url(self):
    super()._compute_website_url()
    for blog_post in self:
        if blog_post.id:
            blog_post.website_url = "/blog/%s/%s" % (
                self.env['ir.http']._slug(blog_post.blog_id),
                self.env['ir.http']._slug(blog_post)
            )
```

Uses `_slug()` which strips special characters and joins with hyphens. Slug is derived from the `name` field.

#### `write(vals)` -- Cascade and published_date

```python
def write(self, vals):
    result = True
    if 'active' in vals and not vals['active']:
        vals['is_published'] = False  # archiving unpublishes
    for post in self:
        copy_vals = dict(vals)
        # auto-set published_date when publishing
        published_in_vals = set(vals.keys()) & {'is_published', 'website_published'}
        if (published_in_vals and 'published_date' not in vals and
                (not post.published_date or post.published_date <= fields.Datetime.now())):
            copy_vals['published_date'] = vals[list(published_in_vals)[0]] and fields.Datetime.now() or False
        result &= super(BlogPost, post).write(copy_vals)
    self._check_for_publication(vals)
    return result
```

Note: loops per-record but `result &=` collects all outcomes. A single failure causes the overall return to be falsy.

#### `_get_access_action()` -- Website redirect

```python
def _get_access_action(self, access_uid=None, force_website=False):
    self.ensure_one()
    user = self.env['res.users'].sudo().browse(access_uid) if access_uid else self.env.user
    if not force_website and user.share and not self.sudo().website_published:
        return super()._get_access_action(...)  # returns forbidden
    return {
        'type': 'ir.actions.act_url',
        'url': self.website_url,
        'target': 'self',
        'target_type': 'public',
        'res_id': self.id,
    }
```

**L4 -- Access logic:** If the user is a portal/share user AND the post is not published, fall back to the standard form view (which will show a access error). For employees or published posts, redirect to the public website URL.

#### `_notify_thread_by_inbox()` -- Silence inbox for comments

```python
def _notify_thread_by_inbox(self, message, recipients_data, msg_vals=False, **kwargs):
    msg_vals = msg_vals or {}
    if msg_vals.get('message_type', message.message_type) == 'comment':
        return  # Skip inbox notification for comments
    return super()._notify_thread_by_inbox(...)
```

**L4 -- Design rationale:** Comment-type messages on blog posts are handled by the website's native comment form (from `website_mail`). Email notifications are sufficient for comment alerts. The Odoo's internal inbox/notification bell would create duplicate notifications, degrading user experience. This override prevents the `mail.thread` inbox notification channel from firing for blog post comments.

#### `_notify_get_recipients_groups()` -- Add access button

When `website_published` is True, sets `has_button_access = True` on all recipient groups in notification emails. This renders an "Access" button in notification emails linking directly to the post.

#### `_default_website_meta()` -- Social sharing OpenGraph

```python
def _default_website_meta(self):
    res = super()._default_website_meta()
    res['default_opengraph']['og:description'] = self.subtitle
    res['default_opengraph']['og:type'] = 'article'
    res['default_opengraph']['article:published_time'] = self.post_date
    res['default_opengraph']['article:modified_time'] = self.write_date
    res['default_opengraph']['article:tag'] = self.tag_ids.mapped('name')
    # background-image might contain single quotes: url('/my/url')
    res['default_opengraph']['og:image'] = json_scriptsafe.loads(
        self.cover_properties
    ).get('background-image', 'none')[4:-1].strip("'")
    res['default_opengraph']['og:title'] = self.name
    res['default_twitter']['twitter:title'] = self.name
    res['default_twitter']['twitter:description'] = self.subtitle
    res['default_meta_description'] = self.subtitle
    return res
```

**L4 -- OG image extraction:** Parses the `cover_properties` JSON. The `background-image` value is of the form `url('/web/image/ir.attachment/123/resized/400x300')` or `url('/website_blog/static/src/img/cover.jpg')`. It strips `url(` (4 chars) and `)` (last char), then strips any surrounding single quotes. Falls back to `'none'` if no image.

#### `_search_get_detail(website, order, options)` -- Searchable mixin

```python
search_fields = ['name', 'author_name']  # always searched
search_extra = search_in_tags  # tags matching search term also matched
fetch_fields = ['name', 'website_url']   # always fetched
if with_description:
    search_fields.append('content')      # add content to search
    fetch_fields.append('content')       # include in results
if with_date:
    fetch_fields.append('published_date')
    mapping['detail'] = {'name': 'published_date', 'type': 'date'}
```

**L4 -- State filtering for designers:**

```python
if request.env.user.has_group('website.group_website_designer'):
    if state == "published":
        domain.append([("website_published", "=", True), ("post_date", "<=", fields.Datetime.now())])
    elif state == "unpublished":
        domain.append(['|', ("website_published", "=", False), ("post_date", ">", fields.Datetime.now())])
else:
    domain.append([("post_date", "<=", fields.Datetime.now())])
```

Designers can filter by published/unpublished. Public users only see published posts with `post_date <= now`. The `state='unpublished'` domain uses OR logic: either not published OR scheduled for future.

---

## `blog.tag`

**File:** `models/website_blog.py`

Organizational labels for posts. Inherits `website.seo.metadata` for optional per-tag SEO.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Tag name. `translate=True`. Uniqueness enforced via SQL constraint. |
| `category_id` | Many2one `blog.tag.category` | No | Parent category. `index=True`. |
| `color` | Integer | No | Color index for UI (color_picker widget). |
| `post_ids` | Many2many `blog.post` | Auto | Reverse of `blog.post.tag_ids`. |

### Constraints

```python
_name_uniq = models.Constraint(
    'unique (name)',
    'Tag name already exists!',
)
```

**L4 -- Uniqueness scope:** The constraint is global, not per-blog. Two blogs cannot share a tag with the same name. Use `category_id` to disambiguate if needed.

---

## `blog.tag.category`

**File:** `models/website_blog.py`

Groups tags into categories (e.g., "Product", "Company", "Industry").

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Category name. `translate=True`. Uniqueness enforced. |
| `tag_ids` | One2many `blog.tag` | Auto | Tags in this category. |

### Constraints

```python
_name_uniq = models.Constraint(
    'unique (name)',
    'Tag category already exists!',
)
```

---

## Controller Routes (`controllers/main.py`)

**Class:** `WebsiteBlog` (`http.Controller`)

### Pagination Constants

```python
_blog_post_per_page = 12    # posts per listing page (multiple of 2,3,4 for grid layouts)
_post_comment_per_page = 10 # comments per page (not currently used in routing, future use)
```

### Routes

#### `GET /blog[/page/N][/tag/TAG][/tag/TAG/page/N]`

```
@route([...patterns...], type='http', auth="public", website=True, sitemap=True,
       list_as_website_content=_lt("Blogs"))
def blog(self, blog=None, tag=None, page=1, search=None, **opt)
```

- If only one blog exists and no specific blog is requested: 302 redirect to that blog's URL
- Multi-tag URLs: 302 redirect to first tag only (avoids duplicate content)
- `opt` contains: `date_begin`, `date_end`, `state` (designer filter)
- Renders template: `website_blog.blog_post_short`

#### `GET /blog/BLOG/feed?limit=N`

```
@route(['/blog/<model("blog.blog"):blog>/feed'], type='http', auth="public",
       website=True, sitemap=True)
def blog_feed(self, blog, limit='15', **kwargs)
```

Returns Atom feed (`application/atom+xml`). Limit is capped at 50. Only includes posts belonging to the specified blog, ordered by `post_date DESC`. Does not filter by publication state (a known design choice -- the feed is public).

#### `GET /blog/BLOG/POST` (v14 compatibility)

```
@route([...old pattern...], ...)
def old_blog_post(self, blog, blog_post, **post)
```

Pre-v14 URL pattern `/blog/BLOG/post/POST`. Returns 301 redirect to new pattern `/blog/BLOG/POST`.

#### `GET /blog/BLOG/POST`

```
@route([...new pattern...], type='http', auth="public", website=True, sitemap=True)
def blog_post(self, blog, blog_post, tag_id=None, page=1, enable_editor=None, **post)
```

**Parameters:**
- `blog`: Required `blog.blog` record matched from URL pattern with inline domain `[('blog_id','=',blog.id)]`
- `blog_post`: `blog.post` with inline domain ensuring it belongs to `blog`
- `tag_id`: Optional int -- highlights a specific tag in the UI
- `enable_editor`: If set, activates the website editor on the page
- `post`: `date_begin`, `date_end` for archive-aware URL state

**Next/previous navigation:** The controller computes `next_post` as the post immediately after the current one in `all_post_ids` (circular: last post links to first). Only considers published posts with `post_date <= now` for non-designers.

**Visit counter logic:**

```python
if blog_post.id not in request.session.get('posts_viewed', []):
    if sql.increment_fields_skiplock(blog_post, 'visits'):
        if not request.session.get('posts_viewed'):
            request.session['posts_viewed'] = []
        request.session['posts_viewed'].append(blog_post.id)
        request.session.touch()
```

**L4 -- Performance and correctness:**
- `sql.increment_fields_skiplock` uses `UPDATE ... SET visits = visits + 1 WHERE id = %s` with `FOR UPDATE SKIP LOCKED` semantics. This avoids blocking concurrent requests for the same post and silently skips if the row is locked by another transaction.
- The `posts_viewed` session list prevents double-counting if the user refreshes the page within the same session.
- `session.touch()` extends the session lifetime on each page view.

### Helper Methods

#### `nav_list(blog=None)`

Uses `_read_group` with `post_date:month` granularity to produce year/month archive navigation:

```python
groups = request.env['blog.post']._read_group(
    dom, groupby=['post_date:month'])
# Returns: { '2024': [{'date_begin': ..., 'date_end': ..., 'month': 'January', 'year': '2024'}, ...], ... }
```

Uses `READ_GROUP_TIME_GRANULARITY['month']` (a models constant) to compute `date_end` as start of next month.

#### `_prepare_blog_values(blogs, blog, ...)` -- Value dictionary builder

**L4 -- Lazy evaluation for performance:**
```python
all_tags = tools.lazy(lambda: blogs.all_tags(join=True) if not blog
                       else blogs.all_tags().get(blog.id, request.env['blog.tag']))
pager = tools.lazy(lambda: request.website.pager(...))
nav_list = tools.lazy(lambda: self.nav_list(blog))
```

These are wrapped in `tools.lazy()` to avoid expensive computation if the template doesn't render the sidebar/pager.

**L4 -- URL normalization redirect:**
```python
fixed_tag_slug = ",".join(request.env['ir.http']._slug(t) for t in active_tags)
if fixed_tag_slug != tags:
    new_url = path.replace("/tag/%s" % tags, ...)
    return request.redirect(new_url, 301)
```

If tag slugs don't match (e.g., special characters normalized), redirect to the canonical URL. This prevents Google from indexing multiple URLs for the same tag combination.

---

## Website Model Extensions (`models/website.py`)

The `website_blog` module extends `website` (the `website.website` model) via `_inherit = 'website'`.

### `get_suggested_controllers()`

Appends Blog to the "Suggested Controllers" list shown in website configurator. Icon: `website_blog`.

### `configurator_set_menu_links(menu_company, module_data)`

Called during website configurator setup. For each blog entry in `module_data.get('#blog', [])`:
1. Creates a `blog.blog` record
2. Creates a `website.menu` with URL `/blog/{blog_id}`
3. If it's the first blog (`idx == 0`), updates the existing `/blog` menu instead of creating a new one

**L4 -- Upgrading existing menu:** The existing "Blog" menu from `website_blog_data.xml` has URL `/blog`. When the configurator sets up a named blog, it reuses that menu entry with the specific blog URL, avoiding duplicate menu items.

### `_search_get_details(search_type, order, options)`

Extends the website global search. When `search_type in ['blogs', 'blogs_only', 'all']`, adds `blog.blog._search_get_detail(...)`. When `search_type in ['blogs', 'blog_posts_only', 'all']`, adds `blog.post._search_get_detail(...)`.

---

## WebsiteSnippetFilter Extensions (`models/website_snippet_filter.py`)

Extends `website.snippet.filter` for the dynamic snippet builder.

### `_get_hardcoded_sample(model)` -- Snippet preview data

When the snippet builder has no real data, it returns sample posts. For `blog.post`, merges generic snippet samples with blog-specific samples:

```python
# Blog samples merged at interleaved indices
merged = []
for index in range(0, max(len(samples), len(data))):
    merged.append({**samples[index % len(samples)], **data[index % len(data)]})
```

This creates a grid of sample posts with realistic blog cover images and names (Islands, Skies, Viewpoints, etc.).

### `default_get(fields)` -- Snippet field defaults

```python
if 'field_names' in defaults and self.env.context.get('model') == 'blog.post':
    defaults['field_names'] = 'name,teaser,subtitle'
```

When the snippet filter is opened for `blog.post`, default the displayed fields to `name, teaser, subtitle` (instead of the generic default).

---

## Security

### Access Control List (`ir.model.access.csv`)

| Record | Model | Group | R | W | C | D |
|--------|-------|-------|---|---|---|---|
| `blog_blog_public` | `blog.blog` | `base.group_public` | 1 | 0 | 0 | 0 |
| `blog_blog_portal` | `blog.blog` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `blog_blog_employee` | `blog.blog` | `base.group_user` | 1 | 0 | 0 | 0 |
| `blog_blog` | `blog.blog` | `website.group_website_designer` | 1 | 1 | 1 | 1 |
| `blog_post_public` | `blog.post` | `base.group_public` | 1 | 0 | 0 | 0 |
| `blog_post_portal` | `blog.post` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `blog_post_employee` | `blog.post` | `base.group_user` | 1 | 0 | 0 | 0 |
| `blog_post` | `blog.post` | `website.group_website_designer` | 1 | 1 | 1 | 1 |
| `blog_tag_public` | `blog.tag` | `base.group_public` | 1 | 0 | 0 | 0 |
| `blog_tag_edition` | `blog.tag` | `website.group_website_designer` | 1 | 1 | 1 | 1 |
| `blog_tag_category_public` | `blog.tag.category` | `base.group_public` | 1 | 0 | 0 | 0 |
| `blog_tag_category` | `blog.tag.category` | `website.group_website_designer` | 1 | 1 | 1 | 1 |

**L4 -- Design:** Public/portal/employee groups get read-only access to all blog models. Only `website.group_website_designer` (website editors in Odoo) gets write/create/delete. This means employees in the internal interface can view blogs but cannot edit them unless given website designer rights.

### Record Rules (`security/website_blog_security.xml`)

```xml
<!-- Public/portal users only see published blog posts -->
<record model="ir.rule" id="website_blog_post_public">
    <field name="domain_force">[('website_published', '=', True)]</field>
    <field name="groups" eval="[(4, ref('base.group_public')), (4, ref('base.group_portal'))]"/>
</record>

<!-- Public/portal users only see active blogs -->
<record model="ir.rule" id="website_blog_public">
    <field name="domain_force">[('active', '=', True)]</field>
    <field name="groups" eval="[(4, ref('base.group_public')), (4, ref('base.group_portal'))]"/>
</record>
```

**L4 -- Record rule scope:** The `website_blog_post_public` rule uses `website_published` (the context-aware computed field from `website.published.multi.mixin`) rather than `is_published`. This means a portal user browsing website A will not see posts published only on website B.

### `_mail_post_access = 'read'`

On `blog.post`: Mail thread access for non-followers is `read`. This allows blog post comments to be readable by anyone with portal access, even without following the post. Without this, portal users would get access errors when viewing comment threads.

---

## Mail/Chatter Integration

### Mail Message Subtype

```xml
<record id="mt_blog_blog_published" model="mail.message.subtype">
    <field name="name">Published Post</field>
    <field name="res_model">blog.blog</field>
    <field name="default" eval="True"/>
</record>
```

Posted on `blog.blog` (not `blog.post`) when a post is published. Blog followers are notified of new posts via this subtype on the blog, not on individual posts.

### Mail Template (`blog_post_template_new_post`)

```xml
<template id="blog_post_template_new_post">
    <p>A new post <t t-out="post.name"/> has been published on the
       <t t-out="object.name"/> blog.</p>
    <a t-attf-href="/blog/#{slug(object)}/#{slug(post)}">Access post</a>
</template>
```

Rendered with `object=blog` and `post=blog_post`. Sends as email to blog followers.

---

## L4: Performance Implications

| Area | Pattern | Risk |
|------|---------|------|
| `blog_post_count` compute | `len(blog_post_ids)` one2many | N+1 when displaying many blogs in a list. Use `read_group` for batch counting. |
| `all_tags()` raw SQL | Direct `cr.execute()` | Fast, but bypasses `active_test` context. Does not filter by `website_id`. |
| `nav_list()` archive query | `_read_group` with `post_date:month` | Groups all posts; no website filter in the raw query (relies on domain pre-filtering). |
| Visit counter | `sql.increment_fields_skiplock` | Non-blocking; safe under concurrent load. No transaction rollback on lock contention. |
| Snippet filter | Merges samples lazily | Only computed when snippet is rendered in edit mode. |
| Cover image URL | `_get_background(height, width)` | Rewrites image URL to include resize params; may cause CDN cache misses if called with varying dimensions. |
| `teaser` compute | `text_from_html()` on every write | O(n) in HTML content length. `teaser_manual` bypasses this. |

---

## L4: Historical Changes (Odoo 18 to 19)

1. **`blog.post` URL slug changed** -- Pre-v14 the URL was `/blog/BLOG/post/POST`. Since v14, it is `/blog/BLOG/POST`. The controller maintains a compatibility redirect (301) at `/blog/BLOG/post/POST`.

2. **`website.published.multi.mixin` replaces `website.published.mixin`** -- The `blog.post` model now uses the multi-website variant. This changes how `website_published` is computed (now context-aware and stored via inverse).

3. **`website.cover_properties.mixin` write override** -- In Odoo 18/19, writing to `cover_properties` preserves the `resize_class` from the existing value if the new JSON doesn't include a valid resize class. This prevents grid/list view renders from stripping the cover's height.

4. **`mail.thread` inbox override** -- The `_notify_thread_by_inbox` override silencing comment notifications was added to reduce notification noise as blog usage scaled.

5. **`website.page_visibility_options.mixin` added** -- `header_visible` and `footer_visible` fields were added to allow per-post control over page chrome. This was part of a broader Odoo 17+ website builder enhancement.

---

## L4: Edge Cases

1. **No default blog** -- If `blog.blog` has no records, creating a `blog.post` without specifying `blog_id` will raise a validation error (the `search([], limit=1)` default returns `False` but the field is required).

2. **Tag slug normalization** -- When filtering by multiple tags, the controller compares normalized slugs. If the input tag string doesn't match after slugification, a 301 redirect to the canonical URL occurs. This prevents duplicate content from differently-encoded tag URLs.

3. **Future-dated publication** -- Posts with `published_date > now` are visible to designers via the "unpublished" filter but hidden from public. Once `post_date` passes, they auto-publish if `is_published = True` was already set.

4. **Copying a post** -- `copy_data()` appends " (copy)" to the post name using `_("%s (copy)")` for i18n. The slug-based URL will differ from the original.

5. **Deleted blog** -- Since `blog_id` has `ondelete='cascade'`, deleting a `blog.blog` deletes all its posts. This is not reversible without a database restore.

6. **Cover image on deleted attachment** -- The `cover_properties` JSON stores image URLs as `url('/web/image/ir.attachment/ID/...')`. If the attachment is deleted, the URL 404s silently on the frontend. No orphan cleanup is performed.

---

## Snippet Templates

The module registers 8 snippet variations in the website editor:

| Snippet | Template ID | Description |
|---------|-------------|-------------|
| Blog Posts Big Picture | `s_blog_posts_big_picture` | Large hero-style cards |
| Blog Posts Card | `s_blog_posts_card` | Standard card with image |
| Blog Posts Horizontal | `s_blog_posts_horizontal` | Horizontal list item |
| Blog Posts List | `s_blog_posts_list` | Compact list view |
| Blog Post Single Aside | `s_blog_posts_single_aside` | Sidebar featured post |
| Blog Post Single Full | `s_blog_posts_single_full` | Full-width single post |
| Blog Post Single Circle | `s_blog_posts_single_circle` | Circular avatar + text |
| Blog Post Single Badge | `s_blog_posts_single_badge` | Badge/sticker style |

All snippets inherit from `website.s_snippet_group` and are registered in the `blogs` snippet group. Dynamic versions use `website.snippet.filter` with the `blog.post` model.

---

## Key SQL Queries

### Tags by Blog Frequency

```sql
SELECT p.blog_id, count(*), r.blog_tag_id
FROM blog_post_blog_tag_rel r
  JOIN blog_post p ON r.blog_post_id = p.id
WHERE p.blog_id IN %s
GROUP BY p.blog_id, r.blog_tag_id
ORDER BY count(*) DESC
```

### Archive Navigation (via `_read_group`)

```sql
SELECT date_trunc('month', post_date), count(*)
FROM blog_post
WHERE blog_id = %s AND post_date <= %s AND active = True
GROUP BY date_trunc('month', post_date)
ORDER BY date_trunc('month', post_date) DESC
```

### Visit Counter Increment (non-blocking)

```sql
UPDATE blog_post
SET visits = visits + 1
WHERE id = %s
-- FOR UPDATE SKIP LOCKED implied by sql.increment_fields_skiplock
```

---

## Related Modules and Mixins

| Module/Mixin | Model | Relationship |
|-------------|-------|-------------|
| `website` | `website.website` | Blog controller context, website domain |
| `website_mail` | mail.thread | Comment/chatter on posts and blogs |
| `website_partner` | `res.partner` | Author avatar via `image_128` |
| `html_builder` | -- | `html_translate` for content field |
| `website.seo.metadata` | Abstract | SEO fields on blog and post |
| `website.published.multi.mixin` | Abstract | `is_published`, `website_published` |
| `website.multi.mixin` | Abstract | `website_id` on blog and post |
| `website.cover_properties.mixin` | Abstract | `cover_properties` JSON |
| `website.page_visibility_options.mixin` | Abstract | `header_visible`, `footer_visible` |
| `website.searchable.mixin` | Abstract | Full-text search |
| `rating` | `rating.rating` | Inherited via `mail.thread` on posts |
| `website_slides` | -- | Similar architecture; reference for comparison |

---

## Related

- [Modules/website](modules/website.md) -- Website framework (required dependency)
- [Modules/website_mail](modules/website_mail.md) -- Comment/discussion integration
- [Modules/website_partner](modules/website_partner.md) -- Author partner profiles
- [Modules/website_slides](modules/website_slides.md) -- E-learning (uses similar content patterns)
- [Modules/website_event](modules/website_event.md) -- Event module (similar architecture)
- [Core/API](core/api.md) -- @api.depends, computed fields, inverse methods
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) -- State machine and action methods
- [Modules/res.partner](modules/res.partner.md) -- Author partner model
- [Core/Fields](core/fields.md) -- Field type reference (Char, Many2one, Html, etc.)
