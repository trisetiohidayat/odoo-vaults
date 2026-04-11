---
tags:
  - odoo
  - odoo19
  - website
  - link_tracker
  - utm
  - marketing
  - modules
---

# website_links

> Generate short, trackable URLs with UTM parameters for marketing campaigns, and view click analytics via integrated graphs.

## Module Overview

| Property | Value |
|----------|-------|
| **Category** | Website/Website |
| **Version** | 1.0 |
| **Depends** | `website`, `link_tracker` |
| **Auto-install** | `True` |
| **License** | LGPL-3 |

## Purpose

`website_links` extends Odoo's `link_tracker` module with a **website-based URL shortening and analytics interface**. It allows marketers to:

1. **Create short URLs** from the website with optional UTM campaign parameters
2. **Track clicks** on shortened links embedded in emails, social posts, etc.
3. **View click analytics** directly in Odoo (list view + dedicated statistics page)
4. **Access Google Analytics data** by appending `+` to a short URL (e.g., `/r/abc123+`)

## Dependencies Chain

```
website_links
├── website      (website context, rendering, menus)
└── link_tracker (link.tracker model, click tracking, UTM)
```

The base `link_tracker` module provides:
- `link.tracker` model (URL shortening, code generation)
- `link_tracker.click` model (individual click records)
- UTM field support (`campaign_id`, `source_id`, `medium_id`)

## Key Concepts

### 1. URL Shortening via JSON-RPC

Marketers create shortened links directly from the Odoo website interface:

```python
# controller/main.py
@http.route('/website_links/new', type='jsonrpc', auth='user', methods=['POST'])
def create_shorten_url(self, **post):
    if 'url' not in post or post['url'] == '':
        return {'error': 'empty_url'}
    return request.env['link.tracker'].search_or_create([post]).read()
```

- Called from a frontend widget (JavaScript on the website)
- `auth='user'` requires logged-in user
- `search_or_create()` -- creates a new tracker or returns existing one for the same URL
- Returns tracker data (id, short URL, code) to the frontend

### 2. Short URL Host Computation

The module overrides `_compute_short_url_host` to dynamically determine the base URL:

```python
# models/link_tracker.py
def _compute_short_url_host(self):
    current_website = self.env['website'].get_current_website()
    base_url = current_website.get_base_url() if current_website == self.env.company.website_id else self.env.company.get_base_url()
    for tracker in self:
        tracker.short_url_host = urls.urljoin(base_url, '/r/')
```

- If the user is on a specific website, use that website's base URL
- Otherwise fall back to the company's base URL
- Result: short URLs are generated as `{website_base}/r/{code}`

### 3. Dedicated Statistics Page

When a user appends `+` to a short URL (`/r/{code}+`), Odoo renders a **statistics dashboard**:

```python
@http.route('/r/<string:code>+', type='http', auth="user", website=True)
def statistics_shorten_url(self, code, **post):
    code = request.env['link.tracker.code'].search([('code', '=', code)], limit=1)
    if code:
        return request.render("website_links.graphs", {
            "can_create_link_tracker_code": request.env['link.tracker.code'].has_access('create'),
            **code.link_id.read()[0]
        })
    else:
        return request.redirect('/', code=301)
```

This page displays:
- Click counts over time (line/bar chart)
- Geographic distribution of clicks
- Device/browser breakdown
- Conversion tracking (if linked to a UTM campaign)

### 4. Recent Links Widget

The frontend provides a "Recent Links" widget:

```python
@http.route('/website_links/recent_links', type='jsonrpc', auth='user')
def recent_links(self, **post):
    return request.env['link.tracker'].recent_links(post['filter'], post['limit'])
```

Returns the user's recently created/tracked links for quick access.

### 5. Custom Short Code Assignment

Users can add a custom memorable code to a shortened URL:

```python
@http.route('/website_links/add_code', type='jsonrpc', auth='user')
def add_code(self, **post):
    link_id = request.env['link.tracker.code'].search([('code', '=', post['init_code'])], limit=1).link_id.id
    new_code = request.env['link.tracker.code'].search_count([
        ('code', '=', post['new_code']), ('link_id', '=', link_id)
    ])
    if new_code > 0:
        return new_code.read()
    else:
        return request.env['link.tracker.code'].create({
            'code': post['new_code'], 'link_id': link_id
        })[0].read()
```

### 6. Statistics Button in Link Tracker List

A button is added to the `link.tracker` list view:

```xml
<button name="action_visit_page_statistics" type="object" string="Statistics" icon="fa-bar-chart"/>
```

