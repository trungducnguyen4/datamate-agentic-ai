from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class NormalizedQueryInfo:
    original_query: str
    clean_query: str
    tokens: List[str] = field(default_factory=list)
    is_why_causal: bool = False
    is_future: bool = False
    is_ambiguous_time: bool = False
    is_subjective: bool = False
    is_quantity_query: bool = False
    is_revenue_query: bool = False
    is_revenue_ranking: bool = False
    is_quantity_ranking: bool = False
    is_profit_cost_query: bool = False
    is_expiration_query: bool = False
    is_stock_query: bool = False
    is_order_count_query: bool = False
    is_order_max_query: bool = False
    is_order_min_query: bool = False
    is_avg_order_revenue_query: bool = False
    is_avg_order_qty_query: bool = False
    is_debt_query: bool = False
    is_debt_amount_query: bool = False
    is_debt_count_query: bool = False
    is_debt_max_query: bool = False
    is_debt_min_query: bool = False
    is_debt_customer_query: bool = False
    is_debt_duration_query: bool = False
    is_debt_highest: bool = False
    debt_above: Optional[float] = None
    debt_below: Optional[float] = None
    is_distinct_product_query: bool = False
    is_unsold_query: bool = False
    is_customer_query: bool = False
    is_customer_loyalty_query: bool = False
    is_employee_query: bool = False
    is_cancellation_query: bool = False
    is_lowest_ranking: bool = False
    is_zero_value_query: bool = False
    is_negative_value_query: bool = False
    is_success_rate_query: bool = False
    is_canceled_revenue_query: bool = False
    is_special_char_query: bool = False
    has_specific_product: Optional[str] = None
    has_specific_order: Optional[str] = None
    has_specific_customer: Optional[str] = None
    top_k: Optional[int] = None
    is_which_day_query: bool = False
    is_which_month_query: bool = False
    is_consecutive_growth_query: bool = False
    is_cancellation_rate_query: bool = False
    is_table_query: bool = False
    category_filter: Optional[str] = None
    metric_target: Optional[str] = None
    candidate_months: List[str] = field(default_factory=list)


