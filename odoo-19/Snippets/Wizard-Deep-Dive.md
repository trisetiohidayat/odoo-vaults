---
type: snippet
tags: [odoo, odoo19, snippet, wizard, transient-model, form, modal, popup]
created: 2026-04-14
---

# Wizard Deep Dive

Comprehensive guide to building wizard patterns in Odoo 19. Wizards are `models.TransientModel` subclasses that store temporary data in a popup form, then act on target records (usually via `active_id` / `active_ids` in context) when the user clicks an action button.

> **Key concept:** TransientModels are automatically deleted by the ORM's garbage collector. Their data is not persisted. They exist only for the duration of a user session.

> **Source references:** `account.wizard.account_validate_account_move`, `sale.wizard.sale_make_invoice_advance`, `account.wizard.account_payment_register`, `mrp.wizard.mrp_consumption_warning`

---

## 1. Basic Transient Model

The minimum setup for a wizard — transient model class plus a simple action method.

### Python Model

```python
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class CancelReasonWizard(models.TransientModel):
    """
    Simplest wizard: captures one field, then acts on the active record.

    TransientModel:
    - Inherits from models.TransientModel (not models.Model)
    - No _table is created in PostgreSQL — uses a virtual table
    - Automatically cleaned up by Odoo's transient record garbage collector
    - Can use all standard field types and relations (Many2one to regular models is fine)
    """
    _name = 'cancel.reason.wizard'
    _description = 'Cancel Reason Wizard'

    reason = fields.Text(string='Cancellation Reason', required=True)

    def action_confirm_cancel(self):
        """
        Action called by the wizard's confirm button.
        Reads active_id from context to know which record to cancel.
        """
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')

        if not active_id or not active_model:
            raise UserError(
                _("No active record found in context.")
            )

        # Get the target record and write to it
        record = self.env[active_model].browse(active_id)
        record.write({
            'state': 'cancelled',
            'cancel_reason': self.reason,
        })

        # Post a message on the record
        record.message_post(
            body=_("Cancelled with reason: %s", self.reason),
            message_type='notification',
        )

        # Close the wizard popup
        return {'type': 'ir.actions.act_window_close'}
```

---

## 2. Wizard Form View (XML)

The XML structure for a wizard form — form inside a modal popup.

### Basic Wizard Form

```xml
<!-- views/wizard_views.xml -->

<odoo>
    <data>
        <!-- Wizard Action: Opens the wizard form -->
        <record id="action_cancel_reason_wizard" model="ir.actions.act_window">
            <field name="name">Cancel Order</field>
            <field name="res_model">cancel.reason.wizard</field>
            <field name="view_mode">form</field>
            <field name="target">new</field>       <!-- opens as popup -->
            <field name="context">{'default_reason': 'Order cancelled by user'}</field>
        </record>

        <!-- Wizard Form View -->
        <record id="view_cancel_reason_wizard" model="ir.ui.view">
            <field name="name">cancel.reason.wizard.form</field>
            <field name="model">cancel.reason.wizard</field>
            <field name="arch" type="xml">
                <form string="Cancel Order">
                    <sheet>
                        <group>
                            <group>
                                <field name="reason" nolabel="1"
                                       placeholder="Enter cancellation reason..."/>
                            </group>
                        </group>
                    </sheet>
                    <footer>
                        <!-- Action button: calls method on the wizard model -->
                        <button name="action_confirm_cancel"
                                string="Confirm Cancellation"
                                type="object"
                                class="oe_highlight"
                                data-hotkey="q"/>
                        <!-- Close button: closes popup without action -->
                        <button string="Discard"
                                special="cancel"
                                class="btn-secondary"
                                data-hotkey="x"/>
                    </footer>
                </form>
            </field>
        </record>
    </data>
</odoo>
```

### Wizard Form with Sheet, Group, and Field Layout

