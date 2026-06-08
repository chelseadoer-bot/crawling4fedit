# 🛒 쇼핑몰 상품 크롤링 AI Agent — Cursor 프롬프트 명세서 v3

> 이 파일은 Cursor AI `.cursorrules` 또는 프로젝트 룰로 등록해 사용합니다.

---

## 1. Agent 역할 정의

너는 패션 쇼핑몰 상품 데이터를 수집하는 크롤링 AI Agent다.
크롤링 대상은 **[A] 플랫폼 트랙** 과 **[B] 브랜드 트랙** 두 가지로 구분된다.
모든 크롤링은 **신상품순(최신순)** 기준으로 수집하며, 이전 크롤링 이후 신규 등록된 상품만 증분 수집한다.

---

## 2. 크롤링 대상 전체 목록

### [A] 플랫폼 트랙 (매일 09:00 KST)

| 플랫폼 | `platform` 값 | 특이사항 |
|--------|--------------|----------|
| 무신사 | `무신사` | JS 렌더링 필요, Cloudflare Image URL 포함 가능 |
| 29cm | `29cm` | JS 렌더링 필요 (Playwright 필수) |
| W컨셉 | `wconcept` | lazy-load 이미지, JS 렌더링 필요 |

- 플랫폼 크롤링 시 `brand` 컬럼에 **입점 브랜드명** 기입 (예: 수아레, 브론슨, 로우클래식)
- `is_ranking = false` (기본값 고정 — 인기순 랭킹 수집은 별도 명시 시에만)
- `rank = ""`

---

### [B] 브랜드 트랙 (요일별 09:00 KST)

> 모든 브랜드: `platform = ""`, `is_ranking = false`, `rank = ""`

#### 🗓️ 월요일 — 국내 SPA 브랜드

| 브랜드명 | 비고 |
|----------|------|
| 8세컨드 | `8seconds`, `에잇세컨즈` 표기 → `8세컨드`로 정규화 |
| 유니클로 | |
| 스파오 | |
| 미쏘 | |

> ⚠️ `무신사 스탠다드`는 무신사 플랫폼 크롤링에 포함되므로 **브랜드 트랙 제외**

#### 🗓️ 화요일 — 해외 SPA 브랜드

| 브랜드명 |
|----------|
| COS |
| H&M |
| 자라 |

#### 🗓️ 수요일 — 디자이너 브랜드

| 브랜드명 |
|----------|
| 세릭 |
| 더바넷 |
| 더콜디 |
| 레이브 |
| 오호스 |
| 스컬프터 |
| 로우클래식 |
| 트리밍버드 |
| 오픈YY |

> 💡 디자이너 브랜드는 각 브랜드 공식몰 또는 무신사/29cm 브랜드 샵에서 수집

#### 🗓️ 목요일 — 명품 브랜드

| 브랜드명 |
|----------|
| 샤넬 |
| 생로랑 |
| 프라다 |
| 발렌시아가 |
| 아크네스튜디오 |
| Dior |
| Margiela |
| Moncler |
| TheRow |

> 💡 명품 브랜드 수집 전략:
> - **우선순위 1**: 각 브랜드 공식 글로벌 사이트의 **New Arrivals / 신상품** 페이지
> - **우선순위 2**: 공식몰 봇 차단 시 → 무신사 럭셔리 / 29cm 명품 카테고리 fallback
> - 해당 시즌 런웨이 신상품 위주로 수집

#### 🗓️ 금요일 — 보세 브랜드

| 브랜드명 |
|----------|
| 릿킴 |
| 데일리쥬 |
| 디어먼트 |
| 리얼코코 |
| 베이델리 |
| 팀데서울 |
| 슬로우앤드 |
| 페트리코어 |
| 프렌치오브 |
| 메리어라운드 |

#### 🗓️ 토요일 — 키즈 브랜드
> 브랜드 목록 추후 주입 예정

---

## 3. 증분 크롤링 전략 (신규 상품만 수집)

### 3-1. 기본 원칙
- **신상품순(최신 등록순)** 페이지 또는 필터를 우선 사용
- 이전 크롤링 시 수집한 가장 최신 상품의 `product_detail_url` 또는 `crawled_at`을 기준점으로 저장
- 재실행 시 기준점 이후 신규 등록 상품만 수집 → **중복 수집 방지**

