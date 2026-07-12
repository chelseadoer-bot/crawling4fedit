"""CSV 컬럼 명세 — 표준 26컬럼 스키마"""

import re
from datetime import datetime

# ── 통화 감지 및 포맷 ─────────────────────────────────────────────────────────
_CURRENCY_SYMBOLS = {
    "KRW": "₩", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
}
_SYMBOL_TO_CURRENCY = {"₩": "KRW", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
_CURRENCY_KW = {
    "krw": "KRW", "won": "KRW", "원": "KRW",
    "usd": "USD", "dollar": "USD",
    "eur": "EUR", "euro": "EUR",
    "gbp": "GBP", "pound": "GBP",
    "jpy": "JPY", "yen": "JPY", "엔": "JPY",
}


def detect_currency(raw: str) -> str:
    """가격 문자열에서 통화 코드 감지. 기본값 KRW."""
    if not raw:
        return "KRW"
    s = raw.strip()
    if s and s[0] in _SYMBOL_TO_CURRENCY:
        return _SYMBOL_TO_CURRENCY[s[0]]
    sl = s.lower()
    for kw, code in _CURRENCY_KW.items():
        if kw in sl:
            return code
    return "KRW"


def format_price(raw, currency: str = "KRW") -> str:
    """가격 → 통화 기호 + 천단위 구분 (예: ₩89,900 / $89.90 / ¥9,900).
    raw가 이미 기호를 포함하면 통화를 재감지해서 재포맷."""
    if raw is None or raw == "":
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    # 기호 포함 입력이면 통화 재감지
    detected = detect_currency(s)
    if detected != "KRW" or s[0] in _SYMBOL_TO_CURRENCY:
        currency = detected
    sym = _CURRENCY_SYMBOLS.get(currency, "₩")
    digits = re.sub(r"[^\d.]", "", s)
    if not digits:
        return s
    try:
        # 소수점 포함 여부
        if "." in digits:
            amount = float(digits)
            return f"{sym}{amount:,.2f}"
        else:
            return f"{sym}{int(digits):,}"
    except ValueError:
        return s

# ── SIMPLE 컬럼 (출력 순서 고정) ─────────────────────────────────────────────
# 필수/플랫폼 필드를 앞에 배치하고, 값이 있는 부가 데이터 컬럼은 뒤에 유지한다.
SIMPLE_COLUMNS = [
    # [플랫폼]
    "platform",
    "is_ranking",
    "rank",
    "brand",
    # [필수]
    "main_category",
    "category",
    "gender",
    "product_name",
    "product_detail_url",
    "thumbnail",
    "regular_price",
    "current_price",
    "discount_rate",
    "crawled_at",
    # [부가 데이터]
    "color",
    "material",
    "details",
    "rating",
    "reviews",
    "manufacture_date",
    "reorder",
]

# 한글 레이블 (UI 헤더)
SIMPLE_COLUMN_LABELS = {
    "platform":           "플랫폼",
    "is_ranking":         "랭킹여부",
    "rank":               "순위",
    "brand":              "브랜드",
    "main_category":      "메인카테고리",
    "category":           "카테고리",
    "gender":             "성별",
    "product_name":       "상품명",
    "product_detail_url": "상품링크",
    "thumbnail":          "이미지",
    "regular_price":      "정상가",
    "current_price":      "판매가",
    "discount_rate":      "할인율",
    "crawled_at":         "수집일",
    "color":              "컬러",
    "material":           "소재",
    "details":            "상세설명",
    "rating":             "평점",
    "reviews":            "리뷰수",
    "manufacture_date":   "제조일",
    "reorder":            "재입고차수",
}

# ── CSV 출력 컬럼 (파일 저장용) ──────────────────────────────────────────────
STANDARD_COLUMNS = [
    "brand",
    "product_name",
    "category",
    "gender",
    "regular_price",
    "current_price",
    "discount_rate",
    "color_text",
    "color_chip",
    "color_classification_url",
    "front_images_url",
    "material",
    "details",
    "rating",
    "reviews",
    "product_detail_url",
    # 확장 속성
    "sizes_available",
    "fit",
    "length",
    "sleeve_length",
    "style",
    "lining",
    "thickness",
    "season",
    "transparency",
    "elasticity",
    "crawled_at",
    "source_site",
]

# ── alias → 표준 컬럼명 역방향 매핑 ─────────────────────────────────────────
ALIAS_MAP: dict[str, list[str]] = {
    "product_name":               ["product_name", "제품명", "상품명", "name", "상품이름"],
    "category":                   ["category", "카테고리", "category_name", "category_large", "category_small"],
    "color_text":                 ["color_text", "색상", "색상명", "color", "colors", "color(text)", "colour"],
    "color_chip":                 ["color_chip", "색상칩"],
    "color_classification_url":   ["color_classification_url", "색상구분이미지", "색상분류이미지URL", "색상분류이미지url", "색상분류이미지"],
    "front_images_url":           ["front_images_url", "대표이미지", "대표이미지URL", "대표이미지url", "이미지", "이미지URL", "이미지url", "image", "image_url"],
    "regular_price":              ["regular_price", "정상가", "price_original"],
    "current_price":              ["current_price", "할인가", "판매가", "가격", "price_sale", "price"],
    "discount_rate":              ["discount_rate", "할인율"],
    "material":                   ["material", "소재"],
    "details":                    ["details", "상세설명", "설명", "상세", "description"],
    "rating":                     ["rating", "평점"],
    "reviews":                    ["reviews", "리뷰수", "리뷰", "후기수"],
    "product_detail_url":         ["product_detail_url", "상세페이지url", "상세페이지URL", "상세url", "detail_url", "detail_page_url", "product_url"],
    "gender":                     ["gender", "성별"],
    "brand":                      ["brand", "브랜드"],
    "sizes_available":            ["sizes_available", "사이즈", "size"],
    "fit":                        ["fit", "핏"],
    "length":                     ["length", "기장"],
    "sleeve_length":              ["sleeve_length", "소매길이", "소매"],
    "style":                      ["style", "스타일"],
    "lining":                     ["lining", "안감"],
    "thickness":                  ["thickness", "두께감", "두께"],
    "season":                     ["season", "계절감", "계절"],
    "transparency":               ["transparency", "비침"],
    "elasticity":                 ["elasticity", "신축성"],
}

# alias → standard 역방향 딕셔너리 (빠른 조회)
_ALIAS_TO_STANDARD: dict[str, str] = {}
for _std, _aliases in ALIAS_MAP.items():
    for _a in _aliases:
        _ALIAS_TO_STANDARD[_a.lower()] = _std


def normalize_column_name(col: str) -> str:
    """어떤 컬럼명이든 표준 스키마 이름으로 변환"""
    return _ALIAS_TO_STANDARD.get(col.lower(), col)


def normalize_row(row: dict) -> dict:
    """row의 컬럼명을 표준화하고 빈 행 형식으로 반환"""
    result = empty_row()
    for k, v in row.items():
        std = normalize_column_name(k)
        if std in result:
            result[std] = _clean(v)
    return result


def _clean(v) -> str:
    """null/None/nan 을 빈 문자열로 변환"""
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("none", "null", "nan", "n/a", "-"):
        return ""
    return s


_GENDER_KO = {
    "women": "여성", "woman": "여성", "female": "여성", "ladies": "여성",
    "men": "남성", "man": "남성", "male": "남성", "mens": "남성",
    "kids": "공용", "unisex": "공용", "공용": "공용",
    "여성": "여성", "남성": "남성",
}


def normalize_gender(v: str) -> str:
    if not v:
        return ""
    return _GENDER_KO.get(v.strip().lower(), v.strip())


def empty_row() -> dict:
    return {col: "" for col in SIMPLE_COLUMNS}


def today_yymmdd() -> str:
    """크롤링 날짜 YYMMDD (예: 260617)"""
    return datetime.now().strftime("%y%m%d")


def now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


# ── 가격/할인율 정규화 ───────────────────────────────────────────────────────

def _to_int_price(raw) -> int | None:
    """가격 문자열(₩89,900 / 89900 / 89.90) → 정수. 실패 시 None."""
    if raw is None:
        return None
    s = re.sub(r"[^\d.]", "", str(raw))
    if not s:
        return None
    try:
        return int(round(float(s))) if "." in s else int(s)
    except ValueError:
        return None


def normalize_prices(regular, current, discount, currency: str = "KRW") -> tuple[str, str, str]:
    """가격 3종을 일관 규칙으로 정규화해서 (regular, current, discount_rate) 반환.

    규칙:
    - regular_price: 항상 정가(원가). 가격이 하나라도 있으면 채운다.
    - current_price: 할인 중일 때만 채운다 (할인 없으면 빈값).
    - discount_rate: 할인 중일 때만 regular/current 비교로 계산한 정수(%).
    - 정가가 없고 할인율만 있으면 current/할인율로 정가를 역산해 복원한다.
    """
    r = _to_int_price(regular)
    c = _to_int_price(current)
    d = _to_int_price(discount)  # 할인율(%) 정수

    # 정가가 없거나 current 이하인데 할인율이 있으면 정가 역산
    if c is not None and d and d > 0 and (r is None or r <= c):
        try:
            r = int(round(c / (1 - d / 100)))
        except ZeroDivisionError:
            r = None

    if r is not None and c is not None and c < r:
        # 진짜 할인
        reg_out, cur_out = r, c
        disc_out = round((r - c) / r * 100)
    else:
        # 할인 아님 → 정가만 채우고 current/할인율 비움
        reg_out = r if r is not None else c
        cur_out = None
        disc_out = None

    def _fmt(v):
        return format_price(v, currency) if v is not None else ""

    return _fmt(reg_out), _fmt(cur_out), (str(disc_out) if disc_out else "")


# ── 성별/플랫폼 추론 ─────────────────────────────────────────────────────────

# 멀티브랜드 플랫폼 크롤러 → 표기 플랫폼명. (그 외 단일 브랜드 사이트는 platform 비움)
PLATFORM_DISPLAY = {
    "29cm": "29CM",
    "musinsa": "무신사",
    "wconcept": "W컨셉",
}


def infer_gender(*texts: str) -> str:
    """URL/그룹/카테고리 등 힌트 텍스트에서 성별 추론. 상품명은 오탐 우려로 제외."""
    blob = " ".join(t for t in texts if t)
    if "여성" in blob:
        return "여성"
    if "남성" in blob:
        return "남성"
    if "공용" in blob or "유니섹스" in blob:
        return "공용"
    low = blob.lower()
    if re.search(r"wom[ae]n|female|ladies|girl|gf=f|womenswear|womanswear", low):
        return "여성"
    if re.search(r"(?:^|[^ow])men|/men|menswear|gf=m|\bmale\b", low):
        return "남성"
    if re.search(r"unisex|kids|baby", low):
        return "공용"
    return ""


def normalize_platform(crawler_id: str | None, current: str = "") -> str:
    """멀티브랜드 플랫폼이면 표기명, 단일 브랜드 사이트면 빈값."""
    if crawler_id and crawler_id in PLATFORM_DISPLAY:
        return PLATFORM_DISPLAY[crawler_id]
    return ""


_PLACEHOLDER_NAME = re.compile(r"^(카테고리\s*\d+|기타)$")

# ── 상품명 정리 / 색상·리오더 추출 ──────────────────────────────────────────
_COLOR_WORDS = [
    "라이트그레이", "스카이블루", "라이트블루", "오프화이트", "다크그레이", "다크브라운", "라이트베이지",
    "블랙", "화이트", "아이보리", "크림", "오트밀", "베이지", "샌드", "그레이", "챠콜", "차콜",
    "네이비", "블루", "데님", "연청", "중청", "진청", "흑청", "인디고", "민트", "그린", "카키",
    "올리브", "머스타드", "옐로우", "레몬", "오렌지", "코랄", "피치", "핑크", "로즈", "레드",
    "버건디", "와인", "브라운", "카멜", "모카", "초코", "퍼플", "라벤더", "바이올렛", "실버",
    "골드", "멀티", "소라",
    "light grey", "light gray", "off white", "dark grey", "dark gray", "dark brown", "sky blue",
    "black", "white", "ivory", "cream", "oatmeal", "beige", "sand", "gray", "grey", "charcoal",
    "navy", "blue", "denim", "indigo", "mint", "green", "khaki", "olive", "mustard", "yellow",
    "lemon", "orange", "coral", "peach", "pink", "rose", "red", "burgundy", "wine", "brown",
    "camel", "mocha", "choco", "purple", "lavender", "violet", "silver", "gold", "multi", "ecru",
]
_COLOR_ALT = "|".join(sorted(map(re.escape, _COLOR_WORDS), key=len, reverse=True))
_CMOD = r"(?:라이트|다크|딥|연|진|light|dark|deep|pale|d\.|l\.)?\s*"
_COLOR_UNIT = r"(?:%s(?:%s))" % (_CMOD, _COLOR_ALT)
_COLOR_ONLY = re.compile(r"^%s(?:\s*[&/,+]?\s*%s)*$" % (_COLOR_UNIT, _COLOR_UNIT), re.I)
_TRAIL_COLOR = re.compile(r"[\s,\-_/]+(%s(?:\s*[&/,+]?\s*%s)?)\s*$" % (_COLOR_UNIT, _COLOR_UNIT), re.I)
_BRACKET = re.compile(r"[\[【][^\]】]*[\]】]")
_TRAIL_PAREN = re.compile(r"\s*\(([^()]*)\)\s*$")
_NCOLORS = re.compile(r"^\d+\s*(?:colors?|색상?|컬러)$", re.I)
_CODE_TOKEN = r"(?=[A-Z0-9\-]*\d)[A-Z][A-Z0-9\-]{4,}"
_PROD_CODE = re.compile(r"[\s_\-/]+" + _CODE_TOKEN + r"\s*$")
_CODE_ONLY = re.compile(r"^" + _CODE_TOKEN + r"$")
_NCOLORS_SUFFIX = re.compile(r"[\s_\-/]*\d+\s*colors?\s*$", re.I)
_HASHTAGS = re.compile(r"(?:\s*#[^\s#]+)+\s*$")
_REORDER_N = re.compile(r"(\d+)\s*(?:차|th|nd|rd|st)?\s*(?:리오더|re-?order|재입고)", re.I)
_REORDER_ANY = re.compile(r"리오더|re-?order", re.I)
_REORDER_PHRASE = re.compile(r"\d*\s*차?\s*(?:리오더|re-?order)\s*[-_/]?\s*", re.I)


def clean_product_name(name: str, color: str = "") -> tuple[str, str, str]:
    """상품명에서 노이즈([기획전]/상품코드/색상 접미어) 제거.
    반환: (정리된 상품명, 색상(기존 우선), 리오더 차수)"""
    if not name:
        return name, color, ""
    orig = name
    reorder = ""
    m = _REORDER_N.search(name)
    if m:
        reorder = m.group(1)
    elif _REORDER_ANY.search(name):
        reorder = "1"

    color_cand = ""
    # 대괄호 그룹: 색상이면 회수, 그 외([단독]/[7/16 예약]/[코드]) 제거
    for content in _BRACKET.findall(name):
        inner = content[1:-1].strip()
        if not color_cand and _COLOR_ONLY.match(inner):
            color_cand = inner
    name = _BRACKET.sub(" ", name)
    name = _REORDER_PHRASE.sub(" ", name)
    name = _HASHTAGS.sub("", name)
    name = _NCOLORS_SUFFIX.sub("", name)
    name = _PROD_CODE.sub("", name)

    # 꼬리 괄호: 색상/N colors/상품코드면 제거 (최대 3회)
    for _ in range(3):
        m = _TRAIL_PAREN.search(name)
        if not m:
            break
        inner = m.group(1).strip()
        if _COLOR_ONLY.match(inner):
            if not color_cand:
                color_cand = inner
            name = name[: m.start()].rstrip()
        elif _NCOLORS.match(inner) or _CODE_ONLY.match(inner) or not inner:
            name = name[: m.start()].rstrip()
        else:
            break

    # 꼬리 색상 (- 블랙 / _IVORY 등, 최대 2회)
    for _ in range(2):
        m = _TRAIL_COLOR.search(name)
        if not m:
            break
        if not color_cand:
            color_cand = m.group(1).strip()
        name = name[: m.start()].rstrip()

    name = _PROD_CODE.sub("", name)
    name = re.sub(r"\s{2,}", " ", name).strip(" -_/,.·")

    if len(name) < 4:  # 과도 삭제 방지
        name = re.sub(r"\s{2,}", " ", _BRACKET.sub(" ", orig)).strip(" -_/,.")
        if len(name) < 2:
            name = orig.strip()
    return name, (color or color_cand), reorder


# ── 악세서리(가방/신발/잡화) 판별 ───────────────────────────────────────────
_ACC_STRONG = re.compile(
    r"키링|키홀더|폰케이스|에코백|발라클라바|밸라클라바|귀걸이|목걸이|팔찌|카드지갑|지갑|"
    r"헤어핀|헤어밴드|스크런치|볼캡|버킷햇|비니|선글라스|머리끈|양말|삭스|넥타이|보타이|"
    r"keyring|phone ?case|balaclava|necklace|earring|bracelet|wallet|socks",
    re.I,
)
_ACC_TAIL = re.compile(
    r"(?:^|[\s\]\)/_\-#])(가방|백팩|숄더백|토트백|크로스백|클러치|파우치|벨트|모자|캡|햇|메리제인|"
    r"슈즈|스니커즈|운동화|부츠|샌들|슬리퍼|뮬|로퍼|플랫|힐|스카프|머플러|장갑|"
    r"bag|backpack|belt|cap|hat|shoes?|sneakers?|boots?|sandals?|slippers?|mule|loafers?|"
    r"heels?|scarf|muffler|gloves?)\s*$",
    re.I,
)


def is_accessory(name: str, category: str = "") -> bool:
    text = f"{name}"
    if _ACC_STRONG.search(text) or _ACC_TAIL.search(text):
        return True
    cat = category or ""
    return bool(re.search(r"ACC|악세|액세|가방|신발|슈즈|주얼리|잡화", cat, re.I))


def finalize_row(
    row: dict,
    *,
    crawler_id: str | None = None,
    brand_id: str = "",
    default_url: str = "",
    group: str = "",
    name: str = "",
    default_gender: str = "",
    currency: str = "KRW",
) -> dict:
    """필수 스키마를 강제하는 행 후처리 (저장/마이그레이션 공통).

    - 가격/할인율 정규화
    - gender 비었으면 URL/그룹/카테고리 힌트로 보강
    - platform: 플랫폼 크롤러만 표기명, 단일 브랜드는 빈값
    - is_ranking 기본 false, rank는 랭킹일 때만 유지
    - main_category/category 둘 다 비면 브랜드명으로 보강
    - crawled_at 비면 오늘 날짜
    """
    reg, cur, disc = normalize_prices(
        row.get("regular_price"), row.get("current_price"), row.get("discount_rate"), currency
    )
    row["regular_price"], row["current_price"], row["discount_rate"] = reg, cur, disc

    # 상품명 정리 + 색상/리오더 추출
    nm, col, reorder = clean_product_name(_clean(row.get("product_name", "")), _clean(row.get("color", "")))
    row["product_name"] = nm
    row["color"] = col
    if not _clean(row.get("reorder", "")) and reorder:
        row["reorder"] = reorder

    # 리뷰/평점 0 → 빈값
    for f in ("reviews", "rating"):
        if _clean(row.get(f, "")) in ("0", "0.0", "0.00"):
            row[f] = ""

    # 카테고리 '여성/우먼' 접두 제거
    cat = _clean(row.get("category", ""))
    if cat:
        row["category"] = re.sub(r"^(여성|우먼|W)\s+", "", cat)

    gender = normalize_gender(_clean(row.get("gender", "")))
    if not gender:
        gender = infer_gender(
            brand_id, default_url, group, name,
            _clean(row.get("main_category", "")), _clean(row.get("category", "")),
        )
    if not gender and default_gender:
        gender = normalize_gender(default_gender)
    row["gender"] = gender

    row["platform"] = normalize_platform(crawler_id, _clean(row.get("platform", "")))

    is_ranking = _clean(row.get("is_ranking", "")).lower()
    row["is_ranking"] = "true" if is_ranking == "true" else "false"
    if row["is_ranking"] != "true":
        row["rank"] = ""

    if not _clean(row.get("main_category", "")) and not _clean(row.get("category", "")):
        nm = _clean(name)
        if nm and not _PLACEHOLDER_NAME.match(nm):
            row["category"] = nm

    if not _clean(row.get("crawled_at", "")):
        row["crawled_at"] = today_yymmdd()

    return row


def make_product_row(currency: str = "KRW", **kwargs) -> dict:
    """SIMPLE 컬럼 행 생성.
    - gender 한글 변환
    - 가격/할인율 정규화 (normalize_prices: 정가 항상, 판매가/할인율은 할인 시만)
    """
    row = empty_row()
    row["is_ranking"] = "false"
    for k, v in kwargs.items():
        if k in row:
            row[k] = _clean(v)
    if row["gender"]:
        row["gender"] = normalize_gender(row["gender"])

    row["regular_price"], row["current_price"], row["discount_rate"] = normalize_prices(
        row["regular_price"], row["current_price"], row["discount_rate"], currency
    )

    return row


def format_price_krw(price) -> str:
    return format_price(price, "KRW")
