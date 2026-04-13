---
uuid: stock-sms-l4
tags:
  - #odoo
  - #odoo19
  - #modules
  - #stock_sms
  - #sms
  - #workflow
created: 2026-04-11
modified: 2026-04-11
module: stock_sms
module_version: "19.0"
module_category: Supply Chain/Inventory
module_type: Odoo Community (CE)
module_location: ~/odoo/odoo19/odoo/addons/stock_sms/
module_dependencies:
  - stock
  - sms
---

# Stock SMS (`stock_sms`)

## Overview

| Attribute | Value |
|---|---|
| **Name** | Stock - SMS |
| **Technical name** | `stock_sms` |
| **Category** | Supply Chain/Inventory |
| **Version** | 1.0 |
| **Depends** | `stock`, `sms` |
| **Auto-install** | Yes |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

Sends an SMS text message confirmation to the customer when an outgoing delivery picking is validated. The module hooks into `stock.picking` validation flow via `_pre_action_done_hook` and `_send_confirmation_email` (called from `button_validate`) to send the notification. It also provides an interactive wizard (`confirm.stock.sms`) that gates the validation on a first-time warning screen, teaching users how to disable the feature.

This module does **not** handle low stock SMS alerts — that functionality belongs to `stock` (reordering rules) or `spreadsheet` modules. The module focuses exclusively on delivery confirmation SMS.

---

## Architecture

### Module Location
`~/odoo/odoo19/odoo/addons/stock_sms/`

### File Tree
```
stock_sms/
├── __init__.py                   # Registers models/, wizard/ submodules + hooks
├── __manifest__.py                # Dependencies, data files, hooks
├── models/
│   ├── __init__.py
│   ├── res_company.py            # res.company fields + _default_confirmation_sms_picking_template
│   ├── res_config_settings.py    # ResConfigSettings related field
│   └── stock_picking.py          # stock.picking SMS workflow overrides
├── wizard/
│   ├── __init__.py
│   ├── confirm_stock_sms.py      # confirm.stock.sms transient wizard
│   └── confirm_stock_sms_views.xml
├── data/
│   └── sms_data.xml              # sms.template noupdate=1 record
├── security/
│   ├── ir.model.access.csv        # ACL entries
│   └── sms_security.xml           # ir.rule for sms.template write access
└── views/
    └── res_config_settings_views.xml  # Inherits stock settings form
```

### Auto-install Behaviour
`auto_install: True` means that when both `stock` and `sms` are installed (or their dependencies resolved), this module is installed automatically. The `post_init_hook` then assigns the default SMS template to all existing companies that lack one.

---

## Fields

### L1/L2 — `res.company` (stock_sms extension)

**File:** `models/res_company.py`

#### `stock_sms_confirmation_template_id`
- **Type:** `Many2one('sms.template')`
- **L2:** The SMS template used for delivery confirmation. Domain-restricted to `model = stock.picking`. Defaulted via `_default_confirmation_sms_picking_template` which looks up `stock_sms.sms_template_data_stock_delivery`. Set on install by `post_init_hook`.
- **Why it exists:** Per-company configuration allows different brands or languages to use different templates.

#### `has_received_warning_stock_sms`
- **Type:** `Boolean`
- **L2:** One-time flag set per company after the SMS warning dialog has been shown once. Prevents the wizard from appearing on every subsequent picking validation.
- **Why it exists:** The `confirm.stock.sms` wizard is a "first-run" notice. Once the user is aware, the flag suppresses it permanently per company unless the module is uninstalled and reinstalled.

---

### L1/L2 — `res.config.settings` (stock_sms extension)

**File:** `models/res_config_settings.py`

#### `stock_sms_confirmation_template_id`
- **Type:** `Many2one('sms.template')` (related, `readonly=False`)
- **Related field:** `company_id.stock_sms_confirmation_template_id`
- **L2:** Exposes the company-level SMS template in the Inventory Settings form. The view makes it conditionally visible — only shown when `stock_confirmation_type == 'sms'` and `stock_text_confirmation` is checked.

---

### L1/L2 — `confirm.stock.sms` Wizard

**File:** `wizard/confirm_stock_sms.py`

#### `pick_ids`
- **Type:** `Many2many('stock.picking', 'stock_picking_sms_rel')`
- **L2:** Stores the picking IDs passed from `_action_generate_warn_sms_wizard`. Used in both `send_sms` and `dont_send_sms` to identify the companies involved and the pickings to validate.
- **Why Many2many:** The wizard can be triggered for multiple pickings at once (batch validation), so `pick_ids` must hold all of them.

---

### L1/L2 — SMS Template Data

**File:** `data/sms_data.xml` (noupdate=1)

**External ID:** `stock_sms.sms_template_data_stock_delivery`

