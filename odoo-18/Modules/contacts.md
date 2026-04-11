---
Module: contacts
Version: Odoo 18
Type: Business
---

# contacts — Contact Management Application

## Overview

The `contacts` module (`addons/contacts/`) is an Odoo application module that provides a **centralized address book** interface for managing contacts. It extends the base `res.partner` model with a dedicated menu, kanban/list/form views, and a contact-specific home screen with systray integration.

**Key architectural note**: This module does **not** add new fields to `res.partner`. It layers application-level UX on top of the existing partner model — views, menus, and user experience features. All actual partner fields live in the `base` module.

**Depends**: `base`, `mail`
**Category**: Sales/CRM
**Application**: Yes
**License**: LGPL-3

---

## Module Structure

```
contacts/
├── __manifest__.py          # Module declaration, depends, views, demo data
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── res_partner.py       # Partner extension (root menu override)
│   └── res_users.py         # Users extension (systray icon override)
├── views/
│   └── contact_views.xml     # Action + menu definitions
└── tests/                   # Tour tests
```

---

## Models

### `res.partner` — Contact / Partner Record

**File**: `models/res_partner.py`

The contacts module **extends** `res.partner` with a single override.

```python
class Partner(models.Model):
    _inherit = "res.partner"

    def _get_backend_root_menu_ids(self):
        """ Adds contacts as a root-level app menu alongside the default app menus. """
        return super()._get_backend_root_menu_ids() + [self.env.ref('contacts.menu_contacts').id]
```

**L4 — What this override does**: By default, Odoo's app launcher only shows modules that define their own root menu. Adding `contacts.menu_contacts` to the returned list makes the **Contacts** app appear in the Odoo backend's sidebar/app launcher alongside Sale, Purchase, etc., even though `res.partner` is a core model.

This is a pure UX override. No fields, no constraints, no records.

---

### `res.users` — User Record

**File**: `models/res_users.py`

```python
class Users(models.Model):
    _name = 'res.users'
    _inherit = ['res.users']

    @api.model
    def _get_activity_groups(self):
        """ Update the systray icon of res.partner activities to use the
        contact application one instead of base icon. """
        activities = super()._get_activity_groups()
        for activity in activities:
            if activity['model'] != 'res.partner':
                continue
            activity['icon'] = modules.module.get_module_icon('contacts')
        return activities
```

**L4 — Systray Integration**: Internal users see a notification bell (systray) for pending activities on partners. By default, the base module would show the generic partner icon. This override swaps it for the Contacts app icon, so the systray activity for partners looks like it belongs to the Contacts app.

---

## Views (XML)

**File**: `views/contact_views.xml`

### Action: `action_contacts`

```xml
<field name="view_mode">kanban,list,form,activity</field>
<field name="context">{'default_is_company': True}</field>
```

- Default view is **Kanban** (contact cards) — not the form.
- Context sets `default_is_company = True`, meaning creating from this view creates a **company** record by default. Individual contacts are created from within a company form.
- Reuses base view definitions: `base.res_partner_kanban_view`, `base.view_partner_tree`, `base.view_partner_form`.
- Search view: `base.view_res_partner_filter` (shared with base).

### Menu Structure

```
Contacts (root menu, icon: contacts,static/description/icon.png)
└── Contacts          → action_contacts              (kanban/list/form/activity)
└── Configuration     (only base.group_system)
    ├── Contact Tags  → base.action_partner_category_form
    ├── Contact Titles → base.action_partner_title_contact
    ├── Industries    → base.res_partner_industry_action
    ├── Localization  (countries, states, country groups)
    │   ├── Countries
    │   ├── States
    │   └── Country Groups
    └── Bank Accounts (bank + partner bank account forms)
```

---

## What `contacts` Adds vs. Base `res.partner`

| Aspect | Base (`base`) | Contacts (`contacts`) |
|--------|---------------|----------------------|
| Partner fields | All fields defined here | None added |
| Menu entry | No dedicated menu | Dedicated "Contacts" app with icon |
| Root app visibility | Not in app launcher | Visible in sidebar/app launcher |
| Systray activity icon | Generic partner icon | Contacts app icon |
| Default view | Form | Kanban board |
| Default partner type | `is_company = False` | `is_company = True` (context) |
| Contact Tags | Accessible via Settings | First item in Configuration |
| Localization config | Deep in Settings | First-class submenu |

---

## Key Design Decisions (L4)

1. **No field additions**: The contacts module intentionally adds zero fields to `res.partner`. It is a pure application/presentation layer over the base partner model.

2. **Delegation to base views**: Rather than redefining form/list/kanban views, it references existing base views. This means any field a third module adds to `res.partner` automatically appears in contacts views.

3. **Company-first default**: The `default_is_company: True` context means the contacts app encourages users to create company records first, then add individual contact persons as children. This mirrors the standard B2B contact hierarchy (commercial entity + contacts).

4. **Mail dependency**: The `mail` module dependency exists because the systray notification system (and any chatter on partner records) requires the mail module's activity tracking infrastructure.

5. **`_get_backend_root_menu_ids` pattern**: This is the official Odoo pattern for making a non-website module appear as a root-level app in the backend sidebar. The same pattern is used by Sale, Purchase, etc.

---

## Related Models (No Direct Changes)

- `res.partner.category` — Contact tags (categories). Managed in contacts Configuration menu via `base.action_partner_category_form`.
- `res.partner.title` — Contact titles (Mr, Ms, Dr). Managed via `base.action_partner_title_contact`.
- `res.country`, `res.country.state` — Countries and states. Both accessible from contacts Configuration > Localization.
- `res.bank`, `res.partner.bank` — Bank accounts accessible from Configuration > Bank Accounts.

---

## Integration Points

| Module | Integration |
|--------|------------|
| `mail` | Activity notifications routed to Contacts app icon in systray |
| `base` | Reuses base partner views, search, and category/title/industry models |
| `portal` | Portal-enabled partners can access their own contact data via portal |

---

## Tags

`#odoo` `#odoo18` `#modules` `#contacts` `#res.partner` `#ux`
