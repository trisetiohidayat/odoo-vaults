---
Module: account_edi_ubl_cii
Version: 18.0
Type: addon
Tags: #account, #edi, #ubl, #cii, #facturx, #xrechnung, #bis3
---

# account_edi_ubl_cii — UBL/CII EDI

Universal module for generating and importing EDI documents in multiple formats: UBL 2.0, UBL 2.1, UBL Bis 3, CII/Factur-X, eFFF (Belgium), NL CIUS, SG UBL, XRechnung, and AU/NZ UBL.

**Depends:** `account`

**Source path:** `~/odoo/odoo18/odoo/addons/account_edi_ubl_cii/`

## Architecture

This is a large format-coverage EDI module. It defines XML generators for each format and hooks into `account.move.send` and `account_move_send` for sending. It also extends `res.partner` with Peppol fields.

## Key Files

- `models/account_edi_common.py` — shared base for EDI generation/import
- `models/account_edi_xml_cii_facturx.py` — Factur-X / CII format
- `models/account_edi_xml_ubl_20.py` — UBL 2.0
- `models/account_edi_xml_ubl_21.py` — UBL 2.1
- `models/account_edi_xml_ubl_bis3.py` — EN 16931 / PEPPOL BIS Billing 3
- `models/account_edi_xml_ubl_a_nz.py` — Australian / New Zealand UBL
- `models/account_edi_xml_ubl_efff.py` — Belgian e-FFF
- `models/account_edi_xml_ubl_nlcius.py` — Dutch CIUS / NL UBL
- `models/account_edi_xml_ubl_sg.py` — Singapore UBL
- `models/account_edi_xml_ubl_xrechnung.py` — German XRechnung (UBL)
- `models/account_move.py` — extends `account.move` for EDI
- `models/account_move_send.py` — extends for send wizard
- `models/ir_actions_report.py` — PDF report generation
- `models/res_partner.py` — Peppol endpoint fields
- `tools/ubl_21_common.py` — shared UBL 2.1 helpers
- `tools/ubl_21_invoice.py` — invoice-specific builders
- `tools/ubl_21_credit_note.py` — credit note builders
- `tools/ubl_21_debit_note.py` — debit note builders
- `tools/ubl_21_order.py` — order/request builders

## Key Extensions

### `AccountMove` — `account.move` (extends)

**File:** `models/account_move.py`

Key additions:
- Peppol fields: `peppol_eas`, `peppol_endpoint`, `peppol_state`
- EDI document number fields for Peppol

### `AccountMoveSend` — `account.move.send` (extends)

**File:** `models/account_move_send.py`

Adds EDI-specific checkboxes and attachment generation for each format.

### `ResPartner` (extends)

**File:** `models/res_partner.py`

Adds Peppol EDI endpoint fields: `peppol_eas` (scheme), `peppol_endpoint` (address).

### `IrActionsReport`

**File:** `models/ir_actions_report.py`

Handles PDF attachment of EDI documents.

## Test Coverage

- `test_ubl_cii.py` — general UBL/CII tests
- `test_ubl_bis3.py` — Bis 3 specific tests
- `test_autopost_bills.py` — automatic posting of bills
- `test_download_docs.py` — document download
- `test_partner_peppol_fields.py` — Peppol field validation

## Format Overview

| Format | File | Country |
|--------|------|---------|
| Factur-X / CII | `account_edi_xml_cii_facturx.py` | France, Germany |
| UBL 2.0 | `account_edi_xml_ubl_20.py` | Generic |
| UBL 2.1 | `account_edi_xml_ubl_21.py` | Generic |
| Bis 3 | `account_edi_xml_ubl_bis3.py` | EU PEPPOL |
| AU/NZ | `account_edi_xml_ubl_a_nz.py` | Australia, NZ |
| eFFF | `account_edi_xml_ubl_efff.py` | Belgium |
| NL CIUS | `account_edi_xml_ubl_nlcius.py` | Netherlands |
| SG UBL | `account_edi_xml_ubl_sg.py` | Singapore |
| XRechnung | `account_edi_xml_ubl_xrechnung.py` | Germany |
