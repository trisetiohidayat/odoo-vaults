# Stock Valuation Flow di Odoo 19: Dari Receipt hingga Journal Entry

## Ringkasan Alur

Stock valuation di Odoo 19 melacak nilai persediaan melalui serangkaian transaksi yang dimulai dari receipt barang supplier, bergerak melalui landed cost (jika ada), hingga akhirnya menghasilkan journal entry yang mempengaruhi laporan keuangan. Alur ini dikelola oleh modul `stock_account` dan terkait erat dengan `account.move` dan `stock.quant`.

---

## 1. Konfigurasi Awal (Prasyarat)

Sebelum valuation berjalan, beberapa konfigurasi harus dipenuhi:

- **Product**: Harus设置为 **"Auto"** valuation (bukan "Manual" atau "No Valuation"). Product memiliki `product_id.categ_id.property_stock_valuation_account_id` yang menunjuk ke akun persediaan.
- **Product Category**: Setiap kategori produk memiliki akun valuation (contoh: "Inventory Valuation") dan akun journal input/output.
- **Warehouse**: Lokasi warehouse harus dikaitkan dengan `view_location_id` dan `lot_stock_id`.
- **Journal**: Setiap kategori produk memiliki `property_stock_journal` yang menentukan jurnal tempat journal entry valuation dibuat.

---

## 2. Alur Lengkap: Purchase Receipt → Journal Entry

### Tahap 1: Purchase Order (PO) Dibuat

```
purchase.order (draft) → purchase.order.line
```

PO berisi produk yang akan dibeli dengan harga beli. Harga ini menjadi dasar awal valuation.

---

### Tahap 2: Receipt (Penerimaan Barang) → Stock Move Dibuat

Ketika PO di-approve dan receipt dilakukan:

```
stock.picking (type: receipt) dibuat
stock.move dibuat dari vendor location → stock location
```

Move ini bernilai berdasarkan harga beli di PO (atau standar price jika dikonfigurasi). Secara default, valuation menggunakan **product cost** dari PO (atau `standard_price` jika tidak ada PO).

---

### Tahap 3: Validation Receipt → Stock Quant Ter-create

Ketika user klik **"Validate"** pada receipt:

```
stock.move (done) → stock.quant dibuat/update
```

Pada titik ini:
- `stock.quant` record dibuat di `stock.location` (lot_stock_id warehouse) dengan kuantitas dan nilai (unit cost × qty).
- Jika **FIFO**: cost diambil dari harga PO.
- Jika **AVCO (Average Cost)**: cost dihitung rata-rata tertimbang.

---

### Tahap 4: Journal Entry Valuation Dibuat (Automatic)

Begitu move menuju status **done**, Odoo secara otomatis membuat journal entry valuation melalui mekanisme accounting layer di `stock_account`:

**Mekanisme internal:**

1. **Angkaian Valuation Layer**: Odoo menyimpan pencatatan valuation per SKU/per location. Setiap quant menyimpan `value` (nilai inventory).

2. **Accounting Entry Generation** (via `stock.move._account_entry_move()`):
   - **Debit**: `stock.valuation.account` (di kategori produk) → asset persediaan
   - **Credit**: `stock.input.account` (atau `stock.valuation.account` lawan) → tergantung konfigurasi journal

**Contoh untuk receipt (incoming):**

| Akun | Debit | Credit |
|------|-------|--------|
| Inventory Valuation (Asset) | XXX | |
| Stock Received Not Invoiced (Payable) | | XXX |

> Catatan: Akun "Stock Received Not Invoiced" (SRNI) adalah akun temporary yang menunggu vendor bill. Ini akan di-offset saat bill dibuat (PO → Vendor Bill matching via `purchase_bill_match_update`).

---

### Tahap 5: Landed Costs (Opsional)

Jika ada biaya tambahan (shipping, import duty, handling):

```
stock.landed.cost (model) → membuat journal entry tambahan
```

Landed cost allocation menambahkan biaya ke unit cost produk, sehingga:
- Debit: Inventory Valuation
- Credit: various expense/asset accounts

