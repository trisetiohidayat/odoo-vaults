---
type: snippet
tags: [odoo, odoo19, snippet, kanban, view, xml, javascript, drag-drop, js-widget]
created: 2026-04-14
---

# Kanban View Patterns

Comprehensive guide to building and customizing Kanban views in Odoo 19. Covers XML architecture, JavaScript widget customization, drag-and-drop, quick create, embedded graphs, and color coding.

> **Note:** In Odoo 19, Kanban views are rendered client-side by the JavaScript KanbanWidget. The server provides the data structure (columns from grouped domain), and the JS layer handles interactions like drag-and-drop and quick create.

---

## 1. Kanban Architecture

Understanding how Odoo renders a Kanban view — the XML structure, column definitions, and record cards.

### Basic Kanban View Structure

```xml
<!-- views/project_task_kanban.xml -->

<odoo>
    <data>
        <!-- Kanban View -->
        <record id="view_project_task_kanban" model="ir.ui.view">
            <field name="name">project.task.kanban</field>
            <field name="model">project.task</field>
            <field name="arch" type="xml">
                <kanban
                    default_group_by="stage_id"
                    default_order="priority desc, sequence asc"
                    records_draggable="true"
                    quick_create_view="project.quick_create_task_form"
                    on_create="quick">
                    <!-- JS-related: drag and drop, quick create, etc -->
                    <field name="stage_id"/>
                    <field name="priority"/>
                    <field name="user_id"/>
                    <field name="date_deadline"/>
                    <field name="kanban_state"/>

                    <!-- Color based on priority -->
                    <templates>
                        <t t-name="kanban-box">
                            <div
                                t-attf-class="oe_kanban_global_click_record oe_kanban_card oe_kanban_card_click_dropdown
                                    #{record.priority.raw_value === '1' ? 'oe_kanban__PRIORITY' : ''}">

                                <!-- Card Header: Title + Priority -->
                                <div class="oe_kanban_card_header">
                                    <div class="oe_kanban_card_header_title">
                                        <field name="name"/>
                                    </div>
                                    <div class="oe_kanban_card_header_action">
                                        <field name="priority" widget="priority"/>
                                    </div>
                                </div>

                                <!-- Card Body -->
                                <div class="oe_kanban_card_content">
                                    <div t-if="record.date_deadline.raw_value"
                                         t-attf-class="
                                             #{ record.date_deadline.raw_value and new Date(record.date_deadline.raw_value) < (new Date()) ? 'text-danger' : ''}">
                                        <i class="fa fa-calendar"/> <field name="date_deadline"/>
                                    </div>
                                    <div>
                                        <field name="user_id" widget="many2one_avatar_user"/>
                                    </div>
                                </div>

                                <!-- Card Footer -->
                                <div class="oe_kanban_card_footer">
                                    <field name="kanban_state" widget="state_selection"/>
                                </div>
                            </div>
                        </t>
                    </templates>
                </kanban>
            </field>
        </record>
    </data>
</odoo>
```

### Kanban Action (with Group By)

```xml
<!-- Kanban must be associated with an action that sets the view mode -->
<record id="action_project_task_kanban" model="ir.actions.act_window">
    <field name="name">Tasks</field>
    <field name="res_model">project.task</field>
    <field name="view_mode">kanban,list,form</field>
    <!-- Default group by stage when opening -->
    <field name="context">{
        'default_user_id': uid,
        'search_default_my_tasks': 1,
    }</field>
</record>

<!-- Menu that opens Kanban by default -->
<menuitem id="menu_project_task_kanban"
          name="Tasks"
          action="action_project_task_kanban"
          parent="menu_project"
          sequence="1"/>
```

### Kanban + List Action (Two Views in One)

```xml
<!-- Some models expose both kanban and list as the default view -->
<record id="action_crm_lead_kanban" model="ir.actions.act_window">
    <field name="name">Pipeline</field>
    <field name="res_model">crm.lead</field>
    <!-- kanban first means it opens by default; list is fallback -->
    <field name="view_mode">kanban,list,form,pivot,graph</field>
    <field name="context">{
        'default_type': 'opportunity',
        'search_default_type': 'opportunity',
    }</field>
</record>
```

