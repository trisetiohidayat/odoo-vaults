# Workflow Patterns

Dokumentasi Odoo 15 untuk workflow dan state machine patterns.

## State Machine Basics

```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('confirm', 'Confirmed'),
    ('done', 'Done'),
    ('cancel', 'Cancelled'),
], string='Status', default='draft', index=True, copy=False, readonly=True,
   track_visibility='onchange')
```

## Action Methods

### Confirm / Approve Action

```python
def action_confirm(self):
    """Confirm the record"""
    for record in self:
        if record.state == 'draft':
            record.write({'state': 'confirm'})
    return True

def action_approve(self):
    """Approve and move to next state"""
    self.write({'state': 'approve'})
    self._send_approval_email()
    return True
```

### Cancel Action

```python
def action_cancel(self):
    """Cancel the record"""
    for record in self:
        if record.state == 'done':
            raise UserError(_('Cannot cancel a done record'))
        record.write({'state': 'cancel'})
    return True
```

### Reset / Draft Action

```python
def action_draft(self):
    """Reset to draft state"""
    self.write({'state': 'draft'})
    return True
```

### Done / Complete Action

```python
def action_done(self):
    """Mark as done"""
    self.write({
        'state': 'done',
        'date_done': fields.Datetime.now(),
    })
    return True
```

## Full Workflow Example

```python
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class MyDocument(models.Model):
    _name = 'my.document'
    _description = 'My Document'
    _order = 'sequence, id'

    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence', default=10)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approve', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', index=True, copy=False, readonly=True,
       track_visibility='onchange')

    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.uid)
    date_approved = fields.Datetime('Approved Date', copy=False, readonly=True)
    note = fields.Text('Notes')

    # ─────────────────────────────────────────────
    # Workflow Actions
    # ─────────────────────────────────────────────

    def action_submit(self):
        """Submit document for review"""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Can only submit draft documents'))
            if not record.name:
                raise ValidationError(_('Name is required'))
        self.write({'state': 'review'})
        self._notify_submission()
        return True

    def action_review(self):
        """Mark as under review"""
        self.write({'state': 'review'})
        return True

    def action_approve(self):
        """Approve the document"""
        for record in self:
            if record.state not in ('draft', 'review'):
                raise UserError(_('Cannot approve in state: %s') % record.state)
        self.write({
            'state': 'approve',
            'date_approved': fields.Datetime.now(),
        })
        self._send_approval_email()
        return True

    def action_done(self):
        """Finalize the document"""
        for record in self:
            if record.state != 'approve':
                raise UserError(_('Must be approved first'))
        self.write({'state': 'done'})
        return True

    def action_cancel(self):
        """Cancel the document"""
        for record in self:
            if record.state == 'done':
                raise UserError(_('Cannot cancel a done record'))
            if record.state == 'done':
                # Unlink related records or revert actions
                record._revert_actions()
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        """Reset to draft"""
        self.write({'state': 'draft'})
        return True

    # ─────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────

    @api.constrains('state', 'user_id')
    def _check_user_required(self):
        for record in self:
            if record.state in ('review', 'approve', 'done'):
                if not record.user_id:
                    raise ValidationError(_('Responsible user is required'))

    # ─────────────────────────────────────────────
    # State-dependent Field Attributes
    # ─────────────────────────────────────────────

    note = fields.Text('Notes', states={
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    })
```

## Wizard Pattern (TransientModel)

Konfirmasi dialog sebelum action:

```python
class ConfirmWizard(models.TransientModel):
    _name = 'confirm.wizard'
    _description = 'Confirmation Wizard'

    def _default_active_id(self):
        return self.env.context.get('active_id', False)

    active_id = fields.Integer('Active ID', default=_default_active_id)
    reason = fields.Char('Reason')

    def action_confirm(self):
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])
        records = self.env(active_model).browse(
            active_ids or [self.active_id]
        )
        for record in records:
            record.write({'state': 'confirm'})
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

# Call wizard from main model:
def action_confirm_wizard(self):
    return {
        'name': _('Confirm Records'),
        'type': 'ir.actions.act_window',
        'res_model': 'confirm.wizard',
        'view_mode': 'form',
        'target': 'new',  # Modal dialog
        'context': {
            'active_model': self._name,
            'active_ids': self.ids,
        },
    }
```

## Button Patterns in XML

```xml
<header>
    <button name="action_submit" string="Submit" type="object"
            class="btn-primary" confirm="Submit this document?"/>
    <button name="action_approve" string="Approve" type="object"
            states="draft,review"/>
    <button name="action_done" string="Mark Done" type="object"
            states="approve" class="btn-success"/>
    <button name="action_cancel" string="Cancel" type="object"
            states="draft,review,approve" class="btn-danger"/>
    <button name="action_draft" string="Reset to Draft" type="object"
            states="cancel"/>
</header>
```

## Workflow Transition Rules

### Conditional Transitions

```python
# Only allow transition from specific states
def action_done(self):
    for record in self:
        if record.state != 'approve':
            raise UserError(_('Cannot mark as done'))
        # Business logic check
        record._validate_completion_requirements()
    return super().action_done()
```

### Cascading State Changes

```python
def action_confirm(self):
    # Confirm main record
    self.write({'state': 'confirm'})
    # Cascade to lines
    for line in self.line_ids:
        line.write({'state': 'confirm'})
    return True
```

## Checklist Pattern

```python
def _validate_can_cancel(self):
    """Check if record can be cancelled"""
    if self.state == 'done':
        return False, _('Cannot cancel a completed record')
    if self.line_ids.filtered(lambda l: l.state == 'done'):
        return False, _('Cancel all line items first')
    return True, None

def action_cancel(self):
    can_cancel, message = self._validate_can_cancel()
    if not can_cancel:
        raise UserError(message)
    self.write({'state': 'cancel'})
```

## See Also
- [[Core/API]] — @api.constrains, @api.onchange
- [[Core/BaseModel]] — CRUD operations
- [[Core/Exceptions]] — UserError, ValidationError
- [[Modules/Sale]] — Sale order workflow example