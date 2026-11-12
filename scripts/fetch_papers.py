#!/usr/bin/env python3
"""
科研HOT | 前沿文献雷达 — 数据拉取脚本
=====================================
来源（全部免 key 公开 API，不用 OpenAlex —— 无 key 会返回 429）：
  1. Europe PMC（主源）：覆盖 PubMed 已发表文献，也索引 bioRxiv / medRxiv 预印本
     https://www.ebi.ac.uk/europepmc/webservices/rest/search
  2. bioRxiv / medRxiv API（补充）：按日期拉取，再按关键词过滤，补 Europe PMC
     尚未索引的预印本（例如 THiRST 在 Europe PMC 中查不到）
     https://api.biorxiv.org/details/biorxiv/<from>/<to>/<cursor>/json
     https://api.biorxiv.org/details/medrxiv/<from>/<to>/<cursor>/json

Gmail《AI文献日报》不在这个脚本里：GitHub Actions 读不了 Gmail。
日报由 Muse 每天 08:00 读完邮件后，只提取标题 + DOI 写进 data/digest.json，
按 DOI 去重合并；本脚本不碰 digest.json。

评分（三维规则算分，不用 LLM、不编造结论）：
  期刊分 40：CNS 正刊 40；CNS 子刊 / Nat Commun / Sci Adv 32；
            领域顶刊 24；其他有刊名 SCI 16；预印本 12
  相关度 40：标题+摘要命中课题关键词，每命中 1 个不同关键词 +5，上限 40
  时效分 20：近 7 天 20；8-14 天 14；15-30 天 8；30 天外 0
推荐理由用模板拼（档位 + 命中的关键词 + 时效），不自由发挥写结论。
英文原题不机翻。

用法：
  python3 scripts/fetch_papers.py [--days 30] [--out data/papers.json] [--today YYYY-MM-DD]
  失败时不覆盖旧文件，退出码 1（Actions 里旧数据保留，页面照常显示）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "papers.json"
UA = {"User-Agent": "research-hot-fetch/1.0 (Han-Z02/research-hot; contact via GitHub)"}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
TIMEOUT = 30

# ---------------------------------------------------------------- 赛道与检索
TRACKS = {
    "scar": {
        "label": "病理性瘢痕与纤维化",
        "queries": [
            '(keloid OR "hypertrophic scar" OR "pathological scar" OR "skin fibrosis")',
            '(POSTN OR TACR1 OR TAC1) AND (scar OR fibrosis OR skin OR fibroblast)',
        ],
    },
    "omics": {
        "label": "单细胞与空间组学方法",
        "queries": [
            '("spatial transcriptomics" OR "single-cell RNA" OR Visium OR cell2location OR deconvolution OR "spatial domain")',
        ],
    },
    "implant": {
        "label": "口腔种植与植入物纤维化",
        "queries": [
            '("dental implant" OR "peri-implant" OR osseointegration OR "implant fibrosis" OR "maxillofacial surgery" OR "alveolar bone")',
        ],
    },
}

# 相关度关键词：(关键词, 展示名)
RELEVANCE_KEYWORDS = [
    ("POSTN", "POSTN"), ("TACR1", "TACR1"), ("TAC1", "TAC1"),
    ("keloid", "瘢痕疙瘩"), ("hypertrophic scar", "增生性瘢痕"),
    ("pathological scar", "病理性瘢痕"), ("skin fibrosis", "皮肤纤维化"),
    ("fibroblast", "成纤维细胞"), ("neurovascular", "神经-血管"),
    ("substance P", "P 物质"), ("TRPV1", "TRPV1"),
    ("Visium", "Visium"), ("cell2location", "cell2location"),
    ("spatial transcriptomics", "空间转录组"), ("spatial domain", "空间域"),
    ("deconvolution", "反卷积"), ("single-cell", "单细胞"),
    ("dental implant", "口腔种植"), ("peri-implant", "种植体周围"),
    ("osseointegration", "骨结合"), ("implant fibrosis", "植入物纤维化"),
    ("maxillofacial", "颌面外科"),
]

# bioRxiv / medRxiv 补充拉取时用的过滤词（小写）
PREPRINT_FILTER = [
    "keloid", "hypertrophic scar", "pathological scar", "skin fibrosis",
    "postn", "tacr1", "tac1", "spatial transcriptomics", "visium",
    "cell2location", "deconvolution", "spatial domain", "single-cell",
    "dental implant", "peri-implant", "osseointegration",
    "implant fibrosis", "maxillofacial", "fibroblast",
]

def clean_text(s: str) -> str:
    """Europe PMC 会返回 HTML 转义（如 &lt;i&gt;）和内联标签，先解码再去标签。"""
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


# 明确不收的内容（用户 2026-11-13 确认）：正畸牙吸收 / OTM。
# 只排除标题明确是 OTM / 正畸相关牙根吸收的论文；种植支抗钉等
# 种植器械类论文不在此列。
def is_excluded(title: str, abstract: str) -> bool:
    t = (title or "").lower()
    a = (abstract or "").lower()
    if "orthodontic tooth movement" in t or "orthodontic-induced" in t:
        return True
    if "root resorption" in t and "orthodontic" in (t + " " + a):
        return True
    return False


# ---------------------------------------------------------------- 期刊档位
TIER_S = {  # 40 分
    "nature", "science", "cell",
    "new england journal of medicine", "lancet", "jama",
}
TIER_A_SUBSTR = (  # 32 分：CNS 子刊 / Nat Commun / Sci Adv 等
    "nature medicine", "nature genetics", "nature cell biology",
    "nature biotechnology", "nature communications", "nature biomedical",
    "science advances", "science immunology", "science translational",
    "cell reports", "cell stem cell", "cell discovery",
    "journal of clinical investigation",
)
TIER_B_SUBSTR = (  # 24 分：领域顶刊
    "journal of investigative dermatology", "wound repair and regeneration",
    "biomaterials", "advanced science", "journal of dental research",
    "clinical oral implants research", "journal of periodontology",
    "journal of clinical periodontology", "bone", "biomaterials science",
    "journal of tissue engineering", "matrix biology",
    "frontiers in immunology", "frontiers in cell and developmental biology",
)


def journal_score(journal: str, is_preprint: bool) -> tuple[int, str]:
    if is_preprint:
        return 12, "预印本"
    j = (journal or "").strip().lower()
    if not j:
        return 16, "其他 SCI"
    if j in TIER_S:
        return 40, "CNS 正刊"
    if any(s in j for s in TIER_A_SUBSTR) or j.startswith("nature ") or j.startswith("cell "):
        return 32, "CNS 子刊"
    if any(s in j for s in TIER_B_SUBSTR):
        return 24, "领域顶刊"
    return 16, "其他 SCI"


def days_ago(date_str: str, today: dt.date) -> int | None:
    if not date_str:
        return None
    try:
        d = dt.date.fromisoformat(date_str[:10])
    except ValueError:
        return None
    return (today - d).days


def recency_score(d: int | None) -> tuple[int, str]:
    if d is None:
        return 0, "日期未知"
    if d <= 7:
        return 20, f"近 {d} 天发表" if d > 0 else "今日发表"
    if d <= 14:
        return 14, f"{d} 天前发表"
    if d <= 30:
        return 8, f"{d} 天前发表"
    return 0, f"{d} 天前发表"


def relevance(keywords_text: str) -> tuple[int, list[str]]:
    low = keywords_text.lower()
    matched: list[str] = []
    for kw, label in RELEVANCE_KEYWORDS:
        if kw.lower() in low and label not in matched:
            matched.append(label)
    return min(40, 5 * len(matched)), matched


def classify_type(title: str, abstract: str, pub_types: list[str], is_preprint: bool) -> str:
    if is_preprint:
        return "Preprint"
    joined = " ".join(pub_types).lower()
    if "review" in joined:
        return "Review"
    text = (title + " " + abstract).lower()
    if any(w in text for w in ("algorithm", "workflow", "pipeline", "tool", "method", "framework", "benchmark")):
        return "Method"
    return "Article"


def make_reason(tier_label: str, matched: list[str], recency_label: str) -> str:
    kw = "、".join(matched[:2]) if matched else "与赛道相关"
    return f"{tier_label} + 命中{kw} + {recency_label}"


# ---------------------------------------------------------------- HTTP
def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def fetch_json_retry(url: str, tries: int = 3) -> dict:
    last: Exception | None = None
    for i in range(tries):
        try:
            return fetch_json(url)
        except Exception as e:  # noqa: BLE001 - 网络抖动时重试，失败记入 errors
            last = e
            time.sleep(2 * (i + 1))
    raise last  # type: ignore[misc]


# ---------------------------------------------------------------- Europe PMC
def fetch_epmc(track: str, query: str, start: str, end: str, today: dt.date) -> list[dict]:
    out: list[dict] = []
    cursor = "*"
    for _page in range(3):  # 每条检索最多 3 页 × 100 条，避免单次运行过重
        q = f"({query}) AND FIRST_PDATE:[{start} TO {end}]"
        url = (
            f"{EPMC}?query={urllib.parse.quote(q)}"
            f"&format=json&pageSize=100&resultType=core&cursorMark={urllib.parse.quote(cursor)}"
        )
        data = fetch_json_retry(url)
        results = data.get("resultList", {}).get("result", [])
        for r in results:
            out.append(normalise_epmc(r, track, today))
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor or not results:
            break
        cursor = nxt
    return out


def normalise_epmc(r: dict, track: str, today: dt.date) -> dict:
    journal_info = r.get("journalInfo", {}) or {}
    journal = (journal_info.get("journal", {}) or {}).get("title", "") or ""
    date = r.get("firstPublicDate") or r.get("firstIndexDate") or ""
    doi = (r.get("doi") or "").strip()
    pmid = (r.get("pmid") or "").strip()
    title = clean_text(r.get("title") or "")
    abstract = clean_text(r.get("abstractText") or "")
    source = (r.get("source") or "").strip()
    is_preprint = source.upper() == "PPR" or "preprint" in (r.get("pubTypeList", {}) or {}).get("pubType", [""])[0].lower() if r.get("pubTypeList") else False
    # Europe PMC 预印本的 source 是 PPR；再以刊名含 bioRxiv/medRxiv 兜底
    if not is_preprint and ("biorxiv" in journal.lower() or "medrxiv" in journal.lower()):
        is_preprint = True
    pub_types = []
    pt = r.get("pubTypeList", {}) or {}
    if isinstance(pt.get("pubType"), list):
        pub_types = [str(x) for x in pt["pubType"]]
    j_score, tier_label = journal_score(journal, is_preprint)
    d = days_ago(date, today)
    r_score, recency_label = recency_score(d)
    rel_score, matched = relevance(title + " " + abstract)
    total = j_score + rel_score + r_score
    return {
        "id": doi or pmid or title,
        "title": title,
        "abstract": abstract,
        "journal": journal or ("bioRxiv" if is_preprint else ""),
        "journal_tier": tier_label,
        "date": date[:10] if date else "",
        "doi": doi,
        "pmid": pmid,
        "pmcid": (r.get("pmcid") or "").strip(),
        "url": f"https://doi.org/{doi}" if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""),
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        "type": classify_type(title, abstract, pub_types, is_preprint),
        "is_preprint": bool(is_preprint),
        "is_open_access": bool(r.get("isOpenAccess")),
        "track": track,
        "score": {"total": total, "journal": j_score, "relevance": rel_score, "recency": r_score},
        "reason": make_reason(tier_label, matched, recency_label),
        "keywords_matched": matched,
        "source": "Europe PMC" + (" (preprint)" if is_preprint else ""),
    }


# ---------------------------------------------------------------- bioRxiv / medRxiv
def fetch_preprint_server(server: str, start: str, end: str, today: dt.date, track: str = "omics") -> list[dict]:
    """按日期拉取，标题+摘要含关键词才留。
    注意：bioRxiv API 按日期升序返回（第 0 页是最老的一天），
    30 天窗口约有 7000 条，每页只返回 30 条，直接从头取只能
    拿到最老的几百条。所以先取 1 页拿到 total，再从 total-1200
    处倒取最近 1200 条（最多 40 页）；更老的预印本主要靠
    Europe PMC 覆盖。即使某篇预印本这里仍漏网，digest.json
    里有它时页面合并后仍会显示（标“邮箱日报”）。
    """
    out: list[dict] = []
    first = fetch_json_retry(f"https://api.biorxiv.org/details/{server}/{start}/{end}/0/json")
    try:
        total = int((first.get("messages") or [{}])[0].get("total") or 0)
    except (ValueError, TypeError):
        total = 0
    if total <= 0:
        return out
    cursor = max(0, total - 1200)
    pages = 40 if total > 1200 else (total + 29) // 30
    for _page in range(pages):
        url = f"https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}/json"
        # total<=2000 时第 0 页就是 first，已取过，直接复用
        data = first if (total <= 2000 and cursor == 0 and _page == 0) else fetch_json_retry(url)
        collection = data.get("collection", [])
        if not collection:
            break
        for c in collection:
            text = ((c.get("title") or "") + " " + (c.get("abstract") or "")).lower()
            if not any(k in text for k in PREPRINT_FILTER):
                continue
            out.append(normalise_preprint(c, server, today))
        cursor += len(collection)
        if cursor >= total:
            break
    return out


def normalise_preprint(c: dict, server: str, today: dt.date) -> dict:
    title = clean_text(c.get("title") or "")
    abstract = clean_text(c.get("abstract") or "")
    date = (c.get("date") or "")[:10]
    doi = (c.get("doi") or "").strip()
    d = days_ago(date, today)
    r_score, recency_label = recency_score(d)
    rel_score, matched = relevance(title + " " + abstract)
    j_score, tier_label = journal_score("", True)
    total = j_score + rel_score + r_score
    # 赛道归属：按命中词判断，默认 omics
    low = (title + " " + abstract).lower()
    if any(k in low for k in ("keloid", "hypertrophic scar", "pathological scar", "skin fibrosis", "postn", "tacr1")):
        track = "scar"
    elif any(k in low for k in ("dental implant", "peri-implant", "osseointegration", "maxillofacial")):
        track = "implant"
    else:
        track = "omics"
    return {
        "id": doi or title,
        "title": title,
        "abstract": abstract,
        "journal": "bioRxiv" if server == "biorxiv" else "medRxiv",
        "journal_tier": tier_label,
        "date": date,
        "doi": doi,
        "pmid": "",
        "pmcid": "",
        "url": f"https://doi.org/{doi}" if doi else "",
        "pubmed_url": "",
        "type": "Preprint",
        "is_preprint": True,
        "is_open_access": True,
        "track": track,
        "score": {"total": total, "journal": j_score, "relevance": rel_score, "recency": r_score},
        "reason": make_reason(tier_label, matched, recency_label),
        "keywords_matched": matched,
        "source": "bioRxiv" if server == "biorxiv" else "medRxiv",
    }


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    ap.add_argument("--today", type=str, default="")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    end = today.isoformat()
    start = (today - dt.timedelta(days=args.days)).isoformat()
    errors: list[str] = []
    by_key: dict[str, dict] = {}

    def add(paper: dict, track: str) -> None:
        if not paper.get("title"):
            return
        if is_excluded(paper.get("title", ""), paper.get("abstract", "")):
            return
        key = (paper.get("doi") or "").lower() or (paper.get("pmid") or "") or paper["title"].strip().lower()
        if key in by_key:
            old = by_key[key]
            # 去重：保留分数高的那条；合并赛道归属
            if paper["score"]["total"] > old["score"]["total"]:
                paper["track"] = old["track"]
                by_key[key] = paper
            return
        paper["track"] = track
        by_key[key] = paper

    for track, cfg in TRACKS.items():
        for q in cfg["queries"]:
            try:
                for p in fetch_epmc(track, q, start, end, today):
                    add(p, track)
            except Exception as e:  # noqa: BLE001 - 单条检索失败不中断整体
                errors.append(f"Europe PMC [{track}] {q[:60]}: {e}")
                print(f"[warn] Europe PMC failed [{track}]: {e}", file=sys.stderr)

    for server in ("biorxiv", "medrxiv"):
        try:
            for p in fetch_preprint_server(server, start, end, today):
                add(p, p["track"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"{server}: {e}")
            print(f"[warn] {server} failed: {e}", file=sys.stderr)

    papers = sorted(by_key.values(), key=lambda p: (-p["score"]["total"], p.get("date", "")), reverse=False)
    # 上面排序：分数降序、日期降序——用两次稳定排序更直观
    papers = sorted(papers, key=lambda p: p.get("date", ""), reverse=True)
    papers = sorted(papers, key=lambda p: p["score"]["total"], reverse=True)

    if not papers:
        print("[error] no papers fetched; keeping old file", file=sys.stderr)
        print("errors:", errors, file=sys.stderr)
        return 1

    by_track = {t: sum(1 for p in papers if p["track"] == t) for t in TRACKS}
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "generated_at_local": f"{today.isoformat()} (Asia/Shanghai, 08:10 刷新)",
        "window": {"start": start, "end": end, "days": args.days},
        "total": len(papers),
        "by_track": by_track,
        "sources": sorted({p["source"].split(" ")[0] for p in papers}),
        "errors": errors,
        "papers": papers,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"fetched {len(papers)} papers, by_track={by_track}, errors={len(errors)}")
    print(f"wrote {out}")
    for p in papers[:10]:
        print(f"  {p['score']['total']:3d} [{p['track']}] {p['date']} {p['title'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
