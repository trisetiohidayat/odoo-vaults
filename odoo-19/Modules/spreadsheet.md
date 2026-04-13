---
uid: spreadsheet
title: Spreadsheet
type: module
category: Productivity/Dashboard
version: "1.0"
created: 2026-04-06
updated: 2026-04-11
dependencies:
  - bus
  - web
  - portal
author: Odoo S.A.
license: LGPL-3
summary: Collaborative spreadsheet application with Odoo data integration, JSON-based document model, and o_spreadsheet engine
tags: [odoo, odoo19, spreadsheet, o_spreadsheet, collaboration, productivity]
---

# Spreadsheet (`spreadsheet`)

## Overview

| Property | Value |
|----------|-------|
| **Module** | `spreadsheet` |
| **Category** | Productivity/Dashboard |
| **License** | LGPL-3 |
| **Edition** | Community (CE) |
| **Depends** | `bus`, `web`, `portal` |
| **Author** | Odoo S.A. |

`spreadsheet` provides **Odoo Sheets** — a collaborative, Excel-like spreadsheet application built on the `o_spreadsheet` JavaScript engine. Spreadsheets can embed **Odoo data sources** (lists, pivots, charts) via a formula language, support **real-time collaboration** through the Odoo bus/WebSocket, and export to XLSX with embedded images. The `spreadsheet.mixin` enables any model to store and manage spreadsheet documents.

> **Note on model scope.** This module provides the base engine only. It does NOT define `spreadsheet.collection`, `spreadsheet.spreadsheet`, `spreadsheet.external`, `spreadsheet.share`, or `spreadsheet.thread`. Those models live in downstream modules such as `spreadsheet_dashboard`, `spreadsheet_account`, etc.

---

## File Structure

