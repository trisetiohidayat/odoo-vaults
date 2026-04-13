# POS SMS

## Overview
- **Name:** POS - SMS
- **Category:** Send sms to customer for order confirmation
- **Depends:** `point_of_sale`, `sms`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Integrates the Point of Sale with SMS. Sends SMS confirmations to customers when orders are placed or updated from the POS.

## Data Files
- `data/sms_data.xml` — SMS templates
- `views/res_config_settings_views.xml` — Settings
- `data/point_of_sale_data.xml` — POS SMS configuration

## Assets
- POS frontend assets for SMS confirmation flow

## Related
- [Modules/point_of_sale](point_of_sale.md) — Base POS module
- [Modules/sms](sms.md) — SMS module
