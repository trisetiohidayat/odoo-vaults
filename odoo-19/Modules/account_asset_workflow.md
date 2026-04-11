---
tags: [odoo, odoo19, enterprise, modules, account_asset, fixed_assets, depreciation, workflow, state_machine]
description: L4 depth — account.asset lifecycle, depreciation board computation, asset.modify wizard, account.move extensions, and bridge modules (fleet, project). Enterprise Edition.
---

# account.asset — Asset Lifecycle & Depreciation Board (Enterprise)

> **Module:** `account_asset` (Enterprise) | **Model:** `account.asset`
> **Source:** `enterprise/account_asset/models/account_asset.py` (1236 lines)
> **Wizard:** `enterprise/account_asset/wizard/asset_modify.py` (405 lines)
> **Version:** Odoo 19 (Enterprise) | License: OEEL-1
> **Depends:** `accountant` | **Category:** `Accounting/Accounting` | **Auto-install:** `True`
> **Tags:** `#odoo` `#odoo19` `#enterprise` `#account_asset` `#depreciation` `#workflow` `#fixed_assets`

---

## Overview

The `account.asset` model (internal name: `account.asset`) is the central entity in Odoo's Fixed Asset management and Revenue Recognition system. It supports two primary use cases: **fixed asset depreciation** (property, plant & equipment) and **deferred revenue recognition**. The model implements a complete asset lifecycle state machine with support for pausing/resuming depreciation, gross increases (revaluation), partial disposal, and sale — all driven by a configurable depreciation board that generates `account.move` entries automatically.

The model inherits from `mail.thread`, `mail.activity.mixin`, and `analytic.mixin`, giving it full chatter, activity, and analytic distribution capabilities.

---

## Module Constants

Defined at module load time (lines 15–16):

```python
DAYS_PER_MONTH = 30    # Fixed 30-day month for depreciation calculations
DAYS_PER_YEAR = 360    # DAYS_PER_MONTH * 12
```

These constants drive all period-length computations. They represent a **fictional 360-day year** (12 x 30-day months), which is standard in many accounting jurisdictions (e.g., French accounting plan). The `daily_computation` mode bypasses these for actual day counts.

---

## L1 — All Fields on `account.asset`

### Identity & Company Fields

```python
name = fields.Char(
    string='Asset Name',
    compute='_compute_name',    # Falls back to first move line name
    store=True,
    required=True,
    readonly=False,
    tracking=True
)
company_id = fields.Many2one(
    'res.company',
    string='Company',
    required=True,
    default=lambda self: self.env.company
)
country_code = fields.Char(related='company_id.account_fiscal_country_id.code')
currency_id = fields.Many2one(
    'res.currency',
    related='company_id.currency_id',
    store=True
)
active = fields.Boolean(default=True)
```

- **`name`** — Computed from the first `original_move_line_ids` name if not manually set. Can be edited manually. Tracked via mail chatter.
- **`company_id`** — Multi-company aware; all account/journal lookups are scoped by company.
- **`country_code`** — Derived from the company's fiscal country; used to switch country-specific behavior.
- **`currency_id`** — Related to company's primary currency; stored for query efficiency.
- **`active`** — Soft-delete flag. Assets can be archived only when in `close` or `model` state (`@api.constrains` enforced).

### State Field

```python
state = fields.Selection(
    selection=[
        ('model',   'Model'),
        ('draft',   'Draft'),
        ('open',    'Running'),
        ('paused',  'On Hold'),
        ('close',   'Closed'),
        ('cancelled', 'Cancelled'),
    ],
    string='Status',
    copy=False,
    default='draft',
    readonly=True,
)
```

- **`model`** — Template asset used to pre-configure default values for newly created assets. Cannot be validated directly; used as a blueprint via `model_id` field.
- **`draft`** — Initial state when an asset is created. All fields are editable. Can transition to `open` via `validate()` or back to `model` via `set_to_draft()`.
- **`open`** — Running state. Depreciation entries are posted. Most field modifications trigger board recomputation.
- **`paused`** — Depreciation is suspended. Pausing creates a final depreciation entry up to the pause date and clears future unposted entries. Can be resumed via `resume_after_pause()`.
- **`close`** — Asset is fully disposed or sold. All depreciation entries are posted. Book value is adjusted (salvage value subtracted).
- **`cancelled`** — Asset is cancelled; all posted depreciation entries are reversed, draft entries deleted.

> **Constraint:** Assets not in `close` or `model` state cannot be archived (`_check_active`).

### Depreciation Method Fields

```python
method = fields.Selection(
    selection=[
        ('linear',                  'Straight Line'),
        ('degressive',              'Declining'),
        ('degressive_then_linear',  'Declining then Straight Line'),
    ],
    string='Method',
    default='linear',
)

method_number = fields.Integer(
    string='Duration',
    default=5,
    help="The number of depreciations needed to depreciate your asset"
)

method_period = fields.Selection(
    [('1', 'Months'), ('12', 'Years')],
    string='Number of Months in a Period',
    default='12',
    help="The amount of time between two depreciations"
)

method_progress_factor = fields.Float(
    string='Declining Factor',
    default=0.3,
)
```

**Depreciation method behavior:**

- **`linear` (Straight Line):** Constant amount per period. `depreciation = total_depreciable_value / asset_lifetime_days` per day unit.
- **`degressive` (Declining Balance):** Declining amount using `method_progress_factor` as the yearly decline rate applied to the remaining (declining) balance.
- **`degressive_then_linear`:** Starts with declining balance but switches to straight line when that yields a higher amount. Ensures the asset is never under-depreciated.

```python
prorata_computation_type = fields.Selection(
    selection=[
        ('none',               'No Prorata'),
        ('constant_periods',   'Constant Periods'),
        ('daily_computation',  'Based on days per period'),
    ],
    string="Computation",
    required=True,
    default='constant_periods',
)
```

- **`none`** — No first-period prorata. Depreciation starts from the fiscal year start date (computed via `_compute_prorata_date`). Suitable when you want alignment with fiscal years.
- **`constant_periods`** — First period is prorated from `prorata_date` to end of first fiscal period. All subsequent periods are full periods (months or years).
- **`daily_computation`** — Every period is prorated based on actual days elapsed. Uses `_get_delta_days` in daily mode (actual calendar days, no 30-day fiction). More accurate for assets acquired mid-period.

```python
prorata_date = fields.Date(
    string='Prorata Date',
    compute='_compute_prorata_date',
    store=True,
    readonly=False,
    required=True,
    precompute=True,
    copy=True,
)

paused_prorata_date = fields.Date(
    compute='_compute_paused_prorata_date',
    # number of days to shift the computation of future deprecations
)
```

- **`prorata_date`** — The starting date for depreciation. When `prorata_computation_type == 'none'`, computed as the fiscal year start date. Otherwise equals `acquisition_date`.
- **`paused_prorata_date`** — Effective start date after accounting for pause days. Equal to `prorata_date + paused_days`. Used as the reference for all day-delta calculations after a pause.