```xml
<record id="view_advance_payment_wizard" model="ir.ui.view">
    <field name="name">sale.advance.payment.inv.form</field>
    <field name="model">sale.advance.payment.inv</field>
    <field name="arch" type="xml">
        <form string="Create Invoice">
            <!-- Optional: invisible fields for compute method inputs -->
            <field name="company_id" invisible="1"/>
            <field name="currency_id" invisible="1"/>

            <!-- Alert box for warnings -->
            <div invisible="not display_draft_invoice_warning"
                 class="alert alert-warning text-center" role="status">
                <field name="display_draft_invoice_warning" invisible="1"/>
                Some draft invoices exist for this order.
            </div>

            <sheet>
                <group>
                    <!-- Two-column layout -->
                    <group string="Invoice Method">
                        <field name="advance_payment_method"
                               widget="radio"/>
                    </group>

                    <!-- Advance payment fields shown conditionally -->
                    <group string="Down Payment Details"
                           invisible="advance_payment_method == 'delivered'">
                        <field name="amount"
                               invisible="advance_payment_method != 'percentage'"
                               required="advance_payment_method == 'percentage'"/>
                        <field name="fixed_amount"
                               invisible="advance_payment_method != 'fixed'"
                               required="advance_payment_method == 'fixed'"/>
                        <field name="amount_invoiced" readonly="1"/>
                    </group>
                </group>

                <!-- Separator -->
                <separator string="Selected Orders"/>
                <field name="sale_order_ids"
                       readonly="1"
                       domain="[('state', 'in', ['sale', 'done'])]">
                    <tree>
                        <field name="name"/>
                        <field name="partner_id"/>
                        <field name="date_order"/>
                        <field name="amount_total"/>
                    </tree>
                </field>
            </sheet>

            <footer>
                <button name="create_invoices"
                        string="Create Invoices"
                        type="object"
                        class="oe_highlight"/>
                <button string="Cancel"
                        special="cancel"
                        class="btn-secondary"/>
            </footer>
        </form>
    </field>
</record>
```

### Wizard Called from a Button

```xml
<!-- In the parent model's form view -->
<button name="%(cancel_reason_wizard_action)s"
        type="action"
        string="Cancel Order"
        invisible="state == 'cancelled'"
        context="{'default_reason': 'Please provide a reason'}"/>
```

---

## 3. default_get — Pre-populating Values

Override `_default_get` (or the modern `default_get` classmethod) to pre-populate wizard fields based on the active record.

### default_get Override

```python
# From: account/wizard/account_validate_account_move.py

class ValidateAccountMove(models.TransientModel):
    _name = 'validate.account.move'
    _description = "Validate Account Move"

    move_ids = fields.Many2many('account.move')
    force_post = fields.Boolean(
        string="Force",
        help="Entries in the future are set to be auto-posted by default. "
             "Check this checkbox to post them now."
    )
    force_hash = fields.Boolean(string="Force Hash")

    @api.model
    def default_get(self, fields):
        """
        Pre-populate wizard fields when it opens.

        Called automatically when the wizard form is first loaded.
        The returned dict sets default values for those fields.

        IMPORTANT: When you return [Command.set(ids)], it sets
        a Many2many field to the given record IDs.
        """
        result = super().default_get(fields)

        if 'move_ids' in fields and not result.get('move_ids'):
            # Read active model and IDs from context
            active_model = self.env.context.get('active_model')
            active_ids = self.env.context.get('active_ids', [])

            if active_model == 'account.move':
                # Filter to only draft moves that have lines
                domain = [('id', 'in', active_ids), ('state', '=', 'draft')]
                moves = self.env['account.move'].search(domain).filtered('line_ids')

                if not moves:
                    raise UserError(
                        _('There are no journal items in draft state to post.')
                    )
                result['move_ids'] = [Command.set(moves.ids)]

            elif active_model == 'account.journal':
                domain = [
                    ('journal_id', '=', self.env.context.get('active_id')),
                    ('state', '=', 'draft'),
                ]
                moves = self.env['account.move'].search(domain).filtered('line_ids')
                result['move_ids'] = [Command.set(moves.ids)]

            else:
                raise UserError(
                    _("Missing 'active_model' in context.")
                )

        return result
```

---

## 4. Action Button Methods

The pattern for action methods in wizards — create records, return window actions, or close the popup.

### Action Methods in Wizard

