# Website Module (website)

## Overview

The `website` module provides multi-website management capabilities, content management, SEO tools, and website configuration for Odoo. It is the foundation for all website-related functionality.

## Key Models

### website (Website)

The central model for multi-website management.

**Fields:**
- `name`: Char - Website name
- `domain`: Char - Domain name (used for routing and domain-based website detection)
- `company_id`: Many2one - Company this website belongs to (key for multi-company/multi-website)
- `language_ids`: Many2many - Available languages
- `default_lang_id`: Many2one - Default language
- `homepage_url`: Char - URL for the homepage
- `configurator_done`: Boolean - Whether the website configurator has been completed
- `social_default_image`: Binary - Default social media image
- `favicon`: Binary - Website favicon
- `user_id`: Many2one - Public user for this website
- `partner_id`: Many2one - Partner associated with the website (typically the company contact)
- `pricelist_id`: Many2one - Current pricelist
- `currency_id`: Many2one - Currency (computed from pricelist)
- `website_logo`: Binary - Logo stored on website (not company)
- `cookies_bar`: Boolean - Show cookies consent bar
- `group_local_server`: Boolean - Enable local server group for development

**Key Methods:**
- `get_current_website()`: Returns the current website based on request context or domain
- `website_domain(website_id)`: Returns domain for filtering records by website
- `sale_product_domain()`: Returns domain for products available on website
- `sale_get_order()`: Gets or creates the current cart (sale.order) for the website
- `sale_reset()`: Clears the cart from session
- `_get_current_pricelist()`: Determines the current pricelist considering GeoIP
- `_get_pl_partner_order()`: Cached method returning available pricelists

**Website Routing (`ir_http` extension):**
- `_auth_method_public()`: Sets public user from website if no user logged in
- `_get_public_users()`: Includes website-specific public user
- `_serve_page()`: Serves website pages from `website.page` model
- `_serve_redirect()`: Handles 301/302 redirects from `website.rewrite`

### website.page

Represents a page on the website, inheriting from `ir.ui.view`.

**Fields:**
- `url`: Char - Page URL (required)
- `view_id`: Many2one - Associated ir.ui.view
- `website_id`: Many2one - Website (inherited from view)
- `website_indexed`: Boolean - Whether page is indexed by search engines
- `date_publish`: Datetime - Scheduled publishing date
- `is_published`: Boolean - Publication status
- `menu_ids`: One2many - Associated website menus
- `is_in_menu`: Boolean - Whether page is linked in a menu
- `is_homepage`: Boolean - Whether this is the website homepage
- `is_visible`: Boolean - Whether page is visible (published and not scheduled)
- `header_overlay`, `header_color`, `header_visible`, `footer_visible`: Page layout options

**Key Methods:**
- `clone_page(page_id, page_name, clone_menu)`: Clones a page with optional menu
- `_get_most_specific_pages()`: Returns the most specific version of pages (website-specific over generic)
- `_search_get_detail()`: Implements website search integration
- `_search_fetch()`: Search implementation for pages

**Cross-Model Relationships:**
- Inherits `website.published.multi.mixin` for publication workflow
- Inherits `website.searchable.mixin` for website search integration
- Links to `ir.ui.view` for actual content rendering

### website.menu

Navigation menu items for websites.

**Fields:**
- `name`: Char - Menu item name (required)
- `url`: Char - URL (can be internal path, external URL, or email)
- `page_id`: Many2one - Link to `website.page`
- `controller_page_id`: Many2one - Link to `website.controller.page`
- `website_id`: Many2one - Website this menu belongs to
- `parent_id`: Many2one - Parent menu item (max 2 levels deep)
- `child_id`: One2many - Child menu items
- `sequence`: Integer - Display order
- `group_ids`: Many2many - Groups that can see this menu
- `is_mega_menu`: Boolean - Whether this is a mega menu
- `mega_menu_content`: Html - Content for mega menus
- `mega_menu_classes`: Char - CSS classes for mega menus
- `is_visible`: Boolean - Computed visibility based on page state

**Key Methods:**
- `_validate_parent_menu()`: Constraint ensuring max 2 levels and mega menu rules
- `get_tree()`: Returns hierarchical menu structure for frontend rendering
- `save()`: Saves menu structure from drag-drop editor
- `_is_active()`: Determines if menu is active based on URL matching
- `_clean_url()`: Normalizes URLs with heuristics

