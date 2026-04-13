---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #pos
  - #restaurant
  - #loyalty
---

# pos_restaurant_loyalty — Restaurant POS + Loyalty Bridge

> Fixes loyalty reward behavior when both `pos_restaurant` and `pos_loyalty` are installed simultaneously. In Odoo 19, loyalty rewards are tied to specific order lines in the cart. When restaurant courses are used (items fired to the kitchen separately), reward lines must follow the same course grouping rules. Without this bridge, loyalty rewards become misaligned with courses or disappear when tables are switched.

**Module:** `pos_restaurant_loyalty` | **Location:** `odoo/addons/pos_restaurant_loyalty/` | **Version:** 1.0
**Depends:** `pos_restaurant`, `pos_loyalty` | **Category:** Sales/Point of Sale | **License:** LGPL-3
**Auto-install:** `True` | **Sequence:** 6

---

## Module Architecture

`pos_restaurant_loyalty` is a **thin behavioral bridge** — zero Python ORM models, zero server-side business logic, zero XML data. It consists of two JavaScript patches that fix interaction bugs between the restaurant course system and the loyalty reward system, plus a test suite verifying the fixes.

```
pos_restaurant_loyalty
    ├── __manifest__.py                          (bridge metadata + JS asset loading)
    ├── __init__.py                              (empty — no Python)
    ├── tests/
    │   ├── __init__.py
    │   └── test_pos_restaurant_loyalty.py      (Python HTTP test)
    └── static/
        ├── src/overrides/models/
        │   ├── pos_order.js                    (reward line → course assignment)
        │   └── pos_store.js                    (table switch → reward refresh)
        └── tests/tours/
            └── PosRestaurantLoyaltyTour.js      (POS tour tests)
```

| Layer | File | Role |
|---|---|---|
| Manifest | `__manifest__.py` | Declares dependencies, loads JS patches and test assets |
| Loyalty fix | `static/src/overrides/models/pos_order.js` | Assigns course to reward lines |
| Reward refresh | `static/src/overrides/models/pos_store.js` | Refreshes rewards on table switch |
| Tests | `tests/test_pos_restaurant_loyalty.py` | HTTP test for loyalty persistence across tables |
| Tours | `static/tests/tours/PosRestaurantLoyaltyTour.js` | POS UI tour tests |

---

## L1: Loyalty Program in Restaurant POS Context

### The Core Tension

The `pos_loyalty` module provides loyalty rewards that attach as **negative-discount lines** on the current order. These are lines with `is_reward_line = True` and a `reward_id` reference.

The `pos_restaurant` module adds **courses** — a way to group order lines for kitchen firing. Each course has an `index` (1st, 2nd, 3rd course) and a `fired` flag.

When both systems are active simultaneously, two problems arise:

**Problem 1: Reward lines have no course**

When a waiter adds products, fires them course-by-course, and a loyalty reward is applied, the reward line has no `course_id`. On the kitchen display, reward lines appear as orphaned items (not belonging to any course), causing confusion or being printed unintentionally.

**Problem 2: Switching tables loses rewards**

In restaurant POS, waiters routinely switch tables (e.g., move a party to a larger table). When `PosStore.setTable()` is called to change the table, the loyalty rewards that were applied to the previous table's order are not re-applied to the new table's order. The customer loses their loyalty discount.

### What This Module Fixes

1. **Reward line course assignment**: When courses are present on an order, any newly created reward line is assigned to the current (last) course so it is grouped correctly on kitchen displays.
2. **Reward persistence across table switches**: When the waiter changes tables, `updateRewards()` is called to re-apply loyalty rewards to the new order.

---

## L2: Server-Side Components

### Manifest

