---
type: module
module: l10n_ro_edi_stock_batch
tags: [odoo, odoo19, l10n, localization, romania, etransport, edi, stock, batch]
created: 2026-04-06
---

# Romania EDI Stock Batch / e-Transport Batch (`l10n_ro_edi_stock_batch`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Romania - E-Transport Batch Pickings |
| **Technical** | `l10n_ro_edi_stock_batch` |
| **Category** | Accounting/Localizations/EDI |
| **Country** | Romania (RO) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |

## Description

This module extends [Modules/l10n_ro_edi_stock](Modules/l10n_ro_edi_stock.md) to support **batch picking** operations for the Romanian e-Transport system. It enables consolidated e-Transport reporting for multiple stock pickings grouped into a single batch operation.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_ro_edi_stock](Modules/l10n_ro_edi_stock.md) | Base e-Transport (ANAF API utilities) |
| [Modules/stock_picking_batch](Modules/stock_picking_batch.md) | Batch picking management |

## Auto-Install

Auto-installs with `l10n_ro_edi_stock` when batch picking is available.

## Key Components

### `stock.picking.batch` Extension

Extends [stock.picking.batch](stock.picking.batch.md) with e-Transport batch reporting:

```python
# Batch-level e-Transport document tracking
l10n_ro_edi_batch_etransport_ids = fields.One2many(
    'l10n_ro_edi.batch.etransport.document',
    inverse_name='batch_id',
)
```

### `l10n_ro_edi.batch.etransport.document`

Tracks batch-level e-Transport documents:

```python
class L10nRoEdiBatchEtransportDocument(models.Model):
    _name = 'l10n_ro_edi.batch.etransport.document'
    _description = 'Romanian e-Transport Batch Document'
```

### Report: `report_picking_batch.xml`

Batch picking slip report adapted for Romanian e-Transport compliance.

## Models

| Model | File | Purpose |
|-------|------|---------|
| `stock.picking.batch` | `stock_picking_batch.py` | Batch picking with e-Transport |
| `stock.picking` | `stock_picking.py` | Picking-level e-Transport links |
| `l10n_ro_edi.batch.etransport.document` | `l10n_ro_edi_stock_document.py` | Batch document tracking |

## Workflow

### Batch e-Transport Flow

```
[Create Batch Pickings] -> [Group into Batch] ->
[Generate Batch e-Transport Report] ->
[Upload to ANAF] -> [Track Batch Status]
```

### Per-Picking Flow (via batch parent)

Individual pickings within a batch inherit batch-level e-Transport reporting:
- Batch upload aggregates all picking data
- Individual picking documents reference the batch parent

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_ro](Modules/l10n_ro.md) | Base Romanian accounting |
| [Modules/l10n_ro_edi](Modules/l10n_ro_edi.md) | ANAF e-Factura |
| [Modules/l10n_ro_edi_stock](Modules/l10n_ro_edi_stock.md) | Base e-Transport for single pickings |
| [Modules/stock_picking_batch](Modules/stock_picking_batch.md) | Batch picking management |

## Configuration

1. Install `l10n_ro_edi_stock` first
2. Install `l10n_ro_edi_stock_batch`
3. Configure batch picking sequences
4. Set up ANAF e-Transport for batch mode
5. Link delivery carriers to batch operations

## Technical Notes

- Batch e-Transport consolidates multiple pickings into one ANAF report
- Uses the same ANAF e-Transport API as [Modules/l10n_ro_edi_stock](Modules/l10n_ro_edi_stock.md)
- Each batch generates a single e-Transport document ID
- Child pickings reference the parent batch document
- Test/prod environment toggle inherited from company settings

## See Also

- [Modules/l10n_ro_edi_stock](Modules/l10n_ro_edi_stock.md) - e-Transport for single pickings
- [Modules/l10n_ro_edi](Modules/l10n_ro_edi.md) - ANAF e-Factura
- [Modules/l10n_ro](Modules/l10n_ro.md) - Romanian accounting
