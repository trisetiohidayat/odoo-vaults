# link_tracker — URL Shortening and Click Tracking

**Module:** `link_tracker`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/link_tracker/`

---

## Overview

The `link_tracker` module provides URL shortening and click tracking for marketing and communications. It converts long URLs into short tracked URLs under the `/r/{code}` path, records each click with metadata (IP, country), aggregates clicks into a count, and integrates with UTM (campaign/medium/source) tracking to support marketing analytics.

---

## Architecture

### Model Structure

```
link.tracker              # Tracked URL container with UTM and click count
link.tracker.code         # Short code mapping to tracker record
link.tracker.click        # Individual click event records
utm.mixin                 # Inherited for campaign/medium/source tracking
mail.render.mixin         # Extended with link conversion in HTML/text bodies
mail.mail.statistics       # Extended with link click tracking
```

### File Map

| File | Purpose |
|------|---------|
| `models/link_tracker.py` | Core tracker and click models |
| `models/utm.py` | UTM mixin inheritance |
| `models/mail_render_mixin.py` | Automatic link conversion in emails |

---

## Core Models

### link.tracker

**`link.tracker`** represents a tracked URL with its short code, UTM parameters, and click statistics.

**Inheritance:** `models.Model` + `utm.mixin`
** `_name`: `link.tracker`
** `_description`: `"Link Tracker"`
** `_order`: `count DESC`
** `_rec_name`: `short_url`

#### Field Reference

**URL Configuration**

| Field | Type | Description |
|-------|------|-------------|
| `url` | `Char` | Target/original URL being tracked (required) |
| `absolute_url` | `Char` | Computed absolute URL (prepends base URL if `url` is relative) |
| `short_url` | `Char` | Full short URL: `{base_url}/r/{code}` |
| `redirected_url` | `Char` | Computed redirect URL with UTM parameters appended |
| `short_url_host` | `Char` | Base for short URL: `{base_url}/r/` |
| `title` | `Char` | Page title (fetched via OpenGraph on creation) |
| `label` | `Char` | Custom button/label for this link |

**Code & Tracking**

| Field | Type | Description |
|-------|------|-------------|
| `code` | `Char` | Short code (e.g., `"aB3kL9"`). Computed from `link_tracker_code`, inverse writes back |
| `link_code_ids` | `One2many(link.tracker.code)` | The actual code record(s). A tracker can have multiple codes in edge cases |
| `link_click_ids` | `One2many(link.tracker.click)` | All click events for this tracker |
| `count` | `Integer` | Total click count. Computed from grouped `link_click_ids` |

**UTM / Marketing (from `utm.mixin`)**

| Field | Type | Description |
|-------|------|-------------|
| `campaign_id` | `Many2one(utm.campaign)` | Marketing campaign |
| `medium_id` | `Many2one(utm.medium)` | Marketing medium (email, social, etc.) |
| `source_id` | `Many2one(utm.source)` | Marketing source (google, facebook, etc.) |

---

#### Unique Constraint

Link trackers are unique per combination of:
```python
LINK_TRACKER_UNIQUE_FIELDS = ('url', 'campaign_id', 'medium_id', 'source_id', 'label')
```

The `_check_unicity()` constraint is enforced via ORM (not SQL) because it must handle null values correctly.

---

#### Key Methods

**`create(vals_list)`**

1. Validates URL (must not start with `?` or `#`)
2. Validates URL via `validate_url()`
3. Fetches `og_title` via OpenGraph lookup if `title` not provided
4. Strips any pre-existing UTM values from vals (forces cookie-based UTM capture)
5. Creates tracker records
6. Generates random short codes via `link.tracker.code._get_random_code_strings()`

```python
link_tracker_codes = self.env['link.tracker.code']._get_random_code_strings(len(vals_list))
self.env['link.tracker.code'].sudo().create([
    {'code': code, 'link_id': link.id}
    for link, code in zip(links, link_tracker_codes)
])
```

**`search_or_create(vals_list)`**

Bulk upsert operation — finds existing trackers matching the unique fields or creates new ones:
1. For each entry in `vals_list`, generates a unique key from the LINK_TRACKER_UNIQUE_FIELDS
2. Searches for existing trackers matching all keys
3. Creates missing trackers
4. Returns records in input order

**`get_url_from_code(code)`**

Looks up a short code and returns the `redirected_url`:
```python
def get_url_from_code(self, code):
    code_rec = self.env['link.tracker.code'].sudo().search([('code', '=', code)])
    if not code_rec:
        return None
    return code_rec.link_id.redirected_url
```

**`_compute_redirected_url()`**

Builds the final redirect URL:
1. If `link_tracker.no_external_tracking` config is set AND the target is external → return plain URL (no UTM params appended for external sites)
2. Otherwise → append UTM parameters as query string: `?utm_source=...&utm_medium=...&utm_campaign=...`

**`_get_title_from_url(url)`**

Calls `link_preview.get_link_preview_from_url()` to fetch OpenGraph `og_title`. Falls back to returning the URL itself.

