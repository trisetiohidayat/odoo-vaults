---
type: pattern
tags: [odoo, odoo19, frontend, ui, discovery, automation, playwright]
created: 2026-04-19
updated: 2026-04-19
version: "1.0"
author: claude-code
prerequisite: odoo-vault-base-analysis
---

# UI Discovery Patterns

## Overview

Dokumentasi ini berisi **discovery rules** — principa yang memungkinkan AI menemukan UI elements secara runtime tanpa harus mendokumentasikan semua selector satu per satu. Berbeda dengan exhaustive documentation, discovery rules mengajarkan *cara menemukan* alih-alih *hasil temuan*.

**Philosophy:** Pattern-based discovery = scalable, maintenance-light, edge-case ready. Documentation-based = brittle, incomplete, requires constant updates.

> **📖 Companion:** Untuk backend/state transition knowledge, lihat [Workflow Patterns](Workflow%20Patterns.md). Untuk selector reference, lihat skill `/odoo-playwright` → `references/odoo-selectors.md`.

---

## Core Principle: Odoo Teleport Pattern

### The Problem

Odoo secara umum **teleports dropdown menus** dari parent element ke `<body>` atau portal root. Artinya:

```
❌ SALAH:   cari dropdown di dalam card parent
✅ BENAR:  cari dropdown di body (teleported)
```

### Why Odoo Does This

Dropdown perlu positioned relative ke viewport, bukan parent. Jika di-tether ke parent, dropdown bisa ter-clip oleh container atau viewport boundary.

### How to Detect

```javascript
// Cek apakah element adalah teleported dropdown
const isTeleported = el => {
  const parent = el.closest('[class*="dropdown"]');
  // Jika parent tidak punya positioning context yang valid
  return el.parentElement?.tagName === 'BODY';
};

// Generic check
const isVisible = el => el.offsetParent !== null;
```

---

## Pattern 1: Dropdown Button → Menu Items

**Trigger:** Button dengan `title="Dropdown menu"` atau class mengandung `dropdown-toggle`

**Anatomy:**
```
DOM Structure:
<div class="o_dropdown_kanban position-absolute ...">
  <button class="dropdown-toggle" title="Dropdown menu">
    <span class="oi oi-ellipsis-v"></span>
  </button>
</div>
<!-- AFTER CLICK: menu teleported to body -->
<div class="o-dropdown--menu o-dropdown--kanban-record-menu dropdown-menu show">
  <a class="dropdown-item oe_kanban_action">Uninstall</a>
  <a class="dropdown-item oe_kanban_action">Module Info</a>
</div>
```

**Discovery Algorithm:**

```javascript
// Step 1: Find dropdown button
const dropdownBtn = document.querySelector('button[title="Dropdown menu"]');

// Step 2: Click it
dropdownBtn.click();

// Step 3: IMMEDIATELY find menu in body (not in parent)
const menu = document.querySelector('.o-dropdown--menu.show');

// Step 4: Find item by text
const item = [...menu.querySelectorAll('.dropdown-item')]
  .find(i => i.textContent.includes('Uninstall'));

// Step 5: Click item
item.click();
```

**Selector Reference:**
| Element | Selector |
|---------|----------|
| Dropdown button | `button[title="Dropdown menu"]` |
| Dropdown container | `.o_dropdown_kanban` |
| Teleported menu (Odoo 17/18) | `.o-dropdown--menu.o-dropdown--kanban-record-menu` |
| Teleported menu (Odoo 19) | `.o-popover .o-dropdown--kanban-record-menu` |
| Menu wrapper | `.o_popover` (Bootstrap popover container) |
| Menu items | `.dropdown-item.oe_kanban_action` |
| By text | `.dropdown-item:has-text("Uninstall")` |

**Confirmation Pattern:**

After clicking menu item, Odoo often shows confirmation dialog:

```javascript
// Check for dialog after action
const dialog = document.querySelector('[role="dialog"]');
if (dialog) {
  // Always present for destructive actions (uninstall, delete)
  // Button selectors: by text or by class
  const confirmBtn = [...dialog.querySelectorAll('button')]
    .find(b => b.textContent.includes('Uninstall'));
}
```

