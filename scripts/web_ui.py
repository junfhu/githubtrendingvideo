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


def github_api_get(path, timeout=15):
    """Call GitHub API with SSL context and retry on transient errors."""
    url = f"https://api.github.com/{path}"
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "trending-video/1.0"}

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
REF_AUDIO = "/home/ppcorn/qwen3tts/hjf_test.wav"
REF_TEXT = "这是一个测试录音，我们看看它的效果如何。"
OUTPUT_DIR = os.path.join(SKILL_DIR, "output")
TRENDING_FILE = os.path.join(SKILL_DIR, "trending.json")

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
        chinese_desc = extract_chinese_description(readme_text, description, topics)
    except Exception as e:
        print(f"README fetch error: {e}")

    # Try to fetch community profile for more metadata
    try:
        github_api_get(f"repos/{owner}/{name}/community/profile")
    except Exception:
        pass

    # Generate narration with timing cues
    weekly_stars = data.get("stars_weekly", "?")
    narration, timing, scene_texts = generate_narration(name, weekly_stars, total_stars, language, chinese_desc or description, features)

    props = {
        "repo": repo,
        "name": name,
        "totalStars": total_stars,
        "weeklyStars": weekly_stars,
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

    try:
        result = subprocess.run(
            [sys.executable, script, url, base_name],
            capture_output=True, text=True, timeout=60
        )

        top_name = None
        intro_name = None
        star_pos = None
        for line in result.stdout.split("\n") + result.stderr.split("\n"):
            if line.startswith("TOP:"):
                top_name = line.split("TOP:", 1)[1].strip()
            elif line.startswith("INTRO:"):
                intro_name = line.split("INTRO:", 1)[1].strip()
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
                with open(props_file, "w", encoding="utf-8") as f:
                    json.dump(props, f, ensure_ascii=False, indent=2)

            return {
                "success": True,
                "top": f"/public/{top_name}",
                "intro": f"/public/{intro_name}" if intro_name else None,
                "star_pos": star_pos,
            }
        return {"success": False, "error": result.stderr or result.stdout}
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Screenshot timed out")
    except Exception as e:
        raise HTTPException(500, str(e))


# ── API: Generate audio ────────────────────────────────────────────────────

def _generate_all_audio(texts_dict, output_dir, base_name):
    """Generate multiple audio files using local VoxCPM (one model load). Returns {label: duration}."""
    from voxcpm import VoxCPM
    import soundfile as sf

    model_path = os.path.join(os.path.expanduser("~"), "voxcpm", "pretrained_models", "VoxCPM2")
    if not os.path.exists(model_path):
        raise RuntimeError(f"VoxCPM model not found at {model_path}")

    print("Loading VoxCPM model (one-time)...")
    model = VoxCPM.from_pretrained(model_path, load_denoiser=False)

    use_ref = os.path.exists(REF_AUDIO)
    ref_wav = REF_AUDIO if use_ref else None

    # Prompt-based warm-up for better voice cloning quality
    if use_ref:
        try:
            print("  Warm-up voice clone...")
            model.generate(
                text="(正常语速，温柔)GitHub热门项目介绍。",
                prompt_wav_path=ref_wav,
                prompt_text=REF_TEXT,
                reference_wav_path=ref_wav,
                cfg_value=2.0,
                inference_timesteps=10,
            )
            print("  Warm-up done")
        except Exception as e:
            print(f"  Warm-up failed (non-fatal): {e}")

    durations = {}
    for label, text in texts_dict.items():
        if not text:
            continue
        text = normalize_for_tts(text)
        out_path = os.path.join(output_dir, f"narration_{base_name}_{label}.wav")
        print(f"  Generating {label} ({len(text)} chars)...")
        try:
            wav = model.generate(
                text="(正常语速，温柔)" + text,
                reference_wav_path=ref_wav,
                cfg_value=2.0,
                inference_timesteps=10,
            )
            sf.write(out_path, wav, model.tts_model.sample_rate)
            dur = len(wav) / model.tts_model.sample_rate
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
    combined_name = f"narration_{safe_name}.wav"

    # Build all texts to generate: 7 scenes + 1 combined
    all_texts = dict(scene_texts) if scene_texts else {}
    all_texts["combined"] = text

    try:
        # Try local VoxCPM first (one model load for all)
        durations = _generate_all_audio(all_texts, PUBLIC_DIR, safe_name)
        combined_dur = durations.pop("combined", sum(durations.values()))
    except Exception as e:
        print(f"Local VoxCPM failed: {e}, trying HuggingFace...")
        # Fallback to HuggingFace Space
        try:
            from gradio_client import Client
            from gradio_client.utils import handle_file
            client = Client("openbmb/VoxCPM-Demo")
            ref_file = handle_file(REF_AUDIO) if os.path.exists(REF_AUDIO) else None

            durations = {}
            for label, scene_text in all_texts.items():
                if not scene_text:
                    continue
                out_path = os.path.join(PUBLIC_DIR, f"narration_{safe_name}_{label}.wav")
                text_norm = normalize_for_tts(scene_text)
                result = client.predict(
                    text_input=text_norm, control_instruction="",
                    reference_wav_path_input=ref_file,
                    use_prompt_text=False, prompt_text_input="",
                    cfg_value_input=2.0, do_normalize=False, denoise=False,
                    api_name="/generate",
                )
                if result and isinstance(result, str):
                    import shutil
                    shutil.copy(result, out_path)
                    try:
                        import wave
                        with wave.open(out_path, "r") as wf:
                            dur = wf.getnframes() / wf.getframerate()
                    except Exception:
                        dur = len(scene_text) * 0.25
                    durations[label] = round(dur, 2)
            combined_dur = durations.pop("combined", sum(durations.values()))
        except Exception as e2:
            raise HTTPException(500, f"Both local VoxCPM and HuggingFace failed: {e2}")

    # Rename combined file to standard name
    combined_src = os.path.join(PUBLIC_DIR, f"narration_{safe_name}_combined.wav")
    combined_dst = os.path.join(PUBLIC_DIR, combined_name)
    if os.path.exists(combined_src):
        if os.path.exists(combined_dst):
            os.remove(combined_dst)
        os.rename(combined_src, combined_dst)

    # Scene timing: fixed short scenes, proportional S5+S6
    timing = data.get("timing", {})
    fixed = {"s1": 2.5, "s2": 2.5, "s3": 2.5, "s4": 2.5, "s7": 2.5}
    fixed_total = sum(fixed.values())
    remaining = max(combined_dur - fixed_total, 10)

    s5_frac = timing.get("s6_features", 0.5) - timing.get("s5_intro", 0.1)
    s6_frac = 1.0 - timing.get("s6_features", 0.5)
    total_frac = max(s5_frac + s6_frac, 0.01)

    durations = dict(fixed)
    durations["s5"] = round(remaining * s5_frac / total_frac, 2)
    durations["s6"] = round(remaining * s6_frac / total_frac, 2)

    total_dur = sum(durations.values())
    print(f"Combined: {combined_dur:.1f}s, scaled total: {total_dur:.1f}s, durations: {durations}")

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

def _clean_md(text):
    """Strip markdown formatting from text."""
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
        "community", "support", "help",
    }
    h = heading.lower().strip()
    if h in skip_words:
        return True
    # Skip headings that start with these patterns
    for prefix in ["using ", "creating ", "how to ", "getting ", "join "]:
        if h.startswith(prefix):
            return True
    return False


