---
tags:
  - odoo
  - odoo19
  - modules
  - web-client
  - orm
  - controllers
---

# web

> The core web client module. Provides all HTTP routing, session management, ORM web APIs (`web_read`, `web_search_read`, `web_read_group`), database management, binary/file serving, menu loading, action loading, export (CSV/XLSX), and Profiling endpoints.

## Module Overview

**Category:** Hidden (auto-installed core module)
**Depends:** `base` (only explicit dependency; all other dependencies are implicit via hooks)
**Bootstrap:** `True` — translations are loaded for the login screen before a session exists
**Version:** `1.0`
**Author:** Odoo S.A.
**License:** LGPL-3

The `web` module is the monolith containing the entire server-side logic for the Odoo web client. In Odoo 19, all web-related server code is consolidated here rather than split across multiple `web_*` modules as in earlier versions. The JavaScript frontend communicates exclusively with these controllers and ORM methods.

### Asset Bundles

The module defines a large number of `ir.module.module` asset bundles consumed by the JS framework:

| Bundle | Purpose |
|---|---|
| `web.assets_backend` | Main backend JS + all views |
| `web.assets_backend_lazy` | Graph + pivot views (lazy-loaded) |
| `web.assets_web` | Backend + main entrypoint |
| `web.assets_frontend` | Public-facing website JS |
| `web.assets_frontend_minimal` | Minimal assets for public pages |
| `web.assets_frontend_lazy` | Frontend lazy bundle |
| `web.report_assets_common` | Common report SCSS |
| `web.report_assets_pdf` | PDF report reset CSS |
| `web.ace_lib` | ACE code editor library |
| `web.assets_web_dark` | Dark mode overrides |
| `web.assets_tests` | Test tours |
| `web.assets_unit_tests_setup` | Unit test framework assets |
| `web.assets_unit_tests` | Unit test files |
| `web.tests_assets` | QUnit test assets |
| `web.qunit_suite_tests` | Legacy QUnit tests |
| `web.assets_clickbot` | Clickbot automation |
| `web.chartjs_lib` | Chart.js + luxon adapter |
| `web.fullcalendar_lib` | FullCalendar library |

### Data Files

```
data/ir_attachment.xml          # image_placeholder attachment
data/report_layout.xml          # report layout ir.attachment records
security/ir.model.access.csv    # ACL for web models
security/web_security.xml       # ir.rule for embedded actions
views/webclient_templates.xml   # webclient_bootstrap, login templates
views/report_templates.xml      # Report rendering templates
views/base_document_layout_views.xml
views/partner_view.xml
views/speedscope_template.xml
views/memory_template.xml
views/speedscope_config_wizard.xml
views/neutralize_views.xml
views/ir_ui_view_views.xml
```

---

## Models

### `models/ir_model.py` — `ir.model` Extension

```python
class IrModel(models.Model):
    _inherit = "ir.model"
```

Extends `ir.model` with methods used by the model selector UI component (used in Studio, custom filters, etc.).

#### `display_name_for(models)`

```python
@api.model
def display_name_for(self, models: list[str]) -> list[dict]
```

Returns display names for a list of technical model names that the current user can access. Models the user cannot access are returned with the raw `model` string as `display_name` — this prevents enumeration attacks.

**L2 — Returns:** `[{"model": str, "display_name": str}, ...]`

**L3 — Logic:** For each model, calls `_is_valid_for_model_selector`. Accessible models are batch-queried via `_display_name_for` in a single `sudo().search_read()` call. Inaccessible ones are returned as-is without revealing existence.

#### `_is_valid_for_model_selector(model)`

```python
@api.model
def _is_valid_for_model_selector(model: str) -> bool
```

Internal predicate. Returns `True` only if ALL of:
- `self.env.user._is_internal()` — user is an employee (not public/portal)
- `self.env.get(model)` resolves to a model — model exists in registry
- `model.has_access("read")` — user has read permission
- `not model._transient` — not a transient model
- `not model._abstract` — not an abstract model

#### `get_available_models()`

```python
@api.model
def get_available_models() -> list[dict]
```

Returns ALL models the current user can access, with display names. Scans `self.pool` (the entire model registry). Called only once per session boot.

#### `_get_definitions(model_names)`

```python
def _get_definitions(self, model_names: list[str]) -> dict
```

Returns field definitions for a set of models, used by the webclient's model introspection system. The output structure per model:

```python
{
    model_name: {
        'description': model._description,
        'fields': {
            fname: field_data  # from fields_get with many attributes
        },
        'inherit': [model_names inherited from],
        'order': model._order,
        'parent_name': model._parent_name,
        'rec_name': model._rec_name,
    }
}
```

**L3 — Filtering logic:**
- Relational fields (many2one, many2many, one2many) are included only if the related model's name is also in `model_names` — prevents leaking access to models the caller didn't request
- `selectable: True` filter excludes system/technical fields
- Related fields are filtered out if their first segment isn't in `fields_data_by_fname` (only included if fully traversable)
- Inverse fields are computed via `model.pool.field_inverses` and filtered by access rights

