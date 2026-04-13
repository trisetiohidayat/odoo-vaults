# Module Install Request (base_install_request)

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | Base - Module Install Request |
| **Technical Name** | `base_install_request` |
| **Category** | Hidden |
| **License** | LGPL-3 |
| **Auto Install** | Yes |

## Description

Allow internal users to request module installation from administrators via email workflow.

## Dependencies

- [Modules/mail](odoo-18/Modules/mail.md)

## Key Features

1. **Request Access Button** - Users can request module installation
2. **Email Notification** - Sends request to administrators
3. **Admin Review** - Shows all dependent apps to be installed
4. **Install Wizard** - One-click module installation

## Models

### base.module.install.request

| Field | Type | Description |
|-------|------|-------------|
| `module_id` | Many2one | Module to request |
| `user_id` | Many2one | Requesting user |
| `body_html` | Html | Justification message |

### base.module.install.review

| Field | Type | Description |
|-------|------|-------------|
| `module_id` | Many2one | Module to install |
| `modules_description` | Html | Dependent apps preview |

## Workflow

```
User clicks "Request Access"
    → User enters justification
    → Email sent to administrators
    → Admin reviews (shows dependencies)
    → Admin clicks "Install"
```

## Related

- [Modules/mail](odoo-18/Modules/mail.md)
- [Modules/base_import_module](odoo-18/Modules/base_import_module.md)
