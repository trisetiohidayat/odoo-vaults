# Purchase Order Workflow: Dari Create PO Sampai Receipt di Odoo 19

**Summary:** Purchase Order workflow di Odoo 19 mencakup dua fase utama — RFQ (Request for Quotation) dan Purchase Order — dimulai dari pembuatan draft PO, melewati konfirmasi untuk mengunci order dan membuat receipt picking, hingga validasi receipt untuk memperbarui quantity on-hand dan stock valuation.

---

## Key Points

- Purchase order melewati state machine: `draft` (RFQ) → `sent` → `to approve` → `purchase` → `done` / `cancel` (via [modules/purchase.md](qmd://odoo19-vault/modules/purchase.md))
- Konfirmasi PO (`button_confirm()`) secara otomatis membuat `stock.picking` bertipe `incoming` yang linked ke PO via field `origin` (via [flows/purchase/purchase-order-creation-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-creation-flow.md))
- Receipt picking harus divalidasi secara independen oleh warehouse user — tidak otomatis done saat PO di-confirm (via [flows/purchase/purchase-order-receipt-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-receipt-flow.md))
- `purchase.order.line.qty_received` di-update setiap kali receipt divalidasi, memungkinkan PO melacak progress pengiriman (via [flows/purchase/purchase-order-receipt-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-receipt-flow.md))
- Partial receipts, over-receipts, dan under-receipts didukung — PO tetap terbuka sampai semua quantity diterima atau user menutup secara eksplisit (via [flows/purchase/purchase-order-receipt-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-receipt-flow.md))
- State `stock.picking` di-compute dari state `stock.move` — tidak writable langsung (via [modules/stock-picking.md](qmd://odoo19-vault/modules/stock-picking.md))

---

## Detail Explanation

### Fase 1: Pembuatan RFQ / Purchase Order (State: `draft`)

Workflow dimulai saat user navigasi ke **Purchase → Orders → Requests for Quotation** dan klik **Create**. Pada fase ini:

1. `purchase.order` dibuat dengan state awal `draft` (RFQ)
2. Setiap order line trigger `_onchange_product_id()` secara otomatis yang:
   - Membaca harga dari `product.supplierinfo` (seller list vendor)
   - Set `product_uom` dari `seller.product_uom` atau `product.uom_po_id`
   - Ambil pajak supplier dari `product.supplier_taxes_id`
   - Sync product name/description dari seller info

Order dalam state `draft` masih bisa diedit — vendor, product lines, quantity, dan harga masih bisa diubah. Baru setelah user klik **Confirm Order**, order terkunci dan tidak bisa sembarangan diedit.

(via [flows/purchase/purchase-order-creation-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-creation-flow.md))

### Fase 2: Konfirmasi PO — RFQ Menjadi Purchase Order (State: `purchase`)

Saat user mengklik **Confirm Order**, `button_confirm()` dipanggil yang menjalankan `_button_confirm()` dengan langkah-langkah berikut:

```
1.  _check_order_enabled() — validasi order masih draft dan tidak cancelled
2.  self.write({'state': 'purchase', 'date_approve': now()})
    → Order terkunci, tidak bisa diedit (tergantung po_lock setting)
3.  for each po_line: _onchange_product_ids()
    → _add_supplier_to_product()
      → product.supplierinfo.create() — vendor ditambahkan ke seller list product
        → Future PO akan default ke vendor ini
4.  _create_picking()
    → Membuat stock.picking bertipe 'incoming'
    → Membuat stock.move per po_line
    → Picking dalam state 'draft' — warehouse user harus konfirmasi & validate
```

**Catatan penting:** Konfirmasi PO tidak otomatis menyelesaikan receipt. Picking masih dalam state `draft` dan harus diproses secara terpisah oleh warehouse user. Ini adalah decoupling antara "saya sudah memesan" (PO confirmed) dan "barang sudah sampai" (receipt validated).

(via [flows/purchase/purchase-order-creation-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-creation-flow.md) dan [flows/purchase/purchase-order-receipt-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-receipt-flow.md))

### Fase 3: Receipt Picking — Terima Barang (stock.picking state flow)

Receipt picking dibuat secara otomatis oleh `_create_picking()` dengan konfigurasi:
- `location_id` = vendor/supplier location
- `location_dest_id` = warehouse `lot_stock_id` (stock location)
- `origin` = `purchase.order.name` (linking PO ke receipt)
- `picking_type_id` = incoming receipt type

Picking melewati state machine berikut:

```
draft
  └─→ confirmed  [action_confirm() — user klik "Confirm" pada receipt]
        ├─→ Stock.move state: 'confirmed'
        └─→ Tidak ada reservation untuk incoming receipt
  └─→ assigned   [action_assign() — user klik "Check Availability"]
        ├─→ incoming receipt: tidak perlu reservation
        └─→ Bisa langsung proceed ke validate
  └─→ done      [action_done() — user klik "Validate" pada receipt]
        ├─→ stock.quant di-update (quantity on-hand bertambah)
        ├─→ stock.valuation.layer dibuat (jika valuation aktif)
        ├─→ account.move (journal entry) dibuat (jika auto-valuation)
        └─→ purchase.order.line.qty_received di-update
```

**Apa yang terjadi saat receipt di-validate:**
1. `stock.quant` di-update — quantity on-hand bertambah di stock location
2. `stock.valuation.layer` dibuat — tracking nilai inventory
3. `account.move` (journal entry) dibuat jika `stock_account` terinstall dan valuation real-time aktif
4. `purchase.order.line.qty_received` di-update sesuai quantity yang diterima

(via [flows/purchase/purchase-order-receipt-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-receipt-flow.md) dan [modules/stock-picking.md](qmd://odoo19-vault/modules/stock-picking.md))

### State Machine Lengkap purchase.order

```
draft (RFQ)
    └─→ sent (RFQ Sent)
           └─→ to approve (To Approve)  [two-step validation: amount >= threshold]
                  └─→ purchase (Purchase Order)  [button_approve()]
                         └─→ done (Done)  [semua qty_received = product_qty]
                         └─→ cancel (Cancelled)  [harus unlock dulu jika locked]
```

(via [modules/purchase.md](qmd://odoo19-vault/modules/purchase.md))

---

## Ringkasan Alur Lengkap

```
USER                    SISTEM                         STOCK
─────────────────────────────────────────────────────────────────
Create PO
  (draft/RFQ)
    │
Klik "Confirm Order" ──→ button_confirm()
    │                      ├─ state = 'purchase'
    │                      ├─ _add_supplier_to_product()
    │                      └─ _create_picking()
    │                           → stock.picking (incoming) dibuat
    │                           → stock.move per line dibuat
    │                           → state = 'draft'
    │
    │                  Receipt picking 'draft'
    │
Klik "Confirm"
receipt ───────────────→ action_confirm()
    │                        → state = 'confirmed'
    │
Klik "Check Availability" → action_assign()
    │                        → state = 'assigned' (no reservation for incoming)
    │
Klik "Validate" ──────────→ action_done()
    │                        ├─ stock.quant updated (+qty on-hand)
    │                        ├─ stock.valuation.layer dibuat
    │                        ├─ account.move (journal entry) dibuat
    │                        └─ purchase.order.line.qty_received di-update
    │
    │
PO qty_received == product_qty?
    └─→ YA → PO siap untuk vendor bill creation
```

---

## Related Topics

- [[Modules/Purchase]] — semua model dan field detail Purchase Order
- [[Modules/Stock]] — stock.quant, stock.move, stock.location
- [[flows/purchase/purchase-to-bill-flow]] — lanjutan workflow: dari receipt ke vendor bill
- [[flows/stock/receipt-flow]] — alur receipt yang lebih detail termasuk return
- [[Modules/stock-account]] — inventory valuation saat receipt divalidasi

---

## Sources

- [flows/purchase/purchase-order-creation-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-creation-flow.md) — Alur lengkap metode chain dari RFQ creation ke PO confirmation
- [flows/purchase/purchase-order-receipt-flow.md](qmd://odoo19-vault/flows/purchase/purchase-order-receipt-flow.md) — Alur detail receipt picking dari confirm sampai validate
- [modules/purchase.md](qmd://odoo19-vault/modules/purchase.md) — Purchase module overview, state machine, model inventory
- [modules/stock-picking.md](qmd://odoo19-vault/modules/stock-picking.md) — stock.picking model, field index, state workflow
