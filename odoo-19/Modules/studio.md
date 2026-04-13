---
type: module
title: "Web Studio — No-Code App Builder"
description: "Odoo Web Studio enables consultants and power users to create custom apps, models, fields, views, and business logic without writing code, then export as installable modules."
source_path: ~/odoo/enterprise/tracon-enterprise/web_studio/
tags:
  - odoo
  - odoo19
  - module
  - studio
  - no-code
  - enterprise
related_modules:
  - base
  - base_automation
  - web
  - web_enterprise
  - mail
created: 2026-04-11
version: "2.0"
---

## Quick Access

### Related Modules
- [Modules/Account](odoo-18/Modules/account.md) — Adding custom fields to invoices via Studio
- [Modules/Sale](odoo-18/Modules/sale.md) — Customizing quotation views via Studio
- [Modules/Stock](odoo-18/Modules/stock.md) — Adding custom inventory fields via Studio
- [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) — Understanding Studio's model extension mechanism
- [Modules/base_automation](odoo-17/Modules/base_automation.md) — Studio automation rules integration

---

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | Studio (App Builder) |
| **Technical Name** | `web_studio` |
| **Category** | Customizations / Studio |
| **Summary** | No-code application builder and customizer |
| **Author** | Odoo S.A. |
| **License** | Odoo Proprietary License (OEEL-1) |
| **Installable** | Enterprise Edition only |
| **Module Version** | 1.0 |
| **Dependencies** | `base_automation`, `base_import_module`, `mail`, `web`, `web_enterprise`, `html_editor`, `web_editor`, `web_map`, `web_gantt`, `web_cohort`, `sms` |

### Description

Odoo Studio is a powerful no-code development environment integrated directly into the Odoo web interface. It allows consultants, power users, and administrators to:

- **Create new models** (database tables) with custom fields
- **Design views** using drag-and-drop: form, list, kanban, calendar, search
- **Define business logic** through action buttons and automation rules
- **Create menus and actions** to navigate between views
- **Export customizations** as installable Odoo modules (upgrade-safe)
- **Apply customizations** to existing Odoo applications

Studio generates XML data files that extend the standard Odoo framework through the standard inheritance mechanism (`_inherit`), making all customizations upgrade-safe and portable.

---

## Architecture

### Module Structure

```
web_studio/
├── __manifest__.py           # Module metadata and dependencies
├── models/
│   ├── __init__.py
│   ├── ir_model.py          # Custom model creation (x_* models)
│   ├── ir_model_data.py     # Studio model data tracking
│   ├── ir_ui_view.py        # View customization and inheritance
│   ├── ir_actions.py        # Action customization
│   ├── ir_actions_act_window.py
│   ├── ir_actions_server.py
│   ├── ir_actions_report.py
│   ├── ir_filters.py
│   ├── ir_qweb.py
│   ├── ir_rule.py
│   ├── ir_ui_menu.py
│   ├── mail_template.py
│   ├── mail_thread.py
│   ├── mail_activity.py
│   ├── mail_activity_type.py
│   ├── base_automation.py    # Studio automation rules
│   ├── report_paperformat.py
│   ├── res_company.py
│   ├── res_groups.py
│   ├── res_users.py
│   ├── studio_approval.py   # Approval workflow
│   ├── studio_export_model.py # Module export
│   ├── studio_mixin.py      # Core mixin for studio operations
│   └── models.py
├── controllers/
├── views/
├── wizard/
├── security/
├── data/
├── demo/
└── static/
    └── src/                 # JavaScript for Studio UI
```

### Key Design Principles

1. **Studio Mixin Pattern**: All studio-tracked records use `studio.mixin` to auto-create `ir.model.data` entries
2. **x_* Naming Convention**: Custom models use the `x_` prefix (e.g., `x_custom_model`)
3. **XML Export**: All customizations are serialized to XML for module export
4. **Inheritance First**: Studio extends existing models via `_inherit` rather than modifying core

---

## Key Models

### 1. Studio Mixin (`studio.mixin`)

Abstract mixin that automatically creates `ir.model.data` entries when records are created in Studio context.

```python
class StudioMixin(models.AbstractModel):
    _name = 'studio.mixin'
    _description = 'Studio Mixin'

    @api.model_create_multi
    def create(self, vals):
        res = super(StudioMixin, self).create(vals)
        if self._context.get('studio') and not self._context.get('install_mode'):
            res._compute_display_name()
            for ob in res:
                ob.create_studio_model_data(ob.display_name)
        return res
```

