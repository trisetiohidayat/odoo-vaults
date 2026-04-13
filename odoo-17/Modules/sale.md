---
tags: [odoo, odoo17, module, sale]
research_depth: deep
---

# Sale Module — Deep Research

**Source:** `addons/sale/models/`

**Files in module:**
- `sale_order.py` (~1898 lines) — Core sale.order model
- `sale_order_line.py` (~1330 lines) — sale.order.line model
- `account_move.py` (~209 lines) — account.move extension for sale integration

---

## sale.order

**Class definition:** `SaleOrder(models.Model)` — Line 30
**Inherits:** `portal.mixin`, `product.catalog.mixin`, `mail.thread`, `mail.activity.mixin`, `utm.mixin`
**Model name:** `_name = 'sale.order'`
**Order:** `_order = 'date_order desc, id desc'`
**Company check:** `_check_company_auto = True`

### SQL Constraints

```python
# Line 37-41
_sql_constraints = [
    ('date_order_conditional_required',
     "CHECK((state = 'sale' AND date_order IS NOT NULL) OR state != 'sale')",
     "A confirmed sales order requires a confirmation date."),
]
```

---

### All Fields (complete)

| Field | Type | Line | Description |
|-------|------|------|-------------|
| `name` | Char | 51 | Order Reference — required, copy=False, trigram index, default "New" |
| `company_id` | Many2one(res.company) | 57 | Required, default from env.company |
| `partner_id` | Many2one(res.partner) | 61 | Customer — required, change_default, tracking=1 |
| `state` | Selection | 67 | Status — draft/sent/sale/cancel, default='draft', readonly, tracking=3 |
| `locked` | Boolean | 73 | Default False — locked orders cannot be modified |
| `client_order_ref` | Char | 75 | Customer Reference, copy=False |
| `create_date` | Datetime | 76 | Creation date (ORM override), readonly, index |
| `commitment_date` | Datetime | 78 | Promised delivery date (overrides lead time calculation) |
| `date_order` | Datetime | 83 | Order Date — required, default=Datetime.now, also confirmation date |
| `origin` | Char | 88 | Source document reference |
| `reference` | Char | 91 | Payment reference, copy=False |
| `require_signature` | Boolean | 96 | Online signature required — computed from company.portal_confirmation_sign |
| `require_payment` | Boolean | 101 | Online payment required — computed from company.portal_confirmation_pay |
| `prepayment_percent` | Float | 106 | Percent to prepay — computed from company.prepayment_percent |
| `signature` | Image | 112 | Customer signature (max 1024x1024, copy=False, attachment) |
| `signed_by` | Char | 115 | Name of signatory |
| `signed_on` | Datetime | 117 | Date/time of signature |
| `validity_date` | Date | 120 | Expiration date — computed from company.quotation_validity_days |
| `journal_id` | Many2one | 124 | Invoicing journal — computed (lowest sequence sale journal), optional override |
| `note` | Html | 132 | Terms and conditions — computed from company.invoice_terms |
| `partner_invoice_id` | Many2one(res.partner) | 137 | Invoice Address — computed from partner.address_get(['invoice']) |
| `partner_shipping_id` | Many2one(res.partner) | 144 | Delivery Address — computed from partner.address_get(['delivery']) |
| `fiscal_position_id` | Many2one | 152 | Fiscal Position — computed from partner+shipping, maps taxes |
| `payment_term_id` | Many2one | 160 | Payment Terms — computed from partner.property_payment_term_id |
| `pricelist_id` | Many2one | 166 | Pricelist — computed from partner.property_product_pricelist |
| `currency_id` | Many2one(res.currency) | 174 | Currency — computed from pricelist or company |
| `currency_rate` | Float | 181 | Currency rate — computed via _get_conversion_rate |
| `user_id` | Many2one(res.users) | 186 | Salesperson — computed from partner.user_id or commercial_partner_id.user_id |
| `team_id` | Many2one(crm.team) | 195 | Sales Team — computed via _get_default_team_id |
| `order_line` | One2many | 205 | Lines (`sale.order.line`), copy=True, auto_join=True |
| `amount_untaxed` | Monetary | 211 | Untaxed total — stored, computed via _compute_amounts |
| `amount_tax` | Monetary | 212 | Tax total — stored, computed via _compute_amounts |
| `amount_total` | Monetary | 213 | Grand total — stored, computed via _compute_amounts |
| `amount_to_invoice` | Monetary | 214 | Amount remaining to invoice — stored, computed |
| `amount_invoiced` | Monetary | 215 | Already invoiced amount — computed |
| `invoice_count` | Integer | 221 | Number of invoices — computed via _get_invoiced |
| `invoice_ids` | Many2many | 222 | Invoices — computed via _get_invoiced, searchable via _search_invoice_ids |
| `invoice_status` | Selection | 228 | Invoice status — stored, computed: upselling/invoiced/to invoice/no |
| `transaction_ids` | Many2many | 235 | Payment transactions — from sale_order_transaction_rel table |
| `authorized_transaction_ids` | Many2many | 240 | Authorized transactions — computed filter on state='authorized' |
| `amount_paid` | Float | 246 | Sum of authorized+done transaction amounts |
| `campaign_id` | Many2one(utm.campaign) | 249 | UTM campaign — ondelete='set null' |
| `medium_id` | Many2one(utm.medium) | 250 | UTM medium — ondelete='set null' |
| `source_id` | Many2one(utm.source) | 251 | UTM source — ondelete='set null' |
| `analytic_account_id` | Many2one | 254 | Analytic Account — copy=False |
| `tag_ids` | Many2many | 259 | CRM Tags |
| `amount_undiscounted` | Float | 265 | Amount before discount — computed |
| `country_code` | Char | 268 | Related company country code (readonly) |
| `expected_date` | Datetime | 269 | Promised delivery date (min lead time from lines) |
| `is_expired` | Boolean | 273 | True if draft/sent and validity_date < today |
| `partner_credit_warning` | Text | 274 | Credit limit warning message (computed) |
| `tax_calculation_rounding_method` | Selection | 276 | Related to company (readonly) |
| `tax_country_id` | Many2one(res.country) | 279 | Fiscal country for tax filtering — computed |
| `tax_totals` | Binary | 284 | JSON tax totals for frontend display |
| `terms_type` | Selection | 285 | Related company terms_type |
| `type_name` | Char | 286 | "Quotation" vs "Sales Order" — computed from state |
| `show_update_fpos` | Boolean | 290 | Flag: fiscal position changed (UX) |
| `has_active_pricelist` | Boolean | 292 | Flag: active pricelist exists (UX) |
| `show_update_pricelist` | Boolean | 294 | Flag: pricelist changed (UX) |

