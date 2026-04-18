---
uuid: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a
tags:
  - odoo
  - odoo19
  - modules
  - framework
  - ui
  - setup
  - ux
---

# Onboarding Toolbox (`onboarding`)

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | `onboarding` |
| **Category** | Hidden (Framework) |
| **Depends** | `web` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Source** | `odoo/addons/onboarding/` |

## Description

The `onboarding` module provides a **reusable onboarding framework** for in-app setup guidance. It displays collapsible panel dialogs in the Odoo interface that walk users through initial configuration steps. Each onboarding panel contains steps that trigger specific actions (opening a form, creating a record, etc.), and progress is tracked persistently per company.

The framework is designed to be:
- **Per-company aware**: Steps can be company-specific or shared across the installation
- **State-aware**: The panel remembers completion state across sessions
- **URL-routed**: Each onboarding has a unique route (`/onboarding/{route_name}`) for direct linking
- **Progress-tracking**: Automatically computes completion percentage from step states
- **Dismissable**: Users can close the panel; it does not reappear automatically

## Module Structure

```
onboarding/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── onboarding_onboarding.py         # Container model (onboarding panel)
│   ├── onboarding_onboarding_step.py    # Individual step model
│   ├── onboarding_progress.py           # Per-company progress tracker
│   └── onboarding_progress_step.py      # Per-step progress tracker
├── controllers/
│   ├── __init__.py
│   └── onboarding.py                    # Panel rendering controller
└── static/
    └── src/
        ├── js/
        │   └── onboarding_controller.js   # Panel JS behavior
        └── scss/
            └── onboarding.scss            # Panel styling
```

## Data Model

### Model Hierarchy

The onboarding framework uses four interrelated models:

```
onboarding.onboarding (panel container)
  ├── Many2many → onboarding.onboarding.step (steps in the panel)
  ├── One2many → onboarding.progress (progress records, one per company)
  │               └── One2many → onboarding.progress.step (per-step states)
  └── Many2one → onboarding.progress (computed, per-company)

onboarding.onboarding.step (individual step)
  ├── Many2many → onboarding.onboarding (which panels contain this step)
  ├── One2many → onboarding.progress.step (progress records per company)
  └── Many2one → onboarding.onboarding.step (computed, per-company)

onboarding.progress (per-company progress for a panel)
  ├── Many2one → onboarding.onboarding (the panel)
  ├── Many2one → res.company (the company, optional for non-per-company)
  └── Many2many → onboarding.progress.step (all step progress records)

onboarding.progress.step (per-step state for a company)
  ├── Many2one → onboarding.onboarding.step (the step)
  ├── Many2one → onboarding.progress (the panel progress)
  └── Many2one → res.company (the company, optional)
```

### `onboarding.onboarding` (Panel Container)

**File:** `models/onboarding_onboarding.py`

The top-level model representing a complete onboarding panel (a group of related setup steps).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display name shown in the panel header |
| `route_name` | Char | One-word URL identifier (`/onboarding/{route_name}`) |
| `step_ids` | Many2many | `onboarding.onboarding.step` records in this panel |
| `text_completed` | Char | Message shown when all steps are done |
| `panel_close_action_name` | Char | Window action to trigger when panel is closed |
| `is_per_company` | Boolean | Computed — whether any step or progress is per-company |
| `current_progress_id` | Many2one | The `onboarding.progress` for the current company |
| `current_onboarding_state` | Selection | Computed: `not_done`, `just_done`, or `done` |
| `is_onboarding_closed` | Boolean | Whether the panel has been dismissed by the user |
| `progress_ids` | One2many | All progress records for this panel (across companies) |
| `sequence` | Integer | Ordering of panels when multiple exist |

**SQL Constraints:**

```python
_route_name_uniq = models.Constraint(
    'UNIQUE (route_name)',
    'Onboarding alias must be unique.',
)
```

Each onboarding panel must have a unique `route_name` used in its URL.

**Key Methods:**