| Property | Value |
|---|---|
| `model_id` | `stock.model_stock_picking` |
| `body` | Dynamic Jinja template string |

**Template body logic:**
```python
# Conceptual Jinja expansion
object.company_id.name + ': We are glad to inform you that your order n° '
+ object.origin + ' has been shipped.'
+ (' Your tracking reference is ' + object.carrier_tracking_ref + '.'
   if hasattr(object, 'carrier_tracking_ref') and object.carrier_tracking_ref else '')
```
- Falls back to omit `order n°` and `origin` if `object.origin` is falsy (e.g., internal transfers).
- Conditionally appends `carrier_tracking_ref` only when present — uses `hasattr` for forward-compatibility in case a stripped-down picking variant lacks the field.
- The template references `object.company_id.name` and `object.origin` directly; missing `origin` produces a shorter message but still valid output.

---

## Method Reference

### `stock.picking` — SMS Workflow (L3)

**File:** `models/stock_picking.py`, class `StockPicking`, `_inherit = 'stock.picking'`

#### `_pre_action_done_hook()` → `res`
- **Inherits from:** `stock` base model (same-named hook)
- **L3 flow:**
  1. Calls `super()._pre_action_done_hook()` — this is where `stock` performs its own validations (e.g., `button_validate` pre-checks).
  2. If the base returns anything other than `True` (e.g., a wizard for quantity shortage), that result is returned immediately without SMS processing.
  3. If base returns `True` **and** `skip_sms` is not in context, calls `_check_warn_sms()`.
  4. If any pickings pass `_check_warn_sms`, returns `_action_generate_warn_sms_wizard()` result — **blocks validation** until user responds to the dialog.
  5. Otherwise returns `res` (which is `True`), allowing validation to proceed.
- **L3:** The guard `res is True` ensures this code only runs when all stock-side preconditions are satisfied. An early return (e.g., quantity wizard) bypasses SMS entirely.

#### `_check_warn_sms()` → `warn_sms_pickings` (recordset)
- **L3 conditions (all must be True):**
  - `company_id._get_text_validation('sms')` — checks `stock_text_confirmation == True` AND `stock_confirmation_type == 'sms'` on the company
  - `picking_type_id.code == 'outgoing'` — only delivery pickings
  - `partner_id.phone` exists —必须有电话号码才能发送
  - `not modules.module.current_test` — skipped during unit tests
  - `not company_id.has_received_warning_stock_sms` — one-time dialog per company
- **L3:** Iterates pickings individually rather than filtering with a domain. This is O(n) but acceptable since batch picking validation is uncommon and the loop body is lightweight.
- **L4:** The `current_test` guard is critical — without it, any test calling `button_validate` on an outgoing picking with a phone-numbered partner would block waiting for wizard input.
- **Failure mode:** If `phone` is missing, the SMS is silently skipped (no error raised) and validation proceeds normally.

#### `_action_generate_warn_sms_wizard()` → `ir.actions.act_window`
- **L3:** Creates a single `confirm.stock.sms` wizard record containing all pickings in `self`. Returns a modal dialog action.
- **L4:** Uses `self.env.ref('stock_sms.view_confirm_stock_sms')` — will raise `ValueError` if the view XML is missing or the module is not fully loaded. This is a hard dependency on view ID resolution.

#### `_send_confirmation_email()` → `None` (overrides parent)
- **Inherits from:** `stock` base model (same-named method)
- **L3 flow:**
  1. Calls `super()._send_confirmation_email()` — sends the stock email confirmation (if configured)
  2. Checks `skip_sms` context and `current_test` guard
  3. Filters self to pickings where company has SMS text validation enabled, picking type is `outgoing`, and partner has a phone
  4. For each picking, calls `_message_sms_with_template(template=..., partner_ids=..., put_in_queue=False)`
- **L3:** Uses `sudo()` on the company and template because the active user performing the validation may not have permission to read the SMS template (ACL `access_sms_template_stock_manager` grants write only to `stock.group_stock_manager`).
- **L4 `put_in_queue=False`:** Forces synchronous delivery. This means `button_validate` will block until the SMS gateway returns or times out. If the SMS service (IAP) is slow or unreachable, validation will appear to hang. Consider if Odoo's async queue would be better for high-volume operations. This is a deliberate design choice for delivery confirmation to ensure the customer gets the SMS before the user moves to the next task.
- **Failure modes:** If the SMS template is deleted or unlinked, `_message_sms_with_template` will raise an error. If the partner has no phone, the picking is silently excluded from the loop.

---

### `confirm.stock.sms` Wizard Actions (L3)

**File:** `wizard/confirm_stock_sms.py`

