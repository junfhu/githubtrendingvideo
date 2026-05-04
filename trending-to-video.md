---
name: trending-to-video
description: 从 GitHub Trending 热门项目中选择一个，自动生成 Remotion 宣传视频（截图 + 动画 + VoxCPM 语音旁白）
allowed-tools: Bash(python3 *) Bash(curl *) Bash(npx *) Bash(mkdir *)
---

# GitHub Trending → 视频

你是 GitHub Trending 视频制作助手。当用户调用此 skill 时，按以下流程执行。

## 前置检查

确保 Chrome 已开启远程调试：

```bash
start "" "C:/Program Files/Google/Chrome/Application/chrome.exe" --remote-debugging-port=9222 --remote-allow-origins=* --headless=new --window-size=1920,1080 "about:blank"
```

## 执行流程

### 步骤 1：抓取热门项目

```bash
PYTHONIOENCODING=utf-8 python3 "D:/BaiduSyncdisk/Obsidian/ForCC/.claude/skills/github-trending/scripts/fetch_trending.py"
```

输出格式：`序号|owner/repo|周增星数|总星数|语言|描述`

### 步骤 2：让用户选择

在对话中展示前 10 个项目列表，让用户选择要制作视频的项目（输入编号 1-10）。

### 步骤 3：获取项目详情

用 WebFetch 抓取项目 README，提取：
- 详细描述
- 核心功能列表（6 个主要功能）
- 作者信息（用户名、身份/头衔）

整理为以下结构化数据：
- `repo`: owner/name
- `totalStars`: 总星数（如 "57,273"）
- `weeklyStars`: 周增星数（如 "34,848"）
- `language`: 主要语言
- `description`: 一句话描述（英文）
- `author`: 作者用户名
- `authorTitle`: 作者身份描述
- `features`: JSON 数组，每个元素 `{name, desc, icon}`

### 步骤 4：截图（CDP）

截图脚本会自动定位星标按钮坐标（输出 `STAR_POS: {x, y, w, h}`），只隐藏全局导航栏和侧边栏，**保留页面主体和星标按钮**，白底截图。

```bash
PYTHONIOENCODING=utf-8 python3 "D:/BaiduSyncdisk/Obsidian/ForCC/.claude/skills/github-trending/scripts/screenshot_cdp.py" "https://github.com/<owner>/<repo>" "screenshot_<safe_name>.png"
```

截图输出中会打印星标按钮的真实坐标，后续视频中红圈定位需使用该坐标。例如：
```
STAR_POS: {"x": 1734.4, "y": 88, "w": 122.6, "h": 28, "vw": 1904, "vh": 985}
```

### 步骤 5：生成 VoxCPM 语音旁白

参考音频：`D:/douyincontent/hjf_test.wav`

生成中文旁白文本（模板）：

```
今天介绍的 GitHub 热门项目是 <repo> ，本周获得<weeklyStars>颗星。这是一个基于<language>语言开发的<简短描述>。主要功能包括：<功能1>、<功能2>、<功能3>等。该项目在社区引起广泛关注，值得开发者了解和尝试。
```

然后通过 HuggingFace API 调用 VoxCPM2（`openbmb/VoxCPM-Demo`）：

```python
from gradio_client import Client
from gradio_client.utils import handle_file

client = Client('openbmb/VoxCPM-Demo')
result = client.predict(
    text_input=narration_text,
    control_instruction='',
    reference_wav_path_input=handle_file('D:/douyincontent/hjf_test.wav'),
    use_prompt_text=False,
    prompt_text_input='',
    cfg_value_input=2.0,
    do_normalize=False,
    denoise=False,
    api_name='/generate',
)
# 将 result 复制到 remotion/public/narration_<safe_name>.wav
```

### 步骤 6：渲染视频

将步骤 3 整理的数据写为 JSON props，渲染 Remotion 视频：

```bash
cd "D:/BaiduSyncdisk/Obsidian/ForCC/.claude/skills/github-trending/remotion" && npx remotion render MainComposition "D:/BaiduSyncdisk/Obsidian/ForCC/Daily Notes/GitHub Trending/<safe_name>-promo.mp4" --props='{"repo":"<repo>","totalStars":"<total>","weeklyStars":"<weekly>","language":"<lang>","description":"<desc>","author":"<author>","authorTitle":"<title>","features":[...],"screenshot":"screenshot_<safe_name>.png","audio":"narration_<safe_name>.wav"}'
```

渲染前需根据 CDP 输出的 `STAR_POS` 坐标更新 `MainComposition.tsx` 中 S3（star_detail）红圈和 `transformOrigin` 参数：
- `circleCX` / `circleCY` = 红圈中心 = starBtn 坐标 ± 边距（当前硬编码为 CDP 实测值）
- `transformOrigin` = `x/vw * 100% y/vh * 100%`（星标按钮在 viewport 中的百分比位置）

