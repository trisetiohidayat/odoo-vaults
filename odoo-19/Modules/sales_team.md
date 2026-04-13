# sales_team

**Category:** Sales/Sales  
**Depends:** `base`, `mail`  
**Author:** Odoo S.A.  
**License:** LGPL-3  
**Module Path:** `odoo/addons/sales_team/`

Sales Teams management. Organizes salespersons into teams with shared pipelines, dashboards, and activity tracking. Provides the core `crm.team` and `crm.team.member` models that are the foundation for CRM pipeline, sales assignment, and reporting across all Sales-related modules in Odoo.

---

## L1: Core Models Overview

### 4.1 Models Inventory

| Model | Kind | File | Description |
|-------|------|------|-------------|
| `crm.team` | Main | `models/crm_team.py` | Sales team configuration with membership management |
| `crm.team.member` | Main | `models/crm_team_member.py` | Explicit membership record linking a user to a team |
| `crm.tag` | Main | `models/crm_tag.py` | Color-coded tags applied to CRM leads/opportunities |
| `res.users` | Extended | `models/res_users.py` | Adds computed `crm_team_ids`, `sale_team_id` to users |

### 4.2 Module Structure

```
sales_team/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── crm_team.py          # CrmTeam (main model)
│   ├── crm_team_member.py   # CrmTeamMember (membership)
│   ├── crm_tag.py           # CrmTag
│   └── res_users.py         # ResUsers extension
├── security/
│   ├── sales_team_security.xml
│   └── ir.model.access.csv
├── data/
│   ├── crm_team_data.xml    # Default team (Website Sales)
│   ├── crm_team_demo.xml
│   └── crm_tag_demo.xml
├── views/
│   ├── crm_team_views.xml
│   ├── crm_team_member_views.xml
│   ├── crm_tag_views.xml
│   └── mail_activity_views.xml
└── static/
    ├── src/
    └── tests/
```

### 4.3 Dependency Graph

```
base  (required)
 mail  (required)
   └── sales_team
         ├── crm          (extends crm.team, adds pipeline views)
         ├── sale         (uses crm.team for team assignment)
         ├── sale_quotation  (uses crm.team)
         ├── crm_helpdesk  (uses crm.team for tickets)
         └── utm          (crm.team tagged with utm sources)
```

`sales_team` itself has minimal dependencies: `base` and `mail`. All other modules that need sales team functionality depend on it.

---

## L2: Field-Level Documentation

### `crm.team` — Field Inventory

**File:** `models/crm_team.py`  
**Inherits:** `mail.thread`  
**Order:** `sequence ASC, create_date DESC, id DESC`  
**Check Company:** `True`

| Field | Type | Required | Default | Stored | Description |
|-------|------|----------|---------|--------|-------------|
| `name` | Char | Yes | — | Yes | Team display name, `translate=True` |
| `sequence` | Integer | No | `10` | Yes | Sort order among teams |
| `active` | Boolean | No | `True` | Yes | Soft-delete / archive flag |
| `company_id` | Many2one `res.company` | No | — | Yes | Team's owning company; if set, restricts membership |
| `currency_id` | Many2one `res.currency` | — | — | Yes | Related from `company_id.currency_id`, readonly |
| `user_id` | Many2one `res.users` | No | — | Yes | Team leader / responsible person; domain: `('share', '!=', True)` |
| `is_membership_multi` | Boolean | — | `False` | Yes (computed) | `True` if `sales_team.membership_multi` config is enabled |
| `member_ids` | Many2many `res.users` | No | — | No | Active members; **computed + inverse** from `crm_team_member_ids` |
| `member_company_ids` | Many2many `res.company` | — | — | No | Computed: team company or all companies if no company set |
| `member_warning` | Text | — | `False` | No | Computed warning when adding single-team user to another team |
| `crm_team_member_ids` | One2many `crm.team.member` | No | — | Yes | Explicit membership records; context `active_test: True` |
| `crm_team_member_all_ids` | One2many `crm.team.member` | No | — | Yes | All memberships including inactive; context `active_test: False` |
| `color` | Integer | No | random 1–11 | Yes | Kanban color index |
| `favorite_user_ids` | Many2many `res.users` | No | `[self.env.uid]` | Yes | Users who bookmarked this team |
| `is_favorite` | Boolean | — | — | No | Computed: current user has team bookmarked |
| `dashboard_button_name` | Char | — | placeholder | No | Computed: button label (placeholder in CE, overloaded in EE) |

