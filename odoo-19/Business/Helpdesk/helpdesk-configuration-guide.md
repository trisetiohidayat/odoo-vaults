---
type: guide
title: "Helpdesk Configuration Guide"
module: helpdesk
submodule: helpdesk
audience: business-consultant, support-manager, ai-reasoning
level: 2
prerequisites:
  - helpdesk_module_installed
  - helpdesk_teams_created
  - stages_configured
  - sla_policies_defined
  - email_aliases_set
estimated_time: "~20 minutes"
related_flows:
  - "[Flows/Helpdesk/ticket-creation-flow](Flows/Helpdesk/ticket-creation-flow.md)"
  - "[Flows/Helpdesk/ticket-resolution-flow](Flows/Helpdesk/ticket-resolution-flow.md)"
source_module: helpdesk
created: 2026-04-07
version: "1.0"
---

# Helpdesk Configuration Guide

> **Quick Summary:** Configure Odoo 19 Helpdesk teams, ticket stages, SLA policies, and email aliases so that incoming support tickets are routed correctly, SLAs are enforced, and customer ratings are collected automatically.

**Actor:** Helpdesk Manager, System Administrator
**Module:** Helpdesk
**Use Case:** End-to-end Helpdesk setup — from team creation to SLA monitoring
**Difficulty:** ⭐⭐ Medium

---

## Prerequisites Checklist

Before starting, ensure the following are configured. Skipping these will cause errors or missing features.

- [ ] **Helpdesk module installed** — Go to `Apps` → search `helpdesk` → install "Helpdesk" (base module)
- [ ] **Helpdesk Teams installed** — The base module includes team management; no extra install needed
- [ ] **SLA Policies** — Install `helpdesk` with SLA feature (included; controlled by `use_sla` flag)
- [ ] **Customer Ratings** — Install rating feature (included; controlled by `use_rating` flag)
- [ ] **Email domain configured** — `Settings → General Settings → Email Alias Domain` set
- [ ] **Working Hours set** — `Settings → Discuss → Working Hours` configured (used for SLA deadline computation)
- [ ] **Users added to Helpdesk groups** — `Settings → Users` → assign `Helpdesk / User` or `Helpdesk / Manager`

> **⚠️ Critical:** If `Working Hours` are not set on the company, SLA deadlines will use 8 hours/day by default, leading to incorrect deadline calculations. Always configure `resource.calendar` on the team.

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Helpdesk/ticket-creation-flow](Flows/Helpdesk/ticket-creation-flow.md) | Full method chain from ticket create to SLA application |
| 🔀 Technical Flow | [Flows/Helpdesk/ticket-resolution-flow](Flows/Helpdesk/ticket-resolution-flow.md) | Ticket close, rating, reopen, and escalate |
| 📖 Module Reference | [Modules/Helpdesk](Modules/helpdesk.md) | Complete field and method reference |
| 🔧 Patterns | [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) | State machine and workflow design |

---

## Use Cases Covered

This guide covers the following use cases. Jump to the relevant section:

