---
type: snippet
tags: [odoo, odoo19, snippet, model, template, code, state-machine, computed, onchange, constraint, wizard]
created: 2026-04-06
updated: 2026-04-14
---

# Model Snippets

Comprehensive real-world code patterns for Odoo 19 model development. All snippets are sourced from actual Odoo CE modules (`sale`, `crm`, `account`) and adapted for custom module use.

> **Source references:** `sale.models.sale_order`, `crm.models.crm_lead`, `account.wizard.account_validate_account_move`, `sale.wizard.sale_make_invoice_advance`

---

## 1. State Machine Pattern

Full `sale.order`-style state machine with action methods, validation, and tracking. This is the canonical Odoo workflow pattern.

### Model Definition

```python
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

class ProjectTask(models.Model):
    _name = 'project.task'
    _description = 'Project Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id desc'

    # -- State Machine States --
    STATE_SELECTION = [
        ('draft', 'New'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ]

    name = fields.Char(string='Title', required=True, tracking=True)
    state = fields.Selection(
        selection=STATE_SELECTION,
        string='Status',
        readonly=True,
        copy=False,
        default='draft',
        tracking=3,
        index=True,
    )
    active = fields.Boolean(default=True)
    priority = fields.Selection(
        [('0', 'Low'), ('1', 'High')],
        string='Priority',
        default='0',
        tracking=True,
    )

    # -- Related Fields --
    user_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        default=lambda self: self.env.user,
        tracking=True,
    )
    partner_id = fields.Many2one('res.partner', string='Customer')
    date_deadline = fields.Date(string='Deadline')
    tag_ids = fields.Many2many('project.tags', string='Tags')

    # -- Computed Tracking Fields --
   kanban_state = fields.Selection(
        [('normal', 'Grey'), ('blocked', 'Red'), ('done', 'Green')],
        string='Kanban State',
        compute='_compute_kanban_state',
        store=True,
        readonly=False,
    )
    is_blocked = fields.Boolean(string='Blocked', compute='_compute_is_blocked', store=True)

    # -- SQL Constraint --
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Task title must be unique!'),
    ]

    # -- Compute Methods --

    @api.depends('state', 'date_deadline')
    def _compute_kanban_state(self):
        """Automatically set kanban state based on deadline and state."""
        today = fields.Date.today()
        for task in self:
            if task.state in ('done', 'cancelled'):
                task.kanban_state = 'done'
            elif task.date_deadline and task.date_deadline < today:
                task.kanban_state = 'blocked'  # Overdue = blocked
            else:
                task.kanban_state = 'normal'

    @api.depends('kanban_state')
    def _compute_is_blocked(self):
        for task in self:
            task.is_blocked = task.kanban_state == 'blocked'

    # -- Constraint Methods --

    @api.constrains('date_deadline', 'state')
    def _check_deadline_in_past(self):
        """Warn if setting a deadline in the past when moving to in_progress."""
        for task in self:
            if task.state == 'in_progress' and task.date_deadline:
                if task.date_deadline < fields.Date.today():
                    raise ValidationError(
                        _("The deadline for task '%s' is set in the past.", task.name)
                    )

    @api.constrains('user_id', 'state')
    def _check_assignee_for_done(self):
        """Require an assignee before marking as done."""
        for task in self:
            if task.state == 'done' and not task.user_id:
                raise ValidationError(
                    _("A task must be assigned before it can be marked as Done.")
                )

    # -- Action Methods (State Transitions) --

    def action_draft(self):
        """Reset task to draft state. Only allowed from cancelled."""
        for task in self:
            if task.state != 'cancelled':
                raise UserError(
                    _("Only cancelled tasks can be reset to draft.")
                )
            task.write({
                'state': 'draft',
                'kanban_state': 'normal',
            })
        return True

    def action_in_progress(self):
        """Start work on the task. Validates required fields first."""
        for task in self:
            if task.state not in ('draft', 'review'):
                raise UserError(
                    _("Task must be in 'New' or 'Review' state to start work.")
                )
            # Validate required fields before proceeding
            if not task.name:
                raise ValidationError(_("Task must have a title."))

            task.write({'state': 'in_progress'})

            # Trigger activity reminder
            task.activity_schedule(
                'mail.mail_activity_data_todo',
                note=_('Task started'),
                user_id=task.user_id.id or self.env.user.id,
            )

            # Log the state change
            task.message_post(
                body=_('Task moved to In Progress'),
                message_type='notification',
            )
        return True

    def action_review(self):
        """Move task to review — signals work is complete and needs approval."""
        for task in self:
            if task.state != 'in_progress':
                raise UserError(
                    _("Only tasks in progress can be moved to review.")
                )
            task.write({'state': 'review'})

            # Notify reviewer via activity
            if task.partner_id:
                task.activity_schedule(
                    'mail.mail_activity_data_review',
                    note=_('Please review: %s', task.name),
                    user_id=task.user_id.id,
                )
        return True

    def action_done(self):
        """Mark task as complete. Locks the record and archives if configured."""
        for task in self:
            if task.state not in ('in_progress', 'review'):
                raise UserError(
                    _("Only tasks in progress or review can be marked done.")
                )
            task.write({
                'state': 'done',
                'kanban_state': 'done',
            })

            # Post completion message
            task.message_post(
                body=_('Task marked as Done by %s', self.env.user.name),
                message_type='notification',
            )

            # If using auto-done setting, lock the task
            if task._should_be_locked():
                task.action_lock()
        return True

    def action_cancel(self):
        """Cancel the task. Can cancel from any non-done state."""
        for task in self:
            if task.state == 'done':
                raise UserError(
                    _("Completed tasks cannot be cancelled. Unlock them first.")
                )
            task.write({
                'state': 'cancelled',
                'kanban_state': 'normal',
            })
            task.message_post(
                body=_('Task cancelled by %s', self.env.user.name),
                message_type='notification',
            )
        return True

    def _should_be_locked(self):
        """Hook: determine if task should be locked after completion."""
        self.ensure_one()
        return self.env['res.groups']._is_feature_enabled(
            'project.group_project_task_allow_team'
        )

    def action_lock(self):
        """Lock the task — prevents further edits."""
        for task in self:
            task.write({'active': False})
        return True
```