**Inverse chain for `member_ids`:**

```
crm.team.member_ids (write)
  → _inverse_member_ids()
    → creates new crm.team.member records for newly added users
    → toggles active=True/False on existing membership records
```

**Key computed triggers (`@api.depends`):**

| Field | Depends on | Notes |
|-------|-----------|-------|
| `is_membership_multi` | `crm_team_id` (via `_compute_is_membership_multi`) | Reads `ir.config_parameter` at compute time |
| `member_ids` | `crm_team_member_ids.active`, `crm_team_member_ids.user_id` | Only counts active memberships |
| `member_company_ids` | `company_id`, `name` | `name` is a "fake trigger" to force recompute |
| `member_warning` | `is_membership_multi`, `member_ids` | Only meaningful in mono-membership mode |
| `is_favorite` | `favorite_user_ids` | Depends on `self.env.user` (dynamic per user) |

**Domain on `user_id`:**
```python
domain=[('share', '!=', True)]
# Excludes portal/shares users; only internal employees
```

**Domain on `member_ids`:**
```python
domain="['&', ('share', '=', False), ('company_ids', 'in', member_company_ids)]"
# Restricts to internal users belonging to team's company (or any company if no company set)
```

---

### `crm.team.member` — Field Inventory

**File:** `models/crm_team_member.py`  
**Inherits:** `mail.thread`  
**Rec Name:** `user_id`  
**Order:** `create_date ASC, id ASC`  
**Check Company:** `True`

| Field | Type | Required | Default | Stored | Description |
|-------|------|----------|---------|--------|-------------|
| `crm_team_id` | Many2one `crm.team` | Yes | `False` | Yes | Team; `ondelete=cascade`; `check_company=False`; `index=True` |
| `user_id` | Many2one `res.users` | Yes | — | Yes | Salesperson; `ondelete=cascade`; `index=True`; `check_company=True` |
| `user_in_teams_ids` | Many2many `res.users` | — | — | No | Computed: users already in team (to avoid duplicates in UI) |
| `user_company_ids` | Many2many `res.company` | — | — | No | Computed: team company or all companies |
| `active` | Boolean | No | `True` | Yes | Soft-archive the membership |
| `is_membership_multi` | Boolean | — | `False` | Yes (computed) | Reads `sales_team.membership_multi` param |
| `member_warning` | Text | — | `False` | No | Computed: warns if user already in other teams (mono-mode) |
| `image_1920` | Image | — | related | No | Related from `user_id.image_1920`; max 1920x1920 |
| `image_128` | Image | — | related | No | Related from `user_id.image_128`; max 128x128 |
| `name` | Char | — | related | No | Related `user_id.display_name`; `readonly=False` (can override) |
| `email` | Char | — | related | No | Related `user_id.email`; readonly |
| `phone` | Char | — | related | No | Related `user_id.phone`; readonly |
| `company_id` | Many2one `res.company` | — | related | No | Related `user_id.company_id`; readonly |

**Domain on `user_id`:**
```python
domain="[('share', '=', False),
         ('id', 'not in', user_in_teams_ids),
         ('company_ids', 'in', user_company_ids)]"
# Excludes: portal users, users already in the team, users not in team company
```

**`_rec_name = 'user_id'` effect:** In many2one dropdowns and chatter, this membership record displays the user name instead of an id.

---

### `crm.tag` — Field Inventory

