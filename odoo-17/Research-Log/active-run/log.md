# Active Run Log — Odoo 17

**Started:** 2026-04-11
**Completed:** 2026-04-11
**Run ID:** odoo17-001
**Mode:** quick (L2)
**Version:** Odoo 17
**Source:** ~/odoo/odoo17/odoo/

## Activity Log

### Vault Structure Created
- 19 directories, 7 initial files
- Research-Log files initialized

### Tier 1 — Foundation Modules ✅
- base ✅ (7 models: res.partner, res.users, res.company, res.partner.bank, res.bank, ir.module.module, ir.config_parameter) — 522 lines
- mail ✅ (9 models: mail.thread, mail.message, mail.mail, mail.followers, mail.notification, mail.activity, mail.composer.mixin, discuss.channel, discuss.channel.member)
- ir_actions ✅ (8 action types + ir.rule)

### Core Framework Docs ✅
- Core/BaseModel.md — ORM foundation
- Core/API.md — @api decorators
- Core/Fields.md — All field types
- Core/HTTP Controller.md — @http.route
- Core/Exceptions.md — ValidationError, UserError, AccessError
- Patterns/Inheritance Patterns.md
- Patterns/Workflow Patterns.md
- Patterns/Security Patterns.md
- Snippets/Model Snippets.md
- Snippets/Controller Snippets.md
- Tools/ORM Operations.md
- Tools/Modules Inventory.md (575 modules catalog)
- New Features/What's New.md
- New Features/API Changes.md
- New Features/New Modules.md

### Tier 2 — Core Business ✅
- sale ✅ (sale.order, sale.order.line)
- purchase ✅ (purchase.order, purchase.order.line)
- stock ✅ (9 models + receipt-flow) — 475 lines
- account ✅ (account.move, account.move.line, account.journal, account.account)
- product ✅ (product.template, product.product, product.category)

### Tier 3 — Extended Business ✅
- crm ✅ (crm.lead, crm.team, crm.stage, crm.tag)
- project ✅ (project.project, project.task, project.task.type)
- hr ✅ (hr.employee, hr.department, hr.job)
- mrp ✅ (mrp.production, mrp.bom, mrp.workorder, mrp.workcenter)
- repair ✅ (repair.order, repair.line)
- quality ✅ (stub — quality module integrated in stock)
- helpdesk ✅ (stub — not in base addons)

### Tier 4 — Ecosystem ✅
- website ✅ (website, website.menu, website.page)
- website_sale ✅ (e-commerce integration)
- sale_management ✅ (sale.order.template, sale.order.option)
- purchase_requisition ✅ (purchase.requisition)

### Tier 5 — Integrations ✅
- payment ✅ (payment.provider, payment.transaction, payment.token)
- auth_signup ✅ (signup flow, OAuth, TOTP)
- calendar ✅ (calendar.event, calendar.attendee, calendar.alarm)
- sms ✅ (sms.sms, sms.template)
- mass_mailing ✅ (mailing.mailing, mailing.contact, mailing.list)
- portal ✅ (portal.mixin, access tokens)

### Tier 6 — Advanced ✅
- mrp_subcontracting ✅ (subcontracting rules)
- point_of_sale ✅ (pos.order, pos.config, pos.session)
- spreadsheet ✅ (spreadsheet.spreadsheet, spreadsheet.share)
- survey ✅ (survey.survey, survey.question, survey.user_input)

### Accounting & Analytics ✅
- stock_account ✅ (stock.valuation.layer, Anglo-Saxon valuation)
- analytic ✅ (account.analytic.account, analytic_distribution JSON)
- google_calendar ✅ (bidirectional sync with Google Calendar)
- account_analytic ✅ (analytic mixin)
- account_check_printing ✅ (check printing)
- base_import ✅ (CSV/Excel import)
- utm ✅ (UTM tracking mixin)

