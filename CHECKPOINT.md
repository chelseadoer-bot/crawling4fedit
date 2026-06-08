# 작업 체크포인트 (2026-06-04)

## 프로젝트 경로
`c:\Users\shim_soyun02\Desktop\AI AGNET\0604_크롤링_ver1`

## 수집 데이터 (CSV)
| 브랜드 | 파일 | 비고 |
|--------|------|------|
| UNIQLO | `data/output/uniqlo/uniqlo_products.csv` | ~602건 |
| COS | `data/output/cos/cos_products.csv` | ~724건, API `itemList` 파서 |
| ZARA | `data/output/zara/zara_products.csv` | ~247건 |
| 발렌시아가 | `data/output/balenciaga/balenciaga_products.csv` | ~308건 |
| 몽클레어 | `data/output/moncler/moncler_products.csv` | ~164건, ready-to-wear |
| 더바넷 | `data/output/barnet/barnet_products.csv` | ~506건 |
| H&M | `data/output/hm/hm_products.csv` | ~36건 (부분, 세션 필요) |
| DIOR / CHANEL | 없음 | 사이트 차단 |

## 주요 코드 변경
- `backend/app/brands/cos/crawler.py` — COS 전용 API 크롤러
- `backend/app/brands/moncler/crawler.py` — Moncler SearchApi 크롤러
- `backend/app/brands/balenciaga/crawler.py` — 발렌시아가
- `backend/app/brands/hm/crawler.py` — H&M + `data/hm_storage_state.json` 지원
- `backend/app/brands/registry.py` — 크롤러 등록·`resolve_crawler_id` 보강
- `config/brands.json` — URL·상태 동기화

## 실행 방법
```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
브라우저: http://127.0.0.1:8000

H&M 세션 저장:
```powershell
cd backend
python scripts/hm_save_session.py
```

전체 크롤:
```powershell
cd backend
python scripts/run_all_crawls.py
```

## COS URL (권장)
`https://www.cos.com/ko-kr/women/view-all.html`  
(`search?q=` 는 목록 수집에 부적합)

## 몽클레어 URL
`https://www.moncler.com/ko-kr/women/ready-to-wear`

## UI 오류 참고
「등록되지 않은 크롤러: cos」→ **예전 백엔드**가 8000 포트에서 실행 중일 때 발생. 서버 재시작 후 해결.