---

## Pattern 2: Form Header Buttons

**Trigger:** Semua button di `<header>` atau `.o_form_statusbar`

**Standard Odoo Header Buttons:**

| Button | Hotkey | Selector |
|--------|--------|----------|
| Save | `s` | `[data-hotkey="s"]` |
| Edit | `e` | `[data-hotkey="e"]` |
| Create | `c` | `[data-hotkey="c"]` |
| Delete | - | `.o_form_button_remove` |

**State-Dependent Visibility:**

```javascript
// Form dalam mode edit vs view — button visibility berubah
const formMode = document.querySelector('.o_form_view')?.classList.contains('o_form_editable')
  ? 'edit'
  : 'view';

// Dalam view mode: hanya Edit button yang visible
// Dalam edit mode: Save, Discard, Create visible
```

**Dropdown in Status Bar:**

Some buttons in header are inside dropdown toggle:

```javascript
// Cek apakah ada toggle di statusbar
const statusbarDropdown = document.querySelector('.o_form_statusbar .dropdown-toggle');
if (statusbarDropdown) {
  statusbarDropdown.click();
  // Menu teleported — find in body
  const menu = document.querySelector('.o-dropdown--menu');
  // Find action by text
  const action = [...menu.querySelectorAll('[role="menuitem"]')]
    .find(i => i.textContent.includes('Confirm'));
  action?.click();
}
```

---

## Pattern 3: Kanban Card Actions

**Trigger:** Module cards atau record cards di `.o_kanban_view`

**Two Categories of Actions:**

```
VISIBLE (direct):
  - Activate (uninstalled module)
  - Learn More (link)
  - Upgrade (installed module with extras)

HIDDEN (dropdown):
  - Uninstall (installed module)
  - Module Info
  - (other module-specific actions)
```

**Discovery Algorithm:**

```javascript
function findKanbanAction(cardText, actionNeeded) {
  const cards = document.querySelectorAll('.o_kanban_record');
  const targetCard = [...cards].find(c => c.innerText.includes(cardText));

  if (!targetCard) return null;

  // Step 1: Check visible buttons first
  const visibleBtns = targetCard.querySelectorAll('button:not([title*="Dropdown"])');
  const directBtn = [...visibleBtns].find(b => b.textContent.includes(actionNeeded));

  if (directBtn) return directBtn.click();

  // Step 2: If not visible, check dropdown
  const dropdownBtn = targetCard.querySelector('button[title="Dropdown menu"]');
  if (dropdownBtn && ['Uninstall', 'Module Info'].includes(actionNeeded)) {
    dropdownBtn.click();
    // Wait for teleport
    const menu = document.querySelector('.o-dropdown--menu.show');
    const item = [...menu.querySelectorAll('.dropdown-item')]
      .find(i => i.textContent.includes(actionNeeded));
    return item?.click();
  }

  return null;
}
```

**Selector Reference:**
| Element | Selector |
|---------|----------|
| Card container | `.o_kanban_record` |
| Card by text | `.o_kanban_record:has-text("ModuleName")` |
| Visible button | `.o_kanban_record button:has-text("Activate")` |
| Dropdown button | `.o_kanban_record button[title="Dropdown menu"]` |
| Teleported menu | `.o-dropdown--menu.o-dropdown--kanban-record-menu` |

---

## Pattern 4: Dialog / Confirmation Modal

**Trigger:** Destructive actions atau multi-step workflows

**Anatomy:**

```html
<div role="dialog" class="modal d-block o_technical_modal">
  <div class="modal-dialog modal-dialog-centered modal-lg">
    <div class="modal-content">
      <header class="modal-header">
        <h4 class="modal-title">Uninstall module</h4>
        <button aria-label="Close">×</button>
      </header>
      <div class="modal-body">
        <!-- Warning text -->
        <!-- Content lists -->
      </div>
      <footer class="modal-footer">
        <button class="btn btn-secondary">Discard</button>
        <button class="btn btn-danger">Uninstall</button>
      </footer>
    </div>
  </div>
</div>
```

**Button Identification:**