---

## 2. Kanban JS Widget

Override the web KanbanView in JavaScript to add custom behavior. This is for advanced customization that cannot be done purely in XML.

### Custom Kanban Widget

```javascript
/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { KanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";

import { useViewService } from "@web/views/view_hook";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

// -- 1. Custom Renderer --
class CustomKanbanRenderer extends KanbanRenderer {
    /**
     * Override to add custom DOM elements or event handlers.
     * Called for every column and every record card.
     */
    getColumns() {
        const columns = super.getColumns(...arguments);
        // Add custom column rendering
        return columns.map(column => ({
            ...column,
            // Custom: add record count badge
            displayCount: column.records.length,
        }));
    }

    /**
     * Override record card rendering.
     */
    getCardRenderProps(record, recordData) {
        const props = super.getCardRenderProps(...arguments);
        return {
            ...props,
            // Add custom data for the template
            isOverdue: this._isOverdue(recordData),
            avatarUrl: `/web/image/res.partner/${recordData.partner_id[0]}/avatar_128`,
        };
    }

    _isOverdue(recordData) {
        if (!recordData.date_deadline) return false;
        const deadline = new Date(recordData.date_deadline.value);
        return deadline < new Date();
    }
}

// -- 2. Custom Controller --
class CustomKanbanController extends KanbanController {
    /**
     * Override to handle custom button clicks in the kanban header.
     */
    setup() {
        super.setup(...arguments);
        // Use the view service to react to model changes
        this.viewService = useViewService();
    }

    /**
     * Called when a record is dropped into a column.
     * Default Odoo behavior: update group_by field.
     * Override here for custom logic (e.g., validation, notifications).
     */
    async onRecordDragAndDrop(record, column) {
        const recordId = record.resId;
        const newGroupId = column.groupId;

        // Custom validation before accepting the drop
        const groupField = this.model.groupBy[0];
        if (groupField === 'stage_id') {
            const newStage = await this.orm.read(
                'project.task.stage',
                [newGroupId],
                ['name', 'fold']
            );
            if (newStage[0]?.fold) {
                // Warn user: dropping to an archived/folded stage
                this.env.services.notification.add(
                    `Cannot drop tasks into folded stage "${newStage[0].name}"`,
                    { type: 'warning' }
                );
                return; // Reject the drop
            }
        }

        // Let default behavior proceed: write the group_by field
        await this.model.movedRecord(recordId, column);
    }

    /**
     * Handle "Quick Create" submission.
     */
    async onQuickCreate(recordData, column) {
        // Validate before creation
        if (!recordData.name) {
            this.env.services.notification.add(
                'Task name is required',
                { type: 'warning' }
            );
            return false;
        }
        // Proceed with creation
        return super.onQuickCreate(...arguments);
    }
}

// -- 3. View with Custom Components --
const customKanbanView = {
    ...KanbanView,
    props: {
        ...KanbanView.props,
        // Add custom props for your kanban
    },
};

registry.category("views").add("custom_kanban", {
    ...KanbanView,
    ...customKanbanView,
    Controller: CustomKanbanController,
    Renderer: CustomKanbanRenderer,
});
```

### Extend Existing Kanban Behavior

```javascript
/** @odoo-module **/

// If you want to extend (not replace) existing kanban behavior:
import { patch } from "@web/core/utils/patch";

import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

patch(KanbanRenderer.prototype, "custom_kanban_renderer", {
    // Add a method
    getCustomColor(record) {
        if (record.state === 'blocked') return 'danger';
        if (record.state === 'done') return 'success';
        return 'secondary';
    },
});
```

---

## 3. Drag and Drop

Odoo's Kanban supports drag-and-drop out of the box for reordering within a column and moving records between columns. Configuration and overrides.

### Enabling Drag and Drop in XML