**L4 — Performance:** Executes one `fields_get()` per model, one `search_read()` for names, and inverse-field lookups via `field_inverses`. For large `model_names` lists, this can be expensive — callers should limit to only needed models.

---

### `models/ir_http.py` — `ir.http` Extension

```python
class IrHttp(models.Model):
    _inherit = 'ir.http'
```

The central HTTP routing mixin. All routes defined in the web module dispatch through this class's hooks.

#### `bots` — Class Attribute

```python
bots = ["bot", "crawl", "slurp", "spider", "curl", "wget",
        "facebookexternalhit", "whatsapp", "trendsmapresolver",
        "pinterest", "instagram", "google-pagerenderer", "preview"]
```

Used by `is_a_bot()` to detect crawler user agents. Simple substring matching — not regex-based for performance.

#### `is_a_bot()`

```python
@classmethod
def is_a_bot(cls) -> bool
```

Checks `request.httprequest.user_agent.string` against the `bots` list. Used to conditionally suppress features (e.g., session tracking, CAPTCHAs) for known crawlers.

**L4 — Edge case:** Substring matching means "chabot" would match "bot". Intentional for the simple use case; strict matching is not needed for this heuristic feature.

#### `_sanitize_cookies(cookies)`

```python
@classmethod
def _sanitize_cookies(cls, cookies: dict) -> None
```

Normalizes the `cids` (company IDs) cookie from comma-separated to hyphen-separated: `"1,2,3"` becomes `"1-2-3"`. Called by the parent at cookie handling time.

#### `_handle_debug()`

```python
@classmethod
def _handle_debug(cls) -> None
```

Parses the `?debug=` query parameter. Valid modes:

| Value | Effect |
|---|---|
| `''` | Disable debug |
| `'1'` | Simple debug mode |
| `'assets'` | Non-minified assets |
| `'tests'` | Load test assets |

Comma-separated combinations are supported: `?debug=assets,tests`. Truthy values not in the allowed list (e.g., `?debug=yes`) are normalized to `'1'`.

**L4 — Security:** Only explicitly whitelisted modes are accepted; arbitrary code execution via debug is prevented.

#### `session_info()`

```python
def session_info(self) -> dict
```

The primary session information payload sent to the webclient on bootstrap. Returns 30+ keys:

| Key | Type | Description |
|---|---|---|
| `uid` | `int\|False` | Current user ID |
| `is_system` | `bool` | Has `base.group_system` |
| `is_admin` | `bool` | Has admin rights |
| `is_public` | `bool` | Public user |
| `is_internal_user` | `bool` | Employee (not portal/public) |
| `user_context` | `dict` | User's lang, tz, etc. |
| `db` | `str` | Database name |
| `registry_hash` | `str` | HMAC of registry sequence (for cache busting) |
| `user_settings` | `dict` | Current user's settings formatted |
| `server_version` | `str` | Odoo version string |
| `server_version_info` | `list` | Odoo version tuple |
| `quick_login` | `bool` | From `web.quick_login` config param |
| `partner_write_date` | `str` | Partner's last write time |
| `partner_display_name` | `str` | Partner name |
| `partner_id` | `int\|None` | Partner ID |
| `web.base.url` | `str` | Base URL from config |
| `active_ids_limit` | `int` | From `web.active_ids_limit` param (default 20000) |
| `profile_session` | `str\|None` | Profiler session ID |
| `profile_collectors` | `list\|None` | Active collectors |
| `profile_params` | `dict\|None` | Profiler params |
| `max_file_upload_size` | `int` | From `web.max_file_upload_size` param |
| `home_action_id` | `int\|False` | User's action_id |
| `currencies` | `list` | All active currencies |
| `bundle_params` | `dict` | `{lang, debug?}` for asset URLs |
| `test_mode` | `bool` | Test framework enabled |
| `view_info` | `dict` | All view type metadata |
| `groups.base.group_allow_export` | `bool` | Export permission |
| `user_companies` | `dict` | Current + allowed companies |
| `disallowed_ancestor_companies` | `dict` | Companies above user's allowed hierarchy |
| `show_effect` | `bool` | Show UI animations |

**L4 — Performance implications:**
- Calls `user._get_company_ids()` (cached) and fetches those companies with `sudo()` — necessary because a user may not have direct read access to ancestor companies
- `max_file_upload_size` is read from `ir.config_parameter` on every call
- `registry_hash` changes every time the registry is rebuilt (e.g., after module install/update), causing full webclient cache invalidation

#### `get_frontend_session_info()`

```python
@api.model
def get_frontend_session_info(self) -> dict
```

Stripped-down version of `session_info()` for public/website pages. Omits `user_settings`, `view_info`, `user_companies`, `active_ids_limit`, `home_action_id`, and `groups`. Uses `is_website_user` instead of `is_public`.

---

### `models/ir_ui_view.py` — View Type Metadata

```python
class IrUiView(models.Model):
    _inherit = 'ir.ui.view'
```

