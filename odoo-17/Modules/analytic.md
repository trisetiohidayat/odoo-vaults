---
tags: [odoo, odoo17, module, analytic]
---

# Analytic Module

**Source:** `addons/analytic/models/`

> Renamed from `account_analytic` in Odoo 17. The module is now just `analytic`.

## Overview

Provides cost-center accounting via analytic accounts and plans. Analytic lines record financial impact of operations independently from journal entries.

## Key Models

| Model | Description |
|-------|-------------|
| `account.analytic.plan` | Plan definition (e.g. "Projects", "Departments") |
| `account.analytic.account` | Analytic account (cost center), linked to a plan |
| `account.analytic.line` | Individual analytic entry |
| `account.analytic.distribution.model` | Auto-fill distribution from partner/product |
| `account.analytic.applicability` | Per-domain applicability rules for plans |

## Analytic Plans

Odoo 17 supports **multiple independent plans** via dynamic column creation on `account.analytic.line`:

```python
class AccountAnalyticPlan(models.Model):
    _name = 'account.analytic.plan'

    def _strict_column_name(self):
        # Project plan gets 'account_id', others get 'x_plan{id}_id'
        return 'account_id' if self == project_plan else f"x_plan{self.id}_id"

    def _sync_plan_column(self):
        # Creates a manual Many2one field on account.analytic.line
        # when a new non-root plan is created
        self.env['ir.model.fields'].sudo().create({
            'name': column,
            'model': 'account.analytic.line',
            'relation': 'account.analytic.account',
            'ttype': 'many2one',
        })
```

The "Project" plan is stored as `analytic.project_plan` config param and uses column `account_id`. Other plans get auto-generated columns like `x_plan5_id`.

## `account.analytic.account`

```python
class AccountAnalyticAccount(models.Model):
    _name = 'account.analytic.account'
    _inherit = ['mail.thread']          # Tracks changes

    name = fields.Char(required=True)
    code = fields.Char(string='Reference')
    plan_id = fields.Many2one('account.analytic.plan', required=True)
    root_plan_id = fields.Many2one(related='plan_id.root_id', store=True)
    partner_id = fields.Many2one('res.partner', string='Customer')
    line_ids = fields.One2many('account.analytic.line', 'auto_account_id')

    # Computed from analytic lines
    balance = fields.Monetary(compute='_compute_debit_credit_balance')
    debit = fields.Monetary(compute='_compute_debit_credit_balance')
    credit = fields.Monetary(compute='_compute_debit_credit_balance')

    @api.depends('line_ids.amount')
    def _compute_debit_credit_balance(self):
        # Groups lines by plan and currency, sums positive=credit, negative=debit
        # Uses _read_group with custom aggregation for balance/debit/credit
```

## `account.analytic.line`

```python
class AccountAnalyticLine(models.Model):
    _name = 'account.analytic.line'

    name = fields.Char(required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    amount = fields.Monetary(required=True, default=0.0)
    unit_amount = fields.Float(string='Quantity')
    product_uom_id = fields.Many2one('uom.uom')
    account_id = fields.Many2one('account.analytic.account', required=True)
    # Magic field: resolves to the right plan-specific column via context
    auto_account_id = fields.Many2one(
        'account.analytic.account',
        compute='_compute_auto_account',
        inverse='_inverse_auto_account',
        search='_search_auto_account',
    )
    partner_id = fields.Many2one('res.partner')
    user_id = fields.Many2one('res.users')
    company_id = fields.Many2one('res.company')
    category = fields.Selection([('other', 'Other')], default='other')
```

### `auto_account_id` Magic Field

Since `account.analytic.line` has one account column per plan (e.g. `account_id`, `x_plan5_id`), the `auto_account_id` field uses context (`analytic_plan_id`) to determine which column to read/write:

```python
@api.depends_context('analytic_plan_id')
def _compute_auto_account(self):
    plan = self.env['account.analytic.plan'].browse(self.env.context.get('analytic_plan_id'))
    for line in self:
        line.auto_account_id = bool(plan) and line[plan._column_name()]
```

## Analytic Distribution

On `account.move.line`, the `analytic_distribution` field is a JSON dict mapping account IDs to percentages:

```python
# Single account at 100%:
analytic_distribution = {str(analytic_account_id): 100.0}

# Multiple accounts (split):
{
    str(account_id_1): 70.0,
    str(account_id_2): 30.0,
}
# Sum must equal 100.
```

Auto-fill via `account.analytic.distribution.model`:
```python
@api.model
def _get_distribution(self, vals):
    # Finds best-matching distribution model based on:
    # - partner_id, partner_category_id, company_id
    # - any custom fields on the distribution model
    # Returns the analytic_distribution dict
```

## Applicability Rules

`account.analytic.applicability` controls when plans appear on business documents:

```python
# business_domain examples: 'general', 'sale_order', 'account_move', 'purchase_order'
applicability = fields.Selection([
    ('optional', 'Optional'),
    ('mandatory', 'Mandatory'),
    ('unavailable', 'Unavailable'),
])
```

## See Also
- [Modules/Account](odoo-18/Modules/account.md) — Journal entries with `analytic_distribution`
- [Modules/Stock Account](Modules/Stock-Account.md) — Stock move analytic lines
- [Modules/Purchase](odoo-18/Modules/purchase.md) — Purchase order analytic distribution
- [Modules/Sale](odoo-18/Modules/sale.md) — Sale order analytic distribution
