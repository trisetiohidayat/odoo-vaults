# Odoo 17 Documentation Vault

Comprehensive documentation for **Odoo 17** codebase, built from actual source code analysis.

> **584 module documentation files** — 29 verified, 12 deep researched, 555 stubs
> **Source:** `~/odoo/odoo17/odoo/`

---

## Core Framework

| Document | Description |
|----------|-------------|
| [Core/BaseModel](core/basemodel.md) | ORM foundation, _name, _inherit, CRUD |
| [Core/API](core/api.md) | @api.depends, @api.onchange, @api.constrains |
| [Core/Fields](core/fields.md) | All field types (Char, Many2one, One2many, etc.) |
| [Core/HTTP Controller](core/http-controller.md) | @http.route, auth types, JSON responses |
| [Core/Exceptions](core/exceptions.md) | ValidationError, UserError, AccessError |

## Patterns

| Document | Description |
|----------|-------------|
| [Patterns/Inheritance Patterns](patterns/inheritance-patterns.md) | _inherit vs _inherits vs mixin |
| [Patterns/Workflow Patterns](patterns/workflow-patterns.md) | State machines, button actions |
| [Patterns/Security Patterns](patterns/security-patterns.md) | ir.rule, ir.model.access, field groups |

## Tools & Snippets

| Document | Description |
|----------|-------------|
| [Tools/ORM Operations](tools/orm-operations.md) | search(), browse(), domains, env |
| [Tools/Modules Inventory](tools/modules-inventory.md) | 575 modules catalog (✅=verified, ⚠️=stub) |
| [Snippets/Model Snippets](snippets/model-snippets.md) | Copy-paste code templates |
| [Snippets/Controller Snippets](snippets/controller-snippets.md) | HTTP/JSON controller templates |

## New Features

| Document | Description |
|----------|-------------|
| [New Features/What's New](new-features/what's-new.md) | Odoo 16 → 17 highlights |
| [New Features/API Changes](new-features/api-changes.md) | Decorator and field changes |
| [New Features/New Modules](new-features/new-modules.md) | New in Odoo 17 |

---

## Module Documentation (Tier 1 — Foundation) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/base](modules/base.md) | ✅ Deep Research | res.partner, res.users, res.company, ir.module.module — 38 files, commercial_partner_id, PBKDF2-SHA512, ir.cron SKIP LOCKED |
| [Modules/mail](modules/mail.md) | ✅ Deep Research | mail.thread, mail.message, discuss.channel — 4,679L source, message_post flow, _notify split, live SQL view |
| [Modules/ir_actions](modules/ir_actions.md) | ✅ Deep Research | ir.actions.act_window, ir.actions.server, ir.rule — 1,414L, 'global' workaround, _get_bindings raw SQL |

## Module Documentation (Tier 2 — Core Business) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/sale](modules/sale.md) | ✅ Deep Research | sale.order, sale.order.line — 5,276L source, 7-step confirm, conditional locking, UTM |
| [Modules/purchase](modules/purchase.md) | ✅ Deep Research | purchase.order, purchase.order.line — 1,762L source, 2-step confirm, _add_supplier_to_product |
| [Modules/stock](modules/stock.md) | ✅ Deep Research | stock.picking, stock.move, stock.quant, stock.valuation.layer — 22 files, quant 5-tuple, button_validate chain |
| [Modules/account](modules/account.md) | ✅ Deep Research | account.move, account.move.line, account.journal — 12-step _post(), Union-Find, CABA, double-entry |
| [Modules/product](modules/product.md) | ✅ Verified | product.template, product.product |