**File:** `models/crm_tag.py`  
**No inheritance** (pure standalone model)

| Field | Type | Required | Default | Stored | Description |
|-------|------|----------|---------|--------|-------------|
| `name` | Char | Yes | — | Yes | Tag name; `translate=True` (supports i18n) |
| `color` | Integer | No | random 1–11 | Yes | Kanban color index |

**SQL Constraint (class-level, Odoo 16+ syntax):**
```python
_name_uniq = models.Constraint(
    'unique (name)',
    'Tag name already exists!',
)
```
This is a **database-level** `UNIQUE` constraint applied at commit time. The `translate=True` on `name` means uniqueness is enforced per language context in multilingual databases.

---

### `res.users` — Extended Fields

**File:** `models/res_users.py`  
**Inherits:** `res.users`

| Field | Type | Required | Default | Stored | Description |
|-------|------|----------|---------|--------|-------------|
| `crm_team_ids` | Many2many `crm.team` | No | — | No | All teams user is a member of; computed via `crm_team_member_ids` |
| `crm_team_member_ids` | One2many `crm.team.member` | No | — | Yes | Direct membership records (reverse of `crm.team.member.user_id`) |
| `sale_team_id` | Many2one `crm.team` | No | — | Yes | Primary sales team; computed from oldest active membership; `store=True` |

**Computed triggers:**

| Field | Depends on | Notes |
|-------|-----------|-------|
| `crm_team_ids` | `crm_team_member_ids.active` | Aggregates `crm_team_id` from active memberships |
| `sale_team_id` | `crm_team_member_ids.crm_team_id`, `crm_team_member_ids.create_date`, `crm_team_member_ids.active` | Returns `crm_team_id` of the **oldest** active membership |

**`_search_crm_team_ids` optimization:**  
This method implements a **custom search operator** for the `crm_team_ids` field. It inlines IDs to avoid performance regression in `ir.rules`:

```python
def _search_crm_team_ids(self, operator, value):
    domain = [('crm_team_member_ids.crm_team_id', operator, value)]
    # If fewer than 10,000 user IDs result, use IN clause for speed
    user_ids = self.env['res.users'].with_context(active_test=False)._search(domain, limit=10_000).get_result_ids()
    if len(user_ids) < 10_000:
        return [('id', 'in', user_ids)]
    return domain  # Fall back to original domain for large datasets
```

**`action_archive` override:**
```python
def action_archive(self):
    # When a user is archived, archive all their team memberships
    self.env['crm.team.member'].search([('user_id', 'in', self.ids)]).action_archive()
    return super().action_archive()
```
This ensures archived users are automatically removed from all sales teams.

---

## L3: Cross-Module, Override Patterns, and Workflow Triggers

### Cross-Model Relationships

```
crm.team
  ├── member_ids ────────────────► res.users  (computed/inverse to crm_team_member_ids)
  ├── crm_team_member_ids ────────► crm.team.member  (one2many)
  └── user_id ───────────────────► res.users  (team leader)

crm.team.member
  ├── crm_team_id ────────────────► crm.team  (many2one)
  └── user_id ────────────────────► res.users  (many2one)

crm.tag
  └── (used by crm.lead via crm module)

res.users
  ├── crm_team_ids ────────────────► crm.team  (many2many via crm_team_member)
  ├── crm_team_member_ids ──────────► crm.team.member  (one2many)
  └── sale_team_id ────────────────► crm.team  (primary team)
```

### Override Patterns

#### Pattern 1: Many2many via One2many Inverse (`crm.team.member_ids`)

`sales_team` uses the **canonical Odoo pattern** for editable many2many backed by an explicit one2many join table:

