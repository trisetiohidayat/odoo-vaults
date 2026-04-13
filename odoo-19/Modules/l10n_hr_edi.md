---
type: module
module: l10n_hr_edi
tags: [odoo, odoo19, l10n, localization, croatia, edi, einvoicing, fiscalization]
created: 2026-04-06
---

# Croatia EDI / E-Invoicing (`l10n_hr_edi`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Croatia - e-invoicing |
| **Technical** | `l10n_hr_edi` |
| **Category** | Accounting/Localizations/Reporting |
| **Country** | Croatia (HR) |
| **License** | OEEL-1 (Odoo Enterprise Edition License) |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |

## Description

This module provides Croatian e-invoicing compliance through the **MojEracun** platform and mandatory invoice fiscalization via the Croatian Tax Authority (Porezna uprava). It extends `l10n_hr` with EDI capabilities required for B2G and B2B transactions.

### Key Capabilities

- **Fiscalization**: Real-time reporting of sales invoices to the Croatian Tax Authority
- **MojEracun Integration**: Electronic invoice exchange via the national e-invoicing system
- **CIUS HR**: UBL 2.1 compliant invoice format per Croatian CIUS specifications
- **Payment Reporting**: Report payment status back to the Tax Authority

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_hr](odoo-18/Modules/l10n_hr.md) | Croatian base accounting localization |
| [Modules/account_edi_ubl_cii](odoo-18/Modules/account_edi_ubl_cii.md) | UBL/CII EDI framework |
| [Modules/account_peppol](odoo-17/Modules/account_peppol.md) | PEPPOL network access |

## Models

### `account.move` Fields

Extends [account.move](account.move.md) with Croatian EDI-specific fields:

```python
# Business Process Type (Obvezni podaci - P signatura)
l10n_hr_process_type = fields.Selection([
    ('P1', "P1: Contract-based delivery"),
    ('P2', "P2: Periodic invoicing"),
    ('P3', "P3: Independent purchase order"),
    ('P4', "P4: Prepayment (advance payment)"),
    ('P5', "P5: Payment on the spot"),
    ('P6', "P6: Payment before delivery"),
    ('P7', "P7: Invoice with delivery note ref"),
    ('P8', "P8: Invoice with shipping/receipt notes"),
    ('P9', "P9: Credit note / negative amounts"),
    ('P10', "P10: Corrective invoice"),
    ('P11', "P11: Partial and final invoices"),
    ('P12', "P12: Self-issuance of invoice"),
    ('P99', "P99: Customer-defined process"),
], string="Business Process Type")

l10n_hr_customer_defined_process_name = fields.Char(
    string="Custom Process Name",
    help="Required when Process Type is P99"
)

# Fiscalization fields
l10n_hr_fiscal_user_id = fields.Many2one('res.partner', string="Fiscal User")
l10n_hr_fiscalization_number = fields.Char(string="Fiscalization Number")
l10n_hr_fiscalization_status = fields.Selection(...)
l10n_hr_fiscalization_error = fields.Char()
l10n_hr_fiscalization_channel_type = fields.Selection(...)

# MojEracun
l10n_hr_mer_document_eid = fields.Char(string="MojEracun Document ID")
l10n_hr_mer_document_status = fields.Selection(...)
l10n_hr_edi_addendum_id = fields.One2many('l10n_hr_edi.addendum', ...)

# Payment Reporting
l10n_hr_payment_method_type = fields.Selection([
    ('G', 'GOTOVINA / Cash'),
    ('K', 'KARTICA / Card'),
    ('T', 'TRANSAKCIJSKI RAČUN / Transfer'),
    ('O', 'OSTALO / Other'),
], string="Payment Method")
l10n_hr_payment_reported_amount = fields.Monetary()
l10n_hr_payment_unreported = fields.Boolean()
```

### `l10n_hr_edi.addendum`

Tracks the complete EDI lifecycle:

