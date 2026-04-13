---
tags: [odoo, odoo17, module, website, research_depth]
research_depth: deep
---

# Website Module — Deep Research

**Source:** `addons/website/models/` (Odoo 17)

## Module Architecture

```
website
    ├── website.menu          (navigation structure, mega menus)
    ├── website.page         (_inherits ir.ui.view, CMS pages)
    ├── website.controller_page  (programmatic pages bound to models)
    ├── website.rewrite     (URL redirects: 301/302/308/404)
    ├── website.configurator_feature (theme setup wizard features)
    ├── website.snippet_filter  (dynamic snippet content filtering)
    ├── website.visitor      (anonymous + portal visitor tracking)
    ├── website.form        (form submission handling)
    └── ir.ui.view          (QWeb templates; pages inherit from here)
        └── ir.qweb         (QWeb rendering engine)
        └── ir.qweb_fields  (QWeb field formatters)
```

Supporting models: `assets.py`, `base_partner_merge.py`, `ir_actions_server.py`, `ir_asset.py`, `ir_binary.py`, `ir_http.py`, `ir_model.py`, `ir_model_data.py`, `ir_rule.py`, `ir_ui_menu.py`, `ir_ui_view.py`, `mixins.py`, `res_company.py`, `res_config_settings.py`, `res_lang.py`, `res_partner.py`, `res_users.py`, `theme_models.py`, `ir_module_module.py`, `ir_qweb.py`.

---

## website — Multi-Website Configuration

**File:** `website.py` (~1700 lines)

### Class Definition (Line 54)

```python
class Website(models.Model):
    _name = "website"
    _description = "Website"
    _order = "sequence, id"
```

### All Fields

| Field | Type | Line | Description |
|-------|------|------|-------------|
| `name` | Char | 72 | Website name, required |
| `sequence` | Integer | 73 | Sort order, default 10 |
| `domain` | Char | 74 | Bound domain (e.g. `https://www.example.com`); HTTP prefix auto-added |
| `company_id` | Many2one res.company | 75 | Company this website belongs to, required |
| `language_ids` | Many2many res.lang | 76 | Active languages, default=all installed |
| `language_count` | Integer | 79 | Computed count of active languages |
| `default_lang_id` | Many2one res.lang | 80 | Default language, required, from ir.default |
| `auto_redirect_lang` | Boolean | 81 | Language-based browser redirect |
| `cookies_bar` | Boolean | 82 | Display cookies bar |
| `configurator_done` | Boolean | 83 | Configurator completed or skipped |
| `logo` | Binary | 110 | Website logo (default: website_logo.svg) |
| `social_twitter` | Char | 111 | Twitter account |
| `social_facebook` | Char | 112 | Facebook account |
| `social_github` | Char | 113 | GitHub account |
| `social_linkedin` | Char | 114 | LinkedIn account |
| `social_youtube` | Char | 115 | YouTube account |
| `social_instagram` | Char | 116 | Instagram account |
| `social_tiktok` | Char | 117 | TikTok account |
| `social_default_image` | Binary | 118 | Custom social share image |
| `has_social_default_image` | Boolean | 119 | Computed: social_default_image is set |
| `google_analytics_key` | Char | 121 | GA4 measurement ID |
| `google_search_console` | Char | 122 | Google Search Console verification |
| `google_maps_api_key` | Char | 124 | Google Maps API key |
| `plausible_shared_key` | Char | 126 | Plausible analytics shared key |
| `plausible_site` | Char | 127 | Plausible site name |
| `user_id` | Many2one res.users | 129 | **Public (guest) user** for this website |
| `partner_id` | Many2one res.partner | 133 | Related: `user_id.partner_id` |
| `cdn_activated` | Boolean | 130 | CDN enabled |
| `cdn_url` | Char | 131 | CDN base URL |
| `cdn_filters` | Text | 132 | URL regex patterns for CDN rewriting |
| `menu_id` | Many2one website.menu | 134 | Root navigation menu (computed) |
| `homepage_url` | Char | 135 | Custom homepage redirect |
| `custom_code_head` | Html | 136 | Custom `<head>` code injection |
| `custom_code_footer` | Html | 137 | Custom end-of-`<body>` code injection |
| `robots_txt` | Html | 139 | robots.txt content (website_designer group) |
| `favicon` | Binary | 145 | Website favicon (256x256 ICO) |
| `theme_id` | Many2one ir.module.module | 146 | Installed theme |
| `specific_user_account` | Boolean | 148 | Portal accounts scoped per website |
| `auth_signup_uninvited` | Selection | 149 | `b2b` (invitation) / `b2c` (free signup) |

