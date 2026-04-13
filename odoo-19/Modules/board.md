---
type: module
module: board
tags: [odoo, odoo19, dashboard, productivity, views, owl]
created: 2026-04-06
updated: 2026-04-11
---

# board — Dashboards

> **Module:** `board` | **Category:** Productivity | **License:** LGPL-3 | **Sequence:** 225
> **Depends:** `spreadsheet_dashboard` | **Version:** 1.0 | **Author:** Odoo S.A.
> **Source:** `~/odoo/odoo19/odoo/addons/board/`

---

## What is board?

The `board` module gives every authenticated user a personal dashboard. Users build dashboards by adding list, graph, pivot, kanban, or calendar views to their board, then arranging and folding individual tiles. All layout data is stored per-user in `ir.ui.view.custom` — `board.board` creates **no database table**.

The board's "My Dashboard" menu item is nested under `spreadsheet_dashboard`'s root menu, which is the primary Odoo 19 structural change from Odoo 18.

---

## Module Dependency Chain

```
spreadsheet_dashboard
  └── board  (My Dashboard menu item, sequence 100)
```

The `spreadsheet_dashboard` module must be installed for the board menu to appear. The board module provides the legacy tile-based dashboard; `spreadsheet_dashboard` provides the modern spreadsheet-based dashboards. Both live under the same root menu.

---

## Models

### `board.board` — Board (AbstractModel)

**File:** `models/board.py`

```python
from odoo import api, fields, models

class BoardBoard(models.AbstractModel):
    _name = 'board.board'
    _description = "Board"
    _auto = False
```

| Property | Value |
|---|---|
| `_name` | `board.board` |
| `_description` | `"Board"` |
| `_auto` | `False` — no DB table, no ORM records |
| Inheritance | `models.AbstractModel` |

#### Why Abstract?

`board.board` inherits from `AbstractModel`, not `models.Model`. `_auto = False` tells the ORM to skip table creation. The model exists purely as a form view routing target. It has no business logic of its own — all data is in `ir.ui.view.custom`.

#### Fields

| Field | Type | Purpose |
|---|---|---|
| `id` | `fields.Id()` | Synthetic primary key. Required by the web client's `onchange()` machinery when initializing a dummy record for any form view. Without it, the client cannot bootstrap the form. No DB column exists. |

#### `create(self, vals_list) → empty recordset`

```python
@api.model_create_multi
def create(self, vals_list):
    return self
```

Overrides `create()` to return `self` (an empty recordset) without persisting anything. Exists purely to satisfy the ORM contract. No board record is ever stored — all layout data goes into `ir.ui.view.custom`.

#### `get_view(view_id=None, view_type='form', **options) → dict`

```python
@api.model
def get_view(self, view_id=None, view_type='form', **options):
    res = super().get_view(view_id, view_type, **options)
    custom_view = self.env['ir.ui.view.custom'].sudo().search(
        [('user_id', '=', self.env.uid), ('ref_id', '=', view_id)], limit=1
    )
    if custom_view:
        res.update({'custom_view_id': custom_view.id, 'arch': custom_view.arch})
    res['arch'] = self._arch_preprocessing(res['arch'])
    return res
```

**Step-by-step:**
1. Calls parent `get_view()` to fetch the base XML from `ir.ui.view` (the `board_my_dash_view` record).
2. Searches `ir.ui.view.custom` for a record matching `(user_id=self.env.uid, ref_id=view_id)`. If found, replaces the `arch` key with the user's saved version.
3. Passes the resolved (base or custom) arch through `_arch_preprocessing()`.
4. Returns the full view descriptor dict (arch, fields, toolbar).

**`sudo()` usage:** The board model runs as the current user; `ir.ui.view.custom` records for other users are not readable by non-admin users. `sudo()` is the only way to fetch a user's own custom view during the get_view call.

#### `_arch_preprocessing(arch) → str`

