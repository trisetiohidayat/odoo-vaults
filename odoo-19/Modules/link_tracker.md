# Link Tracker (`link_tracker`)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `link_tracker` |
| **Category** | Marketing |
| **Depends** | `utm`, `mail` |
| **Data** | `views/link_tracker_views.xml`, `views/utm_campaign_views.xml`, `security/ir.model.access.csv` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Odoo Version** | 19.0 |

## Purpose

The Link Tracker module shortens URLs and tracks clicks with full UTM parameter integration. It enables marketing teams to:

1. **Shorten URLs** for cleaner emails and documents
2. **Track clicks** with detailed analytics (IP, country, timestamp)
3. **Maintain UTM parameters** through redirects
4. **Analyze campaign performance** by linking clicks to UTM campaigns

---

## Architecture Overview

```
Original URL (https://example.com/product)
    -> Create link_tracker record
Short URL (https://your-odoo.com/r/abc123)
    -> User clicks
link.tracker.click record created
    -> Redirect to
Redirected URL with UTM params
(https://example.com/product?utm_source=newsletter&utm_medium=email&utm_campaign=q3)
```

The module acts as a URL proxy layer: every click through a short URL is recorded before a 301 redirect sends the user to the final destination with UTM parameters appended.

---

## Module Structure

```
link_tracker/
├── __manifest__.py
├── __init__.py
├── controller/                  # Note: singular, not "controllers"
│   ├── __init__.py
│   └── main.py                 # /r/<code> redirect controller
├── models/
│   ├── __init__.py
│   ├── link_tracker.py         # link.tracker, link.tracker.code, link.tracker.click
│   ├── utm.py                  # UtmCampaign.click_count extension
│   └── mail_render_mixin.py    # _shorten_links() override
├── views/
│   ├── link_tracker_views.xml   # Tree, form, graph, search for all 3 models
│   └── utm_campaign_views.xml   # Injects click_count button into utm.campaign
├── security/
│   └── ir.model.access.csv
├── tools/
│   ├── __init__.py
│   └── html.py                 # find_links_with_urls_and_labels()
└── tests/
    ├── test_link_tracker.py
    ├── test_mail_render_mixin.py
    └── test_tracker_http_requests.py
```

---

## Models

### 1. `link.tracker`

Main model for tracked URLs. Inherits `utm.mixin` for campaign attribution.

```python
class LinkTracker(models.Model):
    _name = 'link.tracker'
    _rec_name = 'short_url'          # Display name in related records
    _description = "Link Tracker"
    _order = "count DESC"           # Default ordering: busiest links first
    _inherit = ["utm.mixin"]         # campaign_id, source_id, medium_id
```

#### Fields

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `url` | Char | Yes | Yes | Target URL to redirect to (validated, must not start with `?` or `#`) |
| `code` | Char | No | No | Short URL code. Computed from `link_code_ids`, writable via inverse |
| `short_url` | Char | No | No | Full short URL, e.g. `https://odoo.com/r/abc123` (computed) |
| `redirected_url` | Char | No | No | Final URL with UTM params appended (computed) |
| `short_url_host` | Char | No | No | Base short URL host, e.g. `https://odoo.com/r/` (computed) |
| `absolute_url` | Char | No | No | URL with scheme resolved for scheme-relative URLs (computed) |
| `title` | Char | No | Yes | Page title, auto-fetched from Open Graph `og:title` via link preview |
| `label` | Char | No | Yes | Button/link label for human identification (part of uniqueness key) |
| `count` | Integer | No | Yes | Total click count, stored for fast sorting (computed, `store=True`) |
| `campaign_id` | Many2one | No | Yes | UTM campaign (`utm.campaign`, `ondelete='set null'`) |
| `medium_id` | Many2one | No | Yes | UTM medium (`utm.medium`, `ondelete='set null'`) |
| `source_id` | Many2one | No | Yes | UTM source (`utm.source`, `ondelete='set null'`) |
| `link_code_ids` | One2many | No | Yes | `link.tracker.code` records (cascade delete) |
| `link_click_ids` | One2many | No | Yes | `link.tracker.click` records (cascade delete) |