```
spreadsheet/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── spreadsheet_mixin.py      # Abstract mixin — core storage and validation
│   ├── ir_http.py                 # session_info override for can_insert_in_spreadsheet
│   ├── ir_model.py                 # has_searchable_parent_relation override
│   ├── res_currency.py             # Currency structure for spreadsheets
│   ├── res_currency_rate.py         # Exchange rate lookups for formulas
│   └── res_lang.py                  # Locale conversion for spreadsheet formatting
├── utils/
│   ├── __init__.py
│   ├── validate_data.py             # Field chain extraction from spreadsheet JSON
│   ├── json.py                      # JSON extension utility
│   └── formatting.py                # Date/time format conversion
├── static/
│   ├── src/
│   │   ├── index.js                 # Plugin registry (3 registries, 15+ plugins)
│   │   ├── model.js                 # Re-exports OdooSpreadsheetModel = Model
│   │   ├── plugins.js               # Re-exports OdooCorePlugin, CoreViewPlugin, UIPlugin
│   │   ├── hooks.js                 # useSpreadsheetPrint, useSpreadsheetNotificationStore
│   │   ├── o_spreadsheet/           # o_spreadsheet JS engine (npm: @odoo/o-spreadsheet)
│   │   │   ├── o_spreadsheet.js      # Transpiled bundle (v19.0.21, hash e804d77b7)
│   │   │   ├── o_spreadsheet.xml     # QWeb templates
│   │   │   ├── o_spreadsheet.scss    # Styles
│   │   │   ├── o_spreadsheet_variables.scss
│   │   │   ├── odoo_module.js       # Wraps @odoo/o-spreadsheet, exposes window.o_spreadsheet
│   │   │   ├── migration.js          # Version migrations (v1 → v13)
│   │   │   ├── errors.js             # LoadingDataError, EvaluationError sentinels
│   │   │   └── translation.js        # TranslationNamespace + dynamicTranslate
│   │   ├── data_sources/
│   │   │   ├── odoo_data_provider.js # EventBus wrapper; manages ServerData lifecycle
│   │   │   └── server_data.js        # Request, ListRequestBatch, ServerData, BatchEndpoint
│   │   ├── pivot/
│   │   │   ├── index.js              # Pivot command types + PivotOdooCorePlugin registration
│   │   │   ├── odoo_pivot.js         # OdooPivot, OdooPivotRuntimeDefinition, pivotRegistry
│   │   │   ├── pivot_functions.js    # ODOO.PIVOT(), ODOO.PIVOT.HEADER()
│   │   │   └── plugins/
│   │   │       ├── pivot_core_global_filter_plugin.js
│   │   │       └── pivot_odoo_ui_plugin.js
│   │   ├── list/
│   │   │   ├── index.js              # List command types + ListCorePlugin registration
│   │   │   ├── list_functions.js     # ODOO.LIST(), ODOO.LIST.HEADER()
│   │   │   └── plugins/
│   │   │       └── list_core_global_filter_plugin.js
│   │   ├── chart/
│   │   │   ├── index.js              # 14 chart subtypes, chartComponentRegistry, chartSubtypeRegistry
│   │   │   ├── chart_functions.js    # ODOO.CHART()
│   │   │   ├── odoo_menu/
│   │   │   │   └── odoo_menu_chartjs_plugin.js  # ChartJS menu plugin
│   │   │   └── plugins/
│   │   │       ├── odoo_chart_core_plugin.js
│   │   │       ├── odoo_chart_core_view_plugin.js
│   │   │       └── odoo_chart_feature_plugin.js
│   │   ├── global_filters/
│   │   │   ├── index.js              # Command types: ADD/EDIT/REMOVE/MOVE/SET/MANY/SET_OBJECT
│   │   │   └── helpers.js            # globalFieldMatchingRegistry, RELATIVE_PERIODS, getBestGranularity
│   │   ├── currency/
│   │   │   └── plugins/
│   │   │       └── currency.js       # CurrencyPlugin (getCurrencyRate, getCompanyCurrencyFormat)
│   │   ├── ir_ui_menu/
│   │   │   ├── index.js              # IrMenuPlugin registration + BadOdooLinkError
│   │   │   └── ir_ui_menu_plugin.js  # IrMenuPlugin.getIrMenu() by ID or XML ID
│   │   ├── components/
│   │   │   └── share_button/
│   │   │       └── share_button.js   # waitForDataLoaded → freezeOdooData → exportXLSX
│   │   ├── helpers/
│   │   │   ├── model.js              # createSpreadsheetModel, fetchSpreadsheetModel, waitForOdooSources
│   │   │   └── odoo_functions_helpers.js  # extractDataSourceId for autocomplete
│   │   ├── actions/
│   │   │   └── spreadsheet_download_action.js  # downloadSpreadsheet()
│   │   └── assets_backend/
│   │       └── spreadsheet_action_loader.js  # addSpreadsheetActionLazyLoader
│   └── lib/
│       ├── chartjs-chart-geo/chartjs-chart-geo.js
│       └── chart_js_treemap.js
└── tests/
    ├── test_currency.py
    ├── test_currency_rate.py
    ├── test_display_names.py
    ├── test_ir_model.py
    ├── test_locale.py
    ├── test_session_info.py
    └── test_utils.py
```

---

## L1 — Models and Field Definitions

### Core: `spreadsheet.mixin`

```python
class SpreadsheetMixin(models.AbstractModel):
    _name = 'spreadsheet.mixin'
    _description = "Spreadsheet mixin"
    _auto = False   # No database table — only adds fields/methods to inheriting models
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `spreadsheet_binary_data` | Binary | Base64-encoded JSON document. Default: `_empty_spreadsheet_data_base64()`. Stored indirectly via `ir.attachment`. |
| `spreadsheet_data` | Text | Decoded JSON string. Compute/inverse pair with `spreadsheet_binary_data`. |
| `spreadsheet_file_name` | Char | Computed: `{display_name}.osheet.json`. |
| `thumbnail` | Binary | Thumbnail image for list view preview. |

#### RPC Methods

**`get_display_names_for_spreadsheet(args)`** — `@api.readonly`, `@api.model`

Batch RPC: fetch display names for many model/id pairs. Input is `[{model, id}]`. Returns display names in the **same order as input** (critical for formula resolution). Uses `active_test=False`.

```python
# Server receives:
[{"model": "res.partner", "id": 1}, {"model": "product.product", "id": 42}]
# Server returns (preserving order):
["Partner A", "Product X"]
```

**`_check_spreadsheet_data()`** — `@api.constrains("spreadsheet_binary_data")`

Validates JSON parseability and (in test mode) field chain / menu XML ID validity. Raises `ValidationError` with a newline-joined list of all errors found.

**`_empty_spreadsheet_data()`**

Returns the empty workbook template:
```python
{
    "sheets": [{"id": "sheet1", "name": _("Sheet1")}],
    "settings": {"locale": locale},
    "revisionId": "START_REVISION",
}
```

The sheet name is translated via `_()` so all users share the same sheet name — critical for cross-user formula references like `=Sheet1!A1`.

**`_zip_xslx_files(files)`**

Packs a list of `{path, content}` or `{path, imageSrc}` entries into a ZIP (DEFLATED). Image paths are either inline base64 (`data:image/png;base64,...`) or `/web/image/<id>` resolved via `ir.binary`.

---

### `ir.http` Extension

```python
class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super().session_info()
        res["can_insert_in_spreadsheet"] = False  # Disabled by default; enabled by other modules
        return res