def extract_chinese_description(readme_text, fallback_desc, topics):
    """Extract project purpose and structure for Chinese narration."""
    lines = readme_text.split("\n")
    import re as _re

    tagline = ""
    what_is_text = ""
    categories = []  # {name, count}

    # ── Pass 1: extract tagline and "what is / about" section ──
    in_what_is = False
    what_lines = []
    for line in lines:
        stripped = line.strip()

        # Blockquote tagline (marketing blurbs like "Want skills that...") — skip these
        if stripped.startswith("> ") and not tagline:
            t = _clean_md(stripped[2:])
            # Only keep if it reads like a factual description, not a marketing pitch
            if not any(w in t.lower() for w in ["want ", "get started", "try it", "see how", "check out", "click here", "sign up"]):
                if len(t) > 15:
                    tagline = t

        m = _re.match(r"^##\s+", stripped)
        if m:
            heading = stripped[2:].strip()
            h_clean = _re.sub(r"[*_`#]", "", heading).strip()
            if _re.match(r"(What\s+(is|are)|About|Overview|介绍|简介|概述|Background)", h_clean, _re.IGNORECASE):
                in_what_is = True
                continue
            elif in_what_is:
                in_what_is = False

        if in_what_is and stripped and not stripped.startswith("#") and not stripped.startswith("<!--"):
            what_lines.append(stripped)
            if len(" ".join(what_lines)) > 800:
                in_what_is = False

    if what_lines:
        what_is_text = _clean_md(" ".join(what_lines))

    # ── Pass 2: find categories and their items ──
    in_skills_section = False
    current_cat = None

    for line in lines:
        stripped = line.strip()
        m2 = _re.match(r"^##\s+", stripped)
        m3 = _re.match(r"^###\s+", stripped)

        if m3 and in_skills_section:
            name = _clean_md(stripped[3:].strip())
            if not _is_skip_heading(name) and not name.startswith("What"):
                current_cat = {"name": name, "count": 0}
                categories.append(current_cat)
            continue

        if m3 and not in_skills_section:
            continue

        if m2:
            h_clean = _re.sub(r"[*_`#]", "", stripped[2:].strip()).strip()
            if _is_skip_heading(h_clean) or h_clean.startswith("?") or h_clean.startswith("What"):
                in_skills_section = False
                current_cat = None
                continue
            if "skill" in h_clean.lower() or "feature" in h_clean.lower() or "功能" in h_clean:
                in_skills_section = True
                current_cat = None
                continue
            in_skills_section = False
            current_cat = {"name": h_clean, "count": 0}
            categories.append(current_cat)

        # Count items
        if current_cat and _re.match(r"^[-*]\s+\[.+\]", stripped):
            current_cat["count"] += 1
        elif current_cat and _re.match(r"^[-*]\s+", stripped) and len(stripped) > 8:
            if not stripped.startswith("- ["):
                current_cat["count"] += 1

    # ── Build description: summarize what the project does ──
    parts = []

    # Translate the "What is / About" explanation to Chinese (core purpose)
    if what_is_text:
        what_short = what_is_text
        if len(what_is_text) > 500:
            cut = what_is_text.rfind(". ", 250, 500)
            what_short = what_is_text[:cut + 1] if cut > 150 else what_is_text[:500]
        translated = translate_to_chinese(what_short)
        parts.append(translated)

    # Add scope if it's an awesome-list type project
    total_items = sum(c["count"] for c in categories)
    cat_names = [c["name"] for c in categories if c["count"] > 0]
    if cat_names and total_items > 0:
        cat_str = "、".join(cat_names[:6])
        parts.append(f"共收录{total_items}个资源，涵盖{cat_str}等分类")

    if parts:
        return "。".join(parts)

    if topics:
        return f"该项目涵盖{'、'.join(topics[:5])}等领域"

    if fallback_desc and len(fallback_desc) < 80:
        return f"项目简介：{fallback_desc}"

    return ""


