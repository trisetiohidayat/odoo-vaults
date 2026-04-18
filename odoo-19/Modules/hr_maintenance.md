---
type: module
module: hr_maintenance
tags: [odoo, odoo19, hr, maintenance, equipment]
uuid: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
created: 2026-04-06
---

# Equipment Management (hr_maintenance)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Equipment Management |
| **Technical** | `hr_maintenance` |
| **Category** | Human Resources |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module** | `hr_maintenance` |

## Description

This module integrates equipment (and equipment request) tracking with the HR system. It allows companies to assign equipment to employees or departments, track equipment assignments over time, and manage maintenance requests. The equipment model extends the base `maintenance.equipment` with employee and department assignment capabilities, while the maintenance request model can be automatically created from equipment assignments.

The module is particularly useful for:
- IT asset tracking (laptops, monitors, phones)
- Company property (vehicles, tools, uniforms)
- Equipment lending (projectors, cameras, etc.)
- Maintenance scheduling and request management

## Dependencies

```
hr
maintenance
```

- `hr`: Provides `hr.employee` and `res.users` models
- `maintenance`: Provides `maintenance.equipment` and `maintenance.request` models

## Module Structure

```
hr_maintenance/
├── models/
│   ├── equipment.py           # Equipment with employee assignment
│   ├── hr_employee.py         # Employee with equipment count
│   └── maintenance_request.py # Request with employee link
├── views/
│   ├── hr_employee_view.xml   # Employee form with equipment page
│   ├── equipment_view.xml     # Equipment form with assignment
│   └── maintenance_request_views.xml
├── security/
│   └── hr_maintenance_security.xml  # ACL for maintenance records
├── data/
│   └── hr_maintenance_data.xml  # Demo data
└── __manifest__.py
```

## Data Flow

### Equipment Assignment Flow

```
HR creates equipment record
      │
      ▼
Assign to employee OR department
  - employee_id: specific employee
  - department_id: any employee in department
      │
      ▼
Equipment owner computed
  _compute_owner()
    If employee_id: owner = employee_id (user)
    If department_id: owner = department manager
    Else: owner = company
      │
      ▼
Equipment state tracked
  - assigned / available / under repair
```

### Equipment Request from Email

```
Email sent to equipment request address
      │
      ▼
Incoming email processed by mail.thread
      │
      ▼
message_new() handler
  - Extracts sender email
  - Matches to existing employee (by email)
  - Creates maintenance request linked to employee
  - Assigns to employee's equipment if identifiable
      │
      ▼
Request created with:
  - employee_id: matched employee
  - equipment_id: detected or null
  - request_type: 'corrective' or 'preventive'
```

### Subscription / Notification Flow

```
Maintenance request created
      │
      ▼
message_subscribe() called
  - Employee is subscribed to their own requests
  - Department manager subscribed to department requests
  - Owner subscribed to their equipment's requests
      │
      ▼
Followers receive notifications
  - Email notifications (if configured)
  - Odoo inbox notifications
```

## Key Models

### maintenance.equipment (Inherited)

**File:** `models/equipment.py`

Extends the base `maintenance.equipment` with employee/department assignment.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | Many2one | Assigned employee |
| `department_id` | Many2one | Assigned department |
| `equipment_assign` | Selection | Assignment type: `assigned`, `available`, `unassigned` |
| `assigned_date` | Date | Date equipment was assigned |
| `owner_user_id` | Many2one | User who owns this equipment record |

#### Key Methods

##### `_compute_owner()`

Determines who "owns" the equipment record. The owner receives notifications about the equipment's maintenance requests.

```python
def _compute_owner(self):
    """
    Compute the owner of the equipment:
    
    1. If assigned to a specific employee: owner = that employee (as user)
    2. If assigned to a department: owner = department manager
    3. Otherwise: owner = the company
    
    The owner receives all maintenance notifications for this equipment.
    """
    for equipment in self:
        if equipment.employee_id and equipment.employee_id.user_id:
            equipment.owner_user_id = equipment.employee_id.user_id.id
        elif equipment.department_id and equipment.department_id.manager_id:
            equipment.owner_user_id = equipment.department_id.manager_id.user_id.id
        else:
            # Fall back to the admin or current company
            equipment.owner_user_id = self.env.ref('base.user_admin').id
```

**Design rationale:** The owner is the person who should be notified of equipment issues. For employee-assigned equipment, it's the employee. For department-assigned equipment, it's the department manager.

##### `_compute_equipment_assign()`

Determines the assignment state of the equipment.

```python
def _compute_equipment_assign(self):
    """
    Compute assignment state:
    
    'assigned': Assigned to a specific employee
    'available': Assigned to department or company (available for use)
    'unassigned': Not assigned to anyone
    """
    for equipment in self:
        if equipment.employee_id:
            equipment.equipment_assign = 'assigned'
        elif equipment.department_id or not equipment.assign_toNobody:
            equipment.equipment_assign = 'available'
        else:
            equipment.equipment_assign = 'unassigned'
```