```python
class L10nHrEdiAddendum(models.Model):
    _name = 'l10n_hr_edi.addendum'
    _description = "HR EDI Addendum"

    move_id = fields.Many2one('account.move')
    business_document_status = fields.Selection([
        ('0', 'Approved by recipient'),
        ('1', 'Rejected by recipient'),
        ('2', 'Fully paid'),
        ('3', 'Partially paid'),
        ('4', 'Payment timeout'),
        ('99', 'Other'),
    ])
    fiscalization_status = fields.Char()
    fiscalization_number = fields.Char()
    invoice_sending_time = fields.Datetime()
    mer_document_eid = fields.Char()
    mer_document_status = fields.Char()
```

### Other Extended Models

| Model | File | Purpose |
|-------|------|---------|
| `account.journal` | `account_journal.py` | EDI journal configuration |
| `account.move.line` | `account_move_line.py` | Croatian-specific line handling |
| `account.move.send` | `account_move_send.py` | EDI sending via MojEracun |
| `account.tax` | `account_tax.py` | Tax category mapping |
| `product.template` | `product_template.py` | KPD product category |
| `res.company` | `res_company.py` | Company EDI settings |
| `res.partner` | `res_partner.py` | Partner EDI data |
| `res.config.settings` | `res_config_settings.py` | EDI configuration wizard |

## Key Methods

### `account.move` Actions

```python
# Reject a vendor bill on MojEracun
def l10n_hr_edi_mer_action_reject(self):
    """Opens wizard to reject MojEracun invoice"""

# Fetch and update document status
def l10n_hr_edi_mer_action_fetch_status(self):
    """Queries MojEracun for current document status"""

# Report payment to Tax Authority
def l10n_hr_edi_mer_action_report_paid(self):
    """Reports partial/full payment to fiscalization system"""
```

### Fiscalization Number Pattern

Invoice names must follow the pattern: `{serial}/{premises_label}/{device_label}`

Example: `INV/2024/00001/1/1` where:
- `00001` = sequential invoice number
- `1` = business premises identifier
- `1` = cash register/device identifier

## CIUS HR Requirements

The Croatian CIUS extends EN 16931 with mandatory fields:

| Field | Description |
|-------|-------------|
| Business Process Type | P1-P12 or P99 |
| Fiscalization Number | Tax Authority assigned number |
| Operator OIB | Person responsible for issuance |
| Payment Method | Cash, card, transfer, other |
| Invoice Issue Timestamp | When invoice was issued |

## Wizard

### `l10n_hr_edi.mojeracun_reject_wizard`

Allows users to reject vendor bills received via MojEracun with a reason.

## Configuration

1. Install `l10n_hr` first (dependency)
2. Install `l10n_hr_edi`
3. Configure company OIB in company settings
4. Set up MojEracun credentials in company EDI settings
5. Configure fiscal user (person responsible for fiscalization)
6. Set up EDI journal for electronic invoice exchange
7. Configure KPD product categories for classification

## Security

Access rights managed via `security/ir.model.access.csv`:
- `l10n_hr_edi.addendum`: Read/write for internal users
- `l10n_hr_kpd_category`: Product category classification access

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_hr](odoo-18/Modules/l10n_hr.md) | Base Croatian accounting |
| [Modules/l10n_hr_kuna](odoo-18/Modules/l10n_hr_kuna.md) | Historical Kuna currency (deprecated) |
| [Modules/account_edi_ubl_cii](odoo-18/Modules/account_edi_ubl_cii.md) | UBL/CII EDI framework |

## Technical Notes

- License is **OEEL-1** (Enterprise only) - not open source LGPL
- Uses `post_init` hook to configure default EDI settings
- The module extends `sequence.mixin` for Croatian invoice numbering
- Product categories (`l10n_hr_kpd_category`) classify products for KPD reporting
- Cron job (`data/cron.xml`) handles periodic status synchronization
- Default VAT placeholder: `0000000000000` for partners without VAT
