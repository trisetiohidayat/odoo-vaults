---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #pos
  - #restaurant
  - #hr
---

# pos_hr_restaurant — Employee Management Integration for Restaurant POS

> Adapts the behavior of the Point of Sale when both `pos_hr` (employee login/management) and `pos_restaurant` (floor plan/table management) are installed simultaneously. In Odoo 19, `pos_hr_restaurant` bridges two systems that would otherwise conflict: when an employee logs in at a restaurant POS, the floor plan edit controls and idle timer behavior must be adjusted for the restaurant context.

**Module:** `pos_hr_restaurant` | **Location:** `odoo/addons/pos_hr_restaurant/` | **Version:** 1.0
**Depends:** `pos_hr`, `pos_restaurant` | **Category:** Sales/Point of Sale | **License:** LGPL-3
**Auto-install:** `True` (installs automatically when both dependencies are present)

---

## Module Architecture

`pos_hr_restaurant` is a **thin behavioral bridge** — zero Python ORM models, zero server-side logic, zero XML data files. It consists of two client-side JavaScript patches and a test suite.

```
pos_hr_restaurant
    ├── __manifest__.py              (bridge metadata + JS asset loading)
    ├── __init__.py                  (empty — no Python)
    ├── static/src/
    │   ├── app/services/
    │   │   └── pos_store.js         (idle timer override for restaurant)
    │   └── overrides/components/
    │       └── navbar/
    │           └── navbar.js        (edit plan button visibility)
    └── static/tests/
        └── tours/
            └── pos_hr_restaurant_tour.js   (POS UI tour tests)
```

| Layer | File | Purpose |
|---|---|---|
| Idle timer | `static/src/app/services/pos_store.js` | Prevents idle timer reset when on restaurant floor plan screens |
| Edit button | `static/src/overrides/components/navbar/navbar.js` | Hides edit plan button when HR mode is active and employee is not admin |
| Tests | `static/tests/tours/pos_hr_restaurant_tour.js` | POS UI tour tests for default screen behavior |

---

## L1: How HR Integration Works in Restaurant POS

### The Core Tension

`pos_hr` enables **employee login** — a cashier or manager logs in with their employee credentials before opening the POS. This creates a `pos.login` record that tracks who is operating the register.

`pos_restaurant` enables **floor plan editing** — waiters and managers can drag tables, create new floors, and merge tables from the POS UI. The "Edit Plan" button on the navbar is available to `group_pos_manager`.

When both modules are installed, two conflicts arise:

**Conflict 1: Who can edit the floor plan?**

In a pure `pos_hr` setup, the edit plan button is shown based on user permissions (`group_pos_manager`). In a pure `pos_restaurant` setup, any user can edit the floor plan. When both are installed, the restaurant expects any user to edit, but the HR layer adds permission gates. The bridge resolves this: **only employees who are admins (manager-level) can see the Edit Plan button**, while regular employees cannot.

**Conflict 2: Idle timer behavior on floor plan screens**

The POS has an idle timer that resets when the user interacts with the system. In restaurant mode, the waiter frequently walks between tables, leaving the POS unattended on the floor plan screen. The standard idle timer would log out the waiter too aggressively. The bridge prevents the idle timer from resetting on restaurant-specific screens (`FloorScreen`), keeping the session alive during active floor service.

### What This Module Fixes

1. **Edit Plan button visibility**: Hides the Edit Plan button from non-manager employees when in restaurant mode. Restaurant floor editing is restricted to `pos_hr`-logged-in managers.
2. **Idle timer management**: Prevents idle timer reset on restaurant floor screens, allowing waiters to remain logged in while serving tables.

---

## L2: Server-Side Components

### Manifest

