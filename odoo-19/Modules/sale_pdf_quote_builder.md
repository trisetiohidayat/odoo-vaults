# Sale PDF Quote Builder

## Overview
- **Name:** Sales PDF Quotation Builder
- **Category:** Sales/Sales
- **Depends:** `sale_management`
- **Auto-install:** Yes
- **License:** LGPL-3

## Description
Allows building professional quotations by attaching PDF headers, footers, and product documents (e.g. spec sheets) directly into the quotation PDF. Supports **fillable PDF form fields** — dynamic values from the SO/SOL can be auto-filled into form fields in the attached PDFs.

## Models

### `quotation.document`
Inherits from `ir.attachment`. Represents a reusable header or footer PDF.

| Field | Type | Description |
|-------|------|-------------|
| `ir_attachment_id` | Many2one | Inherited ir.attachment |
| `document_type` | Selection | `"header"` or `"footer"` |
| `quotation_template_ids` | Many2many | Restrict to specific SO templates (or all if empty) |
| `form_field_ids` | Many2many | Auto-computed form fields found in the PDF |
| `add_by_default` | Boolean | Auto-add to new SOs |
| `sequence` | Integer | Display order |

Constraints:
- `_check_pdf_validity()`: Only PDF files allowed; encrypted PDFs rejected.
- `_compute_form_field_ids()`: On `datas` change, parses the PDF for form fields and creates `sale.pdf.form.field` records.

### `product.document` (extends `product.document`)
| Field | Type | Description |
|-------|------|-------------|
| `attached_on_sale` | Selection | Added `"inside"` option — include document inside the quote PDF between header and order lines |
| `form_field_ids` | Many2many | Auto-computed form fields for product PDFs |

Constraints:
- `_check_attached_on_and_datas_compatibility()`: `inside` requires `type=binary` and PDF format.

### `sale.pdf.form.field`
Tracks named form fields discovered in PDF documents and maps them to SO/SOL field paths.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Field name as written in the PDF |
| `document_type` | Selection | `"quotation_document"` or `"product_document"` |
| `path` | Char | Dot-path to SO/SOL field for auto-fill (e.g. `partner_id.name`); empty = custom/user-defined field |
| `product_document_ids` / `quotation_document_ids` | Many2many | Linked documents |

Key methods:
- `_check_form_field_name_follows_pattern()`: Alphanumeric/hyphen/underscore only; cannot start with `sol_id_`.
- `_check_valid_and_existing_paths()`: Validates that the dot-path exists on `sale.order` or `sale.order.line`.
- `_add_basic_mapped_form_fields()`: Seeds default mappings (amount_total, partner_id__name, etc.).
- `_create_or_update_form_fields_on_pdf_records()`: Parses PDFs for form fields and creates/links records.

### `sale.order.template` (extends `sale.order.template`)
| Field | Type | Description |
|-------|------|-------------|
| `quotation_document_ids` | Many2many | Headers/footers to auto-apply for this template |

### `sale.order` (extends `sale.order`)
| Field | Type | Description |
|-------|------|-------------|
| `quotation_document_ids` | Many2many | Selected header/footer PDFs |
| `available_quotation_document_ids` | Many2many | Computed — documents visible for this SO |
| `is_pdf_quote_builder_available` | Boolean | Computed — any docs or product docs available |
| `customizable_pdf_form_fields` | JSON | Custom form field values entered by user |

Methods:
- `get_update_included_pdf_params()`: Returns dialog params for the PDF builder UI (selected docs, form field values).

### `ir.actions.report` (extends `ir.actions.report`)
Overrides `_render_qweb_pdf_prepare_streams()` to inject headers, product documents, and footers into the SO PDF.

Pipeline for each order:
1. Append header pages to writer.
2. For each SOL with `product_document_ids`, append those PDF pages.
3. Append the standard SO report pages.
4. Append footer pages.
5. Fill form fields using `pdf.fill_form_fields_pdf()`.

Helper methods:
- `_update_mapping_and_add_pages_to_writer()`: Maps form fields to values and adds PDF pages.
- `_get_value_from_path()`: Resolves dot-path on SO/SOL with formatting (date, monetary, boolean, etc.).
- `_get_custom_value_from_order()`: Reads user-entered custom field values from JSON.
- `_add_pages_to_writer()`: Merges PDF pages, prefixes form field names to avoid collisions, sets read-only+multiline flags.

## Data
- `sale_pdf_form_field.xml`: Default form field mappings.
- `sale_pdf_quote_builder_demo.xml`: Demo data.

## Cron
- `ir_cron.xml`: `_cron_post_upgrade_assign_missing_form_fields` — post-upgrade hook to re-parse PDFs and assign form fields.

## Related
- [Modules/sale_management](Modules/sale_management.md) - Sales order templates
- [Modules/Product](Modules/product.md) - Product documents