##### `create(vals)`

Extends equipment creation to set assignment state and subscribe the owner.

```python
def create(self, vals):
    """
    When equipment is created:
    1. Set the owner based on assignment
    2. Subscribe the owner to receive updates
    3. Log creation in equipment chatter
    """
    equipment = super().create(vals)
    
    # Subscribe the owner to maintenance requests
    if equipment.owner_user_id:
        equipment.message_subscribe(
            partner_ids=equipment.owner_user_id.partner_id.ids
        )
    
    # Log the assignment
    if equipment.employee_id:
        equipment.message_post(
            body=_("Equipment assigned to %s") % equipment.employee_id.name,
            message_type='notification',
        )
    elif equipment.department_id:
        equipment.message_post(
            body=_("Equipment assigned to department %s") % equipment.department_id.name,
            message_type='notification',
        )
    
    return equipment
```

##### `write(vals)`

Handles assignment changes and updates subscriptions.

```python
def write(self, vals):
    """
    When equipment assignment changes:
    1. Update assignment state
    2. Unsubscribe old owner, subscribe new owner
    3. Log the change
    """
    for equipment in self:
        old_owner = equipment.owner_user_id
        old_employee = equipment.employee_id
        
        res = super().write(vals)
        
        # Refresh computed fields
        equipment._compute_owner()
        equipment._compute_equipment_assign()
        
        new_owner = equipment.owner_user_id
        new_employee = equipment.employee_id
        
        # Update subscriptions
        if old_owner and old_owner != new_owner:
            equipment.message_unsubscribe(
                partner_ids=old_owner.partner_id.ids
            )
        
        if new_owner and old_owner != new_owner:
            equipment.message_subscribe(
                partner_ids=new_owner.partner_id.ids
            )
        
        # Log assignment changes
        if 'employee_id' in vals and vals['employee_id'] != old_employee.id:
            new_emp = self.env['hr.employee'].browse(vals['employee_id'])
            equipment.message_post(
                body=_("Equipment reassigned from %s to %s") % (
                    old_employee.name, new_emp.name
                ),
                message_type='notification',
            )
    
    return res
```

##### `_track_subtype()`

Determines the mail thread subtype for tracking changes.

```python
def _track_subtype(self, init_values):
    """
    Return mail thread subtype for this record's changes.
    
    If employee_id changed: 'hr_maintenance.mt_equipment_assigned'
    Otherwise: delegate to parent
    """
    if 'employee_id' in init_values:
        return self.env.ref('hr_maintenance.mt_equipment_assigned')
    return super()._track_subtype(init_values)
```

This triggers the `mt_equipment_assigned` subtype, which followers can subscribe to for notifications when equipment is assigned.

### hr.employee (Inherited)

**File:** `models/hr_employee.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `equipment_ids` | One2many | Equipment assigned to this employee |
| `equipment_count` | Integer | Count of equipment assigned (computed) |

#### Key Methods

##### `_compute_equipment_count()`

Computes the number of equipment items assigned to the employee.

```python
def _compute_equipment_count(self):
    """
    Count equipment records where employee_id = self.
    """
    for employee in self:
        employee.equipment_count = self.env['maintenance.equipment'].search_count([
            ('employee_id', '=', employee.id)
        ])
```

### maintenance.request (Inherited)

**File:** `models/maintenance_request.py`

Extends maintenance requests with employee linking and email-to-request capability.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | Many2one | Employee who owns this request |

#### Key Methods

##### `_default_employee_get()`

Attempts to find the current user's employee record.

```python
def _default_employee_get(self):
    """
    Find the employee record for the current user.
    Used as default for new maintenance requests.
    """
    user = self.env.user
    employee = self.env['hr.employee'].search([
        ('user_id', '=', user.id)
    ], limit=1)
    return employee
```

##### `message_new()`

Handles incoming email to create maintenance requests.

```python
def message_new(self, msg, custom_values=None):
    """
    When an email is received for the maintenance request channel:
    1. Find the sender's email
    2. Match to an employee
    3. Create a maintenance request linked to that employee
    """
    # Extract sender's email address
    email_from = msg.get('from', '')
    
    # Find matching employee by email
    employee = False
    if email_from:
        # Extract email from "Name <email>" format
        match = re.search(r'<(.+?)>', email_from)
        if match:
            email = match.group(1)
        else:
            email = email_from
        
        employee = self.env['hr.employee'].search([
            ('work_email', 'ilike', email)
        ], limit=1)
    
    # Build custom values
    vals = {
        'name': msg.get('subject', 'Maintenance Request'),
        'employee_id': employee.id if employee else False,
        'user_id': False,  # Don't auto-assign to sender
    }
    
    if custom_values:
        vals.update(custom_values)
    
    return super().message_new(msg, vals)
