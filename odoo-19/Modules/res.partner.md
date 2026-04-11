---
type: module
module: res.partner
tags: [odoo, odoo19, partner, contact, company, address]
created: 2026-04-06
---

# res.partner

## Overview

Partner/Contact management - customers, vendors, and companies.

**Location:** `~/odoo/odoo19/odoo/addons/base/`

## Key Models

| Model | Description |
|-------|-------------|
| `res.partner` | Partners/Contacts |

## Partner Types

```
res.partner
├── Company (is_company=True)
│   ├── Child: Contact (individual)
│   └── Child: Contact (individual)
└── Individual (is_company=False)
```

## res.partner Fields

```python
name = fields.Char(required=True)
active = fields.Boolean(default=True)
is_company = fields.Boolean('Is a Company')
company_id = fields.Many2one('res.company')
parent_id = fields.Many2one('res.partner', string='Related Company')
child_ids = fields.One2many('res.partner', 'parent_id')
street = fields.Char()
city = fields.Char()
state_id = fields.Many2one('res.country.state')
country_id = fields.Many2one('res.country')
zip = fields.Char()
phone = fields.Char()
email = fields.Char()
website = fields.Char()

# Commercial fields
user_id = fields.Many2one('res.users', string='Salesperson')
team_id = fields.Many2one('crm.team', string='Sales Team')
```

## Related Models

| Model | Relation |
|-------|----------|
| [[Modules/Sale]] | customer_id |
| [[Modules/Purchase]] | partner_id (vendor) |
| [[Modules/Account]] | partner_id |
| [[Modules/CRM]] | partner_id |
| [[Modules/Stock]] | partner_id |
| [[Modules/MRP]] | None direct |

## Related

- [[Core/BaseModel]] - ORM foundation
- [[Modules/Sale]] - Customer
- [[Modules/Purchase]] - Vendor
- [[Modules/Account]] - Receivables/Payables
- [[Modules/CRM]] - Lead/Opportunity
