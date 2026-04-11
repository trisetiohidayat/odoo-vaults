---
Module: l10n_in_ewaybill_stock
Version: 18.0
Type: l10n/india-edi
Tags: #odoo18 #l10n #edi #ewaybill #stock #india
---

# l10n_in_ewaybill_stock — Indian E-waybill from Stock Picking

## Overview
Enables e-waybill generation directly from the Inventory app without requiring a formal invoice. Users can create an e-waybill from a stock picking (delivery order), which is common for businesses that need to move goods before or without issuing a commercial invoice. Integrates with `l10n_in_stock` and `l10n_in_edi_ewaybill`.

## Country
India

## Dependencies
- l10n_in_stock
- l10n_in_edi_ewaybill

Auto-install: `True`

## Key Models

### `Ewaybill` (`l10n.in.ewaybill`) — l10n_in_ewaybill.py
- `_name = "l10n.in.ewaybill"`
- `_inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']`
- Standalone e-waybill record independent of `account.move`. Links to `stock.picking`.
- **Fields:**
  - `picking_id` — Many2one `stock.picking`
  - `state` — Selection: draft, generated, sent, cancelled
  - `ewaybill_number` — Char, populated after generation
  - `supply_type`, `sub_supply_type`, `doc_type`, `doc_date` — e-waybill document fields
  - `from_partner_id`, `to_partner_id` — Many2one `res.partner`
  - `from_gstin`, `to_gstin` — Char GSTINs
  - `distance`, `transporter_id`, `transporter_name`, `vehicle_no`, `vehicle_type` — transport fields
  - `fiscal_position_id` — Many2one `account.fiscal.position`
  - `line_ids` — One2many `l10n.in.ewaybill.line`
  - `document_date` — Date
- **Methods:**
  - `_compute_supply_type()`, `_compute_document_partners_details()`, `_compute_fiscal_position()` — compute on picking change
  - `_compute_is_editable()` — allows editing in draft state
  - `_compute_content()` — e-waybill JSON content
  - `_compute_display_name()` — display "e-Waybill %s - %s" format
  - `_compute_vehicle_type()` — regular vs over-dimensional cargo
  - `action_generate_ewaybill()` — generates JSON and submits to portal
  - `button_cancel()` — cancels the e-waybill

### `StockMove` (`stock.move`) — stock_move.py
- `_inherit = 'stock.move'`
- `_l10n_in_get_product_tax()` — returns taxes from stock move (supplier/sale taxes based on move direction)

### `StockPicking` (`stock.picking`) — stock_picking.py
- `_inherit = 'stock.picking'`
- Creates and manages linked `l10n.in.ewaybill` records from pickings

## Data Files
- `security/ir_rules.xml` — Record rules for e-waybill access
- `security/ir.model.access.csv`
- `data/ewaybill_type_data.xml` — E-waybill types
- `views/l10n_in_ewaybill_views.xml` — E-waybill form/list views
- `views/stock_picking_views.xml` — Picking views with e-waybill button
- `report/ewaybill_report_views.xml` — E-waybill PDF report
- `report/ewaybill_report.xml` — Report definition
- `wizard/l10n_in_ewaybill_cancel_views.xml` — Cancel wizard

## Installation
`auto_install = True`. Installs with `l10n_in_stock` + `l10n_in_edi_ewaybill`.

## Historical Notes
New in Odoo 18. Before this module, e-waybill could only be generated from an account move (invoice). The standalone `l10n.in.ewaybill` model allows stock operations to generate e-waybills independently, which is a common requirement for manufacturing and logistics companies.