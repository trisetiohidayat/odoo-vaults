---
type: module
module: l10n_ro_edi_stock
tags: [odoo, odoo19, l10n, localization, romania, etransport, edi, stock]
created: 2026-04-06
---

# Romania EDI Stock / e-Transport (`l10n_ro_edi_stock`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Romania - E-Transport |
| **Technical** | `l10n_ro_edi_stock` |
| **Category** | Accounting/Localizations/EDI |
| **Country** | Romania (RO) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |

## Description

This module provides **e-Transport** compliance for Romania through the ANAF (Autoritatea Națională de Administrare Fiscală) e-Transport system. It handles mandatory electronic reporting of transport operations for excisable goods and high-value shipments.

### Key Capabilities

- **ANAF e-Transport API**: Report transport operations to ANAF
- **Stock Picking Integration**: Link transport reports to [stock.picking](stock.picking.md) records
- **Delivery Carrier Support**: Integrate with [delivery.carrier](delivery.carrier.md) for transport mode
- **E-Transport Status Tracking**: Track the status of transport reports

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/stock_delivery](odoo-18/Modules/stock_delivery.md) | Stock delivery integration |
| [Modules/l10n_ro_edi](odoo-18/Modules/l10n_ro_edi.md) | ANAF e-Factura base (provides API utilities) |
| [Modules/stock_picking_batch](odoo-18/Modules/stock_picking_batch.md) | Batch picking support (also required) |

## Models

### `stock.picking` Fields

Extends [stock.picking](stock.picking.md) with e-Transport fields:

```python
l10n_ro_edi_etransport_document_ids = fields.One2many(
    'l10n_ro_edi.etransport.document',
    inverse_name='picking_id',
)

l10n_ro_edi_etransport_state = fields.Selection([
    # e-Transport document states
], string='E-Transport Status')
```

### `l10n_ro_edi.etransport.document`

Tracks e-Transport documents:

```python
class L10nRoEdiEtransportDocument(models.Model):
    _name = 'l10n_ro_edi.etransport.document'
    _description = 'Romanian e-Transport Document'

    picking_id = fields.Many2one('stock.picking')
    # Document identification and status fields
```

### `etransport_api`

ANA ANAF e-Transport API client:

```python
class ETransportAPI:
    """Handles ANAF e-Transport API communication"""

    def get_status(self, company_id, document_load_id, session=None):
        """Query e-Transport document status"""

    def upload_data(self, company_id, data):
        """Upload e-Transport report to ANAF"""
```

**API Endpoints** (from ANAF):
- Test: `https://api.anaf.ro/test/ETRANSPORT/ws/v1`
- Production: `https://api.anaf.ro/prod/ETRANSPORT/ws/v1`

### `delivery.carrier`

Extends [delivery.carrier](delivery.carrier.md) for Romanian e-Transport transport modes:
- Road, Rail, Air, Maritime, Multimodal transport classification

## Template Data

### `template_etransport.xml`

Contains UBL-based e-Transport document templates for ANAF:
- Transport report XML structure
- Excisable goods declaration
- Carrier and vehicle information

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_ro](odoo-18/Modules/l10n_ro.md) | Base Romanian accounting |
| [Modules/l10n_ro_edi](odoo-18/Modules/l10n_ro_edi.md) | ANAF e-Factura (provides shared API utilities) |
| [Modules/l10n_ro_edi_stock_batch](odoo-18/Modules/l10n_ro_edi_stock_batch.md) | e-Transport for batch pickings |
| [Modules/Stock](odoo-18/Modules/stock.md) | Stock management |
| [Modules/stock_delivery](odoo-18/Modules/stock_delivery.md) | Delivery integration |

## Configuration

1. Install `l10n_ro_edi` first (provides API foundation)
2. Install `l10n_ro_edi_stock`
3. Configure ANAF e-Transport credentials in company settings
4. Set up delivery carriers with Romanian transport modes
5. Configure stock picking workflows for e-Transport triggering

## Technical Notes

- Uses the same ANAF access token as [Modules/l10n_ro_edi](odoo-18/Modules/l10n_ro_edi.md) e-Factura
- e-Transport is mandatory for transport of excisable goods
- XML format based on ANAF e-Transport schema v2
- Bearer token authentication (same token as e-Factura)
- Schematron validation errors parsed from `BR-\d{3}` pattern
- Supports test/production environment toggle per company

## See Also

- [Modules/l10n_ro](odoo-18/Modules/l10n_ro.md) - Romanian accounting
- [Modules/l10n_ro_edi](odoo-18/Modules/l10n_ro_edi.md) - ANAF e-Factura
- [Modules/l10n_ro_edi_stock_batch](odoo-18/Modules/l10n_ro_edi_stock_batch.md) - e-Transport for batch pickings