```python
asset_lifetime_days = fields.Float(
    compute="_compute_lifetime_days",
    recursive=True,
    # total number of days to consider for the computation of an asset depreciation board
)
asset_paused_days = fields.Float(copy=False)
```

- **`asset_lifetime_days`** — Total depreciable lifetime in days, computed differently per `prorata_computation_type`:
  - `daily_computation`: actual calendar days from prorata date to end of last period.
  - Otherwise: `method_period * method_number * DAYS_PER_MONTH` (30-day fiction).
  - For child assets (gross increases): remaining days left on the parent asset's lifetime.
- **`asset_paused_days`** — Accumulated number of days the asset was paused. Added to `prorata_date` to compute `paused_prorata_date`. Prevents depreciation during pause periods.

### Account Configuration Fields

```python
account_asset_id = fields.Many2one(
    'account.account',
    string='Fixed Asset Account',
    compute='_compute_account_asset_id',
    store=True,
    readonly=False,
    check_company=True,
    domain="[('account_type', '!=', 'off_balance')]",
    help="Account used to record the purchase of the asset at its original price.",
)

account_depreciation_id = fields.Many2one(
    'account.account',
    string='Depreciation Account',
    check_company=True,
    domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance'))]",
    help="Account used in the depreciation entries, to decrease the asset value.",
)

account_depreciation_expense_id = fields.Many2one(
    'account.account',
    string='Expense Account',
    check_company=True,
    domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance'))]",
    help="Account used in the periodical entries, to record a part of the asset as expense.",
)

journal_id = fields.Many2one(
    'account.journal',
    string='Journal',
    check_company=True,
    domain="[('type', '=', 'general')]",
    compute='_compute_journal_id',
    store=True,
    readonly=False,
)
```

- **`account_asset_id`** — The balance sheet account where the asset's original value sits. Set from `original_move_line_ids.account_id` if linked to journal entries; otherwise defaults from depreciation account.
- **`account_depreciation_id`** — Contra-asset account that accumulates depreciation. Credited each depreciation period; reduces the book value on the balance sheet.
- **`account_depreciation_expense_id`** — Income statement account debited each depreciation period (records depreciation as an expense).
- **`journal_id`** — General journal for depreciation entries. Auto-searched with company + `type='general'` domain if not set.

### Value / Monetary Fields

```python
original_value = fields.Monetary(
    string="Original Value",
    compute='_compute_value',
    store=True,
    readonly=False,
)

book_value = fields.Monetary(
    string='Book Value',
    readonly=True,
    compute='_compute_book_value',
    recursive=True,    # Cascade compute through parent/child hierarchy
    store=True,
    help="Sum of the depreciable value, the salvage value and the book value of all value increase items"
)

value_residual = fields.Monetary(
    string='Depreciable Value',
    compute='_compute_value_residual',
)

salvage_value = fields.Monetary(
    string='Not Depreciable Value',
    compute="_compute_salvage_value",
    store=True,
    readonly=False,
    help="It is the amount you plan to have that you cannot depreciate.",
)

salvage_value_pct = fields.Float(
    string='Not Depreciable Value Percent',
    help="It is the amount you plan to have that you cannot depreciate.",
)

total_depreciable_value = fields.Monetary(
    compute='_compute_total_depreciable_value',
)

gross_increase_value = fields.Monetary(
    string="Gross Increase Value",
    compute="_compute_gross_increase_value",
    compute_sudo=True,
)

non_deductible_tax_value = fields.Monetary(
    string="Non Deductible Tax Value",
    compute="_compute_non_deductible_tax_value",
    store=True,
    readonly=True,
)

related_purchase_value = fields.Monetary(
    compute='_compute_related_purchase_value',
)

already_depreciated_amount_import = fields.Monetary(
    help="In case of an import from another software, you might need to use this field "
         "to have the right depreciation table report. This is the value that was "
         "already depreciated with entries not computed from this model",
)

net_gain_on_sale = fields.Monetary(
    string="Net gain on sale",
    help="Net value of gain or loss on sale of an asset",
    copy=False,
)
```

- **`original_value`** — The asset's acquisition cost. Computed from `related_purchase_value` (sum of `balance * deductible_amount`) plus `non_deductible_tax_value`. Raises `UserError` if linked move lines are not posted.
- **`book_value`** — `value_residual + salvage_value + sum(children_ids.book_value)`. Note: when `state == 'close'` and all depreciation moves are posted, salvage_value is subtracted (the asset is removed from the balance sheet). `recursive=True` means it recomputes whenever any child asset changes.
- **`value_residual`** — Amount still to be depreciated. `original_value - salvage_value - already_depreciated_amount_import - sum(posted_depreciation_moves.depreciation_value)`.
- **`salvage_value`** — Residual value at end of life (not depreciated). If a model is set with `salvage_value_pct != 0`, the salvage is computed as `original_value * salvage_value_pct`; otherwise manually entered.
- **`gross_increase_value`** — Sum of `original_value` of all child assets (gross increases linked via `parent_id`).
- **`non_deductible_tax_value`** — Portion of taxes on the asset purchase that cannot be deducted. Computed from `original_move_line_ids.non_deductible_tax_value`, properly converted to the company's currency and adjusted for `deductible_amount`.
- **`already_depreciated_amount_import`** — For data migration; amount already depreciated before importing into Odoo. Subtracted from the first depreciation entries until exhausted.
- **`net_gain_on_sale`** — Computed on disposal: `selling_price - book_value`. Positive = gain, negative = loss.

### Date Fields

```python
acquisition_date = fields.Date(
    compute='_compute_acquisition_date',
    store=True,
    precompute=True,
    readonly=False,
    copy=True,
)

disposal_date = fields.Date(
    readonly=False,
    compute="_compute_disposal_date",
    store=True,
)
```

- **`acquisition_date`** — Earliest date among `invoice_date` or `date` of `original_move_line_ids`. Precomputed and stored.
- **`disposal_date`** — Set only when `state == 'close'`. Derived from the latest posted depreciation move date.

### Model / Template Fields

```python
model_id = fields.Many2one(
    'account.asset',
    string='Model',
    change_default=True,
    domain="[('company_id', '=', company_id)]",
)

account_type = fields.Selection(
    string="Type of the account",
    related='account_asset_id.account_type',
)

display_account_asset_id = fields.Boolean(
    compute="_compute_display_account_asset_id",
)
```

- **`model_id`** — Links an asset to a template/model asset (state=`model`). When set, an `onchange` copies all depreciation method settings from the model. The model's `original_value` is ignored; only its configuration fields are inherited.

### Parent / Child (Gross Increase) Fields

```python
parent_id = fields.Many2one(
    'account.asset',
    index=True,
    help="An asset has a parent when it is the result of gaining value",
)

children_ids = fields.One2many(
    'account.asset',
    'parent_id',
    help="The children are the gains in value of this asset",
)
```