```

**Use case:** When a user emails the maintenance request address, the system automatically creates a request linked to their employee record, even if they don't have direct Odoo access.

##### `create(vals)`

Extends request creation to subscribe the employee.

```python
def create(self, vals):
    """
    When a maintenance request is created:
    1. Subscribe the employee (if any)
    2. Subscribe the equipment owner (if equipment assigned)
    3. Auto-assign based on employee/department
    """
    requests = super().create(vals)
    
    for request in requests:
        # Subscribe the employee
        if request.employee_id and request.employee_id.user_id:
            request.message_subscribe(
                partner_ids=request.employee_id.user_id.partner_id.ids
            )
        
        # Subscribe the equipment owner
        if request.equipment_id and request.equipment_id.owner_user_id:
            request.message_subscribe(
                partner_ids=request.equipment_id.owner_user_id.partner_id.ids
            )
        
        # Auto-assign to equipment owner if not assigned
        if not request.user_id and request.equipment_id.owner_user_id:
            request.write({
                'user_id': request.equipment_id.owner_user_id.id
            })
    
    return requests
```

## Email-to-Request Configuration

For email-to-request to work, configure an incoming mail server:

1. Go to **Settings > Technical > Email > Incoming Mail Servers**
2. Create a new server:
   - **Server Name**: Your IMAP server
   - **Server Type**: POP/IMAP
   - **Mail Server**: imap.example.com
   - **Port**: 993 (IMAP with SSL)
   - **Username**: maintenance@yourcompany.com
   - **Password**: Your password
   - **Action**: Create a new record
   - **Model**: `maintenance.request`
   - **Template**: Optional email template

When emails arrive at `maintenance@yourcompany.com`, they are automatically converted to maintenance requests, linked to the sender's employee record.

## Architecture Notes

### Owner vs. Assignee

The module distinguishes between two types of responsibility:

| Concept | Field | Meaning |
|---------|-------|---------|
| **Assignee** | `employee_id` | The person using/responsible for the equipment day-to-day |
| **Owner** | `owner_user_id` | The person who receives maintenance notifications |
| **Department** | `department_id` | Equipment assigned to a department, usable by any member |

**Example:** A laptop is assigned to John (assignee), but the IT manager is the owner. John has the laptop, but the IT manager gets notified when the laptop needs maintenance.

### Cascade from Employee to Equipment

When an employee's equipment changes, the equipment owner should be notified:

```
Employee termination
      │
      ▼
HR marks employee as inactive
      │
      ▼
Equipment assigned to that employee
      │
      ▼
Equipment becomes "available" (no longer assigned)
      │
      ▼
Equipment owner notified (department manager or HR)
```

This cascade is handled by the write logic on `hr.employee` (not in `hr_maintenance`, but implied by the design).

### Maintenance Request Lifecycle

```
Draft -> In Progress -> Solved / Cancelled
```

The request can be created from:
- Employee portal (if they have access)
- Email channel (automatic)
- HR/Odoo backend (manual)
- Scheduled preventive maintenance (from equipment's maintenance plan)

## Configuration

### Equipment Categories

Set up equipment categories for different types of assets:

1. Go to **Maintenance > Configuration > Equipment Categories**
2. Create categories: "IT Equipment", "Vehicles", "Tools", "Office Furniture"
3. Assign default maintenance teams to each category

### Maintenance Teams

Configure which users handle maintenance requests for each category:

1. Go to **Maintenance > Configuration > Maintenance Teams**
2. Create teams: "IT Support", "Facilities", "Fleet Management"
3. Assign team members

### Email Server for Requests

1. Go to **Settings > Technical > Email > Incoming Mail Servers**
2. Configure a dedicated address for maintenance requests
3. Set the action to create `maintenance.request` records

## Security Analysis

### Access Control

| Record | Who Can See | Who Can Edit |
|--------|------------|--------------|
| Own equipment | Employee, HR, Manager | HR, Manager |
| Department equipment | Department Manager | HR, Manager |
| All equipment | HR, Manager | HR, Manager |
| Own maintenance requests | Employee, HR, Manager | HR, Manager |
| All maintenance requests | HR, Manager | HR, Manager |

### Record Rules

The module adds `ir.rule` constraints for:
- Employees can only see their own equipment
- Managers can see their department's equipment
- HR can see all equipment

### Data Privacy

- Equipment assignments may be personal data under GDPR
- Maintenance request descriptions may contain sensitive information
- Consider restricting access to maintenance request details

## Related Views

### Employee Form with Equipment Tab

The employee form view includes an "Equipment" page showing all equipment assigned to that employee:

```xml
<page string="Equipment" name="equipment">
    <field name="equipment_ids" readonly="1">
        <tree>
            <field name="name"/>
            <field name="equipment_assign"/>
            <field name="category_id"/>
            <field name="assigned_date"/>
        </tree>
    </field>
</page>
```

### Equipment Kanban View

Equipment can be displayed in Kanban view grouped by assignment state:

```
Assigned (Employee) | Available (Department) | Available (Company)
```

## Related

- [Modules/maintenance](Modules/maintenance.md) — Base maintenance module
- [Modules/hr](Modules/HR.md) — Employee management
- [Modules/hr_equipment](hr_equipment.md) — Equipment request portal
