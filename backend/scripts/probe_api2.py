import json
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}


def get(url, accept="*/*"):
    req = urllib.request.Request(url, headers={**UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


# Barnet - find categories from homepage
try:
    html = get("https://the-barnnet.com/").decode("utf-8", "replace")
    cates = re.findall(r"product/list\.html\?cate_no=(\d+)", html)
    print("barnet cate_no from home:", list(dict.fromkeys(cates))[:10])
    print("detail links on home:", len(re.findall(r"product/detail\.html", html)))
    # extract product blocks from home
    names = re.findall(r"상품명\s*:\s*([^<\n]+)", html)
    prices = re.findall(r"KRW\s*([\d,]+)", html)
    print("home products names", names[:5], "prices", prices[:5])
except Exception as e:
    print("barnet err", e)

# H&M listing API patterns
hm_urls = [
    "https://api.hm.com/search-services/v1/ko_kr/listing/resultpage?pageSource=PLP&page=1&sort=RELEVANCE&pageId=/ladies/shop-by-product/view-all&page-size=36",
    "https://www2.hm.com/hmwebservices/service/product/list/ko_kr/category/ladies/shop-by-product/view-all/36/0/all",
    "https://www2.hm.com/hmwebservices/service/products/search/hm-ko_kr/Online/ko_kr?q=0&page=1&pageSize=36",
]
for u in hm_urls:
    try:
        body = get(u, "application/json")
        data = json.loads(body)
        print("HM OK", u[:90])
        print("  keys", list(data.keys())[:8] if isinstance(data, dict) else type(data))
        if isinstance(data, dict):
            for k in ("results", "products", "pagination", "plpList", "hits"):
                if k in data:
                    v = data[k]
                    print(f"  {k} type", type(v), "len", len(v) if isinstance(v, list) else v)
    except Exception as e:
        print("HM FAIL", u[:70], e)

# Uniqlo women all - try search
try:
    u = "https://www.uniqlo.com/kr/api/commerce/v5/ko/products?path=57892,,,&genderId=57892&offset=0&limit=36&imageRatio=3x4&rankingGender=women&httpFailure=true"
    data = json.loads(get(u, "application/json"))
    total = data.get("result", {}).get("pagination", {}).get("total")
    print("uniqlo women total", total)
except Exception as e:
    print("uniqlo fail", e)