### XML Buttons (State Machine UI)

```xml
<!-- Form view buttons driven by state -->
<form>
    <header>
        <!-- Status bar shows current state -->
        <field name="state" widget="statusbar"
               statusbar_colors="{'cancelled': 'danger', 'done': 'success'}"/>

        <!-- Action buttons: visible only in specific states -->
        <button name="action_draft" type="object"
                string="Reset to Draft"
                invisible="state != 'cancelled'"
                class="oe_highlight"/>

        <button name="action_in_progress" type="object"
                string="Start"
                invisible="state not in ('draft', 'review')"
                class="oe_highlight"
                data-hotkey="v"/>

        <button name="action_review" type="object"
                string="Submit for Review"
                invisible="state != 'in_progress'"/>

        <button name="action_done" type="object"
                string="Mark Done"
                invisible="state not in ('in_progress', 'review')"
                class="oe_highlight"
                data-hotkey="d"/>

        <button name="action_cancel" type="object"
                string="Cancel"
                invisible="state in ('done', 'cancelled')"
                confirm="Are you sure you want to cancel this task?"/>
    </header>
    <sheet>
        <group>
            <field name="name"/>
            <field name="user_id"/>
            <field name="priority"/>
            <field name="date_deadline"/>
        </group>
    </sheet>
</form>
```

### State Transition Diagram

```
┌──────────┐   action_in_progress   ┌───────────────┐
│   draft  │ ─────────────────────→ │  in_progress  │
└──────────┘                         └───────┬───────┘
     ↑                                     │
     │ action_draft (from cancelled)       │ action_review
     │                                     ↓
     │                               ┌──────────┐
     │                               │  review  │
     │                               └────┬─────┘
     │                                    │ action_done
     │ action_cancel                      ↓
     │ ┌──────────────────────────────┐  ┌──────┐
     └─┤       cancelled              │  │ done │
       └──────────────────────────────┘  └──────┘
                    ↑                        │
                    └───── action_cancel ─────┘
```

---

## 2. Computed Field with Dependencies

Multi-level cascade computed pattern — a computed field that depends on another computed field, plus stored vs. non-stored considerations.

### Cascade Computed Fields

