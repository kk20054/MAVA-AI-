import ast
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


def _unwrap(raw):
    parsed = _loads_maybe(raw)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("final_result", "result", "results", "items"):
            inner = _loads_maybe(parsed.get(key))
            if isinstance(inner, list):
                return inner
    return []


def _score(item):
    try:
        return float(item.get("final_score", item.get("relevance", 0.0)))
    except Exception:
        return 0.0


def _dedupe_key(item):
    raw = str(item.get("url") or item.get("title") or item.get("content", "")[:240]).strip().lower()
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()


def _clip(text, max_chars):
    text = re.sub(r"\n{3,}", "\n\n", str(text or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[已按上下文预算截断]"


def _budget_items(items, max_total_chars, per_item_chars):
    selected = []
    used = 0
    for item in items:
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        item = dict(item)
        remaining = max_total_chars - used
        if remaining <= 0:
            break
        clipped = _clip(content, min(per_item_chars, remaining))
        item["content"] = clipped
        used += len(clipped)
        selected.append(item)
    return selected


def main(args: dict) -> dict:
    """
    知识问答链路 v10 - Step 3C
    将 BKS 与联网结果做去重、排序和上下文预算控制。
    """
    query_type = str(args.get("query_type", "")).upper()
    kb_items = _unwrap(args.get("kb_results", args.get("bks_results", "")))
    web_items = _unwrap(args.get("web_results", ""))
    max_chars = int(float(args.get("max_total_chars", 10000)))
    per_item_chars = int(float(args.get("max_chars_per_item", 1800)))

    kb_items = [dict(x, source=x.get("source", "BKS")) for x in kb_items if isinstance(x, dict)]
    web_items = [dict(x, source=x.get("source", "WEB")) for x in web_items if isinstance(x, dict)]

    # 不同问题类型使用不同配比：行内制度重知识库，市场利率重联网。
    if query_type == "INTERNAL_POLICY":
        kb_budget = int(max_chars * 0.72)
        web_budget = max_chars - kb_budget
        kb_limit, web_limit = 5, 2
    elif query_type == "MARKET_RATE":
        web_budget = int(max_chars * 0.72)
        kb_budget = max_chars - web_budget
        kb_limit, web_limit = 2, 5
    else:
        kb_budget = max_chars // 2
        web_budget = max_chars - kb_budget
        kb_limit, web_limit = 4, 4

    kb_sorted = sorted(kb_items, key=lambda x: (bool(x.get("protected")), _score(x)), reverse=True)[:kb_limit]
    web_sorted = sorted(web_items, key=lambda x: (bool(x.get("protected")), _score(x)), reverse=True)[:web_limit]

    seen = set()
    def unique(items):
        out = []
        for item in items:
            key = _dedupe_key(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    if query_type == "MARKET_RATE":
        web_final = unique(_budget_items(web_sorted, web_budget, per_item_chars))
        kb_final = unique(_budget_items(kb_sorted, kb_budget, per_item_chars))
    else:
        kb_final = unique(_budget_items(kb_sorted, kb_budget, per_item_chars))
        web_final = unique(_budget_items(web_sorted, web_budget, per_item_chars))

    blocks = []
    for idx, item in enumerate(kb_final, 1):
        marker = f"[知识库#{idx}]"
        title = item.get("title", "")
        reason = item.get("match_reason", "")
        blocks.append(f"{marker} {title}\n置信/匹配：{reason}\n{item.get('content','')}")
    for idx, item in enumerate(web_final, 1):
        marker = f"[联网#{idx}]"
        title = item.get("title", "")
        url = item.get("url", "")
        reason = item.get("match_reason", "")
        blocks.append(f"{marker} {title}\nURL：{url}\n置信/匹配：{reason}\n{item.get('content','')}")

    return {
        "kb_final_results": json.dumps(kb_final, ensure_ascii=False),
        "web_final_results": json.dumps(web_final, ensure_ascii=False),
        "final_context": "\n\n".join(blocks),
        "has_result": bool(kb_final or web_final),
        "context_stats": json.dumps({
            "kb_count": len(kb_final),
            "web_count": len(web_final),
            "max_total_chars": max_chars,
            "actual_chars": sum(len(x) for x in blocks),
        }, ensure_ascii=False),
    }
