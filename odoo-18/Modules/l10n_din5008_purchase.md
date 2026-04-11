---
Module: l10n_din5008_purchase
Version: 18.0
Type: l10n/din5008
Tags: #odoo18 #l10n #reporting #document_layout #purchase #din5008
---

# l10n_din5008_purchase — DIN 5008 Purchase Orders

## Overview
This module extends `l10n_din5008` (the base DIN 5008 document standard) to apply DIN 5008-compliant formatting to purchase order reports. It adds purchase-order-specific document metadata (RFQ number, order date, incoterms, purchase representative) to the DIN 5008 layout and extends the purchase order report template.

## Country
Germany (`DE`), Switzerland (`CH`) — inherits country context from `l10n_din5008`

## Dependencies
- `l10n_din5008`
- `purchase`

## Key Models
No Python model files. Pure template/QWeb module.

## Data Files

### report/din5008_purchase_order_templates.xml
Defines `report_common_purchase_din5008_template` — a QWeb template fragment that sets three DIN-specific template variables for `purchase.order` reports:

**`din5008_document_information`** block — table of purchase-specific metadata:
| Label | Source Field |
|---|---|
| Request for Quotation No. / Purchase Order No. | `o.name` (label changes by state) |
| Purchase Representative | `o.user_id` |
| Order Reference | `o.partner_ref` |
| Order Date | `o.date_approve` |
| Order Deadline | `o.date_order` |
| Incoterm | `o.incoterm_id.code` |

**`din5008_address_block`** — conditionally renders:
- Shipping address from `dest_address_id` if a specific delivery address is set
- OR shipping address from the warehouse's partner address (`picking_type_id.warehouse_id.partner_id`)
- Labeled as "Shipping Address:"

## Installation
Auto-installs when both `l10n_din5008` and `purchase` are installed. This is handled automatically via `auto_install: True`.

## Integration Pattern
The module does not define a full external layout — instead it injects DIN-specific data into the existing layout chain via QWeb `t-set` variables. The base `l10n_din5008.external_layout_din5008` renders these variables when present. This is a composition-over-inheritance pattern for document layouts.

## Historical Notes
- **Odoo 17 → 18:** New in Odoo 18. The purchase order DIN formatting was previously part of `l10n_de` (Germany-specific) or `purchase` module's own templates.
- The label switching for `o.name` based on `o.state` allows the template to show "Request for Quotation No.:" for draft RFQs and "Purchase Order No.:" for confirmed POs.
- `date_approve` vs `date_order`: `date_approve` is the date the PO was confirmed (approved); `date_order` is the order deadline/request date.
