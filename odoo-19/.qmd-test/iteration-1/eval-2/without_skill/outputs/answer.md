# Purchase Order Workflow di Odoo: Dari Create PO Sampai Receipt

## 1. Purchase Order States (Status PO)

Purchase Order di Odoo memiliki state berikut:

| State | Arti |
|-------|------|
| `Draft` | PO dibuat tapi belum dikirim ke vendor |
| `Sent` | PO sudah dikirim ke vendor (RFQ) |
| `Purchase Order` | PO sudah disetujui/dikonfirmasi |
| `Done` | PO selesai (semua receipt diterima) |
| `Cancelled` | PO dibatalkan |

---

## 2. Langkah-Langkah Workflow

### Step 1: Create Purchase Order (Draft)

1. Buka menu: **Purchases > Orders > Purchase Orders**
2. Klik **Create**
3. Isi field:
   - **Vendor** (partner)
   - **Company** (jika multi-company)
   - **Currency**
4. Di tab **Products**, tambahkan baris:
   - Product
   - Quantity
   - Unit Price
   - Taxes
   - Delivery Date (tanggal pengiriman yang diharapkan)
5. Klik **Save**

PO masih dalam state **Draft**.

---

### Step 2: Confirm Order (Purchase Order)

Dari state **Draft**, user meng-klik tombol **Confirm Order** (atau **Confirm Purchase**).

Effect:
- PO state berubah menjadi **Purchase Order**
- Stok internal receipt (**Incoming Shipment / Stock Picking**) **secara otomatis** di-generate oleh Odoo (tergantung konfigurasi `procurement` dan `stock` module)
- Sistem juga bisa otomatis membuat **Move** untuk `stock.location` terkait

> **Catatan:** Jika `stock` module terinstal, Odoo otomatis membuat picking type `Receipts` dan `stock.picking` incoming shipment.

---

### Step 3: Validate Receipt / Receive Goods

1. Buka menu: **Inventory > Operations > Receipts** (atau dari PO langsung klik **Receipt** smart button)
2. Akan muncul record **Stock Picking** bertipe `incoming`
3. Klik pada picking tersebut
4. Lakukan validasi:
   - Cek/isi **-quantity done** (jumlah yang benar-benar diterima) di setiap move line
   - Klik **Validate** (tombol hijau)

Effect saat validate:
- `stock.move` lines di-confirm
- `stock.quant` di-create/updated (stok bertambah di lokasi warehouse terkait)
- Jika `stock_account` module terinstal, **valuation journal entry** (journal entry penilaian inventaris) juga di-generate secara otomatis (debit persediaan, credit biaya/biaya diterima di muka/ atau lawan akun sesuai konfigurasi)
- Jika purchase invoice sudah dibuat dan matched, accounting entries sudah match

---

### Step 4: Create Vendor Bill (Invoice)

Ini bisa dilakukan **sebelum** atau **sesudah** receipt, tergantung alur yang digunakan:

**Option A: Create Invoice from PO**
- Dari PO, klik **Create Bill** / **Create Invoice**
- Sistem membuat draft `account.move` (Vendor Bill)
- Klik **Confirm** untuk mem-validate invoice

**Option B: Match Receipt dengan Invoice**
- Di vendor bill, gunakan tab **Bill Lines** untuk mendeteksi automatic `purchase.deadline` / purchase order lines
- Sistem melakukan **3-way matching** (PO qty, Receipt qty, Invoice qty)
- Jika semua match dan sesuai, invoice disetujui

---

### Step 5: PO Done

PO akan otomatis berubah ke state **Done** ketika:
- Semua qty di semua order lines sudah diterima penuh (receipt Done)
- Atau user bisa manual set ke Done

---

## 3. Diagram Sederhana

```
Draft PO
  │
  ▼
[Confirm Order] ────────────────────► Purchase Order
  │                                     │
  │ (auto-create)                       │ (user validates)
  ▼                                     ▼
Stock Picking (Incoming)         Receive Goods
  │                              │
  │                              │ (quant updated)
  │                              ▼
  │                         Receipt Done
  │                              │
  └──────────┬───────────────────┘
             │
             ▼
         Create Vendor Bill
             │
             ▼
         Validate Bill
             │
             ▼
         PO Done / Cancelled
```

---

## 4. Key Models yang Terlibat

| Model | Fungsi |
|-------|--------|
| `purchase.order` | Header PO, vendor, terms |
| `purchase.order.line` | Detail product, qty, price |
| `stock.picking` | Incoming shipment record |
| `stock.move` | Individual stock movement lines |
| `stock.quant` | Actual inventory quantities |
| `account.move` | Vendor bill / journal entries |
| `account.move.line` | Journal entry lines |

---

## 5. Konfigurasi Penting

- **Purchase Control**: Settings > Purchases > Allow to create draft invoices / Control Purchase Minimum Planes
- **Stock Valuation**: Install `stock_account` agar valuation entries dibuat otomatis saat receipt
- **Automatic PO Confirmation**: Settings > Purchases > Automatic PO validation (opsional)
- **Procumbentment Configuration**: Buy rule di product category / product template harus disetup agar purchase otomatis ter-trigger

---

## 6. Ringkasan

1. **Create PO** (Draft) -> isi vendor & produk
2. **Confirm Order** -> PO terkirim, stock.picking (receipt) dibuat otomatis
3. **Validate Receipt** -> barang masuk, quant di-update, valuation entry (jika stock_account aktif)
4. **Create/Receive Vendor Bill** -> invoice dari vendor
5. **PO Done** -> seluruh proses selesai