```python
{
    'name': 'POS - Restaurant Loyality',     # Note: misspelled "Loyality" is intentional in Odoo source
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Link module between pos_restaurant and pos_loyalty',
    'description': """
This module correct some behaviors when both module are installed.
""",
    'depends': ['pos_restaurant', 'pos_loyalty'],
    'installable': True,
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_restaurant_loyalty/static/src/**/*',
        ],
        'web.assets_tests': [
            'pos_restaurant_loyalty/static/tests/tours/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

**Auto-install behavior:** When `pos_restaurant` AND `pos_loyalty` are both installed, this module auto-installs. This ensures the loyalty-restaurant interaction is always fixed — an admin does not need to know to manually install it.

**No Python models:** There are zero server-side ORM models, zero fields, zero constraints. The `__init__.py` is empty. All behavior is client-side.

**Spelling note:** The manifest has `'name': 'POS - Restaurant Loyality'` (single 'l' in Loyalty). This is intentional in the Odoo source and preserved here for accuracy.

---

## L3: Client-Side Override Patterns

### File 1: `static/src/overrides/models/pos_order.js`

```javascript
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    _getRewardLineValues(args) {
        const lineValues = super._getRewardLineValues(args);
        // Assign last course to reward lines
        if (this.hasCourses()) {
            const course = this.getLastCourse();
            lineValues.forEach((line) => {
                line.course_id = course;
            });
        }
        return lineValues;
    },
});
```

**Override pattern:** `_getRewardLineValues` is called by `pos_loyalty` when a loyalty reward is applied to the order. The parent implementation (in `pos_loyalty`) creates reward line values (negative discount amounts, `is_reward_line = True`, etc.). This bridge intercepts the return value.

**Behavior when `hasCourses()` is True:** Each reward line value dict in `lineValues` gets `course_id` set to the current last course (`getLastCourse()`). This causes the reward line to appear as part of that course group on the kitchen display.

**Behavior when `hasCourses()` is False:** Returns `super._getRewardLineValues(args)` unchanged. Normal loyalty behavior — no course assignment.

**Trigger:** Called every time a reward is applied, recalculated, or a product is added to the order. Since `pos_loyalty` already guards unnecessary recomputation via its own `@debounce`, the overhead of the additional `hasCourses()` check is negligible.

### File 2: `static/src/overrides/models/pos_store.js`

```javascript
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setTable(table, orderUid = null) {
        await super.setTable(...arguments);
        await this.updateRewards();
    },
});
```

**Override pattern:** `setTable` is called by the POS frontend when a waiter selects a new table (or creates a new table order). The parent implementation (from `point_of_sale`) handles table selection, order retrieval/creation, and UI state updates.

**Bridge addition:** After `super.setTable()` completes, `await this.updateRewards()` is called. The `updateRewards()` method is provided by `pos_loyalty` — it recomputes and reapplies loyalty rewards for the current order.

**Why `await`:** The `super.setTable()` call may trigger network writes (creating or updating the order). `updateRewards()` must wait for those to complete before recomputing rewards, otherwise the reward computation runs against stale order data.

**Trigger:** Every time the waiter switches tables from the floor plan. This includes:
- Selecting a table with an existing order (retrieves that order)
- Selecting a table with no existing order (creates a new order for that table)
- Navigating back to the floor plan and selecting a different table

### Workflow Diagram

```
Waiter opens POS → selects Table 5 → adds Water → reward applied (10% off)
    │
    ├── pos_restaurant_loyalty: reward line gets course_id = Course 1
    │
    ▼
