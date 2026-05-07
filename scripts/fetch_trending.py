import sys
import re

html_path = sys.argv[1] if len(sys.argv) > 1 else "trending.html"

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

repos = []

articles = re.split(r'<article class="Box-row"', html)[1:]

for article in articles:
    # Repo name from h2
    h2_match = re.search(r'<h2 class="h3 lh-condensed">(.*?)</h2>', article, re.DOTALL)
    if not h2_match:
        continue
    h2_content = h2_match.group(1)
    link_match = re.search(r'href="/([^"]+)"', h2_content)
    if not link_match:
        continue
    full_name = link_match.group(1)

    # Description
    desc_match = re.search(r'<p class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>', article, re.DOTALL)
    description = ""
    if desc_match:
        desc_text = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
        description = desc_text.replace('|', '/')

    # Language
    lang_match = re.search(r'itemprop="programmingLanguage"[^>]*>\s*([^<\s]+)', article)
    language = lang_match.group(1) if lang_match else "Unknown"

    # Stars total - from stargazers link
    stars_total = "0"
    stars_match = re.search(r'href="/[^"]+/stargazers"[^>]*>.*?octicon-star.*?</svg>\s*([\d,]+)', article, re.DOTALL)
    if stars_match:
        stars_total = stars_match.group(1).replace(",", "")

    # Stars weekly - from float-sm-right span
    stars_weekly = "?"
    weekly_match = re.search(r'float-sm-right[^>]*>.*?octicon-star.*?</svg>\s*([\d,]+)\s*stars?\s*(this|last)\s', article, re.DOTALL)
    if weekly_match:
        stars_weekly = weekly_match.group(1).replace(",", "")

    repos.append({
        "full_name": full_name,
        "stars_weekly": stars_weekly,
        "stars_total": stars_total,
        "language": language,
        "description": description[:150]
    })

for i, r in enumerate(repos, 1):
    print(f"{i}|{r['full_name']}|{r['stars_weekly']}|{r['stars_total']}|{r['language']}|{r['description']}")