def extract_features(readme_text):
    """Extract features from README — handles awesome-list style with nested categories."""
    import re as _re
    features = []
    lines = readme_text.split("\n")

    # Detect structure: flat ## categories or nested (## Skills → ### Category → items)
    in_skills_section = False
    current_category = None
    category_items = []  # (category_name, item_name, item_desc)

    for line in lines:
        stripped = line.strip()

        m2 = _re.match(r"^##\s+", stripped)
        m3 = _re.match(r"^###\s+", stripped)

        # ### under ## Skills → category
        if m3 and in_skills_section:
            name = _clean_md(stripped[3:].strip())
            if not _is_skip_heading(name):
                current_category = name
            continue

        if m3 and not in_skills_section:
            # Standalone ### item under any ## category
            if current_category:
                item_text = _clean_md(stripped[3:].strip())
                if " - " in item_text:
                    iname, idesc = item_text.split(" - ", 1)
                elif ": " in item_text:
                    iname, idesc = item_text.split(": ", 1)
                else:
                    iname, idesc = item_text, current_category
                category_items.append((current_category, iname.strip()[:40], idesc.strip()[:80]))
            continue

        if m2:
            h_clean = _re.sub(r"[*_`#]", "", stripped[2:].strip()).strip()
            if _is_skip_heading(h_clean) or h_clean.startswith("?") or h_clean.startswith("What"):
                in_skills_section = False
                current_category = None
                continue
            if "skill" in h_clean.lower() or "feature" in h_clean.lower() or "功能" in h_clean:
                in_skills_section = True
                current_category = None
                continue
            in_skills_section = False
            current_category = h_clean

        # Bullet item: `- [name](url) - description` or `- [name/](url) - description`
        if current_category and _re.match(r"^[-*]\s+\[.+\]", stripped):
            item_text = _re.sub(r"^[-*]\s+", "", stripped)
            item_text = _re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", item_text)
            item_text = _re.sub(r"`([^`]+)`", r"\1", item_text)
            # Remove trailing / from folder-style links
            item_text = item_text.rstrip("/")
            if " - " in item_text:
                iname, idesc = item_text.split(" - ", 1)
                category_items.append((current_category, iname.strip()[:40], idesc.strip()[:80]))
            elif len(item_text) > 4:
                category_items.append((current_category, item_text.strip()[:40], current_category))

        # Plain bullet under category (non-link)
        if current_category and _re.match(r"^[-*]\s+", stripped) and not _re.match(r"^[-*]\s+\[", stripped):
            item_text = _clean_md(_re.sub(r"^[-*]\s+", "", stripped))
            if len(item_text) > 8:
                if " - " in item_text:
                    iname, idesc = item_text.split(" - ", 1)
                    category_items.append((current_category, iname.strip()[:40], idesc.strip()[:80]))

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
    parts.append(p2)
    cues["s3_screenshot"] = len("".join(parts))  # S2→S3

    # S3: Weekly stars
    p3 = f"本周获得{weekly_stars}颗星。"
    parts.append(p3)
    cues["s4_starzoom"] = len("".join(parts))  # S3→S4

    # S4: Total stars (continuation with comma)
    p4 = f"，总计{total_stars}颗星。"
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
    cues["s6_features"] = len("".join(parts))  # S5→S6

    # S6: Features — translate descriptions to Chinese for voice
    if features:
        feat_parts = ["核心功能包括："]
        for i, f in enumerate(features[:5]):
            fname = f["name"].strip("/")
            fdesc = f.get("desc", "")[:80]
            # Translate English descriptions to Chinese
            if fdesc and not any('一' <= c <= '鿿' for c in fdesc):
                fdesc = translate_to_chinese(fdesc)
            if fdesc and fname not in fdesc:
                feat_parts.append(f"{fname}，{fdesc}；")
            else:
                feat_parts.append(f"{fname}；")
        feat_text = "".join(feat_parts).rstrip("；") + "。"
        parts.append(feat_text)
    cues["s7_outro"] = len("".join(parts))  # S6→S7

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
    cue_keys = ['s2_project', 's3_screenshot', 's4_starzoom', 's5_intro', 's6_features', 's7_outro']
    scene_texts = {}
    prev = 0
    labels = ['s1', 's2', 's3', 's4', 's5', 's6', 's7']
    idx = 0
    for key in cue_keys:
        pos = cues.get(key, len(narr))
        scene_texts[labels[idx]] = narr[prev:pos].strip('，。、；：！？,.;:!? ')
        prev = pos
        idx += 1
    scene_texts[labels[idx]] = narr[prev:].strip('，。、；：！？,.;:!? ')

    return narr, timing, scene_texts


# ── HTML ───────────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitHub Trending · Video Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #fafaf8; --surface: #ffffff; --elevated: #f3f3f0;
  --border: #e4e4df; --border-light: #d8d8d2;
  --gold: #c8880a; --gold-dim: #a07008; --amber: #d97706;
  --text: #1a1a1e; --text-secondary: #5e5e68; --text-muted: #94949e;
  --accent: #4f46e5; --green: #16a34a; --red: #dc2626;
  --radius: 12px; --radius-sm: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'DM Sans', -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}
body::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(79,70,229,0.04), transparent),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(200,136,10,0.03), transparent);
}

