# auth_password_policy

> Basic password policy configuration and validation for Odoo 19.

## Module Facts

| Property | Value |
|----------|-------|
| **Technical Name** | `auth_password_policy` |
| **Category** | Hidden/Tools |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Odoo Version** | 19.0 |
| **Manifest Depends** | `base_setup`, `web` |
| **Migration Note** | Single `minlength` parameter persisted in `ir.config_parameter` (not `res.company`) — see [[#Design Decision]] |

---

## Design Decision

This module deliberately stores its single policy setting (`minlength`) in `ir.config_parameter` rather than on `res.company`. This is a **system-wide singleton** — there is one password policy for the entire database, not one per company. If per-company policy is needed, a separate module must extend both `res.company` with policy fields and `res.users._check_password_policy()` with company-aware logic.

> **Note on "Advanced" Fields**: Some documentation or community modules mention `require_special_character`, `require_uppercase`, `require_lowercase`, `require_numeric` on `res.company`. These fields do **not** exist in the standard `auth_password_policy` module. They are only enforced by the optional companion module `auth_password_policy_signup` (present in `auth_signup`'s extended flow), or must be implemented custom.

---

## Dependencies

```yaml
depends:
  - base_setup   # Provides res.config.settings form base class and layout
  - web           # Web controller, session auth, RPC bridge for get_password_policy()
```

`base_setup` is critical — it provides the `res.config.settings` form that this module's view `res_config_settings_view_form` inherits from. Without it, the settings panel has no layout to inject into.

---

## Data Files

### `data/defaults.xml`

```xml
<data noupdate="1">
    <record model="ir.config_parameter" id="minlength" forcecreate="True">
        <field name="key">auth_password_policy.minlength</field>
        <field name="value">8</field>
    </record>
</data>
```

- **`noupdate="1"`**: Record is created on first install but not updated on subsequent upgrades. Changing the default `8` on upgrade does nothing for existing databases.
- **`forcecreate="True"`**: The `ir.config_parameter` record is always created if missing (e.g., after a database restore that dropped it).
- **Default value is `8`**: Minimum password length is 8 characters out of the box.

---

## Models

### `res.users` — Extended

**File**: `models/res_users.py`
**Inheritance**: `_inherit = 'res.users'` (classic extension)

#### `get_password_policy()`

```python
@api.model
def get_password_policy(self):
    params = self.env['ir.config_parameter'].sudo()
    return {
        'minlength': int(params.get_param('auth_password_policy.minlength', default=0)),
    }
```

- Decorated with `@api.model` — runs as superuser, no active record context.
- Reads from `ir.config_parameter` using `sudo()` (bypasses ACL; config params are system-only).
- Returns a plain `dict` — serializable over JSON-RPC to the web client.
- Called by the frontend `PasswordField` OWL component on mount (`onWillStart`) to seed the `ConcretePolicy` with the live policy value.

**Security Note**: This method is world-readable (any authenticated user can call it). It only exposes the `minlength` integer, which is not sensitive.

#### `_set_password()`

```python
def _set_password(self):
    self._check_password_policy(self.mapped('password'))
    super(ResUsers, self)._set_password()
```

**Override pattern**: Pre-hook — validates before calling `super()`.

Called by:
- The user password change wizard (`change.password.own`, `change.password.user`).
- Directly via `res.users` write if the `password` field is set programmatically.

The `self.mapped('password')` returns a list of password strings for all records in `self`. This is batch-safe — a single `_check_password_policy` call validates all passwords in one pass.

#### `_check_password_policy(passwords)`

```python
def _check_password_policy(self, passwords):
    failures = []
    params = self.env['ir.config_parameter'].sudo()

    minlength = int(params.get_param('auth_password_policy.minlength', default=0))
    for password in passwords:
        if not password:
            continue                           # skip empty (e.g., no-change sentinel)
        if len(password) < minlength:
            failures.append(_("Your password must contain at least "
                              "%(minimal_length)d characters and only has "
                              "%(current_count)d.",
                              minimal_length=minlength,
                              current_count=len(password)))

    if failures:
        raise UserError(u'\n\n '.join(failures))
```

**Behavior**:
- Empty passwords are silently skipped (`continue`). This prevents false failures when `_set_password` is called without intent to change the password.
- Failures are accumulated for all passwords in the batch, then raised as a single `UserError` with `\n\n ` separators.
- Translation via `_()` is applied at raise time, not at collection time.

**Failure modes**:
| Scenario | Result |
|----------|--------|
| `password` not in write vals | `_check_password_policy` never called — no check |
| `password` is empty string | Skipped silently — allows clearing password |
| `password` is `False`/`None` | Python `TypeError` — `len()` on None |
| `minlength = 0` | All passwords pass (policy disabled) |
| Batch write with mixed failures | All failures reported in one `UserError` |

**Performance**: One `ir.config_parameter` read per batch, not per user. O(1) DB roundtrip for any batch size.

---

### `res.config.settings` — Extended

**File**: `models/res_config_settings.py`
**Inheritance**: `_inherit = 'res.config.settings'` (classic extension)

#### `minlength` — Field

```python
minlength = fields.Integer(
    "Minimum Password Length",
    config_parameter="auth_password_policy.minlength",
    default=0,
    help="Minimum number of characters passwords must contain, "
         "set to 0 to disable.")
```

**Key properties**:
- `config_parameter="auth_password_policy.minlength"` — the field is **not** stored on `res.config.settings`. It is a **proxy** that reads/writes the named `ir.config_parameter` record directly. This means the value persists across wizard closes without explicit `sudo().set_param()` calls.
- `default=0` — matches the Python `default=0` in `get_param()` on the model side.
- `help` text informs the admin that `0` disables the policy.

#### `_on_change_mins()`

```python
@api.onchange('minlength')
def _on_change_mins(self):
    self.minlength = max(0, self.minlength or 0)
```

**Purpose**: Client-side guard against negative or null input. Forces the field to `0` if the user types a negative number or clears the field.

---

## Views

### Settings Panel — `res_config_settings_views.xml`

```xml
<xpath expr="//setting[@id='allow_import']" position="before">
    <setting>
        <field name="minlength"/>
    </setting>
</xpath>
```

Injects the `minlength` field into the **General Settings / Base Setup** panel, immediately before the `allow_import` setting. Priority `20` (higher than default `16`) ensures this view loads after the base setup form is fully defined.

### Change Password Wizards — `res_users.xml`

Two QWeb view overrides:

| Record ID | Inherits | Widget Applied |
|-----------|----------|----------------|
| `change_password` | `base.change_password_own_form` | `password_meter` on `new_password` |
| `change_password_multi` | `base.change_password_wizard_user_tree_view` | `password_meter` on `new_passwd` |

Both switch the password input field from the default `password` type to the `password_meter` widget (OWL component) that shows real-time strength feedback.

---

## Frontend — OWL Components

### `password_policy.js` — Core Scoring Engine

#### `ConcretePolicy` Class

```javascript
constructor({ minlength, minwords, minclasses }) {
    this.minlength = minlength || 0;
    this.minwords  = minwords  || 0;
    this.minclasses = minclasses || 0;
}
```

Three policy dimensions — all optional with a `|| 0` fallback:

| Dimension | Regex used | Purpose |
|-----------|------------|---------|
| `minlength` | — | Character count floor |
| `minwords` | `/[^\W_]+/` (split) | Count of word-like segments separated by non-word chars |
| `minclasses` | 4 separate regex | Number of distinct character classes present: lower, upper, digit, symbol |

**Word-counting caveat**: `\w` includes `_`, so the regex uses `[^\W_]+` (the inverse of `\W` plus underscore). Also, ASCII-only — non-Latin scripts score zero on class checks.

#### `score(password)` — Score Computation

```javascript
score(password) {
    const lengthscore  = Math.min(password.length / this.minlength, 1.0);
    const wordCount    = password.split(/[^\W_]+/).length - 1;
    const wordscore    = this.minwords !== 0
                            ? Math.min(wordCount / this.minwords, 1.0) : 1.0;
    const classes      = ([a-z] + [A-Z] + [\d] + [^\w]) as 0-4 integer;
    const classesscore = Math.min(classes / this.minclasses, 1.0);

    return lengthscore * wordscore * classesscore;
}
```

**Multiplicative scoring**: All three sub-scores multiply together. If any sub-score is `0`, the overall score is `0`. This means a 20-character password with only lowercase letters and no digits scores `0` if `minclasses >= 2`.

#### `computeScore(password, requirements, recommendations)`

```javascript
export function computeScore(password, requirements, recommendations) {
    const req = requirements.score(password);
    const rec = recommendations.score(password);
    return Math.pow(req, 4) * (0.5 + Math.pow(rec, 2) / 2);
}
```

**Score formula**: `req^4 * (0.5 + rec^2 / 2)`

- Requirements score is raised to the 4th power — heavily penalizes non-compliant passwords.
- Recommendations score is squared, contributing at most `+0.5` to the multiplier.
- **Result range**: `[0, 1]` — maps directly to the `<meter>` element's `value` attribute.
- `low="0.5"`, `high="0.99"` on the meter means: below `0.5` = red (Weak), `0.5–0.99` = yellow (Medium), `1.0` = green (Strong).

#### `recommendations` — Recommended Policy Presets

```javascript
export const recommendations = {
    score(password) {
        return Math.max(...this.policies.map((p) => p.score(password)));
    },
    policies: [
        new ConcretePolicy({ minlength: 16, minwords: 2 }),  // 2-word passphrase
        new ConcretePolicy({ minlength: 12, minclasses: 3 }), // 3-class random
    ],
};
```

Based on 2016 research by Shane Wee's (cited in code as "Shay"). Takes the **maximum** score across both policies — a password that satisfies either passphrase-style or random-style guidelines scores well.

### `password_meter.js` — Meter Display Component (OWL)

```javascript
static template = xml`
    <div class="o_password_meter_container">
        <span t-out="passwordStrengthParams.text" .../>
        <meter class="o_password_meter"
            min="0" low="0.5" high="0.99" max="1" optimum="1"
            t-att-value="value"/>
    </div>
`;
```

| Meter value | CSS class | Label |
|-------------|-----------|-------|
| `< 0.5` | `text-danger` | Weak (red) |
| `0.5 – 0.99` | `text-warning` | Medium (yellow) |
| `1.0` | `text-success` | Strong (green) |

The `title` attribute shows the requirements text (e.g., "at least 8 characters") via `_t()` translation.

### `password_field.js` — `password_meter` Field Widget

```javascript
onWillStart(async () => {
    const policy = await orm.call("res.users", "get_password_policy");
    this.state.required = new ConcretePolicy(policy);
});
```

Registered in `web.core.registry` under `fields` as `password_meter`. The component fetches the live policy via an RPC call on mount, so the meter always reflects the current database setting (not a stale client-side default).

**Readonly handling**: When `props.readonly` is true, the field shows `*`.repeat(password length) — does **not** reveal the actual password.

---

## Security Considerations

1. **Server-side enforcement is authoritative**: The client-side `password_meter` widget is cosmetic/guidance only. A determined attacker or API client can bypass JavaScript and submit any password. The `_check_password_policy` method in Python is the actual enforcement point.

2. **No timing attack mitigation**: `_check_password_policy` iterates all passwords and raises a single error. The loop exits only on `continue` (empty) or after the full loop. This is acceptable for a length check; cryptographic comparison functions (used in password hashing) require constant-time algorithms.

3. **`sudo()` in config reads**: Both `get_password_policy()` and `_check_password_policy()` use `.sudo()` to read `ir.config_parameter`. This is correct — config params require superuser write access, and the read is non-sensitive.

4. **`minlength = 0` disables policy**: An admin can effectively disable password length enforcement by setting `minlength = 0`. This is a deliberate design choice (no minimum floor other than 0). In high-security deployments, enforce a minimum of 8 or 12 at the database or auth middleware level.

5. **No rate limiting**: `_check_password_policy` does not implement any rate limiting or account lockout. Brute-force attempts against a user's password are not mitigated by this module. Consider `auth_totp` or MFA for high-value accounts.

---

## Performance Implications

| Operation | Cost | Notes |
|-----------|------|-------|
| `_check_password_policy` | 1 `ir.config_parameter` read per batch | O(1) regardless of batch size |
| `get_password_policy` | 1 `ir.config_parameter` read per RPC | Called once per form mount |
| `PasswordField` mount | 1 ORM RPC call | Async on `onWillStart`; does not block render |
| `score()` computation | O(n) on password length | Pure client-side JavaScript; negligible |
| `computeScore()` | O(1) | Two `ConcretePolicy.score()` calls + math |

**No N+1**: `_check_password_policy` takes a pre-mapped list of passwords; it does not browse additional records.

---

## Odoo 18 → Odoo 19 Changes

| Area | Change |
|------|--------|
| **OWL migration** | Password field rewritten from old `WebClient`-style JS to OWL `Component`. `password_field.js` and `password_meter.js` are new OWL components replacing legacy field widgets. |
| **`auth_signup` split** | In Odoo 18, advanced policies (special char, uppercase, etc.) lived here. In Odoo 19, `auth_password_policy_signup` may be a separate module. The core `auth_password_policy` module itself is unchanged in structure. |
| **`password_meter` widget** | Now registered in `web.core.registry` as `fields.password_meter` using `registry.category("fields").add()`, the standard Odoo 17+ widget registration pattern. |

---

## CSS

**File**: `static/src/css/password_field.css`

```css
owl-component[name="password_meter"] .o_password_meter_container {
    position: relative;
    float: right;
}
```

Positions the meter container `float: right` so it sits to the right of the password input inline. Note: The `owl-component` attribute selector targets the component's wrapping element in the DOM.

---

## Related Modules

| Module | Relationship |
|--------|-------------|
| [[Modules/auth_signup]] | Provides the signup flow; `auth_password_policy` activates on password set during signup |
| [[Modules/auth_totp]] | Two-factor authentication; complementary to password policy |
| [[Modules/base_setup]] | Provides the `res.config.settings` form layout this module injects into |
| `auth_password_policy_signup` | Extended policy with `minwords`, `minclasses`; activates during portal sign-up |

---

## Tags

`#auth` `#password` `#security` `#policy` `#orm` `#client-action` `#owL` `#web`
