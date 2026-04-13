---
tags:
  - odoo
  - odoo19
  - modules
  - mass_mailing
  - website_slides
  - marketing
  - email-marketing
description: Bridge module linking mass mailing campaigns to e-learning course members (website_slides attendees), enabling direct email contact with enrolled partners via a pre-populated mailing domain.
---

# Mass Mailing Slides (`mass_mailing_slides`)

## Module Overview

**Category:** Marketing/Email Marketing
**Version:** 1.0
**Depends:** `website_slides`, `mass_mailing`
**Auto-install:** `True`
**License:** LGPL-3
**Author:** Odoo S.A.

`mass_mailing_slides` is a **thin bridge module** (~190 lines of Python + XML) that adds a "Contact Attendees" action button to the `slide.channel` (Course) model, allowing marketers to launch a `mailing.mailing` form pre-populated with all enrolled partners of a course as recipients. It provides zero new models — its entire purpose is UX wiring between the e-learning enrollment system and the mass mailing engine.

## Architecture

```
slide.channel (website_slides)
    │
    └── inherits: slide.channel
            │
            └── action_mass_mailing_attendees()
                    │
                    ├── context: default_mailing_model_id = res.partner
                    └── context: default_mailing_domain = [('slide_channel_ids', 'in', <channel_ids>)]
                            │
                            └── mailing.mailing form opens with all enrolled partners pre-filtered
                                    │
                                    └── mailing.trace records track sent/opened/clicked/bounced per res.partner res_id
                                            │
                                            └── link_tracker tracks URL clicks with mailing_trace_id linkage
```

## Manifest (`__manifest__.py`)

```python
{
    'name': 'Mass mailing on course members',
    'category': 'Marketing/Email Marketing',
    'version': '1.0',
    'depends': ['website_slides', 'mass_mailing'],
    'data': ['views/slide_channel_views.xml'],
    'auto_install': True,   # installed automatically when both dependencies are present
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

**Key design decisions:**
- `auto_install: True` — the module is automatically installed when both `website_slides` and `mass_mailing` are in the modules path. No manual activation needed.
- `data` only loads the XML view extension; no security CSV files are needed because it reuses existing group-based ACLs from `mass_mailing` and `website_slides`.
- The `description` field in the manifest doubles as the app listing description in the Odoo Apps screen.

## Models

This module declares **no new models**. All behavior is added through inheritance of `slide.channel`.

### `SlideChannel` — Inherited Model

**File:** `models/slide_channel.py`

Inherits from `website_slides.slide.channel`. Adds one action method:

---

#### `action_mass_mailing_attendees()`

Opens the `mailing.mailing` form in create mode, pre-populating the recipients model and domain.

```python
def action_mass_mailing_attendees(self) -> dict
```

**Returns:**
```python
{
    'name': 'Mass Mail Course Members',
    'type': 'ir.actions.act_window',
    'res_model': 'mailing.mailing',
    'view_mode': 'form',
    'target': 'current',
    'context': {
        'default_mailing_model_id': <ir.model id for res.partner>,
        'default_mailing_domain': "[('slide_channel_ids', 'in', <channel_ids>)]",
    },
}
```

**Behavior breakdown:**

| Context Key | Value | Purpose |
|---|---|---|
| `default_mailing_model_id` | `ir.model` ID for `res.partner` | Sets the mailing's **Recipients Model** to Partner. Without it, the mailing defaults to `mailing.list` and the domain would be silently ignored. |
| `default_mailing_domain` | `repr([('slide_channel_ids', 'in', self.ids)])` | Pre-fills the mailing's **Domain** field to return only partners enrolled in the selected channels. Serialized via `repr()` because context values are strings when passed through the action window mechanism. |

**Domain resolution chain:**

1. `self.ids` — the IDs of the currently selected `slide.channel` records (supports multi-select from kanban/list views).
2. The domain `[('slide_channel_ids', 'in', self.ids)]` is applied on `res.partner`.
3. `res.partner.slide_channel_ids` is a **computed/searchable `Many2many`** field defined in `website_slides/models/res_partner.py`:
   ```python
   slide_channel_ids = fields.Many2many(
       'slide.channel', string='eLearning Courses',
       compute='_compute_slide_channel_values',
       search='_search_slide_channel_ids',
       groups="website_slides.group_website_slides_officer")
   ```
4. `_search_slide_channel_ids` translates the Many2many search into a subquery against `slide.channel.partner`:
   ```python
   def _search_slide_channel_ids(self, operator, value):
       cp_enrolled = self.env['slide.channel.partner'].search([
           ('channel_id', operator, value),
           ('member_status', '!=', 'invited')   # <-- excludes invited-only members
       ])
       return [('id', 'in', cp_enrolled.partner_id.ids)]
   ```
5. The `'!=' 'invited'` filter is the critical distinction — **only actively enrolled partners** (status `joined`, `ongoing`, or `completed`) are included. Partners who received an invitation but have not enrolled are excluded from the mailing.

**Recipients included vs. excluded by `member_status`:**

| Member Status | Included in Mailing Domain? | Reason |
|---|---|---|
| `joined` | Yes | Actively enrolled |
| `ongoing` | Yes | Actively enrolled and in progress |
| `completed` | Yes | Finished the course |
| `invited` | **No** | Invitation sent but not yet enrolled |

---

## View Extensions (`views/slide_channel_views.xml`)

Two view inheritance records inject the action button into the Course form and kanban views.

### Form View Button

```xml
<record id="slide_channel_view_form" model="ir.ui.view">
    <field name="name">slide.channel.view.form.inherit.mass.mailing</field>
    <field name="model">slide.channel</field>
    <field name="inherit_id" ref="website_slides.view_slide_channel_form"/>
    <field name="arch" type="xml">
        <button name="action_channel_enroll" position="before">
            <field name="members_count" invisible="1"/>
            <button name="action_mass_mailing_attendees" string="Contact Attendees"
                    type="object" class="oe_highlight"
                    invisible="members_count == 0"
                    groups="mass_mailing.group_mass_mailing_user"/>
        </button>
    </field>