```python
class SaleAdvancePaymentInv(models.TransientModel):
    """From sale/wizard/sale_make_invoice_advance.py"""
    _name = 'sale.advance.payment.inv'

    sale_order_ids = fields.Many2many('sale.order')

    def _check_amount_is_positive(self):
        """Validation before creating invoices."""
        for wizard in self:
            if wizard.advance_payment_method == 'percentage' and wizard.amount <= 0.0:
                raise UserError(
                    _('The value of the down payment amount must be positive.')
                )
            elif wizard.advance_payment_method == 'fixed' and wizard.fixed_amount <= 0.0:
                raise UserError(
                    _('The value of the down payment amount must be positive.')
                )

    def create_invoices(self):
        """
        Main action: validates and creates invoices.

        Returns:
            ir.actions.act_window to open the created invoices
        """
        # Step 1: Validate
        self._check_amount_is_positive()

        # Step 2: Create invoices via business method
        invoices = self._create_invoices(self.sale_order_ids)

        # Step 3: Return action to view the invoices
        return self.sale_order_ids.action_view_invoice(invoices=invoices)

    def _create_invoices(self, sale_orders):
        """Business logic to create invoices."""
        self.ensure_one()
        if self.advance_payment_method == 'delivered':
            return sale_orders._create_invoices(
                final=self.deduct_down_payments,
                grouped=not self.consolidated_billing,
            )
        else:
            # Down payment logic...
            sale_orders.ensure_one()
            # ... compute and create down payment invoice
            return invoice

    # -- Multi-Step: View Draft Invoices instead --
    def view_draft_invoices(self):
        """
        Alternative action: opens a list of draft invoices
        instead of creating new ones.
        """
        return {
            'name': _('Draft Invoices'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'domain': [
                ('line_ids.sale_line_ids.order_id', 'in', self.sale_order_ids.ids),
                ('state', '=', 'draft'),
            ],
        }
```

### Return Actions Reference

```python
# Return to close the popup (no further action)
return {'type': 'ir.actions.act_window_close'}

# Return to reload the current view
return {'type': 'ir.actions.act_window', 'res_model': 'sale.order', 'target': 'current'}

# Return to open a specific record's form
return {
    'type': 'ir.actions.act_window',
    'res_model': 'account.move',
    'res_id': invoice.id,
    'view_mode': 'form',
    'target': 'current',
}

# Return to open a list view with a domain filter
return {
    'type': 'ir.actions.act_window',
    'name': _('Invoices'),
    'res_model': 'account.move',
    'view_mode': 'list,form',
    'domain': [('id', 'in', invoice.ids)],
    'target': 'current',
}

# Return to reload the current form
return {
    'type': 'ir.actions.act_window',
    'res_model': 'sale.order',
    'res_id': self.env.context.get('active_id'),
    'view_mode': 'form',
    'target': 'current',
    'context': dict(self.env.context),
}

# Return action from the target model (computed URL)
return self.sale_order_ids.action_view_invoice(invoices=created_invoices)

# Return a tree/list view directly
return {
    'name': _('Result'),
    'type': 'ir.actions.act_window',
    'res_model': 'result.model',
    'view_mode': 'tree,form',
    'domain': [('id', 'in', result_ids)],
}

# Return an URL redirect
return {
    'type': 'ir.actions.act_url',
    'url': '/my/report/download/%s' % report.id,
    'target': 'new',
}
```

---

## 5. Multi-Step Wizard (State-Based)

A wizard that progresses through multiple steps (Step 1: Select options, Step 2: Review, Step 3: Confirm), using an invisible `wizard_state` field to conditionally show/hide form sections.

### Multi-Step Python