Extends `ir.ui.view` to provide view-type metadata to the webclient for rendering view-switcher icons.

#### `get_view_info()`

```python
def get_view_info(self) -> dict
```

Returns metadata about all non-qweb view types:

```python
{
    'list':    {'display_name': 'List', 'icon': 'oi oi-view-list', 'multi_record': True},
    'form':    {'display_name': 'Form', 'icon': 'fa fa-address-card', 'multi_record': False},
    'graph':   {'display_name': 'Graph', 'icon': 'fa fa-area-chart', 'multi_record': True},
    'pivot':   {'display_name': 'Pivot', 'icon': 'oi oi-view-pivot', 'multi_record': True},
    'kanban':  {'display_name': 'Kanban', 'icon': 'oi oi-view-kanban', 'multi_record': True},
    'calendar':{'display_name': 'Calendar', 'icon': 'fa fa-calendar', 'multi_record': True},
    'search':  {'display_name': 'Search', 'icon': 'oi oi-search', 'multi_record': True},
}
```

**L3 — Usage:** The webclient uses this to render view type icons in the control panel and action switches, independent of whether those views are actually installed.

---

### `models/ir_ui_menu.py` — Menu Loading

```python
class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"
```

Transforms the menu tree into the JSON structure expected by the webclient.

#### `load_web_menus(debug)`

```python
def load_web_menus(self, debug: bool) -> dict
```

Loads all menus and transforms them for the webclient. Key transformations:

1. **Root menu**: special `root` entry with `id='root'`, `appID=False`, empty action
2. **App menus** (where `id == app_id`): recursively resolves the action of the first descendant that has one defined — this is what fires when clicking the app icon in the navbar
3. **Icon resolution priority**:
   - If `web_icon_data` exists: base64-encoded inline data URI
   - If `web_icon` has 3 parts (iconClass, color, backgroundColor): CSS class string
   - If `web_icon` has 2 parts (iconClass, color): icon + color with default background
   - Otherwise: fallback to `/web/static/img/default_icon_app.png`
4. **Whitespace removal**: base64 data URIs have all whitespace removed before sending

**L3 — Recursive action resolution:** Walks the tree depth-first through `children` until finding a menu with `action_id`. This ensures the app always opens to the first meaningful action, even if no action is directly on the app menu item itself.

---

### `models/models.py` — Core Web ORM API

```python
class Base(models.AbstractModel):
    _inherit = 'base'
```

The most consequential model in the module. Provides all the web-client-facing ORM methods used by the JS framework to read, search, group, and export data.

#### `web_name_search(name, specification, domain, operator, limit)`

```python
@api.model
@api.readonly
def web_name_search(self, name, specification, domain=None, operator='ilike', limit=100) -> list[dict]
```

Combines `name_search` with `web_read`. If `specification` is just `{'display_name': {}}`, returns minimal data (id + formatted display name). Otherwise calls `web_read` with the full specification.

#### `web_search_read(domain, specification, offset, limit, order, count_limit)`

```python
@api.model
@api.readonly
def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None) -> dict
```

Combines `search_fetch` + `web_read` + count. The core read method for list/kanban views. Returns `{'length': int, 'records': [...]}`.

**L4 — Count logic:** Only queries `search_count` if:
- `limit` was reached (`len(records) == limit`), AND
- `count_limit` was NOT reached (if provided), AND
- `force_search_count` context is not set

This avoids a second query in most scrolling scenarios.

#### `web_read(specification)`

```python
@api.readonly
def web_read(self, specification: dict[str, dict]) -> list[dict]
```

The central field-reading method. Takes a nested specification dict and returns fully hydrated records. Handles:

**Many2one fields:**
```python
'partner_id': {'fields': {'id': {}, 'display_name': {}}}
# Returns: {'id': 123, 'display_name': 'Camptocamp'}  (not {id: 123})
```
If the co-record doesn't exist or access is denied, returns `{'id': False, 'display_name': "You don't have access to this record"}` — prevents errors from blocking the entire read.

**One2many / Many2many fields:**
- Optional `order` key: reorders with `active_test=False`
- Optional `limit` key: only reads first N related records (for performance)
- Filters out inaccessible co-records (cache pollution guard)
- Sorts results to match original id ordering

**Reference / Many2one Reference fields:**
- Handles both `reference` type (model embedded in value dict) and `many2one_reference` (separate `model_field` on the record)
- Sets `record_values[field.model_field] = False` if the reference target doesn't exist

**Properties fields:**
- Resolves `many2one` and `many2many` property values using `web_read` on the comodel
- Other property types are passed through as-is

**L4 — NewId handling:** When reading records created in the current request but not yet flushed, `id` may be a `NewId`. The `cleanup()` function resolves `NewId.origin` so client code sees a stable identifier. Without this, newly created records would have `id: 0` in responses.

#### `web_read_group(domain, groupby, aggregates, ...)`

