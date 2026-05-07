r"""Build a Remotion promo video for a GitHub repo.

Usage:
  python build_video.py --repo "owner/name" --total-stars "12,345" --weekly-stars "678" \
      --language Python --desc "Project description" --author "Author Name" \
      --author-title "Role" --output "output.mp4"
"""

import argparse, json, os, subprocess, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
REMOTION_DIR = os.path.join(SKILL_DIR, "remotion")
PUBLIC_DIR = os.path.join(REMOTION_DIR, "public")
OUTPUT_BASE = os.path.join(os.path.expanduser("~"), "Daily Notes", "GitHub Trending")
REF_AUDIO = os.path.join(SKILL_DIR, "remotion", "public", "reference.wav")
MODEL_PATH = os.path.join(os.path.expanduser("~"), "voxcpm", "pretrained_models", "VoxCPM2")

DEFAULT_FEATURES = [
    {"name": "/feature-1", "desc": "Core capability description", "icon": "🚀"},
    {"name": "/feature-2", "desc": "Secondary feature overview", "icon": "⚡"},
    {"name": "/feature-3", "desc": "Additional functionality detail", "icon": "🔧"},
    {"name": "/feature-4", "desc": "Key workflow enhancement", "icon": "📦"},
    {"name": "/feature-5", "desc": "Advanced integration support", "icon": "🎯"},
    {"name": "/feature-6", "desc": "Enterprise-grade reliability", "icon": "🛡️"},
]

# ---- Narration generation ----
def generate_narration_text(repo, weekly_stars, description, features, language):
    """Generate Chinese narration script from repo data."""
    feat_names = [f['name'] for f in features[:6]]
    feat_str = "、".join(feat_names[:3]) + "、以及" + feat_names[-1] if len(feat_names) > 1 else feat_names[0]

    return (
        f"{repo.replace('/', ' slash ')}，"
        f"本周 GitHub Trending 热门项目，获得{weekly_stars}颗星。"
        f"这是一个基于{language}语言开发的{description[:50]}。"
        f"主要功能包括：{feat_str}。"
        f"该项目在社区引起广泛关注，值得开发者了解和尝试。"
    )


def generate_voxcpm(text, output_name="narration.wav"):
    """Generate voiceover via local VoxCPM model with reference audio."""
    output_path = os.path.join(PUBLIC_DIR, output_name)
    if os.path.exists(output_path):
        print(f"Audio already exists: {output_path}")
        return output_name

    if not os.path.exists(REF_AUDIO):
        print(f"WARNING: Reference audio not found at {REF_AUDIO}, skipping voiceover")
        return None

    if not os.path.exists(MODEL_PATH):
        print(f"WARNING: VoxCPM model not found at {MODEL_PATH}, skipping voiceover")
        return None

    print(f"Generating VoxCPM voiceover ({len(text)} chars)...")
    try:
        from voxcpm import VoxCPM
        import soundfile as sf

        model = VoxCPM.from_pretrained(MODEL_PATH, load_denoiser=False)
        wav = model.generate(
            text="(正常语速，温柔)" + text,
            reference_wav_path=REF_AUDIO,
            cfg_value=2.0,
            inference_timesteps=10,
        )
        sf.write(output_path, wav, model.tts_model.sample_rate)
        print(f"Voiceover saved: {output_path}")
        return output_name
    except Exception as e:
        print(f"VoxCPM generation failed: {e}")
    return None


# ---- Screenshot ----
def take_screenshot(repo_url, output_name="screenshot.png"):
    """Take clean screenshot via CDP, returns filename in public/."""
    output_path = os.path.join(PUBLIC_DIR, output_name)
    if os.path.exists(output_path):
        print(f"Screenshot already exists: {output_path}")
        return output_name

    script = os.path.join(os.path.dirname(__file__), "screenshot_cdp.py")
    subprocess.run(
        [sys.executable, script, repo_url, output_name],
        check=False, timeout=45
    )
    if os.path.exists(output_path):
        return output_name
    print("WARNING: Screenshot failed, video will have no background image")
    return None


# ---- Render ----
def render_video(props, output_filename):
    """Render Remotion video with given props."""
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    output_path = os.path.join(OUTPUT_BASE, output_filename)

    # Write props to temp file
    props_file = os.path.join(REMOTION_DIR, "props.json")
    with open(props_file, 'w', encoding='utf-8') as f:
        json.dump(props, f, ensure_ascii=False)

    print(f"Rendering video to {output_path}...")
    cmd = [
        "npx", "remotion", "render", "MainComposition", output_path,
        "--props", json.dumps(props),
    ]
    result = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=False, timeout=600)
    if result.returncode == 0:
        print(f"Video rendered: {output_path}")
        return output_path
    else:
        print(f"Render failed with code {result.returncode}")
        return None


# ---- Main ----
def main():
    parser = argparse.ArgumentParser(description="Build GitHub trending promo video")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--total-stars", default="?")
    parser.add_argument("--weekly-stars", default="?")
    parser.add_argument("--language", default="Unknown")
    parser.add_argument("--desc", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--author-title", default="")
    parser.add_argument("--features", default=None, help="JSON array of {name,desc,icon}")
    parser.add_argument("--output", default=None, help="Output filename (default: <repo>-promo.mp4)")
    parser.add_argument("--skip-screenshot", action="store_true")
    parser.add_argument("--skip-audio", action="store_true")
    args = parser.parse_args()

    repo = args.repo
    safe_name = repo.replace('/', '-')
    output_fn = args.output or f"{safe_name}-promo.mp4"

    # Parse features
    features = DEFAULT_FEATURES
    if args.features:
        try:
            features = json.loads(args.features)
        except json.JSONDecodeError:
            print("Invalid features JSON, using defaults")

    # Step 1: Screenshot
    screenshot_fn = None
    if not args.skip_screenshot:
        repo_url = f"https://github.com/{repo}"
        screenshot_fn = take_screenshot(repo_url, f"screenshot_{safe_name}.png")

    # Step 2: Voiceover
    audio_fn = None
    if not args.skip_audio:
        narration = generate_narration_text(
            repo, args.weekly_stars, args.desc, features, args.language
        )
        print(f"Narration: {narration[:100]}...")
        audio_fn = generate_voxcpm(narration, f"narration_{safe_name}.wav")

    # Step 3: Render
    props = {
        "repo": repo,
        "totalStars": args.total_stars,
        "weeklyStars": args.weekly_stars,
        "language": args.language,
        "description": args.desc,
        "author": args.author,
        "authorTitle": args.author_title,
        "features": features,
        "screenshot": screenshot_fn or "",
        "audio": audio_fn or "",
    }
    render_video(props, output_fn)
    print("Done!")


if __name__ == '__main__':
    main()
