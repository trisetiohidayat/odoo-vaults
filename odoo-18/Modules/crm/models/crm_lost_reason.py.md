# CRM Lost Reason - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/crm/models/crm_lost_reason.py`
**Lines:** ~34

---

## Model Overview

`crm.lost.reason` is a simple reference model for categorizing why leads/opportunities were lost.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required; reason name |
| `active` | Boolean | Archive/unarchive |
| `leads_count` | Integer | Computed; number of lost leads with this reason |

---

## Key Methods

### `action_lost_leads()`
**Returns:** An `ir.actions.act_window` that opens the list of leads matching `['|', ('active', '=', False), ('lost_reason_id', '=', self.id)]`.
**Visibility:** Only shows leads that are inactive (lost) and have this reason set.

---

## Edge Cases

1. **Renaming a lost reason:** Does not retroactively rename the reason on existing lost leads; leads retain the reason ID.
2. **Deleting a lost reason:** May fail if leads reference it (standard `unlink` restriction).
3. **`leads_count` accuracy:** The computed count uses `active_test=False`, meaning it counts archived leads as well.

---

## Failure Modes

1. **Delete with referenced leads:** Standard Odoo `unlink` will raise a `ForeignKey` constraint error.
