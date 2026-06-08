import re
import urllib.request

url = "https://the-barnnet.com/product/list.html?cate_no=101"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
print("detail links", len(re.findall("product/detail", html)))
print("product_no", re.findall(r"product_no=(\d+)", html)[:8])
for pat in [
    r'<span class="name[^"]*">\s*<a[^>]*>([^<]+)',
    r'class="description"[^>]*>.*?<strong>([^<]+)',
    r'data-product-no="(\d+)"',
    r'"product_name"\s*:\s*"([^"]+)"',
]:
    m = re.findall(pat, html, re.S)
    print(pat[:40], "->", m[:3])
