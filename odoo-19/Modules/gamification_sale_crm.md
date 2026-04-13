# gamification_sale_crm

> Gamification goals and challenges for CRM and sales performance tracking.

```yaml
category: Sales/CRM
depends: gamification, sale_crm
auto_install: true
license: LGPL-3
```

## Module Architecture

**This is a data-only module.** It contains zero Python model files (`__init__.py` is empty). Its entire purpose is to register records into the gamification framework's `gamification.goal.definition`, `gamification.challenge`, and `gamification.challenge.line` models via XML data files. The actual computation logic lives in the `gamification` base module.

```
gamification_sale_crm/
├── __init__.py           # Empty (no Python code)
├── __manifest__.py        # Depends declaration and data files
├── data/
│   ├── gamification_sale_crm_data.xml     # Challenge state = inprogress (post-install)
│   └── gamification_sale_crm_demo.xml      # All goal definitions + challenge structure
└── i18n/                  # 50+ language translations
```

### Dependency Chain

```
gamification_sale_crm
    ├── gamification       (challenges, goals, badges, karma tracking)
    │       └── base
    └── sale_crm           (crm_lead extensions, sale_order linking)
            ├── crm
            │       └── base
            └── sale
                    └── account (via invoice_user_id on account.move)
```

### Module Philosophy

gamification_sale_crm bridges two worlds:
1. **[Modules/gamification](gamification.md)** — provides the goal/challenge/badge engine (scheduled goals, ranking, reporting, rewards)
2. **[Modules/CRM](CRM.md) + [Modules/Sale](Sale.md) + [Modules/Account](Account.md)** — provide the source-of-truth business records (leads, orders, invoices)

Without gamification_sale_crm, the gamification framework has no CRM-specific KPIs to score. Without gamification, sale_crm has no motivation layer.

---

## Goal Definitions (`gamification.goal.definition`)

All 10 definitions share these structural properties:

| Property | Value |
|---|---|
| `computation_mode` | `count` or `sum` (never `manually` or `python`) |
| `batch_mode` | `True` — all use batch mode for performance |
| `batch_distinctive_field` | User-bucketing field (e.g. `invoice_user_id`, `user_id`) |
| `batch_user_expression` | `user.id` — compares current user ID to bucket value |
| `display_mode` | `progress` (default) — not overridden anywhere |
| `condition` | `higher` (higher is better) or `lower` (lower is better) |
| `challenge_category` | Not set here (inherited from challenge) |

### L3: Batch Mode Internals

Batch mode is the performance-critical path. The `gamification.goal.update_goal()` method groups all goals by their `definition_id`, then for each unique `(start_date, end_date)` pair builds a single `read_group` query that aggregates across **all users simultaneously**:

```python
# gamification/models/gamification_goal.py — simplified
subquery_domain = list(general_domain)
subquery_domain.append((field_name, 'in', list(set(query_goals.values()))))
# field_name = 'invoice_user_id' or 'user_id'
# query_goals = {goal_id: user_id_value, ...}

if definition.computation_mode == 'count':
    user_values = Obj._read_group(subquery_domain, groupby=[field_name], aggregates=['__count'])
else:  # sum
    user_values = Obj._read_group(subquery_domain, groupby=[field_name], aggregates=[f'{value_field_name}:sum'])
```

Without batch mode, each goal would trigger its own `search_count` or `read_group` query — a classic N+1 problem. With 50 salespersons and 10 goal definitions per challenge, batch mode collapses 500 queries into ~10.

---

