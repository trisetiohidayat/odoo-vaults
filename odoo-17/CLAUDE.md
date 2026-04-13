# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Context

This is an **Obsidian vault** containing structured documentation for the **Odoo 17** codebase. The notes are written in Obsidian Flavored Markdown with wikilinks (`[wikilink](wikilink.md)`) and frontmatter tags. The actual Odoo 17 source code lives at `~/odoo/odoo17/` — the vault maps, explains, and cross-links that codebase.

**Vault location:** `~/odoo-vaults/odoo-17/`

## Vault Structure

```
Odoo 17/
├── Core/                  # ORM framework fundamentals
│   ├── BaseModel.md       # Model foundation, _name, _inherit, CRUD methods
│   ├── Fields.md          # Field types (Char, Many2one, Json, etc.)
│   ├── API.md             # @api.depends, @api.onchange, @api.constrains
│   ├── HTTP Controller.md # @http.route, JSON responses, auth types
│   └── Exceptions.md      # ValidationError, UserError, AccessError
├── Patterns/              # Architectural patterns
│   ├── Inheritance Patterns.md   # _inherit vs _inherits vs mixin
│   ├── Workflow Patterns.md       # State machine, action methods
│   └── Security Patterns.md       # ACL CSV, ir.rule, field groups
├── Tools/
│   ├── ORM Operations.md  # search(), browse(), create(), write(), domain operators
│   └── Modules Inventory.md # Odoo 17 modules catalog
├── Snippets/              # Copy-paste code templates
│   ├── Model Snippets.md  # Basic model, computed field, action button
│   └── Controller Snippets.md
├── New Features/          # Odoo 16→17 and 17-specific changes
│   ├── What's New.md
│   ├── API Changes.md
│   └── New Modules.md
├── Modules/               # Per-module documentation
│   ├── 00 - DOC PLAN.md
│   ├── TEMPLATE-module-entry.md
│   └── [module].md
├── Business/              # End-user guides
│   ├── Sale/, Purchase/, Stock/, Account/
├── Flows/                 # Business process flows
│   ├── Sale/, Purchase/, Stock/, Cross-Module/
└── Documentation/
    └── Checkpoints/       # Progress tracking
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
Models like `sale.order`, `purchase.order`, `stock.picking` use a `state` Selection field + explicit action methods (`action_confirm`, `action_done`, etc.). Validations run before `write({'state': ...})`.

## Working with This Vault

### Wikilinks
Use Obsidian wikilinks: `[Core/BaseModel](odoo-18/Core/BaseModel.md)`, `[Modules/Stock](odoo-18/Modules/stock.md)`, `[Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md)`.
**Python models**: use backticks, NOT wikilinks: `` `sale.order` ``

### Code Locations
- Framework: `~/odoo/odoo17/odoo/odoo/models.py`
- Addons: `~/odoo/odoo17/odoo/addons/<module_name>/models/`

### Tags Used
`#odoo`, `#odoo17`, `#orm`, `#fields`, `#api`, `#workflow`, `#security`, `#modules`