### Full Module Stubs ✅
- 555 stub files created for all remaining modules
  - 207 l10n_* country localization modules
  - 21 payment_* provider modules
  - 31 pos_* extensions
  - 74 website_* extensions
  - 23 sale_* extensions
  - And more...

### Business Guides ✅
- Business/Sale/sales-guide.md
- Business/Purchase/purchase-guide.md
- Business/Stock/stock-guide.md
- Business/Account/accounting-guide.md

### Flows ✅
- Flows/Stock/receipt-flow.md
- Flows/Sale/sales-process-flow.md
- Flows/Purchase/purchase-process-flow.md

## Deep Research Pass — 2026-04-11 (Session 1)

Completed comprehensive deep research on 6 core modules. Source read in FULL.

### stock (Deep Research) ✅
- **File:** Modules/stock.md (1,927 lines, 71,302 bytes)
- **Source:** 22 Python files, ~12,344 lines read
- **Key:** Quant 5-tuple system, button_validate() call chain (L1134→L978→L1909→L571→L1074), MTO procurement, FIFO/LIFO/LIFO removal strategies, backorder split at L1947, concurrent SKIP LOCKED safety, 7-step warehouse routing

### account (Deep Research) ✅
- **File:** Modules/account.md (1,175 lines, 47,404 bytes) — 10.5x expansion
- **Key:** _post() has 12 steps (L3893-L4054), Union-Find matching_number, CABA cash-basis taxes, recursive tax.compute_all(), _compute_balance() auto double-entry, 5 payment states, 18 account types

### sale (Deep Research) ✅
- **File:** Modules/sale.md (814 lines)
- **Source:** 5,276 lines read (sale_order.py 1977L, sale_order_line.py 1329L, etc.)
- **Key:** 7-step action_confirm(), conditional locking (group_auto_done_setting), UTM + transaction_ids on invoices, down payment rounding correction, all product-change side effects as computed fields

### purchase (Deep Research) ✅
- **File:** Modules/purchase.md (684 lines)
- **Source:** purchase_order.py 1094L, purchase_order_line.py 668L
- **Key:** 2-step confirmation (to approve state), _add_supplier_to_product() auto-adds vendor to product supplierinfo, invoice policy per product (purchase_method), no auto-cancel on PO cancel

### mrp (Deep Research) ✅
- **Key:** action_produce() full implementation, BOM explode() method, workorder sequencing with blocked_by dependencies, consumption calculation modes, OEE tracking via .scrap_ids

### crm (Deep Research) ✅
- **Key:** Naive Bayes PLS scoring (_pls_get_naive_bayes_probabilities()), weighted round-robin assignment (_allocate_leads()), 7 mixins on crm.lead, action_set_won/lost implementations, convert_opportunity()

## Deep Research Pass — 2026-04-11 (Session 2)

Completed comprehensive deep research on 6 additional modules. All source read in FULL.

### base (Deep Research) ✅
- **File:** Modules/base.md (~995 lines)
- **Source:** 38 model files read across addons/base/models/ (all subdirectories)
- **Key:** res.partner commercial_partner_id pattern, res.users _inherits + passlib PBKDF2-SHA512 600k rounds + SELF_READABLE/WRITEABLE_FIELDS, res.company root/branch hierarchy + currency delegation, ir.module.module 6-state lifecycle + button_* methods, ir.config_parameter raw SQL bypass + ormcache, ir.attachment SHA-based filestore + GC checklist, ir.cron FOR NO KEY UPDATE SKIP LOCKED row locking, res.currency _get_rates() SQL + _convert(), 10 architectural patterns with inline code

