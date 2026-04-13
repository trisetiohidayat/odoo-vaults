# Odoo 17 Documentation Vault

Comprehensive documentation for **Odoo 17** codebase, built from actual source code analysis.

> **584 module documentation files** — 29 verified, 12 deep researched, 555 stubs
> **Source:** `~/odoo/odoo17/odoo/`

---

## Core Framework

| Document | Description |
|----------|-------------|
| [Core/BaseModel](BaseModel.md) | ORM foundation, _name, _inherit, CRUD |
| [Core/API](API.md) | @api.depends, @api.onchange, @api.constrains |
| [Core/Fields](Fields.md) | All field types (Char, Many2one, One2many, etc.) |
| [Core/HTTP Controller](HTTP Controller.md) | @http.route, auth types, JSON responses |
| [Core/Exceptions](Exceptions.md) | ValidationError, UserError, AccessError |

## Patterns

| Document | Description |
|----------|-------------|
| [Patterns/Inheritance Patterns](Inheritance Patterns.md) | _inherit vs _inherits vs mixin |
| [Patterns/Workflow Patterns](Workflow Patterns.md) | State machines, button actions |
| [Patterns/Security Patterns](Security Patterns.md) | ir.rule, ir.model.access, field groups |

## Tools & Snippets

| Document | Description |
|----------|-------------|
| [Tools/ORM Operations](ORM Operations.md) | search(), browse(), domains, env |
| [Tools/Modules Inventory](Modules Inventory.md) | 575 modules catalog (✅=verified, ⚠️=stub) |
| [Snippets/Model Snippets](Model Snippets.md) | Copy-paste code templates |
| [Snippets/Controller Snippets](Controller Snippets.md) | HTTP/JSON controller templates |

## New Features

| Document | Description |
|----------|-------------|
| [New Features/What's New](What's New.md) | Odoo 16 → 17 highlights |
| [New Features/API Changes](API Changes.md) | Decorator and field changes |
| [New Features/New Modules](New Modules.md) | New in Odoo 17 |

---

## Module Documentation (Tier 1 — Foundation) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/base](base.md) | ✅ Deep Research | res.partner, res.users, res.company, ir.module.module — 38 files, commercial_partner_id, PBKDF2-SHA512, ir.cron SKIP LOCKED |
| [Modules/mail](mail.md) | ✅ Deep Research | mail.thread, mail.message, discuss.channel — 4,679L source, message_post flow, _notify split, live SQL view |
| [Modules/ir_actions](ir_actions.md) | ✅ Deep Research | ir.actions.act_window, ir.actions.server, ir.rule — 1,414L, 'global' workaround, _get_bindings raw SQL |

## Module Documentation (Tier 2 — Core Business) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/sale](sale.md) | ✅ Deep Research | sale.order, sale.order.line — 5,276L source, 7-step confirm, conditional locking, UTM |
| [Modules/purchase](purchase.md) | ✅ Deep Research | purchase.order, purchase.order.line — 1,762L source, 2-step confirm, _add_supplier_to_product |
| [Modules/stock](stock.md) | ✅ Deep Research | stock.picking, stock.move, stock.quant, stock.valuation.layer — 22 files, quant 5-tuple, button_validate chain |
| [Modules/account](account.md) | ✅ Deep Research | account.move, account.move.line, account.journal — 12-step _post(), Union-Find, CABA, double-entry |
| [Modules/product](product.md) | ✅ Verified | product.template, product.product |

## Module Documentation (Tier 3 — Extended Business) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/crm](crm.md) | ✅ Deep Research | crm.lead, crm.team, crm.stage — Naive Bayes scoring, round-robin assignment, 7 mixins |
| [Modules/project](project.md) | ✅ Deep Research | project.project, project.task — Many2many user_ids, recursive CTE subtasks, CLOSED_STATES |
| [Modules/hr](hr.md) | ✅ Deep Research | hr.employee, hr.department — live SQL view, coach auto-promotion, 90-day new hire window |
| [Modules/mrp](mrp.md) | ✅ Deep Research | mrp.production, mrp.bom, mrp.workorder — action_produce, BOM explode, workorder sequencing |
| [Modules/repair](repair.md) | ✅ Verified | repair.order |

## Module Documentation (Tier 4 — Ecosystem) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/website](website.md) | ✅ Deep Research | website, website.menu, website.page — _inherits ir.ui.view, get_unique_path, per-website menu dup |
| [Modules/website_sale](website_sale.md) | ✅ Verified | E-commerce sale.order |
| [Modules/sale_management](sale_management.md) | ✅ Verified | sale.order.template |
| [Modules/purchase_requisition](purchase_requisition.md) | ✅ Verified | purchase.requisition |

## Module Documentation (Tier 5 — Integrations) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/payment](payment.md) | ✅ Deep Research | payment.provider, payment.transaction — multi-seq reference, 3-layer callback, 4-day post-process |
| [Modules/calendar](calendar.md) | ✅ Verified | calendar.event, calendar.attendee |
| [Modules/auth_signup](auth_signup.md) | ✅ Verified | User registration, OAuth |
| [Modules/sms](sms.md) | ✅ Verified | sms.sms, sms.template |
| [Modules/mass_mailing](mass_mailing.md) | ✅ Verified | mailing.mailing, mailing.list |
| [Modules/portal](portal.md) | ✅ Verified | portal.mixin |

## Module Documentation (Tier 6 — Advanced) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/point_of_sale](point_of_sale.md) | ✅ Verified | pos.order, pos.config |
| [Modules/mrp_subcontracting](mrp_subcontracting.md) | ✅ Verified | Subcontracting rules |
| [Modules/spreadsheet](spreadsheet.md) | ✅ Verified | spreadsheet.spreadsheet |
| [Modules/survey](survey.md) | ✅ Verified | survey.survey, survey.question |

## Accounting & Analytics ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [Modules/stock_account](stock_account.md) | ✅ Verified | stock.valuation.layer |
| [Modules/analytic](analytic.md) | ✅ Verified | account.analytic.account |

## All 575+ Modules

See [Tools/Modules Inventory](Modules Inventory.md) for the complete catalog including 555 stubs.

---

## Business Guides

| Guide | Description |
|-------|-------------|
| [Business/Sale/sales-guide](sales-guide.md) | Creating and confirming sales orders |
| [Business/Purchase/purchase-guide](purchase-guide.md) | RFQs to vendor bills |
| [Business/Stock/stock-guide](stock-guide.md) | Receipts, deliveries, transfers |
| [Business/Account/accounting-guide](accounting-guide.md) | Invoices and payments |

## Business Flows

| Flow | Description |
|------|-------------|
| [Flows/Stock/receipt-flow](receipt-flow.md) | Vendor → Receipt → Quant |
| [Flows/Sale/sales-process-flow](sales-process-flow.md) | Quotation → Delivery → Invoice |
| [Flows/Purchase/purchase-process-flow](purchase-process-flow.md) | RFQ → Receipt → Bill |

---

## Research Progress

- **29** modules fully verified
- **12** modules deep researched (2 full source passes)
  - Pass 1: stock, account, sale, purchase, mrp, crm
  - Pass 2: base, mail, project, website, payment, hr, ir_actions
- **555** module stubs created
- **584** total documentation files
- Run: `odoo17-001` (2026-04-11, 2 deep research passes)