---

### link.tracker.code

**`link.tracker.code`** maps short alphanumeric codes to tracker records.

**Inheritance:** `models.Model`
** `_name`: `link.tracker.code`
** `_rec_name`: `code`

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `code` | `Char` | The short code (required, unique) |
| `link_id` | `Many2one(link.tracker)` | The linked tracker (cascade delete) |

#### SQL Constraints

```python
('code', 'unique( code )', 'Code must be unique.')
```

#### Code Generation

**`_get_random_code_strings(n)`**

Generates `n` unique random alphanumeric codes:
```python
def _get_random_code_strings(self, n=1):
    size = LINK_TRACKER_MIN_CODE_LENGTH  # 3
    while True:
        code_propositions = [
            ''.join(random.choices(string.ascii_letters + string.digits, k=size))
            for __ in range(n)
        ]
        # Retry with longer codes if collision detected
        if len(set(code_propositions)) != n or self.search_count([('code', 'in', code_propositions)]):
            size += 1
        else:
            return code_propositions
```

---

### link.tracker.click

**`link.tracker.click`** records individual click events.

**Inheritance:** `models.Model`
** `_name`: `link.tracker.click`
** `_rec_name`: `link_id`

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `link_id` | `Many2one(link.tracker)` | Tracked link (indexed, cascade delete) |
| `campaign_id` | `Many2one(utm.campaign)` | Stored from `link_id.campaign_id` for efficient grouping |
| `ip` | `Char` | Clicker's IP address |
| `country_id` | `Many2one(res.country)` | Clicker's country (from IP geolocation) |

#### Click Registration

**`add_click(code, **route_values)`**

The primary API for recording a click:
```python
def add_click(self, code, **route_values):
    tracker_code = self.env['link.tracker.code'].search([('code', '=', code)])
    if not tracker_code:
        return None

    click_values = self._prepare_click_values_from_route(**route_values)
    click_values['link_id'] = tracker_code.link_id.id

    return self.create(click_values)
```

The click is created from the HTTP route parameters (`ip`, `country_code`, etc.) passed by the web controller.

---

## Redirect Flow

```
User visits /r/{code}
         |
         v
link_tracker controller
  - looks up code in link_tracker_code
  - gets link_tracker record
  - creates link_tracker_click record
  - returns 302 redirect to redirected_url
  (with UTM params appended)
```

---

## UTM Integration

The tracker inherits `utm.mixin` which provides `campaign_id`, `medium_id`, `source_id` fields. These are:
- Set at tracker creation time (e.g., when a marketing email is created)
- Appended to the `redirected_url` as query parameters when the user is redirected
- Also used for uniqueness (a tracker for the same URL with different campaigns = different tracker)

The `utm.mixin` provides `tracking_fields()` which lists the UTM field names and their corresponding link tracker field names.

---

## Unique Click Deduplication

The base module does NOT implement IP-based deduplication in the database. Each call to `add_click()` creates a new `link.tracker.click` record. The `count` field is the total number of click records.

Unique click counting is typically handled at the reporting/analytics layer (e.g., grouping by IP per day).

---

## Key Design Decisions

1. **Short code stored separately:** The code is stored in `link.tracker.code` (not on `link.tracker` itself) to support multiple codes pointing to the same tracker (e.g., for A/B testing or migration scenarios). The `code` field on `link.tracker` is a computed/inverse field that syncs with the most recent code record.

2. **Signed UTM handling:** When creating a tracker, pre-existing UTM fields are stripped from the vals (`vals[fname] = False`). This prevents existing UTM cookies from being "baked in" to stored trackers and distorting attribution. Fresh UTM parameters are appended at redirect time.

3. **`search_or_create` preserves order:** The bulk operation returns records in the same order as the input `vals_list`, enabling efficient batch processing while maintaining input/output correspondence.

4. **`...` encoding:** The `redirected_url` replaces `...` in query strings with `%2E%2E%2E` because some nginx configurations flag `...` as a malicious pattern. This is a defensive encoding measure.

5. **`og_title` fallback:** When `title` is not explicitly provided, Odoo attempts to fetch it via OpenGraph from the target URL. This provides human-readable link titles in email clients without pre-fetching every URL at creation time.

6. **Campaign stored on click:** `campaign_id` is stored on `link.tracker.click` as a stored related field. This enables efficient grouping of clicks by campaign without joining through the tracker.

---

## Notes

- The module does NOT implement link conversion in sent emails directly — that is handled by `mail.render.mixin` which calls `link_tracker.convert_links()` to replace URLs in HTML/text bodies with tracked short URLs before sending.
- Click tracking via email open pixels is handled separately in `mail.mail.statistics` (the `link_tracker` extension there).
- `get_url_from_code()` is called by the web controller's redirect route. It returns the `redirected_url` (with UTM params), not the original `url`.
- The `no_external_tracking` config parameter (`link_tracker.no_external_tracking`) prevents UTM parameters from being appended when redirecting to external domains, avoiding issues with third-party sites that don't expect UTM query parameters.
