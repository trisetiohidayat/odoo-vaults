---
tags:
  - odoo
  - odoo19
  - website
  - mass_mailing
  - sms
  - newsletter
  - subscription
  - modules
  - cross-module
summary: "Adds SMS phone number subscription to the website newsletter block, enabling visitors to subscribe to mailing lists via mobile number alongside or instead of email."
description: |
  `website_mass_mailing_sms` extends the website newsletter subscription block from `website_mass_mailing` to support SMS-based subscription. It adds a phone number input field to the newsletter form snippet, allowing visitors to provide their mobile number. The module's controller override (`MassMailController`) handles the subscription logic by resolving phone numbers to the `mailing.contact` record using the mobile field, while the website builder snippet template (`s_newsletter_sms_notifications`) provides the branded UI component that website visitors interact with.

  This enables businesses to capture leads via SMS, grow their SMS marketing audience alongside their email list, and provide a unified subscription experience on the website.
---

# Website Mass Mailing SMS (`website_mass_mailing_sms`)

## Overview

| Property | Value |
|----------|-------|
| **Module** | `website_mass_mailing_sms` |
| **Category** | Website / Website |
| **Depends** | `website_mass_mailing`, `mass_mailing_sms` |
| **Auto-install** | `True` |
| **Version** | `1.0` |
| **License** | LGPL-3 |
| **Odoo** | 19.0 |

`website_mass_mailing_sms` adds a phone number subscription option to the website newsletter block. It allows visitors to subscribe to a mailing list using their mobile number, complementing (or replacing) the email-based subscription that `website_mass_mailing` provides. When a visitor submits their phone number, Odoo creates or updates a `mailing.contact` record with the mobile number, making them available for SMS marketing campaigns.

## Architecture

### Dependency Chain

```
base
  └── mass_mailing (mailing.mailing, mailing.contact, mailing.list)
        └── mass_mailing_sms (SMS composer, mobile field on mailing.contact)
              └── website_mass_mailing_sms  ← this module
                    
  └── website (website, ir.http, MassMailController)
        └── website_mass_mailing (newsletter snippets, subscription controller)
              └── website_mass_mailing_sms  ← this module
```

The module bridges two dependency trees: the SMS infrastructure tree (`mass_mailing_sms`) and the website subscription tree (`website_mass_mailing`). The `website_mass_mailing` module provides the base newsletter subscription controller that `website_mass_mailing_sms` overrides.

### Two-Part Architecture

The module's contribution consists of two distinct parts:

1. **Controller Override** (`MassMailController`): Overrides two methods to handle `mobile` as a subscription type, resolving phone numbers to `mailing.contact` records.
2. **Website Snippet**: Adds a branded SMS newsletter snippet template (`s_newsletter_sms_notifications`) with phone number input, available in the website editor.

## Controller Changes

### `MassMailController` (Extended from `website_mass_mailing`)

```python
# Source: odoo/addons/website_mass_mailing_sms/controllers/main.py
from odoo.http import request
from odoo.addons.mass_mailing.controllers import main


class MassMailController(main.MassMailController):

    def _get_value(self, subscription_type):
        """Resolve the contact value (email or phone) based on subscription type."""
        value = super(MassMailController, self)._get_value(subscription_type)
        if not value and subscription_type == 'mobile':
            if not request.env.user._is_public():
                # Logged-in user: use their partner's phone
                value = request.env.user.partner_id.phone
            elif request.session.get('mass_mailing_mobile'):
                # Returning visitor: use session-stored phone
                value = request.session['mass_mailing_mobile']
        return value

    def _get_fname(self, subscription_type):
        """Return the field name to use for this subscription type."""
        value_field = super(MassMailController, self)._get_fname(subscription_type)
        if not value_field and subscription_type == 'mobile':
            value_field = 'mobile'  # Field on mailing.contact
        return value_field
```

#### Method Details

##### `_get_value(subscription_type)`

Returns the actual contact value (email address or phone number) based on the subscription type:

| `subscription_type` | Normal Return | SMS Override | Logic |
|-------------------|-------------|-------------|-------|
| `email` | Email from form input | (unchanged) | Provided by parent |
| `mobile` | N/A | Phone number | Logged-in user: `user.partner_id.phone`; Anonymous: `session['mass_mailing_mobile']` |

The method first calls `super()` — which handles the standard `email` case — and only intervenes when `subscription_type == 'mobile'` and the parent method returned nothing.

##### `_get_fname(subscription_type)`

Returns the field name on `mailing.contact` where the value should be stored:

