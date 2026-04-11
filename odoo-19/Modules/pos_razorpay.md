# POS Razorpay

## Overview
- **Name:** POS Razorpay
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Integrates your POS with a Razorpay payment terminal. Enables customers to pay by debit/credit cards and UPI through Razorpay POS terminals.

## Features
- Fast payment by swiping/scanning card or QR code
- Supported cards: Visa, MasterCard, Rupay, UPI
- Requires a Razorpay merchant account

## Data Files
- `views/pos_payment_method_views.xml` — Payment method configuration

## Assets
- POS frontend + test assets for Razorpay terminal

## Related
- [[Modules/point_of_sale]] — Base POS module
- [[Modules/payment_razorpay]] — Razorpay online payment
- [[Modules/pos_self_order_razorpay]] — Razorpay in self-order
