import re
import urllib.request
import xml.etree.ElementTree as ET

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()

root = ET.fromstring(fetch("https://www.dior.com/sitemap.xml"))
locs = [el.text for el in root.findall(".//sm:loc", NS)]
print("top sitemaps:", len(locs))
for loc in locs[:20]:
    print(" ", loc)

# find fashion product sitemaps
fashion = [l for l in locs if "fashion" in l and "product" in l.lower()]
print("\nfashion product sitemaps:", fashion[:10])

# parse first relevant sitemap
target = None
for loc in locs:
    if "ko_kr" in loc and ("product" in loc.lower() or "pret" in loc.lower() or "ready" in loc.lower()):
        target = loc
        break
if not target:
    for loc in locs:
        if "product" in loc.lower():
            target = loc
            break

if target:
    print("\nParsing:", target)
    sub = ET.fromstring(fetch(target))
    urls = [el.text for el in sub.findall(".//sm:loc", NS)]
    rtw = [u for u in urls if "ready-to-wear" in u or "pret-a-porter" in u or "/fashion/products/" in u]
    print("total urls:", len(urls))
    print("product-like:", len(rtw))
    for u in rtw[:15]:
        print(" ", u)