```python
@api.model
def _arch_preprocessing(self, arch):
    def remove_unauthorized_children(node):
        for child in node.iterchildren():
            if child.tag == 'action' and child.get('invisible'):
                node.remove(child)
            else:
                remove_unauthorized_children(child)
        return node

    archnode = etree.fromstring(arch)
    archnode.set('js_class', 'board')
    return etree.tostring(
        remove_unauthorized_children(archnode),
        pretty_print=True, encoding='unicode'
    )
```

**Two effects:**

1. **Injects `js_class="board"`** onto the `<form>` root node. The web client uses `js_class` to select the view registry entry — this routes the form view to `BoardController` (OWL) instead of the legacy `FormView`. This is the routing mechanism; no separate view type is needed.
2. **Recursively strips `<action>` nodes with `invisible="1"`** — invisible actions are not rendered as tiles. This is a display-only filter; the actions remain in the stored XML.

---

## Controller Endpoint

### `POST /board/add_to_dashboard` — Add View to Dashboard

**File:** `controllers/main.py`

```python
from lxml import etree as ElementTree
from odoo.http import Controller, route, request

class Board(Controller):
    @route('/board/add_to_dashboard', type='jsonrpc', auth='user')
    def add_to_dashboard(self, action_id, context_to_save, domain, view_mode, name=''):
```

**Request parameters:**

| Parameter | Type | Description |
|---|---|---|
| `action_id` | `int` | DB ID of `ir.actions.act_window` to embed |
| `context_to_save` | `dict` | Session context to restore when tile loads |
| `domain` | `list` | Filter domain (array format) |
| `view_mode` | `str` | View type for tile, e.g., `"list"`, `"graph"` |
| `name` | `str` | Display title for the dashboard tile |

**Precondition check:**
```python
if (action and action['res_model'] == 'board.board'
    and action['views'][0][1] == 'form'   # first view must be form
    and action_id):
```

The endpoint only writes to the board's own "My Dashboard" action. It validates `res_model == 'board.board'` and `views[0][1] == 'form'` as a safety gate. Any other action fails silently, returning `False`.

**`allowed_company_ids` stripping:**
```python
if 'allowed_company_ids' in context_to_save:
    context_to_save.pop('allowed_company_ids')
```

Included in the saved context, the multi-company switcher widget would always filter to the company active when the tile was added, ignoring subsequent switches. Stripping it lets the widget work normally on the dashboard.

**Persistence — upsert into `ir.ui.view.custom`:**
```python
request.env['ir.ui.view.custom'].sudo().create({
    'user_id': request.session.uid,
    'ref_id': view_id,
    'arch': arch
})
```

This is a **create-only**, not an upsert. If a user adds a second tile, a new `ir.ui.view.custom` record is created. The model's unique constraint on `(user_id, ref_id)` will raise an error on the second create. In practice, Odoo's view customization system handles this by using a `write` when the record already exists, but this controller does not check — it always calls `create()`.

**Failure modes:**

| Condition | Result |
|---|---|
| XMLID `board.open_board_my_dash_action` missing | Returns `False` |
| Board form view has no `<column>` | Returns `False` |
| `ir.ui.view.custom` write fails (ACL) | Returns `False` |
| `action_id` is `0` or falsy | Returns `False` |

---

## Data: Views, Actions, Menu

**File:** `views/board_views.xml`

```xml
<!-- base dashboard view: 2-column layout (2fr : 1fr), one empty <column> -->
<record model="ir.ui.view" id="board_my_dash_view">
    <field name="name">My Dashboard</field>
    <field name="model">board.board</field>
    <field name="arch" type="xml">
        <form string="My Dashboard">
            <board style="2-1">
                <column/>
            </board>
        </form>
    </field>
</record>

<!-- window action — the routing entry point -->
<record model="ir.actions.act_window" id="open_board_my_dash_action">
    <field name="name">My Dashboard</field>
    <field name="res_model">board.board</field>
    <field name="view_mode">form</field>
    <field name="context">{'disable_toolbar': True}</field>
    <field name="usage">menu</field>
    <field name="view_id" ref="board_my_dash_view"/>
</record>

<!-- menu under spreadsheet_dashboard root, sequence 100 -->
<menuitem id="menu_board_my_dash"
    name="My Dashboard"
    parent="spreadsheet_dashboard.spreadsheet_dashboard_menu_root"
    action="open_board_my_dash_action"
    sequence="100"/>
```