### `definition_crm_tot_invoices` — Total Invoiced

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_tot_invoices` | `sum` | `higher` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `account.model_account_invoice_report` | PostgreSQL view on `account_move_line` |
| `field_id` | `account.field_account_invoice_report__price_subtotal` | Company-currency untaxed amount |
| `field_date_id` | `account.field_account_invoice_report__invoice_date` | Groups by invoice date, not line date |
| `domain` | `[('state','!=','cancel'),('move_type','=','out_invoice')]` | Excludes cancelled + vendor bills |
| `batch_distinctive_field` | `account.field_account_invoice_report__invoice_user_id` | Bucket by salesperson |
| `batch_user_expression` | `user.id` | |
| `monetary` | `True` | Displays currency symbol |
| `suffix` | Not set | Relies on monetary = True for unit display |

**L3 — Source Model Architecture:**

`account.invoice.report` (`_auto = False`) is a PostgreSQL view joining `account_move_line` → `account_move`. The `price_subtotal` column is computed as:

```sql
-line.balance * currency_rate   -- for out_invoice rows
```

This is always **positive** for `out_invoice` type moves because `balance` is negative for revenue lines. The `payment_state` field is read from `move.payment_state` (the parent move), not from individual lines.

**Edge Case — Cancelled Moves:**

`state != 'cancel'` uses the `state` column on `account_move`, which tracks the move's posting status. A cancelled draft move (never posted) has `state = 'cancel'`. However, if a move was posted and then cancelled (reversal), the reversal is a separate move with its own `state`. The original posted entry is typically reversed, so the net effect is clean. This domain correctly excludes both scenarios.

**L4 — Performance:**

`account.invoice.report` has `_auto = False` (manual SQL view definition via `account_invoice_report_view.xml`). The view rebuilds on module upgrade. It joins `account_move_line` with `display_type = 'product'` — non-product lines (taxes, receivable/payable) are excluded. For large invoice tables, the `invoice_date` index and `state`/`move_type` filter make this reasonably fast.

---

### `definition_crm_nbr_new_leads` — New Leads

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_nbr_new_leads` | `count` | `higher` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `crm.model_crm_lead` | Base CRM model |
| `field_date_id` | `crm.field_crm_lead__create_date` | Search expression: `[('model','=','crm.lead'),('name','=','create_date')]` |
| `domain` | `['|', ('type', '=', 'lead'), ('type', '=', 'opportunity')]` | Both lead and opportunity types |
| `batch_distinctive_field` | `crm.field_crm_lead__user_id` | Bucket by responsible user |
| `suffix` | `leads` | Display unit |

**L3 — Domain Design Rationale:**

The domain uses `OR ('type', '=', 'lead') OR ('type', '=', 'opportunity')` — **not** `(type, 'in', ['lead', 'opportunity'])`. The comment in the XML clarifies: "lead AND opportunity as don't want to be penalised for lead converted to opportunity." Using `OR` means a converted lead/opportunity counts as **one** record, not zero (if only matched on 'opportunity').

If it were `(type, 'in', ['lead', 'opportunity'])`, a lead that gets converted to an opportunity would appear **twice** (once as lead, once as opportunity), double-counting the salesperson's pipeline volume.

**L4 — Date Field via Search Expression:**

`field_date_id` uses a search expression instead of a direct `ref` to `crm.field_crm_lead__create_date`. This is unusual — most other definitions use a direct external ID reference. The search expression finds the field record at runtime, which works but is slightly slower than a direct reference. It may exist because the exact external ID of `create_date` could vary across localization modules.

---

### `definition_crm_lead_delay_open` — Time to Qualify a Lead

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_lead_delay_open` | `sum` | `lower` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `crm.model_crm_lead` | |
| `field_id` | `crm.field_crm_lead__day_close` | Note: uses `day_close` (not `day_open`) |
| `field_date_id` | `crm.field_crm_lead__date_closed` | Date filter is close date |
| `domain` | `[('type', '=', 'lead')]` | Lead type only |
| `batch_distinctive_field` | `crm.field_crm_lead__user_id` | |
| `suffix` | `days` | |
| `condition` | `lower` | Fewer days = better |

**L3 — `day_close` on Lead Type (Not Opportunity):**

`crm.lead.day_close` is computed by `_compute_day_close`:

```python
@api.depends('create_date', 'date_closed')
def _compute_day_close(self):
    for lead in self:
        if lead.date_closed and lead.create_date:
            lead.day_close = abs((lead.date_closed - lead.create_date).days)
        else:
            lead.day_close = None
