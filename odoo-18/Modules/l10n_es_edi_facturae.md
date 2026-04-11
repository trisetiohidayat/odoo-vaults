---
Module: l10n_es_edi_facturae
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #spain #facturae
---

# l10n_es_edi_facturae

## Overview
Generates and imports **Facturae** XML files, Spain's official electronic invoice format for submission to government administrations. Supports Facturae version **3.2.2**. Enables both export (outgoing invoices) and import (vendor bills) of signed Facturae documents. Full XAdES digital signature using company certificates.

## EDI Format / Standard
**Facturae 3.2.2** — Spanish Ministry of Finance electronic invoice format. XML-based, signed with XAdES-BES. Governed by `facturae.es` namespace. Mandatory for invoices to Public Sector and increasingly used in B2B.

## Dependencies
- `certificate` — for digital signing
- `l10n_es` — Spanish chart of accounts base
- Auto-installs when `l10n_es` is present

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountChartTemplate` | `account.chart.template` | `account.chart.template` | Loads es_common tax templates for Facturae |
| `AccountMove` | `account.move` | `account.move` | Core export/import; adds `l10n_es_edi_facturae_xml_file` binary, reason codes, payment means |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | EDI send wizard integration |
| `AccountTax` | `account.tax` | `account.tax` | Tax-level Facturae export configuration |
| `Certificate` | `certificate.certificate` | `certificate.certificate` | Company certificate for signing |
| `Company` | `res.company` | `res.company` | Certificate associations, administrative centers |
| `AcRoleType` | `l10n_es_edi_facturae.ac_role_type` | `base` | Partner administrative center role types |
| `Partner` | `res.partner` | `res.partner` | Administrative center fields for Facturae parties |
| `UoM` | `uom.uom` | `uom.uom` | UoM mapping to Facturae codes |

## Data Files
- `data/uom.uom.csv` — Unit of Measure codes for Facturae
- `data/facturae_templates.xml` — QWeb invoice template
- `data/l10n_es_edi_facturae.ac_role_type.csv` — Role type definitions
- `data/signature_templates.xml` — XAdES-BES signature template

## How It Works

### Export
1. Invoice is validated: company and partner must have VAT, country set
2. `AccountMove._l10n_es_edi_facturae_export_facturae()` builds the XML dictionary
3. Tax grouping produces `TaxOutputs` and `TaxesWithheld` nodes
4. Administrative centers extracted from partner's `facturae_ac` child contacts
5. Payment installments computed from payment terms
6. `AccountMove._l10n_es_facturae_sign_xml()` applies XAdES-BES signature using company certificate
7. Result stored in `l10n_es_edi_facturae_xml_file` binary field (detached attachment)

### Import
- `AccountMove._get_edi_decoder()` detects Facturae XML via namespace
- `AccountMove._import_invoice_facturae()` parses: partner extraction, currency, dates, invoice lines
- Tax matching by rate and amount type (percent vs fixed), price_include consideration
- Multiple invoices in a single Facturae batch are split into separate moves

### Signature
Uses RSA certificate with SHA-256. Signature template includes:
- `ds:SignedInfo` with XAdES-BES policy (`http://www.facturae.es/...`)
- Public key modulus/exponent from DER certificate
- `SignatureValue` computed via `certificate._sign(canonicalize_node(signed_info))`

## Installation
Standard Odoo module installation. Post-init hook `_l10n_es_edi_facturae_post_init_hook` loads CSV UoM mappings. Demo data available in `demo/l10n_es_edi_facturae_demo.xml`.

## Historical Notes
- **Odoo 17**: Initial Facturae support; signature used older XML libraries
- **Odoo 18**: Cleaner XAdES template rendering via QWeb; improved tax rounding (6 decimal places for round_globally); import now handles multiple invoices per file; import uses `ir.qweb` XML cleanup; corrective refunds properly handle partial reconciliation