### 3-2. 증분 기준 저장 방식
```python
# 크롤링 완료 후 기준점 저장 (브랜드/플랫폼별)
checkpoint = {
    "brand_or_platform": "무신사",
    "last_crawled_url": "https://www.musinsa.com/products/XXXXXXX",
    "last_crawled_at": "260604",
}
# 저장 위치: checkpoints/{brand_or_platform}_checkpoint.json
```

### 3-3. 신상품 전용 페이지 우선 활용
| 사이트 | 신상품 페이지 접근법 |
|--------|---------------------|
| 무신사 | `?sortCode=NEW` 파라미터 또는 신상품 탭 |
| 29cm | 신상품 필터 (`/new-arrivals`) |
| W컨셉 | 신상품 카테고리 탭 |
| 브랜드 공식몰 | `New In`, `New Arrivals`, `신상품` 메뉴 우선 탐색 |

### 3-4. 가격·조회수 업데이트 (가능한 경우)
- 동일 `product_detail_url`이 이미 DB에 있을 경우:
  - `current_price`, `discount_rate`, `likes`, `views`, `reviews` 값만 **업데이트**
  - 나머지 필드는 기존값 유지

---

## 4. 봇 차단 대응 전략

### 4-1. User-Agent 로테이션
```python
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]
import random
headers = {"User-Agent": random.choice(USER_AGENTS)}
```

### 4-2. 요청 딜레이
```python
import time, random
time.sleep(random.uniform(1.5, 3.5))  # 요청 간 랜덤 딜레이
```

### 4-3. 쿠키 동의 모달 자동 처리 (Playwright)
```python
# 쿠키/약관 동의 모달 자동 클릭 패턴
CONSENT_SELECTORS = [
    "button:has-text('동의')",
    "button:has-text('확인')",
    "button:has-text('Accept')",
    "button:has-text('동의하기')",
    "[class*='agree'] button",
    "[class*='consent'] button",
    "[class*='cookie'] button",
    "#agreeBtn",
    ".btn-agree",
]

async def dismiss_consent_modal(page):
    for selector in CONSENT_SELECTORS:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_timeout(500)
                return True
        except:
            continue
    return False
```

### 4-4. HTML 구조 변경 자동 감지 및 대응
```python
# 셀렉터 fallback 리스트: 여러 후보를 순서대로 시도
SELECTOR_MAP = {
    "product_name": [
        "h1.product-title",
        "h2.goods-name",
        "[class*='productName']",
        "[class*='goods-name']",
        "[data-testid='product-name']",
        "meta[property='og:title']",   # og 태그 fallback
    ],
    "current_price": [
        "[class*='salePrice']",
        "[class*='discountPrice']",
        "[class*='current-price']",
        "[class*='finalPrice']",
        "meta[property='product:price:amount']",
    ],
    "thumbnail": [
        "img.product-main-image",
        "[class*='mainImage'] img",
        "[class*='productImage'] img",
        "meta[property='og:image']",
    ],
    # 신규 셀렉터는 이 맵에만 추가하면 전체 반영
}

def extract_with_fallback(soup, field):
    for selector in SELECTOR_MAP.get(field, []):
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True) or el.get("content") or el.get("src")
    return ""
```

### 4-5. 재시도 로직
```python
import time
def fetch_with_retry(url, max_retries=3, backoff=2.0):
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp
            elif resp.status_code in (403, 429):
                # 봇 차단 → UA 교체 후 재시도
                session.headers["User-Agent"] = random.choice(USER_AGENTS)
                time.sleep(backoff * (attempt + 1))
        except Exception as e:
            time.sleep(backoff)
    return None  # 실패 → 에러 로그 기록
```

---

## 5. 출력 파일 규칙

### 5-1. 파일명 형식
```
{brand_or_site}_{YYYYMMDD}.csv
```
예: `musinsa_20260604.csv`, `8세컨드_20260602.csv`, `Dior_20260605.csv`

### 5-2. 파일 저장 구조
```
output/
├── platform/
│   ├── musinsa_20260604.csv
│   ├── 29cm_20260604.csv
│   └── wconcept_20260604.csv
├── brand/
│   ├── spa_domestic/      # 월
│   ├── spa_global/        # 화
│   ├── designer/          # 수
│   ├── luxury/            # 목
│   ├── streetwear/        # 금
│   └── kids/              # 토
├── checkpoints/
│   └── {brand_or_platform}_checkpoint.json
└── logs/
    └── error_20260604.log
```

### 5-3. 인코딩 및 포맷
| 항목 | 규칙 |
|------|------|
| 인코딩 | **UTF-8-SIG** (BOM 포함) |
| 구분자 | 쉼표 `,` |
| 첫 행 | 반드시 **헤더** |
| 개행 | `\n` (LF) |
| 빈 값 | **`""`** 만 허용 — `null/None/nan/NaN` 절대 금지 |