```

For a **lead** that never gets converted (stays as `type = 'lead'`), `date_closed` is set when the lead is archived or marked as lost. The goal measures how long a lead remained open before being qualified/closed.

**L4 — `condition = lower` + `completeness` Edge Case:**

In `gamification.goal._get_completion()`, for `condition = 'lower'`:

```python
if goal.current < goal.target_goal:
    goal.completeness = 100.0   # reached
else:
    goal.completeness = 0.0     # not reached
```

For `lower` goals, **completeness is binary** — either 0% or 100%. The goal is either "Time to Qualify is under 15 days" (reached) or not. There is no gradient. This means a salesperson who took 14 days is treated the same as one who took 1 day. This is a known design limitation of the gamification framework.

---

### `definition_crm_lead_delay_close` — Days to Close a Deal

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_lead_delay_close` | `sum` | `lower` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `crm.model_crm_lead` | |
| `field_id` | `crm.field_crm_lead__day_open` | Uses `day_open`, not `day_close` |
| `field_date_id` | `crm.field_crm_lead__date_open` | Date filter is open date |
| `domain` | `[]` | Empty domain — all records |
| `batch_distinctive_field` | `crm.field_crm_lead__user_id` | |
| `suffix` | `days` | |
| `condition` | `lower` | |

**L3 — `day_open` vs `day_close` Confusion:**

This definition sums `day_open` (days from creation to assignment) but names the goal "Days to Close a Deal" and filters with an empty domain (all `crm.lead` records). For **opportunities**, `day_open` measures the time from creation to when the opportunity was first assigned to a user. This is a measure of lead response time, not close time.

The empty domain `[]` includes both leads and opportunities. For leads that haven't been assigned (no `date_open` set), `day_open` is `None` and those records contribute nothing to the `SUM()`. This effectively filters to only assigned records — leads/opportunities that have been worked.

**L4 — `SUM()` of Days for a Count Goal:**

This definition uses `computation_mode = 'sum'` but `field_id = day_open` (a float field representing a single integer per record). The batch query will `SUM(day_open)` across all matching records, giving the **total** days taken by a salesperson to open all assigned opportunities. A salesperson who opened 10 opportunities averaging 5 days each would score 50. The target of `15` in the challenge would mean "total of 15 days" for the month — an extremely low threshold for multiple opportunities.

This seems to assume that `SUM(day_open)` with `computation_mode = 'sum'` would compute an **average** — but it does not. The actual value is the arithmetic sum of all `day_open` values for the period. This is a potential **semantic mismatch** between the challenge name ("Days to Close a Deal" suggesting an average) and the technical implementation (total sum). The `condition = lower` rewards lower totals, so in practice this means "fewer total days spent in 'opening' phase across all opportunities."

---

### `definition_crm_nbr_new_opportunities` — New Opportunities

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_nbr_new_opportunities` | `count` | `higher` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `crm.model_crm_lead` | |
| `field_date_id` | `crm.field_crm_lead__date_open` | Based on **opening date**, not creation |
| `domain` | `[('type','=','opportunity')]` | Opportunity type only |
| `batch_distinctive_field` | `crm.field_crm_lead__user_id` | |
| `suffix` | `opportunities` | |

**L3 — `date_open` as the Date of Record:**

Unlike `definition_crm_nbr_new_leads` which uses `create_date`, this uses `date_open` — the assignment date. A lead created in January but assigned in February would not count for January's opportunity goal, but would for February's. This is intentional: "new opportunities" measures when a lead is **worked**, not when it arrived.

`crm.lead.date_open` is a computed/stored field:

```python
date_open = fields.Datetime('Assignment Date', compute='_compute_date_open', readonly=True, store=True)
```

It is set when the `user_id` is first assigned (stage assignment trigger). It is **not** updated on subsequent user reassignments — so it truly represents the "first assignment date."

---

### `definition_crm_nbr_sale_order_created` — New Sales Orders

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_nbr_sale_order_created` | `count` | `higher` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `sale.model_sale_order` | |
| `field_date_id` | `sale.field_sale_order__date_order` | Order confirmation date |
| `domain` | `[('state','not in',('draft', 'sent', 'cancel'))]` | Confirmed orders only |
| `batch_distinctive_field` | `sale.field_sale_order__user_id` | |
| `suffix` | `orders` | |