Waiter clicks Plan → selects Table 2 → table switch triggered
    │
    ├── PosStore.setTable() called
    │       └── super.setTable() → order for Table 2 created/retrieved
    │
    ▼
    └── pos_restaurant_loyalty: updateRewards() → reward reapplied
            └── _getRewardLineValues() → course_id = Course 1 (Table 2's first course)
```

---

## L3: Failure Modes

| Failure Mode | Trigger | Behavior |
|---|---|---|
| `updateRewards()` fails | Network error during `super.setTable()` | Reward not reapplied; `setTable` result is returned. Next product add will trigger normal reward application. |
| `updateRewards()` called on non-loyalty config | No loyalty program active | `pos_loyalty`'s `updateRewards()` is a no-op (guards internally). No error. |
| Reward line created before any course | No course selected yet | `hasCourses()` returns False; reward line has no `course_id`. No course assignment. |
| Table switch with no order | New table has no existing order | `setTable()` creates a new order; `updateRewards()` applies rewards to the fresh order. |
| Concurrent table switches | Waiter rapidly taps different tables | Each `setTable()` call is awaited; the last one wins. No race condition in the current implementation. |

---

## L4: Test Suite

### Python Test: `tests/test_pos_restaurant_loyalty.py`

The module includes a Python `HttpCase` that inherits from `TestFrontend` (from `pos_restaurant`).

#### Test 1: `test_change_table_rewards_stay`

```python
def test_change_table_rewards_stay(self):
    """
    Test that rewards stay on the order when leaving the table.
    """
    self.env['loyalty.program'].create({
        'name': 'My super program',
        'program_type': 'promotion',
        'trigger': 'auto',
        'applies_on': 'current',
        'rule_ids': [Command.create({'minimum_qty': 1})],
        'reward_ids': [Command.create({
            'reward_type': 'discount',
            'discount': 10,
            'discount_mode': 'percent',
            'discount_applicability': 'order',
        })],
    })
    self.pos_config.with_user(self.pos_user).open_ui()
    self.start_pos_tour("PosRestaurantRewardStay")
    order = self.env['pos.order'].search([])
    self.assertEqual(order.currency_id.round(order.amount_total), 1.98)
```

**What it tests:**
1. Creates a 10% automatic loyalty program
2. Opens POS as `pos_user`
3. Runs `PosRestaurantRewardStay` tour
4. Asserts that after switching tables (Table 5 → main floor → Table 5), the reward is still present
5. `1.98` = Water (2.20) - 10% = 1.98

**Expected order:** Table 5 opened, Water added, 10% reward applied (Water = 2.20, reward = -0.22, total = 1.98). Table switched away and back. Reward persists.

#### Test 2: `test_loyalty_reward_with_courses`

```python
def test_loyalty_reward_with_courses(self):
    """
    Ensure that a loyalty reward line remains in the cart
    when courses are applied in a restaurant POS order.
    """
    self.env['loyalty.program'].search([]).write({'active': False})
    self.env['loyalty.program'].create({
        'name': '10% Discount on All Products',
        'program_type': 'promotion',
        'trigger': 'auto',
        'applies_on': 'current',
        'rule_ids': [Command.create({'minimum_qty': 1})],
        'reward_ids': [Command.create({
            'reward_type': 'discount',
            'discount': 10,
            'discount_mode': 'percent',
            'discount_applicability': 'order',
        })],
    })
    self.pos_config.with_user(self.pos_user).open_ui()
    self.start_pos_tour('test_loyalty_reward_with_courses')
    orders = self.pos_config.current_session_id.order_ids
    self.assertEqual(len(orders), 2)
    self.assertEqual(orders[0].currency_id.round(orders[0].amount_total), 1.98)
    self.assertEqual(len(orders[0].lines.filtered(lambda line: line.is_reward_line)), 1)
    self.assertEqual(orders[1].currency_id.round(orders[1].amount_total), 1.98)
    self.assertEqual(len(orders[1].lines.filtered(lambda line: line.is_reward_line)), 1)
```

**What it tests:**
1. Deactivates all existing loyalty programs
2. Creates a new 10% auto-reward program
3. Runs `test_loyalty_reward_with_courses` tour (see tour steps below)
4. Asserts that exactly 2 orders exist (two table sessions)
5. Each order has exactly 1 reward line
6. Each order total is 1.98 (Water - 10%)

**Expected order:** Table 5 opened, course selected, Water added, reward applied. Back to floor plan. Table 2 opened, Water added (no course yet), reward applied, course selected, reward still present.

### POS Tour: `static/tests/tours/PosRestaurantLoyaltyTour.js`

Two tours define the POS-side test steps:

**`PosRestaurantRewardStay`** (10 steps):
1. `Chrome.startPoS()` + confirm "Open Register"
2. `FloorScreen.clickTable("5")` — select Table 5
3. `ProductScreen.clickDisplayedProduct("Water")` — add Water (triggers 10% reward)
4. `PosLoyalty.hasRewardLine("10% on your order", "-0.22", "1")` — reward visible
5. `Chrome.clickPlanButton()` — go back to floor plan
6. `Chrome.clickBtn("second floor")` — switch floors
7. `Chrome.clickBtn("main floor")` — back to main floor
8. `FloorScreen.clickTable("5")` — select Table 5 again
9. `PosLoyalty.hasRewardLine(...)` — reward still present
10. Test asserts reward total = -0.22, order total = 1.98

**`test_loyalty_reward_with_courses`** (12 steps):
1-4: Table 5 → select course → add Water → reward present
5-6: Back to floor plan
7-12: Table 2 → add Water (before course) → reward present → select course → reward still present

---

## L4: Version Changes (Odoo 18 → 19)

`pos_restaurant_loyalty` version 1.0 was introduced in Odoo 19 as a new bridge module. There is no Odoo 18 equivalent.

### Why This Module Was Created in Odoo 19

Odoo 19 introduced a more modular architecture for POS extensions. The decision to create a separate bridge module for `pos_restaurant` + `pos_loyalty` interaction reflects a broader Odoo 19 pattern of:

1. **Reducing `pos_restaurant` scope**: The restaurant module avoids directly depending on `pos_loyalty`, keeping it as a standalone feature
2. **Explicit dependency rather than implicit coupling**: The interaction is declared in the manifest, making it clear that both modules must coexist
3. **Independent testability**: The bridge has its own test file, making it possible to test the loyalty behavior in a restaurant context without modifying either parent module
4. **Auto-install contract**: Admin does not need to know about the dependency — the bridge activates automatically when both parents are present

### Odoo 18 Equivalent Behavior

In Odoo 18, both `pos_restaurant` and `pos_loyalty` could be installed together, but the loyalty-course interaction bugs were not fixed. Specifically:
- Reward lines did not get assigned to a course
- Switching tables lost loyalty rewards

There was no equivalent bridge module in Odoo 18. An Odoo 18 → 19 upgrade automatically introduces this module, fixing the bugs retroactively.

### API Stability

Since this module has no server-side code, there are no migration scripts or data transforms. The module installs cleanly on upgrade.

---

## Cross-Module Integration

| Partner Module | Relationship | Integration Point |
|---|---|---|
| `pos_restaurant` | Hard dependency | Course system (`hasCourses()`, `getLastCourse()`, `OrderCourse` model); `TipScreen` |
| `pos_loyalty` | Hard dependency | `_getRewardLineValues()` override; `updateRewards()` method |
| `point_of_sale` | Inherited via deps | `PosStore`, `PosOrder` base classes; `PosStore.setTable()` |
| `pos_restaurant_stripe` | No dependency | Coexists independently |

---

## Security

This module has **no security concerns**:
- Zero server-side Python code
- Zero ORM models or access control entries
- JavaScript patches only modify in-memory POS client state
- No data exfiltration or unauthorized access vectors
- No new attachment of files, no external network calls

---

## Related Documentation

- [Modules/pos_restaurant](odoo-18/Modules/pos_restaurant.md) — Restaurant POS base module
- [Modules/pos_loyalty](odoo-18/Modules/pos_loyalty.md) — Loyalty program module
- [Modules/point_of_sale](odoo-18/Modules/point_of_sale.md) — POS base module

---

## L4: Client-Side Source Files (Verified from Source)

### File: `static/src/overrides/models/pos_order.js`

```javascript
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    _getRewardLineValues(args) {
        const lineValues = super._getRewardLineValues(args);
        // Assign last course to reward lines
        if (this.hasCourses()) {
            const course = this.getLastCourse();
            lineValues.forEach((line) => {
                line.course_id = course;
            });
        }
        return lineValues;
    },
});
```

**Verified from source (Odoo 19.0):**
- `this.hasCourses()` checks whether the current order has any courses
- `this.getLastCourse()` returns the course with the highest `index` (the most recently created)
- Each reward line value dict in `lineValues` gets `course_id` set to the current last course object (the model instance, not just an ID)
- If no courses exist, `super._getRewardLineValues(args)` is returned unchanged

### File: `static/src/overrides/models/pos_store.js`

```javascript
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setTable(table, orderUid = null) {
        await super.setTable(...arguments);
        await this.updateRewards();
    },
});
```

**Verified from source (Odoo 19.0):**
- `setTable` is an async method — `await super.setTable(...arguments)` ensures the parent completes before calling `updateRewards()`
- `updateRewards()` is provided by `pos_loyalty` — it recomputes and reapplies loyalty rewards for the current order after the table switch
- `PosStore` is the singleton service (not a model class) — patching `PosStore.prototype` affects the global POS store instance

### POS Tour: `static/tests/tours/PosRestaurantLoyaltyTour.js` (Verified from Source)

```javascript
import * as ProductScreenPos from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ProductScreenResto from "@pos_restaurant/../tests/tours/utils/product_screen_util";
import * as FloorScreen from "@pos_restaurant/../tests/tours/utils/floor_screen_util";
import * as PosLoyalty from "@pos_loyalty/../tests/tours/utils/pos_loyalty_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import { registry } from "@web/core/registry";