**Key decisions:**
- `view_mode: form` — board only has a form representation; this is required.
- `context: {'disable_toolbar': True}` — suppresses the standard form control panel (search bar, filters, favorites) since the dashboard has its own toolbar UI.
- `usage: menu` — marks this as a top-level menu entry in the navigation system.
- `noupdate="1"` — base view is not reinstalled on module upgrade; user customizations in `ir.ui.view.custom` are preserved.

---

## Security

**File:** `security/ir.model.access.csv`

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_board_board_all,board.board,model_board_board,base.group_user,1,0,0,0
```

| Permission | Value | Reason |
|---|---|---|
| `perm_read` | `1` | All authenticated users need read to render their dashboard |
| `perm_write` | `0` | Dashboard writes are controller-mediated via `/board/add_to_dashboard` |
| `perm_create` | `0` | No direct ORM create; `board.board` has `_auto=False` anyway |
| `perm_unlink` | `0` | No direct unlink |

**Why no write ACL?** Dashboard persistence goes through the JSON-RPC controller endpoint (`/board/add_to_dashboard`). The controller writes directly to `ir.ui.view.custom`, keyed on `request.session.uid`. Even if a user had ORM write access to `board.board`, the model's `create()` is a no-op — nothing would be persisted.

**Security boundary:** A malicious user calling `/board/add_to_dashboard` with arbitrary `action_id` values could embed any `ir.actions.act_window` into their own dashboard. However, the embedded tile still enforces normal `ir.rule` record-level ACLs when rendering data — the dashboard does not grant any additional read access to model records.

---

## Frontend Architecture (OWL)

All frontend code is pure OWL (`@odoo/owl`) — no legacy Backbone.

### View Registry Entry

**File:** `static/src/board_view.js`

```javascript
import { registry } from "@web/core/registry";
import { BoardController } from "./board_controller";
import { visitXML } from "@web/core/utils/xml";
import { Domain } from "@web/core/domain";

export class BoardArchParser {
    parse(arch, customViewId) {
        // visits <form>, <board style="N-N">, <column>, <action ...>
        // Returns archInfo object consumed by BoardController props
    }
}

export const boardView = {
    type: "form",       // matches view_type='form' from the window action
    Controller: BoardController,
    props: (genericProps, view) => {
        const { arch, info } = genericProps;
        const board = new BoardArchParser().parse(arch, info.customViewId);
        return { ...genericProps, className: "o_dashboard", board };
    },
};

registry.category("views").add("board", boardView);
```

The board registers as `"board"` in the view registry. Because the action uses `view_type='form'` and the registry entry also has `type: "form"`, the web client picks this entry. The `js_class="board"` injected by `_arch_preprocessing()` on the form root is what actually triggers the selection — the registry matcher compares `js_class` against available view types.

### BoardArchParser — XML → Board State

```javascript
class BoardArchParser {
    parse(arch, customViewId) {
        // Initializes: { title, layout, colNumber, isEmpty,
        //               columns: [actions[], actions[], actions[]],
        //               customViewId }
        // visitXML iterates:
        //   <form string="...">       → title
        //   <board style="2-1">       → layout + colNumber (split("-").length)
        //   <column>                  → increment currentIndex
        //   <action name="42" string="Sales" view_mode="list" ...>
        //       → action object appended to columns[currentIndex].actions
    }
}
```

`colNumber` is derived from the dash-separated parts of the `style` attribute. A `style="1-1-1"` board has `colNumber = 3`. The `columns` array always has 3 slots; only the first `colNumber` are rendered.

The `<action>` tag's `domain` attribute is parsed as a `Domain` object and attached with a `toString()` method so it can be serialized back to XML string form when saving.

### BoardController — Dashboard Orchestration

**File:** `static/src/board_controller.js`

```javascript
export class BoardController extends Component {
    static template = "board.BoardView";
    static components = { BoardAction, Dropdown, DropdownItem };
    static props = { ...standardViewProps, board: Object };

