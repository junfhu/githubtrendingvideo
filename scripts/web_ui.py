#!/usr/bin/env python3
"""Video production dashboard — full workflow hub.

Pages:
  /           Project list (from trending data), each with "Generate Video"
  /editor     Editor: screenshot + metadata + narration + voice + preview + build

Usage:
  python web_ui.py [--port 8765]
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import ssl
import urllib.parse
import urllib.request

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_github_token():
    """Read GitHub token from env or common config files."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    # Check gh CLI config
    for cfg_path in [
        os.path.expanduser("~/.config/gh/hosts.yml"),
        os.path.expanduser("~/.config/gh/config.yml"),
    ]:
        try:
            with open(cfg_path) as f:
                for line in f:
                    if "token:" in line or "oauth_token:" in line:
                        val = line.split(":", 1)[1].strip()
                        if val:
                            return val
        except Exception:
            pass
    return None


def github_api_get(path, timeout=15):
    """Call GitHub API with SSL context and retry on transient errors."""
    url = f"https://api.github.com/{path}"
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "trending-video/1.0"}
    token = _get_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    ctx = ssl.create_default_context()
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1)
REMOTION_DIR = os.path.join(SKILL_DIR, "remotion")
PUBLIC_DIR = os.path.join(REMOTION_DIR, "public")
OUTPUT_DIR = os.path.join(SKILL_DIR, "output")
TRENDING_FILE = os.path.join(SKILL_DIR, "trending.json")

# Edge TTS voice for Chinese narration
EDGE_TTS_VOICE = os.environ.get("EDGE_TTS_VOICE", "zh-CN-YunxiNeural")

os.makedirs(PUBLIC_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def translate_to_chinese(text):
    """Translate English text to Chinese via Google Translate API."""
    if not text or not text.strip():
        return text
    try:
        params = urllib.parse.urlencode({
            "client": "gtx",
            "sl": "en",
            "tl": "zh-CN",
            "dt": "t",
            "q": text[:1500],
        })
        url = f"https://translate.googleapis.com/translate_a/single?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            translated = "".join([s[0] for s in result[0] if s[0]])
            return translated
    except Exception:
        return text  # fallback to original on failure


def _number_to_chinese(n):
    """Convert an integer to Chinese numeral string (e.g. 1234 → 一千二百三十四)."""
    if n == 0:
        return "零"
    digits = "零一二三四五六七八九"
    units = ["", "十", "百", "千"]
    big_units = ["", "万", "亿"]

    # Split into 4-digit segments: [个位段, 万位段, 亿位段]
    segs = []
    while n > 0:
        segs.append(n % 10000)
        n //= 10000

    # Convert each segment to Chinese
    def _seg_cn(seg):
        if seg == 0:
            return ""
        s = ""
        prev_zero = False
        for i in range(3, -1, -1):
            d = (seg // (10 ** i)) % 10
            if d != 0:
                if prev_zero:
                    s += "零"
                s += digits[d] + units[i]
                prev_zero = False
            else:
                prev_zero = s != ""
        if s.startswith("一十"):
            s = s[1:]
        return s

    # Build result high-to-low
    result = ""
    for i in range(len(segs) - 1, -1, -1):
        s = _seg_cn(segs[i])
        if not s:
            continue
        # Need 零 after this segment's unit if next lower segment starts below 千
        need_zero = False
        if i > 0:
            for j in range(i - 1, -1, -1):
                if segs[j] > 0:
                    need_zero = segs[j] < 1000
                    break
        result += s + big_units[i]
        if need_zero:
            result += "零"
    return result


def extract_demo_images(readme_text, repo, max_images=5):
    """Extract demo/output images from README for visual showcase scenes.

    Looks for images in sections like: Demo, Example, Screenshot, Output, Usage, Results.
    Downloads them to remotion/public/ as demo_<repo>_<index>.png

    Returns: list of filenames (relative to public/) that were downloaded successfully.
    """
    import re as _re
    import base64
    from PIL import Image
    import io

    lines = readme_text.split("\n")

    # Sections that typically contain demo/output images
    demo_headings = [
        "demo", "example", "screenshot", "output", "result", "showcase",
        "visualization", "preview", "gallery", "usage", "what you get",
        "演示", "示例", "截图", "效果", "展示", "可视化", "预览", "用法",
        "getting started", "quick start", "install",
    ]
    skip_headings = [
        "install", "installation", "contributing", "license", "changelog",
        "安装", "贡献", "许可证", "更新日志",
    ]

    # Collect image URLs from README, prioritizing demo sections
    in_demo_section = False
    section_score = 0  # higher = more likely to be a demo image
    image_candidates = []  # (url, score)

    # Also check intro paragraphs (before first ##) for hero images
    in_intro = True

    for line in lines:
        stripped = line.strip()

        # Track section headings
        m2 = _re.match(r"^##\s+", stripped)
        m3 = _re.match(r"^###\s+", stripped)
        if m2 or m3:
            heading = stripped.lstrip("#").strip()
            h_lower = _normalize_heading(heading).lower()
            in_intro = False

            if any(kw in h_lower for kw in skip_headings):
                in_demo_section = False
                section_score = 0
                continue

            if any(kw in h_lower for kw in demo_headings):
                in_demo_section = True
                section_score = 10 if any(kw in h_lower for kw in ["demo", "example", "screenshot", "效果", "演示", "示例"]) else 5
            else:
                in_demo_section = False
                section_score = 0
            continue

        # Extract image URLs from markdown: ![alt](url) or <img src="url">
        # Markdown images
        for m in _re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', stripped):
            alt_text = m.group(1).lower()
            url = m.group(2).strip()
            score = section_score if in_demo_section else (3 if in_intro else 1)
            # Boost score if alt text suggests demo content
            if any(kw in alt_text for kw in ["demo", "example", "output", "result", "screenshot", "preview"]):
                score += 5
            # Skip badges, shields, tiny icons
            if any(skip in url.lower() for skip in ["shields.io", "badge", "codecov", "travis-ci", "circleci", "github-actions"]):
                continue
            if url.startswith("http"):
                image_candidates.append((url, score))

        # HTML img tags
        for m in _re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', stripped):
            url = m.group(1).strip()
            score = section_score if in_demo_section else (3 if in_intro else 1)
            if any(skip in url.lower() for skip in ["shields.io", "badge", "codecov"]):
                continue
            if url.startswith("http"):
                image_candidates.append((url, score))

    # Sort by score (descending) and deduplicate
    image_candidates.sort(key=lambda x: -x[1])
    seen_urls = set()
    unique_candidates = []
    for url, score in image_candidates:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_candidates.append((url, score))

    # Download top images
    safe_name = repo.replace("/", "-")
    downloaded = []
    ctx = ssl.create_default_context()

    for i, (url, score) in enumerate(unique_candidates[:max_images * 2]):
        if len(downloaded) >= max_images:
            break
        fname = f"demo_{safe_name}_{len(downloaded)}.png"
        fpath = os.path.join(PUBLIC_DIR, fname)

        try:
            # Handle relative URLs (convert to absolute GitHub raw URL)
            if url.startswith("/") and not url.startswith("//"):
                # Relative path on GitHub — construct raw URL
                owner, name = repo.split("/", 1)
                # Default branch detection would need API call; try main/master
                raw_base = f"https://raw.githubusercontent.com/{owner}/{name}/main"
                url = raw_base + url

            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "image/*",
            })
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = resp.read()

            # Validate it's actually an image (min 5KB, max 10MB)
            if len(data) < 5000 or len(data) > 10_000_000:
                continue

            # Convert to PNG via PIL for consistent format
            img = Image.open(io.BytesIO(data))
            if img.width < 200 or img.height < 100:
                continue  # Skip tiny images (icons, badges)

            # Resize large images to max 1920px wide for Remotion performance
            if img.width > 1920:
                ratio = 1920 / img.width
                img = img.resize((1920, int(img.height * ratio)), Image.LANCZOS)

            img.save(fpath, "PNG")
            downloaded.append(fname)
            print(f"  Demo image: {fname} ({img.width}x{img.height}, score={score})")

        except Exception as e:
            print(f"  Demo image download failed ({url}): {e}")
            continue

    return downloaded