### mail (Deep Research) ✅
- **File:** Modules/mail.md (1,445 lines) — most comprehensive mail doc
- **Source:** ~4,679 lines across mail/models/ (mail.thread 4,679L, mail.message 1,295L, mail.mail 777L, mail.followers 525L, mail.activity 828L, mail.alias 538L, etc.)
- **Key:** message_post() full flow, _notify_thread() + _notify_by_email() split, _track_prepare()/finalize() precommit hooks, _insert_followers() with 4 policies, _compute_state() for activities with TZ-aware deadline, alias_contact security levels, hr.employee.public live SQL view (init recreates on every load), discuss.channel chat max-2 constraint, mail.thread.cc CC parsing, mail.tracking.duration.mixin JSON format

### project (Deep Research) ✅
- **File:** Modules/project.md (619 lines)
- **Source:** 3,498 lines (project_task.py 1,787L, project_project.py 1,057L, etc.)
- **Key:** user_ids is Many2many (multi-assignee, junction table project_task_user_rel), CLOSED_STATES controls everything including dependency blocking, 04_waiting_normal auto-computed from depend_on_ids (lines 300-313), mail.tracking.duration.mixin + _track_duration_field='stage_id' for time-in-stage, recursive CTE for subtask tree (WITH RECURSIVE task_tree, lines 1537-1573), personal stages per user, PROJECT_TASK_READABLE/WRITABLE_FIELDS for portal access, _set_stage_on_project_from_task auto-adds stage to project

### website (Deep Research) ✅
- **File:** Modules/website.md (529 lines)
- **Source:** 3,000 lines (website.py 2,033L, website_menu.py 339L, website_page.py 341L, etc.)
- **Key:** _inherits ir.ui.view delegation (page metadata separate from view), get_unique_path() with -1/-2 suffix, per-website menu duplication on create, _get_most_specific_pages() specificity resolution, public user per website (real res.users with no login), website.rewrite redirect types (301/302/308/404), menu hierarchy max 2 levels enforced, _is_active() URL matching with param subset rule

### payment (Deep Research) ✅
- **File:** Modules/payment.md (560 lines)
- **Source:** 2,401 lines (payment_transaction.py 1,161L, payment_provider.py 758L, payment_method.py 272L, payment_token.py 197L)
- **Key:** _compute_reference() multi-sequence algorithm, 3-layer callback security (sudo check + HMAC hash + callback_is_done flag), state machine idempotency via _update_state(), _cron_finalize_post_processing() with 4-day window for slow providers, child transactions for refunds/captures, 5 operation types, 4 feature flags per provider (tokenization, manual_capture, express_checkout, refunds)

### hr (Deep Research) ✅
- **File:** Modules/hr.md (550 lines)
- **Source:** 1,259 lines across hr/models/ (hr_employee.py 617L, hr_department.py 181L, hr_employee_base.py 303L, etc.)
- **Key:** hr.employee.public is live SQL view recreated via init(), work contact creation on user linking, avatar computation from employee name initials, coach auto-promotion when promoted to manager, parent auto-from-department-manager cascade, newly_hired 90-day window, _parent_store=True on department, manager detection via child_of domain in employee_id bridge

### ir_actions (Deep Research) ✅
- **File:** Modules/ir_actions.md (621 lines)
- **Source:** 1,414 lines (ir_actions.py 1,149L, ir_rule.py 265L)
- **Key:** 'global' Python keyword workaround via setattr(), _compute_views() merge algorithm, _get_bindings() raw SQL + frozendict, run() single/multi dispatch, eval context includes log() writing to ir_logging, webhook field group restriction prevents data leakage, 4 ir.actions.server state types + ir_rule domain combination formula

## Deep Research Summary
- **Session 1 (6 modules):** stock, account, sale, purchase, mrp, crm
- **Session 2 (6 modules):** base, mail, project, website, payment, hr, ir_actions
- **Total deep researched:** 12 modules

## Summary
- **Total module docs:** 584 files
- **Full docs:** 29 modules
- **Deep researched:** 12 modules (2 full passes)
- **Stubs:** 555 modules
- **Core docs:** 15 files
- **Business guides:** 4 files
- **Flows:** 3 files