| `subscription_type` | Field | Notes |
|-------------------|-------|-------|
| `email` | `email` | Standard email field on `mailing.contact` |
| `mobile` | `mobile` | Mobile phone field on `mailing.contact` (added by `mass_mailing_sms`) |

The `mass_mailing_sms` module adds the `mobile` field to `mailing.contact`, and this override tells the subscription controller to use that field for phone number subscriptions.

## Website Snippet

### Template: `s_newsletter_sms_notifications`

```xml
<!-- Source: odoo/addons/website_mass_mailing_sms/views/snippets/snippets_templates.xml -->
<template id="s_newsletter_sms_notifications" name="SMS Notifications">
    <section class="s_newsletter_sms_notifications s_newsletter_list pt64 pb64 o_colored_level o_cc o_cc2"
             data-name="SMS Notifications"
             data-list-id="0">
        <div class="container">
            <div class="row o_grid_mode" data-row-count="7">
                <!-- Image column -->
                <div class="o_grid_item ...">...</div>
                <!-- SMS subscription form column -->
                <div class="o_grid_item o_cc o_cc1 ...">
                    <h2 class="h3-fs" style="text-align: center;">
                        Stay in the Loop !<br/>Get the latest updates
                    </h2>
                    <p style="text-align: center;">
                        Be the first to find out all the latest new, products and trends.
                    </p>
                    <!-- Snippet call renders the subscription form -->
                    <t t-snippet-call="website_mass_mailing_sms.s_newsletter_subscribe_form">
                        <t t-set="thank_you_message">
                            <p class="h6-fs ...">
                                <i class="fa fa-check-circle-o fa-lg"/>
                                Thanks for registering!
                            </p>
                        </t>
                    </t-snippet-call>
                </div>
                <!-- Second image column (hidden on mobile) -->
                <div class="o_grid_item ...">...</div>
            </div>
        </div>
    </section>
</template>
```

### Template: `s_newsletter_subscribe_form`

```xml
<!-- Overrides website_mass_mailing.s_newsletter_subscribe_form, sets type=tel, name=mobile -->
<template id="s_newsletter_subscribe_form" inherit_id="website_mass_mailing.s_newsletter_subscribe_form" primary="True">
    <!-- Change CSS class from s_newsletter_list to s_subscription_list -->
    <xpath expr="//div[contains(@t-attf-class, 's_newsletter_subscribe_form')]" position="attributes">
        <attribute name="t-attf-class" add="s_subscription_list" remove="s_newsletter_list" separator=" "/>
    </xpath>
    <!-- Change input from email to tel (phone number) -->
    <xpath expr="//input" position="attributes">
        <attribute name="type">tel</attribute>
        <attribute name="name">mobile</attribute>
        <attribute name="placeholder">+1 555-555-1234</attribute>
    </xpath>
</template>
```

### Template Snippet Replacement

```xml
<!-- Inherit the website snippet panel to replace the newsletter snippet -->
<template id="snippets" inherit_id="website.snippets">
    <xpath expr="//t[@id='mass_mailing_newsletter_sms_notifications_hook']" position="replace">
        <t t-snippet="website_mass_mailing_sms.s_newsletter_sms_notifications"
           string="Newsletter SMS Notifications"
           t-forbid-sanitize="form"
           group="contact_and_forms">
            <keywords>updates, digest, bulletin, announcements, notifications, communication,
                      promotional, sms, alert, dialog, prompt, subscription, subscribe, news
            </keywords>
        </t>
    </xpath>
</template>
```

## How Subscription Works

### Submission Flow

```
Visitor enters phone number in newsletter form
          │
          ▼
Website Form Submit (POST /web/subcribe)
          │
          ▼
MassMailController._subscribe()
          │
          ├── subscription_type = 'mobile'
          ├── _get_value('mobile') → phone number
          └── _get_fname('mobile') → 'mobile'
                    │
                    ▼
mailing.contact record created/updated
          │
          ├── name: From session or "Unknown"
          ├── mobile: +1 555-555-1234
          └── list_ids: [configured mailing list]
```

### Subscription Record Resolution

When a phone number is submitted:
1. The controller calls `mailing.contact` to find an existing contact with the same mobile number.
2. If found, the existing contact is updated (e.g., subscription lists are added).
3. If not found, a new `mailing.contact` record is created.

The `mobile` field on `mailing.contact` is added by `mass_mailing_sms` and stores the phone number. This is the field that the SMS composer reads when targeting the mailing list.

## Form Builder Whitelist

```xml
<!-- Source: odoo/addons/website_mass_mailing_sms/data/ir_model_data.xml -->
<function model="ir.model.fields" name="formbuilder_whitelist">
    <value>mailing.contact</value>
    <value eval="['mobile']"/>
</function>
```

