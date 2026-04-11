# Module: web_studio

## Overview

| Property | Value |
|----------|-------|
| **Name** | Studio |
| **Module** | `web_studio` |
| **Type** | Enterprise-only (`OEEL-1` license) |
| **Location** | `enterprise/suqma-19.0-20250204/enterprise/web_studio/` |
| **Version** | `1.0` |
| **Category** | `Customizations/Studio` |
| **Sequence** | 75 |
| **License** | `OEEL-1` (Odoo Enterprise Edition License) |
| **Application** | `True` |

`web_studio` is the **client-side** (backend + frontend) of Odoo Studio, the no-code visual app builder and customizer in Odoo Enterprise. It provides the visual tools to create new apps, edit views, configure approvals, and export customizations as installable modules.

> **Note on paths:** In this project, `web_studio` is Enterprise-only. The canonical path is `enterprise/*/web_studio/`. The Community Edition path `odoo/addons/web_studio/` does not exist.

---

## Dependencies

### Hard Dependencies
- `base_automation` -- server actions and automation rules
- `base_import_module` -- module import/export
- `mail` -- messaging (chatter, activities)
- `web` -- web framework
- `web_enterprise` -- Enterprise web features
- `html_editor` -- rich text editing (Odoo 18+)
- `web_editor` -- WYSIWYG editing
- `web_map` -- map view
- `web_gantt` -- Gantt view
- `web_cohort` -- cohort view
- `sms` -- SMS integration

### Security
Only the **admin user** (or users with `base.group_system`) can use Studio features. The module enforces `auth='user'` on all its JSON-RPC endpoints. The export (`/web_studio/export`) additionally checks `request.env.is_admin()`.

---

## Directory Structure

```
web_studio/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── export.py              -- ZIP archive generation (StudioExporter)
│   ├── ir_http.py             -- background image serving
│   ├── keyed_xml_differ.py    -- view normalization diff engine
│   ├── main.py                -- WebStudioController (all JSON-RPC endpoints)
│   ├── report.py              -- report view copy helpers
│   └── xml_resource_editor.py  -- raw XML editor
├── models/
│   ├── __init__.py
│   ├── base.py               -- base get_views override + StudioMixin.create_studio_model_data
│   ├── models.py             -- StudioMixin (create/write auto-tracking)
│   ├── studio_mixin.py        -- StudioMixin (L4: moved to separate file in 19)
│   ├── base_automation.py     -- thin wrapper: _inherit + StudioMixin
│   ├── ir_actions.py          -- thin wrapper: _inherit + StudioMixin
│   ├── ir_actions_act_window.py -- thin wrappers: ir.actions.act_window + ir.actions.act_window.view
│   ├── ir_actions_report.py   -- report rendering in studio context
│   ├── ir_actions_server.py   -- thin wrapper: _inherit + StudioMixin
│   ├── ir_default.py          -- thin wrapper: _inherit + StudioMixin
│   ├── ir_filters.py          -- thin wrapper: _inherit + StudioMixin
│   ├── ir_model.py            -- model creation wizard, OPTIONS_WL, field constraints
│   ├── ir_model_data.py       -- ir.model.data with studio flag
│   ├── ir_module_module.py    -- get_studio_module(), creates studio_customization
│   ├── ir_qweb.py             -- cache key + studio context in QWeb rendering
│   ├── ir_rule.py             -- thin wrapper: _inherit + StudioMixin
│   ├── ir_ui_menu.py          -- menu customization, configuration menu helper
│   ├── ir_ui_view.py          -- view studio context, automatic view generation
│   ├── mail_activity.py        -- approval activities hooked into _action_done
│   ├── mail_activity_type.py  -- thin wrapper: _inherit + StudioMixin
│   ├── mail_template.py        -- thin wrapper: _inherit + StudioMixin
│   ├── mail_thread.py          -- x_studio_partner_id in suggested recipients
│   ├── report_paperformat.py  -- thin wrapper: _inherit + StudioMixin
│   ├── res_company.py         -- background_image, default company fields
│   ├── res_groups.py          -- thin wrapper: _inherit + StudioMixin
│   ├── studio_approval.py      -- approval rule engine (5 models)
│   └── studio_export_model.py  -- export model configuration
├── wizard/
│   ├── __init__.py
│   ├── base_module_uninstall.py -- custom view/field counters in uninstall wizard
│   └── studio_export_wizard.py  -- full export wizard with topological sort
├── views/
│   ├── actions.xml
│   ├── assets.xml
│   ├── base_automation_views.xml
│   ├── ir_actions_report_xml.xml
│   ├── ir_model_data.xml
│   ├── reset_view_arch_wizard.xml
│   ├── studio_approval_views.xml
│   ├── studio_export_model_views.xml
│   └── studio_export_wizard_views.xml
├── security/
│   ├── ir.model.access.csv    -- ACLs for studio models
│   └── studio_security.xml    -- ir.rule for studio.approval.entry
├── data/
│   ├── mail_templates.xml
│   └── web_tour_tour.xml
└── static/src/                -- JS frontend (not analyzed in this doc)
```

---

## L1: Core Models

### 1.1 `base` (AbstractModel, `models/base.py` + `models/models.py`)

The `base` model is extended by two files working in tandem:

#### `base` in `models/base.py` -- StudioMixin Factory

This file defines two extensions on the `base` abstract model:

**`create_studio_model_data(name)`** -- attached to every Odoo model via the ORM registry:

