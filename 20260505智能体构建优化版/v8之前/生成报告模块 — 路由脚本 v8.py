def main(args: dict) -> dict:
    """
    生成报告模块 - 意图守卫路由脚本 v8.0
    输入:
      guard_output: 意图守卫 LLM 原始输出
      query: 用户原始问题
    输出:
      is_redirect: bool
      redirect_message: str
    设计原则:
      LLM 只做第一判断；脚本再做关键词安全网。凡是报告/分析/经营数据相关，默认放行。
    """
    import json

    guard_output = str(args.get("guard_output", "") or "").strip()
    user_query = str(args.get("query", "") or "")

    action = "proceed"
    llm_message = ""
    try:
        si = guard_output.find("{")
        ei = guard_output.rfind("}")
        if si != -1 and ei != -1:
            parsed = json.loads(guard_output[si:ei + 1])
            action = parsed.get("action", "proceed")
            llm_message = parsed.get("message", "")
    except Exception:
        action = "proceed"

    report_signals = [
        "报告", "分析", "总结", "诊断", "复盘", "汇报", "生成", "输出", "制作", "整理",
        "经营", "业绩", "资产", "负债", "存款", "贷款", "收入", "利润", "费用", "中收",
        "同比", "环比", "较上年末", "趋势", "异动", "贡献", "占比", "结构", "预警",
        "客户经理", "管户", "OIC", "oic",
    ]
    external_signals = [
        "hibor", "libor", "sofr", "shibor", "汇率", "gdp", "cpi", "pmi",
        "建行", "中银香港", "汇丰", "恒生银行", "渣打", "花旗", "同业", "宏观",
    ]

    q_lower = user_query.lower()
    has_report_signal = any(kw.lower() in q_lower for kw in report_signals)
    has_external_signal = any(kw.lower() in q_lower for kw in external_signals)
    if action != "proceed" and has_report_signal and not has_external_signal:
        action = "proceed"
    if action not in ("proceed", "redirect_knowledge"):
        action = "proceed"

    if action == "proceed":
        return {"is_redirect": False, "redirect_message": ""}

    if not llm_message or len(llm_message.strip()) < 10:
        llm_message = (
            "您的问题更适合在「知识问答」模块中查看说明或外部信息。\n\n"
            "在「生成报告」模块中，您可以这样提问：\n"
            "- 生成上月经营分析报告\n"
            "- 输出某客户经理季度业绩诊断\n"
            "- 整理近三个月资产负债趋势分析"
        )

    return {"is_redirect": True, "redirect_message": llm_message}
