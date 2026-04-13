---
tags:
  - odoo
  - odoo19
  - modules
  - account
  - mail
  - product
created: 2026-04-11
description: Links product templates to email templates, automatically sending product-specific emails when customer invoices are validated.
---

# product_email_template

## Module Overview

| Attribute       | Value                                                      |
|----------------|------------------------------------------------------------|
| Directory       | `odoo/addons/product_email_template/`                     |
| Version         | `19.0.1.0.0` (Odoo standard, omitted in manifest)        |
| Depends         | `account`                                                  |
| Category        | `Accounting/Accounting`                                    |
| License         | `LGPL-3`                                                   |
| Author          | Odoo S.A.                                                  |
| Auto-install    | No                                                         |
| Installable     | Yes                                                        |

**Purpose:** Links [product.template](product.template.md) records to [mail.template](mail.template.md) records so that when a **customer invoice** (`out_invoice`) is validated (posted via `_post()`), an email is dispatched to the customer for each invoice line whose product has a template assigned. Intended for sending product-specific materials, agendas, access credentials, or documentation automatically at invoice posting.

---

## Module Files

```
product_email_template/
├── __init__.py
├── __manifest__.py                      # Depends: account only
├── models/
│   ├── __init__.py                     # Imports product, account_move
│   ├── product.py                      # product.template extension
│   └── account_move.py                 # account.move extension
├── views/
│   ├── product_views.xml               # Injects email_template_id into product form
│   └── mail_template_views.xml         # Simplified mail.template form (priority 100)
├── tests/
│   ├── __init__.py
│   └── test_account_move.py             # Two post_install test cases
└── i18n/
    └── product_email_template.pot       # + 40 language .po files
```

---

## L1: How Product Templates Have Email Templates Attached

At the most fundamental level, this module does one thing: it adds an optional `email_template_id` field to `product.template`. When a user posts a customer invoice, Odoo iterates over every invoice line. For each line whose product has a template assigned, Odoo renders that template against the `account.move` record and sends the result as an email to the invoice's partner.

The business use case is delivering post-purchase content: a training course vendor links `product.template` "Advanced Python 3" to `mail.template` "Python Course Welcome Email" — containing the agenda, Zoom link, and downloadable PDF syllabus. When the accounting clerk confirms the customer invoice, the student automatically receives the welcome email without any manual intervention.

The field is placed on `product.template` (not `product.product`) for two reasons: first, the typical use case is template-level — one email template per course, shared across all variants of that product; second, placing it on the template avoids data duplication, since each variant implicitly shares the template field through the standard product delegation chain.

**Activation path (user perspective):**
1. Install `product_email_template` (depends on `account`)
2. Go to **Inventory > Products > Products**, select a product
3. Open the **Invoicing** tab (visible to users in `account.group_account_invoice` or `account.group_account_readonly`)
4. In the **Automatic Email at Invoice** group, pick an email template from the dropdown
5. Confirm a customer invoice containing that product
6. The customer receives the email

---

## L2: Field Types, Defaults, Constraints

### `product.template` — Extended

**File:** `models/product.py`

```python
class ProductTemplate(models.Model):
    _inherit = "product.template"

    email_template_id = fields.Many2one('mail.template',
        string='Product Email Template',
        help='When validating an invoice, an email will be sent to the customer '
             'based on this template. The customer will receive an email for each '
             'product linked to an email template.')
```

#### `email_template_id` Field Properties

| Property           | Value                                                             |
|-------------------|-------------------------------------------------------------------|
| Type              | `Many2one`                                                        |
| Relation          | `mail.template`                                                    |
| Storage           | Stored column on `product_template` table                          |
| Ondelete          | Odoo ORM default (`cascade`)                                       |
| Scope             | Per `product.template` — shared by all `product.product` variants   |
| Required          | No (optional)                                                     |
| Default           | `False` / empty recordset                                         |
| Index             | None (no explicit `index=True`)                                    |
| Groups            | None (visible to all with access to the product form)              |

**`product.product` delegation note:** `product.product` inherits from `product.template` via `_inherits = {'product.template': 'product_tmpl_id'}`. Accessing `product_id.email_template_id` in an invoice line transparently delegates to `product_tmpl_id.email_template_id`. The ORM handles this transparently — no computed field or override is needed.