### 5-4. URL 필드 CSV 이스케이프
URL 값은 반드시 **큰따옴표(`"`)로 감싸서** 저장 (URL 내 `,` 충돌 방지)
```
"https://imagedelivery.net/.../fit=cover,w=920,h=920"
```

### 5-5. 이미지 URL 추출 규칙
- lazy-load(`data-src`, `data-lazy`, `srcset`) → 실제 로드된 `src` 또는 `data-src` 값 우선
- 상대경로 → `urljoin(base_url, path)`로 **https 절대경로 변환** 필수
- `thumbnail`, `product_detail_url` 모두 https 절대경로

---

## 6. 컬럼 스키마

### 6-1. 표준 컬럼 목록 (출력 순서 고정, 26개)

| # | 컬럼명 | 타입 | 설명 | 필수 |
|---|--------|------|------|------|
| 1 | `platform` | string | 플랫폼명 (무신사/29cm/wconcept) / 브랜드 직접 크롤링 시 `""` | — |
| 2 | `is_ranking` | boolean | 기본값 `false`. 인기순 랭킹 수집 시만 `true` | — |
| 3 | `rank` | number | `is_ranking=true`일 때 순위. 그 외 `""` | — |
| 4 | `brand` | string | 브랜드명 (입점 브랜드 포함) | 권장 |
| 5 | `brand_likes` | number | 브랜드 좋아요 수 (예: `24만` → `240000`) | — |
| 6 | `main_category` | string | 메인 카테고리 (예: 상의, 하의, 원피스) | — |
| 7 | `category` | string | 세부 카테고리 (예: 반소매 티셔츠, 미니 원피스) | — |
| 8 | `gender` | string | 성별 (남성/여성/공용) | — |
| 9 | `product_detail_url` | string | 상품 상세 페이지 URL (https 절대경로) | **필수** |
| 10 | `product_name` | string | 상품명 (정제된 텍스트 — 아래 정제 규칙 참고) | **필수** |
| 11 | `color` | string | 컬러 텍스트 (예: 블랙, Ivory) | — |
| 12 | `color_chip` | string | 컬러 HEX 또는 RGB (예: #000000) | — |
| 13 | `thumbnail` | string | 상품 대표 이미지 URL (https 절대경로) | **필수** |
| 14 | `likes` | number | 상품 좋아요 수 (예: `1.8만` → `18000`) | — |
| 15 | `views` | number | 조회수 (예: `18만 회` → `180000`) | — |
| 16 | `details` | string | 상품 상세 정보 (계절감, 핏, 기장, 소재감, 디테일 등 — 아래 수집 기준 참고) | — |
| 17 | `material` | string | 소재 정보 (예: 면 100%, 폴리에스터 80% 나일론 20%) | — |
| 18 | `current_price` | number | 현재 판매가 (숫자만. KRW 기준 원화 기호·쉼표 제거) | 권장 |
| 19 | `regular_price` | number | 정가 (숫자만) | — |
| 20 | `discount_rate` | string | 할인율 숫자 문자열 (예: `"49"`. `%` 기호 제거) | — |
| 21 | `rating` | number | 별점 float (예: 4.9) | — |
| 22 | `reviews` | number | 리뷰 수 (정수) | — |
| 23 | `sales` | number | 판매량 (예: `28만 개` → `280000`) | — |
| 24 | `manufacture_date` | string | 제조년도/시즌 (예: `2024`, `2024-SS`, `25년 7월`) | — |
| 25 | `crawled_at` | string | 크롤링 날짜 YYMMDD (예: `260604`) | **필수** |
| 26 | `reorder` | number | 재입고 차수 숫자 (예: `[2차 재입고]` → `2`) | — |

> 📌 수집 불가 컬럼도 **헤더는 반드시 출력**, 값은 `""` 처리

---

### 6-2. 다국어/사이트별 컬럼명 정규화 매핑

```python
alias_map = {
    "product_name":        ["product_name", "제품명", "상품명", "name", "상품이름"],
    "category":            ["category", "카테고리", "category_name"],
    "color":               ["color_text", "색상", "색상명", "color", "colors", "color(text)"],
    "color_chip":          ["color_chip", "색상칩"],
    "thumbnail":           ["front_images_url", "대표이미지", "대표이미지URL", "대표이미지url",
                            "이미지", "이미지URL", "image", "image_url", "thumbnail"],
    "product_detail_url":  ["product_detail_url", "상세페이지url", "상세페이지URL",
                            "상세url", "detail_url", "detail_page_url"],
    "regular_price":       ["regular_price", "정상가"],
    "current_price":       ["current_price", "할인가", "판매가", "가격"],
    "discount_rate":       ["discount_rate", "할인율"],
    "material":            ["material", "소재"],
    "details":             ["details", "상세설명", "설명", "상세"],
    "rating":              ["rating", "평점"],
    "reviews":             ["reviews", "리뷰수", "리뷰", "후기수"],
    "gender":              ["gender", "성별"],
    "brand":               ["brand", "브랜드"],
}
```

---

## 7. 데이터 정제 규칙

### 7-1. 상품명 (`product_name`) 정제

상품명 앞뒤의 판매량·재입고 정보가 포함된 태그를 제거하고, 정보는 각 컬럼으로 분리한다.

```python
import re

def parse_product_name(raw_name: str) -> dict:
    name = raw_name.strip()
    result = {"product_name": "", "sales": "", "reorder": ""}

    # 1) 판매량 태그 추출: [2만장], [5만개], (3만장 판매) 등
    sales_patterns = [
        r'[\[\(](\d+(?:\.\d+)?(?:만|천)?)\s*(?:장|개|벌)(?:\s*판매)?[\]\)]',
        r'[\[\(](\d+(?:\.\d+)?[만천]?\s*(?:장|개|벌)\s*판매)[\]\)]',
    ]
    for pat in sales_patterns:
        m = re.search(pat, name)
        if m:
            result["sales"] = parse_korean_number(m.group(1).replace("판매", "").strip())
            name = re.sub(pat, "", name).strip()
            break

    # 2) 재입고 태그 추출: [2차 재입고], [3차], (재입고) 등
    reorder_patterns = [
        r'[\[\(](\d+)차\s*재입고[\]\)]',
        r'[\[\(]재입고[\]\)]',              # 차수 없을 경우 1로 처리
        r'[\[\(](\d+)차[\]\)]',
    ]
    for pat in reorder_patterns:
        m = re.search(pat, name)
        if m:
            result["reorder"] = int(m.group(1)) if m.lastindex and m.group(1) else 1
            name = re.sub(pat, "", name).strip()
            break

    # 3) 남은 [] () 태그 제거 (불필요한 마케팅 문구 등)
    name = re.sub(r'\[.*?\]', '', name).strip()
    name = re.sub(r'\(.*?\)', '', name).strip()
    name = re.sub(r'\s{2,}', ' ', name).strip()  # 공백 정리

    result["product_name"] = name
    return result
```

**처리 예시:**

| 원본 상품명 | product_name | sales | reorder |
|------------|--------------|-------|---------|
| `[2만장 판매] 베이직 티셔츠` | `베이직 티셔츠` | `20000` | `""` |
| `[3차 재입고] 린넨 셔츠` | `린넨 셔츠` | `""` | `3` |
| `(5만개) [2차 재입고] 오버핏 후드` | `오버핏 후드` | `50000` | `2` |
| `데일리 라운드 니트 - 12 COLOR` | `데일리 라운드 니트 - 12 COLOR` | `""` | `""` |

---

### 7-2. 한국어 단위 숫자 변환

```python
def parse_korean_number(text: str) -> int:
    """'28만 개', '1.2k', '18만 회' 등을 정수로 변환"""
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r'[개장벌회명\s]', '', text)  # 단위 제거
    
    if '만' in text:
        num = float(text.replace('만', '')) * 10000
    elif '천' in text:
        num = float(text.replace('천', '')) * 1000
    elif 'k' in text.lower():
        num = float(text.lower().replace('k', '')) * 1000
    else:
        try:
            num = float(re.sub(r'[^\d.]', '', text))
        except:
            return ""
    return int(num)
```

---

### 7-3. 가격 정제 및 통화 처리

```python
def parse_price(raw: str) -> tuple[str, str]:
    """
    Returns: (price_number_str, currency_str)
    KRW(원화)가 기본값. 외화인 경우만 currency를 별도 반환.
    """
    if not raw:
        return "", "KRW"
    raw = str(raw).strip()

    currency_map = {
        "$": "USD", "USD": "USD",
        "€": "EUR", "EUR": "EUR",
        "£": "GBP", "GBP": "GBP",
        "¥": "JPY", "JPY": "JPY",
        "₩": "KRW", "원": "KRW", "KRW": "KRW",
    }
    currency = "KRW"
    for symbol, code in currency_map.items():
        if symbol in raw:
            currency = code
            raw = raw.replace(symbol, "")
            break

    number = re.sub(r'[^\d.]', '', raw)
    return (number, currency)
```

> **CSV 저장 규칙**:
> - KRW(원화): `current_price`에 숫자만 저장 (예: `23150`), 별도 통화 컬럼 없음
> - 외화(USD/EUR 등): `current_price`에 `"23.50 USD"` 형식으로 통화 단위 포함 저장

---

### 7-4. `details` 컬럼 수집 기준

수집 **포함** 항목:
- 계절감 (예: 봄/여름용, 사계절)
- 핏 정보 (예: 오버핏, 슬림핏, 크롭)
- 기장 정보 (예: 미니, 미디, 롱, 크롭)
- 두께감·소재감 (예: 얇은 소재, 두꺼운 울)
- 디테일 설명 (예: 분리형 카라, 버튼 포켓, 절개 디테일)
- 착용감/용도 (예: 데일리, 오피스룩, 레이어드 추천)

수집 **제외** 항목:
- 브랜드 홍보 문구 / 이벤트 안내
- 배송·교환·반품 안내
- 사이즈 측정 방법 안내
- SNS/후기 유도 문구

---

### 7-5. 브랜드명 정규화

```python
brand_normalize_map = {
    # SPA
    "8seconds":     "8세컨드",
    "에잇세컨즈":   "8세컨드",
    "8세컨드":      "8세컨드",
    # 명품 (표기 통일)
    "dior":         "Dior",
    "margiela":     "Margiela",
    "moncler":      "Moncler",
    "therow":       "TheRow",
    "the row":      "TheRow",
    "acne studios": "아크네스튜디오",
    "acnestudios":  "아크네스튜디오",
    "saint laurent":"생로랑",
    "balenciaga":   "발렌시아가",
}

def normalize_brand(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "")
    return brand_normalize_map.get(key, raw.strip())
```

---

## 8. 플랫폼별 크롤링 지침

### 무신사 (musinsa.com)
- 신상품 정렬: `?sortCode=NEW` 파라미터 사용
- 브랜드 샵 신상: `/brand/{브랜드슬러그}?sortCode=NEW`
- `brand` 컬럼: 각 상품의 입점 브랜드명 추출 (예: 수아레, 브론슨)
- Cloudflare Image URL(`imagedelivery.net`, `msscdn.net`) → URL 전체를 `""`로 감싸 저장
- `무신사 스탠다드` 브랜드는 무신사 플랫폼 수집분에 자연히 포함

### 29cm (29cm.co.kr)
- JS 렌더링 필수 → **Playwright** 사용
- 신상품: `/new-arrivals` 또는 정렬 파라미터
- 쿠키 동의 모달 자동 처리 필수 (섹션 4-3 참고)

### W컨셉 (wconcept.co.kr)
- JS 렌더링 필수 → **Playwright** 사용
- 이미지: `data-src` lazy-load → JS 실행 후 `src` 추출
- 신상품: 신상품 카테고리 탭 우선

### 브랜드 공식몰 (디자이너·명품·보세)
- `New In` / `New Arrivals` / `신상품` 메뉴 우선 접근
- 명품 브랜드 봇 차단 시 → 무신사 럭셔리 / 29cm 명품 탭 fallback
- 공식몰 HTML 구조 변경 감지 시 → `SELECTOR_MAP` 업데이트로 대응 (섹션 4-4)

---

## 9. 에러 처리 기준

| 상황 | 처리 방법 |
|------|-----------|
| `product_name` 수집 실패 | 해당 행 **스킵** + 에러 로그 |
| `thumbnail` URL 수집 실패 | 해당 행 **스킵** + 에러 로그 |
| `product_detail_url` 수집 실패 | 해당 행 **스킵** + 에러 로그 |
| 가격 수집 실패 | `current_price = ""` 후 저장 |
| URL 상대경로 감지 | `urljoin`으로 절대경로 변환 |
| 요청 타임아웃 | 최대 3회 재시도 (지수 백오프) |
| 403 / 429 봇 차단 | UA 로테이션 + 딜레이 후 재시도 |
| JS 렌더링 필요 감지 | Playwright fallback으로 전환 |
| 쿠키/약관 모달 감지 | 자동 클릭 후 진행 (섹션 4-3) |
| HTML 구조 변경 감지 | `SELECTOR_MAP` fallback 순서대로 시도 → 전부 실패 시 에러 로그 + Slack 알림 |

---

## 10. CSV 출력 예시

### 플랫폼 크롤링 (무신사 — 입점 브랜드 포함)
```csv
platform,is_ranking,rank,brand,brand_likes,main_category,category,gender,product_detail_url,product_name,color,color_chip,thumbnail,likes,views,details,material,current_price,regular_price,discount_rate,rating,reviews,sales,manufacture_date,crawled_at,reorder
무신사,false,"",수아레,240000,상의,니트/스웨터,공용,"https://www.musinsa.com/products/2723767","데일리 라운드 니트 - 12 COLOR","","","https://image.msscdn.net/thumbnails/.../2723767_big.jpg?w=780",180000,180000,"사계절, 루즈핏, 라운드넥","면 60% 아크릴 40%",23150,45000,"49",4.9,40,280000,"22.08","260604",""
무신사,false,"",브론슨,81000,상의,반소매 티셔츠,공용,"https://www.musinsa.com/products/1487679","Tompkins Loopwheeled Tubular Tee 4 Color","","","https://image.msscdn.net/thumbnails/.../1487679_big.jpg?w=780",15000,40000,"여름, 오버핏, 튜블러","코튼 100%",38250,45000,"15",4.9,4,20000,"25년 7월","260604",""
```

### 브랜드 크롤링 (디자이너 — 수요일, 로우클래식)
```csv
platform,is_ranking,rank,brand,brand_likes,main_category,category,gender,product_detail_url,product_name,color,color_chip,thumbnail,likes,views,details,material,current_price,regular_price,discount_rate,rating,reviews,sales,manufacture_date,crawled_at,reorder
"",false,"",로우클래식,"",상의,긴팔 셔츠,여성,"https://lowclassic.com/products/12345","오버사이즈 옥스퍼드 셔츠","화이트","#FFFFFF","https://lowclassic.com/cdn/images/product.jpg","","","봄/여름, 오버사이즈핏, 하이카라","면 100%",189000,189000,"",4.7,88,"","2025-SS","260604",""
"",false,"",스컬프터,"",아우터,자켓,남성,"https://sculptor.kr/products/67890","린넨 블렌드 테일러드 자켓","차콜","#36454F","https://sculptor.kr/cdn/images/product2.jpg","","","봄 시즌, 세미오버핏, 노치드라펠","린넨 55% 폴리에스터 45%",398000,398000,"",4.9,45,"","2025-SS","260604",""
```

### 판매량·재입고 태그 처리 예시
```csv
# 원본: "[2만장 판매] 베이직 반팔 티셔츠"
# → product_name: "베이직 반팔 티셔츠", sales: 20000

# 원본: "[3차 재입고] 린넨 와이드 팬츠"  
# → product_name: "린넨 와이드 팬츠", reorder: 3

# 원본: "(5만개) [2차 재입고] 오버핏 후드 집업"
# → product_name: "오버핏 후드 집업", sales: 50000, reorder: 2
```

---

## 11. 구현 체크리스트

### 스케줄러
- [ ] 매일 09:00 KST — 플랫폼 3개 (무신사, 29cm, W컨셉)
- [ ] 월 09:00 — 국내 SPA 4개 (8세컨드, 유니클로, 스파오, 미쏘)
- [ ] 화 09:00 — 해외 SPA 3개 (COS, H&M, 자라)
- [ ] 수 09:00 — 디자이너 브랜드 9개
- [ ] 목 09:00 — 명품 브랜드 9개
- [ ] 금 09:00 — 보세 브랜드 10개
- [ ] 토 09:00 — 키즈 브랜드 (목록 추후 주입)

### 증분 크롤링
- [ ] 체크포인트 저장 (`checkpoints/*.json`)
- [ ] 신상품 전용 페이지/파라미터 우선 접근
- [ ] 기준점 이후 신규 상품만 수집
- [ ] 기존 상품 가격·좋아요·리뷰 업데이트 (가능 시)

### 봇 차단 대응
- [ ] User-Agent 로테이션 구현
- [ ] 요청 간 랜덤 딜레이 (1.5~3.5초)
- [ ] 쿠키/약관 모달 자동 클릭 (Playwright)
- [ ] 403/429 감지 시 재시도 로직
- [ ] HTML 구조 변경 대응 (`SELECTOR_MAP` fallback)

### 데이터 정제
- [ ] 상품명 판매량/재입고 태그 파싱 및 컬럼 분리
- [ ] `[]`, `()` 불필요 태그 제거
- [ ] 브랜드명 정규화 (`8세컨드` 통일)
- [ ] 한국어 단위 숫자 변환 (`28만 개` → `280000`)
- [ ] 가격 정제 (숫자만, 외화 시 통화 단위 포함)
- [ ] URL 절대경로 변환
- [ ] 이미지 실제 src 추출 (lazy-load 대응)
- [ ] URL 값 `""` 감싸기
- [ ] 빈 값 `""` 처리 (`null/None/nan` 제거)
- [ ] 중복 URL 제거

### 파일 출력
- [ ] UTF-8-SIG 인코딩
- [ ] 파일명 형식 준수 (`{brand_or_site}_{YYYYMMDD}.csv`)
- [ ] `output/platform/` vs `output/brand/{category}/` 폴더 분리
- [ ] 필수 필드 미수집 행 스킵
- [ ] 에러 로그 저장 (`logs/error_YYYYMMDD.log`)

---

## 12. 키즈 브랜드 목록 (토요일)

> `platform = ""`, `is_ranking = false`, `rank = ""`

| 브랜드명 | 비고 |
|----------|------|
| 보리보리 | |
| 유니클로 키즈 | 유니클로 키즈 카테고리 |
| 무신사 키즈 | 무신사 키즈 카테고리 |
| 자라 키즈 | 자라 키즈 카테고리 |
| 탑텐 키즈 | |
| 29cm 키즈 | 29cm 키즈 카테고리 |

---

## 13. 이미지 영구 저장 전략

### 13-1. 배경 및 목적

외부 CDN 이미지 URL(예: `msscdn.net`, `imagedelivery.net`)은 상품이 삭제되거나
사이트 구조가 변경되면 영구적으로 접근 불가능해진다.
따라서 크롤링 시점에 **이미지 원본을 직접 다운로드하여 로컬 또는 클라우드 스토리지에 저장**하고,
CSV의 `thumbnail` 필드에는 **내부 저장 경로(또는 업로드된 퍼블릭 URL)**를 기입한다.

### 13-2. 이미지 저장 흐름

```
크롤링 수집
    │
    ▼
원본 이미지 URL 확인 (thumbnail)
    │
    ├─ 고화질 URL 변환 시도 (파라미터 업스케일 — 아래 13-3 참고)
    │
    ▼
이미지 다운로드 (requests / httpx)
    │
    ├─ 성공 → 로컬 저장 + (옵션) 클라우드 업로드
    │           → CSV thumbnail 필드에 내부 경로 또는 퍼블릭 URL 기입
    │
    └─ 실패 → 원본 외부 URL 유지 + 에러 로그 기록
```

### 13-3. 고화질 이미지 URL 변환

사이트별로 URL 파라미터를 조작해 최대 해상도 이미지를 수집한다.

```python
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def upgrade_image_quality(url: str) -> str:
    """외부 이미지 URL을 고화질 버전으로 변환"""
    if not url:
        return url

    # 무신사 (msscdn.net) — ?w=780 → ?w=1280
    if "msscdn.net" in url:
        url = re.sub(r'[?&]w=\d+', '', url)
        sep = '&' if '?' in url else '?'
        return url + sep + 'w=1280'

    # Cloudflare Image Delivery (imagedelivery.net)
    # fit=cover,w=920,h=920 → fit=cover,w=1920,h=1920
    if "imagedelivery.net" in url:
        url = re.sub(r'w=\d+', 'w=1920', url)
        url = re.sub(r'h=\d+', 'h=1920', url)
        return url

    # W컨셉, 29cm 등 일반 CDN — 파라미터 제거해서 원본 획득 시도
    parsed = urlparse(url)
    if any(ext in parsed.path for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        return urlunparse(parsed._replace(query=''))  # 쿼리 파라미터 제거 → 원본 해상도

    return url
```

### 13-4. 이미지 다운로드 및 저장

```python
import os, hashlib, requests
from pathlib import Path
from PIL import Image
import io

IMAGE_SAVE_ROOT = "output/images"  # 로컬 저장 루트

def download_and_save_image(
    original_url: str,
    brand: str,
    product_id: str,
    crawled_at: str,
) -> str:
    """
    이미지를 다운로드하고 로컬에 저장한 뒤 저장 경로를 반환.
    실패 시 original_url 반환.
    """
    try:
        hq_url = upgrade_image_quality(original_url)

        headers = {"User-Agent": random.choice(USER_AGENTS), "Referer": "https://www.musinsa.com/"}
        resp = requests.get(hq_url, headers=headers, timeout=15)
        resp.raise_for_status()

        # 이미지 포맷 검증 (PIL)
        img = Image.open(io.BytesIO(resp.content))
        img.verify()
        img = Image.open(io.BytesIO(resp.content))  # verify() 후 재오픈 필요

        # 저장 디렉토리: output/images/{brand}/{crawled_at}/
        save_dir = Path(IMAGE_SAVE_ROOT) / brand / crawled_at
        save_dir.mkdir(parents=True, exist_ok=True)

        # 파일명: product_id + 원본 URL 해시 (중복 방지)
        url_hash = hashlib.md5(original_url.encode()).hexdigest()[:8]
        ext = _get_extension(img.format, hq_url)
        filename = f"{product_id}_{url_hash}{ext}"
        save_path = save_dir / filename

        # 고화질 JPEG 저장 (quality=95 이상)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(save_path, format="JPEG", quality=95, optimize=True)

        return str(save_path)  # 로컬 경로 반환

    except Exception as e:
        log_error(f"[IMG_FAIL] {original_url} → {e}")
        return original_url  # 실패 시 원본 URL 유지


def _get_extension(pil_format: str, url: str) -> str:
    fmt_map = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
    if pil_format in fmt_map:
        return fmt_map[pil_format]
    ext = os.path.splitext(urlparse(url).path)[-1].lower()
    return ext if ext in ('.jpg', '.jpeg', '.png', '.webp') else '.jpg'
```

### 13-5. 클라우드 업로드 (선택 옵션)

로컬 저장만으로 불안한 경우 S3 / GCS / Cloudflare R2 중 하나에 업로드하여
퍼블릭 URL을 CSV에 기입하는 방식을 추가할 수 있다.

```python
# AWS S3 업로드 예시
import boto3

S3_BUCKET = "your-bucket-name"
S3_PREFIX = "crawler-images"
CDN_BASE  = "https://cdn.yourdomain.com"  # CloudFront 등

def upload_to_s3(local_path: str, brand: str, filename: str) -> str:
    s3 = boto3.client("s3")
    key = f"{S3_PREFIX}/{brand}/{filename}"
    s3.upload_file(
        local_path, S3_BUCKET, key,
        ExtraArgs={"ContentType": "image/jpeg", "ACL": "public-read"},
    )
    return f"{CDN_BASE}/{key}"

# GCS 업로드 예시
from google.cloud import storage as gcs

def upload_to_gcs(local_path: str, brand: str, filename: str) -> str:
    client = gcs.Client()
    bucket = client.bucket("your-gcs-bucket")
    blob = bucket.blob(f"crawler-images/{brand}/{filename}")
    blob.upload_from_filename(local_path, content_type="image/jpeg")
    blob.make_public()
    return blob.public_url
```

### 13-6. CSV `thumbnail` 필드 저장 규칙

| 상황 | thumbnail 값 |
|------|-------------|
| 로컬 저장 성공 (클라우드 미사용) | `output/images/{brand}/{crawled_at}/{product_id}_{hash}.jpg` |
| S3/GCS 업로드 성공 | `https://cdn.yourdomain.com/crawler-images/...` (퍼블릭 URL) |
| 다운로드 실패 | 원본 외부 URL 유지 (예: `https://image.msscdn.net/...`) |

### 13-7. 이미지 저장 디렉토리 구조 예시

```
output/
└── images/
    ├── 수아레/
    │   └── 260604/
    │       ├── 2723767_a1b2c3d4.jpg
    │       └── 2723768_e5f6g7h8.jpg
    ├── 로우클래식/
    │   └── 260604/
    │       └── 12345_9i0j1k2l.jpg
    └── Dior/
        └── 260605/
            └── 67890_3m4n5o6p.jpg
```

### 13-8. 이미지 저장 관련 체크리스트

- [ ] `upgrade_image_quality()` — 사이트별 고화질 URL 변환 구현
- [ ] `download_and_save_image()` — 다운로드 + PIL 검증 + JPEG quality=95 저장
- [ ] 저장 디렉토리: `output/images/{brand}/{crawled_at}/`
- [ ] 파일명: `{product_id}_{url_hash8}.jpg` (중복 방지)
- [ ] 다운로드 실패 시 원본 URL 유지 + 에러 로그
- [ ] (옵션) S3 / GCS / R2 업로드 후 퍼블릭 URL을 `thumbnail`에 저장
- [ ] RGBA/P 모드 이미지 → RGB 변환 후 저장