This `formbuilder_whitelist` call registers the `mobile` field on `mailing.contact` as available for use in website form builders. Without this whitelist entry, the `mobile` field would not be accessible from Odoo's website form builder interface (used for building custom forms that subscribe contacts to mailing lists).

## Practical Usage Scenarios

### Scenario 1: Dual-Channel Newsletter Signup

A business wants visitors to choose how they want to receive updates:
1. **Email newsletter**: Standard email subscription via `website_mass_mailing`.
2. **SMS alerts**: Phone number subscription via `website_mass_mailing_sms`.

The SMS snippet can be placed on a separate website page or as a complementary block alongside the email newsletter block.

### Scenario 2: SMS-Only Subscription

A business prefers SMS as its primary marketing channel for certain customer segments (e.g., time-sensitive promotions in retail). The SMS snippet is placed prominently on the homepage:

1. Visitor enters their phone number and submits.
2. Odoo creates a `mailing.contact` with the mobile number.
3. The contact is added to the configured SMS marketing mailing list.
4. The visitor receives a confirmation SMS (if an automated SMS template is configured on the list).

### Scenario 3: Website Form Integration

An events company uses Odoo's website form builder to create event registration forms. They add the mailing list subscription widget to the form, selecting the "Mobile" subscription type:

1. Attendee registers for an event and provides their phone number.
2. Odoo automatically subscribes the attendee's mobile number to the event's SMS marketing list.
3. The attendee receives SMS reminders about the event.

## Configuration Requirements

### 1. SMS Provider

Before using SMS subscriptions, a SMS provider must be configured in **Settings > Technical > SMS > SMS Providers**. Common options:
- **Twilio**: Configure Account SID, Auth Token, and phone number.
- **Custom SMTP**: Configure an SMS gateway that accepts SMTP.
- **Other providers**: Odoo supports multiple SMS gateways via the `sms` module's extensible architecture.

Without a configured SMS provider, contacts can still be subscribed (the subscription record is created), but SMS campaigns cannot be sent.

### 2. Mailing List

A `mailing.list` record must be configured with:
- A name (e.g., "SMS Marketing - Newsletter").
- A list of subscribed contacts (added via the website snippet or manually).
- An optional welcome SMS template (automatically sent to new subscribers).

### 3. Snippet Configuration

In the website editor:
1. Drag the **Newsletter SMS Notifications** snippet onto a page.
2. In the snippet options, select the target mailing list.
3. The `data-list-id="0"` in the template default can be overridden in the editor to point to the actual list.

## Technical Notes

### `primary="True"` on Template

The `s_newsletter_subscribe_form` template has `primary="True"`, which means it is treated as a standalone template (not just an extension fragment). This allows it to be called via `t-snippet-call` directly.

### Snippet Registration Hook

The snippet panel replaces a placeholder hook (`mass_mailing_newsletter_sms_notifications_hook`) with the actual snippet:

```xml
<xpath expr="//t[@id='mass_mailing_newsletter_sms_notifications_hook']" position="replace">
    <t t-snippet="website_mass_mailing_sms.s_newsletter_sms_notifications" ...>
```

This hook mechanism allows other modules to customize which snippet appears in the newsletter section of the website editor.

### Session Persistence

The `_get_value('mobile')` method stores the submitted phone number in `request.session['mass_mailing_mobile']`. This allows:
- **Logged-in users**: The phone number is read from their partner record on every subscription.
- **Anonymous users**: The phone number is stored in the session, so subsequent subscriptions on the same session pre-fill the field.

### Privacy and Consent

SMS marketing is subject to strict regulations in most jurisdictions (e.g., GDPR in Europe, TCPA in the US, PDPA in Singapore). Organizations should:
- Implement explicit opt-in consent (do not pre-check subscription boxes).
- Maintain records of when and how consent was obtained.
- Provide easy opt-out mechanisms (most SMS platforms support the STOP keyword).
- Consider implementing double opt-in (send a confirmation SMS before adding to active marketing lists).

## Related Documentation

- [Modules/website_mass_mailing](Modules/website_mass_mailing.md) — Base website newsletter subscription
- [Modules/mass_mailing_sms](Modules/mass_mailing_sms.md) — SMS mailing infrastructure (mobile field on mailing.contact)
- [Modules/sms](Modules/sms.md) — SMS delivery infrastructure
- [Modules/mass_mailing](Modules/mass_mailing.md) — Base mass mailing engine
- [Modules/website](Modules/website.md) — Website builder core
- [Modules/mailing_contact](mailing_contact.md) — Mailing contact model