```python
from odoo import fields, models, api
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _description = 'Sales Order Line'

    # -- Primitive Fields --
    product_uom_qty = fields.Float(
        string='Quantity',
        digits='Product Unit of Measure',
        required=True,
        default=1.0,
    )
    price_unit = fields.Float(
        string='Unit Price',
        digits='Product Price',
        required=True,
        default=0.0,
    )
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0,
    )
    tax_id = fields.Many2many(
        'account.tax',
        string='Taxes',
        domain=['|', ('active', '=', False), ('active', '=', True)],
    )

    # -- Monetary Fields (Currency-Aware) --
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='order_id.currency_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='order_id.company_id',
        store=True,
        readonly=True,
    )

    # -- Computed: price_subtotal (no tax) --
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_amount',
        store=True,         # Stored = DB column, searchable/groupable
        readonly=True,
        track_visibility='always',
    )

    # -- Computed: tax_amount (derived from subtotal) --
    price_tax = fields.Float(
        string='Tax',
        compute='_compute_amount',
        store=True,
        readonly=True,
    )

    # -- Computed: price_total (subtotal + tax) --
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_amount',
        store=True,
        readonly=True,
    )

    # -- Multi-Level Cascade: depends on _compute_amount which depends on these --
    @api.depends('product_uom_qty', 'price_unit', 'discount', 'tax_id')
    def _compute_amount(self):
        """
        Cascade compute: price_subtotal → price_tax → price_total.
        All are in one method because they share dependencies.

        IMPORTANT: If price_total were to depend on price_subtotal
        and price_tax (instead of the primitives), that would also work.
        Odoo's ORM handles circular dependencies gracefully by
        topological sorting — as long as no actual cycle exists.
        """
        for line in self:
            # Step 1: Compute subtotal
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            subtotal = price * line.product_uom_qty

            # Step 2: Compute tax
            taxes_res = line.tax_id.compute_all(
                price,
                quantity=line.product_uom_qty,
                product=line.product_id,
                partner=line.order_id.partner_id,
            )
            tax_amount = taxes_res['total_included'] - taxes_res['total_excluded']

            # Step 3: Compute total
            total = subtotal + tax_amount

            # Assign all at once
            line.update({
                'price_subtotal': subtotal,
                'price_tax': tax_amount,
                'price_total': total,
            })
```

### Stored vs. Non-Stored Computed Fields

```python
class ProductProduct(models.Model):
    _name = 'product.product'

    # STORED = written to DB column. Recomputed only when dependencies change.
    # Good for: expensive calculations, fields used in searches/sort/groupby.
    list_price = fields.Float(store=True)

    # NOT STORED = computed on every read. Good for: cheap, dynamic values.
    # NOTE: Odoo 13+ auto-stores related fields by default if related field is stored.
    display_name = fields.Char(compute='_compute_display_name', store=False)

    # STORED + INDEXED: for fields you search or group by.
    name = fields.Char(index='trigram', store=True)  # Trigram index for ilike searches

    # COMPUTED + STORED with recursive dependency
    parent_path = fields.Char(
        compute='_compute_parent_path',
        store=True,
        index=True,
    )

    @api.depends('name', 'parent_id.parent_path')
    def _compute_parent_path(self):
        for record in self:
            if record.parent_id:
                record.parent_path = f"{record.parent_id.parent_path}/{record.id}"
            else:
                record.parent_path = str(record.id)
```

---

## 3. Onchange Cascade

Multiple onchanges triggering each other — a common pattern in sale.order and account.move where changing a field automatically updates others.

### Cascading Onchanges