/* ── Header ──────────────────────────── */
header {
  position: sticky; top: 0; z-index: 100;
  backdrop-filter: blur(20px) saturate(180%);
  background: rgba(250,250,248,0.88);
  border-bottom: 1px solid var(--border);
  padding: 16px 32px;
  display: flex; align-items: center; gap: 16px;
}
header .logo {
  font-family: 'DM Serif Display', serif;
  font-size: 20px; font-weight: 400; letter-spacing: -0.01em;
  background: linear-gradient(135deg, var(--gold) 0%, var(--amber) 50%, #fbbf24 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
header .sep { width: 1px; height: 24px; background: var(--border); }
header .page-title { font-size: 13px; color: var(--text-secondary); font-weight: 500; }
header .actions { margin-left: auto; display: flex; gap: 8px; }

/* ── Buttons ─────────────────────────── */
.btn {
  font-family: 'DM Sans', sans-serif;
  padding: 10px 20px; border-radius: var(--radius-sm); border: 1px solid var(--border-light);
  font-size: 13px; font-weight: 500; cursor: pointer;
  transition: all 0.2s ease;
  background: var(--elevated); color: var(--text);
  letter-spacing: 0.01em;
}
.btn:hover { border-color: var(--text-secondary); transform: translateY(-1px); box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
.btn:active { transform: translateY(0); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; box-shadow: none; }
.btn-sm { padding: 7px 14px; font-size: 12px; }
.btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); }
.btn-primary:hover { box-shadow: 0 4px 20px rgba(79,70,229,0.2); }
.btn-success { background: var(--green); color: #fff; border-color: var(--green); font-weight: 600; }
.btn-success:hover { box-shadow: 0 4px 20px rgba(22,163,74,0.2); }
.btn-gold { background: var(--gold); color: #fff; border-color: transparent; font-weight: 600; }
.btn-gold:hover { box-shadow: 0 4px 20px rgba(200,136,10,0.25); }
.btn-ghost { background: transparent; border-color: transparent; color: var(--text-secondary); }
.btn-ghost:hover { background: var(--elevated); border-color: var(--border); }

/* ── Status Bar ──────────────────────── */
.status-bar {
  position: fixed; bottom: 0; width: 100%; z-index: 100;
  padding: 10px 32px; font-size: 12px; color: var(--text-muted);
  display: flex; align-items: center; gap: 10px;
  backdrop-filter: blur(20px);
  background: rgba(250,250,248,0.88);
  border-top: 1px solid var(--border);
}
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); flex-shrink: 0; transition: all 0.3s; }
.dot.active { background: var(--green); box-shadow: 0 0 8px rgba(34,197,94,0.5); }
.dot.error { background: var(--red); box-shadow: 0 0 8px rgba(239,68,68,0.5); }

/* ── List View ───────────────────────── */
#listView { padding: 40px 32px; max-width: 1320px; margin: 0 auto; position: relative; z-index: 1; }
.list-header { margin-bottom: 32px; }
.list-header h2 { font-family: 'DM Serif Display', serif; font-size: 36px; font-weight: 400; letter-spacing: -0.02em; margin-bottom: 6px; }
.list-header .subtitle { color: var(--text-secondary); font-size: 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 18px; }
.repo-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 24px;
  display: flex; flex-direction: column; gap: 14px;
  transition: all 0.25s ease;
  position: relative; overflow: hidden;
}
.repo-card::before {
  content: ''; position: absolute; inset: 0; opacity: 0; transition: opacity 0.25s;
  background: radial-gradient(ellipse at 0% 0%, rgba(79,70,229,0.05), transparent 70%);
}
.repo-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.06); }
.repo-card:hover::before { opacity: 1; }
.repo-card .r-name {
  font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 600;
  color: var(--text); position: relative; z-index: 1;
}
.repo-card .r-owner { font-size: 12px; color: var(--text-muted); margin-top: -8px; position: relative; z-index: 1; }
.repo-card .r-desc { font-size: 13px; color: var(--text-secondary); line-height: 1.6; flex: 1; position: relative; z-index: 1; }
.repo-card .r-stats { display: flex; gap: 16px; align-items: center; font-size: 12px; color: var(--text-muted); position: relative; z-index: 1; }
.repo-card .r-stats .stat { display: flex; align-items: center; gap: 4px; }
.repo-card .r-stats .stat.stars { color: var(--gold); font-weight: 600; }
.repo-card .r-lang {
  font-size: 10px; padding: 2px 10px; border-radius: 20px;
  background: rgba(79,70,229,0.08); color: var(--accent);
  font-weight: 500; letter-spacing: 0.03em; text-transform: uppercase;
}
.repo-card .r-action { position: relative; z-index: 1; }

/* ── Editor View ─────────────────────── */
#editorView { display: none; padding: 32px; max-width: 1440px; margin: 0 auto; position: relative; z-index: 1; }
.back-row { margin-bottom: 20px; }
.editor-grid { display: grid; grid-template-columns: 1fr 1.6fr; gap: 24px; margin-bottom: 32px; }
.panel {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 24px;
}
.panel-hd { font-family: 'DM Sans', sans-serif; font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.panel-hd::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.shot-wrap { margin-bottom: 14px; }
.shot-label { font-size: 10px; color: var(--text-muted); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.shot-label .dot-indicator { width: 6px; height: 6px; border-radius: 50%; }
.shot-label .dot-indicator.top { background: var(--gold); }
.shot-label .dot-indicator.intro { background: var(--accent); }
.screenshot-img { width: 100%; border-radius: var(--radius-sm); border: 1px solid var(--border); transition: box-shadow 0.2s; }
.screenshot-img:hover { box-shadow: 0 0 0 2px var(--accent); }
.meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.meta-cell {
  background: var(--elevated); border-radius: var(--radius-sm); padding: 14px 16px;
  border: 1px solid transparent; transition: border-color 0.2s;
}
.meta-cell:hover { border-color: var(--border); }
.meta-cell .m-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; font-weight: 600; }
.meta-cell .m-value { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 600; color: var(--text); }
.meta-cell .m-value.gold { color: var(--gold); }
.feature-edit { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.feature-row { display: flex; gap: 8px; align-items: center; }
.feature-row input {
  background: var(--elevated); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); padding: 8px 10px;
  font-size: 12px; font-family: 'DM Sans', sans-serif;
  transition: border-color 0.2s;
}
.feature-row input:focus { border-color: var(--accent); outline: none; }
.feature-row input.f-icon { width: 42px; text-align: center; font-size: 16px; }
.feature-row input.f-name { width: 140px; font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.feature-row input.f-desc { flex: 1; }
.action-bar { display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }
audio { width: 100%; margin-top: 14px; border-radius: var(--radius-sm); }
.empty-state { color: var(--text-muted); text-align: center; padding: 80px 20px; }
.empty-state .empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.4; }
.empty-state h3 { font-size: 18px; margin-bottom: 6px; color: var(--text-secondary); }

/* ── Scene Rows (right panel) ────────── */
.scene-row {
  background: var(--elevated); border-radius: var(--radius-sm);
  overflow: hidden; transition: border-color 0.2s;
}
.scene-row:hover { background: var(--surface); }
.scene-row .sc-row-hd {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
}
.scene-row .sc-row-num {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 700;
  padding: 2px 8px; border-radius: 4px; flex-shrink: 0;
}
.scene-row .sc-row-name { font-size: 12px; font-weight: 600; color: var(--text); }
.scene-row .sc-row-time { margin-left: auto; font-size: 10px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }
.scene-row .sc-row-body { display: flex; gap: 10px; padding: 0 12px 10px 12px; align-items: flex-start; }
.scene-row .sc-row-thumb { width: 80px; height: 48px; object-fit: cover; border-radius: 4px; flex-shrink: 0; border: 1px solid var(--border); }
.scene-row .sc-row-text {
  flex: 1; min-height: 48px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); padding: 8px 10px; font-size: 12px;
  resize: vertical; font-family: 'DM Sans', sans-serif; line-height: 1.5;
  transition: border-color 0.2s;
}
.scene-row .sc-row-text:focus { border-color: var(--accent); outline: none; }

@keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
/* Modal */
.modal-overlay { display:none; position:fixed; inset:0; z-index:1000; background:rgba(0,0,0,0.5); backdrop-filter:blur(4px); justify-content:center; align-items:center; }
.modal-overlay.show { display:flex; }
.modal-box { background:var(--surface); border-radius:var(--radius); padding:40px 56px; text-align:center; box-shadow:0 20px 60px rgba(0,0,0,0.2); max-width:480px; }
.modal-box .modal-icon { font-size:40px; margin-bottom:16px; animation:spin 2s linear infinite; }
.modal-box .modal-title { font-family:'DM Serif Display',serif; font-size:20px; margin-bottom:8px; color:var(--text); }
.modal-box .modal-sub { font-size:13px; color:var(--text-secondary); }
@keyframes spin { 100% { transform:rotate(360deg); } }
</style>
</head>
<body>

<header>
  <div class="logo">Trending Studio</div>
  <div class="sep"></div>
  <span class="page-title" id="pageTitle">Projects</span>
  <div class="actions">
    <button class="btn btn-sm btn-ghost" id="btnRefresh" onclick="refreshTrending()">↻ Refresh</button>
  </div>
</header>

<!-- ─── LIST VIEW ──────────────────────────────────────────────── -->
<div id="listView">
  <div class="list-header">
    <h2>Trending Projects</h2>
    <p class="subtitle">Select a repository to produce a promotional video</p>
  </div>
  <div id="listContent">
    <div class="empty-state"><div class="empty-icon">📡</div><h3>No data yet</h3><p>Click Refresh to fetch GitHub Trending</p></div>
  </div>
</div>

<!-- ─── EDITOR VIEW ─────────────────────────────────────────────── -->
<div id="editorView">
  <div class="back-row">
    <button class="btn btn-sm btn-ghost" onclick="showList()">← Back to Projects</button>
  </div>
  <div class="editor-grid">
    <!-- Left: Screenshots -->
    <div class="panel">
      <div class="panel-hd">Screenshots</div>
      <div class="shot-wrap">
        <div class="shot-label"><span class="dot-indicator top"></span> Top · Header & Stars</div>
        <img class="screenshot-img" id="screenshotTop" src="" alt="Top" onerror="this.style.display='none'">
      </div>
      <div class="shot-wrap">
        <div class="shot-label"><span class="dot-indicator intro"></span> Intro · README</div>
        <img class="screenshot-img" id="screenshotIntro" src="" alt="Intro" onerror="this.style.display='none'">
      </div>
      <div id="noScreenshot" style="color:var(--text-muted);padding:30px;text-align:center;font-size:13px">No screenshots yet</div>
      <div style="margin-top:16px">
        <button class="btn btn-sm btn-gold" id="btnScreenshot" onclick="takeScreenshot()">Take Screenshots</button>
      </div>
    </div>

    <!-- Right: Project info + Features + Scene Timeline + Actions -->
    <div class="panel" style="display:flex;flex-direction:column">
      <div class="panel-hd">Project · <span id="repoBadge" style="text-transform:none;font-weight:400">—</span></div>
      <div class="meta-grid" id="meta"></div>

      <div class="panel-hd">Features</div>
      <div class="feature-edit" id="featuresEdit"></div>

      <div class="panel-hd" style="margin-top:8px">Scene Narration <span style="text-transform:none;font-weight:400;color:var(--text-muted)">— edit text for voice</span></div>
      <div id="sceneTimeline" style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;min-height:200px"></div>
      <div class="action-bar" style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">
        <button class="btn btn-primary" id="btnGenerate" onclick="generateAudio()">Generate Voice</button>
        <button class="btn" id="btnPreview" onclick="previewRemotion()">Preview</button>
        <button class="btn btn-success" id="btnBuild" onclick="buildVideo()">Build Video</button>
      </div>
      <audio id="audioPlayer" controls style="display:none;margin-top:12px"></audio>
    </div>
  </div>
</div>

<div class="status-bar">
  <span class="dot" id="statusDot"></span>
  <span id="statusText">Ready</span>
</div>

<!-- Modal overlay -->
<div class="modal-overlay" id="modalOverlay">
  <div class="modal-box">
    <div class="modal-icon">🎙️</div>
    <div class="modal-title" id="modalTitle">Generating Voice</div>
    <div class="modal-sub" id="modalSub">Once finished, Remotion Studio will open automatically</div>
  </div>
</div>

<script>
const SERVER_IP = '__SERVER_IP__';
let props = {};
let currentView = 'list';

function setStatus(msg, type) {
  document.getElementById('statusText').textContent = msg;
  const dot = document.getElementById('statusDot');
  dot.className = 'dot' + (type === 'error' ? ' error' : type === 'active' ? ' active' : '');
}

// ── View switching ──────────────────────────────────────────────
function showList() {
  currentView = 'list';
  document.getElementById('listView').style.display = 'block';
  document.getElementById('editorView').style.display = 'none';
  document.querySelector('.page-title').textContent = 'Projects';
  const url = new URL(window.location);
  url.searchParams.delete('repo');
  window.history.pushState({}, '', url);
  loadTrending();
}

