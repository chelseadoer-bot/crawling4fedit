import json
import urllib.request
from urllib.parse import urlencode

params = {
    "path": "57892,57959,,",
    "genderId": "57892",
    "offset": "0",
    "limit": "36",
    "imageRatio": "3x4",
    "rankingGender": "women",
    "rankingClassId": "57959",
    "httpFailure": "true",
}
url = "https://www.uniqlo.com/kr/api/commerce/v5/ko/products?" + urlencode(params)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read())

result = data["result"]
print("pagination:", result.get("pagination"))
item = result["items"][0]
print("name:", item.get("name"))
print("productId:", item.get("productId"))
print("prices:", item.get("prices"))
rep = item.get("representative", {})
print("representative:", rep)
imgs = item.get("images", {}).get("main", {})
first_img = next(iter(imgs.values()), {}).get("image", "") if imgs else ""
print("first image:", first_img)
colors = [c.get("name") for c in item.get("colors", [])]
print("colors:", colors)
