# 패션 MD 크롤링 자동화 서비스

여러 패션 브랜드 사이트에서 상품 정보를 수집하고 **표준 CSV**로 출력하는 내부 도구입니다.

> 상세 기획서: [docs/fashion_crawling_spec.md](docs/fashion_crawling_spec.md)  
> **v3 Agent 명세 정리:** [docs/V3_정리.md](docs/V3_정리.md) · [docs/crawler_agent_prompt_v3.md](docs/crawler_agent_prompt_v3.md)

## 프로젝트 구조

```
0604_크롤링_ver1/
├── docs/
│   └── fashion_crawling_spec.md   # 서비스 기획서
├── config/
│   └── brands.json                # 등록된 브랜드 목록
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                # FastAPI 서버
│       ├── core/
│       │   ├── csv_schema.py      # 표준 CSV 컬럼 정의
│       │   └── csv_writer.py
│       ├── brands/
│       │   ├── base.py            # 크롤러 공통 인터페이스
│       │   ├── registry.py        # 브랜드별 크롤러 등록
│       │   └── zara/              # ZARA 전용
│       │       ├── config.json
│       │       └── crawler.py
│       └── services/
│           └── crawler_service.py
├── data/
│   └── output/
│       └── zara/                  # ZARA CSV 저장 위치
│           └── zara_products.csv
├── scripts/
│   └── run_zara.py                # ZARA CLI 실행
└── frontend/                      # (예정) React SPA
```

## 표준 CSV 컬럼

| 컬럼 | 설명 |
|------|------|
| brand | 브랜드명 |
| product_id | 상품코드 |
| product_name | 상품명 |
| category_large | 대분류 |
| category_small | 소분류 |
| price_original | 정가 (숫자) |
| price_sale | 할인가 |
| discount_rate | 할인율 |
| color | 색상 |
| sizes_available | 가용 사이즈 |
| stock_status | 재고상태 |
| product_url | 상품 URL |
| image_url | 대표 이미지 URL |
| crawled_at | 수집일시 |
| source_site | 수집 출처 도메인 |

## 설치

```powershell
cd backend
pip install -r requirements.txt
python -m playwright install chromium
```

## ZARA 크롤링 실행

### CLI

```powershell
python scripts/run_zara.py
```

### API 서버

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

- 브랜드 목록: `GET http://localhost:8000/api/brands`
- ZARA 크롤링: `POST http://localhost:8000/api/brands/zara/crawl`
- CSV 다운로드: `GET http://localhost:8000/api/brands/zara/download`
- API 문서: `http://localhost:8000/docs`

## 새 브랜드 추가 방법

1. `backend/app/brands/{브랜드id}/` 폴더 생성
2. `config.json`, `crawler.py` 작성 (`BaseBrandCrawler` 상속)
3. `backend/app/brands/registry.py`에 크롤러 등록
4. `config/brands.json`에 브랜드 메타 추가
5. `data/output/{브랜드id}/` 폴더 생성

## 현재 등록 브랜드

| ID | 브랜드 | 수집 | 크롤링 방식 |
|----|--------|------|-------------|
| zara | ZARA | 247 | Playwright + API |
| uniqlo | UNIQLO 여성 상의 | 195 | REST API |
| 29cm | 29CM 상의 | 24,904 | REST API |
| dior | DIOR | — | Playwright (봇차단) |

웹 UI: `frontend` → http://localhost:5173
