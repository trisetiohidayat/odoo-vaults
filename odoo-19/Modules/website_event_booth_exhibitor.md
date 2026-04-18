---
uuid: 2b3c4d5e-6f7a-8b9c-0d1e-f2a3b4c5d6e7
title: "Booths/Exhibitors Bridge"
status: published
category: Marketing/Events
tags:
  - odoo
  - odoo19
  - website
  - event
  - booth
  - exhibitor
  - sponsor
created: 2024-01-15
modified: 2024-11-20
---

# Booths/Exhibitors Bridge

## Overview

**Module:** `website_event_booth_exhibitor`
**Category:** Marketing/Events
**Version:** 1.1
**Depends:** `website_event_exhibitor`, `website_event_booth`
**Summary:** Automatically creates a sponsor record when a booth is booked on the website
**Auto-install:** `True`
**License:** LGPL-3
**Author:** Odoo S.A.

`website_event_booth_exhibitor` bridges [Modules/website_event_booth](Modules/website_event_booth.md) (booth registration) and [Modules/website_event_exhibitor](Modules/website_event_exhibitor.md) (exhibitor/sponsor management). When a visitor books a booth on the website and the booth category is configured to create a sponsor, the module automatically generates an `event.sponsor` record and links it to the booth. This enables exhibitors to manage their event presence through the sponsor portal without requiring manual intervention by event staff.

## Architecture

### Dependency Chain

```
website_event_booth_exhibitor
    ├── website_event_booth         (booth registration on website)
    │       └── event.booth model
    │       └── event.booth.category model
    └── website_event_exhibitor     (exhibitor pages, sponsor portal)
            └── event.sponsor model
            └── event.sponsor.type model
```

### Component Map

```
event.booth.category
    ├── use_sponsor (Boolean)
    ├── sponsor_type_id (Many2one)
    └── exhibitor_type (Selection)
            [triggers sponsor creation on booth confirm]

event.booth
    ├── sponsor_id (Many2one)
    ├── sponsor_name, sponsor_email, sponsor_phone (related)
    ├── sponsor_subtitle, sponsor_website_description (related)
    ├── sponsor_image_512 (related)
    └── _action_post_confirm() [OVERRIDE]

WebsiteEventBoothController
    ├── _prepare_booth_registration_values() [EXTEND]
    ├── _prepare_booth_registration_partner_values() [EXTEND]
    └── _prepare_booth_registration_sponsor_values() [NEW]
```

### Key Design Decisions

- **Automatic sponsor creation:** The sponsor is created automatically when a booth is confirmed, not at booking time. This allows exhibitors to complete their booth registration and fill in sponsor details later if needed.
- **Single sponsor per booth-partner-type-event combination:** `_get_or_create_sponsor()` uses a search to avoid duplicate sponsor records. If a sponsor already exists for the same partner, sponsor type, exhibitor type, and event, it reuses the existing record rather than creating a new one.
- **Sponsor fields are read-only on the booth form:** The sponsor-related fields (`sponsor_name`, `sponsor_email`, etc.) are `related` fields pointing to the `sponsor_id` record. This means editing the sponsor details from the booth view directly modifies the linked `event.sponsor` record.
- **Category-level configuration:** The `use_sponsor` flag is on the booth category, not individual booths. This means all booths in a category share the same sponsor-creation behavior, reducing configuration overhead for event organizers.

## Extended Models

### `event.booth.category` — Sponsor Creation Toggle

**File:** `models/event_booth_category.py`

```python
class EventBoothCategory(models.Model):
    _inherit = 'event.booth.category'

    use_sponsor = fields.Boolean(
        string='Create Sponsor',
        help="If set, when booking a booth a sponsor will be created for the user"
    )
    sponsor_type_id = fields.Many2one(
        'event.sponsor.type',
        string='Sponsor Level',
    )
    exhibitor_type = fields.Selection(
        '_get_exhibitor_type',
        string='Sponsor Type',
    )

    @api.onchange('use_sponsor')
    def _onchange_use_sponsor(self):
        if self.use_sponsor:
            if not self.sponsor_type_id:
                self.sponsor_type_id = self.env['event.sponsor.type'].search(
                    [], order="sequence desc", limit=1
                ).id
            if not self.exhibitor_type:
                self.exhibitor_type = self._get_exhibitor_type()[0][0]
```

| Field | Type | Description |
|---|---|---|
| `use_sponsor` | Boolean | When `True`, confirming a booth in this category automatically creates a sponsor record |
| `sponsor_type_id` | Many2one `event.sponsor.type` | The sponsor tier/level assigned to the auto-created sponsor (e.g., Gold, Silver, Bronze) |
| `exhibitor_type` | Selection | The exhibitor category (`sponsor`, `exhibitor`, `online`) copied from `event.sponsor.exhibitor_type` |

