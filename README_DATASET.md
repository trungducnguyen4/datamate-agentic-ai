# Vietnamese Business QA 5-Million-Row Dataset (datamate_vietnamese_qa_5m.csv)

## 1. Overview & Data Dimensions
`datamate_vietnamese_qa_5m.csv` is an industrial-scale synthetic dataset containing **exactly 5,000,000 records** (excluding header) designed specifically for stress-testing natural language data QA, semantic parsing, temporal reasoning, and answerability evaluation under the Zalo AI Challenge 2026 specifications.

- **Total Rows**: Exactly 5,000,000 data lines + 1 header line.
- **Encoding**: UTF-8 without BOM.
- **Determinism**: Generated via `scripts/generate_5m_dataset.py` using fixed seed (`seed = 42`).
- **Data Grain**: Line-item level (each row represents a specific item sold in an invoice).

---

## 2. Business Domains Covered
The dataset covers 8 distinct Vietnamese retail, service, and wholesale sectors:

1. **Pharmacies & Medical Supplies (`duoc_pham`)**:
   - Products: Panadol Extra đỏ vỉ, Berberin hộp, Khẩu trang y tế 4 lớp, Máy đo huyết áp Omron, Siro ho Prospan...
   - Distinctive attributes: Expiration dates (`han_su_dung`), prescription and OTC batches.
2. **F&B, Cafes & Milk Tea (`fnb_cafe`)**:
   - Products: Trà sữa trân châu đường đen, Cà phê sữa đá, Bạc xỉu đá, Trà đào cam sả...
   - Distinctive attributes: High daily transaction volume, perishable single-day items.
3. **Building Materials (`vlxd`)**:
   - Products: Xi măng Hà Tiên PCB40 bao 50kg, Cát vàng xây tô m3, Gạch tuynel 4 lỗ, Sắt phi 10 Hòa Phát...
   - Distinctive attributes: High unit value, wholesale quantities, trade credit debt (`tien_no`).
4. **Grocery & Convenience Stores (`tap_hoa`)**:
   - Products: Nước suối Lavie 500ml, Mì Hảo Hảo tôm chua cay, Sữa tươi Vinamilk 1L, Dầu ăn Simply...
   - Distinctive attributes: Fast-moving consumer goods, diverse packaging units (chai, gói, thùng, túi).
5. **Fashion & Apparel (`thoi_trang`)**:
   - Products: Áo thun cotton nam, Quần jean ống suông, Váy hoa nhí vintage, Áo sơ mi trắng công sở...
   - Distinctive attributes: No expiration dates, seasonal demand peaks.
6. **Electronics & Accessories (`dien_may`)**:
   - Products: Củ sạc nhanh Anker 20W, Tai nghe bluetooth Hoco, Quạt lửng Senko, Ấm siêu tốc Philips...
   - Distinctive attributes: Non-perishable, high unit price, warranty tracking.
7. **Restaurants & Food Services (`nha_hang`)**:
   - Products: Lẩu cá lăng măng chua, Bò lúc lắc khoai tây, Mực một nắng sa tế, Bia Tiger...
   - Distinctive attributes: Weekend dinner peaks, food service portions.
8. **Wholesale & Retail Distributors (`dai_ly_si`)**:
   - Products: Thùng mì Hảo Hảo 30 gói, Thùng nước ngọt Coca Cola 24 lon, Bao gạo thơm Lài Miên 50kg...
   - Distinctive attributes: Bulk packaging, high volume, business-to-business credit terms.

---

## 3. Schema & Column Specifications

| Column Name | Data Type | Semantic Role | Description | Nullable / Imperfections |
| :--- | :--- | :--- | :--- | :--- |
| `ma_giao_dich` | TEXT | primary_key | Unique line item identifier (`TX_0000001`...) | No |
| `ma_hoa_don` | TEXT | invoice_id | Invoice grouping ID (1–4 line items per invoice) | No |
| `ngay_tao` | DATE | date | Transaction date (`YYYY-MM-DD`), 2024-01-01 to 2026-10-31 | No |
| `nganh_hang` | TEXT | domain | Business sector identifier | No |
| `ma_sp` | TEXT | product_code | Unique SKU code (`SP_DP_01`, `SP_VLXD_01`...) | No |
| `ten_san_pham` | TEXT | product_name | Authentic Vietnamese product name | No |
| `don_vi_tinh` | TEXT | unit | Unit of measure (bao, gói, hộp, chai, lon, ly, cái...) | No |
| `so_luong` | INTEGER | quantity | Units sold | No |
| `don_gia` | NUMBER | unit_price | Retail selling price (VND) | No |
| `gia_von` | NUMBER | cost | Cost of goods sold (COGS) per unit (VND) | No |
| `giam_gia` | NUMBER | discount | Line discount applied (VND) | No (0 if no discount) |
| `thanh_tien` | NUMBER | total_amount | Net line total: `(so_luong * don_gia) - giam_gia` | No |
| `trang_thai` | TEXT | status | Order status (`Hoàn thành`, `Đã thanh toán`, `Đã hủy`, `Đổi trả`) | No |
| `han_su_dung` | DATE | expiry | Expiration date (`YYYY-MM-DD`) | Yes (Null for non-perishables) |
| `ma_khach_hang`| TEXT | customer_id | Customer ID (`KH_001`...) | Yes (Null for 15% walk-ins) |
| `ten_khach_hang`| TEXT | customer_name | Authentic Vietnamese customer name | Yes (Null for 15% walk-ins) |
| `hang_khach` | TEXT | loyalty_tier | Customer tier (`VIP`, `Thân thiết`, `Tiêu chuẩn`, `Mới`) | Yes (Null for 15% walk-ins) |
| `phuong_thuc_tt`| TEXT | payment_method| `Tiền mặt`, `Chuyển khoản`, `Thẻ tín dụng`, `Công nợ`, `Ví điện tử` | No |
| `trang_thai_tt`| TEXT | payment_status| `Đã thanh toán`, `Còn nợ`, `Quá hạn` | No |
| `tien_no` | NUMBER | debt | Outstanding unpaid balance (VND) | No (0 if fully paid) |
| `so_luong_ton` | INTEGER | stock | Available warehouse inventory on hand | No |
| `ma_nhan_vien` | TEXT | employee_id | Sales staff identifier (`NV_01`...) | No |
| `ten_nhan_vien`| TEXT | employee_name | Salesperson full Vietnamese name | No |

---

## 4. Financial & Mathematical Integrity
- Every row satisfies:
  $$\text{thanh\_tien} = \text{round}((\text{so\_luong} \times \text{don\_gia}) - \text{giam\_gia}, 2)$$
- Profit metrics can be strictly evaluated as:
  $$\text{loi\_nhuan} = \text{thanh\_tien} - (\text{so\_luong} \times \text{gia\_von})$$
- Line-item grain ensures that running `SUM(thanh_tien)` or `SUM(so_luong)` produces mathematically correct results without duplicating invoice totals.