```xml
<kanban records_draggable="true"
        default_group_by="stage_id">
    <!-- records_draggable: allows reordering within and between columns -->
    <!-- default_group_by: which field to group by (creates columns) -->

    <field name="stage_id"/>

    <templates>
        <t t-name="kanban-box">
            <div class="oe_kanban_global_click oe_kanban_card">
                <!-- Card content -->
                <field name="name"/>
            </div>
        </t>
    </templates>
</kanban>
```

### Column Drag (Reorder Columns)

```xml
<!-- Enable column dragging (reorder stages) -->
<kanban
    default_group_by="stage_id"
    records_draggable="true"
    groups_draggable="true">
    <!-- groups_draggable: allows reordering the column headers themselves -->
</kanban>
```

### Drop Validation on Stage Change

```python
# In the model: validate state transitions on group_by change
# When a record is dropped into a new column (stage), Odoo calls write()
# with the new stage_id. We can use this to validate transitions.

class ProjectTask(models.Model):
    _name = 'project.task'

    stage_id = fields.Many2one('project.task.type', string='Stage')

    # Odoo automatically writes stage_id when drag-and-drop occurs.
    # We can add constraints to prevent invalid transitions.
    @api.constrains('stage_id', 'state')
    def _check_stage_transition(self):
        """
        When dropping a task into a new stage via Kanban drag-and-drop,
        Odoo calls write({'stage_id': new_stage_id}).
        We validate whether the transition is allowed.
        """
        # Example: Cannot move completed tasks back to 'New'
        for task in self:
            if task.stage_id.is_done and task._origin.stage_id.is_done:
                if task.stage_id.sequence < task._origin.stage_id.sequence:
                    # Trying to move backward from done stage
                    raise ValidationError(
                        _("Cannot move a completed task backwards.")
                    )
```

### Custom JS Drop Handler

```javascript
// In your custom KanbanController (from section 2 above):

async onRecordDragAndDrop(record, newColumn, position) {
    /**
     * record: the dragged record { resId, resModel }
     * newColumn: target column { groupId, groupByValue, groupByField }
     * position: 'before', 'after', or 'inside' (top of column)
     */
    const recordId = record.resId;
    const newStageId = newColumn.groupId;

    // Custom: validate the move
    const allowed = await this._validateMove(recordId, newStageId);
    if (!allowed) {
        // Revert: show notification and don't update
        this.env.services.notification.add(
            "This move is not allowed by business rules.",
            { type: 'danger' }
        );
        return false;
    }

    // Call parent to proceed with the write
    return this._super(...arguments);
}

async _validateMove(recordId, newStageId) {
    const task = await this.orm.read(
        'project.task',
        [recordId],
        ['stage_id', 'user_id']
    );

    if (!task[0].user_id) {
        // Task has no assignee — allow the move
        return true;
    }

    // Business rule: assigned tasks can only move to stages
    // that the assignee has access to
    const stage = await this.orm.read(
        'project.task.type',
        [newStageId],
        ['allowed_user_ids']
    );

    if (stage[0].allowed_user_ids?.length > 0) {
        return stage[0].allowed_user_ids.includes(task[0].user_id[0]);
    }

    return true;
}
```

---

## 4. Kanban Quick Create

Inline record creation directly in a Kanban column — no need to open a full form.

### Quick Create XML Configuration

```xml
<kanban
    quick_create_view="project.quick_create_task_form">
    <!-- quick_create_view: form view shown inline when quick creating -->

    <field name="stage_id"/>

    <templates>
        <t t-name="kanban-box">
            <div class="oe_kanban_card">
                <field name="name"/>
            </div>
        </t>
    </templates>
</kanban>
```

### Quick Create Form View

