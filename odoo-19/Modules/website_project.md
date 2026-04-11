---
title: website_project
description: Online task submission via website forms, public project/task portal visibility, and website-integrated project management.
tags: [odoo19, modules, website, project, portal, form-builder]
---

# website_project

## Overview

- **Technical name**: `website_project`
- **Category**: `Website/Website`
- **Summary**: Add a task suggestion form to your website
- **Description**: Generate tasks in Project app from a form published on your website. Requires the *Form Builder* module to build the form.
- **Version**: `1.0`
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Depends**: `website`, `project`
- **Auto-install**: `True`
- **Installable**: `True`

## Purpose

`website_project` bridges the [[Modules/project]] and [[Modules/website]] modules. It enables two core workflows:

1. **Public task submission**: Anonymous and authenticated website visitors can submit tasks via a website form built with the Form Builder, without needing an Odoo account.
2. **Portal task display**: Portal users and employees can view their tasks and projects via the website portal.

The module does **not** extend `project.project` with `website_published` or implement a public project showcase. Those features live in `project` itself (the `privacy_visibility` field) or in `website_project_meet` (for meeting-based project pages). `website_project` focuses purely on the form-to-task pipeline and portal view template overrides.

---

## Module Structure

```
website_project/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── project_task.py      # project.task field extensions
│   └── website_page.py      # website.page cache control
├── controllers/
│   ├── __init__.py
│   └── main.py              # WebsiteForm overrides
├── views/
│   ├── project_portal_project_project_template.xml  # project portal template patch
│   └── project_portal_project_task_template.xml    # task portal template patch
├── data/
│   └── website_project_data.xml   # ir.model record + formbuilder_whitelist
└── static/src/js/
    └── website_project_editor.js  # Form Builder field config for create_task
```

---

## Dependencies

| Module | Role |
|--------|------|
| `website` | Form Builder, website page routing, visitor tracking, portal layout |
| `project` | Task model (`project.task`), project model (`project.project`) |

### Asset Dependencies (Auto-wired)

The `__manifest__.py` declares two asset bundles that ensure JS patches from `website` are available when `project` loads its web client assets:

```python
'assets': {
    'website.website_builder_assets': [
        'website_project/static/src/js/website_project_editor.js',
    ],
    'project.webclient': [
        'website/static/src/js/utils.js',
        'web/static/src/core/autocomplete/*',
        'website/static/src/components/autocomplete_with_pages/*',
    ],
}
```

The `website/static/src/js/utils.js` patch on `LinkDialog` (in `website/static/src/js/editor/editor.js`) is needed by the project webclient. Without this asset declaration, the project webclient would fail if `website` were installed without `website_project` — an uncommon but documented inter-module dependency.

---

## Extended Models

### `project.task` (model extension)

**File**: `models/project_task.py`

```python
class ProjectTask(models.Model):
    _inherit = 'project.task'
```

#### Fields Added

| Field | Type | Store | Related | Notes |
|-------|------|-------|---------|-------|
| `partner_name` | `Char` | Yes | `partner_id.name` | Cached customer name; editable on task form. `readonly=False` allows writeback from form. |
| `partner_company_name` | `Char` | Yes | `partner_id.company_name` | Cached company name from partner; also editable from form. |

Both fields are `related` (stored, `readonly=False`). This pattern allows:

- **Writing** values from the website form directly onto the task record.
- **Reading** the cached value even if the linked partner is later deleted (stored copy).
- When `partner_id` changes, the stored values are automatically recalculated via ORM recomputation.

#### Why `readonly=False` on Related Fields?

Odoo's default for related fields is `readonly=True`. Here, `readonly=False` is deliberate so that the Form Builder can write form-submitted values (`partner_name`, `partner_phone`, `partner_company_name`) into these fields during task creation. Without this flag, the ORM would block writes from `website_form_input_filter`-derived data flows.

---

### `website.page` (model extension)

**File**: `models/website_page.py`

