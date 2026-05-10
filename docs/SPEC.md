# Spec: GitHub Trending Video Studio

## Objective

Full pipeline: fetch GitHub trending repos → select one (or paste any URL) → auto-produce a 7-scene Chinese-narrated promo video with Remotion + Edge TTS.

**User**: Content creator making daily GitHub project spotlight videos.
**Success**: One-click video from trending list or custom URL → downloadable MP4.

---

## Architecture

```
curl trending.html → fetch_trending.py → trending.json
                                              │
                    ┌─────────────────────────┘
                    ▼
          FastAPI Dashboard (:8765)
          ┌────────────────────────────┐
          │  /api/trending             │  List projects
          │  /api/select-project       │  GitHub API + README parse
          │  /api/screenshot           │  Chrome CDP capture
          │  /api/generate-audio       │  Edge TTS + concatenation
          │  /api/build-video          │  npx remotion render
          └────────────────────────────┘
                    │
                    ▼
          Remotion Render (:3000)
          MainComposition.tsx (S1-S7) → output/*.mp4
```

---

## Project Structure

```
SKILL.md                  # Skill entry point (fetch→parse→save workflow)
trending-to-video.md      # Sub-skill: video production workflow
docs/SPEC.md              # This specification
.gitignore                # node_modules, *.mp4, *.wav, screenshot_*.png

scripts/
├── web_ui.py             # FastAPI server + inline SPA (2164 lines)
├── screenshot_cdp.py     # Chrome CDP screenshot capture (490 lines)
└── fetch_trending.py     # HTML parser → trending.json (56 lines)

remotion/
├── package.json          # Remotion v4.0.456, React 18.3
├── tsconfig.json         # ES2018, JSX react-jsx
├── props.json            # Current working props (generated)
├── public/               # Generated assets (screenshots + WAVs)
│   └── reference.wav     # Voice clone reference audio
├── src/
│   ├── index.ts          # RemotionRoot registration
│   ├── Root.tsx          # Composition: 1920×1080, 30fps
│   ├── MainComposition.tsx  # 7-scene renderer (609 lines)
│   └── Transitions.tsx   # Enter/exit animation hooks (450 lines)
└── output/               # Rendered MP4 videos
```

---

## API Endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | SPA dashboard |
| `/api/trending` | GET | Return `trending.json` |
| `/api/trending/fetch` | GET | Re-fetch + parse GitHub trending |
| `/api/select-project` | POST | Fetch repo, extract features, generate narration → `props.json` |
| `/api/screenshot` | POST | Chrome CDP: top + intro + optional S6 screenshots |
| `/api/generate-audio` | POST | Edge TTS → 7 scene MP3s, concatenated → `props.json` |
| `/api/remotion/status` | GET | Check if Remotion Studio running on :3000 |
| `/api/remotion/start` | POST | Start `npx remotion studio` in background |
| `/api/build-video` | POST | `npx remotion render` → poll for completion |
| `/api/render-status` | GET | Render progress |
| `/api/props` | GET | Read `props.json` |
| `/api/save-props` | POST | Write `props.json` |

---

## Video: 7-Scene Structure

All scenes use `fade` enter/exit. Frame ranges computed from per-scene audio durations at 30fps.

| Scene | Name | Visual |
|-------|------|--------|
| S1 | Opening | Purple gradient, typewriter "今天介绍的GitHub热门项目是" |
| S2 | Project Card | White card: name, language badge, description, star stats |
| S3 | Screenshot | Full page screenshot with star count overlay |
| S4 | Star Zoom | Screenshot zoomed 1.6× into star button area |
| S5 | Demo Images / Intro | **With demo images**: ken-burns carousel of project output screenshots; **Without**: README screenshot (scroll if >1080px tall) |
| S6 | Features | Feature cards (6 rows) or How-It-Works screenshot fallback |
| S7 | Outro | Purple gradient, "关注我，获得最新的实用项目信息" |

**Scene transition schedule** (`buildScenes()` in MainComposition.tsx):
```
t = 0
S1: [0,                s1Frames]          t += s1Frames
S2: [t-10,             t+s2Frames]        t += s2Frames      (10-frame overlap)
S3: [t-10,             t+s3Frames]        t += s3Frames      (10-frame overlap)
S4: [t-10,             t+s4Frames]        t += s4Frames      (10-frame overlap)
S5: [t-10,             t+s5Frames-8]      t += s5Frames      (10-frame overlap, 8 early)
S6: [t+2,              t+s6Frames]        t += s6Frames      (2-frame gap)
S7: [t+2,              T]                                     (2-frame gap, fills to end)
```
Total frames: `ceil(durationSeconds × 30) + 15` (15-frame tail padding).

---

## Data Pipeline

### Step 1: Select Project → `POST /api/select-project`
1. GitHub API: `GET /repos/{owner}/{name}` → stargazers_count, language, description, topics
2. GitHub API: `GET /repos/{owner}/{name}/readme` → base64-decode README
3. `extract_features(readme)` → 6 features `[{icon, name, desc}]`
4. `extract_chinese_description(readme)` → translated intro paragraph + target heading
5. `extract_how_it_works(readme)` → S6 fallback if features lack substance (<3 substantial)
6. `extract_demo_images(readme, repo)` → download up to 5 demo/output images from README → `demo_<repo>_<N>.png` in public/
7. `generate_narration(name, stars, ...)` → Chinese text with character-position timing cues
8. Write `props.json`

