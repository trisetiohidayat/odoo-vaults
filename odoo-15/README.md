# Odoo 15 Vault

Documentation vault for Odoo 15.0 codebase research.

**Source:** `/Users/tri-mac/project/roedl/odoo15.0-roedl/odoo/`

## Structure

```
odoo-15/
├── Core/           # ORM fundamentals
├── Patterns/       # Design patterns
├── Tools/          # ORM operations
├── Snippets/       # Code templates
└── Modules/        # Module references
```

## Quick Start

1. [Core/BaseModel](BaseModel.md) — ORM basics
2. [Core/Fields](Fields.md) — Field types
3. [Core/API](API.md) — Decorators
4. [Tools/ORM Operations](ORM Operations.md) — search/browse/create
5. [Modules/Sale](Sale.md) — Sale order
6. [Modules/Stock](Stock.md) — Inventory

## Module Mapping (Keyword → Vault)

| Keyword | File |
|---|---|
| orm/model/base/CRUD | [Core/BaseModel](BaseModel.md) |
| field/char/many2one | [Core/Fields](Fields.md) |
| api/depends/onchange | [Core/API](API.md) |
| controller/http/route | [Core/HTTP Controller](HTTP Controller.md) |
| error/exception/validation | [Core/Exceptions](Exceptions.md) |
| inheritance/_inherit | [Patterns/Inheritance Patterns](Inheritance Patterns.md) |
| workflow/state/action | [Patterns/Workflow Patterns](Workflow Patterns.md) |
| security/acl/groups | [Patterns/Security Patterns](Security Patterns.md) |
| search/browse/domain | [Tools/ORM Operations](ORM Operations.md) |
| snippets/template | [Snippets/Model Snippets](Model Snippets.md) |
| sale/quotation/so | [Modules/Sale](Sale.md) |
| stock/picking/quant | [Modules/Stock](Stock.md) |
| account/invoice/journal | [Modules/Account](Account.md) |
| purchase/po/rfq | [Modules/Purchase](Purchase.md) |
| crm/lead/opportunity | [Modules/CRM](CRM.md) |
| project/task/milestone | [Modules/Project](Project.md) |
| mrp/production/bom | [Modules/MRP](MRP.md) |
| product/pricelist/uom | [Modules/Product](Product.md) |
| partner/contact/bank | [Modules/res.partner](res.partner.md) |

## Core ORM Paths

```
Source: /Users/tri-mac/project/roedl/odoo15.0-roedl/odoo/odoo/
├── models.py      # BaseModel, Model, TransientModel, MetaModel
├── fields.py      # All field types
├── api.py         # Decorators (@api.model, @api.depends, etc.)
├── exceptions.py  # ValidationError, UserError, AccessError
└── http.py        # Web controllers
```

## Module Paths

```
Source: /Users/tri-mac/project/roedl/odoo15.0-roedl/odoo/addons/
├── sale/models/sale_order.py        # SaleOrder, SaleOrderLine
├── stock/models/stock_picking.py    # StockPicking, PickingType
├── account/models/account_move.py   # AccountMove
├── purchase/models/purchase.py      # PurchaseOrder
├── crm/models/crm_lead.py           # CrmLead
├── project/models/project.py        # Project, Task
├── mrp/models/mrp_production.py     # MrpProduction
├── product/models/product_template.py  # ProductTemplate
└── [base]/res_partner.py           # Partner
```# Update Mon Apr 13 14:23:17 WIB 2026
# Fix Mon Apr 13 15:04:55 WIB 2026
# Fix Mon Apr 13 15:12:56 WIB 2026
