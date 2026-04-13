# Turkiye - Nilvera e-Dispatch (`l10n_tr_nilvera_edispatch`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Turkiye - Nilvera e-Dispatch |
| **Technical** | `l10n_tr_nilvera_edispatch` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_tr_nilvera`, `stock` |

## Description
UBL 1.2 e-Dispatch (e-Irsaliye) integration for Turkey via Nilvera portal. Generates and submits electronic dispatch notes for goods shipments. Supports vehicle plates, trailer plates, driver information, carrier selection, and dispatch type (SEVK/MATBUDAN). Tracks dispatch state (to_send/sent).

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_tr_nilvera` | Core Turkish localization + Nilvera base |
| `stock` | Warehouse/picking module |

## Technical Notes
- Country code: `tr` (Turkey)
- Format: UBL 1.2 dispatch (e-Irsaliye)
- API: Nilvera portal
- Dispatch types: `SEVK` (online), `MATBUDAN` (pre-printed)

## Models

### `stock.picking` (Extended)
Fields for e-dispatch:

| Field | Type | Description |
|-------|------|-------------|
| `l10n_tr_nilvera_dispatch_type` | Selection | `SEVK` (Online) or `MATBUDAN` (Pre-printed) |
| `l10n_tr_nilvera_carrier_id` | Many2one | Third-party carrier company (makes vehicle/driver optional) |
| `l10n_tr_nilvera_buyer_id` | Many2one | Buyer (when delivery address differs from purchaser) |
| `l10n_tr_nilvera_seller_supplier_id` | Many2one | Supplier/goods information for the delivery note |
| `l10n_tr_nilvera_buyer_originator_id` | Many2one | Original initiator of the goods acquisition |
| `l10n_tr_nilvera_delivery_printed_number` | Char | Pre-printed delivery note number |
| `l10n_tr_nilvera_delivery_date` | Date | Pre-printed delivery note date |
| `l10n_tr_vehicle_plate` | Many2one | Truck plate number (GIB plate) |
| `l10n_tr_nilvera_trailer_plate_ids` | Many2many | Trailer plate numbers |
| `l10n_tr_nilvera_driver_ids` | Many2many | Drivers of the truck |
| `l10n_tr_nilvera_delivery_notes` | Char | Delivery notes reference |
| `l10n_tr_nilvera_dispatch_state` | Selection | `to_send`, `sent` |

### `stock.picking.type` (Extended)
**`_onchange_sequence_code()`** — Validates that outgoing picking types for Turkish companies have exactly 3 characters in their sequence code

### `res.partner` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_tr_nilvera_edispatch_customs_zip` | Char | ZIP code of customs office for cross-border shipments (max 5 chars) |

### `l10n_tr.nilvera.trailer.plate` (New Model)
GIB-registered vehicle and trailer plate registry.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | GIB plate number |
| `plate_number_type` | Selection | `vehicle` or `trailer` |
| Unique constraint | | `unique(name, plate_number_type)` |

## Related
- [Modules/l10n_tr_nilvera](l10n_tr_nilvera.md) — Core Turkish localization
- [Modules/l10n_tr_nilvera_einvoice](l10n_tr_nilvera_einvoice.md) — Turkish e-invoice via Nilvera
