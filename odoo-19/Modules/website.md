---
type: module
module: website
tags: [odoo, odoo19, website, cms, website-builder, frontend, multi-website, seo]
created: 2026-04-11
---

# Website Module (website)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Website |
| **Technical Name** | `website` |
| **Category** | Website/Website |
| **Version** | 19.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module Path** | `odoo/addons/website/` |
| **External Python Deps** | `geoip2` (via `python-geoip2` apt package) |

## Description

Enterprise website builder providing full CMS capabilities, drag-and-drop page building, multi-website support, SEO optimization, visitor tracking, CDN integration, and website analytics. The website module is the foundation for all website-related functionality in Odoo, from simple landing pages to complex e-commerce storefronts.

### Dependencies

```python
'depends': [
    'digest',        # KPI dashboards
    'web',           # Web framework
    'html_editor',   # WYSIWYG editor
    'http_routing',  # URL routing
    'portal',        # Portal/guest access
    'social_media',  # Social media links
    'auth_signup',   # User registration
    'mail',          # Messaging/email
    'google_recaptcha',  # CAPTCHA
    'utm',           # UTM tracking
    'html_builder',  # HTML building
]
```

---

## Architecture Overview

### Key Design Patterns

1. **Multi-website isolation** via `website_id` on most models
2. **Delegation inheritance** (`_inherits`) for `website.page` and `website.controller.page` referencing `ir.ui.view`
3. **Mixins** for reusable website behaviors (publishing, SEO, cover images, search)
4. **COW (Copy-on-Write)** for per-website view customization
5. **Page caching** with smart invalidation based on website, language, session
6. **Raw SQL UPSERT** for visitor tracking to minimize DB round-trips
7. **ORM cache** at multiple levels: routing map, template cache, per-request cache

### Model Hierarchy

```
website                     # Multi-website config
  ├── website.page         # CMS pages (inherits ir.ui.view via _inherits)
  ├── website.menu         # Navigation tree
  ├── website.visitor      # Visitor profile and tracking
  │     └── website.track # Individual page view records
  ├── website.rewrite      # URL redirects / rewrites
  ├── website.route        # Auto-catalogued HTTP routes (read-only registry)
  └── website.controller.page  # Model-driven dynamic pages (inherits ir.ui.view)
```

### Mixin Classes (shared behaviors)

| Mixin | File | Purpose |
|-------|------|---------|
| `website.multi.mixin` | `mixins.py` | Per-record `website_id` field |
| `website.published.mixin` | `mixins.py` | `is_published` toggle + live preview button |
| `website.published.multi.mixin` | `mixins.py` | Combines multi.mixin + published.mixin + website-aware inverse |
| `website.seo.metadata` | `mixins.py` | SEO fields: title, description, keywords, og:image |
| `website.cover_properties.mixin` | `mixins.py` | JSON cover image styling |
| `website.page_visibility_options.mixin` | `mixins.py` | Header/footer visibility per record |
| `website.page_options.mixin` | `mixins.py` | Header overlay, color customization |
| `website.searchable.mixin` | `mixins.py` | Full-text search across website |

### Complete File Inventory

| File | Purpose |
|------|---------|
| `models/__init__.py` | Imports all 36 sub-modules |
| `models/website.py` | `website` model + `website.route` + `website.rewrite` |
| `models/website_page.py` | `website.page` (delegation inherits `ir.ui.view`) |
| `models/website_menu.py` | `website.menu` (hierarchical navigation) |
| `models/website_visitor.py` | `website.visitor` + `website.track` |
| `models/website_rewrite.py` | `website.rewrite` + `website.route` |
| `models/mixins.py` | All 8 abstract mixin classes |
| `models/ir_http.py` | `ir.http` extension (routing, middleware, public user) |
| `models/ir_ui_view.py` | `ir.ui.view` extension (COW mechanism, visibility) |
| `models/website_form.py` | Form builder (extends `ir.model`, `ir.model.fields`) |
| `models/website_controller_page.py` | `website.controller.page` |
| `models/website_snippet_filter.py` | `website.snippet.filter` (dynamic snippet data source) |
| `models/res_partner.py` | Adds `visitor_ids` and map helpers to `res.partner` |
| `models/res_config_settings.py` | Website settings panel |
| `models/res_company.py` | Company-level website bindings |
| `models/theme_models.py` | Theme installation management |
| `models/assets.py` | Asset bundling and CDN rewriting |
| `models/ir_attachment.py` | Attachment website scoping |
| `models/ir_model_data.py` | XML-ID management per website |
| `models/ir_rule.py` | Record rules for website-scoped access |
| `models/ir_ui_menu.py` | Backend menu website filtering |
| `controllers/main.py` | Homepage, sitemap, robots.txt, page rendering |
| `controllers/backend.py` | Backend website preview action |
| `security/website_security.xml` | Groups and record rules |

---

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `website` | `website.py` | Website configuration |
| `website.page` | `website_page.py` | CMS page (delegates to `ir.ui.view`) |
| `website.menu` | `website_menu.py` | Navigation menu tree |
| `website.visitor` | `website_visitor.py` | Visitor profile and tracking |
| `website.track` | `website_visitor.py` | Individual page view records |
| `website.rewrite` | `website_rewrite.py` | URL redirects / rewrites |
| `website.route` | `website.py` | Auto-catalogued HTTP routes (read-only registry, not a real ORM model in the traditional sense) |

---

## website

**File:** `models/website.py`

Central model representing a single website instance. Each website has its own domain, company, language configuration, menus, pages, and visitors. Heavily instrumented with `ormcache` decorators for high-traffic performance.

### Inheritance

- Inherits from `base.model` (ORM base) -- does **not** use `_inherit` to extend another model.
- Adds `website.domain()` as a computed class method for filtering.

### Class Methods (ORM domain helpers)

