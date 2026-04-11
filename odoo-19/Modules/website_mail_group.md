---
tags:
  - #odoo19
  - #modules
  - #website
  - #mail
---

# website_mail_group

## Overview

| Property | Value |
|----------|-------|
| Module | `website_mail_group` |
| Path | `odoo/addons/website_mail_group/` |
| Category | Website / Email |
| Dependencies | `website`, `mail_group` |
| Key Concept | Redirect mail group to website page |

---

## Purpose

Provides a website-accessible action on `mail.group` records, enabling users to navigate from the back-office mail group to its public website page. This module adds a "View on Website" button to mail group forms.

---

## Architecture

### Inheritance Chain

```
mail.group                    (mail_group module)
    └── MailGroup
            _inherit = 'mail.group'
            └── website_mail_group
```

This is a **minimal module** -- a single method override on the existing `mail.group` model.

---

## Key Models

### `mail.group` (Extended)

**File:** `models/mail_group.py`

#### `action_go_to_website()`

Opens the mail group's public page on the website.

```python
class MailGroup(models.Model):
    _inherit = 'mail.group'

    def action_go_to_website(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/groups/%s' % self.env['ir.http']._slug(self),
        }
```

**Behavior:**
- `ensure_one()` -- only works on a single record
- Generates URL: `/groups/<slugified-group-name>`
- Opens in the current tab (`target: 'self'`)
- Uses `ir.http._slug()` to create a URL-safe slug from the group name

---

## Data Flow

```
User clicks "View on Website" button on mail.group form
        │
        ▼
  action_go_to_website() called
        │
        ▼
  /groups/<slug> URL generated
        │
        ▼
  Website page for mail group displayed
  (handled by website_mail_group controllers)
```

---

## Related Modules

| Module | Role |
|--------|------|
| `mail_group` | Core mail group model (`mail.group`) |
| `website` | Website framework, slug generation |
| `website_mail` | Website-specific mail group pages |

---

## Key Code Pattern

```python
# One-method extension on mail.group
class MailGroup(models.Model):
    _inherit = 'mail.group'

    def action_go_to_website(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/groups/%s' % self.env['ir.http']._slug(self),
        }
```

---

## URL Slugification

The `_slug()` method from `ir.http` converts a record's name into a URL-safe string:

```
"Marketing Team"  →  "marketing-team-12"
"All Staff"      →  "all-staff-5"
```

Where the trailing number is the record's ID, ensuring uniqueness.

---

## Related Documentation

- [[Modules/Mail]] -- Mail threading and group infrastructure
- [[Modules/Website]] -- Website framework
