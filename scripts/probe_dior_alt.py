"""Dior alternate access methods"""
import json
import re
import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}

URL = "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear"

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace"), resp.status

# Try category page HTML
try:
    html, status = fetch(URL)
    print("HTML status:", status, "len:", len(html))
    print("title snippet:", re.search(r"<title>(.*?)</title>", html, re.I))
    if "__NEXT_DATA__" in html:
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
        if m:
            data = json.loads(m.group(1))
            print("NEXT_DATA keys:", list(data.keys()))
            print(json.dumps(data, ensure_ascii=False)[:2000])
    if "Page unavailable" in html:
        print("BLOCKED")
    else:
        links = re.findall(r'href="(/ko_kr/fashion/products/[^"]+)"', html)
        print("product links:", len(links), links[:5])
except Exception as e:
    print("HTML error:", e)

# Try common SFCC / internal APIs
candidates = [
    "https://www.dior.com/on/demandware.store/Sites-dior_kr-Site/ko_KR/Search-UpdateGrid?cgid=diorcom_femme_pretaporter_tout&start=0&sz=48",
    "https://www.dior.com/ko_kr/fashion/products/search?q=&page=1",
]
for u in candidates:
    try:
        body, st = fetch(u)
        print(f"\n{u} -> {st}, len={len(body)}")
        print(body[:500])
    except Exception as e:
        print(f"\n{u} -> error: {e}")