```xml
<!-- Simplified form view for quick creation -->
<record id="quick_create_task_form" model="ir.ui.view">
    <field name="name">project.task.quick.create.form</field>
    <field name="model">project.task</field>
    <field name="arch" type="xml">
        <form>
            <!-- Minimal fields: name is always shown -->
            <group>
                <field name="name"
                       placeholder="Task name..."
                       autofocus="autofocus"
                       class="o_task_name_field"/>
                <!-- Can add a second field like assignee -->
                <field name="user_id"
                       widget="many2one_avatar_user"
                       placeholder="Assignee..."/>
            </group>
        </form>
    </field>
</record>
```

### Quick Create with Default Values from Column

```python
# In the model: set defaults based on the column's group_by value
class ProjectTask(models.Model):
    _name = 'project.task'

    @api.model
    def default_get(self, fields):
        """
        Set default values for quick-created records.
        group_by context tells us which column the user clicked in.
        """
        defaults = super().default_get(fields)

        # group_by context contains e.g. {'stage_id': 5}
        context = self.env.context
        if 'default_stage_id' not in defaults and 'group_by' in context:
            group_by_field = context.get('group_by')
            group_by_value = context.get('default_' + group_by_field)
            if group_by_value:
                defaults['stage_id'] = group_by_value

        return defaults
```

### Quick Create with Auto-advance to Next Column

```javascript
// In custom KanbanController

async onQuickCreate(recordData, column, { close = false } = {}) {
    const result = await this._super(...arguments);

    if (close) {
        // Don't reopen the quick create form
        return result;
    }

    // After quick create, immediately open quick create again
    // This allows rapid entry of multiple tasks in the same column
    await this.model.createRecord(column.groupedByField, {
        ...column.groupId && { [column.groupedByField]: column.groupId },
    });
}
```

---

## 5. Kanban with Embedded Graph

Embed a small bar/pie chart inside each Kanban column header or as a side panel.

### Column Header Graph

```xml
<record id="view_crm_lead_kanban" model="ir.ui.view">
    <field name="name">crm.lead.kanban</field>
    <field name="model">crm.lead</field>
    <field name="arch" type="xml">
        <kanban default_group_by="stage_id">
            <field name="stage_id"/>
            <field name="probability"/>
            <field name="expected_revenue"/>

            <templates>
                <t t-name="kanban-box">
                    <div class="oe_kanban_card oe_kanban_graph_column">
                        <!-- Revenue graph per column -->
                        <kanban_graph
                            type="bar"
                            data-widget="False"
                            toolbar="False"
                            style="width:100%; height: 60px;"/>
                        <hr/>
                        <!-- Normal card content -->
                        <field name="name"/>
                        <div>
                            <field name="expected_revenue"
                                   widget="monetary"/>
                        </div>
                    </div>
                </t>
            </templates>
        </kanban>
    </field>
</record>
```

### Kanban Column Summary Stats

```xml
<kanban default_group_by="stage_id">
    <field name="stage_id"/>

    <templates>
        <t t-name="kanban-box">
            <!-- Standard record card -->
            <div class="oe_kanban_card">
                <field name="name"/>
            </div>
        </t>

        <!-- Column header template (controls what's shown above cards) -->
        <t t-name="kanban-column">
            <div class="o_kanban_record_header">
                <div class="o_kanban_header_title">
                    <!-- Column title -->
                    <field name="stage_id"/>
                </div>

                <!-- Column stats: count + sum of revenue -->
                <div class="o_kanban_header_quick_create"/>
            </div>

            <!-- Column graph (in header area) -->
            <div class="o_kanban_graph">
                <!-- KanbanGraph renders here in Odoo 17+ -->
            </div>

            <!-- Cards will be rendered here -->
            <t t-call="kanban-box"/>
        </t>
    </templates>
</kanban>
```

---

## 6. Custom Kanban States — Color Coding and Progress

Color-code Kanban cards based on field values, priority, or business rules.

### Color Coding via decoration Attributes