**Ondelete behavior:** The ORM default for `Many2one` without an explicit `ondelete` is `cascade` in PostgreSQL terms. For `mail.template` records that are deleted, the FK in `product_template` will be set appropriately. Since the field is optional, this does not cause data integrity failures.

**No constraint on `mail.template` model:** The domain `[('model', '=', 'account.move')]` is enforced only in the UI selector. A template for any other model can still be linked programmatically — it simply will not render correctly against an `account.move` record.

---

### `account.move` — Extended

**File:** `models/account_move.py`

```python
class AccountMove(models.Model):
    _inherit = 'account.move'

    def invoice_validate_send_email(self):
        if self.env.su:
            self = self.with_user(SUPERUSER_ID)
        for invoice in self.filtered(lambda x: x.move_type == 'out_invoice'):
            comment_subtype_id = self.env['ir.model.data']._xmlid_to_res_id('mail.mt_comment')
            for line in invoice.invoice_line_ids:
                if line.product_id.email_template_id:
                    invoice.message_post_with_source(
                        line.product_id.email_template_id,
                        email_layout_xmlid="mail.mail_notification_light",
                        subtype_id=comment_subtype_id,
                    )
        return True

    def _post(self, soft=True):
        posted = super()._post(soft)
        posted.invoice_validate_send_email()
        return posted
```

#### Method Signature Analysis

| Method                           | Decorator | Parameters                   | Returns   | Notes                                       |
|----------------------------------|-----------|------------------------------|-----------|---------------------------------------------|
| `invoice_validate_send_email()`  | None      | `self` (recordset)           | `bool`    | Always `True`; exceptions not propagated     |
| `_post(soft=True)`              | None      | `self`, `soft: bool = True` | recordset | Hooks into account._post                    |

**`soft` parameter:** Passed through to `super()._post()`. `soft=True` is used for auto-posting scheduled future-date invoices. Email sending fires unconditionally regardless of the `soft` flag — there is no branching on `soft` in this module.

**No decorator on either method:** Both `invoice_validate_send_email` and `_post` use no decorator (no `@api.model`, no `@api.multi`). Recordsets are iterated manually inside each method. `@api.multi` was the explicit form in Odoo 14 and earlier; it became the implicit default in Odoo 15+, so omitting it is equivalent to `@api.multi`.

---

### Product Form View — `product_views.xml`

**Target XPath:** `//page[@name='invoicing']//group[@name='accounting']`

```xml
<record id="product_template_form_view" model="ir.ui.view">
    <field name="inherit_id" ref="product.product_template_form_view"/>
    <field name="arch" type="xml">
        <xpath expr="//page[@name='invoicing']//group[@name='accounting']" position="inside">
            <group name="email_template" string="Automatic Email at Invoice">
                <field name="email_template_id"
                    string="Email Template"
                    help="Send a product-specific email once the invoice is validated"
                    domain="[('model','=','account.move')]"
                    context="{
                        'form_view_ref': 'product_email_template.email_template_form_simplified',
                        'default_model': 'account.move',
                        'default_subject': name,
                        'default_name': name,
                    }"/>
            </group>
        </xpath>
        <page name="invoicing" position="attributes">
            <attribute name="groups">account.group_account_invoice,account.group_account_readonly</attribute>
        </page>
    </field>
</record>
```

| Attribute          | Value                                                           |
|--------------------|-----------------------------------------------------------------|
| Domain             | `[('model', '=', 'account.move')]` — restricts template selector  |
| `form_view_ref`   | `product_email_template.email_template_form_simplified` — opens simplified template editor |
| `default_model`   | `'account.move'` — sets `mail.template.model_id` via context     |
| `default_subject`  | `name` — pre-populates template subject with product name         |
| `default_name`    | `name` — pre-populates template internal name with product name   |
| Page visibility    | `account.group_account_invoice` or `account.group_account_readonly` gates the **Invoicing** tab |

The **Invoicing tab** itself is gated by `account` group access. Users without invoice access never see the email template field.

### Simplified Mail Template Form — `mail_template_views.xml`