```python
class SaleAdvancePaymentInv(models.TransientModel):
    """From sale/wizard/sale_make_invoice_advance.py"""
    _name = 'sale.advance.payment.inv'
    _description = 'Sales Advance Payment Invoice'

    # -- Wizard Fields --
    advance_payment_method = fields.Selection(
        selection=[
            ('delivered', "Regular invoice"),
            ('percentage', "Down payment (percentage)"),
            ('fixed', "Down payment (fixed amount)"),
        ],
        string="Create Invoice",
        default='delivered',
        required=True,
    )
    amount = fields.Float(
        string="Down Payment %",
        help="Percentage of amount to be invoiced in advance.",
    )
    fixed_amount = fields.Monetary(
        string="Fixed Amount",
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        compute='_compute_currency_id',
        store=True,
    )
    sale_order_ids = fields.Many2many(
        'sale.order',
        default=lambda self: self.env.context.get('active_ids'),
    )
    count = fields.Integer(string="Order Count", compute='_compute_count')

    # -- Compute Methods --

    @api.depends('sale_order_ids')
    def _compute_count(self):
        """Simple compute: updates when sale_order_ids changes."""
        for wizard in self:
            wizard.count = len(wizard.sale_order_ids)

    @api.depends('sale_order_ids')
    def _compute_currency_id(self):
        """
        Currency is recomputed whenever selected orders change.
        If multiple orders with different currencies exist, result is False.
        """
        self.currency_id = False
        for wizard in self:
            if wizard.count == 1:
                wizard.currency_id = wizard.sale_order_ids.currency_id

    # -- Onchange Methods: Cascade Chain --

    @api.onchange('advance_payment_method')
    def _onchange_advance_payment_method(self):
        """
        Cascade 1: Changing payment method resets the amount fields
        and triggers recomputation of currency_id (via compute dependency).

        Returning {'value': {}} triggers a form refresh with new values.
        """
        if self.advance_payment_method == 'percentage':
            # Reset fixed amount, compute percentage amount
            return {'value': {'fixed_amount': 0.0}}
        elif self.advance_payment_method == 'fixed':
            # Reset percentage, user enters fixed amount
            return {'value': {'amount': 0.0}}
        else:
            # Regular invoice — no advance payment
            return {'value': {'amount': 0.0, 'fixed_amount': 0.0}}

    @api.onchange('sale_order_ids')
    def _onchange_sale_orders(self):
        """
        Cascade 2: When sale orders change, currency_id is recomputed
        (via _compute_currency_id), count is updated, and if there's
        exactly 1 order, we could auto-fill other values.
        """
        if self.count == 1:
            order = self.sale_order_ids
            # Auto-set currency based on the single selected order
            self.currency_id = order.currency_id
            # Could also pre-fill amount based on order's payment terms
            return {
                'warning': {
                    'title': _('Order Selected'),
                    'message': _(
                        "Down payment for order %s will be created.",
                        order.name
                    ),
                }
            }

    # -- Onchange with Domain Filtering --

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """
        Onchange can also set domains dynamically.
        Here we filter available products based on partner.
        """
        if self.partner_id:
            # Filter products allowed for this partner
            return {
                'domain': {
                    'product_id': [
                        ('partner_id', 'in', [self.partner_id.id, False]),
                        ('sale_ok', '=', True),
                    ]
                }
            }
        else:
            return {
                'domain': {
                    'product_id': [('sale_ok', '=', True)]
                }
            }
```

### Onchange with Warning

```python
@api.onchange('date_deadline')
def _onchange_date_deadline(self):
    """Warn if deadline is in the past."""
    if self.date_deadline:
        today = fields.Date.today()
        if self.date_deadline < today:
            return {
                'warning': {
                    'title': _("Deadline in the Past"),
                    'message': _(
                        "You have set a deadline in the past. "
                        "Please confirm this is intentional."
                    ),
                }
            }
```

---

## 4. Button Actions

Confirm, cancel, done buttons with state checks. Pattern sourced from `sale.order` action methods.

### Action with Validation and Pre/Post Hook

```python
class SaleOrder(models.Model):
    """Sourced from sale/models/sale_order.py"""
    _name = 'sale.order'

    state = fields.Selection(
        [('draft', "Quotation"), ('sent', "Quotation Sent"),
         ('sale', "Sales Order"), ('done', "Locked"),
         ('cancel', "Cancelled")],
        string='Status',
        readonly=True,
        copy=False,
        default='draft',
        tracking=3,
    )

    # -- Pre-Validation Check --
    def _confirmation_error_message(self):
        """Return error message if order cannot be confirmed, False otherwise."""
        self.ensure_one()
        if self.state not in {'draft', 'sent'}:
            return _("Some orders are not in a state requiring confirmation.")
        # Check for lines without products
        if any(
            not line.display_type
            and not line.is_downpayment
            and not line.product_id
            for line in self.order_line
        ):
            return _("Some order lines are missing a product.")
        return False

    # -- Prepare Values (Hook Pattern) --
    def _prepare_confirmation_values(self):
        """
        Hook: Returns dict of field values to write on confirmation.
        Override in subclasses to add fields without overriding action_confirm.
        """
        return {
            'state': 'sale',
            'date_order': fields.Datetime.now(),
        }

    # -- Main Action --
    def action_confirm(self):
        """Confirm order: validate, write state, trigger confirmation hooks."""
        for order in self:
            # Step 1: Validate
            error_msg = order._confirmation_error_message()
            if error_msg:
                raise UserError(error_msg)

        # Step 2: Validate analytic distribution
        self.order_line._validate_analytic_distribution()

        # Step 3: Write confirmation values (via hook)
        self.write(self._prepare_confirmation_values())

        # Step 4: Post-confirmation hooks (extensible by submodules)
        context = self.env.context.copy()
        context.pop('default_name', None)
        context.pop('default_user_id', None)
        self.with_context(context)._action_confirm()

        # Step 5: Auto-lock if configured
        self.filtered(lambda so: so._should_be_locked()).action_lock()

        # Step 6: Send confirmation email if requested
        if self.env.context.get('send_email'):
            self._send_order_confirmation_mail()

        return True

    def _action_confirm(self):
        """
        Extension point for modules that need to do something on confirm.
        e.g., sale_stock overrides this to create pickings.
        Called AFTER state is already 'sale'.
        """
        return True

    # -- Cancel with Related Record Handling --
    def action_cancel(self):
        """Cancel order and all related records (invoices, pickings)."""
        for order in self:
            if order.state == 'done':
                raise UserError(
                    _("Cannot cancel a locked order. Unlock it first.")
                )

            # Cancel related pickings
            for picking in order.picking_ids:
                if picking.state not in ('done', 'cancel'):
                    picking.action_cancel()

            # Reset draft invoices
            for invoice in order.invoice_ids:
                if invoice.state == 'posted':
                    invoice.button_draft()

            order.write({'state': 'cancel'})

            # Notify via message
            order.message_post(
                body=_("Order cancelled by %s", self.env.user.name),
                message_type='notification',
            )
        return True

    # -- Lock/Unlock --
    def action_lock(self):
        for order in self:
            order.write({'state': 'done', 'locked': True})

    def action_unlock(self):
        for order in self:
            if order.state != 'done':
                raise UserError(_("Only locked orders can be unlocked."))
            order.write({'state': 'sale', 'locked': False})

    def action_draft(self):
        """Reset cancelled or sent orders to draft."""
        orders = self.filtered(lambda s: s.state in ['cancel', 'sent'])
        return orders.write({
            'state': 'draft',
            'signature': False,
            'signed_by': False,
            'signed_on': False,
        })
```