```python
@api.model
@api.readonly
def web_read_group(self, domain, groupby, aggregates, limit=None, offset=0, order=None, *,
                   auto_unfold=False, opening_info=None, unfold_read_specification=None,
                   unfold_read_default_limit=80, groupby_read_specification=None) -> dict
```

The primary grouped data method. Returns both groups and total count.

**Key parameters:**
- `auto_unfold`: If `True`, automatically unfolds the first 10 groups where `__fold` key is present. Typically `True` for kanban, `False` for list.
- `opening_info`: State of already-opened groups (for reload): `[{"value": raw_value, "folded": bool, "offset": int, "limit": int, "progressbar_domain": domain, "groups": [...]}]`
- `unfold_read_specification`: Fields to read when unfolding a group
- `groupby_read_specification`: Extra fields to read on the grouped-on record (for `<groupby>` leaves in list views)

**L3 — Unfolding algorithm:**
1. First-level groups are computed via `_formatted_read_group_with_length`
2. `_open_groups()` walks each group to determine which to open (respects `MAX_NUMBER_OPENED_GROUPS = 10`)
3. For last-level groups (records): builds a combined domain from parent domain + group domain, searches all matching records in one query
4. Calls `web_read()` once for all records across all open groups — single round-trip
5. Distributes results back to groups via `zip(all_records._ids, web_read())`

**L4 — Edge cases:**
- If offset >= count when reopening, resets offset to 0 and flags the group with `__offset` to sync the UI
- Empty recordsets are folded by default (checked via `field.relational and not group[groupby_spec]`)
- `progressbar_domain` is AND-combined with group domain when clicking progress bar segments
- `groupby_read_specification` uses `assert` to verify the groupby field is relational

#### `formatted_read_group(domain, groupby, aggregates, having, offset, limit, order)`

```python
@api.model
@api.readonly
def formatted_read_group(self, domain, groupby, aggregates, having=(), offset=0, limit=None, order=None) -> list[dict]
```

Formats `_read_group` output for webclient consumption. Handles group expand and temporal fill. The `fill_temporal` context cannot be combined with `offset` or `limit` — raises `ValueError` if attempted.

#### `formatted_read_grouping_sets(domain, grouping_sets, aggregates, order)`

```python
@api.model
@api.readonly
def formatted_read_grouping_sets(self, domain, grouping_sets, aggregates, *, order=None) -> list[list[dict]]
```

Multi groupby version of `formatted_read_group` allowing different groupby specifications in a single SQL request (used by grid/pivot views). Supports date/datetime granularities (`day`, `week`, `month`, `quarter`, `year`, plus integer parts like `year_number`, `month_number`, `day_of_week`, `hour_number`, etc.).

#### `_web_read_group_fill_temporal(groups, groupby, aggregates, fill_from, fill_to, min_groups)`

Fills date/datetime holes in grouped data. Used for chart rendering where gaps between data points should show explicit zero groups rather than missing bars.

Parameters:
- `fill_from` / `fill_to`: Inclusive bounds for filling (only fills between bounds, not outside)
- `min_groups`: Guarantees at least N contiguous groups starting from `fill_from` or lowest existing group

#### `web_resequence(specification, field_name, offset)`

```python
def web_resequence(self, specification: dict, field_name='sequence', offset=0) -> list[dict]
```

Re-sequences records by writing sequential integers starting from `offset`. Used by list view drag-and-drop reordering.

#### `web_save(vals, specification, next_id)` / `web_save_multi(vals_list, specification)`

`web_save` creates or updates a record then returns it read via `web_read`. `web_save_multi` handles batch operations. Uses `bin_size=True` context for binary field optimization.

---

### `models/res_users_settings.py` — User Settings

```python
class ResUsersSettings(models.Model):
    _inherit = 'res.users.settings'
```

Extends `res.users.settings` to support embedded actions (sub-action panels within a form).

#### `embedded_actions_config_ids`

```python
embedded_actions_config_ids = fields.One2many(
    'res.users.settings.embedded.action', 'user_setting_id'
)
```

#### `set_embedded_actions_setting(action_id, res_id, vals)`

Creates or updates embedded action visibility/order settings. Uses `action_id+res_id` as the uniqueness key.

**L3 — Field format:** `embedded_actions_order` and `embedded_actions_visibility` store comma-separated IDs. The `False` string represents "no action" (e.g., `false,123,456`). The method converts to/from this format on write/read.

---

### `models/res_users_settings_embedded_action.py` — Embedded Action Settings

```python
class ResUsersSettingsEmbeddedAction(models.Model):
    _name = 'res.users.settings.embedded.action'
```

Stores per-user, per-action, per-record visibility and ordering preferences for embedded action panels.

| Field | Type | Notes |
|---|---|---|
| `user_setting_id` | `Many2one(res.users.settings)` | Required, cascade delete |
| `action_id` | `Many2one(ir.actions.act_window)` | Required |
| `res_model` | `Char` | Model where the action was opened |
| `res_id` | `Integer` | Record where the action was opened |
| `embedded_actions_order` | `Char` | Comma-separated action IDs in order |
| `embedded_actions_visibility` | `Char` | Comma-separated visibility flags |
| `embedded_visibility` | `Boolean` | Top bar visibility |