##### `_rec_name = 'short_url'`

The display name of a `link.tracker` record is its `short_url` (e.g. `https://odoo.com/r/abc123`). This is used when the model appears as a Many2one target elsewhere (e.g. in click logs).

##### UTM Fields with `ondelete='set null'`

Unlike the base `utm.mixin` default, these fields explicitly use `ondelete='set null'`. If a campaign, medium, or source is deleted, the link tracker is preserved with `campaign_id = False` rather than cascading to delete the tracker. This is intentional: a tracker should not be destroyed just because its UTM reference was archived.

#### Key Computed Fields

##### `short_url` -- The Tracked URL

```python
@api.depends('code')
def _compute_short_url(self):
    for tracker in self:
        try:
            tracker.short_url = tools.urls.urljoin(
                tracker.short_url_host or '', tracker.code or ''
            )
        except ValueError:
            raise UserError(self.env._("Please enter valid short URL code."))
```

Format: `{base_url}/r/{code}`

The `try/except ValueError` guard handles cases where `short_url_host` contains an invalid URL (e.g. a malformed config parameter value).

##### `code` -- Computed with Inverse

The `code` field has a two-way binding through `link.tracker.code`:

```python
def _compute_code(self):
    for tracker in self:
        record = self.env['link.tracker.code'].search(
            [('link_id', 'in', tracker.ids)],
            limit=1, order='id DESC'
        )
        tracker.code = record.code

def _inverse_code(self):
    self.ensure_one()
    if not self.code:
        return
    record = self.env['link.tracker.code'].search(
        [('link_id', '=', self.id)], limit=1, order='id DESC'
    )
    if record:
        record.code = self.code
```

`order='id DESC'` means the most recently created code is used. This allows re-generating the short code: writing to `code` updates the existing `link.tracker.code` record rather than creating duplicates.

##### `redirected_url` -- UTM Parameter Injection

```python
@api.depends('url')
def _compute_redirected_url(self):
    no_external_tracking = self.env['ir.config_parameter'].sudo().get_param(
        'link_tracker.no_external_tracking'
    )

    for tracker in self:
        base_domain = urls.url_parse(tracker.get_base_url()).netloc
        parsed = urls.url_parse(tracker.url)

        # Skip UTM injection for external domains if external tracking is disabled
        if no_external_tracking and parsed.netloc and parsed.netloc != base_domain:
            tracker.redirected_url = parsed.to_url()
            continue

        # Append UTM parameters only for fields that are set
        query = parsed.decode_query()
        for key, field_name, _cook in self.env['utm.mixin'].tracking_fields():
            field = self._fields[field_name]
            attr = tracker[field_name]
            if field.type == 'many2one':
                attr = attr.name        # Use the display name of the record
            if attr:
                query[key] = attr

        query = urls.url_encode(query)
        # '...' is detected as malicious by some nginx configs
        query = query.replace('...', '%2E%2E%2E')
        tracker.redirected_url = parsed.replace(query=query).to_url()
```

**L4 Key behaviors:**
- Reads `link_tracker.no_external_tracking` system parameter (sudo access required)
- Checks `parsed.netloc` -- if the URL has no domain (e.g. `/shop`), it is always treated as local
- For `many2one` UTM fields (campaign, medium, source), uses `attr.name` -- the display name string, not the ID
- The `...` encoding fix: ellipsis characters in query strings are percent-encoded to avoid nginx malicious-traffic detection rules

##### `count` -- Stored Click Counter

```python
@api.depends('link_click_ids.link_id')
def _compute_count(self):
    clicks_data = self.env['link.tracker.click']._read_group(
        [('link_id', 'in', self.ids)],
        ['link_id'],
        ['__count'],
    )
    mapped_data = {link.id: count for link, count in clicks_data}
    for tracker in self:
        tracker.count = mapped_data.get(tracker.id, 0)
```

`store=True` makes this a **stored computed field**. The count is materialized in the `link_tracker` table so that `_order = "count DESC"` sorting is fast without joining the click table.

#### Creation Flow -- `create()`