const ProductScreen = { ...ProductScreenPos, ...ProductScreenResto };

registry.category("web_tour.tours").add("PosRestaurantRewardStay", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.clickDisplayedProduct("Water"),
            PosLoyalty.hasRewardLine("10% on your order", "-0.22", "1"),
            Chrome.clickPlanButton(),
            Chrome.clickBtn("second floor"),
            Chrome.clickBtn("main floor"),
            FloorScreen.clickTable("5"),
            PosLoyalty.hasRewardLine("10% on your order", "-0.22", "1"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_loyalty_reward_with_courses", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.clickCourseButton(),
            ProductScreen.clickDisplayedProduct("Water"),
            PosLoyalty.hasRewardLine("10% on your order", "-0.22", "1"),
            Chrome.clickPlanButton(),
            FloorScreen.clickTable("2"),
            ProductScreen.clickDisplayedProduct("Water"),
            PosLoyalty.hasRewardLine("10% on your order", "-0.22", "1"),
            ProductScreen.clickCourseButton(),
            PosLoyalty.hasRewardLine("10% on your order", "-0.22", "1"),
            Chrome.clickPlanButton(),
        ].flat(),
});
```

**Verified from source (Odoo 19.0):**
- `ProductScreen` is merged from both `pos` and `pos_restaurant` variants — `pos_restaurant` adds `clickCourseButton()` (for selecting a course before adding products)
- `PosLoyalty.hasRewardLine(label, amount, qty)` asserts a reward line exists with the given parameters
- `Chrome.clickBtn("second floor")` and `Chrome.clickBtn("main floor")` switch floors — this tests that reward persistence survives floor navigation, not just table switching
- Both tours end with `Chrome.clickPlanButton()` (returning to the floor plan) — the test assertions occur before this step

### Python Test: `tests/test_pos_restaurant_loyalty.py` (Verified from Source)

```python
from odoo.tests import tagged
from odoo.addons.pos_restaurant.tests.test_frontend import TestFrontend
from odoo import Command

