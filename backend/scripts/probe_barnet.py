import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


for cate in ["101", "222", "24", "43"]:
    url = f"https://the-barnnet.com/product/list.html?cate_no={cate}"
    try:
        html = fetch(url)
        print("=== cate", cate, "len", len(html), "status ok")
        items = re.findall(
            r'<li[^>]*class="[^"]*xans-record-[^"]*"[^>]*>(.*?)</li>',
            html,
            re.S,
        )
        print("  li records", len(items))
        names = re.findall(r'class="name[^"]*"[^>]*>\s*<a[^>]*>([^<]+)', html)
        print("  names", names[:4])
        imgs = re.findall(r'data-src="([^"]+)"|src="(/web/product/[^"]+)"', html)
        print("  imgs", len(imgs))
    except Exception as e:
        print("=== cate", cate, "ERR", e)
