"""Deterministic generator for datamate_vietnamese_qa_5m.csv.

Generates exactly 5,000,000 realistic Vietnamese business QA data rows.
Covering 8 multi-industry business domains with realistic seasonality,
Tet holiday peaks, authentic product catalogs, customer tiers, and payment debts.
"""
from __future__ import annotations
import csv
import datetime
import os
import random
import sys
import time
from typing import Dict, List, Tuple

# Set fixed seed for 100% deterministic reproducibility
RANDOM_SEED = 42
TOTAL_ROWS = 5_000_000
CHUNK_SIZE = 50_000
OUTPUT_FILE = "datamate_vietnamese_qa_5m.csv"

# -----------------------------------------------------------------------------
# Catalog Definition across 8 Domains
# -----------------------------------------------------------------------------
CATALOG = {
    "duoc_pham": [
        ("SP_DP_01", "Panadol Extra đỏ vỉ", "vỉ", 15000, 11000, True),
        ("SP_DP_02", "Berberin hộp", "hộp", 15000, 10000, True),
        ("SP_DP_03", "Khẩu trang 4 lớp y tế", "hộp", 25000, 16000, True),
        ("SP_DP_04", "Máy đo huyết áp Omron", "cái", 1200000, 900000, False),
        ("SP_DP_05", "Nước muối sinh lý Natri Clorid 0.9% 500ml", "chai", 8000, 5000, True),
        ("SP_DP_06", "Bông gòn y tế Bạch Tuyết 100g", "gói", 18000, 12000, True),
        ("SP_DP_07", "Cồn y tế 70 độ 500ml", "chai", 22000, 15000, True),
        ("SP_DP_08", "Vitamin C 500mg hộp 10 vỉ", "hộp", 45000, 32000, True),
        ("SP_DP_09", "Dầu gió xanh Con Én 24ml", "chai", 35000, 26000, True),
        ("SP_DP_10", "Thuốc nhỏ mắt Rohto 12ml", "lọ", 52000, 38000, True),
        ("SP_DP_11", "Siro ho Prospan 100ml", "lọ", 78000, 60000, True),
        ("SP_DP_12", "Nhiệt kế điện tử Microlife", "cái", 210000, 155000, False),
    ],
    "fnb_cafe": [
        ("SP_FNB_01", "Trà sữa trân châu đường đen", "ly", 35000, 12000, True),
        ("SP_FNB_02", "Trà đào cam sả", "ly", 30000, 10000, True),
        ("SP_FNB_03", "Cà phê sữa đá", "ly", 25000, 8000, True),
        ("SP_FNB_04", "Cà phê đen đá", "ly", 20000, 6000, True),
        ("SP_FNB_05", "Trà olong sữa nướng", "ly", 38000, 13000, True),
        ("SP_FNB_06", "Bạc xỉu đá", "ly", 28000, 9000, True),
        ("SP_FNB_07", "Matcha latte đá xay", "ly", 42000, 15000, True),
        ("SP_FNB_08", "Sinh tố bơ dừa", "ly", 45000, 18000, True),
        ("SP_FNB_09", "Bánh sừng bò phô mai", "cái", 25000, 12000, True),
        ("SP_FNB_10", "Trà chanh giã tay", "ly", 22000, 7000, True),
    ],
    "vlxd": [
        ("SP_VLXD_01", "Xi măng Hà Tiên PCB40 bao 50kg", "bao", 90000, 78000, False),
        ("SP_VLXD_02", "Xi măng Holcim PCB40 bao 50kg", "bao", 92000, 80000, False),
        ("SP_VLXD_03", "Cát vàng xây tô m3", "m3", 300000, 220000, False),
        ("SP_VLXD_04", "Đá xanh 1x2 m3", "m3", 350000, 260000, False),
        ("SP_VLXD_05", "Gạch tuynel 4 lỗ Bình Dương", "thiên", 1200000, 950000, False),
        ("SP_VLXD_06", "Sắt phi 10 Hòa Phát cây 11.7m", "cây", 115000, 98000, False),
        ("SP_VLXD_07", "Sắt phi 12 Pomina cây 11.7m", "cây", 165000, 142000, False),
        ("SP_VLXD_08", "Ống nhựa PVC Bình Minh D90", "cây", 140000, 115000, False),
        ("SP_VLXD_09", "Sơn lót chống kiềm Dulux 18L", "thùng", 1450000, 1180000, True),
        ("SP_VLXD_10", "Tôn lạnh mạ kẽm Hoa Sen 0.45mm", "m", 95000, 81000, False),
    ],
    "tap_hoa": [
        ("SP_TH_01", "Nước suối Lavie 500ml", "chai", 6000, 4200, True),
        ("SP_TH_02", "Nước ngọt Coca Cola lon 320ml", "lon", 10000, 7500, True),
        ("SP_TH_03", "Mì Hảo Hảo tôm chua cay gói 75g", "gói", 4500, 3600, True),
        ("SP_TH_04", "Sữa tươi tiệt trùng Vinamilk 100% ít đường 1L", "hộp", 36000, 28500, True),
        ("SP_TH_05", "Nước mắm Nam Ngư Đệ Nhị 900ml", "chai", 28000, 22000, True),
        ("SP_TH_06", "Dầu ăn Simply đậu nành 1L", "chai", 58000, 47000, True),
        ("SP_TH_07", "Gạo thơm ST25 bao 5kg", "bao", 185000, 155000, True),
        ("SP_TH_08", "Trứng gà Ba Huân hộp 10 quả", "hộp", 32000, 25000, True),
        ("SP_TH_09", "Nước giặt OMO Matic cửa trên túi 3.6kg", "túi", 195000, 160000, True),
        ("SP_TH_10", "Nước rửa chén Sunlight chanh 750g", "chai", 26000, 19500, True),
    ],
    "thoi_trang": [
        ("SP_TT_01", "Áo thun cotton nam cổ tròn", "cái", 120000, 65000, False),
        ("SP_TT_02", "Quần jean nam ống suông", "cái", 320000, 180000, False),
        ("SP_TT_03", "Váy hoa nhí xòe vintage", "cái", 280000, 150000, False),
        ("SP_TT_04", "Áo sơ mi trắng công sở nữ", "cái", 210000, 115000, False),
        ("SP_TT_05", "Áo khoác dù gió unisex 2 lớp", "cái", 260000, 140000, False),
        ("SP_TT_06", "Quần short kaki nam", "cái", 160000, 85000, False),
        ("SP_TT_07", "Giày sneaker trắng năng động", "đôi", 450000, 270000, False),
        ("SP_TT_08", "Tất cổ ngắn cotton kháng khuẩn (combo 5 đôi)", "hộp", 65000, 32000, False),
    ],
    "dien_may": [
        ("SP_DM_01", "Củ sạc nhanh Anker 20W Type-C", "cái", 250000, 170000, False),
        ("SP_DM_02", "Cáp sạc bọc dù Type-C Baseus 1m", "sợi", 85000, 45000, False),
        ("SP_DM_03", "Tai nghe bluetooth True Wireless Hoco", "bộ", 320000, 210000, False),
        ("SP_DM_04", "Nồi chiên không dầu Sunhouse 6L", "cái", 1250000, 890000, False),
        ("SP_DM_05", "Quạt lửng Senko cánh 40cm", "cái", 340000, 265000, False),
        ("SP_DM_06", "Ấm siêu tốc Inox 1.8L Philips", "cái", 420000, 310000, False),
        ("SP_DM_07", "Chuột không dây Logitech M170", "cái", 185000, 135000, False),
        ("SP_DM_08", "Pin sạc dự phòng Xiaomi 10000mAh", "cái", 310000, 225000, False),
    ],
    "nha_hang": [
        ("SP_NH_01", "Lẩu cá lăng măng chua nồi lớn", "nồi", 380000, 210000, True),
        ("SP_NH_02", "Bò lúc lắc khoai tây chiên", "đĩa", 145000, 85000, True),
        ("SP_NH_03", "Gà hấp lá chanh nửa con", "đĩa", 160000, 95000, True),
        ("SP_NH_04", "Mực một nắng nướng sa tế", "đĩa", 195000, 120000, True),
        ("SP_NH_05", "Cơm chiên hải sản Hoàng Kim", "thố", 110000, 55000, True),
        ("SP_NH_06", "Rau luộc kho quẹt tôm thịt", "đĩa", 75000, 32000, True),
        ("SP_NH_07", "Bia Tiger lon 330ml", "lon", 22000, 16500, True),
        ("SP_NH_08", "Trái cây thập cẩm theo mùa", "đĩa", 80000, 35000, True),
    ],
    "dai_ly_si": [
        ("SP_SI_01", "Thùng mì Hảo Hảo tôm chua cay 30 gói", "thùng", 125000, 112000, True),
        ("SP_SI_02", "Thùng nước ngọt Coca Cola 24 lon", "thùng", 215000, 192000, True),
        ("SP_SI_03", "Thùng bia Heineken 24 lon", "thùng", 435000, 395000, True),
        ("SP_SI_04", "Thùng sữa tươi tiệt trùng Vinamilk 48 hộp 180ml", "thùng", 345000, 310000, True),
        ("SP_SI_05", "Thùng dầu ăn Simply 12 chai 1L", "thùng", 640000, 585000, True),
        ("SP_SI_06", "Bao gạo thơm Lài Miên 50kg", "bao", 950000, 860000, True),
    ],
}