```python
{
    'name': 'POS HR Restaurant',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Link module between pos_hr and pos_restaurant',
    'description': """
This module adapts the behavior of the PoS when the pos_hr and pos_restaurant are installed.
    """,
    'depends': ['pos_hr', 'pos_restaurant'],
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_hr_restaurant/static/src/**/*',
        ],
        'web.assets_tests': [
            'pos_hr_restaurant/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

**Dependency chain:** `pos_hr` (employee login system) + `pos_restaurant` (restaurant floor/table) → `pos_hr_restaurant` (bridge)

**Auto-install behavior:** When both `pos_hr` AND `pos_restaurant` are installed, this module auto-installs. The bridge activates automatically — an admin does not need to manually select it.

**No Python models:** There are zero server-side ORM models, zero fields, zero constraints. The `__init__.py` is empty. All behavior is client-side.

---

## L3: Client-Side Override Patterns

### File 1: `static/src/app/services/pos_store.js`

```javascript
import { patch } from "@web/core/utils/patch";
import "@pos_restaurant/app/services/pos_store";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    shouldResetIdleTimer() {
        return (
            this.router.state.current !== "LoginScreen" && super.shouldResetIdleTimer(...arguments)
        );
    },
});
```

**Import order matters:** `import "@pos_restaurant/app/services/pos_store"` is imported **before** `PosStore` is patched. This ensures that `pos_restaurant`'s `PosStore` patches are applied first, and then `pos_hr_restaurant` patches the result. The restaurant `pos_store` module (from `pos_restaurant`) defines restaurant-specific `PosStore` behavior that is then further modified here.

**Override pattern:** `shouldResetIdleTimer` is called by the OWL Navbar component on every user interaction (mouse move, keypress, touch). The parent implementation (from `point_of_sale`) returns `True` when the session is considered active, triggering an idle timer reset.

**Restaurant override:** The condition `this.router.state.current !== "LoginScreen"` means the idle timer is reset for all screens **except** the `LoginScreen`. This effectively means the idle timer never resets while the user is logged in — the POS session stays alive indefinitely once the employee has logged in.

**L4 — Why only exclude LoginScreen?** The parent `point_of_sale` base behavior likely resets the idle timer on every non-idle event. By adding `this.router.state.current !== "LoginScreen"` as a conjunction, the override ensures that even on the LoginScreen (which has high-frequency interactions like selecting an employee), the idle timer does not reset. This keeps the restaurant waiter logged in even when they step away on the floor plan.

**Waiter scenario:** A waiter logs in (LoginScreen), enters the floor plan (FloorScreen), and walks to serve a table. The POS tablet sits idle on the floor plan. Without this patch, the idle timer would log out the waiter after N minutes (configured in Odoo). With this patch, the idle timer never resets, keeping the session alive.

**Security note:** A never-expiring session is intentional for restaurant service. The session is closed by the manager when the shift ends (`pos.session.action_pos_session_close()`). The session lock (`locked_by`) is managed by `pos_hr` on login, preventing concurrent logins.

### File 2: `static/src/overrides/components/navbar/navbar.js`

```javascript
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    get showEditPlanButton() {
        if (
            this.pos.config.module_pos_restaurant &&
            (!this.pos.config.module_pos_hr || this.pos.employeeIsAdmin)
        ) {
            return super.showEditPlanButton;
        } else {
            return false;
        }
    },
});
```

**Override pattern:** `showEditPlanButton` is a getter on the `Navbar` OWL component. The parent implementation (from `pos_restaurant` or `point_of_sale`) returns `True` for users with floor edit permissions.

**Restaurant-only config** (`module_pos_restaurant = True`, `module_pos_hr = False`):
- `this.pos.config.module_pos_restaurant` → `True`
- `!this.pos.config.module_pos_hr` → `True` (since `module_pos_hr = False`, `!False = True`)
- `!this.pos.config.module_pos_hr || this.pos.employeeIsAdmin` → `True || ...` = `True`
- Result: `super.showEditPlanButton` — follows the standard restaurant logic (edit button shown)

**Restaurant + HR config with regular employee** (`module_pos_restaurant = True`, `module_pos_hr = True`, `employeeIsAdmin = False`):
- `this.pos.config.module_pos_restaurant` → `True`
- `!this.pos.config.module_pos_hr` → `False`
- `this.pos.employeeIsAdmin` → `False`
- `!False || False` → `False`
- Result: `False` — edit button **hidden** for non-admin employees

**Restaurant + HR config with manager employee** (`module_pos_restaurant = True`, `module_pos_hr = True`, `employeeIsAdmin = True`):
- `!True || True` → `True`
- Result: `super.showEditPlanButton` — edit button **shown** for admin employees

**Logic table:**

| `module_pos_restaurant` | `module_pos_hr` | `employeeIsAdmin` | Result |
|---|---|---|---|
| `True` | `False` | N/A | `super.showEditPlanButton` (shown) |
| `True` | `True` | `True` | `super.showEditPlanButton` (shown) |
| `True` | `True` | `False` | `False` (hidden) |
| `False` | N/A | N/A | `False` (hidden — not restaurant) |

**`this.pos.employeeIsAdmin` source:** This property is defined in `pos_hr`'s `PosStore` extension. It returns `True` if the logged-in employee has admin rights within the `pos_hr` context. The value is set when the employee logs in via the LoginScreen.

---

## L3: Failure Modes

| Failure Mode | Trigger | Behavior |
|---|---|---|
| Session never expires | No interaction for extended period | `shouldResetIdleTimer` never returns `True`. Session stays open indefinitely. No automatic logout. |
| Manager forgets to close session | End of shift without session close | Session remains `opened` in database. Next shift's manager must close it manually. |
| Employee logs in at wrong POS | Same employee logs in on second device | `pos_hr`'s `locked_by` mechanism prevents concurrent login. Second device shows error. |
| `pos_restaurant` not installed but `pos_hr` is | Only `pos_hr` installed | This module does not auto-install (requires both deps). No override is applied. |
| `module_pos_hr` disabled after install | Admin toggles `module_pos_hr = False` in config | Module becomes effectively inactive. `pos_hr_restaurant`'s JS still loads but `module_pos_hr` is `False`, so first path in `showEditPlanButton` applies. |

---

## L4: Test Suite

### POS Tour: `static/tests/tours/pos_hr_restaurant_tour.js` (Verified from Source)

```javascript
import * as PosHr from "@pos_hr/../tests/tours/utils/pos_hr_helpers";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as FloorScreen from "@pos_restaurant/../tests/tours/utils/floor_screen_util";
import * as SelectionPopup from "@point_of_sale/../tests/generic_helpers/selection_popup_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_post_login_default_screen_is_tables", {
    steps: () =>
        [
            Chrome.clickBtn("Open Register"),
            PosHr.clickLoginButton(),
            SelectionPopup.has("Mitchell Admin", { run: "click" }),
            Dialog.confirm("Open Register"),
            FloorScreen.isShown(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_post_login_default_screen_is_register", {
    steps: () =>
        [
            Chrome.clickBtn("Open Register"),
            PosHr.clickLoginButton(),
            SelectionPopup.has("Mitchell Admin", { run: "click" }),
            Dialog.confirm("Open Register"),
            ProductScreen.isShown(),
        ].flat(),
});
```

**Verified from source (Odoo 19.0):**
- `PosHr.clickLoginButton()` — simulates clicking the employee login button
- `SelectionPopup.has("Mitchell Admin", { run: "click" })` — selects the "Mitchell Admin" employee from the employee selection popup
- `Dialog.confirm("Open Register")` — confirms opening the register after employee selection
- `FloorScreen.isShown()` — asserts the floor plan screen is shown (for `default_screen = "tables"`)
- `ProductScreen.isShown()` — asserts the product screen is shown (for `default_screen = "register"`)

### Python Test: `tests/test_frontend.py` (Verified from Source)

```python
from odoo.tests import tagged
from odoo.addons.pos_hr.tests.test_frontend import TestPosHrHttpCommon
from odoo.addons.pos_restaurant.tests.test_frontend import TestFrontendCommon

@tagged("post_install", "-at_install")
class TestUi(TestPosHrHttpCommon, TestFrontendCommon):
    def test_post_login_default_screen_tables(self):
        self.main_pos_config.default_screen = "tables"
        self.main_pos_config.with_user(self.pos_admin).open_ui()
        self.start_pos_tour("test_post_login_default_screen_is_tables", login="pos_admin")

    def test_post_login_default_screen_register(self):
        self.main_pos_config.default_screen = "register"
        self.main_pos_config.with_user(self.pos_admin).open_ui()
        self.start_pos_tour("test_post_login_default_screen_is_register", login="pos_admin")
```

**Verified from source (Odoo 19.0):**
- Inherits from **both** `TestPosHrHttpCommon` (from `pos_hr`) and `TestFrontendCommon` (from `pos_restaurant`) — this is the key: the module's test requires both test mixins to be present
- `self.main_pos_config` is the main POS config set up by `TestFrontendCommon`
- `self.pos_admin` is a demo user who is both a POS admin and an employee with admin rights
- The test sets `default_screen` to `"tables"` or `"register"` and verifies the correct screen appears after login
- `login="pos_admin"` parameter in `start_pos_tour` specifies the user to log in as (uses `pos_hr`'s login mechanism)
- Two separate tests: one for `default_screen = "tables"` (floor plan shown after login), one for `default_screen = "register"` (product screen shown after login)

**Test coverage:** The two tests verify that when `pos_hr` employee login is combined with `pos_restaurant`:
- The floor plan screen opens correctly as the default screen (when configured)
- The product screen opens correctly as the default screen (when configured)
- The employee login flow works in the restaurant context without conflicts

---

## L4: Version Changes (Odoo 18 → 19)

`pos_hr_restaurant` version 1.0 was introduced in Odoo 19 as a new bridge module. There is no Odoo 18 equivalent of this specific module.

### Odoo 18: Pre-existing Implementation

In Odoo 18, the HR + restaurant integration behavior was handled within the individual modules themselves. `pos_hr` had some awareness of restaurant mode, and `pos_restaurant` had some awareness of HR mode. The code was interleaved within the parent modules.

### Odoo 19: Module Extraction

In Odoo 19, this integration logic was **extracted** into `pos_hr_restaurant` as a standalone auto-install bridge module. This follows the same pattern as `pos_restaurant_stripe`, `pos_restaurant_adyen`, and `pos_restaurant_loyalty` — all introduced as separate bridge modules in Odoo 19 to cleanly separate concerns.

### Why a Separate Bridge?

1. **Separation of concerns**: `pos_hr` should not need to know about restaurant-specific behavior, and `pos_restaurant` should not need to know about HR-specific behavior
2. **Independent testability**: The bridge has its own test file, making it possible to test the HR + restaurant interaction without modifying either parent module
3. **Auto-install contract**: Admin does not need to know about the dependency — the bridge activates automatically when both parents are present
4. **Owl patch order**: By importing `pos_restaurant`'s `pos_store` first (`import "@pos_restaurant/app/services/pos_store"`), the bridge ensures its patches apply after `pos_restaurant`'s patches, creating a predictable patch layering

### Known Limitations

| Limitation | Description | Workaround |
|---|---|---|
| Session never expires | No idle timeout after login | Manager must manually close session at end of shift |
| Edit plan button gated by `employeeIsAdmin` | Only manager-level employees can edit floor plan | Grant manager privileges to senior waiters who need floor editing |
| No server-side enforcement | Edit button visibility is client-side only | A knowledgeable user could manipulate JS to reveal the edit button; server has no enforcement |

---

## L4: Security Analysis

### Access Control

No new ACL entries are defined. The module extends the `Navbar` component and `PosStore` service — both are client-side constructs with no server-side ACL enforcement.

The `showEditPlanButton` logic is entirely client-side. A technically sophisticated user could bypass this check by modifying the JavaScript in the browser. For proper security, the floor plan write operations on the server (`sync_from_ui`, `write`) should be guarded by server-side permission checks. These are enforced by `pos_restaurant`'s existing ACL and `group_pos_manager` checks.

### Session Locking

The session locking mechanism (`locked_by` in `pos.session`) is provided by `pos_hr`. The idle timer override in this bridge ensures the session stays alive, but does not affect the lock. Multiple POS devices with the same employee logged in are prevented by `pos_hr`'s lock mechanism.

### No PII Transmission

This module does not transmit any data. All behavior is in-memory JavaScript state on the client.

---

## Cross-Module Integration

| Partner Module | Relationship | Integration Point |
|---|---|---|
| `pos_hr` | Hard dependency | `PosStore.employeeIsAdmin` property; employee login mechanism; `TestPosHrHttpCommon` test mixin |
| `pos_restaurant` | Hard dependency | `PosStore` service (patched); `FloorScreen`; `Navbar.showEditPlanButton`; `TestFrontendCommon` test mixin |
| `point_of_sale` | Inherited via deps | `PosStore` base class; `Navbar` component; `TestCommon` test base |
| `pos_restaurant_stripe` | No dependency | Coexists independently |
| `pos_restaurant_adyen` | No dependency | Coexists independently |
| `pos_restaurant_loyalty` | No dependency | Coexists independently |

### OWL Patch Order

```
point_of_sale: PosStore base, Navbar base
    │
    ▼
pos_hr: PosStore extension (adds employeeIsAdmin), Navbar extension
    │
    ▼
pos_restaurant: PosStore patches, Navbar patches (showEditPlanButton base)
    │
    ▼
pos_hr_restaurant: PosStore.patch (idle timer) + Navbar.patch (showEditPlanButton refinement)
```

The import of `pos_restaurant`'s `pos_store` in `pos_hr_restaurant` ensures `pos_restaurant`'s patches are applied before `pos_hr_restaurant`'s. This is the correct layering.

---

## Related Documentation

- [Modules/pos_hr](modules/pos_hr.md) — Employee login and session management
- [Modules/pos_restaurant](modules/pos_restaurant.md) — Restaurant floor plan and table management
- [Modules/point_of_sale](modules/point_of_sale.md) — POS base module
- [Modules/pos_restaurant_stripe](modules/pos_restaurant_stripe.md) — Stripe tipping bridge
- [Modules/pos_restaurant_adyen](modules/pos_restaurant_adyen.md) — Adyen tipping bridge
- [Modules/pos_restaurant_loyalty](modules/pos_restaurant_loyalty.md) — Loyalty bridge