- **`parent_id`** / **`children_ids`** — Self-referential hierarchy for gross increases (revaluations). When an asset is re-evaluated upward via `asset.modify` wizard with `modify_action='modify'`, a new child asset is created and linked here. Child assets depreciate independently but their book values cascade into the parent's `book_value`.

### Journal Entry Link Fields

```python
depreciation_move_ids = fields.One2many(
    'account.move',
    'asset_id',
    string='Depreciation Lines',
)

original_move_line_ids = fields.Many2many(
    'account.move.line',
    'asset_move_line_rel',
    'asset_id',
    'line_id',
    string='Journal Items',
    copy=False,
)
```

- **`depreciation_move_ids`** — All `account.move` records generated from depreciation. Each move represents one depreciation period. States: `draft` (pending), `posted` (confirmed).
- **`original_move_line_ids`** — The source journal item lines from which the asset was created (typically from a vendor bill or invoice). Changing these after the asset is running raises a constraint error.

### Properties & Analytic

```python
asset_properties_definition = fields.PropertiesDefinition('Model Properties')
asset_properties = fields.Properties(
    'Properties',
    definition='model_id.asset_properties_definition',
    copy=True,
)

analytic_distribution = fields.Json(
    # Inherited from analytic.mixin
)
```

- **`asset_properties`** — Arbitrary properties defined on the model asset (e.g., location, insurance policy number). Inherited from the model via `model_id.asset_properties_definition`.

### Asset Group

```python
asset_group_id = fields.Many2one(
    'account.asset.group',
    string='Asset Group',
    tracking=True,
    index=True,
)
```

- **`asset_group_id`** — Groups related assets (e.g., by category, department, or location). Used for reporting and batch operations.

### Linked Assets & Counts

```python
linked_assets_ids = fields.One2many(
    comodel_name='account.asset',
    compute='_compute_linked_assets',
)
count_linked_asset = fields.Integer(compute="_compute_linked_assets")
warning_count_assets = fields.Boolean(compute="_compute_linked_assets")
```

- **`linked_assets_ids`** — Assets linked via the same `original_move_line_ids` (i.e., multiple assets created from the same invoice line). Used to detect conflicts during disposal.
- **`warning_count_assets`** — Turns the smart button red when any linked asset is in `open` state, alerting the user that disposal may affect other assets.

### Computed Count Fields

```python
depreciation_entries_count = fields.Integer(
    compute='_compute_counts',
    string='# Posted Depreciation Entries',
)
gross_increase_count = fields.Integer(
    compute='_compute_counts',
    string='# Gross Increases',
)
total_depreciation_entries_count = fields.Integer(
    compute='_compute_counts',
    string='# Depreciation Entries',
)
```

---

## L2 — Asset Lifecycle, Depreciation Board & Account Configuration

### State Machine — Complete Lifecycle

```
  ┌─────────────────────────────────────────────────────────────┐
  │                        MODEL                                │
  │  (Template — not depreciable, used as default config)      │
  └──────────────────┬──────────────────────────────────────────┘
                     │ create from model / save as model
                     ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                        DRAFT                                │
  │  All fields editable. Can set model_id to copy config.     │
  │  When original_move_line_ids set: accounts auto-populate.   │
  └──────────────────┬──────────────────────────────────────────┘
                     │ validate()  ──► creates depreciation board
                     ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                         OPEN                                │
  │  Running. Board entries posted/pending.                     │
  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐   │
  │  │   pause()    │  │  action_asset │  │  set_to_close  │   │
  │  │  (On Hold)   │  │   _modify     │  │   (Dispose)    │   │
  │  └──────┬───────┘  └───────┬──────┘  └───────┬───────┘   │
  │         │                  │                  │            │
  │         ▼                  ▼                  ▼            │
  │  ┌──────────────┐  ┌─────────────────┐  ┌───────────┐    │
  │  │    PAUSED    │  │ Modify/Revalue  │  │   CLOSE    │    │
  │  │              │  │  (re-evaluate)  │  │            │    │
  │  │ resume_after_│  │  (gross increase│  │  Full disc │    │
  │  │   pause()    │  │   created)      │  │  or sale   │    │
  │  └──────┬───────┘  └────────┬────────┘  └───────────┘    │
  │         │                   │                             │
  │         └───────────────────┘                             │
  │                  back to OPEN                              │
  └─────────────────────────────────────────────────────────────┘

  set_to_cancelled()  ──► CANCELLED  (any non-close state)
  set_to_draft()      ──► DRAFT      (from model only)
```

### Depreciation Board Structure

The depreciation board is a sequence of `account.move` records stored in `depreciation_move_ids`. Each move represents one depreciation period and is created by `compute_depreciation_board()`.

**Board entry data (prepared by `account.move._prepare_move_for_asset_depreciation`):**

| Field | Purpose |
|-------|---------|
| `asset_id` | Link back to the asset |
| `depreciation_value` | Amount to depreciate this period |
| `asset_depreciation_beginning_date` | Start date of the period covered |
| `asset_remaining_value` | Residual value after this move |
| `asset_depreciated_value` | Cumulative depreciation after this move |
| `asset_number_days` | Number of days in the period |
| `asset_value_change` | Boolean; true for revaluation (positive/negative) entries |
| `asset_move_type` | `depreciation` / `positive_revaluation` / `negative_revaluation` / `disposal` / `sale` |

**Board computation flow:**

```
compute_depreciation_board(date=False)
  │
  ├─► 1. Unlink all draft moves (with date >= threshold)
  │
  ├─► 2. For each asset: _recompute_board(start_date)
  │       │
  │       ├─► Get posted moves, imported amount, residual
  │       ├─► Compute final depreciation date
  │       ├─► Loop while residual > 0 and date < final:
  │       │     ├─► _get_end_period_date(start)
  │       │     ├─► _compute_board_amount(residual, start, end, ...)
  │       │     ├─► residual -= amount
  │       │     ├─► Create move record via _prepare_move_for_asset_depreciation
  │       │     └─► Advance start = end + 1 day
  │       └─► Return list of move vals
  │
  └─► 3. Create all moves, then _post() those whose asset is 'open'
```

**Special behavior for `open` assets:**
- When an asset is `open` (state='open'), `_post()` is called automatically on newly created moves, so future-dated entries are set to auto-post.
- For `draft` assets, moves remain in draft until `validate()` is called.

### Account Configuration Per Asset Type

The three required accounts are configured at different levels:

| Account | Source Priority | Domain Constraint |
|---------|-----------------|-------------------|
| `account_asset_id` | 1. `original_move_line_ids.account_id`, 2. `account_depreciation_id`, 3. Model default | `account_type != 'off_balance'` |
| `account_depreciation_id` | 1. Model default, 2. Manual | Not receivable/payable/cash/credit_card/off_balance |
| `account_depreciation_expense_id` | 1. Model default, 2. Manual | Not receivable/payable/cash/credit_card/off_balance |
| `journal_id` | 1. Model default, 2. Search `type='general'` | `type == 'general'` |

