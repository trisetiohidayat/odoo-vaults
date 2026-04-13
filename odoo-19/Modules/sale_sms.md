# Sale SMS

## Overview
- **Name:** Sale - SMS
- **Category:** Sales/Sales
- **Depends:** `sale`, `sms`
- **Auto-install:** Yes
- **License:** LGPL-3

## Description
Integrates SMS capabilities with Sales Orders. Allows sending SMS notifications to customers when sale order status changes (e.g. when confirmed, when sent, etc.).

## Implementation
This is a thin integration module. The SMS functionality is provided by the `sms` module; this module registers the necessary security records and provides the foundation for SMS templates tied to sale orders.

## Security
- `ir.model.access.csv`: Access rights for SMS models in sale context.
- `security.xml`: Record rules for SMS in sale orders.

## Related
- [Modules/Sale](Modules/Sale.md) - Sales orders
- [Modules/sms](Modules/sms.md) - SMS sending and templates
