import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/javascript, */*; q=0.01"}

apis = [
    "https://the-barnnet.com/exec/front/Product/ApiProductNormal?cate_no=299&supplier_code=S0000000&page=1&count=40",
    "https://the-barnnet.com/exec/front/Product/ApiProductList?cate_no=299&page=1&count=40",
    "https://the-barnnet.com/api/product/list?cate_no=299&page=1&limit=40",
]
for u in apis:
    try:
        req = urllib.request.Request(u, headers=UA)
        body = urllib.request.urlopen(req, timeout=20).read()
        print("OK", u[:80])
        print(body[:300])
    except Exception as e:
        print("FAIL", u[:60], e)