DOMAINS = list(CATALOG.keys())

CUSTOMERS = [
    ("KH_001", "Nguyễn Văn An", "VIP"),
    ("KH_002", "Trần Thị Bình", "Thân thiết"),
    ("KH_003", "Lê Hoàng Cường", "Tiêu chuẩn"),
    ("KH_004", "Phạm Thu Dung", "VIP"),
    ("KH_005", "Hoàng Văn Em", "Mới"),
    ("KH_006", "Vũ Thị Giang", "Thân thiết"),
    ("KH_007", "Đặng Minh Hải", "VIP"),
    ("KH_008", "Bùi Thị Kim", "Tiêu chuẩn"),
    ("KH_009", "Đỗ Văn Long", "Thân thiết"),
    ("KH_010", "Ngô Thị Mai", "VIP"),
    ("KH_011", "Dương Hoàng Nam", "Tiêu chuẩn"),
    ("KH_012", "Lý Thị Oanh", "Mới"),
    ("KH_013", "Phan Thanh Phúc", "VIP"),
    ("KH_014", "Võ Thị Quỳnh", "Thân thiết"),
    ("KH_015", "Trịnh Văn Sơn", "Tiêu chuẩn"),
    ("KH_016", "Đinh Thị Thảo", "VIP"),
    ("KH_017", "Lâm Quốc Uy", "Mới"),
    ("KH_018", "Mai Thị Vân", "Thân thiết"),
    ("KH_019", "Đoàn Văn Xuân", "VIP"),
    ("KH_020", "Cao Thị Yến", "Tiêu chuẩn"),
    ("KH_021", "Phòng khám BS Minh", "VIP"),
    ("KH_022", "Trạm y tế Xã Tân Tiến", "VIP"),
    ("KH_023", "Công ty TNHH Xây dựng Phú Thịnh", "VIP"),
    ("KH_024", "Cửa hàng Tạp hóa Bà Tám", "Thân thiết"),
    ("KH_025", "Quán cơm Phố Cũ", "Thân thiết"),
    ("KH_026", "Nguyễn Thị Thu Hằng", "Tiêu chuẩn"),
    ("KH_027", "Trần Đình Trọng", "Mới"),
    ("KH_028", "Lê Văn Đức", "Thân thiết"),
    ("KH_029", "Phạm Quang Huy", "VIP"),
    ("KH_030", "Nguyễn Tiến Linh", "Tiêu chuẩn"),
]