**Constraint:** UNIQUE(`user_setting_id`, `action_id`, `res_id`) — one setting record per combination.

**Validation:** `_check_embedded_actions_field_format` validates that values are comma-separated integers or `"false"`. Duplicates raise `ValidationError`.

**L4 — Security:** ACL in `web_security.xml` restricts users to their own entries (`user_setting_id.user_id = user.id`). Administrators (`base.group_system`) bypass with `[(1, '=', 1)]`.

---

### `models/res_users.py` — User Extensions

```python
class ResUsers(models.Model):
    _inherit = "res.users"
```

#### `name_search(name, domain, operator, limit)`

Overrides the standard name search to always place the current user first in results. Uses two strategies:

1. **User in results**: pops from current position and inserts at index 0
2. **User not in results but limit reached**: attempts to find the current user with a separate search, replaces the last result with the current user

**L3 — Use case:** In action assignments and user picker dialogs, the current user should appear prominently.

#### `_should_captcha_login(credential)`

```python
def _should_captcha_login(self, credential) -> bool
```

Returns `True` only for `type='password'` credentials. Used by the login controller to conditionally trigger reCAPTCHA verification. The `skip_captcha_login` context value (`SKIP_CAPTCHA_LOGIN` sentinel) bypasses this check — used in automated testing.

#### `_on_webclient_bootstrap()`

Hook called during webclient bootstrap. Called from `controllers/home.py`'s `web_client()`. No-op in the base module; available for override by other modules.

---

### `models/res_partner.py` — vCard Export

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'
```

#### `_build_vcard()` / `_get_vcard_file()`

Builds a vCard 3.0 file from a partner record. Fields included: `n`, `fn`, `adr`, `email` (type=INTERNET), `tel` (type=work), `url`, `org`, `title` (from `function`), `photo` (JPG, base64-decoded from `avatar_512`).

**L4 — Dependency:** Requires the `vobject` Python module. Gracefully returns `False` if not installed (logger warning only).

---

### `models/base_document_layout.py` — Document Layout Wizard

```python
class BaseDocumentLayout(models.TransientModel):
    _name = 'base.document.layout'
```

A TransientModel used in Settings to configure company branding for reports. All fields are `related` to `company_id` with `readonly=False` so changes write back to the company record. The wizard is just an editing interface.

**Computed fields:**

| Field | Logic |
|---|---|
| `is_company_details_empty` | `not html2plaintext(company_details)` — detects empty strings vs. `False` |
| `custom_colors` | `True` if user-set colors differ from logo-extracted colors (case-insensitive) |
| `logo_primary_color` / `logo_secondary_color` | Extracted from logo via PIL color quantization |
| `preview` | QWeb render of `web.report_invoice_wizard_preview` template |

**Color extraction algorithm (`extract_image_primary_secondary_colors`):**
1. Resize logo to 50px height (maintaining aspect ratio) for performance
2. Convert to RGBA
3. Filter out transparent and white-ish pixels (`rgb > white_threshold`)
4. `average_dominant_color(colors)` for primary; second call on remaining for secondary
5. Lightness/saturation comparison: if both similar lightness, more colorful wins; if not, brightest wins

**L4 — Image processing edge cases:**
- `logo += '==='` padding handles base64 padding edge cases
- `try/except` around image processing prevents crashes from corrupt logos
- If logo is entirely white, returns `False, False` for both colors

**Onchanges:**
- `_onchange_company_id`: syncs all related fields when company changes
- `_onchange_logo`: if user re-uploads the original logo, color extraction is skipped (preserves user's custom colors)
- `_onchange_custom_colors`: if user unchecks custom colors, resets to logo-extracted colors

---

### `models/res_config_settings.py`

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    web_app_name = fields.Char('Web App Name', config_parameter='web.web_app_name')
```

Single field: the `web.web_app_name` `ir.config_parameter` controls the `<title>` tag and PWA app name shown in the browser.

---

### `models/ir_qweb_fields.py` — QWeb Image Rendering

```python
class IrQwebFieldImage(models.AbstractModel):
    _inherit = 'ir.qweb.field.image'
```

Overrides the qweb image renderer to add SHA512-based cache busting (`?unique=<hash>`).

```python
def _get_src_urls(self, record, field_name, options) -> tuple[str, str|None]
```

URL pattern: `/web/image/<model>/<id>/<field>/<resize>/<filename>?unique=<sha>`

```python
def record_to_html(self, record, field_name, options) -> Markup
```

Renders the `<img>` tag with `src`, `data-zoom`, `data-zoom-image`, `width`, `height`, `class`, `alt`, and `itemprop` attributes.

```python
class IrQwebFieldImage_Url(models.AbstractModel):
    _inherit = 'ir.qweb.field.image_url'
```

Simple override — returns `image_url` as both src and zoom (no processing).

---

### `models/properties_base_definition.py`