### domain Binding — Multi-Website Resolution (Lines 284-289, 1098-1138)

```python
# _handle_domain (Line 285): Normalizes domain on create/write
if 'domain' in vals and vals['domain']:
    if not vals['domain'].startswith('http'):
        vals['domain'] = 'https://%s' % vals['domain']
    vals['domain'] = vals['domain'].rstrip('/')

# get_current_website (Line 1098): Resolves current website from request
# Priority:
# 1. Context 'website_id' (set by routing)
# 2. Request domain match against website.domain
# 3. Fallback to website with matching company
# 4. Default website (id=1 or first found)
```

The domain resolution mechanism in `get_current_website()` uses the HTTP request's Host header to match against registered `website.domain` values. The `_idna_url()` method (line 333) handles international domain names via IDNA encoding.

### Public User Pattern — website_id Creates a Real res.users (Line 129, 207-226)

```python
user_id = fields.Many2one(
    'res.users',
    string='Public User',
    required=True
)

# On website create, if user_id not provided:
if 'user_id' not in vals:
    company = self.env['res.company'].browse(vals.get('company_id'))
    vals['user_id'] = company._get_public_user().id
```

Each website has a dedicated **public user** (`res.users` record with no login/password). This user:
- Has `share=True` (portal-level access)
- Cannot log in but exists as a real user record
- Is used as the default author for public content
- Is related via `partner_id` (line 133)
- When the website's company changes, the public user is switched to the new company's public user (lines 235-239)

### Theme System (Lines 146, 371-431, 449-802)

```python
theme_id = fields.Many2one('ir.module.module', help='Installed theme')
```

The configurator (`configurator_apply()`, lines 449-802):
1. Installs the selected theme module via `button_immediate_install()`
2. Generates snippet templates
3. Applies color palette via SCSS customization
4. Installs feature modules and creates pages
5. Generates AI text content via OLG API for placeholder text
6. Downloads and attaches industry-specific images

Theme SVG logos are processed via `_process_svg()` (line 34 in configurator_feature.py) which replaces color placeholders (`#3AADAA`, `#7C6576`, etc.) with the website's palette.

### Language Support (Lines 64-81, 1054-1091)

```python
def _active_languages(self):
    return self.env['res.lang'].search([]).ids

def _default_language(self):
    lang_code = self.env['ir.default']._get('res.partner', 'lang')
    def_lang_id = self.env['res.lang']._lang_get_id(lang_code)
    return def_lang_id or self._active_languages()[0]
```

- `_get_alternate_languages()` (line 1054) generates hreflang tags for SEO
- If only one region per language, uses short code (e.g., `en` instead of `en_US`)
- Adds `x-default` hreflang pointing to the default language URL
- `auto_redirect_lang` (line 81) redirects users to their browser's preferred language

### Configurator (Lines 328-802)

The website configurator is a wizard-like flow:
- `configurator_init()`: Fetches industries, features, and module states from IAP
- `configurator_recommended_themes()`: Fetches theme suggestions from IAP, processes SVG previews
- `configurator_apply()`: Installs theme, configures pages, generates content

Key configurator features include:
- CTA button customization (`get_cta_data()`)
- Footer link configuration (`configurator_get_footer_links()`)
- Menu structure creation (`configurator_set_menu_links()`)

---

## website.menu — Navigation Structure

**File:** `website_menu.py` (~340 lines)

### Class Definition (Line 16)