The account selection is validated in `_check_depreciations`: when `state == 'open'`, the last depreciation move's `asset_remaining_value` must be zero (otherwise the asset is under- or over-depreciated).

### First Depreciation Date Logic

The first depreciation date depends on `prorata_computation_type`:

1. **`none`**: `_compute_prorata_date` sets `prorata_date` to the **fiscal year start** (`company_id.compute_fiscalyear_dates(acquisition_date).date_from`). This means depreciation starts from the beginning of the fiscal year, even if the asset was acquired mid-year.

2. **`constant_periods` or `daily_computation`**: `prorata_date = acquisition_date`. The first period is prorated from acquisition date to the end of that period.

The `_get_end_period_date()` method determines each period's end date:
- For monthly (`method_period='1'`): end of the month containing `start_date`, capped at fiscal year end.
- For yearly (`method_period='12'`): fiscal year end.

---

## L3 — Workflow Methods & Board Computation

### `action_asset_modify()` — Modify Wizard Launcher

```python
def action_asset_modify(self):
    """Returns an action opening the asset modification wizard."""
    self.ensure_one()
    new_wizard = self.env['asset.modify'].create({
        'asset_id': self.id,
        'modify_action': 'resume' if self.env.context.get('resume_after_pause') else 'dispose',
    })
    return {
        'name': _('Modify Asset'),
        'view_mode': 'form',
        'res_model': 'asset.modify',
        'type': 'ir.actions.act_window',
        'target': 'new',
        'res_id': new_wizard.id,
        'context': self.env.context,
    }
```

- Opens the `asset.modify` wizard in a modal dialog.
- Sets `modify_action` to `'resume'` when called from `resume_after_pause()`, otherwise defaults to `'dispose'`.
- Used by the "Modify" button on the asset form.

### `validate()` — Draft to Open Transition

```python
def validate(self):
    fields = ['method', 'method_number', 'method_period',
              'method_progress_factor', 'salvage_value', 'original_move_line_ids']
    ref_tracked_fields = self.env['account.asset'].fields_get(fields)
    self.write({'state': 'open'})
    for asset in self:
        # Track changes from model defaults
        tracked_fields = ref_tracked_fields.copy()
        if asset.method == 'linear':
            del tracked_fields['method_progress_factor']
        dummy, tracking_value_ids = asset._mail_track(tracked_fields, dict.fromkeys(fields))
        asset.message_post(body=..., tracking_value_ids=tracking_value_ids)
        # Post message on source moves
        for move_id in asset.original_move_line_ids.mapped('move_id'):
            move_id.message_post(body=msg)
        try:
            if not asset.depreciation_move_ids:
                asset.compute_depreciation_board()  # Generate board if not already done
            asset._check_depreciations()
            asset.depreciation_move_ids.filtered(lambda move: move.state != 'posted')._post()
        except psycopg2.errors.CheckViolation:
            raise ValidationError(_("Atleast one asset (%s) couldn't be set as running..."))
        if asset.account_asset_id.create_asset == 'no':
            asset._post_non_deductible_tax_value()
```

**Key behaviors:**
- Triggers mail tracking for method changes (suppresses `method_progress_factor` when `method='linear'`).
- If no depreciation moves exist yet, calls `compute_depreciation_board()` immediately.
- Posts all draft depreciation entries.
- Catches `CheckViolation` (e.g., required fields missing) and re-raises as `ValidationError`.
- Posts a chatter message on the source vendor bill/invoice.

### `set_to_close()` — Disposal / Sale

```python
def set_to_close(self, invoice_line_ids, date=None, message=None):
    self.ensure_one()
    disposal_date = date or fields.Date.today()
    if disposal_date <= self.company_id._get_user_fiscal_lock_date(self.journal_id):
        raise UserError(_("You cannot dispose of an asset before the lock date."))
    if invoice_line_ids and self.children_ids.filtered(
        lambda a: a.state in ('draft', 'open') or a.value_residual > 0
    ):
        raise UserError(_("You cannot automate the journal entry for an asset "
                          "that has a running gross increase..."))
    full_asset = self + self.children_ids  # Include all gross increases
    full_asset.state = 'close'
    move_ids = full_asset._get_disposal_moves([invoice_line_ids] * len(full_asset), disposal_date)
    selling_price = abs(sum(invoice_line.balance for invoice_line in invoice_line_ids))
    self.net_gain_on_sale = self.currency_id.round(selling_price - self.book_value)
```

- **Precondition:** Disposal date must be after the fiscal lock date.
- **Children included:** All gross increases (`children_ids`) are closed together with the parent asset.
- **Journal entry:** `_get_disposal_moves()` creates the disposal entry:
  - Dr. Depreciation Account (accumulated depreciation)
  - Dr./Cr. Gain/Loss Account (difference between book value and sale proceeds)
  - Cr. Fixed Asset Account (original value)
  - Dr./Cr. Cash/Receivable (sale proceeds, if `invoice_line_ids` provided)
- **`net_gain_on_sale`** = selling price - book value (positive = gain, negative = loss).

### `pause()` — Open to Paused

```python
def pause(self, pause_date, message=None):
    """Sets an 'open' asset in 'paused' state, generating first a depreciation
    line corresponding to the ratio of time spent within the current depreciation
    period before putting the asset in pause. This line and all the previous
    unposted ones are then posted."""
    self.ensure_one()
    self._create_move_before_date(pause_date)  # Creates and posts the partial entry
    self.write({'state': 'paused'})
    self.message_post(body=_("Asset paused. %s", message if message else ""))
```

- Calls `_create_move_before_date(pause_date)` which:
  1. Identifies all posted moves before the pause date.
  2. Cancels all future moves after the pause date.
  3. Computes a prorated depreciation amount up to the pause date.
  4. Inserts a new move for the partial period and posts it.
- Sets `state = 'paused'`.

### `resume_after_pause()` — Paused to Open

```python
def resume_after_pause(self):
    """Sets an asset in 'paused' state back to 'open'.
    A Depreciation line is created automatically to remove from the
    depreciation amount the proportion of time spent in pause in the current period."""
    self.ensure_one()
    return self.with_context(resume_after_pause=True).action_asset_modify()
```

- Delegates to `action_asset_modify()` with `resume_after_pause=True` context.
- The wizard computes `number_days` (pause duration) and adds it to `asset_paused_days`.
- `paused_prorata_date` is shifted forward by the pause duration, extending the asset's life.

### `set_to_running()` — Reset to Running

```python
def set_to_running(self):
    if self.depreciation_move_ids and not max(
        self.depreciation_move_ids, key=lambda m: (m.date, m.id)
    ).asset_remaining_value == 0:
        self.env['asset.modify'].create({
            'asset_id': self.id,
            'name': _('Reset to running')
        }).modify()
    self.write({
        'state': 'open',
        'net_gain_on_sale': 0
    })
```

- **If the last depreciation move's `asset_remaining_value != 0`** (i.e., the board is incomplete), opens the modification wizard to recompute the board before resetting state.
- **If the board is complete** (remaining value = 0), simply resets state to `open` and clears `net_gain_on_sale`.