```python
def create_studio_model_data(self, name):
    IrModelData = self.env['ir.model.data']
    data = IrModelData.search([
        ('model', '=', self._name), ('res_id', '=', self.id)
    ])
    if data:
        data.write({})  # force write to set studio + noupdate flags
    else:
        module = self.env['ir.module.module'].get_studio_module()
        IrModelData.create({
            'name': '%s_%s' % (sanitize_for_xmlid(name or 'False'), uuid.uuid4()),
            'model': self._name,
            'res_id': self.id,
            'module': module.name,
        })
```

> **L4 Note:** `sanitize_for_xmlid()` converts names to ASCII, lowercases, replaces spaces with underscores, and truncates to 20 characters. This prevents XML ID collisions but can produce duplicate names (e.g., "My Custom Model" and "My Custom Module" both sanitize to "my_custom_model"), hence the UUID suffix guarantees uniqueness.

**`fields_get()` override** -- In studio context, for `base.group_system` users only:

```python
def fields_get(self, allfields=None, attributes=None):
    if self.env.context.get('studio') and self.env.user.has_group('base.group_system'):
        return super(Base, self.sudo()).fields_get(allfields, attributes=attributes)
    return super().fields_get(allfields, attributes=attributes)
```

This means regular admin users (without `base.group_system`) do **not** see restricted fields in the Studio field selector.

#### `base` in `models/__init__.py` -- `get_views` Approval Integration

```python
class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    @api.readonly
    def get_views(self, views, options=None):
        result = super().get_views(views, options=options)
        related_models = result['models']
        self_sudo = self.sudo()
        read_group_result = self_sudo.env['studio.approval.rule']._read_group(
            [('model_name', 'in', tuple(related_models))],
            ['model_name'],
        )
        has_approval_rules = {model_name for [model_name] in read_group_result}
        for model_name in related_models:
            related_models[model_name]['has_approval_rules'] = model_name in has_approval_rules
        return result
```

> **L4 Note:** This augments the view rendering response with `has_approval_rules` per model. It runs `sudo()` on the rule query (read_group is batched, so this is efficient) to determine which models have approval rules, allowing the frontend to show/hide the approval button badge.

---

### 1.2 `StudioMixin` (`models/studio_mixin.py` + `models/models.py`)

> **L4 Change (Odoo 19):** The `StudioMixin` class was moved from `models/models.py` to its own file `models/studio_mixin.py`. The original `models/models.py` now re-exports it for backward compatibility.

The foundational mixin that **auto-tracks Studio-created records**.

```python
class StudioMixin(models.AbstractModel):
    _name = 'studio.mixin'
    _description = 'Studio Mixin'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if self.env.context.get('studio') and not self.env.context.get('install_mode'):
            for ob in res:
                ob.create_studio_model_data(ob.display_name)
        return res

    def write(self, vals):
        res = super(StudioMixin, self).write(vals)
        if self.env.context.get('studio') and not self.env.context.get('install_mode'):
            for record in self:
                record.create_studio_model_data(record.display_name)
        return res
```

**Trigger conditions:**
- `self.env.context.get('studio') == True` -- Studio is active
- `self.env.context.get('install_mode') == False` -- NOT during module installation (ORM auto-creates ir.model.data entries during install)

**L4: Why `install_mode` matters.** When a module is installed, Odoo's ORM auto-creates `ir.model.data` entries for all records created during installation. Suppressing Studio's own tracking during install avoids duplicate entries (one auto-created by ORM, one by StudioMixin).

**L4: display_name write bypass removed.** In Odoo 17, there was a performance optimization that short-circuited `write()` when only `display_name` was being updated and the field was not stored. This was removed in Odoo 18/19 -- the write always propagates now, which is important for `ir.model` and `ir.model.fields` where display_name writes from Studio could previously trigger unexpected registry rebuilds.

---

### 1.3 `studio.approval.rule` and Related Models (`models/studio_approval.py`)

Five cooperative models form the approval engine:

#### `studio.approval.rule` (main model)

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Enable/disable rule |
| `model_id` | Many2one `ir.model` | Target model |
| `method` | Char | Method name to intercept (e.g., `action_confirm`) |
| `action_id` | Many2one `ir.actions.actions` | Action to intercept |
| `action_xmlid` | Char (related, searchable) | XML ID of the action |
| `name` | Char | Rule display name |
| `message` | Char (translate) | Step description shown on the approval button |
| `approver_ids` | Many2many `res.users` (compute/inverse) | Users who can approve |
| `approver_log_ids` | One2many `studio.approval.rule.approver` | Delegation log |
| `approval_group_id` | Many2one `res.groups` | Group whose members can approve |
| `users_to_notify` | Many2many `res.users` | Users notified on approval/rejection |
| `notification_order` | Selection (1-9) | Sequential step order |
| `exclusive_user` | Boolean | One approver cannot approve other rules for same record |
| `model_name` | Char (related, stored, indexed) | Denormalized model name for perf |
| `domain` | Char | Domain filter for rule applicability |
| `conditional` | Boolean (computed) | True if domain is set |
| `can_validate` | Boolean (computed, uid-dependent) | Current user can approve |
| `kanban_color` | Integer (computed) | 7 if can_validate else 0 |
| `entry_ids` | One2many `studio.approval.entry` | Approval entries for this rule |
| `entries_count` | Integer (computed) | Number of entries |

**SQL Constraints:**
```python
_method_or_action_together = models.Constraint(
    'CHECK(method IS NULL OR action_id IS NULL)',
    "A rule must apply to an action or a method (but not both).",
)
_method_or_action_not_null = models.Constraint(
    'CHECK(method IS NOT NULL OR action_id IS NOT NULL)',
    "A rule must apply to an action or a method.",
)
```