**Key Behavior:**
- When `context.get('studio')` is True, creates `ir.model.data` entries tagged with Studio
- Does NOT create entries during module install (`install_mode` context)
- Enables tracking of all Studio-created records for export

---

### 2. Ir Model Extensions (`ir.model`)

Studio extends `ir.model` to enable custom model creation:

```python
class IrModel(models.Model):
    _name = 'ir.model'
    _inherit = ['studio.mixin', 'ir.model']

    abstract = fields.Boolean(
        compute='_compute_abstract',
        store=False,
        help="Whether this model is abstract",
        search='_search_abstract'
    )

    @api.model
    def studio_model_create(self, name, options=()):
        """Quick creation of models through Studio."""
        options = set(options)
        use_mail = 'use_mail' in options

        model_values = {
            'name': name,
            'model': 'x_' + sanitize_for_xmlid(name),
            'is_mail_thread': use_mail,
            'is_mail_activity': use_mail,
            'field_id': [
                Command.create({
                    'name': 'x_name',
                    'ttype': 'char',
                    'required': True,
                    'field_description': _('Description'),
                    'translate': True,
                    'tracking': use_mail,
                })
            ]
        }
        # ... create model with requested options
        return (main_model, models_with_menu)
```

**Model Creation Options** (`studio_model_create`):

| Option | Description | Creates |
|--------|-------------|---------|
| `use_mail` | Enable mail thread | Message threading, followers |
| `use_active` | Archive support | `active` boolean field |
| `use_responsible` | User assignment | `user_id` field |
| `use_partner` | Partner linking | `partner_id`, email, phone |
| `use_company` | Multi-company | `company_id` field + rules |
| `use_notes` | HTML notes | `x_notes` HTML field |
| `use_date` | Date tracking | `x_date` field |
| `use_double_dates` | Start/end dates | `x_date_start`, `x_date_end` |
| `use_value` | Monetary value | `x_value` + currency |
| `use_image` | Image field | `x_image` binary field |
| `use_sequence` | Ordering | `sequence` integer field |
| `lines` | Line items | One2many to line model |
| `use_stages` | Kanban stages | Stage model + field |
| `use_tags` | Tagging | Tag model + Many2many |

---

### 3. View Customization (`ir.ui.view`)

Studio extends `ir.ui.view` to support visual view editing:

```python
class View(models.Model):
    _name = 'ir.ui.view'
    _inherit = ['studio.mixin', 'ir.ui.view']

    def _get_closest_primary_view(self):
        """Get the root view that this view inherits from."""
        self.ensure_one()
        view = self
        while view.mode != "primary":
            view = view.inherit_id
        return view
```

**Studio View Modes:**
- **Extension**: Custom view that modifies an existing view (`mode='extension'`)
- **Primary**: New standalone view (`mode='primary'`)

**View Processing:**
- Studio adds `studio_groups` attribute for group-based field visibility
- Processes access rights in Studio context to show/hide based on permissions
- Supports `studio_xpath` for targeted modifications

---

### 4. Studio Export Model (`studio.export.model`)

Tracks which models to export when generating a custom module:

```python
class StudioExportModel(models.Model):
    _name = "studio.export.model"
    _description = "Studio Export Models"

    model_id = fields.Many2one(
        "ir.model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '!=', True), ('abstract', '!=', True)]"
    )
    excluded_fields = fields.Many2many("ir.model.fields")
    domain = fields.Text(default="[]")
    is_demo_data = fields.Boolean(
        default=False,
        help="If set, exported records are demo data during import"
    )
    updatable = fields.Boolean(
        default=True,
        help="Defines if records would be updated during module update"
    )
    include_attachment = fields.Boolean(
        default=False,
        help="Include attachments related to exported records"
    )
```

**Preset Models** (automatically included in export):
Studio exports data for preset models like `res.partner`, `product.product`, `sale.order`, etc., with specific exclusions to avoid exporting sensitive data.

---

### 5. Studio Approval (`studio.approval`)

Enables approval workflows on custom models:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Approval rule name |
| `model_id` | Many2one | Target model |
| `field_id` | Many2one | Field triggering approval |
| `group_ids` | Many2many | Required approver groups |
| `state` | Selection | `pending`, `approved`, `refused` |

---

## How Studio Creates Custom Fields

### Field Naming Convention

All custom fields created through Studio follow the `x_studio_*` naming pattern:

