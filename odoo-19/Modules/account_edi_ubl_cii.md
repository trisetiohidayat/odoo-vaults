---
title: "Account Edi Ubl Cii"
module: account_edi_ubl_cii
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Account Edi Ubl Cii

## Overview

Module `account_edi_ubl_cii` — auto-generated from source code.

**Source:** `addons/account_edi_ubl_cii/`
**Models:** 16
**Fields:** 15
**Methods:** 5

## Models

### account.edi.common (`account.edi.common`)

list of codes: https://docs.peppol.eu/poacc/billing/3.0/codelist/UNECERec20/
        or https://unece.org/fileadmin/DAM/cefact/recommendations/bkup_htm/add2c.htm (sorted by letter)

**File:** `account_edi_common.py` | Class: `AccountEdiCommon`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `body` | `Markup` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `module_installed` | |
| `format_float` | |


### account.edi.ubl (`account.edi.ubl`)

Indicate if the 'tax_data' passed as parameter is a recycling contribution tax.

        :param tax_data:    One of the tax data in base_line['tax_details']['taxes_data'].
        :return:            

**File:** `account_edi_ubl.py` | Class: `AccountEdiUBL`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.cii (`account.edi.xml.cii`)

In factur-x, an invoice has code 380 and a credit note has code 381. However, a credit note can be expressed
        as an invoice with negative amounts. For this case, we need a factor to take the op

**File:** `account_edi_xml_cii_facturx.py` | Class: `AccountEdiXmlCii`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.ubl_20 (`account.edi.xml.ubl_20`)

Returns the `DocumentTypeCode` node tag

**File:** `account_edi_xml_ubl_20.py` | Class: `AccountEdiXmlUBL20`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `format_float` | |


### account.edi.xml.ubl_21 (`account.edi.xml.ubl_21`)

—

**File:** `account_edi_xml_ubl_21.py` | Class: `AccountEdiXmlUbl_21`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.ubl_a_nz (`account.edi.xml.ubl_a_nz`)

* Documentation: https://github.com/A-NZ-PEPPOL/A-NZ-PEPPOL-BIS-3.0/tree/master/Specifications

**File:** `account_edi_xml_ubl_a_nz.py` | Class: `AccountEdiXmlUbl_A_Nz`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.ubl_bis3 (`account.edi.xml.ubl_bis3`)

* Documentation of EHF Billing 3.0: https://anskaffelser.dev/postaward/g3/
    * EHF 2.0 is no longer used:
      https://anskaffelser.dev/postaward/g2/announcement/2019-11-14-removal-old-invoicing-sp

**File:** `account_edi_xml_ubl_bis3.py` | Class: `AccountEdiXmlUbl_Bis3`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.ubl_efff (`account.edi.xml.ubl_efff`)

—

**File:** `account_edi_xml_ubl_efff.py` | Class: `AccountEdiXmlUbl_Efff`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.ubl_nl (`account.edi.xml.ubl_nl`)

SI-UBL 2.0 (NLCIUS) and UBL Bis 3 are 2 different formats used in the Netherlands.
    (source: https://github.com/peppolautoriteit-nl/publications/tree/master/NLCIUS-PEPPOLBIS-Differences)
    NLCIUS

**File:** `account_edi_xml_ubl_nlcius.py` | Class: `AccountEdiXmlUbl_Nl`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.ubl_sg (`account.edi.xml.ubl_sg`)

Documentation: https://www.peppolguide.sg/billing/bis/

**File:** `account_edi_xml_ubl_sg.py` | Class: `AccountEdiXmlUbl_Sg`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.ubl_de (`account.edi.xml.ubl_de`)

—

**File:** `account_edi_xml_ubl_xrechnung.py` | Class: `AccountEdiXmlUbl_De`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### ir.attachment (`ir.attachment`)

Compute the filename based on the uploaded file.

**File:** `account_move.py` | Class: `AccountMove`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `ubl_cii_xml_id` | `Many2one` | Y | — | — | — | — |
| `ubl_cii_xml_file` | `Binary` | Y | — | — | — | — |
| `ubl_cii_xml_filename` | `Char` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_invoice_download_ubl` | |
| `get_extra_print_items` | |


### account.move.send (`account.move.send`)

Include the PDF in the UBL as an AdditionalDocumentReference element.

        According to UBL 2.1 standard, the AdditionalDocumentReference element should be
        placed above ProjectReference wh

**File:** `account_move_send.py` | Class: `AccountMoveSend`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `reader` | `OdooPdfFileReader` | — | — | — | — | — |
| `writer` | `OdooPdfFileWriter` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.tax (`account.tax`)

—

**File:** `account_tax.py` | Class: `AccountTax`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `ubl_cii_tax_category_code` | `Selection` | — | — | — | — | — |
| `ubl_cii_tax_exemption_reason_code` | `Selection` | — | — | — | — | — |
| `ubl_cii_requires_exemption_reason` | `Boolean` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### ir.actions.report (`ir.actions.report`)

—

**File:** `ir_actions_report.py` | Class: `IrActionsReport`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.partner (`res.partner`)

Code used to identify the Endpoint for BIS Billing 3.0 and its derivatives.
             List available at https://docs.peppol.eu/poacc/billing/3.0/codelist/eas/

**File:** `res_partner.py` | Class: `ResPartner`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `invoice_edi_format` | `Selection` | — | — | — | — | — |
| `is_ubl_format` | `Boolean` | Y | — | — | — | — |
| `is_peppol_edi_format` | `Boolean` | Y | — | — | — | — |
| `peppol_endpoint` | `Char` | Y | — | — | Y | — |
| `peppol_eas` | `Selection` | Y | — | — | — | — |
| `available_peppol_eas` | `Json` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Account](Account.md)