**API Constraints (`@api.constrains`):**
- Method cannot be private (`startswith('_')`) or contain `__`
- Method must exist and be callable on the target model
- `create`, `write`, `unlink` are forbidden (compatibility with `base_automation`)
- Rule cannot target itself (`model_id.model == 'studio.approval.rule'`)

**L4: `_base_automation_data_for_model()` -- Sale/PO/Invoice special handling.** This method returns `trigger: 'on_state_set'` for `sale.order`, `account.move`, and `purchase.order`. The trigger activates when the state field changes, with a pre-filter `state != 'draft'`, meaning the rule fires on the transition *away from draft*. This is the standard "confirm" approval pattern.

#### `studio.approval.rule.approver`

Tracks delegation of approval rights and their validity windows.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | Many2one `res.users` | Delegated approver |
| `rule_id` | Many2one `studio.approval.rule` (cascade) | Parent rule |
| `date_to` | Date | Delegation expiry (nullable) |
| `is_delegation` | Boolean (default=True) | True=delegation, False=original assignment |

**`_is_valid()`**: `not self.date_to or self.date_to >= today`
**`_filtered_valid()`**: returns only currently-valid approvers

**L4: Delegation expiration.** When `_delegate_to()` is called, it deletes existing delegations created by the current user (`create_uid == uid AND is_delegation == True`) and creates new delegation records with the given `date_to`. This means a user can only have one active delegation at a time (the new delegation overwrites the old one for that user).

#### `studio.approval.entry`

Tracks per-record approval decisions.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | Many2one `res.users` (default=current user) | Approver/rejecter |
| `rule_id` | Many2one `studio.approval.rule` (cascade) | Parent rule |
| `model` | Char (related stored) | Denormalized model name |
| `method` | Char (related stored) | Denormalized method name |
| `action_id` | Many2one `ir.actions.actions` (related stored) | Denormalized action |
| `res_id` | Many2oneReference | Record ID being approved |
| `reference` | Char (computed) | `"model,res_id"` string |
| `name` | Char (computed stored) | `"UserName - model(res_id)"` |
| `approved` | Boolean | True=approved, False=rejected |

**SQL Constraints:**
```python
_uniq_combination = models.Constraint(
    'unique(rule_id, model, res_id)',
    "A rule can only be approved/rejected once per record.",
)
_model_res_id_idx = models.Index("(model, res_id)")
```

**L4: `studio.approval.entry` does NOT inherit `StudioMixin`.** The comment in the source explicitly states: "entries don't have the studio mixin since they depend on the data of the db - they cannot be included into the Studio Customizations module." Entries are runtime data and should never be exported as part of a Studio customization module.

#### `studio.approval.request`

Tracks open mail activity requests for approvals.

| Field | Type | Description |
|-------|------|-------------|
| `mail_activity_id` | Many2one `mail.activity` (cascade) | Linked activity |
| `rule_id` | Many2one `studio.approval.rule` (cascade) | Parent rule |
| `res_id` | Many2oneReference | Record ID being requested |

**Inverse:** `mail_activity.studio_approval_request_id` points back, allowing the activity to know its approval request context.

#### `studio.approval.rule.delegate` (TransientModel)

Wizard for delegating approval rights.

| Field | Type | Description |
|-------|------|-------------|
| `approval_rule_id` | Many2one `studio.approval.rule` | Rule to delegate |
| `approver_ids` | Many2many `res.users` | Delegated approvers |
| `users_to_notify` | Many2many `res.users` | Additional notifiees |
| `date_to` | Date | Delegation expiry |

---

### 1.4 `studio.export.model` (`models/studio_export_model.py`)

Configures which models are included in the module export.

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Export order |
| `model_id` | Many2one `ir.model` | Model to export (domain: non-transient, non-abstract) |
| `model_name` | Char (related stored) | Model technical name |
| `excluded_fields` | Many2many `ir.model.fields` | Fields to skip (computed readonly) |
| `domain` | Text | Filter records to export (default `"[]"`) |
| `records_count` | Char (computed) | Count of matching records |
| `is_demo_data` | Boolean | Mark records as demo data during import |
| `updatable` | Boolean | Allow update on module upgrade |
| `include_attachment` | Boolean | Include related attachments |

**SQL Constraint:** `unique(model_id)` -- each model only appears once.

**L4: `_compute_excluded_fields()` Logic (complex).** This method builds the exclusion set through three layers:

1. **Preset per-model exclusions** (`DEFAULT_FIELDS_TO_EXCLUDE`): e.g., `sale.order` excludes all financial fields, `res.partner` excludes commercial computed fields, `product.product` excludes variant image sizes.

2. **Abstract model exclusions** (`ABSTRACT_MODEL_FIELDS_TO_EXCLUDE`): Iterates the model's `_base_classes__` chain to find abstract mixins (e.g., `mail.thread`, `avatar.mixin`, `image.mixin`) and excludes their known problematic fields.

3. **Runtime field scanning**: Excludes computed (non-stored non-inverse) fields, related fields pointing to excluded models, `one2many` fields, `l10n_*` module fields, and `many2x` fields whose comodel is in `RELATED_MODELS_TO_EXCLUDE` (all `account.*` models).

