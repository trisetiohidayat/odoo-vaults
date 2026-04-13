---
type: module
module: l10n_co_pos
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Colombia POS Localization (`l10n_co_pos`)

## Overview
- **Name:** Colombian - Point of Sale
- **Country:** Colombia (CO)
- **Category:** Accounting/Localizations/Point of Sale
- **Version:** 1.0
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `l10n_co`, `point_of_sale`
- **Auto-installs:** Yes (auto_installs on its dependencies)
- **Countries:** `co`

## Description

Colombian Point of Sale module extends the base Colombian accounting localization (`l10n_co`) with POS-specific configurations. Provides Colombia-specific JavaScript assets, POS interface customizations, and integration with the DIAN (Direccion de Impuestos y Aduanas Nacionales) electronic invoicing requirements for POS environments.

## Configuration
1. Install `l10n_co` first for the accounting base
2. Install `l10n_co_pos` to enable Colombian POS-specific features
3. Configure POS journals with appropriate document types

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_co](modules/l10n_co.md) | Colombian accounting base |
| [Modules/pos](modules/pos.md) | Point of Sale core module |

## Key Components

### POS Assets
- JavaScript and CSS assets specific to Colombian POS requirements
- Loaded via `point_of_sale._assets_pos` bundle

### POS-Specific Customizations

The module provides Colombia-specific customizations for the POS interface including:
- DIAN-compliant document number formatting for POS receipts
- Integration with Colombian electronic invoice workflows
- Support for the Colombian taxpayer identification (NIT) in POS partner creation

## Colombian POS Document Types

The POS environment in Colombia uses specific document types:

| Document Type | Code | Usage |
|--------------|------|-------|
| Factura POS | Various | Point of Sale receipts |
| Nota Credito POS | Various | POS credit notes |
| Documento soporte | Various | Supporting documents for non-VAT taxpayers |

## DIAN Requirements

Colombia's DIAN requires electronic documents for businesses meeting certain thresholds. The POS must:

1. Generate fiscal documents that comply with DIAN numbering
2. Use the correct document type codes
3. Handle simplified invoice structures for retail/POS environments

## Colombia Tax Reminders

### IVA (Impuesto al Valor Agregado)
- **Standard rate:** 19%
- Reduced rates: 14% (some goods/services), 5% (some goods), 0% (exempt)

### ICA (Impuesto de Industria y Comercio)
- Municipal tax on commercial activities
- Rates vary by municipality and activity type

### Retention Regimes
Colombia has mandatory retention regimes for:
- ReteIVA (IVA withholding) - for taxpayers with high volume operations
- ReteICA (ICA withholding)
- ReteFuente (Income tax withholding)

## Related Modules
- [Modules/l10n_co](modules/l10n_co.md) - Core Colombian accounting
- [Modules/l10n_co_pos](modules/l10n_co_pos.md) - Colombian POS (this module)
- [Modules/account](modules/account.md) - Core accounting
- [Modules/pos](modules/pos.md) - Point of Sale core module
