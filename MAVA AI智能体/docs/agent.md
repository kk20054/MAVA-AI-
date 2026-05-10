# Agent 工作准则

## 本次动手前联网调研记录

日期：2026-05-07

参考来源：
- OpenAI File Search 文档：检索链路内置查询改写、复杂问题拆分、关键词+语义混合检索、结果重排；默认 `score_threshold` 为 0，过高阈值可能遗漏可用片段。来源：https://platform.openai.com/docs/assistants/tools/file-search
- Microsoft Azure AI Search 文档：混合检索使用 Reciprocal Rank Fusion，将多个已排序结果合并；不同检索算法分数范围不同，不应直接用单一分数阈值跨来源裁剪。来源：https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking
- Anthropic Contextual Retrieval：传统 RAG 会因切块丢失上下文而漏召回；BM25 精确匹配可弥补向量语义检索对专有名词、代码、缩写的遗漏；上下文化切块 + BM25 + 重排能显著降低检索失败。来源：https://www.anthropic.com/engineering/contextual-retrieval
- Amazon Bedrock Knowledge Bases 文档：可配置最大召回结果数、Hybrid/Semantic 搜索、元数据过滤、重排和问题拆解；时效类问题应结合最近更新时间等元数据。来源：https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html

## 落地原则

1. 不把 `relevance` 当成唯一裁判。它可能来自不同系统，分数区间、含义和校准方式都不同。
2. 知识问答检索采用“先保召回，再控上下文”的策略。先保留可能相关的片段，再用重排、去重、摘取命中片段控制上下文。
3. 对 HIBOR、LPR、SOFR、汇率等时效市场问题，必须保护实体精确命中、日期、数值、期限字段和权威/常用市场来源，低 `relevance` 不直接删除。
4. 对内部制度、口径、流程类问题，内部知识库优先；联网结果只用于补充通用解释，不可覆盖行内制度。
5. 对上下文窗口限制，优先做片段级压缩：围绕关键词截取、表格行保留、重复结果去重、按来源分配预算，而不是粗暴按阈值删除整条结果。
6. 输出提示词必须暴露来源编号、置信度和时效性，避免模型把低置信或过期资料说成确定事实。

## 本项目进展理解

从本地文件看，报告模块已推进到 v8/v8.1，重点是参数抽取、数据预处理、报告分析师提示词和接入说明；问数模块已推进到 v9，重点是脚本预计算、指标口径约束、经营诊断素材包和回答专家提示词。

本次知识问答模块建议推进为 v10：维持“脚本强约束 + 模型负责表达”的总路线，但把检索侧从“动态阈值删除”升级为“多信号重排 + 保护召回 + 上下文预算压缩”。

## 2026-05-07 追加调研：参数识别与合成对接

补充参考：
- OpenAI File Search 文档强调检索前会进行 query rewriting、复杂问题拆分和多路检索，说明改写后的查询不应替代原始问题，而应和原始意图一起传入生成阶段。来源：https://platform.openai.com/docs/assistants/tools/file-search
- Azure AI Search 语义排序和答案/摘要能力强调从候选文本中提取更贴近查询的片段，说明合成阶段需要明确“用户要的答案形态”和“证据片段的用途”。来源：https://learn.microsoft.com/en-us/azure/search/semantic-search-overview
- Amazon Bedrock Knowledge Bases 支持隐式/显式元数据过滤、查询拆解、重排与引用，说明时间、来源、实体等结构化参数应作为检索和生成的共同上下文。来源：https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html

追加落地原则：
1. 参数识别新增字段必须兼容已发布工作流：只新增，不删除旧字段；旧节点继续使用 `intent/query_type/kb_query/web_query/is_intro`。
2. 时间参数应拆为 `time_profile`，包含用户原始时间词、解析日期范围、是否要求最新、口径日期；合成阶段用它判断是否要提示时效性。
3. 查询改写要给出 `classification_confidence` 和 `rewrite_reason`，并把不确定点放入 `ambiguity_flags`，让生成模型知道哪些假设可以明说。
4. 合成生成继续使用模型，但要传入“任务画像”：`answer_goal + entity_profile + time_profile + confidence`，让模型先按任务类型组织答案，再引用证据。

## 2026-05-07 追加调研：查询解析延迟优化

