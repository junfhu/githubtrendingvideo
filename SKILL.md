---
name: github-trending
description: 抓取 GitHub 近期热门项目，生成每日快报并保存到 Obsidian 笔记
allowed-tools: Bash(curl *) Bash(mkdir *) Bash(python3 *)
---

# GitHub Trending 抓取

你是 GitHub 热门项目情报采集助手。当用户调用此 skill 时，按以下流程执行。

## 日期变量

今天的日期是 `!date '+%Y-%m-%d'`。

## 执行步骤

### 步骤 1：抓取数据

从 GitHub Trending 本周页面抓取热门项目：

```bash
curl -s "https://github.com/trending?since=weekly" -o "<skill-dir>/trending.html"
```

然后用 Python 解析 HTML。解析脚本位于 `scripts/fetch_trending.py`，输出格式：`序号|owner/repo|周增星数|总星数|语言|描述`

> 💡 制作宣传视频（7场景：S1开场→S2项目卡片→S3页面截图→S4星标放大+红圈→S5 README滚动→S6功能介绍→S7结尾），使用 `/trending-to-video`。Web 管理台端口 8765，支持 `?repo=owner/name` 直达。语音优先本地 VoxCPM，回退 HuggingFace。启动：
> ```bash
> source /home/ppcorn/miniconda3/etc/profile.d/conda.sh && conda activate voxcpm && python3 <skill-dir>/scripts/web_ui.py --port 8765
> ```

如果 Trending 页面抓取失败（如被限流），回退为搜索 API：

```bash
curl -s "https://api.github.com/search/repositories?q=stars:>100&sort=stars&order=desc&per_page=10" | python3 -c "
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
data = json.load(sys.stdin)
for r in data.get('items', [])[:10]:
    stars = r['stargazers_count']
    lang = r.get('language') or 'Unknown'
    desc = (r.get('description') or '无描述').replace('\n', ' ')[:100]
    print(f'{r[\"full_name\"]}|?|{stars}|{lang}|{r[\"html_url\"]}|{desc}')
"
```

### 步骤 2：格式化输出

对每个仓库，整理以下信息：项目名称和链接、本周新增星标数、总星标数、主要语言、项目简介（一句话）、值得关注的理由（AI/工具/框架/新概念？）。

最终输出格式：

```markdown
---
tags: [github, trending]
date: !`date '+%Y-%m-%d'`
---

# 🔥 GitHub 热门快报 — !`date '+%Y-%m-%d'`

> 自动抓取，数据来源：GitHub Trending（本周）

| # | 项目 | ⭐ 本周新增 | ⭐ 总计 | 语言 | 简介 |
|---|------|------------|--------|------|------|
| 1 | **[owner/repo](url)** | X | Y | Python | 一句话描述 |

## 值得关注

- **owner/repo1**: 关注理由...
- **owner/repo2**: 关注理由...
```

### 步骤 3：保存笔记

将格式化后的内容保存到 Obsidian vault 下，路径和文件名：

```
Daily Notes/GitHub Trending/GitHub-Trending-!`date '+%Y-%m-%d'`.md
```

先确保目录存在（`mkdir -p`），再写入文件。

### 步骤 4：输出结果

在对话中展示快报摘要（前 5 个项目的简要列表），告知用户笔记保存位置。