---

### All Methods (with line numbers)

| Method | Line | Description |
|--------|------|-------------|
| `init()` | 297 | Creates trigram index on `date_order desc, id desc` |
| `_compute_display_name()` | 303 | Display name with partner name if context `sale_show_partner_name` set |
| `_compute_require_signature()` | 313 | Computes from company.portal_confirmation_sign |
| `_compute_require_payment()` | 318 | Computes from company.portal_confirmation_pay |
| `_compute_prepayment_percent()` | 323 | Computes from company.prepayment_percent |
| `_compute_validity_date()` | 328 | Sets validity_date = today + quotation_validity_days |
| `_compute_journal_id()` | 338 | Sets journal_id = False (overridden per invoice) |
| `_compute_note()` | 341 | Loads invoice terms from company (HTML or plain) |
| `_get_note_url()` | 359 | Returns base URL for terms page |
| `_compute_partner_invoice_id()` | 362 | partner_id.address_get(['invoice')['invoice'] |
| `_compute_partner_shipping_id()` | 367 | partner_id.address_get(['delivery'])['delivery'] |
| `_compute_fiscal_position_id()` | 372 | Maps taxes via fiscal position for partner+shipping address |
| `_compute_payment_term_id()` | 392 | partner_id.property_payment_term_id |
| `_compute_pricelist_id()` | 398 | partner_id.property_product_pricelist (only for state='draft') |
| `_compute_currency_id()` | 409 | From pricelist.currency_id or company.currency_id |
| `_compute_currency_rate()` | 414 | Via res.currency._get_conversion_rate |
| `_compute_has_active_pricelist()` | 424 | True if any active pricelist exists |
| `_compute_user_id()` | 432 | From partner.user_id or commercial_partner_id.user_id or current user |
| `_compute_team_id()` | 445 | Uses crm.team._get_default_team_id with caching |
| `_compute_amounts()` | 468 | Computes amount_untaxed, amount_tax, amount_total (round_globally aware) |
| `_get_invoiced()` | 491 | Computes invoice_ids + invoice_count from order_line.invoice_lines |
| `_search_invoice_ids()` | 502 | Searchable inverse of invoice_ids (handles `= False` edge case) |
| `_compute_invoice_status()` | 538 | Aggregates line-level invoice_status to order level |
| `_compute_authorized_transaction_ids()` | 586 | Filters transaction_ids on state='authorized' |
| `_compute_amount_paid()` | 591 | Sum of amounts from authorized+done transactions |
| `_compute_amount_undiscounted()` | 599 | price_subtotal * 100/(100-discount), handles 100% discount |
| `_compute_expected_date()` | 606 | Min of line._expected_date() across non-delivery, non-display lines |
| `_select_expected_date()` | 624 | Returns min(expected_dates) |
| `_compute_is_expired()` | 628 | True if draft/sent and validity_date < today |
| `_compute_tax_country_id()` | 637 | fiscal_position_id.foreign_vat country else company.account_fiscal_country_id |
| `_compute_amount_to_invoice()` | 645 | amount_total minus sum of posted invoice amounts |
| `_compute_amount_invoiced()` | 659 | amount_total minus amount_to_invoice |
| `_compute_partner_credit_warning()` | 664 | Builds credit warning message from account.move._build_credit_warning_message |
| `_compute_tax_totals()` | 677 | Prepares tax totals JSON via account.tax._prepare_tax_totals |
| `_compute_type_name()` | 688 | "Quotation" for draft/sent/cancel; "Sales Order" otherwise |
| `_compute_access_url()` | 697 | Sets access_url = /my/orders/{id} |
| `_check_order_line_company_id()` | 704 | Constraint: products cannot belong to companies outside order's accessible branches |
| `_check_prepayment_percent()` | 721 | Constraint: require_payment implies 0 < prepayment_percent <= 1.0 |
| `onchange()` | 729 | Overrides to set sale_onchange_first_call and res_partner_search_mode context |
| `_onchange_commitment_date()` | 740 | Warning if commitment_date < expected_date |
| `_onchange_company_id_warning()` | 752 | Warning when changing company on draft SO with lines |
| `_onchange_fpos_id_show_update_fpos()` | 767 | Sets show_update_fpos=True when fiscal position changes |
| `_onchange_partner_id_warning()` | 775 | Shows partner sale warnings (block/no-message) |
| `_onchange_pricelist_id_show_update_prices()` | 801 | Sets show_update_pricelist=True if order_line exists |
| `_onchange_prepayment_percent()` | 805 | Disables require_payment if prepayment_percent cleared |
| `create()` | 812 | Creates sequence number using ir.sequence (sale.order) |
| `copy_data()` | 826 | Copies lines, skipping is_downpayment lines |
| `write()` | 836 | Raises UserError if pricelist changed on confirmed order |
| `_unlink_except_draft_or_cancel()` | 841 | Only draft/cancel orders can be deleted |
| `action_open_discount_wizard()` | 851 | Opens sale.order.discount wizard |
| `action_draft()` | 861 | Resets state to draft, clears signature |
| `action_quotation_send()` | 870 | Opens mail composer with sale template |
| `_find_mail_template()` | 899 | Returns edi template or confirmation template based on state |
| `_get_mail_template()` | 907 | Returns confirmation email template (sale vs proforma) |
| `_get_confirmation_template()` | 914 | Returns default confirmation template or mail_template_sale_confirmation |
| `action_quotation_sent()` | 930 | Sets state to 'sent', subscribes partner |
| `action_confirm()` | 943 | Main confirmation method — validates, writes state, locks |
| `_should_be_locked()` | 983 | Returns True if create_uid has group sale.group_auto_done_setting |
| `_can_be_confirmed()` | 988 | Returns True if state in {'draft', 'sent'} |
| `_prepare_confirmation_values()` | 992 | Returns {state: 'sale', date_order: now} |
| `_action_confirm()` | 1005 | Creates analytic account if expense products exist |
| `_send_order_confirmation_mail()` | 1016 | Sends sale confirmation email |
| `_send_payment_succeeded_for_order_mail()` | 1025 | Sends payment executed email |
| `_send_order_notification_mail()` | 1036 | Core send-mail-via-template helper |
| `action_lock()` | 1059 | Sets self.locked = True |
| `action_unlock()` | 1062 | Sets self.locked = False |
| `action_cancel()` | 1065 | Cancels draft invoices, shows cancel wizard if non-draft |
| `_action_cancel()` | 1103 | Cancels draft invoices, sets state='cancel' |
| `_show_cancel_wizard()` | 1108 | Returns True if any non-draft SO in self |
| `action_preview_sale_order()` | 1118 | Opens portal URL |
| `action_update_taxes()` | 1126 | Recomputes taxes via _recompute_taxes, posts message |
| `_recompute_taxes()` | 1136 | Calls line._compute_tax_id(), sets show_update_fpos=False |
| `action_update_prices()` | 1141 | Recomputes prices via _recompute_prices, posts message |
| `_recompute_prices()` | 1153 | Resets discount, recomputes price_unit and discount |
| `_default_order_line_values()` | 1164 | Merges product catalog defaults |
| `_get_action_add_from_catalog_extra_context()` | 1169 | Adds currency_id and price digits to catalog context |
| `_get_product_catalog_domain()` | 1176 | Filters to sale_ok=True products |
| `_prepare_invoice()` | 1181 | Returns dict of invoice values |
| `action_view_invoice()` | 1214 | Opens invoice list/form action |
| `_get_invoice_grouping_keys()` | 1243 | Returns ['company_id', 'partner_id', 'currency_id', 'fiscal_position_id'] |
| `_nothing_to_invoice_error_message()` | 1246 | Returns user-facing error message |
| `_get_update_prices_lines()` | 1257 | Returns order lines filtered to non-display_type |
| `_get_invoiceable_lines()` | 1261 | Returns lines with qty_to_invoice != 0 (groups downpayments separately) |
| `_create_account_invoices()` | 1288 | Creates account.move records (sudo) |
| `_create_invoices()` | 1294 | Main invoice creation method — groups, sequences, handles downpayments, refunds |
| `_track_finalize()` | 1484 | Skips tracking for draft orders if config param unset |
| `message_post()` | 1496 | Auto-sets state to 'sent' if mark_so_as_sent context |
| `_notify_get_recipients_groups()` | 1505 | Customizes portal button title based on state/payment |
| `_notify_by_email_prepare_rendering_context()` | 1542 | Adds amount and expiry subtitle |
| `_phone_get_number_fields()` | 1566 | Returns [] (no phone fields on sale.order) |
| `_track_subtype()` | 1571 | Returns mt_order_confirmed/sent events |
| `_force_lines_to_invoice_policy_order()` | 1581 | Sets qty_to_invoice = product_uom_qty - qty_invoiced (for auto-pay invoice) |
| `payment_action_capture()` | 1593 | Calls transaction_ids.sudo().action_capture() |
| `payment_action_void()` | 1601 | Calls authorized_transaction_ids.sudo().action_void() |
| `get_portal_last_transaction()` | 1608 | Returns last transaction via _get_last() |
| `_get_order_lines_to_report()` | 1612 | Filters downpayment lines for report based on state |
| `_get_default_payment_link_values()` | 1631 | Computes payment link amount |
| `_has_to_be_signed()` | 1659 | True if draft/sent, not expired, require_signature, no signature |
| `_has_to_be_paid()` | 1679 | True if draft/sent, not expired, require_payment, not done, amount>0, confirmation not reached |
| `_get_portal_return_action()` | 1702 | Returns action for portal back navigation |
| `_get_name_portal_content_view()` | 1707 | Returns sale_order_portal_content view |
| `_get_name_tax_totals_view()` | 1712 | Returns document_tax_totals view |
| `_get_report_base_filename()` | 1716 | Returns "{type_name} {name}" |
| `get_empty_list_help()` | 1723 | Provides empty list help message |
| `_compute_field_value()` | 1729 | On invoice_status change to 'upselling': schedules upsell activity |
| `_create_upsell_activity()` | 1744 | Schedules sale.mail_act_sale_upsell activity |
| `_prepare_analytic_account_data()` | 1757 | Returns analytic account creation dict |
| `_create_analytic_account()` | 1781 | Creates account.analytic.account for order |
| `_prepare_down_payment_section_line()` | 1792 | Returns section line values for invoice down payment |
| `_get_prepayment_required_amount()` | 1815 | Returns amount_total * prepayment_percent (or full amount) |
| `_is_confirmation_amount_reached()` | 1829 | Compares amount_paid vs prepayment required |
| `_generate_downpayment_invoices()` | 1843 | Creates down payment invoice from amount_paid |
| `_get_product_catalog_order_data()` | 1861 | Returns product prices from pricelist |
| `_get_product_catalog_record_lines()` | 1878 | Groups existing lines by product_id |
| `_get_product_documents()` | 1886 | Returns product documents attached to order lines |
| `_filter_product_documents()` | 1895 | Filters documents by attached_on criteria |

---

### action_confirm() — Full Implementation (Lines 943–981)

```python
def action_confirm(self):
    """ Confirm the given quotation(s) and set their confirmation date.

    If the corresponding setting is enabled, also locks the Sale Order.

    :return: True
    :rtype: bool
    :raise: UserError if trying to confirm cancelled SO's
    """
    if not all(order._can_be_confirmed() for order in self):
        raise UserError(_(
            "The following orders are not in a state requiring confirmation: %s",
            ", ".join(self.mapped('display_name')),
        ))

    self.order_line._validate_analytic_distribution()       # (1) Validate analytic distribution

    for order in self:
        order.validate_taxes_on_sales_order()                # (2) Validate taxes on each order
        if order.partner_id in order.message_partner_ids:
            continue
        order.message_subscribe([order.partner_id.id])      # (3) Subscribe partner to chatter

    self.write(self._prepare_confirmation_values())         # (4) Write state='sale', date_order=now

    context = self._context.copy()
    context.pop('default_name', None)
    context.pop('default_user_id', None)

    self.with_context(context)._action_confirm()            # (5) Run _action_confirm hook

    self.filtered(lambda so: so._should_be_locked()).action_lock()  # (6) Lock if setting enabled

    if self.env.context.get('send_email'):
        self._send_order_confirmation_mail()                # (7) Optionally send confirmation email

    return True
```

**Step-by-step breakdown:**
1. `if not all(order._can_be_confirmed() for order in self)` — raises if any order is not in draft/sent state (cancelled orders cannot be confirmed)
2. `self.order_line._validate_analytic_distribution()` — calls each line's analytic distribution validator
3. `order.validate_taxes_on_sales_order()` — Odoo standard tax validation (from account)
4. `order.message_subscribe([order.partner_id.id])` — adds customer as follower (unless already subscribed)
5. `self.write(self._prepare_confirmation_values())` — sets `state='sale'` and `date_order=fields.Datetime.now()`
6. `self.with_context(context)._action_confirm()` — runs the hook for submodules (creates analytic account for expense products)
7. `self.filtered(...).action_lock()` — locks the SO if the `sale.group_auto_done_setting` group is set on the order creator. Locking sets `locked=True`.
8. Optionally sends email via `_send_order_confirmation_mail()`

---

### _action_confirm() — Implementation (Lines 1005–1014)

```python
def _action_confirm(self):
    """ Implementation of additional mechanism of Sales Order confirmation.
        This method should be extended when the confirmation should generate
        other documents. In this method, the SO are in 'sale' state (not yet 'done').
    """
    # create an analytic account if at least an expense product
    for order in self:
        if any(expense_policy not in [False, 'no']
               for expense_policy in order.order_line.product_id.mapped('expense_policy')):
            if not order.analytic_account_id:
                order._create_analytic_account()
```

This hook is designed to be overridden. In the base module, it creates an analytic account if any line has `expense_policy` set to 'cost' or 'sales_team' (i.e., the product is an expense product). The actual procurement and stock picking creation happens in `sale_stock` module via this hook.

---

### action_cancel() — Full Implementation (Lines 1065–1101)

```python
def action_cancel(self):
    """ Cancel SO after showing the cancel wizard when needed.

    For post-cancel operations, please only override :meth:`_action_cancel`.
    """
    if any(order.locked for order in self):
        raise UserError(_("You cannot cancel a locked order. Please unlock it first."))
    cancel_warning = self._show_cancel_wizard()              # (1) Check if wizard needed
    if cancel_warning:
        self.ensure_one()
        template_id = self.env['ir.model.data']._xmlid_to_res_id(
            'sale.mail_template_sale_cancellation', raise_if_not_found=False)
        ctx = {
            'default_template_id': template_id,
            'default_order_id': self.id,
            'mark_so_as_canceled': True,
            'default_email_layout_xmlid': "mail.mail_notification_layout_with_responsible_signature",
            'model_description': self.with_context(lang=lang).type_name,
        }
        return {
            'name': _('Cancel %s', self.type_name),
            'view_mode': 'form',
            'res_model': 'sale.order.cancel',
            'view_id': self.env.ref('sale.sale_order_cancel_view_form').id,
            'type': 'ir.actions.act_window',
            'context': ctx,
            'target': 'new'
        }
    else:
        return self._action_cancel()                         # (2) Direct cancel for drafts

def _action_cancel(self):
    inv = self.invoice_ids.filtered(lambda inv: inv.state == 'draft')  # (3) Cancel draft invoices
    inv.button_cancel()
    return self.write({'state': 'cancel'})                  # (4) Set state to cancel

def _show_cancel_wizard(self):
    """ Returns True if any order in self is non-draft (i.e., sent or confirmed). """
    if self.env.context.get('disable_cancel_warning'):
        return False
    return any(so.state != 'draft' for so in self)
```

**Key behavior:**
- Cannot cancel locked orders (must unlock first)
- Draft orders: direct `_action_cancel()` — no wizard
- Non-draft orders: shows `sale.order.cancel` wizard (sends cancellation email, then cancels)
- `_action_cancel()` cancels any draft invoices before setting state='cancel'

---

### _prepare_invoice() — Invoice Generation (Lines 1181–1212)

```python
def _prepare_invoice(self):
    """ Prepare the dict of values to create the new invoice for a sales order. """
    self.ensure_one()

    values = {
        'ref': self.client_order_ref or '',
        'move_type': 'out_invoice',
        'narration': self.note,
        'currency_id': self.currency_id.id,
        'campaign_id': self.campaign_id.id,
        'medium_id': self.medium_id.id,
        'source_id': self.source_id.id,
        'team_id': self.team_id.id,
        'partner_id': self.partner_invoice_id.id,
        'partner_shipping_id': self.partner_shipping_id.id,
        'fiscal_position_id': (self.fiscal_position_id or
            self.fiscal_position_id._get_fiscal_position(self.partner_invoice_id)).id,
        'invoice_origin': self.name,
        'invoice_payment_term_id': self.payment_term_id.id,
        'invoice_user_id': self.user_id.id,
        'payment_reference': self.reference,
        'transaction_ids': [Command.set(self.transaction_ids.ids)],
        'company_id': self.company_id.id,
        'invoice_line_ids': [],
        'user_id': self.user_id.id,
    }
    if self.journal_id:
        values['journal_id'] = self.journal_id.id
    return values
```

**Key observations:**
- `move_type` is always `out_invoice` (customer invoice)
- `partner_id` is `partner_invoice_id` (not partner_id directly)
- `fiscal_position_id` is resolved if not set
- `transaction_ids` are linked so payments auto-match invoices
- `invoice_origin` holds the SO name
- If `journal_id` is set, it's included; otherwise account uses lowest-sequence sale journal

---

### Lock Mechanism (Lines 73, 983–986, 1059–1063, 1034–1049)

```python
# Field definition (line 73)
locked = fields.Boolean(default=False, copy=False,
    help="Locked orders cannot be modified.")

# Locking decision (line 983)
def _should_be_locked(self):
    self.ensure_one()
    # Public user can confirm SO, so we check the group on any record creator.
    return self.create_uid.has_group('sale.group_auto_done_setting')

# Called at end of action_confirm (line 976)
self.filtered(lambda so: so._should_be_locked()).action_lock()

# Lock toggle methods (lines 1059-1063)
def action_lock(self):
    self.locked = True

def action_unlock(self):
    self.locked = False

# Write protection (lines 1034-1049 in sale_order_line.py write())
if any(self.order_id.mapped('locked')) and any(f in values.keys() for f in protected_fields):
    protected_fields_modified = list(set(protected_fields) & set(values.keys()))
    if 'name' in protected_fields_modified and all(self.mapped('is_downpayment')):
        protected_fields_modified.remove('name')
    fields = self.env['ir.model.fields'].sudo().search([
        ('name', 'in', protected_fields_modified), ('model', '=', self._name)
    ])
    if fields:
        raise UserError(_('It is forbidden to modify the following fields in a locked order:\n%s',
                          '\n'.join(fields.mapped('field_description'))))

# Protected fields (line 1059)
def _get_protected_fields(self):
    return ['product_id', 'name', 'price_unit', 'product_uom', 'product_uom_qty',
            'tax_id', 'analytic_distribution']
```

**Key behavior:**
- Auto-lock happens at confirmation time IF `sale.group_auto_done_setting` is assigned to the order creator (create_uid)
- Manual lock/unlock via `action_lock()` / `action_unlock()` buttons
- Locked SO: blocks writes to `product_id`, `name`, `price_unit`, `product_uom`, `product_uom_qty`, `tax_id`, `analytic_distribution`
- Exception: `name` field can be edited on locked SO if the line is a downpayment line
- action_cancel() refuses to run on locked orders

---

### Sale Order States

```
draft → sent → sale → done
              ↘ cancel
```

| State | Label | Trigger | Behavior |
|-------|-------|---------|----------|
| `draft` | Quotation | Creation, `action_draft()` | Editable, not invoiceable, not locked |
| `sent` | Quotation Sent | email sent, `action_quotation_sent()`, `action_quotation_send()` | Can be confirmed, editable |
| `sale` | Sales Order | `action_confirm()` | Locked if auto-lock setting, invoicing enabled |
| `done` | Locked | `action_done()` button (sale_management) | Read-only, no further changes |
| `cancel` | Cancelled | `action_cancel()` | No further action possible |

**State selection (line 22-27):**
```python
SALE_ORDER_STATE = [
    ('draft', "Quotation"),
    ('sent', "Quotation Sent"),
    ('sale', "Sales Order"),
    ('cancel', "Cancelled"),
]
```
Note: `done` state is not in sale.py itself — it is added by `sale_management` module via `_auto_done()`.

---

### Picking Generation

**Note:** Picking generation does NOT happen in `sale/models/sale_order.py` itself. The base `sale` module does NOT create pickings on confirmation.

The `_action_confirm()` method is a hook (lines 1005–1014):
```python
def _action_confirm(self):
    """ This method should be extended when the confirmation should
        generated other documents. """
    # only creates analytic account for expense products
    for order in self:
        if any(expense_policy not in [False, 'no'] ...):
            if not order.analytic_account_id:
                order._create_analytic_account()
```

**In `sale_stock` module (addons/sale_stock/models/sale_order.py):**
The `_action_confirm()` is overridden to create stock.picking via procurement group:
1. Creates `procurement.group` for the order
2. Calls `sol._launch_stock_rule()` for each line
3. Each line creates a stock.picking (type: OUT) linked to the group
4. Picking is linked back via `move.group_id` and `picking.group_id`

**In `sale` base module:** No picking is created. This is the critical architectural split between base sale and sale_stock.

---

### Invoice Status (Lines 15–20, 228–232)

```python
INVOICE_STATUS = [
    ('upselling', 'Upselling Opportunity'),
    ('invoiced', 'Fully Invoiced'),
    ('to invoice', 'To Invoice'),
    ('no', 'Nothing to Invoice')
]
```

**Computation logic (`_compute_invoice_status`, lines 538–584):**
- Only confirmed orders (state='sale') get meaningful status
- Line-level status bubbles up: if ANY line is 'to invoice', whole SO is 'to invoice'
- Special case: if only discount/delivery/promotion lines can be invoiced (not regular product lines), SO is 'no'
- If all lines are 'invoiced': status is 'invoiced'
- If all lines are 'invoiced' or 'upselling': status is 'upselling'
- Otherwise: 'no'

**On `action_confirm()` confirmation:**
The `_create_invoices()` method (line 1294) groups invoices by default grouping keys and creates invoices. Down payment lines are placed in a dedicated section at the end of the invoice.

**Invoice grouping keys (line 1243):**
```python
def _get_invoice_grouping_keys(self):
    return ['company_id', 'partner_id', 'currency_id', 'fiscal_position_id']
```

---

### _create_invoices() — Main Invoice Creation Logic (Lines 1294–1480)

The full invoice creation process:

1. **Check access** — verify user can create invoices (line 1305)
2. **Prepare per-order invoice vals** — call `_prepare_invoice()` (line 1320)
3. **Get invoiceable lines** — call `_get_invoiceable_lines(final)` (line 1321)
4. **Build invoice line vals** — call `line._prepare_invoice_line()` (line 1341)
5. **Handle down payment section** — create a section note line if downpayment lines exist (lines 1329–1338)
6. **Group invoices** — by grouping keys (lines 1353–1381)
7. **Resquence** — if fewer invoices than orders, renumber sequences (lines 1403–1409)
8. **Create moves** — call `_create_account_invoices()` (line 1411)
9. **Handle refunds** — convert negative-total moves to refunds (lines 1413–1419)
10. **Rounding correction** — adjust down payment rounding delta across invoice lines (lines 1421–1473)
11. **Post notification** — post mail.message_origin_link message (lines 1475–1479)

---

### _get_invoiceable_lines() — Logic (Lines 1261–1286)

```python
def _get_invoiceable_lines(self, final=False):
    """Return the invoiceable lines for order `self`."""
    down_payment_line_ids = []
    invoiceable_line_ids = []
    pending_section = None
    precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

    for line in self.order_line:
        if line.display_type == 'line_section':
            pending_section = line  # carry section forward
            continue
        if line.display_type != 'line_note' and float_is_zero(line.qty_to_invoice, precision_digits=precision):
            continue  # nothing to invoice
        if line.qty_to_invoice > 0 or (line.qty_to_invoice < 0 and final) or line.display_type == 'line_note':
            if line.is_downpayment:
                down_payment_line_ids.append(line.id)  # collect separately
                continue
            if pending_section:
                invoiceable_line_ids.append(pending_section.id)
                pending_section = None
            invoiceable_line_ids.append(line.id)

    return self.env['sale.order.line'].browse(invoiceable_line_ids + down_payment_line_ids)
```

Key: down payment lines are always placed at the end of the invoice (after regular lines), under their own section.

---

## sale.order.line

**Class definition:** `SaleOrderLine(models.Model)` — Line 14
**Inherits:** `analytic.mixin`
**Model name:** `_name = 'sale.order.line'`
**Order:** `_order = 'order_id, sequence, id'`

### SQL Constraints

```python
# Lines 22-29
('accountable_required_fields',
    "CHECK(display_type IS NOT NULL OR (product_id IS NOT NULL AND product_uom IS NOT NULL))",
    "Missing required fields on accountable sale order line.")
('non_accountable_null_fields',
    "CHECK(display_type IS NULL OR (product_id IS NULL AND price_unit = 0 AND product_uom_qty = 0 AND product_uom IS NULL AND customer_lead = 0))",
    "Forbidden values on non-accountable sale order line")
```

---

### All Fields (complete)

| Field | Type | Line | Description |
|-------|------|------|-------------|
| `order_id` | Many2one | 36 | Parent sale.order, required, ondelete='cascade' |
| `sequence` | Integer | 40 | Line order, default=10 |
| `company_id` | Many2one | 43 | Related order.company_id (stored, precompute) |
| `currency_id` | Many2one | 46 | Related order.currency_id (stored, precompute) |
| `order_partner_id` | Many2one | 50 | Related order.partner_id (stored, precompute) |
| `salesman_id` | Many2one | 54 | Related order.user_id (stored, precompute) |
| `state` | Selection | 58 | Related order.state (stored, precompute) |
| `tax_country_id` | Many2one | 62 | Related order.tax_country_id |
| `display_type` | Selection | 65 | line_section/line_note or False (for UI sections) |
| `is_downpayment` | Boolean | 71 | Flag: down payment line (not copied on duplicate) |
| `is_expense` | Boolean | 75 | Flag: line from expense/vendor bill |
| `product_id` | Many2one | 80 | product.product (domain: sale_ok=True) |
| `product_template_id` | Many2one | 85 | product.template (for configurator, NOT related to product_id) |
| `product_uom_category_id` | Many2one | 95 | Related product.uom_id.category_id |
| `product_custom_attribute_value_ids` | One2many | 97 | Custom attribute values from product configurator |
| `product_no_variant_attribute_value_ids` | Many2many | 104 | Attribute values that don't create variants (for description) |
| `name` | Text | 110 | Line description — computed from product (stored, editable) |
| `product_uom_qty` | Float | 115 | Ordered quantity (stored, computed from packaging) |
| `product_uom` | Many2one | 120 | Unit of measure (computed from product, editable) |
| `tax_id` | Many2many | 128 | Taxes (computed from product.supplier_taxes_id + fiscal position) |
| `pricelist_item_id` | Many2one | 137 | Cached pricelist rule used for pricing |
| `price_unit` | Float | 141 | Unit price (computed from pricelist, stored, editable) |
| `discount` | Float | 147 | Discount percentage (computed from pricelist, stored, editable) |
| `price_subtotal` | Monetary | 153 | Untaxed amount (computed, stored) |
| `price_tax` | Float | 157 | Tax amount (computed, stored) |
| `price_total` | Monetary | 161 | Taxed amount (computed, stored) |
| `price_reduce_taxexcl` | Monetary | 165 | price_subtotal / product_uom_qty |
| `price_reduce_taxinc` | Monetary | 169 | price_total / product_uom_qty |
| `product_packaging_id` | Many2one | 175 | Packaging (domain: sales=True, product_id match) |
| `product_packaging_qty` | Float | 182 | Packaging quantity (computed from packaging) |
| `customer_lead` | Float | 187 | Lead time in days (computed: 0 in base sale) |
| `qty_delivered_method` | Selection | 193 | 'manual' or 'analytic' — determines qty_delivered source |
| `qty_delivered` | Float | 206 | Quantity shipped/delivered |
| `qty_invoiced` | Float | 214 | Quantity invoiced (computed) |
| `qty_to_invoice` | Float | 219 | Quantity remaining to invoice (computed) |
| `analytic_line_ids` | One2many | 225 | Analytic lines linked to this SOL |
| `invoice_lines` | Many2many | 229 | account.move.line records linked to this SOL |
| `invoice_status` | Selection | 234 | per-line invoice status |
| `untaxed_amount_invoiced` | Monetary | 245 | Computed sum of posted invoice/refund line subtotals |
| `untaxed_amount_to_invoice` | Monetary | 249 | Remaining untaxed amount to invoice |
| `product_type` | Selection | 255 | Related product.detailed_type (readonly) |
| `product_updatable` | Boolean | 256 | Can edit product? Computed from state/qty_invoiced/qty_delivered/lock |
| `product_uom_readonly` | Boolean | 259 | Can edit UoM? True if saved and state in sale/cancel |
| `tax_calculation_rounding_method` | Selection | 261 | Related company setting (readonly) |

---

### product_id change effects (product_id_change equivalent)

There is no single `product_id_change` method. Instead, Odoo 17 uses computed fields that update automatically when `product_id` changes. The cascade:

| Computed Field | Depends | What happens |
|---------------|---------|-------------|
| `product_template_id` (278) | product_id | Sets to product_id.product_tmpl_id |
| `name` (313) | product_id | Calls `_get_sale_order_line_multiline_description_sale()` |
| `product_uom` (413) | product_id | Sets to product_id.uom_id (if not set or differs) |
| `tax_id` (419) | product_id, company_id | Maps product.taxes_id via fiscal position |
| `pricelist_item_id` (449) | product_id, product_uom, product_uom_qty | Finds matching pricelist rule |
| `price_unit` (462) | product_id, product_uom, product_uom_qty | Computes from pricelist rule |
| `discount` (572) | product_id, pricelist_id | Computes discount vs list price |
| `product_packaging_id` (652) | product_id, product_qty, product_uom | Finds suitable packaging |
| `customer_lead` (676) | (none in base) | Sets to 0.0 |
| `custom_attribute_value_ids` (286) | product_id | Removes invalid custom values |
| `no_variant_attribute_value_ids` (299) | product_id | Removes invalid no-variant attributes |

**Warning display:** `_onchange_product_id_warning()` (line 956) — shows `sale_line_warn` / `sale_line_warn_msg` from product if set to block/no-message.

---

### _prepare_invoice_line() — Invoice Line Values (Lines 1145–1170)

```python
def _prepare_invoice_line(self, **optional_values):
    """Prepare the values to create the new invoice line for a sales order line.

    :param optional_values: any parameter that should be added to the returned invoice line
    :rtype: dict
    """
    self.ensure_one()
    res = {
        'display_type': self.display_type or 'product',
        'sequence': self.sequence,
        'name': self.name,
        'product_id': self.product_id.id,
        'product_uom_id': self.product_uom.id,
        'quantity': self.qty_to_invoice,
        'discount': self.discount,
        'price_unit': self.price_unit,
        'tax_ids': [Command.set(self.tax_id.ids)],
        'sale_line_ids': [Command.link(self.id)],
        'is_downpayment': self.is_downpayment,
    }
    self._set_analytic_distribution(res, **optional_values)
    if optional_values:
        res.update(optional_values)
    if self.display_type:
        res['account_id'] = False
    return res
```

Key: `quantity` is `qty_to_invoice` (not `product_uom_qty`), `sale_line_ids` links back to this SOL, `is_downpayment` propagates to invoice line.

---

### _set_analytic_distribution() (Lines 1172–1181)

```python
def _set_analytic_distribution(self, inv_line_vals, **optional_values):
    analytic_account_id = self.order_id.analytic_account_id.id
    if self.analytic_distribution and not self.display_type:
        inv_line_vals['analytic_distribution'] = self.analytic_distribution
    if analytic_account_id and not self.display_type:
        analytic_account_id = str(analytic_account_id)
        if 'analytic_distribution' in inv_line_vals:
            inv_line_vals['analytic_distribution'][analytic_account_id] = \
                inv_line_vals['analytic_distribution'].get(analytic_account_id, 0) + 100
        else:
            inv_line_vals['analytic_distribution'] = {analytic_account_id: 100}
```

Two sources of analytic distribution:
1. Line-level distribution (e.g., from analytic distribution model)
2. Order-level analytic_account_id

If both are set, percentages are added (not overwritten).

---

### Key Line Methods

| Method | Line | Description |
|--------|------|-------------|
| `_compute_name()` | 313 | Generates name from product + custom attributes + downpayment state |
| `_get_sale_order_line_multiline_description_sale()` | 343 | Returns product.get_product_multiline_description_sale() + variant attrs |
| `_compute_product_uom_qty()` | 397 | Computes from packaging if packaging is set |
| `_compute_product_uom()` | 413 | Sets from product.uom_id if not set or different |
| `_compute_tax_id()` | 419 | Maps product.taxes_id via fiscal position with caching |
| `_compute_pricelist_item_id()` | 449 | Finds matching pricelist rule |
| `_compute_price_unit()` | 462 | Gets price from pricelist (skips if qty_invoiced > 0) |
| `_get_display_price()` | 490 | Returns pricelist price (honors discount_policy) |
| `_get_pricelist_price()` | 515 | Calls pricelist_item_id._compute_price() |
| `_compute_discount()` | 572 | Computes discount % vs base price (only if discount_policy='without_discount') |
| `_compute_amount()` | 623 | Computes price_subtotal, price_tax, price_total |
| `_compute_qty_delivered_method()` | 679 | Sets 'analytic' for is_expense, 'manual' otherwise |
| `_compute_qty_delivered()` | 695 | From analytic lines (expense) or manual |
| `_get_delivered_quantity_by_analytic()` | 729 | Groups AAL by so_line, converts UoM |
| `_compute_qty_invoiced()` | 763 | Sums invoice/refund quantities |
| `_compute_qty_to_invoice()` | 791 | qty_delivered OR product_uom_qty minus qty_invoiced based on invoice_policy |
| `_compute_invoice_status()` | 806 | Sets to to invoice/invoiced/upselling/no |
| `_compute_untaxed_amount_invoiced()` | 851 | Sums posted invoice/refund price_subtotal |
| `_compute_untaxed_amount_to_invoice()` | 871 | Computes remaining untaxed amount |
| `_compute_analytic_distribution()` | 919 | From account.analytic.distribution.model |
| `_compute_product_updatable()` | 932 | False if cancelled or locked or partially processed |
| `_onchange_product_id_warning()` | 956 | Shows product sale warnings |
| `_onchange_product_packaging_id()` | 973 | Warns if qty doesn't match packaging |
| `create()` | 993 | Handles display_type lines, posts message for extra lines on confirmed SO |
| `write()` | 1013 | Prevents display_type change, product change on non-updatable lines |
| `_get_protected_fields()` | 1059 | ['product_id', 'name', 'price_unit', 'product_uom', 'product_uom_qty', 'tax_id', 'analytic_distribution'] |
| `_update_line_quantity()` | 1070 | Posts message about qty change |
| `_check_line_unlink()` | 1091 | Cannot delete confirmed lines unless is_downpayment without invoice |
| `_validate_analytic_distribution()` | 1190 | Validates analytic distribution for draft/sent lines |
| `_get_downpayment_line_price_unit()` | 1198 | Sums posted invoice line prices for down payment |
| `_convert_to_sol_currency()` | 1295 | Converts amount to SOL currency |

---

## account.move extension (sale/models/account_move.py)

The `sale` module extends `account.move` (not `sale.order` extends account) to add sale-specific fields and behavior.

### Fields added (Lines 13–22)

```python
team_id = fields.Many2one('crm.team', string='Sales Team',
    compute='_compute_team_id', store=True, readonly=False,
    ondelete="set null", tracking=True)
campaign_id = fields.Many2one(ondelete='set null')   # UTM
medium_id = fields.Many2one(ondelete='set null')     # UTM
source_id = fields.Many2one(ondelete='set null')     # UTM
sale_order_count = fields.Integer(compute="_compute_origin_so_count")
```

### Key method overrides

| Method | Line | Description |
|--------|------|-------------|
| `_compute_team_id()` | 32 | Sets team from invoice_user_id + partner.team_id |
| `_compute_origin_so_count()` | 47 | Counts distinct SOs from line_ids.sale_line_ids |
| `_reverse_moves()` | 52 | Preserves UTM campaign/medium/source on reversal |
| `action_post()` | 64 | Updates down payment line prices after posting |
| `button_draft()` | 80 | Recomputes DP line names |
| `button_cancel()` | 88 | Recomputes DP line names |
| `_post()` | 96 | Auto-reconciles invoice with posted payment transactions |
| `_invoice_paid_hook()` | 109 | Posts message on SO when invoice is paid |
| `_is_downpayment()` | 145 | Returns True if all lines are downpayment SOLs |
| `_get_sale_order_invoiced_amount()` | 150 | Sums invoice totals for a given SO |
| `_get_partner_credit_warning_exclude_amount()` | 169 | Reduces credit warning by amount already allocated to SOs |

---

## See Also

- [Modules/sale_stock](modules/sale_stock.md) — Picking creation on SO confirmation
- [Modules/account](modules/account.md) — Invoice creation and payment
- [Modules/sale_management](modules/sale_management.md) — `done` state locking, discount wizard
- [Modules/sale_loyalty](modules/sale_loyalty.md) — Loyalty programs applied to SOs
- [Modules/sale_mrp](modules/sale_mrp.md) — Kit products and kit delivery logic
- [Modules/hr_expense](modules/hr_expense.md) — Expense products create analytic entries on confirmed SOs