    setup() {
        this.board = useState(this.props.board);  // reactive copy

        if (this.env.isSmall) {
            this.selectLayout("1", false);  // single-column on mobile
        } else {
            useSortable({
                ref: mainRef,
                elements: ".o-dashboard-action",
                handle: ".o-dashboard-action-header",
                groups: ".o-dashboard-column",
                connectGroups: true,
                onDrop: ({ element, previous, parent }) => {
                    const fromColIdx = parseInt(element.parentElement.dataset.idx, 10);
                    const fromActionIdx = parseInt(element.dataset.idx, 10);
                    const toColIdx = parseInt(parent.dataset.idx, 10);
                    const toActionIdx = previous
                        ? parseInt(previous.dataset.idx, 10) + 1 : 0;
                    this.moveAction(fromColIdx, fromActionIdx, toColIdx, toActionIdx);
                },
            });
        }
    }
}
```

**`moveAction()` logic (cross-column vs. within-column):**
- **Cross-column:** `splice(1)` removes from source, `splice(0, action)` inserts into target.
- **Within-column (higher index to lower):** `splice(fromIdx, 1)` then `splice(toIdx, 0, action)`.
- **Within-column (lower index to higher):** `splice(toIdx+1, 0, action)` then `splice(fromIdx, 1)` — inserting at the target position first avoids index shift.
- No-op if `fromColIdx === toColIdx && fromActionIdx === toActionIdx`.

**`selectLayout(newLayout)` logic:**
- If `nextColNbr < currentColNbr` (reducing columns), all actions from removed columns are appended to `cols[nextColNbr - 1]` before the layout switch.
- Chart canvas resize: `browser.requestAnimationFrame(() => this.render(true))` forces canvas-based charts to re-read their container dimensions after CSS grid changes.

**`saveBoard()` serialization:**
```javascript
saveBoard() {
    const templateFn = renderToString.app.getTemplate("board.arch");
    const bdom = templateFn(this.board, {});
    const root = document.createElement("rendertostring");
    blockDom.mount(bdom, root);
    const result = xmlSerializer.serializeToString(root);
    const arch = result.slice(result.indexOf("<", 1), result.indexOf("</rendertostring>"));

    rpc("/web/view/edit_custom", {
        custom_id: this.board.customViewId,
        arch,
    });
    rpcBus.trigger("CLEAR-CACHES");
}
```

The `board.arch` template renders a `<form>` with a `<board style="...">` containing `<column>` elements, each with `<action>` children. The `arch` string is the full XML — not a JSON blob. The `/web/view/edit_custom` endpoint (from `web` module) handles the actual `ir.ui.view.custom` write. `rpcBus.trigger("CLEAR-CACHES")` invalidates the Odoo web client view cache so the updated arch is picked up on subsequent navigation.

### BoardAction — Individual Tile

**File:** `static/src/board_action.js`

```javascript
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";
import { makeContext } from "@web/core/context";
import { user } from "@web/core/user";
import { Component, onWillStart } from "@odoo/owl";

export class BoardAction extends Component {
    static template = "board.BoardAction";
    static components = { View };
    static cache = {};  // class-level (shared across all instances in this tab)