Ini dilakukan melalui wizard `stock.landed.cost` dan menambah nilai quant.

---

## 3. Dua Metode Valuation Utama

### FIFO (First In, First Out)

- Setiap incoming receipt menambah layer costing baru
- Saat keluar (delivery), cost diambil dari layer tertua
- Cocok untuk produk dengan masa pakai terbatas

### AVCO (Average Cost / Moving Average)

- Setiap incoming receipt mengupdate `standard_price` rata-rata
- Saat keluar, cost menggunakan harga rata-rata terkini
- Inventory valuation = `standard_price × qty on hand`

---

## 4. Proses Update Nilai (Re-valuation)

Jika ada perubahan harga setelah quant masuk:

```
stock.valuation.adjustments
```

Melalui mekanisme:
1. Quant lama di-adjust (mengubah unit cost)
2. Journal entry dibuat untuk selisih:
   - Jika naik: Debit Inventory Valuation, Credit Stock Valuation Adjustment (income)
   - Jika turun: Debit Stock Valuation Adjustment (expense), Credit Inventory Valuation

---

## 5. Delivery (Keluar Barang)

Untuk completeness, saat delivery dilakukan (SO delivery):

1. **Move done** → `stock.quant` quantity berkurang
2. **Journal entry dibuat** (cost of goods sold):
   - Debit: Cost of Goods Sold (Expense)
   - Credit: Inventory Valuation (Asset)

---

## 6. Diagram Alur Sederhana

```
PO Created → PO Approved
                    ↓
Receipt Scheduled → Receipt Validated
                              ↓
                    stock.move (done)
                              ↓
                    stock.quant created/updated
                              ↓
                    Journal Entry Generated
                     (Debit: Inventory Asset
                      Credit: Stock Input/SRNI)
                              ↓
                    Vendor Bill Created → SRNI cleared
                              ↓
                    (Optional) Landed Cost → adjusts unit cost
```

---

## 7. Akun-Akun yang Terlibat

| Akun | Jenis | Fungsi |
|------|-------|--------|
| `property_stock_valuation_account` (di product category) | Asset | Tempat debit saat receipt, kredit saat delivery |
| `property_stock_journal` | Journal | Jurnal tempat entry posted |
| `property_stock_account_input_categ` | Asset/Pending | Credit saat receipt, menunjukkan barang masuk tapi belum di-invoice |
| `property_stock_account_output_categ` | Expense | Debit saat delivery (COGS) |

---

## 8. Kapan Journal Entry Dibuat?

Journal entry valuation dibuat **saat move selesai (done)** melalui `stock_account` module, bukan saat invoice. Ini berarti:

1. **Receipt validation** → inventory valued di buku saat barang fisik masuk
2. **Vendor bill posting** → mengoffset akun SRNI

Ini mengikuti prinsip double-entry bookkeeping: Inventory meningkat saat barang masuk, payable meningkat saat bill di-post.

---

## 9. Pencatatan Multi-Currency

Jika PO dalam mata uang asing:
- Stock move valued dalam **company currency** menggunakan rate saat receipt
- SRNI journal entry juga dalam company currency
- Differences dari currency conversion posting ke **Forex Adjustment** account

---

## 10. Debugging & Troubleshooting

- **Tidak ada journal entry?** → Pastikan product category punya valuation account + stock journal. Pastikan `stock_account` module terinstall.
- **Nilai tidak sesuai?** → Check `stock.quant` value field. Check `product.template.standard_price`.
- **Layer cost hilang?** → Check `stock.move.location_dest_id` valuation layers.

---

## Kesimpulan

Stock valuation flow di Odoo 19 bekerja melalui integrasi antara:

1. **`stock`** module: mengelola quant, move, dan valuation layers
2. **`stock_account`** module: menjembatani ke accounting dengan generate journal entries
3. **`account`** module: posting dan reporting

Flow utama: Receipt validates → Quant updated with value → Journal entry debit inventory asset + credit stock input (SRNI) → Vendor bill offsets SRNI. Untuk landed cost, unit cost bisa di-adjust post-receipt dengan journal entry tambahan.