# Sale Loyalty Delivery

## Overview
- **Name:** Sale Loyalty - Delivery
- **Category:** Sales/Sales
- **Depends:** `sale_loyalty`, `delivery`
- **Auto-install:** Yes
- **License:** LGPL-3

## Description
Adds a **Free Shipping** loyalty reward type to the `sale_loyalty` module. Loyalty programs can now reward customers with free delivery (or free delivery up to a maximum cost).

## Models

### `loyalty.reward` (extends `loyalty.reward`)
| Field | Type | Description |
|-------|------|-------------|
| `reward_type` | Selection | Added `"shipping"` (Free Shipping) option |

When `reward_type = "shipping"`:
- `description` is auto-set to "Free shipping".
- If `discount_max_amount` is set, appends " (Max {amount})" to the description.
- The reward grants free delivery — the delivery cost for the cheapest available carrier is waived.

## Data
- `views/loyalty_reward_views.xml`: Form view modification to show shipping reward fields.

## Related
- [[Modules/sale_loyalty]] - Loyalty programs in sales
- [[Modules/delivery]] - Delivery carriers and pricing
