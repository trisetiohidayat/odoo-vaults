---
Module: crm_iap_enrich
Version: Odoo 18
Type: Integration
Tags: #odoo, #odoo18, #crm, #iap, #lead-enrichment, #clearbit, #reveal
---

# crm_iap_enrich — CRM Lead Enrichment via IAP

## Overview

| Property | Value |
|---|---|
| Category | Sales/CRM |
| Depends | `iap_crm`, `iap_mail` |
| Auto-install | `True` |
| Version | 1.1 |
| License | LGPL-3 |
| Source | `addons/crm_iap_enrich/` |

**Purpose:** Enriches `crm.lead` records with company data (name, address, phone, country, state) by calling the Clearbit-like IAP service using the lead's **email domain**. Enrichment is triggered automatically via a hourly cron or manually via the "Enrich" button on the lead form. Each enrichment request consumes IAP credits from the `reveal` service account.

**IAP Service:** `https://iap-services.odoo.com/iap/clearbit/1/lead_enrichment_email`

---

## Architecture

```
crm.lead (enriched)
    │
    ├── iap_enrich_done (Boolean)         — prevents re-enrichment
    ├── reveal_id (Char, from iap_crm)    — IAP request tracking ID
    ├── show_enrich_button (Boolean)      — UI visibility of manual button
    │
    ├── iap_enrich()                      — main enrichment action
    ├── _iap_enrich_from_response()        — parses IAP response
    └── _iap_enrich_leads_cron()           — scheduled batch enrichment

IAP Stack:
    crm_iap_enrich → iap_crm (reveal_id field) → iap (iap.enrich.api._request_enrich)
                                                               ↓
                                              /iap/clearbit/1/lead_enrichment_email
                                                               ↓
                                              Odoo IAP (Clearbit/ZoomInfo proxy)
```

---

## Model Extensions

### `crm.lead` — Extended by `crm_iap_enrich`

**File:** `models/crm_lead.py`

#### Added Fields

| Field | Type | Description |
|---|---|---|
| `iap_enrich_done` | `Boolean` | `True` if enrichment was attempted (success or failure). Prevents repeated enrichment attempts. |
| `show_enrich_button` | `Boolean` (computed) | `True` if the "Enrich" button should be visible on the lead form. |

**`show_enrich_button` Compute Logic:**

```python
def _compute_show_enrich_button(self):
    for lead in self:
        if (not lead.active                       # lead is lost
            or not lead.email_from                # no email to enrich
            or lead.email_state == 'incorrect'    # email marked bad
            or lead.iap_enrich_done               # already enriched
            or lead.reveal_id                     # already revealed (iap_crm)
            or lead.probability == 100):          # won/lost leads
            lead.show_enrich_button = False
        else:
            lead.show_enrich_button = True
```

**L4 Note:** A lead with `email_state == 'incorrect'` (manually marked bad email) will not show the Enrich button, even if it has never been enriched. This prevents wasted credit on known-bad addresses.

#### `create()` — Auto-trigger Enrichment

```python
@api.model_create_multi
def create(self, vals_list):
    leads = super(Lead, self).create(vals_list)
    enrich_mode = self.env['ir.config_parameter'].sudo().get_param(
        'crm.iap.lead.enrich.setting', 'auto')
    if enrich_mode == 'auto':
        cron = self.env.ref('crm_iap_enrich.ir_cron_lead_enrichment', raise_if_not_found=False)
        if cron:
            cron._trigger()
    return leads
```

**Behavior:** On lead creation, if `crm.iap.lead.enrich.setting` is `'auto'`, the enrichment cron is immediately triggered (in addition to its hourly run). The cron then picks up newly created leads in its next batch.

#### `iap_enrich(from_cron=False)` — Main Enrichment Method

This is the core method. It processes leads in batches of 50 with per-batch `SAVEPOINT` commits to avoid losing credits on partial failures.