    setup() {
        onWillStart(async () => {
            let result = BoardAction.cache[action.actionId];
            if (!result) {
                result = await rpc("/web/action/load", { action_id: action.actionId });
                BoardAction.cache[action.actionId] = result;
            }
            if (!result) { this.isValid = false; return; }

            const viewMode = action.viewMode || result.views[0][1];
            const formView = result.views.find(v => v[1] === "form");
            this.formViewId = formView ? formView[0] : false;

            this.viewProps = {
                resModel: result.res_model,
                type: viewMode,
                display: { controlPanel: false },
                selectRecord: (resId) => this.selectRecord(result.res_model, resId),
            };
            const view = result.views.find(v => v[1] === viewMode);
            if (view) this.viewProps.viewId = view[0];
            const searchView = result.views.find(v => v[1] === "search");
            this.viewProps.views = [
                [this.viewProps.viewId || false, viewMode],
                [(searchView && searchView[0]) || false, "search"],
            ];
            if (action.context) {
                this.viewProps.context = makeContext([action.context, { lang: user.context.lang }]);
                if ("group_by" in this.viewProps.context) {
                    const groupBy = this.viewProps.context.group_by;
                    this.viewProps.groupBy = typeof groupBy === "string" ? [groupBy] : groupBy;
                }
            }
            if (action.domain) this.viewProps.domain = action.domain;
            if (viewMode === "list") this.viewProps.allowSelectors = false;
        });
    }
}
```

**Class-level cache behavior:** `BoardAction.cache` is a static property on the class — shared across every `BoardAction` instance in the browser tab. Loading an action definition via `/web/action/load` is an RPC call; deduplication matters. Cache key is the integer `actionId`. The cache persists for the lifetime of the browser tab.

**Edge case — missing form view:** If `formView` is not found in `result.views`, `formViewId` is `false`. `selectRecord()` then calls `doAction` with no `view_id`, and the web client uses the default form view for the model. No error is raised.

**Edge case — deleted action:** If `/web/action/load` returns falsy (action does not exist or access denied), `isValid = false` and the tile renders "Invalid action" (warning div).

**`group_by` context handling:** The `group_by` key is extracted from the saved `action.context` and moved to `viewProps.groupBy` as an array, which the list/graph renderer reads to pre-group records.

### AddToBoard — Cog Menu Component

**File:** `static/src/add_to_board/add_to_board.js`

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

**Displayed for:** list, graph, pivot, kanban, calendar views on window actions.
**Not displayed for:** form views (would have no meaning on a dashboard), non-window actions (wizards, reports, server actions).

**`addToBoard()` context construction:**
```javascript
const contextToSave = {
    ...Object.fromEntries(
        Object.entries(globalContext).filter(
            entry => !entry[0].startsWith("search_default_")
        )
    ),
    ...context,                          // current search values
    orderedBy: orderBy,
    group_by: groupBys,
    dashboard_merge_domains_contexts: false,  // prevent domain merging
};
```

`dashboard_merge_domains_contexts: false` is the critical flag. Without it, the web client would combine the saved `domain` with any active search filter at render time, producing unexpected results. Setting it to `false` ensures the tile respects only its saved domain.

The `search_default_*` keys are stripped — these represent "default filters" from the URL or previous searches, not user-intentional filters to save.

**RPC call:**
```javascript
await rpc("/board/add_to_dashboard", {
    action_id: this.env.config.actionId || false,
    context_to_save: contextToSave,
    domain,
    name: this.state.name,
    view_mode: this.env.config.viewType,
});
```

After success, the notification says "Please refresh your browser for the changes to take effect" — the dashboard is updated in `ir.ui.view.custom` but the current dashboard view may still show stale data until navigation.

---

## Board XML Format

The board uses a custom non-standard XML vocabulary parsed at runtime by `BoardArchParser` (JS) and serialized by the Python controller.

```xml
<form string="My Dashboard">
    <board style="2-1">
        <column>
            <action name="42" string="Sales Graph" view_mode="graph,list"
                context="{...}" domain="[('state', '=', 'done')]" fold="0"/>
        </column>
        <column>
            <action name="87" string="Partners" view_mode="list" context="{}" domain="[]"/>
        </column>
    </board>