| Method | Description |
|--------|-------------|
| `_compute_is_per_company()` | Sets True if any step is per-company |
| `_compute_current_progress()` | Finds/creates the progress record for current company |
| `write()` | Syncs progress step records when steps are added/removed |
| `action_close()` | Marks the panel as dismissed |
| `action_close_panel(xmlid)` | Closes a panel by external ID (quietly ignores if not found) |
| `action_refresh_progress_ids()` | Resets progress for a panel (used when `is_per_company` changes) |
| `action_toggle_visibility()` | Toggles panel open/closed state |
| `_search_or_create_progress()` | Returns existing progress or creates new one |
| `_create_progress()` | Creates new `onboarding.progress` records |
| `_prepare_rendering_values()` | Prepares dict of values for QWeb panel rendering |

**Per-Company Computation Logic:**

```python
@api.depends_context('company')
@api.depends('progress_ids', 'progress_ids.is_onboarding_closed',
             'progress_ids.onboarding_state', 'progress_ids.company_id')
def _compute_current_progress(self):
    for onboarding in self:
        # Finds progress record where company_id matches current context
        current_progress_id = onboarding.progress_ids.filtered(
            lambda progress: progress.company_id.id in {False, self.env.company.id}
        )
        # {False, company_id} means: either no company set OR current company
        # This allows one progress record to serve all companies (when not per-company)
        # Or separate records per company (when per-company)
```

### `onboarding.onboarding.step` (Step)

**File:** `models/onboarding_onboarding_step.py`

An individual setup step within an onboarding panel.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `onboarding_ids` | Many2many | Which panels contain this step |
| `title` | Char | Step title displayed in the panel |
| `description` | Char | Explanatory text below the title |
| `button_text` | Char | Text on the action button (default: "Let's do it") |
| `done_icon` | Char | Font Awesome icon shown when step is done (default: `fa-star`) |
| `done_text` | Char | Text shown when step is completed |
| `step_image` | Binary | Optional image/illustration for the step |
| `step_image_filename` | Char | Filename for the image |
| `step_image_alt` | Char | Alt text for the image |
| `panel_step_open_action_name` | Char | Window action name to trigger when button is clicked |
| `current_progress_step_id` | Many2one | The `onboarding.progress.step` for current company |
| `current_step_state` | Selection | Computed: `not_done`, `just_done`, or `done` |
| `progress_ids` | One2many | All step progress records (across companies) |
| `is_per_company` | Boolean | Whether this step tracks progress per company (default: True) |
| `sequence` | Integer | Ordering of steps within the panel |

**Constraint:**

```python
@api.constrains('onboarding_ids')
def check_step_on_onboarding_has_action(self):
    # Steps linked to a panel MUST have an action
    # Otherwise clicking the button does nothing
    if steps_without_action := self.filtered(
        lambda step: step.onboarding_ids and not step.panel_step_open_action_name
    ):
        raise ValidationError(_(
            'An "Opening Action" is required for the following steps to be '
            'linked to an onboarding panel: %(step_titles)s',
            step_titles=steps_without_action.mapped('title'),
        ))
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `_compute_current_progress()` | Finds the progress step record for current company |
| `write()` | Resets progress when `is_per_company` changes; syncs on onboarding change |
| `action_set_just_done()` | Marks this step as `just_done` and creates progress if needed |
| `action_validate_step(xml_id)` | API for JS to validate a step by XML ID; returns `"NOT_FOUND"`, `"JUST_DONE"`, or `"WAS_DONE"` |
| `_get_placeholder_filename(field)` | Returns fallback image when `step_image` is not set |
| `_create_progress_steps()` | Creates `onboarding.progress.step` records for current company |

### `onboarding.progress` (Per-Company Panel Progress)

**File:** `models/onboarding_progress.py`

Tracks the overall state of an onboarding panel for a specific company (or globally if not per-company).

**File:** `models/onboarding_progress.py`

```python
ONBOARDING_PROGRESS_STATES = [
    ('not_done', 'Not done'),
    ('just_done', 'Just done'),
    ('done', 'Done'),
]
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `onboarding_state` | Selection | Computed: `done` if all steps done, else `not_done` |
| `is_onboarding_closed` | Boolean | Whether the user dismissed this panel |
| `company_id` | Many2one | The company (null means shared across companies) |
| `onboarding_id` | Many2one | The parent `onboarding.onboarding` |
| `progress_step_ids` | Many2many | All `onboarding.progress.step` records for this progress |