class VietnameseNLP:
    """Comprehensive Vietnamese NLU preprocessor for DataMate.

    Handles:
    1. Conversational honorifics and polite fluff stripping.
    2. Slang, abbreviations, and teencode expansion (sp, dc, bn, ko, nhiu, z, rui, date...).
    3. Northern, Central, and Southern regional dialect normalization (tháng ni, mô, rứa, răng, bữa giờ...).
    4. Accentless (không dấu) recovery for key business query phrases.
    5. Semantic intent and negative trigger classification.
    """

    # Teencode / Abbreviation dictionary (word boundaries)
    TEENCODE_MAP = {
        r"\bsp\b": "sản phẩm",
        r"\bdc\b": "được",
        r"\bđc\b": "được",
        r"\bbn\b": "bao nhiêu",
        r"\bko\b": "không",
        r"\bk\b": "không",
        r"\bhk\b": "không",
        r"\bhông\b": "không",
        r"\bnhiu\b": "nhiêu",
        r"\bnhìu\b": "nhiều",
        r"\bz\b": "vậy",
        r"\brùi\b": "rồi",
        r"\bròi\b": "rồi",
        r"\bdùm\b": "giúp",
        r"\bgiùm\b": "giúp",
        r"\bdate\b": "hạn sử dụng",
        r"\bcheck\b": "kiểm tra",
        r"\btui\b": "tôi",
        r"\bsl\b": "số lượng",
        r"\bdt\b": "doanh thu",
        r"\bkh\b": "khách hàng",
        r"\bhqua\b": "hôm qua",
        r"\bhq\b": "hôm qua",
        r"\bhqa\b": "hôm qua",
        r"\bhnay\b": "hôm nay",
    }

    # Regional dialect mapping
    DIALECT_MAP = {
        # Central dialect (Miền Trung)
        r"\btháng ni\b": "tháng này",
        r"\btuần ni\b": "tuần này",
        r"\bngày ni\b": "ngày này",
        r"\bhôm ni\b": "hôm nay",
        r"\bhom ni\b": "hôm nay",
        r"\bnăm ni\b": "năm nay",
        r"\bđơn mô\b": "đơn nào",
        r"\bthuốc mô\b": "thuốc nào",
        r"\bmặt hàng mô\b": "mặt hàng nào",
        r"\bhàng mô\b": "hàng nào",
        r"\bmón mô\b": "món nào",
        r"\bsp mô\b": "sản phẩm nào",
        r"\brứa\b": "vậy",
        r"\brăng\b": "tại sao",
        r"\bhè\b": "",
        r"\bchi\b": "gì",
        r"\bchừ\b": "hiện tại",
        # Northern & Southern dialect nuances
        r"\bto tiền nhất\b": "nhiều tiền nhất",
        r"\bnặng tiền nhất\b": "nhiều tiền nhất",
        r"\bbán chậm nhất\b": "bán ế nhất",
        r"\bnguồn thu kém nhất\b": "thu về ít tiền nhất",
        r"\bmón nào\b": "món nào",
        r"\bđược nhiêu\b": "được bao nhiêu",
        r"\bbao nhiêu tiền rồi ta\b": "bao nhiêu tiền",
        r"\bta\b$": "",
    }

    # Common unaccented patterns -> Accented equivalents
    UNACCENTED_PHRASES = [
        (r"\bthang nay mat hang nao ban chay nhat\b", "tháng này mặt hàng nào bán chạy nhất"),
        (r"\bmat hang nao ban chay nhat\b", "mặt hàng nào bán chạy nhất"),
        (r"\bmat hang nao ban e nhat thang nay\b", "mặt hàng nào bán ế nhất tháng này"),
        (r"\bmat hang nao ban e nhat\b", "mặt hàng nào bán ế nhất"),
        (r"\bsp ban dc nhieu nhat tuan roi la gi\b", "sản phẩm bán được nhiều nhất tuần rồi là gì"),
        (r"\bsp ban dc nhieu nhat\b", "sản phẩm bán được nhiều nhất"),
        (r"\bsan pham nao thu ve nhieu tien nhat thang nay\b", "sản phẩm nào thu về nhiều tiền nhất tháng này"),
        (r"\bsan pham nao thu ve nhieu tien nhat\b", "sản phẩm nào thu về nhiều tiền nhất tháng này"),
        (r"\bthu ve nhieu tien nhat\b", "thu về nhiều tiền nhất"),
        (r"\bban chay nhat\b", "bán chạy nhất"),
        (r"\bban chay\b", "bán chạy"),
        (r"\bban e nhat\b", "bán ế nhất"),
        (r"\bban cham nhat\b", "bán chậm nhất"),
        (r"\bthang nay ban duoc bao nhieu don\b", "tháng này bán được bao nhiêu đơn"),
        (r"\bdon hang nao co gia tri cao nhat\b", "đơn hàng nào có giá trị cao nhất"),
        (r"\btong tien no cua khach hang la bao nhieu\b", "tổng tiền nợ của khách hàng là bao nhiêu"),
        (r"\btong tien no\b", "tổng tiền nợ"),
        (r"\btong no\b", "tổng nợ"),
        (r"\btong cong no\b", "tổng công nợ"),
        (r"\bcung ky nam ngoai doanh thu bao nhieu\b", "cùng kỳ năm ngoái doanh thu bao nhiêu"),
        (r"\bcung ky nam ngoai\b", "cùng kỳ năm ngoái"),
        (r"\btu sau tet den gio ban duoc bao nhieu\b", "từ sau tết đến giờ bán được bao nhiêu"),
        (r"\btu sau tet den gio\b", "từ sau tết đến giờ"),
        (r"\bdoanh thu tu dau thang den het hom qua\b", "doanh thu từ đầu tháng đến hết hôm qua"),
        (r"\btu dau thang den het hom qua\b", "từ đầu tháng đến hết hôm qua"),
        (r"\bthang nay ban duoc bao nhieu san pham\b", "tháng này bán được bao nhiêu sản phẩm"),
        (r"\b7 ngay gan day ban duoc bao nhieu\b", "7 ngày gần đây bán được bao nhiêu"),
        (r"\bthang nay\b", "tháng này"),
        (r"\bthang truoc\b", "tháng trước"),
        (r"\btuan nay\b", "tuần này"),
        (r"\btuan roi\b", "tuần rồi"),
        (r"\btuan truoc\b", "tuần trước"),
        (r"\bdoanh thu\b", "doanh thu"),
        (r"\bso luong\b", "số lượng"),
        (r"\bmat hang\b", "mặt hàng"),
        (r"\bthuoc nao\b", "thuốc nào"),
        (r"\bmon nao\b", "món nào"),
        (r"\bcon ai no\b", "còn ai nợ"),
        (r"\bchua tra\b", "chưa trả"),
        (r"\bloi nhuan\b", "lợi nhuận"),
        (r"\blai rong\b", "lãi ròng"),
        (r"\bsap het han\b", "sắp hết hạn"),
        (r"\bkho con bao nhieu\b", "kho còn bao nhiêu"),
        (r"\btai sao\b", "tại sao"),
        (r"\bgiam\b", "giảm"),
        (r"\btang\b", "tăng"),
        (r"\bdu doan\b", "dự đoán"),
        (r"\bngay mai\b", "ngày mai"),
        (r"\bhom nay\b", "hôm nay"),
        (r"\bhom qua\b", "hôm qua"),
        (r"\bbao nhieu\b", "bao nhiêu"),
        (r"\btien\b", "tiền"),
        (r"\bso don hang\b", "số đơn hàng"),
        (r"\bso don\b", "số đơn"),
        (r"\btong so don\b", "tổng số đơn"),
        (r"\bbao nhieu don\b", "bao nhiêu đơn"),
        (r"\bmay don\b", "mấy đơn"),
        (r"\bso luong don\b", "số lượng đơn"),
        (r"\bla bao nhieu\b", "là bao nhiêu"),
        (r"\bla bao nhiu\b", "là bao nhiêu"),
        (r"\bquy\s*([1-4]|i{1,3}|iv)\b", r"quý \1"),
        (r"\bthang\s*(\d{1,2})\b", r"tháng \1"),
        (r"\bnam\s*(\d{4})\b", r"năm \1"),
    ]

    # Conversational polite fluff / honorific patterns to strip for semantic core
    FLUFF_PATTERNS = [
        r"^\s*[eê]\s+",
        r"^\s*[eê]\s+này\s+",
        r"^\s*[eê]\s+bạn\s+",
        r"^\s*[eê]\s+cho\s+(?:mình|em|tôi)?\s*hỏi\s+",
        r"^\s*alo\s+",
        r"^\s*ơi\s+",
        r"^\s*mấy anh chị cho em hỏi\s*",
        r"^\s*anh\s*\/\s*chị xem giúp em\s*",
        r"^\s*anh chị xem giúp em\s*",
        r"^\s*anh\s+chị\s+coi\s+giúp\s+em\s*",
        r"^\s*anh\s+chị\s+coi\s+dùm\s+em\s*",
        r"^\s*anh\s+chị\s+cho\s+em\s+hỏi\s*",
        r"^\s*anh\s+chị\s+vui\s+lòng\s+kiểm\s+tra\s*",
        r"^\s*cho tôi biết\s*",
        r"^\s*xin hỏi\s*",
        r"^\s*cho mình hỏi\s*",
        r"^\s*nhờ shop kiểm tra dùm mình\s*",
        r"^\s*nhờ shop kiểm tra giúp mình\s*",
        r"^\s*cô\s*\/\s*chú coi thử\s*",
        r"^\s*cô chú coi thử\s*",
        r"^\s*không biết\s*",
        r"^\s*xem dùm tui\s*",
        r"^\s*xem giúp mình\s*",
        r"^\s*check giúp mình\s*",
        r"\bvới\s*$",
        r"\bnhé\s*$",
        r"\bnhỉ\s*$",
        r"\bạ\s*$",
        r"\bnha\s*$",
        r"\bvậy shop\s*$",
        r"\bz shop\s*$",
        r"\bvậy bác\s*$",
        r"\bvậy nè\s*$",
        r"\bvậy\s*$",
        r"\bvay\s*$",
        r"\bvay\s+nha\s*$",
        r"\bvậy\s+nha\s*$",
        r"\bvay\s+nhe\s*$",
        r"\bvậy\s+nhé\s*$",
        r"\bvay\s+shop\s*$",
        r"\bta\s*$",
    ]

    # Business prefixes that don't add semantic filters
    BUSINESS_REFERENCES = [
        r"\bbên mình\b",
        r"\btiệm mình\b",
        r"\bnhà thuốc mình\b",
        r"\bcửa hàng mình\b",
        r"\bquán mình\b",
        r"\bshop mình\b",
        r"\bshop\b",
    ]

    @classmethod
    def process_query(cls, query: str) -> NormalizedQueryInfo:
        """Fully process and normalize a Vietnamese question."""
        if not query:
            return NormalizedQueryInfo(original_query="", clean_query="")

        raw = unicodedata.normalize("NFC", query).strip()
        q = raw.lower()

        # Step 1: Detect intent flags before stripping
        is_why_causal = bool(re.search(r"\b(tại sao|tai sao|vì sao|vi sao|nguyên nhân|nguyen nhan|răng|do đâu|do dau)\b", q))
        is_future = bool(re.search(r"\b(dự đoán|dự báo|ngày mai|tháng sau|tuần sau|sắp tới|tương lai)\b", q))
        is_ambiguous_time = bool(re.search(r"\bbữa giờ\b", q))
        is_subjective = bool(re.search(r"\b(có khá không|khá không|ổn không|tốt không|kinh doanh.*được không|tình hình.*được không)\b", q))

        # Check for unaccented phrases
        for pattern, replacement in cls.UNACCENTED_PHRASES:
            q = re.sub(pattern, replacement, q)

        # Step 2: Expand teencode & slang
        for pattern, replacement in cls.TEENCODE_MAP.items():
            q = re.sub(pattern, replacement, q)

        # Step 3: Map regional dialects
        for pattern, replacement in cls.DIALECT_MAP.items():
            q = re.sub(pattern, replacement, q)

        # Step 4: Semantic intent classifications
        is_profit_cost_query = bool(
            re.search(r"\b(lợi nhuận|lãi ròng|lãi|giá vốn|chi phí|chi phí nhập|roi)\b", q)
        )
        is_expiration_query = bool(
            re.search(r"\b(hết hạn|sắp hết hạn|hết date|hạn sử dụng|hsd)\b", q)
        )
        is_stock_query = bool(
            re.search(r"\b(kho còn|trong kho|tồn kho|số lượng tồn|hàng tồn)\b", q)
            or (re.search(r"\bcòn bao nhiêu\b", q) and re.search(r"\bkho\b", q))
        )
        is_customer_loyalty_query = bool(
            re.search(r"\b(thân thiết nhất|khách quen|vip|khách hàng thân thiết)\b", q)
        )
        is_employee_query = bool(
            re.search(r"\b(nhân viên|người bán|nhân viên bán hàng)\b", q)
        )
        is_debt_duration_query = bool(
            re.search(r"\b(nợ tiền lâu nhất|nợ lâu nhất|quá hạn lâu nhất)\b", q)
        )
        is_debt_query = bool(
            re.search(r"\b(nợ|còn nợ|chưa trả|công nợ|khoản nợ)\b", q)
        )
        is_unsold_query = bool(
            re.search(r"\b(chưa bán được|chưa bán ra|không bán được)\b", q)
        )

        is_not_canceled = bool(re.search(r"\b(không bị hủy|không hủy|chưa bị hủy|chưa hủy)\b", q))
        is_cancellation_query = bool(
            re.search(r"\b(hủy|cancel|tỷ lệ hủy|đơn hủy|bị hủy)\b", q)
        ) and not is_not_canceled

        # Debt sub-types
        is_debt_highest = bool(re.search(r"\b(ai|khách hàng nào|người nào)\b", q) and re.search(r"\b(nợ nhiều tiền nhất|nợ nhiều nhất|nợ lớn nhất)\b", q))
        is_debt_max_query = bool(re.search(r"\b(khoản nợ lớn nhất|khoản nợ cao nhất|mức nợ cao nhất)\b", q) or (re.search(r"\bnợ lớn nhất\b", q) and not is_debt_highest))
        is_debt_min_query = bool(re.search(r"\b(khoản nợ nhỏ nhất|khoản nợ thấp nhất|nợ nhỏ nhất)\b", q))
        is_debt_count_query = bool(re.search(r"\b(bao nhiêu khách|số khách|mấy khách|bao nhiêu người)\b", q) and re.search(r"\b(nợ|còn nợ)\b", q))

        debt_above_match = re.search(r"nợ trên\s*(\d+)\s*(?:triệu|tr)", q)
        debt_above = float(debt_above_match.group(1)) * 1_000_000 if debt_above_match else None

        debt_below_match = re.search(r"nợ dưới\s*(\d+)\s*(?:triệu|tr)", q)
        debt_below = float(debt_below_match.group(1)) * 1_000_000 if debt_below_match else None

        is_debt_amount_query = bool(
            re.search(r"\b(tổng số tiền nợ|tổng công nợ|tổng nợ|tổng tiền nợ|nợ bao nhiêu tiền|tiền nợ.*bao nhiêu)\b", q)
        ) or (is_debt_query and bool(re.search(r"\b(tổng|bao nhiêu)\b", q)) and not is_debt_max_query and not is_debt_min_query and not is_debt_count_query and not bool(re.search(r"\b(ai|những ai|danh sách|mấy khách|bao nhiêu khách)\b", q)))

        is_debt_customer_query = bool(
            re.search(r"\b(ai nợ|những ai nợ|ai đang nợ|những ai đang nợ|còn ai nợ|danh sách nợ)\b", q)
        ) or is_debt_highest

        # Order queries
        is_order_count_query = (
            bool(
                re.search(
                    r"\b(bao nhiêu đơn|bao nhieu don|mấy đơn|may don|số đơn hàng|so don hang|số đơn|so don|số lượng đơn|so luong don|tổng số đơn|tong so don)\b",
                    q,
                )
            ) or is_not_canceled
        ) and not bool(re.search(r"\b(ai|khách nào|khach nao|người nào|nguoi nao|sản phẩm nào|san pham nao|món nào|mon nao)\b", q))

        is_order_max_query = bool(
            re.search(r"\b(đơn hàng nào|đơn nào|đơn).*(giá trị cao nhất|giá trị thanh toán cao nhất|thanh toán cao nhất|nhiều tiền nhất|to tiền nhất|nặng tiền nhất|lớn nhất|giá trị lớn nhất)\b", q)
            or re.search(r"\b(đơn hàng lớn nhất|đơn lớn nhất|giá trị đơn hàng cao nhất)\b", q)
        )
        is_order_min_query = bool(
            re.search(r"\b(đơn hàng.*giá trị nhỏ nhất|đơn.*nhỏ nhất|giá trị nhỏ nhất.*đơn|giá trị thấp nhất)\b", q)
        )

        # Average per order queries
        is_avg_order_revenue_query = bool(
            re.search(r"\b(doanh thu trung bình|doanh thu bình quân|trung bình mỗi đơn.*doanh thu|doanh thu.*trung bình mỗi đơn)\b", q)
        )
        is_avg_order_qty_query = bool(
            re.search(r"\b(số lượng.*trung bình mỗi đơn|số lượng bán.*trung bình|trung bình mỗi đơn.*số lượng|bán ra trung bình mỗi đơn)\b", q)
        )

        # Distinct product count
        is_distinct_product_query = bool(
            re.search(r"\b(bao nhiêu mặt hàng khác nhau|mấy mặt hàng khác nhau|số mặt hàng khác nhau|bao nhiêu sản phẩm khác nhau)\b", q)
        )

        # Revenue ranking vs Quantity ranking
        is_revenue_ranking = bool(
            re.search(r"\b(thu về nhiều tiền nhất|mang về nhiều tiền nhất|mang lại nhiều tiền nhất|mang lại nhìu tiền nhất|doanh thu cao nhất|doanh thu lớn nhất|doanh số cao nhất|doanh số lớn nhất|thu tiền nhiều nhất|đóng góp doanh thu lớn nhất)\b", q)
            or (re.search(r"\b(mặt hàng|sản phẩm|thuốc|món|hàng|sp)\b", q) and re.search(r"\b(doanh thu|doanh số|nhiều tiền|nhìu tiền)\b", q) and re.search(r"\b(nhất|cao nhất|lớn nhất)\b", q))
        )
        is_revenue_lowest = bool(
            re.search(r"\b(doanh thu thấp nhất|thu về ít tiền nhất|nguồn thu kém nhất|doanh số thấp nhất)\b", q)
        )

        is_quantity_ranking = bool(
            re.search(r"\b(bán chạy nhất|bán nhiều nhất|tiêu thụ nhiều nhất|tiêu thụ lớn nhất|bán tốt nhất|bán được nhiều nhất|bán dc nhiều nhất|chạy nhất)\b", q)
            or (re.search(r"\b(số lượng bán|số lượng tiêu thụ|số lượng)\b", q) and re.search(r"\b(lớn nhất|cao nhất|nhiều nhất)\b", q))
            or (re.search(r"\b(mặt hàng|sản phẩm|thuốc|món|hàng|sp)\b", q) and re.search(r"\b(nhiều nhất|chạy nhất|ít nhất|ít người mua|nhiều người mua|ưa chuộng nhất)\b", q) and not is_revenue_ranking)
        ) and not is_revenue_ranking

        is_lowest_ranking = bool(
            re.search(r"\b(bán ế nhất|bán ít nhất|bán chậm nhất|lượng bán thấp nhất|lượng bán nhỏ nhất|tiêu thụ ít nhất|số lượng bán nhỏ nhất|ít người mua|ít khách mua|ít ai mua|ít người mua nhất|ít khách mua nhất|mua ít nhất|người mua ít nhất|khách mua ít nhất|ít được mua nhất)\b", q)
            or (re.search(r"\b(sản phẩm|mặt hàng|thuốc|món|hàng|sp)\b", q) and re.search(r"\b(ít|kém|thấp|ế)\b", q) and re.search(r"\b(nhất|nhứt|mua|bán)\b", q))
        ) or is_revenue_lowest

        # Check "bán được bao nhiêu"
        has_unit_word = bool(re.search(r"\b(cái|hộp|vỉ|ly|chai|bịch|gói|sản phẩm|sp|món|chiếc|máy|đơn|lon|bộ|đôi|cuộn|thùng|cây)\b", q))
        is_ban_duoc_bao_nhieu = bool(re.search(r"\b(bán được bao nhiêu|bán được nhiêu|bán dc bn|bán dc bao nhiêu|bán ra bao nhiêu|bán ra dc bao nhiêu|bán ra bnhiu)\b", q))
        is_asking_money = bool(re.search(r"\b(tiền|doanh thu|doanh số|thu được)\b", q))

        is_revenue_query = bool(
            re.search(r"\b(doanh thu|doanh số|bao nhiêu tiền|nhiêu tiền|tổng tiền|tổng số tiền|thu được bao nhiêu tiền|trị giá bao nhiêu)\b", q)
            or (is_ban_duoc_bao_nhieu and not has_unit_word and (is_asking_money or bool(re.search(r"\b(bao nhiêu rồi|nhiêu rồi|bn rùi|bn ròi)\b", q))))
        ) or is_revenue_ranking or is_revenue_lowest

        is_quantity_query = bool(
            re.search(r"\b(tổng số lượng|số lượng bán|tổng sản lượng|sản lượng|bao nhiêu cái|bao nhiêu ly|bao nhiêu hộp|bao nhiêu vỉ|bao nhiêu món|bao nhiêu sản phẩm|bao nhiêu chiếc|bao nhiêu máy|số lượng.*bán|bán ra.*số lượng)\b", q)
            or re.search(r"\b(có\s+)?(bao nhiêu|mấy)\s+(?:máy|máy mới|máy cũ|chiếc|cái|ly|hộp|vỉ|món|sản phẩm|đơn|chai|lon|bịch|gói|bộ|đôi|cuộn|thùng|cây)\b", q)
            or re.search(r"\b(?:bán|báng|tiêu thụ)\s+(?:ra\s+|được\s+|đượt\s+)?(?:bao nhiêu|bnhiu|mấy)\s*(?:máy|máy mới|máy cũ|chiếc|cái|ly|hộp|vỉ|món|sản phẩm|chai|lon|bịch|gói|bộ|đôi|cuộn|thùng|cây)?\b", q)
            or (is_ban_duoc_bao_nhieu and (has_unit_word or not (is_asking_money or bool(re.search(r"\b(bao nhiêu rồi|nhiêu rồi|bn rùi|bn rồi)\b", q)))))
        ) or is_quantity_ranking or (is_lowest_ranking and not is_revenue_lowest)

        # Category and custom metric filters
        category_filter = None
        if re.search(r"\b(nhóm máy mới|máy mới|may moi|nhom may moi)\b", q):
            category_filter = "máy mới"
        elif re.search(r"\b(nhóm máy cũ|máy cũ|may cu|nhom may cu|điện thoại cũ|dien thoai cu)\b", q):
            category_filter = "máy cũ"
        elif re.search(r"\b(nhóm phụ kiện|phụ kiện|phu kien|nhom phu kien)\b", q):
            category_filter = "phụ kiện"
        elif re.search(r"\b(điện thoại|chiếc điện thoại|mấy máy.*không kể phụ kiện|cả máy mới.*máy cũ|gộp cả máy mới)\b", q):
            category_filter = "máy"
        elif re.search(r"\b(thuốc kê đơn|thuoc ke don)\b", q):
            category_filter = "thuốc kê đơn"

        metric_target = None
        if re.search(r"\b(thu máy cũ|thu may cu|máy cũ trừ vào|may cu tru vao)\b", q):
            metric_target = "thu_may_cu"
        elif re.search(r"\b(khách phải trả|khach phai tra|khách trả|khach tra|khách phãi trả)\b", q):
            metric_target = "khach_tra"
        elif re.search(r"\b(tiền bớt|tiền giảm|bớt được|chiết khấu)\b", q):
            metric_target = "bot"

        # Edge checks
        is_zero_value_query = bool(re.search(r"\b(bằng 0|bằng 0 đồng|0 đồng)\b", q))
        is_negative_value_query = bool(re.search(r"\b(tiền âm|số tiền âm|âm)\b", q))
        is_success_rate_query = bool(re.search(r"\b(thành công)\b", q) and re.search(r"\b(tỷ lệ|phần trăm)\b", q))
        is_canceled_revenue_query = bool(re.search(r"\b(tổng tiền.*bị hủy|tiền bán.*bị hủy|doanh thu.*bị hủy)\b", q))
        is_special_char_query = bool(re.search(r"\b(ký tự đặc biệt)\b", q))

        # Extract specific entities if mentioned
        has_specific_product = None
        for p_kw in [
            "panadol", "berberin", "khẩu trang", "máy đo huyết áp", "sp_a", "sp_b", "sp_c",
            "xiaomi redmi note 14", "xiaomi redmi 14c", "redmi note 14", "redmi note 12",
            "samsung galaxy a56", "galaxy a56", "iphone 16 pro max", "iphone 15", "iphone 11",
            "cốc sạc nhanh 20w", "kệ điện thoại", "thẻ nhớ microsd", "thẻ nhớ 64g",
            "tiger lon", "tiger", "heineken", "xi măng hà tiên", "xi măng insee",
            "costar omega 3", "gạch ống", "cà phê sữa", "trà đào cam sả", "cà phê đen"
        ]:
            if p_kw in q:
                has_specific_product = p_kw
                break

        # Date & Month selection queries (AnswerType.DATE)
        is_which_day_query = bool(re.search(r"\b(ngày nào|ngay nao|hạn dùng ngày nào|hạn sử dụng ngày nào|vào ngày nào)\b", q))
        is_which_month_query = bool(re.search(r"\b(tháng nào|thang nao|vào tháng nào|trong tháng nào|tháng mô|thang mo)\b", q)) and not is_which_day_query
        if is_which_day_query or is_which_month_query:
            is_revenue_ranking = False
            is_quantity_ranking = False
            is_lowest_ranking = False

        from datamate.temporal.resolver import TemporalResolver
        candidate_months = TemporalResolver.extract_candidate_months(q)

        # Consecutive Growth boolean query (e.g. Doanh thu 3 tháng có tăng liên tục không?)
        is_consecutive_growth_query = bool(
            re.search(r"\b(tăng liên tục|tang lien tuc|luôn cao hơn tháng trước|luon cao hon thang truoc|tháng sau.*cao hơn tháng trước|thang sau.*cao hon thang truoc)\b", q)
        ) and bool(re.search(r"\b(không|khong|ko|k|nhỉ|hả|\?)\b", q))

        # Cancellation rate percent query (Rule 18: Tỉ lệ đơn huỷ trong kỳ)
        is_cancellation_rate_query = bool(
            re.search(r"\b(tỉ lệ.*huỷ|ti le.*huy|tỉ lệ.*hủy|ti le.*huy|phần trăm.*huỷ|phan tram.*huy|bao nhiêu %.*đơn.*hủy|bao nhieu %.*don.*huy|bn %.*đơn.*hủy|% đơn bị huỷ|% don bi huy)\b", q)
        )

        # Table query (e.g. Bảng khách nợ kèm số tiền còn nợ)
        is_table_query = bool(re.search(r"\b(bảng|kèm số tiền|kèm số nợ|mỗi người còn nợ bao nhiêu|mỗi người.*nợ bao nhiêu|mỗi người.*bao nhiêu)\b", q))

        if is_quantity_ranking or is_revenue_ranking or is_lowest_ranking or is_which_day_query or is_which_month_query:
            has_specific_product = None
        elif not has_specific_product:
            # Check for products in quotes
            quote_m = re.search(r"['\"]([^'\"]{3,40})['\"]", raw)
            if quote_m:
                has_specific_product = quote_m.group(1).strip()
            else:
                # Check for explicit brand & model patterns (e.g. iPhone 16, Samsung A56, Xiaomi Note 14)
                brand_m = re.search(r"\b(iPhone\s+[\w\s\-\+]+|Samsung\s+[\w\s\-\+]+|Xiaomi\s+[\w\s\-\+]+|Redmi\s+[\w\s\-\+]+|OPPO\s+[\w\s\-\+]+|vivo\s+[\w\s\-\+]+|Tiger\s+[\w\s]+|Heineken\s+[\w\s]+|Xi măng\s+[\w\s\-]+)\b", raw, re.IGNORECASE)
                if brand_m:
                    cand = brand_m.group(1).strip()
                    if len(cand) >= 4 and not any(k in cand.lower() for k in ["bao nhieu", "bnhiu", "duoc", "khong"]):
                        has_specific_product = cand

        order_match = re.search(r"\b(hd\d+|dh\d+|ord\d+)\b", q)
        has_specific_order = order_match.group(1).upper() if order_match else None

        has_specific_customer = None
        if not ("trạm y tế và phòng khám" in q or "phòng khám và trạm y tế" in q):
            for c_kw in ["bs hùng", "bác sĩ hùng", "bs minh", "trạm y tế"]:
                if c_kw in q:
                    has_specific_customer = c_kw
                    break

        # Step 5: Clean query by stripping polite fluff and business prefixes
        # Note: Avoid matching 'hàng' when part of 'khách hàng', 'cửa hàng', 'đơn hàng', 'giao hàng', 'ngân hàng'
        q_no_common_hang = re.sub(r"\b(khách hàng|cửa hàng|đơn hàng|giao hàng|ngân hàng|mua hàng|bán hàng)\b", " ", q)
        is_asking_for_product = bool(
            re.search(r"\b(sản phẩm|mặt hàng|thuốc|món|hàng|sp|dịch vụ|loại hàng|hàng hóa|mặt hàng nào|sản phẩm nào|thuốc nào|món nào|hàng nào|sp nào)\b", q_no_common_hang)
        )

        is_customer_query = (
            bool(
                re.search(r"\b(khách nào|khách hàng nào|ai mua|ai là khách|khách sộp|khách chi tiêu|khách quen|khách vip|khách mua nhiều|khách hay đổi ý|top.*khách|khách trung thành|khách.*nhiều đơn|khách.*nhiều tiền)\b", q)
                or (re.search(r"\b(ai|người nào|khách nào|khách hàng nào)\b", q) and re.search(r"\b(mua|chi tiêu|đặt đơn|sộp|đóng góp)\b", q))
            )
            and not is_asking_for_product
        )

        # Extract top_k if specified (e.g. top 3, 5 mặt hàng, top 5 khách hàng)
        top_k = None
        k_match = re.search(r"(?<![\/\-\d])(?:top\s*(\d+)|(\d+)\s+(?:mặt hàng|sản phẩm|sp|hàng|khách|món|khách hàng|nhân viên))\b", q)
        if k_match:
            k_val = int(k_match.group(1) or k_match.group(2))
            if 1 < k_val <= 20 and k_val not in (24, 25, 26, 27):
                top_k = k_val


        clean = q
        for pat in cls.FLUFF_PATTERNS:
            clean = re.sub(pat, " ", clean, flags=re.IGNORECASE)

        for pat in cls.BUSINESS_REFERENCES:
            clean = re.sub(pat, " ", clean, flags=re.IGNORECASE)

        clean = re.sub(r"\s+", " ", clean).strip()
        tokens = clean.split()

        return NormalizedQueryInfo(
            original_query=raw,
            clean_query=clean,
            tokens=tokens,
            is_why_causal=is_why_causal,
            is_future=is_future,
            is_ambiguous_time=is_ambiguous_time,
            is_subjective=is_subjective,
            is_quantity_query=is_quantity_query,
            is_revenue_query=is_revenue_query,
            is_revenue_ranking=is_revenue_ranking,
            is_quantity_ranking=is_quantity_ranking,
            is_profit_cost_query=is_profit_cost_query,
            is_expiration_query=is_expiration_query,
            is_stock_query=is_stock_query,
            is_order_count_query=is_order_count_query,
            is_order_max_query=is_order_max_query,
            is_order_min_query=is_order_min_query,
            is_avg_order_revenue_query=is_avg_order_revenue_query,
            is_avg_order_qty_query=is_avg_order_qty_query,
            is_debt_query=is_debt_query,
            is_debt_amount_query=is_debt_amount_query,
            is_debt_count_query=is_debt_count_query,
            is_debt_max_query=is_debt_max_query,
            is_debt_min_query=is_debt_min_query,
            is_debt_customer_query=is_debt_customer_query,
            is_debt_duration_query=is_debt_duration_query,
            is_debt_highest=is_debt_highest,
            debt_above=debt_above,
            debt_below=debt_below,
            is_distinct_product_query=is_distinct_product_query,
            is_unsold_query=is_unsold_query,
            is_customer_query=is_customer_query,
            is_customer_loyalty_query=is_customer_loyalty_query,
            is_employee_query=is_employee_query,
            is_cancellation_query=is_cancellation_query,
            is_lowest_ranking=is_lowest_ranking,
            is_zero_value_query=is_zero_value_query,
            is_negative_value_query=is_negative_value_query,
            is_success_rate_query=is_success_rate_query,
            is_canceled_revenue_query=is_canceled_revenue_query,
            is_special_char_query=is_special_char_query,
            has_specific_product=has_specific_product,
            has_specific_order=has_specific_order,
            has_specific_customer=has_specific_customer,
            top_k=top_k,
            is_which_day_query=is_which_day_query,
            is_which_month_query=is_which_month_query,
            is_consecutive_growth_query=is_consecutive_growth_query,
            is_cancellation_rate_query=is_cancellation_rate_query,
            is_table_query=is_table_query,
            category_filter=category_filter,
            metric_target=metric_target,
            candidate_months=candidate_months,
        )
