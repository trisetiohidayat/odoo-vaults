---
type: module
name: web
version: Odoo 18
tags: [module, web, http, orm, session, export]
source: ~/odoo/odoo18/odoo/addons/web/
---

# Web

Odoo web client server-side logic — session management, ORM web APIs, database management, binary serving, menu loading, action loading, export, and profiling.

**Source:** `addons/web/`
**Category:** Hidden (auto-installs with base)

---

## Models

### `ir.model` Extension

```python
class IrModel(models.Model):
    _inherit = "ir.model"
```

| Method | Decorator | Description |
|--------|-----------|-------------|
| `display_name_for(models)` | `@api.model` | Display names for models user can access. Returns raw name for inaccessible models (prevents enumeration). |
| `get_available_models()` | `@api.model` | ALL models current user can access — called once per session boot. |
| `_get_definitions(model_names)` | — | Field definitions for model introspection. |

---

### `ir.http` Extension — Central HTTP Routing Mixin

```python
class Http(models.AbstractModel):
    _inherit = 'ir.http'
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `bots` | `list[str]` | User-agents treated as bots: `["bot", "crawl", "slurp", "spider", "curl", "wget", "facebookexternalhit", "whatsapp", ...]` |

| Method | Description |
|--------|-------------|
| `is_a_bot()` | Checks UA against `bots` list (substring match) |
| `_sanitize_cookies(cookies)` | Normalizes `cids` cookie: `"1,2,3"` → `"1-2-3"` |
| `_handle_debug(rule, args)` | Parses `?debug=` — modes: `''`, `'1'`, `'assets'`, `'tests'`, `'disable-t-cache'` |
| `session_info()` | **Primary session payload** — 30+ keys sent to webclient on bootstrap |
| `get_frontend_session_info()` | Stripped-down session info for public/website pages |
| `get_currencies()` | Currency data (symbol, position, decimal_places) — cached |

**`session_info()` keys:**
```
uid, is_system, is_admin, is_public, is_internal_user,
user_context{lang, tz, uid}, db, user_settings,
server_version, quick_login, partner_write_date,
partner_display_name, web.base.url, active_ids_limit,
profile_session, currencies, bundle_params{lang, debug?},
test_mode, view_info, user_companies{current, allowed},
show_effect
```

---

### `base` Extension — Core Web ORM API

```python
class Base(models.AbstractModel):
    _inherit = 'base'
```

| Method | Decorator | Returns | Description |
|--------|-----------|---------|-------------|
| `web_search_read(domain, spec, offset, limit, order, count_limit)` | `@api.model` `@api.readonly` | `{length, records}` | `search_fetch` + `web_read` + count |
| `web_read(specification)` | `@api.readonly` | list of dicts | Central field-reading — handles m2o, o2m, m2m, reference, properties |
| `web_read_group(domain, groupby, aggregates, ...)` | `@api.model` `@api.readonly` | grouped dicts | Primary grouped data method — supports auto_unfold |
| `formatted_read_group(...)` | `@api.model` `@api.readonly` | formatted dicts | Formats `_read_group` for webclient — handles date fill |
| `formatted_read_grouping_sets(...)` | `@api.model` `@api.readonly` | formatted sets | Multi groupby for grid/pivot views |
| `web_save(vals, spec, next_id)` | — | dict | Create/update + return via `web_read` |
| `web_save_multi(vals_list, spec)` | — | list | Batch `web_save` |
| `web_resequence(spec, field_name, offset)` | — | bool | Re-sequence records by writing sequential integers |

**`web_read()` field handling:**
- **Many2one**: Returns `{'id', 'display_name'}` — graceful error if inaccessible
- **One2many/Many2many**: Supports `order` and `limit` keys in spec
- **Reference**: Sets field to `False` if target doesn't exist
- **Properties**: Resolves m2o/m2m values, passes others through

---

### `ir.ui.menu` Extension

```python
class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"
```

| Method | Description |
|--------|-------------|
| `load_web_menus(debug)` | Loads all menus for webclient. Resolves app actions recursively. |

**Icon resolution priority:**
1. `web_icon_data` — base64 data URI
2. `web_icon` (3 parts) — CSS class string
3. `web_icon` (2 parts) — icon + color, default bg
4. Fallback — `/web/static/img/default_icon_app.png`

---

### `ir.ui.view` Extension

```python
class View(models.Model):
    _inherit = 'ir.ui.view'
```

| Method | Description |
|--------|-------------|
| `get_view_info()` | Metadata about all non-qweb view types for webclient view-switcher icons |

**View types:** `list`, `form`, `graph`, `pivot`, `kanban`, `calendar`, `search`

---

### `ir.qweb.field.image` Extension

```python
class ImageUrlConverter(models.AbstractModel):
    _inherit = 'ir.qweb.field.image_url'
```

| Method | Description |
|--------|-------------|
| `_get_src_urls(record, field, options)` | Returns src + zoom URLs with SHA512 cache-busting `?unique=<hash>` |

**URL pattern:** `/web/image/<model>/<id>/<field>/<resize>/<filename>?unique=<sha>`

---

### `res.users` Extension

```python
class ResUsers(models.Model):
    _inherit = "res.users"
```

| Method | Description |
|--------|-------------|
| `name_search(name, args, operator, limit)` | Places current user first in results (pops and inserts at index 0) |
| `_on_webclient_bootstrap()` | Hook called during webclient bootstrap — no-op by default |

---

### `res.partner` Extension — vCard Export

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'
```