This opens the dedicated statistics page (`/r/{code}+`) for that tracker.

```python
def action_visit_page_statistics(self):
    return {
        'name': _("Visit Webpage Statistics"),
        'type': 'ir.actions.act_url',
        'url': '%s+' % (self.short_url),
        'target': 'new',
    }
```

### 7. Menu Integration

The module adds a "Link Tracker" menu entry under the website menu:

```xml
<menuitem id="menu_link_tracker"
    name="Link Tracker"
    sequence="25"
    parent="website.menu_current_page"
    action="website.website_preview"/>
```

Points to `website.website_preview` (the website page preview/action), allowing easy access to the link management interface.

## File Structure

```
website_links/
├── __init__.py
├── __manifest__.py
├── controller/
│   ├── __init__.py
│   └── main.py              # JSON-RPC endpoints + short URL stats
├── models/
│   ├── __init__.py
│   └── link_tracker.py      # _compute_short_url_host override + action
├── views/
│   ├── link_tracker_views.xml         # list view button injection
│   ├── website_links_template.xml     # /r short URL page
│   └── website_links_graphs.xml       # statistics graphs page
├── static/
│   ├── src/
│   │   ├── components/*.js   # frontend components
│   │   ├── interactions/*.js
│   │   ├── services/website_custom_menus.js
│   │   ├── css/website_links.css
│   │   └── xml/*.xml
│   └── tests/**
├── security/
│   └── ir.model.access.csv
├── i18n/
│   └── *.po
└── tests/
```

## URL Structure

| URL | Type | Auth | Description |
|-----|------|------|-------------|
| `/website_links/new` | JSON-RPC | User | Create/get short URL |
| `/r/{code}` | HTTP | Public | Redirect to target URL, log click |
| `/r/{code}+` | HTTP | User+Website | Statistics dashboard |
| `/website_links/add_code` | JSON-RPC | User | Add custom code |
| `/website_links/recent_links` | JSON-RPC | User | Get recent links |
| `/website_links/shorten` | HTTP | User | Shorten URL page |

## Flow Diagram

```
                    Marketer creates short link
                    (from website widget or API)
                             |
                             v
              link.tracker record created
              (or existing one returned)
                             |
                             v
              Short URL displayed:
              https://company.com/r/abc123
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
   Embed in email    Share on social    Use in SMS/ad
         |                   |                   |
         v                   v                   v
   Recipient clicks  Recipient clicks  Recipient clicks
         |                   |                   |
         v                   v                   v
   /r/abc123 (public)  /r/abc123       /r/abc123
         |                   |                   |
         v                   v                   v
   link_tracker.click created   +   UTM params captured
         |                   |                   |
         v                   v                   v
         All clicks aggregated in
         link.tracker click_count
                             |
                             v
         Marketer visits /r/abc123+
         to see statistics dashboard
```

## Link Tracker Model (from `link_tracker` base module)

| Field | Type | Description |
|-------|------|-------------|
| `url` | Char | Original target URL |
| `code` | Char | Short code (e.g., `abc123`) |
| `short_url` | Char (computed) | Full short URL |
| `title` | Char | Optional label |
| `campaign_id` | Many2one | UTM campaign |
| `source_id` | Many2one | UTM source |
| `medium_id` | Many2one | UTM medium |
| `link_click_ids` | One2many | Click records |

## Integration with `mass_mailing_crm`

When short links are used in mass mailings with UTM parameters:
- The `source_id` set on the link tracker matches leads created from clicks
- `mass_mailing_crm` counts those leads in the mailing's stat button
- This creates a full **campaign attribution chain**: mailing → click → website visit → lead → opportunity

## Related Modules

| Module | Relationship |
|--------|-------------|
| `link_tracker` | Base module providing `link.tracker` and click tracking |
| `website` | Provides website context, rendering, menus |
| `mass_mailing` | Uses link trackers for UTM-tagged URLs in emails |
| `mass_mailing_crm` | Can count leads attributed to UTM sources from link trackers |

## Static Assets

The module includes frontend JavaScript components and CSS:

```python
'assets': {
    'web.assets_frontend': [
        'website_links/static/src/components/*.js',
        'website_links/static/src/interactions/*.js',
        'website_links/static/src/css/website_links.css',
        'website_links/static/src/xml/*.xml',
    ],
    'website.assets_editor': [
        'website_links/static/src/services/website_custom_menus.js',
    ],
}
```

These provide the interactive URL shortener widget and recent links list shown on the website.

