---
Module: l10n_pe
Version: 18.0
Type: l10n/peru
Tags: #odoo18 #l10n #accounting #peru
---

# l10n_pe — Peru Accounting

## Overview
Peruvian accounting localization providing the Peruvian chart of accounts, SUNAT (Superintendencia Nacional de Aduanas y de Administracion Tributaria) taxes, document types (Factura Electronica, Boleta de Venta, Nota de Credito, Nota de Debito), identification types (DNI, RUC, Carnet de Extranjeria), and district-level geographic data (province, district). Maintained by Vauxoo. Requires [Modules/l10n_latam_base](l10n_latam_base.md) and [Modules/l10n_latam_invoice_document](l10n_latam_invoice_document.md).

## Country/Region
Peru (country code: PE)

## Dependencies
- base_vat
- base_address_extended
- l10n_latam_base
- l10n_latam_invoice_document
- account_debit_note
- account

## Key Models

### `account.move` (Extended)
Inherits: `account.move`
Methods:
- `_get_l10n_latam_documents_domain()`: Extends base domain. For sale journals in Peru, restricts to SUNAT document codes: 01 (Factura), 03 (Boleta), 07 (Nota de Credito), 08 (Nota de Debito), 20 (Comprobante de Percepcion), 40 (Comprobante de Retencion). For sales to foreign partners (identification type not RUC), adds codes 08b and 02 (internal refund types).
- `_inverse_l10n_latam_document_number()`: Inherits to pad document numbers to 8 digits after prefix. Example: transforms `FFF-32` to `FFF-00000032` for correct report formatting.

### `res.city` (Extended)
Inherits: `res.city`
Identification types for Peru: DNI (natural persons), RUC (companies), Carnet de Extranjeria.

### `account.chart.template` (Extended)
Method `_template_pe()`: Loads Peruvian chart of accounts.

## Chart of Accounts
Peruvian chart of accounts aligned with NIIF (Normas Internacionales de Informacion Financiera) as required by SUNAT. 4-digit account codes: 1-Activo, 2-Pasivo, 3-Patrimonio, 4-Ingresos, 5-Gastos, 6-Costos, 7-Cuentas de Cierre.

## Tax Structure
- **IGV** (Impuesto General a las Ventas): 18%
- **ISC** (Impuesto Selectivo al Consumo): Specific consumption taxes
- **IVAP**: Impuesto a la Venta del Arroz Pilado (special rate)
- Document types for SUNAT electronic invoice: Factura (01), Boleta (03), Nota de Credito (07), Nota de Debito (08), Percepcion (20), Retencion (40)

## SUNAT Document Types
Key codes:
- 01: Factura Electronica (for VAT-registered recipients)
- 03: Boleta de Venta Electronica (for end consumers)
- 07: Nota de Credito (credit memo)
- 08: Nota de Debito (debit memo)
- 20: Comprobante de Percepcion (perception document)
- 40: Comprobante de Retencion (retention document)

## Data Files
- `security/ir.model.access.csv`
- `views/account_tax_view.xml`: Tax configuration
- `views/res_bank_view.xml`: Peruvian banks
- `data/l10n_latam_document_type_data.xml`: SUNAT document types
- `data/res.city.csv`: Peruvian cities
- `data/l10n_pe.res.city.district.csv`: Districts per city
- `data/res_country_data.xml`: Country configuration
- `data/l10n_latam_identification_type_data.xml`: DNI, RUC, CE identification types
- `data/res.bank.csv`: Peruvian banks
- `demo/demo_company.xml`, `demo/demo_partner.xml`

## Installation
Install with accounting. Chart template and SUNAT document types loaded via data.

## Historical Notes
Version 3.0 in Odoo 18. Peru's SUNAT has progressively mandated electronic invoicing since 2014. The separation between Factura (01) and Boleta (03) is key: Facturas can be used when both issuer and recipient are VAT-registered (RUC); Boletas are for sales to end consumers (who may not have an RUC). The district-level geographic data (`l10n_pe.res.city.district`) is needed for the electronic invoice XML schema (CPE format).