**Priority:** `100` — only activated when explicitly referenced via `form_view_ref` context; does not replace the standard `mail.template` form.

```xml
<record id="email_template_form_simplified" model="ir.ui.view">
    <field name="model">mail.template</field>
    <field name="priority">100</field>
    <field name="arch" type="xml">
        <form string="Email Template">
            <group>
                <field name="subject" invisible="1"/>
                <field name="name" invisible="1"/>
                <field name="model" invisible="1"/>
                <h3 colspan="2">Body</h3>
                <field name="body_html" nolabel="1" colspan="2" widget="html_mail"/>
                <field name="attachment_ids" nolabel="1" colspan="2" widget="many2many_binary"/>
            </group>
        </form>
    </field>
</record>
```

Fields hidden from the simplified form: `email_from`, `email_to`, `reply_to`, `use_default_to`, `partner_to`, `email_cc`, `report_template_ids`, `model_id`. These take standard defaults: `email_from` uses the company's sender address; `email_to` uses the invoice's partner email via `use_default_to=True`.

---

## L3: Cross-Model Integration, Override Pattern, Workflow Trigger

### Cross-Model: Product ↔ Email Template

```
product.template
  └── email_template_id ──────────────→ mail.template
                                         ├── model_id → ir.model (account.move)
                                         ├── body_html   → QWeb body
                                         ├── subject     → email subject
                                         ├── attachment_ids → files attached to email
                                         └── use_default_to → True (default): resolves to invoice partner
```

The `mail.template` model is a generic template engine. When `message_post_with_source` renders it, the template's `model_id` (`account.move`) determines the render context. The `account.move` record is passed as `object` and `invoice` template variables. The `partner_id` of the invoice is used for `email_to` resolution (via `use_default_to=True`).

**Template body implication:** Since the render context is the `account.move`, not the product or the invoice line, any product-specific placeholders in the template body must use dot-notation against the invoice lines or must be written to reference `object.partner_id.name` etc. There is no built-in access to the triggering line or product in the template context.

### Override Pattern: `_post` Hook

```
account.move: action_post()
    │
    ▼
account.move: _post(soft=False)
    │  [account/models/account_move.py]
    │  • Validates required fields
    │  • Assigns invoice number
    │  • Creates account.move line entries
    │  • Locks editable fields
    │  ✔ super() returns successfully
    │
    ▼
product_email_template.account_move: invoice_validate_send_email()
    │  [product_email_template/models/account_move.py]
    │  • Escalates to SUPERUSER_ID if already in sudo context
    │  • Filters: move_type == 'out_invoice' only
    │  • Resolves: mail.mt_comment subtype ID (numeric)
    │  • For each invoice_line_ids line:
    │       if line.product_id.email_template_id:
    │           invoice.message_post_with_source(
    │               line.product_id.email_template_id,
    │               email_layout_xmlid="mail.mail_notification_light",
    │               subtype_id=<numeric_subtype_id>,
    │           )
    │               │
    │               ├── QWeb render body_html against account.move as object
    │               ├── Resolve recipients via mail.template use_default_to
    │               ├── Link attachment_ids from template
    │               ├── Wrap in mail.mail_notification_light layout
    │               └── Dispatch mail.mail record → SMTP queue
    │
    ▼
Returned posted recordset (email already queued)
```

**Execution order guarantee:** Because `invoice_validate_send_email()` is called **after** `super()._post()` returns successfully, a validation error in `_post` (e.g., missing account, invalid tax computation) prevents any email from being dispatched.

**Transaction boundary:** `message_post_with_source` creates `mail.mail` and `mail.message` records within the current transaction. The actual SMTP send happens asynchronously via the `mail.mail` cron. If the `_post` transaction rolls back, the email records are rolled back along with it.

### Workflow Trigger: Invoice Validation

The trigger is `_post()`, called by `action_post()` (the UI button) and also by automated cron jobs when invoices reach their `auto_post` scheduled date.

| Trigger Source          | Call Chain                                                     |
|------------------------|----------------------------------------------------------------|
| UI: "Confirm" button   | `action_post()` → `_post()` → `invoice_validate_send_email()` |
| Cron: auto-post         | `_autopost_to_invoice()` → `_post(soft=True)` → ...           |
| Python API              | `.write({'state': 'posted'})` → `_post()` → ...              |