**L4: Preset models (`PRESET_MODELS_DEFAULTS`) -- 65+ models.** Includes all common Odoo models with pre-configured export settings. Notably, `account.move` is **absent** from this list (financial data must not be exported). `sale.order` and `purchase.order` use domain filters to exclude draft/cancel records.

---

### 1.5 `ir.model` Extension (`models/ir_model.py`)

`OPTIONS_WL` -- 13 model creation options:

| Option | Fields Created | Notes |
|--------|---------------|-------|
| `use_mail` | Enables `mail_thread` + `mail_activity` on model | Enables chatter + activities |
| `use_active` | `x_active` (boolean) | Note: cannot use `x_studio_active` -- not supported by ORM |
| `use_responsible` | `x_studio_user_id` (many2one res.users, domain: `share=False`) | Tracks, with `tracking=True` |
| `use_partner` | `x_studio_partner_id` + `x_studio_partner_phone` (related) + `x_studio_partner_email` (related) | Related fields are NOT stored |
| `use_company` | `x_studio_company_id` (many2one res.company) | Creates multi-company `ir.rule`; sets defaults per company |
| `use_notes` | `x_studio_notes` (html) | |
| `use_date` | `x_studio_date` (date) | |
| `use_double_dates` | `x_studio_date_stop` (datetime) + `x_studio_date_start` (datetime) | |
| `use_value` | `x_studio_currency_id` (many2one res.currency) + `x_studio_value` (monetary) | Sets defaults per company |
| `use_image` | `x_studio_image` (binary) | |
| `use_sequence` | `x_studio_sequence` (integer, handle widget) | Sets default order; sets default value `10` |
| `use_stages` | Full stage model + `x_studio_stage_id` + `x_studio_priority` + `x_color` + `x_studio_kanban_state` | Creates stage model with 3 default stages; `on_delete='restrict'` |
| `use_tags` | Full tag model + `x_studio_tag_ids` (many2many) | Tag model includes `x_color` |
| `lines` | One2many pointing to auto-generated line model | Creates line model with `x_studio_sequence` + `x_name` + many2one back-ref |

**Key methods:**

- **`studio_model_create(name, options)`**: Main model creation pipeline. Calls `_create_option_*` for each option, then `_post_create_option_*` (after `_setup_access_rights()` and `create_automatic_views()`).
- **`_setup_access_rights()`**: Creates two `ir.model.access` records -- full access to `base.group_system`, read/write/create (no unlink) to `base.group_user`.
- **`_create_default_action(name)`**: Creates `ir.actions.act_window` with sorted view modes.
- **`studio_model_infos(model_name)`**: Returns model metadata + up to 10 record IDs for preview.

**L4: `use_active` uses `x_active` not `x_studio_active`.** This is a deliberate ORM constraint -- the ORM does not support custom prefixes on the `active` field name. The `x_active` field follows Odoo's convention for "archivable" models.

**L4: `_create_option_use_stages` creates `on_delete='restrict'` on `x_studio_stage_id`.** This prevents accidentally deleting a stage that has records assigned to it. The default stage order is `id asc` (rather than sequence-based) to match the creation order of New/In Progress/Done.

---

### 1.6 `ir.ui.view` Extension (`models/ir_ui_view.py`)

Studio overrides 15+ methods on `ir.ui.view`:

| Method | Purpose |
|--------|---------|
| `_get_view_cache_key()` | Adds `studio` to cache key tuple |
| `_get_view_field_attributes()` | Adds `'manual'` to attributes in studio context |
| `get_views()` | Adds `studio=True` and `no_address_format=True` to context |
| `_postprocess_access_rights()` | Sets nodes `invisible` instead of deleting them in studio |
| `_postprocess_attributes()` | Preserves `groups` attribute through super() |
| `set_studio_groups()` | Converts XML ID-based groups to JSON for editor |
| `set_studio_map_popup_fields()` | Serializes map view field IDs for editor |
| `set_studio_pivot_measure_fields()` | Serializes pivot measure field IDs for editor |
| `create_automatic_views()` | Dispatches to `auto_*_view()` methods |
| `auto_list_view()` | Creates list view with smart field selection |
| `auto_form_view()` | Creates form with header, two-column group, chatter |
| `auto_search_view()` | Creates search with filters, groupbys, date filters |
| `auto_calendar_view()` | Calendar view for `x_studio_date` models |
| `auto_gantt_view()` | Gantt view for `x_studio_date_start`+`x_studio_date_stop` |
| `auto_map_view()` | Map view for `x_studio_partner_id` models |
| `auto_pivot_view()` | Pivot with `x_studio_value` as measure |
| `auto_graph_view()` | Graph with `x_studio_value` as measure |
| `auto_kanban_view()` | Kanban with stage grouping, priority, color |
| `_is_studio_view()` | Checks `xml_id.startswith('studio_customization')` |
| `_groups_branding()` | Adds `studio-view-group-ids` to specs tree |
| `_set_groups_info()` | Propagates group names/IDs to child nodes |
| `_check_parent_groups()` | Detects group-dependent hook nodes |
| `_apply_studio_specs()` | Spec-by-spec application with group tracking |
| `apply_inheritance_specs()` | Entry point; calls `_groups_branding()` in studio |
| `normalize()` / `normalize_with_keyed_tree()` | View architecture normalization via `KeyedXmlDiffer` |
| `copy_qweb_template()` | Copies QWeb report templates |
| `_validate_tag_button()` | Validates `studio_approval` attribute on buttons |
| `_contains_branded()` | Detects studio branding in view nodes |
| `is_node_branded()` | Checks `data-oe-model`, `apply-inheritance-specs-node-removal`, `t-*` attrs |
| `save_embedded_field()` | Never saves t-field content in studio context |

