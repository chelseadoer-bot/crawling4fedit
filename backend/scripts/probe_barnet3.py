import re
import urllib.request

for path in [
    "product/list_all.html?cate_no=299",
    "product/list_all.html?cate_no=368",
    "product/list.html?cate_no=101",
]:
    url = f"https://the-barnnet.com/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    detail = len(re.findall("product/detail", html))
    names = re.findall(r'<strong class="[^"]*">\s*([^<]+?)\s*</strong>', html)
    print(path, "len", len(html), "detail", detail, "names", names[:3])
