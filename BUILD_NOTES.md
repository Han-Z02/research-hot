# BUILD_NOTES — 科研HOT GitHub Pages 站（本地准备记录）

> 本文件记录本次本地准备的实际情况。**本站尚未部署、尚未上线**：
> 文件只在 `~/workspace/research-hot-site/`，没有创建 GitHub 仓库、
> 没有推送、没有向 GitHub 写任何东西。

## 做了什么

按 2026-11-13 用户确认的规格，在本地准备了 GitHub Pages 站的全部文件：

- `index.html`：单页静态站，报纸版式。含简易密码门（SHA-256 哈希比对，
  解锁状态只存 `sessionStorage`）、四栏（精选 / 最新 / 每周深读 / 收藏）、
  赛道 + 类型筛选、关键词搜索、星标收藏（`localStorage`）、卡片展开英文摘要、
  状态行（数据更新时间、篇数、来源）。
- `config.js`：密码哈希占位符 `REPLACE_WITH_SHA256_HASH` + 设置方法注释。
  **没有生成、没有编造任何真实密码或哈希。**
- `scripts/fetch_papers.py`：拉 Europe PMC + bioRxiv/medRxiv、去重、按三维规则
  打分、生成 `data/papers.json`。不用 OpenAlex（无 key 会 429）。
- `data/papers.json`：脚本真实跑出来的数据（见下）。
- `data/digest.json`：2026-11-12 期《AI文献日报》种子，仅标题 + DOI + 日期 +
  类型 + 来源，共 4 条。
- `.github/workflows/daily.yml`：每天 08:10 Asia/Shanghai（cron `10 0 * * *`，
  即 00:10 UTC）运行拉取脚本、提交数据变化、部署 Pages。
- `README.md`：站点说明、数据来源与评分规则、密码门设置与哈希命令、
  Gmail 日报合并方式、维护走 PR。

## 真实拉取结果（最后一次完整运行）

- 运行时间：2026-11-13 02:21 CST（UTC 2026-11-12 18:21），窗口
  2026-10-13 至 2026-11-12（近 30 天），耗时约 250 秒（主要在 bioRxiv 分页）。
- **总数 955 篇，errors 为空**。赛道：瘢痕与纤维化 236、单细胞与空间组学 424、
  口腔种植与植入物 295。
- 来源：Europe PMC 672、Europe PMC（预印本）112、bioRxiv 129、medRxiv 42。
  类型：Preprint 283、Method 264、Article 248、Review 160。
- 日报种子 4 篇 DOI 在 `papers.json` 里全部命中：
  SigDoTS、MorphoANOVA、THiRST（bioRxiv 补充拉取）、Spatialsnake。
  页面合并时其中 3 篇按 DOI 去重后加「邮箱日报」标记；THiRST 在早期
  版本中曾漏网，现已在库内。
- `data/papers.json` 2,347,323 字节。101 篇无 DOI、129 篇在 Europe PMC 中
  无摘要（卡片会显示“未提供摘要，见原文”，不编造）。
- 样例 Top 3（按规则分）：
  1. 63 分，2026-11-01，Spatial multiomics identifies rheumatoid arthritis
     synovial niches…（瘢痕赛道，Frontiers in Immunology）
  2. 62 分，2026-11-07，Single-cell and spatial transcriptomics of cellular
     heterogeneity in Alzheimer disease.
  3. 62 分，2026-11-05，TWEAK signaling drives the transition from psoriasis
     to atopic dermatitis-like inflammation…

## 修过的问题（真实发生）

1. 标题含 HTML 转义（`&lt;i&gt;` 等）：Europe PMC 返回转义标题，
   脚本现用 `html.unescape` + 去标签处理，重跑后为 0。
2. 混入 OTM 论文：首版含《Single-Cell Atlas of Human Orthodontic Tooth
   Movement》等 4 篇标题明确的 OTM / 正畸牙根吸收论文，已加排除规则
   （标题含 "orthodontic tooth movement" 或正畸相关 "root resorption"），
   重跑后标题中已无 OTM；种植支抗钉等种植器械类论文不在排除之列。