```python
# When user creates field "My Custom Field" via Studio UI
# System automatically generates: x_studio_my_custom_field

def sanitize_for_xmlid(s):
    """Transform string to valid XML ID and field name."""
    uni = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    slug_str = re.sub(r'\W', ' ', uni).strip().lower()
    slug_str = re.sub(r'[-\s]+', '_', slug_str)
    return slug_str[:20]  # Max 20 chars for field name
```

### Field Types Supported

| Studio Type | Odoo Field Type | Storage |
|------------|-----------------|---------|
| Text | `char` | Stored |
| Multiline Text | `text` | Stored |
| Integer | `integer` | Stored |
| Decimal | `float` | Stored |
| Boolean | `boolean` | Stored |
| Date | `date` | Stored |
| Date & Time | `datetime` | Stored |
| Selection | `selection` | Stored |
| Many2One | `many2one` | Stored (FK) |
| One2Many | `one2many` | Virtual |
| Many2Many | `many2many` | Relation table |
| HTML | `html` | Stored |
| Binary | `binary` | Stored/Filestore |
| Image | `binary` | Stored/Filestore |

---

## View Customization Mechanism

### How Studio Modifies Views

1. **Read Base View**: Studio loads the original view XML architecture
2. **Apply User Changes**: User drags/drops elements in Studio UI
3. **Generate XPaths**: Studio generates `xpath` expressions for modifications
4. **Create Extension View**: New view with `mode='extension'` and `inherit_id` pointing to base
5. **Store in Database**: Extension view stored as `ir.ui.view` record

### Example: Adding a Field via Xpath

```xml
<!-- Base view (original) -->
<form>
    <group>
        <field name="name"/>
    </group>
</form>

<!-- Studio extension view -->
<form inherit_id="base.view_form">
    <xpath expr="//group" position="inside">
        <field name="x_studio_custom_field"/>
    </xpath>
</form>
```

### Studio View Attributes

| Attribute | Description |
|-----------|-------------|
| `studio_position` | Placement hint for UI |
| `studio_x` | X coordinate |
| `studio_y` | Y coordinate |
| `studio_width` | Element width |
| `studio_group_header` | Group container |
| `studio_children_view` | Embedded subview |

---

## App Creation Workflow

### Step-by-Step: Creating a New App

```
1. Navigate to: Settings > Studio > Create App
   |
   v
2. Enter App Details:
   - Technical Name: auto-generated as x_appname
   - Display Name: Human-readable name
   - Icon: Select from preset or upload
   - Description: App description
   |
   v
3. Studio creates:
   - New model (x_appname)
   - Menu item under app
   - Initial form and list views
   |
   v
4. Customize the App:
   - Add fields via Field Editor
   - Design views via View Editor
   - Create actions and buttons
   |
   v
5. Configure Options:
   - Enable mail tracking
   - Add partner/company linking
   - Configure stages (for kanban)
   |
   v
6. Export as Module:
   - Studio > Export
   - Download ZIP
   - Install on target database
```

### What Gets Created

For a new app "Project Tracker":

| Component | XML ID | Description |
|-----------|--------|-------------|
| Model | `x_project_tracker` | Main data model |
| Field | `x_name` | Required name field |
| Menu | `menu_project_tracker` | App menu item |
| Action | `action_project_tracker` | Window action |
| View | `view_project_tracker_form` | Form view |
| View | `view_project_tracker_list` | List view |
| Access | `access_x_project_tracker` | ACL record |

---

## Automation Rules (Studio + base_automation)

Studio integrates with `base_automation` to create server actions triggered by:

### Trigger Types

| Trigger | Description | On Create | On Update | On Delete |
|---------|-------------|-----------|-----------|-----------|
| Based on Fields | When specific fields change | Yes | Yes | No |
| On Time Condition | Scheduled triggers | Yes | Yes | Yes |
| On CRUD | Create/Write/Unlink | Yes | Yes | Yes |

### Automation Rule Structure

```python
# When creating automation in Studio:
# 1. Creates ir.actions.server record
# 2. Creates base.automation.rule record
# 3. Links trigger to model and fields

# Example: Send email when stage changes to "Done"
ir.actions.server:
    - name: "Send Completion Email"
    - model_id: x_project_tracker
    - state: code
    - code: |
        if record.x_stage == 'done':
            template = env.ref('mail_template_x_project_done')
            template.send_mail(record.id)

base.automation.rule:
    - name: "Send Completion Email"
    - model_id: x_project_tracker
    - trigger: on_write
    - trigger_field_ids: x_stage_id
    - action_server_id: ir.actions.server.id
```

---

## Field Properties Configuration

