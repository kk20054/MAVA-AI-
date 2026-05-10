import ast
import datetime
import hashlib
import json
import math
import re
from urllib.parse import urlparse


def _loads_maybe(value):
    if isinstance(value, (list, dict)):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(text)
        except Exception:
            pass
    return None


def _unwrap_results(raw):
    parsed = _loads_maybe(raw)
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return []
    for key in ("final_result", "web_result", "result", "results", "data"):
        if key in parsed:
            inner = _loads_maybe(parsed.get(key))
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                for nested in ("result", "results", "items"):
                    if isinstance(inner.get(nested), list):
                        return inner[nested]
    return []


def _as_list(value):
    parsed = _loads_maybe(value)
    if isinstance(parsed, list):
        return [str(x).strip() for x in parsed if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[,，|/、\s]+", value) if x.strip()]
    return []


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _tokenize(text):
    text = str(text or "")
    words = re.findall(r"[A-Za-z][A-Za-z0-9+./-]*|\d+(?:\.\d+)?%?|[\u4e00-\u9fff]{2,}", text.lower())
    stop = {"最新", "今日", "今天", "最近", "当前", "查询", "帮我", "一下", "多少", "是什么", "参考日期"}
    return [w for w in words if w not in stop]


def _extract_dates(text):
    dates = []
    for y, m, d in re.findall(r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})", text):
        try:
            dates.append(datetime.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    return dates


def _domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _recency_score(dates, current_date):
    if not dates:
        return 0.0
    best = min(abs((current_date - d).days) for d in dates)
    if best <= 1:
        return 1.0
    if best <= 3:
        return 0.85
    if best <= 7:
        return 0.65
    if best <= 31:
        return 0.35
    return 0.05


def _source_score(url, title, content, query_type):
    dom = _domain(url)
    text = f"{title} {content}".lower()
    score = 0.0
    if any(x in dom for x in ("hkab.org.hk", "hkma.gov.hk", "info.gov.hk", "pbc.gov.cn")):
        score += 1.0
    elif any(x in dom for x in ("bochk.com", "hsbc.com.hk", "hangseng.com", "icbcasia.com")):
        score += 0.65
    elif any(x in dom for x in ("eastmoney.com", "fx678.com", "investing.com")):
        score += 0.45
    elif any(x in dom for x in ("baidu.com", "cngold.org")):
        score += 0.15
    if query_type == "MARKET_RATE" and ("利率" in text or "rate" in text):
        score += 0.15
    return min(score, 1.0)


def _evidence_score(text):
    score = 0.0
    if re.search(r"\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*bp", text, re.I):
        score += 0.35
    if re.search(r"(隔夜|overnight|o/n|1\s*个月|1m|3\s*个月|3m|一周|1w|期限|tenor)", text, re.I):
        score += 0.3
    if "|" in text and "---" in text:
        score += 0.2
    if _extract_dates(text):
        score += 0.15
    return min(score, 1.0)


def _offtopic_penalty(text, query, protected_terms):
    t = text.lower()
    q = query.lower()
    penalty = 0.0
    if "hibor" in q or "同业拆息" in q:
        has_hibor = any(term.lower() in t for term in protected_terms) or "同业拆息" in t
        if not has_hibor:
            penalty += 0.55
        if ("lpr" in t or "贷款基准利率" in t or "公积金" in t) and not has_hibor:
            penalty += 0.35
        if "按揭贷款计划" in t and "最新" not in t:
            penalty += 0.15
    return min(penalty, 0.9)


def _compress_content(content, terms, max_chars):
    content = re.sub(r"\n{3,}", "\n\n", str(content or "")).strip()
    if len(content) <= max_chars:
        return content
    lowered = content.lower()
    positions = []
    for term in terms:
        if not term:
            continue
        idx = lowered.find(term.lower())
        if idx >= 0:
            positions.append(idx)
    if not positions:
        return content[:max_chars]
    center = min(positions)
    start = max(0, center - max_chars // 3)
    end = min(len(content), start + max_chars)
    return content[start:end].strip()


def _dedupe_key(title, url, content):
    raw = (url or title or content[:200]).strip().lower()
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()


def main(args: dict) -> dict:
    """
    知识问答链路 v10 - Step 3A
    联网结果多信号筛选。重点修复：relevance 为 0 但实体、日期、数值命中的结果被误删。
    """
    raw_result = args.get("web_result", args.get("result", ""))
    user_query = str(args.get("user_query", args.get("query", ""))).strip()
    rewritten_query = str(args.get("rewritten_query", "")).strip()
    query_type = str(args.get("query_type", "")).strip().upper()
    freshness_required = str(args.get("freshness_required", "")).lower() in ("true", "1", "yes") or bool(args.get("freshness_required") is True)
    keywords = _as_list(args.get("search_keywords", ""))
    protected_terms = _as_list(args.get("protected_terms", ""))
    threshold = _to_float(args.get("threshold", 0.18), 0.18)
    top_k = int(_to_float(args.get("top_k", 5), 5))
    min_keep = int(_to_float(args.get("min_keep", 2), 2))
    max_chars = int(_to_float(args.get("max_chars_per_item", 1800), 1800))

    try:
        current_date = datetime.datetime.strptime(str(args.get("currentTime", ""))[:10], "%Y-%m-%d").date()
    except Exception:
        current_date = datetime.date.today()

    query_text = " ".join([user_query, rewritten_query] + keywords + protected_terms)
    terms = []
    seen_terms = set()
    for item in protected_terms + keywords + _tokenize(query_text):
        key = item.lower()
        if item and key not in seen_terms:
            terms.append(item)
            seen_terms.add(key)

    results = _unwrap_results(raw_result)
    if not results:
        return {"final_result": json.dumps([], ensure_ascii=False), "has_result": False, "diagnostics": "empty_web_results"}

    processed = []
    seen = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or item.get("name", "")).strip()
        url = str(item.get("url", "") or item.get("link", "")).strip()
        content = str(item.get("content", "") or item.get("snippet", "") or item.get("summary", "")).strip()
        if not content and isinstance(item.get("data"), dict):
            data = item["data"]
            title = title or str(data.get("title", ""))
            content = str(data.get("content", "") or data.get("snippet", ""))
        if not content and not title:
            continue

        key = _dedupe_key(title, url, content)
        if key in seen:
            continue
        seen.add(key)

        raw_rel = _to_float(item.get("relevance", item.get("score", 0.0)), 0.0)
        rel_norm = max(0.0, min(raw_rel, 1.0))
        full_text = f"{title}\n{content}"
        full_lower = full_text.lower()

        exact_hits = [term for term in protected_terms if term and term.lower() in full_lower]
        keyword_hits = [term for term in terms if term and term.lower() in full_lower]
        lexical = min(len(set(x.lower() for x in keyword_hits)) / max(len(set(x.lower() for x in terms)), 1), 1.0)
        exact = min(len(exact_hits) / max(len(protected_terms), 1), 1.0)
        dates = _extract_dates(full_text + " " + url)
        fresh = _recency_score(dates, current_date)
        source = _source_score(url, title, content, query_type)
        evidence = _evidence_score(full_text)
        penalty = _offtopic_penalty(full_text, user_query + " " + rewritten_query, protected_terms)

        final_score = (
            0.24 * rel_norm
            + 0.28 * exact
            + 0.16 * lexical
            + 0.14 * fresh
            + 0.10 * source
            + 0.12 * evidence
            - penalty
        )
        final_score = max(0.0, round(final_score, 4))

        protected = bool(exact_hits and (evidence >= 0.35 or fresh >= 0.35 or rel_norm >= 0.55))
        if freshness_required and query_type == "MARKET_RATE" and exact_hits and dates:
            protected = True

        reasons = []
        if exact_hits:
            reasons.append("实体命中:" + "/".join(exact_hits[:3]))
        if dates:
            reasons.append("包含日期:" + max(dates).isoformat())
        if evidence >= 0.35:
            reasons.append("包含数值/期限证据")
        if source >= 0.45:
            reasons.append("来源可用")
        if raw_rel > 0:
            reasons.append("原始相关度:" + str(raw_rel))

        processed.append({
            "source": "WEB",
            "title": title,
            "url": url,
            "relevance": raw_rel,
            "final_score": final_score,
            "protected": protected,
            "low_confidence": final_score < 0.35 and not protected,
            "match_reason": "；".join(reasons) if reasons else "弱匹配",
            "content": _compress_content(content, terms, max_chars),
            "raw_data": item,
        })

    if not processed:
        return {"final_result": json.dumps([], ensure_ascii=False), "has_result": False, "diagnostics": "no_valid_web_items"}

    protected_items = [x for x in processed if x["protected"]]
    scored_items = [x for x in processed if x["final_score"] >= threshold]
    selected_map = {}
    for item in sorted(protected_items + scored_items, key=lambda x: (x["protected"], x["final_score"], x["relevance"]), reverse=True):
        selected_map[_dedupe_key(item["title"], item["url"], item["content"])] = item

    selected = list(selected_map.values())
    if len(selected) < min_keep:
        for item in sorted(processed, key=lambda x: (x["final_score"], x["relevance"]), reverse=True):
            selected_map[_dedupe_key(item["title"], item["url"], item["content"])] = item
            selected = list(selected_map.values())
            if len(selected) >= min_keep:
                break

    selected = sorted(selected, key=lambda x: (x["protected"], x["final_score"], x["relevance"]), reverse=True)[:top_k]
    return {
        "final_result": json.dumps(selected, ensure_ascii=False),
        "has_result": bool(selected),
        "diagnostics": json.dumps({
            "input_count": len(results),
            "processed_count": len(processed),
            "selected_count": len(selected),
            "protected_count": len([x for x in selected if x["protected"]]),
            "threshold": threshold,
        }, ensure_ascii=False),
    }