```python
class MassConfirmWizard(models.TransientModel):
    _name = 'mass.confirm.wizard'
    _description = 'Multi-Step Mass Confirmation Wizard'

    # -- Step State --
    wizard_state = fields.Selection(
        [('step1', 'Select'), ('step2', 'Review'), ('step3', 'Confirm')],
        string='Step',
        default='step1',
        readonly=True,
    )

    # -- Step 1 Fields --
    partner_ids = fields.Many2many('res.partner', string='Partners')
    order_count = fields.Integer(
        string='Orders to Confirm',
        compute='_compute_order_count',
        readonly=True,
    )

    # -- Step 2 Fields --
    preview_line_ids = fields.One2many(
        'mass.confirm.wizard.line',
        'wizard_id',
        string='Orders to Process',
        readonly=True,
    )
    validated = fields.Boolean(string='Validated')

    # -- Step 2 Validation --
    @api.depends('partner_ids')
    def _compute_order_count(self):
        for wizard in self:
            orders = self.env['sale.order'].search([
                ('partner_id', 'in', wizard.partner_ids.ids),
                ('state', 'in', ['draft', 'sent']),
            ])
            wizard.order_count = len(orders)

    # -- Step Transitions --

    def action_next_to_review(self):
        """Step 1 → Step 2: Build preview lines."""
        self.ensure_one()

        if not self.partner_ids:
            raise UserError(_("Please select at least one partner."))

        # Build preview lines
        self.preview_line_ids.unlink()
        orders = self.env['sale.order'].search([
            ('partner_id', 'in', self.partner_ids.ids),
            ('state', 'in', ['draft', 'sent']),
        ])

        for order in orders:
            self.env['mass.confirm.wizard.line'].create({
                'wizard_id': self.id,
                'order_id': order.id,
            })

        self.write({'wizard_state': 'step2', 'validated': True})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mass.confirm.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_select(self):
        """Step 2 → Step 1: Go back."""
        self.ensure_one()
        self.write({'wizard_state': 'step1'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mass.confirm.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm(self):
        """Step 2/3 → Execute and close."""
        self.ensure_one()

        orders = self.env['sale.order'].search([
            ('partner_id', 'in', self.partner_ids.ids),
            ('state', 'in', ['draft', 'sent']),
        ])

        confirmed = orders.action_confirm()
        self.message_post(
            body=_("Mass confirmed %d orders.", len(orders)),
            message_type='notification',
        )
        return {'type': 'ir.actions.act_window_close'}


class MassConfirmWizardLine(models.TransientModel):
    """Preview lines for multi-step wizard."""
    _name = 'mass.confirm.wizard.line'
    _description = 'Wizard Preview Line'

    wizard_id = fields.Many2one('mass.confirm.wizard')
    order_id = fields.Many2one('sale.order', string='Order', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    amount = fields.Monetary(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
```

### Multi-Step XML

```xml
<record id="view_mass_confirm_wizard" model="ir.ui.view">
    <field name="model">mass.confirm.wizard</field>
    <field name="arch" type="xml">
        <form>
            <!-- Step indicator -->
            <div class="oe_title">
                <h3>
                    <field name="wizard_state" invisible="1"/>
                    <span invisible="wizard_state != 'step1'">Step 1: Select Partners</span>
                    <span invisible="wizard_state != 'step2'">Step 2: Review Orders</span>
                </h3>
            </div>

            <group>
                <!-- STEP 1: Partner selection -->
                <group invisible="wizard_state != 'step1'">
                    <field name="partner_ids" widget="many2many_tags"
                           domain="[('customer_rank', '>', 0)]"/>
                    <field name="order_count" readonly="1"/>
                </group>

                <!-- STEP 2: Preview -->
                <group invisible="wizard_state != 'step2'">
                    <field name="preview_line_ids" readonly="1">
                        <tree>
                            <field name="order_id"/>
                            <field name="partner_id"/>
                            <field name="amount"/>
                        </tree>
                    </field>
                </group>
            </group>

            <footer>
                <!-- Step 1 buttons -->
                <button invisible="wizard_state != 'step1'"
                        name="action_next_to_review"
                        string="Next: Review"
                        type="object"
                        class="oe_highlight"/>
                <button invisible="wizard_state != 'step1'"
                        special="cancel"
                        string="Cancel"
                        class="btn-secondary"/>

                <!-- Step 2 buttons -->
                <button invisible="wizard_state != 'step2'"
                        name="action_back_to_select"
                        string="Back"
                        type="object"
                        class="btn-secondary"/>
                <button invisible="wizard_state != 'step2'"
                        name="action_confirm"
                        string="Confirm Mass Action"
                        type="object"
                        class="oe_highlight"/>
            </footer>
        </form>
    </field>
</record>
```

---

## 6. Wizard to Model Creation

Create real database records (non-transient) from wizard values.

### Create Records from Wizard