function showEditor(repo) {
  currentView = 'editor';
  document.getElementById('listView').style.display = 'none';
  document.getElementById('editorView').style.display = 'block';
  document.querySelector('.page-title').textContent = repo.split('/').pop();
  const url = new URL(window.location);
  url.searchParams.set('repo', repo);
  window.history.pushState({}, '', url);
  selectProject(repo);
}

// ── List: load trending ─────────────────────────────────────────
async function loadTrending() {
  try {
    const r = await fetch('/api/trending');
    const repos = await r.json();
    if (!repos.length) {
      document.getElementById('listContent').innerHTML = '<div class="empty"><h3>No data</h3><p>Click "Refresh Trending" to fetch data</p></div>';
      return;
    }
    let html = '<div class="grid">';
    repos.forEach((repo, idx) => {
      const stars = repo.stars_weekly !== '?' ? repo.stars_weekly : '';
      const shortName = repo.full_name.split('/').pop();
      html += '<div class="repo-card" style="animation: fadeUp 0.4s ' + (idx * 0.06) + 's both">' +
        '<div class="r-name">' + esc(shortName) + '</div>' +
        '<div class="r-owner">' + esc(repo.full_name) + '</div>' +
        '<div class="r-desc">' + esc(repo.description || 'No description') + '</div>' +
        '<div class="r-stats">' +
          (stars ? '<span class="stat stars">⭐ ' + esc(stars) + ' /wk</span>' : '') +
          '<span class="stat">⭐ ' + esc(repo.stars_total || '?') + '</span>' +
          '<span class="r-lang">' + esc(repo.language || '?') + '</span>' +
        '</div>' +
        '<div class="r-action">' +
          '<button class="btn btn-sm btn-primary" onclick="showEditor(\'' + esc(repo.full_name) + '\')">Generate Video</button>' +
        '</div>' +
      '</div>';
    });
    html += '</div>';
    document.getElementById('listContent').innerHTML = html;
  } catch(e) {
    setStatus('Failed to load trending: ' + e.message, 'error');
  }
}

async function refreshTrending() {
  const btn = document.getElementById('btnRefresh');
  btn.disabled = true; btn.textContent = 'Fetching...';
  setStatus('Fetching GitHub Trending...', 'active');
  try {
    await fetch('/api/trending/fetch');
    // Poll for completion
    const interval = setInterval(async () => {
      const r = await fetch('/api/trending');
      const repos = await r.json();
      if (repos.length > 0) {
        clearInterval(interval);
        btn.disabled = false; btn.textContent = 'Refresh Trending';
        setStatus('Fetched ' + repos.length + ' projects', 'active');
        loadTrending();
      }
    }, 2000);
    setTimeout(() => { clearInterval(interval); btn.disabled = false; btn.textContent = 'Refresh Trending'; }, 30000);
  } catch(e) {
    setStatus('Fetch failed: ' + e.message, 'error');
    btn.disabled = false; btn.textContent = 'Refresh Trending';
  }
}

// ── Editor: select & load project ────────────────────────────────
async function selectProject(repo) {
  setStatus('Fetching repo details...', 'active');
  // Find weekly stars from trending data
  let starsWeekly = '?';
  try {
    const r = await fetch('/api/trending');
    const repos = await r.json();
    const found = repos.find(x => x.full_name === repo);
    if (found) starsWeekly = found.stars_weekly || '?';
  } catch(e) {}

  try {
    const r = await fetch('/api/select-project', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({repo, stars_weekly: starsWeekly})
    });
    if (!r.ok) throw new Error((await r.json()).detail);
    props = await r.json();
    renderEditor();
    setStatus('Ready', '');
    // Auto-take screenshot
    setTimeout(() => takeScreenshot(), 500);
  } catch(e) {
    setStatus('Error: ' + e.message, 'error');
  }
}

function renderEditor() {
  const displayName = (props.name || props.repo || '').split('/').pop();
  document.getElementById('repoBadge').textContent = displayName;
  document.querySelector('.page-title').textContent = displayName;

  if (props.screenshot) {
    document.getElementById('screenshotTop').src = '/public/' + props.screenshot;
    document.getElementById('screenshotTop').style.display = 'block';
    document.getElementById('noScreenshot').style.display = 'none';
  } else {
    document.getElementById('screenshotTop').style.display = 'none';
    document.getElementById('noScreenshot').style.display = 'block';
  }
  if (props.screenshotIntro) {
    document.getElementById('screenshotIntro').src = '/public/' + props.screenshotIntro;
    document.getElementById('screenshotIntro').style.display = 'block';
  } else {
    document.getElementById('screenshotIntro').style.display = 'none';
  }

  let meta = '';
  if (props.totalStars) meta += '<div class="meta-cell"><div class="m-label">Total Stars</div><div class="m-value gold">⭐ ' + esc(props.totalStars) + '</div></div>';
  if (props.weeklyStars) meta += '<div class="meta-cell"><div class="m-label">This Week</div><div class="m-value">🔥 +' + esc(props.weeklyStars) + '</div></div>';
  if (props.language) meta += '<div class="meta-cell"><div class="m-label">Language</div><div class="m-value">' + esc(props.language) + '</div></div>';
  if (props.author) meta += '<div class="meta-cell"><div class="m-label">Author</div><div class="m-value" style="font-size:14px">' + esc(props.author) + '</div></div>';
  if (props.chineseDesc) meta += '<div class="meta-cell" style="grid-column:1/-1"><div class="m-label">Introduction</div><div class="m-value" style="font-size:12px;font-weight:400;font-family:\'DM Sans\',sans-serif">' + esc(props.chineseDesc) + '</div></div>';
  document.getElementById('meta').innerHTML = meta;

  // Editable features
  let featsHtml = '';
  (props.features || []).forEach((f, i) => {
    featsHtml += '<div class="feature-row">' +
      '<input class="f-icon" value="' + esc(f.icon || '') + '" onchange="updateFeature(' + i + ', \'icon\', this.value)">' +
      '<input class="f-name" value="' + esc(f.name || '') + '" onchange="updateFeature(' + i + ', \'name\', this.value)">' +
      '<input class="f-desc" value="' + esc(f.desc || '') + '" onchange="updateFeature(' + i + ', \'desc\', this.value)">' +
    '</div>';
  });
  document.getElementById('featuresEdit').innerHTML = featsHtml;

  // Audio player
  if (props.audio) {
    const player = document.getElementById('audioPlayer');
    player.src = '/public/' + props.audio;
    player.style.display = 'block';
  }

  // Render scene timeline
  renderSceneTimeline();
}