When adding fields in Studio, users can configure:

### Basic Properties

| Property | Odoo Field Attribute | Description |
|----------|--------------------|-------------|
| Label | `string` | Display name |
| Technical Name | `name` | Database column |
| Required | `required` | Mandatory field |
| Readonly | `readonly` | Cannot edit |
| Index | `index` | Database index |

### Advanced Properties

| Property | Attribute | Description |
|----------|-----------|-------------|
| Default Value | `default` | Pre-populated value |
| Help Text | `help` | Hover tooltip |
| Constraint | `constrains` | Validation rule |
| Store | `store` | Persist computed fields |
| Compute | `compute` | Formula field |
| Related | `related` | Delegated field |

### Widget Selection

| Widget | Field Types | Purpose |
|--------|-----------|---------|
| monetary | float, monetary | Currency display |
| date | date | Date picker |
| datetime | datetime | Date+time picker |
| many2one | many2one | Dropdown selector |
| many2many_tags | many2many | Tag pills |
| binary_file | binary | File upload |
| image | binary | Image display |
| progressbar | float | Progress indicator |

---

## Menu Customization

### Adding Menu Items

Studio can create:
1. **Top-level menu**: New application entry
2. **Sub-menu**: Category under existing menu
3. **Action menuitem**: Links to view/action

### Menu Structure Generated

```python
# Menu creation
ir.ui.menu:
    - name: "Project Tracker"
      action: action_project_tracker
      parent: False  # Top-level
      sequence: 15
      groups: base.group_user

# Can also create child menus
ir.ui.menu:
    - name: "Reports"
      parent: menu_project_tracker
      action: action_project_tracker_report
```

---

## Access Rights Management

### Automatic ACL Generation

When creating a new model, Studio automatically creates ACL entries:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_x_project_tracker_user,x_project_tracker.user,model_x_project_tracker,base.group_user,1,1,1,1
access_x_project_tracker_manager,x_project_tracker.manager,model_x_project_tracker,base.group_system,1,1,1,1
```

### Access Groups

| Group | Read | Write | Create | Unlink |
|-------|------|-------|--------|--------|
| User (base.group_user) | Yes | Yes | Yes | Yes |
| Manager (base.group_system) | Yes | Yes | Yes | Yes |
| Employee (base.group_user) | Yes | No | No | No |

---

## Module Export

### Export Process

```
1. User clicks: Studio > Export
   |
   v
2. Studio collects:
   - Custom models (x_*)
   - Custom fields on existing models
   - Custom views
   - Custom actions
   - Custom menus
   - Access rights
   - Automation rules
   |
   v
3. Generate module structure:
   |-- __manifest__.py
   |-- models/
   |   |-- __init__.py
   |   |-- model_file.py
   |-- views/
   |   |-- views.xml
   |   |-- templates.xml
   |-- security/
   |   |-- ir.model.access.csv
   |-- data/
   |   |-- data.xml
   |-- static/
       |-- description/
           |-- icon.png
   |
   v
4. ZIP and download
```

### Export Options

| Option | Description |
|--------|-------------|
| Include Demo Data | Include sample records |
| Include Attachments | Bundle file attachments |
| Update Existing | Overwrite on reinstall |
| Exclude Fields | Skip specific fields |

---

## Themes and Visual Customization

### Studio Themes

Studio supports theme application for consistent styling:

```xml
<!-- Theme application in views -->
<div class="o_project_tracker_form">
    <div class="oe_title">
        <h1>
            <field name="x_name" placeholder="Project Name"/>
        </h1>
    </div>
</div>

<style>
    .o_project_tracker_form {
        background-color: #f8f9fa;
    }
    .oe_title h1 {
        color: #2c3e50;
        font-size: 24px;
    }
