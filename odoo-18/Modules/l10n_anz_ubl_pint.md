---
Module: l10n_anz_ubl_pint
Version: 1.0
Type: l10n/australia_newzealand
Tags: #odoo18 #l10n #edi #peppol #ubl #gst #australia #newzealand
---

# l10n_anz_ubl_pint — Australia & New Zealand UBL PINT

## Overview
This module implements the Peppol International (PINT) format for Billing, specialized for Australia (AU) and New Zealand (NZ). It extends `account_edi_ubl_cii_tax_extension` (which itself extends `account_edi_ubl_cii`) to produce Peppol-compliant e-invoices that conform to the PINT ANZ (Australia & New Zealand) specification. It is an EDI module — it generates and validates XML invoice files for Peppol network exchange.

## Countries
Australia (`AU`) and New Zealand (`NZ`)

## Dependencies
- `account_edi_ubl_cii_tax_extension`

## Key Models

### account_edi_xml_pint_anz.py
```python
class AccountEdiXmlUBLPINTANZ(models.AbstractModel):
    _inherit = "account.edi.xml.ubl_bis3"
    _name = "account.edi.xml.pint_anz"
```
Inherits from `account.edi.xml.ubl_bis3` (Peppol BIS Billing 3 base). Provides the ANZ PINT implementation.

**Key methods:**

`_get_partner_party_vals()` — Extends BIS3 to force all tax schemes to `GST` (no other tax scheme is valid in AU/NZ).

`_get_invoice_tax_totals_vals_list()` — If invoice currency differs from company currency, appends a second `TaxTotal` section in the accounting currency, per PINT ANZ rules for multi-currency invoices.

`_get_tax_unece_codes()` — OVERRIDE: If supplier has no VAT, returns tax category `O` (Outside scope of tax) with no exemption reason. If supplier is GST-registered, delegates to standard BIS3 logic.

`_get_tax_category_list()` — Forces all tax category schemes to `GST` (id: `GST`).

`_get_customization_ids()` — Registers the ANZ PINT customization ID: `urn:peppol:pint:billing-1@aunz-1`.

`_get_partner_party_legal_entity_vals_list()` — For AU/NZ partners, sets `company_id_attrs['schemeID']` to the Peppol EAS (Electronic Address Scheme) from `partner.peppol_eas`. Validates: AU partners must use EAS `0151` (ABN), NZ partners must use EAS `0088` (EAN).

`_get_invoice_line_item_vals()` — Removes the `percent` field from tax category lines where `tax_category_code == 'O'` (Not Subject to Tax), per PINT ANZ v1.1.0 rules.

`_export_invoice_filename()` — Returns `<filename>_pint_anz.xml` to identify the format.

`_export_invoice_vals()` — Adds:
- `customization_id`: `urn:peppol:pint:billing-1@aunz-1`
- `profile_id`: `urn:peppol:bis:billing`
- `tax_currency_code`: company currency name (when different from invoice currency)

`_export_invoice_constraints()` — Validates:
- `sg_vat_category_required`: every tax must have a category from `{S, E, Z, G, O}`
- `anz_tax_breakdown_amount`: category `O` (not subject to tax) must have tax amount 0
- `anz_non_gst_supplier_tax_scope`: if supplier has no VAT, non-zero taxes remapped to `O` are invalid
- `anz_duplicate_tax_breakdown`: at most one `O` tax subtotal allowed
- `au_<partner>_eas_0151`: AU partners must have Peppol EAS `0151`
- `nz_<partner>_eas_0088`: NZ partners must have Peppol EAS `0088`

### res_partner.py
```python
class ResPartner(models.Model):
    _inherit = 'res.partner'
    invoice_edi_format = fields.Selection(selection_add=[('pint_anz', "Australia (Peppol Pint AU)")])

    def _get_edi_builder(self, invoice_edi_format): ...
    def _get_ubl_cii_formats_info(self): ...
```
Adds `pint_anz` to the EDI format selection on partners. Sets its priority sequence to `90` (higher than UBL ANZ from `account_edi_ubl_cii`) so it takes precedence when both AU and NZ are available.

## Data Files
None (pure code module).

## EDI/Fiscal Reporting
This is the primary mechanism for e-invoicing compliance in AU and NZ:

**Australia:** The Australian Tax Office (ATO) mandates Peppol BIS 3.0 via the "Digital Ready" program. The PINT ANZ format is the Peppol International specialization for AU/NZ. GST is the only tax; the `tax_scheme_vals` must always be `GST`.

**New Zealand:** IRD (Inland Revenue Department) has adopted the same Peppol PINT ANZ framework. NZ also uses GST exclusively at 15%.

**PINT (Peppol International):** A base standard maintained by the Peppol Authority that countries adopt for international e-invoicing. PINT ANZ v1.1.0 is the current version implemented here.

## Installation
Standard optional installation. Install when the company is AU/NZ-based and will send/receive Peppol e-invoices.

## Historical Notes
- **Odoo 17 → 18:** This module is new in Odoo 18. There was no AU/NZ PINT implementation in Odoo 17 (UBL ANZ existed but not the Peppol PINT format).
- The module prioritizes sequence `90` over the standard UBL ANZ from `account_edi_ubl_cii` (sequence `50`) to ensure PINT is used when available.
- GST categories: `S` = Standard rate, `E` = Exempt, `Z` = Zero rated, `G` = Free/0% (exports), `O` = Outside scope.
