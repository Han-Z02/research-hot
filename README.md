# 科研HOT｜前沿文献雷达

课题组内部的前沿文献雷达：病理性瘢痕与纤维化、单细胞与空间组学方法、
口腔种植与植入物纤维化。每天自动刷新，打开即看。

- 在线地址：https://han-z02.github.io/research-hot/ （需密码解锁）
- 私人版（仅韩）：Muse 侧边栏「科研HOT」空间（另含 Gmail 日报全文笔记与持久收藏同步）

## 栏目

| 栏目 | 内容 |
|---|---|
| 精选 | 近 7 天综合分 Top 10 + 按天分组 |
| 最新 | 按发表时间倒序 |
| 每周深读 | 上周（周一至周日）综合分 Top 7 |
| 收藏 | 星标，保存在本浏览器（localStorage），不受 30 天窗口限制 |

筛选：3 个赛道 + 类型（Article / Review / Preprint / Method）+ 关键词搜索。
不收正畸牙吸收 / OTM（标题明确是正畸牙移动或正畸相关牙根吸收的论文会被排除）。

## 数据来源与评分

数据源（全部免 key 公开 API）：

- **Europe PMC（主源）**：覆盖 PubMed 已发表文献，也索引 bioRxiv / medRxiv 预印本。
- **bioRxiv / medRxiv API（补充）**：按日期拉取、按关键词过滤，补 Europe PMC
  尚未索引的预印本。注意 bioRxiv API 按日期升序、每页 30 条，
  脚本先取 total 再倒取最近 1200 条；更老的预印本主要靠 Europe PMC。
- **不用 OpenAlex**：无 key 会返回 429，期刊档位改用策展名单（见脚本）。

评分（三维规则算分，不用 LLM、不编造结论）：

- 期刊分量 40：CNS 正刊 40；CNS 子刊 / Nat Commun / Sci Adv 32；
  领域顶刊 24；其他有刊名 SCI 16；预印本 12。
- 课题相关度 40：标题 + 摘要命中课题关键词（POSTN、TACR1、Visium、
  cell2location、瘢痕疙瘩、口腔种植等），每命中 1 个不同关键词 +5，上限 40。
- 时效 20：近 7 天 20；8–14 天 14；15–30 天 8。
- 推荐理由用模板拼（档位 + 命中的关键词 + 时效），不自由发挥写结论。
- 英文原题不机翻；预印本标「Preprint · 未同行评审」；收最近 30 天。

已知局限：组学赛道的检索词较宽，精选 Top 里会混入少量与瘢痕 / 种植
无关的空间组学论文（如其他疾病的空间图谱）；后续可收紧为“必须同时
命中赛道锚词”。评分规则改动请先在 PR 里说明。

## 密码门（简易密码门，不是真加密）

打开站先输密码，输对才显示内容；解锁状态只保留在当前标签页会话
（sessionStorage），关掉标签页需重输。站里只存密码的 SHA-256 哈希，
不存明文密码。

**局限必须如实告诉课题组**：`data/papers.json` 在仓库里仍是明文，
懂行的人直接读数据文件就能绕过密码门，只防随手点开的外人。
文献本身都是公开的，锁只是限定课题组范围。

设置 / 更换密码（密码原文绝不在聊天里发）：

```bash
# 在你自己的电脑上算哈希（macOS / Linux）
printf '%s' '你的新密码' | shasum -a 256
# Windows PowerShell
(New-Object System.Security.Cryptography.SHA256Managed).ComputeHash(
  [Text.Encoding]::UTF8.GetBytes('你的新密码')) |
  ForEach-Object { $_.ToString('x2') } -join ''
```

只把算出来的 64 位十六进制哈希发给 Muse，填进 `config.js` 的
`PASSWORD_SHA256`（替换 `REPLACE_WITH_SHA256_HASH` 占位符）；
或你自己改这个文件后提 PR。哈希换了之后，课题组需用新密码重新解锁。

## Gmail 日报如何合并

GitHub Actions 读不了 Gmail，所以日报**不由 Actions 拉取**：

1. Muse 每天 08:00 读完 Gmail 里当日《AI文献日报》后，只提取
   **标题 + DOI**，写进 `data/digest.json`，按 DOI 去重合并；
   不放邮件原文和中文日报笔记。
2. 页面加载时把 `digest.json` 与 `data/papers.json` 按 DOI 合并：
   已在文献库里的加「邮箱日报」标记；不在的补一条仅标题 + DOI 的卡。
3. 种子：2026-11-12 期 4 条（SigDoTS、MorphoANOVA、THiRST、Spatialsnake，
   均为 bioRxiv 预印本）。GSE307504 是数据资源不是论文，不做成卡，
   只在这里提一句：瘢痕 scRNA 42,607 细胞 + Visium，可作 TACR1 / 内皮
   邻域假设的外部对照，每种瘢痕空间组仅 1 张切片。

## 自动刷新

`.github/workflows/daily.yml` 每天 08:10 Asia/Shanghai（00:10 UTC）
运行 `scripts/fetch_papers.py`，更新 `data/papers.json` 后提交并部署
Pages。手动刷新：在 GitHub 仓库 Actions 页点 Run workflow。

本地手动跑一次：

```bash
python3 scripts/fetch_papers.py --days 30   # 写 data/papers.json
python3 -m http.server 8000                  # 浏览器打开 http://localhost:8000/
```

## 维护

- 改动走 PR 给韩审，不直接推 main。
- 改检索词、评分档位或栏目时，同步改 `scripts/fetch_papers.py`、
  `index.html` 和本 README 的对应章节，并在 PR 说明里写清影响。
- 文件结构：`index.html`（单页站）`config.js`（密码哈希占位符）
  `data/papers.json`（每日生成）`data/digest.json`（日报种子）
  `scripts/fetch_papers.py`（拉取 + 打分）`.github/workflows/daily.yml`。
