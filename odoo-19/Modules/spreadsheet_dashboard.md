---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #spreadsheet
  - #dashboard
  - #ce
---

# spreadsheet_dashboard (Spreadsheet Dashboard)

## Module Overview

**Module Name:** `spreadsheet_dashboard`  
**Type:** Community (CE)  
**Location:** `odoo/addons/spreadsheet_dashboard/`  
**Category:** Productivity/Dashboard  
**License:** LGPL-3  
**Version:** 1.0

**Summary:** Provides a dashboard system for sharing Odoo spreadsheets. Dashboards group related spreadsheets into a navigation menu, allow users to favorite them, and support public sharing via secure tokens for read-only external access.

**Key Value Proposition:**
- Group spreadsheets into dashboard menus
- Favorite dashboards for quick access
- Share dashboards externally with a public URL
- Read-only spreadsheet rendering (external viewers cannot edit)
- Export dashboard data to Excel
- Access control per dashboard (groups-based)
- Multi-company dashboard data

**Dependencies:** `spreadsheet`  
**Auto-install:** No (requires explicit installation)

---

## Architecture

### Relationship to Spreadsheets

`sheet.dashboard` does **not** store spreadsheet data directly. Instead, it wraps the Odoo spreadsheet engine (`spreadsheet` module). The actual spreadsheet data lives in the `spreadsheet.spreadsheet` model (from the `spreadsheet` module), referenced via the `spreadsheet.mixin` mixin.

```
spreadsheet.spreadsheet (data storage from spreadsheet module)
        │
        │ (inherits spreadsheet.mixin)
        ▼
spreadsheet.dashboard (dashboard wrapper)
        ├── groups dashboards into a menu
        ├── provides sharing infrastructure
        └── provides favorite mechanism
```

### Key Mixin: `spreadsheet.mixin`

Both `spreadsheet.dashboard` and `spreadsheet.dashboard.share` inherit from `spreadsheet.mixin` (defined in the `spreadsheet` module). This mixin provides:

| Field/Method | Description |
|-------------|-------------|
| `spreadsheet_data` | JSON field storing the spreadsheet document data |
| `spreadsheet_binary_data` | Binary field for Excel export of the spreadsheet |
| `name` | Spreadsheet name |
| `_get_serialized_readonly_dashboard()` | Returns snapshot + locale + currency for rendering |

---

## Key Models

### 1. `spreadsheet.dashboard.group`

Groups multiple dashboards into a single navigation menu section.

**Table:** `spreadsheet_dashboard_group`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required, translate) | Group display name |
| `dashboard_ids` | One2many `spreadsheet.dashboard` | All dashboards in this group |
| `published_dashboard_ids` | One2many (filtered) | Only `is_published=True` dashboards |
| `sequence` | Integer | Menu ordering |

**Key Method:**
```python
@api.ondelete(at_uninstall=False)
def _unlink_except_spreadsheet_data(self):
    # Prevents deleting groups that are referenced by other modules
    external_id = external_ids[group.id]
    if external_id and not external_id.startswith('__export__'):
        raise UserError(_("You cannot delete %s as it is used in another module."))
```

---

### 2. `spreadsheet.dashboard` (Main Model)

The primary model. Inherits `spreadsheet.mixin`.

**Table:** `spreadsheet_dashboard`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required, translate) | Dashboard title |
| `dashboard_group_id` | Many2one `spreadsheet.dashboard.group` | Parent group |
| `sequence` | Integer | Ordering within group |
| `spreadsheet_data` | JSON (from mixin) | Live spreadsheet data |
| `spreadsheet_binary_data` | Binary (from mixin) | Excel export file |
| `sample_dashboard_file_path` | Char | Path to JSON template file for new dashboards |
| `is_published` | Boolean | Whether visible in menu (default: True) |
| `company_ids` | Many2many `res.company` | Companies this dashboard applies to |
| `group_ids` | Many2many `res.groups` | User groups allowed to view (default: `base.group_user` — all internal users) |
| `favorite_user_ids` | Many2many `res.users` | Users who favorited this dashboard |
| `is_favorite` | Boolean (computed) | Is current user in `favorite_user_ids`? |
| `main_data_model_ids` | Many2many `ir.model` | Models referenced in the spreadsheet (for empty-state detection) |

#### `is_favorite` Computation

```python
@api.depends_context('uid')
@api.depends('favorite_user_ids')
def _compute_is_favorite(self):
    for dashboard in self:
        dashboard.is_favorite = self.env.uid in dashboard.favorite_user_ids.ids
```

#### `action_toggle_favorite`