### Wizard-Action Button (opens a form)

```python
# In a model: open a wizard form when button is clicked
def action_open_discount_wizard(self):
    """Open a wizard to apply a discount to the order."""
    self.ensure_one()
    return {
        'name': _("Apply Discount"),
        'type': 'ir.actions.act_window',
        'res_model': 'sale.order.discount',
        'view_mode': 'form',
        'target': 'new',         # Opens as a popup
        'context': {
            'default_order_id': self.id,
            'active_model': self._name,
            'active_id': self.id,
            'active_ids': self.ids,
        },
    }
```

---

## 5. Constraints

`@api.constrains` for field-level validation and `_sql_constraints` for database-level rules.

### Python Constraints with super() Call

```python
class SaleOrder(models.Model):
    """Sourced from sale/models/sale_order.py"""
    _name = 'sale.order'

    # -- API Constraint: Python-level validation on write --
    @api.constrains('company_id', 'order_line')
    def _check_order_line_company_id(self):
        """
        Validates that all products in order lines belong to
        companies accessible from the order's company.

        @api.constrains is called on every create/write.
        If it raises ValidationError, the entire transaction is rolled back.
        """
        for order in self:
            invalid_companies = order.order_line.product_id.company_id.filtered(
                lambda c: order.company_id not in c._accessible_branches()
            )
            if invalid_companies:
                bad_products = order.order_line.product_id.filtered(
                    lambda p: p.company_id
                    and p.company_id in invalid_companies
                )
                raise ValidationError(_(
                    "Your quotation contains products from company %s "
                    "whereas your quotation belongs to company %s. "
                    "Please remove the products from other companies.",
                    ', '.join(invalid_companies.sudo().mapped('display_name')),
                    order.company_id.display_name,
                ))

    @api.constrains('prepayment_percent')
    def _check_prepayment_percent(self):
        """Ensure prepayment percent is between 0 and 1."""
        for order in self:
            if order.require_payment:
                if not (0 < order.prepayment_percent <= 1.0):
                    raise ValidationError(
                        _("Prepayment percentage must be a valid percentage.")
                    )

    # -- Extending a parent constraint (calling super) --
    def _check_some_parent_constraint(self):
        """
        When extending a model that already has @api.constrains,
        override the method and call super() to include both
        parent and child validation logic.
        """
        # First run parent validation
        super()._check_some_parent_constraint()
        # Then run additional child-specific validation
        for record in self:
            if record.custom_field and record.state == 'draft':
                # Your additional validation here
                pass
```

### SQL Constraints