EMPLOYEES = [
    ("NV_01", "Nguyễn Thị Thùy Trang"),
    ("NV_02", "Trần Quốc Toản"),
    ("NV_03", "Lê Thị Bích Ngọc"),
    ("NV_04", "Phạm Văn Đồng"),
    ("NV_05", "Hoàng Kim Oanh"),
    ("NV_06", "Vũ Đức Thắng"),
    ("NV_07", "Đặng Thu Thảo"),
    ("NV_08", "Bùi Minh Trí"),
    ("NV_09", "Đỗ Thu Hà"),
    ("NV_10", "Ngô Văn Kiên"),
]

HEADER = [
    "ma_giao_dich",
    "ma_hoa_don",
    "ngay_tao",
    "nganh_hang",
    "ma_sp",
    "ten_san_pham",
    "don_vi_tinh",
    "so_luong",
    "don_gia",
    "gia_von",
    "giam_gia",
    "thanh_tien",
    "trang_thai",
    "han_su_dung",
    "ma_khach_hang",
    "ten_khach_hang",
    "hang_khach",
    "phuong_thuc_tt",
    "trang_thai_tt",
    "tien_no",
    "so_luong_ton",
    "ma_nhan_vien",
    "ten_nhan_vien",
]


def generate_dataset(output_path: str = OUTPUT_FILE, total_rows: int = TOTAL_ROWS) -> None:
    print(f"=== Starting 5M Dataset Generation ===")
    print(f"Target file: {output_path}")
    print(f"Target data rows: {total_rows:,}")
    print(f"Random seed: {RANDOM_SEED}")

    random.seed(RANDOM_SEED)
    t_start = time.time()

    # Precompute date distribution over 2024-01-01 to 2026-10-31 (1035 days)
    start_date = datetime.date(2024, 1, 1)
    end_date = datetime.date(2026, 10, 31)
    total_days = (end_date - start_date).days + 1

    # Weighting days: Tet peaks have 2.5x traffic
    # Tet windows:
    # 2024: Jan 20 to Feb 15
    # 2025: Jan 10 to Feb 05
    # 2026: Jan 28 to Feb 25
    tet_ranges = [
        (datetime.date(2024, 1, 20), datetime.date(2024, 2, 15)),
        (datetime.date(2025, 1, 10), datetime.date(2025, 2, 5)),
        (datetime.date(2026, 1, 28), datetime.date(2026, 2, 25)),
    ]

    dates_pool = []
    date_weights = []
    for d_idx in range(total_days):
        cur_d = start_date + datetime.timedelta(days=d_idx)
        dates_pool.append(cur_d)
        w = 1.0
        # Check Tet peak
        for s_t, e_t in tet_ranges:
            if s_t <= cur_d <= e_t:
                w = 2.5
                break
        # Weekend boost
        if cur_d.weekday() in (5, 6):
            w *= 1.3
        date_weights.append(w)

    # Status distributions
    status_choices = ["Hoàn thành", "Đã thanh toán", "Đã hủy", "Đổi trả"]
    status_weights = [0.85, 0.08, 0.04, 0.03]

    payment_methods = ["Tiền mặt", "Chuyển khoản", "Thẻ tín dụng", "Công nợ", "Ví điện tử"]
    payment_weights = [0.45, 0.35, 0.10, 0.08, 0.02]

    written_count = 0
    invoice_seq = 1
    current_invoice_id = f"HD{dates_pool[0].strftime('%Y%m%d')}_{invoice_seq:05d}"
    invoice_lines_left = random.randint(1, 4)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)

        chunk_rows = []
        for i in range(1, total_rows + 1):
            # Select date using weighted random choices in bulk periodically
            cur_date = random.choices(dates_pool, weights=date_weights, k=1)[0]

            # Invoices group 1-4 lines together
            if invoice_lines_left <= 0:
                invoice_seq += 1
                current_invoice_id = f"HD{cur_date.strftime('%Y%m%d')}_{invoice_seq:06d}"
                invoice_lines_left = random.randint(1, 4)
            invoice_lines_left -= 1

            tx_id = f"TX_{i:07d}"
            date_str = cur_date.strftime("%Y-%m-%d")

            # Domain selection
            domain = random.choice(DOMAINS)
            prod = random.choice(CATALOG[domain])
            p_code, p_name, p_unit, p_price, p_cost, p_has_exp = prod

            # Quantity: Wholesale / Building materials has larger quantities
            if domain in ("vlxd", "dai_ly_si"):
                qty = random.randint(5, 50)
            elif domain == "tap_hoa":
                qty = random.randint(1, 10)
            elif domain in ("fnb_cafe", "nha_hang"):
                qty = random.randint(1, 6)
            else:
                qty = random.randint(1, 5)

            # Discount: 10% chance of 5% - 10% discount
            if random.random() < 0.10:
                raw_amt = qty * p_price
                disc = round(raw_amt * random.uniform(0.05, 0.10), 0)
            else:
                disc = 0.0

            total_amt = round(qty * p_price - disc, 2)
            status = random.choices(status_choices, weights=status_weights, k=1)[0]

            # Expiry date: perishable / medicines have expiry date 6-24 months from transaction
            if p_has_exp:
                exp_offset = random.randint(180, 720)
                exp_date_str = (cur_date + datetime.timedelta(days=exp_offset)).strftime("%Y-%m-%d")
            else:
                exp_date_str = ""

            # Customer: 15% anonymous walk-ins
            if random.random() < 0.15:
                cust_id = ""
                cust_name = ""
                cust_tier = ""
            else:
                c = random.choice(CUSTOMERS)
                cust_id, cust_name, cust_tier = c

            # Payment
            pm = random.choices(payment_methods, weights=payment_weights, k=1)[0]
            if pm == "Công nợ":
                debt_sub = random.random()
                if debt_sub < 0.65:
                    pay_status = "Còn nợ"
                    debt_amt = total_amt
                elif debt_sub < 0.85:
                    pay_status = "Quá hạn"
                    debt_amt = total_amt
                else:
                    pay_status = "Đã thanh toán"
                    debt_amt = 0.0
            else:
                pay_status = "Đã thanh toán"
                debt_amt = 0.0

            stock_qty = random.randint(10, 500)
            emp = random.choice(EMPLOYEES)
            emp_id, emp_name = emp

            row = [
                tx_id,
                current_invoice_id,
                date_str,
                domain,
                p_code,
                p_name,
                p_unit,
                qty,
                p_price,
                p_cost,
                disc,
                total_amt,
                status,
                exp_date_str,
                cust_id,
                cust_name,
                cust_tier,
                pm,
                pay_status,
                debt_amt,
                stock_qty,
                emp_id,
                emp_name,
            ]
            chunk_rows.append(row)

            if len(chunk_rows) >= CHUNK_SIZE:
                writer.writerows(chunk_rows)
                written_count += len(chunk_rows)
                chunk_rows = []
                if written_count % 500_000 == 0 or written_count == total_rows:
                    elapsed = time.time() - t_start
                    rate = written_count / elapsed
                    print(f"Generated {written_count:,} / {total_rows:,} rows ({rate:,.0f} rows/s)...")

        if chunk_rows:
            writer.writerows(chunk_rows)
            written_count += len(chunk_rows)

    elapsed_total = time.time() - t_start
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n Generation Complete!")
    print(f"Total Rows Written (excluding header): {written_count:,}")
    print(f"File Size: {file_size_mb:.2f} MB")
    print(f"Total Generation Time: {elapsed_total:.2f} s ({written_count / elapsed_total:,.0f} rows/s)")