```python
def action_toggle_favorite(self):
    self.ensure_one()
    current_user_id = self.env.uid
    if current_user_id in self.favorite_user_ids.ids:
        self.sudo().favorite_user_ids = [Command.unlink(current_user_id)]
    else:
        self.sudo().favorite_user_ids = [Command.link(current_user_id)]
```

#### `_get_serialized_readonly_dashboard`

Returns the data needed to render a **read-only snapshot** of the spreadsheet:

```python
def _get_serialized_readonly_dashboard(self):
    snapshot = json.loads(self.spreadsheet_data)
    user_locale = self.env['res.lang']._get_user_spreadsheet_locale()
    snapshot.setdefault('settings', {})['locale'] = user_locale
    default_currency = self.env['res.currency'].get_company_currency_for_spreadsheet()
    return json.dumps({
        'snapshot': snapshot,
        'revisions': [],
        'default_currency': default_currency,
        'translation_namespace': self._get_dashboard_translation_namespace(),
    })
```

Key points:
- Loads live `spreadsheet_data` as a snapshot
- Sets user locale from `res.lang._get_user_spreadsheet_locale()`
- Sets currency from company settings
- Clears revisions (no undo history for external viewers)
- Returns translation namespace for i18n

#### `_dashboard_is_empty`

Detects if the dashboard's referenced data models have no records (used to show "sample data" state):

```python
def _dashboard_is_empty(self):
    return any(
        self.env[model].search_count([], limit=1) == 0
        for model in self.sudo().main_data_model_ids.mapped("model")
    )
```

#### `copy_data`

Custom copy behavior — appends " (copy)" to the dashboard name:

```python
def copy_data(self, default=None):
    default = dict(default or {})
    vals_list = super().copy_data(default=default)
    if 'name' not in default:
        for dashboard, vals in zip(self, vals_list):
            vals['name'] = _("%s (copy)", dashboard.name)
    return vals_list
```

---

### 3. `spreadsheet.dashboard.share`

Handles **public sharing** of dashboards. Each share record is a copy/link to a specific dashboard with its own access token.

**Table:** `spreadsheet_dashboard_share`

| Field | Type | Description |
|-------|------|-------------|
| `dashboard_id` | Many2one `spreadsheet.dashboard` (required) | The dashboard being shared |
| `access_token` | Char (required, unique) | UUID-based token for the share URL |
| `name` | Char (related) | Alias to `dashboard_id.name` |
| `full_url` | Char (computed) | The public share URL |
| `excel_export` | Binary | Pre-generated Excel file for download |
| `spreadsheet_binary_data` | Binary (inherited from mixin) | The spreadsheet Excel data |

#### `_compute_full_url`

```python
def _compute_full_url(self):
    for share in self:
        share.full_url = "%s/dashboard/share/%s/%s" % (
            share.get_base_url(), share.id, share.access_token
        )
```

Share URL format: `https://example.com/dashboard/share/{share_id}/{access_token}`

#### `action_get_share_url`

Called by the JS client when creating a share link:

```python
@api.model
def action_get_share_url(self, vals):
    if "excel_files" in vals:
        excel_zip = self._zip_xslx_files(vals["excel_files"])
        del vals["excel_files"]
        vals["excel_export"] = base64.b64encode(excel_zip)
    return self.create(vals).full_url
```