</record>
```

**Placement:** `before="action_channel_enroll"` — the "Contact Attendees" button appears to the left of the "Enroll Attendees" button on the course form header action area.

**Visibility conditions:**
- `invisible="members_count == 0"` — button is hidden when the course has zero enrolled members. This prevents launching a mailing that would immediately return an empty recipient list.
- `members_count` is a **stored computed integer** on `slide.channel` (defined in `website_slides`):
  ```python
  members_count = fields.Integer('# Enrolled Attendees', compute='_compute_members_counts')
  # Formula: members_engaged_count + members_completed_count
  # Excludes: invited count
  ```

**Security group:** `mass_mailing.group_mass_mailing_user` — only users with mass mailing rights can send. This defers to the existing `mass_mailing` module's ACL rather than duplicating it.

**Button style:** `class="oe_highlight"` — renders with a prominent primary-color style, consistent with other primary action buttons in Odoo.

### Kanban View Dropdown

```xml
<record id="slide_channel_view_kanban" model="ir.ui.view">
    <field name="name">slide.channel.view.kanban.inherit.mass.mailing</field>
    <field name="model">slide.channel</field>
    <field name="inherit_id" ref="website_slides.slide_channel_view_kanban"/>
    <field name="arch" type="xml">
        <xpath expr="//a[@name='action_channel_invite']" position="after">
            <a role="menuitem" name="action_mass_mailing_attendees" type="object"
               groups="mass_mailing.group_mass_mailing_user" class="dropdown-item">
                Contact Attendees
            </a>
        </xpath>
    </field>