#### `_onchange_use_sponsor()`

When an event organizer checks the "Create Sponsor" checkbox:
- If no sponsor level is set, it automatically selects the highest-tier sponsor type (sorted by `sequence` descending).
- If no exhibitor type is set, it defaults to the first option in the selection list.

This auto-fill behavior reduces configuration steps for event managers.

---

### `event.booth` — Sponsor Linkage

**File:** `models/event_booth.py`

```python
class EventBooth(models.Model):
    _inherit = 'event.booth'

    use_sponsor = fields.Boolean(related='booth_category_id.use_sponsor')
    sponsor_type_id = fields.Many2one(related='booth_category_id.sponsor_type_id')
    sponsor_id = fields.Many2one(
        'event.sponsor',
        string='Sponsor',
        copy=False,
    )
    sponsor_name = fields.Char(string='Sponsor Name', related='sponsor_id.name')
    sponsor_email = fields.Char(string='Sponsor Email', related='sponsor_id.email')
    sponsor_phone = fields.Char(string='Sponsor Phone', related='sponsor_id.phone')
    sponsor_subtitle = fields.Char(string='Sponsor Slogan', related='sponsor_id.subtitle')
    sponsor_website_description = fields.Html(
        string='Sponsor Description',
        related='sponsor_id.website_description',
    )
    sponsor_image_512 = fields.Image(
        string='Sponsor Logo',
        related='sponsor_id.image_512',
    )
```

| Field | Type | Source | Description |
|---|---|---|---|
| `sponsor_id` | Many2one `event.sponsor` | Direct | The linked sponsor record, created automatically on confirmation |
| `sponsor_name` | Char | `sponsor_id.name` | Exhibitor company/person name |
| `sponsor_email` | Char | `sponsor_id.email` | Contact email |
| `sponsor_phone` | Char | `sponsor_id.phone` | Contact phone |
| `sponsor_subtitle` | Char | `sponsor_id.subtitle` | Tagline or slogan |
| `sponsor_website_description` | Html | `sponsor_id.website_description` | Rich-text company description shown on event page |
| `sponsor_image_512` | Binary | `sponsor_id.image_512` | Logo image (512px max) |

All fields except `sponsor_id` are read-only `related` fields. Editing them in the booth form view directly modifies the underlying `event.sponsor` record.

#### `action_view_sponsor()`

```python
def action_view_sponsor(self):
    action = self.env['ir.actions.act_window']._for_xml_id(
        'website_event_exhibitor.event_sponsor_action'
    )
    action['views'] = [(False, 'form')]
    action['res_id'] = self.sponsor_id.id
    return action
```

Opens the sponsor form view in read/write mode from the booth form. This allows event staff to edit sponsor details without navigating to the Exhibitors menu.

#### `_get_or_create_sponsor(vals)`

```python
def _get_or_create_sponsor(self, vals):
    self.ensure_one()
    sponsor_id = self.env['event.sponsor'].sudo().search([
        ('partner_id', '=', self.partner_id.id),
        ('sponsor_type_id', '=', self.sponsor_type_id.id),
        ('exhibitor_type', '=', self.booth_category_id.exhibitor_type),
        ('event_id', '=', self.event_id.id),
    ], limit=1)
    if not sponsor_id:
        values = {
            'event_id': self.event_id.id,
            'sponsor_type_id': self.sponsor_type_id.id,
            'exhibitor_type': self.booth_category_id.exhibitor_type,
            'partner_id': self.partner_id.id,
            **{key.partition('sponsor_')[2]: value
               for key, value in vals.items()
               if key.startswith('sponsor_')},
        }
        if not values.get('name'):
            values['name'] = self.partner_id.name
        sponsor_id = self.env['event.sponsor'].sudo().create(values)
    return sponsor_id.id
```

| Parameter | Type | Description |
|---|---|---|
| `vals` | dict | Sponsor field values from the registration form (e.g., `sponsor_name`, `sponsor_email`, etc.) |

**Uniqueness constraint:** The search uses four fields: `partner_id`, `sponsor_type_id`, `exhibitor_type`, and `event_id`. This means a partner can have at most one sponsor record per event per sponsor type, which aligns with real-world scenarios where a company typically has one booth per event.

**Sponsor field mapping:** The dict comprehension `{key.partition('sponsor_')[2]: value for key, value in vals.items() if key.startswith('sponsor_')}` strips the `sponsor_` prefix from incoming values and maps them to the corresponding `event.sponsor` fields. For example, `sponsor_name` maps to `name`, `sponsor_email` maps to `email`, etc.

**Fallback for name:** If no `sponsor_name` was provided in `vals`, the booth's `partner_id.name` is used as the sponsor's display name.