```python
# crm_team.py — computed + inverse
member_ids = fields.Many2many(
    'res.users',  # Target
    compute='_compute_member_ids',   # Aggregated from crm_team_member_ids
    inverse='_inverse_member_ids',   # Creates/updates crm.team.member records
    search='_search_member_ids',     # Search by crm_team_member_ids.user_id
)

# Inverse: translates many2many write → one2many operations
def _inverse_member_ids(self):
    for team in self:
        memberships = team.crm_team_member_ids  # existing
        users_current = team.member_ids          # newly written value
        users_new = users_current - memberships.user_id  # to add

        # Create new memberships
        self.env['crm.team.member'].create([
            {'crm_team_id': team.id, 'user_id': user.id}
            for user in users_new
        ])

        # Toggle active on existing memberships
        for membership in memberships:
            membership.active = membership.user_id in users_current
```

This pattern allows users to manage team membership both through the `crm.team` form (adding/removing members) and through the `crm.team.member` form directly.

#### Pattern 2: Config Parameter — Runtime Behavior Switch

`is_membership_multi` is a **runtime flag** read from `ir.config_parameter`:

```python
# Read from system parameter (stored in ir_config table)
multi_enabled = self.env['ir.config_parameter'].sudo().get_param(
    'sales_team.membership_multi',  # key
    False                            # default
)
self.is_membership_multi = multi_enabled
```

When `sales_team.membership_multi` is `True` (set via System Parameters), users can belong to multiple active sales teams simultaneously. When `False` (default), creating an active membership **automatically archives** any existing active membership for that user (see `_synchronize_memberships`).

#### Pattern 3: Mail Thread on Membership

`crm.team.member` inherits `mail.thread` despite using `mail_create_nosubscribe` in `create()`:

```python
# crm_team_member.py
class CrmTeamMember(models.Model):
    _inherit = ['mail.thread']  # Enables chatter on membership records

    def create(self, vals_list):
        return super().with_context(mail_create_nosubscribe=True).create(vals_list)
        # mail_create_nosubscribe: don't auto-follow team when member is created
        # Chatter is used for tracked fields and notes, not for following
```

#### Pattern 4: Favorite Teams via Many2many on User

```python
# crm_team.py
favorite_user_ids = fields.Many2many(
    'res.users', 'team_favorite_user_rel', 'team_id', 'user_id',
    default=_get_default_favorite_user_ids  # defaults to [self.env.uid]
)

def _inverse_is_favorite(self):
    sudoed_self = self.sudo()
    to_fav = sudoed_self.filtered(lambda t: self.env.user not in t.favorite_user_ids)
    to_fav.write({'favorite_user_ids': [(4, self.env.uid)]})  # add
    (sudoed_self - to_fav).write({'favorite_user_ids': [(3, self.env.uid)]})  # remove
```

Also: when members are added to a team, the team is automatically added to their favorites:
```python
def _add_members_to_favorites(self):
    for team in self:
        team.favorite_user_ids = [(4, member.id) for member in team.member_ids]
```

### Workflow Triggers

`sales_team` does not implement explicit state machine transitions. Instead, the "workflow" is implicit through **membership lifecycle**:

| Event | Trigger | Action |
|-------|---------|--------|
| User added to team | `_inverse_member_ids()` called | Creates `crm.team.member` with `active=True` |
| User removed from team | `_inverse_member_ids()` called | Sets `active=False` on membership |
| User archived | `res.users.action_archive()` overridden | Archives all their memberships |
| Team deleted | `write()` / unlink | `_unlink_except_default()` prevents deletion of Website Sales / POS default teams |
| New membership created (mono-mode) | `create()` on `crm.team.member` | `_synchronize_memberships()` archives other memberships |
| Team's `company_id` changed | `write()` on `crm.team` | `_constrains_company_members()` re-validates all memberships |

### Modules That Extend `crm.team`

| Extending Module | Fields Added | Purpose |
|-----------------|-------------|---------|
| `crm` | `use_lead`, `use_opportunities`, pipeline views | CRM pipeline management |
| `sale` | `team_id` on `sale.order`, assignment rules | Sales order team assignment |
| `sale_quotation` | Same as `sale` | Quotation workflow |
| `sale_management` | `team_id` on `sale.order` | Sales management |
| `helpdesk` | `team_id` on `helpdesk.ticket` | Helpdesk team routing |
| `crm_helpdesk` | `team_id` on `helpdesk.ticket` | CRM-linked helpdesk |
| `appointment` | `team_id` on appointment types | Appointment sales team |