```python
def website_domain(self) -> Domain
    # Returns Domain('website_id', 'in', [False, *self.ids])
    # Used to scope any search to "generic + this website's records"

def _active_languages(self) -> list[int]
    # Returns IDs of all installed languages

def _default_language(self) -> res.lang.id
    # Returns the lang from ir.default 'res.partner.lang'
    # Falls back to the first active language
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | Char | Yes | — | Website display name |
| `sequence` | Integer | No | `10` | Sort order across websites |
| `domain` | Char | No | `False` | Primary domain, e.g. `https://shop.example.com` |
| `domain_punycode` | Char | Auto | Computed | ASCII-encoded domain for IDN support (e.g. `xn--...` for unicode domains) |
| `company_id` | Many2one | Yes | `self.env.company` | Associated `res.company` |
| `language_ids` | Many2many | Yes | `_active_languages()` | All enabled languages |
| `language_count` | Integer | Auto | Computed | `len(language_ids)` |
| `default_lang_id` | Many2one | Yes | `_default_language()` | Default landing language; on change to `language_ids`, auto-resets to first remaining language if removed |
| `auto_redirect_lang` | Boolean | No | `True` | Auto-redirect based on browser `Accept-Language` header |
| `user_id` | Many2one | Yes | Auto from `company._get_public_user()` or `base.public_user` | "Public user" -- the `res.users` record executed for unauthenticated visitors |
| `partner_id` | Many2one | Auto | `user_id.partner_id` | Public partner (synced) |
| `menu_id` | Many2one | Auto | Computed via `_compute_menu` | Root `website.menu` for this site |
| `homepage_url` | Char | No | `False` | Custom redirect for homepage, e.g. `/shop`. Must start with `/`. Trailing slash stripped on write via `_handle_homepage_url`. |
| `logo` | Binary | No | SVG from `website/static/src/img/website_logo.svg` | Website-specific logo |
| `favicon` | Binary | No | ICO from `web/static/img/favicon.ico` | Favicon, auto-converted to 256x256 ICO on write via `_handle_favicon` |
| `theme_id` | Many2one | No | `False` | Currently installed theme (`ir.module.module`) |
| `specific_user_account` | Boolean | No | `False` | If True, new portal signups are tied to this website |
| `auth_signup_uninvited` | Selection | No | `'b2b'` | `'b2b'` = invite only; `'b2c'` = free signup |
| `cookies_bar` | Boolean | No | `False` | Show cookie consent banner. On enable: auto-creates `/cookie-policy` page via `website.cookie_policy` view. On disable: deletes that page. |
| `block_third_party_domains` | Boolean | No | `True` | Block tracking domains (YouTube, Google Maps, etc.) |
| `custom_blocked_third_party_domains` | Text | No | `False` | User-defined additional blocked domains; lines starting with `#` are comments; `#ignore_default` as first line replaces the default list entirely |
| `blocked_third_party_domains` | Text | Auto | Computed | Merged default + custom blocked domains |
| `cdn_activated` | Boolean | No | `False` | Enable CDN URL rewriting |
| `cdn_url` | Char | No | `''` | CDN base URL |
| `cdn_filters` | Text | No | newline-joined `DEFAULT_CDN_FILTERS` | URL patterns (regex) triggering CDN rewrite. Written as one regex per line. |
| `custom_code_head` | Html | No | `False` | Custom `<script>`/`<style>` injected in `<head>`. `sanitize=False` -- raw HTML allowed. |
| `custom_code_footer` | Html | No | `False` | Custom code injected before `</body>` |
| `robots_txt` | Html | No | `False` | Custom `robots.txt` content; groups-restricted to `website_designer` |
| `google_analytics_key` | Char | No | `False` | GA4 Measurement ID |
| `google_search_console` | Char | No | `False` | Google Search Console verification key |
| `google_maps_api_key` | Char | No | `False` | Google Maps API key (used by `res.partner.google_map_img/link`) |
| `plausible_site` | Char | No | `False` | Plausible analytics site ID, e.g. `example.com` |
| `plausible_shared_key` | Char | No | `False` | Plausible shared key for authenticated stats |
| `configurator_done` | Boolean | No | `False` | Setup wizard completed flag |

**L4: CDN Default Filters (`DEFAULT_CDN_FILTERS`):**
```python
DEFAULT_CDN_FILTERS = [
    "^/[^/]+/static/",
    "^/web/(css|js)/",
    "^/web/image",
    "^/web/content",
    "^/web/assets",
    "^/website/image/",  # retrocompatibility
]
```

**L4: Blocked Third-Party Domains (`DEFAULT_BLOCKED_THIRD_PARTY_DOMAINS`):**
Covers Google (all TLDs), YouTube, Instagram, Vimeo, Dailymotion, TikTok, Facebook, Twitter/X, and Google Tag Manager. Used by the iframe sanitization system to block embeds from these domains when `block_third_party_domains=True`.

### Social Media Fields

| Field | Type | Default |
|-------|------|---------|
| `social_twitter` | Char | `base.main_company.social_twitter` |
| `social_facebook` | Char | `base.main_company.social_facebook` |
| `social_github` | Char | `base.main_company.social_github` |
| `social_linkedin` | Char | `base.main_company.social_linkedin` |
| `social_youtube` | Char | `base.main_company.social_youtube` |
| `social_instagram` | Char | `base.main_company.social_instagram` |
| `social_tiktok` | Char | `base.main_company.social_tiktok` |
| `social_discord` | Char | `base.main_company.social_discord` |
| `social_default_image` | Binary | `False` |
| `has_social_default_image` | Boolean | Auto (`social_default_image` is truthy) |

### Key Methods

#### Website Resolution

```python
@api.model
def get_current_website(fallback=True) -> website
```
Resolution order: `force_website_id` session key > context `website_id` > request Host header (via `_get_current_website_id`) > `fallback=True` returns first website in DB > empty browse record.

Cached via `ormcache` on `_get_current_website_id(domain_name, fallback)` -- the domain-level cache means the DB is hit once per domain per process.

```python
@api.model
def _get_current_website_id(domain_name, fallback=True) -> int | False
```
Matches `domain` (after punycode normalization) against `website.domain`. Also tries with port stripped. Falls back to first record if `fallback=True`.

```python
def _force(website_id) -> None
def _force_website(website_id) -> None
```
Sets `request.session['force_website_id']` for the current session. Used by "Preview on Website" button.

```python
@api.model
def is_public_user() -> bool
```
Returns `True` if `request.env.user.id == request.website.user_id` (i.e. the public user is in effect).

#### Page Management