```xml
<!-- decoration-* classes apply CSS classes based on a Python expression -->
<kanban
    default_group_by="stage_id"
    decoration-success="state == 'done'"
    decoration-danger="state in ('cancelled', 'blocked')"
    decoration-warning="kanban_state == 'blocked'"
    decoration-info="priority == '1'">

    <templates>
        <t t-name="kanban-box">
            <div class="oe_kanban_card">
                <field name="name"/>
            </div>
        </t>
    </templates>
</kanban>

<!-- Odoo applies these CSS classes automatically:
     decoration-success → bg-success (green)
     decoration-danger  → bg-danger  (red)
     decoration-warning → bg-warning (yellow)
     decoration-info   → bg-info    (blue)
     decoration-secondary → bg-secondary (grey)
     decoration-muted   → text-muted
-->
```

### Dynamic Color via `t-attf-class`

```xml
<!-- Custom color based on multiple conditions -->
<t t-name="kanban-box">
    <div t-attf-class="
        oe_kanban_card
        {{ record.kanban_state.raw_value === 'blocked' ? 'bg-danger text-white' : '' }}
        {{ record.date_deadline.raw_value and new Date(record.date_deadline.raw_value) < new Date() ? 'bg-warning' : '' }}">
        <!-- Card content -->
        <field name="name"/>

        <!-- Colored badge for state -->
        <span class="badge"
              t-attf-class="
                  {{ record.state.raw_value === 'done' ? 'bg-success' : '' }}
                  {{ record.state.raw_value === 'blocked' ? 'bg-danger' : '' }}">
            <field name="state"/>
        </span>
    </div>
</t>
```

### Progress Bar in Card

```xml
<kanban default_group_by="stage_id">
    <field name="progress" widget="progressbar"/>

    <templates>
        <t t-name="kanban-box">
            <div class="oe_kanban_card">
                <field name="name"/>
                <!-- Progress bar widget -->
                <field name="progress"
                       widget="progressbar"
                       options="{'current_value': 'progress', 'max_value': 'progress_max', 'editable': False}"/>
            </div>
        </t>
    </templates>
</kanban>
```

### Colored Border per Column (CSS)

```xml
<!-- Column header color via style or color index -->
<kanban default_group_by="stage_id">
    <field name="stage_id"/>
    <!-- stage_id has a 'color' field (integer) on the stage model -->

    <templates>
        <t t-name="kanban-column">
            <div class="o_kanban_record_header"
                 t-att-style="'border-left: 4px solid ' + (record.stage_id.raw_value && record.stage_id.raw_value[1] ? 'hsl(' + (record.stage_id.raw_value[0] * 37 % 360) + ', 70%, 50%)' : '#ccc')">
                <field name="stage_id"/>
            </div>
            <t t-call="kanban-box"/>
        </t>
    </templates>
</kanban>
```

---

## 7. Kanban with Action Buttons

Buttons inside Kanban cards that trigger actions without opening the full form.

### Card Buttons (Global Click vs. Button Click)

```xml
<kanban default_group_by="stage_id">
    <field name="stage_id"/>
    <field name="state"/>

    <templates>
        <t t-name="kanban-box">
            <div class="oe_kanban_card oe_kanban_global_click">
                <!-- Global click: clicking anywhere opens the form -->

                <div class="d-flex justify-content-between align-items-start">
                    <field name="name"/>

                    <!-- Action buttons (use stopPropagation so clicking
                         them doesn't open the form) -->
                    <div class="oe_kanban_action"
                         t-on-click.stop="(ev) => props.onAction('action_assign')">
                        <a title="Assign to me">
                            <i class="fa fa-user-plus"/>
                        </a>
                    </div>
                </div>

                <!-- Priority widget -->
                <field name="priority" widget="priority"/>

                <!-- Footer buttons -->
                <div class="oe_kanban_card_footer">
                    <span class="float-end">
                        <!-- Direct method call via type="object" pattern -->
                        <a type="object" name="action_schedule"
                           class="fa fa-clock-o"
                           title="Schedule"/>
                        <a type="object" name="action_send_mail"
                           class="fa fa-envelope-o"
                           title="Send Email"/>
                    </span>
                </div>
            </div>
        </t>
    </templates>
</kanban>
```

### Buttons with Confirmation