```python
class CreatePurchaseWizard(models.TransientModel):
    _name = 'create.purchase.wizard'
    _description = 'Create Purchase from Wizard'

    partner_id = fields.Many2one('res.partner', string='Vendor', required=True)
    date_order = fields.Date(string='Order Date', required=True,
                             default=fields.Date.today)
    line_ids = fields.One2many(
        'create.purchase.wizard.line',
        'wizard_id',
        string='Order Lines',
    )
    notes = fields.Text(string='Internal Notes')

    def action_create_purchase(self):
        """
        Create a real purchase.order record from wizard data,
        then close the wizard.
        """
        self.ensure_one()

        # Create the purchase order
        purchase_vals = {
            'partner_id': self.partner_id.id,
            'date_order': self.date_order,
            'notes': self.notes or '',
            'origin': self._context.get('active_model') or '',
        }
        purchase_order = self.env['purchase.order'].create(purchase_vals)

        # Create order lines
        for line in self.line_ids:
            self.env['purchase.order.line'].create({
                'order_id': purchase_order.id,
                'product_id': line.product_id.id,
                'product_qty': line.product_qty,
                'price_unit': line.price_unit,
                'date_planned': self.date_order,
            })

        # Post a message
        purchase_order.message_post(
            body=_("Created from wizard by %s", self.env.user.name),
            message_type='notification',
        )

        # Open the created record
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': purchase_order.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CreatePurchaseWizardLine(models.TransientModel):
    """Line items in the wizard (also transient)."""
    _name = 'create.purchase.wizard.line'

    wizard_id = fields.Many2one('create.purchase.wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    price_unit = fields.Float(string='Unit Price', required=True)
    product_uom = fields.Many2one('uom.uom', string='UoM',
                                  related='product_id.uom_po_id')
```

---

## 7. Wizard with Line Items (One2many in Transient)

Wizards frequently use One2many to handle multiple items — line editing within the popup itself.

### Wizard with Editable Lines

```python
class StockAssignSerialWizard(models.TransientModel):
    """Assign serial numbers to stock moves via wizard lines."""
    _name = 'stock.assign.serial.wizard'
    _description = 'Assign Serial Numbers'

    # -- Parent Reference --
    move_id = fields.Many2one('stock.move', readonly=True)

    # -- Wizard Lines (One2many) --
    line_ids = fields.One2many(
        'stock.assign.serial.wizard.line',
        'wizard_id',
        string='Serial Numbers',
    )
    count = fields.Integer(string='Lines', compute='_compute_count', store=True)

    @api.depends('line_ids')
    def _compute_count(self):
        for wizard in self:
            wizard.count = len(wizard.line_ids)

    def action_assign(self):
        """
        Process the serial numbers from wizard lines
        and assign them to the stock move.
        """
        self.ensure_one()
        for line in self.line_ids:
            if not line.serial_number:
                raise ValidationError(
                    _("Serial number is required on all lines.")
                )

            # Assign serial number to move line
            line.move_line_id.write({
                'lot_id': line.lot_id.id,
                'qty_done': line.quantity,
            })
        return {'type': 'ir.actions.act_window_close'}


class StockAssignSerialWizardLine(models.TransientModel):
    """Line for entering serial number per unit."""
    _name = 'stock.assign.serial.wizard.line'

    wizard_id = fields.Many2one('stock.assign.serial.wizard')
    move_line_id = fields.Many2one('stock.move.line', readonly=True)
    serial_number = fields.Char(string='Serial Number')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial')
    quantity = fields.Float(string='Qty', default=1.0)
```

### Wizard Lines XML

```xml
<record id="view_assign_serial_wizard" model="ir.ui.view">
    <field name="model">stock.assign.serial.wizard</field>
    <field name="arch" type="xml">
        <form>
            <group>
                <field name="move_id" readonly="1"/>
                <field name="count"/>
            </group>
            <group>
                <field name="line_ids" nolabel="1">
                    <tree editable="bottom">
                        <field name="serial_number"/>
                        <field name="lot_id"
                               context="{'default_product_id': move_line_id.product_id.id}"/>
                        <field name="quantity"/>
                    </tree>
                </field>
            </group>
            <footer>
                <button name="action_assign" string="Assign" type="object"
                        class="oe_highlight"/>
                <button special="cancel" string="Cancel"/>
            </footer>
        </form>
    </field>
</record>
```

