---
Module: l10n_fr_facturx_chorus_pro
Version: 18.0
Type: l10n/fr
Tags: #odoo18 #l10n #accounting #edi
---

# l10n_fr_facturx_chorus_pro

## Overview
France-specific EDI extension that bridges Factur-X (EN 16931 compliant cross-border e-invoice format) with Chorus Pro — France's government e-invoicing portal for public procurement. Adds three optional fields to invoices required when submitting to Chorus Pro and enables Peppol channel delivery via the Pagero network.

## Country
[France](modules/account.md) 🇫🇷

## Dependencies
- [account](core/basemodel.md)
- account_edi_ubl_cii
- [l10n_fr_account](modules/account.md)

## Key Models

### AccountMove
`models/account_move.py` — extends `account.move`
- `buyer_reference` (Char) — "Service Exécutant" in Chorus Pro; the service code for the ordering public entity
- `contract_reference` (Char) — "Numéro de Marché" in Chorus Pro; the public procurement contract reference
- `purchase_order_reference` (Char) — "Engagement Juridique" in Chorus Pro; the legal commitment number

These fields are displayed in a "Chorus Pro" group on the invoice form, visible only for out_invoice and out_refund.

### AccountEdiXmlUBLBIS3 (extends account_edi_ubl_cii)
`models/account_edi_xml_ubl_bis3.py` — extends `account.edi.xml.ubl_bis3`
- `_export_invoice_vals()` — extends: adds `buyer_reference` to BuyerReference node (Pagero requirement), `purchase_order_reference` to OrderReference/ID node
- `_export_invoice_constraints()` — validates SIRET presence on both customer (if Chorus Peppol ID) and supplier (if FR supplier submitting to Chorus)
- `_add_invoice_header_nodes()` — extends: serializes BuyerReference and OrderReference into XML
- `_get_party_node()` — extends: adds PartyIdentification node with SIRET (schemeID FR:SIRET) for French parties, or VAT for non-French, when customer has Chorus Pro Peppol ID `0009:11000201100044`

## Data Files
No data files (all configuration is in model extensions and view inheritance).

## Chart of Accounts
Inherits from base `account` and [l10n_fr_account](modules/account.md).

## Tax Structure
Inherits from [l10n_fr_account](modules/account.md).

## Fiscal Positions
Inherits from [l10n_fr_account](modules/account.md).

## EDI/Fiscal Reporting

**Factur-X / Chorus Pro integration:**
- Extends EN 16931 UBL-BIS3 export format (Factur-X is based on this)
- When customer Peppol endpoint = `0009:11000201100044` (Chorus Pro Peppol ID):
  - BuyerReference → Service Code in Chorus
  - OrderReference/ID → Commitment Number in Chorus
  - PartyIdentification → SIRET for French suppliers, VAT for EU suppliers
- Validation: SIRET required on customer + French suppliers
- Pagero network used as transport layer

**Chorus Pro fields:**
| Field | Chorus Pro Name | XML Node |
|---|---|---|
| `buyer_reference` | Service Exécutant | `cbc:BuyerReference` |
| `contract_reference` | Numéro de Marché | (serialized in header) |
| `purchase_order_reference` | Engagement Juridique | `cac:OrderReference/cbc:ID` |

## Installation
No auto_install; install manually. No demo data.

## Historical Notes

**Odoo 17 → 18 changes:**
- New module — Chorus Pro integration was previously handled via third-party connectors or manual field entry
- Factur-X (EN 16931) is mandatory for B2G in France (from 2020 for large enterprises, phased to 2025 for SMEs)
- Chorus Pro integration via Peppol network (Pagero) is the recommended transport path
- SIRET-based party identification is a key Chorus Pro requirement that generic Factur-X did not previously handle

**Performance Notes:**
- EDI extension only activates for invoices to Chorus Pro Peppol ID — no overhead for other invoices
- SIRET validation runs on invoice export, not on every save