**L4: `_postprocess_access_rights()` group visibility logic.** When a user lacks group access:
- In list views: `column_invisible='True'` is set on the node
- In other views: `invisible='True'` is set
- The `groups` attribute is **removed** before calling `super()`, then **restored** after
- The `__groups_key__` attribute survives the round-trip and is used for `has_access()` checks

**L4: View normalization via `KeyedXmlDiffer`.** The normalization compares:
- `old_tree`: the inheritance tree **excluding** the studio view
- `new_tree`: the inheritance tree **including** the studio view

The diff produces minimal XPath expressions. New unnamed nodes in container types get a `name` attribute of `studio_<tag>_<6-char-uuid>` to provide a stable XPath anchor.

**L4: `_x2many_missing_view_archs()` override.** In studio context, missing sub-view architectures are set with `studio_subview_inlined="1"`, which tells the frontend to render them as inline (collapsed) rather than as clickable links.

---

### 1.7 `ir.model.data` Extension (`models/ir_model_data.py`)

| Field Added | Type | Description |
|------------|------|-------------|
| `studio` | Boolean | True if created/edited via Studio |

**L4: `studio_customization` is always imported (`imported=True`).** The `get_studio_module()` creates a module with `imported=True`, meaning it is loaded from its XML files on every boot. This is what makes Studio customizations persistent -- they live in the database (in `ir.model.data` pointing to `studio_customization`) and are applied on every startup.

**`_xmlid_for_export()`** strips both `__export__.` and `studio_customization.` prefixes:
```python
def _xmlid_for_export(self):
    return self.complete_name.replace('__export__.', '').replace('studio_customization.', '')
```

---

### 1.8 `ir.module.module` Extension (`models/ir_module_module.py`)

```python
def get_studio_module(self):
    studio_module = self.search([('name', '=', 'studio_customization')])
    if not studio_module:
        studio_module = self.create({
            'name': 'studio_customization',
            'application': False,
            'category_id': self.env.ref('base.module_category_customizations_studio').id,
            'shortdesc': 'Studio customizations',
            'description': '...',
            'state': 'installed',
            'imported': True,          # loaded from DB on every boot
            'author': self.env.company.name,
            'icon': '/base/static/description/icon.png',
            'license': 'OPL-1',
            'dependencies_id': [(0, 0, {'name': 'web_studio'})],
        })
    return studio_module
```

**L4: `imported=True` is critical.** Without this flag, Odoo would try to find `studio_customization` as an installable module on disk. With `imported=True`, Odoo reads it entirely from the database via `ir.model.data` entries.

**L4: `state='installed'` means no upgrade logic runs.** The module never goes through the upgrade lifecycle, so its data is always present. This is appropriate since Studio customizations are user data, not code.

---

### 1.9 `res.company` Extension (`models/res_company.py`)

| Field | Type | Description |
|-------|------|-------------|
| `background_image` | Binary (attachment=True) | Home menu background image |

**L4: Company creation auto-default propagation.** When a new company is created, the `create()` override searches for all manual (custom) `x_studio_company_id` and `x_studio_currency_id` fields across all installed models and sets `ir.default` values for the new company. This ensures Studio-created company/currency fields have correct defaults for newly created companies without requiring manual configuration.

---

### 1.10 `ir.qweb` Extension (`models/ir_qweb.py`)

```python
def _get_template_cache_keys(self):
    return super()._get_template_cache_keys() + ["studio"]

def _prepare_environment(self, values):
    if self.env.context.get("studio"):
        for k in ["main_object"]:
            if k in values:
                del values[k]
    return super()._prepare_environment(values)
```