```

Other modules (e.g., `spreadsheet_dashboard`) override this to set `can_insert_in_spreadsheet = True`, which controls whether the web client shows the "Insert in Spreadsheet" contextual action.

---

### `ir.model` Extension

```python
class IrModel(models.Model):
    _inherit = "ir.model"

    @api.readonly
    @api.model
    def has_searchable_parent_relation(self, model_names):
        result = {}
        for model_name in model_names:
            model = self.env.get(model_name)
            if model is None or not model.has_access("read"):
                result[model_name] = False
            else:
                result[model_name] = model._parent_store and model._parent_name in model._fields
        return result
```

Returns for which models a stored parent relationship should be traversed during spreadsheet field chain resolution. Only returns `True` if: (1) the model exists, (2) the current user has read access, (3) the model has `_parent_store = True` and `_parent_name` is a real field.

---

### `res.currency` Extension

```python
class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.readonly
    @api.model
    def get_company_currency_for_spreadsheet(self, company_id=None):
        company = self.env["res.company"].browse(company_id) if company_id else self.env.company
        if not company.exists():
            return False
        currency = company.currency_id
        return {
            "code": currency.name,
            "symbol": currency.symbol,
            "decimalPlaces": currency.decimal_places,
            "position": currency.position,
        }
```

---

### `res.currency.rate` Extension

```python
class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    @api.model
    def _get_rate_for_spreadsheet(self, currency_from_code, currency_to_code,
                                  date=None, company_id=None):
        if not currency_from_code or not currency_to_code:
            return False
        Currency = self.env["res.currency"].with_context({"active_test": False})
        currency_from = Currency.search([("name", "=", currency_from_code)])
        currency_to = Currency.search([("name", "=", currency_to_code)])
        if not currency_from or not currency_to:
            return False
        company = self.env["res.company"].browse(company_id) if company_id else self.env.company
        date = fields.Date.from_string(date) if date else fields.Date.context_today(self)
        return Currency._get_conversion_rate(currency_from, currency_to, company, date)

    @api.readonly
    @api.model
    def get_rates_for_spreadsheet(self, requests):
        result = []
        for request in requests:
            record = request.copy()
            record.update({"rate": self._get_rate_for_spreadsheet(**request)})
            result.append(record)
        return result
```

`get_rates_for_spreadsheet` is the batch RPC method. It deduplicates identical requests server-side (via `ListRequestBatch` on the JS side) and returns results preserving input order.

---

### `res.lang` Extension

```python
class ResLang(models.Model):
    _inherit = "res.lang"

    @api.readonly
    @api.model
    def get_locales_for_spreadsheet(self):
        langs = self.with_context(active_test=False).search([])
        return [lang._odoo_lang_to_spreadsheet_locale() for lang in langs]

    @api.model
    def _get_user_spreadsheet_locale(self):
        lang = self._lang_get(self.env.user.lang or 'en_US')
        return lang._odoo_lang_to_spreadsheet_locale()

    def _odoo_lang_to_spreadsheet_locale(self):
        return {
            "name": self.name,
            "code": self.code,
            "thousandsSeparator": self.thousands_sep,
            "decimalSeparator": self.decimal_point,
            "dateFormat": strftime_format_to_spreadsheet_date_format(self.date_format),
            "timeFormat": strftime_format_to_spreadsheet_time_format(self.time_format),
            "formulaArgSeparator": ";" if self.decimal_point == "," else ",",
            "weekStart": int(self.week_start),
        }