```python
class Menu(models.Model):
    _name = "website.menu"
    _description = "Website Menu"
    _parent_store = True    # enables hierarchical queries
    _order = "sequence, id"
```

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Menu label, required, translate |
| `url` | Char | URL, default '' |
| `page_id` | Many2one website.page | Related CMS page |
| `controller_page_id` | Many2one website.controller_page | Related programmatic page |
| `new_window` | Boolean | Open in new tab |
| `sequence` | Integer | Sort order, default=last sequence + 1 |
| `website_id` | Many2one website | Owning website, cascade delete |
| `parent_id` | Many2one website.menu | Parent menu item |
| `child_id` | One2many website.menu | Child menu items |
| `parent_path` | Char | Materialized path for hierarchical queries |
| `is_visible` | Boolean | Computed visibility (checks page/controller publish status) |
| `is_mega_menu` | Boolean | Is a mega menu (computed from mega_menu_content) |
| `mega_menu_content` | Html | Mega menu content (QWeb/HTML) |
| `mega_menu_classes` | Char | CSS classes for mega menu |

### Menu Hierarchy — Max 2 Levels (Lines 69-98)

```python
def _validate_parent_menu(self):
    # Level check: menus cannot exceed 2 levels of nesting
    level = 0
    current_menu = parent_menu
    while current_menu:
        level += 1
        current_menu = current_menu.parent_id
        if level > 2:
            raise UserError(_("Menus cannot have more than two levels of hierarchy."))

    # Mega menu constraint: no parent, no children
    if parent_menu.is_mega_menu or (record.is_mega_menu and (parent_menu.parent_id or record.child_id)):
        raise UserError(_("A mega menu cannot have a parent or child menu."))

    # Submenu constraint: menus with children cannot be submenus
    if record.child_id and (parent_menu.parent_id or record.child_id.child_id):
        raise UserError(_("Menus with child menus cannot be added as a submenu."))
```

### Mega Menus — is_mega_menu (Lines 29-39, 53-55)

```python
is_mega_menu = fields.Boolean(
    compute=_compute_field_is_mega_menu,
    inverse=_set_field_is_mega_menu
)

def _set_field_is_mega_menu(self):
    for menu in self:
        if menu.is_mega_menu:
            if not menu.mega_menu_content:
                menu.mega_menu_content = self.env['ir.ui.view']._render_template(
                    'website.s_mega_menu_odoo_menu'
                )
        else:
            menu.mega_menu_content = False
            menu.mega_menu_classes = False
```

When a menu is set as mega menu without content, it gets the default `s_mega_menu_odoo_menu` template. Mega menus are always considered non-active (`_is_active()` returns False for mega menu).

### Per-Website Menu Duplication (Lines 100-142)

```python
def create(self, vals_list):
    for vals in vals_list:
        if 'website_id' in vals:
            menus |= super().create(vals)  # normal creation
            continue
        elif self._context.get('website_id'):
            vals['website_id'] = self._context['website_id']
            menus |= super().create(vals)  # with context website
            continue
        else:
            # No website_id specified: duplicate for ALL existing websites
            # Replace parent_id with each website's root menu
            for website in self.env["website"].search([]):
                parent_id = vals.get("parent_id")
                if not parent_id or parent_id == default_main_menu.id:
                    parent_id = website.menu_id.id
                w_vals.append({
                    **vals,
                    'website_id': website.id,
                    'parent_id': parent_id,
                })
            new_menu = super().create(w_vals)[-1:]
```

When a menu is created without `website_id`, Odoo duplicates it across **all existing websites**, substituting the parent_id with each website's root menu.

### _is_active() — URL Matching (Lines 197-255)

Menu is active if:
1. Menu has no children AND URL matches the request URL (after unslugifying)
2. OR any child menu is active
3. Query string parameters must match (not strict superset — allows extra params on request)
4. Domain must match if present in menu URL
5. Mega menus are never considered active (line 221)

```python
# Slug comparison: /shop/1 matches /shop/my-product-1
if unslug_url(menu_url.path) == unslug_url(request_url.path):
    if self.page_id and menu_url.path != request_url.path:
        return False  # exact path match required for pages
```