### `set_to_cancelled()` — Cancel Asset

```python
def set_to_cancelled(self):
    for asset in self:
        posted_moves = asset.depreciation_move_ids.filtered(lambda m: (
            not m.reversal_move_ids and not m.reversed_entry_id and m.state == 'posted'
        ))
        if posted_moves:
            # Compute reversal amounts
            depreciation_change = sum(posted_moves.line_ids.mapped(
                lambda l: l.debit if l.account_id == asset.account_depreciation_expense_id else 0.0
            ))
            acc_depreciation_change = sum(posted_moves.line_ids.mapped(
                lambda l: l.credit if l.account_id == asset.account_depreciation_id else 0.0
            ))
            # Cancel future moves first
            asset._cancel_future_moves(datetime.date.min)
            # Post reversal message to chatter
            asset._message_log(body=msg)  # details of reversed entries
        # Delete draft entries
        asset.depreciation_move_ids.filtered(lambda m: m.state == 'draft')\
            .with_context(force_delete=True).unlink()
        asset.asset_paused_days = 0
        asset.write({'state': 'cancelled'})
```

- Reverses all posted depreciation entries by posting reversal moves.
- Posts a detailed chatter message showing which entries were reversed and the amounts credited/debited to expense vs. depreciation accounts.
- Resets `asset_paused_days` to 0.

### `compute_depreciation_board()` — Board Generator

```python
def compute_depreciation_board(self, date=False):
    # 1. Unlink draft moves at or after the threshold date
    self.depreciation_move_ids.filtered(
        lambda mv: mv.state == 'draft' and (mv.date >= date if date else True)
    ).unlink()

    new_depreciation_moves_data = []
    for asset in self:
        new_depreciation_moves_data.extend(asset._recompute_board(date))

    new_depreciation_moves = self.env['account.move'].create(new_depreciation_moves_data)
    new_depreciation_moves_to_post = new_depreciation_moves.filtered(
        lambda move: move.asset_id.state == 'open'
    )
    # In case of the asset is in running mode, we post in the past
    # and set to auto post move in the future
    new_depreciation_moves_to_post._post()
```

- **Unlinks draft moves** before regenerating to prevent duplicates.
- Calls `_recompute_board()` for each asset.
- For `open` assets: posts all new moves immediately (including future-dated ones, which the `_post()` mechanism handles by setting them to auto-post).
- For `draft` assets: moves remain in draft.

### `_recompute_board()` — Core Board Algorithm

```python
def _recompute_board(self, start_depreciation_date=False):
    self.ensure_one()
    posted = self.depreciation_move_ids.filtered(
        lambda mv: mv.state == 'posted' and not mv.asset_value_change
    ).sorted(key=lambda mv: (mv.date, mv.id))

    imported_amount = self.already_depreciated_amount_import
    residual_amount = self.value_residual - sum(
        self.depreciation_move_ids.filtered(lambda mv: mv.state == 'draft').mapped('depreciation_value')
    )
    if not posted:
        residual_amount += imported_amount
    residual_declining = residual_at_compute = residual_amount
    start_recompute_date = start_depreciation_date = start_yearly_period = \
        start_depreciation_date or self.paused_prorata_date

    last_day_asset = self._get_last_day_asset()
    final_depreciation_date = self._get_end_period_date(last_day_asset)
    total_lifetime_left = self._get_delta_days(start_depreciation_date, last_day_asset)

    depreciation_move_values = []
    if not float_is_zero(self.value_residual, precision_rounding=self.currency_id.rounding):
        while not self.currency_id.is_zero(residual_amount) and \
              start_depreciation_date < final_depreciation_date:
            period_end = self._get_end_period_date(start_depreciation_date)
            days, amount = self._compute_board_amount(
                residual_amount, start_depreciation_date, period_end,
                False, lifetime_left, residual_declining,
                start_yearly_period, total_lifetime_left,
                residual_at_compute, start_recompute_date
            )
            residual_amount -= amount
            # Handle already_depreciated_amount_import: subtract from first entries
            if not posted:
                if abs(imported_amount) <= abs(amount):
                    amount -= imported_amount
                    imported_amount = 0
                else:
                    imported_amount -= amount
                    amount = 0
            if not float_is_zero(amount, ...):
                depreciation_move_values.append(
                    self.env['account.move']._prepare_move_for_asset_depreciation({...})
                )
            start_depreciation_date = period_end + relativedelta(days=1)
    return depreciation_move_values
```

### `_compute_board_amount()` — Period Amount Calculator

The most complex method. Computes the depreciation for a single period given:
- `residual_amount` — remaining depreciable value
- `period_start_date`, `period_end_date` — the period boundaries
- `days_left_to_depreciated` — total days remaining
- `residual_declining` — declining balance base (for degressive methods)
- `start_yearly_period` / `total_lifetime_left` / `residual_at_compute` / `start_recompute_date` — for linear recompute scenarios

**Linear method:**
```python
if self.method == 'linear':
    if total_lifetime_left and float_compare(total_lifetime_left, 0, 2) > 0:
        # Recomputing from a mid-life date: use remaining / total ratio
        computed_linear_amount = residual_amount - residual_at_compute * (
            1 - self._get_delta_days(start_recompute_date, period_end_date) / total_lifetime_left
        )
    else:
        computed_linear_amount = self._get_linear_amount(
            days_before_period, days_until_period_end, self.total_depreciable_value
        )
    amount = min(computed_linear_amount, residual_amount, key=abs)
```

**Degressive method:**
```python
# Linear amount from beginning of year to end of period
expected_remaining_value_with_linear = residual_declining - residual_declining * \
    self._get_delta_days(effective_start_date, period_end_date) / days_left_from_beginning_of_year
linear_amount = residual_amount - expected_remaining_value_with_linear
amount = _get_max_between_linear_and_degressive(linear_amount, effective_start_date)
```

