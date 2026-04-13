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

1. [[Core/BaseModel]] — ORM basics
2. [[Core/Fields]] — Field types
3. [[Core/API]] — Decorators
4. [[Tools/ORM Operations]] — search/browse/create
5. [[Modules/Sale]] — Sale order
6. [[Modules/Stock]] — Inventory

## Module Mapping (Keyword → Vault)

| Keyword | File |
|---|---|
| orm/model/base/CRUD | [[Core/BaseModel]] |
| field/char/many2one | [[Core/Fields]] |
| api/depends/onchange | [[Core/API]] |
| controller/http/route | [[Core/HTTP Controller]] |
| error/exception/validation | [[Core/Exceptions]] |
| inheritance/_inherit | [[Patterns/Inheritance Patterns]] |
| workflow/state/action | [[Patterns/Workflow Patterns]] |
| security/acl/groups | [[Patterns/Security Patterns]] |
| search/browse/domain | [[Tools/ORM Operations]] |
| snippets/template | [[Snippets/Model Snippets]] |
| sale/quotation/so | [[Modules/Sale]] |
| stock/picking/quant | [[Modules/Stock]] |
| account/invoice/journal | [[Modules/Account]] |
| purchase/po/rfq | [[Modules/Purchase]] |
| crm/lead/opportunity | [[Modules/CRM]] |
| project/task/milestone | [[Modules/Project]] |
| mrp/production/bom | [[Modules/MRP]] |
| product/pricelist/uom | [[Modules/Product]] |
| partner/contact/bank | [[Modules/res.partner]] |

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
```