</record>
```

**Placement:** inside the kanban card's overflow menu (`...`), inserted after `action_channel_invite`. This is a dropdown menu item, not a direct button — consistent with how other per-record actions appear in the kanban card action menu.

**Note on multi-record context:** When multiple `slide.channel` records are selected in a kanban/list view, `self.ids` will contain all selected channel IDs. The resulting mailing domain `[('slide_channel_ids', 'in', [id1, id2, ...])]` will include partners enrolled in **any** of the selected courses (set-union, not intersection).

---

## Data Model — Supporting Fields (from `website_slides`)

These fields from `website_slides` are the data backbone of the integration:

### `slide.channel` Fields

| Field | Type | Computed | Description |
|---|---|---|---|
| `partner_ids` | `Many2many(res.partner)` | Yes | All enrolled partner records across all active statuses (joined/ongoing/completed). Excludes invited. The mailing domain resolves through this field on `res.partner`. |
| `members_count` | `Integer` | Yes | Count of active enrolled members (joined + ongoing + completed). Excludes invited. Drives button visibility. |
| `channel_partner_ids` | `One2many(slide.channel.partner)` | — | Join table records with per-member enrollment metadata. Domained to `member_status != 'invited'`. |
| `members_engaged_count` | `Integer` | Yes | Count of `joined` + `ongoing` members only. |
| `members_completed_count` | `Integer` | Yes | Count of `completed` members only. |
| `members_invited_count` | `Integer` | Yes | Count of `invited` members (excluded from mailing). |

### `slide.channel.partner` (Enrollment Join Table)

| Field | Type | Description |
|---|---|---|
| `channel_id` | `Many2one(slide.channel)` | The course; indexed. On-delete cascade. |
| `partner_id` | `Many2one(res.partner)` | The enrolled member; indexed. On-delete cascade. |
| `member_status` | `Selection` | One of: `invited`, `joined`, `ongoing`, `completed`. Readonly; set on enrollment. |
| `completion` | `Integer` | Percentage 0–100 of slides completed. Subject to CHECK constraint `[0, 100]`. |
| `completed_slides_count` | `Integer` | Absolute count of completed slides. |
| `active` | `Boolean` | Soft-delete support. Archived records are excluded from the mailing domain via `active=True` filter. |
| `partner_email` | `Char` | Related `partner_id.email`; used by mailing renderer. |

**Constraints:**
```python
_channel_partner_uniq = models.Constraint(
    'unique(channel_id, partner_id)',
    'A partner membership to a channel must be unique!',
)
_check_completion = models.Constraint(
    'check(completion >= 0 and completion <= 100)',
    'The completion of a channel is a percentage and should be between 0% and 100.',
)
```

### `res.partner` Fields (from `website_slides`)

| Field | Type | Description |
|---|---|---|
| `slide_channel_ids` | `Many2many(slide.channel)` | Computed; channels the partner is actively enrolled in (joined/ongoing/completed). Excludes invited. Group-gated to `group_website_slides_officer`. |
| `slide_channel_completed_ids` | `One2many(slide.channel)` | Computed; only completed courses. |
| `slide_channel_count` | `Integer` | Total count of enrolled courses. |

The Many2many relationship uses `_search_slide_channel_ids` which runs a subquery on `slide.channel.partner`:
```python
cp_enrolled = self.env['slide.channel.partner'].search([
    ('channel_id', operator, value),
    ('member_status', '!=', 'invited')
])
return [('id', 'in', cp_enrolled.partner_id.ids)]
```

---

## Mailing Statistics Chain

Once a `mailing.mailing` is created from `action_mass_mailing_attendees`, the full mailing lifecycle is handled by the `mass_mailing` module.

### Recipient Resolution

1. `mailing.mailing.mailing_domain` is set to `[('slide_channel_ids', 'in', channel_ids)]` via the action context's `default_mailing_domain`.
2. When the user clicks **Send** (`action_send_mail`), `mailing.mailing._get_remaining_recipients()` calls `search(mailing_domain)` against `res.partner`.
3. `res.partner` records are fetched and `mailing.trace` records are created linking each partner's `id` as `res_id`.

### `mailing.trace` — Per-Recipient Statistics

```python
class MailingTrace(models.Model):
    _name = 'mailing.trace'
    _description = 'Mailing Statistics'
    _order = 'create_date DESC'

    trace_type = fields.Selection([('mail', 'Email')], default='mail')
    model = fields.Char(string='Document model', required=True)  # = 'res.partner'
    res_id = fields.Many2oneReference(string='Document ID', model_field='model')  # partner id
    mass_mailing_id = fields.Many2one('mailing.mailing')
    trace_status = fields.Selection(selection=[
        ('outgoing', 'Outgoing'),
        ('process', 'Processing'),
        ('pending', 'Sent'),
        ('sent', 'Delivered'),
        ('open', 'Opened'),
        ('reply', 'Replied'),
        ('bounce', 'Bounced'),
        ('error', 'Exception'),
        ('cancel', 'Cancelled')], default='outgoing')
    failure_type = fields.Selection([...])  # mail_bounce, mail_bl, mail_optout, mail_dup, etc.
    links_click_ids = fields.One2many('link.tracker.click', 'mailing_trace_id')
    links_click_datetime = fields.Datetime('Clicked On')
    sent_datetime = fields.Datetime('Sent On')
    open_datetime = fields.Datetime('Opened On')
    reply_datetime = fields.Datetime('Replied On')
```

**Key constraint:** `CHECK(res_id IS NOT NULL AND res_id != 0)` — every trace must be linked to a valid partner record.

### Click Tracking Path

When a recipient clicks a tracked URL in the email:
1. `link.tracker.click` record is created with `mailing_trace_id` linking back to the trace
2. `click.mailing_trace_id.set_opened()` transitions the trace to `open` status (idempotent — already-opened traces are skipped)
3. `click.mailing_trace_id.set_clicked()` updates `links_click_datetime`

### Status Transition Summary

```
outgoing → pending → sent → open → reply
                        ↘ bounce / error
                        ↘ cancel (before send, if blacklisted/opted-out/dup)