If `excel_files` are provided (from the spreadsheet's Excel export), they are zipped and stored as `excel_export` for public download.

#### Access Control: `_check_dashboard_access`

```python
def _check_dashboard_access(self, access_token):
    self.ensure_one()
    token_access = self._check_token(access_token)
    dashboard = self.dashboard_id.with_user(self.create_uid)
    user_access = dashboard.has_access("read")
    if not (token_access and user_access):
        raise Forbidden(_("You don't have access to this dashboard. "))
```

Both conditions must pass:
1. **Token valid**: `consteq(access_token, self.access_token)` — timing-safe comparison
2. **Creator still has read access**: the share creator's user must still be able to read the dashboard

---

## Sharing Flow

### Internal Sharing (Within Odoo)

1. User opens a dashboard
2. Clicks "Share" button
3. JS client calls `spreadsheet.dashboard.share/action_get_share_url`
4. A `spreadsheet.dashboard.share` record is created with a UUID token
5. The share URL is displayed: `/dashboard/share/{id}/{token}`

### External Access (Public URL)

1. External user visits `/dashboard/share/{id}/{token}`
2. Controller `DashboardShareRoute.share_portal` handles the request
3. `_check_dashboard_access(token)` validates the token and dashboard access
4. The controller renders the public spreadsheet layout with read-only data
5. External user sees the dashboard as a frozen spreadsheet (no editing)

### Share URL Components

```
/dashboard/share/<share_id>/<token>
         │           │
         │           └── UUID token (from spreadsheet_dashboard_share.access_token)
         │               Validated via _check_token() using consteq()
         └── Internal share record ID
             Used to lookup the share record
             Combined with token to authorize access
```

### Excel Download

```
/dashboard/download/<share_id>/<token>
```

Returns the pre-generated `excel_export` binary from the share record, if it was included at share creation time.

### Data Fetch

```
/dashboard/data/<share_id>/<token>
```

Returns the spreadsheet binary data (JSON) for the shared dashboard.

---

## Access Control

### Within Odoo

- **`group_ids`**: Only users in these groups can see the dashboard in the menu. Default: `base.group_user` (all internal users).
- **`company_ids`**: Multi-company visibility filter.
- **`is_published`**: Controls menu visibility (not security — unpublished dashboards can still be accessed directly).

### External Sharing

The share link gives **read-only** access to anyone with the URL. The external viewer:
- Can see the spreadsheet data (as of the share moment)
- Cannot edit the spreadsheet
- Cannot see other dashboards
- Cannot access any other Odoo data
- Access is validated via token + creator's permissions

---

## Dashboard Menu Structure

```
Dashboard Menu (from data/dashboard.xml)
│
├── Group: "Financial"
│   ├── Dashboard: "P&L Report"
│   ├── Dashboard: "Balance Sheet"
│   └── Dashboard: "Cash Flow"
│
├── Group: "Sales"
│   ├── Dashboard: "Sales Analysis"
│   └── Dashboard: "Pipeline"
│
└── Group: "Operations"
    └── Dashboard: "Stock Levels"
```

The menu is generated from `spreadsheet_dashboard_group` → `spreadsheet_dashboard` records and rendered in the Odoo web client sidebar.

---

## Key Behaviors

### Read-Only Snapshot for External Views

When sharing externally, the dashboard renders in "frozen" mode — no revision history, no live formula recalculation (the data was pre-computed). This is intentional for security and performance.

### Favorite Mechanism

Users can mark dashboards as favorites. The `is_favorite` field is computed dynamically based on whether the current user's ID is in `favorite_user_ids`. Toggling favorites uses `Command.link`/`Command.unlink` on the Many2many field.

### Main Data Models

The `main_data_model_ids` field declares which Odoo models the dashboard's spreadsheet references. This is used by `_dashboard_is_empty()` to detect when there is no real data yet and show an appropriate placeholder/sample state.

---

## Templates and Assets

### JavaScript Assets

The module registers JS bundles for the spreadsheet dashboard UI:

```python
'assets': {
    'spreadsheet.o_spreadsheet': [
        'spreadsheet_dashboard/static/src/bundle/**/*.js',
        'spreadsheet_dashboard/static/src/bundle/**/*.xml',
    ],
    'spreadsheet.assets_print': [
        'spreadsheet_dashboard/static/src/print_assets/**/*',
    ],
    'web.assets_backend': [
        'spreadsheet_dashboard/static/src/assets/**/*.js',
        'spreadsheet_dashboard/static/src/**/*.scss',
    ],
}
```

### Views

Dashboard form view defined in `views/spreadsheet_dashboard_views.xml`.

---

## Security Considerations

1. **Token Security**: Uses `uuid.uuid4()` for tokens and `consteq()` for timing-safe comparison (prevents timing attacks).
2. **Creator Permission Check**: External access requires the share creator to still have read access — if a dashboard is made private or deleted, all its shares become invalid.
3. **No Edit Access**: External shares are always read-only snapshots.
4. **Group-based Access**: Within Odoo, only authorized groups can see dashboards.
5. **No Data Isolation**: External viewers see the same data the creator sees (filtered by creator's company/groups).

---

## Related Modules

| Module | Purpose |
|--------|---------|
| `spreadsheet` | Core spreadsheet engine (required dependency) |
| `spreadsheet_account` | Accounting formula providers for spreadsheets |
| `spreadsheet_dashboard_account_accountant` | Accountant-specific dashboard templates |
| `spreadsheet_dashboard_documents` | Documents dashboard templates |
| `spreadsheet_dashboard_crm` | CRM dashboard templates |
| `spreadsheet_dashboard_*` (many) | Industry/role-specific dashboard packs |

---

## See Also

- [[Modules/spreadsheet_account]] — Accounting formulas used inside dashboard spreadsheets
- [[Modules/spreadsheet]] — Core spreadsheet engine
- [[Core/API]] — Computed fields, @api.depends_context
- [[Patterns/Security Patterns]] — Token-based access control
