---
tags: [odoo, odoo19, modules, account_asset, fixed_assets, depreciation, enterprise]
description: Fixed asset management and depreciation accounting (Enterprise Edition) - Full depth documentation
---

# Assets Management (`account_asset`)

> **Enterprise Module** | License: OEEL-1
> Odoo 19 Enterprise-only module for fixed asset management and depreciation tracking.
> Depends: `accountant` | Auto-install: `True`
> Path: `enterprise/account_asset/`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Models Inventory](#2-models-inventory)
3. [AccountAsset: Core Model](#3-accountasset-core-model)
   - [3.1 State Machine](#31-state-machine)
   - [3.2 Depreciation Configuration Fields](#32-depreciation-configuration-fields)
   - [3.3 Value Fields](#33-value-fields)
   - [3.4 Account and Link Fields](#34-account-and-link-fields)
4. [Depreciation Board Computation (L3)](#4-depreciation-board-computation-l3)
   - [4.1 compute_depreciation_board(): High-Level Flow](#41-compute_depreciation_board-high-level-flow)
   - [4.2 _recompute_board(): The Core Loop](#42-_recompute_board-the-core-loop)
   - [4.3 _get_delta_days: Constant vs Daily Computation](#43-_get_delta_days-constant-vs-daily-computation)
   - [4.4 _get_linear_amount(): Straight-Line Calculation](#44-_get_linear_amount-straight-line-calculation)
   - [4.5 _compute_board_amount(): Method Variants](#45-_compute_board_amount-method-variants)
   - [4.6 Linear Depreciation Detail](#46-linear-depreciation-detail)
   - [4.7 Degressive Depreciation Detail](#47-degressive-depreciation-detail)
   - [4.8 Degressive Then Linear Detail](#48-degressive-then-linear-detail)
5. [Value Fields and book_value Recursion (L3)](#5-value-fields-and-book_value-recursion-l3)
6. [Asset Modification Wizard (L3)](#6-asset-modification-wizard-l3)
   - [6.1 Modify/Re-evaluate Flow](#61-modifyre-evaluate-flow)
   - [6.2 Pause/Resume Flow](#62-pauseresume-flow)
   - [6.3 Disposal and Sale Flow](#63-disposal-and-sale-flow)
   - [6.4 Gain/Loss Calculation](#64-gainloss-calculation)
7. [Gross Increase: Parent/Children Assets (L3)](#7-gross-increase-parentchildren-assets-l3)
8. [Auto-Creation from Vendor Bills (L3)](#8-auto-creation-from-vendor-bills-l3)
9. [Extended Models](#9-extended-models)
   - [9.1 account.move Extended](#91-accountmove-extended)
   - [9.2 account.move.line Extended](#92-accountmoveline-extended)
   - [9.3 account.account Extended](#93-accountaccount-extended)
   - [9.4 res.company Extended](#94-rescompany-extended)
   - [9.5 account.chart.template Extended](#95-accountcharttemplate-extended)
   - [9.6 account.return Extended](#96-accountreturn-extended)
10. [Depreciation Report Handler (L3)](#10-depreciation-report-handler-l3)
11. [Performance Considerations (L4)](#11-performance-considerations-l4)
12. [Key Constants and Version History (L4)](#12-key-constants-and-version-history-l4)
13. [Edge Cases (L3)](#13-edge-cases-l3)
14. [Integration Points](#14-integration-points)

---

## 1. Overview

The `account_asset` module manages fixed assets throughout their lifecycle: acquisition, depreciation, revaluation, and disposal. It integrates deeply with `account.move` (journal entries) and supports three depreciation methods with configurable prorata computation.

**Key capabilities:**
- Asset templates (models) for consistent depreciation settings across asset types
- Three depreciation methods: linear (straight-line), degressive, and degressive-then-linear
- Three prorata computation types (Odoo 19): `none`, `constant_periods`, `daily_computation`
- Gross increase (revaluation) creating child assets linked to parent
- Pause/resume depreciation without losing accumulated depreciation
- Disposal and sale with automatic gain/loss calculation
- Auto-creation of assets from vendor bills based on account configuration
- Comprehensive depreciation schedule report with grouping by account/asset group
- Non-deductible tax handling for asset original value
- Multi-company aware with fiscal lock date validation
- Analytic distribution support via `analytic.mixin`

---

## 2. Models Inventory

| Model | Type | Table/Engine | Description |
|-------|------|-------------|-------------|
| `account.asset` | Main | `account_asset` | Fixed asset with depreciation configuration |
| `account.asset.group` | Main | `account_asset_group` | Grouping/categorizing assets |
| `asset.modify` | Transient Wizard | `asset_modify` | Modify/revalue/pause/dispose/sell assets |
| `account.move` | Extended | `account_move` | Links journal entries to assets |
| `account.move.line` | Extended | `account_move_line` | Links invoice lines to assets |
| `account.account` | Extended | `account_account` | Auto-asset creation configuration |
| `res.company` | Extended | `res_company` | Gain/loss accounts for disposal |
| `account.asset.report.handler` | Abstract | N/A (report engine) | Depreciation schedule report generator |
| `account.return` | Extended | `account_return` | Annual closing validation check |
| `account.chart.template` | Extended | N/A (template engine) | CSV template import for assets |

**Critical architectural note:** There is **no separate `account.asset.depreciation.line` model**. Depreciation "lines" are `account.move` records with `asset_id` set and `asset_move_type='depreciation'`. This means depreciation entries are full journal entries (with two lines: debit expense, credit depreciation account), not simple line records.

---

## 3. AccountAsset: Core Model

Model: `account.asset` | `_description: 'Asset/Revenue Recognition'`
Inherits: `mail.thread`, `mail.activity.mixin`, `analytic.mixin`

### 3.1 State Machine

```
                    +------------------+
                    |                  |
                    v                  |
+-------------+  validate()  +---------+--------+
|   model     | +---------> |   draft         |
|  (template) |              +----+---+--------+
+-------------+                  |   |
        ^                        v   | set_to_draft()
        | (action_save_model)     |   |
        +---------------------+---+---+----+
                    |  open           |    |
                    | (running)        |    |
     +--------------+                  |    |
     |              |                  |    |
     v              |                  |    |
  pause()           |                  |    |
+-------------+      |                  |    |
|   paused    |      |                  |    |
+------+------+      |                  |    |
       | resume_     |                  |    |
       | after_pause  |                  |    |
       +-------------+                  |    |
                                     v    v
                                  close     |
                              (set_to_close  |
                               or sell)      |
                                     ^       |
                                     |       v
                                     +---> cancelled
```

| State | Description | Allowed Operations |
|-------|-------------|-------------------|
| `model` | Template/blueprint - not a real asset | Save as model, delete |
| `draft` | Created but not confirmed | Validate, edit fields, delete (if no posted moves) |
| `open` | Running - depreciation entries being posted | Pause, close, cancel, modify |
| `paused` | Depreciation temporarily suspended | Resume, close |
| `close` | Fully depreciated or disposed | Set to running (reopen) |
| `cancelled` | Asset cancelled (posted entries reversed, draft deleted) | Archive |

**State transition methods:**

| Method | From | To | Notes |
|--------|------|----|-------|
| `validate()` | draft | open | Computes board, posts entries |
| `set_to_draft()` | open | draft | Only if no posted depreciation |
| `set_to_running()` | close | open | Calls `asset.modify` wizard if residual > 0 |
| `pause(pause_date, message)` | open | paused | Creates partial depreciation before pause date |
| `resume_after_pause()` | paused | open | Via `asset.modify` with `resume_after_pause` context |
| `set_to_close(invoice_lines, date)` | open | close | Creates disposal move |
| `set_to_cancelled()` | any (except model) | cancelled | Reverses posted, deletes draft |
| `action_save_model()` | any | model | Saves as template |

### 3.2 Depreciation Configuration Fields

```python
method = fields.Selection([
    ('linear', 'Straight Line'),
    ('degressive', 'Declining'),
    ('degressive_then_linear', 'Declining then Straight Line')
], string='Method', default='linear')

method_number = fields.Integer(string='Duration', default=5,
    help="Number of depreciation periods (e.g., 5 years = 5 for yearly, 60 for monthly)")

method_period = fields.Selection([
    ('1', 'Months'),   # Monthly: 12 entries per year
    ('12', 'Years')    # Yearly: 1 entry per year
], string='Number of Months in a Period', default='12',
    help="Time between depreciation entries; '1' = monthly, '12' = yearly")

method_progress_factor = fields.Float(string='Declining Factor', default=0.3,
    help="For degressive methods; 0.3 = 30% declining rate applied per period")
```

**`prorata_computation_type`** (Odoo 19 new field, replaces old boolean `prorata`):

```python
prorata_computation_type = fields.Selection([
    ('none', 'No Prorata'),
    # Prorata date = first day of fiscal year. First/last periods NOT prorated.
    # Total lifetime = method_period * method_number * 30 days (constant)

    ('constant_periods', 'Constant Periods'),
    # Prorata date = acquisition_date. Uses 30-day/month approximation.
    # First period prorated from acquisition_date to period end.
    # Last period prorated from period start to asset end.
    # Total lifetime = method_period * method_number * 30 days

    ('daily_computation', 'Based on days per period'),
    # Prorata date = acquisition_date. Uses ACTUAL calendar days.
    # More accurate for assets acquired mid-period.
    # Total lifetime = actual days between prorata_date and end date.
], string="Computation", required=True, default='constant_periods')
```

**Prorata date computation:**

```python
prorata_date = fields.Date(
    compute='_compute_prorata_date', store=True, readonly=False,
    required=True, precompute=True, copy=True,
    help='Starting date of the period used in the prorata calculation'
)

@api.depends('acquisition_date', 'company_id', 'prorata_computation_type')
def _compute_prorata_date(self):
    for asset in self:
        if asset.prorata_computation_type == 'none' and asset.acquisition_date:
            # Use fiscal year start date
            fiscalyear_date = asset.company_id.compute_fiscalyear_dates(
                asset.acquisition_date
            ).get('date_from')
            asset.prorata_date = fiscalyear_date
        else:
            asset.prorata_date = asset.acquisition_date
```

**Paused prorata date (L3):** When an asset is paused, the `paused_prorata_date` shifts to account for paused days:

```python
paused_prorata_date = fields.Date(compute='_compute_paused_prorata_date')

@api.depends('prorata_date', 'prorata_computation_type', 'asset_paused_days')
def _compute_paused_prorata_date(self):
    for asset in self:
        if asset.prorata_computation_type == 'daily_computation':
            asset.paused_prorata_date = asset.prorata_date + relativedelta(
                days=asset.asset_paused_days
            )
        else:
            # Convert paused days to months + remaining days
            asset.paused_prorata_date = asset.prorata_date + relativedelta(
                months=int(asset.asset_paused_days / DAYS_PER_MONTH),  # 30
                days=asset.asset_paused_days % DAYS_PER_MONTH
            )
```

**Asset lifetime days (L3):**

```python
asset_lifetime_days = fields.Float(
    compute="_compute_lifetime_days", recursive=True,
    help='Total number of days for the asset depreciation board'
)

@api.depends('method_number', 'method_period', 'prorata_computation_type')
def _compute_lifetime_days(self):
    for asset in self:
        if not asset.parent_id:
            if asset.prorata_computation_type == 'daily_computation':
                # Actual calendar days: (prorata_date + months - prorata_date).days
                asset.asset_lifetime_days = (
                    asset.prorata_date + relativedelta(
                        months=int(asset.method_period) * asset.method_number
                    ) - asset.prorata_date
                ).days
            else:
                # 30-day months: method_period * method_number * 30
                asset.asset_lifetime_days = (
                    int(asset.method_period) * asset.method_number * DAYS_PER_MONTH
                )
        else:
            # Child asset: limited to parent's remaining life
            # See Section 7: Gross Increase for details
            parent_end_date = ...
            asset.asset_lifetime_days = asset._get_delta_days(
                asset.prorata_date, parent_end_date
            )
```

**`asset_paused_days`** accumulates days spent in paused state:

```python
asset_paused_days = fields.Float(copy=False)
# Updated during resume_after_pause:
#   asset_paused_days += _get_delta_days(pause_date, resume_date) - 1
# The -1 ensures same-day pause/resume = no gap
# Used in paused_prorata_date computation
```

### 3.3 Value Fields

```python
original_value = fields.Monetary(
    string="Original Value",
    compute='_compute_value', store=True, readonly=False
)
# = related_purchase_value + non_deductible_tax_value
# related_purchase_value = sum(line.balance * line.deductible_amount / 100)
# If multiple_assets_per_line: divides by quantity

salvage_value = fields.Monetary(
    string='Not Depreciable Value',
    compute="_compute_salvage_value", store=True, readonly=False
)
# If model has salvage_value_pct != 0: original_value * salvage_value_pct
# Otherwise: user-set value

salvage_value_pct = fields.Float(
    string='Not Depreciable Value Percent'
    # Used by _compute_salvage_value when model is set
)

total_depreciable_value = fields.Monetary(compute='_compute_total_depreciable_value')
# = original_value - salvage_value

value_residual = fields.Monetary(
    string='Depreciable Value',
    compute='_compute_value_residual'
)
# = original_value - salvage_value - already_depreciated_amount_import
#   - sum(posted_depreciation_moves.mapped('depreciation_value'))

book_value = fields.Monetary(
    string='Book Value',
    readonly=True, compute='_compute_book_value',
    recursive=True, store=True
)
# = value_residual + salvage_value + sum(children_ids.book_value)
# If state='close' and all moves posted: book_value -= salvage_value
# recursive=True: Odoo tracks circular dependency through children_ids
# store=True: persisted to DB

gross_increase_value = fields.Monetary(
    string="Gross Increase Value",
    compute="_compute_gross_increase_value", compute_sudo=True
)
# = sum(children_ids.original_value)

non_deductible_tax_value = fields.Monetary(
    string="Non Deductible Tax Value",
    compute="_compute_non_deductible_tax_value", store=True, readonly=True
)
# Sum of non-deductible taxes from original_move_line_ids
# Converts to company currency, applies deductible_amount %
# Stored for performance (changes only when invoice changes)

related_purchase_value = fields.Monetary(
    compute='_compute_related_purchase_value'
)
# = sum(line.balance * line.deductible_amount / 100)
# deductible_amount: percentage of the line that IS deductible

already_depreciated_amount_import = fields.Monetary(
    help="For imports from other software. Value already depreciated via entries "
         "not computed from this model. Added to first depreciation entries."
)

net_gain_on_sale = fields.Monetary(
    string="Net gain on sale",
    copy=False,
    help="selling_price - book_value"
)
```

**Value computation chain:**

```
original_move_line_ids (invoice lines)
    |
    +-- line.balance * line.deductible_amount / 100 for each line
    |       |
    |       +-- If multiple_assets_per_line: / quantity
    |
    +-- Sum = related_purchase_value
            |
            +-- non_deductible_tax_value (added)
                    |
                    v
              original_value

original_value
    |
    +-- salvage_value (user-set or computed from salvage_value_pct)
            |
            v
    total_depreciable_value = original_value - salvage_value

total_depreciable_value
    |
    +-- sum(posted depreciation_move.depreciation_value)
    +-- already_depreciated_amount_import
            |
            v
    value_residual = total_depreciable_value - depreciated

value_residual + salvage_value + sum(children.book_value)
    |
    v
book_value (recursive)
```

### 3.4 Account and Link Fields

```python
account_asset_id = fields.Many2one(
    'account.account',
    string='Fixed Asset Account',
    compute='_compute_account_asset_id', store=True, readonly=False,
    domain="[('account_type', '!=', 'off_balance')]",
    help="Balance sheet account. Dr when acquiring, Cr when disposing."
)
# Computed from original_move_line_ids if they exist

account_depreciation_id = fields.Many2one(
    'account.account',
    string='Depreciation Account',
    domain=[('account_type', 'not in', (
        'asset_receivable', 'liability_payable', 'asset_cash',
        'liability_credit_card', 'off_balance'
    ))],
    help="Contra asset account. Cr for depreciation, Dr for disposals."
)

account_depreciation_expense_id = fields.Many2one(
    'account.account',
    string='Expense Account',
    domain=[('account_type', 'not in', (...same...))],
    help="P&L account. Dr for depreciation expense each period."
)

journal_id = fields.Many2one(
    'account.journal',
    string='Journal',
    domain="[('type', '=', 'general')]",
    compute='_compute_journal_id', store=True, readonly=False,
    help="General journal for depreciation entries."
)
# Default: first general journal for the company

depreciation_move_ids = fields.One2many(
    'account.move', 'asset_id',
    string='Depreciation Lines'
)
# All journal entries (depreciation, disposal, revaluation) linked to this asset.
# Both posted and draft entries are tracked here.

original_move_line_ids = fields.Many2many(
    'account.move.line', 'asset_move_line_rel', 'asset_id', 'line_id',
    string='Journal Items', copy=False
)
# Invoice/vendor bill lines from which this asset was created.
# The balance of these lines determines the original_value.

model_id = fields.Many2one(
    'account.asset',
    string='Model',
    domain="[('company_id', '=', company_id)]",
    help="Asset template. When set, depreciation settings are copied via _onchange_model_id."
)

parent_id = fields.Many2one(
    'account.asset', index=True,
    help="Parent asset when this asset is a gross increase (revaluation)."
)

children_ids = fields.One2many(
    'account.asset', 'parent_id',
    help="Gross increase sub-assets. Their values are included in parent's book_value."
)

asset_group_id = fields.Many2one(
    'account.asset.group', string='Asset Group',
    tracking=True, index=True,
    help="Optional grouping for reporting and filtering."
)

asset_properties_definition = fields.PropertiesDefinition('Model Properties')
asset_properties = fields.Properties(
    'Properties', definition='model_id.asset_properties_definition', copy=True
)
```

---

## 4. Depreciation Board Computation (L3)

The depreciation board is the schedule of journal entries that reduce the asset's book value over time.

### 4.1 `compute_depreciation_board()`: High-Level Flow

```python
def compute_depreciation_board(self, date=False):
    """Generate/re-generate the full depreciation board for assets.

    Args:
        date: If provided, unlink draft moves at or after this date,
              then recompute from this date forward.
              If False, unlink ALL draft moves and recompute entirely.

    This is the main entry point for depreciation computation.
    Called by:
    - validate() when confirming an asset
    - asset_modify.modify() after revaluation/pause/resume
    - Manual "Regenerate Depreciation" button (if any)
    """
    # Step 1: Unlink draft moves at or after the given date
    # This ensures we don't have conflicting draft entries
    self.depreciation_move_ids.filtered(
        lambda mv: mv.state == 'draft'
        and (mv.date >= date if date else True)
    ).unlink()

    # Step 2: For each asset, compute new depreciation moves
    # Each call to _recompute_board() returns a list of dicts
    # suitable for account.move.create()
    new_depreciation_moves_data = []
    for asset in self:
        new_depreciation_moves_data.extend(asset._recompute_board(date))

    # Step 3: Batch create all moves
    # This is more efficient than creating moves one at a time
    new_depreciation_moves = self.env['account.move'].create(new_depreciation_moves_data)

    # Step 4: Post moves for open assets
    # Draft moves in the past are auto-posted by _post()
    # Draft moves in the future remain draft (for cron-based auto-posting)
    new_depreciation_moves_to_post = new_depreciation_moves.filtered(
        lambda move: move.asset_id.state == 'open'
    )
    new_depreciation_moves_to_post._post()
```

### 4.2 `_recompute_board()`: The Core Loop

```python
def _recompute_board(self, start_depreciation_date=False):
    """Compute depreciation schedule for ONE asset.

    Returns a list of account.move create dictionaries.

    State variables tracked across the loop:
    - residual_amount: Amount still to depreciate
    - residual_declining: Used for degressive method, tracks declining value
    - start_depreciation_date: Current position in the board
    - start_yearly_period: For degressive methods, tracks fiscal year boundaries
    - imported_amount: Pre-imported depreciation to apply to first entries
    """
    self.ensure_one()

    # Get all already-posted depreciation moves (excluding value changes)
    posted = self.depreciation_move_ids.filtered(
        lambda mv: mv.state == 'posted' and not mv.asset_value_change
    ).sorted(key=lambda mv: (mv.date, mv.id))

    # Initial residual = value_residual
    # Subtract draft depreciation values (they're still in value_residual)
    residual_amount = self.value_residual - sum(
        self.depreciation_move_ids.filtered(lambda mv: mv.state == 'draft')
        .mapped('depreciation_value')
    )

    # If no posted moves, add the imported depreciation amount
    # This prevents double-counting imported + computed depreciation
    if not posted:
        residual_amount += self.already_depreciated_amount_import

    residual_declining = residual_at_compute = residual_amount

    # Determine start date: paused_prorata_date if not resuming from specific date
    start = start_yearly_period = start_depreciation_date or self.paused_prorata_date

    # Calculate end date and total lifetime remaining
    last_day = self._get_last_day_asset()
    final_date = self._get_end_period_date(last_day)
    total_lifetime_left = self._get_delta_days(start, last_day)

    depreciation_move_values = []

    # MAIN LOOP: iterate period by period until fully depreciated
    while (
        not self.currency_id.is_zero(residual_amount)
        and start < final_date
    ):
        period_end = self._get_end_period_date(start)

        # Compute depreciation for this period
        days, amount = self._compute_board_amount(
            residual_amount, start, period_end,
            False,              # days_already_depreciated (unused)
            total_lifetime_left,  # lifetime_left
            residual_declining,    # for degressive
            start_yearly_period,  # for degressive
            total_lifetime_left,  # total_lifetime_left
            residual_at_compute,  # for linear recompute
            start                 # start_recompute_date
        )

        residual_amount -= amount

        # Handle already_depreciated_amount_import
        # Subtract from first depreciation entries until exhausted
        if not posted:
            if abs(imported_amount) <= abs(amount):
                amount -= imported_amount
                imported_amount = 0
            else:
                imported_amount -= amount
                amount = 0

        # Create depreciation move if amount is non-zero
        if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
            depreciation_move_values.append(
                self.env['account.move']._prepare_move_for_asset_depreciation({
                    'amount': amount,
                    'asset_id': self,
                    'depreciation_beginning_date': start,
                    'date': period_end,
                    'asset_number_days': days,
                })
            )

        # Reset yearly tracking for degressive methods
        # At the end of each fiscal year, reset the declining balance
        if period_end == self.company_id.compute_fiscalyear_dates(
            period_end
        ).get('date_to'):
            start_yearly_period = period_end + relativedelta(years=1)
            residual_declining = residual_amount

        # Advance to next period
        start = period_end + relativedelta(days=1)

    return depreciation_move_values
```

### 4.3 `_get_delta_days`: Constant vs Daily Computation

This is the most critical method for prorata accuracy. It has two completely different implementations:

```python
DAYS_PER_MONTH = 30  # Constant for accounting convention
DAYS_PER_YEAR = 360  # 12 * 30

def _get_delta_days(self, start_date, end_date):
    """Compute number of days between two dates for depreciation calculation.

    IMPORTANT: Called O(N*M) times during board computation where:
    - N = number of depreciation periods (up to 60 for 5-year monthly)
    - M = number of value changes (revaluations)
    Inlined or cached in hot paths.

    Accuracy vs convention trade-off:
    - constant_periods: Fast, consistent with accounting ledgers, may differ from calendar
    - daily_computation: Accurate, respects actual month lengths and leap years
    """
    if self.prorata_computation_type == 'daily_computation':
        # Method: Actual calendar days + 1 (inclusive range)
        # June 15 to June 20 = 6 days (15, 16, 17, 18, 19, 20)
        return (end_date - start_date).days + 1
    else:
        # Method: 30-day month approximation (Swiss/French accounting convention)
        # Each month = 30 days regardless of actual calendar days
        # February = 30 days, January 31 = 30 days

        # Pro-rata for start date (remaining days in the month)
        # Example: June 20 (30-day month)
        # start_prorata = (30 - 20 + 1) / 30 = 11/30 = 0.367
        start_date_days_month = end_of(start_date, 'month').day
        start_prorata = (
            start_date_days_month - start_date.day + 1
        ) / start_date_days_month

        # Pro-rata for end date (elapsed days in the month)
        # Example: August 14 (31-day month)
        # end_prorata = 14 / 31 = 0.452
        end_prorata = end_date.day / end_of(end_date, 'month').day

        # Composite formula:
        # Example: June 20 to August 14
        # = 11/30*30 + 14/31*30 + 0*(2020-2020) + 30*(8-6-1)
        # = 11 + 13.55 + 0 + 30 = 54.55 days
        return sum((
            start_prorata * DAYS_PER_MONTH,
            end_prorata * DAYS_PER_MONTH,
            (end_date.year - start_date.year) * DAYS_PER_YEAR,
            (end_date.month - start_date.month - 1) * DAYS_PER_MONTH,
        ))
```

**L3 Edge Case - Leap Year with daily_computation:**

With `daily_computation`, a 5-year asset acquired on 2024-02-29 will have:
- 2024: 337 days (Feb 29 to Dec 31, leap year)
- 2025: 365 days
- Total = actual calendar days

With `constant_periods`, the same asset uses the formula above, completely ignoring leap years.

### 4.4 `_get_linear_amount()`: Straight-Line Calculation

```python
def _get_linear_amount(self, days_before_period, days_until_period_end,
                       total_depreciable_value):
    """Compute one period's straight-line depreciation amount.

    Formula: How much of total_depreciable_value is attributable to this period?
    Based on the proportion of the asset's lifetime that falls within this period.

    Also subtracts value decreases (revaluations) spread over remaining life.
    """
    # Value that should have been depreciated up to period start
    amount_expected_previous = (
        total_depreciable_value * days_before_period / self.asset_lifetime_days
    )

    # Value that should have been depreciated up to period end
    amount_expected_current = (
        total_depreciable_value * days_until_period_end / self.asset_lifetime_days
    )

    # This period's depreciation = difference
    number_days_for_period = days_until_period_end - days_before_period

    # Subtract value decreases (negative revaluations) spread over remaining periods
    # Each revaluation's depreciation is spread pro-rata over remaining life
    amount_of_decrease_spread_over_period = [
        number_days_for_period
        * mv.depreciation_value
        / (
            self.asset_lifetime_days
            - self._get_delta_days(
                self.paused_prorata_date,
                mv.asset_depreciation_beginning_date
            )
        )
        for mv in self.depreciation_move_ids.filtered(lambda mv: mv.asset_value_change)
    ]

    computed_linear_amount = (
        self.currency_id.round(amount_expected_current)
        - self.currency_id.round(amount_expected_previous)
        - sum(amount_of_decrease_spread_over_period)
    )
    return self.currency_id.round(computed_linear_amount)
```

### 4.5 `_compute_board_amount()`: Method Variants

This single method handles all three depreciation methods:

```python
def _compute_board_amount(self, residual_amount, period_start_date, period_end_date,
                           days_already_depreciated, days_left_to_depreciated,
                           residual_declining, start_yearly_period=None,
                           total_lifetime_left=None, residual_at_compute=None,
                           start_recompute_date=None):
    """Compute depreciation amount for one period, based on the method.

    Returns (number_of_days, depreciation_amount) tuple.
    """
    def _get_max_between_linear_and_degressive(linear_amount,
                                               effective_start_date=start_yearly_period):
        """For degressive methods: return max(linear_amount, degressive_amount).

        This is what makes 'degressive_then_linear' work: when degressive falls
        below linear, it automatically switches to linear.
        """
        fiscalyear_dates = self.company_id.compute_fiscalyear_dates(period_end_date)
        days_in_fiscalyear = self._get_delta_days(
            fiscalyear_dates['date_from'], fiscalyear_dates['date_to']
        )

        degressive_total_value = residual_declining * (
            1 - self.method_progress_factor
            * self._get_delta_days(effective_start_date, period_end_date)
            / days_in_fiscalyear
        )
        degressive_amount = residual_amount - degressive_total_value

        return self._degressive_linear_amount(
            residual_amount, degressive_amount, linear_amount
        )

    # Zero lifetime or zero residual = no depreciation
    if float_is_zero(self.asset_lifetime_days, 2) or float_is_zero(residual_amount, 2):
        return 0, 0

    # Calculate days in this period
    days_until_period_end = self._get_delta_days(self.paused_prorata_date, period_end_date)
    days_before_period = self._get_delta_days(
        self.paused_prorata_date, period_start_date + relativedelta(days=-1)
    )
    days_before_period = max(days_before_period, 0)
    number_days = days_until_period_end - days_before_period

    # === METHOD: LINEAR ===
    if self.method == 'linear':
        if total_lifetime_left and float_compare(total_lifetime_left, 0, 2) > 0:
            # Recomputation case (after revaluation):
            # Recompute based on remaining lifetime, not original lifetime
            computed_linear_amount = (
                residual_amount
                - residual_at_compute * (
                    1 - self._get_delta_days(start_recompute_date, period_end_date)
                    / total_lifetime_left
                )
            )
        else:
            # Normal case
            computed_linear_amount = self._get_linear_amount(
                days_before_period, days_until_period_end, self.total_depreciable_value
            )
        amount = min(abs(computed_linear_amount), abs(residual_amount), key=abs)

    # === METHOD: DEGRESSIVE ===
    elif self.method == 'degressive':
        effective_start_date = (
            max(start_yearly_period, self.paused_prorata_date)
            if start_yearly_period
            else self.paused_prorata_date
        )
        days_left_from_beginning_of_year = (
            self._get_delta_days(effective_start_date, period_start_date - relativedelta(days=1))
            + days_left_to_depreciated
        )
        expected_remaining_value_with_linear = (
            residual_declining
            - residual_declining
            * self._get_delta_days(effective_start_date, period_end_date)
            / days_left_from_beginning_of_year
        )
        linear_amount = residual_amount - expected_remaining_value_with_linear

        amount = _get_max_between_linear_and_degressive(linear_amount, effective_start_date)

    # === METHOD: DEGRESSIVE THEN LINEAR ===
    elif self.method == 'degressive_then_linear':
        if not self.parent_id:
            # Standard: use asset's own total_depreciable_value
            linear_amount = self._get_linear_amount(
                days_before_period, days_until_period_end, self.total_depreciable_value
            )
        else:
            # CHILD: match parent's depreciation curve (see Section 7)
            # The child's depreciable value is adjusted to follow parent
            parent_moves = self.parent_id.depreciation_move_ids.filtered(
                lambda mv: mv.date <= self.prorata_date
            ).sorted(key=lambda mv: (mv.date, mv.id))

            parent_cumulative = (
                parent_moves[-1].asset_depreciated_value
                if parent_moves
                else self.parent_id.already_depreciated_amount_import
            )
            parent_depreciable = (
                parent_moves[-1].asset_remaining_value
                if parent_moves
                else self.parent_id.total_depreciable_value
            )

            if self.currency_id.is_zero(parent_depreciable):
                linear_amount = self._get_linear_amount(...)
            else:
                # Adjust depreciable value to match parent curve
                depreciable_value = (
                    self.total_depreciable_value
                    * (1 + parent_cumulative / parent_depreciable)
                )
                linear_amount = (
                    self._get_linear_amount(
                        days_before_period, days_until_period_end, depreciable_value
                    )
                    * self.asset_lifetime_days / self.parent_id.asset_lifetime_days
                )

        amount = _get_max_between_linear_and_degressive(linear_amount)

    # Normalize sign for negative assets (credit notes)
    if self.currency_id.compare_amounts(residual_amount, 0) > 0:
        amount = max(amount, 0)
    else:
        amount = min(amount, 0)

    # Cap at end of lifetime
    amount = self._get_depreciation_amount_end_of_lifetime(
        residual_amount, amount, days_until_period_end
    )

    return number_days, self.currency_id.round(amount)
```

### 4.6 Linear Depreciation Detail

**For a 100,000 asset with 5-year linear, yearly:**
- `total_depreciable_value` = 100,000 - 0 = 100,000
- `method_number` = 5
- `method_period` = '12' (yearly)
- `prorata_computation_type` = 'constant_periods'
- `asset_lifetime_days` = 12 * 5 * 30 = 1800 days
- Annual depreciation = 100,000 / 5 = 20,000

If acquired mid-year (June 15):
- First period (June 15 to Dec 31): ~16/30 months
- Days calculation via `_get_delta_days` gives the fraction
- `_get_linear_amount` computes the prorated amount

### 4.7 Degressive Depreciation Detail

**For a 100,000 asset with 3-year degressive, 30% rate, yearly:**
- Year 1: 100,000 * 30% = 30,000
- Year 2: 70,000 * 30% = 21,000
- Year 3: 49,000 * 30% = 14,700 (but need to switch to linear if linear > degressive)

The `_get_max_between_linear_and_degressive` function ensures the higher of degressive and linear is used. When linear becomes higher (because remaining life is short), the method switches.

### 4.8 Degressive Then Linear Detail

This method uses the declining balance rate but ensures the asset is fully depreciated by switching to straight-line when beneficial. The switch point is automatic: whenever the declining balance depreciation would be less than what linear would give, linear is used instead.

---

## 5. Value Fields and book_value Recursion (L3)

### `_compute_book_value`: Recursive Store

```python
book_value = fields.Monetary(
    compute='_compute_book_value',
    recursive=True,   # Odoo 17+: handles circular dependency through children
    store=True,       # Persisted to DB for fast reads
    help="Sum of depreciable value, salvage value, and book value of all gross increases"
)

@api.depends('value_residual', 'salvage_value', 'children_ids.book_value')
def _compute_book_value(self):
    for record in self:
        record.book_value = (
            record.value_residual
            + record.salvage_value
            + sum(record.children_ids.mapped('book_value'))
        )
        # If fully closed and all depreciation posted: subtract salvage
        # (closed assets show 0 book value even with salvage)
        if (
            record.state == 'close'
            and all(move.state == 'posted' for move in record.depreciation_move_ids)
        ):
            record.book_value -= record.salvage_value
```

**`recursive=True` mechanism (L4):**
- Odoo 17+ ORM detects that `book_value` depends on `children_ids.book_value`
- When a child's `book_value` is written, Odoo automatically recomputes parent's `book_value`
- `store=True` means these are persisted: reads are fast (no recomputation)
- Circular dependency protection: if A has parent B, and B has parent A, Odoo prevents infinite loops
- Performance implication: each depreciation posting triggers parent recomputation via DB write

### `_compute_value_residual`

```python
@api.depends(
    'original_value', 'salvage_value', 'already_depreciated_amount_import',
    'depreciation_move_ids.state',
    'depreciation_move_ids.depreciation_value',
    'depreciation_move_ids.reversal_move_ids'
)
def _compute_value_residual(self):
    for record in self:
        posted_depreciation_moves = record.depreciation_move_ids.filtered(
            lambda mv: mv.state == 'posted'
        )
        record.value_residual = (
            record.original_value
            - record.salvage_value
            - record.already_depreciated_amount_import
            - sum(posted_depreciation_moves.mapped('depreciation_value'))
        )
```

**Important:** Only `posted` moves are counted. Draft moves are NOT subtracted, which means `value_residual` temporarily overstates the remaining amount while draft entries exist.

---

## 6. Asset Modification Wizard (L3)

Model: `asset.modify` | Transient Model | `ir.actions.act_window` (target: new)

### 6.1 Modify/Re-evaluate Flow

The `modify()` method on the wizard handles three distinct scenarios based on `modify_action`:

```python
def modify(self):
    """Entry point for all modification actions."""
    if self.date <= self.asset_id.company_id._get_user_fiscal_lock_date(...):
        raise UserError(_("Cannot modify before lock date"))

    # Capture old values for tracking/chatter
    old_values = {
        'method_number': self.asset_id.method_number,
        'method_period': self.asset_id.method_period,
        'value_residual': self.asset_id.value_residual,
        'salvage_value': self.asset_id.salvage_value,
    }

    # === RESUME AFTER PAUSE ===
    if self.env.context.get('resume_after_pause'):
        date_before_pause = max(
            asset.depreciation_move_ids, key=lambda x: x.date
        ).date if asset.depreciation_move_ids else asset.acquisition_date
        number_days = asset._get_delta_days(date_before_pause, self.date) - 1
        # If same-day pause/resume: number_days = 0
        if self.currency_id.compare_amounts(number_days, 0) < 0:
            raise UserError(_("Cannot resume at date <= pause date"))

        asset_vals.update({
            'asset_paused_days': self.asset_id.asset_paused_days + number_days,
            'state': 'open',
        })
        self.asset_id.message_post(body=_("Asset unpaused. %s", self.name))

    # === RE-EVALUATION ===
    # Calculate value change from old to new
    current_book = self.asset_id._get_own_book_value(self.date)
    after_book = self._get_own_book_value()  # wizard's value_residual + salvage_value
    increase = after_book - current_book

    # Write new depreciation parameters
    asset_vals = {
        'method_number': self.method_number,
        'method_period': self.method_period,
        'salvage_value': self.salvage_value,  # new salvage
    }

    # POSITIVE revaluation: create gross increase
    if residual_increase + salvage_increase > 0:
        reval_move = self.env['account.move'].create({
            'journal_id': self.asset_id.journal_id.id,
            'date': self.date + relativedelta(days=1),
            'move_type': 'entry',
            'asset_move_type': 'positive_revaluation',
            'line_ids': [
                Command.create({
                    'account_id': self.account_asset_id.id,
                    'debit': residual_increase + salvage_increase,
                    'credit': 0,
                    'name': _('Value increase for: %(asset)s', asset=self.asset_id.name),
                }),
                Command.create({
                    'account_id': self.account_asset_counterpart_id.id,
                    'debit': 0,
                    'credit': residual_increase + salvage_increase,
                }),
            ],
        })
        reval_move._post()

        # Create child asset (gross increase)
        asset_increase = self.env['account.asset'].create({
            'name': self.asset_id.name + ': ' + self.name,
            'parent_id': self.asset_id.id,
            'original_value': residual_increase + salvage_increase,
            'acquisition_date': self.date + relativedelta(days=1),
            # ... full field mapping from parent
        })
        asset_increase.validate()

    # NEGATIVE revaluation: create depreciation entry
    if increase < 0:
        self.env['account.move'].create(
            self.env['account.move']._prepare_move_for_asset_depreciation({
                'amount': -increase,
                'asset_id': self.asset_id,
                'asset_value_change': True,
                'asset_move_type': 'negative_revaluation',
                # ...
            })
        )._post()

    # Recompute board from modification date
    restart_date = (
        self.date
        if self.env.context.get('resume_after_pause')
        else self.date + relativedelta(days=1)
    )
    self.asset_id.compute_depreciation_board(restart_date)

    # Propagate method changes to children (gross increases)
    if computation_children_changed:
        for child in self.asset_id.children_ids:
            child.write({
                'method_number': asset_vals['method_number'],
                'method_period': asset_vals['method_period'],
                'asset_paused_days': self.asset_id.asset_paused_days,
            })
            if child.depreciation_move_ids:
                child.compute_depreciation_board(restart_date)
            child._check_depreciations()
            child.depreciation_move_ids.filtered(
                lambda mv: mv.state != 'posted'
            )._post()

    # Track changes in chatter
    tracked_fields = self.env['account.asset'].fields_get(old_values.keys())
    changes, tracking_value_ids = self.asset_id._mail_track(
        tracked_fields, old_values
    )
    if changes:
        self.asset_id.message_post(
            body=_('Depreciation board modified %s', self.name),
            tracking_value_ids=tracking_value_ids
        )
```

### 6.2 Pause/Resume Flow

**Pause (`asset.pause()`):**

```python
def pause(self, pause_date, message=None):
    """Suspend depreciation at a specific date.

    1. Create depreciation entry covering from last entry to pause_date
    2. Set state to 'paused'
    3. Message in chatter
    """
    self.ensure_one()
    # Creates final depreciation entry up to pause_date
    self._create_move_before_date(pause_date)
    self.write({'state': 'paused'})
    self.message_post(body=_("Asset paused. %s", message or ""))
```

**`_create_move_before_date()`:** This helper cancels future draft moves and creates a single depreciation entry covering the period up to the given date. It handles the complex case of finding the right beginning date for the new entry (accounting for already-posted entries and future posted entries).

**Resume (`asset.resume_after_pause()`):**

```python
def resume_after_pause(self):
    """Resume depreciation after a pause."""
    self.ensure_one()
    return self.with_context(resume_after_pause=True).action_asset_modify()
    # Opens wizard with modify_action forced to 'resume'
```

### 6.3 Disposal and Sale Flow

**`set_to_close()` and `_get_disposal_moves()`:**

```python
def set_to_close(self, invoice_line_ids, date=None, message=None):
    """Close asset and create disposal or sale journal entry.

    Args:
        invoice_line_ids: Customer invoice lines (empty = pure disposal)
        date: Disposal date (default today)
        message: Chatter message

    Closes parent + ALL children (gross increases) in one call.
    Each asset gets its own disposal move.
    """
    disposal_date = date or fields.Date.today()

    if disposal_date <= self.company_id._get_user_fiscal_lock_date(self.journal_id):
        raise UserError(_("Cannot dispose before lock date"))

    # Prevent disposal if children (gross increases) are still active
    if invoice_line_ids and self.children_ids.filtered(
        lambda a: a.state in ('draft', 'open') or a.value_residual > 0
    ):
        raise UserError(_("Dispose children assets first"))

    # Close parent + children together
    full_asset = self + self.children_ids
    full_asset.state = 'close'

    # Create disposal moves for each
    move_ids = full_asset._get_disposal_moves(
        [invoice_line_ids] * len(full_asset), disposal_date
    )

    # Calculate net gain/loss on sale
    selling_price = abs(sum(line.balance for line in invoice_line_ids))
    self.net_gain_on_sale = self.currency_id.round(selling_price - self.book_value)
```

**Disposal move structure (no invoice - pure disposal):**

```
Line 1: account_asset_id              Cr  original_value     (closes asset account)
Line 2: account_depreciation_id        Dr  accumulated_depr   (removes accumulated depr)
Line 3: gain_account_id / loss_account_id  Dr/Cr  difference     (gain or loss)
```

**Sale move structure (with customer invoice):**

```
Line 1: account_asset_id              Cr  original_value     (closes asset)
Line 2: account_depreciation_id       Dr  accumulated_depr   (removes accumulated)
Line 3: Receivable account            Dr  invoice_amount     (customer payment)
Line 4: gain_account_id / loss_account_id  Dr/Cr  difference
```

### 6.4 Gain/Loss Calculation

```python
def _compute_gain_or_loss(self):
    """Determine if disposal/sale results in gain, loss, or break-even."""
    for record in self:
        balances = abs(sum(
            invoice.balance for invoice in record.invoice_line_ids
        ))
        book_value = record.asset_id._get_own_book_value(record.date)
        comparison = record.company_id.currency_id.compare_amounts(
            book_value, balances
        )
        if record.modify_action in ('sell', 'dispose') and comparison < 0:
            record.gain_or_loss = 'gain'   # Proceeds > book value
        elif record.modify_action in ('sell', 'dispose') and comparison > 0:
            record.gain_or_loss = 'loss'   # Proceeds < book value
        else:
            record.gain_or_loss = 'no'     # Break-even
```

**L3 Edge Case:** When `invoice_line_ids` is empty (pure disposal), `balances = 0`, and `comparison > 0` (book_value > 0), so `gain_or_loss = 'loss'`. This means pure disposal always shows a loss equal to the remaining book value.

---

## 7. Gross Increase: Parent/Children Assets (L3)

Gross increases are child assets created during positive revaluation. They:
- Depreciate independently but capped at parent's remaining life
- Have their values included in parent's `book_value`
- Follow the same depreciation method as parent (copied on creation)

### Child Asset Lifetime

```python
# In _compute_lifetime_days for children:
if asset.parent_id:
    if asset.prorata_computation_type == 'daily_computation':
        parent_end_date = (
            asset.parent_id.paused_prorata_date
            + relativedelta(days=int(asset.parent_id.asset_lifetime_days - 1))
        )
    else:
        parent_end_date = (
            asset.parent_id.paused_prorata_date
            + relativedelta(
                months=int(asset.parent_id.asset_lifetime_days / DAYS_PER_MONTH),
                days=int(asset.parent_id.asset_lifetime_days % DAYS_PER_MONTH) - 1
            )
        )
    asset.asset_lifetime_days = asset._get_delta_days(
        asset.prorata_date, parent_end_date
    )
```

**Example:** Parent acquired Jan 1, 2020, 5-year life ending Dec 31, 2024. Child created July 1, 2022 (revaluation). Child's remaining life = ~2.5 years, not full 5 years.

### Child Depreciation for `degressive_then_linear`

```python
# In _compute_board_amount for degressive_then_linear with parent:
# The child's depreciable value is adjusted so its curve matches parent:
depreciable_value = (
    self.total_depreciable_value
    * (1 + parent_cumulative_depreciation / parent_depreciable_value)
)
linear_amount = (
    self._get_linear_amount(..., depreciable_value)
    * self.asset_lifetime_days / self.parent_id.asset_lifetime_days
)
```

This ensures the child follows the same depreciation curve as the parent would have continued following.

---

## 8. Auto-Creation from Vendor Bills (L3)

### Trigger Point

Auto-creation happens in `account.move._post()`:

```python
def _post(self, soft=True):
    posted = super()._post(soft)
    posted._log_depreciation_asset()
    posted.sudo()._auto_create_asset()  # Auto-create assets here
    return posted
```

### `_auto_create_asset()` Flow

```python
def _auto_create_asset(self):
    """Create draft assets from invoice lines with asset-configured accounts.

    Called via sudo() during _post().
    Processes all posted invoices in self.
    """
    create_list = []
    invoice_list = []
    auto_validate = []

    for move in self:
        if not move.is_invoice():
            continue

        for move_line in move.line_ids:
            # Skip if account can't/doesn't create assets
            if not move_line.account_id.can_create_asset:
                continue
            if move_line.account_id.create_asset == "no":
                continue
            if move_line.asset_ids:  # Already linked
                continue
            if move_line.tax_line_id:  # Tax line
                continue
            if (move_line.currency_id or move.currency_id).is_zero(move_line.price_total):
                continue
            if move_line.price_total <= 0:
                continue
            # Skip customer invoice asset accounts
            if (move.move_type in ('out_invoice', 'out_refund')
                    and move_line.account_id.internal_group == 'asset'):
                continue

            # Require a name (label) for the asset
            if not move_line.name:
                if move_line.product_id:
                    move_line.name = move_line.product_id.display_name
                else:
                    raise UserError(_(
                        "Journal Items of %(account)s should have a label "
                        "to generate an asset",
                        account=move_line.account_id.display_name
                    ))

            # Determine number of assets to create
            if move_line.account_id.multiple_assets_per_line:
                # Decimal quantities rounded DOWN to int
                units_quantity = max(1, int(move_line.quantity))
            else:
                units_quantity = 1

            # Get asset model from account configuration
            model_ids = move_line.account_id.asset_model_ids.filtered(
                lambda m: m.company_id in move_line.company_id.parent_ids
            )

            # Prepare asset values
            vals = {
                'name': move_line.name,
                'company_id': move_line.company_id.id,
                'currency_id': move_line.company_currency_id.id,
                'analytic_distribution': move_line.analytic_distribution,
                'original_move_line_ids': [(6, False, move_line.ids)],
                'state': 'draft',
                'acquisition_date': (
                    move.invoice_date
                    if not move.reversed_entry_id
                    else move.reversed_entry_id.invoice_date
                ),
            }

            # Create asset(s)
            for i in range(units_quantity):
                if units_quantity > 1:
                    vals['name'] = _(
                        "%(move_line)s (%(current)s of %(total)s)",
                        move_line=move_line.name, current=i+1, total=units_quantity
                    )
                if model_ids:
                    vals['model_id'] = model_ids[0].id
                create_list.append(vals.copy())
                auto_validate.extend([move_line.account_id.create_asset == 'validate'])
                invoice_list.extend([move])

    # Batch create all assets
    assets = self.env['account.asset'].with_context({}).create(create_list)

    # Post-creation setup
    for asset, vals, invoice, validate in zip(assets, create_list, invoice_list, auto_validate):
        if 'model_id' in vals:
            asset._onchange_model_id()  # Copy model settings
            if validate:
                asset.validate()       # Immediate validation
        if invoice:
            asset.message_post(body=_(
                "Asset created from invoice: %s", invoice._get_html_link()
            ))
            asset._post_non_deductible_tax_value()
```

---

## 9. Extended Models

### 9.1 `account.move` Extended

Model: `account.move` | Inherits: standard `account.move`

**New fields on `account.move`:**

```python
asset_id = fields.Many2one(
    'account.asset', string='Asset',
    index=True, ondelete='cascade', copy=False,
    domain="[('company_id', '=', company_id)]"
)
# Primary asset for this depreciation entry.
# Set automatically by _prepare_move_for_asset_depreciation().

asset_remaining_value = fields.Monetary(
    string='Depreciable Value',
    compute='_compute_depreciation_cumulative_value'
)
# Remaining depreciable value AFTER this entry is posted.
# Iteratively computed: each move knows its remaining value.

asset_depreciated_value = fields.Monetary(
    string='Cumulative Depreciation',
    compute='_compute_depreciation_cumulative_value'
)
# Total depreciation accumulated through this entry.
# Iteratively computed: each move knows cumulative total.

asset_value_change = fields.Boolean(
    help="True for revaluation entries (positive or negative), "
         "False for regular depreciation. Excluded from 'posted' "
         "filter in _recompute_board."
)

asset_number_days = fields.Integer(
    string="Number of days", copy=False
)
# DEPRECATED: retained for backward compatibility with imports.
# Replaced by computation via _get_delta_days.

asset_depreciation_beginning_date = fields.Date(
    string="Date of the beginning of the depreciation",
    copy=False
)
# Start date of the period this entry covers.
# Used by _get_residual_value_at_date() for mid-period valuations.

depreciation_value = fields.Monetary(
    string="Depreciation",
    compute="_compute_depreciation_value",
    inverse="_inverse_depreciation_value",
    store=True
)
# The depreciation amount. Computed from expense account line balances.
# Can be manually adjusted via inverse method.

asset_ids = fields.One2many(
    'account.asset', compute="_compute_asset_ids"
)
# Assets created from this move (purchase/revaluation moves).

asset_move_type = fields.Selection([
    ('depreciation', 'Depreciation'),
    ('sale', 'Sale'),
    ('purchase', 'Purchase'),
    ('disposal', 'Disposal'),
    ('negative_revaluation', 'Negative revaluation'),
    ('positive_revaluation', 'Positive revaluation'),
], compute='_compute_asset_move_type', store=True, copy=False)
```

**`_compute_depreciation_cumulative_value()`:**

```python
def _compute_depreciation_cumulative_value(self):
    """Iteratively compute remaining and cumulative values for each move.

    Uses self.env.protecting() to handle the case where writing
    to asset_remaining_value triggers write to the asset record,
    which in turn might read depreciation_move_ids.
    """
    self.asset_depreciated_value = 0
    self.asset_remaining_value = 0

    fields_to_protect = [
        self._fields['asset_remaining_value'],
        self._fields['asset_depreciated_value']
    ]
    with self.env.protecting(fields_to_protect, self.asset_id.depreciation_move_ids):
        for asset in self.asset_id:
            depreciated = asset.already_depreciated_amount_import
            remaining = asset.total_depreciable_value - asset.already_depreciated_amount_import

            for move in asset.depreciation_move_ids.sorted(
                lambda mv: (mv.date, mv._origin.id)
            ):
                if move.state != 'cancel':
                    remaining -= move.depreciation_value
                    depreciated += move.depreciation_value
                move.asset_remaining_value = remaining
                move.asset_depreciated_value = depreciated
```

**`_prepare_move_for_asset_depreciation()`:** (used by both asset and move models)

```python
@api.model
def _prepare_move_for_asset_depreciation(self, vals):
    """Create journal entry dict for a depreciation move.

    Creates a two-line entry:
    - Line 1 (depreciation account): credit for the amount
    - Line 2 (expense account): debit for the amount

    Handles currency conversion: amounts in asset.currency_id are
    converted to company.currency_id.
    """
    asset = vals['asset_id']
    depreciation_date = vals.get('date', fields.Date.context_today(self))
    company_currency = asset.company_id.currency_id
    current_currency = asset.currency_id
    amount_currency = vals['amount']
    amount = current_currency._convert(
        amount_currency, company_currency, asset.company_id, depreciation_date
    )

    # Keep partner from original invoice if unique
    partner = asset.original_move_line_ids.mapped('partner_id')
    partner = partner[:1] if len(partner) <= 1 else self.env['res.partner']

    move_line_1 = {
        'name': _("%s: Depreciation", asset.name),
        'partner_id': partner.id,
        'account_id': asset.account_depreciation_id.id,
        'debit': 0.0 if amount > 0 else -amount,
        'credit': amount if amount > 0 else 0.0,
        'currency_id': current_currency.id,
        'amount_currency': -amount_currency,
    }
    move_line_2 = {
        'name': _("%s: Depreciation", asset.name),
        'partner_id': partner.id,
        'account_id': asset.account_depreciation_expense_id.id,
        'credit': 0.0 if amount > 0 else -amount,
        'debit': amount if amount > 0 else 0.0,
        'currency_id': current_currency.id,
        'amount_currency': amount_currency,
    }

    # Apply analytic distribution if set on asset
    if asset.analytic_distribution:
        move_line_1['analytic_distribution'] = asset.analytic_distribution
        move_line_2['analytic_distribution'] = asset.analytic_distribution

    return {
        'partner_id': partner.id,
        'date': depreciation_date,
        'journal_id': asset.journal_id.id,
        'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
        'asset_id': asset.id,
        'ref': _("%s: Depreciation", asset.name),
        'asset_depreciation_beginning_date': vals['depreciation_beginning_date'],
        'asset_number_days': vals['asset_number_days'],
        'asset_value_change': vals.get('asset_value_change', False),
        'move_type': 'entry',
        'currency_id': current_currency.id,
        'asset_move_type': vals.get('asset_move_type', 'depreciation'),
        'company_id': asset.company_id.id,
    }
```

**`_reverse_moves()` extension:**

When a depreciation entry is reversed, the system:
1. Finds the next draft depreciation entry and adds the reversed value to it
2. If no draft entry exists (and asset not closed), creates a new depreciation entry
3. Posts a message to the asset's chatter
4. Links the reversal via `asset_id` and `asset_number_days` (negated)

### 9.2 `account.move.line` Extended

Model: `account.move.line` | Inherits: standard `account.move.line`

```python
asset_ids = fields.Many2many(
    'account.asset', 'asset_move_line_rel', 'line_id', 'asset_id',
    string='Related Assets', copy=False
)
# A single invoice line can generate multiple assets when
# multiple_assets_per_line=True. Each asset references the same line.

non_deductible_tax_value = fields.Monetary(
    compute='_compute_non_deductible_tax_value',
    currency_field='company_currency_id'
)
# Non-deductible portion of taxes on this line.
# Computed via SQL for performance, aggregating tax details.

def turn_as_asset(self):
    """Context action to convert invoice line to asset.

    Opens account.asset form with original_move_line_ids pre-filled.
    """
    return {
        "name": _("Turn as an asset"),
        "type": "ir.actions.act_window",
        "res_model": "account.asset",
        "views": `False, "form"`,
        "context": {
            'default_original_move_line_ids': [(6, False, active_ids)],
            'default_company_id': self.company_id.id,
        },
    }

def _get_computed_taxes(self):
    """Skip tax computation for lines linked to assets."""
    if self.move_id.asset_id:
        return self.tax_ids
    return super()._get_computed_taxes()
```

### 9.3 `account.account` Extended

```python
asset_model_ids = fields.Many2many(
    'account.asset',
    domain=[('state', '=', 'model')],
    help="When this account is used on a vendor bill, assets will be created "
         "from these models. If empty and create_asset != 'no', "
         "a generic draft asset is created."
)

create_asset = fields.Selection([
    ('no', 'No'),
    ('draft', 'Create in draft'),
    ('validate', 'Create and validate'),
], compute='_compute_create_asset', readonly=False, store=True,
    required=True, precompute=True)

can_create_asset = fields.Boolean(compute="_compute_can_create_asset")
# Computed: True only for account_type in ('asset_fixed', 'asset_non_current')

multiple_assets_per_line = fields.Boolean(
    default=False,
    help="When enabled on an account, invoice lines with quantity N "
         "create N separate assets instead of 1 asset for the total."
)
# Example: Bill for 5 identical computers -> 5 individual asset records.
# Decimal quantities are rounded DOWN to nearest integer.

@api.depends('asset_model_ids')
def _compute_create_asset(self):
    for account in self:
        if not account.create_asset or account.create_asset == 'no':
            account.create_asset = 'draft' if account.asset_model_ids else 'no'
```

### 9.4 `res.company` Extended

```python
gain_account_id = fields.Many2one(
    'account.account',
    check_company=True,
    help="Used when selling an asset above its book value (gain on sale). "
         "Set at company level as default for asset disposal."
)

loss_account_id = fields.Many2one(
    'account.account',
    check_company=True,
    help="Used when selling an asset below its book value (loss on sale)."
)
```

### 9.5 `account.chart.template` Extended

```python
@template(model='account.asset')
def _get_account_asset(self, template_code):
    """Import asset models from CSV template.

    Allows defining asset model templates in the accounting data files.
    Each row in the CSV becomes a account.asset record with state='model'.
    """
    return {
        xmlid: {
            'state': 'model',  # Always imported as model, not asset
            **vals,
        }
        for xmlid, vals in self._parse_csv(template_code, 'account.asset').items()
    }
```

### 9.6 `account.return` Extended

```python
def _check_suite_annual_closing(self, check_codes_to_ignore):
    """Annual closing validation: check if depreciation was posted.

    Adds a check that runs during the annual closing sequence.
    If 'check_fixed_assets' is not in ignored codes, verifies that
    at least one open asset had depreciation entries in the period.
    """
    checks = super()._check_suite_annual_closing(check_codes_to_ignore)

    if 'check_fixed_assets' not in check_codes_to_ignore:
        domain = [
            ('company_id', 'in', self.company_ids.ids),
            ('state', '=', 'open'),
            ('depreciation_move_ids', '!=', False),
            ('depreciation_move_ids.date', '<=', fields.Date.to_string(self.date_to)),
            ('depreciation_move_ids.date', '>=', fields.Date.to_string(self.date_from)),
        ]
        fixed_assets_exist = self.env['account.asset'].sudo().search_count(domain, limit=1)
        if not fixed_assets_exist:
            checks.append({
                'name': _("Fixed Assets"),
                'message': _(
                    "Odoo manages depreciation for your fixed assets. "
                    "No depreciation was recorded for this period."
                ),
                'code': 'check_fixed_assets',
                'result': 'todo',
            })
    return checks
```

---

## 10. Depreciation Report Handler (L3)

Model: `account.asset.report.handler` | Abstract report engine

### Report Purpose

Generates the "Depreciation Schedule" report showing asset values and accumulated depreciation across a fiscal period.

### Report Columns

| Group | Columns |
|-------|---------|
| Characteristics | Acquisition Date, Method, Duration/Rate |
| Assets | Opening, +, -, Closing |
| Depreciation | Opening, +, -, Closing |
| Book Value | Net book value at period end |

### Key Query: `_query_values()`

```python
def _query_values(self, options):
    """SQL query aggregating asset and depreciation data for the report.

    Key aggregations:
    - depreciated_before: depreciation posted BEFORE date_from
    - depreciated_during: depreciation posted BETWEEN date_from and date_to
    - asset_disposal_value: depreciation on disposal day (for gain/loss calc)

    Filters applied:
    - asset.acquisition_date <= date_to OR has moves <= date_to
    - asset.disposal_date >= date_from OR disposal_date IS NULL
    - asset.state not in ('model', 'draft', 'cancelled')
    - asset.active = True
    - company in report companies
    """
    SQL(
        """
        SELECT
            asset.id AS asset_id,
            asset.parent_id AS parent_id,
            asset.name AS asset_name,
            asset.asset_group_id AS asset_group_id,
            asset.original_value AS asset_original_value,
            asset.currency_id AS asset_currency_id,
            COALESCE(asset.salvage_value, 0) AS asset_salvage_value,
            MIN(move.date) AS asset_date,
            asset.disposal_date AS asset_disposal_date,
            asset.acquisition_date AS asset_acquisition_date,
            asset.method AS asset_method,
            asset.method_number AS asset_method_number,
            asset.method_period AS asset_method_period,
            asset.method_progress_factor AS asset_method_progress_factor,
            asset.state AS asset_state,
            -- Depreciation aggregations
            COALESCE(SUM(move.depreciation_value)
                FILTER (WHERE move.date < %(date_from)s), 0)
            + COALESCE(asset.already_depreciated_amount_import, 0)
            AS depreciated_before,
            COALESCE(SUM(move.depreciation_value)
                FILTER (WHERE move.date BETWEEN %(date_from)s AND %(date_to)s), 0)
            AS depreciated_during,
            COALESCE(SUM(move.depreciation_value)
                FILTER (WHERE move.date BETWEEN %(date_from)s AND %(date_to)s
                        AND move.asset_number_days IS NULL), 0)
            AS asset_disposal_value
        FROM account_asset asset
        JOIN account_account account ON asset.account_asset_id = account.id
        LEFT JOIN account_move move ON (
            move.asset_id = asset.id
            AND move.state = 'posted'
        )
        WHERE asset.company_id IN %(company_ids)s
          AND (asset.acquisition_date <= %(date_to)s OR move.date <= %(date_to)s)
          AND (asset.disposal_date >= %(date_from)s OR asset.disposal_date IS NULL)
          AND asset.state NOT IN ('model', 'draft', 'cancelled')
          AND asset.active = 't'
        GROUP BY asset.id, account_id, account_code, account_name
        ORDER BY account_code, asset.acquisition_date, asset.id
        """
    )
```

### Report Grouping

The report supports grouping by:
- `account_id` (default): Groups assets under their fixed asset accounts
- `asset_group_id`: Groups assets under asset group categories
- `none`: Flat list of all assets

Additionally, the report hierarchy follows `account.group` (account groups) when present, providing: Account Group -> Account -> Asset.

### Parent/Children Merging

```python
def _get_parent_asset_values(self, options, asset_line, asset_children_lines):
    """Merge children (gross increase) values into parent asset.

    For each column (opening, additions, etc.), children values are
    added to parent values:
    - asset_opening += children.opening (if opened before date_from)
    - asset_add += children.add (if opened in period)
    - depreciation_opening += children's depreciated_before
    - depreciation_add += children's depreciated_during

    This ensures gross increases appear as adjustments to the parent
    in the depreciation schedule report, not as separate rows.
    """
    for child in asset_children_lines:
        depreciation_opening += child['depreciated_before']
        depreciation_add += child['depreciated_during']
        # ... merge other columns ...
```

---

## 11. Performance Considerations (L4)

### O(N*M) Board Computation Complexity

```python
# In _recompute_board():
while residual_amount != 0 and start < final_date:
    days, amount = self._compute_board_amount(...)  # O(1) per period

    # In _get_linear_amount() called from _compute_board_amount():
    amount_of_decrease_spread_over_period = [
        number_days * mv.depreciation_value / (
            self.asset_lifetime_days
            - self._get_delta_days(paused_prorata_date, mv.asset_depreciation_beginning_date)
        )
        for mv in self.depreciation_move_ids.filtered(lambda mv: mv.asset_value_change)
    ]  # O(M) where M = number of value changes
```

For an asset with:
- N = 60 periods (5 years monthly)
- M = 2 value changes (two revaluations)
- Total `_get_delta_days` calls = O(N * (1 + M)) ≈ 180 calls
- Each with constant-time arithmetic

**Mitigation:** The inner loop (M value changes) only iterates over `asset_value_change=True` moves, which are rare (revaluations happen infrequently).

### `book_value` Recursive Store: Cascading Writes

```python
# When child's book_value changes:
child.book_value = new_value  # Triggers write

# Odoo with recursive=True automatically:
# 1. Writes child.book_value to DB
# 2. Finds parent(s) depending on child.parent_id
# 3. Reads parent's value_residual, salvage_value, children_ids.book_value
# 4. Computes new parent.book_value
# 5. Writes parent.book_value to DB
# 6. Repeats for grandparent if exists

# For a 3-level hierarchy: 1 child write -> 2 parent writes -> 1 grandparent write
```

### `_compute_depreciation_cumulative_value`: Iterative Computation

```python
# Called when viewing the asset form (to show depreciation board lines)
# Also called when any depreciation move's fields are read
for asset in self.asset_id:
    for move in asset.depreciation_move_ids.sorted(...):  # O(K) per asset
        move.asset_remaining_value = remaining
        move.asset_depreciated_value = depreciated
```

For an asset with 60 depreciation entries, this loop runs 60 iterations. With `store=True` on `asset_remaining_value` and `asset_depreciated_value`, these values are cached.

### Batch Move Creation

```python
# All depreciation moves created in a single batch call
new_depreciation_moves = self.env['account.move'].create(
    new_depreciation_moves_data  # List of 1-60 dicts
)
```

This is significantly faster than creating moves one at a time (single SQL INSERT vs N INSERT statements).

---

## 12. Key Constants and Version History (L4)

```python
DAYS_PER_MONTH = 30   # Accounting convention: each month = 30 days
DAYS_PER_YEAR = 360   # 12 * 30
```

### Odoo 18 to 19 Changes

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| Prorata field | Boolean `prorata` | `prorata_computation_type` Selection |
| Salvage calculation | Manual only | `salvage_value_pct` on model |
| Children depreciation | Basic | Inherits parent's curve for degressive_then_linear |
| Prorata date | Computed per-entry | Centralized in `prorata_date` + `paused_prorata_date` |
| Depreciation board | Regenerated on change | Selective unlink + recompute from date |
| Import handling | Complex | `already_depreciated_amount_import` streamlined |
| Non-deductible tax | Basic | Enhanced with multi-currency conversion |

### Historical Note: 30-Day Month Convention

The `constant_periods` prorata type uses a 30-day month regardless of actual calendar days. This is a legacy accounting convention (used in Swiss, French, Belgian accounting) that ensures:
- Consistent depreciation amounts across months
- Simple calculations without calendar irregularity
- Alignment with manual ledger-based accounting

Modern companies requiring calendar-accurate depreciation use `daily_computation`.

---

## 13. Edge Cases (L3)

### Same-Day Pause and Resume

```python
number_days = asset._get_delta_days(pause_date, resume_date) - 1
# If pause_date == resume_date:
# _get_delta_days returns 1 (inclusive)
# number_days = 0 (no additional paused days)
```

### Disposal Date at Period Boundary

Depreciation entries with `date == disposal_date` are included in `all_lines_before_disposal`, ensuring full period depreciation is captured before disposal.

### Negative Assets (Credit Notes)

```python
# In _get_parent_asset_values for report:
if asset_currency.compare_amounts(asset_line['asset_original_value'], 0) < 0:
    asset_add, asset_minus = -asset_minus, -asset_add
    depreciation_add, depreciation_minus = -depreciation_minus, -depreciation_add
```

Negative `original_value` (from refunds/credit notes) flips the +/- columns in the depreciation schedule report.

### Lock Date Validation

Every state-changing operation validates against the fiscal lock date:
- `set_to_close`: disposal_date > lock_date
- `pause`: creates moves before lock_date (blocked if pause_date <= lock_date via `_create_move_before_date`)
- `modify`: modification date > lock_date

### Future-Dated Depreciation Reversal Block

```python
# In asset_modify.create():
if asset.depreciation_move_ids.filtered(
    lambda m: m.state == 'posted'
    and not m.reversal_move_ids
    and m.date > fields.Date.today()
):
    raise UserError(_('Reverse the depreciation entries posted in the future...'))
```

You cannot modify an asset if it has future-dated posted depreciation entries. They must be reversed first.

### Multi-Company Asset Creation

```python
model_ids = move_line.account_id.asset_model_ids.filtered(
    lambda model: model.company_id in move_line.company_id.parent_ids
)
```

Models must belong to the same company as the invoice line or to a parent company. This prevents cross-company asset creation.

### Circular Parent-Child Prevention

A child asset cannot itself have children of the same parent (direct acyclic graph enforced by `parent_id` being a single Many2one, not recursive). However, a child can have its own children (grandchildren), creating deeper hierarchies.

### Asset with No Depreciation (Salvage = Original)

```python
if float_is_zero(self.asset_lifetime_days, 2) or float_is_zero(residual_amount, 2):
    return 0, 0
```

If `salvage_value = original_value`, then `value_residual = 0`, and no depreciation entries are created. The asset can still be disposed of (creating a disposal entry).

### Reversal of Depreciation Moves

```python
def _reverse_moves(self, default_values_list=None, cancel=False):
    for move, default_values in zip(self, default_values_list):
        if move.asset_id:
            first_draft = min(
                move.asset_id.depreciation_move_ids.filtered(lambda m: m.state == 'draft'),
                key=lambda m: m.date, default=None
            )
            if first_draft:
                # Add reversed value to existing draft entry
                first_draft.depreciation_value += move.depreciation_value
            elif move.asset_id.state != 'close':
                # Create new replacement entry
                self.create(self._prepare_move_for_asset_depreciation({...}))
```

---

## 14. Integration Points

| Source | Target | Integration |
|--------|--------|-------------|
| Vendor bill posting | `account.asset` | `_auto_create_asset()` creates draft assets |
| Invoice line | `account.asset` | `original_move_line_ids` (Many2many) |
| Depreciation move | `account.asset` | `depreciation_move_ids` (One2many) |
| Asset modification | `account.move` | `_prepare_move_for_asset_depreciation()` |
| Revaluation | `account.asset` (child) | `parent_id` creates gross increase child |
| Annual closing | `account.return` | `check_fixed_assets` validation |
| Chart of accounts | `account.asset` (model) | CSV template import |
| Account config | `account.asset` | `asset_model_ids`, `create_asset` on account |
| Company settings | Disposal | `gain_account_id`, `loss_account_id` |

---

## See Also

- [Modules/Account](odoo-18/Modules/account.md) - Journal entries that become asset acquisitions
- [Modules/account_analytic](odoo-19/Modules/account_analytic.md) - Analytic distribution on asset depreciation
- [Modules/account_accountant](odoo-17/Modules/account_accountant.md) - Required EE framework dependency
- [Core/API](odoo-18/Core/API.md) - @api.depends, computed fields, recursive store
- [Core/Fields](odoo-18/Core/Fields.md) - Monetary fields, Many2many relations
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) - ACL for asset models
