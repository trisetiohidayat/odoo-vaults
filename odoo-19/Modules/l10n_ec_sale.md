---
type: module
module: l10n_ec_sale
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Ecuador Sale Localization (`l10n_ec_sale`)

## Overview
- **Name:** Ecuador - Sale
- **Country:** Ecuador (EC)
- **Category:** Accounting/Localizations/Sale
- **Version:** 1.0
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `l10n_ec`, `sale`
- **Auto-installs:** Yes (auto_installs on its dependencies)
- **Countries:** `ec`

## Description

Ecuador Sale module extends the base Ecuadorian accounting localization (`l10n_ec`) with sale-specific configurations and SRI payment method integration for the [Modules/Sale](Sale.md) module.

## Configuration
1. Install `l10n_ec` first for the accounting base
2. Install `l10n_ec_sale` to enable sale-specific Ecuadorian features
3. Configure SRI payment methods in Point of Sale and Sales Order payment methods

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_ec](l10n_ec.md) | Ecuadorian accounting base |
| [Modules/Sale](Sale.md) | Sales management module |

## Key Models

### sale.order (Inherit)
Extends `sale.order`:

- **l10n_ec_sri_payment_id:** Many2one to `l10n_ec.sri.payment` - SRI payment method for the sale
- **_prepare_invoice():** Passes SRI payment method to the generated invoice when country code is EC
- **_create_invoices():** Auto-populates SRI payment method from POS transaction payment methods onto the created invoice

### payment.method (Inherit)
Extends `payment.method`:

- **l10n_ec_sri_payment_id:** Many2one to `l10n_ec.sri.payment` - links payment method to an SRI payment type
- **fiscal_country_codes:** Returns comma-separated fiscal country codes from current companies (used for POS fiscal country filtering)

## SRI Payment Method Integration

SRI (Servicio de Rentas Internas) requires specifying the payment method on electronic invoices. This module bridges the gap between Odoo's payment methods and SRI's mandated payment method codes.

### Common SRI Payment Codes
| Code | Description |
|------|-------------|
| `01` | SIN FORMAS DE PAGO |
| `02` | CHEQUE PROPIO |
| `03` | CHEQUE CERTIFICADO |
| `04` | CHEQUE DE VENTAS |
| `05` | TARJETA DE CREDITO |
| `06` | TARJETA DE DEBITO |
| `07` | DINERO ELECTRONICO |
| `08` | TARJETA PREPAGO |
| `09` | OTROS |
| Various | Additional codes per SRI regulations |

## Data Files
- `data/payment_method_data.xml` - Payment method configuration
- `views/payment_method_views.xml` - Payment method form/view customization
- `views/sale_order_views.xml` - Sale order form customization (SRI payment method field)

## Workflow
1. User selects SRI payment method on Sale Order or POS order
2. When invoice is created from sale order, SRI payment method is carried over
3. When invoice is created from POS, payment transaction's SRI method is used (if only one type exists)
4. Invoice's `l10n_ec_sri_payment_id` is set for SRI electronic document submission

## Related Modules
- [Modules/l10n_ec](l10n_ec.md) - Core Ecuadorian accounting
- [Modules/l10n_ec_sale](l10n_ec_sale.md) - Ecuador sale (this module)
- [Modules/l10n_ec_stock](l10n_ec_stock.md) - Ecuador stock extensions
- [Modules/Sale](Sale.md) - Sales management
- [Modules/pos](pos.md) - Point of Sale
