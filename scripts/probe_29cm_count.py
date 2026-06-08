"""29CM category count check"""
import json
import urllib.request

url = "https://display-bff-api.29cm.co.kr/api/v1/listing/items/count"
body = json.dumps({
    "pageType": "CATEGORY_PLP",
    "sortType": "RECOMMENDED",
    "facets": {"categoryFacetInputs": [{"largeId": 268100100, "middleId": 268103100}]},
}).encode()
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as resp:
    print(json.loads(resp.read()))