```python
class PropertiesBaseDefinition(models.Model):
    _inherit = "properties.base.definition"
```

#### `get_properties_base_definition(model_name, field_name)`

```python
@api.model
def get_properties_base_definition(self, model_name: str, field_name: str) -> dict
```

Returns the base definition for a Properties field. Used by the Studio/definition UI to read property field schemas. Requires `read` access to the model. Returns `sudo()` results.

---

## Controllers

### `controllers/home.py` — Entry Points

#### `/web`, `/odoo`, `/odoo/<path:subpath>`, `/scoped_app/<path:subpath>`

```python
@http.route([...], type='http', auth="none", readonly=_web_client_readonly)
def web_client(self, s_action=None, **kw)
```

The main backend entry point. `auth="none"` allows redirect without auth. Flow:

1. `ensure_db()` — redirect to `/web/database/selector` if no db
2. If no `session.uid` → redirect to `/web/login?redirect=...`
3. If session invalid (`security.check_session`) → `SessionExpiredException`
4. If non-internal user → redirect to `/web/login_successful` (portal user landing)
5. Restore `request.env` user to `session.uid`
6. Call `_on_webclient_bootstrap()` hook on user
7. Render `web.webclient_bootstrap` template with `session_info` + `browser_cache_secret`

**L4 — `browser_cache_secret`:** HMAC signed with `request.env.user._session_token_get_values()`. Changes on password or 2FA changes, busting the browser cache for the affected user.

**L4 — Security headers:**
- `X-Frame-Options: DENY`
- `Cache-Control: no-store`

#### `/web/login`

```python
@http.route('/web/login', type='http', auth='none', readonly=False)
def web_login(self, redirect=None, **kw)
```

Handles login with captcha support. Flow:
1. `ensure_db()`
2. On GET: renders login form (with optional `error` param)
3. On POST:
   - Extracts `credential = {'login', 'password', 'type': 'password'}`
   - Calls `_should_captcha_login`; if True, calls `_verify_request_recaptcha_token`
   - `request.session.authenticate(env, credential)`
   - Redirects to `_login_redirect(uid)`
4. Sets `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'`

**L4 — Captcha bypass:** The `skip_captcha_login` context (set via `SKIP_CAPTCHA_LOGIN` sentinel) allows test code to skip captcha validation entirely.

#### `/web/become` (Switch to Admin)

```python
@http.route('/web/become', type='http', auth='user', sitemap=False, readonly=True)
def switch_to_admin(self)
```

Promotes the current user to `SUPERUSER_ID` in the session. Only works if the user has `is_system` rights. Invalidates the session token cache and recomputes it.

#### `/web/health`

```python
@http.route('/web/health', type='http', auth='none', save_session=False)
def health(self, db_server_status=False) -> JSONResponse
```

Kubernetes-ready health check. Returns `{"status": "pass"}` (200) or `{"status": "fail", "db_server_status": False}` (500). Does not use the session (save_session=False).

#### `/robots.txt`

Returns an empty disallow list by default. Override `_get_allowed_robots_routes()` to allow specific routes.

---

### `controllers/session.py` — Session Management

#### `/web/session/authenticate`

```python
@http.route('/web/session/authenticate', type='jsonrpc', auth="none", readonly=False)
def authenticate(self, db, login, password, base_location=None)
```

Session creation endpoint. Uses `ExitStack` to handle both new and existing database contexts. If the authenticated UID differs from the session UID (e.g., existing session renewal in mobile app), returns `{'uid': None}` as a workaround for outdated mobile apps.

#### `/web/session/destroy`

Calls `request.session.logout()` to terminate the session.

#### `/web/session/logout`

```python
@http.route('/web/session/logout', type='http', auth='none', readonly=True)
def logout(self, redirect='/odoo')
```

HTTP redirect logout. Keeps the database in the session but destroys auth credentials. Redirects to the specified URL.

---

### `controllers/action.py` — Action Loading

#### `/web/action/load`

```python
@route('/web/action/load', type='jsonrpc', auth='user', readonly=True)
def load(self, action_id, context=None)
```

Loads an action by ID, xmlid, or path. Supports `ir.actions.actions` records with a `path` field. The returned action is cleaned via `clean_action()` which strips non-readable fields.

**L4 — Action cleaning (`clean_action` utility):**
- Keeps only fields in `_get_readable_fields()` for the action type OR fields not in `_fields.keys()` (custom properties)
- Logs a warning for custom properties fields (passing via `params`/`context` is preferred)
- Auto-generates `views` from `view_mode` if not present

#### `/web/action/run`

Executes a `ir.actions.server` by ID and returns the resulting action.

#### `/web/action/load_breadcrumbs`

