# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Context

This is an **Obsidian vault** containing structured documentation for the **Odoo 19** codebase. The notes are written in Obsidian Flavored Markdown with wikilinks (`[Modules/Stock](Stock.md)`) and frontmatter tags. The actual Odoo 19 source code lives at `~/odoo/odoo19/` — the vault maps, explains, and cross-links that codebase.

**Vault location:** `~/odoo-vaults/odoo-19/`

## Vault Structure

```
Odoo 19/
├── Core/                  # ORM framework fundamentals
│   ├── BaseModel.md       # Model foundation, _name, _inherit, CRUD methods
│   ├── Fields.md          # Field types (Char, Many2one, Json, etc.)
│   ├── API.md             # @api.depends, @api.onchange, @api.constrains
│   ├── HTTP Controller.md # @http.route, JSON responses, auth types
│   └── Exceptions.md      # ValidationError, UserError, AccessError
├── Patterns/              # Architectural patterns
│   ├── Inheritance Patterns.md   # _inherit vs _inherits vs mixin
│   ├── Workflow Patterns.md        # State machine, action methods
│   └── Security Patterns.md       # ACL CSV, ir.rule, field groups
├── Tools/
│   ├── ORM Operations.md  # search(), browse(), create(), write(), domain operators
│   └── Modules Inventory.md # 304 Odoo 19 modules catalog
├── Snippets/              # Copy-paste code templates
│   ├── Model Snippets.md  # Basic model, computed field, action button
│   └── Controller Snippets.md
├── New Features/          # Odoo 18→19 and 19-specific changes
│   ├── What's New.md
│   ├── API Changes.md     # Json field, @api.model_create_multi, deprecations
│   └── New Modules.md
├── Modules/               # Per-module documentation (80+ modules)
│   ├── Stock.md           # stock.quant, stock.picking, stock.move, warehouse
│   ├── Purchase.md        # purchase.order, purchase.order.line, PO→invoice flow
│   ├── Account.md         # account.move, journal entries, invoicing
│   ├── Sale.md, CRM.md, MRP.md, Product.md, HR.md, etc.
│   └── res.partner.md
└── Documentation/
    └── Checkpoints/       # Progress tracking for documentation coverage
```

## Key Architectural Insights

### Odoo ORM Foundation (`odoo/odoo/models.py`)
- All models inherit from `BaseModel`. `_name` is the identifier; `_inherit` controls extension.
- Recordsets are lazy — chaining `self.env['model'].search(...).write(...)` executes only at write.
- `@api.model` methods run as superuser with no active record; `@api.depends`/`@api.onchange`/`@api.constrains` run with ACL.

### Three Inheritance Patterns
1. **Classic** (`_inherit = 'parent.model'`): Adds fields/methods to existing model.
2. **Delegation** (`_inherits = {...}`): Child model stores parent fields via Many2one with `delegate=True`.
3. **Prototype** (`_inherit = ['model.a', 'mixin.b']`): Creates new model combining behaviors.

### State Workflow Pattern
Models like `sale.order`, `purchase.order`, `stock.picking` use a `state` Selection field + explicit action methods (`action_confirm`, `action_done`, etc.) rather than Odoo's deprecated XML workflow engine. Validations run before `write({'state': ...})`.

### Stock Valuation (via `stock_account` module)
Inventory valuation is tracked through `stock.quant` quantities at specific `stock.location` entries. Valuation entries are created when a `stock.move` is done. Key locations: `property_stock_valuation_account_id` on product category and `account.move.line` entries generated on move confirmation.

### Purchase→Stock→Account Flow
1. `purchase.order` confirmed → creates `stock.picking` (receipt)
2. Receipt validated → `stock.quant` updated + `account.move` (journal entry) generated
3. Vendor bill created from PO → matched against receipt

## Working with This Vault

### Wikilinks
Use Obsidian wikilinks for cross-references: `[Modules/Stock](Stock.md)`, `[Core/API](API.md)`, `[Patterns/Security Patterns](Security Patterns.md)`. These link to markdown files in the vault — not to Python files in the codebase.

### Code Locations
When referencing Odoo source code, the canonical path pattern is:
- Framework: `~/odoo/odoo19/odoo/odoo/models.py`
- Addons: `~/odoo/odoo19/odoo/addons/<module_name>/models/`

### Module Documentation Coverage
~80 of 304 modules are documented. Use the Checkpoints (`Documentation/Checkpoints/`) to track what's been covered. Key business modules (Stock, Purchase, Account, Sale, CRM, MRP) are documented in depth.

### Tags Used
`#odoo`, `#odoo19`, `#orm`, `#fields`, `#api`, `#workflow`, `#security`, `#modules`
Per-module docs also carry module-specific tags.