**L4: Why `main_object` is removed.** In report preview within Studio, the `main_object` (typically the report's record) could be used in t-raw/t-out expressions to render user-controlled content. By removing it from the QWeb environment, any such expressions render as empty, preventing potential XSS in the report preview pane.

**L4: `_render()` forces `inherit_branding=True` in studio.** This ensures every QWeb node gets `data-oe-model`, `data-oe-id` attributes during report rendering in Studio, enabling the WYSIWYG report editor to identify and edit elements.

---

## L2: Cross-Model Relationships and Workflows

### 2.1 Approval Workflow Architecture

The approval engine uses a **method patching** pattern registered via `_register_hook()`:

```
studio.approval.rule.create()
  -> _make_automated_actions()     # creates base.automation for state-change models
  -> _post_create_delete()          # links automation to rules
  -> _update_registry()             # calls _unregister_hook + _register_hook

_register_hook():
  -> patches every method on every model that has a rule
  -> patched method: checks approvals, then calls original method if all approved
  -> original method stored as: method.studio_approval_rule_origin
```

**Patched method behavior:**
1. If `env.su` (superuser/sudo): skip all approval checks (prevents ecommerce/invoice flows from breaking)
2. Calls `check_approval(model, res_id, method, None)` for each record
3. `check_approval()` auto-creates an approval entry if current user can approve
4. If all records approved: calls `method.studio_approval_rule_origin()`
5. If some records not approved: calls origin on approved records, returns notification action for unapproved

**L4: `sudo()` bypass in approval checks.** The `_make_approval_method()` wrapper explicitly skips approval checks in `sudo()` environments. This is critical for:
- E-commerce order confirmations (online payment succeeds, order auto-confirmed)
- Invoice posting from payment workflows
- Any automation or API that uses sudo to bypass access rights

**L4: `FOR UPDATE NOWAIT` lock on approval rules.** `_set_approval()` acquires `SELECT FOR UPDATE NOWAIT` on all rules for the same (model, method, action) before creating an entry. This prevents race conditions where two concurrent approvers could both pass the exclusivity check and both create entries. The `NOWAIT` modifier avoids deadlocks; Odoo's ORM retries on lock acquisition failure.

### 2.2 Mail Activity Integration (`mail_activity.py`)

When a mail activity with `studio_approval_request_id` is marked done:
1. All related `studio.approval.request` records are fetched via domain on `(res_id, rule_id)` pairs
2. Extra activities to mark done = related requests' mail activities minus the current batch
3. Those extra activities are marked done via `super()._action_done()` first
4. For each `(res_id, rule)` pair: `rule.set_approval(res_id, True)` is called inside `contextlib.suppress(UserError)` -- meaning access errors or already-approved errors are silently swallowed
5. All approval requests are then `unlink()`ed (since Odoo 18.3, activities are archived not deleted, so manual request cleanup is needed)

**L4: Why `contextlib.suppress(UserError)` is safe.** If the current user marks the activity done but doesn't have approval rights, `set_approval()` raises `UserError`. The suppression means: (a) the activity is still marked done, (b) no entry is created, (c) no notification is sent. If a different user with proper rights marks it done, their name goes on the approval entry -- the "wrong" user action is effectively ignored.

### 2.3 View Editing Flow

The `edit_view` controller handles a 4-stage pipeline:

**Stage 1 -- Binary field pre-processing:**
- When adding a non-image/non-signature binary field, injects a companion `_filename` char field operation immediately after
- Sets `filename='x_<fieldname>_filename'` on the binary field

**Stage 2 -- Monetary field pre-processing:**
- When adding a monetary field, automatically creates a `x_studio_currency_id` many2one (if no currency field exists)
- Sets `currency_field='x_studio_currency_id'` on the monetary field
- Handles related monetary fields (follows the related chain to find the correct currency)

**Stage 3 -- Field creation:**
- Calls `create_new_field()` for new fields before applying view operations
- Special handling for `special='lines'` (one2many with auto-generated line model)
- Many2one fields get `create_name_field` option for the rec name

**Stage 4 -- Operation application + normalization:**
- All 14 whitelisted operations applied in order to the XML tree
- Kanban view: all field xpath targets prefixed with `templates//`
- After all operations: `studio_view.normalize()` called
- If normalization raises `ValidationError` (element cannot be located): un-normalized arch is used

### 2.4 Automatic View Generation Field Conventions

| Field Name Pattern | View Types Generated | Notes |
|-------------------|---------------------|-------|
| `x_studio_date` | Calendar | `date_start='x_studio_date', create_name_field='x_name'` |
| `x_studio_date_start` + `x_studio_date_stop` | Gantt | Both required |
| `x_studio_stage_id` | Kanban + Pivot + Graph | Kanban: `default_group_by`, progressbar |
| `x_studio_partner_id` | Map | `res_partner='x_studio_partner_id'` |
| `x_studio_value` | Pivot + Graph | As measure; `sample='1'` for demo data |
| Any model | List + Form + Search | Always generated |
| `x_studio_image` | Kanban card aside | `zoom: true, background: true` |
| `x_studio_tag_ids` | Kanban + List + Search | `color_field: 'x_color'` |

**L4: Kanban `auto_kanban_view()` generates a full Bootstrap 5 card structure.** The template includes `d-flex` header with favorite priority, `display_name` as h5, body with tags, footer with state selection and user avatar, and a dropdown menu for edit/delete/color picker. The `highlight_color="x_color"` attribute drives the kanban card color strip.

---

## L3: Security Architecture

### 3.1 Access Control Summary

| Model | group_system | group_user | Notes |
|-------|-------------|-----------|-------|
| `studio.approval.rule` | CRUD | Read | Settings-level access |
| `studio.approval.entry` | CRUD | Read + Create + Unlink own | `ir.rule`: users see only own entries |
| `studio.approval.request` | CRUD | No access | Hidden from regular users |
| `studio.export.model` | CRUD | No access | Settings only |
| `studio.export.wizard` | CRUD | No access | Settings only |
| `studio.export.wizard.data` | CRUD | No access | Settings only |
| `studio.approval.rule.approver` | CRUD | No access | |
| `studio.approval.rule.delegate` | CRUD | Read + Write | Internal users can delegate |

**L4: `studio.approval.entry` ir.rule.** Two rules:
- `base.group_user`: `domain_force: [('user_id', '=', user.id)]` -- users see only their own entries
- `base.group_system`: `domain_force: [(1, '=', 1)]` -- admins see all entries

This means in the approval kanban view, regular users only see entries they created. Admins see everything.

### 3.2 `__groups_key__` Attribute Lifecycle

1. During view rendering in studio: `groups` attribute is moved to `__groups_key__` before `super()._postprocess_access_rights()`
2. `super()` processes `__groups_key__` and sets nodes invisible as needed
3. After `super()`: `groups` is restored from the stored copy
4. `set_studio_groups()` converts XML IDs to JSON and sets `studio_groups` on the node
5. The frontend reads `studio_groups` JSON to display the group editor widget

### 3.3 `studio_customization` Module Security

Since `studio_customization` is `imported=True`, it bypasses the normal module upgrade mechanism. All its `ir.model.data` entries have `noupdate=True`, meaning:
- Upgrading `web_studio` does **not** overwrite customizations
- The customizations are always loaded from the database
- They survive module upgrades and are never auto-reset

---

## L4: Performance, Historical Changes, Edge Cases

### 4.1 Odoo 18 -> 19 Changes

| Change | Impact |
|--------|--------|
| `StudioMixin` moved to `studio_mixin.py` | Internal refactor; no API change |
| `StudioMixin.write()` display_name bypass removed | More correct but slightly more expensive writes |
| `OPERATIONS_WHITELIST` added `add_header_button` | Replaces `add_button_action` in naming |
| `mail.activity` entries now archived (not deleted) on 18.3+ | `_action_done` manually unlinks `studio.approval.request` |
| `ir.ui.view._x2many_missing_view_archs()` override added | Missing sub-views get `studio_subview_inlined="1"` |
| Lazy asset bundle `web_studio.studio_assets` | Loads only when Studio first opens |

### 4.2 Performance Considerations

1. **Lazy bundle loading.** The `web_studio.studio_assets` bundle includes `web.assets_backend_lazy`, meaning Studio JS/CSS are not loaded until Studio is first opened. This significantly improves normal (non-Studio) page load times.

2. **View cache key includes `studio`.** `_get_view_cache_key()` appends `self.env.context.get("studio")` to the cache key, ensuring views are cached separately in studio vs. normal mode. Without this, entering Studio mode would serve stale cached views.

3. **`model_name` is stored/indexed on `studio.approval.rule`.** Avoids repeated `related` lookups when iterating rules for the same model.

4. **`_model_res_id_idx` composite index on `studio.approval.entry`.** The `("(model, res_id)")` index speeds up `_delete_entries()` cleanup queries and entry lookups.

5. **`get_views` approval scan is batched.** The `_read_group` in `base.get_views()` is a single SQL query for all models in the current view batch, not one query per model.

6. **`studio_export_model._compute_excluded_fields()` runs at write time (readonly=False, compute=True).** The exclusion set is computed once when `model_id` is set and stored. This is expensive (iterates all model fields) but makes export operations fast.

### 4.3 Edge Cases

**Edge case: Model name collision after sanitization.** `sanitize_for_xmlid()` truncates to 20 chars. "My Custom Model" and "My Custom Module" both become "my_custom_model". The UUID suffix (`uuid.uuid4()[:8]`) on the `ir.model.data.name` field prevents actual XML ID collisions, but the display name in Studio can be confusing.

**Edge case: `exclusive_user` cross-rule enforcement.** If rule A has `exclusive_user=True` and rule B has `exclusive_user=False`, a user who approves rule A cannot approve rule B for the same record (but can for different records). The `_set_approval()` check for non-exclusive rules explicitly looks for any `exclusive_user=True` rule the same user has approved.

**Edge case: `check_approval()` partial success on batch calls.** When a method is called on multiple records (e.g., `action_confirm()` on 5 selected records), if 3 have all approvals and 2 don't, the patched method calls the original on the 3 approved records and returns a notification listing the 2 that were skipped. This is a deliberate design to avoid blocking bulk operations.

**Edge case: Deleting a rule with existing entries.** Both `unlink()` (via `@api.ondelete`) and `write()` with `model_id`/`method`/`action_id` changes are blocked if `entry_ids` exist. The error message instructs users to archive the rule instead.

**Edge case: Binary filename field for related fields.** When adding a related binary field (e.g., `x_document` related to `ir.attachment.datas`), the companion `_filename` field's `related` attribute is constructed by following the original related chain: `attachment_id.filename` becomes the path for the filename field.

**Edge case: Multi-company currency defaults.** When `use_value` is selected, `_post_create_option_use_value()` sets `x_studio_currency_id` default for **all existing companies** at model creation time. This is done via `ir.default.set(..., company_id=company.id)` for each company.

---

## Data Flows

### Model Creation Flow
```
User clicks "Create App" in Studio
  -> /web_studio/create_new_app
      -> ir.model.studio_model_create(name, options)
          -> _create_option_* for each option (creates field Command records)
          -> self.create([model_values] + extra_models_values)  -- batch create
          -> all_models._setup_access_rights()
          -> ir.ui.view.create_automatic_views() for each model
      -> model._create_default_action(name)
      -> ir.ui.menu.with_context(studio=True).create({...})
          -> create root menu + child menu + optional config menu
      -> Returns {menu_id, action_id}
```

### View Editing Flow
```
User edits view in Studio (drag field, change attribute, etc.)
  -> Frontend sends operations array to /web_studio/edit_view
      -> Parses studio_view_arch XML
      -> Pre-processes binary fields (inject filename field)
      -> Pre-processes monetary fields (inject currency field)
      -> For each operation:
          -> Creates field if doesn't exist (create_new_field)
          -> Kanban: prefixes xpath targets with templates//
          -> Calls _operation_* handler
      -> studio_view.normalize()  -- keyed XML diff
      -> _set_studio_view() -- creates/updates studio inheritance view
      -> Returns rendered view + field definitions
```

### Approval Workflow Flow
```
Rule created:
  studio.approval.rule.create()
    -> _make_automated_actions()  -- base.automation for sale/account/purchase
    -> _post_create_delete()
    -> _update_registry()
      -> _register_hook()
          -> patches method on target model with approval wrapper

User triggers button (method call):
  Patched method wrapper:
    -> check_approval(model, res_id, method, None)
        -> _set_approval(res_id, True)  -- auto-approve if user can approve
        -> If cannot: _create_request(res_id)  -- creates mail.activity
    -> If all approved: call original method
    -> If not: return notification action

User marks activity Done:
  mail.activity._action_done()
    -> Hook: for each studio_approval_request
        -> rule.set_approval(res_id, True)
        -> Creates studio.approval.entry
        -> Removes pending mail activity request
    -> super()._action_done()
```

### Export as Module Flow
```
User clicks Export in Studio
  -> /web_studio/export (admin only)
      -> studio.export.wizard.get_export_info()
          -> _get_models_to_export()  -- topological sort with cycle detection
          -> For each model:
              -> _get_groups_fields()  -- splits data/demo
              -> Groups by model, generates data XML
      -> generate_archive()  -- ZIP with __manifest__.py + data files
      -> Returns customizations.zip
```

---

## Key Extension Patterns

### Pattern 1: StudioMixin Inheritance (Thin Wrapper)

Most models use this single-line pattern for Studio tracking:
```python
class IrFilters(models.Model):
    _name = 'ir.filters'
    _inherit = ['studio.mixin', 'ir.filters']
```
The mixin adds `create()`/`write()` auto-tracking -- nothing else needed.

### Pattern 2: Selective Override

Models needing specific Studio behavior override targeted methods:
- `ir.ui.view`: override `_postprocess_access_rights` for studio-specific group handling
- `ir.model`: override `studio_model_create` for full creation wizard
- `res.company`: override `create` for default value propagation
- `ir.qweb`: override `_prepare_environment` for XSS prevention

### Pattern 3: Method Patching (Approval Engine)

`_register_hook()` dynamically patches methods on arbitrary models:
```python
def _patch(Model, method_name, function):
    method = getattr(ModelClass, method_name, None)
    function.studio_approval_rule_origin = method  # store original
    setattr(ModelClass, method_name, function)       # replace with wrapper
```
This is the same technique used by `base_automation` and is safe for coexistence (both call `_unregister_hook()` before re-patching).

### Pattern 4: Context-Guarded Behavior

Many behaviors are gated by `self.env.context.get('studio')`:
- `StudioMixin.create/write`: auto-tracking
- `ir.model.data.write`: sets noupdate+studio
- `ir.ui.view._postprocess_access_rights`: invisible instead of delete
- `ir.qweb._prepare_environment`: removes main_object
- `fields_get`: returns all fields including restricted ones

---

## Thin Wrapper Models (StudioMixin-only inheritance)

These models exist only to add Studio auto-tracking via `StudioMixin`. No other overrides:

| Model File | Models Extended |
|-----------|----------------|
| `base_automation.py` | `base.automation` |
| `ir_actions.py` | `ir.actions.actions` |
| `ir_actions_act_window.py` | `ir.actions.act_window` + `ir.actions.act_window.view` |
| `ir_actions_server.py` | `ir.actions.server` |
| `ir_default.py` | `ir.default` |
| `ir_filters.py` | `ir.filters` |
| `ir_rule.py` | `ir.rule` |
| `mail_activity_type.py` | `mail.activity.type` |
| `mail_template.py` | `mail.template` |
| `report_paperformat.py` | `report.paperformat` |
| `res_groups.py` | `res.groups` |

---

## Wizard: `studio.export.wizard`

**`StudioExportWizard`** (TransientModel):
- `default_export_data`: pre-filled with all `ir.model.data` where `studio=True`
- `include_additional_data`: toggles display of `additional_models`
- `include_demo_data`: cascading toggle (enables `include_additional_data`)
- `additional_models`: computed from `studio.export.model` records
- `additional_export_data`: computed from `additional_models._get_exportable_records()`

**`_get_models_to_export()` -- Topological sort with cycle detection:**
1. Builds dependency graph from relational field information
2. Uses `topological_sort()` (standard Odoo tool) + custom `_find_circular_dependencies()`
3. Circular dependencies are detected and reported, not broken
4. Demo data is exported before master data (`is_demo=True` then `False`)

**`FIELDS_TO_EXPORT` -- 14 models with explicit field lists.** This whitelist prevents accidental export of internal Odoo fields (e.g., `create_date`, `write_uid`, `__last_update`). Models not in this list use `OrderedSet(Model._fields) - MAGIC_COLUMNS` as the export set.

**`_get_groups_fields()` -- Split data/demo logic.** For non-demo records, fields pointing to demo records are moved to the demo export group. This ensures that when importing, demo records are loaded first and master records can reference them.

---

## Wizard: `base_module_uninstall`

When uninstalling `web_studio` via the module uninstall wizard, Studio-specific counters are shown:
- `custom_views`: views from `studio_customization` ir.model.data (excluding QWeb)
- `custom_reports`: report actions from `studio_customization`
- `custom_models`: models with `state='manual'`
- `custom_fields`: fields with `state='manual'`

The `_get_models()` override ensures that custom Studio models (`state='manual'`) are included in the uninstall's model list, so their database tables are dropped.

---

## Tags

`#odoo` `#odoo19` `#enterprise` `#studio` `#no-code` `#app-builder` `#customization` `#approval-workflow` `#export-module` `#view-customization`

---

## Related Documentation

- [[Modules/web_studio]] -- `web_enterprise` dependency
- [[Core/BaseModel]] -- ORM foundation (StudioMixin inherits BaseModel)
- [[Patterns/Inheritance Patterns]] -- `_inherit` vs `_inherits` vs mixin
- [[Patterns/Workflow Patterns]] -- state machine pattern in Odoo
- [[Core/Fields]] -- field types including custom `x_` fields