def normalize_for_tts(text):
    """Normalize text so TTS reads all-caps words properly instead of letter-by-letter."""
    import re as _re
    # Words that TTS reads correctly as letters (keep as-is)
    keep_upper = {'API', 'URL', 'HTML', 'CSS', 'JS', 'JSON', 'XML', 'HTTP', 'HTTPS', 'SSH',
                  'GPU', 'CPU', 'RAM', 'SSD', 'USB', 'SDK', 'CLI', 'UI', 'UX', 'AI', 'ML',
                  'PDF', 'CSV', 'SQL', 'DNS', 'CDN', 'CI', 'CD', 'PR', 'MR', 'TTS', 'TXT'}
    # Convert other all-caps words to lowercase for proper pronunciation
    def _fix_word(m):
        word = m.group(0)
        if word.upper() in keep_upper or len(word) <= 1:
            return word
        return word.lower().replace('.md', ' markdown').replace('.MD', ' markdown')
    return _re.sub(r'\b[A-Z]{2,}(?:\.[A-Za-z]+)?\b', _fix_word, text)


def get_server_ip():
    """Detect the server's LAN IP address for external access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="Video Production Dashboard")
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

render_status = {"running": False, "progress": "", "output": None}
is_fetching = False
remotion_process = None
REMOTION_PORT = 3000


def is_remotion_running():
    """Check if Remotion Studio is reachable."""
    try:
        urllib.request.urlopen(f"http://localhost:{REMOTION_PORT}", timeout=2)
        return True
    except Exception:
        return False


def start_remotion():
    """Start Remotion Studio as a background process."""
    global remotion_process
    if is_remotion_running():
        return True

    # Ensure a props.json exists so Remotion has data to render
    props_file = os.path.join(REMOTION_DIR, "props.json")
    if not os.path.exists(props_file):
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump({
                "repo": "owner/repo",
                "name": "project",
                "totalStars": "0",
                "weeklyStars": "0",
                "language": "TypeScript",
                "description": "Select a project in the dashboard",
                "author": "author",
                "authorTitle": "Developer",
                "features": [
                    {"name": "feature-1", "desc": "Select a project first", "icon": "🚀"},
                    {"name": "feature-2", "desc": "Choose from trending list", "icon": "⚡"},
                    {"name": "feature-3", "desc": "Then generate video", "icon": "🔧"},
                    {"name": "feature-4", "desc": "Preview and build", "icon": "📦"},
                    {"name": "feature-5", "desc": "Share your video", "icon": "🎯"},
                    {"name": "feature-6", "desc": "Enjoy!", "icon": "🛡️"},
                ],
                "narration": "请先在管理台选择一个项目，然后点击 Generate Video。",
                "narrationTiming": {},
                "screenshot": "",
                "audio": "",
                "durationSeconds": 30,
                "sceneDurations": {},
                "sceneTexts": {},
            }, f, ensure_ascii=False, indent=2)

    try:
        remotion_process = subprocess.Popen(
            ["npx", "remotion", "studio", "--host=0.0.0.0", "--props=props.json"],
            cwd=REMOTION_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for it to be ready
        for _ in range(30):
            time.sleep(1)
            if is_remotion_running():
                return True
        return False
    except Exception as e:
        print(f"Failed to start Remotion: {e}")
        return False

# ── API: Trending ──────────────────────────────────────────────────────────

@app.get("/api/trending")
def get_trending():
    if os.path.exists(TRENDING_FILE):
        with open(TRENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


@app.get("/api/trending/fetch")
def fetch_trending():
    global is_fetching
    if is_fetching:
        return {"status": "already fetching"}
    is_fetching = True

    def do_fetch():
        global is_fetching
        try:
            html_path = os.path.join(SKILL_DIR, "trending.html")
            ctx = ssl.create_default_context()
            urllib.request.urlretrieve("https://github.com/trending?since=weekly", html_path)
            script = os.path.join(SKILL_DIR, "scripts", "fetch_trending.py")
            result = subprocess.run([sys.executable, script, html_path], capture_output=True, text=True, timeout=30)
            repos = []
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 5)
                    if len(parts) >= 5:
                        repos.append({
                            "full_name": parts[1].strip(),
                            "stars_weekly": parts[2].strip(),
                            "stars_total": parts[3].strip(),
                            "language": parts[4].strip(),
                            "description": parts[5].strip() if len(parts) > 5 else "",
                        })
            with open(TRENDING_FILE, "w", encoding="utf-8") as f:
                json.dump(repos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fetch error: {e}")
        finally:
            is_fetching = False

    threading.Thread(target=do_fetch, daemon=True).start()
    return {"status": "started"}


# ── API: Project selection ─────────────────────────────────────────────────

@app.post("/api/select-project")
def select_project(data: dict):
    """Fetch repo details from GitHub API, generate narration, save props."""
    repo = data.get("repo", "")
    if not repo:
        raise HTTPException(400, "No repo specified")

    try:
        owner, name = repo.split("/", 1)
    except ValueError:
        raise HTTPException(400, "Invalid repo format (use owner/name)")

    # Fetch repo info from GitHub API
    info = {}
    try:
        info = github_api_get(f"repos/{owner}/{name}")
    except Exception as e:
        print(f"GitHub API error: {e}")

    total_stars = f"{info.get('stargazers_count', 0):,}"
    language = info.get("language") or "Unknown"
    description = (info.get("description") or "").replace("|", "/")[:150]
    author = info.get("owner", {}).get("login", owner) if isinstance(info.get("owner"), dict) else owner
    topics = info.get("topics", []) or []

    author_title = f"{author} - Developer"

    # Fetch README for feature extraction & Chinese description
    readme_text = ""
    chinese_desc = ""
    intro_heading = ""
    intro_heading_index = 0
    features = [
        {"name": "/feature-1", "desc": "Core capability", "icon": "🚀"},
        {"name": "/feature-2", "desc": "Key functionality", "icon": "⚡"},
        {"name": "/feature-3", "desc": "Important tool", "icon": "🔧"},
        {"name": "/feature-4", "desc": "Workflow enhancement", "icon": "📦"},
        {"name": "/feature-5", "desc": "Integration support", "icon": "🎯"},
        {"name": "/feature-6", "desc": "Production ready", "icon": "🛡️"},
    ]

    try:
        readme_info = github_api_get(f"repos/{owner}/{name}/readme")
        import base64
        readme_text = base64.b64decode(readme_info.get("content", "")).decode("utf-8", errors="replace")
        features = extract_features(readme_text)

        desc_data = extract_chinese_description(readme_text, description, topics)
        chinese_desc = desc_data.get("text", "") if isinstance(desc_data, dict) else desc_data
        intro_heading = desc_data.get("heading", "") if isinstance(desc_data, dict) else ""
        intro_heading_index = desc_data.get("heading_index", 0) if isinstance(desc_data, dict) else 0

        # Extract demo images from README for visual showcase scenes
        demo_images = extract_demo_images(readme_text, repo, max_images=5)
        print(f"Extracted {len(demo_images)} demo images for {repo}")
    except Exception as e:
        print(f"README fetch error: {e}")
        demo_images = []

    # Try to fetch community profile for more metadata
    try:
        github_api_get(f"repos/{owner}/{name}/community/profile")
    except Exception:
        pass

    # Generate narration with timing cues
    weekly_stars = data.get("stars_weekly", "?")
    weekly_stars_clean = weekly_stars if weekly_stars and weekly_stars not in ('?', '0') else ''
    narration, timing, scene_texts = generate_narration(name, weekly_stars_clean, total_stars, language, chinese_desc or description, features)

    props = {
        "repo": repo,
        "name": name,
        "totalStars": total_stars,
        "weeklyStars": weekly_stars_clean,
        "language": language,
        "description": description,
        "chineseDesc": chinese_desc,
        "author": author,
        "authorTitle": author_title,
        "features": features,
        "narration": narration,
        "narrationTiming": timing,
        "sceneTexts": scene_texts,
        "screenshot": "",
        "screenshotIntroHeading": intro_heading,
        "screenshotIntroHeadingIndex": intro_heading_index,
        "demoImages": demo_images if demo_images else [],
        "audio": "",
        "durationSeconds": max(15, len(narration) * 0.25),
        "sceneDurations": {},
    }

    props_file = os.path.join(REMOTION_DIR, "props.json")
    with open(props_file, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    return props


# ── Chrome management ──────────────────────────────────────────────────────

def is_chrome_running():
    try:
        urllib.request.urlopen(f"http://localhost:9222/json", timeout=2)
        return True
    except Exception:
        return False


def ensure_chrome_running():
    if is_chrome_running():
        return True
    try:
        subprocess.Popen(
            ["google-chrome", "--remote-debugging-port=9222", "--remote-allow-origins=*",
             "--headless=new", "--window-size=1920,1080", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        for _ in range(15):
            time.sleep(0.5)
            if is_chrome_running():
                return True
    except FileNotFoundError:
        pass

    # Try chromium, chromium-browser
    for bin_name in ["chromium-browser", "chromium"]:
        try:
            subprocess.Popen(
                [bin_name, "--remote-debugging-port=9222", "--remote-allow-origins=*",
                 "--headless=new", "--window-size=1920,1080", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            for _ in range(15):
                time.sleep(0.5)
                if is_chrome_running():
                    return True
        except FileNotFoundError:
            continue
    return False


# ── API: Screenshot ────────────────────────────────────────────────────────

@app.post("/api/screenshot")
def take_screenshot(data: dict):
    repo = data.get("repo", "")
    if not repo:
        raise HTTPException(400, "No repo specified")

    if not ensure_chrome_running():
        raise HTTPException(500, "Cannot start Chrome. Install google-chrome or chromium-browser.")

    safe_name = repo.replace("/", "-")
    base_name = f"screenshot_{safe_name}"
    url = f"https://github.com/{repo}"

    script = os.path.join(SKILL_DIR, "scripts", "screenshot_cdp.py")

    # Get the target heading from props for a focused intro screenshot
    target_heading = data.get("heading", "")
    target_heading_index = data.get("heading_index", 0)
    if not target_heading:
        props_file = os.path.join(REMOTION_DIR, "props.json")
        if os.path.exists(props_file):
            with open(props_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
            target_heading = existing.get("screenshotIntroHeading", "")
            target_heading_index = existing.get("screenshotIntroHeadingIndex", 0)

    cmd = [sys.executable, script, url, base_name]
    if target_heading:
        cmd.extend(["--heading", target_heading])
    if target_heading_index:
        cmd.extend(["--heading-index", str(target_heading_index)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        top_name = None
        intro_name = None
        intro_height = None
        star_pos = None
        for line in result.stdout.split("\n") + result.stderr.split("\n"):
            if line.startswith("TOP:"):
                top_name = line.split("TOP:", 1)[1].strip()
            elif line.startswith("INTRO:"):
                intro_name = line.split("INTRO:", 1)[1].strip()
            elif line.startswith("INTRO_H:"):
                try:
                    intro_height = int(line.split("INTRO_H:", 1)[1].strip())
                except Exception:
                    pass
            elif "STAR_POS:" in line:
                try:
                    star_pos = json.loads(line.split("STAR_POS:", 1)[1].strip())
                except Exception:
                    pass

        if top_name and os.path.exists(os.path.join(PUBLIC_DIR, top_name)):
            props_file = os.path.join(REMOTION_DIR, "props.json")
            if os.path.exists(props_file):
                with open(props_file, "r", encoding="utf-8") as f:
                    props = json.load(f)
                props["screenshot"] = top_name
                if intro_name:
                    props["screenshotIntro"] = intro_name
                if intro_height:
                    props["screenshotIntroHeight"] = intro_height
                with open(props_file, "w", encoding="utf-8") as f:
                    json.dump(props, f, ensure_ascii=False, indent=2)

            return {
                "success": True,
                "top": f"/public/{top_name}",
                "intro": f"/public/{intro_name}" if intro_name else None,
                "intro_height": intro_height,
                "star_pos": star_pos,
            }
        return {"success": False, "error": result.stderr or result.stdout}
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Screenshot timed out")
    except Exception as e:
        raise HTTPException(500, str(e))


# ── API: Generate audio ────────────────────────────────────────────────────

def _generate_all_audio(texts_dict, output_dir, base_name):
    """Generate multiple audio files using Edge TTS. Returns {label: duration}."""
    import asyncio
    import edge_tts

    durations = {}
    for label, text in texts_dict.items():
        if not text:
            continue
        text = normalize_for_tts(text)
        out_path = os.path.join(output_dir, f"narration_{base_name}_{label}.mp3")
        print(f"  Generating {label} ({len(text)} chars)...")

        async def _gen():
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE, rate="+10%")
            await communicate.save(out_path)

        try:
            asyncio.run(_gen())
            # Measure duration via ffprobe
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_entries", "format=duration", out_path],
                    capture_output=True, text=True, timeout=5,
                )
                info = json.loads(result.stdout)
                dur = float(info["format"]["duration"])
            except Exception:
                # Fallback: estimate from file size (mp3 ~24kbps for Edge TTS)
                dur = os.path.getsize(out_path) / 3000
            durations[label] = round(dur, 2)
            print(f"  {label}: {dur:.1f}s")
        except Exception as e:
            print(f"  {label} FAILED: {e}")
            raise

    return durations


@app.post("/api/generate-audio")
def generate_audio(data: dict):
    text = data.get("text", "")
    if not text:
        raise HTTPException(400, "No text provided")

    repo = data.get("repo", "repo")
    safe_name = repo.replace("/", "-")
    scene_texts = data.get("scene_texts", {})
    combined_name = f"narration_{safe_name}.mp3"

    # Build all texts to generate: 7 scenes + 1 combined
    all_texts = dict(scene_texts) if scene_texts else {}
    all_texts["combined"] = text

    try:
        durations = _generate_all_audio(all_texts, PUBLIC_DIR, safe_name)
        combined_dur = durations.pop("combined", sum(durations.values()))
    except Exception as e:
        raise HTTPException(500, f"Edge TTS generation failed: {e}")

    # Rename combined file to standard name
    combined_src = os.path.join(PUBLIC_DIR, f"narration_{safe_name}_combined.mp3")
    combined_dst = os.path.join(PUBLIC_DIR, combined_name)
    if os.path.exists(combined_src):
        if os.path.exists(combined_dst):
            os.remove(combined_dst)
        os.rename(combined_src, combined_dst)

    # Use exact per-scene audio durations — discard combined file, concatenate scenes instead.
    # This guarantees each scene visual aligns perfectly with its audio.
    for s in ['s1', 's2', 's3', 's4', 's5', 's7']:
        if s not in durations:
            durations[s] = 2.0

    total_dur = sum(durations[s] for s in ['s1', 's2', 's3', 's4', 's5', 's7'])
    # Concatenate per-scene MP3s using ffmpeg (MP3 concat requires ffmpeg, not Python wave module)
    combined_path = os.path.join(PUBLIC_DIR, combined_name)
    scene_order = ['s1', 's2', 's3', 's4', 's5', 's7']
    mp3_files = []
    for s in scene_order:
        mp3_path = os.path.join(PUBLIC_DIR, f"narration_{safe_name}_{s}.mp3")
        if os.path.exists(mp3_path):
            mp3_files.append(mp3_path)

    if mp3_files:
        # Create concat list file for ffmpeg
        concat_list = os.path.join(PUBLIC_DIR, f"_concat_{safe_name}.txt")
        with open(concat_list, "w") as f:
            for mp3 in mp3_files:
                f.write(f"file '{mp3}'\n")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                 "-c", "copy", combined_path],
                capture_output=True, text=True, timeout=30,
            )
            print(f"Concatenated {len(mp3_files)} scene MP3s → {combined_path} ({total_dur:.1f}s)")
        except Exception as e:
            print(f"ffmpeg concat failed: {e}, using combined file as-is")
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)
    else:
        print("WARNING: no scene MP3s found, keeping TTS combined file")

    print(f"Scene durations: {durations}, total: {total_dur:.1f}s")

    # Update props with scaled exact scene durations
    props_file = os.path.join(REMOTION_DIR, "props.json")
    if os.path.exists(props_file):
        with open(props_file, "r", encoding="utf-8") as f:
            props = json.load(f)
        props["audio"] = combined_name
        props["sceneDurations"] = durations
        props["durationSeconds"] = round(total_dur, 1)
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump(props, f, ensure_ascii=False, indent=2)

    return {"success": True, "path": f"/public/{combined_name}", "duration": total_dur, "sceneDurations": durations}


# ── API: Remotion Studio ────────────────────────────────────────────────────

@app.get("/api/remotion/status")
def remotion_status():
    return {"running": is_remotion_running(), "port": REMOTION_PORT}


@app.post("/api/remotion/start")
def remotion_start():
    if is_remotion_running():
        return {"started": True, "message": "Already running"}
    ok = start_remotion()
    return {"started": ok, "message": "Started" if ok else "Failed to start"}


# ── API: Build video ───────────────────────────────────────────────────────

def _render_cover_still(composition_id: str, output_name: str, repo: str, props_data: dict):
    """Shared helper to render a Remotion Still cover."""
    props_file = os.path.join(REMOTION_DIR, "props.json")
    if not props_data:
        if os.path.exists(props_file):
            with open(props_file, "r", encoding="utf-8") as f:
                props_data = json.load(f)

    cover_props = {
        "repo": props_data.get("repo", repo),
        "name": props_data.get("name", ""),
        "totalStars": props_data.get("totalStars", "0"),
        "weeklyStars": props_data.get("weeklyStars", ""),
        "language": props_data.get("language", ""),
        "description": props_data.get("description", ""),
        "screenshot": props_data.get("screenshot", ""),
    }

    with open(props_file, "w", encoding="utf-8") as f:
        json.dump(cover_props, f, ensure_ascii=False)

    output_path = os.path.join(OUTPUT_DIR, output_name)
    cmd = [
        "npx", "remotion", "still", "src/index.ts", composition_id, output_path,
        "--props", json.dumps(cover_props),
    ]
    result = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(result.stderr[:500])
    return f"/output/{output_name}"


@app.post("/api/render-cover-mobile")
def render_cover_mobile(data: dict):
    """Render Douyin mobile cover (1080x1920, 9:16 portrait)."""
    repo = data.get("repo", "repo")
    safe_name = repo.replace("/", "-")
    try:
        path = _render_cover_still("CoverMobile", f"{safe_name}-cover-mobile.png", repo, data.get("props", {}))
        return {"success": True, "path": path}
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except FileNotFoundError:
        raise HTTPException(500, "npx not found. Install Node.js.")
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Cover render timed out (120s)")


@app.post("/api/render-cover-pc")
def render_cover_pc(data: dict):
    """Render PC landscape cover (1920x1080, 16:9)."""
    repo = data.get("repo", "repo")
    safe_name = repo.replace("/", "-")
    try:
        path = _render_cover_still("CoverPC", f"{safe_name}-cover-pc.png", repo, data.get("props", {}))
        return {"success": True, "path": path}
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except FileNotFoundError:
        raise HTTPException(500, "npx not found. Install Node.js.")
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Cover render timed out (120s)")


@app.post("/api/build-video")
def build_video(data: dict):
    global render_status
    if render_status["running"]:
        raise HTTPException(400, "Render already in progress")

    output_name = data.get("output_name", "output.mp4")
    output_path = os.path.join(OUTPUT_DIR, output_name)
    props = data.get("props", {})

    props_file = os.path.join(REMOTION_DIR, "props.json")
    with open(props_file, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False)

    render_status = {"running": True, "progress": "Starting render...", "output": output_path}

    def do_render():
        global render_status
        try:
            cmd = [
                "npx", "remotion", "render", "MainComposition", output_path,
                "--props", json.dumps(props),
            ]
            process = subprocess.Popen(
                cmd, cwd=REMOTION_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in process.stdout:
                render_status["progress"] = line.strip()
            process.wait()
            if process.returncode == 0:
                render_status["progress"] = f"Done: {output_path}"
                render_status["output"] = output_path
            else:
                render_status["progress"] = f"Failed (code {process.returncode})"
        except Exception as e:
            render_status["progress"] = f"Error: {e}"
        finally:
            render_status["running"] = False

    threading.Thread(target=do_render, daemon=True).start()
    return {"success": True, "output_path": output_path}


@app.get("/api/render-status")
def get_render_status():
    return render_status


@app.get("/api/props")
def get_props():
    props_file = os.path.join(REMOTION_DIR, "props.json")
    if os.path.exists(props_file):
        with open(props_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@app.post("/api/save-props")
def save_props(data: dict):
    props_file = os.path.join(REMOTION_DIR, "props.json")
    with open(props_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"success": True}


# ── Helpers ────────────────────────────────────────────────────────────────

def _strip_html(text):
    """Remove HTML tags, entities, and emoji — keep only readable text."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<(?:br|p|/p|/div|/li|/tr)\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'")
    text = text.replace("&nbsp;", " ").replace("&#x27;", "'")
    text = re.sub(r"&#?\w+;", " ", text)
    # Strip emoji and other unicode symbols (keep CJK, Latin, numbers, basic punctuation)
    text = re.sub(r'[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF'
                  r'☀-➿⭐✅❌✨❤'
                  r'⬆➡⚙⚡]', '', text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_table_rows(text):
    """Convert markdown table content to readable list format."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip table separator rows (|---|---|)
        if re.match(r"^[\|\s\-:]+$", stripped) and not re.search(r'[^\|\s\-:]', stripped):
            continue
        # Remove pipe characters and replace with comma-separated items
        if "|" in stripped:
            cells = [c.strip() for c in stripped.split("|")]
            cells = [c for c in cells if c and not re.match(r"^[-:]+$", c)]
            if cells:
                cleaned.append(": ".join(cells) if len(cells) == 2 else ", ".join(cells))
        else:
            cleaned.append(stripped)
    return " ".join(cleaned)


def _clean_md(text):
    """Strip markdown formatting and HTML tags from text."""
    text = _strip_html(text)
    text = _clean_table_rows(text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[*_~`|]", "", text)
    text = re.sub(r"[-=]{3,}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_heading(text):
    """Strip emoji, markdown formatting, and extra whitespace from a heading."""
    import re as _re
    # Remove emoji and common unicode symbols (keep CJK, Latin, numbers, punctuation)
    text = _re.sub(r'[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF'
                   r'☀-➿⭐✅❌✨❤'
                   r'⬆➡➡⚙⚡✨]', '', text)
    text = _re.sub(r'[^\w\s一-鿿぀-ゟ゠-ヿ가-힯'
                   r'\-\(\)\[\]{}.,;:!?@#$%^&*+=/\\|~`\'"]', '', text)
    text = _re.sub(r'[*_`#]', '', text)
    text = _re.sub(r'\s+', ' ', text).strip()
    return text


def _heading_contains(heading, terms):
    """Check if a heading contains any of the given terms (case-insensitive)."""
    h = heading.lower()
    for term in terms:
        if term.lower() in h:
            return True
    return False


def _is_skip_heading(heading):
    """Check if a heading is a standard boilerplate section to skip."""
    skip_words = {
        "installation", "install", "usage", "using", "getting started",
        "quickstart", "quick start", "contributing", "license", "documentation",
        "docs", "requirements", "prerequisites", "setup", "development",
        "build", "testing", "deploy", "deployment", "changelog",
        "faq", "troubleshooting", "acknowledgments", "credits",
        "table of contents", "contents", "categories", "目录",
        "creating", "create", "join the community", "join",
        "community", "support", "help", "related", "resources",
    }
    h = heading.lower().strip()
    if h in skip_words:
        return True
    for prefix in ["using ", "creating ", "how to ", "getting ", "join ", "related "]:
        if h.startswith(prefix):
            return True
    return False


def extract_chinese_description(readme_text, fallback_desc, topics):
    """Extract project core value proposition for Chinese narration.

    Returns: {"text": str, "heading": str, "heading_index": int}
    """
    lines = readme_text.split("\n")
    import re as _re

    # ── Define heading categories ──
    value_headings = [
        "what you get", "what you can do", "what you will get",
        "what you gain", "what you learn", "benefits", "use cases",
        "能获得什么", "你可以", "你能做什么", "你能得到什么",
        "功能介绍", "它能做什么", "有什么用", "核心价值",
        "highlights", "亮点", "特色", "features", "功能", "主要特性",
    ]
    intro_headings = [
        "what is", "what are", "about", "overview", "background",
        "介绍", "简介", "概述", "背景", "项目介绍", "关于",
    ]

    tagline = ""
    what_is_text = ""
    matched_heading = ""
    heading_index = 0
    categories = []

    # ── Pass 0: extract intro paragraphs before the first ## heading ──
    # Many READMEs put their best description here, before any section
    intro_lines = []
    for line in lines:
        stripped = line.strip()
        if _re.match(r"^##\s+", stripped):
            break
        # Skip HTML divs, badges, images, code blocks, blockquotes, horizontal rules
        if stripped.startswith("<") or stripped.startswith("```") or stripped.startswith("---"):
            continue
        if stripped.startswith("[!") or stripped.startswith("> "):
            continue
        if not stripped or stripped.startswith("#"):
            continue
        # Skip badge/shield lines
        if "shields.io" in stripped.lower() or "badge" in stripped.lower():
            continue
        intro_lines.append(stripped)

    intro_text = _clean_md(" ".join(intro_lines))
    # Only use if it's actually descriptive (not just a tagline or badges)
    if len(intro_text) > 40:
        what_is_text = intro_text
        # Use the first h2 heading for screenshot targeting
        for line in lines:
            m = _re.match(r"^##\s+", line.strip())
            if m:
                matched_heading = line.strip()[2:].strip()
                heading_index = 1
                break

    # ── Pass 1+2+3: only run if intro paragraphs didn't yield good content ──
    if what_is_text:
        # Already got a good description from intro paragraphs — use it directly
        pass
    else:
        # Collect ALL h2 sections with scores
        sections = []  # [(heading_text, heading_index, cleaned_text, score, raw_text)]
        h2_count = 0
        current_heading = ""
        current_lines = []

        def _finish_section():
            nonlocal current_heading, current_lines
            if current_lines and current_heading:
                raw = " ".join(current_lines)
                text = _clean_md(raw)
                if len(text) > 20:
                    h_clean = _normalize_heading(current_heading)
                    score = 0
                    if _heading_contains(h_clean, value_headings):
                        score = 10
                    elif _heading_contains(h_clean, intro_headings):
                        score = 5
                    elif not _is_skip_heading(h_clean):
                        score = 2
                    if score > 0:
                        sections.append((current_heading, h2_count, text, score, raw))
            current_heading = ""
            current_lines = []

        for line in lines:
            stripped = line.strip()

            # Blockquote tagline
            if stripped.startswith("> ") and not tagline:
                t = _clean_md(stripped[2:])
                if len(t) > 15 and not any(w in t.lower() for w in
                    ["want ", "get started", "try it", "see how", "check out", "click here", "sign up"]):
                    tagline = t

            m = _re.match(r"^##\s+", stripped)
            if m:
                _finish_section()
                current_heading = stripped[2:].strip()
                h2_count += 1
                continue

            if current_heading and stripped and not stripped.startswith("#") and not stripped.startswith("<!--"):
                if len(current_lines) < 30:
                    current_lines.append(stripped)

        _finish_section()

        # Pick the best section: blend heading relevance with content quality
        # Check RAW text (before _clean_md) for table indicators — pipes, separators
        scored = []
        for heading, idx, cleaned_text, score, raw_text in sections:
            pipe_ratio = raw_text.count("|") / max(len(raw_text), 1)
            dash_lines = len(re.findall(r"[-=]{3,}", raw_text))
            # Quality factor: 1.0 for prose, <0.5 for table-heavy sections
            quality_factor = 1.0
            if pipe_ratio > 0.03 or dash_lines > 1:
                quality_factor = max(0.2, 1.0 - pipe_ratio * 25)
            elif pipe_ratio > 0.01:
                quality_factor = 0.8
            effective_score = round(score * quality_factor, 1)
            prose_len = len(cleaned_text)
            scored.append((heading, idx, cleaned_text, effective_score, prose_len))

        scored.sort(key=lambda s: (s[3], s[4]), reverse=True)
        if scored:
            best = scored[0]
            what_is_text = best[2]
            matched_heading = best[0]
            heading_index = best[1]

        # ── Pass 2: if no section found, try first substantive paragraph ──
        if not what_is_text:
            in_section = False
            for line in lines:
                stripped = line.strip()
                m = _re.match(r"^##\s+", stripped)
                if m:
                    _finish_section()  # clean up
                    h_clean = _normalize_heading(stripped[2:].strip())
                    if _is_skip_heading(h_clean):
                        in_section = False
                        continue
                    if in_section:
                        break
                    in_section = True
                    current_heading = stripped[2:].strip()
                    current_lines = []
                    continue
                if in_section and stripped and not stripped.startswith("#") and not stripped.startswith("<!--") and not stripped.startswith(">"):
                    current_lines.append(stripped)
                    if len(" ".join(current_lines)) > 600:
                        break
            if current_lines:
                what_is_text = _clean_md(" ".join(current_lines))
                matched_heading = current_heading

        # ── Pass 3: count categories for awesome-list projects ──
        current_cat = None
        for line in lines:
            stripped = line.strip()
            if _re.match(r"^###\s+", stripped):
                name = _normalize_heading(stripped[3:].strip())
                if name and not _is_skip_heading(name):
                    current_cat = {"name": name, "count": 0}
                    categories.append(current_cat)
                continue
            if _re.match(r"^##\s+", stripped):
                h_clean = _normalize_heading(stripped[2:].strip())
                if _heading_contains(h_clean, ["skill", "feature", "功能", "category", "分类"]):
                    current_cat = None
                    continue
                current_cat = None
            if current_cat and _re.match(r"^[-*]\s+", stripped) and len(stripped) > 8:
                current_cat["count"] += 1

    # ── Build description text ──
    parts = []
    if what_is_text:
        what_short = what_is_text
        if len(what_is_text) > 500:
            cut = what_is_text.rfind(". ", 250, 500)
            if cut < 150:
                cut = what_is_text.rfind("。", 250, 500)
            what_short = what_is_text[:cut + 1] if cut > 150 else what_is_text[:500]
        translated = translate_to_chinese(what_short)
        parts.append(translated)

    total_items = sum(c["count"] for c in categories)
    cat_names = [c["name"] for c in categories if c["count"] > 0]
    if cat_names and total_items > 0:
        cat_str = "、".join(cat_names[:6])
        parts.append(f"共收录{total_items}个资源，涵盖{cat_str}等分类")

    result_text = ""
    if parts:
        result_text = "。".join(parts)
    elif topics:
        result_text = f"该项目涵盖{'、'.join(topics[:5])}等领域"
    elif fallback_desc and len(fallback_desc) < 80:
        result_text = f"项目简介：{fallback_desc}"

    return {"text": result_text, "heading": matched_heading, "heading_index": heading_index}


def extract_features(readme_text):
    """Extract features from README — handles awesome-list, tables, **bold** items, etc."""
    import re as _re
    features = []
    lines = readme_text.split("\n")

    feature_headings = ["skill", "feature", "功能", "特性", "列表", "list", "plugins"]
    in_skills = False
    current_category = None
    category_items = []  # (category_name, item_name, item_desc)

    for line in lines:
        stripped = line.strip()

        m2 = _re.match(r"^##\s+", stripped)
        m3 = _re.match(r"^###\s+", stripped)

        if m3:
            name = _normalize_heading(stripped[3:].strip())
            if name and in_skills and not _is_skip_heading(name):
                current_category = name
            continue

        if m2:
            h_clean = _normalize_heading(stripped[2:].strip())
            if _is_skip_heading(h_clean):
                in_skills = False
                current_category = None
                continue
            if _heading_contains(h_clean, feature_headings):
                in_skills = True
                current_category = h_clean
                continue
            in_skills = False
            current_category = h_clean

        if not current_category:
            continue

        # Format: `- [name](url) - description`
        m = _re.match(r"^[-*]\s+\[.+\]", stripped)
        if m:
            item_text = _clean_md(stripped)
            if " - " in item_text:
                iname, idesc = item_text.split(" - ", 1)
                category_items.append((current_category, iname.strip()[:50], idesc.strip()[:100]))
            elif len(item_text) > 4:
                category_items.append((current_category, item_text.strip()[:50], current_category))
            continue

        # Format: `- **name** — description` or `- **name**: description`
        m = _re.match(r"^[-*]\s+\*\*(.+?)\*\*[\s:—]*(.+)", stripped)
        if m:
            iname = m.group(1).strip()
            idesc = _clean_md(m.group(2).strip())
            category_items.append((current_category, iname[:50], idesc[:100]))
            continue

        # Format: `- name: description` or `- name - description`
        m = _re.match(r"^[-*]\s+(.+)", stripped)
        if m:
            item_text = _clean_md(m.group(1))
            if len(item_text) > 8:
                if " - " in item_text:
                    iname, idesc = item_text.split(" - ", 1)
                elif ": " in item_text:
                    iname, idesc = item_text.split(": ", 1)
                else:
                    iname, idesc = item_text, current_category
                category_items.append((current_category, iname.strip()[:50], idesc.strip()[:100]))

        # Table row: `| name | description |`
        m = _re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|", stripped)
        if m and not _re.match(r"^[\|\s\-:]+$", stripped):
            iname = _clean_md(m.group(1))
            idesc = _clean_md(m.group(2))
            if iname and not _heading_contains(iname, ["name", "名称", "feature"]):
                category_items.append((current_category, iname[:50], idesc[:100]))

    # Build features, pick diverse items across categories
    if category_items:
        # Pick up to 6 items, trying to cover different categories
        seen_cats = set()
        for cat, name, desc in category_items:
            if len(features) >= 6:
                break
            if cat not in seen_cats or len(features) < 3:
                features.append({
                    "name": name,
                    "desc": desc,
                    "icon": ["🚀", "⚡", "🔧", "📦", "🎯", "🛡️"][len(features) % 6],
                })
                seen_cats.add(cat)

    # Fallback: old-style Features section
    if len(features) < 3:
        in_features = False
        fallback_items = []
        for line in lines:
            lower = line.strip().lower()
            if lower.startswith("##") and ("feature" in lower or "功能" in lower):
                in_features = True
                continue
            if in_features and line.startswith("##"):
                in_features = False
                continue
            if in_features and _re.match(r"^[-*\d.]\s", line.strip()):
                cleaned = _clean_md(_re.sub(r"^[-*\d.]\s+", "", line.strip()))
                if 5 < len(cleaned) < 150:
                    fallback_items.append(cleaned)

        for i, item in enumerate(fallback_items[:6]):
            parts = item.split(":", 1) if ":" in item else item.split(" - ", 1) if " - " in item else [item, item[:50]]
            name = parts[0].strip()[:40] or f"feature-{i+1}"
            desc = parts[1].strip()[:80] if len(parts) > 1 else name
            features.append({"name": name, "desc": desc, "icon": ["🚀", "⚡", "🔧", "📦", "🎯", "🛡️"][i % 6]})

    # Ensure 6 features
    defaults = [
        {"name": "Core Engine", "desc": "Main processing capability", "icon": "🚀"},
        {"name": "Key Feature", "desc": "Essential functionality", "icon": "⚡"},
        {"name": "Tool Integration", "desc": "Built-in tool support", "icon": "🔧"},
        {"name": "Workflow", "desc": "Streamlined workflow", "icon": "📦"},
        {"name": "Advanced Mode", "desc": "Extended capabilities", "icon": "🎯"},
        {"name": "Production Ready", "desc": "Enterprise grade", "icon": "🛡️"},
    ]
    while len(features) < 6:
        features.append(defaults[len(features)])

    # Clean up: strip leading / from names (e.g. "/feature-1" → "feature-1")
    for f in features:
        f["name"] = f["name"].strip("/")

    return features[:6]


def extract_how_it_works(readme_text):
    """Extract 'How It Works' / workflow section from README.

    Returns: {"text": str, "heading": str, "heading_index": int}
    Searches for: How It Works, Architecture, Workflow, 工作原理, 怎么用 etc.
    """
    lines = readme_text.split("\n")
    import re as _re

    how_it_works_terms = [
        "how it works", "how does it work", "how this works", "how to use",
        "architecture", "system design", "design overview",
        "workflow", "pipeline", "process", "flow",
        "工作原理", "工作流程", "怎么用", "如何使用", "使用方法", "实现原理",
        "getting started", "quick start", "quickstart",
    ]

    h2_count = 0
    in_target = False
    target_lines = []
    target_heading = ""
    target_heading_index = 0

    for line in lines:
        stripped = line.strip()
        m = _re.match(r"^##\s+", stripped)
        if m:
            h2_count += 1
            heading = stripped[2:].strip()
            h_clean = _normalize_heading(heading)
            if in_target:
                in_target = False
            if _heading_contains(h_clean, how_it_works_terms):
                in_target = True
                target_heading = heading
                target_heading_index = h2_count
                target_lines = []

        if in_target and stripped and not stripped.startswith("#") and not stripped.startswith("<!--"):
            target_lines.append(stripped)
            if len(" ".join(target_lines)) > 800:
                in_target = False

    if not target_lines:
        return {"text": "", "heading": "", "heading_index": 0}

    raw_text = _clean_md(" ".join(target_lines))
    # Translate to Chinese for narration
    if len(raw_text) > 500:
        cut = raw_text.rfind(". ", 250, 500)
        raw_text = raw_text[:cut + 1] if cut > 100 else raw_text[:500]
    chinese = translate_to_chinese(raw_text)

    return {
        "text": chinese or raw_text,
        "heading": target_heading,
        "heading_index": target_heading_index,
    }


def generate_narration(name, weekly_stars, total_stars, language, description, features):
    # Build narration with per-scene timing cues
    parts = []
    cues = {}

    # S1: Opening (fixed)
    p1 = "今天介绍的 GitHub 热门项目是"
    parts.append(p1)
    cues["s2_project"] = len("".join(parts))  # S1→S2 transition

    # S2: Project name (visual only, name spoken as part of flow)
    p2 = f" {name}。"

    # Convert star counts to Chinese numerals for natural TTS reading
    def _star_cn(val_str):
        try:
            n = int(str(val_str).replace(",", ""))
            return _number_to_chinese(n)
        except (ValueError, TypeError):
            return str(val_str)
    total_cn = _star_cn(total_stars)
    weekly_cn = _star_cn(weekly_stars) if weekly_stars else ""

    has_weekly = weekly_stars and weekly_stars not in ('?', '0')
    if has_weekly:
        parts.append(p2)
        cues["s3_screenshot"] = len("".join(parts))
        # S3: Weekly stars
        p3 = f"本周获得{weekly_cn}颗星。"
        parts.append(p3)
        cues["s4_starzoom"] = len("".join(parts))
        # S4: Total stars
        p4 = f"，总计{total_cn}颗星。"
        parts.append(p4)
    else:
        # No weekly data — S3 uses total stars, S4 is visual-only (star zoom)
        parts.append(p2)
        cues["s3_screenshot"] = len("".join(parts))
        # S3: Total stars
        p3 = f"总计{total_cn}颗星。"
        parts.append(p3)
        cues["s4_starzoom"] = len("".join(parts))
        # S4: brief filler so star zoom scene has audio
        p4 = f"这个项目非常受欢迎。"
        parts.append(p4)
    cues["s5_intro"] = len("".join(parts))  # S4→S5

    # S5: Description — translate to Chinese if needed
    if description:
        desc_clean = description.replace("|", "，").strip()
        if not any('一' <= c <= '鿿' for c in desc_clean):
            desc_clean = translate_to_chinese(desc_clean)
        if len(desc_clean) > 300:
            cut = desc_clean.rfind("。", 0, 300)
            desc_clean = desc_clean[:cut + 1] if cut > 80 else desc_clean[:300]
        parts.append(desc_clean + "。")
    cues["s7_outro"] = len("".join(parts))  # S5→S7

    # S7: Outro (fixed)
    p7 = "关注我，获得最新的实用项目信息。"
    parts.append(p7)

    narr = "".join(parts)
    total_chars = len(narr)

    # Convert character positions to fraction (0-1) of total narration
    timing = {}
    for scene, pos in cues.items():
        timing[scene] = round(pos / total_chars, 3) if total_chars > 0 else 0

    # Extract 7 scene texts for per-scene audio generation
    cue_keys = ['s2_project', 's3_screenshot', 's4_starzoom', 's5_intro', 's7_outro']
    scene_texts = {}
    prev = 0
    labels = ['s1', 's2', 's3', 's4', 's5', 's7']
    idx = 0
    for key in cue_keys:
        pos = cues.get(key, len(narr))
        scene_texts[labels[idx]] = narr[prev:pos].strip('，。、；：！？,.;:!? ')
        prev = pos
        idx += 1
    scene_texts[labels[idx]] = narr[prev:].strip('，。、；：！？,.;:!? ')

    return narr, timing, scene_texts


# ── HTML ───────────────────────────────────────────────────────────────────

TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates")
INDEX_HTML = os.path.join(TEMPLATE_DIR, "index.html")

def get_html_template(server_ip=""):
    """Read the SPA template from file, replacing placeholders."""
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()
    if server_ip:
        html = html.replace("__SERVER_IP__", server_ip)
    return html

# ── HTML template now in templates/index.html, loaded via get_html_template() ──

# ── Pages ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return _HTML_TEMPLATE


@app.get("/editor", response_class=HTMLResponse)
def editor_page():
    return _HTML_TEMPLATE


# ── Main ───────────────────────────────────────────────────────────────────

_HTML_TEMPLATE = ""

def main():
    parser = argparse.ArgumentParser(description="Video Production Dashboard")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    args = parser.parse_args()

    server_ip = get_server_ip()
    global _HTML_TEMPLATE
    _HTML_TEMPLATE = get_html_template(server_ip)

    print(f"Dashboard: http://{server_ip}:{args.port}  (local: http://localhost:{args.port})")

    # Start Remotion Studio in background
    if not is_remotion_running():
        print("Starting Remotion Studio...")
        threading.Thread(target=start_remotion, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