```python
class ProductProduct(models.Model):
    _name = 'product.product'

    # -- SQL Constraints: DB-level rules, always enforced --
    _sql_constraints = [
        # Unique constraint: product reference must be unique
        ('default_code_unique', 'unique(default_code)',
         'Product reference must be unique!'),

        # Check constraint: name must not be null/empty
        ('name_check', 'CHECK(name IS NOT NULL AND name != \'\')',
         'The name of the product cannot be empty!'),

        # Positive price constraint
        ('positive_price', 'CHECK(list_price >= 0)',
         'Product price must be non-negative!'),
    ]
```

### Constrain with Related Record Access

```python
@api.constrains('partner_id')
def _check_partner_is_customer(self):
    """
    Access partner fields within @api.constrains — Odoo loads
    all tracked fields automatically, so partner_id.name etc.
    are available without explicit depends.
    """
    for record in self:
        if record.partner_id and record.partner_id.customer_rank <= 0:
            raise ValidationError(
                _("The selected partner is not marked as a customer.")
            )
```

---

## 6. Create/Write Override

`@api.model_create_multi` for bulk record creation hooks, and `write`/`create` overrides for pre/post processing.

### @api.model_create_multi with Pre/Post Hook

```python
class SaleOrder(models.Model):
    """Sourced from sale/models/sale_order.py"""
    _name = 'sale.order'

    # -- Bulk Create Override --
    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create for all records. Runs before and after DB insert.

        vals_list: list of dicts — one dict per record being created
        @api.model_create_multi decorator enables bulk optimization.
        """
        # PRE-HOOK: Enrich each vals dict before insertion
        for vals in vals_list:
            # Auto-generate sequence number if name is "New"
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                seq_date = None
                if 'date_order' in vals:
                    seq_date = fields.Datetime.context_timestamp(
                        self,
                        fields.Datetime.to_datetime(vals['date_order'])
                    )
                vals['name'] = (
                    self.env['ir.sequence'].with_company(vals.get('company_id')
                        or self.env.company).next_by_code(
                            'sale.order',
                            sequence_date=seq_date,
                        ) or _('New')
                )

            # Set default company if not specified
            if 'company_id' not in vals:
                vals['company_id'] = self.env.company.id

        # CORE: Delegate to ORM
        return super().create(vals_list)

    # -- Write Override --
    def write(self, vals):
        """
        Runs before updating each record.
        Can add computed defaults or prevent certain writes.
        """
        # Example: Prevent pricelist change on confirmed orders
        if 'pricelist_id' in vals:
            confirmed_orders = self.filtered(lambda so: so.state == 'sale')
            if confirmed_orders:
                raise UserError(
                    _("You cannot change the pricelist of a confirmed order!")
                )

        return super().write(vals)

    # -- ondelete Behavior --
    # Use @api.ondelete to intercept record deletion
    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft_or_cancel(self):
        """Prevent deletion of non-draft orders."""
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_(
                    "You cannot delete a sent quotation or a confirmed sales order. "
                    "You must first cancel it."
                ))
```

### Copy Override with Line Filtering

```python
class SaleOrder(models.Model):
    """Sourced from sale/models/sale_order.py"""

    def _get_copiable_order_lines(self):
        """
        Returns order lines that should be copied.
        Excludes down-payment lines from copy.
        """
        return self.order_line.filtered(lambda l: not l.is_downpayment)

    def copy_data(self, default=None):
        """
        Override copy to exclude down-payment lines
        and generate a new sequence number.
        """
        default = dict(default or {})
        # Check if order_line is being explicitly excluded in the copy call
        default_has_no_order_line = 'order_line' not in default
        default.setdefault('order_line', [])  # Empty list = no lines copied

        # Get standard copy data for each field
        vals_list = super().copy_data(default=default)

        if default_has_no_order_line:
            # Only copy non-downpayment lines
            for order, vals in zip(self, vals_list):
                vals['order_line'] = [
                    Command.create(line_vals)
                    for line_vals in
                    order._get_copiable_order_lines().copy_data()
                ]
        return vals_list
```

---

## 7. Name Search Customization

Override `_name_search` to provide custom search behavior when users type in a Many2one field.

### Custom Name Search

