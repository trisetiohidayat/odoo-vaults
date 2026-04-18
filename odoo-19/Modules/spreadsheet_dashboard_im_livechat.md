---
tags: [odoo, odoo19, spreadsheet, dashboard, livechat, im_livechat, website, customer-service]
---

# spreadsheet_dashboard_im_livechat

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_im_livechat` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `im_livechat` |
| Auto-install trigger | `im_livechat` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides two pre-configured [spreadsheet_dashboard](spreadsheet_dashboard.md) templates for customer service managers: a historical "Live Chat" performance dashboard and a real-time "Live Chat - Ongoing Sessions" dashboard. Both auto-install when `im_livechat` is active and are placed in the Website dashboard group.

## Module Architecture

Pure data module — no Python code, no views.

```
spreadsheet_dashboard_im_livechat/
├── __init__.py               # empty
├── __manifest__.py           # depends on im_livechat, auto_install
└── data/
    ├── dashboards.xml        # creates 2 spreadsheet.dashboard records
    └── files/
        ├── livechat_dashboard.json              # historical performance
        ├── livechat_sample_dashboard.json       # sample for historical
        ├── livechat_ongoing_dashboard.json      # real-time sessions view
        └── livechat_sample_ongoing_dashboard.json # sample for ongoing
```

This is the only spreadsheet dashboard module that creates **two** dashboard records, making it unique among the batch.

## Dashboard Record Definitions

Source: `/data/dashboards.xml`

### Dashboard 1: Live Chat (Historical)

```xml
<record id="spreadsheet_dashboard_livechat" model="spreadsheet.dashboard">
    <field name="name">Live Chat</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_im_livechat/data/files/livechat_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('im_livechat.model_im_livechat_report_channel'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_im_livechat/data/files/livechat_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_website"/>
    <field name="group_ids"
           eval="[Command.link(ref('im_livechat.im_livechat_group_manager'))]"/>
    <field name="sequence">100</field>
    <field name="is_published">True</field>
</record>
```

### Dashboard 2: Live Chat - Ongoing Sessions

```xml
<record id="spreadsheet_dashboard_livechat_ongoing" model="spreadsheet.dashboard">
    <field name="name">Live Chat - Ongoing Sessions</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_im_livechat/data/files/livechat_ongoing_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('im_livechat.model_im_livechat_report_channel'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_im_livechat/data/files/livechat_sample_ongoing_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_website"/>
    <field name="group_ids"
           eval="[Command.link(ref('im_livechat.im_livechat_group_manager'))]"/>
    <field name="sequence">125</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties Summary

| Property | Live Chat | Ongoing Sessions |
|----------|-----------|-----------------|
| `name` | "Live Chat" | "Live Chat - Ongoing Sessions" |
| `sequence` | 100 | 125 |
| `group` | Website | Website |
| `access` | im_livechat_group_manager | im_livechat_group_manager |
| `main_data_model_ids` | `im_livechat.report.channel` | `im_livechat.report.channel` |
| Sample file | Yes | Yes |

Both dashboards use `im_livechat.im_livechat_group_manager` for access — only LiveChat Managers can view either dashboard.

## Framework Integration

### Main Data Model: `im_livechat.report.channel`

Both dashboards use `im_livechat.report.channel` as their `main_data_model_ids`. This is the reporting view model for live chat channels, not the raw `im_livechat.channel` model itself. The reporting model aggregates session data for analytics purposes.

The empty-data check via `_dashboard_is_empty()` queries `im_livechat.report.channel.search_count([], limit=1)`. If no chat sessions have occurred, both dashboards fall back to their respective sample JSON files.

### Two-Dashboard Design

The split between historical and ongoing is architectural: live chat operations have two distinct analytical needs:

1. **Historical analysis** (sequence 100): Performance over time — SLA compliance, response times, satisfaction scores, operator efficiency. This data is stable and can be aggregated over periods.

2. **Ongoing sessions** (sequence 125): Current state — active conversations, waiting visitors, operator workload right now. This is more like a real-time operations view.

Because spreadsheet dashboards are not truly real-time (they show data at load time), the "Ongoing Sessions" dashboard reflects the state when the dashboard was last opened or refreshed.

## Data Sources and KPI Structure

### Primary Model: `im_livechat.report.channel`

This is a SQL view/report model that aggregates data from raw chat sessions. It pre-computes key metrics:

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `channel_id` | Many2one | Chat session reference |
| `livechat_operator_id` | Many2one | Operator/agent |
| `start_date` | Datetime | Session start time |
| `time_to_answer` | Float | Minutes to first response |
| `duration` | Float | Session length in minutes |
| `nbr_speaking` | Integer | Messages exchanged |
| `rating_last_value` | Float | Customer satisfaction score |
| `country_id` | Many2one | Visitor's country |
| `channel_name` | Char | Channel name |

### Secondary Models

| Model | Relationship | Dashboard Use |
|-------|-------------|---------------|
| `im_livechat.channel` | via channel_id | Channel configuration, name |
| `res.partner` | operator's partner | Operator name |
| `rating.rating` | customer ratings | Satisfaction scores (CSAT) |
| `mail.message` | messages in channel | Message count per session |
| `discuss.channel` | base channel model | Session state (open/closed) |

## Historical Dashboard KPIs

**Volume Metrics**
- Total chat sessions per period (day/week/month)
- Sessions per operator
- Sessions by channel/website
- Peak hours (time of day with highest volume)
- Sessions by visitor country

**Response Time Performance**
- Average time to first response (seconds/minutes)
- Response time distribution (histogram)
- SLA compliance: % of sessions answered within target time
- Missed chats (visitor left before response)

**Session Quality**
- Average session duration
- Messages per session (conversation depth)
- Sessions ended by operator vs. by visitor
- Repeat visitors (identified by email/cookie)

**Customer Satisfaction (CSAT)**
- Average rating score (typically 1-5 stars)
- % of sessions rated
- Rating distribution
- Rating trend over time
- Low-rated sessions (requiring follow-up)

**Operator Performance**
- Sessions handled per operator
- Average response time per operator
- Average rating per operator
- Active hours per operator

## Ongoing Sessions Dashboard KPIs

**Current State (at dashboard load time)**
- Number of active sessions right now
- Sessions waiting for operator response
- Longest-waiting session (oldest unanswered)
- Active operators currently online

**Workload Distribution**
- Sessions per operator (current load)
- Sessions by channel
- Visitor countries currently chatting

**Session Details**
- List of current sessions with duration so far
- Sessions flagged as urgent or escalated
- Sessions with no operator assigned

**Refresh Pattern**

Because spreadsheets do not auto-refresh, managers typically reload the Ongoing Sessions dashboard periodically or set up a browser auto-refresh. The "Ongoing" nature is more of a "snapshot of now" than a live feed.

## Access Control

`im_livechat.im_livechat_group_manager` controls access to both dashboards. This group is granted to team leads and supervisors, not to individual chat operators. Operators see only their own chat window; managers see the aggregated analytics.

## Auto-Install Behavior

```python
'auto_install': ['im_livechat'],
```

When `im_livechat` is installed (typically as part of a Website or Sales app setup), both live chat dashboards auto-install immediately, placing them under the Website group for managers.

## Dependencies Chain

```
spreadsheet_dashboard_im_livechat
├── spreadsheet_dashboard   # base framework
└── im_livechat             # depends on:
    ├── mail                # discuss.channel, mail.message
    ├── rating              # rating.rating (CSAT scores)
    └── bus                 # real-time messaging bus
```

## Customization

**Historical dashboard extensions:**
1. Add SLA thresholds: color cells red/green based on target response time
2. Add channel filter: slicer by `channel_id` for multi-channel businesses
3. Weekly trends chart: pivot by week to show volume over longer periods

**Ongoing sessions extensions:**
1. Escalation tracking: add a KPI for sessions tagged as escalated
2. Auto-refresh: open in a browser tab with periodic refresh via JavaScript injection
3. Operator availability: link to HR attendance data if `hr_attendance` is installed

## Related Modules

- [spreadsheet_dashboard](spreadsheet_dashboard.md) — Dashboard framework
- [spreadsheet_account](spreadsheet_account.md) — Accounting formulas (not directly used but available)
- `im_livechat` — Live chat channels, operators, sessions, ratings
- `rating` — CSAT rating model linked to chat sessions

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_im_livechat/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_im_livechat/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_im_livechat/data/files/livechat_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_im_livechat/data/files/livechat_ongoing_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_im_livechat/data/files/livechat_sample_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_im_livechat/data/files/livechat_sample_ongoing_dashboard.json`
