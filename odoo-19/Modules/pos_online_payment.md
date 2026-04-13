# POS Online Payment

## Overview
- **Name:** Point of Sale online payment
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`, `account_payment`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Enables online payment for POS orders. Customers can pay their POS order via a payment link sent by the cashier (e.g., email/SMS). The payment is processed through the website payment flow and synced back to the POS order.

## Key Features
- Send payment links to customers for POS orders
- Online payment processing via website payment form
- Real-time sync of payment status back to POS
- Customer display support for payment status

## Assets
- `pos_online_payment.assets_prod` — Main POS app assets
- `pos_online_payment.customer_display_assets` — Customer display popup
- `pos_online_payment.customer_display_assets_test` — Customer display test tour

## Data Files
- `views/res_config_settings_views.xml` — Settings
- `views/payment_transaction_views.xml` — Payment transactions
- `views/pos_payment_views.xml` — POS payment views
- `views/pos_payment_method_views.xml` — Payment method config
- `views/payment_portal_templates.xml` — Portal templates
- `views/account_payment_views.xml` — Account payment views

## Related
- [Modules/point_of_sale](odoo-18/Modules/point_of_sale.md) — Base POS module
- [Modules/payment](odoo-18/Modules/payment.md) — Payment engine
- [Modules/pos_online_payment_self_order](odoo-18/Modules/pos_online_payment_self_order.md) — Online payment in self-order