```python
class ResPartner(models.Model):
    _name = 'res.partner'

    # -- Custom _name_search --
    @api.model
    def _name_search(self, name='', args=None, operator='ilike',
                      limit=100, name_get_uid=None):
        """
        Override to search partners by multiple fields beyond just 'name'.

        Sourced from: base logic in res.partner, extended by sale/purchase.

        Args:
            name: Search term entered by user
            args: Domain filter from the field's domain attribute
            operator: Domain operator (usually 'ilike')
            limit: Max results to return
            name_get_uid: UID to use for name_get()
        """
        if args is None:
            args = []

        # Determine search columns based on what user typed
        domain = ['|', '|', '|',
            ('name', operator, name),
            ('display_name', operator, name),
            ('email', operator, name),
            ('ref', operator, name),      # Internal reference
            ('vat', operator, name),     # Tax ID (for vendors)
        ]

        # Apply context-based filtering
        if self.env.context.get('sale_show_partner_name'):
            # In sale context, also search parent company name
            domain = ['|'] + domain + [
                ('parent_id.name', operator, name)
            ]

        if self.env.context.get('partner_only'):
            domain = [('customer_rank', '>', 0)] + domain

        return self._search(
            domain + args,
            limit=limit,
            access_right_uid_uid=name_get_uid,
        )

    # -- Or: extend _rec_names_search property --
    @property
    def _rec_names_search(self):
        """
        Defines which fields are searched by name_search.
        Return a list of field names to search.
        """
        if self.env.context.get('sale_show_partner_name'):
            return ['name', 'partner_id.name', 'ref', 'email']
        return ['name', 'ref']
```

### Name Search with Category Filter

```python
class ProjectProject(models.Model):
    _name = 'project.project'

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, **kwargs):
        """
        Search projects, optionally filtering by tag/category
        passed via context.
        """
        if args is None:
            args = []

        # If searching with a category filter in context
        if self.env.context.get('category_filter'):
            args += [('category_id', '=', self.env.context['category_filter'])]

        return super()._name_search(name, args, operator, limit, **kwargs)
```

---

## 8. Copy Override

Override `_copy` or `copy_data` to control what gets duplicated when a user clicks "Duplicate".

### _copy Override

```python
class SaleOrderLine(models.Model):
    """Control what gets copied when duplicating a sale order."""

    def _copy(self, default=None):
        """
        _copy is called for each line during copy.
        Override to reset fields that shouldn't be copied.
        """
        # Reset fields that should not be duplicated
        default = dict(default or {})
        default.setdefault('name', self.name)  # Keep name but could regenerate
        default.setdefault('sequence', 10)

        # Copy the line via ORM
        new_line = super()._copy(default)

        # Post-copy hook: e.g., re-price the copied line
        new_line._onchange_product_id()
        return new_line

    # -- Alternative: copy_data (for bulk copy of entire recordset) --
    def copy_data(self, default=None):
        """
        Returns a list of dicts representing the values to use
        when creating copies of self.

        Override here to skip certain fields or modify line data.
        """
        result = super().copy_data(default=default)
        for vals in result:
            # Reset qty_invoiced since we copy the line, not the invoice
            vals['qty_invoiced'] = 0.0
            vals['qty_delivered'] = 0.0
            # Keep product reference but mark as new line
        return result
```

---

## 9. Active Record Toggle (Archive/Unarchive)

The `active` field pattern and how archive/unarchive work in Odoo models.

### Soft Delete with Active Toggle

```python
class SaleOrder(models.Model):
    _name = 'sale.order'

    # -- Active Field: Default=True means records are visible --
    active = fields.Boolean(default=True, string='Active', index=True)

    # -- Default domain on search: active=T -- #
    # NOTE: Odoo's ORM automatically filters out inactive records
    # in search() unless you pass (0,0) or set active_test=False.

    def action_archive(self):
        """Archive selected records (soft delete)."""
        for record in self:
            if record.state == 'sale':
                raise UserError(
                    _("Cannot archive a confirmed order. Cancel it first.")
                )
            record.write({'active': False})

        # Post archive message
        self.message_post(
            body=_("Archived by %s", self.env.user.name),
            message_type='notification',
        )
        return True

    def action_unarchive(self):
        """Restore archived records."""
        self.write({'active': True})
        self.message_post(
            body=_("Restored from archive by %s", self.env.user.name),
            message_type='notification',
        )
        return True

    # -- Overriding unlink() for soft delete (optional) --
    def unlink(self):
        """
        By default, unlink() performs hard delete.
        Override here to make it a soft delete instead.
        """
        # Option A: Soft delete
        self.write({'active': False})
        return True

        # Option B: Allow hard delete for certain states only
        records_to_delete = self.filtered(
            lambda r: r.state in ('draft', 'cancel')
        )
        records_to_delete.mapped('order_line').unlink()
        return super().unlink()
```

### Searching with Inactive Records

