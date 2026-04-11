# website_mass_mailing_sms

Odoo 19 Website/CRM Module

## Overview

`website_mass_mailing_sms` extends `website_mass_mailing` with **SMS subscription**. Visitors can subscribe to a mailing list using their phone number, enabling SMS-based marketing campaigns alongside email marketing.

## Module Details

- **Category**: Website/Website
- **Depends**: `website_mass_mailing`, `mass_mailing_sms`
- **Version**: 1.0
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Key Features

Extends the standard newsletter block from `website_mass_mailing` with an SMS template option:
- Adds phone number input to the newsletter block.
- Visitors can subscribe via SMS (phone number) or email.
- Enables SMS-based marketing campaigns from the same mailing list.

## Relationship to Other Modules

| Module | Role |
|---|---|
| `website_mass_mailing` | Newsletter block framework |
| `mass_mailing_sms` | SMS subscription mechanism and campaign management |
| `website_mass_mailing_sms` | Adds SMS option to website newsletter block |

## Usage

1. Install `website_mass_mailing_sms` alongside `website_mass_mailing`.
2. Configure SMS provider (Twilio, etc.) in **Settings > SMS**.
3. In the website editor, enable the **SMS subscription** option on the newsletter block.
