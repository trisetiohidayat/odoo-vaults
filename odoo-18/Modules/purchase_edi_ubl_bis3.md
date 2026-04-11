# purchase_edi_ubl_bis3 — Purchase EDI UBL BIS3

**Tags:** #odoo #odoo18 #purchase #edi #ubl #bis3 #international-trade
**Odoo Version:** 18.0
**Module Category:** Purchase + EDI Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`purchase_edi_ubl_bis3` provides UBL BIS3 export support for purchase orders. It complements `sale_edi_ubl` by enabling the same EDI format on the Purchase side, generating conformant UBL 2.1 BIS 3 purchase order XML documents that can be sent to government portals or procurement platforms in jurisdictions that mandate EDI (e.g., PEPPOL networks in the EU).

**Technical Name:** `purchase_edi_ubl_bis3`
**Python Path:** `~/odoo/odoo18/odoo/addons/purchase_edi_ubl_bis3/`
**Depends:** `purchase`, `account_edi_ubl_cii`
**Inherits From:** `purchase.order`, `account.edi.xml.ubl_bis3`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/purchase_order.py` | `purchase.order` | EDI builder registration |
| `models/purchase_edi_xml_ubl_bis3.py` | `account.edi.xml.ubl_bis3` | UBL BIS3 purchase order XML generation |

---

## Models Reference

### `purchase.order` (models/purchase_order.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_get_edi_builders()` | Registers `purchase.edi.xml.ubl_bis3` for UBL BIS3 export |

---

### `account.edi.xml.ubl_bis3` (models/purchase_edi_xml_ubl_bis3.py)

This model extends `account.edi.xml.ubl_bis3` with purchase-order-specific export logic. See the parent model in `account_edi_ubl_cii` for the full UBL BIS3 generation framework.

#### Methods

| Method | Behavior |
|--------|----------|
| `_export_purchase_order_filename()` | Returns filename: `{SUPPLIER_SIRE}_{BUYER_SIRE}_{ORDER_NAME}.xml` |
| `_get_country_vals()` | Serializes country as `cbc:Country` UBL element |
| `_get_partner_address_vals()` | Serializes supplier/buyer address as `cac:Address` |
| `_get_partner_party_tax_scheme_vals()` | Tax scheme registration (VAT/TIN) |
| `_get_partner_party_legal_entity_vals()` | Party legal entity (name, ID) |
| `_get_partner_contact_vals()` | Contact details (phone, email) |
| `_get_partner_party_vals()` | Full party block: address + contact + tax scheme + legal entity |
| `_get_delivery_party_vals()` | Delivery party (dropship or warehouse) |
| `_get_payment_terms_vals()` | Payment terms as `cac:PaymentTerms` |
| `_get_tax_category_vals()` | Tax category per line (rate, category code) |
| `_get_line_allowance_charge_vals()` | Line-level discounts/charges |
| `_get_line_item_price_vals()` | Item price with allowance/charge details |
| `_get_anticipated_monetary_total_vals()` | Anticipated total with tax |
| `_get_item_vals()` | Item description, commodity classification |
| `_get_order_lines()` | Serializes all POLs as `cac:OrderLine` |
| `_export_order_vals()` | Assembles full UBL document structure |
| `_export_order()` | Main entry: generates and returns XML attachment |

#### UBL Document Structure

The exported XML follows UBL 2.1 BIS 3 Order schema:
- `cac:Order` (root)
  - `cbc:ID`, `cbc:IssueDate`, `cbc:OrderTypeCode`
  - `cac:BuyerCustomerParty` (our company)
  - `cac:SellerSupplierParty` (vendor)
  - `cac:Delivery` (if dropship)
  - `cac:PaymentTerms`
  - `cac:TaxTotal`
  - `cac:AnticipatedMonetaryTotal`
  - `cac:OrderLine[]` (one per POL)

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

No data file (`data/` directory does not exist in this module).

---

## Critical Behaviors

1. **EDI Builder Registration**: `_get_edi_builders()` on `purchase.order` registers the UBL BIS3 format as an available export option, similar to how `sale_edi_ubl` does for sale orders.

2. **Dual-Use Class**: `account.edi.xml.ubl_bis3` is used for both sale and purchase EDI. This model extends it with purchase-order-specific field names (Order vs. Order) and UBL element population.

3. **Filename Convention**: `{SupplierVAT}_{BuyerVAT}_{POName}.xml` — uses VAT numbers (SIRET/SIREN in France, VAT ID in EU) for cross-border identification.

4. **Tax Total**: `_get_anticipated_monetary_total_vals()` computes the grand total including all taxes, used by tax authorities for pre-clearance validation.

5. **Line Allowances**: Discounts and extra charges per line are serialized as `cac:AllowanceCharge` elements, preserving the actual price after discount for EDI compliance.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified. Module structure and EDI logic remain consistent.

---

## Notes

- This module is the purchase-side equivalent of `sale_edi_ubl`
- Both use `account.edi.xml.ubl_bis3` as the base class, with module-specific overrides
- The BIS3 (Business Interoperability Settings) profile is the PEPPOL-compliant subset of UBL 2.1
- Works in conjunction with `purchase_edi_ubl_bis3` on the buyer side and `sale_edi_ubl` on the seller side
- UBL XML attachments are attached to the PO record via the EDI framework
