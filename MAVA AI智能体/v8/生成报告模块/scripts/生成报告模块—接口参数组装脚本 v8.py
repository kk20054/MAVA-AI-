def main(args: dict) -> dict:
    """
    生成报告模块 - 接口参数组装脚本 v8
    输入：param_output（参数抽取 LLM 输出）、query（用户原文）、可选 batch_date/ee
    输出：requestType=1 的接口参数，以及缺参提示。
    """
    import datetime
    import json
    import re

    query = str(args.get("query", "") or "")
    param_output = str(args.get("param_output", "") or "")

    def parse_json(text):
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end + 1])
        except Exception:
            return {}
        return {}

    def normalize_date(value):
        value = str(value or "").strip()
        if not value:
            return ""
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        m = re.search(r"(20\d{2})[年\-/\.]?(\d{1,2})[月\-/\.]?(\d{1,2})", value)
        if m:
            y, mo, d = map(int, m.groups())
            try:
                return datetime.date(y, mo, d).strftime("%Y-%m-%d")
            except Exception:
                return ""
        return ""

    parsed = parse_json(param_output)
    batch_date = normalize_date(args.get("batch_date") or parsed.get("batch_date") or parsed.get("batchDate"))
    ee = str(args.get("ee") or parsed.get("ee") or parsed.get("OIC") or parsed.get("oic") or "").strip()

    if not batch_date:
        m = re.search(r"(20\d{2})[-/]?(\d{2})[-/]?(\d{2})", query)
        if m:
            batch_date = normalize_date("".join(m.groups()))

    if not ee:
        m = re.search(r"(?:客户经理|OIC|oic|ee|员工号|编号)\s*[:：为是]?\s*([A-Za-z0-9_-]{4,})", query)
        if m:
            ee = m.group(1).strip()

    missing = []
    if not batch_date:
        missing.append("batch_date")
    if not ee:
        missing.append("ee")

    message = ""
    if missing:
        labels = {"batch_date": "报告数据日期", "ee": "客户经理/OIC编号"}
        need = "、".join(labels[x] for x in missing)
        message = f"请补充{need}后再生成报告。"

    return {
        "requestType": 1,
        "batch_date": batch_date,
        "ee": ee,
        "missing_fields": missing,
        "is_ready": len(missing) == 0,
        "message": message,
        "api_params": {
            "requestType": 1,
            "batch_date": batch_date,
            "ee": ee
        }
    }
