import json
import re
import urllib.request

# Barnet cafe24
url = "https://the-barnnet.com/product/list.html?cate_no=24"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode("utf-8", "replace")
print("barnet len", len(html))
print("product/detail links", len(re.findall(r"/product/detail\.html", html)))
names = re.findall(r'class="name[^"]*"[^>]*>\s*<a[^>]*>([^<]+)', html)
print("names sample", names[:5])

# H&M APIs
apis = [
    "https://api.hm.com/search-services/v1/ko_kr/listing/resultpage?pageSource=PLP&page=1&sort=RELEVANCE&pageId=/ladies/shop-by-product/view-all&page-size=36",
    "https://www2.hm.com/hmwebservices/service/product/list/ko_kr/category/0/0/36/0/all",
]
for api in apis:
    try:
        req = urllib.request.Request(
            api,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(800)
            print("HM OK", api[:70], body[:150])
    except Exception as e:
        print("HM FAIL", api[:70], e)

# COS - try product listing API patterns (H&M group)
cos_apis = [
    "https://www.cos.com/api/search/ko-kr/women?page=0&pageSize=48",
    "https://www.cos.com/seo-sitemap/ko-kr/women",
]
for api in cos_apis:
    try:
        req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(500)
            print("COS OK", api, body[:120])
    except Exception as e:
        print("COS FAIL", api[:60], e)

# Uniqlo root - navigation categories
req = urllib.request.Request(
    "https://www.uniqlo.com/kr/api/commerce/v5/ko/layout?device=desktop",
    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
        print("uniqlo layout ok", list(data.keys())[:5])
except Exception as e:
    print("uniqlo layout fail", e)
