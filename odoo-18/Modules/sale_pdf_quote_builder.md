---
Module: sale_pdf_quote_builder
Version: 18.0
Type: addon
Tags: #sale #pdf #quote #document-builder
---

# sale_pdf_quote_builder — PDF Quote Builder with Headers, Footers & Form Fields

**Summary:** Build customized sales quotations by embedding PDF headers, footers, and product documents with dynamic/form field filling.

**Depends:** `sale_management`
**Auto-install:** True
**License:** LGPL-3
**Source:** `~/odoo/odoo18/odoo/addons/sale_pdf_quote_builder/`

## Overview

`sale_pdf_quote_builder` enables rich PDF quotation customization:
1. Attach PDF headers and footers to sale order templates or individual orders
2. Attach product PDFs (e.g., spec sheets) inside the quote between header and order table
3. Fill PDF AcroForm fields dynamically from sale order/line data or custom user input
4. Render configured matrices (from `product_matrix`) in the PDF report

Uses PyPDF4 (`PdfFileWriter`/`PdfFileReader`) to merge and fill forms server-side.

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/ir_actions_report.py` | `ir.actions.report` | PDF merge into QWeb report |
| `models/quotation_document.py` | `quotation.document` (new model inheriting `ir.attachment`) | PDF document model |
| `models/product_document.py` | `product.document` | `inside` attachment mode, form field linking |
| `models/sale_order.py` | `sale.order` | Available PDF docs, form fields, save/update params |
| `models/sale_order_line.py` | `sale.order.line` | Product PDF docs for line-level attachment |
| `models/sale_order_template.py` | `sale.order.template` | PDF doc attachment to templates |
| `models/sale_pdf_form_field.py` | `sale.pdf.form.field` (new model) | Form field definitions for dynamic data |

**Controller:**
- `controllers/quotation_document.py` — `POST /sale_pdf_quote_builder/quotation_document/upload`

---

## Models

### `quotation.document` — `QuotationDocument`

**File:** `models/quotation_document.py` (lines 10–72)
**Inherits:** `ir.attachment` via `_inherits`

```python
class QuotationDocument(models.Model):
    _name = 'quotation.document'
    _inherits = {'ir.attachment': 'ir_attachment_id'}