```python
def iap_enrich(self, from_cron=False):
    batches = [self[index:index + 50] for index in range(0, len(self), 50)]
    for leads in batches:
        lead_emails = {}
        with self._cr.savepoint():
            # FOR UPDATE NOWAIT lock on each lead
            self._cr.execute("SELECT 1 FROM {} WHERE id in %s FOR UPDATE NOWAIT", ...)

            for lead in leads:
                if lead.probability == 100 or lead.iap_enrich_done:
                    continue
                if not lead.email_from:
                    continue

                normalized_email = tools.email_normalize(lead.email_from)
                if not normalized_email:
                    # Email invalid → mark done, post no-credit note
                    lead.write({'iap_enrich_done': True})
                    lead.message_post('crm_iap_enrich.mail_message_lead_enrich_no_email', ...)
                    continue

                email_domain = normalized_email.split('@')[1]
                # Discard generic email providers (gmail, outlook, yahoo, etc.)
                if email_domain in iap_tools._MAIL_PROVIDERS:
                    lead.write({'iap_enrich_done': True})
                    lead.message_post('crm_iap_enrich.mail_message_lead_enrich_notfound', ...)
                else:
                    lead_emails[lead.id] = email_domain

            if lead_emails:
                try:
                    iap_response = self.env['iap.enrich.api']._request_enrich(lead_emails)
                except iap_tools.InsufficientCreditError:
                    _logger.info('Lead enrichment failed because of insufficient credit')
                    if not from_cron:
                        self.env['iap.account']._send_no_credit_notification(
                            service_name='reveal', title=_("Not enough credits..."))
                    break  # no point processing remaining batches
                except Exception as e:
                    if not from_cron:
                        self.env['iap.account']._send_error_notification(...)
                    _logger.info('Error during lead enrichment: %s', e)
                else:
                    if not from_cron:
                        self.env['iap.account']._send_success_notification(
                            message=_("The leads/opportunities have successfully been enriched"))
                    self._iap_enrich_from_response(iap_response)
```

**Key Design Decisions:**

1. **Batch size of 50** — Prevents timeout on large datasets. Each batch is independently committed.
2. **FOR UPDATE NOWAIT lock** — Prevents concurrent enrichment of the same lead from multiple requests. If lock fails, the batch continues to the next one.
3. **SAVEPOINT per batch** — If a batch fails mid-way, the `savepoint` rollback only affects that batch. Committed batches are preserved.
4. **Generic email provider filter** — `iap_tools._MAIL_PROVIDERS` contains domains like `gmail.com`, `outlook.com`, `yahoo.com`, `hotmail.com`, etc. Enrichment on these domains is skipped and marked done with a note — no credit consumed.
5. **`from_cron` flag** — Controls whether user notifications are sent. Cron runs suppress notifications; manual button triggers them.
6. **Early `break` on credit exhaustion** — Stops processing remaining batches when credits run out to avoid partial enrichment without notification.
7. **`commit()` after each batch** — Outside test mode, explicitly commits each batch so a rollback doesn't undo already-successful enrichments.

#### `_iap_enrich_from_response(iap_response)` — Parse and Apply IAP Data

```python
def _iap_enrich_from_response(self, iap_response):
    for lead in self.search([('id', 'in', list(iap_response.keys()))]):
        iap_data = iap_response.get(str(lead.id))
        if not iap_data:
            lead.write({'iap_enrich_done': True})
            lead.message_post('crm_iap_enrich.mail_message_lead_enrich_notfound', ...)
            continue

        values = {'iap_enrich_done': True}

        # Field mapping: lead_field → iap_field
        # Only fills empty fields (never overwrites user-entered data)
        lead_fields  = ['partner_name', 'reveal_id', 'street', 'city', 'zip']
        iap_fields   = ['name',         'clearbit_id', 'street_name', 'city', 'postal_code']

        for lead_field, iap_field in zip(lead_fields, iap_fields):
            if not lead[lead_field] and iap_data.get(iap_field):
                values[lead_field] = iap_data[iap_field]

        # Phone: first number → phone, second → mobile
        if not lead.phone and iap_data.get('phone_numbers'):
            values['phone'] = iap_data['phone_numbers'][0]
        if not lead.mobile and iap_data.get('phone_numbers') and len(iap_data['phone_numbers']) > 1:
            values['mobile'] = iap_data['phone_numbers'][1]

        # Country/state from country_code + state_code
        if not lead.country_id and iap_data.get('country_code'):
            country = self.env['res.country'].search([('code', '=', iap_data['country_code'].upper())])
            values['country_id'] = country.id
            country = lead.country_id  # reassign for state lookup below
        if not lead.state_id and country and iap_data.get('state_code'):
            state = self.env['res.country.state'].search([
                ('code', '=', iap_data['state_code']),
                ('country_id', '=', country.id)
            ])
            values['state_id'] = state.id

        lead.write(values)

        # Post enrichment note with company info
        template_values = iap_data
        template_values['flavor_text'] = _("Lead enriched based on email address")
        lead.message_post(
            'iap_mail.enrich_company',
            render_values=template_values,
            subtype_xmlid='mail.mt_note',
        )
```

**Field Mapping:**

