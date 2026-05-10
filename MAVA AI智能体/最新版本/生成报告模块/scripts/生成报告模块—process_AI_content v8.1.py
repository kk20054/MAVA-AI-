def main(args: dict) -> dict:
    import ast
    import html
    import json
    import re

    analysis_str = str(args.get('analysis_raw', '') or '')
    if not analysis_str.strip():
        return {"financial_highlights": "", "key_facts": "", "report_sections_json": "{}"}

    def extract_dict_text(text):
        block = re.search(r'```(?:python|json)?\s*([\s\S]*?)```', text)
        if block:
            text = block.group(1)
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start:end + 1]

    def parse_content(dict_text):
        cleaned = re.sub(r',\s*([\]}])', r'\1', dict_text)
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        try:
            return ast.literal_eval(cleaned)
        except Exception:
            return None

    def normalize_key(key):
        key = str(key or '').strip()
        key = re.sub(r'^[一二三四五六七八九十\d]+[、\.\s]*', '', key)
        return key

    def normalize_item(item):
        text = str(item or '').strip()
        if not text:
            return ''
        text = re.sub(r'^\s*[•●]\s*', '-', text)
        if not text.startswith('-'):
            text = '-' + text
        text = clean_parenthetical_evidence(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def clean_parenthetical_evidence(text):
        # 防止模型输出“建议动作（依据：xxx）”这类不自然格式。
        evidence_patterns = [
            r'[（(]\s*(?:数据)?依据\s*[:：]\s*([^）)]{1,180})[）)]',
            r'[（(]\s*(?:理由|分析依据|支撑依据)\s*[:：]\s*([^）)]{1,180})[）)]',
        ]
        evidence = []
        for pat in evidence_patterns:
            for m in re.finditer(pat, text):
                val = m.group(1).strip()
                if val:
                    evidence.append(val)
            text = re.sub(pat, '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        if evidence:
            base = text.rstrip('。；;')
            ev = '；'.join(evidence[:2])
            if any(k in base for k in ['建议', '可', '需', '应']):
                text = f'{base}。该项安排主要基于{ev}，后续需结合客户、产品和期限结构继续跟踪。'
            else:
                text = f'{base}，主要基于{ev}。后续需结合客户、产品和期限结构继续跟踪。'
        return text

    dict_text = extract_dict_text(analysis_str)
    content = parse_content(dict_text) if dict_text else None
    if not isinstance(content, dict):
        return {"financial_highlights": "", "key_facts": "", "report_sections_json": "{}"}

    sections = {}
    financial_items = []
    suggestion_items = []

    for key, value in content.items():
        clean_key = normalize_key(key)
        raw_items = value if isinstance(value, list) else [value]
        items = [normalize_item(x) for x in raw_items]
        items = [x for x in items if x]
        if not items:
            continue
        sections[clean_key] = items
        if any(kw in clean_key for kw in ['经营情况', '主要经营', '经营分析', '亮点']):
            financial_items.extend(items)
        elif any(kw in clean_key for kw in ['建议', '关注', '下一步']):
            suggestion_items.extend(items)

    def to_html_lines(items):
        safe_items = [html.escape(x, quote=False) for x in items]
        return "<br>".join(safe_items)

    return {
        "financial_highlights": to_html_lines(financial_items),
        "key_facts": to_html_lines(suggestion_items),
        "report_sections_json": json.dumps(sections, ensure_ascii=False)
    }
