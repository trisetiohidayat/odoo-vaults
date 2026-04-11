---
type: module
module: l10n_ro_cpv_code
tags: [odoo, odoo19, l10n, localization, romania, cpv, procurement]
created: 2026-04-06
---

# Romania CPV Product Classification (`l10n_ro_cpv_code`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Romania - CPV Code |
| **Technical** | `l10n_hu_edi` |
| **Category** | Hidden |
| **Country** | Romania (RO) |
| **License** | LGPL-3 |
| **Author** | Odoo |
| **Version** | 1.0 |

## Description

This module adds **CPV (Common Procurement Vocabulary)** product classification support for Romania. The Romanian CIUS-RO format requires precise categorization of products sold to be included in the line details of electronic invoices.

The CPV system is the EU-standard vocabulary for procurement classification:
- 8-digit codes for products/services
- Hierarchical structure (division, group, class, category, subcategory)

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/l10n_ro_edi]] | Romanian e-invoicing (which depends on [[Modules/l10n_ro]]) |

## Category

`Hidden` - This module does not appear in the Apps list and is automatically installed as a dependency when needed.

## Data

### `l10n_ro.cpv.code.csv`

Contains the complete Romanian CPV code reference data. The CSV includes:
- CPV code (8 digits)
- CPV description (Romanian)
- Parent category hierarchy

Example entries:
```
code,description,parent_code
03100000-5,Produse agricole,03000000-8
03111000-5,Sămânță,03100000-5
```

## Models

### `product.template`

Extends [[product.template]] to add CPV code field:

```python
l10n_ro_cpv_code = fields.Many2one(
    'l10n_ro.cpv.code',
    string='CPV Code',
    help='Common Procurement Vocabulary code for Romanian e-invoicing'
)
```

### `l10n_ro.cpv.code`

Reference model for CPV codes:

```python
class L10nRoCpvCode(models.Model):
    _name = 'l10n_ro.cpv.code'
    _description = 'Romanian CPV Code'
    _order = 'code'

    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Description', required=True)
    parent_id = fields.Many2one('l10n_ro.cpv.code', string='Parent')
    child_ids = fields.One2many('l10n_ro.cpv.code', 'parent_id', string='Children')
```

## Usage

### Adding CPV Code to Products

1. Go to **Inventory > Products > Products**
2. Open a product form
3. In the **Romanian EDI** section, select the appropriate CPV code
4. The CPV code will be automatically included in e-invoices sent via ANAF

### CIUS-RO Integration

The [[Modules/l10n_ro_edi]] module automatically:
- Reads CPV code from product
- Includes it in the UBL invoice under `Item/CommodityClassification`
- Validates that CPV code is present for Romanian B2G invoices

## Related Modules

| Module | Relationship |
|--------|-------------|
| [[Modules/l10n_ro]] | Base Romanian accounting |
| [[Modules/l10n_ro_edi]] | E-invoicing that uses CPV codes |

## Technical Notes

- CPV codes are mandatory for B2G (government) invoices in Romania
- The module loads CSV data on installation via `data/l10n_ro.cpv.code.csv`
- Security via `security/ir.model.access.csv` - read access for all users, write for manager
- Product view inheritance adds CPV field in a dedicated "Romanian EDI" page

## See Also

- [[Modules/l10n_ro]] - Romanian accounting
- [[Modules/l10n_ro_edi]] - ANAF e-Factura integration
