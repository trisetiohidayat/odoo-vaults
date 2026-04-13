# POS DPO Pay

## Overview
- **Name:** PoS DPO Pay
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Integrates your POS with DPO payment terminal. Supports all currencies supported by the terminal — primarily for the **African region**. Enables customers to pay using debit/credit cards and Mobile Money (Airtel Money / M-Pesa).

## Features
- Quick payment via card swiping, scanning, or tapping
- Mobile Money support: Airtel Money, M-Pesa
- Supported cards: Visa, MasterCard, American Express, etc.
- Requires a DPO merchant account

## Data Files
- `views/pos_payment_method_views.xml` — Payment method configuration
- `views/pos_payment_views.xml` — Payment views

## Assets
- POS frontend assets for DPO terminal integration

## Related
- [Modules/point_of_sale](point_of_sale.md) — Base POS module