</form>
```

**`<action>` attributes:**

| Attribute | Type | Stored as | Purpose |
|---|---|---|---|
| `name` | int | `"42"` | Action ID to embed |
| `string` | str | `"Sales Graph"` | Tile header title |
| `view_mode` | str | `"graph,list"` | Comma-separated view types |
| `context` | str | `"{...}"` | JSON dict string, deserialized on tile load |
| `domain` | str | `"[('state', '=', 'done')]"` | Domain expression string |
| `fold` | str | `"0"` or `"1"` | Folded state (0=expanded, 1=collapsed) |

---

## Layout Styles (CSS Grid)

**File:** `static/src/board_controller.scss`

| Style | Grid columns | CSS class |
|---|---|---|
| `1` | `1fr` | `.o-dashboard-layout-1` |
| `1-1` | `1fr 1fr` | `.o-dashboard-layout-1-1` |
| `1-1-1` | `1fr 1fr 1fr` | `.o-dashboard-layout-1-1-1` |
| `1-2` | `1fr 2fr` | `.o-dashboard-layout-1-2` |
| `2-1` | `2fr 1fr` | `.o-dashboard-layout-2-1` |

All layouts use CSS `display: grid`. Column overflow is `overflow-x: scroll`. Tile content max-height is `80vh` with `overflow: auto`. Graph canvas height is forced to `300px`; calendar wrapper height is `400px`.

---

## Odoo 18 → Odoo 19 Changes

| Area | Odoo 18 | Odoo 19 |
|---|---|---|
| Dependency | `depends: ['base']` | `depends: ['spreadsheet_dashboard']` |
| Menu parent | Standalone root menu | Under `spreadsheet_dashboard_menu_root` |
| Frontend framework | Backbone / FormView | OWL (`BoardController`, `BoardAction`) |
| Add to board UX | Dropdown in search bar | Cog menu (favorites panel) |
| Board arch serialization | JSON blob | XML via `renderToString` + `blockDom` |
| Custom view persistence | Direct ORM write | `/web/view/edit_custom` JSON-RPC |
| Layout change | Server-side view update | Client-side drag + save |
| `group_by` in context | Not handled | Extracted and passed to view props |

---

## Performance Considerations

| Concern | Detail |
|---|---|
| `BoardAction.cache` | Class-level action definition cache prevents redundant `/web/action/load` RPCs. One RPC per unique `actionId` per browser tab. |
| Chart resize hack | `browser.requestAnimationFrame(() => this.render(true))` after layout change forces canvas-based chart redraw at correct dimensions. Without it, charts in a 3-column grid may render at 1-column width. |
| `CLEAR-CACHES` | `rpcBus.trigger("CLEAR-CACHES")` invalidates the web client view cache so the saved arch is picked up without a full page reload. |
| `ir.ui.view.custom` lookup | `get_view()` always searches for a custom view on every dashboard load — one extra DB query per page load. |
| Arch parsing | `BoardArchParser` iterates the full arch XML on every `get_view()` call — O(n) in tile count. Not cached server-side. |
| Multiple tiles with same action | All instances share the same `BoardAction.cache` entry; only the first tile per action type triggers a `/web/action/load` RPC. |
| `useSortable()` | Enabled only when `!env.isSmall`. On mobile, the board renders in single-column layout without drag handles. |

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Action deleted after adding to dashboard | `/web/action/load` returns falsy. `BoardAction` sets `isValid = false`. Dashboard renders "Invalid action" warning. No crash. |
| Embedded action has no form view | `formViewId` is `false`. `selectRecord()` opens the default form view (no `view_id` in `doAction`). |
| `allowed_company_ids` in saved context | Stripped in controller before saving. Dashboard respects current multi-company switcher state. |
| Empty dashboard (no tiles) | `BoardArchParser` sets `isEmpty = true` when no `<action>` tags are found. `BoardController` renders `board.NoContent` template with setup instructions. |
| Drag from wider to narrower column | `moveAction()` splices the action reference into the new column. `saveBoard()` serializes the full arch — actions in overflow columns are included. |
| Reduce columns (3→1) | `selectLayout()` appends all actions from removed columns into `cols[0]` before switching layout. No data loss. |
| Second tile added by same user | `ir.ui.view.custom` create may violate `(user_id, ref_id)` unique constraint. In practice, the board_arch is updated atomically so the second write succeeds. |
| Concurrent edits (two browser tabs) | Last-write-wins on `ir.ui.view.custom`. No optimistic locking. |
| `view_mode` not in action's views list | `BoardAction` falls back to `result.views[0][1]` (the first available view type). No error. |
| `search_default_*` keys in context | Stripped before saving. These are session defaults, not user-selected filters. |
| `domain` string with special chars | Stored as raw XML attribute string. Parsed by `new Domain(domain).toList()` in `BoardArchParser`. Invalid domain syntax would cause a parse error on dashboard load. |

---

## Cross-Module Integration Map

```
board.board (Python model)
  └── get_view() reads ir.ui.view.custom (per-user) + ir.ui.view (base)
  └── _arch_preprocessing() → injects js_class="board"

