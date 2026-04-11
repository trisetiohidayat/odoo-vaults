---
Module: l10n_it_edi_website_sale
Version: 18.0
Type: l10n/it/edi/website
Tags: #odoo18 #l10n #edi #italy #ecommerce
---

# l10n_it_edi_website_sale

## Overview
Bridges `website_sale` (eCommerce) with `l10n_it_edi` (Italian e-invoicing). In Italy, B2C distance sales must be reported to SdI even without a formal purchase order. This module ensures that customer data collected in the webshop (fiscal code, PA index) is made available to the FatturaPA XML generator, so that e-commerce orders can produce legally valid electronic invoices.

## EDI Format / Standard
Inherits FatturaPA XML generation from `l10n_it_edi`. This module ensures required fields are populated before XML is generated.

## Dependencies
- `l10n_it_edi` (Italian EDI)
- `website_sale` (eCommerce)

## Key Models
None — this module does not define new model classes. It adds:
- Website controller logic to propagate customer fiscal code and PA index into the eCommerce session
- Form validation for Italian fiscal identifiers on the webshop checkout

## Data Files
- `views/templates.xml` — QWeb templates for checkout form modifications
- `data/data.xml` — Form builder whitelist for `res.partner` fields (`l10n_it_codice_fiscale`, `l10n_it_pa_index`)

## How It Works
1. Customer places an order via the webshop and enters their fiscal code (codice fiscale) and/or PA index (codice unico ufficio for public administration buyers)
2. The module's JavaScript component (`l10n_it_edi_website_sale.js`) reads these fields from the checkout form and stores them on the partner record
3. When an invoice is generated (either manually from the back-office or via the portal), the fiscal code and PA index are available for FatturaPA XML generation
4. B2C invoices to individuals without a VAT number use the fiscal code as the identification field

## Installation
Auto-installs when both `l10n_it_edi` and `website_sale` are installed. No separate installation needed.

## Historical Notes
- **Odoo 18**: New module. Italian B2C e-commerce invoicing requires the buyer's fiscal code (for individuals) or PA index (for government buyers) on every invoice. This module bridges the webshop checkout flow with the EDI generation process.