#### `send_sms()` → `stock.picking.button_validate() result`
- **L3:** Sets `has_received_warning_stock_sms = True` on all unique companies from the wizard's pickings (using `sudo()`). Then calls `button_validate` for the pickings passed in the `button_validate_picking_ids` context key.
- **L4:** The context key `button_validate_picking_ids` is populated by the stock validation flow when it needs to defer to an intermediate wizard. If this context is missing, `browse()` returns an empty recordset and `button_validate` is called on nothing — the picking validation silently does nothing.

#### `dont_send_sms()` → `stock.picking.button_validate() result`
- **L3:** Same as `send_sms` but also sets `company_id.stock_text_confirmation = False` — this disables SMS confirmation globally for that company in one click.
- **L4:** The `stock_text_confirmation = False` write targets `res.company` directly, bypassing the `stock` module's `stock_confirmation_type` field. This is safe because `stock_confirmation_type` defaults to `'sms'`, so re-enabling SMS would require the user to set `stock_text_confirmation = True` again in settings.

---

### Hooks (L3)

**File:** `__init__.py`

#### Post-init hook: `_assign_default_sms_template_picking_id(env)`
- Runs on module install (or upgrade) via `post_init_hook`.
- Searches all `res.company` records that lack a `stock_sms_confirmation_template_id`.
- Sets `stock_text_confirmation = True` and assigns the external ID `stock_sms.sms_template_data_stock_delivery` as the default.
- **L4:** Safe to re-run on upgrade — only affects companies with no template assigned. The `raise_if_not_found=False` on `env.ref` means a missing template XML won't crash the module install.

#### Uninstall hook: `_reset_sms_text_confirmation(env)`
- Runs on module uninstall via `uninstall_hook`.
- Finds companies where `stock_text_confirmation == True` AND `stock_confirmation_type == 'sms'`.
- Sets `stock_text_confirmation = False`. Does **not** clear `stock_sms_confirmation_template_id` — the template assignment is preserved so re-installing restores the prior configuration.
- **L4:** Does not reset `has_received_warning_stock_sms`. Re-installing will show the wizard again even if the user previously dismissed it.

---

## Security

### ACL Entries (`security/ir.model.access.csv`)

| ID | Model | Group | Permissions |
|---|---|---|---|
| `access_sms_template_stock_manager` | `sms.model_sms_template` | `stock.group_stock_manager` | Read, Write, Create, Unlink |
| `access_confirm_stock_sms` | `model_confirm_stock_sms` | `stock.group_stock_user` | Read, Write, Create (no Unlink) |

**L3 analysis:**
- Stock **users** get read/write on `confirm.stock.sms` (needed to operate the wizard) but cannot unlink it.
- Stock **managers** additionally get full access on `sms.template` records scoped to `stock.picking`. This allows managers to customize the delivery SMS template from within Odoo.
- The `confirm.stock.sms` model is a `TransientModel` — in Odoo 17+, transient records are automatically cleaned up by the garbage collector and are **exempt from record rules** by default. The lack of an explicit `ir.rule` on this model is therefore correct and intentional.

### Record Rule (`security/sms_security.xml`)

**External ID:** `stock_sms.ir_rule_sms_template_stock_manager`

```python
domain_force: [('model_id.model', '=', 'stock.picking')]
perm_read: False
```

**L3 analysis:**
- Applies only to `stock.group_stock_manager`.
- `perm_read: False` means managers **cannot read** SMS templates they don't own through this rule — but since they have full access via the ACL, the read permission is granted by the ACL entry and the rule acts as a write-gate only.
- The rule restricts **write/create/unlink** operations to templates whose `model_id.model` equals `'stock.picking'`. This prevents stock managers from modifying unrelated SMS templates (e.g., `crm.lead` or `sale.order` templates) that may be owned by other departments.
- **L4 security consideration:** There is no company-level restriction. A manager in one company can write SMS templates for pickings in any company — this may be intentional (templates are often centrally managed) but is worth noting for multi-company deployments.

---

## Cross-Module Integration

### With `stock`

| Integration Point | Detail |
|---|---|
| `stock.picking` fields used | `picking_type_id.code`, `partner_id.phone`, `company_id`, `origin`, `carrier_tracking_ref` |
| `stock.res_company` fields | `stock_text_confirmation`, `stock_confirmation_type` (defined in `stock` base, read by `stock_sms`) |
| `_get_text_validation()` | Method on `res.company` in `stock`; `stock_sms` calls it to gate all SMS behaviour |
| `_send_confirmation_email()` | Method on `stock.picking`; `stock_sms` overrides to extend with SMS |
| `_pre_action_done_hook()` | Hook on `stock.picking`; `stock_sms` wraps it to inject the warning wizard |
| Settings form | `ResConfigSettings` inherits from `stock` settings form to add SMS template field |

### With `sms`

