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
google-chrome --remote-debugging-port=9222 --remote-allow-origins=* --headless=new --window-size=1920,1080 "about:blank"
```

## 执行流程

### 步骤 1：确保 Chrome 远程调试运行

```bash
google-chrome --remote-debugging-port=9222 --remote-allow-origins=* --headless=new --window-size=1920,1080 "about:blank"
```

> Remotion Studio 由 Web 管理台自动启动，无需手动运行。点击 "Preview in Remotion" 按钮时自动检测并启动。

### 步骤 2：抓取 Trending 数据（如尚未抓取）

```bash
curl -s "https://github.com/trending?since=weekly" -o "<skill-dir>/trending.html"
python3 "<skill-dir>/scripts/fetch_trending.py" "<skill-dir>/trending.html"
```

将输出（`序号|owner/repo|...` 格式）写入 `<skill-dir>/trending.json`。

### 步骤 3：启动 Web 管理台

```bash
source /home/ppcorn/miniconda3/etc/profile.d/conda.sh && conda activate voxcpm && python3 "<skill-dir>/scripts/web_ui.py" --port 8765
```

Web 管理台启动后会打印服务器外部地址（如 `http://192.168.x.x:8765`），在浏览器中打开该地址即可。如果在服务器本机操作，也可以使用 `http://localhost:8765`。

> 服务绑定在 `0.0.0.0`，支持从局域网内其他设备访问。如果从其他设备连接，请使用服务器 IP 地址而非 localhost。

### 步骤 4：用户在 Web 管理台完成全部操作

Web 管理台提供完整工作流，URL 支持 `?repo=owner/name` 直接加载项目：

1. **Refresh Trending** → 从 GitHub 抓取最新 trending 数据
2. **Generate Video** → 选择项目，自动获取 README、提取功能、生成旁白
3. **Take Screenshots** → 自动 CDP 截图（top + intro/README），星标自动加红圈
4. **编辑** → 左侧截图预览，右侧项目信息 + 功能列表 + S1-S7 场景旁白文本（每行可编辑）
5. **Generate Voice** → 通过 HuggingFace Space `openbmb/VoxCPM-Demo` 生成语音
6. **Preview in Remotion** → 自动生成语音后打开 Remotion Studio（视频时长匹配语音）
7. **Build Video** → 渲染最终 MP4

## 场景与时间线

视频共 7 个场景，时长由语音自动决定（`durationSeconds * 30 + 15` 帧）。场景时间与旁白文本对齐（`narrationTiming` 中的字符位置比例）。

| 场景 | 内容 | 截图 | 语音对应 |
|------|------|------|------|
| S1 开场 | 紫蓝渐变 + 打字机 | — | "今天介绍的GitHub热门项目是" |
| S2 项目卡片 | 白色卡片：项目名+语言+描述+统计 | — | 项目名称 |
| S3 页面截图 | 页面顶部截图 + 星数叠加 | top | "本周获得xxx颗星" |
| S4 星标放大 | 截图放大至星标区域 + 红圈 | top | "总计xxx颗星" |
| S5 项目介绍 | 核心价值截图（定位到 Why/About 标题）缓慢平移 + 微缩放 | intro（定位到匹配标题） | 项目核心价值描述 |
| S6 功能介绍 | 功能卡片逐个高亮 + intro 截图淡背景 | intro | "主要功能包括..." |
| S7 结尾 | 紫蓝渐变 + "关注我，获得最新的实用项目信息" | — | 结尾语音 |

## 场景转场

所有场景切换使用纯 `fade` 淡入淡出，无转场特效覆盖层。

## 关键实现细节

### 开场设计（S1 + S7 首尾呼应）
- **S1**：紫蓝渐变背景（`#667eea → #764ba2`） + 磨砂玻璃卡片，白色大字打字机 + 金色闪烁光标
- **S7**：与 S1 呼应的紫蓝渐变背景 + 磨砂玻璃卡片，白色文字居中

### 星标文字（S3）
截图上方叠加深色半透明卡片显示星数，总星数直接展示完整值。

### 星标红框（S4）
红框通过 CDP 直接在浏览器中注入：
1. 在当前页面找到 Star 按钮（GitHub 现在使用 `<a>` 标签，非 `<button>`）
   - 策略 1：查找 `span.d-inline` 中文本为 "Star" 或 "Unstar" 的元素，取其最近的 `<a>` 父元素
   - 策略 2：查找 `a.btn-sm.btn` 中文本包含 "Star" 的链接
   - 策略 3：查找 `[aria-label*="star"]` 元素
2. 创建一个 `position: fixed; z-index: 99999` 的 `<div>` 覆盖层，精确放置在 Star 按钮的 bounding box 上（各边扩展 5-6px），设置 `border: 4px solid #ff3333` + 红色 `box-shadow` glow
3. 同时对 Star 元素本身应用 `outline: 3px solid #ff3333` + `box-shadow`
4. 第二张截图前移除红圈覆盖层（`#__star_red_ring__`）

### 截图说明
**第一张截图（top）**：页面顶部，包含 Star 按钮区域。在注入红圈后捕获。

**第二张截图（intro/README）**：从 README 顶部开始往下截，只截取内容区域（不含两侧空白）。
关键实现（`screenshot_cdp.py`）：
1. 找到 `article.markdown-body`（或 `#readme`）元素
2. `window.scrollTo(0, scrollY + rect.top)` 将 README 顶部滚到视口顶部
3. 设置 viewport 高度为 README 完整 `scrollHeight`，**宽度保持 1920px 不变**（避免布局重排导致元素位移）
4. 重新测量 `rect`，计算**页面坐标系**中的裁剪区域：
   - `clip.x = scrollX + rect.left`（README 左边界绝对位置，约 378px）
   - `clip.y = scrollY + rect.top`（README 上边界绝对位置，约 2496px）
   - `clip.width = rect.width`（内容列宽度，约 838px）
   - `clip.height = scrollHeight`（完整内容高度）
5. `Page.captureScreenshot` 传入 `clip` 参数精确截取
6. **关键坑**：CDP 的 `clip` 使用**页面坐标系**（page coordinates），不是视口相对坐标；且不能改变 viewport 宽度，否则 GitHub 响应式布局会重排

### S5 项目介绍（滚动动画）
第二张截图是拍平的完整 README 长图。S5 场景使用 `translateY` 从 0%→-200% 快速滚动，模拟从上往下阅读 README 的效果。

### 场景时间对齐
**S1-S4、S7**：固定 2.5 秒。**S5、S6**：按字符比例分配音频剩余时间。`sceneDurations` 保存在 props.json，`buildScenes()` 将其转为精确帧数。

### 语音生成
**优先本地 VoxCPM**（`~/voxcpm/pretrained_models/VoxCPM2`），一次加载生成 7 场景 + 1 合并音频。`normalize_for_tts()` 自动转换全大写词（如 `SKILL.md`→`skill markdown`）。本地失败则回退 HuggingFace Space。

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
  narration: string;      // Chinese narration text (editable in web UI)
  screenshot: string;     // filename in public/
  audio: string;          // filename in public/
}
```
