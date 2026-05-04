"""Fetch GitHub Trending weekly page and output top 10 repos as structured data."""
import sys, re, json, urllib.request

sys.stdout.reconfigure(encoding='utf-8')

TRENDING_URL = "https://github.com/trending?since=weekly"
HTML_FILE = "D:/BaiduSyncdisk/Obsidian/ForCC/.claude/skills/github-trending/trending.html"

def fetch():
    """Download trending page HTML."""
    req = urllib.request.Request(TRENDING_URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req).read().decode('utf-8', errors='replace')
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    return html

def parse(html):
    """Parse trending HTML and return list of repo dicts."""
    articles = html.split('<article')
    repos = []
    for art in articles[1:]:
        h2_block = re.search(r'<h2[^>]*>(.*?)</h2>', art, re.DOTALL)
        repo = None
        if h2_block:
            h2_href = re.search(r'href="/([^"]+)"', h2_block.group(1))
            if h2_href:
                path = h2_href.group(1)
                parts = path.split('/')
                if len(parts) == 2 and 'login' not in path and 'sponsors' not in path:
                    repo = path

        desc_m = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', art, re.DOTALL)
        lang_m = re.search(r'itemprop="programmingLanguage"[^>]*>([^<]+)<', art)
        stars_week = re.search(r'([\d,]+)\s+stars?\s+this\s+week', art)
        total_stars = re.search(r'stargazers[^>]*>.*?([\d,]+)\s*</a>', art, re.DOTALL)

        if repo:
            repos.append({
                'repo': repo,
                'url': f'https://github.com/{repo}',
                'weeklyStars': stars_week.group(1) if stars_week else '?',
                'totalStars': total_stars.group(1) if total_stars else '?',
                'language': lang_m.group(1).strip() if lang_m else 'Unknown',
                'description': re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()[:120] if desc_m else '',
            })
            if len(repos) >= 10:
                break
    return repos

def main():
    print("Fetching GitHub Trending (weekly)...", file=sys.stderr)
    try:
        html = fetch()
    except Exception as e:
        print(f"Fetch failed: {e}, using cached HTML...", file=sys.stderr)
        with open(HTML_FILE, 'r', encoding='utf-8') as f:
            html = f.read()

    repos = parse(html)
    if not repos:
        print("No repos found!", file=sys.stderr)
        sys.exit(1)

    # Output JSON for machine consumption, text for human
    if '--json' in sys.argv:
        print(json.dumps(repos, ensure_ascii=False, indent=2))
    else:
        for i, r in enumerate(repos):
            print(f"{i+1}|{r['repo']}|{r['weeklyStars']}|{r['totalStars']}|{r['language']}|{r['description']}")

if __name__ == '__main__':
    main()
