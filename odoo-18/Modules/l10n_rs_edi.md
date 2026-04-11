---
Module: l10n_rs_edi
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #serbia #efaktura #ubl
---

# l10n_rs_edi

## Overview
Serbian e-invoicing module integrating with **eFaktura**, Serbia's mandatory electronic invoice system. Serbia mandated B2G (government) e-invoicing since 2022, with B2B mandatory from 2023. This module generates and submits invoices in the Serbian UBL 2.1 eFaktura format via the Serbian fiscal system API.

## EDI Format / Standard
**UBL 2.1 eFaktura RS** — Serbian profile of UBL 2.1 (CEN 16931:2017 compliant). Customization ID: `urn:mfin.gov.rs:srbdt:2022`. Endpoint schemeID `9948` for Serbian parties. Tax period obligations code in invoice period. Public funds identification for government invoices.

## Dependencies
- `account_edi_ubl_cii` — Base UBL/CII framework
- `l10n_rs` — Serbian chart of accounts

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountEdiXmlUBL21RS` | `account.edi.xml.ubl.rs` | `account.edi.xml.ubl_21` | Serbian UBL 2.1: customization_id, endpoint schemeID 9948, billing reference for refunds, tax period obligations code |
| `AccountMove` | `account.move` | `account.move` | Serbian invoice fields: `l10n_rs_tax_date_obligations_code` |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard |
| `ResCompany` | `res.company` | `res.company` | Serbian EDI configuration |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | Partner `l10n_rs_edi_registration_number`, `l10n_rs_edi_public_funds` |

## Data Files
- `views/res_config_settings_views.xml` — Settings form
- `views/account_move.xml` — Invoice form fields
- `views/res_partner_views.xml` — Partner fields

## How It Works

### UBL Customization
Serbian UBL profile adds:
- `customization_id`: `urn:mfin.gov.rs:srbdt:2022` (Serbian fiscal code)
- `endpoint_id` with schemeID `9948` for Serbian TIN
- Numeric country codes (PRS-style) for partner VAT parsing
- Public funds field `JBKJS: {code}` in party identification for government invoices
- Tax date obligations code in invoice period (for different invoice types)

### Credit Note Reference
Refunds include billing reference to original invoice via `billing_reference_vals`: `id` = original invoice name, `issue_date` = original date.

### Partner Identification
Serbian partners: VAT parsed as numeric (without country prefix), endpoint = VAT number, schemeID = 9948. For companies with registration numbers (not VAT), uses `l10n_rs_edi_registration_number`.

## Installation
Auto-installs with `l10n_rs`. Standard module installation.

## Historical Notes
- **Odoo 17**: Serbian e-invoicing not available
- **Odoo 18**: First complete eFaktura integration. Serbia's eFaktura system is based on UBL 2.1 with Serbian-specific extensions.