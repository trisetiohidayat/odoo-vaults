---
Module: board
Version: Odoo 18
Type: Integration
Tags: [board, dashboard, custom-view, ir.ui.view.custom, odoo-web]
---

# board — Personal Dashboard ("My Dashboard")

## Overview

The `board` module implements Odoo's **personalizable dashboard** — a per-user layout of embedded action tiles rendered in the web client. It is the technical engine behind the *My Dashboard* menu entry (`spreadsheet_dashboard` parent menu).

> **Key distinction:** Odoo's standard dashboard reports (e.g., Sales Dashboard, MRP Dashboard) are pre-built saved views in their respective apps. The `board` dashboard is a user-specific, freely arranged collection of any action the user chooses to pin — driven by `<board>` XML layout and the `ir.ui.view.custom` custom-view mechanism.

**Depends:** `spreadsheet_dashboard` (provides the menu root)
**Category:** Productivity
**License:** LGPL-3

---

## Architecture

```
board.board (AbstractModel, _auto=False)
  └─ get_view(view_id, view_type)   ← overrides ORM get_view
  └─ _arch_preprocessing(arch)     ← injects js_class='board'
  └─ BoardArchParser (JS)           ← parses <board>/<column>/<action> XML
  └─ BoardController (JS)          ← drag-drop, layout switch, saveBoard()

ir.ui.view.custom
  └─ user_id, ref_id, arch         ← stores per-user custom board XML
BoardAction (JS)
  └─ embeds any ir.actions.act_window inside a board tile
```

---

## Model: `board.board`

**File:** `addons/board/models/board.py`

### Class Definition

```python
class Board(models.AbstractModel):
    _name = 'board.board'
    _description = "Board"
    _auto = False
```

`board.board` is an **abstract model** — it has no database table. It exists purely as a view container for the personal dashboard.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | `fields.Id()` | Dummy field required for web client form initialization (onchange requires an id) |

### Key Methods

#### `get_view(view_id=None, view_type='form', **options)`

Overrides `models.AbstractModel.get_view()` to support custom per-user board layouts.

```python
@api.model
def get_view(self, view_id=None, view_type='form', **options):
    res = super().get_view(view_id, view_type, **options)
    custom_view = self.env['ir.ui.view.custom'].sudo().search([
        ('user_id', '=', self.env.uid),
        ('ref_id', '=', view_id)
    ], limit=1)
    if custom_view:
        res.update({
            'custom_view_id': custom_view.id,
            'arch': custom_view.arch,
        })
    res['arch'] = self._arch_preprocessing(res['arch'])
    return res
```

**Logic:**
1. Look up `ir.ui.view.custom` record matching current user and base view id (`ref_id`)
2. If found, replace arch with the user's personalized arch
3. Pass through `_arch_preprocessing` before returning

#### `_arch_preprocessing(arch)`

```python
@api.model
def _arch_preprocessing(self, arch):
    from lxml import etree
    def remove_unauthorized_children(node):
        for child in node.iterchildren():
            if child.tag == 'action' and child.get('invisible'):
                node.remove(child)
            else:
                remove_unauthorized_children(child)
        return node
    archnode = etree.fromstring(arch)
    # Inject js_class='board' to force BoardView instead of FormView
    archnode.set('js_class', 'board')
    return etree.tostring(remove_unauthorized_children(archnode), pretty_print=True, encoding='unicode')
```

**What it does:**
- Injects `js_class="board"` attribute on the root `<form>` node — this makes the web client instantiate `BoardView` instead of the standard `FormView`
- Recursively removes any `<action>` tags with `invisible="1"` (security: don't show actions the user can't access)
- Returns the processed arch as a unicode XML string

#### `create(vals_list)`

```python
@api.model_create_multi
def create(self, vals_list):
    return self
```

Override returns an empty recordset — board has no real records to create. The "record" the web client sees is always the singleton board singleton.

---

## XML Board Layout Structure

**File:** `addons/board/views/board_views.xml`

### Default View (noupdate=1)

```xml
<record model="ir.ui.view" id="board_my_dash_view">
    <field name="name">My Dashboard</field>
    <field name="model">board.board</field>
    <field name="arch" type="xml">
        <form string="My Dashboard">
            <board style="2-1">
                <column>
                </column>
            </board>
        </form>
    </field>
</record>
```

### Default Action