Builds breadcrumb display names for a chain of actions. Handles:
- Server actions with a `path` (must have one to be restored)
- Client actions (no multi-record views, can't resolve next action)
- New records (`resId == 'new'`)

---

### `controllers/model.py` — Model Definitions

#### `/web/model/get_definitions`

```python
@route("/web/model/get_definitions", methods=["POST"], type="http", auth="user")
def get_model_definitions(self, model_names, **kwargs)
```

Proxied call to `ir.model._get_definitions()`. Takes a JSON list of model names and returns the field definition map.

---

### `controllers/dataset.py` — ORM Method Calls

#### `/web/dataset/call_kw`

```python
@route(['/web/dataset/call_kw', '/web/dataset/call_kw/<path:path>'], type='jsonrpc', auth="user")
def call_kw(self, model, method, args, kwargs, path=None)
```

Generic RPC over ORM methods. `thread_local.rpc_model_method` is set to `'<model>.<method>'` for profiler integration. Readonly detection checks the method's `_readonly` attribute by walking the MRO.

#### `/web/dataset/call_button`

Same as `call_kw` but processes the return value through `clean_action()`. Used for button handlers that return action dictionaries.

---

### `controllers/binary.py` — File/Image Serving

#### `/web/content` (and variants)

```python
@route([...], type='http', auth='public', readonly=True)
def content_common(self, xmlid=None, model='ir.attachment', id=None, ...)
```

Serves binary content from any model/field. Delegates to `ir.binary._find_record` and `ir.binary._get_stream_from`. Supports `access_token` for public access to protected records. The `unique` parameter enables `immutable` + long cache headers.

#### `/web/assets/<unique>/<filename>`

```python
@route('/web/assets/<string:unique>/<string:filename>', type='http', auth="public", readonly=True)
def content_assets(self, filename=None, unique=ANY_UNIQUE, ...)
```

Serves compiled JS/CSS asset bundles. If the attachment doesn't exist, generates it on the fly using `ir.qweb._get_asset_bundle`. If the requested `unique` doesn't match the current bundle version, redirects to the correct URL.

**L4 — Asset caching:** Version hash is derived from all source file hashes + language + debug mode. Changing any JS file or installing a module invalidates all bundles for that bundle name.

#### `/web/image` (and variants)

```python
@route([...], type='http', auth='public', readonly=True, save_session=False)
def content_image(self, xmlid=None, model='ir.attachment', ...)
```

Serves images with on-the-fly resize/crop. Falls back to a placeholder image on `UserError` if not downloading. If dimensions are 0x0, guesses a reasonable size from the field name.

#### `/web/binary/upload_attachment`

```python
@http.route('/web/binary/upload_attachment', type='http', auth="user")
def upload_attachment(self, model, id, ufile, callback=None)
```

Multipart upload for attachments. Returns a `<script>` tag if `callback` is provided (legacy JSONP-style response), otherwise plain JSON.

#### `/web/binary/company_logo`, `/logo`, `/logo.png`

```python
@route([...], type='http', auth="none", cors="*")
def company_logo(self, dbname=None, **kw)
```

Serves company logo. Uses direct SQL query to avoid ORM overhead. Falls back to static Odoo logo if not found.

---

### `controllers/database.py` — DB Manager

**Routes:**
- `/web/database/selector` — Database selection page
- `/web/database/manager` — Full database management
- `/web/database/create` — Create new database
- `/web/database/duplicate` — Duplicate database
- `/web/database/drop` — Drop database
- `/web/database/backup` — Generate backup ZIP
- `/web/database/restore` — Restore from backup
- `/web/database/change_password` — Change master password
- `/web/database/list` — JSON list of databases (mobile app use)

**L4 — Security:** All routes are `auth="none"` but controlled by `list_db` config option. Database creation validates names against `DBNAME_PATTERN = '^[a-zA-Z0-9][a-zA-Z0-9_.-]+$'`. Master password operations use `verify_admin_password` to check against the configured admin password. These routes render raw QWeb templates from `web/static/src/public/*.qweb.html`.

---

### `controllers/export.py` — Data Export

#### `GroupsTreeNode`

Builds an ordered tree from `formatted_read_group` results. Used for hierarchical (grouped) Excel export. Aggregates are propagated up the tree via `functools.cached_property` for performance.

Supports aggregators: `max`, `min`, `sum`, `avg`, `bool_and`, `bool_or`. Handles empty iterables gracefully.

#### `/web/export/formats`

Returns `{'tag': 'xlsx', 'label': 'XLSX', 'error': error_or_None}` and `{'tag': 'csv', 'label': 'CSV'}`.

#### `/web/export/get_fields(model, domain, ...)`

Returns the field tree for the export field selector. Handles `properties` fields by querying definition records to resolve dynamic field schemas.

**L4 — Property field handling:** Property fields are expanded at export time by querying the definition record model and extracting property schemas. Properties with `comodel` not in the current environment are skipped.

#### `/web/export/csv` and `/web/export/xlsx`

Both call `base(data)` which:
1. Parses JSON params: `model`, `fields`, `ids`, `domain`, `import_compat`
2. Searches records
3. If `groupby` is set (non-import_compat): builds `GroupsTreeNode` and calls `from_group_data`
4. Otherwise: calls `export_data` and `from_data`

CSV export disables group export entirely. XLSX export recursively writes groups with subtotals.

---

### `controllers/webclient.py` — Webclient Bootstrap

#### `/web/webclient/bootstrap_translations`

Loads `.po` translation files for modules with `bootstrap: True` for the login screen. Used before a session exists. Strips sub-language suffix (e.g., `fr_BE` loads `fr.po`).

#### `/web/webclient/translations`

Hash-based translation caching. If the client's hash matches the server's hash, returns only `{'lang': lang, 'hash': hash}` without body. Otherwise returns the full translation map.

**L4 — Cache strategy:** Uses `ormcachel` on `_get_web_translations_hash`. The `translation_data` cache entry is popped from `request.env.cr.cache` on cold cache hits to avoid double-fetching.

#### `/web/webclient/version_info`

Returns `exp_version()` (Odoo version info RPC).

#### `/web/bundle/<bundle_name>`

Returns the list of `<script>` and `<link>` tags for a named asset bundle. Used by the JS module loader to dynamically load bundle definitions.

---

### `controllers/profiling.py`

#### `/web/set_profiling`

Enables/disables the profiler. Collectors default to `['sql', 'traces_async']`. State is stored in `ir.profile`.

#### `/web/speedscope/<profile>`

Renders the speedscope flamegraph visualizer for a profile ID (or comma-separated IDs). Supports downloading as JSON or HTML. CDN URL configurable via `speedscope_cdn` ir.config_parameter.

#### `/web/profile_config/<profile>`

Configuration page for a profile, including memory profiling via `memory_open` action.

---

### `controllers/utils.py` — Utility Functions

#### `ensure_db(redirect, db)`

```python
def ensure_db(redirect='/web/database/selector', db=None) -> None
```

Ensures a database is selected. Redirects to `/web/database/selector` if none is found. Validates the db name via `http.db_filter()` to prevent database forgery attacks. If db is provided in the session but differs from the requested one, creates a new session and redirects.

#### `clean_action(action, env)`

```python
def clean_action(action, env) -> dict
```

Strips non-readable fields from an action dictionary. Keeps custom properties but logs a warning recommending `params`/`context` instead. Auto-generates `views` from `view_mode` if missing.

#### `get_action_triples(env, path)`

```python
def get_action_triples(env, path) -> Generator[tuple]
```

Parses `/odoo`-like paths (e.g., `/all-tasks/5/project.project/1/tasks`) into `(active_id, action, record_id)` triples. Supports `action-` prefixes, `m-` model prefixes, and dotted model names.

#### `_get_login_redirect_url(uid, redirect)`

```python
def _get_login_redirect_url(uid, redirect=None) -> str
```

Decides post-login redirect. If fully logged in, redirects to `/odoo` (internal) or `/web/login_successful` (external). If partial session (MFA), builds an MFA URL and appends the redirect as a query parameter.

#### `is_user_internal(uid)`

```python
def is_user_internal(uid) -> bool
```

Returns `user._is_internal()` for the given UID.

---

## Security

### Access Control

| Model | ACL | Who |
|---|---|---|
| `base.document.layout` | `base.group_system` (rw) | System admins only |
| `res.users.settings.embedded.action` | `base.group_user` (full) | All internal users |
| `ir.model` | Inherited from `base` | Only readable fields exposed |

### Record Rules

`res.users.settings.embedded.action` has two rules:
- Users: `user_setting_id.user_id = user.id` — can only see/edit their own
- Admins (`base.group_system`): `[(1, '=', 1)]` — unrestricted

### Cookie Security

- `cids` cookie: sanitized from comma to hyphen separator to prevent injection
- Session cookie: managed by `ir.http._post_logout` clearing `cids`
- `browser_cache_secret`: HMAC-signed, changes on security-relevant events

### CSRF

CSRF is disabled (`csrf=False`) on database management routes (`/web/database/*`) and file upload (`/web/binary/upload_attachment`) because they use `type='http'` form submission. All JSON-RPC routes use token-based auth and are inherently CSRF-protected.

---

## Historical Notes (Odoo 17 → 19)

1. **Module consolidation**: In Odoo 18, many `web_*` addons (web_diagram, web_graph, etc.) were merged into `web`. Odoo 19 retains this structure.
2. **Session info expansion**: `session_info()` grew `quick_login`, `view_info`, `groups.base.group_allow_export`, `bundle_params`, and `user_companies` fields over versions.
3. **Asset bundles**: The bundle architecture was redesigned with include/exclude directives and sub-bundle naming conventions. Odoo 19 extends this with dark mode bundles and print-specific bundles.
4. **Properties fields**: Support for `properties` type in `web_read` (nested many2one/many2many resolution) was added in Odoo 18+.
5. **`formatted_read_grouping_sets`**: Multi-groupby grouping sets for grid/pivot views was added in Odoo 17.
6. **Captcha login**: `_should_captcha_login` and recaptcha verification was added post-Odoo 17.
7. **`web_resequence`**: The re-sequencing API for list view drag-and-drop was formalized in this module.
