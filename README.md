# GitHub Trending Video Studio

抓取 GitHub 热门项目，一键生成 7 场景中文解说宣传视频 —— Remotion 动画 + VoxCPM TTS 语音。

## 架构

```
curl trending.html → fetch_trending.py → trending.json
                                              │
                    ┌─────────────────────────┘
                    ▼
          FastAPI Dashboard (:8765)
          ┌────────────────────────────┐
          │  /api/trending             │  列出项目
          │  /api/select-project       │  GitHub API + README 解析
          │  /api/screenshot           │  Chrome CDP 截图
          │  /api/generate-audio       │  VoxCPM TTS 语音
          │  /api/build-video          │  npx remotion render
          └────────────────────────────┘
                    │
                    ▼
          Remotion Render
          MainComposition.tsx (S1-S7) → output/*.mp4
```

## 项目结构

```
├── SKILL.md                    # Skill 入口 (fetch→parse→save 流程)
├── trending-to-video.md        # 子 skill: 视频制作流程
├── docs/SPEC.md                # 完整架构规格
├── scripts/
│   ├── web_ui.py               # FastAPI 服务器 + SPA 仪表板
│   ├── screenshot_cdp.py       # Chrome CDP 截图自动化
│   └── fetch_trending.py       # HTML 解析器 → trending.json
├── remotion/
│   ├── src/
│   │   ├── MainComposition.tsx # 7 场景渲染器
│   │   └── Transitions.tsx     # 动画 hooks
│   ├── public/                 # 生成的素材 (截图 + WAV)
│   └── output/                 # 渲染完成的 MP4
├── templates/
│   └── index.html              # Web UI SPA 模板
└── output/                     # 最终视频
```

## 环境要求

| 依赖 | 用途 |
|------|------|
| Python 3 + conda (voxcpm 环境) | Web 服务器、TTS、截图 |
| Node.js + Remotion v4.0.456 | 视频渲染 |
| Chromium | CDP 截图 |
| VoxCPM2 模型 (`~/voxcpm/pretrained_models/VoxCPM2/`) | 本地 TTS 语音合成 |
| `GITHUB_TOKEN` 环境变量 | GitHub API 认证 (避免 60/hr 限流) |

### Python 包 (voxcpm 环境)

`fastapi, uvicorn, websocket-client, voxcpm, soundfile, gradio_client, Pillow, numpy`

### npm 包 (remotion/)

`remotion ^4.0.456, react ^18.3.1, typescript ^5.4.0`

## 快速开始

### 1. 启动 Chrome 远程调试

```bash
google-chrome --remote-debugging-port=9222 --remote-allow-origins=* --headless=new --window-size=1920,1080 "about:blank"
```

### 2. 启动 Web 管理台

```bash
conda activate voxcpm
python3 ~/.claude/skills/github-trending/scripts/web_ui.py --port 8765
```

服务绑定 `0.0.0.0`，浏览器打开 `http://localhost:8765`。支持 `?repo=owner/name` 直达项目。

### 3. 制作视频

在 Web 管理台中完成 4 步：

1. **Refresh Trending** — 从 GitHub Trending 抓取最新数据
2. **Generate Video** — 选择项目，自动获取 README、提取功能、生成旁白
3. **Take Screenshots** — CDP 自动截图（top + intro），星标加红圈
4. **Build Video** — Remotion 渲染为 MP4

中间可编辑截图的场景旁白文本、功能列表等。语音生成（VoxCPM TTS）会自动触发。

## 7 场景视频结构

| 场景 | 名称 | 画面 |
|------|------|------|
| S1 | 开场 | 紫蓝渐变 + 打字机文字 "今天介绍的GitHub热门项目是" |
| S2 | 项目卡片 | 白色卡片：项目名、语言标签、描述、星数统计 |
| S3 | 页面截图 | 完整页面截图 + 星数叠加 |
| S4 | 星标缩放 | 截图缩放至星标按钮区域 + 红色发光环 |
| S5 | 项目介绍 | README 截图缓慢滚动 (从上往下阅读效果) |
| S6 | 功能介绍 | 功能卡片逐个高亮 + intro 截图淡背景 |
| S7 | 结尾 | 紫蓝渐变 + "关注我，获得最新的实用项目信息" |

全部场景使用 fade 淡入淡出转场。时长由语音自动决定（`durationSeconds × 30 + 15` 帧），分辨率 1920×1080，30fps。

## API 端点

| 路由 | 方法 | 用途 |
|------|------|------|
| `/` | GET | SPA 仪表板 |
| `/api/trending` | GET | 返回缓存的热门数据 |
| `/api/trending/fetch` | GET | 重新抓取 GitHub Trending |
| `/api/select-project` | POST | 获取仓库详情 + 提取功能 + 生成旁白 → props.json |
| `/api/screenshot` | POST | Chrome CDP 截图 (top + intro) |
| `/api/generate-audio` | POST | VoxCPM TTS → 7 场景 WAV → props.json |
| `/api/remotion/status` | GET | 检查 Remotion Studio 状态 |
| `/api/remotion/start` | POST | 后台启动 Remotion Studio |
| `/api/build-video` | POST | `npx remotion render` → 轮询完成 |
| `/api/render-status` | GET | 渲染进度 |
| `/api/props` | GET | 读取 props.json |
| `/api/save-props` | POST | 写入 props.json |

## 语音生成

优先本地 VoxCPM2 模型，回退 HuggingFace Space `openbmb/VoxCPM-Demo`。使用 `reference.wav` 进行声音克隆（CFG 2.0, 10 inference steps）。`normalize_for_tts()` 自动转换全大写词（如 `SKILL.md` → `skill markdown`）。

## 已知限制

- GitHub API 未认证时 60/hr 限流，需设置 `GITHUB_TOKEN`
- Chrome CDP 单实例：同一时间只能有一个 Chrome 占用 9222 端口
- Google Translate API 无认证，可能触发 IP 限流
- 大 README 截图可能超过 6000px，Remotion 渲染时内存压力大
- 使用 Python `wave` 模块拼接 WAV（ffmpeg 拼接会产生损坏的 LIST chunk 头）

## 输出

渲染完成的 MP4 视频保存在 `output/<repo-slug>-promo.mp4`。
