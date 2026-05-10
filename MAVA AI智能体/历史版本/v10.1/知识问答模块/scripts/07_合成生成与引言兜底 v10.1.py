import ast
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


def _json_text(value, default):
    parsed = _loads_maybe(value)
    if parsed is None:
        parsed = default
    try:
        return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        return json.dumps(default, ensure_ascii=False)


def _format_results(raw, label):
    items = _unwrap(raw)
    if not items:
        return f"（{label}无匹配结果）"
    blocks = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        title = item.get("title", "")
        url = item.get("url", "")
        reason = item.get("match_reason", "")
        score = item.get("final_score", item.get("relevance", ""))
        low_conf = "（低置信度）" if item.get("low_confidence") else ""
        stale = "（时效性偏旧）" if item.get("stale_for_live_market") else ""
        header = f"[{label}#{i}] {title} {low_conf}{stale}".strip()
        if score != "":
            header += f"（综合分: {score}）"
        if url:
            header += f"\nURL：{url}"
        if reason:
            header += f"\n匹配原因：{reason}"
        content = str(item.get("content", "")).strip()
        if content:
            blocks.append(f"{header}\n{content}")
    return "\n\n".join(blocks) if blocks else f"（{label}无有效内容）"


def main(args: dict) -> dict:
    """
    知识问答链路 v10 - Step 4
    根据意图和检索结果构建最终 LLM Prompt。
    """
    user_query = str(args.get("user_query", "")).strip()
    intent = str(args.get("intent", "")).strip().upper() or "KNOWLEDGE"
    query_type = str(args.get("query_type", "")).strip().upper() or "GENERAL_KNOWLEDGE"
    answer_goal = str(args.get("answer_goal", "")).strip().lower() or "summary"
    rewritten_query = str(args.get("rewritten_query", "")).strip()
    date_context = str(args.get("date_context", "")).strip()
    time_profile = _json_text(args.get("time_profile", ""), {})
    entity_profile = _json_text(args.get("entity_profile", ""), {})
    rewrite_reason = str(args.get("rewrite_reason", "")).strip()
    ambiguity_flags = _json_text(args.get("ambiguity_flags", ""), [])
    classification_confidence = args.get("classification_confidence", "")
    final_context = str(args.get("final_context", "")).strip()
    kb_results_raw = args.get("kb_final_results", args.get("kb_results", ""))
    web_results_raw = args.get("web_final_results", args.get("web_results", ""))

    is_intro = args.get("is_intro", False)
    if isinstance(is_intro, str):
        is_intro = is_intro.lower() in ("true", "1", "yes")
    if is_intro and intent not in ("GUIDE_DATA", "GUIDE_REPORT"):
        intent = "INTRO"

    if intent == "INTRO":
        intro_prompt = f"""【角色】
你是工银亚洲 MAVA 智能分析助手。

【用户输入】
{user_query}

【任务】
判断用户意图，从下方模板库中选择最匹配的模板，完整原样输出。
- 若用户在打招呼或问功能，输出模板A
- 若用户问怎么使用，输出模板B
- 若无法判断，输出模板A

【严格规则】
1. 必须 100% 原样输出选定模板的全部文字，不得增删改任何内容。
2. 不得在模板前后添加任何额外文字。
3. 禁止输出模板标签文本。

<模板A>
您好，我是工银亚洲 MAVA 智能分析助手。我可以协助您完成以下三类工作：

**一、数据查询** ← 请点击下方「查询数据」按钮

支持查询 OIC 维及部门维的资产负债、损益类指标数据，包括时点余额、日均余额、月累计及年累计等。

**二、报告生成** ← 请点击下方「生成报告」按钮

支持一键生成 OIC 维度的综合经营分析报告，涵盖规模、效益、质量等多维度分析。

**三、知识问答** ← 当前模式

支持解答财会制度、核算口径、系统操作、市场资讯等问题，基于行内知识库及联网检索提供参考。

请告诉我您的具体需求，我将为您提供支持。
</模板A>

<模板B>
感谢您的咨询。以下是 MAVA 智能分析助手的使用指引：

本助手通过对话框下方的三个按钮切换功能模式：

**「查询数据」**模式：请明确时间范围和指标类型。如需查询特定客户经理的数据，请提供其 9 位 EE 编号。默认查询本人数据。

**「生成报告」**模式：支持按月度、季度、半年度、年度生成 OIC 维度经营诊断报告。

**「知识问答」**模式（当前）：直接输入您的问题即可，系统将自动检索行内知识库和互联网信息为您解答。

请根据您的需求点击对应按钮开始使用。
</模板B>"""
        return {"final_prompt": intro_prompt, "mode": "INTRO", "direct_response": ""}

    if intent == "GUIDE_DATA":
        response = (
            "您的问题涉及具体经营数据查询。请点击对话框下方的**「查询数据」**按钮切换至数据查询模式，"
            "系统将按时间、指标和 OIC/部门维度为您检索所需数据。\n\n"
            "使用提示：请明确时间范围；如需查询特定客户经理，请注明 9 位 EE 编号；默认查询本人管户数据。"
        )
        return {"final_prompt": f"【任务】原样输出以下内容，不做任何修改：{response}", "mode": "GUIDE_DATA", "direct_response": response}

    if intent == "GUIDE_REPORT":
        response = (
            "您的问题涉及经营分析报告生成。请点击对话框下方的**「生成报告」**按钮切换至报告生成模式，"
            "系统可一键生成 OIC 维度的综合经营诊断报告。\n\n"
            "使用提示：支持月度、季度、半年度及年度维度；默认生成本人报告，如需生成其他客户经理的报告请注明 EE 编号。"
        )
        return {"final_prompt": f"【任务】原样输出以下内容，不做任何修改：{response}", "mode": "GUIDE_REPORT", "direct_response": response}

    kb_text = _format_results(kb_results_raw, "知识库")
    web_text = _format_results(web_results_raw, "联网")
    if final_context:
        evidence_text = final_context
    else:
        evidence_text = f"【内部知识库检索结果】\n{kb_text}\n\n【联网检索结果】\n{web_text}"

    has_result = "无匹配结果" not in evidence_text and "无有效内容" not in evidence_text

    if query_type == "INTERNAL_POLICY":
        source_policy = (
            "本问题属于行内制度/流程/口径/操作类。必须以内部知识库为主；联网信息只能用于通用背景，"
            "不得覆盖或推断工银亚洲内部制度。若知识库无结果，应明确说明未检索到行内依据。"
        )
    elif query_type == "MARKET_RATE":
        source_policy = (
            "本问题属于市场利率/外部数据类。优先使用联网检索中包含明确日期、数值、期限和来源的结果；"
            "BKS 可作为背景或历史材料。若结果时效性不足，必须提示用户进一步核验最新官方报价。"
        )
    else:
        source_policy = (
            "内部知识库优先于联网检索。通用知识、宏观资讯和公开披露信息可综合联网结果，"
            "但所有事实性表述必须能在检索结果中找到依据。"
        )

    goal_policy_map = {
        "latest_value": (
            "用户要的是最新/当前数值。回答应先给结论和口径日期，再用表格列示检索证据中出现的期限、数值和来源；"
            "如检索证据未覆盖某个期限，不要补猜，明确写“检索结果未覆盖”。"
        ),
        "definition": "用户要的是定义或口径解释。回答应先给一句话定义，再分点说明适用场景、计算或注意事项。",
        "procedure": "用户要的是操作流程。回答应按步骤组织，并只引用知识库中出现的流程。",
        "policy_lookup": "用户要的是制度/标准/要求。回答应突出制度依据、适用条件、标准值和例外情况；缺失时明确说明未检索到。",
        "comparison": "用户要的是比较或趋势。回答应围绕时间、对象、变化方向和幅度组织；没有数值证据时不得判断趋势。",
        "summary": "用户要的是概览。回答应先给总体结论，再列关键依据和注意事项。",
    }
    goal_policy = goal_policy_map.get(answer_goal, goal_policy_map["summary"])

    task_profile = f"""【任务画像】
- answer_goal：{answer_goal}
- query_type：{query_type}
- entity_profile：{entity_profile}
- time_profile：{time_profile}
- classification_confidence：{classification_confidence}
- rewrite_reason：{rewrite_reason if rewrite_reason else "无"}
- ambiguity_flags：{ambiguity_flags}

【任务画像使用说明】
1. 任务画像用于帮助你理解用户要的答案形态，不是给用户展示的调试信息。
2. 若 entity_profile.default_assumption 非空，且该假设会影响答案口径，请在回答开头用自然语言轻量说明，例如“您未指定币种，以下按港元 HIBOR 理解”。
3. 若 classification_confidence 低于 0.70 或 ambiguity_flags 非空，只说明影响答案的关键不确定点，不要输出字段名。
4. 若 time_profile.freshness_required 为 true，必须强调检索结果的日期或“截至检索结果所示日期”。"""

    no_result_template = (
        "抱歉，目前未能检索到与您问题直接相关的信息。建议您：\n"
        "1. 换一种方式描述问题，或提供更具体的关键词。\n"
        "2. 如涉及行内制度或操作流程，请参考行内最新发文及通知。\n"
        "3. 如涉及市场资讯或外部数据，请以权威机构或官方渠道最新披露为准。"
    )

    rag_prompt = f"""【角色定位】
你是工银亚洲 MAVA 智能分析助手的知识问答模块，负责基于检索结果为用户提供准确、专业、可追溯的回答。

【用户问题】
{user_query}

【改写后的检索问题】
{rewritten_query if rewritten_query else user_query}

【问题类型】
{query_type}

{task_profile}

【信息使用策略】
{source_policy}

【答案组织策略】
{goal_policy}

【检索证据】
{evidence_text}

【当前日期上下文】
{date_context}

【回答要求】
1. 仅使用“检索证据”中的信息回答，不得凭模型记忆补充工银亚洲制度、流程、数值标准或内部规定。
2. 涉及市场数据时，优先提取日期、币种、期限、利率数值和来源；如果证据未覆盖用户关心的期限，请明确说明。
3. 如证据之间冲突，优先采用更权威、更新且更直接命中用户问题的来源，并说明“不同来源口径可能存在差异”。
4. 对低置信度或时效性偏旧材料，应以“仅供参考，建议进一步核验”表述。
5. 回答中保留来源编号，例如“据[联网#1]”，不要输出原始 JSON。
6. 根据“答案组织策略”选择回答结构，避免把最新数值问题写成泛泛科普，也避免把定义问题写成新闻摘要。
7. 统一使用 Markdown，语言专业、简洁、客观。

【无结果兜底】
若检索证据没有任何有效内容，请直接输出：
{no_result_template}

【禁止事项】
1. 严禁编造检索证据中未出现的数值、日期、流程、政策条款。
2. 严禁给出投资建议、预测性结论或带主观偏好的判断。
3. 严禁将猜测表述为确定事实。
4. 严禁输出模板标签或调试信息。

【免责声明】
回答末尾必须单独一行输出：
※ 本回答基于工银亚洲内部知识库及互联网公开信息检索生成，仅供参考，不构成任何业务决策依据。如涉及具体业务操作，请以行内最新制度及正式发文为准。
"""

    if not has_result:
        rag_prompt += "\n【当前检索状态】未检索到有效内容，请触发无结果兜底。\n"

    return {"final_prompt": rag_prompt, "mode": "RAG", "direct_response": ""}