```

---

## Cross-Module Integration Map

```
mass_mailing_slides
    │
    ├── INHERITS: slide.channel (website_slides)
    │       │
    │       ├── USES: slide.channel.partner (website_slides)
    │       │       └── LINKS: res.partner via partner_id
    │       │
    │       └── USES: res.partner (base)
    │               │
    │               └── MAILING DOMAIN: slide_channel_ids in [channel_ids]
    │
    ├── OPENS: mailing.mailing (mass_mailing)
    │       │
    │       ├── RECIPIENT MODEL: res.partner
    │       ├── MAILING DOMAIN: [('slide_channel_ids', 'in', channel_ids)]
    │       │
    │       ├── CREATES: mailing.trace (mass_mailing)
    │       │       └── res_id → res.partner.id
    │       │
    │       └── TRACKS: link.tracker (mass_mailing)
    │               └── mailing_trace_id → mailing.trace.id
    │
    ├── REQUIRES GROUP: mass_mailing.group_mass_mailing_user
    │
    └── AUTO-INSTALL: triggered when website_slides AND mass_mailing are both installed
```

---

## Performance Considerations

### `members_count` Compute

`_compute_members_counts` on `slide.channel` runs a `read_group` against `slide.channel.partner` with `sudo()`:

```python
def _compute_members_counts(self):
    read_group_res = self.env['slide.channel.partner'].sudo()._read_group(
        domain=[('channel_id', 'in', self.ids)],
        groupby=['channel_id', 'member_status'],
        aggregates=['__count']
    )
    data = {(channel.id, member_status): count for channel, member_status, count in read_group_res}
    for channel in self:
        channel.members_invited_count = data.get((channel.id, 'invited'), 0)
        channel.members_engaged_count = data.get((channel.id, 'joined'), 0) + data.get((channel.id, 'ongoing'), 0)
        channel.members_completed_count = data.get((channel.id, 'completed'), 0)
        channel.members_count = channel.members_engaged_count + channel.members_completed_count
