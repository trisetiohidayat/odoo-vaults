---
Module: base_install_request
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #modules, #workflow
---

# base_install_request

Allows users to request module installation approval before an administrator installs it. Extends `ir.module.module` with a request workflow.

## Module Overview

- **Model:** `ir.module.module` (extension via `action_open_install_request()`)
- **Dependency:** `base`
- **Pattern:** Adds a button on `ir.module.module` form view that opens a request wizard

---

## Model Extension

### `ir.module.module` (extension)

```python
class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def action_open_install_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': _('Activation Request of "%s"', self.shortdesc),
            'view_mode': 'form',
            'res_model': 'base.module.install.request',
            'context': {'default_module_id': self.id},
        }
```

**`action_open_install_request()`**

Opens the module install request wizard as a modal form, pre-filled with the current module's ID.

- `target='new'` — Opens as a popup window
- `name` — Uses the module's `shortdesc` (short description) in the dialog title
- `context` — Passes `default_module_id` to the wizard

---

## Module Structure

The module consists of a single Python file extending `ir.module.module`. The actual request model (`base.module.install.request`) and its line model (`base.module.install.request.line`) — along with their views and workflows — are part of a separate module or built into the Odoo platform's standard module request infrastructure.

### View (`ir_module_module_views.xml`)

The XML defines the button that triggers `action_open_install_request()` on the module form view.

### Context Injection

The `context: {'default_module_id': self.id}` pattern pre-populates the wizard's `module_id` field so the requesting user does not need to select the module manually.

---

## L4 Notes

- **Request vs direct install:** The module does not perform direct installation — it delegates to a separate request model. This creates a workflow separation: a user can request a module, and only an administrator can approve and execute the install.
- **`shortdesc` field:** This is the human-readable module name stored on `ir.module.module` (e.g., "Discuss" instead of "mail").
- **`ensure_one()`:** The action is only valid when exactly one module record is active. If called from a list view with multiple selected modules, this raises an error.
- **`target='new'`:** The wizard opens as a popup rather than replacing the current view. This keeps the module list visible in the background.
- **The request models** (`base.module.install.request`, `base.module.install.request.line`) are not defined in this module — they are part of `base` or a platform-level feature. This module only adds the trigger action.
- **Security:** The request workflow typically involves record rules restricting who can create requests vs who can approve them (usually administrators).
- **Relation to `base.module.install.request`:** This model is referenced by the wizard but defined elsewhere (likely in `base` or a platform module). The request line model allows specifying multiple modules in a single request.
