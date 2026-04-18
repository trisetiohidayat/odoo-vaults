---
tags: [odoo, odoo19, spreadsheet, dashboard, events, event_sale, marketing]
---

# spreadsheet_dashboard_event_sale

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_event_sale` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `event_sale` |
| Auto-install trigger | `event_sale` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides a pre-configured [spreadsheet_dashboard](spreadsheet_dashboard.md) template for event managers showing event sales performance. Auto-installs whenever `event_sale` is active — no manual installation required.

## Module Architecture

This is a pure data module. It contains no Python model code, no views, and no controllers. Its only contribution is a single XML data file that inserts a `spreadsheet.dashboard` record into the database.

```
spreadsheet_dashboard_event_sale/
├── __init__.py               # empty
├── __manifest__.py           # metadata, depends, auto_install
└── data/
    ├── dashboards.xml        # creates spreadsheet.dashboard record
    └── files/
        ├── events_dashboard.json        # live dashboard spreadsheet data
        └── events_sample_dashboard.json # demo/sample version shown when no data
```

The JSON files contain the full spreadsheet definition in Odoo's internal spreadsheet format — cell formulas, chart configurations, pivot table definitions, named ranges, and locale settings. These files are base64-encoded and stored in the `spreadsheet_binary_data` field on the `spreadsheet.dashboard` record.

## Dashboard Record Definition

Source: `/data/dashboards.xml`

```xml
<record id="spreadsheet_dashboard_events" model="spreadsheet.dashboard">
    <field name="name">Events</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_event_sale/data/files/events_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('event.model_event_event'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_event_sale/data/files/events_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_marketing"/>
    <field name="group_ids"
           eval="[Command.link(ref('event.group_event_manager'))]"/>
    <field name="sequence">60</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties

| Field | Value | Significance |
|-------|-------|--------------|
| `name` | "Events" | Displayed in dashboard menu |
| `dashboard_group_id` | `group_marketing` | Appears under "Marketing" section |
| `group_ids` | `event.group_event_manager` | Only Event Managers can access |
| `sequence` | 60 | Sort position within the Marketing group |
| `main_data_model_ids` | `event.event` | Used by `_dashboard_is_empty()` to detect empty data |
| `is_published` | True | Visible to authorized users immediately |

## Framework Integration

### spreadsheet.dashboard Model

All spreadsheet dashboard modules operate through the `spreadsheet.dashboard` model defined in [spreadsheet_dashboard](spreadsheet_dashboard.md). Key methods this module relies on:

**`_dashboard_is_empty()`**
Checks whether `event.event` has any records. If the model returns zero results via `search_count([], limit=1)`, the framework switches to displaying `events_sample_dashboard.json` instead of the live spreadsheet. This prevents showing blank dashboards to new users.

**`_get_serialized_readonly_dashboard()`**
Serializes the spreadsheet data as JSON including:
- The snapshot (cell data, formulas, charts, pivots)
- User locale from `res.lang._get_user_spreadsheet_locale()`
- Default company currency via `res.currency.get_company_currency_for_spreadsheet()`
- Empty revisions list (dashboards are read-only by default)

**`_get_dashboard_translation_namespace()`**
Returns the module name (`spreadsheet_dashboard_event_sale`) to scope translations for the dashboard's translatable strings.

### Access Control Logic

The dashboard is restricted to users with `event.group_event_manager` group. The `group_ids` Many2many field is evaluated at install time and checked by the web client when building the dashboard menu. Non-Event-Managers will not see the "Events" entry in the Marketing dashboard group.

## Data Sources and KPI Structure

The dashboard spreadsheet reads from Odoo data using ODOO.PIVOT and ODOO.LIST formulas embedded in the JSON. The primary source model is `event.event`, but event sale dashboards also pull from related models through relational joins in pivot formulas.

### Primary Model: `event.event`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Event name dimension |
| `date_begin` | Datetime | Period filtering |
| `date_end` | Datetime | Event duration |
| `stage_id` | Many2one | Event lifecycle stage |
| `seats_available` | Integer | Capacity KPI |
| `seats_reserved` | Integer | Registration count |
| `seats_max` | Integer | Capacity planning |
| `seats_unconfirmed` | Integer | Pending registrations |

### Secondary Models (via event_sale dependency)

| Model | Relationship | Dashboard Use |
|-------|-------------|---------------|
| `event.registration` | event_id → event.event | Attendee counts, conversion |
| `event.ticket` | event_id → event.event | Ticket type breakdown, pricing |
| `sale.order` | via event.registration | Revenue tracking |
| `sale.order.line` | via ticket purchases | Revenue per ticket type |

### Key KPIs Tracked

**Registration Metrics**
- Total registrations per event
- Confirmed vs. unconfirmed attendee ratio
- Seats fill rate: `seats_reserved / seats_max`
- Registration trend over time (monthly/quarterly view)

**Revenue Metrics**
- Total revenue per event (linked sale order amounts)
- Revenue per ticket type
- Average ticket price
- Revenue by event category or tag

**Event Performance**
- Events by stage (draft, confirmed, ended, cancelled)
- Upcoming events with remaining capacity
- Top events by registration count
- Top events by revenue

**Sales Funnel**
- Registration conversion rate (unconfirmed → confirmed)
- Attendee vs. capacity analysis
- Ticket sales velocity (registrations per day before event)

## Auto-Install Behavior

```python
'auto_install': ['event_sale'],
```

When `event_sale` is installed (which itself depends on `event` + `sale`), Odoo automatically installs `spreadsheet_dashboard_event_sale`. This ensures Event Managers see the Events dashboard immediately after setting up event ticketing — without requiring manual configuration.

The reverse is also true: uninstalling `event_sale` will uninstall this module and remove the dashboard record.

## Dashboard Groups

The "Marketing" dashboard group (`spreadsheet_dashboard_group_marketing`) is defined in the base `spreadsheet_dashboard` module. Within Marketing, sequence 60 positions the Events dashboard after higher-priority marketing metrics. Other modules may add dashboards to the same group with different sequences.

## Customization

Because `spreadsheet.dashboard` records are standard ORM records, they can be customized post-install:

1. **Edit the spreadsheet**: Navigate to Dashboards > Events, click Edit, modify cells/pivots/charts, save. Changes are stored as new revisions on the `spreadsheet.dashboard` record.

2. **Fork the dashboard**: Use the "Copy" action to create a custom variant without modifying the module-provided original.

3. **Restrict access**: Modify `group_ids` on the record to further restrict visibility beyond Event Managers.

4. **Add to favorites**: Users can mark dashboards as favorites via `action_toggle_favorite()`, which adds their UID to `favorite_user_ids`.

## Sample Dashboard Behavior

When `event.event` has no records (`search_count == 0`), the framework loads `events_sample_dashboard.json` instead of the live spreadsheet. This pre-populated file shows realistic demo data so new users understand what the dashboard will look like once events are entered. The sample dashboard is read-only and displays a notice that it contains example data.

## Dependencies Chain

```
spreadsheet_dashboard_event_sale
├── spreadsheet_dashboard      # base dashboard framework + spreadsheet.dashboard model
└── event_sale                 # depends on:
    ├── event                  # event.event, event.registration, event.ticket
    └── sale                   # sale.order, sale.order.line
```

## Related Modules

- [spreadsheet_dashboard](spreadsheet_dashboard.md) — Framework that defines `spreadsheet.dashboard` model, groups, and rendering
- [spreadsheet_account](spreadsheet_account.md) — Accounting formula functions used in financial spreadsheets
- `event_sale` — Adds ticket sales and sale order linking to events
- `event` — Core event management (event.event, event.registration)

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_event_sale/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_event_sale/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_event_sale/data/files/events_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_event_sale/data/files/events_sample_dashboard.json`

## Development Notes

Because this is a data-only module, all changes to the dashboard content must be made through:
1. **Odoo UI**: Edit the spreadsheet interactively through the dashboard interface
2. **JSON file modification**: Update `events_dashboard.json` and re-install the module
3. **ir.model.data overrides**: In a custom module, use `<record id="spreadsheet_dashboard_event_sale.spreadsheet_dashboard_events" model="spreadsheet.dashboard">` with only the fields to override (e.g., `sequence`, `group_ids`)

There are no Python override points in this module because it has no Python code. All customization happens at the data record level or in the spreadsheet JSON itself.
