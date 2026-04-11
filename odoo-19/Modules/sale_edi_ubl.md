# sale_edi_ubl

Odoo 19 Sales/EDI Module

## Overview

`sale_edi_ubl` enables Odoo to **import and export Sale Orders via the UBL Bis 3 format** (Peppol Ordering 3.0). It extends `account_edi_ubl_cii` with sale order-specific EDI capabilities for electronic document interchange with B2B partners.

## Module Details

- **Category**: Sales/Sales
- **Depends**: `sale`, `account_edi_ubl_cii`
- **Version**: 1.0
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Key Components

### Abstract Model: `sale.edi.xml.ubl_bis3`

Inherits from `account.edi.xml.ubl_bis3` and implements sale order-specific EDI:

**Export (UBL XML generation):**
- `_export_order()` — Generates the full UBL Order XML document.
- `_get_sale_order_node()` — Builds the document structure with header, parties, lines, taxes, monetary totals.
- `_add_sale_order_header_nodes()` — CustomizationID `urn:fdc:peppol.eu:poacc:trns:order:3`, ProfileID `urn:fdc:peppol.eu:poacc:bis:ordering:3`, order type code 220.
- `_add_sale_order_monetary_total_nodes()` — Includes line extension, tax, allowance/charge, prepaid, and payable amounts.
- `_ubl_get_line_allowance_charge_discount_node()` — Extends to strip reason/multiplier/base from discount nodes for the ordering profile.

**Import (UBL XML parsing):**
- `_retrieve_order_vals()` — Extracts order vals from UBL tree (partner, lines, delivery address, etc.).
- `_import_order_ubl()` — Main import entry point, also recomputes `price_unit` and `discount` from sale price data.
- `_get_product_xpaths()` — Adds `variant_barcode` (`ExtendedID`) and `variant_default_code` (`SellersItemIdentification/ExtendedID`) to support product variant matching.

### Models

#### `sale.order` (Inherited)

- `_get_edi_builders()` — Adds `sale.edi.xml.ubl_bis3` to EDI builders.
- `_get_import_file_type()` — Identifies UBL Bis 3 files by CustomizationID `urn:fdc:peppol.eu:poacc:trns:order:3`.
- `_get_edi_decoder()` — Routes to `_import_order_ubl()` for matching files.
- `_create_activity_set_details()` — Creates a mail activity on the order for unimported details.

#### `product.product` (Inherited)

Extends `_get_product_domain_search_order()` to include `variant_default_code` and `variant_barcode` in product search priority, enabling variant-level matching in UBL imports.

## Peppol Compliance

- Format: UBL Order 2.1 (Peppol BIS Ordering 3.0)
- Customization ID: `urn:fdc:peppol.eu:poacc:trns:order:3`
- Profile ID: `urn:fdc:peppol.eu:poacc:bis:ordering:3`
- Order Type Code: 220