| Integration Point | Detail |
|---|---|
| `sms.template` model | Templates stored here; `stock_sms` creates one noupdate default |
| `_message_sms_with_template()` | Odoo framework method on `mail.thread`; `stock.picking` inherits this via `mail.thread` (through `stock.picking`'s model chain) |
| IAP SMS gateway | Handled entirely by the `sms` module; `stock_sms` only calls the template rendering method |
| SMS credits | IAP buy-more-credits widget shown in settings view when SMS type is selected |

### With `stock` Configuration Flow

```
Settings: Inventory > Enable "Stock Text Confirmation" + set type to "SMS"
    → sets res.company.stock_text_confirmation = True
    → onchange auto-enables module_stock_sms = True

Settings form: SMS template dropdown appears (ResConfigSettings view extension)
    → links res.company.stock_sms_confirmation_template_id

button_validate on outgoing picking:
    → _pre_action_done_hook()
        → _check_warn_sms() → if has_received_warning_stock_sms=False
            → _action_generate_warn_sms_wizard()
                → confirm.stock.sms wizard dialog
                    → send_sms() → button_validate()
                        → _send_confirmation_email()
                            → _message_sms_with_template()
    OR
    → _check_warn_sms() returned empty → res = True
        → button_validate() completes
            → _send_confirmation_email() (same SMS path)
```

---

## Performance Considerations

### Synchronous SMS Dispatch
- `put_in_queue=False` in `_message_sms_with_template` means the HTTP call to the IAP SMS endpoint blocks the request thread until delivery or timeout.
- For high-volume warehouses (100+ deliveries/day), this adds latency to each `button_validate` call. The `sms` module does support queued (async) sending, but `stock_sms` deliberately uses sync mode so the confirmation SMS is guaranteed delivered before the user proceeds.
- **Mitigation:** For high-volume operations, consider patching `_send_confirmation_email` to pass `put_in_queue=True` at the cost of eventual delivery guarantee.

### Wizard One-time Flag
- `has_received_warning_stock_sms` is a Boolean on `res.company`. Once set to `True`, it is never reset by normal operation (only on uninstall/reinstall cycle). This means the warning wizard appears **once per company over the module's lifetime** — no performance degradation over time.

### Iterative `_check_warn_sms`
- The loop over `self` (rather than a domain-based batch filter) is O(n) in Python but I/O-light. For most use cases (1-10 pickings at a time), this is negligible. For extreme batch operations with 1000+ pickings, a domain-based filter would be more efficient.

---

## Edge Cases

| Scenario | Behaviour |
|---|---|
| No phone on partner | Picking validates normally; SMS silently skipped (no error) |
| Partner has only `mobile` field | Since the check uses `partner_id.phone`, pickings with only a mobile number will not trigger SMS. This is a known gap — use case should extend the condition to check `phone` OR `mobile`. |
| SMS template deleted | `_message_sms_with_template` raises `ValueError`; validation fails with traceback |
| `skip_sms` in context | Both `_pre_action_done_hook` and `_send_confirmation_email` skip all SMS logic — used in automated tests and programmatic workflows |
| Unit test context (`current_test`) | Both methods bail out early — no wizard popup, no SMS attempt |
| Internal transfer picking (`internal`) | Silently skipped — only `outgoing` pickings trigger SMS |
| Multi-company, one company has SMS disabled | `_check_warn_sms` returns an empty recordset for that company; other company pickings in the same batch proceed normally |
| `carrier_tracking_ref` is empty string (`""`) | `hasattr` check passes but the empty string is falsy, so the `carrier_tracking_ref` clause is excluded from the message — message reads without the tracking reference portion |
| IAP SMS credits exhausted | `sms` module returns a failure response; `_message_sms_with_template` handles this gracefully (logs error, returns). Validation still completes. |

---

## Odoo 18 → Odoo 19 Changes

The `stock_sms` module is structurally identical between Odoo 18 and Odoo 19 — no breaking changes were introduced. The module's core behaviour (SMS on delivery validation) remains the same.

Notable consistent aspects:
- `auto_install: True` and `post_init_hook` mechanism preserved.
- `_pre_action_done_hook` and `_send_confirmation_email` override points remain the canonical extension mechanism.
- The `confirm.stock.sms` wizard transient model pattern is unchanged.

---

## Related Documentation
- [Modules/Stock](Modules/stock.md) — `stock.picking` base model, `button_validate` flow, `_pre_action_done_hook`, `_send_confirmation_email`
- [Modules/SMS](Modules/sms.md) — `sms.template`, `_message_sms_with_template`, IAP SMS gateway
- [Modules/res.partner](Modules/res.partner.md) — `partner_id.phone` field used for SMS recipient
- [Core/API](Core/API.md) — `@api.model`, `@api.onchange` decorators relevant to `ResConfigSettings`
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — ir.rule record rules, ACL CSV format, transient model security

---

## Tags
#odoo #odoo19 #modules #stock_sms #sms #workflow