```javascript
const dialog = document.querySelector('[role="dialog"]');
const buttons = dialog.querySelectorAll('button');

// Pattern: Primary action = text match or btn-primary/btn-danger
// Pattern: Cancel = btn-secondary or text contains 'Cancel', 'Discard'
const confirmBtn = [...buttons].find(b =>
  b.textContent.includes('Uninstall') ||
  b.classList.contains('btn-danger') ||
  b.classList.contains('btn-primary')
);
```

**Wait Pattern for Dialog:**

```javascript
// Wait for dialog to appear (async operation)
await new Promise(r => setTimeout(r, 1000));
const dialog = document.querySelector('[role="dialog"]');
if (!dialog) {
  // Check if action happened directly (no dialog needed)
  return { success: true, noDialog: true };
}
```

---

## Pattern 5: Search / Control Panel

**Trigger:** `.o_control_panel` container

**Components:**
- Search input: `.o_searchview_input`
- Filter toggle: `.o_filter_menu .dropdown-toggle`
- Group by toggle: `.o_group_by_menu .dropdown-toggle`
- View switcher: `.o_switch_view`
- Actions menu: `.o_cp_action_menus .dropdown-toggle`

**Dropdown Pattern (same as Pattern 1):**

```javascript
// Open filter dropdown
const filterToggle = document.querySelector('.o_filter_menu .dropdown-toggle');
filterToggle.click();

// Find filter in teleported menu
const menu = document.querySelector('.o-dropdown--menu.show');
const filterItem = [...menu.querySelectorAll('[role="menuitem"]')]
  .find(i => i.textContent.includes('My Records'));
filterItem?.click();
```

---

## Pattern 6: Wizard / Multi-Step

**Trigger:** Multi-step dialog with step indicator

**Anatomy:**

```html
<div class="modal">
  <div class="o_wizard_steps">
    <span class="o_wizard_step active" data-step="1">1. Configure</span>
    <span class="o_wizard_step" data-step="2">2. Preview</span>
  </div>
  <div class="modal-body">
    <!-- Step 1 fields -->
  </div>
  <footer class="modal-footer">
    <button class="btn btn-secondary">Back</button>
    <button class="btn btn-primary">Next</button>
  </footer>
</div>
```

**Discovery Algorithm:**

```javascript
// Get step count
const steps = document.querySelectorAll('.o_wizard_step');
const totalSteps = steps.length;

// Navigate steps
function nextStep() {
  const nextBtn = [...document.querySelectorAll('.modal-footer button')]
    .find(b => b.textContent.includes('Next') || b.classList.contains('btn-primary'));
  nextBtn?.click();
}

// Fill fields based on current step
function fillCurrentStep(data) {
  const activeStep = document.querySelector('.o_wizard_step.active');
  const stepNum = activeStep?.dataset.step;

  // Each step has different fields — identify by name attribute
  const fields = document.querySelectorAll('[name]');
  data.forEach(({ name, value }) => {
    const field = document.querySelector(`[name="${name}"]`);
    if (field) field.fill?.(value) || field.querySelector('input')?.fill(value);
  });
}
```

---

## Generic Discovery Heuristic

Gunakan ini untuk SEMUA Odoo page yang tidak familiar:

```javascript
function odooDiscover() {
  const results = {
    buttons: [],
    dropdowns: [],
    menus: [],
    dialogs: null,
    forms: []
  };

  // 1. Get all buttons with text
  document.querySelectorAll('button').forEach(b => {
    if (b.offsetParent !== null) { // visible only
      results.buttons.push({
        text: b.textContent.trim(),
        selector: getSelector(b),
        hotkey: b.dataset.hotkey,
        title: b.title,
        parent: b.parentElement.className
      });
    }
  });

  // 2. Get all dropdown toggles
  document.querySelectorAll('.dropdown-toggle, .o-dropdown-toggle').forEach(t => {
    results.dropdowns.push({
      text: t.textContent.trim(),
      selector: getSelector(t),
      parent: t.closest('[class*="kanban"], [class*="form"]')?.className
    });
  });

  // 3. Get all visible menus
  document.querySelectorAll('.o-dropdown--menu.show, .dropdown-menu.show').forEach(m => {
    results.menus.push([...m.querySelectorAll('.dropdown-item, [role="menuitem"]')]
      .map(i => i.textContent.trim()));
  });

  // 4. Check for dialog
  results.dialogs = document.querySelector('[role="dialog"]');

  return results;
}

// Helper: generate stable selector
function getSelector(el) {
  // Prefer data-* attributes
  if (el.dataset.id) return `[data-id="${el.dataset.id}"]`;
  if (el.dataset.hotkey) return `[data-hotkey="${el.dataset.hotkey}"]`;
  if (el.name) return `[name="${el.name}"]`;

  // Fall back to text content
  const text = el.textContent.trim().substring(0, 30);
  if (text) return `button:has-text("${text}")`;

  // Last resort: position
  return el.className;
}
```

