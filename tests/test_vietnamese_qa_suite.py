import os
import shutil
import tempfile
import pandas as pd
import pytest

from datamate.core.types import AnswerType, QuestionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import evaluate_single_answer


@pytest.fixture
def qa_fixture_env():
    """Build a comprehensive multi-business environment designed to test all 6 QA groups:

    - biz_semantic_probe: Specially crafted fixture where Quantity leader and Revenue leader are completely different!
        * Product A: Quantity 100, Revenue 1,000,000
        * Product B: Quantity 20, Revenue 2,000,000
    - biz_pharmacy: Full pharmacy data with historical dates, lunar festival dates, debt records.
    - biz_orders_empty: Empty table to test no transactions.
    """
    temp_dir = tempfile.mkdtemp()

    # -------------------------------------------------------------
    # 1. BIZ: biz_semantic_probe (User's Recommended Fixture!)
    # -------------------------------------------------------------
    biz_sem = os.path.join(temp_dir, "biz_semantic_probe")
    os.makedirs(biz_sem, exist_ok=True)
    with open(os.path.join(biz_sem, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Cửa hàng bách hóa Probe\nThử nghiệm phân biệt số lượng và doanh thu.\n")

    sem_orders = {
        "ngay_ban": ["2026-03-01", "2026-03-02", "2026-03-03"],
        "ma_sp": ["SP_A", "SP_B", "SP_C"],
        "ten_san_pham": ["Sản phẩm A", "Sản phẩm B", "Sản phẩm C"],
        "so_luong": [100, 20, 5],
        "don_gia": [10000, 100000, 20000],
        "thanh_tien": [1000000, 2000000, 100000],
        "trang_thai": ["Hoàn thành", "Hoàn thành", "Hoàn thành"],
    }
    pd.DataFrame(sem_orders).to_csv(os.path.join(biz_sem, "don_hang.csv"), index=False, encoding="utf-8")

    # -------------------------------------------------------------
    # 2. BIZ: biz_099 (Nhà thuốc An Tâm)
    # -------------------------------------------------------------
    biz_099 = os.path.join(temp_dir, "biz_099")
    os.makedirs(biz_099, exist_ok=True)
    with open(os.path.join(biz_099, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Nhà thuốc An Tâm\nBán lẻ dược phẩm, thiết bị y tế.\n")

    # Hoa don
    # as_of_date = 2026-03-04 (Wednesday)
    # Previous week (Tuần rồi): 2026-02-23 to 2026-03-01
    # 7 ngày gần đây: 2026-02-26 to 2026-03-04
    # Tết 2026: 2026-02-17
    # Rằm tháng Giêng 2026: 2026-03-03
    # Cùng kỳ năm ngoái: 2025-03-04
    hoa_don_data = {
        "ma_don": ["HD01", "HD02", "HD03", "HD04", "HD05", "HD06", "HD07"],
        "ngay_tao": [
            "2025-03-04",  # Cùng kỳ năm ngoái (March 2025)
            "2026-02-18",  # Sau Tết (Mùng 2 Tết)
            "2026-02-25",  # Tuần rồi (Wednesday of prev week)
            "2026-03-02",  # Tháng này (Monday of this week)
            "2026-03-03",  # Tháng này (Rằm tháng Giêng)
            "2026-03-04",  # Tháng này (as_of_date)
            "2026-03-04",  # Tháng này (as_of_date)
        ],
        "ten_thuoc": [
            "Panadol Extra đỏ vỉ",
            "Berberin hộp",
            "Panadol Extra đỏ vỉ",
            "Panadol Extra đỏ vỉ",
            "Berberin hộp",
            "Khẩu trang 4 lớp",
            "Máy đo huyết áp Omron",
        ],
        "so_luong": [50, 15, 40, 100, 30, 50, 2],
        "don_gia": [15000, 15000, 15000, 15000, 15000, 25000, 1200000],
        "thanh_tien": [750000, 225000, 600000, 1500000, 450000, 1250000, 2400000],
        "trang_thai": [
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
        ],
    }
    pd.DataFrame(hoa_don_data).to_csv(os.path.join(biz_099, "hoa_don.csv"), index=False, encoding="utf-8")

    # So no
    so_no_data = {
        "ten_khach_hang": ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến", "Bs Hùng"],
        "so_dien_thoai": ["0901234567", "0912345678", "0987654321"],
        "tong_no": [4500000, 12000000, 0],
    }
    pd.DataFrame(so_no_data).to_csv(os.path.join(biz_099, "so_no.csv"), index=False, encoding="utf-8")

    # -------------------------------------------------------------
    # 3. BIZ: biz_empty_sales (No transactions in date range)
    # -------------------------------------------------------------
    biz_empty = os.path.join(temp_dir, "biz_empty_sales")
    os.makedirs(biz_empty, exist_ok=True)
    with open(os.path.join(biz_empty, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Tiệm mới mở\nChưa phát sinh giao dịch.\n")
    empty_df = pd.DataFrame(columns=["ngay_tao", "ten_thuoc", "so_luong", "thanh_tien", "trang_thai"])
    empty_df.to_csv(os.path.join(biz_empty, "hoa_don.csv"), index=False, encoding="utf-8")

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# SECTION 6: 15 PRIORITY TEST CASES CHECKLIST
# ==============================================================================

def test_p0_checklist_vn02(qa_fixture_env):
    """VN-02: Tháng này mặt hàng nào bán chạy nhất?"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_vn02", business_id="biz_099", question="Tháng này mặt hàng nào bán chạy nhất?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.STRING
    assert ans.answer == "Panadol Extra đỏ vỉ"


def test_p0_checklist_vn03(qa_fixture_env):
    """VN-03: Anh/chị xem giúp em tháng này thuốc nào bán chạy nhất với."""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_vn03", business_id="biz_099", question="Anh/chị xem giúp em tháng này thuốc nào bán chạy nhất với.", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.STRING
    assert ans.answer == "Panadol Extra đỏ vỉ"


def test_p0_checklist_chat01(qa_fixture_env):
    """CHAT-01: sp bán dc nhiều nhất tuần rồi là gì"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_chat01", business_id="biz_099", question="sp bán dc nhiều nhất tuần rồi là gì", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.STRING
    assert ans.answer == "Panadol Extra đỏ vỉ"


def test_p0_checklist_chat06(qa_fixture_env):
    """CHAT-06: thang nay mat hang nao ban chay nhat (tiếng Việt không dấu)"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_chat06", business_id="biz_099", question="thang nay mat hang nao ban chay nhat", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.STRING
    assert ans.answer == "Panadol Extra đỏ vỉ"


def test_p0_checklist_chat07(qa_fixture_env):
    """CHAT-07: sp nào bán dc nhìu nhất tuần rùi z shop (teencode)"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_chat07", business_id="biz_099", question="sp nào bán dc nhìu nhất tuần rùi z shop", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.STRING
    assert ans.answer == "Panadol Extra đỏ vỉ"


def test_p0_checklist_dia04(qa_fixture_env):
    """DIA-04: Bữa giờ thuốc nào bán chạy nhất vậy? (Thời gian mơ hồ 'bữa giờ' -> ABSTAIN)"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_dia04", business_id="biz_099", question="Bữa giờ thuốc nào bán chạy nhất vậy?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.ABSTAIN


def test_p0_checklist_dia06(qa_fixture_env):
    """DIA-06: Tháng ni thuốc mô bán chạy nhất rứa? (Phương ngữ miền Trung)"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_dia06", business_id="biz_099", question="Tháng ni thuốc mô bán chạy nhất rứa?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.STRING
    assert ans.answer == "Panadol Extra đỏ vỉ"


def test_p0_checklist_sem01_quantity(qa_fixture_env):
    """SEM-01: Sản phẩm nào bán được nhiều nhất? -> Tính theo SUM(quantity)"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_sem01", business_id="biz_semantic_probe", question="Sản phẩm nào bán được nhiều nhất?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.STRING
    assert ans.answer == "Sản phẩm A"  # Qty: 100 > 20


def test_p0_checklist_sem02_revenue(qa_fixture_env):
    """SEM-02: Sản phẩm nào thu về nhiều tiền nhất? -> Tính theo SUM(revenue)"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_sem02", business_id="biz_semantic_probe", question="Sản phẩm nào thu về nhiều tiền nhất?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.STRING
    assert ans.answer == "Sản phẩm B"  # Revenue: 2,000,000 > 1,000,000


def test_p0_checklist_sem03_profit_unanswerable(qa_fixture_env):
    """SEM-03: Sản phẩm nào có lợi nhuận cao nhất? -> Không có giá vốn -> UNANSWERABLE"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_sem03", business_id="biz_semantic_probe", question="Sản phẩm nào có lợi nhuận cao nhất?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.UNANSWERABLE


def test_p0_checklist_time04(qa_fixture_env):
    """TIME-04: 7 ngày gần đây bán được bao nhiêu? -> Dynamic 7-day window [2026-02-26 to 2026-03-04]

    Orders in window:
    - 2026-03-02: 100
    - 2026-03-03: 30
    - 2026-03-04: 50
    - 2026-03-04: 2
    Total qty = 182
    """
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_time04", business_id="biz_099", question="7 ngày gần đây bán được bao nhiêu?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.NUMBER
    assert ans.answer == 182


def test_p0_checklist_time06(qa_fixture_env):
    """TIME-06: Từ sau Tết đến giờ bán được bao nhiêu? (Tết 2026: 2026-02-17 to 2026-03-04)

    Orders:
    - 2026-02-18: 15
    - 2026-02-25: 40
    - 2026-03-02: 100
    - 2026-03-03: 30
    - 2026-03-04: 50
    - 2026-03-04: 2
    Total qty = 237
    """
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_time06", business_id="biz_099", question="Từ sau Tết đến giờ bán được bao nhiêu?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.NUMBER
    assert ans.answer == 237


def test_p0_checklist_neg01_net_profit(qa_fixture_env):
    """NEG-01: Lợi nhuận ròng tháng này bao nhiêu? -> UNANSWERABLE"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_neg01", business_id="biz_099", question="Lợi nhuận ròng tháng này bao nhiêu?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.UNANSWERABLE


def test_p0_checklist_neg04_causal_why(qa_fixture_env):
    """NEG-04: Tại sao doanh thu tháng này giảm? -> UNANSWERABLE (Không bịa nguyên nhân)"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_neg04", business_id="biz_099", question="Tại sao doanh thu tháng này giảm?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type == AnswerType.UNANSWERABLE


def test_p0_checklist_neg09_no_transactions(qa_fixture_env):
    """NEG-09: Thuốc nào bán chạy nhất? (Khi không có giao dịch -> Không tự bịa sản phẩm!)"""
    agent = DataMateAgent(qa_fixture_env)
    q = QuestionItem(id="chk_neg09", business_id="biz_empty_sales", question="Thuốc nào bán chạy nhất?", as_of_date="2026-03-04")
    ans = agent.answer_question(q)
    assert ans.type in (AnswerType.ABSTAIN, AnswerType.UNANSWERABLE)
    assert ans.answer is None  # Must NOT hallucinate any product name!


# ==============================================================================
# GROUP A: XƯNG HÔ, LỊCH SỰ VÀ VĂN HÓA GIAO TIẾP
# ==============================================================================

def test_group_a_honorifics_and_politeness(qa_fixture_env):
    agent = DataMateAgent(qa_fixture_env)

    # VN-01
    q1 = QuestionItem(id="vn01", business_id="biz_099", question="Tháng này mặt hàng nào bán chạy nhất?", as_of_date="2026-03-04")
    ans1 = agent.answer_question(q1)
    assert ans1.answer == "Panadol Extra đỏ vỉ"

    # VN-03: Doanh thu tháng này (March 2026: 1.5M + 450k + 1.25M + 2.4M = 5,600,000)
    q3 = QuestionItem(id="vn03", business_id="biz_099", question="Cho mình hỏi doanh thu tháng này là bao nhiêu ạ?", as_of_date="2026-03-04")
    ans3 = agent.answer_question(q3)
    assert ans3.type == AnswerType.NUMBER
    assert ans3.answer == 5600000

    # VN-04: Tuần rồi bán được bao nhiêu tiền? (2026-02-23 to 2026-03-01: 600,000)
    q4 = QuestionItem(id="vn04", business_id="biz_099", question="Nhờ shop kiểm tra dùm mình tuần rồi bán được bao nhiêu tiền nhé.", as_of_date="2026-03-04")
    ans4 = agent.answer_question(q4)
    assert ans4.type == AnswerType.NUMBER
    assert ans4.answer == 600000

    # VN-05: Bên mình còn ai đang nợ tiền chưa trả không?
    q5 = QuestionItem(id="vn05", business_id="biz_099", question="Bên mình còn ai đang nợ tiền chưa trả không?", as_of_date="2026-03-04")
    ans5 = agent.answer_question(q5)
    assert ans5.type == AnswerType.LIST
    assert "Phòng khám BS Minh" in ans5.answer
    assert "Trạm y tế Xã Tân Tiến" in ans5.answer
    assert "Bs Hùng" not in ans5.answer  # 0 debt

    # VN-06: Mặt hàng bán ế nhất (ít nhất) tháng này -> Máy đo huyết áp Omron (qty 2)
    q6 = QuestionItem(id="vn06", business_id="biz_099", question="Cô/chú coi thử mặt hàng nào bán ế nhất tháng này.", as_of_date="2026-03-04")
    ans6 = agent.answer_question(q6)
    assert ans6.type == AnswerType.STRING
    assert ans6.answer == "Máy đo huyết áp Omron"

    # VN-08: Mấy anh chị cho em hỏi sản phẩm nào bán tốt nhất trong tháng này?
    q8 = QuestionItem(id="vn08", business_id="biz_099", question="Mấy anh chị cho em hỏi sản phẩm nào bán tốt nhất trong tháng này?", as_of_date="2026-03-04")
    ans8 = agent.answer_question(q8)
    assert ans8.answer == "Panadol Extra đỏ vỉ"


# ==============================================================================
# GROUP B: TIẾNG LÓNG, VIẾT TẮT, KHÔNG DẤU, TEENCODE
# ==============================================================================

def test_group_b_chat_and_teencode(qa_fixture_env):
    agent = DataMateAgent(qa_fixture_env)

    # CHAT-02
    q2 = QuestionItem(id="chat02", business_id="biz_099", question="tháng này sp nào bán chạy nhất vậy shop", as_of_date="2026-03-04")
    assert agent.answer_question(q2).answer == "Panadol Extra đỏ vỉ"

    # CHAT-03: tuần rồi bán dc bn tiền?
    q3 = QuestionItem(id="chat03", business_id="biz_099", question="tuần rồi bán dc bn tiền?", as_of_date="2026-03-04")
    assert agent.answer_question(q3).answer == 600000

    # CHAT-04: còn ai nợ tiền chưa trả ko?
    q4 = QuestionItem(id="chat04", business_id="biz_099", question="còn ai nợ tiền chưa trả ko?", as_of_date="2026-03-04")
    ans4 = agent.answer_question(q4)
    assert ans4.type == AnswerType.LIST
    assert len(ans4.answer) == 2

    # CHAT-05: doanh thu tháng này nhiu z?
    q5 = QuestionItem(id="chat05", business_id="biz_099", question="doanh thu tháng này nhiu z?", as_of_date="2026-03-04")
    assert agent.answer_question(q5).answer == 5600000

    # CHAT-08: check giúp mình doanh thu tháng này nha
    q8 = QuestionItem(id="chat08", business_id="biz_099", question="check giúp mình doanh thu tháng này nha", as_of_date="2026-03-04")
    assert agent.answer_question(q8).answer == 5600000

    # CHAT-10: thuốc nào sắp hết date vậy?
    q10 = QuestionItem(id="chat10", business_id="biz_099", question="thuốc nào sắp hết date vậy?", as_of_date="2026-03-04")
    assert agent.answer_question(q10).type == AnswerType.UNANSWERABLE


# ==============================================================================
# GROUP C: PHƯƠNG NGỮ BẮC - TRUNG - NAM
# ==============================================================================

def test_group_c_regional_dialects(qa_fixture_env):
    agent = DataMateAgent(qa_fixture_env)

    # DIA-01: Miền Bắc (tiêu thụ nhiều nhất)
    q1 = QuestionItem(id="dia01", business_id="biz_099", question="Tháng này mặt hàng nào tiêu thụ nhiều nhất nhỉ?", as_of_date="2026-03-04")
    assert agent.answer_question(q1).answer == "Panadol Extra đỏ vỉ"

    # DIA-03: Miền Nam (món nào bán chạy nhất)
    q3 = QuestionItem(id="dia03", business_id="biz_099", question="Tháng này món nào bán chạy nhất vậy shop?", as_of_date="2026-03-04")
    assert agent.answer_question(q3).answer == "Panadol Extra đỏ vỉ"

    # DIA-05: Miền Nam (Hông biết tháng này doanh thu được nhiêu rồi ta?)
    q5 = QuestionItem(id="dia05", business_id="biz_099", question="Hông biết tháng này doanh thu được nhiêu rồi ta?", as_of_date="2026-03-04")
    assert agent.answer_question(q5).answer == 5600000

    # DIA-07: Miền Trung (Răng tháng này doanh thu thấp hơn tháng trước hè? -> UNANSWERABLE)
    q7 = QuestionItem(id="dia07", business_id="biz_099", question="Răng tháng này doanh thu thấp hơn tháng trước hè?", as_of_date="2026-03-04")
    assert agent.answer_question(q7).type == AnswerType.UNANSWERABLE

    # DIA-08: Biến thể từ vựng (Tiệm mình tháng này bán được bao nhiêu món rồi?)
    # Total March qty = 100 + 30 + 50 + 2 = 182
    q8 = QuestionItem(id="dia08", business_id="biz_099", question="Tiệm mình tháng này bán được bao nhiêu món rồi?", as_of_date="2026-03-04")
    assert agent.answer_question(q8).answer == 182


# ==============================================================================
# GROUP D: SEMANTIC TESTING
# ==============================================================================

def test_group_d_semantic_distinctions(qa_fixture_env):
    agent = DataMateAgent(qa_fixture_env)

    # SEM-04: Đơn hàng nào có giá trị cao nhất? (HD07 với 2,400,000)
    q4 = QuestionItem(id="sem04", business_id="biz_099", question="Đơn hàng nào có giá trị cao nhất?", as_of_date="2026-03-04")
    ans4 = agent.answer_question(q4)
    assert ans4.answer == "HD07"

    # SEM-06: Mặt hàng nào bán ế nhất? (Máy đo huyết áp Omron: qty 2)
    q6 = QuestionItem(id="sem06", business_id="biz_099", question="Mặt hàng nào bán ế nhất?", as_of_date="2026-03-04")
    assert agent.answer_question(q6).answer == "Máy đo huyết áp Omron"

    # SEM-07: Ai đang nợ tiền lâu nhất? -> Không có ngày vay/hạn nợ -> UNANSWERABLE
    q7 = QuestionItem(id="sem07", business_id="biz_099", question="Ai đang nợ tiền lâu nhất?", as_of_date="2026-03-04")
    assert agent.answer_question(q7).type == AnswerType.UNANSWERABLE

    # SEM-08: Mặt hàng nào có doanh thu thấp nhất trong tháng? (Berberin: 450k)
    q8 = QuestionItem(id="sem08", business_id="biz_099", question="Mặt hàng nào có doanh thu thấp nhất tháng này?", as_of_date="2026-03-04")
    assert agent.answer_question(q8).answer == "Berberin hộp"

    # SEM-10: Tháng này bán được bao nhiêu đơn? -> COUNT đơn = 4
    q10 = QuestionItem(id="sem10", business_id="biz_099", question="Tháng này bán được bao nhiêu đơn?", as_of_date="2026-03-04")
    ans10 = agent.answer_question(q10)
    assert ans10.type == AnswerType.NUMBER
    assert ans10.answer == 4


# ==============================================================================
# GROUP E: TEMPORAL TESTING & AS_OF_DATE SENSITIVITY
# ==============================================================================

def test_group_e_temporal_accuracy(qa_fixture_env):
    agent = DataMateAgent(qa_fixture_env)

    # TIME-01: Tháng này doanh thu bao nhiêu? (5,600,000)
    q1 = QuestionItem(id="t01", business_id="biz_099", question="Tháng này doanh thu bao nhiêu?", as_of_date="2026-03-04")
    assert agent.answer_question(q1).answer == 5600000

    # TIME-05: Cùng kỳ năm ngoái doanh thu bao nhiêu? (March 2025: 750,000)
    q5 = QuestionItem(id="t05", business_id="biz_099", question="Cùng kỳ năm ngoái doanh thu bao nhiêu?", as_of_date="2026-03-04")
    assert agent.answer_question(q5).answer == 750000

    # TIME-08: Từ mùng 1 đến rằm tháng Giêng bán được bao nhiêu? (2026-02-17 to 2026-03-03)
    # Orders:
    # 2026-02-18 (Berberin: 15)
    # 2026-02-25 (Panadol: 40)
    # 2026-03-02 (Panadol: 100)
    # 2026-03-03 (Berberin: 30)
    # Total = 185
    q8 = QuestionItem(id="t08", business_id="biz_099", question="Từ mùng 1 đến rằm tháng Giêng bán được bao nhiêu?", as_of_date="2026-03-04")
    assert agent.answer_question(q8).answer == 185

    # TIME-09: Doanh thu từ đầu tháng đến hết hôm qua? (2026-03-01 to 2026-03-03)
    # 2026-03-02 (1.5M) + 2026-03-03 (450k) = 1,950,000
    q9 = QuestionItem(id="t09", business_id="biz_099", question="Doanh thu từ đầu tháng đến hết hôm qua là bao nhiêu?", as_of_date="2026-03-04")
    assert agent.answer_question(q9).answer == 1950000

    # TIME-10: Ngày 04/03 doanh thu bao nhiêu? (2026-03-04: 1.25M + 2.4M = 3,650,000)
    q10 = QuestionItem(id="t10", business_id="biz_099", question="Ngày 04/03 doanh thu bao nhiêu?", as_of_date="2026-03-04")
    assert agent.answer_question(q10).answer == 3650000


def test_group_e_dynamic_as_of_date_switch(qa_fixture_env):
    """CRITICAL TEST: Switching as_of_date changes outputs dynamically without relying on machine clock."""
    agent = DataMateAgent(qa_fixture_env)

    # Query 1: As of 2026-03-04 -> Tháng này = March 2026 -> 5,600,000
    q_march = QuestionItem(id="dyn_01", business_id="biz_099", question="Tháng này doanh thu bao nhiêu?", as_of_date="2026-03-04")
    ans_march = agent.answer_question(q_march)
    assert ans_march.answer == 5600000

    # Query 2: Change as_of_date to February (2026-02-28) -> Tháng này = Feb 2026 -> 225k + 600k = 825,000
    q_feb = QuestionItem(id="dyn_02", business_id="biz_099", question="Tháng này doanh thu bao nhiêu?", as_of_date="2026-02-28")
    ans_feb = agent.answer_question(q_feb)
    assert ans_feb.answer == 825000

    # Query 3: Change as_of_date to March 2025 -> Tháng này = March 2025 -> 750,000
    q_2025 = QuestionItem(id="dyn_03", business_id="biz_099", question="Tháng này doanh thu bao nhiêu?", as_of_date="2025-03-10")
    ans_2025 = agent.answer_question(q_2025)
    assert ans_2025.answer == 750000


# ==============================================================================
# GROUP F: NEGATIVE TESTING & ANSWERABILITY
# ==============================================================================

def test_group_f_unanswerable_and_abstain(qa_fixture_env):
    agent = DataMateAgent(qa_fixture_env)

    # NEG-02: Thuốc nào sắp hết hạn?
    q2 = QuestionItem(id="neg02", business_id="biz_099", question="Thuốc nào sắp hết hạn?", as_of_date="2026-03-04")
    assert agent.answer_question(q2).type == AnswerType.UNANSWERABLE

    # NEG-03: Kho còn bao nhiêu thuốc Panadol?
    q3 = QuestionItem(id="neg03", business_id="biz_099", question="Kho còn bao nhiêu thuốc Panadol?", as_of_date="2026-03-04")
    assert agent.answer_question(q3).type == AnswerType.UNANSWERABLE

    # NEG-05: Dự đoán tháng sau bán được bao nhiêu?
    q5 = QuestionItem(id="neg05", business_id="biz_099", question="Dự đoán tháng sau bán được bao nhiêu?", as_of_date="2026-03-04")
    assert agent.answer_question(q5).type == AnswerType.UNANSWERABLE

    # NEG-06: Khách hàng thân thiết nhất là ai?
    q6 = QuestionItem(id="neg06", business_id="biz_099", question="Khách hàng thân thiết nhất là ai?", as_of_date="2026-03-04")
    assert agent.answer_question(q6).type == AnswerType.UNANSWERABLE

    # NEG-07: ROI của cửa hàng là bao nhiêu?
    q7 = QuestionItem(id="neg07", business_id="biz_099", question="ROI của cửa hàng là bao nhiêu?", as_of_date="2026-03-04")
    assert agent.answer_question(q7).type == AnswerType.UNANSWERABLE

    # NEG-08: Doanh thu của nhân viên Nguyễn Văn A?
    q8 = QuestionItem(id="neg08", business_id="biz_099", question="Doanh thu của nhân viên Nguyễn Văn A?", as_of_date="2026-03-04")
    assert agent.answer_question(q8).type == AnswerType.UNANSWERABLE

    # NEG-10: Ngày mai cửa hàng sẽ bán được bao nhiêu?
    q10 = QuestionItem(id="neg10", business_id="biz_099", question="Ngày mai cửa hàng sẽ bán được bao nhiêu?", as_of_date="2026-03-04")
    assert agent.answer_question(q10).type == AnswerType.UNANSWERABLE
