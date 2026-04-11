---
type: module
module: l10n_uy_pos
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Uruguay POS Localization (`l10n_uy_pos`)

## Overview
- **Name:** Uruguayan - Point of Sale
- **Country:** Uruguay (UY)
- **Category:** Accounting/Localizations/Point of Sale
- **Version:** 1.0
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `l10n_uy`, `point_of_sale`
- **Auto-installs:** Yes (auto_install on its dependencies)
- **Countries:** `uy`

## Description

This module brings the technical requirements for Uruguayan Point of Sale regulation. Install this if you are using the Point of Sale app in Uruguay.

Provides POS-specific configurations, assets, and document handling for the Uruguayan market, including support for the DGI-mandated e-ticket and e-invoice requirements in POS environments.

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/l10n_uy]] | Uruguayan accounting base |
| [[Modules/pos]] | Point of Sale core module |

## Key Components

### POS Assets
- JavaScript and CSS assets specific to Uruguayan POS requirements
- Loaded via `point_of_sale._assets_pos` bundle

### Document Type Integration
Integrates with [[Modules/l10n_latam_invoice_document]] to handle:
- E-ticket documents for POS receipts (codes 101-103, 201-203)
- E-receipt documents for consumer transactions
- Proper sequence management for POS-specific document types

## Uruguayan POS-Specific Documents

The POS environment in Uruguay uses specific document types:

| Document Type | Code Range | Usage |
|--------------|-----------|-------|
| E-Ticket | 101, 102, 103 | Electronic tickets |
| E-Ticket (Alternate) | 201, 202, 203 | Cross-referenced variants |
| E-Receipt | Various | Consumer receipts via POS |

## Configuration Notes

1. Install `l10n_uy` first to set up the accounting base
2. Install `l10n_uy_pos` to enable POS-specific configurations
3. Configure POS journals with appropriate document types
4. Set up fiscal printer integration if required by DGI regulations

## Related Modules
- [[Modules/l10n_uy]] - Core Uruguayan accounting
- [[Modules/l10n_uy_pos]] - Uruguayan POS (this module)
- [[Modules/l10n_latam_base]] - Latin America base localization
- [[Modules/l10n_latam_invoice_document]] - LATAM document types
- [[Modules/pos]] - Point of Sale core module
