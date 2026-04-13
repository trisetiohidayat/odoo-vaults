---
type: module
module: l10n_ro_edi
tags: [odoo, odoo19, l10n, localization, romania, edi, einvoicing, ANAF, eFactura]
created: 2026-04-06
---

# Romania EDI / ANAF e-Factura (`l10n_ro_edi`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Romania - E-invoicing |
| **Technical** | `l10n_ro_edi` |
| **Category** | Accounting/Localizations/EDI |
| **Country** | Romania (RO) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |

## Description

This module provides Romanian e-invoice compliance through the **ANAF (Autoritatea Națională de Administrare Fiscală)** e-Factura system. It implements the Romanian CIUS (Core Invoice Usage Statement) based on UBL 2.1.

### Key Capabilities

- **CIUS-RO**: Romanian extension of EN 16931 UBL invoice format
- **ANAF SPV Integration**: Send/receive invoices via ANAF's Platforma Națională RO e-Factura
- **Invoice Lifecycle Tracking**: Track invoice status through the SPV validation process
- **B2G Compliance**: Mandatory e-invoicing for government procurement
- **Invoice Import**: Receive and process vendor bills from SPV

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md) | UBL/CII EDI framework |
| [Modules/l10n_ro](l10n_ro.md) | Romanian base accounting |

## Auto-Install

Auto-installs with `l10n_ro_edi` when dependencies are met.

## Key Components

### EDI XML Builder: `account.edi.xml.ubl_ro`

Custom UBL 2.1 format for Romania implementing CIUS-RO:

```
Customization ID: urn:cen.eu:en16931:2017#compliant#urn:efactura.mfinante.ro:CIUS-RO:1.0.1
```

Extends `account.edi.xml.ubl_bis3` with Romanian-specific requirements.

### ANAF API Integration (`utils.py`)

Romanian SPV API functions:

```python
# Send invoice to ANAF
_request_ciusro_send_invoice(company, xml_data, move_type, is_b2b)

# Fetch invoice status from ANAF
_request_ciusro_fetch_status(company, key_loading, session)

# Download invoice answer
_request_ciusro_download_answer(company, key_download, session)

# Synchronize all invoices
_request_ciusro_synchronize_invoices(company, session)
```

## Models

### `account.move` Fields

```python
l10n_ro_edi_document_ids = fields.One2many(
    'l10n_ro_edi.document',
    inverse_name='invoice_id',
)

l10n_ro_edi_state = fields.Selection([
    ('invoice_not_indexed', 'Not indexed'),
    ('invoice_sent', 'Sent'),
    ('invoice_refused', 'Refused'),
    ('invoice_validated', 'Validated'),
], string='E-Factura Status', compute='_compute_l10n_ro_edi_state')

l10n_ro_edi_index = fields.Char(string='E-Factura Index', readonly=True)
```

### `l10n_ro_edi.document`

Tracks complete EDI document lifecycle:

```python
class L10nRoEdiDocument(models.Model):
    _name = 'l10n_ro_edi.document'

    invoice_id = fields.Many2one('account.move')
    state = fields.Selection([
        ('invoice_sent', 'Sent'),
        ('invoice_not_indexed', 'Not indexed'),
        ('invoice_refused', 'Refused'),
        ('invoice_validated', 'Validated'),
    ])
    # Download/signature keys
    key_download = fields.Char()
    key_signature = fields.Char()
    key_certificate = fields.Char()
    attachment = fields.Binary()
    message = fields.Char()
```

### `ciusro.document`

Internal model for SPV communication:

```python
class CiusroDocument(models.Model):
    _name = 'ciusro.document'
    _description = 'ciusro.document'
```

### Other Extended Models

| Model | File | Purpose |
|-------|------|---------|
| `account.move.send` | `account_move_send.py` | EDI send flow |
| `res.company` | `res_company.py` | ANAF credentials, access token |
| `res.config.settings` | `res_config_settings.py` | ANAF configuration |
| `res.partner` | `res_partner.py` | Partner ANAF data |

## CIUS-RO Requirements

The Romanian CIUS extends EN 16931 with:

| Field | Requirement |
|-------|------------|
| VAT Number (CIF) | Mandatory for both parties |
| City (Bucharest) | Must use SECTOR 1-6 format |
| State/County | Mandatory, using RO-XX format |
| Street | Mandatory |
| Company Registry | Mandatory for legal entities |

### Bucharest Address Format

When partner's state is București (code `B`), the city must be:
- `SECTOR1`, `SECTOR2`, `SECTOR3`, `SECTOR4`, `SECTOR5`, or `SECTOR6`

## Invoice Flow

### Sending (B2B / B2G)

```
[Draft] -> [Post] -> Generate CIUS-RO XML -> Send to ANAF
-> Receive Index -> Fetch Status -> [Validated / Refused]
```

### Receiving (Vendor Bills)

```
Synchronize from ANAF -> Match/Create Bill -> Process
-> Download Answer -> Store Signature
```

### State Machine

```
Not indexed --[SPV timeout 3+ days]--> Refused
Sent --[Fetch Status]--> Not indexed / Refused / Validated
Validated --[Re-send not possible]
```

## Key Methods

### `account.move` Actions

```python
# Fetch and update invoice status from ANAF
def action_l10n_ro_edi_fetch_invoices(self):
    """Synchronizes invoices with the ANAF SPV"""

# Internal: send invoice
def _l10n_ro_edi_send_invoice(self, xml_data):
    """Sends CIUS-RO XML to ANAF SPV"""

# Internal: fetch sent invoice status
def _l10n_ro_edi_fetch_invoice_sent_documents(self):
    """Queries ANAF for sent invoice status"""

# Internal: synchronize from ANAF
def _l10n_ro_edi_fetch_invoices(self):
    """Gets all invoices from ANAF SPV"""
```

## Configuration

1. Install `l10n_ro` first
2. Install `l10n_ro_edi`
3. Register at ANAF for SPV access
4. Configure in **Settings > Accounting > Romanian EDI**:
   - ANAF API credentials (access token)
   - Test/Production environment
   - Import journal for received invoices
5. Install [Modules/l10n_ro_cpv_code](l10n_ro_cpv_code.md) for product classification
6. Set CPV codes on products for B2G invoices

## Technical Notes

- ANAF SPV uses OAuth2 authentication with access tokens
- 3-day holding period for non-indexed invoices before auto-refusal
- Bucharest (state code `B`) requires SECTOR1-6 city format
- Default VAT placeholder: `0000000000000` for non-VAT registered partners
- Cron job (`data/ir_cron.xml`) handles periodic synchronization
- Assets include Web components for the EDI status UI

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_ro](l10n_ro.md) | Base Romanian accounting |
| [Modules/l10n_ro_cpv_code](l10n_ro_cpv_code.md) | CPV product classification for invoices |
| [Modules/l10n_ro_edi_stock](l10n_ro_edi_stock.md) | e-Transport for stock/inventory |
| [Modules/l10n_ro_edi_stock_batch](l10n_ro_edi_stock_batch.md) | e-Transport batch processing |

## See Also

- [Modules/l10n_ro](l10n_ro.md) - Romanian accounting
- [Modules/l10n_ro_cpv_code](l10n_ro_cpv_code.md) - CPV product classification
- [Modules/l10n_ro_edi_stock](l10n_ro_edi_stock.md) - Romanian e-Transport
