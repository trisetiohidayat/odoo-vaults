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

1. [Core/BaseModel](odoo-18/Core/BaseModel.md) — ORM basics
2. [Core/Fields](odoo-18/Core/Fields.md) — Field types
3. [Core/API](odoo-18/Core/API.md) — Decorators
4. [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) — search/browse/create
5. [Modules/Sale](odoo-18/Modules/sale.md) — Sale order
6. [Modules/Stock](odoo-18/Modules/stock.md) — Inventory

## Module Mapping (Keyword → Vault)

| Keyword | File |
|---|---|
| orm/model/base/CRUD | [Core/BaseModel](odoo-18/Core/BaseModel.md) |
| field/char/many2one | [Core/Fields](odoo-18/Core/Fields.md) |
| api/depends/onchange | [Core/API](odoo-18/Core/API.md) |
| controller/http/route | [Core/HTTP Controller](odoo-18/Core/HTTP Controller.md) |
| error/exception/validation | [Core/Exceptions](odoo-18/Core/Exceptions.md) |
| inheritance/_inherit | [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) |
| workflow/state/action | [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) |
| security/acl/groups | [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) |
| search/browse/domain | [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) |
| snippets/template | [Snippets/Model Snippets](odoo-18/Snippets/Model Snippets.md) |
| sale/quotation/so | [Modules/Sale](odoo-18/Modules/sale.md) |
| stock/picking/quant | [Modules/Stock](odoo-18/Modules/stock.md) |
| account/invoice/journal | [Modules/Account](odoo-18/Modules/account.md) |
| purchase/po/rfq | [Modules/Purchase](odoo-18/Modules/purchase.md) |
| crm/lead/opportunity | [Modules/CRM](odoo-18/Modules/CRM.md) |
| project/task/milestone | [Modules/Project](odoo-18/Modules/project.md) |
| mrp/production/bom | [Modules/MRP](odoo-18/Modules/mrp.md) |
| product/pricelist/uom | [Modules/Product](odoo-18/Modules/product.md) |
| partner/contact/bank | [Modules/res.partner](odoo-19/Modules/res.partner.md) |

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
