# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Context

This is an **Obsidian vault** containing structured documentation for the **Odoo 18** codebase. The notes are written in Obsidian Flavored Markdown with wikilinks (`[Modules/Stock](Modules/Stock.md)`) and frontmatter tags. The actual Odoo 18 source code lives at `~/odoo/odoo18/odoo/` — the vault maps, explains, and cross-links that codebase.

**Vault location:** `~/odoo-vaults/odoo-18/`
**Source location:** `~/odoo/odoo18/odoo/`
**Total Modules:** 606 addons
**Modules Documented:** 64 (Phase 1-5 complete, 10.5%)
**Version:** 18.0.0 FINAL

## Vault Structure

```
odoo-18/
├── Core/                  # ORM framework fundamentals
│   ├── BaseModel.md       # Model foundation, _name, _inherit, CRUD methods
│   ├── Fields.md          # Field types (Char, Many2one, Json, etc.)
│   ├── API.md             # @api.depends, @api.onchange, @api.constrains
│   ├── HTTP Controller.md # @http.route, JSON responses, auth types
│   └── Exceptions.md      # ValidationError, UserError, AccessError
├── Patterns/              # Architectural patterns
│   ├── Inheritance Patterns.md   # _inherit vs _inherits vs mixin
│   ├── Workflow Patterns.md      # State machine, action methods
│   └── Security Patterns.md     # ACL CSV, ir.rule, field groups
├── Tools/
│   ├── ORM Operations.md  # search(), browse(), create(), write(), domain operators
│   └── Modules Inventory.md # 304 Odoo 18 modules catalog
├── Snippets/              # Copy-paste code templates
│   ├── Model Snippets.md
│   ├── Controller Snippets.md
│   └── method-chain-example.md
├── New Features/          # Odoo 17→18 and 18-specific changes
│   ├── What's New.md
│   ├── API Changes.md
│   └── New Modules.md
├── Modules/               # Per-module documentation (all addons)
│   ├── 00 - DOC PLAN.md
│   ├── TEMPLATE-module-entry.md
│   ├── Stock.md, Purchase.md, Account.md, Sale.md, CRM.md, MRP.md, etc.
│   └── l10n_*.md
├── Business/              # End-user guides
│   ├── TEMPLATE-guide.md
│   └── Sale/, Purchase/, Stock/, Account/, etc.
├── Flows/                 # Business process flows
│   ├── TEMPLATE-flow.md
│   └── Sale/, Purchase/, Stock/, Cross-Module/, etc.
├── Documentation/
│   ├── Checkpoints/
│   └── Upgrade-Plan/
├── Research-Log/          # Research state management
│   ├── active-run/
│   ├── completed-runs/
│   ├── backlog.md
│   └── verified-status.md
└── docs/plans/
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

### Purchase→Stock→Account Flow
1. `purchase.order` confirmed → creates `stock.picking` (receipt)
2. Receipt validated → `stock.quant` updated + `account.move` (journal entry) generated
3. Vendor bill created from PO → matched against receipt

## Working with This Vault

### Wikilinks
Use Obsidian wikilinks for cross-references: `[Modules/Stock](Modules/Stock.md)`, `[Core/API](Core/API.md)`, `[Patterns/Security Patterns](Patterns/Security-Patterns.md)`. These link to markdown files in the vault — not to Python files in the codebase.

### Code Locations
When referencing Odoo source code, the canonical path pattern is:
- Framework: `~/odoo/odoo18/odoo/odoo/models.py`
- Addons: `~/odoo/odoo18/odoo/addons/<module_name>/models/`

### Module Documentation Coverage
Documentation starts from scratch. Use the Research-Log (`Research-Log/backlog.md`) to track coverage. Key business modules (Stock, Purchase, Account, Sale, CRM, MRP) should be prioritized.

## Phase 5: Integrations (complete)
Phase 5 complete (16 modules). Phase 6: Localization (l10n modules) — 150+ country-specific modules pending.

### Tags Used
`#odoo`, `#odoo18`, `#orm`, `#fields`, `#api`, `#workflow`, `#security`, `#modules`
Per-module docs also carry module-specific tags.