**SQL Constraint:**

```python
_onboarding_company_uniq = models.UniqueIndex("(onboarding_id, COALESCE(company_id, 0))")
```

PostgreSQL `UniqueIndex` is used instead of `models.Constraint` because `COALESCE` is not supported in SQL CHECK constraints.

**State Computation:**

```python
@api.depends('onboarding_id.step_ids', 'progress_step_ids', 'progress_step_ids.step_state')
def _compute_onboarding_state(self):
    for progress in self:
        # Panel is 'done' only if ALL steps are done/just_done
        done_count = len(progress.progress_step_ids.filtered(
            lambda p: p.step_state in {'just_done', 'done'}
        ))
        total_count = len(progress.onboarding_id.step_ids)
        progress.onboarding_state = 'done' if done_count == total_count else 'not_done'
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `_recompute_progress_step_ids()` | Syncs the Many2many of step progress records |
| `action_close()` | Marks the panel as dismissed (`is_onboarding_closed = True`) |
| `action_toggle_visibility()` | Toggles `is_onboarding_closed` |
| `_get_and_update_onboarding_state()` | Fetches state for rendering; transitions `just_done` → `done` |

### `onboarding.progress.step` (Per-Step State)

**File:** `models/onboarding_progress_step.py`

Tracks the completion state of an individual step for a specific company.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `step_state` | Selection | `not_done`, `just_done`, or `done` (default: `not_done`) |
| `step_id` | Many2one | The parent `onboarding.onboarding.step` |
| `progress_ids` | Many2many | Links to `onboarding.progress` records |
| `company_id` | Many2one | The company (null if step is not per-company) |

**SQL Constraint:**

```python
_company_uniq = models.UniqueIndex("(step_id, COALESCE(company_id, 0))")
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `action_set_just_done()` | Transitions `not_done` → `just_done`; returns self |
| `action_consolidate_just_done()` | Transitions `just_done` → `done`; used by panel completion logic |

## State Machine

### Step States

```
┌──────────┐  action_set_just_done()  ┌───────────┐  action_consolidate_just_done()  ┌──────┐
│ not_done │ ─────────────────────────→│ just_done │ ──────────────────────────────────→│ done │
└──────────┘                           └───────────┘                                    └──────┘
                                              ↑ (already done, no-op)
```

- **`not_done`**: Step has not been completed. The action button is clickable.
- **`just_done`**: Step was just completed. Shown once with a success state. The next panel render transitions this to `done`.
- **`done`**: Step is completed. The success icon and "Step Completed!" text are shown.

### Panel States

```
┌──────────┐  all steps done   ┌───────────┐  one render cycle  ┌──────┐
│ not_done │ ─────────────────→│ just_done │ ───────────────────→│ done │
└──────────┘                    └───────────┘                    └──────┘
       ↑ (steps reopened)            ↑
```

The `just_done` state is shown once (on the next page load after completion) to celebrate completion, then transitions to `done` automatically.

### Consolidation Flow

The consolidation mechanism (`_get_and_update_onboarding_state()`) runs when the panel is rendered:

```python
def _get_and_update_onboarding_state(self):
    # Called by the controller before rendering the panel
    progress_steps_to_consolidate = self.env['onboarding.progress.step']

    for step in self.onboarding_id.step_ids:
        step_state = step.current_step_state
        if step_state == 'just_done':
            # Collect steps to consolidate
            progress_steps_to_consolidate |= step.current_progress_step_id

    # Batch update: just_done → done
    progress_steps_to_consolidate.action_consolidate_just_done()

    # Build state dict for rendering
    # Returns {step_id: state, 'onboarding_state': 'closed'/'just_done'/'done'}
```

This is the mechanism that ensures `just_done` is shown exactly once: the consolidation happens in the controller, before rendering.

## Progress Step Id Synchronization