```python
class WebsitePage(models.Model):
    _inherit = 'website.page'

    @api.model
    def _allow_to_use_cache(self, request):
        if request.httprequest.path == '/your-task-has-been-submitted':
            return False
        return super()._allow_to_use_cache(request)
```

#### Method: `_allow_to_use_cache()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `request` | `website.request` | Current HTTP request object |

**Logic**: Returns `False` for the path `/your-task-has-been-submitted`, disabling page caching for the post-submission confirmation page. For all other paths, delegates to the parent.

**Why needed**: The confirmation page (`task_submitted` template) renders dynamic data — specifically the submitted task ID via `_website_form_last_record()`. If cached, subsequent visitors would see stale task IDs or an empty page. This is a common pattern for any transient-dynamic page in Odoo website.

---

## Controllers

### `WebsiteForm` — extends `website.controllers.form.WebsiteForm`

**File**: `controllers/main.py`

The controller inherits from `website.controllers.form.WebsiteForm` (defined in `website/controllers/form.py`) and overrides two methods to handle `project.task` submissions.

#### Route: `/website/form/<model_name>`

**Inherited from parent**: The parent `WebsiteForm.website_form()` route at `/website/form/<model_name>` handles all website form POSTs, including project.task. It calls `extract_data()` then `insert_record()` within a savepointed transaction. The child controller does not override the route itself — only the two processing methods.

---

#### `extract_data(model_sudo, values)` — Override

**Signature** (inherited from parent):
```python
def extract_data(self, model_sudo, values) -> dict
# Returns: {'record': {...}, 'attachments': [...], 'custom': '...', 'meta': '...'}
```

**Behavior for `project.task`**:

```python
if model_sudo.model == 'project.task' and values.get('email_from'):
```

Called for every submitted form. For `project.task` with an `email_from` field present, the method performs a partner resolution step before returning to the parent:

**Step 1 — Partner lookup by email**:
```python
partner = request.env['mail.thread'].sudo()._partner_find_from_emails_single(
    [values['email_from']], no_create=True
)
data['record']['email_from'] = values['email_from']
```

Uses `_partner_find_from_emails_single()` (from `mail.thread` mixin, executed as `sudo()`). `no_create=True` means it will NOT auto-create a partner if no match is found — only an existing partner is linked.

**Step 2a — Partner found** (`if partner:`):
```python
data['record']['partner_id'] = partner.id
custom = [
    ('partner_name',     data['record'].pop('partner_name', False)),
    ('partner_phone',   data['record'].pop('partner_phone', False)),
    ('partner_company_name', data['record'].pop('partner_company_name', False)),
]
data['custom'] += "\n" + "\n".join(["%s : %s" % c for c in custom])
```