```python
# Search INCLUDING archived records
archived_orders = self.env['sale.order'].with_context(
    active_test=False
).search([('name', 'ilike', 'SO001')])

# Search EXCLUDING active filter entirely (all records)
all_orders = self.env['sale.order'].search([])  # active_test=False default
active_orders = self.env['sale.order'].search(
    [('active', '=', True)]
)
```

---

## 10. Sequential Numbering

Using `ir.sequence` for auto-generated sequential codes (SO numbers, invoice numbers, etc.).

### Sequence-Based Numbering

```python
class SaleOrder(models.Model):
    """Sourced from sale/models/sale_order.py"""
    _name = 'sale.order'

    name = fields.Char(
        string='Order Reference',
        required=True,
        copy=False,
        readonly=False,
        index='trigram',        # Trigram index for fast ilike search
        default=lambda self: _('New'),
    )

    # -- Create Override for Sequence Assignment --
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                # Determine sequence date from order date if provided
                seq_date = None
                if 'date_order' in vals:
                    seq_date = fields.Datetime.context_timestamp(
                        self,
                        fields.Datetime.to_datetime(vals['date_order'])
                    )
                # Get sequence with company fallback
                company_id = vals.get('company_id') or self.env.company.id
                vals['name'] = (
                    self.env['ir.sequence'].with_company(company_id).next_by_code(
                        'sale.order',
                        sequence_date=seq_date,
                    ) or _('New')
                )
        return super().create(vals_list)

    # -- Manual Sequence Reset (e.g., for a new year) --
    def _resequence(self):
        """
        Resequence all records to fill gaps.
        Useful after bulk imports or data cleanup.
        """
        for index, record in enumerate(
            self.search([], order='date_order, id'), start=1
        ):
            new_name = self.env['ir.sequence'].with_company(
                record.company_id
            ).next_by_code('sale.order')
            if new_name:
                record.name = new_name
        return True
```

### ir.sequence XML Definition

```xml
<!-- security/ir_sequence_data.xml or data/data.xml -->

<record id="seq_sale_order" model="ir.sequence">
    <field name="name">Sale Order Sequence</field>
    <field name="code">sale.order</field>
    <field name="prefix">SO%(year)s/</field>
    <field name="padding">5</field>
    <field name="company_id" eval="False"/>
</record>

<!-- Example output: SO2026/00001, SO2026/00002 -->

<!-- Sequence with date-based prefix -->
<record id="seq_project_task" model="ir.sequence">
    <field name="name">Project Task Sequence</field>
    <field name="code">project.task</field>
    <field name="prefix">TASK-%(month)s-</field>  <!-- TASK-04-00001 -->
    <field name="padding">5</field>
</record>

<!-- Sequence with daily reset -->
<record id="seq_mrp_production" model="ir.sequence">
    <field name="name">Manufacturing Order</field>
    <field name="code">mrp.production</field>
    <field name="prefix">MO/%(year)s/%(month)s/%(day)s/</field>
    <field name="padding">4</field>
</record>
```

### Sequence Interpolation Codes

| Code | Description | Example |
|------|-------------|---------|
| `%(year)s` | 4-digit year | 2026 |
| `%(month)s` | 2-digit month | 04 |
| `%(day)s` | 2-digit day | 14 |
| `%(y)s` | 2-digit year | 26 |
| `%(doy)s` | Day of year | 104 |
| `%(dow)s` | Day of week (1=Mon) | 3 |
| `%(sequence)s` | Sequence number | 00001 |
| `%(company_id)s` | Company ID | 1 |

---

## Related

- [Core/BaseModel](BaseModel.md) — Model foundation, `_name`, `_inherit`, CRUD methods
- [Core/Fields](Fields.md) — Field types (Char, Many2one, Json, Monetary, etc.)
- [Core/API](API.md) — Decorators: `@api.depends`, `@api.onchange`, `@api.constrains`
- [Core/Exceptions](Exceptions.md) — ValidationError, UserError, AccessError
- [Patterns/Workflow Patterns](Workflow Patterns.md) — State machine, action methods
- [Patterns/Security Patterns](Security Patterns.md) — ACL CSV, ir.rule, field groups
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) — `_inherit` vs `_inherits` vs mixin
- [Tools/ORM Operations](ORM Operations.md) — `search()`, `browse()`, `create()`, `write()`, domain operators
- [Snippets/Wizard-Deep-Dive](Wizard-Deep-Dive.md) — TransientModel, wizard forms, action buttons
- [Snippets/Kanban-View-Patterns](Kanban-View-Patterns.md) — Kanban XML, JS widget, drag-and-drop