```python
@api.model_create_multi
def create(self, vals_list):
    vals_list = [vals.copy() for vals in vals_list]   # Defensive copy
    for vals in vals_list:
        # 1. URL presence validation
        if 'url' not in vals:
            raise ValueError(_('Creating a Link Tracker without URL is not possible'))

        # 2. Reject query-string-only or fragment-only URLs
        if vals['url'].startswith(('?', '#')):
            raise UserError(_(""%s" is not a valid link, links cannot redirect to the current page.", vals['url']))

        # 3. Normalize and validate URL (prepends http:// if missing, rejects invalid)
        vals['url'] = validate_url(vals['url'])

        # 4. Auto-fetch Open Graph title if not provided
        if not vals.get('title'):
            vals['title'] = self._get_title_from_url(vals['url'])

        # 5. Block UTM cookie inheritance
        for (__, fname, __) in self.env['utm.mixin'].tracking_fields():
            if fname not in vals:
                vals[fname] = False

    links = super().create(vals_list)

    # 6. Generate and store random short codes
    link_tracker_codes = self.env['link.tracker.code']._get_random_code_strings(len(vals_list))
    self.env['link.tracker.code'].sudo().create([
        {'code': code, 'link_id': link.id}
        for link, code in zip(links, link_tracker_codes)
    ])

    return links
```

**L4 Critical design decisions:**

1. **Defensive `copy()`**: Each dict in `vals_list` is shallow-copied so mutations don't leak between batch records.
2. **URL rejection (`?` or `#` prefix)**: These would redirect to "the current page" which is meaningless.
3. **`validate_url()`** (from `odoo.tools.mail`): Normalizes URLs by prepending `http://` if no scheme is present.
4. **Title auto-fetch via `link_preview`**: Calls `odoo.addons.mail.tools.link_preview.get_link_preview_from_url()`. Makes an outbound HTTP HEAD/GET request to extract `og:title`. Falls back to the raw URL if unreachable.
5. **UTM cookie blocking**: The explicit `vals[fname] = False` assignment overrides `utm.mixin` defaults that might read from HTTP cookie values.

#### `search_or_create()` -- Batch Deduplication

```python
@api.model
def search_or_create(self, vals_list):
    """Get existing or newly created records matching vals_list items in preserved order supporting duplicates."""
```

This method is the primary integration point for `mass_mailing` and other modules. It:
- Deduplicates links by `(url, campaign_id, medium_id, source_id, label)` key
- Returns existing trackers if already present
- Creates new trackers only when needed
- Preserves input order in the returned recordset (important for mass mailing where each link position matters)
- Handles duplicates in the input list (e.g., the same URL 5 times in one email body maps to 5 positions, all pointing to the same tracker)

**L4 -- Order preservation pattern**: The implementation uses `seen_keys.add(key)` inside the comprehension to both check and add in a single operation, preserving insertion order for deduplicated results.

#### Uniqueness Constraint -- `_check_unicity()`

```python
LINK_TRACKER_UNIQUE_FIELDS = ('url', 'campaign_id', 'medium_id', 'source_id', 'label')

@api.constrains(*LINK_TRACKER_UNIQUE_FIELDS)
def _check_unicity(self):
```

Uses `Domain.OR()` and `Domain.AND()` for portable domain construction. The constraint handles the special case where `label` can be `False` or `''` (both treated as equivalent).

**L4 -- Why not a SQL UNIQUE constraint?** Because `NULL != NULL` in SQL, making it impossible to create a true partial unique index for "label can be either False or empty string". The Python-level constraint handles this correctly.

---

### 2. `link.tracker.code`

Stores the random short-code strings that map to a `link.tracker`.

```python
class LinkTrackerCode(models.Model):
    _name = 'link.tracker.code'
    _rec_name = 'code'
    _code = models.Constraint('unique( code )', 'Code must be unique.')
```

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `code` | Char | Yes | Yes | The short code string (unique) |
| `link_id` | Many2one | Yes | Yes | Parent link tracker |