3. bioRxiv 补充拉取偏差：API 按日期升序、每页只返回 30 条，
   直接从头取只能拿到窗口最老的几百条，THiRST（11 月 9 日）一度漏网。
   已改为先取 total 再倒取最近 1200 条（40 页），THiRST 现已命中。
   更老的预印本主要靠 Europe PMC 覆盖；即使漏网，`digest.json` 里有
   的话页面合并后仍会显示。

## 验证结果（实际做过的）

- `scripts/fetch_papers.py` 真实跑通 3 次，最后一次 955 篇、errors 空；
  `data/papers.json`、`data/digest.json` 均可 JSON 解析。
- `config.js` 经 `node --check` 语法通过；`index.html` 内联 JS 经
  `node --check` 语法通过；`.github/workflows/daily.yml` 经 PyYAML 解析，
  cron 为 `10 0 * * *`（`on:` 已加引号，避免 YAML 1.1 把它当布尔值）。
- 本地静态服务器（`python3 -m http.server`）实测：`index.html` /
  `config.js` / `data/papers.json` / `data/digest.json` 均返回 HTTP 200，
  标题“科研HOT｜前沿文献雷达”可读。
- 密码门哈希算法验证：Node `crypto.subtle`（页面用的同一 API）与
  Python `hashlib` 对同一测试字符串算出的 SHA-256 完全一致
  （`7c13ab2e…`，测试串仅用于验证，未用作密码）。
- `index.html` 经字符串检查：密码门、四栏、筛选、搜索、收藏、摘要展开、
  `data/papers.json` / `data/digest.json` 引用均存在。

## 未验证项（诚实记录）

- **没有在真实浏览器里打开过页面**：本机无 Chromium / Firefox /
  Playwright，未做目检。密码门交互、四栏渲染、星标、搜索过滤只经过
  代码检查与语法验证，未经浏览器实测。
- **GitHub Actions 工作流未真实跑过**：YAML 可解析，但 Actions 环境
  下的拉取耗时、推送权限、Pages 部署均未验证；首次运行请在 Actions
  页手动点 Run workflow 观察。
- **生产环境每日 08:10 刷新未验证**：需上线后次日看数据更新时间。
- 首次运行耗时约 250 秒，工作流 `timeout-minutes: 20` 留有余量。

## 已知局限（写给韩和课题组）

- 组学赛道检索词较宽，精选 Top 里会混入少量与瘢痕 / 种植无关的
  空间组学论文（如类风湿关节炎滑膜、阿尔茨海默病空间图谱）。
  这是按确认的三维规则算分的结果，不是编造；后续可收紧为
  “必须同时命中赛道锚词”，改动前请先确认。
- 密码门是简易门：`data/papers.json` 在仓库明文，懂行者直接读
  数据文件可绕过，只防随手点开的外人，不是真加密。
- 收藏只保存在各人浏览器，不共享；课题组共享的“精选”只能由
  韩在 Muse 私人空间星标后同步，或后续在库里维护一份清单。

## 还缺什么（被阻塞的两件事）

1. **用户手动建库并授权**：韩已于 2026-11-13 02:18 手动新建公开库
   `Han-Z02/research-hot`（main 分支，README 仅 `# research-hot`，
   Muse 读库已核实可用）。仍需韩在 GitHub 上给 Muse App 装上该库
   授权，Muse 才能推文件；推库后还需在仓库 Settings → Pages 里确认
   Pages 来源（建议 GitHub Actions）。
2. **密码哈希**：`config.js` 里仍是占位符 `REPLACE_WITH_SHA256_HASH`，
   替换前密码门会提示未设置、站点打不开。韩需在自己电脑上用
   README 里的方法算出新密码的 SHA-256 哈希，只发哈希（绝不在聊天
   里发密码原文），由 Muse 填入后随首批文件一起推送。

完成后请按此核对：推库 → Actions 首次运行成功 → 打开
https://han-z02.github.io/research-hot/ 输密码进入 → 状态行显示
当日数据更新时间与“邮箱日报已合并”类标记。