## Module Documentation (Tier 3 — Extended Business) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/crm](modules/crm.md) | ✅ Deep Research | crm.lead, crm.team, crm.stage — Naive Bayes scoring, round-robin assignment, 7 mixins |
| [Modules/project](modules/project.md) | ✅ Deep Research | project.project, project.task — Many2many user_ids, recursive CTE subtasks, CLOSED_STATES |
| [Modules/hr](modules/hr.md) | ✅ Deep Research | hr.employee, hr.department — live SQL view, coach auto-promotion, 90-day new hire window |
| [Modules/mrp](modules/mrp.md) | ✅ Deep Research | mrp.production, mrp.bom, mrp.workorder — action_produce, BOM explode, workorder sequencing |
| [Modules/repair](modules/repair.md) | ✅ Verified | repair.order |

## Module Documentation (Tier 4 — Ecosystem) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/website](modules/website.md) | ✅ Deep Research | website, website.menu, website.page — _inherits ir.ui.view, get_unique_path, per-website menu dup |
| [Modules/website_sale](modules/website_sale.md) | ✅ Verified | E-commerce sale.order |
| [Modules/sale_management](modules/sale_management.md) | ✅ Verified | sale.order.template |
| [Modules/purchase_requisition](modules/purchase_requisition.md) | ✅ Verified | purchase.requisition |

## Module Documentation (Tier 5 — Integrations) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/payment](modules/payment.md) | ✅ Deep Research | payment.provider, payment.transaction — multi-seq reference, 3-layer callback, 4-day post-process |
| [Modules/calendar](modules/calendar.md) | ✅ Verified | calendar.event, calendar.attendee |
| [Modules/auth_signup](modules/auth_signup.md) | ✅ Verified | User registration, OAuth |
| [Modules/sms](modules/sms.md) | ✅ Verified | sms.sms, sms.template |
| [Modules/mass_mailing](modules/mass_mailing.md) | ✅ Verified | mailing.mailing, mailing.list |
| [Modules/portal](modules/portal.md) | ✅ Verified | portal.mixin |

## Module Documentation (Tier 6 — Advanced) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/point_of_sale](modules/point_of_sale.md) | ✅ Verified | pos.order, pos.config |
| [Modules/mrp_subcontracting](modules/mrp_subcontracting.md) | ✅ Verified | Subcontracting rules |
| [Modules/spreadsheet](modules/spreadsheet.md) | ✅ Verified | spreadsheet.spreadsheet |
| [Modules/survey](modules/survey.md) | ✅ Verified | survey.survey, survey.question |

## Accounting & Analytics ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/stock_account](modules/stock_account.md) | ✅ Verified | stock.valuation.layer |
| [Modules/analytic](modules/analytic.md) | ✅ Verified | account.analytic.account |

## All 575+ Modules

See [Tools/Modules Inventory](tools/modules-inventory.md) for the complete catalog including 555 stubs.

---

## Business Guides

| Guide | Description |
|-------|-------------|
| [Business/Sale/sales-guide](business/sale/sales-guide.md) | Creating and confirming sales orders |
| [Business/Purchase/purchase-guide](business/purchase/purchase-guide.md) | RFQs to vendor bills |
| [Business/Stock/stock-guide](business/stock/stock-guide.md) | Receipts, deliveries, transfers |
| [Business/Account/accounting-guide](business/account/accounting-guide.md) | Invoices and payments |

## Business Flows

| Flow | Description |
|------|-------------|
| [Flows/Stock/receipt-flow](flows/stock/receipt-flow.md) | Vendor → Receipt → Quant |
| [Flows/Sale/sales-process-flow](flows/sale/sales-process-flow.md) | Quotation → Delivery → Invoice |
| [Flows/Purchase/purchase-process-flow](flows/purchase/purchase-process-flow.md) | RFQ → Receipt → Bill |

---

## Research Progress

- **29** modules fully verified
- **12** modules deep researched (2 full source passes)
  - Pass 1: stock, account, sale, purchase, mrp, crm
  - Pass 2: base, mail, project, website, payment, hr, ir_actions
- **555** module stubs created
- **584** total documentation files
- Run: `odoo17-001` (2026-04-11, 2 deep research passes)