| `crm.lead` field | IAP response key | Notes |
|---|---|---|
| `partner_name` | `name` | Company legal name |
| `reveal_id` | `clearbit_id` | Clearbit's internal ID |
| `street` | `street_name` | Street address |
| `city` | `city` | City name |
| `zip` | `postal_code` | ZIP/postal code |
| `phone` | `phone_numbers[0]` | First phone number |
| `mobile` | `phone_numbers[1]` | Second phone number (if exists) |
| `country_id` | `country_code` | ISO 3166-1 alpha-2 code |
| `state_id` | `state_code` | State ISO code (requires country_id) |
| `description` | (via `iap_mail.enrich_company` template) | Rendered in message body |

**L4 — Non-Overwriting Policy:**
All fields are filled **only if currently empty**. If a salesperson has already entered a phone number or city, the IAP data is ignored for that field. This prevents IAP from overwriting manually curated data.

#### `_merge_get_fields_specific()` — Merge Behavior

```python
def _merge_get_fields_specific(self):
    return {
        ** super(Lead, self)._merge_get_fields_specific(),
        'iap_enrich_done': lambda fname, leads: any(lead.iap_enrich_done for lead in leads),
    }
```

On lead merge, if **any** source lead was enriched, the target lead is marked as enriched (`iap_enrich_done = True`). This is conservative — it prevents re-enriching a merged lead.

#### `_iap_enrich_leads_cron()` — Scheduled Batch Enrichment

```python
@api.model
def _iap_enrich_leads_cron(self, enrich_hours_delay=1, leads_batch_size=1000):
    timeDelta = self.env.cr.now() - datetime.timedelta(hours=enrich_hours_delay)
    leads = self.search([
        ('iap_enrich_done', '=', False),
        ('reveal_id', '=', False),
        '|', ('probability', '<', 100), ('probability', '=', False),
        ('create_date', '>', timeDelta)
    ], limit=leads_batch_size)
    leads.iap_enrich(from_cron=True)
```

**Cron Criteria:**
- `iap_enrich_done = False` — not yet enriched
- `reveal_id = False` — not yet revealed by `crm_iap_lead_enrich_domain` (prevent double processing)
- Probability `< 100` — not won/lost
- `create_date > now - 1 hour` — only leads created in the last hour (configurable via `enrich_hours_delay`)

The cron runs **every 1 hour** (configured in `data/ir_cron.xml`). It processes up to **1000 leads** per run.

---

### `res.config.settings` — Extended by `crm_iap_enrich`

**File:** `models/res_config_settings.py`

**No new fields.** Controls the `lead_enrich_auto` selection already present in the CRM settings form.

```python
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.model
    def get_values(self):
        values = super().get_values()
        cron = self.sudo().env.ref('crm_iap_enrich.ir_cron_lead_enrichment', raise_if_not_found=False)
        values['lead_enrich_auto'] = 'auto' if cron and cron.active else 'manual'
        return values

    def set_values(self):
        super().set_values()
        cron = self.sudo().env.ref('crm_iap_enrich.ir_cron_lead_enrichment', ...)
        if cron and cron.active != (self.lead_enrich_auto == 'auto'):
            cron.active = self.lead_enrich_auto == 'auto'
```

**Setting:** `CRM > Configuration > Settings > Lead Enrichment`: `"auto"` or `"manual"`.

- **Auto:** Cron is active, runs every hour, triggers on lead creation.
- **Manual:** Cron is inactive. Users must click "Enrich" button on each lead.

---

## IAP Enrichment API

**Service:** `iap.enrich.api` (abstract model, `addons/iap/models/iap_enrich_api.py`)

```python
@api.model
def _request_enrich(self, lead_emails):
    # lead_emails: dict{lead_id: email_domain}
    params = {
        'domains': lead_emails,
    }
    return self._contact_iap('/iap/clearbit/1/lead_enrichment_email', params=params)

def _contact_iap(self, local_endpoint, params):
    account = self.env['iap.account'].get('reveal')  # reveal service account
    dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
    params['account_token'] = account.account_token
    params['dbuuid'] = dbuuid
    base_url = self.env['ir.config_parameter'].sudo().get_param(
        'enrich.endpoint', 'https://iap-services.odoo.com')
    return iap_tools.iap_jsonrpc(base_url + local_endpoint, params=params, timeout=300)
```

**Credit Consumption:**
- 1 credit per **domain** (not per lead). If multiple leads share the same domain and are enriched in the same batch request, credit is consumed per unique domain.
- Service name: `'reveal'`
- Error: `InsufficientCreditError` → triggers notification to admin

---

## Data Records

### Cron

**File:** `data/ir_cron.xml`