**`degressive_then_linear` method:**
- Computes the linear amount on the **total depreciable value** (or for children: an adjusted depreciable value scaled by the parent's remaining ratio).
- Uses `max(degressive, linear)` to ensure the asset is never under-depreciated.

The `_get_linear_amount()` helper computes:
```
linear = total_depreciable_value * (days_until_period_end / asset_lifetime_days)
       - total_depreciable_value * (days_before_period / asset_lifetime_days)
       - sum(value_decreases_from_gross_increases)
```

### `_get_delta_days()` — Day Count (Two Modes)

```python
def _get_delta_days(self, start_date, end_date):
    self.ensure_one()
    if self.prorata_computation_type == 'daily_computation':
        # Actual calendar days: (end - start).days + 1
        return (end_date - start_date).days + 1
    else:
        # 30-day fictional month method (constant_periods / none)
        # Each month = 30 days regardless of actual calendar length
        start_date_days_month = end_of(start_date, 'month').day
        start_prorata = (start_date_days_month - start_date.day + 1) / start_date_days_month
        end_prorata = end_date.day / end_of(end_date, 'month').day
        return sum((
            start_prorata * DAYS_PER_MONTH,           # partial start month
            end_prorata * DAYS_PER_MONTH,             # partial end month
            (end_date.year - start_date.year) * DAYS_PER_YEAR,  # full years
            (end_date.month - start_date.month - 1) * DAYS_PER_MONTH  # full months
        ))
```

**Example — `constant_periods` mode:**
- Asset starts June 20, period ends August 14
- `start_prorata` = (30 - 20 + 1) / 30 = 11/30 (June's remaining 11 days as 30-day-equivalent)
- `end_prorata` = 14 / 31 (August's 14 days as 30-day-equivalent)
- Result = 11 + 14 + 360*(2020-2020) + 30*(8-6-1) = ~54.55 "30-day months"

**Example — `daily_computation` mode:**
- Same dates: (Aug 14 - Jun 20).days + 1 = 56 actual days

### `action_asset_modify()` in Wizard (`asset.modify.modify()`)

The wizard's `modify()` method (405 lines) handles four actions:

1. **`dispose`** — Calls `asset.set_to_close()` with no invoice lines. Posts a disposal journal entry removing the asset from the balance sheet.
2. **`sell`** — Same as dispose but with invoice lines representing the sale proceeds. Computes gain/loss from book value vs. selling price.
3. **`modify` (Re-evaluate)** — The most complex path:
   - Calls `_create_move_before_date(date)` to finalize depreciation up to the modify date.
   - Computes `current_asset_book = asset._get_own_book_value(date)`.
   - Computes `after_asset_book = wizard._get_own_book_value()` (from new salvage/value_residual).
   - **If book value increased**: Creates a revaluation journal entry (Dr. Fixed Asset, Cr. Counterpart), then **creates a new child asset** (gross increase) with `parent_id = self.asset_id`. The child is validated immediately and begins depreciating.
   - **If book value decreased**: Creates a negative revaluation depreciation entry (`asset_value_change=True`).
   - Recomputes the depreciation board from `date + 1 day`.
   - If `method_number` or `method_period` changed: propagates changes to all children and recomputes their boards too.
4. **`pause`** — Delegates to `asset.pause()`.

---

## L4 — Performance, Security & Edge Cases

### O(N x M) Compute Performance

The depreciation board computation has polynomial complexity:

- **`N`** = number of assets being processed in a single `compute_depreciation_board()` call
- **`M`** = number of depreciation periods (approximately `method_number` for linear, potentially more for degressive)

For each period, `_compute_board_amount()` performs:
- Fiscal year date computation: `company_id.compute_fiscalyear_dates()` — potentially a DB query or complex computation.
- `_get_delta_days()` — arithmetic operations (fast) or `end_of()` calls from `date_utils` (moderate cost).
- Currency rounding: `self.currency_id.round(amount)` — database-level precision handling.

**Performance profile:**
- A 5-year monthly asset = 60 periods. One `compute_depreciation_board()` on a batch of 100 such assets = 6,000 period computations.
- The `while` loop in `_recompute_board()` terminates early when `residual_amount` reaches zero, but degressive methods can produce more periods than `method_number` suggests.
- The `_post()` call on each new move is the dominant cost for large batches — consider batching assets by journal for bulk posting.

**Optimization strategies:**
- `compute_depreciation_board()` is typically called interactively or from the wizard, not in bulk workflows. For bulk operations, consider overriding with `batch=True`.
- The `already_depreciated_amount_import` handling subtracts from the first entries, reducing the total number of entries needed.
- Child asset board recomputation (`modify()` → `children.write()` → `child.compute_depreciation_board()`) can cascade for deep revaluation chains.

### `prorata_computation_type` — Three Computation Modes

| Mode | First Period | Subsequent Periods | Accuracy | Use Case |
|------|-------------|-------------------|----------|----------|
| `none` | Full period (fiscal year start) | Full periods | Low | Aligned with fiscal year; simplest |
| `constant_periods` | Prorated from `prorata_date` to period end | Full periods | Medium | Most common; prorates first period only |
| `daily_computation` | Prorated (actual days) | Prorated (actual days) | High | Assets acquired mid-month; maximum precision |

**`daily_computation` mode:**
- `_get_delta_days()` returns `(end_date - start_date).days + 1` (inclusive day count).
- `_get_last_day_asset()` computes: `prorata_date + relativedelta(months=period*number, days=-1)` — but in actual calendar days.
- `paused_prorata_date` accumulates `asset_paused_days` in actual calendar days (not 30-day units).
- `asset_lifetime_days` = actual calendar days between prorata date and end of last period.

**Constant periods mode (`constant_periods` / `none`):**
- Uses the 360-day year (30-day fictional months) throughout.
- `_get_delta_days()` uses partial-month fractions for start and end periods.
- `paused_prorata_date` adds `asset_paused_days / 30` months + remainder days.
- More stable depreciation amounts (no variation from month length differences).

### Book Value Cascade (Recursive Store)

```python
book_value = fields.Monetary(
    compute='_compute_book_value',
    recursive=True,  # Odoo 16+: recomputes when children change
    store=True,
)

@api.depends('value_residual', 'salvage_value', 'children_ids.book_value')
def _compute_book_value(self):
    for record in self:
        record.book_value = (
            record.value_residual
            + record.salvage_value
            + sum(record.children_ids.mapped('book_value'))  # recursive!
        )
        if record.state == 'close' and all(
            move.state == 'posted' for move in record.depreciation_move_ids
        ):
            record.book_value -= record.salvage_value
```

- `recursive=True` — Odoo's ORM marks this field as needing cascade recomputation whenever any child asset's `book_value` changes. This ensures that revaluing a gross increase automatically updates the parent's book value without explicit recomputation.
- The `state == 'close'` adjustment subtracts salvage value because a closed asset is no longer on the balance sheet — its book value should be zero at that point.
- **Security note:** Users with write access to child assets (gross increases) can indirectly affect the parent's `book_value`. Access control should consider the parent-child relationship.

### Asset Modification Wizard (`asset.modify`)

The wizard is a **TransientModel** (data is not persisted long-term), which means:
- It runs with the permissions of the current user (not superuser).
- It can only access records the user has rights to.
- The `asset_id` is a `Many2one` to the real `account.asset`.

**`gain_value` computation:**
```python
def _compute_gain_value(self):
    for record in self:
        record.gain_value = record.currency_id.compare_amounts(
            record._get_own_book_value(),       # New book value from wizard fields
            record.asset_id._get_own_book_value(record.date)  # Current book value at date
        ) > 0
```
Positive `gain_value` triggers creation of a gross increase child asset.

**Child asset creation from wizard (`modify()`):**
```python
asset_increase = self.env['account.asset'].create({
    'name': self.asset_id.name + ': ' + self.name,
    ...
    'parent_id': self.asset_id.id,  # Links as gross increase
    'original_move_line_ids': [(6, 0, move.line_ids.filtered(...).ids)],
})
asset_increase.validate()  # Immediately transitions to 'open'
```
The child asset is validated immediately, computing its own depreciation board independently. The parent's `book_value` picks up the child's `original_value` through the cascade.

### Lock Date Protection

Multiple methods enforce fiscal lock date:

```python
# set_to_close
if disposal_date <= self.company_id._get_user_fiscal_lock_date(self.journal_id):
    raise UserError(_("You cannot dispose of an asset before the lock date."))

# asset.modify.modify
if self.date <= self.asset_id.company_id._get_user_fiscal_lock_date(...):
    raise UserError(_("You can't re-evaluate the asset before the lock date."))
```

- The lock date is company-specific and set by the accounting manager.
- Prevents posting entries in locked (already closed) accounting periods.

### Import Safety (`already_depreciated_amount_import`)

When migrating from legacy systems, assets may already be partially depreciated:

```python
if not posted_depreciation_move_ids:
    residual_amount += imported_amount
```

The imported amount is added to the residual before computing the board. Subsequent board entries have the imported amount subtracted from the first ones until exhausted:
```python
if abs(imported_amount) <= abs(amount):
    amount -= imported_amount
    imported_amount = 0
else:
    imported_amount -= amount
    amount = 0
```

This ensures the total depreciation over the asset's life equals `original_value - salvage_value`, regardless of pre-import depreciation.

### Constraint: No Bill Changes After Running

```python
@api.constrains('original_move_line_ids')
def _check_related_purchase(self):
    for asset in self:
        if asset.original_move_line_ids and asset.related_purchase_value == 0:
            raise UserError(_("You cannot create an asset from lines containing "
                               "credit and debit on the account or with a null amount"))
        if asset.state not in ('model', 'draft'):
            raise UserError(_("You cannot add or remove bills when the asset "
                               "is already running or closed."))
```

- Once an asset is `open`, `paused`, or `close`, its source journal items cannot be modified. This prevents accounting inconsistencies.
- Zero-balance lines (equal debits and credits on the same account) are rejected.

### Constraint: Remaining Value Must Be Zero

```python
@api.constrains('depreciation_move_ids')
def _check_depreciations(self):
    for asset in self:
        if (
            asset.state == 'open'
            and asset.depreciation_move_ids
            and not asset.currency_id.is_zero(
                asset.depreciation_move_ids.sorted(...)[-1].asset_remaining_value
            )
        ):
            raise UserError(_("The remaining value on the last depreciation line must be 0"))
```

- Enforced only when `state == 'open'`. Prevents leaving an asset with unrecovered book value.
- This is why `set_to_running()` checks the last move's `asset_remaining_value` before allowing reset.

### Unlink Protection

```python
@api.ondelete(at_uninstall=True)
def _unlink_if_model_or_draft(self):
    for asset in self:
        if asset.state in ['open', 'paused', 'close']:
            raise UserError(_("You cannot delete a document that is in %s state."))
        posted_amount = len(asset.depreciation_move_ids.filtered(lambda x: x.state == 'posted'))
        if posted_amount > 0:
            raise UserError(_("You cannot delete an asset linked to posted entries."))
```

- Assets in running/paused/closed states cannot be deleted at all (even at module upgrade).
- Assets with any posted depreciation entries cannot be deleted.
- This is an `at_uninstall=True` constraint, which means it also fires during module upgrades (unlike regular `constrains`).

### Write Side Effects

```python
def write(self, vals):
    result = super().write(vals)
    for asset in self:
        for move in asset.depreciation_move_ids:
            if move.state == 'draft' and 'analytic_distribution' in vals:
                move.line_ids.analytic_distribution = vals['analytic_distribution']
            lock_date = move.company_id._get_user_fiscal_lock_date(asset.journal_id)
            if move.date > lock_date:
                if 'account_depreciation_id' in vals:
                    move.line_ids[::2].account_id = vals['account_depreciation_id']   # Every other (first line)
                if 'account_depreciation_expense_id' in vals:
                    move.line_ids[1::2].account_id = vals['account_depreciation_expense_id']  # Every other (second line)
                if 'journal_id' in vals:
                    move.journal_id = vals['journal_id']
    return result
```

- When depreciation accounts or journal are changed, all **draft** future moves are updated in-place (avoiding unlink/recreate overhead).
- Changes to posted moves are not allowed (lock date check prevents it).
- Analytic distribution is propagated to draft depreciation entry lines.

### LIFETIME_DAYS Constant

The fictional constant for the 360-day year (12 months x 30 days) is used throughout:

- `_compute_lifetime_days`: `method_period * method_number * DAYS_PER_MONTH`
- `_get_delta_days()` (constant_periods mode): partial-month fractions multiplied by `DAYS_PER_MONTH`
- `_get_last_day_asset()`: `paused_prorata_date + relativedelta(months=period*number, days=-1)`

The `asset_lifetime_days` computed field stores this as a `Float` (not `Integer`) to accommodate the fractional day counts from the 30-day month method.

### Asset Group (Categorization)

The `asset_group_id` Many2one field provides a grouping mechanism for reporting but does not affect depreciation computation. It is primarily used in:
- Asset reports (grouped balance sheet view)
- Batch validation/disposal actions
- Access control scoping (if combined with record rules)

---

## Wizard: `asset.modify` Field Reference

| Field | Type | Purpose |
|-------|------|---------|
| `asset_id` | Many2one | Target asset |
| `modify_action` | Selection | `dispose`, `sell`, `modify`, `pause`, `resume` |
| `method_number` | Integer | New depreciation duration |
| `method_period` | Selection | New period length |
| `value_residual` | Monetary | New depreciable amount (computed from `_get_residual_value_at_date(date)`) |
| `salvage_value` | Monetary | New salvage value |
| `date` | Date | Date of the operation (default: today) |
| `account_asset_id` | Many2one | Fixed asset account for gross increase |
| `account_asset_counterpart_id` | Many2one | Counterpart for revaluation journal entry |
| `account_depreciation_id` | Many2one | Depreciation account for child asset |
| `account_depreciation_expense_id` | Many2one | Expense account for child asset |
| `gain_account_id` / `loss_account_id` | Many2one | Gain/loss accounts (from company) |
| `invoice_ids` | Many2many | Customer invoice for sale |
| `invoice_line_ids` | Many2many | Invoice lines for sale proceeds |
| `gain_or_loss` | Selection | Computed: `gain` / `loss` / `no` |
| `gain_value` | Boolean | Computed: true if book value increased |
| `informational_text` | Html | User-facing summary of what the action will do |

---

## Field Dependencies Map

```
original_move_line_ids
  ├─► original_value         (_compute_value)
  ├─► acquisition_date       (_compute_acquisition_date)
  ├─► name                   (_compute_name)
  ├─► account_asset_id       (_compute_account_asset_id)
  ├─► analytic_distribution (_compute_analytic_distribution)
  ├─► related_purchase_value (_compute_related_purchase_value)
  ├─► non_deductible_tax_value (_compute_non_deductible_tax_value)
  ├─► display_account_asset_id (_compute_display_account_asset_id)
  └─► linked_assets_ids       (_compute_linked_assets)

model_id
  ├─► name (if not set)
  └─► onchange: copies method, accounts, journal, analytic_distribution

depreciation_move_ids
  ├─► value_residual         (_compute_value_residual)
  ├─► disposal_date          (_compute_disposal_date)
  ├─► depreciation_entries_count  (_compute_counts)
  └─► total_depreciation_entries_count (_compute_counts)

children_ids.book_value  ──►  book_value (recursive=True, _compute_book_value)
parent_id                 ──►  children_ids (inverse)
                              ├─► asset_lifetime_days  (_compute_lifetime_days) [for child]
                              └─► gross_increase_value (_compute_gross_increase_value)

method_number + method_period + prorata_computation_type
  └─► asset_lifetime_days     (_compute_lifetime_days)

acquisition_date + company_id + prorata_computation_type
  └─► prorata_date            (_compute_prorata_date)

prorata_date + prorata_computation_type + asset_paused_days
  └─► paused_prorata_date      (_compute_paused_prorata_date)
```


---

## Bridge Modules

The `account_asset` ecosystem includes two auto-install bridge modules:

### `account_asset_fleet` — Vehicles as Assets

**Path:** `enterprise/account_asset_fleet/` (auto-install bridge)

**Depends:** `account_fleet` + `account_asset`

**Purpose:** Adds vehicle-specific fields to `account.asset` by injecting a `fleet.vehicle` link into the asset form, enabling fleet managers to manage company vehicles as formal accounting assets.

**Manifest:**
```python
{
    'name': 'Assets/Fleet bridge',
    'category': 'Accounting/Accounting',
    'summary': 'Manage assets with fleets',
    'version': '1.0',
    'depends': ['account_fleet', 'account_asset'],
    'data': ['views/account_asset_views.xml', 'views/account_move_views.xml'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
```

**Cross-module relationship:**
- `account.asset` records that represent company vehicles gain a `fleet.vehicle` link
- The bridge module adds vehicle-specific view buttons and fields to the asset form
- Depreciation of vehicles follows the same `account.asset` lifecycle as any fixed asset
- When a vehicle is disposed (via `set_to_close()`), the fleet record can be archived

**Typical usage:** A company that uses Odoo Fleet to track vehicles will install `account_asset_fleet` so that each vehicle acquisition creates both a `fleet.vehicle` record and an `account.asset` record. The asset's depreciation entries post to the accounting ledger automatically.

---

### `project_account_asset` — Project Asset Count

**Path:** `enterprise/project_account_asset/` (auto-install bridge)

**Depends:** `project` + `account_asset`

**Purpose:** Adds a computed integer field `asset_count` to `project.project`, showing the number of assets whose analytic account is linked to the project. This is a read-only informational bridge (no workflow changes).

**Manifest:**
```python
{
    'name': 'Project Accounting Assets',
    'version': '1.0',
    'category': 'Services/assets',
    'summary': 'Bridge created to add the number of assets linked to an AA to a project form',
    'depends': ['project', 'account_asset'],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
```

**Cross-module relationship:**
- Reads `account.asset` records that have analytic distribution entries pointing to the project
- Displays the count on the project form as a smart button or stat label
- Does not create or modify assets; purely informational

---

## Odoo 18 → 19 Changes

Key behavioral changes in Odoo 19 versus Odoo 18 for `account_asset`:

### 1. `prorata_computation_type` Split (Odoo 17+)

The old `prorata` boolean field was replaced by a selection field with three options (`none`, `constant_periods`, `daily_computation`). This change (introduced in Odoo 17) persists in Odoo 19. When migrating, any asset with `prorata=True` should map to `prorata_computation_type='constant_periods'`.

### 2. Recursive `book_value` Store (Odoo 16+)

The `book_value` field uses `recursive=True`, meaning the ORM automatically recomputes it when any child asset's `book_value` changes. This eliminates the need for explicit recomputation after gross increase creation. Child depreciation changes cascade up to the parent's reported book value without manual triggers.

### 3. `_onchange_model_id` Now Copies Analytic Distribution

The `onchange` handler on `model_id` was extended to also copy `analytic_distribution` from the model to the asset. This ensures that analytic tags are inherited consistently when creating an asset from a template.

### 4. `analytic.mixin` Integration (Odoo 14+)

The `analytic_distribution` JSON field (from `analytic.mixin`) is automatically propagated from `original_move_line_ids` to the asset, and from there to all generated depreciation entries. Changing the analytic distribution on an open asset updates all draft depreciation entry lines in-place.

### 5. Asset Creation from Bill Post (Odoo 16+)

The `_post()` override on `account.move` calls `_auto_create_asset()` on posted invoices. Assets are created in draft state and optionally auto-validated if the account's `create_asset` field is set to `'validate'`. This happens at bill posting time, not at bill creation, so assets appear as draft until the invoice is confirmed.

### 6. `asset_move_type` on `account.move` (Odoo 16+)

The `asset_move_type` selection field on `account.move` tracks the purpose of each depreciation-related move. Values include `depreciation`, `sale`, `purchase`, `disposal`, `positive_revaluation`, `negative_revaluation`. This field is computed from the presence/absence of `asset_id` and `asset_ids` on the move.

---

## Quick Reference: All Action Methods

| Method | Transitions From | Transitions To | Wizard? |
|--------|-----------------|---------------|---------|
| `validate()` | `draft` | `open` | No |
| `set_to_draft()` | `model` | `draft` | No |
| `set_to_running()` | `close` | `open` | Conditional |
| `pause()` | `open` | `paused` | Internal |
| `resume_after_pause()` | `paused` | `open` | Yes (`asset.modify`) |
| `set_to_close()` | `open`, `paused` | `close` | Yes (`asset.modify`) |
| `set_to_cancelled()` | `draft`, `model`, `open`, `paused` | `cancelled` | No |

> **Note:** `set_to_running()` only opens the modification wizard if the last depreciation move's `asset_remaining_value != 0`. If the board is already complete, it resets state directly.

---

## Quick Reference: Constraint Summary

| Constraint | Enforced When | Failure Mode |
|-----------|--------------|--------------|
| `_check_active` | Archive attempt | `UserError`: "You cannot archive a record that is not closed" |
| `_check_depreciations` | State becomes `open` | `UserError`: "The remaining value on the last depreciation line must be 0" |
| `_check_related_purchase` | `original_move_line_ids` change or asset non-draft | `UserError`: "You cannot add or remove bills when the asset is already running" |
| `CheckViolation` (DB) | `validate()` with missing required fields | `ValidationError` caught and re-raised |
| Fiscal lock date | Any write/create that would post in locked period | `UserError`: "You cannot ... before the lock date" |
| `_unlink_if_model_or_draft` | `at_uninstall=True` unlink attempt | Prevents deletion of running/paused/closed assets |
