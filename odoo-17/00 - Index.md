# Odoo 17 Documentation Vault

Comprehensive documentation for **Odoo 17** codebase, built from actual source code analysis.

> **584 module documentation files** — 29 verified, 12 deep researched, 555 stubs
> **Source:** `~/odoo/odoo17/odoo/`

---

## Core Framework

| Document | Description |
|----------|-------------|
| [[Core/BaseModel]] | ORM foundation, _name, _inherit, CRUD |
| [[Core/API]] | @api.depends, @api.onchange, @api.constrains |
| [[Core/Fields]] | All field types (Char, Many2one, One2many, etc.) |
| [[Core/HTTP Controller]] | @http.route, auth types, JSON responses |
| [[Core/Exceptions]] | ValidationError, UserError, AccessError |

## Patterns

| Document | Description |
|----------|-------------|
| [[Patterns/Inheritance Patterns]] | _inherit vs _inherits vs mixin |
| [[Patterns/Workflow Patterns]] | State machines, button actions |
| [[Patterns/Security Patterns]] | ir.rule, ir.model.access, field groups |

## Tools & Snippets

| Document | Description |
|----------|-------------|
| [[Tools/ORM Operations]] | search(), browse(), domains, env |
| [[Tools/Modules Inventory]] | 575 modules catalog (✅=verified, ⚠️=stub) |
| [[Snippets/Model Snippets]] | Copy-paste code templates |
| [[Snippets/Controller Snippets]] | HTTP/JSON controller templates |

## New Features

| Document | Description |
|----------|-------------|
| [[New Features/What's New]] | Odoo 16 → 17 highlights |
| [[New Features/API Changes]] | Decorator and field changes |
| [[New Features/New Modules]] | New in Odoo 17 |

---

## Module Documentation (Tier 1 — Foundation) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [[Modules/base]] | ✅ Deep Research | res.partner, res.users, res.company, ir.module.module — 38 files, commercial_partner_id, PBKDF2-SHA512, ir.cron SKIP LOCKED |
| [[Modules/mail]] | ✅ Deep Research | mail.thread, mail.message, discuss.channel — 4,679L source, message_post flow, _notify split, live SQL view |
| [[Modules/ir_actions]] | ✅ Deep Research | ir.actions.act_window, ir.actions.server, ir.rule — 1,414L, 'global' workaround, _get_bindings raw SQL |

## Module Documentation (Tier 2 — Core Business) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [[Modules/sale]] | ✅ Deep Research | sale.order, sale.order.line — 5,276L source, 7-step confirm, conditional locking, UTM |
| [[Modules/purchase]] | ✅ Deep Research | purchase.order, purchase.order.line — 1,762L source, 2-step confirm, _add_supplier_to_product |
| [[Modules/stock]] | ✅ Deep Research | stock.picking, stock.move, stock.quant, stock.valuation.layer — 22 files, quant 5-tuple, button_validate chain |
| [[Modules/account]] | ✅ Deep Research | account.move, account.move.line, account.journal — 12-step _post(), Union-Find, CABA, double-entry |
| [[Modules/product]] | ✅ Verified | product.template, product.product |

## Module Documentation (Tier 3 — Extended Business) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [[Modules/crm]] | ✅ Deep Research | crm.lead, crm.team, crm.stage — Naive Bayes scoring, round-robin assignment, 7 mixins |
| [[Modules/project]] | ✅ Deep Research | project.project, project.task — Many2many user_ids, recursive CTE subtasks, CLOSED_STATES |
| [[Modules/hr]] | ✅ Deep Research | hr.employee, hr.department — live SQL view, coach auto-promotion, 90-day new hire window |
| [[Modules/mrp]] | ✅ Deep Research | mrp.production, mrp.bom, mrp.workorder — action_produce, BOM explode, workorder sequencing |
| [[Modules/repair]] | ✅ Verified | repair.order |

## Module Documentation (Tier 4 — Ecosystem) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [[Modules/website]] | ✅ Deep Research | website, website.menu, website.page — _inherits ir.ui.view, get_unique_path, per-website menu dup |
| [[Modules/website_sale]] | ✅ Verified | E-commerce sale.order |
| [[Modules/sale_management]] | ✅ Verified | sale.order.template |
| [[Modules/purchase_requisition]] | ✅ Verified | purchase.requisition |

## Module Documentation (Tier 5 — Integrations) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [[Modules/payment]] | ✅ Deep Research | payment.provider, payment.transaction — multi-seq reference, 3-layer callback, 4-day post-process |
| [[Modules/calendar]] | ✅ Verified | calendar.event, calendar.attendee |
| [[Modules/auth_signup]] | ✅ Verified | User registration, OAuth |
| [[Modules/sms]] | ✅ Verified | sms.sms, sms.template |
| [[Modules/mass_mailing]] | ✅ Verified | mailing.mailing, mailing.list |
| [[Modules/portal]] | ✅ Verified | portal.mixin |

## Module Documentation (Tier 6 — Advanced) ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [[Modules/point_of_sale]] | ✅ Verified | pos.order, pos.config |
| [[Modules/mrp_subcontracting]] | ✅ Verified | Subcontracting rules |
| [[Modules/spreadsheet]] | ✅ Verified | spreadsheet.spreadsheet |
| [[Modules/survey]] | ✅ Verified | survey.survey, survey.question |

## Accounting & Analytics ✅

| Module | Status | Key Models |
|--------|--------|-----------|
| [[Modules/stock_account]] | ✅ Verified | stock.valuation.layer |
| [[Modules/analytic]] | ✅ Verified | account.analytic.account |

## All 575+ Modules

See [[Tools/Modules Inventory]] for the complete catalog including 555 stubs.

---

## Business Guides

| Guide | Description |
|-------|-------------|
| [[Business/Sale/sales-guide]] | Creating and confirming sales orders |
| [[Business/Purchase/purchase-guide]] | RFQs to vendor bills |
| [[Business/Stock/stock-guide]] | Receipts, deliveries, transfers |
| [[Business/Account/accounting-guide]] | Invoices and payments |

## Business Flows

| Flow | Description |
|------|-------------|
| [[Flows/Stock/receipt-flow]] | Vendor → Receipt → Quant |
| [[Flows/Sale/sales-process-flow]] | Quotation → Delivery → Invoice |
| [[Flows/Purchase/purchase-process-flow]] | RFQ → Receipt → Bill |

---

## Research Progress

- **29** modules fully verified
- **12** modules deep researched (2 full source passes)
  - Pass 1: stock, account, sale, purchase, mrp, crm
  - Pass 2: base, mail, project, website, payment, hr, ir_actions
- **555** module stubs created
- **584** total documentation files
- Run: `odoo17-001` (2026-04-11, 2 deep research passes)