def validate_dataset(filepath: str = OUTPUT_FILE, expected_rows: int = TOTAL_ROWS) -> bool:
    print(f"\n=== Validating Dataset Integrity: {filepath} ===")
    t_start = time.time()

    row_count = 0
    math_errors = 0
    header_checked = False

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        if header != HEADER:
            print(f" Header mismatch! Expected: {HEADER}, Got: {header}")
            return False

        for row in reader:
            row_count += 1
            qty = float(row[7])
            price = float(row[8])
            disc = float(row[10])
            total = float(row[11])
            expected_total = round(qty * price - disc, 2)
            if round(total, 2) != expected_total:
                math_errors += 1
                if math_errors <= 5:
                    print(f"Math Error at row {row_count}: {row[0]}, total={total}, expected={expected_total}")

            if row_count % 1_000_000 == 0:
                print(f"Validated {row_count:,} rows...")

    elapsed = time.time() - t_start
    print(f"Validation Time: {elapsed:.2f} s")
    print(f"Validated Rows: {row_count:,} (Expected: {expected_rows:,})")
    print(f"Math calculation errors: {math_errors}")

    if row_count == expected_rows and math_errors == 0:
        print(" Integrity Check PASSED: Exactly 5,000,000 valid data rows, 0 calculation errors.")
        return True
    else:
        print(" Integrity Check FAILED!")
        return False


if __name__ == "__main__":
    generate_dataset()
    ok = validate_dataset()
    sys.exit(0 if ok else 1)