### Modules That Extend `crm.team.member`

No other module in the Odoo CE codebase directly extends `crm.team.member`. It is used as-is by CRM, sale, and helpdesk modules to resolve team membership for document assignment.

---

## L4: Version Change Odoo 18 to 19

### Changes in `sales_team` (Odoo 18 → 19)

**`crm_tag.py` — SQL Constraint Syntax (Odoo 16+ class-level):**

The file uses the modern class-level constraint syntax introduced in Odoo 16:

```python
# Odoo 16+ syntax (used in Odoo 19)
class CrmTag(models.Model):
    _name = 'crm.tag'
    _name_uniq = models.Constraint(
        'unique (name)',
        'Tag name already exists!',
    )
```

This is functionally equivalent to the older `_sql_constraints` tuple list, just written as a class attribute. Both compile to the same `ALTER TABLE ADD CONSTRAINT` SQL.

**`res_users.py` — `_search_crm_team_ids` inline IDs optimization:**

The `_search_crm_team_ids` method has a hardcoded limit of `10_000`:

```python
IN_MAX = 10_000  # inlined literal (Odoo 19)
# Previously may have used a config-dependent value
```

This limit determines when the search falls back from an `IN (id1, id2, ...)` clause to a subquery. With more than 10,000 matching users, the method uses a standard domain to avoid constructing an excessively large SQL `IN` clause.

**`crm_team.py` — `_get_default_favorite_user_ids` uses `self.env.uid`:**

```python
def _get_default_favorite_user_ids(self):
    return [(6, 0, [self.env.uid])]
```

When a new team is created, the creating user automatically has it added to their favorites. This behavior is unchanged from Odoo 18 — the method has been stable.

**`crm_team_member.py` — `default=False` on `crm_team_id` field:**

```python
crm_team_id = fields.Many2one(
    'crm.team',
    default=False,  # Explicit default=False (clarifies intent)
    ...
)
```

This is a **clarification** (not a behavior change): explicitly setting `default=False` communicates that no team is pre-selected when creating a new membership record, which is important for the `group_expand` on the field to work correctly in tree views.

**Removal of `@api.multi` decorators:**

Odoo 19 removes the `@api.multi` decorator as it is now the **default** for all recordset methods. Any method signature `def method(self, ...)` is implicitly multi-record. No `@api.multi` decorators appear in this module's Odoo 19 codebase.

**`mail.thread` mixin stable:**  
The `_inherit = ['mail.thread']` list syntax (prototype inheritance) is stable in Odoo 19 and used consistently throughout.

### No Breaking Changes

`sales_team` had **no breaking changes** between Odoo 18 and 19. The module is highly stable as it represents core sales infrastructure.

### Migration Checklist

- [ ] Verify `sales_team.membership_multi` config parameter is set if multi-team mode is desired
- [ ] Default teams (`sales_team.salesteam_website_sales`, `sales_team.pos_sales_team`) must not be deleted — protected by `_unlink_except_default`
- [ ] If custom code creates `crm.team.member` records, ensure it handles mono-vs-multi membership mode via `_synchronize_memberships`
- [ ] Ensure all users in team have `company_ids` that include the team's `company_id` (enforced by `_constrains_company_members`)

### Related Documentation

- [Modules/CRM](odoo-18/Modules/CRM.md) — `crm` module uses `crm.team` as pipeline container
- [Modules/Sale](odoo-18/Modules/sale.md) — `sale.order` uses `team_id` for assignment
- [Core/Fields](odoo-18/Core/Fields.md) — Many2many with compute/inverse pattern
- [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) — Classic vs. prototype inheritance