</style>
```

### Color Palette

Studio provides preset color schemes:
- Primary colors for headers
- Status colors for state fields
- Badge colors for kanban cards

---

## Best Practices

### DO: Use Studio For

- Rapid prototyping of new models
- Adding fields to existing models
- Creating simple workflows
- Building internal tools
- Custom reports with grouped views

### DON'T: Use Studio For

- Complex business logic requiring Python
- Performance-critical computations
- Integration with external systems
- Advanced security models
- Database-level optimizations

### Performance Considerations

1. **Computed Fields**: Store results if queried frequently
2. **Indexes**: Enable on searchable custom fields
3. **One2many Limits**: Avoid deep hierarchies
4. **Automation Triggers**: Use field-specific triggers over "on all changes"

---

## Common Use Cases

### Use Case 1: Custom Partner Fields

```python
# Studio creates on res.partner:
x_studio_industry_segment = fields.Many2one('industry.segment')
x_studio_credit_limit = fields.Monetary('Credit Limit', currency_field='currency_id')
x_studio_onboarding_stage = fields.Selection([
    ('new', 'New'),
    ('contacted', 'Contacted'),
    ('qualified', 'Qualified'),
    ('won', 'Won')
])
```

### Use Case 2: Custom Document Model

```python
# New model: Contract Management
class XContract(models.Model):
    _name = 'x_contract'
    _description = 'Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    x_name = fields.Char('Contract Name', required=True)
    x_partner_id = fields.Many2one('res.partner', 'Customer')
    x_date_start = fields.Date('Start Date')
    x_date_end = fields.Date('End Date')
    x_value = fields.Monetary('Contract Value', currency_field='currency_id')
    x_stage_id = fields.Many2one('x_contract_stage', 'Stage')
    x_attachment_ids = fields.Many2many('ir.attachment')
```

### Use Case 3: Automated Reminders

```python
# Studio automation rule:
# When: Contract end_date is in 30 days
# Do: Create activity for contract owner

base.automation.rule:
    trigger: on_time
    timing: based on field
    field: x_date_end
    condition: x_date_end - today <= 30 days
    action: Create Activity
    activity_type: Reminder
    summary: "Contract expiring soon"
```

---

## Limitations and Constraints

### Technical Limitations

| Limitation | Description | Workaround |
|------------|-------------|------------|
| No Python code | Cannot add custom methods | Export and add manually |
| No custom SQL | Cannot add DB constraints | Use @constrains |
| Limited to ORM | Cannot bypass ORM | Write custom module |
| Model name prefix | Must use `x_` prefix | Accept limitation |

### Business Limitations

| Limitation | Description |
|------------|-------------|
| Admin-only access | Only admin can use Studio |
| No version control | Export to git for history |
| No collaboration | One user at a time |
| Limited testing | Export and test in dev |

---

## Migration Notes

### Upgrading Studio Customizations

When upgrading from Odoo 15/16/17 to 19:

1. Studio exports remain compatible
2. Re-export all customizations
3. Test in staging environment
4. Install as new module
5. Uninstall old customizations

### Export Compatibility

| Odoo Version | Export Format | Compatible |
|-------------|---------------|------------|
| 15.x | ZIP with Python 3 | Yes |
| 16.x | ZIP with Python 3.10+ | Yes |
| 17.x | ZIP with Python 3.10+ | Yes |
| 18.x | ZIP with Python 3.10+ | Yes |
| 19.x | ZIP with Python 3.10+ | Yes |

---

## Security Considerations

### Access Control

- Only `base.group_system` (Admin) can use Studio
- Custom fields inherit model permissions
- Views respect existing access rules
- Exported modules maintain ACL definitions

### Data Protection

- Export includes access restrictions
- Sensitive fields can be hidden via groups
- Record rules apply to custom models
- Company-dependent fields supported

---

## File Reference

### Key Files

| File | Purpose |
|------|---------|
| `models/studio_mixin.py` | Core mixin for Studio tracking |
| `models/ir_model.py` | Custom model creation |
| `models/ir_ui_view.py` | View customization |
| `models/studio_export_model.py` | Module export |
| `models/studio_approval.py` | Approval workflows |
| `wizard/` | Export wizard, reset wizard |

### Manifest Data Files

```python
'data': [
    'views/assets.xml',
    'views/actions.xml',
    'views/ir_actions_report_xml.xml',
    'views/ir_model_data.xml',
    'views/studio_approval_views.xml',
    'views/reset_view_arch_wizard.xml',
    'views/studio_export_wizard_views.xml',
    'views/studio_export_model_views.xml',
    'data/mail_templates.xml',
    'data/mail_activity_type_data.xml',
    'data/web_tour_tour.xml',
    'wizard/base_module_uninstall_view.xml',
    'security/ir.model.access.csv',
    'security/studio_security.xml',
]
```

---

## Related Documentation

- [Core/BaseModel](odoo-18/Core/BaseModel.md) — Understanding Odoo model inheritance
- [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) — Studio's extension mechanism
- [Modules/base_automation](odoo-17/Modules/base_automation.md) — Automation rules created by Studio
- [Core/API](odoo-18/Core/API.md) — @api.depends, @api.onchange for computed fields

---

*Document version: 2.0 | Last updated: 2026-04-11 | Source: `web_studio` module v1.0*
