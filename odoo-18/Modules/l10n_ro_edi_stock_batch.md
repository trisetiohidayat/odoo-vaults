---
Module: l10n_ro_edi_stock_batch
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #romania #etransport #batch
---

# l10n_ro_edi_stock_batch

## Overview
Extends [Modules/l10n_ro_edi_stock](modules/l10n_ro_edi_stock.md) to support e-Transport declarations for **batch pickings** (multiple pickings grouped together). When multiple stock pickings are processed in a batch, this module generates a consolidated e-Transport declaration covering all pickings in the batch.

## EDI Format / Standard
Same as [Modules/l10n_ro_edi_stock](modules/l10n_ro_edi_stock.md) — e-Transport XML format for ANAF.

## Dependencies
- `l10n_ro_edi_stock` — Base e-Transport module
- `stock_picking_batch` — Batch picking management

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `L10nRoEdiStockDocument` | `l10n_ro_edi.stock.document` | `l10n_ro_edi.stock.document` | Extends stock document with batch picking link |
| `StockPickingBatch` | `stock.picking.batch` | `stock.picking.batch` | Batch-level e-Transport reporting |
| `Picking` | `stock.picking` | `stock.picking` | Pickings in batch get batch-level e-Transport |

## Data Files
- `views/stock_picking_batch_views.xml` — Batch picking form with e-Transport fields
- `report/report_picking_batch.xml` — Batch report with e-Transport info

## How It Works
When a batch picking is processed, the module:
1. Groups all pickings in the batch
2. Generates a single e-Transport declaration covering all goods in the batch
3. Each picking in the batch gets linked to the batch-level declaration
4. When the batch is validated, the e-Transport document is submitted to ANAF

## Installation
Auto-installs with `l10n_ro_edi_stock`. No separate activation.

## Historical Notes
- **Odoo 18**: New module. Supports the common warehouse practice of batched picking operations while maintaining e-Transport compliance.