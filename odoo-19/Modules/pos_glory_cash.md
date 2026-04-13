# POS Glory Cash

## Overview
- **Name:** POS Glory Cash Machines
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Integrates your POS with a Glory automatic cash payment device. Glory devices handle cash counting, change calculation, and counterfeit detection.

## Features
- Automatic cash payment processing
- Change calculation from Glory device
- Cash reconciliation in POS session

## Data Files
- `views/pos_payment_method_views.xml` — Payment method configuration

## Assets
- Frontend: backend assets + POS frontend assets (split bundle)
- Unit test assets for Glory cash machine utils

## Related
- [Modules/point_of_sale](Modules/point_of_sale.md) — Base POS module