| # | Use Case | Page | Difficulty |
|---|----------|------|-----------|
| 1 | Create a team and configure stages | [#use-case-a-create-a-team-and-configure-stages](#use-case-a-create-a-team-and-configure-stages.md) | ⭐ |
| 2 | Create a ticket and assign it | [#use-case-b-create-a-ticket-and-assign-it](#use-case-b-create-a-ticket-and-assign-it.md) | ⭐ |
| 3 | Handle an SLA breach | [#use-case-c-handle-an-sla-breach](#use-case-c-handle-an-sla-breach.md) | ⭐⭐ |
| 4 | Configure SLA policies | [#use-case-d-configure-sla-policies](#use-case-d-configure-sla-policies.md) | ⭐⭐ |
| 5 | Set up customer ratings | [#use-case-e-set-up-customer-ratings](#use-case-e-set-up-customer-ratings.md) | ⭐⭐ |

---

## Use Case A: Create a Team and Configure Stages

### Scenario

The support manager needs to create a dedicated "Tier-1 Support" team with four custom stages: New, In Progress, Waiting, and Solved. Each stage needs to control ticket flow and email notifications.

### Steps

#### Step 1 — Navigate to Helpdesk Teams

Go to: `Helpdesk → Configuration → Teams`

Click **[Create]**.

> **⚡ System Behavior:** The team creation form opens. Default stages are pre-populated (New, In Progress, Solved, Cancelled) from the XML data loaded during module installation.

#### Step 2 — Fill Team Basic Information

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Team Name** | Tier-1 Support | ✅ Yes | — |
| **Company** | Your Company | ✅ Yes | Default from Settings |
| **Privacy Visibility** | All Internal Users | No | Default: Portal |
| **Email Alias** | tier1-support | No | Auto-generated from name |

> **⚡ System Trigger:** When `Email Alias` is enabled (`use_alias = True`), Odoo creates an incoming email gateway. Emails sent to `{alias_name}@{alias_domain}` automatically create `helpdesk.ticket` records. See [Flows/Helpdesk/ticket-creation-flow](Flows/Helpdesk/ticket-creation-flow.md) for the `message_new()` flow.

#### Step 3 — Configure Team Members

Go to the **Team Members** tab.

Click **Add** and select users from the list.

| Field | Value | Notes |
|-------|-------|-------|
| **Member** | John Agent, Jane Agent | At least one member required |
| **Assignment Method** | Balanced | Balances open ticket count |

> **⚡ System Trigger:** When `Automatic Assignment` is enabled, Odoo auto-assigns new tickets to the member with the fewest open tickets (balanced) or uses round-robin (randomly). This calls `team._determine_user_to_assign()` on ticket creation. See [Flows/Helpdesk/ticket-creation-flow#step-5](Flows/Helpdesk/ticket-creation-flow#step-5.md).

#### Step 4 — Configure Stages

Go to the **Stages** tab.

Stages control the ticket lifecycle. Default stages are already created:

| Stage Name | Sequence | Folded (Closed) | Template Email | Purpose |
|-----------|----------|----------------|---------------|---------|
| New | 0 | No | New Ticket Email | Entry point |
| In Progress | 1 | No | — | Active work |
| Waiting | 2 | No | — | Awaiting customer |
| Solved | 3 | **Yes** | Solution Email | Resolution |
| Cancelled | 4 | Yes | — | Cancelled |

To add a new stage:
Click **Add** in the Stages tab.

| Field | Value | Notes |
|-------|-------|-------|
| **Stage Name** | Escalated | Required |
| **Sequence** | 5 | Determines order in Kanban |
| **Folded** | No | Set to Yes only for final closed states |
| **Template Email** | Escalation Template | Email sent when ticket enters this stage |

> **⚡ System Trigger:** When a ticket moves to a **folded stage** (`fold = True`), Odoo sets `close_date = now` and marks SLAs as reached. See [Flows/Helpdesk/ticket-resolution-flow#path-a](Flows/Helpdesk/ticket-resolution-flow#path-a.md).

> **⚡ Side Effect:** The `Template Email` field links to `email.template`. When a stage change occurs, `ticket._track_template({'stage_id'})` renders and queues this template for delivery to followers.

#### Step 5 — Set Working Hours (Required for SLA)

Go to **Working Hours** field on the team form.

Click **Edit** and configure the working calendar.

| Field | Value | Notes |
|-------|-------|-------|
| **Working Hours** | Mon-Fri 08:00-18:00 | Used for SLA deadline |
| **Company** | Your Company | Inherited from company or overridden |

> **⚡ System Trigger:** The working calendar is used by `helpdesk.sla.status._compute_deadline()` to compute SLA deadlines in business hours, not wall-clock hours. For example, a 1-day SLA created at 17:00 on Friday expires at 17:00 on Monday (not Saturday).

#### Step 6 — Save and Verify

Click **Save**.

**Expected Results Checklist:**
- [ ] Team appears in **Helpdesk → Teams** list
- [ ] Email alias `{alias_name}@{alias_domain}` is active
- [ ] Members can see team tickets in **Helpdesk → Tickets**
- [ ] Kanban view shows correct stage columns
- [ ] Dashboard shows team statistics under **Helpdesk → Dashboard**

---

## Use Case B: Create a Ticket and Assign It

### Scenario

An agent receives an email from a customer about a billing issue and needs to manually create a ticket, assign it to the correct team, and ensure the SLA policy is applied.

### Steps

#### Step 1 — Create a Ticket Manually

Navigate to: `Helpdesk → Tickets → Create`

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Subject** | Billing error on Invoice #1234 | ✅ Yes | — |
| **Team** | Tier-1 Support | ✅ Yes | Default from user's team |
| **Customer** | Acme Corp (partner) | No | — |
| **Customer Email** | billing@acme.com | No | Auto-filled from partner |
| **Priority** | High (2) | No | Default: Low (0) |
| **Ticket Type** | Billing | No | Categorization |

> **⚡ System Trigger:** When **Customer** (partner) is selected, `_compute_partner_email()` and `_compute_partner_phone()` auto-fill email and phone from the partner record. See [Flows/Helpdesk/ticket-creation-flow#step-7](Flows/Helpdesk/ticket-creation-flow#step-7.md).

> **⚡ System Trigger:** When **Team** is selected, `_compute_user_and_stage_ids()` fires, which calls `team._determine_stage()` (sets initial stage to "New") and `team._determine_user_to_assign()` (assigns to least-loaded member). See [Flows/Helpdesk/ticket-creation-flow#steps-4-5](Flows/Helpdesk/ticket-creation-flow#steps-4-5.md).

#### Step 2 — Verify Auto-Assignment

After saving, check the ticket form:

| Field | Value | Notes |
|-------|-------|-------|
| **Stage** | New | From team's first stage |
| **Assigned to** | John Agent | Based on balanced assignment |
| **Ticket Ref** | 00045 | Auto-generated sequence |

> **⚡ Side Effect:** On save, `helpdesk.ticket.create()` also:
> - Creates `helpdesk.sla.status` records for each matching SLA policy
> - Sets `assign_date = now` and `assign_hours = 0`
> - Subscribes the customer (`message_subscribe`) so they receive updates
> - Posts a "New ticket" message in the chatter

#### Step 3 — Manually Reassign if Needed

If the auto-assignment is incorrect:

Click **Assign To Me** button (shown only if `user_id` is empty).

Or: Edit the **Assigned to** field directly.

> **⚡ System Trigger:** Changing `user_id` via `write({'user_id': uid})` triggers `message_subscribe(uid)` to add the new assignee as a follower. See [Flows/Helpdesk/ticket-creation-flow#step-7](Flows/Helpdesk/ticket-creation-flow#step-7.md).

#### Step 4 — Change Stage (Kanban or Form)

Drag the ticket card in Kanban to the "In Progress" column.

Or: Edit the **Stage** dropdown on the ticket form.

> **⚡ System Trigger:** Stage change triggers `_track_template({'stage_id'})`. If the new stage has an email template, it is rendered and sent. See [Flows/Helpdesk/ticket-creation-flow#track-template](Flows/Helpdesk/ticket-creation-flow#track-template.md).

---

## Use Case C: Handle an SLA Breach

### Scenario

A "High Priority" ticket has been in the "New" stage for longer than its 2-hour SLA deadline. The manager needs to identify the breached ticket, reassign it, and escalate it.

### Steps

#### Step 1 — Identify SLA Breaches

Navigate to: `Helpdesk → Dashboard`

Look at the **Failed SLA Ticket** counter on the team card.

Or: Use the search filter:
Go to: `Helpdesk → Tickets → Filters → Failed SLA`

> **⚡ System Behavior:** Tickets with `sla_fail = True` are those where `sla_deadline < now` or `sla_reached_late = True` (SLA deadline was missed). The `sla_fail` field is computed via `_compute_sla_fail()` in `helpdesk.ticket`. See [Flows/Helpdesk/ticket-creation-flow#sla-status](Flows/Helpdesk/ticket-creation-flow#sla-status.md).

#### Step 2 — View SLA Details on a Ticket

Open a breached ticket.

Scroll to the **SLA Status** smart button (or the **SLA Deadline** field on the form).

| Field | Value | What It Means |
|-------|-------|---------------|
| **SLA Policy** | High Priority - 2h | Policy name |
| **Deadline** | 2026-04-07 10:00 | Must solve by this time |
| **Status** | Failed | Deadline already passed |
| **Exceeded Hours** | +1.5h | How much past deadline |

#### Step 3 — Escalate the Ticket

Click the **Escalate** button on the ticket form (visible to Helpdesk Managers).

| Field | Value | Notes |
|-------|-------|-------|
| **Priority** | Bumped up by 1 level | 1→2, 2→3 |
| **Team** | Changed to escalation team | If configured |

> **⚡ System Trigger:** `action_escalate()` writes `priority` bump and optionally changes `team_id`. It then calls `_sla_apply()` to recompute SLA deadlines for the new team and priority. See [Flows/Helpdesk/ticket-resolution-flow#path-e](Flows/Helpdesk/ticket-resolution-flow#path-e.md).

#### Step 4 — Manually Override SLA Deadline (Optional)

For special cases, an admin can manually update the SLA status:

Go to: `Helpdesk → Tickets → [Open Ticket] → SLA Status` tab.

Find the relevant SLA line and click **Edit**.

| Field | Override Value | Caution |
|-------|--------------|---------|
| **Deadline** | Set a new future date | Manual override; not recommended |
| **Reached Date** | Set to now | Marks SLA as reached at this moment |

> **⚠️ Critical:** Manually setting `reached_datetime` changes the SLA status from "failed" to "reached" and removes the ticket from the breach list. Use only for legitimate exceptions.

---

## Use Case D: Configure SLA Policies

### Scenario

The support manager wants to define SLA policies: 4 hours for High priority, 8 hours for Medium, and 24 hours for Low. Each SLA should start counting from the "New" stage.

### Steps

#### Step 1 — Enable SLA on the Team

Go to: `Helpdesk → Configuration → Teams → [Your Team]`

Check **SLA Policies** (`use_sla = True`).

Click **Save**.

> **⚡ System Trigger:** Enabling `use_sla` automatically assigns `helpdesk.group_use_sla` to all users in the `helpdesk.group_helpdesk_user` group. It also activates the SLA-related fields on ticket forms.

#### Step 2 — Create SLA Policies

Go to: `Helpdesk → Configuration → SLA Policies → Create`

Create three SLA policies:

**Policy 1: Critical (4 hours)**

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | Critical - 4h Response | Display name |
| **Team** | Tier-1 Support | Applies to this team only |
| **Priority** | Urgent (3) | Matches ticket priority '3' |
| **Time** | 4 | Hours to deadline |
| **Stage** | New | SLA counted from this stage |
| **Exclude Stages** | Solved, Cancelled | Pauses SLA while ticket in these stages |

**Policy 2: High Priority (8 hours)**

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | High - 8h Response | Display name |
| **Team** | Tier-1 Support | Applies to this team only |
| **Priority** | High (2) | Matches ticket priority '2' |
| **Time** | 8 | Hours to deadline |
| **Stage** | New | SLA counted from this stage |

**Policy 3: Standard (24 hours)**

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | Standard - 24h Response | Display name |
| **Team** | Tier-1 Support | Applies to this team only |
| **Priority** | Low (0), Medium (1) | Matches all lower priorities |
| **Time** | 24 | Hours to deadline |
| **Stage** | New | SLA counted from this stage |

> **⚡ System Trigger:** When a ticket is created with a given priority, `helpdesk.ticket._sla_find()` searches for matching policies where `team_id`, `priority`, and `stage_id.sequence` all match. The matched SLAs are then linked via `helpdesk.sla.status`. See [Flows/Helpdesk/ticket-creation-flow#step-9](Flows/Helpdesk/ticket-creation-flow#step-9.md).

#### Step 3 — Configure Working Hours for SLA Accuracy

Go to: `Helpdesk → Configuration → Teams → [Your Team] → Working Hours`

Set the calendar to match your support hours (e.g., 24/7 or Mon-Fri 9-17).

> **⚡ Side Effect:** The `resource.calendar` is used to compute `helpdesk.sla.status.deadline` as `create_date + working_hours`. A 4-hour SLA starting at 16:00 with a 9-17 calendar will expire at 12:00 the next working day.

#### Step 4 — Verify SLA Application

Create a test ticket with High priority.

Open the ticket and check the **SLA Status** smart button.

Expected: One SLA status record with deadline = `create_date + 8 working hours`.

---

## Use Case E: Set Up Customer Ratings

### Scenario

The support manager wants to automatically send a satisfaction survey to customers when a ticket is solved. Poor ratings (below 3/5) should trigger a notification to the manager.

### Steps

#### Step 1 — Enable Ratings on the Team

Go to: `Helpdesk → Configuration → Teams → [Your Team]`

Check **Customer Ratings** (`use_rating = True`).

> **⚡ System Trigger:** Enabling `use_rating` assigns `helpdesk.group_use_rating` to all team members. Rating-related fields appear on ticket forms.

#### Step 2 — Configure Rating Settings

On the same team form:

| Field | Value | Notes |
|-------|-------|-------|
| **Customer Ratings** | ✅ Enabled | Required to send surveys |
| **Portal Show Rating** | ✅ Enabled | Shows ratings on website |
| **Rating Satisfaction Days** | 7 | Avg computed from last 7 days |

#### Step 3 — Verify Rating Template

When a ticket moves to the Solved stage, Odoo automatically calls `rating.rating.rating_request()` which sends the rating email using the default template.

Check the template: `Helpdesk → Configuration → Email Templates → Rating Request`

| Field | Value |
|-------|-------|
| **Model** | helpdesk.ticket |
| **Subject** | Rate your experience — {{ object.number }} |
| **Template** | 5-star rating form link |

> **⚡ System Trigger:** When the ticket moves to a folded (solved) stage, `rating_parent_mixin._rating_apply()` creates `rating.rating` records for the ticket. The customer receives an email with a unique portal link. See [Flows/Helpdesk/ticket-resolution-flow#path-b](Flows/Helpdesk/ticket-resolution-flow#path-b.md).

#### Step 4 — Monitor Ratings

Go to: `Helpdesk → Reporting → Customer Satisfaction`

View:
- Average rating (last 7 days)
- Rating distribution (1-5 stars)
- Per-team breakdown

| Rating | Action |
|--------|--------|
| 5/5 (Excellent) | No action needed |
| 3-4/5 (Good) | Monitor trend |
| 1-2/5 (Poor) | `kanban_state = blocked` → Manager notified |

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Not setting working hours on team | SLA deadlines computed as 8h/day regardless of actual schedule | Always configure `resource.calendar_id` on the team |
| 2 | Forgetting to enable `use_sla` on team | No SLA policies applied to tickets | Check the SLA Policies checkbox on the team form |
| 3 | Stage sequence gaps | SLA policies don't match correctly | Ensure stage sequence numbers are contiguous |
| 4 | Wrong email alias domain | Email-to-ticket not working | Set `base_setup.default_external_email_server` or alias domain |
| 5 | Portal users can't see tickets | Privacy visibility set to "Invited internal users" | Change to "Portal" or "All internal users" |
| 6 | Rating email not sent | Team `use_rating` disabled | Enable Customer Ratings on the team |
| 7 | SLA not resetting on priority change | Old SLA deadline still shown | Changing priority triggers `_sla_apply()` automatically |
| 8 | Auto-close cron not running | Tickets auto-close after N days but cron may be disabled | Check `ir_cron_auto_close_ticket` is active in `Settings → Technical → Scheduled Actions` |
| 9 | Duplicate ticket creation from email | Same email creates multiple tickets | Odoo deduplicates by `Message-ID` header in `mail.message` |

---

## Configuration Deep Dive

### Related Configuration Paths

| Configuration | Menu Path | Controls |
|--------------|-----------|----------|
| Email Alias Domain | Settings → General → Email Alias Domain | Email gateway subdomain |
| Working Hours | Settings → Discuss → Working Hours | Default calendar for all teams |
| SLA Groups | Settings → Users → Helpdesk / SLA | Who can see SLA fields |
| Rating Groups | Settings → Users → Helpdesk / Rating | Who can see rating fields |
| Auto-close Cron | Settings → Technical → Scheduled Actions → Auto-close Tickets | Inactivity period for auto-close |
| Email Templates | Helpdesk → Configuration → Email Templates | Notification content |

### Advanced Options

| Option | Field Name | Default | Effect When Enabled |
|--------|-----------|---------|-------------------|
| Auto Assignment | `helpdesk.team.auto_assignment` | False | New tickets auto-assigned to team members |
| Balanced Assignment | `helpdesk.team.assign_method` | randomly | Assigns to member with fewest open tickets |
| Closure by Customers | `helpdesk.team.allow_portal_ticket_closing` | False | Customers can close tickets from portal |
| Auto-close Inactive | `helpdesk.team.auto_close_ticket` | False | Tickets auto-close after `auto_close_day` inactivity |
| Show Ratings on Portal | `helpdesk.team.portal_show_rating` | False | Public access to team rating stats |
| SLA Exclude Stages | `helpdesk.sla.exclude_stage_ids` | None | SLA timer pauses while ticket in excluded stages |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|---------|
| SLA not applied to new ticket | `use_sla = False` on team | Go to team → check "SLA Policies" |
| Email alias not creating tickets | Wrong alias domain or firewall | Verify alias in `Helpdesk → Configuration → Teams → Alias`; test with `echo "test" \| mail -s "Test" alias@domain` |
| Rating email not sent | `use_rating = False` on team | Enable "Customer Ratings" on team |
| Auto-assignment not working | `auto_assignment` not enabled on team | Check `Helpdesk → Configuration → Teams → [Team] → Auto Assignment` |
| Ticket stuck in wrong stage | Stage not in team's stage list | Add stage to team in team's Stages tab |
| SLA deadline wrong | Wrong working hours calendar | Update `resource.calendar_id` on the team |
| Manager not notified of bad rating | No `_notify_bad_rating()` override | Implement override in custom module |
| Customer cannot access ticket in portal | Privacy visibility = "Invited internal users" | Change to "Portal" or "All internal users" |
| Kanban shows no columns | Stages not assigned to team | Go to team → Stages tab → add all stages |
| Duplicate tickets from email | Email re-sent or retried | Message-ID deduplication prevents most duplicates; check mail gateway logs |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Helpdesk/ticket-creation-flow](Flows/Helpdesk/ticket-creation-flow.md) | Full method chain — for developers |
| 🔀 Technical Flow | [Flows/Helpdesk/ticket-resolution-flow](Flows/Helpdesk/ticket-resolution-flow.md) | Ticket close, rating, and reopen — for developers |
| 📖 Module Reference | [Modules/Helpdesk](Modules/helpdesk.md) | Complete field and method list |
| 🔧 Patterns | [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) | Workflow design patterns |
| 🛠️ Snippets | [Snippets/Model Snippets](Snippets/Model Snippets.md) | Code snippets for customization |