**L3 — State Filter Deep Dive:**

The domain `[('state','not in',('draft', 'sent', 'cancel'))]` includes `sale_order` states: `sale` (confirmed), `done` (locked), and potentially `pos_order` linked states. The `sale_crm` module links opportunities to sale orders via `crm_lead.order_ids`. A salesperson's `user_id` on the sale order determines attribution.

**Edge Case — Orders from Opportunities:**

When a quotation is confirmed from an opportunity, the sale order inherits the `user_id` from the opportunity's responsible salesperson (via `sale_crm._prepare_opportunity_quotation_context()`). If a manager confirms a subordinate's quotation, the order is still attributed to the subordinate (the opportunity owner), which is correct for gamification purposes.

---

### `definition_crm_nbr_paid_sale_order` — Paid Sales Orders

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_nbr_paid_sale_order` | `count` | `higher` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `account.model_account_invoice_report` | |
| `field_date_id` | `account.field_account_invoice_report__invoice_date` | Invoice date, not payment date |
| `domain` | `[('payment_state','in',('paid', 'in_payment')),('move_type','=','out_invoice')]` | |
| `batch_distinctive_field` | `account.field_account_invoice_report__invoice_user_id` | |
| `suffix` | `orders` | |

**L3 — `payment_state` as the Payment Proxy:**

`payment_state` on `account.move` reflects the invoice-level payment status. Valid values (in Odoo 19) include: `not_paid`, `in_payment`, `paid`, `partial`, `reversed`, `invoicing_legacy`. Including both `'paid'` and `'in_payment'` is important because `in_payment` is a **transitional state** — an invoice moves from `not_paid` → `in_payment` → `paid` during the payment process. An invoice that is mid-payment on the goal-computation date would be counted correctly.

**L4 — `invoice_date` vs Payment Date:**

The goal uses `invoice_date` (not the payment date) as the date filter. This means a December 2025 invoice paid in February 2026 still counts toward the December challenge goal. This is correct for revenue-recognition purposes but may feel counterintuitive — a salesperson is credited at invoice issuance, not at cash receipt.

---

### `definition_crm_tot_paid_sale_order` — Total Paid Sales Orders

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_tot_paid_sale_order` | `count` | `higher` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `account.model_account_invoice_report` | |
| `field_id` | `account.field_account_invoice_report__price_subtotal` | |
| `field_date_id` | `account.field_account_invoice_report__invoice_date` | |
| `domain` | `[('payment_state','in',('paid', 'in_payment')),('move_type','=','out_invoice')]` | Same as count variant |
| `batch_distinctive_field` | `account.field_account_invoice_report__invoice_user_id` | |
| `monetary` | `True` | |

**Bug/Design Issue — `computation_mode = 'count'` Instead of `'sum'`:**

This definition has `computation_mode = 'count'` in the XML but is meant to compute a **sum** (total monetary value). For `count` mode, `update_goal()` calls `Obj._read_group(..., aggregates=['__count'])` — it counts records, ignoring `field_id` entirely. This goal will count the number of paid invoices, not their total value.

This is a **confirmed bug**: the `computation_mode` should be `'sum'`, not `'count'`. The monetary field, `price_subtotal`, and the goal name all indicate a sum should be computed. The sibling definition `definition_crm_tot_invoices` correctly uses `sum`, but this one does not. In practice, the goal will show a count of paid invoices rather than total paid revenue.

---

