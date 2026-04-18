---
title: "Sale Pdf Quote Builder"
module: sale_pdf_quote_builder
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Sale Pdf Quote Builder

## Overview

Module `sale_pdf_quote_builder` — auto-generated from source code.

**Source:** `addons/sale_pdf_quote_builder/`
**Models:** 7
**Fields:** 23
**Methods:** 4

## Models

### ir.actions.report (`ir.actions.report`)

Override to add and fill headers, footers and product documents to the sale quotation.

**File:** `ir_actions_report.py` | Class: `IrActionsReport`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `writer` | `PdfFileWriter` | — | — | — | — | — |
| `reader` | `PdfFileReader` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.pdf.form.field (`sale.pdf.form.field`)

—

**File:** `product_document.py` | Class: `ProductDocument`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `attached_on_sale` | `Selection` | — | — | — | — | — |
| `form_field_ids` | `Many2many` | Y | — | — | Y | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_open_pdf_form_fields` | |


### quotation.document (`quotation.document`)

—

**File:** `quotation_document.py` | Class: `QuotationDocument`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `ir_attachment_id` | `Many2one` | — | — | — | — | Y |
| `document_type` | `Selection` | — | — | — | — | Y |
| `active` | `Boolean` | — | — | — | — | — |
| `sequence` | `Integer` | — | — | — | — | — |
| `quotation_template_ids` | `Many2many` | — | — | — | — | — |
| `form_field_ids` | `Many2many` | Y | — | — | Y | — |
| `add_by_default` | `Boolean` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_open_pdf_form_fields` | |
| `create` | |


### quotation.document (`quotation.document`)

—

**File:** `sale_order.py` | Class: `SaleOrder`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `available_quotation_document_ids` | `Many2many` | Y | — | — | — | — |
| `is_pdf_quote_builder_available` | `Boolean` | Y | — | — | — | — |
| `quotation_document_ids` | `Many2many` | — | — | — | — | — |
| `customizable_pdf_form_fields` | `Json` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `get_update_included_pdf_params` | |


### product.document (`product.document`)

—

**File:** `sale_order_line.py` | Class: `SaleOrderLine`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `available_product_document_ids` | `Many2many` | Y | — | — | — | — |
| `product_document_ids` | `Many2many` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### quotation.document (`quotation.document`)

—

**File:** `sale_order_template.py` | Class: `SaleOrderTemplate`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `quotation_document_ids` | `Many2many` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.pdf.form.field (`sale.pdf.form.field`)

Ensure the names only contains alphanumerics, hyphens and underscores.

        :return: None
        :raises: ValidationError if the names aren't alphanumerics, hyphens and underscores.

**File:** `sale_pdf_form_field.py` | Class: `SalePdfFormField`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `name` | `Char` | — | — | — | — | Y |
| `document_type` | `Selection` | — | — | — | — | Y |
| `path` | `Char` | — | — | — | — | — |
| `product_document_ids` | `Many2many` | — | — | — | — | — |
| `quotation_document_ids` | `Many2many` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/Sale]]