---

### Cross-Module Integrations

| Module                    | Integration Point                                                  |
|---------------------------|-------------------------------------------------------------------|
| `account`                 | Extends `account.move`. Only fires on `move_type == 'out_invoice'`. |
| `mail`                    | `mail.template` as relation. `message_post_with_source`. `mail.mail_notification_light` layout. `mail.mt_comment` subtype. |
| `product`                 | Extends `product.template`. Reads via `line.product_id` delegation. |
| `base`                    | `ir.model.data._xmlid_to_res_id` for numeric subtype ID lookup.  |
| `mail.compose.message`    | Internally used by `message_post_with_source` composer.          |

---

## L4: Odoo 18 to 19 Changes, Security

### Odoo 18 → 19 Changes

No structural changes were introduced to `product_email_template` between Odoo 18 and Odoo 19. The module's architecture — `_post` override, `message_post_with_source` API, simplified template form — was stable across the boundary.

Key observations:

1. **`_post` hook stability:** The `account` module refactored `_post` in Odoo 17 (breaking it into `_post` / `_post_validate_and_sync` / `_compute_name`) but the hook contract remained stable. `product_email_template` calls `super()._post(soft=soft)` first, then fires emails — this ordering is preserved in Odoo 19.

2. **`message_post_with_source` API:** Introduced in Odoo 15 as part of the mail composer refactor; has not changed signature. Renders `mail.template` via QWeb using the `mail.render.mixin` mechanism.

3. **`SUPERUSER_ID` constant:** In `models/account_move.py`, imported as `from odoo import api, models, SUPERUSER_ID`. `SUPERUSER_ID` remains the integer `True` (which acts as ID 2 in `res.users`) in Odoo 19, unchanged from Odoo 18.

4. **`move_type` field:** The field name `move_type` on `account.move` replaced the older `type` field starting in Odoo 17. `product_email_template` correctly uses `move_type` (not `type`), confirming it was written for Odoo 17+.

5. **`soft` parameter:** Passed through to `super()._post()`. In Odoo 19, the `account` module's `_post` signature is `_post(self, soft=True)` — unchanged from Odoo 18.

6. **Method decorators:** Both `invoice_validate_send_email` and `_post` use no decorator. This is equivalent to `@api.multi` in Odoo 15+ (the default for recordset methods). No change needed between Odoo 18 and 19.

7. **Potential concern — `ir.model.data` deprecation:** In Odoo 18+, `ir.model.data` is partially deprecated in favor of direct `ir.model.data._load_xmlid` and the `get_object` helper. However, `_xmlid_to_res_id` is still functional and used extensively in Odoo core and community modules. No migration needed at this time.

### Security Analysis

| Concern                           | Risk Level | Mitigation                                                   |
|-----------------------------------|-----------|--------------------------------------------------------------|
| Portal user mail access          | MEDIUM     | `with_user(SUPERUSER_ID)` within the method only            |
| Field visibility                  | LOW        | `account.group_account_invoice` gates the Invoicing tab       |
| Template model restriction (UI vs Python) | LOW   | UI domain not enforced in Python — template model not validated |
| ACL on `mail.template`            | MEDIUM     | Record rule silently returns empty recordset — no email sent  |
| No recipient validation           | LOW        | Mail composer handles bounces; no pre-validation here        |
| Email as chatter message          | LOW        | Logged in `mail.message` for audit trail                    |
| SUPERUSER escalation scope        | LOW        | Method-scoped; does not persist after return                 |
| SQL injection                     | SAFE       | All queries use ORM — no raw SQL                             |
| XSS in template body              | SAFE       | QWeb rendering applies Odoo's standard HTML sanitization     |
| Data exfiltration                 | SAFE       | No external API calls; only reads product/template records    |

**`SUPERUSER_ID` escalation detail (source-verified):**

```python
def invoice_validate_send_email(self):
    if self.env.su:                       # Is current context already running as superuser?
        # sending mail in sudo was meant for it being sent from superuser
        self = self.with_user(SUPERUSER_ID)  # Re-bind (idempotent)
    for invoice in self.filtered(lambda x: x.move_type == 'out_invoice'):
        ...
```

