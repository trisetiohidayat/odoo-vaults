# Stock Valuation Flow di Odoo 19: Dari Receipt hingga Journal Entry

**Pertanyaan:** Jelaskan bagaimana stock valuation flow bekerja di Odoo 19, dari receipt sampai journal entry.

**Summary:** Ketika user memvalidasi receipt (menekan tombol Validate), Odoo secara otomatis meng-create journal entry accounting yang menggerakkan nilai dari Stock Interim Account ke Stock Valuation Account, dengan setiap done move menciptakan `stock.valuation.layer` dan sepasang `account.move.line` (debit-kredit).

---

## Key Points

- **Trigger:** `stock.move.action_done()` dipanggil saat user klik **Validate** pada `stock.picking` receipt — tidak ada aksi user setelah itu selain kaskade valuation logic otomatis (via [flows/stock/stock-valuation-flow.md](qmd://odoo19-vault/flows/stock/stock-valuation-flow.md))
- **Dua metode valuation:** `real_time` (otomatis per move) vs `periodic` (manual, adjustment di closing), dikontrol via field `property_valuation` pada `product.category` (via [modules/stock-account.md](qmd://odoo19-vault/modules/stock-account.md))
- **Model inti:** `stock.valuation.layer` mencatat setiap perubahan inventory valuation (FIFO/AVCO), dan link ke `account.move` yang dihasilkan (via [modules/stock-account.md](qmd://odoo19-vault/modules/stock-account.md))
- **Purchase receipt khusus:** Terima barang dari vendor → receipt move → stock valuation layer → journal entry (via [flows/stock/stock-valuation-flow.md](qmd://odoo19-vault/flows/stock/stock-valuation-flow.md) + cross-vault source)
- **Account configuration:** Valuasi di-resolve dari `product.categ_id.property_valuation` atau fallback ke `company.inventory_valuation` (via [modules/stock-account.md](qmd://odoo19-vault/modules/stock-account.md))

---

## Detail Explanation

### 1. Konfigurasi Awal: Cost Method dan Valuation Type

Sebelum flow berjalan, produk harus dikonfigurasi dengan benar. Ada **tiga cost method** di Odoo 19:

| Cost Method | Penjelasan |
|---|---|
| **FIFO** (First In First Out) | Nilai keluar = harga layer tertua yang masuk |
| **AVCO** (Average Cost) | Nilai keluar = rata-rata tertimbang dari semua layer masuk |
| **Standard Price** | Nilai keluar = `product.standard_price` yang fixed |

Dan **dua valuation type** di level `product.category`:

- **Real-Time (Perpetual):** Setiap stock move yang di-validate langsung trigger journal entry
- **Periodic (Manual):** Tidak ada journal entry otomatis; valuation di-adjust secara manual saat closing period

Konfigurasi ini di-resolve secara berjenjang:
```
product.categ_id.property_valuation → company.inventory_valuation
product.categ_id.property_cost_method → company.cost_method
```
(via [modules/stock-account.md](qmd://odoo19-vault/modules/stock-account.md))

### 2. Dari Purchase Order ke Receipt Picking

Ketika Purchase Order di-confirm, Odoo secara otomatis membuat `stock.picking` bertipe **incoming** (receipt). User menerima barang fisik dan meng-input jumlah yang diterima (qty_done) di move lines.

### 3. Trigger Utama: `stock.move.action_done()`

Saat user klik **Validate** pada receipt picking, metode `action_done()` dipanggil. Ini adalah **system-level trigger** — tidak ada aksi user setelahnya selain kaskade valuation logic otomatis.

Chain lengkapnya:
```
stock.move.action_done()
  ├─► stock.move._action_done()
  │     ├─► move lines confirmed (qty_done set)
  │     ├─► stock.move.write({'state': 'done'})
  │     └─► _action_done() — routing berdasarkan move type
  │           └─► IF move_type == 'incoming': receipt valuation logic
  │
  └─► stock.picking._compute_state() → state = 'done'
```
(via [flows/stock/stock-valuation-flow.md](qmd://odoo19-vault/flows/stock/stock-valuation-flow.md))

### 4. Receipt Valuation: stock.quant update + valuation layer creation

Untuk incoming move (receipt), chain berjalan:

1. `stock.move.line._action_done()` dipanggil
2. `stock.quant._update_available_quantity()` meng-update quantity di location tujuan (storage/location inventory)
3. **Jika valuation == 'real_time':**
   - `stock.valuation.layer.create()` dibuat dengan field:
     - `product_id`, `stock_move_id`
     - `quantity` = qty_done
     - `unit_cost` = dari PO line (untuk receipt dari vendor)
     - `value` = qty * unit_cost
     - `account_move_id` = None (belum diisi)
4. `_create_account_move_line()` dipanggil untuk buat journal entry

### 5. Journal Entry Creation (Real-Time)

Dari valuation layer, Odoo menciptakan `account.move` dengan pasangan debit-credit:

```
account.move.create({
    move_type: 'entry',
    line_ids: [
        (0,0, {
            account_id: STOCK_VALUATION_ACCOUNT,
            debit: value,         # Stock Asset naik
            credit: 0
        }),
        (0,0, {
            account_id: STOCK_INTERIM_ACCOUNT,
            debit: 0,
            credit: value         # Stock Interim (AP/Pending) turun
        })
    ]
})
```

Logika debet/kredit untuk **Receipt**:
- **Debit** Stock Valuation Account (aktiva inventory bertambah)
- **Credit** Stock Interim Account (pending receipt/AP dari vendor)

Setelah move dibuat, `stock.valuation.layer` di-write dengan `account_move_id`-nya:
```python
stock.valuation.layer.write({account_move_id: new_move.id})
```
(via [flows/stock/stock-valuation-flow.md](qmd://odoo19-vault/flows/stock/stock-valuation-flow.md))

### 6. Cost Method Resolution untuk Receipt

Untuk **purchase receipt**, unit_cost berasal dari PO line (`price_unit`). Tapi bagaimana cost disimpan tergantung cost method:

- **FIFO:** Layer baru dibuat per receipt; value = qty * PO price_unit. Layer ini akan jadi sumber cost saat produk keluar nanti.
- **AVCO:** Odoo rata-rata cost lama dengan cost receipt baru: `new_avg = (old_value + new_qty*cost) / (old_qty + new_qty)`. Layer dengan `quantity` negatif tetap menggunakan current average cost.
- **Standard:** Jika `product.standard_price` berbeda dari PO price, selisih langsung trigger revaluation journal entry.

### 7. Delivery/Sales Valuation (Completeness)

Untuk outgoing moves (delivery), chain mirip tapi dengan logika berbeda:

- **FIFO:** `stock.quant._consume_layer_fifo()` consume layer tertua berdasarkan `create_date`
- **AVCO:** `value_out = qty * current_avg_cost`
- **Standard:** `value = qty * product.standard_price`

Journal entry untuk delivery (real-time):
```
Debit:  Stock Interim Account (pending delivery)
Credit: Stock Valuation Account (inventory asset turun)
```

### 8. Landed Costs: Penambahan Nilai Inventory

Setelah receipt, landed costs (freight, duties, handling) bisa ditambahkan ke inventory valuation via `stock.valuation.layer._adjust_landed_cost()` yang dipanggil oleh `ir.cron`. Ini menambah nilai inventory tanpa perlu validate move baru.

---

## Accounts yang Terlibat

| Account | Role | arah |
|---|---|---|
| **Stock Valuation Account** (asset) | Menyimpan nilai inventory di-balance sheet | Debit saat receipt, Credit saat delivery |
| **Stock Interim Account** (asset/liability) | Buffer antara receipt/delivery dan actual accounting | Credit saat receipt, Debit saat delivery |

Konfigurasi akun ada di:
- `res.company` (default valuation accounts)
- `product.category` (`property_stock_valuation_account_id`)
- `stock.location` (bisa override per location)

(via [modules/stock-account.md](qmd://odoo19-vault/modules/stock-account.md))

---

## Model-Model yang Terlibat

| Model | File | Peran |
|---|---|---|
| `stock.move` | `stock/models/stock_move.py` | Trigger utama `action_done()` |
| `stock.quant` | `stock/models/stock_quant.py` | Update qty per location/lot |
| `stock.valuation.layer` | `stock_account/models/stock_valuation_layer.py` | Catat setiap perubahan nilai |
| `account.move` | `account/models/account_move.py` | Journal entry untuk valuation |
| `product.category` | `product/models/product_category.py` | `property_valuation`, `property_cost_method` |
| `account.journal` | `account/models/account_journal.py` | Journal untuk Stock Valuation (type: "general" atau "stock journal") |

---

## Summary Diagram

```
[Purchase Order confirmed]
       │
       ▼
[Incoming Picking created]  ── stock.picking (receipt)
       │
       ▼
[User: Validate button]
       │
       ▼
stock.move.action_done()
       │
       ├─► stock.quant.update: qty on hand +1
       │
       ├─► IF real_time:
       │     stock.valuation.layer.create({
       │       qty, unit_cost, value
       │     })
       │       │
       │       ▼
       │     account.move.create() ── ST: "Stock Journal"
       │       │                         Debit: Stock Valuation (asset +)
       │       │                         Credit: Stock Interim (asset -)
       │       ▼
       │     stock.valuation.layer.write(account_move_id)
       │
       └─► IF periodic: layer dibuat tapi TIDAK ada journal entry
       │
       ▼
[Picking state = 'done']
```

---

## Sources

- [flows/stock/stock-valuation-flow.md](qmd://odoo19-vault/flows/stock/stock-valuation-flow.md) — Main flow document dengan complete method chain
- [modules/stock-account.md](qmd://odoo19-vault/modules/stock-account.md) — Module documentation dengan model extensions, configuration fields, dan cost method hierarchy
- [odoo-minimal-wiki/wiki/sources/odoo19-stock-account-stock-move-py.md](qmd://odoo-minimal-wiki/wiki/sources/odoo19-stock-account-stock-move-py.md) — Source code reference untuk real-time valuation logic
- [odoo-minimal-wiki/wiki/sources/odoo19-purchase-stock-stock-move-py.md](qmd://odoo-minimal-wiki/wiki/sources/odoo19-purchase-stock-stock-move-py.md) — Source code untuk purchase_stock extension pada stock move

---

*Generated: 2026-04-17 using QMD AI Researcher skill on odoo19-vault*