### get_tree() — Frontend Menu Rendering (Lines 258-282)

Returns a nested dict of menus for JSON serialization to JavaScript:

```python
def make_tree(node):
    menu_node = {
        'fields': {...},
        'children': [make_tree(child) for child in node.child_id],
        'is_homepage': menu_url == (website.homepage_url or '/'),
    }
```

### save() — Persisting Menu Editor Changes (Lines 284-339)

The website editor calls `save(website_id, data)` with a full menu tree. It:
1. Deletes menus in `to_delete`
2. Creates new menus (string IDs prefixed with `new-`)
3. Binds menus to pages via URL matching
4. Updates existing menus

---

## website.page — CMS Pages

**File:** `website_page.py` (~340 lines)

### Class Definition (Line 16)

```python
class Page(models.Model):
    _name = 'website.page'
    _inherits = {'ir.ui.view': 'view_id'}    # delegation inheritance
    _inherit = [
        'website.published.multi.mixin',
        'website.searchable.mixin',
    ]
    _description = 'Page'
    _order = 'website_id'
```

### _inherits Delegation — page IS a view (Line 18)

```python
_inherits = {'ir.ui.view': 'view_id'}
```

This is **delegation inheritance** (`_inherits`), not classic inheritance. The `website.page` record stores additional page metadata while delegating all view-related fields (`name`, `key`, `arch_db`, `website_id`, `inherit_id`, etc.) to the underlying `ir.ui.view` record. Deleting a `website.page` also deletes its `view_id` unless other pages share that view.

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `url` | Char | Page URL, required (slugified on write) |
| `view_id` | Many2one ir.ui.view | Delegated view record, required, cascade delete |
| `website_indexed` | Boolean | Include in sitemap, default True |
| `date_publish` | Datetime | Scheduled publish date |
| `menu_ids` | One2many website.menu | Menus linking to this page |
| `is_in_menu` | Boolean | Computed: page has menus; inverse creates/removes menu |
| `is_homepage` | Boolean | Computed: this page is the website homepage |
| `is_visible` | Boolean | Computed: published AND (no publish date OR past) |
| `header_overlay` | Boolean | Page option |
| `header_color` | Char | Page option |
| `header_text_color` | Char | Page option |
| `header_visible` | Boolean | Page option, default True |
| `footer_visible` | Boolean | Page option, default True |
| `website_id` | Many2one website | From view; controls multi-website scoping |
| `arch` | Text | From view; QWeb template content |

### URL Slugification — write() Behavior (Lines 174-207)

On URL change in `write()`:
1. `url` is slugified via `slugify(url, max_length=1024, path=True)` → prefixed with `/`
2. `get_unique_path()` ensures uniqueness for this website
3. All linked `website.menu` records have their URLs synced
4. If `redirect_old_url` flag is set, a `website.rewrite` entry is created for the old URL
5. Website's `homepage_url` is synced if this page was the homepage

### Visibility / Access Control (Lines 63-67, 223-240)

```python
def _compute_visible(self):
    for page in self:
        page.is_visible = page.website_published and (
            not page.date_publish or page.date_publish < fields.Datetime.now()
        )
```

Search results (`_search_get_detail`) filter out:
- Unpublished pages (unless user is designer)
- Password-protected pages
- Pages requiring login (if public user)
- Pages not matching the user's group membership

### _get_most_specific_pages() — Multi-Website Page Resolution (Lines 106-124)

When multiple websites share a generic page (no `website_id`), and one website's copy has a different URL, the generic page becomes inaccessible. `_get_most_specific_pages()` returns only the most specific page per URL:

```python
for page in self.sorted(key=lambda p: (p.url, not p.website_id)):
    # Take only: unique URL with website, OR unique URL without website (no other website-specific copy)
    if page.website_id or page_keys.count(page.key) == 1:
        ids.append(page.id)
```

---

## website.rewrite — URL Redirects

**File:** `website_rewrite.py` (~160 lines)