#### `_action_post_confirm(write_vals)`

```python
def _action_post_confirm(self, write_vals):
    for booth in self:
        if booth.use_sponsor and booth.partner_id:
            booth.sponsor_id = booth._get_or_create_sponsor(write_vals)
    super(EventBooth, self)._action_post_confirm(write_vals)
```

This is the trigger point. After the parent `_action_post_confirm()` completes (which handles the base booth confirmation logic), this override checks whether the booth's category has `use_sponsor=True` and whether the booth has an assigned partner. If both conditions are true, it calls `_get_or_create_sponsor()` and writes the result to `sponsor_id`.

The `write_vals` parameter contains any sponsor-related fields submitted during registration (name, email, phone, etc.) that should be applied to the created sponsor record.

## Extended Controllers

### `WebsiteEventBoothController` — Sponsor Fields in Registration

**File:** `controllers/event_booth.py`
**Inherits:** `website_event.controllers.main.WebsiteEventController`

The controller extends three methods to inject sponsor-related data into the booth registration flow.

#### `_prepare_booth_registration_values(event, kwargs)`

```python
def _prepare_booth_registration_values(self, event, kwargs):
    booth_values = super( ... )._prepare_booth_registration_values(event, kwargs)
    if not booth_values.get('contact_email'):
        booth_values['contact_email'] = kwargs.get('sponsor_email')
    if not booth_values.get('contact_name'):
        booth_values['contact_name'] = kwargs.get('sponsor_name')
    if not booth_values.get('contact_phone'):
        booth_values['contact_phone'] = kwargs.get('sponsor_phone')

    booth_values.update(
        **self._prepare_booth_registration_sponsor_values(event, booth_values, kwargs)
    )
    return booth_values
```

| Condition | Action |
|---|---|
| `contact_email` not set | Fall back to `sponsor_email` from request |
| `contact_name` not set | Fall back to `sponsor_name` from request |
| `contact_phone` not set | Fall back to `sponsor_phone` from request |

This method ensures that if a booth registration form includes sponsor fields but leaves contact fields empty, the sponsor values are used as a fallback. This prevents empty contact details in the booth record.

#### `_prepare_booth_registration_partner_values(event, kwargs)`

```python
def _prepare_booth_registration_partner_values(self, event, kwargs):
    if not kwargs.get('contact_email') and kwargs.get('sponsor_email'):
        kwargs['contact_email'] = kwargs['sponsor_email']
    if not kwargs.get('contact_name') and kwargs.get('sponsor_name'):
        kwargs['contact_name'] = kwargs['sponsor_name']
    if not kwargs.get('contact_phone') and kwargs.get('sponsor_phone'):
        kwargs['contact_phone'] = kwargs['sponsor_phone']
    return super( ... )._prepare_booth_registration_partner_values(event, kwargs)
```

Same fallback logic applied at the partner-values preparation stage, before the partner record is looked up or created. This ensures the partner record has complete contact information.

#### `_prepare_booth_registration_sponsor_values(event, booth_values, kwargs)`

```python
def _prepare_booth_registration_sponsor_values(self, event, booth_values, kwargs):
    sponsor_values = {
        'sponsor_name': kwargs.get('sponsor_name') or booth_values.get('contact_name'),
        'sponsor_email': kwargs.get('sponsor_email') or booth_values.get('contact_email'),
        'sponsor_phone': kwargs.get('sponsor_phone') or booth_values.get('contact_phone'),
        'sponsor_subtitle': kwargs.get('sponsor_slogan'),
        'sponsor_website_description': plaintext2html(
            kwargs.get('sponsor_description')
        ) if kwargs.get('sponsor_description') else '',
        'sponsor_image_512': base64.b64encode(
            kwargs['sponsor_image'].read()
        ) if kwargs.get('sponsor_image') else False,
    }
    return sponsor_values
```

Builds the complete sponsor values dictionary from HTTP request parameters. Key transformations:

| Source Field | Target Field | Transformation |
|---|---|---|
| `sponsor_name` / `contact_name` | `sponsor_name` | Preferred; falls back to contact name |
| `sponsor_email` / `contact_email` | `sponsor_email` | Preferred; falls back to contact email |
| `sponsor_phone` / `contact_phone` | `sponsor_phone` | Preferred; falls back to contact phone |
| `sponsor_slogan` | `sponsor_subtitle` | Direct map (note: renamed field) |
| `sponsor_description` | `sponsor_website_description` | `plaintext2html()` — converts plain text to basic HTML |
| `sponsor_image` | `sponsor_image_512` | `base64.b64encode()` — converts uploaded file to base64 |

## Data Flow