如需调整任何场景的时间或转场效果，修改 `SCENES` 数组（定义于 `MainComposition.tsx`）中对应项的 `start`/`end`/`enter`/`exit`/`nextTransition` 字段即可。

### 步骤 7：展示结果

告知用户视频保存位置，输出视频时长和文件大小。

## 场景与时间线

视频共 6 个场景，总长 31 秒 / 930 帧 @ 30fps。

| 场景 | 帧 | 时间 | 内容 | 语音对应 |
|------|-----|------|------|------|
| S1a 打字机 | 0–80 | 0–2.7s | 紫蓝渐变背景 + 磨砂玻璃卡片，白色大字打字机 + 金色闪烁光标 | "今天介绍的GitHub热门项目是" |
| S1b 项目揭示 | 70–150 | 2.3–5s | 灰白渐变背景 + 白色卡片布局：项目名+图标+语言标签+描述+统计卡片 | "mattpocock/skills" |
| S2 截图+星数 | 135–300 | 4.5–10s | 全页截图（白底），深色半透明卡片叠加星数 | "本周获得xxx颗星" |
| S3 星标红框 | 280–420 | 9.3–14s | 截图放大右上角星标区域（红框已由 CDP 注入截图） + 星数 | 星数+项目描述 |
| S4 功能列表 | 400–840 | 13.3–28s | 白底 + 6大核心功能卡片（逐帧硬编码触发） + 项目简介卡片 | "主要功能包括..." |
| S5 结语 | 820–930 | 27.3–31s | 紫蓝渐变 + 磨砂玻璃卡片（与 S1a 呼应），"关注我，获得最新的实用项目信息" | 结尾语音 |

## 场景转场

所有场景切换使用纯 `fade` 淡入淡出，无转场特效覆盖层。画面干净无闪烁。

## 关键实现细节

### 开场设计（S1a + S1b）
采用现代前端设计风格（frontend aesthetic）：
- **S1a**：紫蓝渐变背景（`#667eea → #764ba2`） + 磨砂玻璃卡片（`backdrop-filter: blur`），白色大字打字机 + 金色闪烁光标
- **S1b**：灰白渐变背景 + 白色卡片布局，项目名配图标 + 语言标签胶囊 + 描述文字 + 两张指标卡片（Total Stars / This Week，左侧彩色边框）

### 结语设计（S5）
与 S1a 呼应的紫蓝渐变背景 + 磨砂玻璃卡片，白色文字居中。

### 星标文字（S2）
截图上方叠加深色半透明卡片（`rgba(13,17,23,0.85)` 圆角底）衬白色数字，帧 175 淡入、帧 270 淡出。总星数直接显示完整值。

### 星标红框（S3）
红框通过 CDP 直接注入截图：截图时在浏览器中找到 Star 按钮的 `aria-label`，对其容器设置 `outline: 3px solid #ff3333` + 红色 `box-shadow` glow。不再使用 Remotion SVG 覆盖层，位置 100% 准确。

### 功能列表（S4）
白底 + light-mode 配色。功能卡片通过硬编码帧偏移数组 `featureFrames` 逐个触发高亮，与语音逐项对齐。如需微调某个功能的出现时机，修改对应帧偏移值即可。

```typescript
const featureFrames = [55, 108, 162, 218, 272, 335];
// 每个值 = 相对 S4 起始帧的偏移量
```

### 语音旁白
VoxCPM 生成的中文旁白，结尾包含 "关注我，获得最新的实用项目信息"。参考音频 `D:/douyincontent/hjf_test.wav`。

### 设计原则
- **S1a + S5**（首尾呼应）：紫蓝渐变 + 磨砂玻璃卡片（frontend aesthetic）
- **S1b**：灰白渐变 + 白色卡片布局，指标卡片左侧彩色边框
- **S2–S4**：纯色背景，无渐变、无扫描线、无转场特效覆盖层
- 场景切换仅用 fade 淡入淡出，保持画面干净无闪烁
- 不暴露 GitHub 完整 URL
- 星标红框由 CDP 注入截图，100% 精准定位
- 总星数直接展示完整值，不计数动画
- 功能清单用 `featureFrames` 逐帧硬编码时间点与语音对齐

## 输出文件

```
Daily Notes/GitHub Trending/<repo-slug>-promo.mp4
```

## Props 接口

```typescript
interface VideoProps {
  repo: string;           // "owner/name"
  totalStars: string;     // "57,273"
  weeklyStars: string;    // "34,848"
  language: string;       // "Python"
  description: string;    // one-line description
  author: string;         // author username
  authorTitle: string;    // author role/identity
  features: Array<{       // 6 features
    name: string;         // "/feature-name"
    desc: string;         // "What it does"
    icon: string;         // emoji
  }>;
  screenshot: string;     // filename in public/
  audio: string;          // filename in public/
}
```