function getSceneTexts() {
  const narration = props.narration || '';
  const timing = props.narrationTiming || {};
  // New cue names: s2_project, s3_screenshot, s4_starzoom, s5_intro, s6_features, s7_outro
  const keys = ['s2_project', 's3_screenshot', 's4_starzoom', 's5_intro', 's6_features', 's7_outro'];
  const positions = keys.map(k => Math.floor((timing[k] || 0) * narration.length)).filter(p => p > 0);

  let prev = 0;
  const parts = [];
  for (const pos of positions) {
    parts.push(narration.slice(prev, pos).trim());
    prev = pos;
  }
  parts.push(narration.slice(prev).trim());

  // Strip leading/trailing punctuation from each part
  const stripPunct = (s) => s.replace(/^[，。、；：！？,.;:!?\s]+|[，。、；：！？,.;:!?\s]+$/g, '').trim();

  return {
    s1: stripPunct(parts[0]) || '今天介绍的 GitHub 热门项目是',
    s2: stripPunct(parts[1]) || '',
    s3: stripPunct(parts[2]) || '',
    s4: stripPunct(parts[3]) || '',
    s5: stripPunct(parts[4]) || '',
    s6: stripPunct(parts[5]) || '',
    s7: stripPunct(parts[6]) || '关注我，获得最新的实用项目信息',
  };
}

function renderSceneTimeline() {
  const totalSec = props.durationSeconds || 30;
  const T = totalSec * 30;
  const timing = props.narrationTiming || {};
  const texts = getSceneTexts();

  const sceneColors = ['#6366f1','#8b5cf6','#f0c040','#ef4444','#3b82f6','#22c55e','#6366f1'];
  const sceneNames = ['Opening','Project Card','Screenshot','Star Zoom','Intro README','Features','Outro'];
  const scenes = [
    { start:0, end:80, img:null, text:texts.s1 },
    { start:70, end:150, img:null, text:props.name||'project' },
    { start:135, end:280, img:props.screenshot, text:texts.s3 },
    { start:260, end:360, img:props.screenshot, text:texts.s4 },
    { start:300, end:Math.floor(T*0.88), img:props.screenshotIntro, text:texts.s5 },
    { start:Math.floor(T*0.86), end:Math.floor(T*0.95), img:props.screenshotIntro, text:texts.s6 },
    { start:Math.floor(T*0.93), end:T, img:null, text:texts.s7 },
  ];

  let html = '';
  scenes.forEach((s, i) => {
    const imgSrc = s.img ? '/public/' + s.img : '';
    const secStart = (s.start / 30).toFixed(1);
    const secEnd = (s.end / 30).toFixed(1);
    const c = sceneColors[i];
    html += '<div class="scene-row" style="border-left:3px solid ' + c + '">' +
      '<div class="sc-row-hd">' +
        '<span class="sc-row-num" style="background:' + c + '15;color:' + c + '">S' + (i+1) + '</span>' +
        '<span class="sc-row-name">' + sceneNames[i] + '</span>' +
        '<span class="sc-row-time">' + secStart + 's → ' + secEnd + 's</span>' +
      '</div>' +
      '<div class="sc-row-body">' +
        (imgSrc ? '<img class="sc-row-thumb" src="' + imgSrc + '" onerror="this.style.display=\'none\'">' : '') +
        '<textarea class="sc-row-text" id="sceneText_' + i + '" onchange="updateSceneText()" rows="2">' + esc(s.text) + '</textarea>' +
      '</div>' +
    '</div>';
  });
  document.getElementById('sceneTimeline').innerHTML = html;
}

function collectNarration() {
  // Collect all scene texts into one narration string
  const texts = [];
  for (let i = 0; i < 7; i++) {
    const el = document.getElementById('sceneText_' + i);
    if (el && el.value.trim()) texts.push(el.value.trim());
  }
  return texts.join('');
}

function updateSceneText() {
  props.narration = collectNarration();
}

function updateFeature(i, field, value) {
  if (props.features && props.features[i]) {
    props.features[i][field] = value;
  }
}