```

| Field | Type | Notes |
|-------|------|-------|
| `ir_attachment_id` | Many2one → `ir.attachment` | Required; cascade delete |
| `document_type` | Selection | `header` or `footer`; default `header` |
| `active` | Boolean | Allows hiding without deleting; default True |
| `sequence` | Integer | Display ordering; default 10 |
| `quotation_template_ids` | Many2many → `sale.order.template` | Templates this doc applies to |
| `form_field_ids` | Many2many → `sale.pdf.form.field` (computed) | Form fields parsed from PDF |

**Key Methods:**

- `_check_pdf_validity()` (line 33) — `@api.constrains('datas')` — Only PDF files allowed; checks not encrypted via `utils._ensure_document_not_encrypted()`.
- `_compute_form_field_ids()` (line 43) — Clears existing links, calls `_create_or_update_form_fields_on_pdf_records()` to parse form fields from PDF binary data.
- `action_open_pdf_form_fields()` (line 53) — Opens `sale.pdf.form.field` list filtered to this document.
- `@model_create_multi` `create()` (line 63) — Sets `res_model='quotation.document'` and `res_id=doc.id` on the underlying attachment.

---

### `sale.pdf.form.field` — `SalePdfFormField`

**File:** `models/sale_pdf_form_field.py` (lines 10–140)

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char (readonly, required) | Field name as written in the PDF |
| `document_type` | Selection (readonly) | `quotation_document` or `product_document` |
| `path` | Char | Dot-notation path for dynamic filling (e.g., `partner_id.name`); empty = custom input |
| `product_document_ids` | Many2many → `product.document` | Links field to specific product documents |
| `quotation_document_ids` | Many2many → `quotation.document` | Links field to specific quotation documents |

**SQL Constraints:**
- `unique_name_per_doc_type` — Field name unique per document type.

**Key Methods:**

- `_check_form_field_name_follows_pattern()` (line 35) — `@api.constrains('name')` — Names must match `^(\w|-)+$`; header/footer names cannot start with `sol_id_`.
- `_check_valid_and_existing_paths()` (line 47) — `@api.constrains('path')` — Validates path exists on `sale.order` (header/footer) or `sale.order.line` (product document).
- `_check_document_type_and_document_linked_compatibility()` (line 69) — Prevents cross-linking between doc types.
- `_add_basic_mapped_form_fields()` (line 80) — Creates default mapped fields: quotation (`amount_total`, `partner_id__name`, `user_id__email`, etc.) and product (`description`, `discount`, `price_unit`, `tax_incl_price`, etc.).
- `_cron_post_upgrade_assign_missing_form_fields()` (line 110) — Post-upgrade cron to scan PDFs and create missing form field records.
- `_create_or_update_form_fields_on_pdf_records(records, doc_type)` (line 119) — Reads PDF binary, parses AcroForm field names via `utils._get_form_fields_from_pdf()`, creates or links `sale.pdf.form.field` records.

---

### `sale.order`

**File:** `models/sale_order.py` (lines 10–135)

| Field | Type | Notes |
|-------|------|-------|
| `available_product_document_ids` | Many2many → `quotation.document` (computed) | Headers/footers available for the order based on template |
| `is_pdf_quote_builder_available` | Boolean (computed) | True if any available header/footer or product document |
| `quotation_document_ids` | Many2many → `quotation.document` | Selected headers and footers for this order |
| `customizable_pdf_form_fields` | Json | Custom (non-dynamic) form field values per document/line |

**Key Methods:**

- `_compute_available_product_document_ids()` (line 23) — Union of template-matched and order-specific documents.
- `_compute_is_pdf_quote_builder_available()` (line 31) — Checks for any available header/footer/product documents.
- `_onchange_sale_order_template_id()` (line 38) — Clears documents no longer available for the new template.
- `get_update_included_pdf_params()` (line 45) — Returns dialog parameters for frontend PDF configuration: headers, footers, per-line product documents with custom form field values.
- `save_included_pdf(selected_pdf)` (line 105) — Writes selected header/footer and product document IDs.
- `save_new_custom_content(document_type, form_field, content)` (line 125) — Persists custom form field values into the Json mapping.

---

### `sale.order.line`

**File:** `models/sale_order_line.py` (lines 10–42)

| Field | Type | Notes |
|-------|------|-------|
| `available_product_document_ids` | Many2many → `product.document` (computed, sudo) | Product docs with `attached_on_sale='inside'` for this line's product |
| `product_document_ids` | Many2many → `product.document` | Selected product documents to include in PDF |

**Key Methods:**

- `_onchange_product()` (line 25) — Prunes selected documents that are no longer available when product changes.
- `_compute_available_product_document_ids()` (line 30) — Uses `_read_group` for efficient computation.

---

### `sale.order.template`

**File:** `models/sale_order_template.py`

| Field | Type | Notes |
|-------|------|-------|
| `quotation_document_ids` | Many2many → `quotation.document` | Default headers/footers for orders using this template |

---

### `product.document`

**File:** `models/product_document.py` (lines 10–62)

| Field | Type | Notes |
|-------|------|-------|
| `attached_on_sale` | Selection | Added `inside` option — PDF included in quote between header and order table |
| `form_field_ids` | Many2many → `sale.pdf.form.field` (computed) | Form fields parsed from the PDF |

**Key Methods:**

- `_check_attached_on_and_datas_compatibility()` (line 22) — `@api.constrains` — `attached_on_sale='inside'` requires `type='binary'`, a PDF file, and no encryption.
- `_compute_form_field_ids()` (line 39) — Parses PDF form fields when `attached_on_sale='inside'` and PDF data is set.
- `action_open_pdf_form_fields()` (line 52) — Opens form fields list filtered to this product document.

---

### `ir.actions.report`

**File:** `models/ir_actions_report.py` (lines 10–220)

Overrides `_render_qweb_pdf_prepare_streams()` to intercept PDF generation for `sale.report_saleorder`.

**Key Methods:**

- `_render_qweb_pdf_prepare_streams()` (line 17) — Entry point. For `sale.report_saleorder`, fetches headers, footers, product documents. Uses `PdfFileWriter` to prepend headers, insert product docs between header and order table, append footers. Calls `fill_form_fields_pdf()` with mapped values.
- `_update_mapping_and_add_pages_to_writer()` (line 80) — Parses document form fields, resolves values (dynamic via `_get_value_from_path` or custom via `_get_custom_value_from_order`), and adds PDF pages to writer with prefixed field names.
- `_get_value_from_path(form_field, order, order_line=None)` (line 116) — Follows dot-notation path from `order` or `order_line`, formats by type: `boolean`→Yes/No, `monetary`→formatted amount, `date`/`datetime`→localized, `selection`→label, relational→display names. Multiple values joined with `, `.
- `_get_custom_value_from_order()` (line 166) — Reads from `order.customizable_pdf_form_fields` Json for user-entered custom values.
- `_add_pages_to_writer()` (line 185) — Reads PDF, prefixes all form field names with document ID, sets read-only and multiline flags, adds pages to writer.

---

## Controller

### `QuotationDocumentController`

**File:** `controllers/quotation_document.py` (lines 10–50)

**Endpoint:** `POST /sale_pdf_quote_builder/quotation_document/upload`

- Accepts multipart file upload (`ufile`)
- Optionally scoped to `sale_order_template_id`
- Creates `quotation.document` records with uploaded binary data
- Validates PDF not encrypted via `utils._ensure_document_not_encrypted()`
- Returns JSON `{success: _}` or `{error: str(e)}`

---

## Data Files

| File | Purpose |
|------|---------|
| `data/ir_cron.xml` | Scheduled action for post-upgrade form field parsing |
| `data/sale_pdf_form_field.xml` | Creates default mapped form fields |
| `data/sale_pdf_quote_builder_demo.xml` | Demo data |
| `report/ir_actions_report.xml` | Report action for quotation PDF |
| `security/ir.model.access.csv` | Access rights for new models |
| `security/ir_rules.xml` | Record rules |
| `views/*.xml` | Form/list views for all new models |
| `wizards/res_config_settings_views.xml` | Settings |

---

## PDF Rendering Pipeline

```
sale.order report triggered (sale.report_saleorder)
    ↓
ir.actions.report._render_qweb_pdf_prepare_streams
    ↓
Fetch quotation_document_ids (headers + footers)
Fetch product_document_ids per line
    ↓
For each document:
  Parse form fields → update mapping
  Prefix field names with doc ID
  Set read-only + multiline flags
  Add pages to PdfFileWriter
    ↓
Add base quotation pages
    ↓
Fill all form fields (dynamic + custom) via pdf.fill_form_fields_pdf()
    ↓
Output merged PDF with filled forms
```

---

## Default Form Field Paths

**Quotation document (header/footer):**
| Field Name | Path |
|---|---|
| `amount_total` | `amount_total` |
| `amount_untaxed` | `amount_untaxed` |
| `client_order_ref` | `client_order_ref` |
| `delivery_date` | `commitment_date` |
| `order_date` | `date_order` |
| `name` | `name` |
| `partner_id__name` | `partner_id.name` |
| `user_id__email` | `user_id.login` |
| `user_id__name` | `user_id.name` |
| `validity_date` | `validity_date` |

**Product document (per line):**
| Field Name | Path |
|---|---|
| `description` | `name` |
| `discount` | `discount` |
| `price_unit` | `price_unit` |
| `quantity` | `product_uom_qty` |
| `tax_excl_price` | `price_subtotal` |
| `tax_incl_price` | `price_total` |
| `uom` | `product_uom.name` |
| `product_sale_price` | `product_id.lst_price` |