### Class Definition (Line 52)

```python
class WebsiteRewrite(models.Model):
    _name = 'website.rewrite'
    _description = "Website rewrite"
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Rule name, required |
| `website_id` | Many2one website | Target website |
| `active` | Boolean | Default True |
| `url_from` | Char | Source URL (indexed) |
| `route_id` | Many2one website.route | Route to prefill url_from |
| `url_to` | Char | Destination URL |
| `redirect_type` | Selection | `404`/`301`/`302`/`308` |
| `sequence` | Integer | Rule priority |

### redirect_type Options (Lines 62-73)

| Type | Description |
|------|-------------|
| `301` | Moved permanently — browser caches redirect |
| `302` | Moved temporarily — no browser cache |
| `308` | Rewrite — adds alias in routing map; both URLs work |
| `404` | Not Found — removes from routing map |

308 rewrite rules are validated for URL parameter compatibility (lines 95-114):
- All `<param>` in `url_from` must appear in `url_to`
- `url_to` cannot be an existing route
- Werkzeug routing map validates the URL_to syntax

`_invalidate_routing()` (line 151) calls `self.env.registry.clear_cache('routing')` to reload routing rules across all workers.

---

## website.controller_page — Programmatic Pages

**File:** `website_controller_page.py` (~65 lines)

### Class Definition (Line 7)

```python
class WebsiteControllerPage(models.Model):
    _name = 'website.controller_page'
    _inherits = {'ir.ui.view': 'view_id'}
    _inherit = [
        'website.published.multi.mixin',
        'website.searchable.mixin',
    ]
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `view_id` | Many2one ir.ui.view | Delegated view, cascade delete |
| `menu_ids` | One2many website.menu | Related menus |
| `website_id` | Many2one website | From view |
| `page_name` | Char | Display name, used in URL |
| `name_slugified` | Char | Computed URL slug |
| `page_type` | Selection | `listing` (list) or `single` (detail) |
| `record_domain` | Char | Domain to restrict visible records |
| `default_layout` | Selection | `grid`/`list` |

Like `website.page`, this uses delegation `_inherits`. It exposes model/record data on the website without a custom controller, with a route `/model/<name_slugified>`.

---

## website.configurator.feature — Theme Setup Wizard

**File:** `website_configurator_feature.py` (~65 lines)

### Class Definition (Line 10)

```python
class WebsiteConfiguratorFeature(models.Model):
    _name = 'website.configurator.feature'
    _description = 'Website Configurator Feature'
    _order = 'sequence'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Display order |
| `name` | Char | Feature name, translate |
| `description` | Char | Feature description, translate |
| `icon` | Char | Icon identifier |
| `iap_page_code` | Char | IAP service identifier for snippet list generation |
| `website_config_preselection` | Char | Comma-separated website types for pre-selection |
| `page_view_id` | Many2one ir.ui.view | View template for this feature |
| `module_id` | Many2one ir.module.module | Module to install for this feature |
| `feature_url` | Char | URL path for the feature |
| `menu_sequence` | Integer | If set, creates a menu at this sequence |
| `menu_company` | Boolean | If set, adds as child of "Company" menu |

Either `page_view_id` OR `module_id` must be set (not both), enforced by `_check_module_xor_page_view()`.

### _process_svg() — Theme Logo Color Replacement (Lines 33-63)

Replaces placeholder colors in theme SVG logos:
- Reads `theme/static/description/{theme}.svg`
- Maps default palette colors to the website's palette
- Substitutes color values and image URLs

---

## See Also

- [Modules/website_sale](Modules/website_sale.md) — e-commerce / shop
- [Modules/Sale](Modules/Sale.md) — base sale orders
- [Modules/sale_management](Modules/sale_management.md) — quotation templates
- [Modules/CRM](Modules/CRM.md) — website lead capture via `website_crm`
- [Modules/website_blog](Modules/website_blog.md) — blog
- [Modules/website_event](Modules/website_event.md) — events
- [Core/HTTP Controller](Core/HTTP-Controller.md) — @http.route, JSON responses
