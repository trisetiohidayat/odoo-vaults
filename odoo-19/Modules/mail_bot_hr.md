---
title: OdooBot HR
description: Bridge between OdooBot (mail_bot) and the HR module. Adds the OdooBot notification alert widget to HR-modified user preference forms.
tags: [odoo19, hr, mail, bot, chat, odoobot, notification, module]
model_count: 0
models: []
dependencies:
  - mail_bot
  - hr
category: Productivity/Discuss
source: odoo/addons/mail_bot_hr/
created: 2026-04-14
uuid: f9b2d6c3-4e1a-8f7d-4b5c-9a3e7d2b8f1c
---

# OdooBot HR

## Overview

**Module:** `mail_bot_hr`
**Category:** Productivity/Discuss
**Depends:** `mail_bot`, `hr`
**Auto-install:** True
**License:** LGPL-3
**Author:** Odoo S.A.

`mail_bot_hr` is the thinnest possible bridge module: a single XML view modification that integrates OdooBot into the HR-modified user preference forms. It contains no Python models, no data files, and no business logic. Its sole purpose is to make the OdooBot notification alert widget (`notification_alert`) appear in the correct position within the HR app's customized user forms.

OdooBot is Odoo's built-in AI assistant. When enabled (via the `mail_bot` module), it participates in the Discuss app as a bot contact, responds to slash commands (`/help`, `/whoami`, `/stats`), and displays a notification badge in the top navigation bar. The `notification_alert` widget is a frontend component that renders this notification state.

The HR module overrides the `res.users` form views to add HR-specific fields (employee profile, department, job title). The `mail_bot_hr` module then takes those HR-overridden views and inserts the `notification_alert` widget.

## Module Structure

```
mail_bot_hr/
├── __init__.py
├── __manifest__.py
└── views/
    └── res_users_views.xml  # Two view inherits: inserts notification_alert widget
```

That is the entire module. Two XML records, no Python code.

## View Modifications

File: `views/res_users_views.xml`

The module modifies two distinct form views for `res.users`:

### 1. Simplified Preferences Form

