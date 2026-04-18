---
title: "Sale Edi Ubl"
module: sale_edi_ubl
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Sale Edi Ubl

## Overview

Module `sale_edi_ubl` — auto-generated from source code.

**Source:** `addons/sale_edi_ubl/`
**Models:** 3
**Fields:** 0
**Methods:** 0

## Models

### product.product (`product.product`)

Override of `account` to include the variant identifiers in the search order.

        If the product is not found using `*ItemIdentification:ID` elements, tries again with the
        `*ItemIdentific

**File:** `product_product.py` | Class: `ProductProduct`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.edi.xml.ubl_bis3 (`sale.edi.xml.ubl_bis3`)

Fill order details by extracting details from xml tree.
        param order: Order to fill details from xml tree.
        param tree: Xml tree to extract details.
        :return: list of logs to add 

**File:** `sale_edi_xml_ubl_bis3.py` | Class: `SaleEdiXmlUbl_Bis3`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.order (`sale.order`)

Identify UBL files.

**File:** `sale_order.py` | Class: `SaleOrder`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/Sale]]
