# mail_bot_hr

Odoo 19 Productivity/Human Resources Module

## Overview

`mail_bot_hr` is a **bridge module** between `mail_bot` (OdooBot) and `hr` (Human Resources). It integrates OdooBot into the HR app, displaying OdooBot state and notifications in the HR-modified user form.

## Module Details

- **Category**: Productivity/Discuss
- **Depends**: `mail_bot`, `hr`
- **Version**: 1.0
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Functionality

Adds OdooBot interaction to HR-managed user forms:
- Displays OdooBot status in the employee/user form modified by `hr`.
- Enables OdooBot's `/help` and other commands in the HR app context.
- This is a thin bridge — no additional Python models. The HR view modifications in `views/res_users_views.xml` add OdooBot widgets to user forms.

## Relationship to Other Modules

| Module | Role |
|---|---|
| `mail_bot` | OdooBot core (OdooBot AI assistant) |
| `hr` | Human Resources app |
| `mail_bot_hr` | Bridge — OdooBot in HR user forms |