When a partner is found:
- Sets `partner_id` on the task (links the task to the existing partner record).
- **Removes** `partner_name`, `partner_phone`, `partner_company_name` from `data['record']` (they are NOT written as fields since the partner is already linked — the partner's own fields will show via the related `partner_name`/`partner_company_name` fields).
- Adds the stripped values to `data['custom']` as a plain-text block appended to any existing custom fields.

**Step 2b — No partner found** (`else:`):
```python
data['record']['email_cc'] = values['email_from']
if values.get('partner_phone'):
    data['record']['partner_phone'] = values['partner_phone']
if values.get('partner_name'):
    data['record']['partner_name'] = values['partner_name']
if values.get('partner_company_name'):
    data['record']['partner_company_name'] = values['partner_company_name']
```

When no partner exists:
- Stores the email in `email_cc` (a standard `mail.thread` field) so the email is preserved.
- Writes `partner_name`, `partner_phone`, `partner_company_name` directly to the task record (these become the stored cached values from `models/project_task.py`).

**Security note**: `extract_data()` runs as `SUPERUSER_ID` (`sudo()`) because the parent method validates `model_sudo.env.su`. Form data is authorized field-by-field via `authorized_fields = model_sudo.with_user(SUPERUSER_ID)._get_form_writable_fields(values)` (parent method). Only fields that are both whitelisted in `ir.model` (`formbuilder_whitelist`) AND present in `_get_form_writable_fields()` can be written.

---

#### `insert_record(request, model_sudo, values, custom, meta)` — Override

**Signature** (inherited from parent):
```python
def insert_record(self, request, model_sudo, values, custom, meta=None) -> int
# Returns: record ID of created task
```

**Behavior for `project.task`**:

```python
if model_name == 'project.task':
    visitor_sudo = request.env['website.visitor']._get_visitor_from_request()
    visitor_partner = visitor_sudo.partner_id
    if visitor_partner:
        values['partner_id'] = visitor_partner.id
    values.setdefault('user_ids', False)
```

**Step 1 — Visitor partner linking**:
Calls `website.visitor._get_visitor_from_request()` to fetch the current website visitor. If the visitor has a linked `partner_id` (tracked via `website.visitor` model), that partner is forcibly set on the task. This **overrides** whatever `partner_id` was set in `extract_data()` — the visitor's partner takes precedence. This means a logged-in portal user submitting a task will always have the task linked to their own partner record, not an arbitrary email-supplied partner.

**Step 2 — User assignment**:
```python
values.setdefault('user_ids', False)
```

Sets `user_ids` to `False` if not already present in `values`. Background: when `project.task` is created from the web editor without a `user_ids` key, Odoo's default `user_ids` logic fills it with `OdooBot` (the system user). Setting it to `False` explicitly ensures no user is auto-assigned from a website form submission — the task enters as unassigned.

**Step 3 — Description assembly** (after `super()` call returns `res`):
```python
task = request.env['project.task'].sudo().browse(res)
custom = custom.replace('email_from', _('Email'))
custom_label = nl2br_enclose(_("Other Information"), 'h4')
default_field = model_sudo.website_form_default_field_id
default_field_data = values.get(default_field.name, '')
default_field_content = (nl2br_enclose(default_field.name.capitalize(), 'h4')
                         + nl2br_enclose(html2plaintext(default_field_data), 'p'))
custom_content = (default_field_content if default_field_data else '') \
               + (custom_label + custom if custom else '') \
               + (self._meta_label + meta if meta else '')
if default_field.name:
    if default_field.ttype == 'html':
        custom_content = nl2br(custom_content)
    task[default_field.name] = custom_content
    task._message_log(body=custom_content, message_type='comment')
```

After record creation:
1. Reloads the created task via `sudo()` browse.
2. Rebuilds the `custom` text to rename the `email_from` label to a human-readable "Email".
3. Assembles content from three sources: the default field value (`description` by config), the custom fields block, and the metadata block.
4. Writes the assembled content to the default field (`description`).
5. Also posts the content as a `_message_log` (chatter message), creating an audit trail separate from the description field.

**Edge case — `default_field.ttype == 'html'`**: The description field on `project.task` is an HTML field, so `nl2br()` is applied (converts newlines to `<br/>` tags). If the description field type were changed to plain text, this branch would not execute.

---

## Data: `ir.model` Registration and Whitelist

**File**: `data/website_project_data.xml`

```xml
<record id="project.model_project_task" model="ir.model">
    <field name="website_form_key">create_task</field>
    <field name="website_form_default_field_id" ref="project.field_project_task__description" />
    <field name="website_form_access">True</field>
    <field name="website_form_label">Create a Task</field>
</record>

<function model="ir.model.fields" name="formbuilder_whitelist">
    <value>project.task</value>
    <value eval="[
        'name',
        'partner_name',
        'partner_phone',
        'partner_company_name',
        'description',
        'project_id',
        'task_properties',
    ]"/>
</function>
```

| Field | Ir.model Field | Purpose |
|-------|---------------|---------|
| `website_form_key` | `create_task` | Links the `form_editor_actions` registry entry (JS side) to this model registration. |
| `website_form_default_field_id` | `description` | Field where custom+meta content is assembled and written. |
| `website_form_access` | `True` | Enables the form builder for this model. |
| `website_form_label` | `Create a Task` | Human-readable label in the Form Builder UI. |

#### Whitelisted Fields for Form Builder

The `formbuilder_whitelist` call enables these fields as form inputs in the website Form Builder UI:

- `name` — Task subject (required in JS config: `modelRequired: true`)
- `partner_name` — Customer full name (fillWith: `name`)
- `partner_phone` — Customer phone (fillWith: `phone`)
- `partner_company_name` — Company name (fillWith: `commercial_company_name`)
- `description` — Task description (required in JS config)
- `project_id` — Target project (many2one, `required: true`, domain: `is_template = false`)
- `task_properties` — Task properties (json field)

Fields NOT in the whitelist (e.g., `user_ids`, `stage_id`, `priority`) are not exposed in the Form Builder but could still be set programmatically via `website_form_input_filter` hook if needed.

---

## Static JS: Form Builder Field Configuration

**File**: `static/src/js/website_project_editor.js`

```javascript
registry.category("website.form_editor_actions").add('create_task', {
    formFields: [{ ... }],
    fields: [{ name: 'project_id', type: 'many2one', ... }],
    successPage: '/your-task-has-been-submitted',
});
```

| Property | Value | Description |
|----------|-------|-------------|
| `formFields` | Array of field configs | Standard contact-info fields auto-filled from browser/portal data (`fillWith`) |
| `fields` | Array of model-specific fields | `project_id` many2one with domain `is_template = false` |
| `successPage` | `/your-task-has-been-submitted` | Redirect target after successful submission |

**Auto-fill mapping** (`fillWith`):
- `partner_name` → browser `name` field
- `partner_phone` → browser `phone` field
- `email_from` → browser `email` field
- `partner_company_name` → browser `commercial_company_name` field

This leverages the browser's autofill infrastructure for a better UX — returning users see their details pre-populated.

---

## Website Pages and Templates

### Confirmation Page: `/your-task-has-been-submitted`

**File**: `views/project_portal_project_task_template.xml`

```xml
<record id="task_submitted_page" model="website.page">
    <field name="is_published">True</field>
    <field name="url">/your-task-has-been-submitted</field>
    <field name="website_indexed">False</field>
    <field name="view_id" ref="task_submitted"/>
</record>
```

| Property | Value | Note |
|----------|-------|------|
| `is_published` | `True` | Page is publicly accessible |
| `website_indexed` | `False` | Excluded from search engine indexing |
| `url` | `/your-task-has-been-submitted` | Slug-based, translatable URL |

**Template**: `task_submitted` renders:
- A "Thank you!" success message.
- The submitted task ID (via `_website_form_last_record()`).
- A conditional link to `/my/task/<id>` — only shown if: the visitor is logged in (`request.session.uid`), the task has a project, AND `project_privacy_visibility in ['employees', 'portal']`.

The link to `/my/task/<id>` is gated by `task_privacy_visibility` and the presence of a `project_id`, not by `website_published` — this is because portal users who can see the task via project sharing are authorized to view it.

### Portal Template Patches

| Template | Override | Change |
|---------|----------|--------|
| `project.portal_my_project` | `website_portal_my_project` | Sets `additional_title = project.name` |
| `project.portal_my_task` | `website_portal_my_task` | Sets `additional_title = task.name` |

These patches set the page `<title>` tag to the specific task/project name rather than a generic "My Project" or "My Task".

---

## Tests

**File**: `tests/test_project_portal_access.py`

### `test_post_chatter_as_portal_user`

Verifies that a portal user can post a message (chatter) on a task shared via project portal link.

- Sets `privacy_visibility = 'portal'` on the project.
- Extracts `access_token`, `pid`, `hash` from the project share link.
- Makes a POST to `ThreadController().mail_message_post()` under a portal user context via `MockRequest`.
- Asserts the message was created with the portal user's `author_id`.

### `test_portal_task_submission`

Verifies that a completely **public (unauthenticated)** user can submit a task via the website form.

- Calls `self.authenticate(None, None)` to simulate an anonymous session.
- Creates a partner record directly in the test database.
- POSTs to `/website/form/project.task` with form data including an email matching the pre-created partner.
- Asserts the task was created AND that the partner's name is preserved (not overwritten by `partner_name` from the form data).

This test confirms the **partner-overwrite protection**: even though the form sends `partner_name: 'Not Jean Michel'`, the `extract_data()` code finds the existing partner by email and links it, discarding the form-supplied `partner_name` from the record write — so the partner record is not modified.

---

## Workflow Summary: Anonymous Task Submission

```
Public Visitor
    │
    ▼
/website/form/project.task  (POST)
/website/controllers/form.py → WebsiteForm.website_form()
    │
    ▼
WebsiteForm.extract_data()
    ├── _get_form_writable_fields() → authorized_fields
    ├── input_filters applied to each field
    ├── website_form_input_filter() hook (if defined)
    │
    ├── IF email_from found in submission:
    │   └── _partner_find_from_emails_single(email)
    │       ├── IF partner EXISTS:
    │       │   ├── data['record']['partner_id'] = partner.id
    │       │   └── pop partner_name/phone/company → custom text
    │       └── IF partner NOT EXISTS:
    │           ├── data['record']['email_cc'] = email
    │           └── write partner_name/phone/company to record
    │
    ▼
WebsiteForm.insert_record()
    │
    ├── _get_visitor_from_request()
    │   └── IF visitor.partner_id exists:
    │       └── values['partner_id'] = visitor_partner.id  (overrides above)
    │
    ├── values['user_ids'] = False  (prevent OdooBot auto-assignment)
    │
    ├── super().insert_record() → create(project.task, values)
    │
    ├── Assemble custom_content from description + custom + meta
    ├── task[description] = custom_content
    └── task._message_log(body=custom_content)  (audit trail)
            │
            ▼
    Session: form_builder_model_model = 'project.task'
    Session: form_builder_id = <task_id>
            │
            ▼
    JSON response: {'id': <task_id>}
            │
            ▼
    Browser → redirect to /your-task-has-been-submitted
```

---

## L4: Performance, Security, and Edge Cases

### Performance Considerations

1. **Caching control**: `_allow_to_use_cache()` returns `False` for one specific path. The caching check runs on every request to the website page resolver, which is lightweight — a simple string comparison on `request.httprequest.path`. No measurable performance impact.

2. **`website.visitor` lookup on every submission**: `insert_record()` calls `_get_visitor_from_request()` for every `project.task` form submission. This hits the visitor-tracking middleware. For high-traffic sites, this is a minor query per submission — acceptable given the savepoint in the parent route already limits transaction scope.

3. **`sudo()` on record reload**: After `insert_record()` returns the ID, the controller does `request.env['project.task'].sudo().browse(res)`. For portal users who can see the task via project sharing, this `sudo()` bypasses record rules only to read the task for description assembly. Write operations after creation use the normal ACL-checked environment.

4. **Stored related fields**: `partner_name` and `partner_company_name` are stored, meaning any change to `partner_id.name` or `partner_id.company_name` triggers recomputation of these fields via the ORM's dependency tracking. This is a one-time write per task creation, not a real-time dependency.

### Security Considerations

1. **Public CSRF**: The `/website/form/<model_name>` route has `csrf=False` and `auth="public"`. The comment in the code explains that CSRF is only enforced for authenticated sessions (SameSite cookie policy causes session loss for embedded forms). Public form submissions are inherently at risk of spam/automated abuse. Rate limiting and captcha (`captcha='website_form'`) are the mitigations — the captcha is enabled via route kwarg.

2. **Field whitelisting**: `formbuilder_whitelist` is the authoritative gate. Even if an attacker submits extra POST fields, only whitelisted fields in `_get_form_writable_fields()` are processed. The `website_form_access = True` flag on `ir.model` must also be set.

3. **`values.setdefault('user_ids', False)`**: This prevents tasks submitted from the website from being assigned to `OdooBot` (the default behavior when `user_ids` is not in the create vals). Without this, every website-submitted task would have a spurious OdooBot assignment. Setting `False` creates an empty recordset assignment.

4. **Partner overwrite protection**: When `_partner_find_from_emails_single()` finds an existing partner, `partner_name`/`partner_phone`/`partner_company_name` are moved to `custom` text and not written to the task record's direct fields. This prevents a website form submission from modifying an existing partner's data. The test `test_portal_task_submission` explicitly validates this.

5. **Visitor partner vs. email partner priority**: In `insert_record()`, the visitor's partner always overrides whatever partner was resolved by email in `extract_data()`. This is correct behavior: a logged-in portal user submitting a form should have the task linked to their own partner identity, not to some partner that shares the submitted email address.

### Historical Changes (Odoo 18 → 19)

The module is small and largely unchanged between Odoo 18 and 19. Key observations:

- **`website_published` on `project.project`**: This field is defined in the base `project` module (in `project/models/project.py`), not in `website_project`. The `website_project` module does NOT add or modify `website_published` behavior.
- **Form Builder integration**: The pattern of `formbuilder_whitelist` + `ir.model` record + JS `registry.category("website.form_editor_actions")` is the stable Odoo approach for custom model forms and is consistent across versions 17–19.
- **Confirmation page URL**: The URL `/your-task-has-been-submitted` has been stable since at least Odoo 16. The `website_indexed = False` flag was added in Odoo 16+ to prevent search engine indexing of these dynamic confirmation pages.
- **Stored related fields** (`partner_name`, `partner_company_name`): The `store=True, readonly=False` pattern on related fields was introduced as a recommended practice in Odoo 16+ to support Form Builder writeback scenarios.

### Edge Cases

1. **Task submitted by authenticated portal user who is NOT a follower of the project**: The task is still created. Portal access to the project via `project_privacy_visibility = 'portal'` grants the ability to view the shared project and its tasks in the portal. The task creation itself does not require project follow permissions.

2. **Task submitted with a project_id that is a template** (`is_template = True`): The Form Builder JS domain filter `[is_template, =, false]` prevents this in the UI. An API-level attacker could POST with a template project ID. The ORM would accept it (no SQL constraint), but this would likely cause downstream issues (e.g., template tasks have special handling in project kanban views). No explicit server-side guard exists.

3. **Visitor with no partner but form email matches existing partner**: `extract_data()` finds the partner and links it. `insert_record()` then overwrites with the visitor's `partner_id` if the visitor has one. If the visitor is anonymous (no partner), the email-resolved partner is used. This is the intended precedence order.

4. **Duplicate task submission (double-POST)**: The parent route wraps everything in a savepoint. If the response JSON is returned but the client re-sends (browser back button, network retry), a duplicate task will be created. Odoo does not have built-in idempotency for website form submissions. Client-side form disabling after submit is the expected UX mitigation.

5. **`description` field type change**: If a system administrator changes `project.task.description` from HTML to plain text (`ttype != 'html'`), the `insert_record()` override will still write to it but the `nl2br()` call will not happen. Custom content containing newlines would then be stored as plain text — the `<h4>` headings from `nl2br_enclose` would still be applied via the template string formatting, not as HTML.

---

## Cross-Module Integration Map

```
website_project
    │
    ├── EXTENDS project.task
    │       fields: partner_name, partner_company_name (related, stored)
    │
    ├── EXTENDS website.page
    │       method: _allow_to_use_cache() — cache control
    │
    ├── EXTENDS WebsiteForm (website/controllers/form.py)
    │       overrides: extract_data(), insert_record()
    │
    ├── OVERRIDES project.portal_my_project (template)
    │       sets: additional_title
    │
    ├── OVERRIDES project.portal_my_task (template)
    │       sets: additional_title
    │
    ├── DEPENDS ON website
    │       Form Builder, visitor tracking, portal layout
    │
    ├── DEPENDS ON project
    │       project.task, project.project models
    │
    └── ASSERTS VIA tests/
            test_project_portal_access.py
            ├── test_post_chatter_as_portal_user
            └── test_portal_task_submission
```

---

## Related Modules

- [[Modules/website]] — Website builder, Form Builder, visitor tracking
- [[Modules/project]] — Project and task models, portal templates
- [[Modules/website_project]] — Meeting-based project page integration on website

## Tags

#odoo19 #modules #website #project #portal #form-builder