---

## 8. Wizard Triggering Background Jobs

Use the wizard to collect parameters, then queue a background job for long-running operations.

### Wizard with Queue Job

```python
from odoo.addons.queue_job.models.job import job


class MassExportWizard(models.TransientModel):
    _name = 'mass.export.wizard'
    _description = 'Mass Export Wizard'

    format = fields.Selection(
        [('xlsx', 'Excel'), ('csv', 'CSV'), ('pdf', 'PDF')],
        string='Export Format',
        required=True,
        default='xlsx',
    )
    include_archived = fields.Boolean(string='Include Archived Records')
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')

    def action_export(self):
        """
        Trigger a background job to perform the export,
        then close the wizard immediately.
        """
        self.ensure_one()

        # Queue the job with recordset
        job_uuid = self._export_async()

        # Notify user that export is in progress
        self.env.user.notify_info(
            message=_('Export is being prepared. You will be notified when ready.'),
        )

        return {'type': 'ir.actions.act_window_close'}

    @job
    def _export_async(self):
        """Background job: performs the actual export."""
        self.ensure_one()

        records = self._get_records_for_export()
        if self.format == 'xlsx':
            return self._export_xlsx(records)
        elif self.format == 'csv':
            return self._export_csv(records)
        else:
            return self._export_pdf(records)

    def _get_records_for_export(self):
        """Build domain for export based on wizard options."""
        domain = []
        if not self.include_archived:
            domain += [('active', '=', True)]
        if self.date_from:
            domain += [('date', '>=', self.date_from)]
        if self.date_to:
            domain += [('date', '<=', self.date_to)]
        return self.env['exportable.model'].search(domain)
```

---

## 9. Confirmation Wizard (Yes/No Pattern)

Simple confirmation popup — asks user to confirm before executing a destructive action.

### Confirmation Wizard Pattern

```python
class ConfirmCancelWizard(models.TransientModel):
    """Simple yes/no confirmation without extra fields."""
    _name = 'confirm.cancel.wizard'
    _description = 'Confirm Cancellation'

    message = fields.Text(
        string='Message',
        readonly=True,
        default=lambda s: _(
            "Are you sure you want to cancel? "
            "This action cannot be undone."
        ),
    )

    def action_yes(self):
        """User clicked Yes — proceed with cancellation."""
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')
        record = self.env[active_model].browse(active_id)

        record.action_cancel()  # Delegate to the model's cancel method
        return {'type': 'ir.actions.act_window_close'}

    def action_no(self):
        """User clicked No — do nothing, close."""
        return {'type': 'ir.actions.act_window_close'}


# XML
<record id="action_confirm_cancel" model="ir.actions.act_window">
    <field name="name">Confirm Cancellation</field>
    <field name="res_model">confirm.cancel.wizard</field>
    <field name="view_mode">form</field>
    <field name="target">new</field>
</record>

<record id="view_confirm_cancel_wizard" model="ir.ui.view">
    <field name="model">confirm.cancel.wizard</field>
    <field name="arch" type="xml">
        <form string="Confirm">
            <field name="message" readonly="1"/>
            <footer>
                <button name="action_yes" string="Yes, Cancel"
                        type="object" class="oe_highlight"/>
                <button name="action_no" string="No, Keep It"
                        special="cancel" class="btn-secondary"/>
            </footer>
        </form>
    </field>
</record>

<!-- Call from parent form -->
<button name="%(action_confirm_cancel)s"
        type="action"
        string="Cancel"
        invisible="state == 'cancelled'"
        confirm="This will cancel the order. Continue?"/>
```

---

## 10. Export Wizard (Generate and Download)

A wizard that collects export parameters, generates a file, and returns a download URL.

### Export to File Pattern

