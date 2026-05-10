import ast
import datetime
import hashlib
import json
import re


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
    # 兼容不同工作流节点命名：BKS 节点常见 raw_result/result/bks_result/final_result
    for key in ("raw_result", "final_result", "bks_result", "result", "results", "data", "items"):
        if key in parsed:
            inner = _loads_maybe(parsed.get(key))
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                for nested in ("raw_result", "result", "results", "items", "data"):
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
    return re.findall(r"[A-Za-z][A-Za-z0-9+./-]*|\d+(?:\.\d+)?%?|[\u4e00-\u9fff]{2,}", str(text or "").lower())


def _extract_dates(text):
    dates = []
    for y, m, d in re.findall(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})", str(text or "")):
        try:
            dates.append(datetime.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    return dates


def _compress_content(content, terms, max_chars):
    content = re.sub(r"\n{3,}", "\n\n", str(content or "")).strip()
    if len(content) <= max_chars:
        return content
    lowered = content.lower()
    positions = [lowered.find(t.lower()) for t in terms if t and lowered.find(t.lower()) >= 0]
    if not positions:
        return content[:max_chars]
    center = min(positions)
    start = max(0, center - max_chars // 3)
    end = min(len(content), start + max_chars)
    return content[start:end].strip()


def _dedupe_key(title, content):
    raw = (title or content[:220]).strip().lower()
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()


def _extract_item(item):
    data = item.get("data", item) if isinstance(item, dict) else {}
    if not isinstance(data, dict):
        return "", "", 0.0, item
    snippet = data.get("snippet", {})
    if isinstance(snippet, dict):
        title = str(snippet.get("title", "") or data.get("title", "")).strip()
        content = str(snippet.get("content", "") or data.get("content", "")).strip()
    else:
        title = str(data.get("title", "")).strip()
        content = str(data.get("content", "") or snippet).strip()
    relevance = _to_float(data.get("relevance", data.get("score", item.get("relevance", 0.0))), 0.0)
    return title, content, relevance, item


def main(args: dict) -> dict:
    """
    知识问答链路 v10 - Step 3B
    BKS 结果多信号筛选。内部制度问题保知识库优先；市场实时问题将知识库作为背景，避免旧材料压过联网结果。
    """
    def first_arg(*names):
        for name in names:
            value = args.get(name)
            if value not in (None, "", [], {}):
                return value
        return ""

    raw_result = first_arg("bks_result", "raw_result", "result", "final_result", "results")
    user_query = str(args.get("user_query", args.get("query", ""))).strip()
    rewritten_query = str(args.get("rewritten_query", "")).strip()
    query_type = str(args.get("query_type", "")).strip().upper()
    freshness_required = str(args.get("freshness_required", "")).lower() in ("true", "1", "yes") or bool(args.get("freshness_required") is True)
    keywords = _as_list(first_arg("search_keywords", "keywords", "keyword", "query_keywords"))
    protected_terms = _as_list(args.get("protected_terms", ""))
    threshold = _to_float(args.get("threshold", 0.16), 0.16)
    top_k = int(_to_float(args.get("top_k", 4), 4))
    min_keep = int(_to_float(args.get("min_keep", 1), 1))
    max_chars = int(_to_float(args.get("max_chars_per_item", 2200), 2200))

    try:
        current_date = datetime.datetime.strptime(str(args.get("currentTime", ""))[:10], "%Y-%m-%d").date()
    except Exception:
        current_date = datetime.date.today()

    query_text = " ".join([user_query, rewritten_query] + keywords + protected_terms)
    terms = []
    seen_terms = set()
    for term in protected_terms + keywords + _tokenize(query_text):
        key = str(term).lower()
        if term and key not in seen_terms:
            terms.append(term)
            seen_terms.add(key)

    results = _unwrap_results(raw_result)
    if not results:
        return {
            "final_result": json.dumps([], ensure_ascii=False),
            "has_result": False,
            "diagnostics": json.dumps({
                "reason": "empty_bks_results",
                "input_keys": sorted(list(args.keys())),
                "raw_result_type": type(raw_result).__name__,
                "raw_result_length": len(str(raw_result)) if raw_result is not None else 0,
                "hint": "请确认 BKS 检索结果已映射到 raw_result/bks_result/result 任一字段。",
            }, ensure_ascii=False),
        }

    processed = []
    seen = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        title, content, raw_rel, raw_data = _extract_item(item)
        if not content and not title:
            continue
        key = _dedupe_key(title, content)
        if key in seen:
            continue
        seen.add(key)

        full_text = f"{title}\n{content}"
        full_lower = full_text.lower()
        exact_hits = [term for term in protected_terms if term and term.lower() in full_lower]
        keyword_hits = [term for term in terms if term and term.lower() in full_lower]
        rel_norm = max(0.0, min(raw_rel / 5.0 if raw_rel > 1.0 else raw_rel, 1.0))
        lexical = min(len(set(x.lower() for x in keyword_hits)) / max(len(set(x.lower() for x in terms)), 1), 1.0)
        exact = min(len(exact_hits) / max(len(protected_terms), 1), 1.0)
        dates = _extract_dates(full_text)
        recent_days = min([abs((current_date - d).days) for d in dates], default=9999)
        freshness = 1.0 if recent_days <= 7 else 0.5 if recent_days <= 60 else 0.1 if dates else 0.0
        has_table = 1.0 if ("|" in content and "---" in content) else 0.0
        has_number = 1.0 if re.search(r"\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*bp", content, re.I) else 0.0

        internal_boost = 0.0
        if query_type == "INTERNAL_POLICY":
            internal_boost = 0.18
        elif query_type == "MARKET_RATE" and freshness_required:
            internal_boost = -0.05

        final_score = (
            0.30 * rel_norm
            + 0.24 * exact
            + 0.18 * lexical
            + 0.10 * freshness
            + 0.08 * has_table
            + 0.07 * has_number
            + internal_boost
        )
        final_score = max(0.0, round(final_score, 4))

        protected = bool(exact_hits and (query_type != "MARKET_RATE" or has_number or has_table))
        stale_for_live_market = bool(query_type == "MARKET_RATE" and freshness_required and recent_days > 14)

        reasons = []
        if exact_hits:
            reasons.append("实体命中:" + "/".join(exact_hits[:3]))
        if raw_rel:
            reasons.append("原始相关度:" + str(raw_rel))
        if dates:
            reasons.append("材料日期:" + max(dates).isoformat())
        if stale_for_live_market:
            reasons.append("时效性偏旧")

        processed.append({
            "source": "BKS",
            "title": title,
            "relevance": raw_rel,
            "final_score": final_score,
            "protected": protected,
            "stale_for_live_market": stale_for_live_market,
            "low_confidence": final_score < 0.35 and not protected,
            "match_reason": "；".join(reasons) if reasons else "弱匹配",
            "content": _compress_content(content, terms, max_chars),
            "raw_data": raw_data,
        })

    if not processed:
        return {"final_result": json.dumps([], ensure_ascii=False), "has_result": False, "diagnostics": "no_valid_bks_items"}

    selected_map = {}
    for item in sorted(processed, key=lambda x: (x["protected"], x["final_score"], x["relevance"]), reverse=True):
        if item["protected"] or item["final_score"] >= threshold:
            selected_map[_dedupe_key(item["title"], item["content"])] = item
    selected = list(selected_map.values())
    if len(selected) < min_keep:
        for item in sorted(processed, key=lambda x: (x["final_score"], x["relevance"]), reverse=True):
            selected_map[_dedupe_key(item["title"], item["content"])] = item
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