The guard `if self.env.su` detects whether the current execution context is already running as `SUPERUSER_ID` (e.g., portal user posting via `sudo()`). The `with_user(SUPERUSER_ID)` call is idempotent — re-binding to the same user has no effect. Without this guard, a portal user posting an invoice would be blocked by mail ACLs when `message_post_with_source` tried to render or send.

**ACL gap — silent failure:** If the current user lacks read access to the `mail.template` record linked to the product, `line.product_id.email_template_id` returns an empty recordset. The `if` condition fails silently. No email is sent and no error is raised. This is standard Odoo ACL behavior. In multi-company or restricted-group scenarios, ensure the template has appropriate read access for users who post invoices.

**Email body content security:** The `body_html` field of `mail.template` supports raw QWeb. If a template uses `t-raw` directives with unsanitized user content, that content is exposed to the email recipient. Odoo's standard `mail.message` rendering applies sanitization to the final HTML output, but template authors must not include raw user-generated content without proper QWeb escaping.

---

## Data Flow

```
User clicks "Confirm" on out_invoice
    │
    ▼
account.move: action_post()
    │
    ▼
account.move: _post(soft=False)
    │
    ▼
product_email_template.account_move: invoice_validate_send_email()
    │  • Filters: move_type == 'out_invoice'
    │  • Resolves: mail.mt_comment subtype ID
    │  • For each invoice_line_ids line:
    │       if line.product_id.email_template_id:
    │           invoice.message_post_with_source(
    │               line.product_id.email_template_id,
    │               email_layout_xmlid="mail.mail_notification_light",
    │               subtype_id=<comment_subtype_id>,
    │           )
    │               │
    │               ├── QWeb render body_html against account.move as object
    │               ├── Resolve recipients via mail.template use_default_to
    │               ├── Link attachment_ids from template
    │               ├── Wrap in mail.mail_notification_light layout
    │               └── Dispatch mail.mail record → SMTP queue
    │
    ▼
Returned posted recordset
```

---

## Edge Cases and Failure Modes

### Same product on multiple lines sends multiple emails
If the same product (with a template) appears on two invoice lines, two emails are sent — one per line iteration. No deduplication. This may be intentional (e.g., two seats for a training course) or unintended.

### Line without a product silently skipped
Invoice lines of type `section`, `note`, or lines with `product_id = False` are iterated but produce no email.

### Vendor bills and refunds produce zero emails
The `move_type == 'out_invoice'` filter is hardcoded. Credit notes, vendor bills, and internal transfers are completely silent.

### Empty template body sends a mail notification with no body
`message_post_with_source` renders the template even if `body_html` is empty. The result is a `mail.mail` notification with an empty body, sent to the partner.

### Partner with no email address
If `partner_id.email` is empty and `use_default_to=True` (the default), the mail composer attempts to send without recipients. The mail record may be created but never dispatched.

### Invoice posted by public/portal user via `sudo()`
The explicit `with_user(SUPERUSER_ID)` guard handles this scenario. Tested by `test_send_as_system_when_sudo`.

### `_post()` raises before email send
`invoice_validate_send_email()` is called **after** `super()._post()` returns. If `super()._post()` raises, no emails are dispatched. If `super()._post()` succeeds but an unrelated exception propagates out of `invoice_validate_send_email`, the email has already been queued and will not be rolled back.

### Record rules on `mail.template`
Access-denied silently returns empty recordset — no email for that line, no error.

---

## Performance Considerations

- **Linear email count:** Each templated invoice line triggers one `message_post_with_source` call. An invoice with 50 templated lines fires 50 emails in a single `_post` call.
- **O(n) QWeb renders:** Each call renders `body_html` independently. No batch rendering.
- **Subtype resolution O(1):** `_xmlid_to_res_id` is called outside the inner loop, once per invoice.
- **No attachment deduplication:** Same `ir.attachment` linked to multiple templates appears in multiple emails.
- **SMTP dispatch:** Each email triggers a separate `mail.mail` creation and SMTP send. For bulk invoice posting, emails are sent sequentially within each `_post`.

---

## Tests