### `definition_crm_nbr_customer_refunds` — Customer Credit Notes

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_nbr_customer_refunds` | `count` | `lower` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `account.model_account_invoice_report` | |
| `field_date_id` | `account.field_account_invoice_report__invoice_date` | |
| `domain` | `[('state','!=','cancel'),('move_type','=','out_refund')]` | Cancelled refunds excluded |
| `batch_distinctive_field` | `account.field_account_invoice_report__invoice_user_id` | |
| `suffix` | `invoices` | |
| `condition` | `lower` | Fewer refunds = better |

**L3 — `out_refund` Attribution:**

Customer credit notes in Odoo 19 have `move_type = 'out_refund'`. The `invoice_user_id` on a credit note is typically set from the original invoice's `invoice_user_id`. This links the refund back to the original salesperson. This is the correct attribution model for "who generated the most refunds."

---

### `definition_crm_tot_customer_refunds` — Total Customer Credit Notes

| XML ID | Computation Mode | Condition |
|---|---|---|
| `definition_crm_tot_customer_refunds` | `sum` | `higher` |

**Fields:**

| Field | Value | Notes |
|---|---|---|
| `model_id` | `account.model_account_invoice_report` | |
| `field_id` | `account.field_account_invoice_report__price_subtotal` | |
| `field_date_id` | `account.field_account_invoice_report__invoice_date` | |
| `domain` | `[('state','!=','cancel'),('move_type','=','out_refund')]` | Same domain as count variant |
| `batch_distinctive_field` | `account.field_account_invoice_report__invoice_user_id` | |
| `monetary` | `True` | |
| `condition` | `higher` | |

**L4 — Sign Confusion on Credit Note Amounts:**

This definition has a **logical sign issue** in Odoo 19. The `account.invoice.report` SQL computes `price_subtotal` for `out_refund` as:

```sql
line.price_subtotal * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
```

For `out_refund`, `price_subtotal` is **negative** (the line amount is negated). With `condition = 'higher'`, the goal rewards the salesperson with the **most negative sum** — i.e., the highest magnitude of refunds. This is the **inverse** of what the description says: "The total credit note value is negative. Validated when higher (min credit note value)." The description acknowledges the negative value but incorrectly concludes that `higher` means "better" when in this context it actually rewards worse performance.

The companion `definition_crm_nbr_customer_refunds` uses `condition = 'lower'` (fewer refunds is better), which is correct. The `condition = 'higher'` on the sum variant contradicts the count variant's logic. The description appears to have been written by someone who confused the database sign with the semantic direction.

---

## Challenges (`gamification.challenge`)

### Challenge: Monthly Sales Targets (`challenge_crm_sale`)

| XML ID | State | Period | Visibility | Participants | Report Frequency |
|---|---|---|---|---|---|
| `challenge_crm_sale` | `inprogress` | `monthly` | `ranking` | `group_sale_salesman` | `weekly` |

**Participant Domain:**

```python
[('all_group_ids', 'in', [ref('sales_team.group_sale_salesman')])]
```

This uses `all_group_ids` (not `groups_id`) — a computed/concat field on `res.users` that aggregates all group memberships including inherited groups. This ensures that a user who indirectly has the salesman group (through a combined group that includes it) will be included.

**Goal Lines:**

| Line | Definition | Target |
|---|---|---|
| `line_crm_sale1` | `definition_crm_tot_invoices` | $20,000 |

Single-goal challenge. Only "Total Invoiced" is tracked. A salesperson is considered to have **succeeded** when `current >= 20,000` (USD or company currency).

**L3 — `state = inprogress` in Non-Demo Data:**

The `state` is set to `inprogress` in `gamification_sale_crm_data.xml` (non-demo, non-noupdate), which is loaded post-install. This means the Monthly Sales Targets challenge starts running immediately upon module installation. Goals are generated for all current `group_sale_salesman` members and will begin accumulating from the install date.

---

### Challenge: Lead Acquisition (`challenge_crm_marketing`)

| XML ID | State | Period | Visibility | Participants | Report Frequency |
|---|---|---|---|---|---|
| `challenge_crm_marketing` | `draft` (default) | `monthly` | `ranking` | `group_sale_salesman` | `weekly` |

**Goal Lines:**

| Line | Definition | Target | Sequence |
|---|---|---|---|
| `line_crm_marketing1` | `definition_crm_nbr_new_leads` | 7 | 1 |
| `line_crm_marketing2` | `definition_crm_lead_delay_open` | 15 days | 2 |
| `line_crm_marketing3` | `definition_crm_nbr_new_opportunities` | 5 | 3 |

Multi-goal challenge. A salesperson succeeds only when **all three** goals are reached simultaneously (`count == len(line_ids)` check in `_check_challenge_reward`). The `sequence` field on `challenge.line` controls display order in the UI.

**L3 — AND Logic on Goals:**

In `_check_challenge_reward()`, a user receives the challenge reward badge **only** if `count == len(challenge.line_ids)` — i.e., every single goal is in `reached` state. Partial success (2 of 3 goals) earns no badge. This is strict AND-logic, not a weighted score.

---

## Gamification Framework Integration

### Cron Job: `_cron_update()`

The gamification cron (`ir.cron.server` → `gamification.challenge._cron_update`) runs daily. It:

1. Starts any `draft` challenges whose `start_date <= today`
2. Closes any `inprogress` challenges whose `end_date < today`
3. Calls `_update_all()` for all in-progress challenges

**`_update_all()` performance path:**

```python
# Only update goals for active users with valid sessions
query = """
    SELECT gg.id FROM gamification_goal gg
    JOIN mail_presence mp ON mp.user_id = gg.user_id
    WHERE gg.write_date <= mp.last_presence
      AND mp.last_presence >= now() - interval 'session_lifetime seconds'
      AND gg.closed IS NOT TRUE
      AND gg.challenge_id IN ...
"""
```

Goals are only recalculated for users who are **currently active** in the web client. Idle users' goals are not recomputed until they log in. This prevents unnecessary computation but means that a user's goal values may lag behind reality for inactive users.

### Leaderboard Serialization

`challenge._get_serialized_challenge_lines()` produces the ranking data. For `visibility_mode = 'ranking'`, it returns top-N goals sorted by:

```python
goals.sorted(key=lambda goal: (
    -goal.completeness,
    -goal.current if line.condition == 'higher' else goal.current
))
```

Priority: (1) highest completeness, then (2) highest raw current value (for `higher`) or lowest (for `lower`). This means a user at 100% completeness always ranks above a user at 50%, regardless of absolute values.

---

## Odoo 18 → Odoo 19 Changes

| Area | Odoo 18 | Odoo 19 | Impact |
|---|---|---|---|
| `account.invoice` | Standalone model | Merged into `account.move` | `account.invoice.report` view still works; `invoice_user_id` moved to `account.move` |
| `payment_state` values | `'paid', 'partial'` | Added `'in_payment'` transitional state | Goals now include `in_payment` invoices — slightly broader reach |
| Gamification goal `remind_update_delay` | Days-based integer | Unchanged | |
| `mail_presence` session tracking | Basic | Enhanced with `SESSION_LIFETIME` | More accurate active-user filtering in `_update_all` |
| `challenge.user_domain` | Simple domain | Unchanged | Still uses `all_group_ids` for membership check |
| `computation_mode = 'sum'` on `price_subtotal` | Works | Unchanged | |

---

## Security Considerations

| Concern | Detail |
|---|---|
| **Leaderboard visibility** | `visibility_mode = 'ranking'` makes all participants' scores visible to all other participants. Any user in `group_sale_salesman` can see every other salesperson's invoiced amount and lead counts. This may be undesirable in some organizations. |
| **Challenge management** | Creating/editing challenges requires `gamification.challenge` write access. The `manager_id` field defaults to `env.uid` (the creator). |
| **Badge granting** | `_reward_user()` creates `gamification.badge.user` records. This requires `gamification.badge.user` create access. |
| **Report messages** | `report_progress()` posts to `mail.thread` on the challenge record and sends `mail.message` to participants. Requires `mail.group` membership for `report_message_group_id`. |
| **Demo data** | `gamification_sale_crm_demo.xml` loads with `noupdate="1"` — it will not overwrite existing records on upgrade but will install them on first setup. |

---

## Performance Profile

| Operation | Cost | Notes |
|---|---|---|
| Batch goal computation | ~1 query per definition per date range | 10 definitions = ~10 SQL queries per cron run |
| `_update_all()` session filter | 1 SQL query per challenge | Filters to only active web users |
| Leaderboard serialization | 1 `search()` + `sorted()` per challenge line | O(n log n) sort per line, n = participant count |
| `report_progress()` rendering | 1 `message_post()` or N `message_notify()` calls | Email delivery handled by `mail` module async queue |

The module's performance impact is dominated by the `account.invoice.report` view joins, not the gamification layer itself.

---

## Failure Modes and Edge Cases

| Failure Mode | Cause | Result |
|---|---|---|
| **Missing `invoice_user_id`** | Invoice created via backend without user assignment | Goal computation skips that invoice; salesperson loses credit |
| **`date_open` never set** | Opportunity created but never assigned | `day_open = None`, record excluded from `definition_crm_lead_delay_close` |
| **`date_closed` not set on leads** | Lead archived without explicit close | `day_close = None`, excluded from `definition_crm_lead_delay_open` sum |
| **Cancelled then re-invoiced** | Original invoice cancelled, new invoice created | Old invoice excluded (`state != 'cancel'`), new counted |
| **`computation_mode = 'count'` on sum goal** | Bug in `definition_crm_tot_paid_sale_order` | Shows count of invoices, not sum of amounts |
| **`condition = 'higher'` on negative refund sum** | Semantic bug in `definition_crm_tot_customer_refunds` | Rewards highest refund magnitude |
| **User removed from sales team group** | Admin changes group membership | `_recompute_challenge_users()` removes them; existing goals remain in DB with stale data |
| **Challenge period rolls over mid-goal** | Monthly challenge crosses month boundary | New goals created for new period; old goals remain with their period dates |
| **`account.invoice.report` view not refreshed** | `_auto = False` view needs manual refresh | View is recreated on module upgrade; intermediate data changes require DB rebuild |

---

## Related Models Summary

| Model | Role in gamification_sale_crm |
|---|---|
| `gamification.goal.definition` | 10 CRM/Sales KPI definitions registered here |
| `gamification.challenge` | 2 monthly challenges (Monthly Sales Targets, Lead Acquisition) |
| `gamification.challenge.line` | 4 goal-to-challenge bindings with targets |
| `gamification.goal` | Created automatically by challenge; stores per-user progress |
| `gamification.badge` / `gamification.badge.user` | Reward mechanism (not used in default data) |
| `crm.lead` | Source of lead counts, opportunity counts, and day metrics |
| `sale.order` | Source of confirmed order count |
| `account.move` | Underpins `account.invoice.report` view; provides `invoice_user_id`, `payment_state` |
| `account.invoice.report` | PostgreSQL view joining lines to moves; used for all invoice-based KPIs |
| `res.users` | Participants; goals attributed via `user_id` fields |

## See Also

- [Modules/gamification](gamification.md) — Base gamification framework (challenges, goals, badges, karma)
- [Modules/crm](CRM.md) — `crm.lead` model and pipeline management
- [Modules/Sale](Sale.md) — `sale.order` confirmation flow
- [Modules/Account](Account.md) — `account.move` and invoice reporting
- [Modules/sale_crm](sale_crm.md) — Links sale orders to CRM leads/opportunities
- [Modules/gamification](gamification.md) — HR-specific gamification goals
- [Modules/gamification](gamification.md) — Gamification overview module