**Why separate from `link.tracker`?** The code is stored separately to:
- Allow `UNIQUE` SQL constraint (cannot have two different trackers with the same code)
- Enable `link.tracker.code` to be queried independently by the HTTP controller (`/r/abc123`)
- Keep the `link.tracker` table lean (click count queries don't join into this table)

#### Code Generation -- `_get_random_code_strings()`

```python
@api.model
def _get_random_code_strings(self, n=1):
    size = LINK_TRACKER_MIN_CODE_LENGTH  # 3 characters minimum
    while True:
        code_propositions = [
            ''.join(random.choices(string.ascii_letters + string.digits, k=size))
            for __ in range(n)
        ]
        if len(set(code_propositions)) != n or self.search_count([('code', 'in', code_propositions)], limit=1):
            size += 1  # Increase length if collision detected
        else:
            return code_propositions
```

**L4 -- Collision handling**: The generator loops until it finds `n` unique codes with no existing match in the database. If `n` is large (e.g., an email with 50 links), collision probability increases, so the code length grows dynamically.

---

### 3. `link.tracker.click`

Records each click event on a tracked link.

```python
class LinkTrackerClick(models.Model):
    _name = 'link.tracker.click'
    _rec_name = "link_id"
```

| Field | Type | Description |
|-------|------|-------------|
| `link_id` | Many2one | The tracker being clicked |
| `campaign_id` | Many2one | UTM campaign (stored from `link_id`, indexed `btree_not_null`) |
| `ip` | Char | Clicker's IP address |
| `country_id` | Many2one `res.country` | Geolocated country from IP |

**Why store `campaign_id` on click?** Enables grouping clicks by campaign directly on `link.tracker.click` without joining through `link_id`. The `campaign_id` field has `index='btree_not_null'` to optimize campaign-level click aggregation queries.

#### Click Recording -- `add_click()`

```python
@api.model
def add_click(self, code, **route_values):
    tracker_code = self.env['link.tracker.code'].search([('code', '=', code)])
    if not tracker_code:
        return None
    route_values['link_id'] = tracker_code.link_id.id
    click_values = self._prepare_click_values_from_route(**route_values)
    return self.create(click_values)
```

**L4 -- Performance**: This is the hot path (executed on every click). The code lookup is indexed (`UNIQUE` constraint on `code`). The `create()` call triggers the stored `count` recomputation on `link.tracker` via `@api.depends('link_click_ids.link_id')`.

---

## HTTP Controller

**File:** `~/odoo/odoo19/odoo/addons/link_tracker/controller/main.py`

```python
class LinkTracker(http.Controller):

    @http.route('/r/<string:code>', type='http', auth='public', website=True)
    def full_url_redirect(self, code, **post):
        if not request.env['ir.http'].is_a_bot():
            request.env['link.tracker.click'].sudo().add_click(
                code,
                ip=request.httprequest.remote_addr,
                country_code=request.geoip.country_code,
            )
        redirect_url = request.env['link.tracker'].get_url_from_code(code)
        if not redirect_url:
            raise NotFound()
        return request.redirect(redirect_url, code=301, local=False)
```

**L4 Critical design decisions:**

1. **`auth='public'`**: The redirect endpoint must be accessible to anyone, including non-logged-in users. This is intentional -- click tracking works for all recipients.
2. **`website=True`**: Enables website routing context (required for `geoip` and `get_base_url()`).
3. **`is_a_bot()` check**: Bots (crawlers, indexers) do not create click records. This prevents inflating click counts with crawler traffic.
4. **`sudo()` for click creation**: Click recording runs with elevated privileges to bypass record rules. Click tracking should always work regardless of user permissions.
5. **`local=False` on redirect**: Forces an external redirect (HTTP 301) rather than an internal Odoo reroute. This is important for external URLs.
6. **`link_tracker.get_url_from_code(code)`**: Two-step lookup (code -> `link.tracker.code` -> `link.tracker` -> `redirected_url`) ensures proper UTM injection through the computed field.

---

## Link Shortening in Mail Templates -- `mail.render.mixin`

**File:** `~/odoo/odoo19/odoo/addons/link_tracker/models/mail_render_mixin.py`

The `mail.render.mixin` is inherited by `mail.mail`, `mail.template`, and `mass_mailing`. The module overrides `_shorten_links()` and `_shorten_links_text()` to automatically convert all URLs in rendered HTML/text content into tracked short URLs.

### `_shorten_links()` -- HTML Content

```python
@api.model
def _shorten_links(self, html, link_tracker_vals, blacklist=None, base_url=None):
    if not html or is_html_empty(html):
        return html

    base_url = base_url or self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    short_schema = base_url + '/r/'

    root_node = lxml.html.fromstring(html)
    link_nodes, urls_and_labels = find_links_with_urls_and_labels(
        root_node, base_url,
        skip_regex=rf'^{URL_SKIP_PROTOCOL_REGEX}',
        skip_prefix=short_schema,
        skip_list=blacklist)

    if not link_nodes:
        return html

    links_trackers = self.env['link.tracker'].search_or_create([
        dict(link_tracker_vals, **url_and_label) for url_and_label in urls_and_labels
    ])

    for node, link_tracker in zip(link_nodes, links_trackers):
        node.set("href", link_tracker.short_url)

    new_html = lxml.html.tostring(root_node, encoding="unicode", method="xml")
    if isinstance(html, markupsafe.Markup):
        new_html = markupsafe.Markup(new_html)

    return new_html
```

**L4 -- How link injection works:**
1. Parses HTML with `lxml` (preserves document structure)
2. Extracts all `<a>` tags with `href` attributes
3. Applies skip rules (already-shortened URLs, unsubscribe URLs, blacklisted paths)
4. Calls `search_or_create()` to get/create trackers in batch
5. Replaces each `href` with the `short_url`
6. Returns Markup-safe string if input was Markup-safe

**L4 -- Label extraction**: `find_links_with_urls_and_labels()` extracts a label from the link text or nested `<img>` alt for human identification in the tracker UI.

### `find_links_with_urls_and_labels()` -- HTML Parsing

**File:** `~/odoo/odoo19/odoo/addons/link_tracker/tools/html.py`

```python
def find_links_with_urls_and_labels(root_node, base_url, skip_regex=None, skip_prefix=None, skip_list=None):
    link_nodes, urls_and_labels = [], []

    for link_node in root_node.iter(tag="a"):
        original_url = link_node.get("href")
        if not original_url:
            continue
        absolute_url = base_url + original_url if original_url.startswith(('/', '?', '#')) else original_url
        # Skip matching links...
        # Extract label from link text or child elements...
        link_nodes.append(link_node)
        urls_and_labels.append({'url': absolute_url, 'label': label})

    return link_nodes, urls_and_labels
```

**Label extraction priority:**
1. Link text content (stripped, max 40 chars)
2. `<img alt="">` attribute from nested images
3. Filename from `<img src="">`
4. Empty string

**L4 -- `MAX_LABEL_LENGTH = 40`**: Labels longer than 40 characters are truncated to prevent storage bloat and maintain clean UI display.

---

## UTM Campaign Extension

```python
class UtmCampaign(models.Model):
    _inherit = 'utm.campaign'

    click_count = fields.Integer(
        string="Number of clicks generated by the campaign",
        compute="_compute_clicks_count")

    def _compute_clicks_count(self):
        click_data = self.env['link.tracker.click']._read_group(
            [('campaign_id', 'in', self.ids)],
            ['campaign_id'], ['__count'])
        mapped_data = {campaign.id: count for campaign, count in click_data}
        for campaign in self:
            campaign.click_count = mapped_data.get(campaign.id, 0)
```

This enables direct click count display on UTM campaign records without joining through `link.tracker`.

---

## Performance Considerations

### Click Recording Efficiency

The click recording path (`add_click()`) is optimized for high throughput:

1. **Single indexed query**: The code lookup uses `UNIQUE(code)` index.
2. **Minimal field write**: Only `link_id`, `ip`, and `country_id` are stored.
3. **Deferred `count` recomputation**: The `link.tracker.count` stored field is recalculated via `_compute_count()` using `_read_group()`, which is efficient (single aggregate query).
4. **No `write()` on `link.tracker`**: Click creation triggers ORM recomputation without explicit write.

### URL Validation Cost

`create()` calls `_get_title_from_url()` which makes an outbound HTTP request to fetch Open Graph metadata. This happens synchronously at tracker creation time. For mass mailing with thousands of unique links, this could be slow.

**Mitigation**: The `link_preview` module caches link previews. The `_get_title_from_url()` call uses the cached result if available.

### Batch Shortening

`_shorten_links()` uses `search_or_create()` in batch mode, minimizing database round-trips:
- One `search()` for all existing trackers
- One `create()` for all new trackers
- One loop for href replacement

---

## Security Considerations

### Link Injection in User Content

The `_shorten_links()` method processes HTML content that may contain user-submitted data (e.g., email templates). Key protections:

1. **Skip rules**: Already-shortened URLs are not re-shortened (prevents infinite redirect loops).
2. **Blacklist**: `/unsubscribe_from_list` and `/sms/` paths are excluded.
3. **Protocol validation**: Only HTTP/HTTPS links are shortened (via `URL_SKIP_PROTOCOL_REGEX`).

### No External Tracking for Internal URLs

When `link_tracker.no_external_tracking = True`:
- Internal URLs (same domain as `web.base.url`) get UTM parameters appended
- External URLs are passed through unchanged (no UTM injection)

This prevents leaking UTM parameters to third-party sites that aren't configured to handle them.

### Click Data Privacy

Click records store:
- `ip`: The clicker's IP address (GDPR implication: should be pseudonymized or logged with consent)
- `country_id`: Geolocated from IP (less granular, lower privacy risk)

**L4 -- GDPR note**: Storing IP addresses in `link.tracker.click` may require GDPR compliance measures (consent, retention limits, anonymization). The module does not implement these natively.

### URL Validation

The `validate_url()` call in `create()` and `search_or_create()`:
- Prepends `http://` if missing
- Rejects URLs with only query strings (`?foo=bar`) or fragments (`#section`)
- Rejects invalid URLs

This prevents creating trackers that would redirect to invalid destinations.

---

## Odoo 18 -> 19 Changes

### Manifest Changes

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| `version` | `1.0` | `1.1` |
| `data` | Views + security | Same (unchanged) |
| `depends` | `utm`, `mail` | Same (unchanged) |

### Code Changes in Odoo 19

1. **`_get_random_code_strings()` loop fix**: In Odoo 18, the random code generation used `while len(set(code_propositions)) != n or self.search_count(...)` which could loop indefinitely if the database was full. Odoo 19 uses a cleaner loop structure.

2. **`Domain` class for constraints**: Odoo 19 introduced the `Domain` class for portable domain construction. The `_check_unicity()` and `search_or_create()` methods use `Domain.OR()` and `Domain.AND()` for cleaner, more portable domain expressions.

3. **`is_a_bot()` check**: The HTTP controller was updated to use `request.env['ir.http'].is_a_bot()` to skip click recording for crawlers. This was potentially added in Odoo 18 or earlier and refined in Odoo 19.

4. **Werkzeug `urljoin` behavior**: Odoo 19 may have updated the Werkzeug version, affecting URL parsing behavior in `_compute_absolute_url()` and `_compute_redirected_url()`.

5. **`markupsafe.Markup` handling**: Explicit check `if isinstance(html, markupsafe.Markup)` to preserve Markup-safe strings through the shortening process.

6. **Test coverage**: Odoo 19 tests (`test_mail_render_mixin.py`, `test_tracker_http_requests.py`) cover the shortening pipeline more thoroughly than earlier versions.

---

## Related Modules

- [Modules/mail](modules/mail.md) -- Inherits `mail.render.mixin`; all outgoing emails have links automatically shortened
- `mass_mailing` -- Extensive use of `search_or_create()` for per-link tracking in email campaigns
- [Modules/utm](modules/utm.md) -- Provides UTM mixin and campaign/source/medium models
- `website_sms` -- Uses link tracking for SMS click analytics (via link tracker click records)

## Tags

#odoo #odoo19 #modules #marketing #utm #tracking #performance