**File:** `tests/test_account_move.py`

Both tests inherit from `AccountTestInvoicingCommon` and are tagged `post_install, -at_install`.

### Setup (shared)

```python
def setUp(self):
    super().setUp()
    Template = self.env['mail.template']
    self.template = Template.create({
        'name': 'Product Template',
        'subject': 'YOUR PRODUCT',
        'model_id': self.env['ir.model']._get_id('account.move')
    })
    self.customer = self.env['res.partner'].create({
        'name': 'James Bond',
        'email': 'james.bond@yopmail.com'
    })
    self.product_a.email_template_id = self.template.id
```

The test product `self.product_a` comes from `AccountTestInvoicingCommon` (provided by the `account` module's test common class). The template's `model_id` is explicitly set to `account.move`, matching the product form view domain.

### `test_send_product_template_email_on_invoice_post`

Creates a customer invoice with one line (product_a, qty 1, price 123), posts it, then asserts:
1. Exactly 1 `mail.message` with `subject = 'YOUR PRODUCT'` was created after the prior max ID.
2. That message has a non-empty `email_from` address.

### `test_send_as_system_when_sudo`

Same invoice creation and post, but the `action_post()` call is wrapped as:

```python
pub_user = self.env['res.users'].create({
    'login': 'test_public_user',
    'name': 'test_public_user',
    'email': False,
    'group_ids': [(6, 0, [self.env.ref('base.group_public').id])]
})
invoice.with_user(pub_user).sudo().action_post()
```

`pub_user` is a `res.users` in `base.group_public` with no email address. The test confirms that even a public user triggering invoice posting results in an email with a valid `email_from`, validating the `with_user(SUPERUSER_ID)` guard.

---

## Field Reference

### `product.template` — Added Fields

| Field               | Type      | Relation          | Stored | Required | Notes                                      |
|---------------------|-----------|-------------------|--------|----------|--------------------------------------------|
| `email_template_id` | Many2one | `mail.template`   | Yes    | No       | Shared across all product variants          |

### `account.move` — Methods

| Method                             | Decorator | Parameters                    | Returns   | Notes                                     |
|------------------------------------|-----------|-------------------------------|-----------|-------------------------------------------|
| `invoice_validate_send_email()`    | None      | `self`                        | `bool`    | Sends n emails for n templated lines      |
| `_post(soft=True)`                | None      | `self`, `soft: bool = True`  | recordset | Hooks into account._post                  |

### `mail.template` — Key Fields Used by This Module

| Field            | Type     | Used By                             | Notes                                              |
|------------------|----------|-------------------------------------|----------------------------------------------------|
| `model_id`       | Many2one | Domain filter                       | Determines available templates in selector        |
| `subject`        | Char     | Pre-filled via context              | Hidden in simplified form; pre-populated          |
| `body_html`      | Html     | QWeb render in `message_post_with_source` | Rendered against `account.move` as `object` |
| `attachment_ids` | M2M      | Attached to dispatched email        | Visible in simplified form                         |
| `use_default_to` | Boolean  | Recipient resolution                | Default `True`; resolves from invoice partner     |

---

## Limitations Summary

| Limitation                                  | Workaround                                           |
|--------------------------------------------|------------------------------------------------------|
| Sends on `out_invoice` only               | Custom module extending `invoice_validate_send_email` |
| Same product on multiple lines = duplicate emails | Custom extension with line deduplication         |
| No per-variant template assignment          | Custom module extending `product.product`            |
| Template render context is `account.move`, not line | Use QWeb line iteration in template body   |
| No scheduling/delay                        | Custom module using `ir.cron`                        |
| No bounce/error handling                   | Mail module handles; module does not intercept      |
| Template record rules silently block sends | Grant read access to the template for relevant users |

---

## See Also

- [Modules/account](Modules/account.md) — `account.move` base model, `_post()` lifecycle
- [Modules/mail](Modules/mail.md) — `mail.template`, `message_post_with_source`, `mail.render.mixin`
- [Modules/product](Modules/product.md) — `product.template`, `product.product` delegation chain
- [Core/API](Core/API.md) — `@api.model`, `@api.depends` patterns for similar override patterns
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — `_post` state machine override pattern