### Step 2: Screenshot → `POST /api/screenshot`
1. Launch Chromium `--headless=new --remote-debugging-port=9222`
2. Navigate to `github.com/{repo}`, hide nav/sidebar
3. Inject red ring `<div>` around star button
4. Capture **top** screenshot (1920×1080 viewport)
5. Remove ring, scroll to target heading, resize viewport to section height
6. Capture **intro** screenshot, validate via PIL std-deviation check
7. Optional: capture **S6** "How It Works" screenshot
8. Update `props.json` with filenames + screenshot heights

### Step 3: Audio → `POST /api/generate-audio`
1. Generate 7 per-scene MP3s via Edge TTS (`zh-CN-YunxiNeural`)
   - Voice configurable via `EDGE_TTS_VOICE` env var
   - Free cloud service, no local model or GPU required
2. Measure each MP3 duration via ffprobe
3. Concatenate per-scene MP3s using ffmpeg concat demuxer
4. Store exact measured durations as `sceneDurations`
5. Update `props.json` with audio path, `durationSeconds`, `sceneDurations`

### Step 4: Render → `POST /api/build-video`
1. Write props to `props.json`
2. `npx remotion render MainComposition output.mp4 --props <json>`
3. Poll `/api/render-status` every 2s for completion

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Concatenated scene MP3s over combined TTS | Guarantees perfect audio-visual alignment per scene |
| ffmpeg concat demuxer for MP3 concat | MP3 format requires ffmpeg; previously WAV used Python wave module |
| Edge TTS over VoxCPM | Free, no local model/GPU, reliable cloud service, native Chinese support |
| Character-position timing cues | Approximate scene boundaries in narration text; now unused for timing |
| Fixed scene structure (S1-S7) | Consistent video format across all projects |
| Conditional S5/S6 scroll | Skip scroll when screenshot ≤1080px (fits screen) |
| Demo image extraction from README | Visual demo output (detection results, screenshots) is more engaging than text; auto-fallback to README scroll when no images found |
| S5 ken-burns carousel for demo images | Smooth zoom+pan animation makes static screenshots feel dynamic |
| Weekly stars optional | Omitted from narration + display when `'?'` (unknown for custom URLs) |
| GITHUB_TOKEN from env | Avoids 60/hr rate limit; reads from `GITHUB_TOKEN`, `GH_TOKEN`, or `~/.config/gh/hosts.yml` |

---

## Dependencies

### Python (system)
fastapi, uvicorn, websocket-client, edge-tts, Pillow, numpy

### npm (remotion/)
remotion ^4.0.456, react ^18.3.1, typescript ^5.4.0

### System
chromium-browser, ffmpeg, curl

---

## Hardcoded Paths

| Path | Purpose |
|------|---------|
| `~/.config/gh/hosts.yml` | GitHub CLI token auto-detect |
| `translate.googleapis.com/translate_a/single` | Chinese translation (no auth) |
| Edge TTS cloud service | Chinese narration (`zh-CN-YunxiNeural`, configurable via `EDGE_TTS_VOICE`) |
| CDP port `9222`, Studio port `3000`, Dashboard port `8765` | Fixed ports |

---

## Props.json Schema

```json
{
  "repo": "owner/name",
  "name": "short-name",
  "totalStars": "12,345",
  "weeklyStars": "1,234",
  "language": "TypeScript",
  "description": "Project description",
  "chineseDesc": "中文项目介绍",
  "author": "owner",
  "authorTitle": "owner - Developer",
  "features": [{"name": "/feature", "desc": "description", "icon": "🚀"}],
  "demoImages": ["demo_owner-name_0.png", "demo_owner-name_1.png"],
  "narration": "full Chinese narration text",
  "narrationTiming": {"s2_project": 0.05, "s3_screenshot": 0.10, "s4_starzoom": 0.15, "s5_intro": 0.20, "s6_features": 0.60, "s7_outro": 0.95},
  "sceneTexts": {"s1": "text", "s2": "text", "...": "..."},
  "screenshot": "screenshot_X_top.png",
  "screenshotIntro": "screenshot_X_intro.png",
  "screenshotIntroHeight": 2400,
  "s6Screenshot": "screenshot_X_s6.png",
  "s6ScreenshotHeight": 1800,
  "audio": "narration_X.wav",
  "durationSeconds": 52.9,
  "sceneDurations": {"s1": 2.7, "s2": 1.6, "s3": 3.2, "s4": 1.9, "s5": 22.6, "s6": 18.2, "s7": 2.7}
}
```

---

## Known Issues

1. **HTML in narration**: `extract_chinese_description()` doesn't fully strip HTML tags from README
2. **GitHub API rate limiting**: 60/hr unauthenticated → needs `GITHUB_TOKEN`
3. **Google Translate rate limiting**: No auth, may trigger IP blocking
4. **Chrome CDP single-instance**: Only one Chrome on port 9222
5. **Inline HTML maintenance**: ~900 lines of HTML/CSS/JS embedded in Python string
6. **No Obsidian output**: SKILL.md claims `Daily Notes/` saving but web_ui.py doesn't implement it
7. **Large S5 screenshots**: Can exceed 6000px height, causing Remotion memory pressure

---

## Boundaries

**Always do:**
- Verify Python syntax + `npx tsc --noEmit` before committing
- Sync frontend JS `props` with backend API responses
- Keep S1-S7 scene structure intact when changing timing
- Use ffmpeg concat demuxer for MP3 concatenation

**Ask first:**
- Adding new npm or Python dependencies
- Changing scene count or order (S1-S7)
- Changing Edge TTS voice model
- Changing Remotion resolution or FPS

**Never do:**
- Commit secrets, API tokens, credentials
- Commit generated assets (MP3, MP4, PNG, trending.json)
- Edit `remotion/public/` assets directly (they're all generated)
