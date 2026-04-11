---
Module: l10n_tr_nilvera_edispatch
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #turkey #dispatch #nilvera
---

# l10n_tr_nilvera_edispatch

## Overview
Generates and manages e-Dispatch (e-İrsaliye) XML documents for outgoing stock moves in Turkey, using UBL 1.2.1/TR format. Triggered when a stock picking is validated (state = `done`). The module extends `stock` and `l10n_tr_nilvera`.

## EDI Format / Standard
UBL 1.2.1 with Turkish e-Dispatch profile (`TR1.2.1`). Dispatch scenarios: `TEMELIRSALIYE` (standard online dispatch).

## Dependencies
- `l10n_tr_nilvera` -- core Nilvera client/partner status
- `stock` -- stock picking workflow

## Key Models

### `stock.picking` (`l10n_tr_nilvera_edispatch.stock_picking`)
Extends: `stock.picking`

Fields:
- `l10n_tr_nilvera_dispatch_type` -- Selection: `SEVK` (Online) | `MATBUDAN` (Pre-printed)
- `l10n_tr_nilvera_carrier_id` -- Many2one to `res.partner` (carrier company)
- `l10n_tr_nilvera_buyer_id` / `l10n_tr_nilvera_seller_supplier_id` / `l10n_tr_nilvera_buyer_originator_id` -- Partner fields for multi-party dispatch
- `l10n_tr_nilvera_delivery_printed_number` / `_date` -- For `MATBUDAN` type
- `l10n_tr_vehicle_plate` -- Many2one to `l10n_tr.nilvera.trailer.plate` (vehicle)
- `l10n_tr_nilvera_trailer_plate_ids` -- Many2many to trailer plates
- `l10n_tr_nilvera_driver_ids` -- Many2many to `res.partner` (drivers)
- `l10n_tr_nilvera_delivery_notes` -- Char
- `l10n_tr_nilvera_dispatch_state` -- Selection: `to_send | sent`
- `l10n_tr_nilvera_edispatch_warnings` -- Json (computed from field validation)

Methods:
- `button_validate()` -- EXTENDS stock; sets `dispatch_state = 'to_send'` if partner is set, otherwise posts informational message
- `_l10n_tr_validate_edispatch_fields()` -- Validates all required dispatch fields; called at `done` state
- `_l10n_tr_validate_edispatch_on_done()` -- Comprehensive validation: partner details, TCKN for Turkish drivers, carrier/vehicle/driver requirements, printed note format for `MATBUDAN`
- `_l10n_tr_generate_edispatch_xml()` -- Generates UBL 1.2.1 XML from picking data; creates `ir.attachment`; posts to chatter
- `action_generate_l10n_tr_edispatch_xml()` -- Action wrapper; validates before generating
- `action_mark_l10n_tr_edispatch_status()` -- Marks as `sent`

### `l10n_tr.nilvera.trailer.plate` (`l10n_tr_nilvera_edispatch.l10n_tr_nilvera_trailer_plate`)
Stands alone: no `_inherit`.

- `name` -- Char (GİB Plate Number)
- `plate_number_type` -- Selection: `vehicle | trailer`
- SQL unique constraint on `(name, plate_number_type)`

### `res.partner` / `stock.picking.type`
Minimal extensions for driver and picking type compatibility.

## Data Files
- `templates/l10n_tr_nilvera_edispatch.xml` -- QWeb UBL 1.2.1 dispatch template
- `security/ir.model.access.csv` -- ACL entries
- `views/stock_picking_views.xml`, `views/l10n_tr_nilvera_trailer_plate_views.xml`, `views/res_partner_views.xml`

## How It Works
1. Stock picking is validated (`button_validate()`)
2. `_l10n_tr_validate_edispatch_on_done()` runs validations (partners, drivers, vehicle plates)
3. Warnings are shown as JSON computed field on the picking form
4. User clicks "Generate e-Dispatch XML"; `_l10n_tr_generate_edispatch_xml()` renders the UBL template
5. XML attachment is created and linked to the picking chatter
6. User manually sends the XML to Nilvera (or uses an action); `action_mark_l10n_tr_edispatch_status()` marks as `sent`
7. Driver TCKN must be 11 digits and country must be TR; vehicle plate is required unless a carrier is specified

## Installation
Install after `l10n_tr_nilvera` and `stock`. Requires Turkish company and partner configurations (TCKN on drivers, vehicle plate master data).

## Historical Notes
e-Dispatch (e-İrsaliye) became mandatory in Turkey alongside e-invoice. Unlike the e-invoice flow which is fully API-driven, the dispatch flow currently generates a downloadable XML that users transmit manually. The `MATBUDAN` (pre-printed) dispatch type supports legacy workflows where sequential printed numbers are pre-assigned by the tax office.