/board/add_to_dashboard (Controller)
  └── env.ref('board.open_board_my_dash_action')  → validates target
  └── board.board.get_view()  → reads base arch to locate <column>
  └── ir.ui.view.custom.create()  → persists user's board XML

BoardController (OWL, static/src/board_controller.js)
  └── /web/view/edit_custom  → saves board XML (from web module)
  └── rpcBus.trigger('CLEAR-CACHES')

BoardAction (OWL, static/src/board_action.js)
  └── /web/action/load  → loads embedded action definition (once per actionId)
  └── BoardAction.cache  → class-level deduplication
  └── makeContext()  → merges saved context with user language

AddToBoard (OWL, cog menu, static/src/add_to_board/add_to_board.js)
  └── /board/add_to_dashboard
  └── this.env.searchModel  → reads domain, context, groupBy, orderBy
  └── cogMenuRegistry  → registered at sequence 10

spreadsheet_dashboard
  └── provides parent menu root for board menu item
```

---

## Static Assets

| File | Purpose |
|---|---|
| `static/src/board_view.js` | View registry entry + `BoardArchParser` |
| `static/src/board_controller.js` | `BoardController` OWL component + `saveBoard()`, `moveAction()`, `selectLayout()` |
| `static/src/board_action.js` | `BoardAction` OWL component (per-tile) |
| `static/src/board_action.xml` | Template: renders `<View>` or "Invalid action" |
| `static/src/board_controller.xml` | BoardView template, NoContent template, `board.arch` serialization template |
| `static/src/board_controller.scss` | CSS grid layouts, tile styling, scroll behavior |
| `static/src/add_to_board/add_to_board.js` | `AddToBoard` cog menu component |
| `static/src/add_to_board/add_to_board.xml` | Dropdown UI with SVG dashboard icon |
| `static/img/layout_*.png` | Layout selector thumbnails (1, 1-1, 1-1-1, 1-2, 2-1) |
| `static/tests/add_to_dashboard.test.js` | Unit tests for AddToBoard cog menu flow |
| `static/tests/board.test.js` | Integration tests for dashboard rendering |

---

## Related

- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Modern spreadsheet-based dashboards (parent menu root)
- [Modules/web](Modules/web.md) — Web client view registry, `/web/view/edit_custom` endpoint
- [Core/HTTP Controller](Core/HTTP-Controller.md) — Odoo HTTP route decorators, `auth='user'`
- [Tools/ORM Operations](Tools/ORM-Operations.md) — `ir.ui.view.custom` model, view customization system

---

## Tags

#odoo #odoo19 #modules #dashboard #board #personal-view #ir.ui.view.custom #owl