```python
@api.model
def new_page(name=False, add_menu=False, template='website.default_page',
             ispage=True, namespace=None, page_values=None, menu_values=None,
             sections_arch=None, page_title=None) -> dict
```
Creates a new `ir.ui.view` (COW'd from template with a unique key) and optionally a `website.page` record and `website.menu` entry. Returns `{'url': page_url, 'view_id': view.id, 'page_id': page.id, 'menu_id': menu.id}`.

**Key behavior:** If `sections_arch` is provided, HTML is injected into the `#wrap` div of the template. The `arch_db` is written with `lang=None` to avoid translation chaining.

```python
def get_unique_path(page_url) -> str
```
Appends `-n` suffix if the URL already exists for this website's scope. Searched domain includes `website_id` context or current website.

```python
def get_unique_key(string, template_module=False) -> str
```
Returns a unique `ir.ui.view.key` (e.g. `website.my-page-1`) by checking both generic and website-specific views.

```python
def _bootstrap_homepage() -> None
```
Called on website `create()`. References `website.homepage` view, sets its arch to a blank `oe_structure` div, creates a `website.page` record with `/` URL, and copies the main menu hierarchy.

```python
def copy_menu_hierarchy(top_menu) -> None
```
Recursively copies a menu tree under a new top menu for this website.

```python
def _get_website_pages(domain=None, order='name', limit=None) -> website.page
```
Returns `website.page` records for the current website using `_get_most_specific_pages()` (prefers COW'd pages over generic ones with the same URL).

#### Caching

```python
@ormcache('self.env.uid', 'self.id', cache='templates')
def is_menu_cache_disabled() -> bool
```
Returns `True` if the website's menu contains any URL with an ID pattern (e.g. `/shop/1`) or any group-restricted menu item. This flag is used by the frontend to decide whether the menu can be client-side rendered (cacheable) or must be server-rendered per-request.

```python
@ormcache('(request.httprequest.path, self.env.context.get("website_id"))', cache='templates.cached_values')
@api.model
def _get_page_info(request) -> dict | None
```
Cached lookup of page metadata (id, URL, view_id, group_ids) by request path. Clears when templates clear.

```python
@ormcache('self.id')
def _get_cached_values() -> dict
```
Prefetches only `user_id`, `company_id`, `default_lang_id`, `homepage_url` for a website. Explicitly avoids prefetching translatable fields (which could raise errors in invalid language contexts during early request dispatch).

#### Image and CDN

```python
@api.model
def image_url(record, field, size=None) -> str
```
Generates `/web/image/{model}/{id}/{field}[/{size}]?unique={sha7}`. The SHA is the first 7 hex chars of SHA-512 of `write_date`. CDN-aware via `get_cdn_url()`.

```python
def get_cdn_url(uri) -> str
```
Checks `uri` against each line of `cdn_filters` as a regex. If matched, prepends `cdn_url`. Used in QWeb templates via `website.get_cdn_url()`.

#### Utilities

```python
@api.model
def viewref(view_id, raise_if_not_found=True) -> ir.ui.view
```
Returns the most specific `ir.ui.view` for the current website context. Also looks at archived views (`active_test=False`).

```python
@api.model
def is_view_active(key) -> bool | None
```
Returns `True`/`False`/`None` (not found) for a template key.

```python
@api.model
def pager(url, total, page=1, step=30, scope=5, url_args=None)
```
Delegates to `portal.pager`. Generates pagination URL parameters.

```python
def rule_is_enumerable(rule) -> bool
```
Checks whether a Werkzeug routing rule can generate sitemap-compatible GET URLs. Filters out rules that require auth, non-HTTP types, or converters without a `generate()` method.

```python
def _enumerate_pages(query_string=None, force=False) -> generator
```
Yields all public indexed pages and controller-generated URLs for sitemap.xml. Domain filters depend on `force`:
- `force=False`: `website_indexed=True`, `visibility=False`, `is_visible` (published + past date_publish)
- `force=True`: all pages regardless of publication state

Also generates pages from model converters (e.g. `/shop/product/1`) by calling `sitemap_qs2dom()`.

```python
def get_website_page_ids() -> dict[int | None, list[int]]
```
Returns pages grouped by website ID. Raises `AccessError` if user lacks `group_website_restricted_editor`.

```python
def check_existing_page(page) -> bool
```
Heuristic check using: (1) `website.page` record, (2) `website.rewrite` with 301/302, (3) routing map match, (4) `werkzeug.routing.RequestRedirect` (for 308 rewrites). Not perfectly reliable.

```python
def search_pages(needle=None, limit=None) -> list
```
Slugs `needle` and calls `_enumerate_pages(force=True)`.

```python
def get_suggested_controllers() -> list[tuple]
```
Returns `[(label, url, icon), ...]` for the backend panel. Default: Homepage and Contact Us.

```python
def get_client_action_url(url, mode_edit=False, mode_debug=0) -> str
```
Builds `/odoo/action-website.website_preview?path=...&enable_editor=...&debug=...`.

```python
def get_client_action(url, mode_edit=False, website_id=False) -> dict
```
Returns the `website.website_preview` action with params for the preview controller.

#### SEO and Canonical

```python
def _get_canonical_url() -> str
```
Returns localized canonical URL via `ir.http._url_localized()`.

```python
def _is_canonical_url() -> bool
```
Compares current request URL against canonical URL. Handles quoted characters properly (non-canonical if current URL has quotable chars because the canonical URL is always quoted).

#### Snippet and Asset Management

```python
@api.model
def get_theme_configurator_snippets(theme_name) -> dict
```
Merges base `configurator_snippets` from the website manifest with theme-specific overrides, then inserts addon snippets at configured positions.

```python
def _preconfigure_snippet(snippet, el, customizations) -> None
```
Applies default + theme-level customization to a snippet DOM element before rendering in the configurator. Handles data attributes, classes, styles, filters, and background options.

```python
def _is_snippet_used(snippet_module, snippet_id, asset_version, asset_type, html_fields) -> bool
```
SQL-driven check across all HTML fields for snippet usage via `data-snippet` attribute. Also checks template definitions (which lack `data-snippet` in source).

```python
def _disable_unused_snippets_assets() -> None
```
Batch-deactivates snippet assets (SCSS/JS) not found in any HTML field across the website. Run as a cron to clean up after theme switches.

#### Configurator

```python
@api.model
def configurator_init() -> dict
```
Returns features, logo, and industry list from the Odoo API (`/api/website/1/configurator/industries`). Gracefully returns empty industries on `AccessError`.

```python
@api.model
def configurator_apply(theme_name, selected_features, industry_id, industry_name,
                       selected_palette, logo_attachment_id, website_purpose,
                       website_type, **kwargs) -> None
```
Full website initialization:
1. Installs chosen theme
2. Sets logo (from attachment or company)
3. Applies color palette (both palette name and per-color overrides)
4. Configures CTA button
5. Installs feature modules and creates feature pages
6. Applies per-addon overrides via `configurator_addons_apply` extension hook
7. Updates footer links
8. Downloads and attaches industry-specific images
9. Copies configurator pages to a "landing pages" namespace for the "+New" dialog

#### Configuration Constraints

```python
@api.constrains('domain')
def _check_domain() -> None
# Raises ValidationError if domain path contains '/./' or '/../' segments

@api.constrains('homepage_url')
def _check_homepage_url() -> None
# Raises ValidationError if homepage_url doesn't start with '/'

@api.constrains('domain')
def _domain_unique -> models.Constraint('unique(domain)')
```

#### SQL Constraints

```python
_domain_unique = models.Constraint(
    'unique(domain)',
    'Website Domain should be unique.',
)
```

### Performance Notes (L4)

- `get_current_website()` is called on every HTTP request; its internal `_get_current_website_id` is fully cached via `ormcache` keyed by `(domain_name, fallback)`.
- `_get_cached_values()` intentionally avoids prefetching translatable fields to prevent `MissingError` during early request dispatch before language is fully initialized.
- `is_menu_cache_disabled()` uses `ormcache('self.env.uid', 'self.id', cache='templates')` -- user-specific because `group_ids` evaluation is user-dependent.
- `_enumerate_pages()` does massive SQL work but is only called for sitemap.xml (every 12 hours) and the page search endpoint.
- `_disable_unused_snippets_assets()` is a cron job, not on-hot path.

---

## website.page

**File:** `models/website_page.py`

Represents a CMS page. Uses **delegation inheritance** (`_inherits = {'ir.ui.view': 'view_id'}`) -- every `website.page` record is a thin wrapper over an `ir.ui.view` record. The actual HTML content lives in `ir.ui.view.arch_db`; `website.page` adds URL routing, publication state, scheduling, and SEO metadata.

### Inheritance Chain

```python
_inherits = {'ir.ui.view': 'view_id'}
_inherit = [
    'website.published.multi.mixin',  # is_published + multi-website
    'website.searchable.mixin',        # Full-text search
    'website.page_options.mixin',       # Header overlay, color customization
]
```

### Fields

| Field | Type | Delegated | Description |
|-------|------|-----------|-------------|
| `url` | Char | No | Page URL, e.g. `/about-us` (required, unique per website via `get_unique_path`) |
| `view_id` | Many2one ir.ui.view | Yes (key) | The wrapped view record (`ondelete=cascade`). Required. |
| `view_write_uid` | Many2one res.users | Yes | Last user to modify the view content |
| `view_write_date` | Datetime | Yes | Last modification timestamp |
| `website_indexed` | Boolean | No | Include in sitemap.xml and search (default: `True`) |
| `date_publish` | Datetime | No | Scheduled publication date/time. `is_visible = is_published AND (not date_publish OR date_publish < now)` |
| `menu_ids` | One2many | No | `website.menu` records pointing to this page (`ondelete=cascade`) |
| `is_in_menu` | Boolean | Auto | `bool(menu_ids)` |
| `is_homepage` | Boolean | Auto | `url == (website.homepage_url or '/')`. Also True when `website_id` matches current website and URL is `/`. |
| `is_visible` | Boolean | Auto | `website_published AND (not date_publish OR date_publish < now)` |
| `is_new_page_template` | Boolean | No | Offer as a template in "+New" page dialog under "Custom" category |
| `website_id` | Many2one | From `view_id` | Delegates to `view_id.website_id`. `ondelete='cascade'`. |
| `arch` | Text | From `view_id` | Content XML; `depends_context=('website_id',)` ensures COW reload |
| `key` | Char | From `view_id` | View key for uniqueness |
| `name` | Char | From `view_id` | Page display name |
| `track` | Boolean | From `view_id` | Enable visitor tracking for this page |
| `visibility` | Selection | From `view_id` | `''` (public), `'connected'`, `'restricted_group'`, `'password'` |
| `group_ids` | Many2many | From `view_id` | Groups required to access when `visibility='restricted_group'` |
| `header_visible` | Boolean | From `page_visibility_options` mixin | Show header on this page |
| `footer_visible` | Boolean | From `page_visibility_options` mixin | Show footer on this page |
| `header_overlay` | Boolean | From `page_options` mixin | Header overlay mode |
| `header_color` | Char | From `page_options` mixin | Header background color class |
| `header_text_color` | Char | From `page_options` mixin | Header text color |

### Key Methods

```python
@api.depends('url')
def _compute_website_url(self) -> None
```
Overrides the mixin's default to simply set `website_url = url`. The mixin is designed for records with computed URLs; `website.page` has a stored URL.

```python
@api.depends_context('uid')
def _compute_can_publish(self) -> None
```
Grants publish permission to anyone in `website.group_website_designer`. For others, delegates to the mixin's logic (ACL-based).

```python
def _get_most_specific_pages() -> website.page
```
Returns one page per URL, preferring website-specific COW pages over generic ones. Uses a single sorted pass with a `Counter` on keys:

1. Search all pages in the website domain
2. Sort by `(url, not website_id)` -- specific pages first
3. Walk the sorted list, collecting only the first match per URL, plus generic pages that have no COW counterpart

**Edge case:** If a generic page was later given a different URL via COW, it should not be accessible under the original generic URL. Handled by checking `page_keys_counts[page.key] == 1` for generic pages.

```python
def copy_data(default=None) -> list[dict]
```
If `view_id` not in defaults, copies the view with the target `website_id`. Slugs the URL via `get_unique_path`.

```python
@api.model
def clone_page(page_id, page_name=None, clone_menu=True) -> str
```
Duplicates a page and its menu (if same website). Returns the new URL.

```python
def unlink() -> bool
```
Deletes orphaned `ir.ui.view` records only if they have no other `website.page` children and no inherit children. The view table is cleaned before `super().unlink()`. Template cache is cleared if any pages remain.

```python
def write(vals) -> bool
```
On `url` change: slugifies via `ir.http._slugify()`, checks uniqueness, syncs all menu URLs pointing to the old URL, and updates `website.homepage_url` if this page is the homepage.
On `name` change: regenerates the view `key` to maintain uniqueness.
On `visibility` change from `restricted_group`: clears `group_ids`.
Clears the `templates` registry cache after URL/visibility/group changes because page renderability depends on those fields.

```python
def get_website_meta() -> dict
```
Delegates to `view_id.get_website_meta()` which uses the `website.seo.metadata` mixin.

```python
@api.model
def _search_get_detail(website, order, options) -> dict
```
Implements `website.searchable.mixin`. Non-designers get a reinforced domain requiring `website_published=True`, `website_indexed=True`, no password protection, and appropriate visibility/group checks.

```python
@api.model
def _search_fetch(search_detail, search, limit, order) -> (recordset, count)
```
Overridden to search the most-specific pages only. If `description` is in the mapping and a `search` term is provided, falls back to raw SQL `ILIKE` against `ir.ui.view.arch_db` (with translation join) because QWeb fields are not searchable by the ORM. Strips XML tags from matched HTML before returning.

```python
def action_page_debug_view() -> dict
```
Opens the wrapped `ir.ui.view` in the extended view form (`website.view_view_form_extend`).

### Page Caching (L4)

```python
_CACHE_DURATION = 3600  # 1 hour
```

Cache key: `(website.id, request.lang.code, request.httprequest.path, request.session.debug)`

**Cache eligibility** (`_allow_to_use_cache`):
- `GET` request only
- No query parameters
- Public user (`request.env.user._is_public()`)
- No `group_ids` on the page (no access-restricted content)

**CSRF post-processing** (`_post_process_response_from_cache`):
Cached HTML has CSRF tokens replaced via `re.sub` at serve time. Two patterns are replaced: `csrf_token: "..."` and `name="csrf_token" value="..."`.

**Cache invalidation:**
- Triggered by: `url` change, `visibility` change, `group_ids` change, `is_published` change
- Mechanism: `self.env.registry.clear_cache('templates')` -- clears all template caches across all workers

**Cache bypass:**
- Designer users always get fresh renders (checked in `_get_response_raw`)
- Pages where this website-specific COW has a different URL than the generic version bypass cache

---

## website.menu

**File:** `models/website_menu.py`

Hierarchical navigation menus. Supports regular links, mega menus (full-width dropdowns with custom HTML content), and dropdown containers.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Menu label (`translate=True`, required) |
| `url` | Char | Stored computed: from `page_id` or manual; `"#"` for mega/dropdown parents |
| `page_id` | Many2one | Linked `website.page` (`ondelete=cascade`, `index='btree_not_null'`) |
| `controller_page_id` | Many2one | Linked `website.controller.page` (`ondelete=cascade`, `index='btree_not_null'`) |
| `new_window` | Boolean | Open in new tab (`target="_blank"`) |
| `sequence` | Integer | Sort order (default: `max(existing.sequence) + 1`) |
| `website_id` | Many2one | Parent website (`ondelete=cascade`) |
| `parent_id` | Many2one | Parent menu item (`ondelete=cascade`) |
| `child_id` | One2many | Child menu items (inverse of `parent_id`) |
| `parent_path` | Char | Materialized path (`'1/5/23/'`) for fast tree queries and `lft/rght` ancestry |
| `is_visible` | Boolean | Auto-computed: `True` unless linked page/controller is unpublished or password-protected |
| `group_ids` | Many2many | Only show to users in these groups. `group_website_designer` is auto-added on write. |
| `is_mega_menu` | Boolean | Computed from `bool(mega_menu_content)`. Inverse writes `mega_menu_content`. |
| `mega_menu_content` | Html | Custom HTML for mega menu panels (`sanitize=False`, `translate=True`, `prefetch=True`) |
| `mega_menu_classes` | Char | CSS classes for mega menu styling |

### Display Name

Computed with `[website.name]` suffix when `display_website` context is set OR user has `group_multi_website`.

### Menu Auto-duplication (L4)

```python
@api.model_create_multi
def create(vals_list) -> website.menu
```

This is the most complex `create()` in the module. For each item in `vals_list`:

1. If `url == '/default-main-menu'`: create normally (used for data.xml bootstrap)
2. If `website_id` explicitly provided: create normally for that website
3. If `website_id` in context: use context value
4. **Otherwise (no website)**: For every existing website, create a copy under that website's root menu. If the parent was the default main menu (`website.main_menu`), also create a record under the generic main menu itself.

Returns the last-created record. This means `ir.model.data` XML lookups that expect one record will get the last website's menu.

### URL Resolution

```python
@api.depends("page_id", "is_mega_menu", "child_id")
def _compute_url() -> None
```
- Mega menu or has children: `url = "#"`
- Has `page_id`: `url = page_id.url`
- Otherwise: `url` stays as written (or `"#"` default)

```python
def _clean_url() -> str
```
Auto-corrects bare URLs: prepends `mailto:` for `@`, prepends `/` for non-HTTP, otherwise leaves unchanged.

### Active Detection

```python
def _is_active() -> bool
```
Compares the current request URL against the menu URL:
- Anchor/query components are considered for exact URLs
- Mega menus are never considered "active" (no URL comparison)
- Dropdown parents are active if any child is active
- Handles unslugging (e.g., `/shop/1` matches `/shop/my-product-1`)
- Query parameters must be a subset of the request's parameters
- External URLs must match the same netloc

### Visibility Computation (L4)

```python
def _compute_visible() -> None
```
Checks both `page_id` and `controller_page_id`:
- Uses `sudo()` to read the linked record without raising access errors for public users
- Distinguishes between unpublished (hidden) and password-protected (also hidden from public, but shown to designers with a lock icon)

### Constraint: Two-level Hierarchy

```python
@api.constrains("parent_id", "child_id", "is_mega_menu", "mega_menu_content")
def _validate_parent_menu() -> None
```

1. Maximum 2 levels of nesting (parent + children; grandchildren are rejected)
2. Mega menus cannot have parents or children
3. Menus with children cannot be placed as children themselves (no 3-level chains)

### Cascade Delete

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_master_tags() -> None
```
Raises `UserError` if attempting to delete `website.main_menu` (the generic template menu that serves as parent for new website menus).

```python
def unlink() -> bool
```
On unlink of a menu whose parent was `website.main_menu`, also removes menus from all other websites that share the same URL. This keeps menus synchronized across websites when the source menu is deleted.

---

## website.visitor

**File:** `models/website_visitor.py`

Tracks website visitors -- both authenticated partners and anonymous sessions. Uses raw SQL for performance-critical paths.

### website.track Model

| Field | Type | Description |
|-------|------|-------------|
| `visitor_id` | Many2one | Parent `website.visitor` (`ondelete=cascade`, `index=True`) |
| `page_id` | Many2one | `website.page` visited (`index=True`, `ondelete=cascade`) |
| `url` | Text | Full URL path visited (indexed) |
| `visit_datetime` | Datetime | Timestamp (default: `now()`, required, readonly) |

No `_log_access = True` (inherited: False) -- no `create_uid`, `write_uid`, etc.

### website.visitor Fields

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | Char | Primary key. For logged-in: `partner.id` (integer stored as string). For anonymous: SHA1 of `(IP, UA, session_id)` truncated to 32 hex chars. Unique constraint. |
| `website_id` | Many2one | Website where visitor was created (readonly) |
| `partner_id` | Many2one | Linked `res.partner`. Computed from `access_token` -- if length is 32 it's anonymous (no partner). `index='btree_not_null'`. |
| `partner_image` | Binary | `partner_id.image_1920` (related) |
| `country_id` | Many2one | From GeoIP lookup (`res.country` by code). `country_code` from `request.geoip` may not exist in Odoo's country table -- silently skipped. |
| `country_flag` | Char | `country_id.image_url` (related) |
| `lang_id` | Many2one | Visitor's browser language at creation time (`request.lang.id`) |
| `timezone` | Selection | From browser `tz` cookie, falling back to user profile timezone |
| `email` | Char | From linked partner via `sudo()` batch search read |
| `mobile` | Char | From linked partner phone via `sudo()` batch search read |
| `visit_count` | Integer | Number of distinct visit sessions (default: 1). Incremented when gap > 8 hours. |
| `website_track_ids` | One2many | `website.track` records (readonly) |
| `visitor_page_count` | Integer | Total page views across all tracks (auto-computed via `_read_group`) |
| `page_ids` | Many2many | Unique pages visited. `group_website_designer` only. |
| `page_count` | Integer | Number of unique pages (auto-computed via `_read_group`) |
| `last_visited_page_id` | Many2one | Most recently visited page via `visit_datetime:max` in `_read_group` |
| `create_date` | Datetime | First connection (readonly) |
| `last_connection_datetime` | Datetime | Last page view timestamp. Updated on every tracked page visit. |
| `time_since_last_action` | Char | Human-readable "2 minutes ago" via `_format_time_ago` |
| `is_connected` | Boolean | True if `last_connection_datetime` within 5 minutes |

### Visitor Lifecycle (L4)

```
Anonymous request
    │
    ├── _get_access_token() → SHA1(IP, UA, session_id)[:32]
    │
    └── _upsert_visitor(token, force_track_values)
            │
            ├── INSERT INTO website_visitor (ON CONFLICT access_token DO UPDATE)
            │       Sets last_connection_datetime=NOW()
            │       Increments visit_count IF last_connection < now() - 8h
            │       Also inserts website_track in same query (WITH clause)
            │
            └── Returns (visitor_id, 'inserted' | 'updated')
                    │
                    └── _get_visitor_from_request(force_create=True)
                            │
                             → sudo'd visitor record
                                     │
User logs in
    │
    ├── New visitor created with access_token = partner_id
    │
    └── _merge_visitor(target_visitor)
            ├── Moves all website_track records to target
            ├── unlink() anonymous visitor
            └── Other modules (website_sale, crm) extend to merge their own data

After 60 days of inactivity (partner_id=None)
    │
    └── _cron_unlink_old_visitors() → unlink() batch of 1000
```

### Key Methods

```python
def _get_access_token() -> str | int
```
Returns `request.env.user.partner_id.id` for authenticated users (non-public). For anonymous: SHA1 of `(remote_addr, HTTP_USER_AGENT, session.sid)` encoded as 32-char hex string. Raises `ValueError` if called outside a request context.

```python
def _upsert_visitor(access_token, force_track_values=None) -> (int, str)
```
Single raw SQL UPSERT. `ON CONFLICT (access_token)` updates `last_connection_datetime` and conditionally increments `visit_count`. When `force_track_values` is provided, uses a CTE to insert the track record in the same round-trip.

**Critical:** `visit_count` increment uses `last_connection_datetime < NOW() - INTERVAL '8 hours'` -- not the application server clock, but the database clock (`NOW() AT TIME ZONE 'UTC'`).

```python
def _get_visitor_from_request(force_create=False, force_track_values=None) -> website.visitor | None
```
Reads visitor by `access_token`. If `force_create` or if visitor has no timezone (read-only transaction where upsert isn't possible), calls `_upsert_visitor`. Returns `None` if no session/uid yet (JSON requests from mobile apps).

```python
def _add_tracking(domain, website_track_values) -> None
```
Adds a track record only if the most recent track is more than 30 minutes old. Prevents duplicate tracks from polling/keepalive requests.

```python
def _merge_visitor(target) -> None
```
Moves all `website_track_ids` to target and deletes self. Raises `ValueError` if target has no `partner_id`. Extension point for `website_sale` (cart merging), `crm` (lead merging).

```python
def _cron_unlink_old_visitors(batch_size=1000) -> None
```
Called by `ir.cron` (technical). Deletes visitors matching `_inactive_visitors_domain()` (older than 60 days by default, no partner). Uses `_commit_progress` for batch progress tracking.

```python
def _inactive_visitors_domain() -> Domain
```
Default: `last_connection_datetime < (now - delay_days) AND partner_id = False`. Override in submodules to add custom inactivity criteria (e.g., no leads, no carts).

```python
def _update_visitor_timezone(timezone) -> None
```
Raw SQL `UPDATE` with `FOR NO KEY UPDATE SKIP LOCKED` to avoid concurrent update errors. Called in read-only contexts (where ORM write would fail) to set timezone from browser cookie.

```python
def _update_visitor_last_visit() -> None
```
Raw SQL update of `last_connection_datetime` and conditional `visit_count` increment. Uses `FOR NO KEY UPDATE SKIP LOCKED`. Called after every tracked page view.

### Visitor Identification Edge Cases (L4)

1. **Same user on multiple devices:** Each device generates a different SHA1 (different IP, possibly different UA, different session), creating separate visitor records. These can be merged on login via `_merge_visitor`.
2. **Same session across days:** The same anonymous token persists across visits. `visit_count` increments every 8+ hour gap.
3. **Partner login from multiple devices:** After login, `_upsert_visitor` creates a record with `access_token = partner_id` (no 32-char length). The `_compute_partner_id` recognizes this pattern and maps it to the partner.
4. **GeoIP country not in Odoo:** The SQL subquery `SELECT id FROM res_country WHERE code = country_code` silently returns `NULL` if the country code is unknown. The visitor is still created.
5. **Concurrent upserts:** The `ON CONFLICT (access_token)` clause handles race conditions. The `FOR NO KEY UPDATE SKIP LOCKED` in timezone/visit updates handles concurrent reads.

---

## website.rewrite

**File:** `models/website_rewrite.py`

SEO-friendly URL redirects and rewrites. Replaces the deprecated XML workflow engine approach.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Descriptive name (required) |
| `website_id` | Many2one | Target website (`ondelete=cascade`) |
| `active` | Boolean | Default: `True` |
| `url_from` | Char | Source URL pattern (indexed). Auto-filled from `route_id`. |
| `route_id` | Many2one | `website.route` to pre-fill `url_from` and `url_to` from the route's `path` |
| `url_to` | Char | Destination URL |
| `redirect_type` | Selection | See redirect types below |
| `sequence` | Integer | Priority order |

### Redirect Types

| Value | Label | Behavior | Routing Impact |
|-------|-------|----------|---------------|
| `301` | Moved Permanently | Browser caches redirect | Matched in `_serve_redirect()` fallback after routing |
| `302` | Moved Temporarily | Browser does not cache | Same as 301 but no caching hint |
| `308` | Redirect/Rewrite | Permanent alias; both URLs work | **Alters routing map** via `_invalidate_routing()`: adds `url_to` as a new route |
| `404` | Not Found | Returns 404; removes from routing map | **Alters routing map** via `_invalidate_routing()`: skips the route |

### Constraints

```python
@api.constrains('url_to', 'url_from', 'redirect_type')
def _check_url_to() -> None
```
- 301/302/308: `url_to` and `url_from` required; neither can start with `#`; base paths must differ
- 308: `url_to` must start with `/`; must preserve all route parameters from `url_from`; `url_to` cannot match an existing route; `url_to` cannot be `/`
- Additionally validates `url_to` is a parseable Werkzeug rule

### Routing Integration (L4)

`ir_http._get_rewrites(website_id)` builds a dict `{url_from: rewrite}` for `redirect_type in ('308', '404')`. This is cached per website via `ormcache`. During `_generate_routing_rules()`:
- `308`: yields `url_to` as a new route AND yields `url_from` with a partial endpoint that performs the redirect
- `404`: skips the original route (not yielded)
- 301/302: not in the routing map; handled as a fallback in `_serve_redirect()` after routing fails

### Write/Invalidation

When `redirect_type` changes to/from `'308'` or `'404'`, `write()` calls `_invalidate_routing()` which clears the `routing` cache across all workers via `self.env.registry.clear_cache('routing')`.

---

## website.controller.page

**File:** `models/website_controller_page.py`

Model-driven dynamic pages that expose arbitrary Odoo models publicly. Similar to `website.page` but backed by a model+domain instead of a static QWeb template.

### Inheritance

```python
_inherits = {'ir.ui.view': 'view_id'}
_inherit = [
    'website.published.multi.mixin',
    'website.searchable.mixin',
]
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `view_id` | Many2one | Listing/catalog view (`ondelete=cascade`) |
| `record_view_id` | Many2one | Single-record detail view (`ondelete=cascade`) |
| `menu_ids` | One2many | Menus linked to this page |
| `website_id` | Many2one | Delegated from `view_id` |
| `name` | Char | Stored compute+inverse of `view_id.name` |
| `name_slugified` | Char | Stored compute+inverse; URL-safe name; unique constraint `unique(name_slugified)` |
| `url_demo` | Char | `"/model/{name_slugified}"` (computed) |
| `record_domain` | Char | Domain to restrict which records are publicly visible |
| `default_layout` | Selection | `'grid'` or `'list'` (default: `'grid'`) |

### Route

Auto-generates route `/model/<string:name_slugified>`.

### Lifecycle

- `create()`: calls `_check_user_has_model_access()` (verifies the user can read the model)
- `write()`: syncs menu name and URL; re-checks model access if `model_id` changed; cascades to menu records
- `unlink()`: same COW-aware cascade delete as `website.page`

---

## Mixins (Reusable Behaviors)

### website.multi.mixin

```python
class WebsiteMultiMixin(models.AbstractModel):
    _name = 'website.multi.mixin'
    website_id = fields.Many2one("website", string="Website",
                                  ondelete="restrict", index=True)
```

Provides `can_access_from_current_website()` which checks `website_id in (False, current_website.id)`.

### website.published.mixin

```python
class WebsitePublishedMixin(models.AbstractModel):
    _name = 'website.published.mixin'
    is_published = fields.Boolean(copy=False,
                                   default=lambda self: self._default_is_published(),
                                   index=True)
    website_published = fields.Boolean(related='is_published', readonly=False)
    can_publish = fields.Boolean(compute='_compute_can_publish')
    website_url = fields.Char(compute='_compute_website_url')
    website_absolute_url = fields.Char(compute='_compute_website_absolute_url')
```

- `_default_is_published()`: override in subclasses (default: `False`)
- `website_publish_button()`: toggles `is_published` in-place
- `_compute_can_publish()`: checks `_check_user_can_modify` via `website` model; raises `AccessError` if forbidden
- Access guard in `create()` and `write()` to prevent publishing without permission

### website.published.multi.mixin

```python
class WebsitePublishedMultiMixin(WebsitePublishedMixin):
    _name = 'website.published.multi.mixin'
    _inherit = ['website.published.mixin', 'website.multi.mixin']

    website_published = fields.Boolean(
        compute='_compute_website_published',
        inverse='_inverse_website_published',
        search='_search_website_published',
        related=False, readonly=False
    )
```

- `_compute_website_published`: `True` only if `is_published=True AND (no website_id OR website matches context)`
- `_inverse_website_published`: writes back to `is_published`
- `_search_website_published`: supports `website.published = True` in domains; returns website-aware domain in frontend context
- `open_website_url()`: handles both current-website and cross-website navigation with domain-based URL building

### website.seo.metadata

```python
class WebsiteSeoMetadata(models.AbstractModel):
    _name = 'website.seo.metadata'
    is_seo_optimized = fields.Boolean(compute='_compute_is_seo_optimized', store=True)
    website_meta_title = fields.Char(translate=True, prefetch="website_meta")
    website_meta_description = fields.Text(translate=True, prefetch="website_meta")
    website_meta_keywords = fields.Char(translate=True, prefetch="website_meta")
    website_meta_og_img = fields.Char  # OpenGraph image URL
    seo_name = fields.Char(translate=True, prefetch=True)  # URL-friendly name
```

- `_compute_is_seo_optimized`: `True` only when title, description, AND keywords are all set
- `_default_website_meta()`: builds default OG/Twitter cards from request context, company social links
- `get_website_meta()`: merges user custom values over defaults; strips domain from absolute OG image URLs

### website.cover_properties.mixin

```python
class WebsiteCoverPropertiesMixin(models.AbstractModel):
    _name = 'website.cover_properties.mixin'
    cover_properties = fields.Text(
        default=lambda s: json_safe.dumps({
            "background_color_class": "o_cc3",
            "background-image": "none",
            "opacity": "0.2",
            "resize_class": "o_half_screen_height",
        })
    )
```

- `write()`: preserves `resize_class` when updating via list views (prevents CSS class loss)
- `_get_background()`: resolves `/web/image/` URLs with optional `height`/`width` query params appended

### website.page_visibility_options.mixin

```python
class WebsitePageVisibilityOptionsMixin(models.AbstractModel):
    header_visible = fields.Boolean(default=True)
    footer_visible = fields.Boolean(default=True)
```

Per-record control of layout chrome.

### website.page_options.mixin

```python
class WebsitePageOptionsMixin(models.AbstractModel):
    _name = 'website.page_options.mixin'
    _inherit = ['website.page_visibility_options.mixin']
    header_overlay = fields.Boolean()
    header_color = fields.Char()
    header_text_color = fields.Char()
```

Adds header styling customization.

### website.searchable.mixin

```python
class WebsiteSearchableMixin(models.AbstractModel):
    _name = 'website.searchable.mixin'
    _description = 'Website Searchable Mixin'
```

Required method to implement:

```python
@api.model
def _search_get_detail(website, order, options) -> dict:
    """
    Returns: {
        'model': str,
        'base_domain': list,
        'search_fields': list[str],
        'fetch_fields': list[str],
        'mapping': dict,  # {'field_name': {'name': str, 'type': str, 'match': bool}}
        'icon': str,
        'requires_sudo': bool,  # optional
    }
    """
```

`_search_build_domain()`: builds AND domain combining base domain with OR of ILIKE matches per field per search term. Supports an `extra` function for per-term additional conditions.

---

## ir.ui.view Extension

**File:** `models/ir_ui_view.py`

### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `website_id` | Many2one | Website scope (`ondelete=cascade`). Presence of this field marks a view as COW'd. |
| `page_ids` | One2many | `website.page` records using this view |
| `controller_page_ids` | One2many | `website.controller.page` records using this view |
| `first_page_id` | Many2one | First `website.page` using this view (computed) |
| `track` | Boolean | Enable visitor tracking for pages using this view (default: `False`) |
| `visibility` | Selection | `''` (public), `'connected'`, `'restricted_group'`, `'password'` |
| `visibility_password` | Char | Hashed password (`groups='base.group_system'`, not readable by designers) |
| `visibility_password_display` | Char | `********` or empty string (computed/inverse for designer UI) |

### COW Mechanism (L4)

The COW (Copy-on-Write) mechanism allows each website to have customized versions of generic views without modifying the original.

```python
def write(self, vals) -> bool
```

1. **No COW if:** `no_cow` context set, no `website_id` in context, or view already has `website_id` set
2. **Flush + invalidate:** pages are flushed and the whole recordset invalidated before writes to prevent cache pollution
3. **Existing specific view found:** write directly to that view (don't create a duplicate)
4. **No existing specific view:** copy the generic view with `website_id` set to current website, same `key`, and same `inherit_id` (for inheriting views)
5. **Child inheritance chain:** all `inherit_children_ids` are also COW'd:
   - If child was already specific to this website: copy it to new parent and delete the original (to preserve `id` ordering)
   - If child was generic: trigger COW on it (write to `inherit_id=new_specific_parent`)
6. **Pages:** `_create_website_specific_pages_for_view()` creates copies of all `website.page` records using this view

**COU (Copy-on-Unlink):** When deleting a generic view in a website context, all other websites get their own copies created via `write()`.

### Visibility (L4)

```python
def _get_pwd() / def _set_pwd() -> None
```
`_set_pwd` hashes the password using `request.env.user._crypt_context()` and writes it to `visibility_password` via `sudo()` (bypassing the field's groups restriction).

Visibility is enforced in `ir.http._pre_dispatch()` via `record.can_access_from_current_website()` which calls `_handle_visibility()` on `ir.ui.view`.

---

## website.form

**File:** `models/website_form.py`

Backend infrastructure for the drag-and-drop Form Builder.

### ir.model Extension

| Field | Type | Description |
|-------|------|-------------|
| `website_form_access` | Boolean | Enable form builder for this model |
| `website_form_default_field_id` | Many2one | Text field to store form field data |
| `website_form_label` | Char | Submit button label (`translate=True`) |
| `website_form_key` | Char | Registry key for FormBuilder plugins |

### ir.model.fields Extension

```python
website_form_blacklisted = fields.Boolean(
    'Blacklisted in web forms', default=True, index=True,
    help='Blacklist this field for web forms'
)
```

**Default is `True` (blacklisted)**. Fields must be explicitly whitelisted. This is initialized in `init()` via raw SQL to set all existing NULL values to `True`.

### Form Builder Flow

1. Backend: Admin enables `website_form_access` on model; picks a text field for data storage
2. Frontend: Editor drags fields from palette; each field maps to an `ir.model.fields` record
3. Submit: POST to `/website/form/` controller
4. Controller: looks up `website_form_key` or model name in FormBuilder registry; calls `_get_form_writable_fields()` to get allowed fields; validates input; creates record

```python
def _get_form_writable_fields(property_origins=None) -> dict
```
Whitelist of fields: `website_form_blacklisted = False`. Special case: for `mail.mail`, hardcoded set `email_from, email_to, email_cc, email_bcc, body, reply_to, subject`. Strips `readonly`, `json`, `many2one_reference`, and magic columns.

```python
def formbuilder_whitelist(model, fields) -> bool
```
Called from frontend to dynamically whitelist fields. Only allowed for `website.group_website_designer`. Uses raw SQL to avoid triggering registry reloads (ORM would reload for custom fields).

---

## ir.http Middleware

**File:** `models/ir_http.py`

Overrides the base `http_routing` ir_http class to add website awareness.

### Key Overrides

| Method | Purpose |
|--------|---------|
| `_auth_method_public()` | Sets `request.uid` to `website.user_id` if no session |
| `_get_public_users()` | Adds `website.user_id` to the public user list |
| `_match(path)` | Sets `request.website_routing` from current website before routing |
| `_frontend_pre_dispatch()` | Sets `allowed_company_ids`, `website_id` context, `request.website` |
| `_get_default_lang()` | Returns website's `default_lang_id` in frontend context |
| `_register_website_track(response)` | Hook after response: if view has `track=True`, creates visitor + track via `_handle_webpage_dispatch` |
| `_serve_page()` | Dispatches to `website.page._get_response()`; handles trailing slash redirects and canonical redirects |
| `_serve_redirect()` | After routing fails, checks `website.rewrite` for 301/302 matches |
| `_serve_fallback()` | Entry point: tries attachments, then page, then redirects |
| `_url_for(url, lang_code)` | Applies URL rewriting (from `website.rewrite`) before returning |

### Request Flow

```
HTTP Request
    │
    ├── ir.http._match()
    │       Sets request.website_routing = website.id
    │       (cached routing map per website)
    │
    ├── ir.http._pre_dispatch()
    │       Sets allowed_company_ids (single-company lock)
    │       Sets website_id context
    │       Sets request.website = website record
    │       Injects tz from GeoIP cookie
    │
    ├── Route handler executes
    │
    ├── ir.http._post_dispatch()
    │       Calls _register_website_track(response)
    │       Checks response.status_code == 200
    │       Checks not a bot
    │       Checks X-Disable-Tracking header not set
    │       If view has track=True: upsert visitor + insert track
    │
    └── HTTP Response
```

### Bot Detection

`_register_website_track` calls `is_a_bot()` to skip tracking for crawlers. Bots would otherwise inflate visitor counts.

---

## website.snippet.filter

**File:** `models/website_snippet_filter.py`

Data source for dynamic snippets (e.g., "show 4 latest products").

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Filter display name (`translate=True`) |
| `action_server_id` | Many2one | Server action providing data (XOR with `filter_id`) |
| `filter_id` | Many2one | `ir.filters` record providing domain/sort (XOR with `action_server_id`) |
| `field_names` | Char | Comma-separated list of field names to render |
| `limit` | Integer | Max records (1-16; enforced by constraint) |
| `website_id` | Many2one | Website scope (`ondelete=cascade`) |
| `model_name` | Char | Computed from either `filter_id` or `action_server_id` |
| `help` | Text | Filter description (`translate=True`) |

### Data Flow

`_prepare_values()` applies `website_id` and `company_id` scoping automatically if those fields exist on the target model. Adds `is_published=True` if the field exists. Runs as `sudo(False)` to respect ir.rules.

Sample records are generated by `_prepare_sample()` using hardcoded sample data or random monetary/integer values.

---

## Security

### Groups Hierarchy

```
base.group_system
    └── implied: website.group_website_designer (via implied_by_ids)
                    └── implied: website.group_website_restricted_editor
                                └── implied: base.group_sanitize_override

base.group_public
    └── implied: website.website_page_controller_expose

base.group_portal
    └── implied: website.website_page_controller_expose
```

### Record Rules

| Rule | Model | Groups | Domain |
|------|-------|--------|--------|
| `website_menu` | `website.menu` | all | `group_ids` is empty OR user in group |
| `website_designer_edit_qweb` | `ir.ui.view` (qweb only) | `website_designer` | `(1, '=', 1)` (full access) |
| `website_designer_view` | `ir.ui.view` (non-qweb) | `website_designer` | read-only |
| `website_group_system_edit_all_views` | `ir.ui.view` | `base.group_system` | `(1, '=', 1)` |
| `website_page_rule_public` | `website.page` | public+portal | `website_published=True` |
| `view_rule_visibility_public` | `ir.ui.view` (qweb) | public | `visibility in ('public', False)` |
| `view_rule_visibility_connected` | `ir.ui.view` (qweb) | portal | `visibility in ('public', 'connected', False)` |
| `website_page_controller_rule_public` | `website.controller.page` | public+portal | `website_published=True` |

### Key Security Notes (L4)

- **Visitor data**: `website_track_ids` and `page_ids` are restricted to `website_designer` via field groups; computed via `sudo()` internally
- **Password-protected pages**: `visibility_password` is stored hashed and only readable by `base.group_system`; designers see `********` via `visibility_password_display` computed field
- **Form builder**: requires `website_form_access=True` on the model; fields must be explicitly whitelisted
- **COW isolation**: the `website_id` + record rules combination ensures each website's designer can only modify their own views
- **CSRF in cached pages**: CSRF tokens are post-processed (replaced) in cached HTML at serve time, preventing token reuse attacks
- **Multi-company**: `allowed_company_ids` is locked to the website's `company_id` during frontend dispatch, preventing cross-company data leakage
- **XSS in mega_menu_content**: `sanitize=False` but the HTML editor context ensures only whitelisted tags are allowed in the editor itself

---

## Performance Considerations

| Area | Technique | Impact |
|------|-----------|--------|
| Visitor tracking | Raw SQL UPSERT | Single DB round-trip per page view |
| Timezone updates | `FOR NO KEY UPDATE SKIP LOCKED` | Avoids deadlocks in concurrent requests |
| Routing map | Per-website `ormcache` on `_rewrite_len` | Avoids rebuild on every request |
| Page lookup | `ormcache` on `_get_page_info` | Sub-millisecond cached page metadata |
| Website resolution | `ormcache` on `_get_current_website_id` | One DB hit per domain per worker process |
| Menu visibility | Prefetched in `_compute_menu` | Single query for all menus + is_visible |
| Snippet asset cleanup | Batch SQL + `active` toggle | Reduces asset bundle size after theme switches |
| `_get_cached_values` | Manual `fetch()` of 4 fields only | Avoids translatable-field access during early dispatch |

---

## Odoo 18 -> Odoo 19 Changes

| Area | Change |
|------|--------|
| Visitor tracking | `_upsert_visitor` now uses raw SQL with `WITH` clause for combined visitor+track upsert in a single query |
| Page caching | Full HTTP caching system with `_allow_to_use_cache`, `_get_cache_key`, `_post_process_response_from_cache` hooks added |
| Page visibility | New `visibility` field on `ir.ui.view` (password, connected, group) replacing older `website_published` approaches |
| SEO metadata | `website.seo.metadata` mixin enhanced with `is_seo_optimized` computed field |
| Form builder | `website_form_key` field added for FormBuilder plugin registry |
| CDN | `cdn_filters` now stored as newline-separated regexes instead of a comma-separated string |
| Third-party blocking | Default blocked domain list expanded significantly; `#ignore_default` directive added |
| Menu constraint | Two-level hierarchy constraint now explicitly enforced; mega menu parent/child rules clarified |
| Plausible | Shared key authentication support added (`plausible_shared_key`) |
| Robots.txt | Now stored as `Html` field (was Char/blob) |

---

## Related

- [Modules/website_blog](modules/website_blog.md) -- Blog posts and tags
- [Modules/website_sale](modules/website_sale.md) -- E-commerce storefront
- [Modules/website_event](modules/website_event.md) -- Event management
- [Modules/website_forum](modules/website_forum.md) -- Forum/community
- [Modules/website_crm](modules/website_crm.md) -- Lead capture forms
- [Modules/website_payment](modules/website_payment.md) -- Online payments
- [Modules/website_livechat](modules/website_livechat.md) -- Live chat
- [Modules/website_slides](modules/website_slides.md) -- E-learning
- [Modules/website_hr_recruitment](modules/website_hr_recruitment.md) -- Job applications
- [Core/API](core/api.md) -- HTTP routing, controllers
- [Patterns/Security Patterns](patterns/security-patterns.md) -- ACL, record rules
