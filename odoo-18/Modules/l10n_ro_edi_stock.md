---
Module: l10n_ro_edi_stock
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #romania #etransport #anaf
---

# l10n_ro_edi_stock

## Overview
Romanian **e-Transport** module for electronic transport declarations. Romania's ANAF requires real-time reporting of goods transport via the e-Transport system. This module generates and submits e-Transport declarations from [Modules/Stock](stock.md) pickings, linking them to the fiscal identity of the company and vehicles used.

## EDI Format / Standard
**e-Transport XML** — Romanian ANAF format for transport declarations. UBL-based but specialized for logistics. Links to `stock.picking` records. Vehicle details, route information, and goods classification included.

## Dependencies
- `stock_delivery` — Delivery orders for transport
- `l10n_ro_edi` — Base Romanian EDI (provides `l10n_ro_edi.document` and API)
- Auto-installs with `l10n_ro_edi`

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `L10nRoEdiStockDocument` | `l10n_ro_edi.stock.document` | `l10n_ro_edi.document` | Extends base document: picking_id link, stock-specific state (`stock_sent/stock_sending_failed/stock_validated`), UIT, ANAF load ID |
| `ETransportAPI` | — | — | API client for ANAF e-Transport endpoint |
| `DeliveryCarrier` | `delivery.carrier` | `delivery.carrier` | Vehicle fields: license plate, trailer plate, driver ID |
| `Picking` | `stock.picking` | `stock.picking` | e-Transport declaration fields; links to L10nRoEdiStockDocument |
| `AccountMove` | `account.move` | `account.move` | Invoices linked to transport documents |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard |

## Data Files
- `data/template_etransport.xml` — QWeb template for e-Transport XML
- `views/res_config_settings_views.xml` — Settings
- `views/stock_picking_views.xml` — Picking form with e-Transport fields
- `views/delivery_carrier_views.xml` — Carrier vehicle fields
- `report/report_deliveryslip.xml` — Delivery slip with e-Transport QR

## How It Works

### Transport Declaration
1. Picking confirmed/validated → `L10nRoEdiStockDocument` created
2. `_generate_etransport_xml()` builds ANAF-compliant XML
3. Submitted via ANAF e-Transport API
4. UIT (Unique Identification Number) assigned by ANAF
5. State transitions: `stock_sending_failed → stock_sent → stock_validated`

### Stock/Picking Flow
- Picking linked to document via `picking_id` field (vs invoice linking via `invoice_id` in base)
- Override of base `l10n_ro_edi.document` to use `stock_validated` state
- Vehicle information from delivery carrier

### API Integration
`ETransportAPI` class handles ANAF web service calls for transport declarations. Separate endpoint from invoice API.

## Installation
Auto-installs with `l10n_ro_edi`. Standard module installation.

## Historical Notes
- **Odoo 18**: New module. Romania introduced e-Transport reporting for goods transport. Declaration required for road transport of goods above certain thresholds.