```

The `formulaArgSeparator` is the critical detail: European locales (decimal point = `,`) use semicolon `;` in formulas; US locales use comma `,`.

---

## L2 — Storage Architecture, Computed/Inverse, RPC Batching

### Storage Architecture: `ir.attachment` Backing Store

`spreadsheet_binary_data` is **NOT stored directly on the mixin's table**. The mixin has `_auto = False` — it contributes fields and methods to inheriting models but creates no table of its own. The actual binary storage uses `ir.attachment` as a virtual foreign key:

```
spreadsheet_data (Text field on inheriting model's table)
       │
       │  _inverse_spreadsheet_data()
       ↓
spreadsheet_binary_data (Binary field on inheriting model's table)
       │
       │  Stored in ir.attachment record:
       │    res_model = 'inheriting.model.name'
       │    res_field = 'spreadsheet_binary_data'
       │    res_id    = spreadsheet.id
       ↓
ir.attachment table (separate table, enables FTS and ACL)
```

**Why `ir.attachment` backing?**
- Full-text search on spreadsheet content via the attachment table
- Standard access control (read/write based on `ir.attachment` ACL, not the mixin's table schema)
- Efficient lazy loading — data fetched only when the `spreadsheet_data` Text field is accessed

### Computed/Inverse Pair

**Read (compute):**
```python
@api.depends("spreadsheet_binary_data")
def _compute_spreadsheet_data(self):
    attachments = self.env['ir.attachment'].with_context(bin_size=False).search([
        ('res_model', '=', self._name),
        ('res_field', '=', 'spreadsheet_binary_data'),
        ('res_id', 'in', self.ids),
    ])
    data = {attachment.res_id: attachment.raw for attachment in attachments}
    for spreadsheet in self:
        spreadsheet.spreadsheet_data = data.get(spreadsheet.id, False)
```

Note: `_compute_spreadsheet_data` runs on the mixin's class, so `self._name` inside the method refers to whatever inheriting model is in the recordset.

**Write (inverse):**
```python
def _inverse_spreadsheet_data(self):
    for spreadsheet in self:
        if not spreadsheet.spreadsheet_data:
            spreadsheet.spreadsheet_binary_data = False
        else:
            spreadsheet.spreadsheet_binary_data = base64.b64encode(
                spreadsheet.spreadsheet_data.encode()
            )
```

When `spreadsheet_binary_data` changes, Odoo's ORM automatically creates or updates the corresponding `ir.attachment` record because the field name matches.

### RPC Batch Method Pattern

The batch RPC pattern used throughout this module:

```python
# Python side: receives a LIST of request objects
@api.readonly
@api.model
def get_rates_for_spreadsheet(self, requests):
    return [self._get_rate_for_spreadsheet(**req) for req in requests]

# JS side: ListRequestBatch deduplicates and batches identical requests
class ListRequestBatch {
    get payload() {
        // Flattens and deduplicates all request args
        return [removeDuplicates(this.requests.map(r => r.args).flat())];
    }
    splitResponse(results) { /* maps results back to requests */ }
}
```

---

## L3 — Validation, Field Chains, Odoo Data Sources

### `_check_spreadsheet_data()` — Constraint Validation

```python
@api.constrains("spreadsheet_binary_data")
def _check_spreadsheet_data(self):
    for spreadsheet in self.filtered("spreadsheet_binary_data"):
        try:
            data = json.loads(base64.b64decode(spreadsheet.spreadsheet_binary_data).decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValidationError(_("Invalid data"))

        if not (tools.config['test_enable'] or tools.config['test_file']):
            continue  # SKIPPED in production

        if data.get("[Content_Types].xml"):
            continue  # XLSX file — skip field chain validation

        # Validate field chains and menu XML IDs...
```

**Key behavior:** Validation runs **only in test mode** (`test_enable` or `test_file` config flags). In production, only JSON parse validity is checked. This prevents performance impact on every save.

### `validate_data.py` — Field Chain Extraction

| Function | Purpose |
|----------|---------|
| `fields_in_spreadsheet(data)` | Returns `{model_name: Set[field_names]}` for all Odoo data sources |
| `pivot_fields(pivot)` | Extracts from pivot definition (colGroupBys/columns, rowGroupBys/rows, measures, domain) |
| `list_fields(list_def)` | Extracts from list/readsheet definition (columns, orderBy, domain) |
| `chart_fields(chart)` | Extracts from chart definition (groupBy, measure, domain) |
| `filter_fields(data)` | Extracts from global filter definitions (handles version migration) |
| `odoo_view_fields(view)` | Extracts from embedded view action links |
| `odoo_view_links(data)` | Parses `odoo://view/{...}` markdown URLs in cells |
| `odoo_charts(data)` | Returns all Odoo chart figures (type starts with `odoo_`) including carousel charts |
| `links_urls(data)` | Extracts all markdown link URLs from cells |
| `menus_xml_ids_in_spreadsheet(data)` | Returns menu XML IDs from `chartOdooMenusReferences` and `odoo://ir_menu_xml_id/` links |

#### Version Migration: `odooVersion < 5`

The `filter_fields()` function branches on `data["odooVersion"]`:

```
odooVersion < 5 (old format):
  globalFilters[].pivotFields     → pivot_id → {field}
  globalFilters[].listFields      → list_id  → {field}
  globalFilters[].graphFields     → chart_id → {field}

odooVersion >= 5 (new format):
  pivots[].fieldMatching.chain    → field chain
  lists[].fieldMatching.chain     → field chain
  charts[].fieldMatching.chain    → field chain
```

The `pivot_measure_fields()` function also handles the `"field"` → `"name"` → `"fieldName"` key rename across versions.

#### Measure Field Extraction

```python
def pivot_measure_fields(pivot):
    measures = [
        measure if isinstance(measure, str)
        else measure["field"] if "field" in measure
        else measure["name"] if "name" in measure
        else measure["fieldName"]
        for measure in pivot["measures"]
        if "computedBy" not in measure  # Skip computed/measures
    ]
    return [m for m in measures if m != "__count"]
```

---

## L4 — Performance, Plugin Architecture, Odoo 19 Changes, JS Architecture

### Performance: `ir.attachment` Lazy Loading

The `_compute_spreadsheet_data()` method searches attachments matching only the current recordset's IDs:

```python
('res_id', 'in', self.ids)
```

This avoids loading all attachments for the model at once. For models with thousands of spreadsheet records, this is critical — only the accessed records load their attachment.

### Performance: Batch RPC Deduplication

`ListRequestBatch.payload` deduplicates identical request args before sending:

```javascript
get payload() {
    const payload = removeDuplicates(this.requests.map(r => r.args).flat());
    return [payload];
}
```

Two cells referencing the same currency rate on the same date produce **one RPC**, not two.

### Plugin Architecture (`index.js`)

Three registries from `@odoo/o-spreadsheet` are populated:

#### `corePluginRegistry` (7 plugins — business logic)

| Key | Class | Responsibility |
|-----|-------|---------------|
| `OdooGlobalFiltersCorePlugin` | `GlobalFiltersCorePlugin` | Global filter state, evaluation |
| `PivotOdooCorePlugin` | `PivotOdooCorePlugin` | Odoo pivot definition, metadata |
| `OdooPivotGlobalFiltersCorePlugin` | `PivotCoreGlobalFilterPlugin` | Pivot-filter integration |
| `OdooListCorePlugin` | `ListCorePlugin` | Odoo list definition |
| `OdooListCoreGlobalFilterPlugin` | `ListCoreGlobalFilterPlugin` | List-filter integration |
| `odooChartCorePlugin` | `OdooChartCorePlugin` | Odoo chart definition |
| `chartOdooMenuPlugin` | `ChartOdooMenuPlugin` | Menu-to-chart linkage |

#### `coreViewsPluginRegistry` (4 plugins — UI/view logic)

| Key | Class |
|-----|-------|
| `OdooGlobalFiltersCoreViewPlugin` | `GlobalFiltersCoreViewPlugin` |
| `OdooPivotGlobalFiltersCoreViewPlugin` | `PivotCoreViewGlobalFilterPlugin` |
| `OdooListCoreViewPlugin` | `ListCoreViewPlugin` |
| `OdooChartCoreViewPlugin` | `OdooChartCoreViewPlugin` |

#### `featurePluginRegistry` (5 plugins — user-facing features)

| Key | Class |
|-----|-------|
| `OdooPivotGlobalFilterUIPlugin` | `PivotUIGlobalFilterPlugin` |
| `OdooGlobalFiltersUIPlugin` | `GlobalFiltersUIPlugin` |
| `odooPivotUIPlugin` | `PivotOdooUIPlugin` |
| `odooListUIPlugin` | `ListUIPlugin` |
| `OdooChartFeaturePlugin` | `OdooChartFeaturePlugin` |

#### `globalFieldMatchingRegistry` (filter integration per data source type)

Each entry provides getters for filter-to-data-source field matching:

```javascript
globalFieldMatchingRegistry.add("pivot", {
    getIds: (getters) => getters.getPivotIds().filter(
        (id) => getters.getPivotCoreDefinition(id).type === "ODOO" &&
               getters.getPivotFieldMatch(id)
    ),
    getFieldMatching: (getters, pivotId, filterId) =>
        getters.getPivotFieldMatching(pivotId, filterId),
    getModel: (getters, pivotId) => getters.getPivot(pivotId).model,
    waitForReady: (getters) =>
        getters.getPivotIds()
            .map(id => getters.getPivot(id))
            .filter(p => p.type === "ODOO")
            .map(p => p.loadMetadata()),
    // ...
});

globalFieldMatchingRegistry.add("list", { /* ... */ });
globalFieldMatchingRegistry.add("chart", { /* ... */ });
```

### OdooDataProvider / ServerData / BatchEndpoint

```
Spreadsheet Cell referencing Odoo data
       │
       ↓
OdooDataProvider.get() or .batch.get()
       │
       ├── Cache hit? → return cached value
       │
       └── Cache miss? → throw LoadingDataError (sentinel)
                   │
                   ↓
              ServerData.get() or ServerData.batch.get()
                   │
                   ├── Individual: orm.call() directly
                   │                   │
                   │                   └── Cache result, throw LoadingDataError
                   │
                   └── Batched: BatchEndpoint._scheduleNextBatch()
                                   │
                                   ├── queueMicrotask (microtask-level batching)
                                   │
                                   └── orm.call(model, method, [deduplicated_payload])
                                               │
                                    ┌──────────┴──────────┐
                                    ↓                     ↓
                               Success?              Failure?
                                    ↓                     ↓
                           splitResponse()      _retryOneByOne()
                           update cache         individual orm.call()
                           notify OdooDataProvider
                                   │
                                   ↓
                          data-source-updated event
                          (or 10s timeout → force update)
```

**`OdooDataProvider`** extends `EventBus`. It wraps `ServerData` and tracks pending promises. When a `data-source-updated` event fires, all dependent cells re-evaluate. If data is still loading after 10 seconds, it forces an update anyway.

**`BatchEndpoint`** schedules batches via `queueMicrotask`, which fires before the next macrotask (e.g., before a frame render). If the batch RPC fails, it falls back to `_retryOneByOne()` — firing individual RPCs for each request and resolving with errors for failed ones.

### Data Source Classes

All Odoo data sources follow a hierarchy:

```
LoadableDataSource (o-spreadsheet base)
    └── OdooViewsDataSource (common Odoo-specific logic)
        ├── ListDataSource  (type: "ODOO.LIST")
        ├── OdooPivot       (type: "ODOO.PIVOT")
        └── ChartDataSource (type: "odoo_*")
```

`OdooPivot` has a nested `OdooPivotRuntimeDefinition` that extends `PivotRuntimeDefinition` from o-spreadsheet. It auto-sets granularity for date/datetime fields that lack granularity in the definition.

### Chart Subtypes

14 Odoo-specific chart subtypes registered in `chartSubtypeRegistry`:

| Subtype | Base Type | Category |
|---------|-----------|----------|
| `odoo_line` | odoo_line | line |
| `odoo_stacked_line` | odoo_line | line |
| `odoo_area` | odoo_line | area |
| `odoo_stacked_area` | odoo_line | area |
| `odoo_bar` | odoo_bar | column |
| `odoo_stacked_bar` | odoo_bar | column |
| `odoo_horizontal_bar` | odoo_bar | bar |
| `odoo_horizontal_stacked_bar` | odoo_bar | bar |
| `odoo_combo` | odoo_combo | line |
| `odoo_pie` | odoo_pie | pie |
| `odoo_doughnut` | odoo_pie | pie |
| `odoo_scatter` | odoo_scatter | misc |
| `odoo_waterfall` | odoo_waterfall | misc |
| `odoo_pyramid` | odoo_pyramid | misc |
| `odoo_radar` | odoo_radar | misc |
| `odoo_filled_radar` | odoo_radar | misc |
| `odoo_geo` | odoo_geo | misc |
| `odoo_funnel` | odoo_funnel | misc |
| `odoo_treemap` | odoo_treemap | hierarchical |
| `odoo_sunburst` | odoo_sunburst | hierarchical |

### Locale System and Date Epoch

`formatting.py` defines two conversion functions:

```python
INITIAL_1900_DAY = datetime(1899, 12, 30)  # Excel-compatible epoch
SECONDS_PER_DAY = 86400

def date_to_spreadsheet_date_number(d):
    dt = datetime.combine(d, datetime.min.time())
    return (dt.timestamp() - INITIAL_1900_DAY.timestamp()) / SECONDS_PER_DAY
    # Note: no timezone offset for pure date

def datetime_to_spreadsheet_date_number(dt, tz_name):
    context_tz = pytz.timezone(tz_name)
    localized = dt.astimezone(context_tz)
    offset = localized.utcoffset() / timedelta(seconds=1)
    return (dt.timestamp() + offset) / SECONDS_PER_DAY
    # Note: timezone offset IS applied for datetime
```

**Why the difference?** A pure date has no time component, so the midnight-in-UTC interpretation is stable across timezones. A datetime's interpretation depends on the user's timezone, so the offset is explicitly added.

### Odoo Spreadsheet JS Engine Integration

The o-spreadsheet engine (`@odoo/o-spreadsheet` npm package, version **19.0.21**, hash `e804d77b7`) is wrapped by `odoo_module.js`:

```javascript
import * as spreadsheet from "@odoo/o-spreadsheet";
window.o_spreadsheet = spreadsheet;
spreadsheet.helpers.installTranslator((term) => _t(term));
```

This exposes `window.o_spreadsheet` and installs Odoo's translation function into o-spreadsheet's helper registry. The `TranslationNamespace` plugin then uses `appTranslateFn` to bridge Odoo i18n (`.po` files) into spreadsheet dynamic translation.

### Share Button: Snapshot Creation

When sharing a spreadsheet (read-only public link):

```javascript
// share_button.js
onOpened() {
    return waitForDataLoaded(model)        // Wait all data sources
        .then(() => freezeOdooData(model))  // Snapshot current data values
        .then(() => model.exportXLSX())      // Generate XLSX snapshot
        .then(xlsx => onSpreadsheetShared(data, xlsx))
}
```

`freezeOdooData()` walks all data sources and snapshots their current values into the spreadsheet JSON. This creates a **static snapshot** — no live data, no revision tracking, no formulas. The XLSX is then uploaded and a public URL is generated.

### `addSpreadsheetActionLazyLoader`

The backend spreadsheet action (triggered from menu or action button) uses lazy asset loading:

```javascript
// spreadsheet_action_loader.js
addSpreadsheetActionLazyLoader();
// Web client sees the lazy loader first, loads spreadsheet.o_spreadsheet bundle,
// then executes the real action. The full bundle (~MBs) is not loaded for every page.
```

This is wired into `web.assets_backend` in `__manifest__.py`.

### Version Migration: JS Side (`migration.js`)

Two migration steps are registered:

**`17.3.1`** — v1 function name renaming (Odoo 17 era):
```
PIVOT       → ODOO.PIVOT
PIVOT.HEADER → ODOO.PIVOT.HEADER
LIST        → ODOO.LIST
FILTER.VALUE → ODOO.FILTER.VALUE
```

**`18.1.2`** — field chain migration based on `odooVersion`:
```javascript
if (odooVersion < 13) {
    // Run field chain migration (changes how field matching is stored)
}
```

### JSON Utility

`json.py` provides `extend_serialized_json(json, key_value_pairs)`:

```python
extend_serialized_json('{"a": 1}', [('key', '"value"')])
# → '{"a": 1,"key":"value"}'
```

Values must already be serialized strings. This avoids re-parsing and re-serializing large JSON documents when appending metadata.

### Asset Bundles

Six asset bundles defined in `__manifest__.py`:

| Bundle | Load Point | Contents |
|--------|-----------|----------|
| `web.chartjs_lib` | web dependency | chartjs-chart-geo, chartjs treemap |
| `spreadsheet.o_spreadsheet` | backend action | Full editor: o_spreadsheet + all plugins + graph/pivot models |
| `spreadsheet.public_spreadsheet` | public portal | Read-only viewer: subset of assets + public_readonly_app |
| `spreadsheet.assets_print` | print mode | Print/PDF assets |
| `web.assets_backend` | backend | SCSS + assets_backend |
| `web.assets_unit_tests` | test mode | All test files + full o_spreadsheet |

The `spreadsheet.o_spreadsheet` bundle uses `('remove', ...)` to exclude `assets_backend` and `public_readonly_app` assets — those are loaded separately as needed.

### Error Sentinels (`errors.js`)

```javascript
export const LOADING_ERROR = "Loading...";
export class LoadingDataError extends EvaluationError {}
export function isLoadingError({ value }) {
    return value && value.value === LOADING_ERROR;
}
```

Cells holding unresolved data sources display `"Loading..."` and throw `LoadingDataError`. This is caught by the spreadsheet engine's error handling and rendered as a loading state rather than a `#ERROR`.

### Odoo 18 to 19 Changes

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| `spreadsheet_binary_data` storage | In mixin table (theoretical) | Via `ir.attachment` backing |
| `validate_data.py` old keys | `pivotFields`, `listFields`, `graphFields` only | Added `odooVersion < 5` branch |
| Pivot measure keys | `field` | Added `name` → `fieldName` migration |
| `session_info` flag | `can_insert_in_spreadsheet` | Same |
| `has_searchable_parent_relation` | Odoo 16+ | Same |
| `ir.http` override | Sets flag to `False` | Same |
| Batch RPC (`get_rates_for_spreadsheet`) | Single requests | Deduplicated batch |
| o_spreadsheet version | ~18.x | 19.0.21 |
| Chart subtypes | Fewer | 14+ subtypes including geo, funnel, pyramid |

### Odoo Spreadsheet Formula Reference

| Formula | Module | Purpose |
|---------|--------|---------|
| `=ODOO.PIVOT(id, measure)` | `spreadsheet` | Get cell value from Odoo pivot |
| `=ODOO.PIVOT.HEADER(id, ...)` | `spreadsheet` | Get header label from pivot |
| `=ODOO.LIST(id, index, field)` | `spreadsheet` | Get cell value from Odoo list |
| `=ODOO.LIST.HEADER(id, field)` | `spreadsheet` | Get column header from list |
| `=ODOO.CHART(id)` | `spreadsheet` | Reference an Odoo chart |
| `=ODOO.CURRENCY.RATE(from, to, date)` | `spreadsheet_account` | Live exchange rate |
| `=ODOO.FILTER.VALUE(filter_id)` | `spreadsheet` | Current value of a global filter |

---

## Related Documentation

- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard templates using `spreadsheet.mixin`
- [Modules/spreadsheet_account](Modules/spreadsheet_account.md) — Accounting data source and currency formulas
- [Core/API](Core/API.md) — `@api.model` RPC methods, `@api.constrains`, `@api.depends`
- [Core/Fields](Core/Fields.md) — Binary field storage, computed/inverse pattern
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Collaboration patterns via `bus` module
- [Modules/bus](Modules/bus.md) — WebSocket real-time collaboration
