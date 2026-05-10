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
        text = re.sub(r'\s+', ' ', text).strip()
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
