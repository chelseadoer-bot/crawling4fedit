# ZARA 크롤러

ZARA 한국 사이트 베스트셀러 카테고리 크롤러입니다.

## 파일

| 파일 | 설명 |
|------|------|
| `config.json` | 기본 URL, 카테고리 ID 등 브랜드 설정 |
| `crawler.py` | Playwright 기반 크롤링 로직 |

## 수집 방식

1. Playwright로 페이지 접속 + 자동 스크롤
2. ZARA 내부 API (`/category/{id}/products?ajax=true`)에서 상품 데이터 수집
3. 표준 CSV 컬럼으로 변환 후 `data/output/zara/zara_products.csv` 저장

## 실행

```powershell
python scripts/run_zara.py
```

## 주의

- Akamai 봇 차단으로 **headless 모드 사용 불가**
- 브라우저 창이 자동으로 열립니다