```
[Visitor fills booth registration form on website]
    Fields: contact_name, contact_email, contact_phone,
            sponsor_name, sponsor_email, sponsor_slogan,
            sponsor_description, sponsor_image
             |
             v
[WebsiteEventBoothController]
    _prepare_booth_registration_values()
    _prepare_booth_registration_partner_values()
    _prepare_booth_registration_sponsor_values()
             |
             v
[Booth confirmation (backend or website)]
    event.booth._action_post_confirm(write_vals)
             |
         [use_sponsor=True AND partner_id exists?]
             |
          Yes  -->  _get_or_create_sponsor(write_vals)
                        |
                        v
                   [Search: partner+type+exhibitor_type+event]
                        |
                    Found? --> Reuse existing sponsor
                    Not found? --> Create new event.sponsor
                        |
                        v
                   booth.sponsor_id = sponsor.id
                        |
                        v
[Exhibitor portal (website_event_exhibitor)]
    Sponsor page displays booth.sponsor_name, sponsor_image_512,
    sponsor_website_description from the linked sponsor record
```

## Views

### Booth Category Form — Sponsor Configuration

**File:** `views/event_booth_category_views.xml`

Adds the "Create Sponsor" checkbox, "Sponsor Level" dropdown, and "Sponsor Type" selection to the booth category form. This is where event organizers configure whether booths in this category should generate sponsor records.

### Booth Registration Template

**File:** `views/event_booth_registration_templates.xml`

Overrides the booth registration form to include sponsor fields (name, email, slogan, description, logo image upload). These fields are shown when the selected booth category has `use_sponsor=True`.

### Booth Form View

**File:** `views/event_booth_views.xml`

Adds a "View Sponsor" button and the related sponsor fields to the backend booth form, allowing event staff to see and navigate to the linked sponsor record.

### Sponsor Email Template

**File:** `views/mail_templates.xml`

Notification email sent to the exhibitor after the sponsor record is created, confirming their presence at the event.

## JavaScript Assets

### Frontend Interaction

**File:** `static/src/interactions/booth_sponsor_details.js`

A web interaction (OWL component or interaction mixin) that handles sponsor field display/hide logic on the booth registration page. It shows sponsor fields only when the selected booth category has `use_sponsor=True`, hiding them for standard booth categories to keep the form clean.

### Test Tours

**File:** `static/tests/tours/website_event_booth_exhibitor_steps.js`
**File:** `static/tests/tours/website_event_booth_exhibitor.js`

Tour steps for the booth-exhibitor flow in Odoo's website testing framework. Tests cover the full registration flow including sponsor field entry and sponsor creation on confirmation.

## Related Modules

| Module | Role |
|---|---|
| [Modules/website_event_booth](Modules/website_event_booth.md) | Booth registration on website; provides the base `_action_post_confirm()` hook used here |
| [Modules/website_event_exhibitor](Modules/website_event_exhibitor.md) | Exhibitor/sponsor portal pages; provides the `event.sponsor` model and portal views |
| [Modules/event_booth](Modules/event_booth.md) | Backend booth management; the `event.booth` model being extended |
| `event` | Event module; provides `event.event` and `event.sponsor.type` models |
| `website_event` | Base event website module |

## Security Considerations

- The sponsor record is created with `sudo()` to bypass record rules during the automatic creation process, since the booth partner may not yet have access to the sponsor model.
- Sponsor field values from HTTP requests are sanitized before storage. The `plaintext2html()` function strips potentially dangerous HTML tags.
- Image uploads are validated by the Odoo attachment system, which enforces file size limits and accepted MIME types.

## Performance Notes

- `_get_or_create_sponsor()` performs a `search()` before any `create()`, preventing duplicate sponsor records and the need for deduplication queries later.
- The `related` fields on `event.booth` (sponsor_name, etc.) are read-only and do not add compute overhead — they simply reflect the linked `event.sponsor` record.
- The controller's fallback logic avoids unnecessary database writes by only preparing sponsor values when the category has `use_sponsor=True`.

## Migration Notes

Key points for migration from older versions:

- The `exhibitor_type` selection values are now dynamically sourced from `event.sponsor._fields['exhibitor_type'].selection` via `_get_exhibitor_type()`, ensuring consistency with the sponsor model.
- If upgrading from a version that did not have the `use_sponsor` flag, event organizers should review their booth categories and enable the flag for categories that should auto-create sponsors.
- The `sponsor_slogan` → `sponsor_subtitle` field rename is handled in the controller's dict comprehension and does not require data migration.

## See Also

- [Modules/website_event_booth](Modules/website_event_booth.md)
- [Modules/website_event_exhibitor](Modules/website_event_exhibitor.md)
- [Modules/event_booth](Modules/event_booth.md)
