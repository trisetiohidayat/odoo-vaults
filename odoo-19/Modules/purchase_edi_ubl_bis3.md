---
tags: [odoo, odoo19, modules, purchase, edi, ubl, bis3, peppol, electronic-invoice]
modLevel: L4
module: purchase_edi_ubl_bis3
category: Supply Chain/Purchase
depends: [purchase, account_edi_ubl_cii]
license: LGPL-3
auto_install: true
---

# purchase_edi_ubl_bis3

**Module:** Import/Export electronic orders with UBL
**Version:** 1.0 (Odoo 19)
**Author:** Odoo S.A.
**Category:** Supply Chain/Purchase
**Depends:** `purchase`, `account_edi_ubl_cii`
**License:** LGPL-3
**Auto-install:** True

**Source path:** `~/odoo/odoo19/odoo/addons/purchase_edi_ubl_bis3/`

---

## L1: How BIS3 UBL Invoices Are Processed from Vendors

### Overview

`purchase_edi_ubl_bis3` extends `purchase.order` and `account.edi.xml.ubl_bis3` to enable the **full cycle** of electronic purchase ordering via the UBL BIS 3 (Business Interoperability Settings 3) format — the Peppol network standard for order documents. The module handles both **outbound** (export PO as UBL XML to vendor) and **inbound** (import vendor's UBL response or vendor invoice as a bill, linked to a PO).

The module sits in the dependency chain as follows:

```
purchase.order (purchase module)
    └── purchase_edi_ubl_bis3.models.purchase_order
        ├── _get_edi_builders()     ← adds purchase.edi.xml.ubl_bis3 as builder
        ├── _get_import_file_type() ← identifies UBL BIS 3 order by CustomizationID
        └── _get_edi_decoder()     ← routes import to _import_order_ubl

account.edi.xml.ubl_bis3 (account_edi_ubl_cii)
    └── purchase.edi.xml.ubl_bis3 (abstract model, this module)
        ├── _export_order()         ← generates UBL BIS 3 Order XML
        └── _retrieve_order_vals() ← parses UBL into purchase order fields
```

### Vendor Invoice Import Flow (Bill from UBL)

When a vendor sends a UBL BIS 3 document (a response to an order, or an unsolicited invoice), Odoo processes it through the **attachment-to-document pipeline**:

1. **File type detection** — `purchase.order._get_import_file_type()` inspects the incoming XML's `{*}CustomizationID` element. If it matches `urn:fdc:peppol.eu:poacc:trns:order:3`, the file is tagged as `purchase.edi.xml.ubl_bis3`.

2. **Decoder routing** — `purchase.order._get_edi_decoder()` dispatches to `purchase.edi.xml.ubl_bis3._import_order_ubl()` with priority 20.

3. **Order creation/update** — `_retrieve_order_vals()` (BIS3 override) extracts document-level fields, then extends with:
   - `partner_id` from the `SellerSupplierParty` node (via `_import_partner()`)
   - `dest_address_id` (delivery address) from the `Delivery` node
   - `partner_ref` from the document `{*}ID` element
   - `origin` from `OriginatorDocumentReference/{*}ID` (the original PO reference)
   - `order_line` values reconstructed from `OrderLine/{*}LineItem` nodes
   - Allowance/charge lines from document-level `AllowanceCharge` nodes

4. **Line adaptation** — invoice-style line data (`quantity`) is renamed to `product_qty`. Invoice-specific fields (`deferred_start_date`, `deferred_end_date`) are stripped. Products not matched by name cause a logged warning but still create a description-only line.

5. **Activity logging** — any parsing warnings are logged as mail activities on the purchase order via `_create_activity_set_details()`.

6. **Bill creation** — if the incoming document is a vendor bill, `account.journal._create_document_from_attachment()` creates an `account.move` of type `in_invoice`, linked to the original PO via `invoice_origin` and `line_ids.purchase_order_id`.

### Test Coverage

| Test | Scenario |
|------|----------|
| `TestPurchaseOrderEDIGen.test_purchase_order_download_edi` | Exports confirmed PO as UBL BIS 3 XML; compares against `tests/data/test_po_edi.xml` |
| `TestAccountMoveImport.test_import_purchase_order_reference_from_provided_field` | UBL bill with PO reference in `{*}ID` correctly linked |
| `TestAccountMoveImport.test_import_purchase_order_reference_from_lines_description` | UBL bill with PO reference in line description |
| `TestAccountMoveImport.test_multiple_purchase_order_references` | `invoice_origin` containing multiple refs; first match wins |

---

## L2: Field Types, Defaults, Constraints

### Models

#### Abstract Model: `purchase.edi.xml.ubl_bis3`

```python
class PurchaseEdiXmlUbl_Bis3(models.AbstractModel):
    _name = 'purchase.edi.xml.ubl_bis3'
    _inherit = ['account.edi.xml.ubl_bis3']
    _description = "Purchase UBL BIS Ordering 3.5"
```

This is an **abstract** model — no persistent records. All logic is in-memory method overrides.

#### Extension: `purchase.order`

No new database fields are added to `purchase.order`. The extension contributes three method overrides and one new method:

```python
class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _get_edi_builders(self):
        """Append purchase.edi.xml.ubl_bis3 to parent builders."""

    def _get_import_file_type(self, file_data):
        """Detect UBL BIS 3 by CustomizationID == 'urn:fdc:peppol.eu:poacc:trns:order:3'."""

    def _get_edi_decoder(self, file_data, new=False):
        """Route to _import_order_ubl with priority 20."""

    def _create_activity_set_details(self, body):
        """Create mail.activity on PO with import warnings."""

    @api.model
    def _get_line_vals_list(self, lines_vals):
        """Adapt [(name, qty, price, tax_ids)] tuples into purchase.order.line command dicts."""
```

### Configuration Defaults (via __manifest__.py)

| Setting | Value | Effect |
|---------|-------|--------|
| `auto_install: True` | Installed automatically when dependencies are present | Enables EDI for POs without manual activation |
| `depends: ['purchase', 'account_edi_ubl_cii']` | Hard dependency chain | Ensures purchase and UBL base are present before this module |

### UBL BIS 3 Order Document Constants

| Constant | XML value | Purpose |
|----------|-----------|---------|
| `CustomizationID` | `urn:fdc:peppol.eu:poacc:trns:order:3` | Peppol Ordering 3.0 spec identifier (used for import detection too) |
| `ProfileID` | `urn:fdc:peppol.eu:poacc:bis:ordering:3` | Peppol BIS Ordering profile |
| `OrderTypeCode` | `105` | UN/ECE rec. 1001 code for Order |
| `Note` | `html2plaintext(purchase_order.note)` | PO internal note as document-level note |
| `DocumentCurrencyCode` | `vals['currency_name']` | Order currency (not company currency) |
| `QuotationDocumentReference/ID` | `purchase_order.partner_ref` | Vendor's reference on our PO |
| `OriginatorDocumentReference/ID` | `purchase_order.origin` | Original RFQ / quotation reference |
| Line sequence start | `0` then `1, 2, 3...` | Allowance lines at 0; real lines at incrementing index |

### Internal vals Dict (Export Pipeline)

During export, a `vals` dict is built and threaded through all `_add_purchase_order_*` methods:

| Key | Type | Description |
|-----|------|-------------|
| `purchase_order` | `purchase.order` recordset | Source PO |
| `document_type` | `str` | Always `'order'` |
| `supplier` | `res.partner` | `purchase_order.partner_id` |
| `customer` | `res.partner` | `purchase_order.company_id.partner_id.commercial_partner_id` |
| `partner_shipping` | `res.partner` | Delivery address (contact of type `delivery`, or commercial partner) |
| `currency_id` | `res.currency` | `purchase_order.currency_id` |
| `company_currency_id` | `res.currency` | `purchase_order.company_id.currency_id` |
| `use_company_currency` | `bool` | Always `False` — amounts in order currency |
| `fixed_taxes_as_allowance_charges` | `bool` | Always `True` — fixed taxes rendered as AllowanceCharge nodes |
| `base_lines` | `list[dict]` | Base lines with tax details + `supplier_info` from `variant_seller_ids` |
| `_ubl_values` | `dict` | Populated by `_add_document_monetary_total_vals()` with aggregated totals |

---

## L3: Cross-Model Integration, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model: Purchase ↔ EDI UBL

```
┌──────────────────────────────────────────────────────────────────┐
│                      purchase.order                               │
│  _get_edi_builders() ───────────► adds purchase.edi.xml.ubl_bis3│
│  _get_import_file_type() ◄──────── returns 'purchase.edi.xml.ubl_bis3'
│  _get_edi_decoder() ◄──────────── dispatch to _import_order_ubl  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ (via account_edi_ubl_cii)
┌────────────────────────────▼─────────────────────────────────────┐
│           purchase.edi.xml.ubl_bis3 (abstract)                   │
│  _export_order() ──────────────► etree.tostring (UBL XML bytes)  │
│  _retrieve_order_vals() ───────► order_vals dict + logs          │
│  _setup_base_lines() ─────────── adds supplier_info to base_line  │
│  _add_purchase_order_*() ────── build XML node tree              │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│           account.edi.xml.ubl_bis3 (inherited, account_edi_ubl_cii)│
│  _get_party_node()          Party address/contact rendering      │
│  _import_partner()           Partner matching/creation            │
│  _import_lines()             Line parsing (quantity, price)      │
│  _import_currency()          Currency detection                  │
│  _add_document_monetary_total_vals()  Totals aggregation         │
│  _ubl_add_line_item_node()   Item description/name/code nodes     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                        account.move                               │
│  (inbound) Vendor bills created from UBL via                      │
│  account.journal._create_document_from_attachment()              │
│  Linked to purchase.order via invoice_origin + line_ids.purchase_order_id │
└──────────────────────────────────────────────────────────────────┘
```

### Override Pattern

The module uses a **parallel-method override pattern** — every `_add_purchase_order_*` method replaces its invoice counterpart entirely, while using `super()` for sub-tasks that are shared (e.g., `_ubl_add_line_item_node`):

| Method | Pattern | Reason |
|--------|---------|--------|
| `_add_purchase_order_config_vals()` | `EXTENDS` (sets purchase-specific vals) | Parent doesn't have purchase config; new method |
| `_setup_base_lines()` | `EXTENDS` via `super()` then custom logic | Parent has base tax computation; we add `supplier_info` |
| `_add_purchase_order_line_id_nodes()` | `EXTENDS` (delegates to parent) | ID node structure is shared |
| `_add_purchase_order_allowance_charge_nodes()` | `OVERRIDE` (no `super()`) | Invoice uses different early-payment logic |
| `_add_purchase_order_tax_total_nodes()` | `OVERRIDE` (no `super()`) | Uses currency-specific tax total nodes |
| `_add_purchase_order_monetary_total_nodes()` | `OVERRIDE` (no `super()`) | Order has `AnticipatedMonetaryTotal` vs Invoice's `LegalMonetaryTotal` |
| `_add_purchase_order_line_amount_nodes()` | `OVERRIDE` (no `super()`) | Order quantity handling differs from invoice |
| `_add_purchase_order_line_item_nodes()` | `OVERRIDE` (no `super()`) | Item node assembled differently for orders |
| `_add_purchase_order_line_price_nodes()` | `OVERRIDE` (no `super()`) | Price node has no allowance reference in orders |
| `_ubl_add_line_item_name_description_nodes()` | `EXTENDS` via `super()` then override `cbc:Name` | Parent adds base name; we replace with supplier product name |
| `_ubl_add_line_item_identification_nodes()` | `EXTENDS` via `super()` then add SellersItemIdentification | Parent adds standard ID; we add supplier code |
| `_retrieve_order_vals()` | `EXTENDS` via `super()` then extends dict | Parent gets date/currency/payment-term; we add partner/delivery/lines |

### Workflow Trigger: Vendor Invoice Import

```
ir.attachment created (mimetype: application/xml)
        │
        ▼
account.journal._create_document_from_attachment(attachment_id)
        │
        ├── identifies journal (default_journal_id or auto-detect)
        ▼
purchase.order._get_import_file_type({'xml_tree': tree, ...})
        │  checks CustomizationID == 'urn:fdc:peppol.eu:poacc:trns:order:3'
        ▼
purchase.order._get_edi_decoder(file_data, new=True)
        │  returns {priority: 20, decoder: purchase.edi.xml.ubl_bis3._import_order_ubl}
        ▼
purchase.edi.xml.ubl_bis3._import_order_ubl(order, file_data, new)
        │  (creates or updates purchase.order)
        ▼
account.move created (in_invoice) if bill, else PO updated in place
        │
        ▼
account.move._link_bill_origin_to_purchase_orders()
        │  matches invoice_origin string against PO.name
        ▼
purchase.order.line_ids updated with purchase_order_id
```

The trigger is **non-destructive** for order responses: if the UBL document is an order acknowledgment, it updates the existing `purchase.order` in place. If it is a vendor bill, a new `account.move` is created and linked.

### Failure Modes

| Failure | Symptom | Root Cause | Handling |
|---------|---------|------------|----------|
| **Product not found on import** | Mail activity on PO with warning | Supplier's UBL product description does not match any `product.product` record by name/SKU | Logged via `_create_activity_set_details()`. Line created with description only, `product_id` unset. |
| **Currency mismatch** | Silent zero amounts or `ValidationError` | `DocumentCurrencyCode` in UBL does not match any active `res.currency` | `_import_currency()` returns `(None, logs)`; logs as warning |
| **Partner not found** | Vendor not set on PO | No `res.partner` matches the UBL party's VAT or name | `_import_partner()` creates a new partner or returns `(False, logs)` |
| **XML namespace mismatch** | File type not detected; falls through to another decoder | UBL with non-standard namespace, `CustomizationID` not found | Falls through to `super()._get_import_file_type()` |
| **Allowance line with no tax** | Tax total mismatch | Fixed tax not mapping to any `account.tax` | Lines still created via `Command.create()`, logged |
| **Wrong company context** | EDI format not available | `new=True` from journal carries wrong company | EDI decoder respects journal's company; wrong journal → wrong company |
| **Importing non-order UBL (e.g., invoice response)** | Document type code mismatch | If vendor sends invoice instead of order response, `_retrieve_order_vals` processes it as an order | The `_import_order_ubl` method handles invoice documents via the same pipeline; the journal type determines whether `account.move` or `purchase.order` is created |

---

## L4: Version Changes Odoo 18 → 19, Security

### Odoo 18 → Odoo 19 Changes

| Aspect | Odoo 18 | Odoo 19 | Impact |
|--------|---------|---------|--------|
| **Module structure** | `purchase_edi_ubl` bundled UBL 2.1 + BIS3 | Split into `purchase_edi_ubl_bis3` + `account_edi_ubl_cii` | Odoo 19 restructured EDI into format-specific auto-installable modules. BIS3 is now cleanly separated. |
| **Abstract model name** | `purchase.ubl` or `purchase.edi.ubl` (informal) | Standardized as `purchase.edi.xml.ubl_bis3` | Consistent with `account.edi.xml.ubl_bis3` naming scheme |
| **`auto_install`** | Not present | `True` | BIS3 EDI is automatically enabled when `purchase` and `account_edi_ubl_cii` are present |
| **Test organization** | Inline XML strings | Separate `tests/data/` and `tests/test_files/` directories | Cleaner separation of fixtures from test code |
| **`Command` vs `(0,0,)` tuples** | Both supported | `Command.create()`, `Command.set()` preferred | `purchase_order.py` uses `Command.set()` for tax IDs |
| **`html2plaintext` import** | `openerp.tools` | `odoo.tools` | Import path updated |
| **PEP 8 naming consistency** | Mixed (`PurchaseEdiXmlUbl_Bis3`) | Unchanged | Class name unchanged; follows Odoo convention for EDI format models |
| **`_retrieve_order_vals` extension** | Simple parent call + dict extension | Same pattern | Behavior stable |

### Security Analysis

| Area | Risk | Assessment | Notes |
|------|------|-----------|-------|
| **XML parsing (XXE)** | Low | External entity expansion is disabled by default in `lxml.etree`. `dict_to_xml` does not enable DTD loading. | Safe for untrusted XML input. |
| **Import file type bypass** | Low | A malformed UBL file with matching `CustomizationID` but wrong structure routes to BIS3 decoder, where structural failures may produce silent errors or logged warnings — not code execution. | No arbitrary code execution risk. |
| **Supplier info in export** | Data integrity | `variant_seller_ids` filtered by partner. A user with write access could add misleading product codes — this is a data integrity concern, not a security vulnerability. | Informational warning; not a security issue. |
| **Activity logging** | Low | `_create_activity_set_details()` constructs mail.activity note from XML-parsed text. The `body` argument is HTML-escaped by the mail system. | Safe from XSS in activity notes. |
| **ACL / Access Rights** | N/A | Abstract model has no persisted records. `purchase.order` ACL governed by `purchase` module. | No additional attack surface. |
| **Multi-company** | Safe | Record rules on `purchase.order` prevent cross-company reads. EDI decoder runs in journal's company context. | Proper isolation maintained. |
| **Attachment mimetype** | Low | Only `application/xml` or XML-like mimetypes reach the import pipeline. Other file types are filtered upstream by `_create_document_from_attachment`. | Safe. |

### Data Integrity: Supplier Product Identification

The `_setup_base_lines()` method attaches `supplier_info` (the `product.supplierinfo` record matching the vendor) to each `base_line` dict. This enables:

- **Supplier product name** (`supplier_info.product_name`) → `cbc:Name` in Item node (overrides standard product name)
- **Supplier product code** (`supplier_info.product_code`) → `cac:SellersItemIdentification/cbc:ID`

This is the key differentiator from invoice export: purchase order export includes the vendor's own product identification, critical for Peppol compliance and vendor ERP integration. The filter requires `s.product_code or s.product_name` to be truthy — lines without supplier product info fall back to standard product identification.

### Persistence Behavior

| Operation | Behavior |
|-----------|----------|
| `purchase.edi.xml.ubl_bis3` (abstract) | No persistent records. All computation in-memory during export/import. |
| `purchase.order._get_edi_builders()` | Extends parent result in-memory. No stored changes. |
| `purchase.order._get_edi_decoder()` | Returns a dict with a method reference. No persistence. |
| UBL file import | Creates or updates `purchase.order` records (persisted). Vendor bills create `account.move` records. |
| Test fixtures | `tests/data/test_po_edi.xml` and `tests/test_files/ubl_bis3_PO*.xml` are static XML fixtures for comparison tests — not runtime data. |

---

## Module File Map

```
purchase_edi_ubl_bis3/
├── __init__.py
├── __manifest__.py              # auto_install=True, depends: purchase, account_edi_ubl_cii
├── models/
│   ├── __init__.py
│   ├── purchase_edi_xml_ubl_bis3.py   # Abstract EDI processor — export + import
│   │                                        # Key methods: _export_order, _get_purchase_order_node,
│   │                                        # _setup_base_lines, _retrieve_order_vals,
│   │                                        # _add_purchase_order_* (14 node builders)
│   └── purchase_order.py                   # PO extensions: _get_edi_builders,
│                                            #   _get_import_file_type, _get_edi_decoder,
│                                            #   _create_activity_set_details, _get_line_vals_list
├── tests/
│   ├── __init__.py
│   ├── test_purchase_order_edi_gen.py  # Export: PO → UBL BIS 3 XML (compares to fixture)
│   ├── test_account_move_import.py     # Import: UBL → bill + PO linking
│   ├── data/
│   │   └── test_po_edi.xml              # Expected XML output (date placeholder replaced at runtime)
│   └── test_files/
│       ├── ubl_bis3_PO.xml             # PO ref in {*}ID field
│       └── ubl_bis3_PO_description.xml # PO ref in line Item/Description
└── i18n/                              # Translation files (pot/po/mo)
```

## See Also

- [Modules/account_edi_ubl_cii](odoo-18/Modules/account_edi_ubl_cii.md) — Base UBL BIS 3 implementation (invoices and orders)
- [Modules/purchase](odoo-18/Modules/purchase.md) — Purchase order model
- [Modules/account_peppol](odoo-17/Modules/account_peppol.md) — Peppol network integration (uses account_edi_proxy_client)
- [Modules/account_edi_proxy_client](odoo-18/Modules/account_edi_proxy_client.md) — EDI proxy infrastructure
- [Peppol Ordering 3.0 Specification](https://docs.peppol.eu/poacc/bis/order-3/)
- [UBL 2.1 Order Template](https://github.com/OpenPEPPOL/peppol-bis-invoice-3/tree/master/guidelines/bis-order)

---

**Related Tags:** #purchase #edi #ubl #bis3 #peppol #electronic-invoice #xml #l4