```xml
<record model="ir.actions.act_window" id="open_board_my_dash_action">
    <field name="name">My Dashboard</field>
    <field name="res_model">board.board</field>
    <field name="view_mode">form</field>
    <field name="context">{'disable_toolbar': True}</field>
    <field name="usage">menu</field>
    <field name="view_id" ref="board_my_dash_view"/>
</record>
```

### Board Style Attribute

The `style` attribute on `<board>` controls column layout:

| Style | Columns | Description |
|-------|---------|-------------|
| `"1"` | 1 | Single column |
| `"1-1"` | 2 | Two equal columns |
| `"2-1"` | 3 | Wide left (2/3), narrow right (1/3) — **default in empty board** |
| `"1-2"` | 3 | Narrow left (1/3), wide right (2/3) |

When changing layout via `selectLayout()` in `BoardController`, actions from dropped columns are migrated to the last visible column before the column count shrinks.

### `<action>` Element Attributes

When a user adds an item via "Add to board", the controller (`board/controllers/main.py`) writes an `<action>` element with:

```xml
<action
    name="[action_id]"           <!-- ir.actions.act_window database ID -->
    string="[display_name]"      <!-- Tile title -->
    view_mode="[list/graph/pivot/...]"  <!-- View type -->
    context="[serialized_context]"
    domain="[serialized_domain]"
    fold="0|1"                   <!-- Initially collapsed? -->
/>
```

---

## Storage: `ir.ui.view.custom`

Custom board layouts are stored in `ir.ui.view.custom`, not in the original view's arch.

| Field | Type | Purpose |
|-------|------|---------|
| `user_id` | `res.users` | Owner of this customization |
| `ref_id` | `ir.ui.view` | Base view being customized (here: `board_my_dash_view` id) |
| `arch` | `text` | Full board XML arch with added `<action>` elements |

**Security:** Custom views are private — only the creating user sees them.

---

## Controller: `add_to_dashboard`

**File:** `addons/board/controllers/main.py`

```python
@route('/board/add_to_dashboard', type='json', auth='user')
def add_to_dashboard(self, action_id, context_to_save, domain, view_mode, name=''):
    action = request.env.ref('board.open_board_my_dash_action').sudo()
    if action and action['res_model'] == 'board.board' and action['views'][0][1] == 'form' and action_id:
        view_id = action['views'][0][0]
        board_view = request.env['board.board'].get_view(view_id, 'form')
        if board_view and 'arch' in board_view:
            board_arch = ElementTree.fromstring(board_view['arch'])
            column = board_arch.find('./board/column')
            if column is not None:
                # Strip allowed_company_ids to avoid multi-company filtering issues
                if 'allowed_company_ids' in context_to_save:
                    context_to_save.pop('allowed_company_ids')
                new_action = ElementTree.Element('action', {
                    'name': str(action_id),
                    'string': name,
                    'view_mode': view_mode,
                    'context': str(context_to_save),
                    'domain': str(domain)
                })
                column.insert(0, new_action)
                arch = ElementTree.tostring(board_arch, encoding='unicode')
                request.env['ir.ui.view.custom'].sudo().create({
                    'user_id': request.session.uid,
                    'ref_id': view_id,
                    'arch': arch
                })
                return True
    return False
```

**What it does:**
1. Loads the current user's board view (with any existing custom tiles)
2. Appends a new `<action>` element inside the first `<column>` of the `<board>`
3. Writes the updated arch to `ir.ui.view.custom` for the current user

---

## Frontend: JavaScript Architecture

### BoardArchParser (`board/static/src/board_view.js`)

```javascript
export class BoardArchParser {
    parse(arch, customViewId) {
        // Returns archInfo:
        // { title, layout, colNumber, isEmpty, columns: [{ actions: [...] }, ...], customViewId }
        // Parses <board style="..."> → colNumber = style.split("-").length
        // Parses <action name="..." string="..." view_mode="..." domain="..." fold="...">
    }
}
export const boardView = {
    type: "form",        // board is registered as a form view variant
    Controller: BoardController,
    props: (genericProps, view) => {
        const board = new BoardArchParser().parse(arch, info.customViewId);
        return { ...genericProps, className: "o_dashboard", board };
    }
};
registry.category("views").add("board", boardView);
```

The board is registered in the `views` registry with type `"form"` — it is a **form view variant** that uses `BoardController` instead of the standard form controller.

### BoardController (`board/static/src/board_controller.js`)