```python
import base64
import io
from odoo import fields, models, api, _


class ExportReportWizard(models.TransientModel):
    _name = 'export.report.wizard'
    _description = 'Export Report Wizard'

    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    report_format = fields.Selection(
        [('xlsx', 'Excel'), ('csv', 'CSV')],
        required=True,
        default='xlsx',
    )
    include_details = fields.Boolean(string='Include Details', default=True)

    def action_export(self):
        """
        Generate the report and return a download action.
        """
        self.ensure_one()

        # Get records
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        if self.partner_id:
            domain += [('partner_id', '=', self.partner_id.id)]

        records = self.env['account.move'].search(domain)

        if not records:
            raise UserError(_("No records found for the selected period."))

        # Generate file
        if self.report_format == 'xlsx':
            file_name, file_content = self._generate_xlsx(records)
        else:
            file_name, file_content = self._generate_csv(records)

        # Save as attachment
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'raw': file_content,
            'mimetype': (
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                if self.report_format == 'xlsx' else 'text/csv'
            ),
            'res_model': 'export.report.wizard',
            'res_id': self.id,
        })

        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'new',
        }

    def _generate_xlsx(self, records):
        """Generate Excel file using openpyxl."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Report"

        # Headers
        headers = ['Date', 'Partner', 'Reference', 'Amount']
        ws.append(headers)

        for record in records:
            ws.append([
                record.date,
                record.partner_id.name,
                record.name,
                record.amount_total,
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        file_name = f"report_{self.date_from}_{self.date_to}.xlsx"
        return file_name, content

    def _generate_csv(self, records):
        """Generate CSV file."""
        import csv
        import io as csv_io

        output = csv_io.StringIO()
        writer = csv.writer(output)

        writer.writerow(['Date', 'Partner', 'Reference', 'Amount'])
        for record in records:
            writer.writerow([
                record.date,
                record.partner_id.name,
                record.name,
                record.amount_total,
            ])

        content = output.getvalue().encode('utf-8')
        file_name = f"report_{self.date_from}_{self.date_to}.csv"
        return file_name, content
```

---

## 11. Report Wizard

Open a wizard to set report parameters, then call and download a QWeb PDF report.

### Wizard for Report Parameters

```python
class VendorReportWizard(models.TransientModel):
    _name = 'vendor.report.wizard'
    _description = 'Vendor Report Wizard'

    partner_ids = fields.Many2many('res.partner', string='Vendors')
    date_from = fields.Date(string='From Date',
                             default=fields.Date.today().replace(day=1))
    date_to = fields.Date(string='To Date',
                           default=fields.Date.today)
    state = fields.Selection(
        [('all', 'All'), ('invoiced', 'Invoiced'), ('paid', 'Paid')],
        string='Status',
        default='all',
    )
    company_id = fields.Many2one('res.company',
                                  default=lambda self: self.env.company)

    def action_print_report(self):
        """
        Call the QWeb report with the wizard's data as report values.

        Returns a report download action.
        """
        self.ensure_one()

        # Build the domain based on wizard options
        domain = [
            ('partner_id', 'in', self.partner_ids.ids),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
        ]

        if self.state == 'invoiced':
            domain += [('state', '=', 'posted')]
        elif self.state == 'paid':
            domain += [('payment_state', '=', 'paid')]

        records = self.env['account.move'].search(domain)

        if not records:
            raise UserError(_("No invoices found for the selected criteria."))

        # Return report action
        return self.env.ref('vendor_report.action_vendor_summary').report_action(
            records,
            data={
                'date_from': self.date_from,
                'date_to': self.date_to,
                'state': self.state,
            },
        )

    def action_preview_report(self):
        """
        Alternative: open a new window showing the report data
        without generating a PDF.
        """
        return {
            'name': _('Report Preview'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', 'in', self.partner_ids.ids),
                ('invoice_date', '>=', self.date_from),
                ('invoice_date', '<=', self.date_to),
            ],
            'target': 'current',
        }
```

---

## 12. Common Pitfalls

Avoid these mistakes when building wizards — they cause the most bugs in practice.

### Pitfall 1: Button type="object" vs "action"

```xml
<!-- WRONG: type="action" calls an ir.actions.act_window ID, not a method -->
<button name="%(wizard_action)s" type="action" string="Do It"/>
<!-- Here, wizard_action must be an integer ID from ir.actions.act_window -->

<!-- CORRECT: type="object" calls a Python method by name -->
<button name="action_do_it" type="object" string="Do It"/>
<!-- Python method: def action_do_it(self): ... -->
```

### Pitfall 2: Forgetting `ensure_one()` in Action Methods

