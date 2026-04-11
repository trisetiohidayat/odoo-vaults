# Research Backlog — Odoo 17

## Completed ✅
All Tier 1–3 modules fully documented and verified.

### Tier 1 — Foundation ✅
- base ✅ — 7 models, 522 lines
- mail ✅ — 9 models, message_post full flow
- ir_actions ✅ — 8 action types + ir_rule

### Tier 2 — Core Business ✅
- sale ✅ — 7-step action_confirm(), 814 lines
- purchase ✅ — 2-step confirmation, 684 lines
- stock ✅ — quant 5-tuple, button_validate() chain, 1,927 lines
- account ✅ — 12-step _post(), Union-Find, CABA, 1,175 lines
- product ✅ — 3 core models

### Tier 3 — Extended ✅
- crm ✅ — Naive Bayes scoring, round-robin
- project ✅ — recursive CTE subtasks, user_ids M2M
- hr ✅ — public live SQL view, coach promotion
- mrp ✅ — BOM explode, workorders, OEE

## Remaining Work

### Tier 4 — Ecosystem (partial)
- website ✅, website_sale ✅, website_studio ✅, website_sale_loyalty ✅
- payment ✅, sale_management ✅, purchase_requisition ✅
- calendar ✅, survey ✅, point_of_sale ✅, sale_loyalty ✅
- mass_mailing ✅, sms ✅, portal ✅

### Tier 5 — Integrations (partial)
- auth_totp ✅, auth_oauth ✅, auth_totp_mail ✅
- digest ✅, iap ✅, google_calendar ✅
- crm_iap_enrich ✅, iap_crm ✅, iap_mail ✅
- l10n_generic_coa ✅, l10n_us ✅, l10n_de ✅

### Tier 6 — Advanced (partial)
- mrp_subcontracting ✅, stock_account ✅, repair ✅
- project_account ✅, quality ✅, helpdesk ✅, sale_timesheet ✅
- stock_picking_type ✅, stock_warehouse ✅, stock_picking_batch ✅

## Gaps Found
- ~530 Tier 5/6 modules still stubs (l10n_*, payment_*, auth_*, etc.)
- Enterprise-only modules: quality, helpdesk — limited source available
