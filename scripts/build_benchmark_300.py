"""Build the 300+ Vietnamese Question Benchmark Dataset for DataMate.

Generates tests/data/vietnamese_qa_benchmark_300.json with 350 comprehensive
test questions across 17 linguistic, semantic, temporal, and answerability categories.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List

OUTPUT_PATH = "tests/data/vietnamese_qa_benchmark_300.json"


def build_benchmark() -> List[Dict[str, Any]]:
    questions = []

    # Helper to add questions
    def add_q(
        qid: str,
        category: str,
        biz: str,
        q_text: str,
        intent: str,
        measures: List[str],
        ans_type: str,
        expected_ans: Any,
        reason: str,
        time_range: Dict[str, str] | None = None,
        as_of_date: str = "2026-03-04",
        cluster_id: str | None = None,
        metamorphic_rule: str | None = None,
    ):
        questions.append({
            "id": qid,
            "category": category,
            "business_id": biz,
            "as_of_date": as_of_date,
            "question": q_text,
            "expected_intent": intent,
            "expected_measures": measures,
            "expected_time_range": time_range,
            "expected_type": ans_type,
            "expected_answer": expected_ans,
            "reason": reason,
            "paraphrase_cluster_id": cluster_id,
            "metamorphic_rule": metamorphic_rule,
        })

    # -------------------------------------------------------------------------
    # 1. Formal Vietnamese (20 questions)
    # -------------------------------------------------------------------------
    formal_data = [
        ("BM_FORMAL_01", "Tháng này mặt hàng nào có doanh số cao nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "Formal revenue inquiry"),
        ("BM_FORMAL_02", "Anh/chị vui lòng kiểm tra doanh thu tháng vừa rồi.", "revenue", ["thanh_tien"], "number", 825000, "Formal request for previous month revenue (Feb 2026: 225k + 600k = 825k)"),
        ("BM_FORMAL_03", "Cho tôi biết sản phẩm có số lượng tiêu thụ lớn nhất trong tháng này.", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Formal quantity ranking"),
        ("BM_FORMAL_04", "Nhờ bạn thống kê các khách hàng còn công nợ chưa thanh toán.", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Formal debt listing"),
        ("BM_FORMAL_05", "Xin hỏi tổng số tiền bán hàng trong tuần trước là bao nhiêu?", "revenue", ["thanh_tien"], "number", 600000, "Formal previous calendar week revenue (2026-02-23 to 2026-03-01: 600k)"),
        ("BM_FORMAL_06", "Vui lòng cho biết số lượng đơn hàng đã thực hiện trong tháng 3 năm 2026.", "order_count", ["count_orders"], "number", 4, "Formal monthly order count"),
        ("BM_FORMAL_07", "Kính nhờ kiểm tra mặt hàng có sản lượng bán thấp nhất tháng này.", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Formal lowest sales quantity ranking"),
        ("BM_FORMAL_08", "Đơn hàng nào đạt giá trị thanh toán cao nhất từ trước đến nay?", "order_max", ["thanh_tien"], "string", "HD07", "Formal max value order"),
        ("BM_FORMAL_09", "Xin cho biết tổng doanh thu phát sinh trong ngày 04/03/2026.", "revenue", ["thanh_tien"], "number", 3650000, "Formal specific date revenue (1.25M + 2.4M = 3.65M)"),
        ("BM_FORMAL_10", "Khách hàng nào đã đóng góp doanh thu lớn nhất cho cửa hàng?", "top_customer", ["thanh_tien"], "unanswerable", None, "Missing customer attribution in invoice table -> UNANSWERABLE"),
        ("BM_FORMAL_11", "Cho tôi hỏi mặt hàng nào có doanh thu thấp nhất tháng này.", "ranking_product_revenue", ["thanh_tien"], "string", "Berberin hộp", "Formal lowest revenue item (Berberin 450k)"),
        ("BM_FORMAL_12", "Tổng số tiền nợ hiện tại của tất cả khách hàng là bao nhiêu?", "total_debt", ["tong_no"], "number", 16500000, "Formal total debt calculation (4.5M + 12M = 16.5M)"),
        ("BM_FORMAL_13", "Xin kiểm tra xem có bao nhiêu giao dịch bị hủy bỏ trong tuần rồi.", "cancel_count", ["trang_thai"], "number", 0, "Formal cancellations count"),
        ("BM_FORMAL_14", "Tổng sản lượng thuốc đã bán ra trong tháng này là bao nhiêu?", "quantity", ["so_luong"], "number", 182, "Formal total items quantity in March 2026 (100 + 30 + 50 + 2 = 182)"),
        ("BM_FORMAL_15", "Vui lòng tra cứu doanh thu của cùng kỳ năm ngoái.", "revenue", ["thanh_tien"], "number", 750000, "Formal YoY same period revenue (March 2025: 750,000)"),
        ("BM_FORMAL_16", "Xin hỏi từ sau Tết Nguyên Đán đến nay cửa hàng đã bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 237, "Formal post-Tet quantity calculation (237 items)"),
        ("BM_FORMAL_17", "Mặt hàng nào có số lượng bán nhiều nhất trong ngày hôm qua?", "ranking_product_quantity", ["so_luong"], "string", "Berberin hộp", "Formal yesterday top seller (March 3rd: Berberin 30)"),
        ("BM_FORMAL_18", "Cho tôi biết doanh thu lũy kế từ đầu tháng đến hết hôm qua.", "revenue", ["thanh_tien"], "number", 1950000, "Formal MTD until yesterday revenue (March 1-3: 1.5M + 450k = 1.95M)"),
        ("BM_FORMAL_19", "Cửa hàng có bao nhiêu sản phẩm đang bị tồn đọng chưa bán được?", "unsold_check", ["stock"], "boolean", False, "Formal unsold stock status"),
        ("BM_FORMAL_20", "Vui lòng cho biết tổng doanh số đạt được trong 7 ngày gần đây.", "revenue", ["thanh_tien"], "number", 5600000, "Formal dynamic 7-day rolling revenue"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in formal_data:
        add_q(qid, "formal", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 2. Casual Vietnamese (20 questions)
    # -------------------------------------------------------------------------
    casual_data = [
        ("BM_CASUAL_01", "Tháng này món nào bán chạy nhất vậy?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Casual quantity ranking"),
        ("BM_CASUAL_02", "Cửa hàng mình còn ai nợ tiền không?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Casual debtor query"),
        ("BM_CASUAL_03", "Tuần rồi bán được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 600000, "Casual prev week revenue"),
        ("BM_CASUAL_04", "Mặt hàng nào đang bán ế nhất?", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Casual lowest quantity sold"),
        ("BM_CASUAL_05", "Xem giúp mình doanh thu tháng này nhé.", "revenue", ["thanh_tien"], "number", 5600000, "Casual monthly revenue"),
        ("BM_CASUAL_06", "Hôm qua bán được bao nhiêu tiền thế?", "revenue", ["thanh_tien"], "number", 450000, "Casual yesterday revenue (March 3: 450k)"),
        ("BM_CASUAL_07", "Tháng này tiệm mình bán được mấy đơn rồi?", "order_count", ["count_orders"], "number", 4, "Casual monthly orders count"),
        ("BM_CASUAL_08", "Đơn nào nhiều tiền nhất vậy bạn?", "order_max", ["thanh_tien"], "string", "HD07", "Casual max order value"),
        ("BM_CASUAL_09", "Thuốc nào bán được nhiều nhất tuần rồi?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Casual prev week top seller"),
        ("BM_CASUAL_10", "Tiệm mình còn bao nhiêu tiền nợ chưa thu được?", "total_debt", ["tong_no"], "number", 16500000, "Casual total debt balance"),
        ("BM_CASUAL_11", "7 ngày gần đây bán được bao nhiêu món?", "quantity", ["so_luong"], "number", 182, "Casual dynamic 7 days items sold"),
        ("BM_CASUAL_12", "Cùng kỳ năm ngoái bán được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 750000, "Casual YoY revenue"),
        ("BM_CASUAL_13", "Mặt hàng nào thu về ít tiền nhất tháng này?", "ranking_product_revenue", ["thanh_tien"], "string", "Berberin hộp", "Casual lowest revenue item"),
        ("BM_CASUAL_14", "Từ sau Tết đến nay bán được bao nhiêu tiền rồi?", "revenue", ["thanh_tien"], "number", 6425000, "Casual post-Tet revenue"),
        ("BM_CASUAL_15", "Tháng trước bán được bao nhiêu tiền vậy?", "revenue", ["thanh_tien"], "number", 825000, "Casual prev month revenue"),
        ("BM_CASUAL_16", "Tháng này bán được bao nhiêu hộp thuốc?", "quantity", ["so_luong"], "number", 182, "Casual monthly total quantity"),
        ("BM_CASUAL_17", "Hôm nay bán được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 3650000, "Casual as_of_date revenue"),
        ("BM_CASUAL_18", "Món nào mang về nhiều tiền nhất tháng này?", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "Casual top revenue item"),
        ("BM_CASUAL_19", "Có ai nợ tiền lâu chưa trả không?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Casual debt inquiry"),
        ("BM_CASUAL_20", "Tuần này tiệm mình bán được bao nhiêu đơn rồi?", "order_count", ["count_orders"], "number", 4, "Casual current week order count"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in casual_data:
        add_q(qid, "casual", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 3. Abbreviations & Texting (20 questions)
    # -------------------------------------------------------------------------
    abbr_data = [
        ("BM_ABBR_01", "sp bán dc nhiều nhất tuần rồi là gì", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Teencode: sp, dc"),
        ("BM_ABBR_02", "tháng này sp nào bán chạy nhất vậy shop", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Teencode: sp, shop"),
        ("BM_ABBR_03", "tuần rồi bán dc bn tiền?", "revenue", ["thanh_tien"], "number", 600000, "Teencode: dc, bn"),
        ("BM_ABBR_04", "còn ai nợ tiền chưa trả ko?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Teencode: ko"),
        ("BM_ABBR_05", "doanh thu tháng này nhiu z?", "revenue", ["thanh_tien"], "number", 5600000, "Teencode: nhiu, z"),
        ("BM_ABBR_06", "check giúp mình doanh thu tháng này nha", "revenue", ["thanh_tien"], "number", 5600000, "Slang: check, nha"),
        ("BM_ABBR_07", "sp nào bán dc nhìu nhất tuần rùi z shop", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Teencode: sp, dc, nhìu, rùi, z, shop"),
        ("BM_ABBR_08", "xem dùm tui tháng này bán được nhiêu rồi", "revenue", ["thanh_tien"], "number", 5600000, "Slang: dùm, tui, nhiêu"),
        ("BM_ABBR_09", "thuốc nào sắp hết date vậy?", "unanswerable_missing_expiry", ["han_su_dung"], "unanswerable", None, "Slang: date -> expiry (missing in biz_099)"),
        ("BM_ABBR_10", "dt tháng này bn z?", "revenue", ["thanh_tien"], "number", 5600000, "Teencode: dt, bn, z"),
        ("BM_ABBR_11", "sl bán ra tháng này là bn?", "quantity", ["so_luong"], "number", 182, "Teencode: sl, bn"),
        ("BM_ABBR_12", "bán dc bn đơn tháng này z?", "order_count", ["count_orders"], "number", 4, "Teencode: dc, bn, z"),
        ("BM_ABBR_13", "sp nào mang lại nhìu tiền nhất tháng này?", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "Teencode: sp, nhìu"),
        ("BM_ABBR_14", "tuan roi ban dc bn tien z shop?", "revenue", ["thanh_tien"], "number", 600000, "Teencode + No accent"),
        ("BM_ABBR_15", "check dùm tui tổng nợ bn nha", "total_debt", ["tong_no"], "number", 16500000, "Slang + Teencode: check, dùm, tui, bn, nha"),
        ("BM_ABBR_16", "ai nợ tiền chưa trả z?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Teencode: z"),
        ("BM_ABBR_17", "sp nào bán ế nhất tháng ni?", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Teencode + Dialect: sp, tháng ni"),
        ("BM_ABBR_18", "7 ngày gần đây bán dc bn?", "quantity", ["so_luong"], "number", 182, "Teencode: dc, bn"),
        ("BM_ABBR_19", "check sl sp bán chạy nhất tuần rồi", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Teencode: check, sl, sp"),
        ("BM_ABBR_20", "tiệm mình còn ai nợ ko z shop?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Teencode: ko, z, shop"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in abbr_data:
        add_q(qid, "abbreviations_texting", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 4. No-accent Vietnamese (20 questions)
    # -------------------------------------------------------------------------
    no_accent_data = [
        ("BM_ACCENT_01", "thang nay mat hang nao ban chay nhat", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "No-accent top seller"),
        ("BM_ACCENT_02", "doanh thu thang nay la bao nhieu", "revenue", ["thanh_tien"], "number", 5600000, "No-accent monthly revenue"),
        ("BM_ACCENT_03", "tuan roi ban dc bao nhieu tien", "revenue", ["thanh_tien"], "number", 600000, "No-accent prev week revenue"),
        ("BM_ACCENT_04", "con ai no tien chua tra ko", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "No-accent debt inquiry"),
        ("BM_ACCENT_05", "mat hang nao ban e nhat thang nay", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "No-accent lowest seller"),
        ("BM_ACCENT_06", "thang truoc ban duoc bao nhieu tien", "revenue", ["thanh_tien"], "number", 825000, "No-accent prev month revenue"),
        ("BM_ACCENT_07", "7 ngay gan day ban duoc bao nhieu", "quantity", ["so_luong"], "number", 182, "No-accent dynamic 7 days"),
        ("BM_ACCENT_08", "san pham nao thu ve nhieu tien nhat thang nay", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "No-accent top revenue product"),
        ("BM_ACCENT_09", "thang nay ban duoc bao nhieu don", "order_count", ["count_orders"], "number", 4, "No-accent monthly order count"),
        ("BM_ACCENT_10", "don hang nao co gia tri cao nhat", "order_max", ["thanh_tien"], "string", "HD07", "No-accent max order value"),
        ("BM_ACCENT_11", "tong tien no cua khach hang la bao nhieu", "total_debt", ["tong_no"], "number", 16500000, "No-accent total debt"),
        ("BM_ACCENT_12", "cung ky nam ngoai doanh thu bao nhieu", "revenue", ["thanh_tien"], "number", 750000, "No-accent YoY revenue"),
        ("BM_ACCENT_13", "tu sau tet den gio ban duoc bao nhieu", "quantity", ["so_luong"], "number", 237, "No-accent post-Tet quantity"),
        ("BM_ACCENT_14", "hom qua ban duoc bao nhieu tien", "revenue", ["thanh_tien"], "number", 450000, "No-accent yesterday revenue"),
        ("BM_ACCENT_15", "thuoc nao ban chay nhat tuan roi", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "No-accent prev week top medicine"),
        ("BM_ACCENT_16", "doanh thu tu dau thang den het hom qua", "revenue", ["thanh_tien"], "number", 1950000, "No-accent MTD until yesterday"),
        ("BM_ACCENT_17", "thang nay ban duoc bao nhieu san pham", "quantity", ["so_luong"], "number", 182, "No-accent monthly total quantity"),
        ("BM_ACCENT_18", "ngay 04/03 doanh thu bao nhieu", "revenue", ["thanh_tien"], "number", 3650000, "No-accent explicit date revenue"),
        ("BM_ACCENT_19", "loi nhuan rong thang nay bao nhieu", "unanswerable_missing_cost", ["loi_nhuan"], "unanswerable", None, "No-accent unanswerable profit query"),
        ("BM_ACCENT_20", "tai sao doanh thu thang nay giam", "unanswerable_causal_why", [], "unanswerable", None, "No-accent causal why query"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in no_accent_data:
        add_q(qid, "no_accent", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 5. Northern Dialect (15 questions)
    # -------------------------------------------------------------------------
    north_data = [
        ("BM_NORTH_01", "Tháng này mặt hàng nào tiêu thụ nhiều nhất nhỉ?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Northern: tiêu thụ nhiều nhất, nhỉ"),
        ("BM_NORTH_02", "Cửa hàng mình còn mặt hàng nào chưa bán được không?", "unsold_check", ["stock"], "boolean", False, "Northern: chưa bán được không"),
        ("BM_NORTH_03", "Hôm nay cửa hàng bán được mấy đơn rồi bác?", "order_count", ["count_orders"], "number", 2, "Northern: mấy đơn, bác (today HD06, HD07 = 2 orders)"),
        ("BM_NORTH_04", "Mặt hàng nào bán chậm nhất tháng này nhỉ?", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Northern: bán chậm nhất"),
        ("BM_NORTH_05", "Bác xem hộ em tháng này doanh thu được bao nhiêu rồi.", "revenue", ["thanh_tien"], "number", 5600000, "Northern: xem hộ em"),
        ("BM_NORTH_06", "Tuần rồi cửa hàng mình thu được bao nhiêu tiền nhỉ?", "revenue", ["thanh_tien"], "number", 600000, "Northern: thu được bao nhiêu tiền nhỉ"),
        ("BM_NORTH_07", "Còn ai nợ tiền chưa trả không vậy bác?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Northern: vậy bác"),
        ("BM_NORTH_08", "Đơn hàng nào to tiền nhất trong tháng này?", "order_max", ["thanh_tien"], "string", "HD07", "Northern: to tiền nhất"),
        ("BM_NORTH_09", "Hôm qua bán được bao nhiêu tiền vậy nhỉ?", "revenue", ["thanh_tien"], "number", 450000, "Northern: vậy nhỉ"),
        ("BM_NORTH_10", "Thuốc nào bán chạy nhất tuần vừa rồi?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Northern: tuần vừa rồi"),
        ("BM_NORTH_11", "Tháng này cửa hàng mình tiêu thụ được bao nhiêu món hàng?", "quantity", ["so_luong"], "number", 182, "Northern: tiêu thụ được bao nhiêu món"),
        ("BM_NORTH_12", "Cùng kỳ năm ngoái thu được bao nhiêu tiền nhỉ bác?", "revenue", ["thanh_tien"], "number", 750000, "Northern: cùng kỳ năm ngoái"),
        ("BM_NORTH_13", "Mặt hàng nào mang lại nguồn thu kém nhất tháng này?", "ranking_product_revenue", ["thanh_tien"], "string", "Berberin hộp", "Northern: nguồn thu kém nhất"),
        ("BM_NORTH_14", "Từ sau Tết đến nay bác bán được bao nhiêu sản phẩm rồi?", "quantity", ["so_luong"], "number", 237, "Northern: bác bán được"),
        ("BM_NORTH_15", "Tổng công nợ của tiệm mình là bao nhiêu vậy bác?", "total_debt", ["tong_no"], "number", 16500000, "Northern: tổng công nợ"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in north_data:
        add_q(qid, "northern_dialect", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 6. Central Dialect (15 questions)
    # -------------------------------------------------------------------------
    central_data = [
        ("BM_CENTRAL_01", "Tháng ni thuốc mô bán chạy nhất rứa?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Central: Tháng ni, mô, rứa"),
        ("BM_CENTRAL_02", "Răng tháng này doanh thu thấp hơn tháng trước hè?", "unanswerable_causal_why", [], "unanswerable", None, "Central: Răng, hè -> Causal why question"),
        ("BM_CENTRAL_03", "Tuần ni tiệm mình bán được bao nhiêu tiền rứa?", "revenue", ["thanh_tien"], "number", 5600000, "Central: Tuần ni, rứa"),
        ("BM_CENTRAL_04", "Còn ai nợ tiền chửa trả không hè?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Central: chửa trả, hè"),
        ("BM_CENTRAL_05", "Thuốc mô thu về nhiều tiền nhất tháng ni?", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "Central: Thuốc mô, tháng ni"),
        ("BM_CENTRAL_06", "Hôm qua bán được bao nhiêu tiền rứa?", "revenue", ["thanh_tien"], "number", 450000, "Central: rứa"),
        ("BM_CENTRAL_07", "Tháng ni tiệm mình bán được bao nhiêu đơn rồi hè?", "order_count", ["count_orders"], "number", 4, "Central: Tháng ni, hè"),
        ("BM_CENTRAL_08", "Đơn mô nhiều tiền nhất rứa hè?", "order_max", ["thanh_tien"], "string", "HD07", "Central: Đơn mô, rứa hè"),
        ("BM_CENTRAL_09", "Tuần rồi bán được bao nhiêu tiền rứa?", "revenue", ["thanh_tien"], "number", 600000, "Central: rứa"),
        ("BM_CENTRAL_10", "Thuốc mô bán ế nhất tháng ni rứa?", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Central: Thuốc mô, tháng ni, rứa"),
        ("BM_CENTRAL_11", "Cùng kỳ năm ngoái bán được bao nhiêu tiền rứa hè?", "revenue", ["thanh_tien"], "number", 750000, "Central: rứa hè"),
        ("BM_CENTRAL_12", "Từ sau Tết đến chừ bán được bao nhiêu món rồi?", "quantity", ["so_luong"], "number", 237, "Central: đến chừ"),
        ("BM_CENTRAL_13", "Tổng tiền nợ chừ là bao nhiêu rứa?", "total_debt", ["tong_no"], "number", 16500000, "Central: chừ, rứa"),
        ("BM_CENTRAL_14", "Răng doanh thu hôm nay lại giảm rứa hè?", "unanswerable_causal_why", [], "unanswerable", None, "Central: Răng -> Unanswerable"),
        ("BM_CENTRAL_15", "Mặt hàng mô có doanh thu thấp nhất tháng ni?", "ranking_product_revenue", ["thanh_tien"], "string", "Berberin hộp", "Central: Mặt hàng mô, tháng ni"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in central_data:
        add_q(qid, "central_dialect", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 7. Southern Dialect (15 questions)
    # -------------------------------------------------------------------------
    south_data = [
        ("BM_SOUTH_01", "Bữa giờ món nào bán chạy nhất vậy?", "abstain_ambiguous_time", [], "abstain", None, "Southern: 'Bữa giờ' is vague -> ABSTAIN"),
        ("BM_SOUTH_02", "Hông biết tháng này doanh thu được nhiêu rồi ta?", "revenue", ["thanh_tien"], "number", 5600000, "Southern: Hông biết, nhiêu, ta"),
        ("BM_SOUTH_03", "Coi dùm tui mặt hàng nào bán ế nhất.", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Southern: Coi dùm tui, bán ế"),
        ("BM_SOUTH_04", "Tiệm mình tháng này bán được bao nhiêu món rồi?", "quantity", ["so_luong"], "number", 182, "Southern: bao nhiêu món"),
        ("BM_SOUTH_05", "Tuần rồi bán được nhiêu tiền vậy shop?", "revenue", ["thanh_tien"], "number", 600000, "Southern: nhiêu tiền"),
        ("BM_SOUTH_06", "Còn ai nợ tiền chưa trả hông shop?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Southern: hông shop"),
        ("BM_SOUTH_07", "Hôm qua bán được bộn tiền hông ta?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Southern subjective: 'bộn tiền' -> ABSTAIN"),
        ("BM_SOUTH_08", "Đơn hàng nào nặng tiền nhất vậy nè?", "order_max", ["thanh_tien"], "string", "HD07", "Southern: nặng tiền nhất"),
        ("BM_SOUTH_09", "Coi giúp tui thuốc nào bán chạy nhất tháng này.", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Southern: Coi giúp tui"),
        ("BM_SOUTH_10", "Từ sau Tết tới chừ bán được bao nhiêu tiền rồi?", "revenue", ["thanh_tien"], "number", 6425000, "Southern: tới chừ"),
        ("BM_SOUTH_11", "Tháng này gom được bao nhiêu tiền nợ rồi ta?", "total_debt", ["tong_no"], "number", 16500000, "Southern: gom được, ta"),
        ("BM_SOUTH_12", "Cùng kỳ năm ngoái bán được nhiêu tiền z shop?", "revenue", ["thanh_tien"], "number", 750000, "Southern + Teencode: nhiêu, z"),
        ("BM_SOUTH_13", "Món nào thu về ít tiền nhất trong tháng vậy?", "ranking_product_revenue", ["thanh_tien"], "string", "Berberin hộp", "Southern: Món nào, ít tiền nhất"),
        ("BM_SOUTH_14", "Tháng trước bán được nhiêu tiền vậy kìa?", "revenue", ["thanh_tien"], "number", 825000, "Southern: nhiêu tiền, vậy kìa"),
        ("BM_SOUTH_15", "Hôm nay bán được bao nhiêu đơn rồi hè?", "order_count", ["count_orders"], "number", 2, "Southern order count"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in south_data:
        add_q(qid, "southern_dialect", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 8. Politeness and Social Expressions (20 questions)
    # -------------------------------------------------------------------------
    polite_data = [
        ("BM_POLITE_01", "Mấy anh chị cho em hỏi sản phẩm nào bán tốt nhất trong tháng này?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Honorific fluff prefix"),
        ("BM_POLITE_02", "Anh/chị xem giúp em tháng này thuốc nào bán chạy nhất với.", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Honorific fluff prefix & suffix"),
        ("BM_POLITE_03", "Dạ cho mình hỏi doanh thu tháng này là bao nhiêu ạ?", "revenue", ["thanh_tien"], "number", 5600000, "Polite particles: Dạ, ạ"),
        ("BM_POLITE_04", "Nhờ shop kiểm tra dùm mình tuần rồi bán được bao nhiêu tiền nhé.", "revenue", ["thanh_tien"], "number", 600000, "Polite padding: Nhờ shop, dùm mình, nhé"),
        ("BM_POLITE_05", "Cô/chú coi thử mặt hàng nào bán ế nhất tháng này.", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Honorific: Cô/chú coi thử"),
        ("BM_POLITE_06", "Bên mình còn ai đang nợ tiền chưa trả không ạ?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Polite suffix: ạ"),
        ("BM_POLITE_07", "Không biết tháng này tiệm mình bán được bao nhiêu rồi nhỉ?", "revenue", ["thanh_tien"], "number", 5600000, "Polite padding: Không biết... nhỉ"),
        ("BM_POLITE_08", "Em chào anh chị, cho em hỏi hôm qua bán được bao nhiêu tiền ạ?", "revenue", ["thanh_tien"], "number", 450000, "Greeting fluff: Em chào anh chị... ạ"),
        ("BM_POLITE_09", "Dạ anh chị kiểm tra giúp em đơn hàng lớn nhất tuần rồi với nha.", "order_max", ["thanh_tien"], "string", "HD03", "Polite padding: Dạ, giúp em, với nha"),
        ("BM_POLITE_10", "Nhờ bạn xem hộ mình tháng trước thu về bao nhiêu tiền nhé.", "revenue", ["thanh_tien"], "number", 825000, "Polite padding: Nhờ bạn, xem hộ mình, nhé"),
        ("BM_POLITE_11", "Cho em xin thông tin mặt hàng nào bán chạy nhất 7 ngày qua ạ.", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Polite padding: Cho em xin... ạ"),
        ("BM_POLITE_12", "Làm phiền shop kiểm tra giúp tổng nợ hiện tại là bao nhiêu.", "total_debt", ["tong_no"], "number", 16500000, "Polite fluff: Làm phiền shop"),
        ("BM_POLITE_13", "Dạ shop ơi, tháng này tiệm mình bán được bao nhiêu đơn rồi ạ?", "order_count", ["count_orders"], "number", 4, "Polite fluff: Dạ shop ơi... ạ"),
        ("BM_POLITE_14", "Anh chị cho em hỏi cùng kỳ năm ngoái bán được bao nhiêu tiền với ạ.", "revenue", ["thanh_tien"], "number", 750000, "Polite fluff: Anh chị cho em hỏi... với ạ"),
        ("BM_POLITE_15", "Nhà thuốc mình từ sau Tết đến nay bán được bao nhiêu sản phẩm rồi nhỉ?", "quantity", ["so_luong"], "number", 237, "Polite padding: Nhà thuốc mình... nhỉ"),
        ("BM_POLITE_16", "Em phiền anh chị xem giúp mặt hàng nào doanh thu thấp nhất tháng này.", "ranking_product_revenue", ["thanh_tien"], "string", "Berberin hộp", "Polite fluff: Em phiền anh chị"),
        ("BM_POLITE_17", "Cho mình hỏi nhỏ xíu là hôm nay bán được bao nhiêu tiền rồi nè?", "revenue", ["thanh_tien"], "number", 3650000, "Polite fluff: Cho mình hỏi nhỏ xíu"),
        ("BM_POLITE_18", "Dạ em nhờ shop kiểm tra thuốc nào bán chạy nhất hôm qua với ạ.", "ranking_product_quantity", ["so_luong"], "string", "Berberin hộp", "Polite fluff: Dạ em nhờ shop"),
        ("BM_POLITE_19", "Bác vui lòng xem giúp cháu danh sách khách nợ tiền với nhé.", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Polite fluff: Bác vui lòng... cháu"),
        ("BM_POLITE_20", "Xin phép cho mình hỏi doanh thu từ đầu tháng đến hết hôm qua là bao nhiêu ạ?", "revenue", ["thanh_tien"], "number", 1950000, "Polite fluff: Xin phép cho mình hỏi... ạ"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in polite_data:
        add_q(qid, "politeness_social", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 9. Business Semantic Distinctions (30 questions)
    # -------------------------------------------------------------------------
    # On biz_fixture_probe:
    # Product A: Qty 100, Revenue 1,000,000
    # Product B: Qty 20, Revenue 2,000,000
    sem_data = [
        ("BM_SEM_01", "biz_fixture_probe", "Sản phẩm nào bán được nhiều nhất?", "ranking_product_quantity", ["so_luong"], "string", "Sản phẩm A", "Quantity ranking: A (100) > B (20)"),
        ("BM_SEM_02", "biz_fixture_probe", "Sản phẩm nào thu về nhiều tiền nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Sản phẩm B", "Revenue ranking: B (2M) > A (1M)"),
        ("BM_SEM_03", "biz_fixture_probe", "Sản phẩm nào có doanh thu cao nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Sản phẩm B", "Revenue ranking: B (2M) > A (1M)"),
        ("BM_SEM_04", "biz_fixture_probe", "Sản phẩm nào tiêu thụ được nhiều nhất?", "ranking_product_quantity", ["so_luong"], "string", "Sản phẩm A", "Quantity ranking: A (100) > B (20)"),
        ("BM_SEM_05", "biz_fixture_probe", "Sản phẩm nào mang về nhiều tiền nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Sản phẩm B", "Revenue ranking: B (2M) > A (1M)"),
        ("BM_SEM_06", "biz_fixture_probe", "Sản phẩm nào bán ế nhất?", "ranking_product_quantity", ["so_luong"], "string", "Sản phẩm C", "Lowest quantity ranking: C (5)"),
        ("BM_SEM_07", "biz_fixture_probe", "Sản phẩm nào có doanh thu thấp nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Sản phẩm C", "Lowest revenue ranking: C (100k)"),
        ("BM_SEM_08", "biz_fixture_probe", "Tổng doanh thu là bao nhiêu?", "revenue", ["thanh_tien"], "number", 3100000, "Total revenue: 1M + 2M + 100k = 3.1M"),
        ("BM_SEM_09", "biz_fixture_probe", "Tổng số lượng sản phẩm bán ra là bao nhiêu?", "quantity", ["so_luong"], "number", 125, "Total quantity: 100 + 20 + 5 = 125"),
        ("BM_SEM_10", "biz_fixture_probe", "Bán được bao nhiêu đơn hàng?", "order_count", ["count_orders"], "number", 3, "Total distinct orders: 3"),
        ("BM_SEM_11", "biz_099", "Tháng này mặt hàng nào bán chạy nhất?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "March top quantity: Panadol (100)"),
        ("BM_SEM_12", "biz_099", "Tháng này mặt hàng nào thu về nhiều tiền nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "March top revenue: Omron (2.4M)"),
        ("BM_SEM_13", "biz_099", "Tháng này mặt hàng nào bán được ít nhất?", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "March lowest quantity: Omron (2)"),
        ("BM_SEM_14", "biz_099", "Tháng này mặt hàng nào có doanh thu thấp nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Berberin hộp", "March lowest revenue: Berberin (450k)"),
        ("BM_SEM_15", "biz_099", "Tháng này bán được bao nhiêu đơn?", "order_count", ["count_orders"], "number", 4, "Distinct order count: 4"),
        ("BM_SEM_16", "biz_099", "Tháng này bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 182, "Sum of quantities: 182"),
        ("BM_SEM_17", "biz_099", "Tháng này doanh thu là bao nhiêu?", "revenue", ["thanh_tien"], "number", 5600000, "Sum of total_amount: 5,600,000"),
        ("BM_SEM_18", "biz_099", "Đơn hàng nào có giá trị cao nhất?", "order_max", ["thanh_tien"], "string", "HD07", "Max order amount: HD07"),
        ("BM_SEM_19", "biz_099", "Ai đang nợ tiền lâu nhất?", "unanswerable_missing_debt_duration", ["tong_no"], "unanswerable", None, "Missing debt aging/due date in so_no.csv"),
        ("BM_SEM_20", "biz_099", "Tổng số tiền nợ là bao nhiêu?", "total_debt", ["tong_no"], "number", 16500000, "Sum of tong_no: 16.5M"),
        ("BM_SEM_21", "biz_099", "Những ai đang nợ tiền chưa trả?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "List distinct debtors where tong_no > 0"),
        ("BM_SEM_22", "biz_099", "Sản phẩm nào có lợi nhuận cao nhất?", "unanswerable_missing_cost", ["loi_nhuan"], "unanswerable", None, "Missing cost column in hoa_don.csv"),
        ("BM_SEM_23", "biz_099", "Lợi nhuận gộp tháng này là bao nhiêu?", "unanswerable_missing_cost", ["loi_nhuan"], "unanswerable", None, "Missing cost column in hoa_don.csv"),
        ("BM_SEM_24", "biz_099", "Tỷ suất lợi nhuận của cửa hàng là bao nhiêu?", "unanswerable_missing_cost", ["loi_nhuan"], "unanswerable", None, "Missing cost/profit column"),
        ("BM_SEM_25", "biz_099", "Kho còn bao nhiêu thuốc Panadol?", "unanswerable_missing_stock", ["stock"], "unanswerable", None, "Missing stock column/table in biz_099"),
        ("BM_SEM_26", "biz_099", "Thuốc nào sắp hết hạn sử dụng?", "unanswerable_missing_expiry", ["han_su_dung"], "unanswerable", None, "Missing expiry column in hoa_don.csv"),
        ("BM_SEM_27", "biz_099", "Khách hàng nào mua nhiều nhất?", "unanswerable_missing_customer", ["khach_hang"], "unanswerable", None, "Missing customer column in sales table"),
        ("BM_SEM_28", "biz_099", "Nhân viên nào bán được nhiều tiền nhất?", "unanswerable_missing_employee", ["nhan_vien"], "unanswerable", None, "Missing employee column in sales table"),
        ("BM_SEM_29", "biz_099", "Bán được bao nhiêu tiền trong tuần rồi?", "revenue", ["thanh_tien"], "number", 600000, "Weekly revenue distinction"),
        ("BM_SEM_30", "biz_099", "Bán được bao nhiêu sản phẩm trong tuần rồi?", "quantity", ["so_luong"], "number", 40, "Weekly quantity distinction (Panadol 40)"),
    ]
    for qid, biz, text, intent, meas, atype, ans, rsn in sem_data:
        add_q(qid, "business_semantics", biz, text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 10. Temporal Reasoning (25 questions)
    # -------------------------------------------------------------------------
    temporal_data = [
        ("BM_TIME_01", "Tháng này doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 5600000, "Current month strictly via as_of_date", {"start_date": "2026-03-01", "end_date": "2026-03-31"}),
        ("BM_TIME_02", "Tháng trước bán được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 825000, "Previous month", {"start_date": "2026-02-01", "end_date": "2026-02-28"}),
        ("BM_TIME_03", "Tuần rồi bán được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 600000, "Previous calendar week (Mon-Sun)", {"start_date": "2026-02-23", "end_date": "2026-03-01"}),
        ("BM_TIME_04", "7 ngày gần đây bán được bao nhiêu?", "quantity", ["so_luong"], "number", 182, "Dynamic 7-day rolling window [as_of_date - 6, as_of_date]", {"start_date": "2026-02-26", "end_date": "2026-03-04"}),
        ("BM_TIME_05", "7 ngày qua doanh thu là bao nhiêu?", "revenue", ["thanh_tien"], "number", 5600000, "Dynamic 7-day rolling revenue", {"start_date": "2026-02-26", "end_date": "2026-03-04"}),
        ("BM_TIME_06", "Hôm nay doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 3650000, "Exact as_of_date revenue", {"start_date": "2026-03-04", "end_date": "2026-03-04"}),
        ("BM_TIME_07", "Hôm qua doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 450000, "Yesterday revenue", {"start_date": "2026-03-03", "end_date": "2026-03-03"}),
        ("BM_TIME_08", "Hôm kia doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 1500000, "Day before yesterday revenue (March 2nd: 1.5M)", {"start_date": "2026-03-02", "end_date": "2026-03-02"}),
        ("BM_TIME_09", "Cùng kỳ năm ngoái doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 750000, "Same month last year (March 2025: 750k)", {"start_date": "2025-03-01", "end_date": "2025-03-31"}),
        ("BM_TIME_10", "Doanh thu từ đầu tháng đến hết hôm qua?", "revenue", ["thanh_tien"], "number", 1950000, "Month start to yesterday [2026-03-01, 2026-03-03]", {"start_date": "2026-03-01", "end_date": "2026-03-03"}),
        ("BM_TIME_11", "Ngày 04/03 doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 3650000, "Explicit date DD/MM", {"start_date": "2026-03-04", "end_date": "2026-03-04"}),
        ("BM_TIME_12", "Ngày 02/03/2026 doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 1500000, "Explicit date DD/MM/YYYY", {"start_date": "2026-03-02", "end_date": "2026-03-02"}),
        ("BM_TIME_13", "Tháng 2 năm 2026 doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 825000, "Explicit month and year", {"start_date": "2026-02-01", "end_date": "2026-02-28"}),
        ("BM_TIME_14", "Tháng 3 năm 2025 doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 750000, "Historical month and year", {"start_date": "2025-03-01", "end_date": "2025-03-31"}),
        ("BM_TIME_15", "Năm ngoái doanh thu là bao nhiêu?", "revenue", ["thanh_tien"], "number", 750000, "Full previous year 2025", {"start_date": "2025-01-01", "end_date": "2025-12-31"}),
        ("BM_TIME_16", "Năm nay doanh thu là bao nhiêu?", "revenue", ["thanh_tien"], "number", 6425000, "Full current year 2026 up to date", {"start_date": "2026-01-01", "end_date": "2026-12-31"}),
        ("BM_TIME_17", "Quý 1 năm 2026 doanh thu là bao nhiêu?", "revenue", ["thanh_tien"], "number", 6425000, "Quarter 1 (Jan - Mar 2026)", {"start_date": "2026-01-01", "end_date": "2026-03-31"}),
        ("BM_TIME_18", "Tuần này bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 182, "Current calendar week quantity", {"start_date": "2026-03-02", "end_date": "2026-03-08"}),
        ("BM_TIME_19", "Tuần này doanh thu là bao nhiêu?", "revenue", ["thanh_tien"], "number", 5600000, "Current calendar week revenue", {"start_date": "2026-03-02", "end_date": "2026-03-08"}),
        ("BM_TIME_20", "Mặt hàng nào bán chạy nhất trong 7 ngày gần đây?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Rolling 7 days top seller", {"start_date": "2026-02-26", "end_date": "2026-03-04"}),
        ("BM_TIME_21", "Mặt hàng nào có doanh thu cao nhất trong 7 ngày qua?", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "Rolling 7 days top revenue", {"start_date": "2026-02-26", "end_date": "2026-03-04"}),
        ("BM_TIME_22", "Doanh thu ngày 03/03 là bao nhiêu?", "revenue", ["thanh_tien"], "number", 450000, "Explicit date DD/MM", {"start_date": "2026-03-03", "end_date": "2026-03-03"}),
        ("BM_TIME_23", "Tháng trước bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 55, "Prev month quantity (15 + 40 = 55)", {"start_date": "2026-02-01", "end_date": "2026-02-28"}),
        ("BM_TIME_24", "Tuần rồi bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 40, "Prev week quantity (Panadol 40)", {"start_date": "2026-02-23", "end_date": "2026-03-01"}),
        ("BM_TIME_25", "Hôm qua bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 30, "Yesterday quantity (Berberin 30)", {"start_date": "2026-03-03", "end_date": "2026-03-03"}),
    ]
    for qid, text, intent, meas, atype, ans, rsn, tr in temporal_data:
        add_q(qid, "temporal_reasoning", "biz_099", text, intent, meas, atype, ans, rsn, time_range=tr)

    # -------------------------------------------------------------------------
    # 11. Lunar Calendar (15 questions)
    # -------------------------------------------------------------------------
    lunar_data = [
        ("BM_LUNAR_01", "Từ sau Tết đến giờ bán được bao nhiêu?", "quantity", ["so_luong"], "number", 237, "Solar date of Mùng 1 Tết Bính Ngọ (2026-02-17) to as_of_date", {"start_date": "2026-02-17", "end_date": "2026-03-04"}),
        ("BM_LUNAR_02", "Từ sau Tết đến nay doanh thu là bao nhiêu?", "revenue", ["thanh_tien"], "number", 6425000, "Post-Tet revenue", {"start_date": "2026-02-17", "end_date": "2026-03-04"}),
        ("BM_LUNAR_03", "Từ mùng 1 đến rằm tháng Giêng bán được bao nhiêu?", "quantity", ["so_luong"], "number", 185, "Lunar 1/1 to Lunar 15/1 (2026-02-17 to 2026-03-03: 15+40+100+30 = 185)", {"start_date": "2026-02-17", "end_date": "2026-03-03"}),
        ("BM_LUNAR_04", "Từ mùng 1 đến rằm tháng Giêng thu được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 2775000, "Lunar 1/1 to 15/1 revenue (225k+600k+1.5M+450k = 2,775,000)", {"start_date": "2026-02-17", "end_date": "2026-03-03"}),
        ("BM_LUNAR_05", "Rằm tháng Giêng năm nay bán được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 450000, "Rằm tháng Giêng 2026 is 2026-03-03 (Berberin: 450k)", {"start_date": "2026-03-03", "end_date": "2026-03-03"}),
        ("BM_LUNAR_06", "Rằm tháng Giêng bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 30, "Rằm tháng Giêng 2026 quantity (Berberin: 30)", {"start_date": "2026-03-03", "end_date": "2026-03-03"}),
        ("BM_LUNAR_07", "Tháng Giêng năm nay bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 237, "Lunar Month 1 (2026-02-17 to 2026-03-18: 237 items)", {"start_date": "2026-02-17", "end_date": "2026-03-18"}),
        ("BM_LUNAR_08", "Tháng Giêng năm nay doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 6425000, "Lunar Month 1 revenue", {"start_date": "2026-02-17", "end_date": "2026-03-18"}),
        ("BM_LUNAR_09", "Mặt hàng nào bán chạy nhất từ sau Tết đến giờ?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Post-Tet top quantity seller (Panadol 140)"),
        ("BM_LUNAR_10", "Mặt hàng nào thu về nhiều tiền nhất từ sau Tết đến nay?", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "Post-Tet top revenue seller (Omron 2.4M)"),
        ("BM_LUNAR_11", "Mặt hàng nào bán chạy nhất vào ngày Rằm tháng Giêng?", "ranking_product_quantity", ["so_luong"], "string", "Berberin hộp", "Rằm tháng Giêng top product"),
        ("BM_LUNAR_12", "Từ sau Tết đến nay bán được bao nhiêu đơn hàng?", "order_count", ["count_orders"], "number", 6, "Post-Tet order count (HD02 to HD07 = 6 orders)"),
        ("BM_LUNAR_13", "Mùng 2 Tết bán được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 225000, "Mùng 2 Tết Bính Ngọ is 2026-02-18 (Berberin: 225k)", {"start_date": "2026-02-18", "end_date": "2026-02-18"}),
        ("BM_LUNAR_14", "Mùng 2 Tết bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 15, "Mùng 2 Tết Bính Ngọ quantity (Berberin: 15)", {"start_date": "2026-02-18", "end_date": "2026-02-18"}),
        ("BM_LUNAR_15", "Mặt hàng nào bán ế nhất từ sau Tết đến giờ?", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Post-Tet lowest seller (Omron 2)"),
    ]
    for item in lunar_data:
        qid, text, intent, meas, atype, ans, rsn = item[:7]
        tr = item[7] if len(item) > 7 else None
        add_q(qid, "lunar_calendar", "biz_099", text, intent, meas, atype, ans, rsn, time_range=tr)

    # -------------------------------------------------------------------------
    # 12. Missing Data & Answerability (30 questions)
    # -------------------------------------------------------------------------
    unans_data = [
        ("BM_UNANS_01", "Lợi nhuận ròng tháng này bao nhiêu?", "unanswerable_missing_cost", ["loi_nhuan"], "unanswerable", None, "Missing cost column in schema"),
        ("BM_UNANS_02", "Thuốc nào sắp hết hạn?", "unanswerable_missing_expiry", ["han_su_dung"], "unanswerable", None, "Missing expiration column in schema"),
        ("BM_UNANS_03", "Kho còn bao nhiêu thuốc Panadol?", "unanswerable_missing_stock", ["stock"], "unanswerable", None, "Missing inventory table / stock column"),
        ("BM_UNANS_04", "Tại sao doanh thu tháng này giảm?", "unanswerable_causal_why", [], "unanswerable", None, "Causal why questions cannot be answered from transaction data"),
        ("BM_UNANS_05", "Dự đoán tháng sau bán được bao nhiêu?", "unanswerable_future_forecast", [], "unanswerable", None, "Future predictions cannot be answered without forecast module"),
        ("BM_UNANS_06", "Khách hàng thân thiết nhất là ai?", "unanswerable_missing_loyalty", ["khach_hang"], "unanswerable", None, "Missing loyalty column/definition in schema"),
        ("BM_UNANS_07", "ROI của cửa hàng là bao nhiêu?", "unanswerable_missing_cost", ["roi"], "unanswerable", None, "Missing investment/capital data"),
        ("BM_UNANS_08", "Doanh thu của nhân viên Nguyễn Văn A?", "unanswerable_missing_employee", ["nhan_vien"], "unanswerable", None, "Missing employee column in schema"),
        ("BM_UNANS_09", "Ngày mai cửa hàng sẽ bán được bao nhiêu?", "unanswerable_future_forecast", [], "unanswerable", None, "Future prediction"),
        ("BM_UNANS_10", "Ai đang nợ tiền lâu nhất?", "unanswerable_missing_debt_duration", ["tong_no"], "unanswerable", None, "Missing debt due date in schema"),
        ("BM_UNANS_11", "Chi phí nhập hàng tháng này là bao nhiêu?", "unanswerable_missing_cost", ["gia_von"], "unanswerable", None, "Missing cost/cogs data"),
        ("BM_UNANS_12", "Nguyên nhân vì sao tuần rồi bán ế?", "unanswerable_causal_why", [], "unanswerable", None, "Causal explanation request"),
        ("BM_UNANS_13", "Dự báo doanh số tuần tới như thế nào?", "unanswerable_future_forecast", [], "unanswerable", None, "Future forecast"),
        ("BM_UNANS_14", "Khách VIP mua nhiều nhất là ai?", "unanswerable_missing_loyalty", ["khach_hang"], "unanswerable", None, "Missing VIP / loyalty definition"),
        ("BM_UNANS_15", "Tỷ lệ lãi ròng của tiệm là bao nhiêu?", "unanswerable_missing_cost", ["loi_nhuan"], "unanswerable", None, "Missing expense/cost data"),
        ("BM_UNANS_16", "Nhân viên nào bán được nhiều đơn nhất?", "unanswerable_missing_employee", ["nhan_vien"], "unanswerable", None, "Missing employee column"),
        ("BM_UNANS_17", "Số lượng hàng tồn kho của từng loại thuốc?", "unanswerable_missing_stock", ["stock"], "unanswerable", None, "Missing stock data"),
        ("BM_UNANS_18", "Ngày hết hạn của khẩu trang y tế là khi nào?", "unanswerable_missing_expiry", ["han_su_dung"], "unanswerable", None, "Missing expiration date"),
        ("BM_UNANS_19", "Do đâu mà khách hàng không chịu trả nợ?", "unanswerable_causal_why", [], "unanswerable", None, "Subjective causal explanation"),
        ("BM_UNANS_20", "Tháng tới tiệm có đạt chỉ tiêu không?", "unanswerable_future_forecast", [], "unanswerable", None, "Future prediction"),
        ("BM_UNANS_21", "Giá vốn của thuốc Panadol là bao nhiêu?", "unanswerable_missing_cost", ["gia_von"], "unanswerable", None, "Missing cost data"),
        ("BM_UNANS_22", "Điểm tích lũy của khách hàng BS Minh là bao nhiêu?", "unanswerable_missing_loyalty", ["diem_tich_luy"], "unanswerable", None, "Missing loyalty point data"),
        ("BM_UNANS_23", "Ai là người bán được nhiều nhất trong ca sáng?", "unanswerable_missing_employee", ["ca_lam_viec"], "unanswerable", None, "Missing shifts and employee data"),
        ("BM_UNANS_24", "Thuốc nào đã quá hạn sử dụng mà chưa hủy?", "unanswerable_missing_expiry", ["han_su_dung"], "unanswerable", None, "Missing expiration date"),
        ("BM_UNANS_25", "Tại sao số lượng Berberin bán ra lại ít hơn Panadol?", "unanswerable_causal_why", [], "unanswerable", None, "Causal explanation"),
        ("BM_UNANS_26", "Tháng sau có nên nhập thêm khẩu trang không?", "unanswerable_future_forecast", [], "unanswerable", None, "Business decision recommendation"),
        ("BM_UNANS_27", "Tỷ suất hoàn vốn đầu tư của nhà thuốc là bao nhiêu?", "unanswerable_missing_cost", ["roi"], "unanswerable", None, "Missing ROI investment data"),
        ("BM_UNANS_28", "Nhân viên thu ngân tên là gì?", "unanswerable_missing_employee", ["nhan_vien"], "unanswerable", None, "Missing cashier data"),
        ("BM_UNANS_29", "Nhà thuốc còn bao nhiêu hộp Berberin trong kho?", "unanswerable_missing_stock", ["stock"], "unanswerable", None, "Missing inventory data"),
        ("BM_UNANS_30", "Nguyên nhân doanh thu tháng 2 thấp hơn tháng 3?", "unanswerable_causal_why", [], "unanswerable", None, "Causal explanation"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in unans_data:
        add_q(qid, "missing_data_answerability", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 13. Ambiguous Questions -> ABSTAIN (15 questions)
    # -------------------------------------------------------------------------
    abstain_data = [
        ("BM_ABS_01", "Bữa giờ bán có khá không?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Ambiguous time + subjective criterion 'khá'"),
        ("BM_ABS_02", "Bữa giờ thuốc nào bán chạy nhất vậy?", "abstain_ambiguous_time", [], "abstain", None, "'Bữa giờ' is vague temporal window"),
        ("BM_ABS_03", "Dạo này tiệm mình làm ăn có ổn không?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Subjective qualitative question"),
        ("BM_ABS_04", "Thời tiết hôm nay thế nào?", "abstain_out_of_domain", [], "abstain", None, "Out-of-domain question"),
        ("BM_ABS_05", "Bữa nay tới giờ bán được nhiều chưa?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Subjective question"),
        ("BM_ABS_06", "Cửa hàng có bán đắt hàng không bạn?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Subjective criterion"),
        ("BM_ABS_07", "Dạo này khách khứa có đông vui không?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Subjective question"),
        ("BM_ABS_08", "Tình hình kinh doanh chung dạo này thế nào?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Vague general question"),
        ("BM_ABS_09", "Bữa giờ thu được nhiều tiền hông?", "abstain_ambiguous_time", [], "abstain", None, "Vague time window"),
        ("BM_ABS_10", "Ai là người đẹp trai nhất cửa hàng?", "abstain_out_of_domain", [], "abstain", None, "Nonsensical subjective question"),
        ("BM_ABS_11", "Thuốc nào bán chạy nhất trong ngày 2026-03-10?", "abstain_no_transactions", [], "abstain", None, "No transactions on future/empty date -> do not hallucinate product!"),
        ("BM_ABS_12", "Hôm qua bán có được giá không?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Subjective criterion"),
        ("BM_ABS_13", "Mấy hôm nay thuốc nào bán được?", "abstain_ambiguous_time", [], "abstain", None, "'Mấy hôm nay' is undefined time window"),
        ("BM_ABS_14", "Tiệm mình bán đồ có tốt không?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Qualitative subjective question"),
        ("BM_ABS_15", "Tình hình bán buôn gần đây có khởi sắc không?", "abstain_ambiguous_or_subjective", [], "abstain", None, "Subjective question"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in abstain_data:
        add_q(qid, "ambiguous_questions", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 14. Multi-condition Queries (20 questions)
    # -------------------------------------------------------------------------
    multi_data = [
        ("BM_MULTI_01", "Trong tuần rồi có bao nhiêu đơn hàng đã thanh toán?", "order_count", ["count_orders"], "number", 1, "Week filter + status filter (HD03)"),
        ("BM_MULTI_02", "Tháng này có bao nhiêu đơn hàng có trạng thái đã thanh toán?", "order_count", ["count_orders"], "number", 4, "Month filter + valid status filter"),
        ("BM_MULTI_03", "Tuần rồi doanh thu các đơn đã thanh toán là bao nhiêu?", "revenue", ["thanh_tien"], "number", 600000, "Week filter + amount calculation"),
        ("BM_MULTI_04", "Trong tháng 3 năm 2026, thuốc nào bán được trên 50 vỉ?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Threshold + ranking (Panadol 100 > 50)"),
        ("BM_MULTI_05", "Có khách hàng nào nợ trên 10 triệu đồng không?", "debt_customers_list", ["tong_no"], "list", ["Trạm y tế Xã Tân Tiến"], "Debt threshold > 10M (Trạm y tế: 12M)"),
        ("BM_MULTI_06", "Danh sách các khách hàng nợ dưới 5 triệu đồng?", "debt_customers_list", ["tong_no"], "list", ["Phòng khám BS Minh"], "Debt threshold < 5M (Phòng khám: 4.5M)"),
        ("BM_MULTI_07", "Trong tháng này có đơn hàng nào trị giá trên 2 triệu không?", "order_max", ["thanh_tien"], "string", "HD07", "Order value > 2M (HD07: 2.4M)"),
        ("BM_MULTI_08", "Ngày 04/03 có bao nhiêu đơn hàng đã hoàn tất?", "order_count", ["count_orders"], "number", 2, "Date filter + count (HD06, HD07 = 2)"),
        ("BM_MULTI_09", "Ngày 04/03 sản phẩm nào bán được số lượng nhiều nhất?", "ranking_product_quantity", ["so_luong"], "string", "Khẩu trang 4 lớp", "Date filter + quantity ranking (Khẩu trang 50 > Omron 2)"),
        ("BM_MULTI_10", "Ngày 04/03 sản phẩm nào mang lại nhiều tiền nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Máy đo huyết áp Omron", "Date filter + revenue ranking (Omron 2.4M > Khẩu trang 1.25M)"),
        ("BM_MULTI_11", "Từ sau Tết đến nay có bao nhiêu đơn hàng không bị hủy?", "order_count", ["count_orders"], "number", 6, "Post-Tet valid orders count"),
        ("BM_MULTI_12", "Thuốc nào bán được số lượng nhiều nhất trong các ngày chẵn tháng 3?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Day condition + quantity"),
        ("BM_MULTI_13", "Trong tháng 2 năm 2026, có bao nhiêu sản phẩm Berberin được bán ra?", "quantity", ["so_luong"], "number", 15, "Specific month + product filter"),
        ("BM_MULTI_14", "Trong tháng 3 năm 2026, có bao nhiêu hộp Berberin được bán ra?", "quantity", ["so_luong"], "number", 30, "Specific month + product filter"),
        ("BM_MULTI_15", "Đơn hàng ngày 03/03 trị giá bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 450000, "Date filter + amount (HD05: 450k)"),
        ("BM_MULTI_16", "Đơn hàng ngày 02/03 bán được bao nhiêu vỉ thuốc?", "quantity", ["so_luong"], "number", 100, "Date filter + quantity (HD04: 100)"),
        ("BM_MULTI_17", "Trong các đơn hàng tháng này, đơn hàng nào có số lượng sản phẩm ít nhất?", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Lowest quantity in month"),
        ("BM_MULTI_18", "Khách hàng nào đang nợ nhiều tiền nhất?", "debt_customers_list", ["tong_no"], "list", ["Trạm y tế Xã Tân Tiến"], "Top debt customer (12M)"),
        ("BM_MULTI_19", "Tổng số tiền nợ của các trạm y tế và phòng khám là bao nhiêu?", "total_debt", ["tong_no"], "number", 16500000, "Sum of institutional debt"),
        ("BM_MULTI_20", "Trong tháng này có bao nhiêu mặt hàng khác nhau đã phát sinh doanh số?", "quantity", ["so_luong"], "number", 4, "Distinct products count in March (Panadol, Berberin, Khẩu trang, Omron)"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in multi_data:
        add_q(qid, "multi_condition", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 15. Aggregations and Grouping (20 questions)
    # -------------------------------------------------------------------------
    agg_data = [
        ("BM_AGG_01", "Doanh thu trung bình mỗi đơn hàng trong tháng này là bao nhiêu?", "revenue", ["thanh_tien"], "number", 1400000, "Average order value (5.6M / 4 = 1,400,000)"),
        ("BM_AGG_02", "Đơn hàng nào có giá trị cao nhất?", "order_max", ["thanh_tien"], "string", "HD07", "Max value order ID"),
        ("BM_AGG_03", "Mặt hàng nào có doanh thu thấp nhất tháng này?", "ranking_product_revenue", ["thanh_tien"], "string", "Berberin hộp", "Min revenue item"),
        ("BM_AGG_04", "Tổng số tiền khách hàng đang nợ là bao nhiêu?", "total_debt", ["tong_no"], "number", 16500000, "Sum of debts"),
        ("BM_AGG_05", "Số lượng bán ra trung bình mỗi đơn trong tháng 3 là bao nhiêu?", "quantity", ["so_luong"], "number", 45.5, "Average items per order (182 / 4 = 45.5)"),
        ("BM_AGG_06", "Sản phẩm nào có tổng số lượng bán lớn nhất tháng này?", "ranking_product_quantity", ["so_luong"], "string", "Panadol Extra đỏ vỉ", "Max quantity product"),
        ("BM_AGG_07", "Sản phẩm nào có tổng số lượng bán nhỏ nhất tháng này?", "ranking_product_quantity", ["so_luong"], "string", "Máy đo huyết áp Omron", "Min quantity product"),
        ("BM_AGG_08", "Đơn hàng có giá trị nhỏ nhất tháng này trị giá bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 450000, "Min order value in March (HD05: 450k)"),
        ("BM_AGG_09", "Khoản nợ lớn nhất hiện tại của một khách hàng là bao nhiêu?", "total_debt", ["tong_no"], "number", 12000000, "Max individual debt (Trạm y tế: 12M)"),
        ("BM_AGG_10", "Khoản nợ nhỏ nhất lớn hơn 0 của khách hàng là bao nhiêu?", "total_debt", ["tong_no"], "number", 4500000, "Min positive debt (Phòng khám: 4.5M)"),
        ("BM_AGG_11", "Tổng tiền bán được trong 7 ngày gần đây là bao nhiêu?", "revenue", ["thanh_tien"], "number", 5600000, "Rolling 7-day sum"),
        ("BM_AGG_12", "Tổng số lượng hàng bán ra trong tuần rồi là bao nhiêu?", "quantity", ["so_luong"], "number", 40, "Weekly sum quantity"),
        ("BM_AGG_13", "Doanh thu ngày hôm qua là bao nhiêu?", "revenue", ["thanh_tien"], "number", 450000, "Daily sum"),
        ("BM_AGG_14", "Tổng số đơn hàng thực hiện trong năm 2026 đến nay?", "order_count", ["count_orders"], "number", 6, "YTD order count (HD02 to HD07 = 6)"),
        ("BM_AGG_15", "Tổng doanh thu năm 2026 đến nay là bao nhiêu?", "revenue", ["thanh_tien"], "number", 6425000, "YTD revenue sum"),
        ("BM_AGG_16", "Giá trị đơn hàng cao nhất trong năm 2025 là bao nhiêu?", "revenue", ["thanh_tien"], "number", 750000, "Historical max order (HD01: 750k)"),
        ("BM_AGG_17", "Số khách hàng hiện đang còn nợ tiền là bao nhiêu người?", "order_count", ["tong_no"], "number", 2, "Count distinct debtors with debt > 0"),
        ("BM_AGG_18", "Tổng số lượng vỉ Panadol bán ra trong tháng 3 là bao nhiêu?", "quantity", ["so_luong"], "number", 100, "Sum of quantity for specific SKU"),
        ("BM_AGG_19", "Tổng doanh thu bán Panadol trong tháng 3 là bao nhiêu?", "revenue", ["thanh_tien"], "number", 1500000, "Sum of revenue for specific SKU"),
        ("BM_AGG_20", "Tổng số lượng máy đo huyết áp bán ra trong tháng 3 là bao nhiêu?", "quantity", ["so_luong"], "number", 2, "Sum of quantity for Omron"),
    ]
    for qid, text, intent, meas, atype, ans, rsn in agg_data:
        add_q(qid, "aggregations_grouping", "biz_099", text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 16. SQL Edge Cases (20 questions)
    # -------------------------------------------------------------------------
    edge_data = [
        ("BM_EDGE_01", "Tỷ lệ hủy đơn hàng trong tháng này là bao nhiêu phần trăm?", "cancel_rate", ["trang_thai"], "percent", 0.0, "Zero cancellations -> 0.0%"),
        ("BM_EDGE_02", "Số lượng đơn hàng bị hủy trong tuần rồi là bao nhiêu?", "cancel_count", ["trang_thai"], "number", 0, "Zero cancellations count"),
        ("BM_EDGE_03", "Có đơn hàng nào có số tiền âm không?", "revenue", ["thanh_tien"], "number", 0, "No negative amounts"),
        ("BM_EDGE_04", "Tổng nợ của khách hàng Bs Hùng là bao nhiêu?", "total_debt", ["tong_no"], "number", 0, "Customer with exact 0 debt balance"),
        ("BM_EDGE_05", "Thuốc nào bán chạy nhất trong ngày 2026-03-01?", "abstain_no_transactions", [], "abstain", None, "No transactions on Sunday 2026-03-01 -> ABSTAIN"),
        ("BM_EDGE_06", "Doanh thu trong ngày 2026-03-01 là bao nhiêu?", "revenue", ["thanh_tien"], "number", 0.0, "Zero sales on date -> returns 0.0"),
        ("BM_EDGE_07", "Số lượng đơn hàng trong ngày 2026-03-01 là bao nhiêu?", "order_count", ["count_orders"], "number", 0, "Zero orders on date -> returns 0"),
        ("BM_EDGE_08", "Tỷ lệ đơn hủy trong ngày 2026-03-01 là bao nhiêu?", "cancel_rate", ["trang_thai"], "percent", 0.0, "Division by zero safeguard -> returns 0.0%"),
        ("BM_EDGE_09", "biz_fixture_probe", "Sản phẩm nào bán chạy nhất khi số lượng bằng nhau?", "ranking_product_quantity", ["so_luong"], "string", "Sản phẩm A", "Tie breaker test"),
        ("BM_EDGE_10", "biz_empty_sales", "Thuốc nào bán chạy nhất?", "abstain_no_transactions", [], "abstain", None, "Empty sales table -> ABSTAIN"),
        ("BM_EDGE_11", "biz_empty_sales", "Doanh thu tháng này là bao nhiêu?", "revenue", ["thanh_tien"], "number", 0.0, "Empty table sum -> returns 0.0"),
        ("BM_EDGE_12", "biz_empty_sales", "Tháng này có bao nhiêu đơn hàng?", "order_count", ["count_orders"], "number", 0, "Empty table count -> returns 0"),
        ("BM_EDGE_13", "Mặt hàng có tên chứa ký tự đặc biệt có doanh số bao nhiêu?", "revenue", ["thanh_tien"], "number", 1250000, "Product with digits: Khẩu trang 4 lớp"),
        ("BM_EDGE_14", "Có đơn hàng nào có giá trị bằng 0 đồng không?", "revenue", ["thanh_tien"], "number", 0, "Zero-value orders count"),
        ("BM_EDGE_15", "Tỷ lệ đơn hàng thành công trong tháng này là bao nhiêu?", "cancel_rate", ["trang_thai"], "percent", 100.0, "100% completed orders"),
        ("BM_EDGE_16", "biz_fixture_probe", "Sản phẩm có mã SP_A có số lượng bán là bao nhiêu?", "quantity", ["so_luong"], "number", 100, "Code-based query"),
        ("BM_EDGE_17", "Đơn hàng mã HD07 có giá trị bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 2400000, "Specific invoice lookup"),
        ("BM_EDGE_18", "Ngày 29/02/2026 có doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 0.0, "Invalid leap day in non-leap year -> 0"),
        ("BM_EDGE_19", "Doanh thu tháng 13 năm 2026 là bao nhiêu?", "revenue", ["thanh_tien"], "number", 0.0, "Non-existent month 13"),
        ("BM_EDGE_20", "Tổng tiền bán của đơn hàng bị hủy là bao nhiêu?", "revenue", ["thanh_tien"], "number", 0.0, "Cancelled orders sum"),
    ]
    for item in edge_data:
        if len(item) == 7:
            qid, text, intent, meas, atype, ans, rsn = item
            biz = "biz_099"
        else:
            qid, biz, text, intent, meas, atype, ans, rsn = item
        add_q(qid, "sql_edge_cases", biz, text, intent, meas, atype, ans, rsn)

    # -------------------------------------------------------------------------
    # 17. Paraphrase & Metamorphic Clusters (30 questions)
    # -------------------------------------------------------------------------
    # Cluster 1: Monthly Top Seller (Quantity)
    cluster_1 = [
        ("BM_PARA_01", "Tháng này sản phẩm nào bán chạy nhất?", "ranking_product_quantity", "Panadol Extra đỏ vỉ", "Standard natural"),
        ("BM_PARA_02", "sp nào bán dc nhiều nhất tháng này vậy shop", "ranking_product_quantity", "Panadol Extra đỏ vỉ", "Teencode variant"),
        ("BM_PARA_03", "Anh chị coi dùm em mặt hàng nào có số lượng bán cao nhất trong tháng này.", "ranking_product_quantity", "Panadol Extra đỏ vỉ", "Polite honorific variant"),
        ("BM_PARA_04", "thang nay mat hang nao ban chay nhat", "ranking_product_quantity", "Panadol Extra đỏ vỉ", "No-accent variant"),
        ("BM_PARA_05", "Tháng ni thuốc mô bán chạy nhất rứa?", "ranking_product_quantity", "Panadol Extra đỏ vỉ", "Central dialect variant"),
    ]
    for qid, text, intent, ans, rsn in cluster_1:
        add_q(qid, "paraphrase_clusters", "biz_099", text, intent, ["so_luong"], "string", ans, rsn, cluster_id="CLUSTER_TOP_SELLER_MONTH")

    # Cluster 2: Monthly Revenue
    cluster_2 = [
        ("BM_PARA_06", "Doanh thu tháng này là bao nhiêu?", "revenue", 5600000, "Standard"),
        ("BM_PARA_07", "doanh thu thang nay la bao nhieu", "revenue", 5600000, "No accent"),
        ("BM_PARA_08", "Cho mình hỏi doanh thu tháng này là bao nhiêu ạ?", "revenue", 5600000, "Polite"),
        ("BM_PARA_09", "doanh thu tháng này nhiu z?", "revenue", 5600000, "Teencode"),
        ("BM_PARA_10", "Hông biết tháng này doanh thu được nhiêu rồi ta?", "revenue", 5600000, "Southern dialect"),
    ]
    for qid, text, intent, ans, rsn in cluster_2:
        add_q(qid, "paraphrase_clusters", "biz_099", text, intent, ["thanh_tien"], "number", ans, rsn, cluster_id="CLUSTER_REVENUE_MONTH")

    # Cluster 3: Outstanding Debtors List
    cluster_3 = [
        ("BM_PARA_11", "Những ai đang nợ tiền chưa trả?", "debt_customers_list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Standard"),
        ("BM_PARA_12", "Bên mình còn ai đang nợ tiền chưa trả không?", "debt_customers_list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Polite"),
        ("BM_PARA_13", "còn ai nợ tiền chưa trả ko?", "debt_customers_list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Teencode"),
        ("BM_PARA_14", "con ai no tien chua tra ko", "debt_customers_list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "No accent"),
        ("BM_PARA_15", "Còn ai nợ tiền chửa trả không hè?", "debt_customers_list", ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến"], "Central dialect"),
    ]
    for qid, text, intent, ans, rsn in cluster_3:
        add_q(qid, "paraphrase_clusters", "biz_099", text, intent, ["tong_no"], "list", ans, rsn, cluster_id="CLUSTER_DEBTORS_LIST")

    # Cluster 4: Previous Week Revenue
    cluster_4 = [
        ("BM_PARA_16", "Tuần rồi bán được bao nhiêu tiền?", "revenue", 600000, "Standard"),
        ("BM_PARA_17", "Nhờ shop kiểm tra dùm mình tuần rồi bán được bao nhiêu tiền nhé.", "revenue", 600000, "Polite"),
        ("BM_PARA_18", "tuần rồi bán dc bn tiền?", "revenue", 600000, "Teencode"),
        ("BM_PARA_19", "tuan roi ban dc bao nhieu tien", "revenue", 600000, "No accent"),
        ("BM_PARA_20", "Tuần rồi thu được bao nhiêu tiền nhỉ bác?", "revenue", 600000, "Northern"),
    ]
    for qid, text, intent, ans, rsn in cluster_4:
        add_q(qid, "paraphrase_clusters", "biz_099", text, intent, ["thanh_tien"], "number", ans, rsn, cluster_id="CLUSTER_PREV_WEEK_REVENUE")

    # Metamorphic Tests: Measure Invariance & Sensitivity
    metamorphic_data = [
        ("BM_META_01", "biz_099", "Tháng này doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 5600000, "Base query", "RULE_POLITE_INVARIANCE", "2026-03-04"),
        ("BM_META_02", "biz_099", "Dạ em kính chào anh chị, cho em xin phép được hỏi doanh thu tháng này là bao nhiêu ạ?", "revenue", ["thanh_tien"], "number", 5600000, "Polite particles must NOT change the SQL result", "RULE_POLITE_INVARIANCE", "2026-03-04"),
        ("BM_META_03", "biz_fixture_probe", "Sản phẩm nào bán được nhiều nhất?", "ranking_product_quantity", ["so_luong"], "string", "Sản phẩm A", "Quantity measure target", "RULE_MEASURE_SENSITIVITY", "2026-03-04"),
        ("BM_META_04", "biz_fixture_probe", "Sản phẩm nào thu về nhiều tiền nhất?", "ranking_product_revenue", ["thanh_tien"], "string", "Sản phẩm B", "Revenue measure target must change output from A to B", "RULE_MEASURE_SENSITIVITY", "2026-03-04"),
        ("BM_META_05", "biz_099", "Tháng này doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 5600000, "As of 2026-03-04", "RULE_DATE_SENSITIVITY", "2026-03-04"),
        ("BM_META_06", "biz_099", "Tháng này doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 825000, "As of 2026-02-28 must shift target to Feb 2026 (825k)", "RULE_DATE_SENSITIVITY", "2026-02-28"),
        ("BM_META_07", "biz_099", "Tháng này doanh thu bao nhiêu?", "revenue", ["thanh_tien"], "number", 750000, "As of 2025-03-10 must shift target to March 2025 (750k)", "RULE_DATE_SENSITIVITY", "2025-03-10"),
        ("BM_META_08", "biz_099", "Tháng này bán được bao nhiêu đơn?", "order_count", ["count_orders"], "number", 4, "Distinct order count (4)", "RULE_ORDER_VS_PRODUCT", "2026-03-04"),
        ("BM_META_09", "biz_099", "Tháng này bán được bao nhiêu sản phẩm?", "quantity", ["so_luong"], "number", 182, "Total item quantity (182) != Order count (4)", "RULE_ORDER_VS_PRODUCT", "2026-03-04"),
        ("BM_META_10", "biz_099", "Tháng này tiệm mình thu được bao nhiêu tiền?", "revenue", ["thanh_tien"], "number", 5600000, "Total revenue (5.6M) != Quantity (182)", "RULE_REVENUE_VS_QUANTITY", "2026-03-04"),
    ]
    for qid, biz, text, intent, meas, atype, ans, rsn, mrule, aod in metamorphic_data:
        add_q(qid, "metamorphic_tests", biz, text, intent, meas, atype, ans, rsn, metamorphic_rule=mrule, as_of_date=aod)

    return questions


def main():
    qs = build_benchmark()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(qs, f, ensure_ascii=False, indent=2)

    # Also write JSONL format for streaming pipelines
    jsonl_path = os.path.splitext(OUTPUT_PATH)[0] + ".jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"Generated Benchmark with {len(qs)} questions.")
    print(f"JSON Output: {OUTPUT_PATH}")
    print(f"JSONL Output: {jsonl_path}")


if __name__ == "__main__":
    main()
