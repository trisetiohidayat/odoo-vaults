# sale_edi_ubl — Sale EDI UBL

**Tags:** #odoo #odoo18 #sale #edi #ubl #international-trade #peppol
**Odoo Version:** 18.0
**Module Category:** Sale + EDI Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_edi_ubl` provides UBL EDI export and import support for sale orders. It extends the `account_edi_ubl_cii` framework with sale-order-specific field mapping, UBL BIS 3 order document generation, and import logic for UBL order responses. It is the counterpart to `purchase_edi_ubl_bis3` for the selling side.

**Technical Name:** `sale_edi_ubl`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_edi_ubl/`
**Depends:** `sale`, `account_edi_ubl_cii`
**Inherits From:** `sale.order`, `account.edi.common`, `account.edi.xml.ubl_bis3`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order.py` | `sale.order` | EDI decoder registration, order line mapping, UBL order creation |
| `models/sale_edi_common.py` | `sale.edi.common` (abstract) | UBL import logic, partner resolution |
| `models/sale_edi_xml_ubl_bis3.py` | `sale.edi.xml.ubl_bis3` | UBL BIS3 XML order generation |

---

## Models Reference

### `sale.edi.common` (models/sale_edi_common.py)

Abstract model extending `account.edi.common`. Provides shared UBL import logic.

#### Methods

| Method | Behavior |
|--------|----------|
| `_import_order_ubl()` | Parses UBL order XML: extracts order ID, dates, currency, partner info |
| `_import_order_lines()` | Maps UBL line items to SOL data (product, qty, price, discount) |
| `_import_payment_term_id()` | Maps UBL PaymentTerms to `account.payment.term` |
| `_import_delivery_partner()` | Extracts delivery address from UBL Delivery element |
| `_get_sale_order_values()` | Builds base SO vals dict from parsed UBL |
| `_retrieve_partner()` | Resolves partner by VAT/email from UBL party data |

---

### `sale.edi.xml.ubl_bis3` (models/sale_edi_xml_ubl_bis3.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_import_fill_order()` | Populates SO from UBL document: partner, lines, payment terms, delivery |
| `_import_retrieve_delivery_vals()` | Gets delivery address from UBL cac:Delivery block |

---

### `sale.order` (models/sale_order.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_get_order_edi_decoder()` | Registers UBL decoder alongside standard JSON decoder |
| `_get_order_ubl_builder_from_xml_tree()` | Identifies UBL document type and selects appropriate builder |
| `_create_activity_set_details()` | Creates sale activity set from EDI data |
| `_get_line_vals_list()` | Maps SOL to UBL line vals for export |

#### EDI Decoder Architecture

The EDI framework calls `_get_order_edi_decoder()` to find matching decoders for an incoming document. UBL XML is recognized by its namespace. The builder generates the UBL document as a `ir.attachment` on the SO.

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

| File | Content |
|------|---------|
| `data/edi_data.xml` | UBL BIS3 format definition for sale order export |

---

## Critical Behaviors

1. **UBL Import**: `_import_order_ubl()` parses UBL 2.1 Order XML documents (typically from buyers using PEPPOL or similar EDI networks). It maps UBL elements to Odoo fields: order reference, dates, currency, line items, taxes, payment terms.

2. **Partner Resolution**: `_retrieve_partner()` matches incoming EDI partners by VAT number. If no match, creates a new partner record — enabling automatic prospect creation from EDI orders.

3. **Sale Order Export**: `_get_line_vals_list()` maps SOL data (product code, description, qty, UoM, price, discounts) to UBL CAC elements (`cac:OrderLine`, `cac:LineItem`, `cac:Price`, etc.).

4. **BIS3 Compliance**: The exported UBL follows the PEPPOL BIS 3 (Business Interoperability Settings) profile, which is the subset of UBL 2.1 mandated for government EDI in many EU jurisdictions.

5. **Dual Direction**: This module handles both import (buyer sends UBL order → Odoo creates SO) and export (Odoo sends UBL order → buyer processes). The `sale_edi_xml_ubl_bis3` model handles export; `sale_edi_common` handles import.

---

## v17→v18 Changes

- `_get_order_edi_decoder()` and `_get_order_ubl_builder_from_xml_tree()` methods added for improved EDI decoder architecture
- `_create_activity_set_details()` method added for activity creation from EDI data
- UBL BIS3 export compliance updates

---

## Notes

- UBL (Universal Business Language) 2.1 is an international EDI standard maintained by OASIS
- PEPPOL (Pan-European Public Procurement OnLine) uses UBL BIS 3 as its document format
- `sale_edi_ubl` and `purchase_edi_ubl_bis3` together enable full EDI order processing
- The `account_edi_ubl_cii` module provides the shared UBL infrastructure reused here