**Edge Cases:**
- Menus without `website_id` are duplicated for all websites on create
- Main menu (`website.main_menu`) cannot be deleted
- URL matching considers unslugified paths and query parameters

### website.multi.mixin

Abstract mixin providing `website_id` field for multi-website scoping.

**Fields:**
- `website_id`: Many2one - Website scoping field

**Key Methods:**
- `can_access_from_current_website()`: Checks if record is accessible from current website context

**Usage Pattern:**
Models that need website-scoped content should inherit this mixin to get automatic website filtering.

### website.published.mixin

Abstract mixin for publication workflow.

**Fields:**
- `is_published`: Boolean - Publication status
- `website_published`: Boolean - Website-specific publication (computed/inverse)
- `can_publish`: Boolean - Whether current user can publish
- `website_url`: Char - Full URL to access document

**Key Methods:**
- `website_publish_button()`: Toggle publication status
- `open_website_url()`: Open the website URL in client action
- `_compute_can_publish()`: Checks if user has website designer rights

### website.seo.metadata

Abstract mixin providing SEO fields.

**Fields:**
- `website_meta_title`: Char - SEO title
- `website_meta_description`: Text - SEO description
- `website_meta_keywords`: Char - SEO keywords
- `website_meta_og_img`: Char - OpenGraph image
- `is_seo_optimized`: Boolean - Whether SEO fields are complete

**Key Methods:**
- `_default_website_meta()`: Returns default meta information for the record
- `get_website_meta()`: Returns final meta information merging defaults with custom values

### res.company (website extension)

**Fields:**
- `website_id`: Many2one - Computed from linked website record

**Key Methods:**
- `_compute_website_id()`: Searches for website with matching company_id
- `_check_active()`: Constraint preventing archive of company with linked website

## Configuration Models

### website.configurator.feature

Features available in the website configurator wizard.

**Fields:**
- `name`: Char - Feature name
- `description`: Text - Feature description
- `icon`: Char - Icon class (FA icons)
- `module_id`: Many2one - ir.module.module to install
- `page_view_id`: Many2one - ir.ui.view for page-based features
- `menu_sequence`: Integer - Position in menu
- `menu_company`: Boolean - Add in "Company" submenu
- `website_config_preselection`: Char - Preselection for configurator

### website.configurator.step

Steps in the configurator wizard workflow.

## Search Integration

### website.searchable.mixin

Abstract mixin for integrating models into website search.

**Key Methods:**
- `_search_build_domain()`: Builds search domain from query terms
- `_search_get_detail()`: Returns search configuration (model, domain, fields, mapping)
- `_search_fetch()`: Performs the actual search
- `_search_render_results()`: Renders search results

**Usage:**
Models like `website.page`, `blog.post`, `event.event`, `product.template` inherit this mixin for website search functionality.

## Edge Cases and Workflow Triggers

1. **Page URL Slugging**: When `url` is changed, it is automatically slugified and menu URLs are synced
2. **Website COW (Copy-on-Write)**: Generic pages can be COWed per website; most specific pages take precedence
3. **Menu Duplication**: Menus without `website_id` are automatically duplicated for all websites
4. **SEO Canonical**: `_default_website_meta()` generates canonical URLs based on request context
5. **Multi-language Routing**: Language prefix is added to URL when not default language
6. **GeoIP Pricelist**: `_get_current_pricelist()` uses GeoIP country code to suggest locale-appropriate pricelist
7. **Cookie Consent**: `_is_allowed_cookie()` validates optional cookies based on website setting
8. **Tracking Registration**: `_register_website_track()` logs page views for published pages with tracking enabled

## Cross-Module Relationships

- **website_sale**: Extends website with eCommerce fields (pricelists, cart, checkout flow)
- **website_blog**: Blog integration via `website.searchable.mixin`
- **website_event**: Event pages via website.menu and website.page
- **website_crm**: Lead capture from website forms
- **website_slides**: Course/channel pages for eLearning

## Key Technical Patterns

### Website Detection
```python
website = request.env['website'].get_current_website()
```

### Multi-website Domain
```python
domain = website.website_domain()  # [('website_id', 'in', [False, website.id])]
```

### URL Generation
```python
url = '/shop/%s' % self.env['ir.http']._slug(product)
```

### Session-based Cart
```python
sale_order = website.sale_get_order(force_create=True)
```