When steps are added to or removed from an onboarding panel, the `onboarding.progress` records must be updated to include or exclude the corresponding step progress records.

### When Steps Are Added

```python
def write(self, vals):
    already_linked_steps = self.step_ids
    res = super().write(vals)
    if self.step_ids != already_linked_steps:
        # Sync: add new steps' progress to all progress records
        self.progress_ids._recompute_progress_step_ids()
    return res
```

### `_recompute_progress_step_ids()`

```python
def _recompute_progress_step_ids(self):
    for progress in self:
        # Simply reassign from the onboarding's current step progress
        progress.progress_step_ids = progress.onboarding_id.step_ids.current_progress_step_id
```

The `current_progress_step_id` on each step is itself a computed field that finds the progress step record matching the current company context.

### When `is_per_company` Changes

If a step's `is_per_company` field changes:
1. The existing `progress.step` records are deleted (unlinked)
2. `onboarding_ids.action_refresh_progress_ids()` is called
3. New progress records are created for any affected `onboarding.progress` records

## Per-Company vs. Global Progress

The onboarding framework supports both per-company and global (installation-wide) progress tracking:

| Scenario | `is_per_company` | Progress records |
|----------|-------------------|------------------|
| Company A and B share the same progress | `False` (default) | 1 progress record with `company_id = False` |
| Each company has its own progress | `True` | 1 progress per company |

The key is in the filter: `{False, self.env.company.id}`. When `is_per_company = False`, the step's progress is linked to a `company_id = False` record. When `is_per_company = True`, steps track progress per company.

## Controller

**File:** `controllers/onboarding.py`

The controller handles:
1. Rendering the onboarding panel QWeb template
2. Responding to step completion actions
3. Computing and returning state values for the JS panel

It is accessed at `/onboarding/{route_name}` where `route_name` comes from `onboarding.onboarding.route_name`.

## JS Panel Behavior

**File:** `static/src/js/onboarding_controller.js`

The frontend JavaScript:
- Loads the panel via the controller route
- Displays the panel as a collapsible side banner
- Handles button clicks that call `onboarding.onboarding.step`'s `action_validate_step()` RPC method
- Shows/hides the panel based on the `is_onboarding_closed` state
- Animates progress updates

## Module-Specific Onboardings

Odoo's business modules define their own onboarding panels. Common patterns:

### Sale Order Onboarding (`sale`)

- Step: Create a product
- Step: Set up a sales team
- Step: Configure invoicing policy

### Inventory Onboarding (`stock`)

- Step: Configure warehouses
- Step: Set up routes
- Step: Create push/f pull rules

### Accounting Onboarding (`account`)

- Step: Configure chart of accounts
- Step: Set up fiscal years
- Step: Define payment terms

Each of these modules creates records in `onboarding.onboarding` and `onboarding.onboarding.step` via data files, then tracks progress using the framework.

## Creating a Custom Onboarding Panel

### Step 1: Define the Onboarding Record

```xml
<record id="onboarding_myapp" model="onboarding.onboarding">
    <field name="name">My App Setup</field>
    <field name="route_name">myapp_setup</field>
    <field name="step_ids" eval="[(4, ref('onboarding_myapp_step1')), (4, ref('onboarding_myapp_step2'))]"/>
    <field name="text_completed">Your My App is configured!</field>
    <field name="panel_close_action_name">myapp.action_configuration</field>
</record>
```

### Step 2: Define Steps

```xml
<record id="onboarding_myapp_step1" model="onboarding.onboarding.step">
    <field name="title">Create your first item</field>
    <field name="description">Items are the core of My App.</field>
    <field name="button_text">Create item</field>
    <field name="panel_step_open_action_name">myapp.action_create_item</field>
</record>
```

### Step 3: Install Data

Add to the module's `__manifest__.py`:
```python
'data': [
    'data/onboarding_data.xml',
],
```

## Related

- [Modules/web](web.md) — Web framework (dependency)
- [Modules/sale](sale.md) — Sales (uses onboarding for initial setup)
- [Modules/stock](stock.md) — Inventory (uses onboarding)
- [Modules/account](account.md) — Accounting (uses onboarding)