补充参考方向：
- 轻量 RAG 路由通常采用“规则优先 + 小模型/短提示词兜底”，只让模型处理模糊语义，不让模型重复做日期解析、实体归一化、置信度计算等脚本可完成的工作。
- 查询改写的延迟主要受输入提示词长度和输出字段数量影响；结构化输出字段越多，模型生成 token 越多，响应越慢。
- 对已发布工作流，最稳妥的降延迟方案不是重排节点，而是把 01 预处理提示词瘦身：模型只输出 intent、query_type、raw_query、rewritten_query、search_keywords、protected_terms、freshness_required；`answer_goal/time_profile/entity_profile/confidence/rewrite_reason/ambiguity_flags` 仍由 02 脚本补齐。

v10.2 落地原则：
1. 01 只做“少量语义判断 + 检索改写”，输出字段从 13 个减少到 7 个。
2. 02 保持 v10.1 的字段补齐能力，兼容 01 不输出复杂画像。
3. 牺牲一点模型端精细判断，换取明显更低延迟；复杂结构仍由脚本稳定生成。
## 2026-05-09 追加调研：OIC 看板与对话框联动

参考来源：
- Microsoft Power BI Copilot：强调在报表、视觉对象和语义模型上下文中生成摘要和解释，适合作为“看板点击后把当前上下文交给助手”的参考。来源：https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-introduction
- Microsoft Fabric / Power BI Copilot 概览：将 Copilot 放在已有 BI 资产旁边，辅助生成洞察、叙述和页面内容，说明 AI 助手应嵌入在数据页面旁侧，而不是另起孤立入口。来源：https://learn.microsoft.com/en-us/fabric/get-started/copilot-power-bi-overview
- Tableau Pulse：以指标为中心推送洞察，并支持围绕指标继续追问，适合作为 OIC 指标卡到洞察解释的参考。来源：https://www.tableau.com/products/tableau-pulse
- ThoughtSpot Spotter：偏“自然语言 + 指标语义层 + 可追溯分析”的模式，可参考其把自然语言追问绑定到指标语义层的做法。来源：https://www.thoughtspot.com/product/spotter

落地原则：
1. OIC 看板不是单纯多做图表，而是把“指标、产品、客户、日期、OIC”变成稳定的 `dashboard_context`，每次点击都显式更新上下文。
2. 对话框不应猜测用户刚才点击了什么，必须读取前端传入的 `dashboard_context` 和后端生成的 `analysis_pack`。
3. 数值、排名、同比、环比、客户贡献由脚本和接口生成；模型只负责解释、归因、组织语言和提出下一步追问。
4. 点击 KPI 后刷新第二行趋势和产品 Rank；点击产品后刷新第三行客户 Top20；点击客户后进入客户贡献解释。链路应固定，减少模型解析压力。
5. 生成报告模块应复用当前看板的 `analysis_pack`，不要重新取数和重复计算。
6. 知识问答模块只处理制度、口径、市场背景；经营数据追问优先走 OIC 数据分析链路。

## 2026-05-10 追加调研：问数助手、看板和报告的统一架构

本次将此前“问数助手与经营看板优化建议”沉淀为项目级架构方案，核心产物见：

- `MAVA AI智能体/docs/问数助手与经营看板架构迭代方案.md`
- `MAVA AI智能体/examples/OIC看板联动demo/oic_dashboard_interactive_demo.html`
- `MAVA AI智能体/examples/OIC看板联动demo/OIC看板交互Demo与落地说明_v3.md`

追加落地原则：
1. `dashboard_context` 是看板和对话框之间的唯一上下文契约，点击 KPI、产品、客户、范围、日期时都要显式更新。
2. `analysis_pack` 是问数回答、看板刷新和报告生成的统一事实包，报告模块应优先复用它，不重新取数。
3. `dim_metric_registry` 和 `dim_metric_product_mapping` 应成为指标语义层核心资产，避免问数、看板、报告各自维护口径。
4. 客户 TopN 属于敏感经营明细，必须配套权限校验、访问审计和导出/报告留痕。
5. NL2SQL 只建议作为后续分析师沙盒能力，并限定脱敏数据、白名单、AST 校验、超时、LIMIT 和审计。
