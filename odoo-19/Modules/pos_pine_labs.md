# POS Pine Labs

## Overview
- **Name:** POS Pine Labs
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Integrates your POS with Pine Labs payment terminals. Available only for companies using INR currency. Enables card/UPI payments via Pine Labs terminals.

## Features
- Quick payment via card swiping, scanning, or tapping
- UPI QR code support
- Supported cards: Visa, MasterCard, RuPay
- INR currency only

## Data Files
- `views/pos_payment_views.xml` — Payment views
- `views/pos_payment_method_views.xml` — Payment method configuration

## Assets
- POS frontend + unit test assets for Pine Labs

## Related
- [Modules/point_of_sale](point_of_sale.md) — Base POS module
- [Modules/pos_self_order_pine_labs](pos_self_order_pine_labs.md) — Pine Labs in self-order
