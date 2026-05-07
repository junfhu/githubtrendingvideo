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
    intro_heading = ""
    intro_heading_index = 0
    s6_content = ""
    s6_heading = ""
    s6_heading_index = 0
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

        # S6 fallback: if features lack substance, extract "How It Works" instead
        substantial = [f for f in features if len(f.get("desc", "")) > 15]
        if len(substantial) < 3:
            s6_data = extract_how_it_works(readme_text)
            if s6_data.get("text"):
                s6_content = s6_data["text"]
                s6_heading = s6_data["heading"]
                s6_heading_index = s6_data["heading_index"]
                print(f"S6 using How-It-Works: heading={s6_heading}, index={s6_heading_index}")

        desc_data = extract_chinese_description(readme_text, description, topics)
        chinese_desc = desc_data.get("text", "") if isinstance(desc_data, dict) else desc_data
        intro_heading = desc_data.get("heading", "") if isinstance(desc_data, dict) else ""
        intro_heading_index = desc_data.get("heading_index", 0) if isinstance(desc_data, dict) else 0
    except Exception as e:
        print(f"README fetch error: {e}")

    # Try to fetch community profile for more metadata
    try:
        github_api_get(f"repos/{owner}/{name}/community/profile")
    except Exception:
        pass

    # Generate narration with timing cues
    weekly_stars = data.get("stars_weekly", "?")
    weekly_stars_clean = weekly_stars if weekly_stars and weekly_stars not in ('?', '0') else ''
    narration, timing, scene_texts = generate_narration(name, weekly_stars_clean, total_stars, language, chinese_desc or description, features, s6_content)

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
        "s6Content": s6_content,
        "s6Heading": s6_heading,
        "s6HeadingIndex": s6_heading_index,
        "s6Screenshot": "",
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
    s6_heading = data.get("s6_heading", "")
    s6_heading_index = data.get("s6_heading_index", 0)
    if not target_heading:
        props_file = os.path.join(REMOTION_DIR, "props.json")
        if os.path.exists(props_file):
            with open(props_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
            target_heading = existing.get("screenshotIntroHeading", "")
            target_heading_index = existing.get("screenshotIntroHeadingIndex", 0)
            s6_heading = existing.get("s6Heading", "")
            s6_heading_index = existing.get("s6HeadingIndex", 0)

    cmd = [sys.executable, script, url, base_name]
    if target_heading:
        cmd.extend(["--heading", target_heading])
    if target_heading_index:
        cmd.extend(["--heading-index", str(target_heading_index)])
    if s6_heading:
        cmd.extend(["--s6-heading", s6_heading])
    if s6_heading_index:
        cmd.extend(["--s6-heading-index", str(s6_heading_index)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        top_name = None
        intro_name = None
        s6_name = None
        intro_height = None
        s6_height = None
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
            elif line.startswith("S6_H:"):
                try:
                    s6_height = int(line.split("S6_H:", 1)[1].strip())
                except Exception:
                    pass
            elif line.startswith("S6:"):
                s6_name = line.split("S6:", 1)[1].strip()
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
                if s6_name:
                    props["s6Screenshot"] = s6_name
                if intro_height:
                    props["screenshotIntroHeight"] = intro_height
                if s6_height:
                    props["s6ScreenshotHeight"] = s6_height
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

    # Use exact per-scene audio durations — discard combined file, concatenate scenes instead.
    # This guarantees each scene visual aligns perfectly with its audio.
    for s in ['s1', 's2', 's3', 's4', 's5', 's6', 's7']:
        if s not in durations:
            durations[s] = 2.0

    total_dur = sum(durations[s] for s in ['s1', 's2', 's3', 's4', 's5', 's6', 's7'])
    # Concatenate per-scene WAVs using Python's wave module (ffmpeg concat produces broken headers)
    import wave as _wave
    combined_path = os.path.join(PUBLIC_DIR, combined_name)
    scene_order = ['s1', 's2', 's3', 's4', 's5', 's6', 's7']
    wav_readers = []
    total_frames = 0
    params = None
    for s in scene_order:
        wav_path = os.path.join(PUBLIC_DIR, f"narration_{safe_name}_{s}.wav")
        if os.path.exists(wav_path):
            wf = _wave.open(wav_path, 'rb')
            wav_readers.append(wf)
            total_frames += wf.getnframes()
            if params is None:
                params = wf.getparams()
    if wav_readers and params:
        with _wave.open(combined_path, 'wb') as out:
            out.setparams(params)
            out.setnframes(total_frames)
            for wf in wav_readers:
                wf.rewind()
                out.writeframes(wf.readframes(wf.getnframes()))
                wf.close()
        print(f"Concatenated {len(wav_readers)} scene WAVs → {combined_path} ({total_frames} frames, {total_dur:.1f}s)")
    else:
        print("WARNING: no scene WAVs found, keeping TTS combined file")

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
    """Remove HTML tags and entities, keeping only readable content."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<(?:br|p|/p|/div|/li|/tr)\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'")
    text = text.replace("&nbsp;", " ").replace("&#x27;", "'")
    text = re.sub(r"&#?\w+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_md(text):
    """Strip markdown formatting and HTML tags from text."""
    text = _strip_html(text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_heading(text):
    """Strip emoji, markdown formatting, and extra whitespace from a heading."""
    import re as _re
    # Remove emoji and special unicode symbols
    text = _re.sub(r'[\U0001F300-\U0001F9FF☀-➿⭐✅❌✨❤⬆→➡⚙⚡✨]', '', text)
    text = _re.sub(r'[^\w\s一-鿿぀-ゟ゠-ヿ가-힯\-\(\)\[\]{}.,;:!?@#\$%^&*+=/\\|~`\'"]', '', text)
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

    # ── Pass 1: find best matching section by priority ──
    # Collect ALL h2 sections with scores
    sections = []  # [(heading_text, heading_index, lines_list, score)]
    h2_count = 0
    current_heading = ""
    current_lines = []

    def _finish_section():
        nonlocal current_heading, current_lines
        if current_lines and current_heading:
            text = _clean_md(" ".join(current_lines))
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
                    sections.append((current_heading, h2_count, text, score, len(text)))
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
            current_lines.append(stripped)
            if len(current_lines) > 30:  # Cap per section
                break

    _finish_section()

    # Pick the best section: prefer value (score 10) with most content
    sections.sort(key=lambda s: (s[3], s[4]), reverse=True)
    if sections:
        best = sections[0]
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
    categories = []
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
    """Extract 'How It Works' / workflow section for S6 fallback.

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


def generate_narration(name, weekly_stars, total_stars, language, description, features, s6_text=""):
    # Build narration with per-scene timing cues
    parts = []
    cues = {}

    # S1: Opening (fixed)
    p1 = "今天介绍的 GitHub 热门项目是"
    parts.append(p1)
    cues["s2_project"] = len("".join(parts))  # S1→S2 transition

    # S2: Project name (visual only, name spoken as part of flow)
    p2 = f" {name}。"

    has_weekly = weekly_stars and weekly_stars not in ('?', '0')
    if has_weekly:
        parts.append(p2)
        cues["s3_screenshot"] = len("".join(parts))
        # S3: Weekly stars
        p3 = f"本周获得{weekly_stars}颗星。"
        parts.append(p3)
        cues["s4_starzoom"] = len("".join(parts))
        # S4: Total stars
        p4 = f"，总计{total_stars}颗星。"
        parts.append(p4)
    else:
        # No weekly data — S3 uses total stars, S4 is visual-only (star zoom)
        parts.append(p2)
        cues["s3_screenshot"] = len("".join(parts))
        # S3: Total stars
        p3 = f"总计{total_stars}颗星。"
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
    cues["s6_features"] = len("".join(parts))  # S5→S6

    # S6: Features — or "How It Works" fallback
    if s6_text:
        parts.append(s6_text.rstrip("。；") + "。")
    elif features:
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
