import urllib.request
from pathlib import Path

url = "https://the-barnnet.com/product/list.html?cate_no=101"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
out = Path(__file__).resolve().parents[2] / "data" / "debug_barnet.html"
out.write_text(html[:80000], encoding="utf-8")
print("saved", out, "len", len(html))
print(html[20000:21000])