// ── Editor: actions ──────────────────────────────────────────────
async function takeScreenshot() {
  const btn = document.getElementById('btnScreenshot');
  btn.disabled = true; btn.textContent = 'Capturing...';
  setStatus('Taking screenshots via CDP...', 'active');
  try {
    const r = await fetch('/api/screenshot', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({repo: props.repo})
    });
    const data = await r.json();
    if (data.success) {
      props.screenshot = data.top.split('/').pop();
      props.screenshotIntro = data.intro ? data.intro.split('/').pop() : null;
      document.getElementById('screenshotTop').src = data.top;
      document.getElementById('screenshotTop').style.display = 'block';
      if (data.intro) {
        document.getElementById('screenshotIntro').src = data.intro;
        document.getElementById('screenshotIntro').style.display = 'block';
      }
      document.getElementById('noScreenshot').style.display = 'none';
      setStatus('Screenshots captured' + (data.star_pos ? ', star position found' : ''), 'active');
    } else {
      setStatus('Screenshot failed: ' + (data.error || 'unknown'), 'error');
    }
  } catch(e) { setStatus(e.message, 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Take Screenshots'; }
}

async function generateAudio() {
  const btn = document.getElementById('btnGenerate');
  btn.disabled = true; btn.textContent = 'Generating...';
  setStatus('Generating voiceover via VoxCPM...', 'active');
  try {
    // Save current props (including edited narration and features)
    props.narration = collectNarration();
    await fetch('/api/save-props', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(props)
    });

    const r = await fetch('/api/generate-audio', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: props.narration, repo: props.repo, scene_texts: props.sceneTexts || {}})
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    const data = await r.json();
    props.audio = data.path.split('/').pop();
    const player = document.getElementById('audioPlayer');
    player.src = data.path;
    player.style.display = 'block';
    player.play();
    setStatus('Voiceover ready (' + data.duration.toFixed(1) + 's)', 'active');
  } catch(e) { setStatus(e.message, 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Generate Voice'; }
}

async function previewRemotion() {
  const modal = document.getElementById('modalOverlay');
  const modalTitle = document.getElementById('modalTitle');
  const modalSub = document.getElementById('modalSub');

  modal.classList.add('show');
  modalTitle.textContent = 'Generating Voice';
  modalSub.textContent = 'Once finished, Remotion Studio will open automatically';
  setStatus('Preparing preview...', 'active');

  try {
    props.narration = collectNarration();
    await fetch('/api/save-props', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(props)
    });

    // Always regenerate audio for fresh preview
    try {
      const audioR = await fetch('/api/generate-audio', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: props.narration, repo: props.repo, scene_texts: props.sceneTexts || {}})
      });
      if (audioR.ok) {
        const audioData = await audioR.json();
        props.audio = audioData.path.split('/').pop();
        document.getElementById('audioPlayer').src = audioData.path;
        document.getElementById('audioPlayer').style.display = 'block';
        setStatus('Voiceover ready (' + audioData.duration.toFixed(1) + 's)', 'active');
      }
    } catch(e) {
      setStatus('Voice generation failed, continuing without audio: ' + e.message, 'error');
    }

    // Start/check Remotion Studio
    modalTitle.textContent = 'Starting Remotion';
    modalSub.textContent = 'Launching studio...';
    setStatus('Checking Remotion Studio...', 'active');
    const statusR = await fetch('/api/remotion/status');
    const status = await statusR.json();
    if (!status.running) {
      const startR = await fetch('/api/remotion/start', {method: 'POST'});
      const start = await startR.json();
      if (!start.started) {
        modal.classList.remove('show');
        setStatus('Failed to start Remotion Studio', 'error');
        return;
      }
      for (let i = 0; i < 15; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const check = await fetch('/api/remotion/status');
        const s = await check.json();
        if (s.running) break;
      }
    }

    // Small delay to ensure files are synced
    await new Promise(r => setTimeout(r, 1500));
    modal.classList.remove('show');
    setStatus('Opening Remotion Studio...', 'active');
    window.open('http://' + window.location.hostname + ':3000?t=' + Date.now(), '_blank');
  } catch(e) {
    modal.classList.remove('show');
    setStatus('Remotion: ' + e.message, 'error');
  }
}

async function buildVideo() {
  const btn = document.getElementById('btnBuild');
  btn.disabled = true; btn.textContent = 'Building...';
  const modal = document.getElementById('modalOverlay');
  const modalTitle = document.getElementById('modalTitle');
  const modalSub = document.getElementById('modalSub');

  modal.classList.add('show');
  modalTitle.textContent = 'Building Video';
  modalSub.textContent = 'Generating voiceover and rendering...';
  setStatus('Preparing build...', 'active');

  // Save edits
  props.narration = collectNarration();
  await fetch('/api/save-props', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(props)
  });

  // Always generate audio before building
  try {
    const audioR = await fetch('/api/generate-audio', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: props.narration, repo: props.repo, scene_texts: props.sceneTexts || {}})
    });
    if (audioR.ok) {
      const audioData = await audioR.json();
      props.audio = audioData.path ? audioData.path.split('/').pop() : props.audio;
      props.durationSeconds = audioData.duration;
      props.sceneDurations = audioData.sceneDurations;
      setStatus('Voiceover ready (' + audioData.duration.toFixed(1) + 's)', 'active');
    }
  } catch(e) {
    setStatus('Voice gen failed, building without audio: ' + e.message, 'error');
  }

  setStatus('Starting render...', 'active');
  modalTitle.textContent = 'Rendering Video';
  modalSub.textContent = 'This may take a few minutes...';
  try {
    const safeName = (props.repo || 'repo').replace(/[\\/]/g, '-');
    const r = await fetch('/api/build-video', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({output_name: safeName + '-promo.mp4', props})
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    pollRenderStatus();
  } catch(e) { setStatus(e.message, 'error'); btn.disabled = false; btn.textContent = 'Build Video'; }
}

function pollRenderStatus() {
  const interval = setInterval(async () => {
    try {
      const r = await fetch('/api/render-status');
      const data = await r.json();
      setStatus(data.progress, data.running ? 'active' : (data.output ? 'active' : 'error'));
      if (!data.running) {
        clearInterval(interval);
        document.getElementById('modalOverlay').classList.remove('show');
        document.getElementById('btnBuild').disabled = false;
        document.getElementById('btnBuild').textContent = 'Build Video';
      }
    } catch(e) {}
  }, 2000);
}

function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }

// Init — auto-load project from URL param
(function() {
  const params = new URLSearchParams(window.location.search);
  const repo = params.get('repo');
  if (repo) {
    showEditor(repo);
  } else {
    loadTrending();
  }
})();
</script>
</body>
</html>"""

# ── Pages ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_TEMPLATE


@app.get("/editor", response_class=HTMLResponse)
def editor_page():
    return HTML_TEMPLATE


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Video Production Dashboard")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    args = parser.parse_args()

    server_ip = get_server_ip()
    # Replace placeholder in HTML template with actual server IP
    global HTML_TEMPLATE
    HTML_TEMPLATE = HTML_TEMPLATE.replace("__SERVER_IP__", server_ip)

    print(f"Dashboard: http://{server_ip}:{args.port}  (local: http://localhost:{args.port})")

    # Start Remotion Studio in background
    if not is_remotion_running():
        print("Starting Remotion Studio...")
        threading.Thread(target=start_remotion, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
