# Italy - Sale E-invoicing (`l10n_it_edi_sale`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Italy - Sale E-invoicing |
| **Technical** | `l10n_it_edi_sale` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_it_edi`, `sale` |

## Description
Extends sale orders with Italian e-invoicing (FatturaPA/SDI) metadata. Allows recording origin documents (purchase order, contract, agreement), CIG (tender identifier), and CUP (public investment identifier) on sale orders, and propagates these values to the generated customer invoice for SDI transmission.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_it_edi` | Core Italian SDI/FatturaPA e-invoicing |
| `sale` | Base sale order module |

## Technical Notes
- Country code: `it` (Italy)
- Standard: SDI/FatturaPA
- CIG/CUP: Mandatory for PA (Public Administration) invoicing per Italian procurement law

## Models

### `sale.order` (Extended)
Fields for Italian e-invoice origin data:

| Field | Type | Description |
|-------|------|-------------|
| `l10n_it_origin_document_type` | Selection | Type of origin document: `purchase_order`, `contract`, `agreement` |
| `l10n_it_origin_document_name` | Char | Name/number of the origin document |
| `l10n_it_origin_document_date` | Date | Date of the origin document |
| `l10n_it_cig` | Char | CIG (Codice Identificativo Gara) — Tender unique identifier |
| `l10n_it_cup` | Char | CUP (Codice Unico di Progetto) — Public investment unique identifier |
| `l10n_it_partner_pa` | Boolean | True if the customer is a Public Administration entity (computed) |

**`_compute_l10n_it_partner_pa()`:** Computed from partner's PA index (7-digit code) or `_l10n_it_edi_is_public_administration()` result. Controls visibility of CIG/CUP fields.

**`_prepare_invoice()`:** EXTENDS `sale`. Propagates origin document and CIG/CUP fields to the generated invoice with smart logic:
- If origin document fields are partially filled: pass all fields as-is (avoid mismatches)
- If only CIG/CUP are filled: default origin document type to `purchase_order`, use SO name/date
- Otherwise: inherit normally from `sale`

## Related
- [Modules/l10n_it_edi](Modules/l10n_it_edi.md) — Core Italian SDI/FatturaPA e-invoicing
- [Modules/Sale](Modules/Sale.md) — Base sale order module
- [Modules/l10n_it_edi_doi](Modules/l10n_it_edi_doi.md) — Italian Declaration of Intent (scambi_elenconi)
