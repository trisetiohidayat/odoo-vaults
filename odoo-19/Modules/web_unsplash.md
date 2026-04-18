---
uuid: 5f4d3c2b-1a0e-4f5d-9c8b-2e6a7c4d8f0e
tags:
  - odoo
  - odoo19
  - modules
  - integration
  - media
  - html_editor
  - website
---

# Web Unsplash (`web_unsplash`)

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | `web_unsplash` |
| **Category** | Hidden (Infrastructure) |
| **Depends** | `base_setup`, `html_editor` |
| **Auto-install** | True |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Source** | `odoo/addons/web_unsplash/` |

## Description

The `web_unsplash` module integrates the **Unsplash API** into Odoo, enabling users to search and insert high-quality, royalty-free images directly from within Odoo's image picker (media dialog). Images are served from the Unsplash CDN rather than being downloaded into Odoo's attachment storage, keeping database size minimal.

Unsplash provides free high-resolution photos under the [Unsplash License](https://unsplash.com/license). Proper attribution is managed by the Unsplash API license automatically.

## Architecture

This is a **frontend integration module** that connects the [Modules/html_editor](html_editor.md) image picker to the Unsplash API. It consists of:

- A **backend model layer** that stores Unsplash credentials and manages attachment rights for Unsplash URLs
- A **frontend service layer** (JavaScript) that wraps the Unsplash REST API
- A **media dialog integration** that exposes Unsplash search as a tab in Odoo's image picker
- **Attachment override** that bypasses rights checks for properly formatted Unsplash URLs

The module does **not** define any business models. Its purpose is purely to bridge the HTML editor's media dialog to Unsplash's image library.

## Module Structure

```
web_unsplash/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── ir_attachment.py       # Attachment rights bypass for Unsplash URLs
│   ├── ir_qweb_fields.py      # QWeb image field override for Unsplash URLs
│   ├── res_config_settings.py # Unsplash credentials in Settings
│   └── res_users.py           # Unsplash settings permission check
└── static/
    └── src/
        ├── js/
        │   ├── unsplash_service.js        # Unsplash API wrapper
        │   ├── media_dialog/              # Media dialog integration
        │   ├── unsplash_credentials/      # Credential management
        │   ├── unsplash_error/           # Error handling
        │   └── unsplash_beacon.js        # Usage analytics beacon
        └── lib/                           # Unsplash SDK or dependencies
```

## Models

### `ir.attachment` (Extension)

**File:** `models/ir_attachment.py`

The `IrAttachment` model is extended to bypass attachment rights checks when the attachment represents an Unsplash image. Normally, Odoo restricts the "URL + binary type" combination (a common attack vector for serving malicious files through the attachment system). Unsplash images use the `/unsplash/` URL path, which must be explicitly allowed.

**Key Method:**

```python
def _can_bypass_rights_on_media_dialog(self, **attachment_data):
    # Allows /unsplash/ URL + binary type combination that is normally forbidden
    forbidden = 'url' in attachment_data and attachment_data.get('type', 'binary') == 'binary'
    if forbidden and attachment_data['url'].startswith('/unsplash/'):
        return True
    return super()._can_bypass_rights_on_media_dialog(**attachment_data)
```

This method is called by `_check_serving_attachments` to determine whether a given attachment record can be served. By returning `True` for `/unsplash/` URLs, Unsplash images are served correctly even when the record otherwise would be blocked.

### `ir.qweb.field.image` (Extension)

**File:** `models/ir_qweb_fields.py`

The `IrQwebFieldImage` abstract model extends the QWeb image field serializer to handle Unsplash image URLs during HTML field conversion (e.g., when saving a page or email template that contains Unsplash images back to the database).

```python
class IrQwebFieldImage(models.AbstractModel):
    _inherit = 'ir.qweb.field.image'

    @api.model
    def from_html(self, model, field, element):
        # If the img src points to /unsplash/, look up the corresponding
        # ir.attachment record and return its binary data
        if element.find('.//img') is None:
            return False
        url = element.find('.//img').get('src')
        url_object = urls.url_parse(url)

        if url_object.path.startswith('/unsplash/'):
            res_id = element.get('data-oe-id')
            if res_id:
                res_id = int(res_id)
                res_model = model._name
                attachment = self.env['ir.attachment'].search([
                    '&', '|', '&',
                    ('res_model', '=', res_model),
                    ('res_id', '=', res_id),
                    ('public', '=', True),
                    ('url', '=', url_object.path),
                ], limit=1)
                return attachment.datas

        return super().from_html(model, field, element)
```

**Why this matters:** When a user inserts an Unsplash image into a website page or mass mailing, Odoo stores the image as an `ir.attachment` with a `/unsplash/` URL. The `from_html` override ensures that when Odoo serializes the HTML field (e.g., to save it), it can properly locate and store the binary data for Unsplash images.

### `res.config.settings` (Extension)

**File:** `models/res_config_settings.py`

Stores Unsplash API credentials as `ir.config_parameter` values:

| Field | Config Parameter | Description |
|-------|-----------------|--------------|
| `unsplash_access_key` | `unsplash.access_key` | Unsplash API Access Key |
| `unsplash_app_id` | `unsplash.app_id` | Unsplash Application ID |

These are stored via `config_parameter=` on the field definition, which writes directly to `ir.config_parameter` without needing a separate `set_values()` method.

**Configuration path:** `Settings > General Settings > Integrations > Unsplash`

To obtain credentials, register an application at [unsplash.com/developers](https://unsplash.com/developers). The Access Key is used for API requests; the Application ID identifies the application in API usage tracking.

### `res.users` (Extension)

**File:** `models/res_users.py`

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    def _can_manage_unsplash_settings(self):
        self.ensure_one()
        # Returns True for ERP managers OR website restricted editors
        return (self.sudo().has_group('base.group_erp_manager')
                or self.sudo().has_group('website.group_website_restricted_editor'))
```

This method checks whether the current user can manage Unsplash settings. Note the comment about the module dependency ordering: `website` does not depend on `web_unsplash`, so the check cannot be placed in the website module directly. This extension ensures both ERP managers and website editors can configure Unsplash.

## Frontend Architecture

### Unsplash Service (`unsplash_service.js`)

The frontend service wraps the Unsplash REST API:

| Endpoint | Purpose |
|---------|---------|
| `GET /search/photos` | Search for images by keyword |
| `GET /photos/:id` | Get details of a specific photo |
| `GET /users/:username` | Get photographer profile |

The service handles:
- **Rate limiting** via the Unsplash API quota
- **Authentication** using the Access Key from settings
- **Pagination** for search results
- **Attribution tracking** to comply with Unsplash license requirements

### Media Dialog Integration

When a user opens the image picker in the HTML editor, the Unsplash tab appears as a search interface. The flow is:

1. User types a search query in the Unsplash tab
2. `unsplash_service.js` calls the Unsplash API with the access key
3. Results are displayed as thumbnails
4. User clicks an image to insert it
5. An `ir.attachment` record is created with:
   - `type = 'url'`
   - `url = '/unsplash/<photo_id>'`
   - `public = True`
   - `res_model`, `res_id` pointing to the parent record
6. The image is rendered from the Unsplash CDN URL

### Unsplash Beacon (`unsplash_beacon.js`)

Tracks Unsplash image usage for attribution purposes. Unsplash requires that applications track which photos are used and ensure proper attribution. The beacon sends usage events to Odoo's analytics pipeline (or directly to Unsplash, depending on configuration).

### Error Handling (`unsplash_error/`)

Handles various failure scenarios:
- Invalid or expired Access Key
- Rate limit exceeded (Unsplash has a request-per-hour limit)
- Network failures
- Malformed API responses

## Configuration

### Obtaining Unsplash Credentials

1. Go to [unsplash.com/developers](https://unsplash.com/developers)
2. Create a new application
3. Note the **Access Key** and **Application ID**
4. In Odoo, go to **Settings > General Settings > Integrations > Unsplash**
5. Enter the Access Key and Application ID

### Rate Limits

Unsplash API has rate limits that vary by plan:

| Plan | Requests per hour | Demo limit |
|------|-------------------|------------|
| Free (Demo) | 50 | 50 requests/hour |
| Production | 5,000+ | Varies by plan |

If rate limits are exceeded, the Unsplash tab shows an error message and falls back to local uploaded images.

## Image Storage Strategy

The module uses a **CDN-first, attachment-second** strategy:

| Aspect | Behavior |
|--------|----------|
| **Display** | Images are served directly from `images.unsplash.com` CDN |
| **Storage** | Only the URL (`/unsplash/<id>`) and metadata are stored in `ir.attachment` |
| **Attribution** | The `ir.attachment` record includes the photographer name/URL |
| **Offline** | If Unsplash is unreachable, images fail to load (no local fallback) |
| **Backup** | `ir_qweb_field_image.from_html()` can extract binary data if available |

This approach keeps Odoo's storage minimal but means Unsplash images require internet connectivity to display.

## Security Considerations

1. **URL validation**: Only `/unsplash/` paths bypass the media dialog rights check
2. **Access key exposure**: The Access Key is stored as `ir.config_parameter` and visible in settings (not sensitive in the same way as passwords)
3. **CSRF**: The Unsplash API itself handles OAuth-style authentication; no additional CSRF tokens are needed for read operations
4. **Attachment serving**: Unsplash attachments are served as `public=True` records, meaning they can be accessed without authentication

## Related

- [Modules/html_editor](html_editor.md) — Core rich text editor with media dialog
- [Modules/website](website.md) — Website builder, primary consumer of Unsplash images
- [Modules/mass_mailing](mass_mailing.md) — Email editor also uses the media dialog
- [Modules/web_unsplash](../Tools/Unsplash%20Image%20Integration.md) — (if custom doc exists)

## Image Insertion Workflow

Understanding the complete flow from search to display helps when debugging Unsplash integration issues.

### Step 1: User Opens Media Dialog

When a user clicks the image icon in the HTML editor, Odoo loads the media dialog component. The Unsplash tab is registered as one of the available tabs alongside:
- **Uploaded images**: From the ir.attachment gallery
- **Webcam** (if supported): Direct capture
- **Unsplash**: Search and browse free images
- **Stock Images** (in Enterprise): Stock photo integration

The Unsplash tab lazily loads — it only initializes the Unsplash API connection when the tab is first selected, reducing initial page load time.

### Step 2: Search and Browse

```javascript
// Simplified search flow in unsplash_service.js
async searchUnsplash(query, page = 1, perPage = 30) {
    const accessKey = this.getAccessKey();
    const url = `https://api.unsplash.com/search/photos?query=${query}&page=${page}&per_page=${perPage}`;

    const response = await fetch(url, {
        headers: {
            'Authorization': `Client-ID ${accessKey}`,
            'Accept-Version': 'v1'
        }
    });

    const data = await response.json();
    return {
        results: data.results.map(this.formatPhoto),
        total: data.total,
        total_pages: data.total_pages
    };
}
```

Each photo in the search result includes:
- **ID**: Unsplash's unique identifier
- **URLs**: Thumbnail, small, regular, full, raw resolution URLs
- **User**: Photographer's name and profile link
- **Links**: Download link, location, etc.

### Step 3: Attachment Record Creation

When a user selects an image, an `ir.attachment` record is created:

```python
# ir.attachment record created on image selection
{
    'name': f'Unsplash - {photo_id}',
    'type': 'url',                    # Not 'binary' — it's a CDN URL
    'url': f'/unsplash/{photo_id}',   # Internal URL path
    'mimetype': 'image/jpeg',
    'public': True,                   # Accessible without login
    'res_model': 'ir.ui.view',        # Parent model (e.g., the page)
    'res_id': view_id,                # Parent record ID
    # Binary data may be stored via ir_qweb_field_image.from_html()
}
```

The key insight is `type = 'url'` with a `/unsplash/` path. This distinguishes Unsplash attachments from regular URL attachments and enables the special rights bypass in `_can_bypass_rights_on_media_dialog()`.

### Step 4: Image Rendering

When a page containing a Unsplash image is rendered, the template uses the standard QWeb image field rendering:

```xml
<img t-att-src="attachment.url" alt="..."/>
```

The Odoo asset serving system recognizes `/unsplash/` URLs and generates the appropriate CDN URL (e.g., `https://images.unsplash.com/photo-1234567890?w=800`) based on the attachment's metadata.

## Attachment Storage Decisions

The choice to store only the URL (not the binary) has important implications:

| Aspect | CDN Strategy (Unsplash) | Downloaded Strategy |
|--------|------------------------|---------------------|
| **Odoo storage** | Minimal (URL only) | Large (full image per use) |
| **Display speed** | Fast (Unsplash CDN) | Depends on Odoo server |
| **Offline mode** | Not available | Available |
| **Image customization** | Limited (Unsplash parameters) | Full control |
| **Attribution** | Auto via Unsplash API | Manual |
| **Bandwidth cost** | Pushed to Unsplash | Odoo's server |
| **Data residency** | US (Unsplash servers) | Odoo database region |

For most use cases, the CDN strategy is optimal. For air-gapped or offline deployments, images would need to be downloaded and stored as binary attachments instead.

## Frontend Services Detail

### `unsplash_service.js` API

The Unsplash service provides a clean JavaScript API to the frontend:

```javascript
class UnsplashService {
    constructor(accessKey, appId) {
        this.accessKey = accessKey;
        this.appId = appId;
    }

    async search(query, page, perPage) { /* ... */ }
    async getPhoto(id) { /* ... */ }
    async getUserPhotos(username) { /* ... */ }
    async trackDownload(photoId) { /* Required by Unsplash API guidelines */ }
}
```

**Attribution tracking**: The Unsplash API license requires tracking when photos are used. The `trackDownload()` method calls Unsplash's download tracking endpoint whenever a user inserts an image.

### Error Handling

The Unsplash error module handles several failure scenarios:

| Error Type | Cause | User Experience |
|------------|-------|----------------|
| `invalid_access_key` | Wrong or expired Access Key | "Invalid Unsplash credentials" |
| `rate_limit_exceeded` | Too many requests | "Unsplash rate limit reached. Try again later." |
| `network_error` | No internet / timeout | "Could not connect to Unsplash" |
| `photo_not_found` | Deleted Unsplash photo | Broken image placeholder |

The media dialog shows a graceful error state with the option to fall back to uploaded images.

## Comparing Image Sources in Odoo

Odoo supports multiple image sources in the media dialog:

| Source | Storage | Attribution | License |
|--------|---------|------------|---------|
| **Uploaded** | Odoo filestore (`ir.attachment` as binary) | None | Internal |
| **Unsplash** | Unsplash CDN | Auto via API | Unsplash License (free) |
| **Stock (EE)** | Stock provider CDN | Per-provider | Per-provider |
| **Google Images (legacy)** | Cached in filestore | None | Public domain |

The `web_unsplash` module only handles Unsplash. Other sources are managed by their respective modules or the base `ir.attachment` system.
