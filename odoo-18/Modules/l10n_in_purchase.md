---
Module: l10n_in_purchase
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #purchase #india
---

# l10n_in_purchase — Indian Purchase Report (GST)

## Overview
India-specific extension of the Purchase module, adding GST-specific fields and behavior to purchase orders and vendor bills. Carries GST treatment, HSN codes, and place-of-supply logic through to vendor bills. Also provides GST purchase register report.

## Country
India

## Dependencies
- l10n_in
- purchase

## Key Models

### `PurchaseOrder` (`purchase.order`) — purchase_order.py
- `_inherit = "purchase.order"`
- `l10n_in_gst_treatment` — Selection: regular, composition, unregistered, consumer, overseas, special_economic_zone, deemed_export, uin_holders
- `_compute_l10n_in_gst_treatment()` — `@api.depends('partner_id')` — auto-computes from partner (mirrors same logic as sale orders): if partner has no treatment, defaults to `overseas` if foreign, or `regular` if Indian with VAT, or `consumer`
- No fiscal position logic (purchase fiscal positions handled by `l10n_in` base on state)

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = 'account.move'`
- `_onchange_purchase_auto_complete()` — `@api.onchange('purchase_vendor_bill_id', 'purchase_id')`
  - When a vendor bill is created from a Purchase Order, copies the PO's `l10n_in_gst_treatment` to the bill
  - Only activates for Indian companies (country_code == 'IN')

## Data Files
- `views/report_purchase_order.xml` — Purchase order report with Indian GST fields
- `views/purchase_order_views.xml` — PO form with GST treatment field

## GST Treatment on Purchase
GST treatment on vendor bills determines the applicable tax (intra-state CGST+SGST vs inter-state IGST) via fiscal positions from [Modules/l10n_in](Modules/l10n_in.md).

Taxable treatments: regular, composition, special_economic_zone, deemed_export
These require the vendor to have a valid GSTIN.

## Installation
`auto_install = True`. Auto-installs with its dependencies (`l10n_in` + `purchase`).

## Historical Notes
Version 1.0 in Odoo 18. Works with `l10n_in_purchase_stock` (which depends on this module) for full warehouse+tax integration on the purchase side.