Manages:
- **Drag-and-drop** via `useSortable` (OWL hook): reorders tiles within and across columns
- **Layout switching**: `selectLayout("1-1")`, `selectLayout("2-1")`, etc.
- **Close tile**: removes a tile from the board with confirmation dialog
- **Fold/unfold**: collapses individual tiles
- **Save board**: serializes the board state back to XML and calls `/web/view/edit_custom` RPC

### BoardAction (`board/static/src/board_action.js`)

Each tile is a `BoardAction` component that embeds a `View` component (list, graph, pivot, kanban, etc.) with:
- `resModel` from the original action
- `viewMode` from the action
- Serialized `context` and `domain` from the stored action XML

### AddToBoard (`board/static/src/add_to_board/add_to_board.js`)

A cog menu entry registered via `cogMenuRegistry`:

```javascript
export const addToBoardItem = {
    Component: AddToBoard,
    groupNumber: 20,
    isDisplayed: ({ config }) => {
        const { actionType, actionId, viewType } = config;
        return actionType === "ir.actions.act_window" && actionId && viewType !== "form";
    },
};
cogMenuRegistry.add("add-to-board", addToBoardItem, { sequence: 10 });
```

Collects context, domain, group_by, order_by from the search model and calls `/board/add_to_dashboard`.

---

## L4: Deep Architecture Notes

### board.board vs. ir.ui.view.custom vs. spreadsheet_dashboard

| Feature | `board.board` | `spreadsheet_dashboard` |
|---------|---------------|------------------------|
| Database table | No (`_auto=False`) | Yes (`spreadsheet.dashboard`) |
| Storage of user layout | `ir.ui.view.custom` per user | Owns the dashboard model |
| Tile type | Any `ir.actions.act_window` (list, graph, kanban, pivot) | Spreadsheet + KPI cards |
| Layout control | `<board>` XML `<column>` + `<action>` | Spreadsheet grid |
| Customization | Drag-and-drop + "Add to board" | Spreadsheet editor |
| Depends on | `spreadsheet_dashboard` menu | Standalone |
| JS class | `BoardView` (js_class injection) | `SpreadsheetDashboardView` |

### How the board loads a user's custom layout

```
GET /web#menu_id=board_menu
  → loads open_board_my_dash_action (ir.actions.act_window)
  → res_model=board.board, view_mode=form
  → web client calls board.board.get_view(view_id, 'form')
  → get_view searches ir.ui.view.custom WHERE user_id=uid AND ref_id=view_id
  → if found: returns custom arch; else: returns default board view arch
  → _arch_preprocessing injects js_class='board'
  → BoardView instantiated with parsed BoardArchParser result
```

### js_class injection mechanism

In `_arch_preprocessing`, the root `<form>` element gets `js_class="board"` injected via lxml. This overrides the default `form` view widget in the web client, causing `registry.category("views").add("board", boardView)` to be matched. The `boardView` has `type="form"` but uses `BoardController` and `BoardArchParser`.

### Why ir.ui.view.custom is used instead of view inheritance

Odoo has two customization mechanisms:
1. **View inheritance** (`<xpath>` modifications in an inherited view): stored in `ir.ui.view` with `inherit_id` — global, affects all users
2. **Custom views** (`ir.ui.view.custom`): per-user overrides stored separately — does not pollute the global view

Board uses mechanism #2 because each user has their own unique arrangement of action tiles. Storing this in `ir.ui.view` would either overwrite other users' layouts or require complex inheritance chains.

### Custom view editing RPC

When a user reorders tiles, `BoardController.saveBoard()` calls:

```javascript
rpc("/web/view/edit_custom", {
    custom_id: this.board.customViewId,
    arch,  // XML string of board with new action order
});
```

This maps to `ir.ui.view.custom`'s write method (or create if first time).

### Security: invisible action filtering

`_arch_preprocessing` recursively removes any `<action>` tags with `invisible="1"`. This prevents users from seeing dashboard tiles for actions they do not have access to.

### Drag-drop cross-column reordering

Uses OWL's `useSortable` with `groups: ".o-dashboard-column"` — allows dragging tiles between columns. On drop:
1. Splice action from source column
2. Insert at target position
3. Call `saveBoard()` to persist new order

---

## Cron / Scheduling

No scheduled jobs — board is purely on-demand, rendered when the user opens My Dashboard.

---

## Related Models

| Model | Role |
|-------|------|
| `board.board` | Dashboard container (abstract) |
| `ir.ui.view.custom` | Per-user custom board XML storage |
| `ir.actions.act_window` | Action definitions for each dashboard tile |
| `spreadsheet.dashboard` | Related dashboard menu root (parent of board menu item) |