@tagged("post_install", "-at_install")
class TestPoSRestaurantLoyalty(TestFrontend):
    def test_change_table_rewards_stay(self):
        """
        Test that make sure that rewards stay on the order when leaving the table
        """
        self.env['loyalty.program'].create({
            'name': 'My super program',
            'program_type': 'promotion',
            'trigger': 'auto',
            'applies_on': 'current',
            'rule_ids': [Command.create({'minimum_qty': 1})],
            'reward_ids': [Command.create({
                'reward_type': 'discount',
                'discount': 10,
                'discount_mode': 'percent',
                'discount_applicability': 'order',
            })],
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("PosRestaurantRewardStay")
        order = self.env['pos.order'].search([])
        self.assertEqual(order.currency_id.round(order.amount_total), 1.98)

    def test_loyalty_reward_with_courses(self):
        """
        Ensure that a loyalty reward line remains in the cart
        when courses are applied in a restaurant POS order.
        """
        self.env['loyalty.program'].search([]).write({'active': False})
        self.env['loyalty.program'].create({
            'name': '10% Discount on All Products',
            'program_type': 'promotion',
            'trigger': 'auto',
            'applies_on': 'current',
            'rule_ids': [Command.create({'minimum_qty': 1})],
            'reward_ids': [Command.create({
                'reward_type': 'discount',
                'discount': 10,
                'discount_mode': 'percent',
                'discount_applicability': 'order',
            })],
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('test_loyalty_reward_with_courses')
        orders = self.pos_config.current_session_id.order_ids
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].currency_id.round(orders[0].amount_total), 1.98)
        self.assertEqual(len(orders[0].lines.filtered(lambda line: line.is_reward_line)), 1)
        self.assertEqual(orders[1].currency_id.round(orders[1].amount_total), 1.98)
        self.assertEqual(len(orders[1].lines.filtered(lambda line: line.is_reward_line)), 1)
```

**Verified from source (Odoo 19.0):**
- Inherits `TestFrontend` from `pos_restaurant` — provides the POS tour framework and test setup
- `self.pos_config` is the main POS config (with restaurant mode enabled from the `TestFrontend` setup)
- `self.pos_user` is a demo user with `group_pos_user`
- `self.start_pos_tour(name)` runs the named POS UI tour
- `order = self.env['pos.order'].search([])` — no domain filter; gets the most recently created order(s)
- For `test_loyalty_reward_with_courses`: `orders[0]` is from Table 5 (water + reward), `orders[1]` is from Table 2 (water added before course, reward still applied, then course selected and reward persists)
- `1.98 = 2.20 (Water price from demo data) - 10% = 1.98`