**Record:** `res_users_view_form_simple_modif`
**Target:** `hr.res_users_view_form_simple_modif` (HR's simplified user preferences form)
**Priority:** `15` (overrides HR's priority-10 form)

```xml
<record id="res_users_view_form_simple_modif" model="ir.ui.view">
    <field name="name">res.users.preferences.form.simplified.inherit</field>
    <field name="model">res.users</field>
    <field name="inherit_id" ref="hr.res_users_view_form_simple_modif"/>
    <field name="priority">15</field>
    <field name="arch" type="xml">
        <widget name="notification_alert" position="replace"/>
    </field>
</record>
```

This is a `position="replace"` operation. The HR module likely placed a placeholder `notification_alert` widget in this form, and `mail_bot_hr` replaces it with the actual widget implementation. Since `mail_bot_hr` has a higher priority (15 > 10), its view wins over HR's version.

The "simplified preferences form" is the quick-access user preferences panel accessible via the user menu (top-right avatar), used for changing password, language, and notification settings without leaving the current page.

### 2. Full Profile Form

**Record:** `res_users_view_form_preferences`
**Target:** `hr.res_users_view_form_preferences` (HR's full user profile form)
**Priority:** default (16, which overrides HR's priority-10 version)

```xml
<record id="res_users_view_form_preferences" model="ir.ui.view">
    <field name="name">res.users.profile.form.inherit</field>
    <field name="model">res.users</field>
    <field name="inherit_id" ref="hr.res_users_view_form_preferences"/>
    <field name="arch" type="xml">
        <sheet position="before">
            <widget name="notification_alert"/>
        </sheet>
    </field>
</record>
```

This inserts the `notification_alert` widget at the top of the form, before the `<sheet>` element (which contains the user's personal information). The widget appears as a banner or alert box at the very top of the user profile form.

The "profile form" is the full `res.users` form accessible from **Settings > Users & Companies > Users**, which is customized by the HR module to show employee details alongside user credentials.

## The `notification_alert` Widget

The `notification_alert` widget is a JavaScript component defined in the `mail_bot` module. It renders the OdooBot notification state. In its default form, it shows:
- A colored badge or alert indicating the OdooBot status
- Any pending notifications or tips for the user
- An interactive element (often a chat bubble or icon)

This widget is the visual manifestation of OdooBot's presence in the HR context. Without `mail_bot_hr`, the widget would not appear on the HR-modified user forms, and HR users would not see OdooBot notifications in their HR app session.

## Why Two View Inherits?

The module targets two separate `res.users` form views:

| View | Purpose | Access Path |
|------|---------|-------------|
| `res_users_view_form_simple_modif` | Quick preferences | User menu → Preferences |
| `res_users_view_form_preferences` | Full profile | Settings → Users → Form |

The HR module overrides both of these views to add HR-specific fields. The `mail_bot_hr` module takes over from where HR left off and adds the OdooBot widget. This two-tier approach ensures OdooBot is visible regardless of how the user accesses their profile.

## Inheritance Chain

Understanding the view resolution order:

```
1. base/res_users_view_form_simple_modif (base module, priority=16)
   └── Injected by: base module's minimal user form

2. hr/res_users_view_form_simple_modif (hr module, priority=10)
   └── Inherits from: base view
   └── Adds: employee_id, department_id, job_title fields

3. mail_bot_hr/res_users_view_form_simple_modif (mail_bot_hr, priority=15)
   └── Inherits from: hr view
   └── Action: replaces notification_alert widget
   └── Result: OdooBot widget appears in simplified HR preferences
```

```
1. base/res_users_view_form_preferences (base module, priority=16)
   └── Injected by: base module's full user form

2. hr/res_users_view_form_preferences (hr module, priority=10)
   └── Inherits from: base view
   └── Adds: employee_id, department_id, job_title fields

3. mail_bot_hr/res_users_view_form_preferences (mail_bot_hr, default priority=16)
   └── Inherits from: hr view
   └── Action: inserts notification_alert before sheet
   └── Result: OdooBot widget appears at top of HR full profile
```

## What OdooBot Does

OdooBot (from the `mail_bot` module) is an AI assistant accessible in Odoo's Discuss app. It provides:

- **Onboarding tips** -- When a new employee logs in, OdooBot sends a welcome message with getting-started tips.
- **Slash commands** -- Users can type `/help` to see available commands, `/whoami` to see their profile, `/stats` for usage statistics.
- **Automation suggestions** -- OdooBot can suggest workflow automations based on user behavior.
- **Fun interactions** -- Easter eggs like `/coffee` (random coffee GIF), `/giphy` (search GIFs).

In the HR context, OdooBot is particularly useful for onboarding new employees. When a new employee record is created in HR and a portal user is assigned, OdooBot can send them a welcome message through the Discuss app.

## Relationship to Other Modules

| Module | Role | Relationship |
|--------|------|-------------|
| `mail_bot` | OdooBot core | Defines the `notification_alert` widget and OdooBot logic |
| `hr` | HR app | Overrides `res.users` views to add employee fields |
| `mail_bot_hr` | Bridge | Inherits HR views to insert OdooBot widget |
| `mail` | Messaging | The Discuss app and channel system OdooBot uses |

## Security

Since this module adds no data access, it requires no additional ACL entries. It inherits the security model of the views it modifies:

- `res.users` form access is controlled by `hr` module ACLs
- The `notification_alert` widget respects the current user's access rights
- No new records are created, so no data access is granted or restricted

## Extension Points

| Extension Point | How to Extend |
|-----------------|---------------|
| Widget position | Change `position="before"` to `position="after"` or `position="inside"` to reposition the widget |
| Widget customization | Override the `notification_alert` template in a child module |
| New form views | Add similar view inherits for any additional `res.users` forms created by other modules |
| Widget conditional display | Add `attrs` or `invisible` conditions to show the widget only for certain user groups |

## Related

- [Modules/mail_bot](Modules/mail_bot.md) -- OdooBot core: AI assistant, slash commands, onboarding
- [Modules/hr](Modules/HR.md) -- HR module: employee records, HR-modified user forms
- [Modules/mail](Modules/mail.md) -- Messaging infrastructure: channels, messages, Discuss app
- [Modules/hr_skills](Modules/hr_skills.md) -- HR Skills: resume lines, skills tracking
- [Modules/hr_skills_event](Modules/hr_skills_event.md) -- HR Skills Event: onsite training resume lines
- [Modules/hr_skills_survey](Modules/hr_skills_survey.md) -- HR Skills Survey: certification resume lines


## The Two-View Inheritance Pattern Explained

Understanding why `mail_bot_hr` overrides two separate views requires understanding Odoo's view inheritance mechanism.

### Odoo's View Priority System

Odoo resolves view conflicts using the `priority` field on `ir.ui.view`:
- Lower priority numbers load first (higher priority)
- When two views inherit from the same parent, the one with the lower priority "wins"
- `priority=10` loads before `priority=16`

The HR module uses `priority=10` (a common convention for "primary" view modifications). The `mail_bot_hr` module uses `priority=15` for the simplified form and the default priority for the full form, which means it loads after HR's modifications but before the base view.

### The Simplified Preferences Form

**Record ID:** `res_users_view_form_simple_modif`
**Path:** User menu (top-right avatar) → Preferences
**Purpose:** Quick access to change password, language, and notification preferences without leaving the current page.

HR adds to this form:
- `employee_id` field linking to the HR employee record
- `department_id` showing the employee's department
- `job_title` field

`mail_bot_hr` then takes this HR-modified form and performs a `position="replace"` on the `notification_alert` widget. The `replace` means it removes whatever widget was there and substitutes the real OdooBot notification component.

### The Full Profile Form

**Record ID:** `res_users_view_form_preferences`
**Path:** Settings → Users & Companies → Users → click a user
**Purpose:** Comprehensive user profile including HR data, credentials, and preferences.

HR adds to this form:
- Employee tab with personal information (birthday, SSN, etc.)
- Department and manager information
- HR-specific configuration

`mail_bot_hr` inserts the `notification_alert` widget before the `<sheet>` element using `position="before"`. This places it as a banner above all the user information fields.

### Why `position="replace"` vs `position="before"`?

The different positioning strategies reflect different UI goals:
- The simplified form replaces an existing placeholder widget, likely because HR positioned a stub that needed completion
- The full form inserts above the sheet, which is the standard Odoo pattern for alert banners and contextual notices

## The OdooBot Onboarding Journey

OdooBot's primary HR-related function is employee onboarding. When a new employee record is created with a user account, OdooBot can initiate a structured onboarding conversation:

### Step 1: New Employee User Account Created

An HR administrator creates a user account for a new hire:
- `res.users` record created with login, email, and groups
- The user belongs to the `Internal User` group (or a specific department group)
- OdooBot detects the new user through the `mail.channel` subscription

### Step 2: OdooBot Sends Welcome Message

OdooBot automatically sends a welcome message in the user's personal Discuss channel:

```
OdooBot: Welcome to the team! 👋
I'm OdooBot, your digital assistant.
Here are some things I can help you with:

• Type /help to see all available commands
• Type /whoami to see your profile
• Type /stats to see your activity summary

Need help getting started? Just ask!
```

### Step 3: Slash Commands for New Employees

New employees can use slash commands to quickly get oriented:

- `/help` -- Lists all available OdooBot commands with descriptions
- `/whoami` -- Displays the user's own profile information
- `/steps` -- Shows onboarding checklist (if configured by HR)
- `/calendar` -- Shows today's calendar (integrates with calendar module)
- `/tasks` -- Shows pending tasks from the project module

### Step 4: HR Automation with OdooBot

HR can create automation rules that trigger OdooBot messages:

1. **30-day check-in**: After 30 days, OdooBot asks: "How is your onboarding going?"
2. **Training completion**: When an employee completes a certification, OdooBot congratulates them
3. **Birthday reminder**: OdooBot sends birthday wishes on the employee's birthday
4. **Goal review**: Quarterly, OdooBot prompts employees to update their goals

These automations are implemented via `mail.channel` subscriptions and `bus.bus` notifications triggered from HR models.

## Technical: How the `notification_alert` Widget Works

The `notification_alert` widget is a JavaScript web component defined in `mail_bot/static/src/js/mail_bot.js`. It subscribes to the `"mail_notification_alert"` bus channel:

```javascript
// Conceptual (not actual source):
const notificationChannel = 'mail_notification_alert';

Bus.on(notificationChannel, (payload) => {
    // payload: { title, message, type, actions }
    this.displayAlert(payload);
});
```

When OdooBot posts a notification, the payload is pushed to this channel and the widget renders it in the user form. The widget appears as a colored banner at the top of the form with:
- An icon (info/warning/success icon)
- The notification title
- The notification message
- Optional action buttons (e.g., "Dismiss", "Open", "Learn More")

In the HR context, this means OdooBot notifications appear directly on the user profile page, keeping new employees informed without leaving the HR app.

## View Priority Reference

| View | Module | Priority | Purpose |
|------|--------|----------|---------|
| `base.res_users_view_form_simple_modif` | `base` | 16 | Base simplified preferences |
| `hr.res_users_view_form_simple_modif` | `hr` | 10 | Adds employee fields |
| `mail_bot_hr.res_users_view_form_simple_modif` | `mail_bot_hr` | 15 | Replaces notification_alert |
| `base.res_users_view_form_preferences` | `base` | 16 | Base full profile form |
| `hr.res_users_view_form_preferences` | `hr` | 10 | Adds employee fields |
| `mail_bot_hr.res_users_view_form_preferences` | `mail_bot_hr` | 16 (default) | Inserts notification_alert |