| Method | Description |
|--------|-------------|
| `_build_vcard()` | Builds vCard 3.0: n, fn, adr, email, tel, url, org, title, photo |
| `_get_vcard_file()` | Serializes vCard to bytes. Requires `vobject` module — returns `False` if missing |

---

### `base.document.layout` — TransientModel Wizard

```python
class BaseDocumentLayout(models.TransientModel):
    _name = 'base.document.layout'
    _description = 'Company Document Layout'
```

| Field | Type | Description |
|-------|------|-------------|
| `company_id` | Many2one | Required, defaults to current company |
| `logo` | Binary | Related to `company_id.logo` |
| `report_header/footer/details` | Html | Related company fields |
| `logo_primary_color` | Char | Computed from logo via PIL color quantization |
| `logo_secondary_color` | Char | Computed from logo |
| `custom_colors` | Boolean | True if user colors differ from extracted |
| `preview` | Html | Computed QWeb render preview |

---

## Controllers

### `home.py` — Entry Points

| Route | Auth | Description |
|-------|------|-------------|
| `/` | `none` | Redirect → `/odoo` or `/web/login_successful` |
| `/web`, `/odoo` | `none` | Main backend entry point |
| `/web/login` | `none` | Login handler with captcha |
| `/web/login_successful` | `user` | Landing page for external users |
| `/web/become` | `user` | Switch to admin |
| `/web/health` | `none` | Kubernetes health check (no session) |
| `/robots.txt` | `none` | Robots.txt |

---

### `session.py` — Session Management

| Route | Method | Description |
|-------|--------|-------------|
| `/web/session/get_session_info` | `get_session_info` | Returns session info, touches session |
| `/web/session/authenticate` | `authenticate` | Session creation (mobile app workaround) |
| `/web/session/destroy` | `destroy` | JSON logout |
| `/web/session/logout` | `logout` | HTTP redirect logout |

---

### `action.py` — Action Loading

| Route | Method | Description |
|-------|--------|-------------|
| `/web/action/load` | `load` | Load action by ID, xmlid, or path |
| `/web/action/run` | `run` | Execute `ir.actions.server` |
| `/web/action/load_breadcrumbs` | `load_breadcrumbs` | Build breadcrumb display names |

---

### `model.py` — Model Introspection

| Route | Method | Description |
|-------|--------|-------------|
| `/web/model/get_definitions` | `get_model_definitions` | Field definitions for models |

---

### `binary.py` — File Serving

| Route | Method | Description |
|-------|--------|-------------|
| `/web/content` | `content_common` | Serve binary from any model/field |
| `/web/assets/<unique>/<filename>` | `content_assets` | Serve compiled JS/CSS bundles |
| `/web/image` | `content_image` | Images with resize/crop |
| `/web/binary/upload_attachment` | `upload_attachment` | Multipart attachment upload |
| `/logo`, `/logo.png` | `company_logo` | Company logo |

---

### `database.py` — DB Management

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/web/database/selector` | `selector` | `none` | DB selection page |
| `/web/database/manager` | `manager` | `none` | Full DB management |
| `/web/database/create` | `create` | `none` | Create DB |
| `/web/database/backup` | `backup` | `none` | Generate backup |
| `/web/database/restore` | `restore` | `none` | Restore from backup |
| `/web/database/change_password` | `change_password` | `none` | Change master pw |

**DB name pattern:** `^[a-zA-Z0-9][a-zA-Z0-9_.-]+$`

---

### `export.py` — Data Export

| Route | Method | Format |
|-------|--------|--------|
| `/web/export/formats` | `formats` | Available formats |
| `/web/export/get_fields` | `get_fields` | Field tree for export |
| `/web/export/csv` | `web_export_csv` | CSV |
| `/web/export/xlsx` | `web_export_xlsx` | XLSX with grouping support |

**Grouping:** `GroupsTreeNode` builds tree from `read_group` results. Aggregators: `max`, `min`, `sum`, `avg`, `bool_and`, `bool_or`.

---

### `webclient.py` — Bootstrap

| Route | Method | Description |
|-------|--------|-------------|
| `/web/webclient/bootstrap_translations` | `bootstrap_translations` | Login screen `.po` translations |
| `/web/webclient/translations/<unique>` | `translations` | Hash-cached translations |
| `/web/webclient/version_info` | `version_info` | Odoo version info |
| `/web/tests` | `unit_tests_suite` | QUnit test suite |
| `/web/bundle/<bundle_name>` | `bundle` | Asset bundle definition |

---

### `profiling.py` — Performance

| Route | Method | Description |
|-------|--------|-------------|
| `/web/set_profiling` | `profile` | Enable/disable profiler |
| `/web/speedscope` | `speedscope` | Speedscope flamegraph visualizer |

---

## Cross-Module Relations

| Module | Integration |
|--------|-------------|
| `base` | Only explicit dependency |
| `mail` | Session info + messaging |
| `website` | Frontend routing via `http_routing` |
| `report` | Report layout via `base.document.layout` |

---

## Related Links
- [Core/HTTP Controller](HTTP Controller.md) — HTTP routing reference
- [Modules/http_routing](http_routing.md) — Multilingual URL routing
- [Modules/website](website.md) — Website builder