```

- **O(n)** where n = number of `slide.channel.partner` records for the channel batch — not a concern for typical course sizes.
- Uses `sudo()` because officers need to see enrollment counts without explicit read access on the partner records themselves.
- Cached via the ORM compute cache; only recomputes on partner enrollment status changes.
- `members_count == 0` is evaluated client-side in the form view's `invisible` attribute — no extra RPC needed.

### Mailing Domain Query

When the mailing form loads, `mailing.mailing._compute_mailing_domain()` resolves `default_mailing_domain` from the action context. The domain `[('slide_channel_ids', 'in', channel_ids)]` translates to a subquery:

```sql
SELECT id FROM res_partner
WHERE id IN (
    SELECT partner_id FROM slide_channel_partner
    WHERE channel_id IN (<channel_ids>)
      AND member_status != 'invited'
      AND active = true
)
```

- Simple indexed subquery (`index=True` on `channel_id`, `partner_id`, and `active` in `slide_channel_partner`).
- For courses with thousands of members, the partner search respects ORM record rules and can be slow if the user lacks `mass_mailing.group_mass_mailing_user` but has restricted `res.partner` access.

### Large Recipient Sets

`mailing.mailing._action_send_mail()` batches sends via `mail.mail` records and the mailing trace. For courses with 10,000+ members, the sending process is handled asynchronously by the `mail` module's mail queue. The `mass_mailing` module's `ab_testing_enabled` flag can be used to test on a subset before full send.

---

## Security Considerations

### Group-Based Access Control

| Group | Access |
|---|---|
| `mass_mailing.group_mass_mailing_user` | Can see and click "Contact Attendees" button; can send mailings |
| `website_slides.group_website_slides_officer` | Can view `partner_ids`, `members_count`, `channel_partner_ids` on `slide.channel` |

**Key insight:** The `mass_mailing.group_mass_mailing_user` check gates the button, but `members_count` itself is **not** gated by this group. Any user who can view the course form will see the count of enrolled members, even if they cannot click the mailing button.

### Partner Data Exposure

When the mailing form opens, `default_mailing_domain` is passed as a stringified Python repr in the action context. This domain is visible in:
1. The browser's URL (GET parameter for the action window)
2. The mailing form's Domain field (editable by the user before send)

A user with mailing rights who modifies the domain to remove the channel filter could inadvertently include all partners in the system. The `mass_mailing` module's `mailing_filter_id` (favorite filter) feature can lock down domain options in a deployed system.

### Record Rules

No record rules are introduced by this module. The standard `ir.rule` for `slide.channel` and `slide.channel.partner` (if any) apply. Users can only mail attendees of channels they have read access to.

### Opt-Out Compliance

The `mass_mailing` module respects `mail.blacklist` and per-model opt-out lists via `_mailing_get_opt_out_list()`. For `res.partner`, the standard email blacklist is applied automatically. Partners who have unsubscribed globally will be excluded from the mailing even if they appear in the channel enrollment, with trace status set to `cancel` and failure_type `mail_bl`.

---

## Edge Cases

### Empty Course

When `members_count == 0`, the button is hidden via `invisible="members_count == 0"`. However, the action method `action_mass_mailing_attendees()` does **not** guard against this — if the invisible domain is bypassed via a custom view or direct action call, the method opens a mailing form with an empty recipient domain, resulting in zero recipients and an error on send.

### Archived Partner Records

`slide.channel.partner.active = False` records (de-activated enrollments) are excluded from the domain via `_search_slide_channel_ids` using `active=True` filtering in the subquery. Archived partners will not receive mass mailing emails.

### Multi-Record Action (Batch Mailing)

When called from a list view with multiple `slide.channel` records selected, the domain becomes:
```python
[('slide_channel_ids', 'in', [id1, id2, id3])]
```
This creates a **union** of all enrolled partners across all selected courses. If the same partner is enrolled in multiple selected courses, they appear once in the recipient list (deduplication happens at `res.partner` level). However, the `mailing.trace` records for a re-send of the same mailing will only reach partners not already traced for that mailing.

### Duplicate Send Protection

`mailing.mailing._get_remaining_recipients()` excludes already-mailed `res_id` values for the same `mass_mailing_id` by checking `mailing.trace`:
```python
already_mailed = self.env['mailing.trace'].search_read(
    [('mass_mailing_id', '=', self.id), ('res_id', 'in', res_ids)],
    ['res_id']
)
done_res_ids = {record['res_id'] for record in already_mailed}
```
Re-sending the same mailing to the same channel only reaches partners not already traced.

### Channel Visibility: Members-Only Courses

For `slide.channel` records where `visibility = 'members'`, the channel is only visible on the website to enrolled partners. However, the "Contact Attendees" button is available to any user with `mass_mailing.group_mass_mailing_user` who has access to the channel form backend view. There is no additional visibility check — if a user can see the form, they can initiate a mailing. This is consistent with the Odoo principle that backend access and website visibility are separate concerns.

### mailing_filter_id Override

`mailing.mailing` has a `mailing_filter_id` field (favorite filter) that can pre-populate the domain from a saved filter. If a user has a default filter configured, it is applied in `_compute_mailing_domain` before the context `default_mailing_domain` value is processed. The context value set by `mass_mailing_slides` may be partially overridden in this scenario — the user should verify the recipient count in the mailing form before sending.

---

## Odoo 18 → Odoo 19 Changes

The `mass_mailing_slides` module had no significant functional changes between Odoo 18 and Odoo 19. Both versions share the identical:

- `action_mass_mailing_attendees` implementation (same method body, same context keys)
- View XML placement: `before="action_channel_enroll"` on form; after `action_channel_invite` on kanban
- `members_count == 0` visibility guard on the form button

**Relevant upstream changes in `website_slides` (Odoo 19):**
- `members_count` remains `members_engaged_count + members_completed_count` — unchanged
- `_search_slide_channel_ids` on `res.partner` continues to exclude `member_status = 'invited'` records
- No changes to `slide.channel.partner` structure

**Relevant upstream changes in `mass_mailing` (Odoo 19):**
- `mailing.mailing` now has a `mailing_filter_id` field (favorite filter) that may override the pre-populated domain set by `mass_mailing_slides` if a user has a default filter configured.
- `mailing_trace_ids` on `mailing.mailing` uses a more efficient aggregate query in `_compute_kpi_sms` / `_compute_kpi_mail` to avoid N+1 lookups on large campaigns.

---

## Related Documentation

- [Modules/website_slides](Modules/website_slides.md) — Course model, enrollment lifecycle, `slide.channel.partner`
- [Modules/mass_mailing](Modules/mass_mailing.md) — `mailing.mailing`, `mailing.trace`, `link.tracker`
- [Modules/res.partner](Modules/res.partner.md) — Partner model (recipient model for mailings)
- [Core/Fields](Core/Fields.md) — Many2many, One2many, computed/searchable field patterns
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine patterns (member status lifecycle: invited → joined → ongoing → completed)
