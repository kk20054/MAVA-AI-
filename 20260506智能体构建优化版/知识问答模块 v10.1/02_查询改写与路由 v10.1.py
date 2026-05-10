def main(args: dict) -> dict:
    """
    知识问答链路 v10 - Step 2
    职责：解析 Step 1 分类 JSON，叠加规则兜底，输出检索参数。
    """
    import datetime
    import json
    import re
    from datetime import timedelta

    raw_query_input = str(args.get("query", "")).strip()
    classify_result = str(args.get("classify_result", "")).strip()
    current_time_str = str(args.get("currentTime", "")).strip()

    VALID_INTENTS = {"INTRO", "GUIDE_DATA", "GUIDE_REPORT", "KNOWLEDGE"}
    VALID_QUERY_TYPES = {
        "INTRO", "GUIDE_DATA", "GUIDE_REPORT", "INTERNAL_POLICY",
        "FINANCE_DEFINITION", "MARKET_RATE", "MACRO_NEWS",
        "ICBC_PUBLIC", "GENERAL_KNOWLEDGE",
    }

    def parse_jsonish(value):
        if isinstance(value, dict):
            return value
        if not value:
            return None
        text = str(value).strip()
        md = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        if md:
            text = md.group(1)
        obj = re.search(r"\{.*\}", text, re.S)
        if obj:
            text = obj.group(0)
        try:
            return json.loads(text)
        except Exception:
            return None

    parsed = None
    for candidate in (classify_result, raw_query_input):
        parsed = parse_jsonish(candidate)
        if parsed and isinstance(parsed, dict) and parsed.get("intent"):
            break
        parsed = None

    user_query = raw_query_input
    llm_intent = ""
    query_type = ""
    answer_goal = ""
    rewritten_query = ""
    search_keywords = []
    protected_terms = []
    freshness_required = False
    time_profile = {}
    entity_profile = {}
    classification_confidence = 0.0
    rewrite_reason = ""
    ambiguity_flags = []
    kb_query = ""
    web_query = ""

    if parsed:
        llm_intent = str(parsed.get("intent", "")).strip().upper()
        query_type = str(parsed.get("query_type", "")).strip().upper()
        answer_goal = str(parsed.get("answer_goal", "")).strip().lower()
        user_query = str(parsed.get("raw_query") or raw_query_input).strip()
        rewritten_query = str(parsed.get("rewritten_query", "")).strip()
        kb_query = str(parsed.get("kb_query", "")).strip()
        web_query = str(parsed.get("web_query", "")).strip()
        search_keywords = parsed.get("search_keywords", []) or []
        protected_terms = parsed.get("protected_terms", []) or []
        freshness_required = bool(parsed.get("freshness_required", False))
        time_profile = parsed.get("time_profile", {}) if isinstance(parsed.get("time_profile", {}), dict) else {}
        entity_profile = parsed.get("entity_profile", {}) if isinstance(parsed.get("entity_profile", {}), dict) else {}
        classification_confidence = parsed.get("classification_confidence", 0.0)
        rewrite_reason = str(parsed.get("rewrite_reason", "")).strip()
        ambiguity_flags = parsed.get("ambiguity_flags", []) or []

    if not user_query:
        user_query = raw_query_input

    if isinstance(search_keywords, str):
        search_keywords = [x.strip() for x in re.split(r"[,，|/、\s]+", search_keywords) if x.strip()]
    if isinstance(protected_terms, str):
        protected_terms = [x.strip() for x in re.split(r"[,，|/、]+", protected_terms) if x.strip()]
    if isinstance(ambiguity_flags, str):
        ambiguity_flags = [x.strip() for x in re.split(r"[,，|/、\s]+", ambiguity_flags) if x.strip()]

    q = user_query.strip()
    q_lower = q.lower()

    INTRO_PATTERNS = [
        r"^[\s]*(你好|您好|hi|hello|hey|哈喽|嗨|早上好|下午好|晚上好|早安|午安|晚安)[\s!！。.？?，,]*$",
        r"(你是谁|你是什么|你叫什么|请问你是)",
        r"^.{0,6}(你能做什么|有什么功能|能帮我做什么|怎么用|如何使用|使用指引|功能介绍|使用说明)",
        r"^[\s!！?？。.，,]{0,3}$",
    ]

    EXTERNAL_MARKET = (
        r"(hibor|libor|sofr|lpr|shibor|prime rate|同业拆息|银行同业拆借|基准利率|"
        r"汇率|美元兑|港币兑|人民币兑|即期汇率|远期汇率|"
        r"国债|收益率曲线|cpi|gdp|pmi|失业率|通胀|"
        r"恒生指数|上证|道琼斯|标普|纳斯达克|股票|"
        r"香港银行业|行业整体|全行业|市场整体|"
        r"金管局|hkma|央行|fed|美联储)"
    )
    ICBC_PUBLIC = r"(工商银行|中国工商银行|总行|母行|境内行)"

    GUIDE_DATA_PATTERNS = [
        r"(帮我|请|麻烦|我想|我要|能否|可以).{0,10}(查|看|查询|查看|检索|拉|调|导出).{0,25}(贷款余额|存款余额|日均余额|利息净收入|中间业务收入|手续费|营业收入|营业利润|税前利润|净利润|汇兑损益|不良贷款|不良率|拨备覆盖率|逾期贷款|关注类|RAROC|EVA|经济利润|利润分成|RWA|风险加权|资本占用|成本收入比|FTP成本|管户资产|管户负债)",
        r"(我的|我管户|我名下|本人).{0,18}(余额|收入|利润|损益|不良|拨备|贷款|存款|资产|负债|数据|指标|情况|表现)",
        r"EE\s*(?:编号)?\s*\d{6,}.{0,25}(数据|余额|收入|情况|贷款|存款|资产|负债|利润|损益|不良|拨备)",
        r"(查|看).{0,8}(上月|上个月|本月|去年|今年|上季|同比|环比|较上年末|上半年|下半年).{0,18}(余额|收入|损益|贷款|存款|资产|负债|数据|利润|不良|拨备)",
    ]
    GUIDE_REPORT_PATTERNS = [
        r"(帮我|请|麻烦|我想|我要|能否|可以).{0,10}(生成|出|写|制作|导出|做).{0,12}(报告|报表|分析报告|经营报告|诊断报告)",
        r"(经营|诊断|业绩|绩效|综合).{0,6}(报告|报表|分析)",
        r"(生成|出|做|写).{0,6}(一份|个).{0,6}(报告|分析)",
    ]

    def has(patterns):
        return any(re.search(p, q_lower, re.I) for p in patterns)

    rule_intent = ""
    if len(q.replace(" ", "")) <= 2 or has(INTRO_PATTERNS):
        rule_intent = "INTRO"
    elif has(GUIDE_REPORT_PATTERNS):
        rule_intent = "GUIDE_REPORT"
    elif has(GUIDE_DATA_PATTERNS):
        if re.search(EXTERNAL_MARKET, q_lower, re.I) or re.search(ICBC_PUBLIC, q_lower, re.I):
            rule_intent = "KNOWLEDGE"
        else:
            rule_intent = "GUIDE_DATA"

    if rule_intent in {"INTRO", "GUIDE_DATA", "GUIDE_REPORT"}:
        final_intent = rule_intent
    elif llm_intent in VALID_INTENTS:
        final_intent = llm_intent
    elif rule_intent:
        final_intent = rule_intent
    else:
        final_intent = "KNOWLEDGE"

    if final_intent != "KNOWLEDGE":
        query_type = final_intent
    elif query_type not in VALID_QUERY_TYPES or query_type in {"INTRO", "GUIDE_DATA", "GUIDE_REPORT"}:
        if re.search(EXTERNAL_MARKET, q_lower, re.I):
            query_type = "MARKET_RATE"
        elif re.search(ICBC_PUBLIC, q_lower, re.I):
            query_type = "ICBC_PUBLIC"
        elif re.search(r"(制度|流程|报销|审批|标准|规定|办法|操作|系统|提交|申请|口径)", q):
            query_type = "INTERNAL_POLICY"
        elif re.search(r"(是什么|什么是|什么意思|定义|怎么计算|如何计提|口径|公式|含义)", q):
            query_type = "FINANCE_DEFINITION"
        elif re.search(r"(政策|新闻|监管|金管局|hkma|经济|行业|宏观|最新)", q_lower, re.I):
            query_type = "MACRO_NEWS"
        else:
            query_type = "GENERAL_KNOWLEDGE"

    try:
        current_date = datetime.datetime.strptime(current_time_str[:10], "%Y-%m-%d").date() if current_time_str else datetime.date.today()
    except ValueError:
        current_date = datetime.date.today()
    current_date_str = current_date.strftime("%Y-%m-%d")

    def get_month_end(year, month):
        nxt = datetime.date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        return nxt - timedelta(days=1)

    month_ends = []
    ty, tm = current_date.year, current_date.month
    for _ in range(3):
        tm -= 1
        if tm <= 0:
            tm += 12
            ty -= 1
        month_ends.append(get_month_end(ty, tm))

    date_context = {
        "今天": current_date_str,
        "昨天": (current_date - timedelta(days=1)).strftime("%Y-%m-%d"),
        "上年末": datetime.date(current_date.year - 1, 12, 31).strftime("%Y-%m-%d"),
        "上月末": month_ends[0].strftime("%Y-%m-%d"),
        "上上月末": month_ends[1].strftime("%Y-%m-%d"),
        "上上上月末": month_ends[2].strftime("%Y-%m-%d"),
    }

    def add_flag(flag):
        if flag and flag not in ambiguity_flags:
            ambiguity_flags.append(flag)

    def month_range(year, month):
        return datetime.date(year, month, 1), get_month_end(year, month)

    def previous_week_range(base_date):
        this_monday = base_date - timedelta(days=base_date.weekday())
        start = this_monday - timedelta(days=7)
        end = start + timedelta(days=6)
        return start, end

    def detect_time_profile(query_text):
        text = query_text.strip()
        profile = {
            "time_expression": "",
            "resolved_date_range": {},
            "as_of_date": "",
            "freshness_required": False,
            "time_basis": "none",
        }

        explicit = re.search(r"(20\d{2})[-/年](\d{1,2})(?:[-/月](\d{1,2})日?)?", text)
        if explicit:
            y, m = int(explicit.group(1)), int(explicit.group(2))
            if explicit.group(3):
                d = int(explicit.group(3))
                try:
                    dt = datetime.date(y, m, d)
                    profile.update({
                        "time_expression": explicit.group(0),
                        "resolved_date_range": {"start": dt.isoformat(), "end": dt.isoformat()},
                        "as_of_date": dt.isoformat(),
                        "time_basis": "explicit_date",
                    })
                    return profile
                except ValueError:
                    add_flag("invalid_explicit_date")
            else:
                try:
                    start, end = month_range(y, m)
                    profile.update({
                        "time_expression": explicit.group(0),
                        "resolved_date_range": {"start": start.isoformat(), "end": end.isoformat()},
                        "as_of_date": end.isoformat(),
                        "time_basis": "period",
                    })
                    return profile
                except ValueError:
                    add_flag("invalid_explicit_month")

        rules = [
            (r"(今天|今日|当前|现在)", "latest", current_date, current_date, True),
            (r"(昨天|昨日)", "explicit_date", current_date - timedelta(days=1), current_date - timedelta(days=1), False),
            (r"(最近|最新|近况|目前)", "latest", current_date - timedelta(days=7), current_date, True),
        ]
        for pattern, basis, start, end, fresh in rules:
            m = re.search(pattern, text)
            if m:
                profile.update({
                    "time_expression": m.group(1),
                    "resolved_date_range": {"start": start.isoformat(), "end": end.isoformat()},
                    "as_of_date": end.isoformat(),
                    "freshness_required": fresh,
                    "time_basis": basis,
                })
                return profile

        if re.search(r"上周|上一周", text):
            start, end = previous_week_range(current_date)
            profile.update({
                "time_expression": "上周",
                "resolved_date_range": {"start": start.isoformat(), "end": end.isoformat()},
                "as_of_date": end.isoformat(),
                "time_basis": "period",
            })
            return profile

        if re.search(r"上月|上个月", text):
            end = month_ends[0]
            start = datetime.date(end.year, end.month, 1)
            profile.update({
                "time_expression": "上月",
                "resolved_date_range": {"start": start.isoformat(), "end": end.isoformat()},
                "as_of_date": end.isoformat(),
                "time_basis": "period",
            })
            return profile

        if re.search(r"今年|本年", text):
            start = datetime.date(current_date.year, 1, 1)
            profile.update({
                "time_expression": "今年",
                "resolved_date_range": {"start": start.isoformat(), "end": current_date.isoformat()},
                "as_of_date": current_date.isoformat(),
                "time_basis": "period",
            })
            return profile

        if re.search(r"去年|上年", text):
            start = datetime.date(current_date.year - 1, 1, 1)
            end = datetime.date(current_date.year - 1, 12, 31)
            profile.update({
                "time_expression": "去年",
                "resolved_date_range": {"start": start.isoformat(), "end": end.isoformat()},
                "as_of_date": end.isoformat(),
                "time_basis": "historical",
            })
            return profile

        return profile

    def infer_answer_goal(query_text, intent_value, type_value):
        text = query_text.lower()
        if intent_value == "INTRO":
            return "greeting"
        if intent_value == "GUIDE_DATA":
            return "guide_data"
        if intent_value == "GUIDE_REPORT":
            return "guide_report"
        if type_value == "INTERNAL_POLICY":
            return "procedure" if re.search(r"(怎么|如何|流程|步骤|操作|提交|申请|办理)", query_text) else "policy_lookup"
        if type_value == "FINANCE_DEFINITION":
            return "definition"
        if type_value == "MARKET_RATE" and re.search(r"(最新|今天|今日|最近|当前|现在|是多少|报价|利率表|多少)", query_text):
            return "latest_value"
        if re.search(r"(是什么|什么是|什么意思|定义|含义|口径|公式|怎么计算|如何计提)", query_text):
            return "definition"
        if re.search(r"(怎么|如何|流程|步骤|操作|提交|申请|办理)", query_text):
            return "procedure"
        if re.search(r"(制度|标准|规定|办法|要求|审批|报销)", query_text):
            return "policy_lookup"
        if re.search(r"(比较|对比|变化|趋势|走势|涨跌|较|同比|环比)", query_text):
            return "comparison"
        return "summary"

    def detect_entity_profile(query_text, type_value):
        text = query_text.lower()
        profile = {
            "primary_entity": "",
            "entity_type": "general",
            "currency": "",
            "tenors": [],
            "default_assumption": "",
        }
        tenor_map = [
            (r"(隔夜|overnight|o/n|\bon\b)", "O/N"),
            (r"(1\s*周|一周|1w)", "1W"),
            (r"(2\s*周|两周|2w)", "2W"),
            (r"(1\s*个月|一个月|1m)", "1M"),
            (r"(3\s*个月|三个月|3m)", "3M"),
            (r"(6\s*个月|六个月|6m)", "6M"),
            (r"(12\s*个月|一年|1y)", "12M"),
        ]
        tenors = []
        for pattern, value in tenor_map:
            if re.search(pattern, text, re.I) and value not in tenors:
                tenors.append(value)

        if re.search(r"hibor|同业拆息|银行同业拆", text, re.I):
            profile.update({
                "primary_entity": "HIBOR",
                "entity_type": "market_rate",
                "currency": "HKD" if not re.search(r"cnh|人民币|离岸人民币", text, re.I) else "CNH",
                "tenors": tenors,
            })
            assumptions = []
            if not re.search(r"hkd|港元|港币|cnh|人民币|离岸人民币", text, re.I):
                assumptions.append("用户未说明币种，默认按 HKD HIBOR 理解")
                add_flag("default_hkd_hibor")
            if not tenors:
                assumptions.append("用户未说明期限，优先列示检索证据中的常用期限")
                add_flag("missing_tenor")
            profile["default_assumption"] = "；".join(assumptions)
            return profile
        if re.search(r"lpr|贷款市场报价", text, re.I):
            profile.update({
                "primary_entity": "LPR",
                "entity_type": "market_rate",
                "currency": "CNY",
                "tenors": tenors,
                "default_assumption": "用户未说明期限时，优先列示 1年期和5年期以上 LPR。",
            })
            if not tenors:
                add_flag("missing_tenor")
            return profile
        if type_value == "INTERNAL_POLICY":
            clean = re.sub(r"(工银亚洲|是什么|什么是|怎么|如何|的|？|\?)", "", query_text).strip()
            terms = re.findall(r"[\u4e00-\u9fff]{2,}", clean)
            profile.update({"primary_entity": terms[0] if terms else clean, "entity_type": "policy"})
            return profile
        if type_value == "FINANCE_DEFINITION":
            clean = re.sub(r"(是什么|什么是|什么意思|定义|含义|？|\?)", "", query_text).strip()
            terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}", clean)
            profile.update({"primary_entity": terms[0] if terms else "", "entity_type": "finance_metric"})
            return profile
        if type_value == "ICBC_PUBLIC":
            profile.update({"primary_entity": "中国工商银行", "entity_type": "institution"})
            return profile
        return profile

    def merge_profile(base, fallback):
        merged = dict(fallback)
        if isinstance(base, dict):
            for key, value in base.items():
                if value not in ("", None, [], {}):
                    merged[key] = value
        return merged

    inferred_time_profile = detect_time_profile(q)
    time_profile = merge_profile(time_profile, inferred_time_profile)
    if time_profile.get("as_of_date") in ("当前日期", "current_date", "today"):
        time_profile["as_of_date"] = current_date_str
    if time_profile.get("freshness_required"):
        freshness_required = True

    if not answer_goal:
        answer_goal = infer_answer_goal(q, final_intent, query_type)

    inferred_entity_profile = detect_entity_profile(q, query_type)
    entity_profile = merge_profile(entity_profile, inferred_entity_profile)

    if not rewrite_reason:
        if final_intent == "GUIDE_DATA":
            rewrite_reason = "用户请求内部经营数据具体数值，应引导至查询数据模块。"
        elif final_intent == "GUIDE_REPORT":
            rewrite_reason = "用户请求生成经营分析报告，应引导至报告生成模块。"
        elif final_intent == "INTRO":
            rewrite_reason = "用户为问候、功能咨询或使用说明，无需检索。"
        elif query_type == "MARKET_RATE":
            rewrite_reason = "用户问题属于外部市场数据，改写时强化核心英文缩写、中文全称、时效和常用期限。"
        elif query_type == "INTERNAL_POLICY":
            rewrite_reason = "用户问题属于行内制度或流程，改写时保留原词并补充制度、流程、规定等检索词。"
        elif query_type == "FINANCE_DEFINITION":
            rewrite_reason = "用户问题属于财务概念或口径解释，改写时补充定义、口径、计算方法等检索词。"
        else:
            rewrite_reason = "按知识问答问题保留用户核心表达并补充必要检索关键词。"

    if not classification_confidence:
        if rule_intent:
            classification_confidence = 0.92
        elif llm_intent in VALID_INTENTS:
            classification_confidence = 0.82
        elif query_type != "GENERAL_KNOWLEDGE":
            classification_confidence = 0.88
        else:
            classification_confidence = 0.72
    try:
        classification_confidence = float(classification_confidence)
    except (TypeError, ValueError):
        classification_confidence = 0.72
    if ambiguity_flags:
        classification_confidence = max(0.55, classification_confidence - min(len(ambiguity_flags) * 0.02, 0.08))
    classification_confidence = round(min(max(classification_confidence, 0.0), 1.0), 2)

    if freshness_required and final_intent == "KNOWLEDGE":
        add_flag("freshness_requires_web")

    if final_intent != "KNOWLEDGE":
        return {
            "intent": final_intent,
            "query_type": query_type,
            "user_query": user_query,
            "answer_goal": answer_goal,
            "rewritten_query": "",
            "search_keywords": json.dumps([], ensure_ascii=False),
            "protected_terms": json.dumps([], ensure_ascii=False),
            "freshness_required": False,
            "time_profile": json.dumps(time_profile, ensure_ascii=False),
            "entity_profile": json.dumps(entity_profile, ensure_ascii=False),
            "classification_confidence": classification_confidence,
            "rewrite_reason": rewrite_reason,
            "ambiguity_flags": json.dumps(ambiguity_flags, ensure_ascii=False),
            "should_search": False,
            "short_circuit_type": final_intent,
            "is_intro": True,
            "kb_query": "",
            "web_query": "",
            "status": "SHORT_CIRCUIT",
            "date_context": json.dumps(date_context, ensure_ascii=False),
        }

    time_words = r"(最新|今天|今日|最近|当前|现在|是多少|报价|利率表)"
    if re.search(time_words, q):
        freshness_required = True
        time_profile["freshness_required"] = True
        if not time_profile.get("as_of_date"):
            time_profile["as_of_date"] = current_date_str
        if time_profile.get("time_basis") == "none":
            time_profile["time_basis"] = "latest"
        add_flag("freshness_requires_web")

    def add_unique(items, more):
        seen = {str(x).lower() for x in items}
        for x in more:
            if x and str(x).lower() not in seen:
                items.append(x)
                seen.add(str(x).lower())
        return items

    if query_type == "MARKET_RATE":
        if re.search(r"hibor|同业拆息|银行同业拆", q_lower, re.I):
            rewritten_query = rewritten_query or "HKD HIBOR 香港银行同业拆息 最新 今日 报价 隔夜 1个月 3个月"
            search_keywords = add_unique(search_keywords, ["HIBOR", "HKD HIBOR", "香港银行同业拆息", "隔夜", "1个月", "3个月", "最新"])
            protected_terms = add_unique(protected_terms, ["HIBOR", "HKD HIBOR", "香港银行同业拆息", "Hong Kong Interbank Offered Rate"])
            kb_query = kb_query or "HIBOR 香港银行同业拆息 口径 背景"
            web_query = web_query or "HKD HIBOR 香港银行同业拆息 最新 今日 报价"
        elif re.search(r"lpr|贷款市场报价", q_lower, re.I):
            rewritten_query = rewritten_query or "LPR 贷款市场报价利率 最新 报价"
            search_keywords = add_unique(search_keywords, ["LPR", "贷款市场报价利率", "最新"])
            protected_terms = add_unique(protected_terms, ["LPR", "贷款市场报价利率"])
        else:
            rewritten_query = rewritten_query or f"{q} 最新 今日 报价"
            search_keywords = add_unique(search_keywords, re.findall(r"[A-Za-z]{2,}|[\u4e00-\u9fff]{2,}", q))
            protected_terms = add_unique(protected_terms, search_keywords[:3])
    elif query_type == "INTERNAL_POLICY":
        policy_entity = entity_profile.get("primary_entity") if isinstance(entity_profile, dict) else ""
        rewritten_query = rewritten_query or f"工银亚洲 {policy_entity or q} 制度 流程 规定 操作"
        search_keywords = add_unique(search_keywords, re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}", q))
        protected_terms = add_unique(protected_terms, search_keywords[:3])
    elif query_type == "FINANCE_DEFINITION":
        finance_entity = entity_profile.get("primary_entity") if isinstance(entity_profile, dict) else ""
        rewritten_query = rewritten_query or f"{finance_entity or q} 财务口径 定义 计算方法"
        search_keywords = add_unique(search_keywords, re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}", q))
        protected_terms = add_unique(protected_terms, search_keywords[:2])
    elif query_type == "ICBC_PUBLIC":
        rewritten_query = rewritten_query or f"中国工商银行 {q} 年报 公告"
        search_keywords = add_unique(search_keywords, ["中国工商银行", "工商银行", "年报", "公告"])
        protected_terms = add_unique(protected_terms, ["中国工商银行", "工商银行"])
    else:
        rewritten_query = rewritten_query or q
        search_keywords = add_unique(search_keywords, re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}", q))
        protected_terms = add_unique(protected_terms, search_keywords[:2])

    kb_query = kb_query or rewritten_query
    web_query = web_query or rewritten_query
    if freshness_required and "参考日期" not in web_query:
        web_query = f"{web_query}（参考日期：{current_date_str}）"
    if ambiguity_flags:
        classification_confidence = round(
            max(0.55, min(classification_confidence, 0.96) - min(len(ambiguity_flags) * 0.005, 0.02)),
            2,
        )

    return {
        "intent": final_intent,
        "query_type": query_type,
        "user_query": user_query,
        "answer_goal": answer_goal,
        "rewritten_query": rewritten_query,
        "search_keywords": json.dumps(search_keywords, ensure_ascii=False),
        "protected_terms": json.dumps(protected_terms, ensure_ascii=False),
        "freshness_required": freshness_required,
        "time_profile": json.dumps(time_profile, ensure_ascii=False),
        "entity_profile": json.dumps(entity_profile, ensure_ascii=False),
        "classification_confidence": classification_confidence,
        "rewrite_reason": rewrite_reason,
        "ambiguity_flags": json.dumps(ambiguity_flags, ensure_ascii=False),
        "should_search": True,
        "short_circuit_type": "NONE",
        "is_intro": False,
        "kb_query": kb_query,
        "web_query": web_query,
        "status": "PROCEED_TO_SEARCH",
        "date_context": json.dumps(date_context, ensure_ascii=False),
    }