```xml
<!-- Action button that opens a wizard on click -->
<button name="%(action_cancel_task_wizard)s"
        type="action"
        string="Cancel"
        class="btn-sm btn-danger"/>

<!-- Or use icon-only button with tooltip -->
<a name="%(action_cancel_task_wizard)s"
   type="action"
   class="fa fa-ban"
   title="Cancel Task"/>
```

### Prevent Card Open When Clicking Button

```xml
<!-- In kanban-box, stop propagation of button clicks -->
<div class="oe_kanban_card">

    <!-- Method button — opens confirm dialog (Odoo handles stopPropagation) -->
    <button name="action_done"
            type="object"
            string="Mark Done"
            class="btn btn-success btn-sm"/>

    <!-- Icon button — need stopPropagation in JS -->
    <span class="fa fa-check"
          style="cursor: pointer;"
          t-on-click.stop="(ev) => props.onAction('action_done')"/>

    <!-- Dropdown in card -->
    <div class="dropdown">
        <button class="dropdown-toggle"
                data-bs-toggle="dropdown"
                t-on-click.stop>  <!-- stop: prevents card from opening -->
            <field name="state"/>
        </button>
        <div class="dropdown-menu">
            <a class="dropdown-item" href="#"
               t-on-click.stop="(ev) => props.onAction('action_set_draft')">
                Set to Draft
            </a>
            <a class="dropdown-item" href="#"
               t-on-click.stop="(ev) => props.onAction('action_cancel')">
                Cancel
            </a>
        </div>
    </div>
</div>
```

---

## 8. Overflow Handling — Large Columns

Handle columns with many records efficiently — lazy loading, lazy grouping, and pagination.

### Lazy Loading in Kanban

```xml
<!-- Odoo 17+ automatically handles lazy loading for large datasets.
     For very large columns, enable lazy="lazy" on the kanban view. -->
<kanban
    default_group_by="stage_id"
    lazy="lazy"
    records_limit="40">
    <!-- records_limit: show max N records per column;
         extra records are loaded when user scrolls down -->
</kanban>
```

### Grouped Domain in Model

```python
# Control which records appear in each column via the model's
# _read_group_raw or a custom method.

class CrmLead(models.Model):
    _name = 'crm.lead'

    def _get_groupby_states(self):
        """
        Return the stages to use as Kanban columns.
        Override to filter stages shown in Kanban.
        """
        stages = self.env['crm.stage'].search([
            ('active', '=', True),
            ('pipe_line', '=', True),  # Only show in pipeline
        ], order='sequence')
        return stages
```

### Show/Hide Column Based on Records

```xml
<kanban default_group_by="stage_id">
    <field name="stage_id"/>

    <templates>
        <!-- Hide empty columns entirely -->
        <t t-name="kanban-column">
            <t t-if="Object.keys(column.count || {}).length > 0">
                <!-- Only render if column has records -->
                <div class="o_kanban_column">
                    <div class="o_kanban_header">
                        <field name="stage_id"/>
                        <span class="badge bg-secondary">
                            <t t-esc="column.records.length"/>
                        </span>
                    </div>
                    <t t-call="kanban-box"/>
                </div>
            </t>
        </t>
    </templates>
</kanban>
```

### Collapsible Column (Fold/Unfold)

```xml
<!-- Click column header to fold/unfold (Odoo built-in).
     Requires folded attribute on stage/group_by model. -->

<!-- In the group_by model (stage), add: -->
<record id="stage_done" model="project.task.type">
    <field name="name">Done</field>
    <field name="fold" eval="True"/>  <!-- Column starts folded -->
</record>

<!-- In kanban template: show fold/unfold button -->
<t t-name="kanban-column">
    <div class="o_kanban_column"
         t-att-data-folded="column.isFolded">
        <div class="o_kanban_header"
             t-on-click="ev => column.toggle()">
            <!-- Fold indicator -->
            <i class="fa"
               t-attf-class="{{ column.isFolded ? 'fa-chevron-right' : 'fa-chevron-down' }}"/>
            <field name="stage_id"/>
        </div>
        <!-- Records shown only when unfolded -->
        <div t-if="!column.isFolded">
            <t t-call="kanban-box"/>
        </div>
    </div>
</t>
```

