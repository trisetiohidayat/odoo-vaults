# Odoo Vaults

Documentation vaults for multiple Odoo versions, generated from source code research.

**Location:** `/Users/tri-mac/odoo-vaults/`

## Vaults

| Version | Status | Source Path |
|---------|--------|-------------|
| [Odoo 15](./odoo-15/) | Active | `/Users/tri-mac/project/roedl/odoo15.0-roedl/odoo/` |
| [Odoo 17](./odoo-17/) | Available | — |
| [Odoo 18](./odoo-18/) | Available | — |
| [Odoo 19](./odoo-19/) | Available | — |

## Structure

```
odoo-vaults/
├── odoo-15/           # Odoo 15.0 documentation (active)
├── odoo-17/           # Odoo 17.0 documentation
├── odoo-18/           # Odoo 18.0 documentation
├── odoo-19/           # Odoo 19.0 documentation
└── tools.yaml         # Research tools configuration
```

## Vault Structure (per version)

Each vault follows this pattern:

```
odoo-XX/
├── Core/              # ORM fundamentals (BaseModel, Fields, API, Exceptions)
├── Patterns/          # Design patterns (inheritance, security, workflow)
├── Flows/             # Business process flows
├── Tools/             # ORM operations and utilities
├── Snippets/          # Code templates
├── Modules/           # Module references (Sale, Stock, Account, etc.)
├── Business/          # Business logic documentation
├── New Features/      # Version-specific changes
├── Research-Log/       # Research activity logs
└── README.md          # Version-specific documentation
```

## Quick Navigation

### Odoo 15 (Active)

| Topic | File |
|-------|------|
| ORM basics | [[odoo-15/Core/BaseModel]] |
| Field types | [[odoo-15/Core/Fields]] |
| API decorators | [[odoo-15/Core/API]] |
| HTTP controllers | [[odoo-15/Core/HTTP Controller]] |
| Exceptions | [[odoo-15/Core/Exceptions]] |
| Inheritance patterns | [[odoo-15/Patterns/Inheritance Patterns]] |
| Security patterns | [[odoo-15/Patterns/Security Patterns]] |
| Workflow patterns | [[odoo-15/Patterns/Workflow Patterns]] |

### Module Mapping (Odoo 15)

| Keyword | File |
|---------|------|
| sale/quotation/so | [[odoo-15/Modules/Sale]] |
| stock/picking/quant | [[odoo-15/Modules/Stock]] |
| account/invoice/journal | [[odoo-15/Modules/Account]] |
| purchase/po/rfq | [[odoo-15/Modules/Purchase]] |
| crm/lead/opportunity | [[odoo-15/Modules/CRM]] |
| project/task/milestone | [[odoo-15/Modules/Project]] |
| mrp/production/bom | [[odoo-15/Modules/MRP]] |
| product/pricelist/uom | [[odoo-15/Modules/Product]] |
| partner/contact/bank | [[odoo-15/Modules/res.partner]] |

## Search Keywords

Quick lookup table for finding relevant documentation:

| Search Term | Documentation |
|-------------|--------------|
| `model._name`, `self.env` | [[odoo-15/Core/BaseModel]] |
| `Char`, `Many2one`, `One2many` | [[odoo-15/Core/Fields]] |
| `@api.depends`, `@api.onchange` | [[odoo-15/Core/API]] |
| `ValidationError`, `UserError` | [[odoo-15/Core/Exceptions]] |
| `_inherit`, `_name` | [[odoo-15/Patterns/Inheritance Patterns]] |
| `ir.rule`, `groups` | [[odoo-15/Patterns/Security Patterns]] |
| `state`, `button_` | [[odoo-15/Patterns/Workflow Patterns]] |
| `search()`, `browse()`, `create()` | [[odoo-15/Tools/ORM Operations]] |
| `sale.order`, `account.move` | [[odoo-15/Modules/Sale]], [[odoo-15/Modules/Account]] |

## Usage Tips

1. **Open in Obsidian** — This vault is designed for [Obsidian](https://obsidian.md/)
2. **Use backlinks** — Click links to navigate between related topics
3. **Follow research logs** — See [[odoo-15/Research-Log/active-run/]] for development notes
4. **Check module paths** — Each module doc includes source file paths for reference

## Contributing

When adding new documentation:
1. Place files in appropriate folder (Core, Modules, Patterns, etc.)
2. Update this README with new entries in the mapping tables
3. Use Obsidian wikilinks `[[file-name]]` for internal references
4. Follow existing file structure and formatting

## Notes

- Vaults are research-based, generated from actual Odoo source code
- Each version may have different structure as features evolve
- Odoo 15 is the primary/active vault with comprehensive documentation