```xml
<record id="ir_cron_lead_enrichment" model="ir.cron">
    <field name="name">CRM: enrich leads (IAP)</field>
    <field name="model_id" ref="crm.model_crm_lead"/>
    <field name="user_id" ref="base.user_root"/>
    <field name="state">code</field>
    <field name="code">model._iap_enrich_leads_cron()</field>
    <field name="interval_number">1</field>
    <field name="interval_type">hours</field>
</record>
```

Runs as `base.user_root` (superuser) to avoid ACL issues.

### Server Action

**File:** `data/ir_action.xml`

```xml
<record id="action_enrich_mail" model="ir.actions.server">
    <field name="name">Enrich</field>
    <field name="model_id" ref="model_crm_lead"/>
    <field name="binding_model_id" ref="crm.model_crm_lead"/>
    <field name="state">code</field>
    <field name="code">records.iap_enrich()</field>
</record>
```

This action is bound to `crm.lead` so it appears in the "Action" dropdown on the lead list/form. The `show_enrich_button` on the form controls visibility in the UI.

### Mail Templates (Internal Notes)

**File:** `data/mail_templates.xml`

Two noupdate templates used for `message_post`:

1. **`mail_message_lead_enrich_notfound`** — Posted when IAP returns no data or email is a generic provider. Text: *"No company data found based on the email address or email address is one of an email provider. No credit was consumed."*

2. **`mail_message_lead_enrich_no_email`** — Posted when email address is invalid (doesn't normalize). Text: *"Enrichment could not be done because the email address does not look valid."*

### Form Button

**File:** `views/crm_lead_views.xml`

Two buttons (one for leads, one for opportunities) with `data-hotkey="g"` and visibility driven by `show_enrich_button`:

```xml
<button string="Enrich" name="iap_enrich" type="object"
        class="btn btn-secondary" data-hotkey="g"
        title="Enrich lead with company data"
        invisible="not show_enrich_button or type == 'opportunity'"/>
```

### Config Settings

**File:** `views/res_config_settings_view.xml`

Places the `iap_buy_more_credits` widget after the `lead_enrich_auto` field in the CRM settings form.

---

## Enrichment vs Reveal — Key Distinction

| Aspect | `crm_iap_enrich` (this module) | `crm_iap_lead_enrich_domain` (website_crm_iap) |
|---|---|---|
| Trigger | Email domain (email_from) | Website visitor domain (IP + hostname) |
| Automatic? | Yes (cron, configurable) | Yes (automatic on form fill) |
| Credit model | Per unique domain enriched | Per reveal request |
| Sets `reveal_id`? | No | Yes |
| Works for leads without email? | No | Yes (uses visitor IP) |
| `iap_enrich_done` set? | Yes | No |
| IAP endpoint | `/iap/clearbit/1/lead_enrichment_email` | `/iap/clearbit/1/lead` (likely) |

**Conflict prevention:** The cron excludes leads with `reveal_id` set (`('reveal_id', '=', False)`) so leads already processed by the reveal service are not re-enriched by the email-based enricher.

---

## Key L4 Insights

1. **Non-overwriting enrichment** — Every field is filled only if currently empty. Salesperson data always takes precedence over IAP data.
2. **Dual-trigger system** — Cron runs hourly and also fires immediately on lead creation. This gives near-instant enrichment without hammering IAP on bulk imports.
3. **Credit efficiency via batch dedup** — `lead_emails` dict deduplicates by domain. Multiple leads from the same company consume only 1 credit.
4. **No-retry after failure** — `iap_enrich_done = True` is set even on failures (invalid email, no data found, error). Failed leads are never retried automatically. Manual re-enrichment requires resetting the field.
5. **`reveal_id` interaction** — If `crm_iap_lead_enrich_domain` (website-based reveal) is installed and has already revealed a lead, the email enricher skips it entirely. This prevents double credit consumption.
6. **Per-batch commit** — `self.env.cr.commit()` after each batch ensures partial success is preserved. If credits run out mid-batch, already-enriched leads stay enriched.
7. **Generic email provider blocking** — Before calling IAP, domains in `iap_tools._MAIL_PROVIDERS` (gmail, outlook, yahoo, hotmail, etc.) are rejected client-side. No credit consumed for personal email addresses.
8. **Country/state resolution** — Both country and state are looked up by code. If the country lookup fails, the state is also skipped (prevents orphan state assignments).
9. **Notification gating** — `from_cron` flag ensures users don't get notifications for automated background enrichment. Notifications are only sent for manual enrichment actions.
10. **`probabilty = 100` skip** — Won leads (`probability == 100`) are excluded from enrichment. Lost leads (`active = False`) are excluded by the cron search. Both are skipped in the manual enrich path as well.