---

## Quick Reference: Kanban XML Attributes

| Attribute | Values | Purpose |
|-----------|--------|---------|
| `default_group_by` | field name | Column grouping field |
| `default_order` | `field1, field2 desc` | Default sorting |
| `records_draggable` | `true` / `false` | Enable record drag-drop |
| `groups_draggable` | `true` / `false` | Enable column reordering |
| `quick_create_view` | XML ID | Form for inline quick create |
| `on_create` | `'quick'` / XML ID | Action on "Create" button |
| `quick_create` | `'quick'` / `'lazy'` | Quick create behavior |
| `lazy` | `'lazy'` | Lazy-load large groups |
| `records_limit` | integer | Max records per column before scroll |
| `decoration-*` | Python expression | Conditional CSS coloring |
| `color` | field name | Map field value to color palette |

---

## Quick Reference: Kanban JS Events

| Event | Handler | Trigger |
|-------|---------|---------|
| `record dropped` | `onRecordDragAndDrop(record, column)` | Drag record to new column |
| `column reordered` | `onColumnDragAndDrop(col1, col2)` | Drag column header |
| `quick create` | `onQuickCreate(data, column)` | Submit inline create form |
| `record clicked` | GlobalClickRecord | Click card body |
| `button clicked` | stopPropagation + action | Click button in card |
| `column fold` | `column.toggle()` | Click column header |

---

## Common Kanban Pitfalls

### Pitfall 1: `default_group_by` on Non-Groupable Field

```xml
<!-- WRONG: Char/Text fields cannot be grouped -->
<kanban default_group_by="description">
    <!-- Odoo will fail or group by a limited set -->

<!-- CORRECT: Use fields that have a Many2one or Selection type -->
<kanban default_group_by="stage_id">
```

### Pitfall 2: Missing `<field name="stage_id"/>` Inside Kanban

```xml
<!-- WRONG: Group_by field must be listed as a field in the kanban -->
<kanban default_group_by="stage_id">
    <!-- stage_id field must be declared inside -->
    <field name="name"/>
    <!-- Missing: <field name="stage_id"/> -->
```

### Pitfall 3: Template Without `kanban-box`

```xml
<!-- WRONG: Template must be named 'kanban-box' -->
<t t-name="kanban-card">
    <!-- Will not render -->
</t>

<!-- CORRECT: Use exact template name -->
<t t-name="kanban-box">
    <div class="oe_kanban_card">
        <field name="name"/>
    </div>
</t>
```

### Pitfall 4: Slow Kanban with Heavy Computed Fields

```python
# Kanban renders ALL visible records. Heavy computed fields
# in the kanban template cause slow rendering.

# BAD: Computing something expensive per record in the template
<field name="expensive_computed_field"/>  <!-- called for every card -->

# GOOD: Store expensive computed fields or precompute with batch
# in a compute method that handles all records at once.
@api.depends('record_ids')
def _batch_compute_stats(self):
    # Compute in batch for performance
    for record in self:
        record.stats = self._compute_stats_batch(record)
```

---

## Related

- [Core/BaseModel](BaseModel.md) — Models and fields that feed data into Kanban views
- [Core/Fields](Fields.md) — Widgets available: `priority`, `progressbar`, `many2one_avatar_user`
- [Core/API](API.md) — `@api.depends` for fields used in Kanban decorations
- [Modules/CRM](CRM.md) — crm.lead pipeline as canonical Kanban example
- [Modules/Project](Project.md) — project.task kanban with stage management
- [Modules/Stock](Stock.md) — stock.picking kanban with quick transfer
- [Snippets/Model Snippets](Model%20Snippets.md) — State machine models that power Kanban views
- [Snippets/Wizard-Deep-Dive](Snippets/Wizard-Deep-Dive.md) — Wizards triggered from Kanban action buttons