---

## Usage in Skill

### Skill Workflow (pseudo-code):

```
1. User: "uninstall module X"

2. Load vault:
   - ir.module.module entry
   - Check for UI Entry section

3. If UI Entry exists:
   - Use documented selectors
   - Execute with confidence

4. If NO UI Entry:
   - Run odooDiscover() to analyze current page
   - Apply discovery patterns:
     a. Find module card by text
     b. Check visible buttons
     c. If needed action not visible → open dropdown
     d. Find item in teleported menu
     e. Click and handle dialog

5. Verify result:
   - Check for errors (toast notification)
   - Check for navigation (redirect)
   - Check for state change (re-render)
```

### Example: Full Uninstall Flow

```javascript
// Step 1: Navigate to Apps page
await page.goto(`${url}/web/apps`);
await page.waitForLoadState('networkidle');

// Step 2: Search for module
await page.fill('input.o_searchview_input', 'Employees');
await page.press('input.o_searchview_input', 'Enter');
await page.waitForTimeout(2000);

// Step 3: Find module card and dropdown
await page.evaluate(() => {
  const cards = document.querySelectorAll('.o_kanban_record');
  const empCard = [...cards].find(c => c.innerText.includes('Centralize employee'));

  if (!empCard) throw new Error('Module card not found');

  // Click dropdown button
  const dropdownBtn = empCard.querySelector('button[title="Dropdown menu"]');
  if (!dropdownBtn) throw new Error('Dropdown button not found');
  dropdownBtn.click();
});

// Step 4: Find and click Uninstall
await page.evaluate(() => {
  const menu = document.querySelector('.o-dropdown--menu.show');
  const uninstall = [...menu.querySelectorAll('.dropdown-item')]
    .find(i => i.textContent.includes('Uninstall'));
  if (!uninstall) throw new Error('Uninstall not found');
  uninstall.click();
});

// Step 5: Confirm in dialog
await page.evaluate(() => {
  const dialog = document.querySelector('[role="dialog"]');
  if (dialog) {
    const confirmBtn = [...dialog.querySelectorAll('button')]
      .find(b => b.textContent.includes('Uninstall') && b.classList.contains('btn-danger'));
    if (confirmBtn) confirmBtn.click();
  }
});

// Step 6: Wait for uninstall to complete
await page.waitForTimeout(5000);
```

---

## Anti-Patterns

| Anti-Pattern | Problem | Correct |
|--------------|---------|--------|
| `await page.goto('http://localhost:8069/web/apps')` | Hardcoded URL | Use context variable `${url}/web/apps` |
| `page.click('button:has-text("Uninstall")')` | Matches multiple elements | Use `.dropdown-item:has-text("Uninstall")` in context |
| Clicking element before checking visibility | Flaky test | Always check `offsetParent !== null` |
| Not waiting for teleported menu | Menu not found | Always `waitForSelector('.o-dropdown--menu.show')` |
| Hardcoded sleep | Race condition | Use `waitForLoadState` or wait for element |
| Assuming immediate state change | Test fails | Wait and re-check actual page state |

---

## Related

- [Workflow Patterns](Workflow%20Patterns.md) — Backend state machine patterns (what things ARE)
- [Modules/ir.module.module](Modules/ir.module.module.md) — Model with UI entry example
- Skill `/odoo-playwright` → `references/odoo-selectors.md` — Selector reference
- Skill `/odoo-playwright` → `SKILL.md` — Tool syntax and execution