```python
# WRONG: self might contain multiple wizard records
def action_confirm(self):
    self.write({'state': 'done'})  # Writes to ALL wizard records!

# CORRECT: Ensure single record
def action_confirm(self):
    self.ensure_one()  # Raise error if multiple
    self.write({'state': 'done'})
    return {'type': 'ir.actions.act_window_close'}
```

### Pitfall 3: Context Not Passed Correctly

```xml
<!-- WRONG: No context — wizard won't know the active record -->
<button name="%(wizard_action)s" type="action" string="Cancel"/>

<!-- CORRECT: Pass active_id/active_ids in context -->
<record id="wizard_action" model="ir.actions.act_window">
    <field name="context">{
        'active_model': 'sale.order',
        'active_id': active_id,
        'active_ids': active_ids,
    }</field>
</record>

<!-- CORRECT: From parent form button, use explicit context -->
<button name="%(wizard_action)s" type="action" string="Cancel"
        context="{'active_model': 'sale.order', 'active_id': active_id}"/>
```

### Pitfall 4: `default_get` Not Called When Returning `{'type': 'ir.actions.act_window_close'}`

```python
# WRONG: If you return act_window_close from action, wizard state is NOT reset
def action_cancel(self):
    return {'type': 'ir.actions.act_window_close'}  # wizard reopens same state

# CORRECT: Close then reopen to reset defaults
def action_cancel(self):
    return {'type': 'ir.actions.act_window_close'}

# To reset wizard to initial state: return the action to reopen it
def action_reset(self):
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'wizard.model',
        'view_mode': 'form',
        'target': 'new',
    }
```

### Pitfall 5: Using `@api.depends` on TransientModel Fields

```python
# @api.depends DOES work on TransientModels, but transient fields
# are recomputed eagerly on every write, which can cause
# infinite loops in multi-step wizards.

# SAFE: Use compute only for fields derived from context-derived data
# AVOID: Computing one transient field from another transient field
#        in a tight loop.
```

### Pitfall 6: Not Closing Popup After Action

```python
# WRONG: Returns nothing — popup stays open
def action_do_it(self):
    self.env['res.partner'].create({...})
    # No return = stays on wizard

# CORRECT: Always return close action
def action_do_it(self):
    self.env['res.partner'].create({...})
    return {'type': 'ir.actions.act_window_close'}

# Or return an action to open something else
def action_do_it(self):
    record = self.env['res.partner'].create({...})
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'res.partner',
        'res_id': record.id,
        'view_mode': 'form',
        'target': 'current',
    }
```

### Pitfall 7: Access Rights on TransientModel

```python
# TransientModel records are created by the current user.
# The current user's ACL applies — even for sudo() usage.

# If you need to create records that the user can't normally create:
def _create_protected_record(self):
    return self.sudo().env['protected.model'].create({...})
```

---

## Quick Reference: Wizard Patterns by Use Case

| Use Case | Pattern | Key Points |
|----------|---------|-----------|
| Capture reason/notes | Basic TransientModel | One field, one action |
| Multi-step process | State-based wizard | `wizard_state` field drives visibility |
| Bulk action confirmation | Wizard with preview | Show affected records before executing |
| Line item entry | One2many in transient | Editable tree inside popup |
| Generate download file | Export wizard | Create attachment, return download URL |
| Report generation | Report wizard | Call `report_action()` with data dict |
| Trigger background job | Queue job from wizard | Close popup immediately, job runs async |
| Yes/No confirmation | Simple confirmation | Two buttons: action_yes / action_no |
| Parameter collection then create | Model creation wizard | Build vals dict, call `env[model].create()` |

---

## Related

- [Core/BaseModel](Core/BaseModel.md) — `_name`, `_description`, model inheritance
- [Core/Fields](Core/Fields.md) — Field types used in wizards: Many2many, One2many, Monetary
- [Core/API](Core/API.md) — `@api.model`, `@api.depends`, `@api.onchange`
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machines that wizards often trigger
- [Snippets/Model Snippets](Model%20Snippets.md) — State machine, button actions, computed fields
- [Modules/Account](Modules/Account.md) — account.move and how wizard actions interact with invoices
- [Modules/Sale](Modules/Sale.md) — sale.order workflow and down payment wizards
