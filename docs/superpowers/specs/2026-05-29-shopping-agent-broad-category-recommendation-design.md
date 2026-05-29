# Shopping Agent Broad Category Recommendation Design

## 背景

当前后端导购 Agent 已经支持多轮购买上下文、LLM 结构化理解、规则兜底、上下文归档恢复、负反馈排除、无结果建议和推荐工具错误兜底。推荐链路也已经支持向量检索和关键词检索。

但在用户只提出泛品类请求时，体验还不够顺：

```text
推荐手机
推荐护肤品
看看耳机
有什么咖啡推荐
```

这类请求不是无效需求。真实导购场景里，用户经常先说一个大方向，再逐步补充预算、用途、品牌、肤质、口味等条件。如果系统一开始只追问细节，会显得迟钝；如果直接假装已经了解完整需求，又可能推荐不够精准。

本方案采用混合策略：**先按泛品类返回默认 Top3，让用户有可看的结果；同时在回复中提示用户可以继续补充关键条件来细化推荐**。

## 目标

- `/chat` 能识别 `推荐手机`、`推荐护肤品` 这类泛品类购买请求。
- 泛品类请求直接触发推荐工具，而不是进入通用澄清。
- 推荐结果仍来自现有推荐链路，不编造商品。
- 回复文案明确提示可继续补充预算、用途、品牌、肤质等条件。
- 该能力优先在 Agent 层落地，保持 `/recommend` 单轮接口兼容。
- 保持现有负反馈、上下文归档恢复、无结果和工具错误语义不变。

## 非目标

- 不在本方案中重做完整语义搜索或排序模型。
- 不引入新的数据库、搜索服务或外部依赖。
- 不改变 `/chat`、`/chat/stream`、`/recommend` 的顶层响应协议。
- 不让 LLM 直接决定最终商品列表。
- 不在第一版中实现复杂属性追问表单或前端 UI 改造。
- 不在第一版中处理所有口语化别名，例如 `爱疯`、`华伟`、`小蓝瓶`；这些可作为后续别名/纠错能力。

## 术语

### 泛品类请求

用户表达了明确购物目标，但没有提供足够细的约束：

```text
推荐手机
推荐护肤品
看看耳机
有没有咖啡推荐
```

它至少包含一个可映射到商品目录的目标品类，例如 `手机`、`护肤品`、`耳机`、`咖啡`。

### 完整购买请求

用户除了品类外，还提供预算、用途、品牌、关注点、肤质、场景等约束：

```text
预算6000以内，推荐拍照好的手机
推荐敏感肌能用的保湿护肤品
想买办公室喝的低糖咖啡
```

当前系统已经能较好处理这类请求，本方案不改变其主流程。

### 无效或过泛请求

用户没有给出可映射到商品目录的购物目标：

```text
随便看看
推荐一下
有什么好东西
```

这类请求仍应澄清，不应凭空选择品类。

## 设计原则

- **先给结果，再引导细化。** 泛品类请求应返回可见商品，同时告诉用户如何继续收窄。
- **识别在 Agent 层，召回在推荐链路。** Agent 负责判断是否该调用推荐工具；推荐链路继续负责筛选、检索和构建商品卡片。
- **泛品类不是负反馈，也不是上下文恢复。** 不应污染 `excluded_brands`、`negative_updates` 或 pending restore 状态。
- **不要把缺失约束当成错误。** 没有预算和用途时，推荐链路可以按品类默认召回 Top K。
- **保持 strict recommendation invariant。** 无结果返回空列表；异常向上或由 Agent tool_error 兜底；不伪造商品。
- **回复文案确定性生成。** 泛品类细化提示由后端规则生成，不依赖 LLM 自由发挥。

## 用户体验

### 场景 1：推荐手机

输入：

```text
推荐手机
```

期望行为：

- Agent 理解为 `intent=recommend`。
- `purchase_need="推荐手机"`。
- `preferences.target_category="手机"`。
- `preferences.category="数码电子"`。
- `preferences.is_broad_category_request=True`。
- 调用推荐工具。
- 返回默认 Top3 手机相关商品。
- 回复：

```text
我先按手机给你筛了几款。如果你告诉我预算、用途或品牌偏好，我可以继续缩小范围。
```

### 场景 2：推荐护肤品

输入：

```text
推荐护肤品
```

期望行为：

- Agent 理解为 `intent=recommend`。
- `target_category` 可规范化为 `护肤` 或 `护肤品`，但必须能映射到 `美妆护肤`。
- 调用推荐工具。
- 回复提示用户可继续补充肤质、功效、预算或品牌。

示例回复：

```text
我先按护肤品给你筛了几款。如果你告诉我肤质、功效需求或预算，我可以继续缩小范围。
```

### 场景 3：泛品类后继续细化

第一轮：

```text
用户：推荐手机
系统：返回默认手机推荐，并提示预算/用途/品牌
```

第二轮：

```text
用户：预算4000以内，拍照好一点
```

期望：

- 复用当前手机购买上下文。
- 更新 `budget=4000`、`focus=["拍照"]`。
- 重新推荐，而不是重新询问品类。

### 场景 4：过泛请求仍澄清

输入：

```text
推荐一下
```

期望：

- 不随机选择品类。
- 返回通用澄清：

```text
可以告诉我想买的品类、预算和最在意的点吗？
```

### 场景 5：切换泛品类

已有手机上下文后，用户说：

```text
推荐护肤品
```

期望：

- 识别为新的购买目标。
- 将手机上下文归档。
- 清空活跃推荐状态。
- 按护肤品进行默认推荐。
- 不把手机预算、手机负反馈、手机品牌偏好带入护肤品。

## 推荐架构

```text
用户消息
  -> LLMUserUnderstandingService
  -> fallback_understanding()
  -> category_rules.detect_target_category()
  -> broad category request detection
  -> LangGraphAgentRunner.update_memory()
  -> build_recommendation_query()
  -> RecommendationTool.run()
  -> recommendation_core.pipeline.recommend_products()
  -> Retriever.search()
  -> ChatResponse
```

该功能主要落在 Agent 理解和回复层：

- `agent/category_rules.py`：识别泛品类目标和泛品类购买信号。
- `agent/fallback_understanding.py`：在 LLM 不可用、LLM 脏输出或 LLM 过度澄清时，可靠地把泛品类请求转成 `recommend`。
- `agent/query_builder.py`：用 `purchase_need`、`target_category`、`category` 构造干净推荐 query。
- `agent/graph/runner.py`：根据 `is_broad_category_request` 生成带细化提示的推荐回复。
- `tests/test_agent.py`、`tests/test_main.py`：覆盖理解、集成回复和 SSE 状态。

## 数据模型

第一版不新增 Pydantic 响应 schema，只在现有 `ConversationState.preferences` 中增加一个布尔标记：

```python
preferences = {
    "target_category": "手机",
    "category": "数码电子",
    "is_broad_category_request": True,
}
```

可选增强字段：

```python
preferences = {
    "broad_category_prompt_fields": ["预算", "用途", "品牌偏好"],
}
```

MVP 推荐只实现 `is_broad_category_request`，细化提示字段由后端根据 `target_category` 动态生成，避免把文案型数据长期写入状态。

### 状态更新规则

- 泛品类请求命中后，写入 `purchase_need`、`target_category`、`category` 和 `is_broad_category_request=True`。
- 后续用户补充任何明确约束，例如预算、用途、品牌、肤质、focus，应保留 `target_category/category`，并可将 `is_broad_category_request` 改为 `False`。
- 如果用户切换到另一个目标品类，应沿用现有 `reset_context=True` 机制归档旧上下文。
- 泛品类请求不应写入 `negative_updates`、`excluded_product_ids` 或 `excluded_brands`。

## 品类识别设计

现有 `TARGET_CATEGORY_ALIASES` 已包含部分目标品类：

```python
"手机": ("手机", "数码电子")
"耳机": ("耳机", "数码电子")
"咖啡": ("咖啡", "食品生活")
"护肤": ("护肤", "美妆护肤")
```

需要补强泛品类表达：

```python
"护肤品": ("护肤品", "美妆护肤")
"护肤产品": ("护肤品", "美妆护肤")
"美妆": ("美妆", "美妆护肤")
"化妆品": ("化妆品", "美妆护肤")
```

具体是否规范化为 `护肤` 还是 `护肤品` 可在实现时确定，但必须满足两个条件：

- 推荐 query 中包含用户容易理解的目标词。
- 结构化 `category` 能映射到商品目录已有类别 `美妆护肤`。

### 购买信号

泛品类请求应识别以下信号：

```text
推荐
看看
想看
有啥
有什么
帮我选
挑一下
```

`推荐手机`、`看看手机`、`有什么护肤品推荐` 都应命中。

仅有品类词但没有购买信号时要谨慎：

```text
手机
护肤品
```

MVP 可选择把单独品类词也视为泛品类请求，因为聊天场景中用户单独输入 `手机` 通常就是导购意图。但如果担心误判，可先只支持带购买信号的表达。推荐第一版支持单独品类词，因为用户成本更低，且不会编造商品，只是按品类召回。

## 理解层设计

### LLM 主路径

Prompt 可以补充示例：

```text
用户=推荐手机
return intent=recommend, purchase_need=推荐手机,
preference_updates={"target_category":"手机","category":"数码电子","is_broad_category_request":true}
```

```text
用户=推荐护肤品
return intent=recommend, purchase_need=推荐护肤品,
preference_updates={"target_category":"护肤品","category":"美妆护肤","is_broad_category_request":true}
```

但 prompt 只是辅助，不能依赖 LLM 稳定遵守。

### 规则 fallback

`fallback_understanding()` 当前要求泛品类请求同时具备 target 和约束才返回推荐：

```python
has_constraint = budget/brand/focus/usage/preferred_brands or negative_updates
if not has_constraint:
    return None
```

本方案要新增一条独立路径：

```python
if target is not None and has_broad_category_signal(message):
    return UserUnderstanding(
        intent=UserIntent.RECOMMEND,
        confidence=0.5,
        purchase_need=message,
        preference_updates={
            "target_category": target.target_category,
            "category": target.catalog_category,
            "is_broad_category_request": True,
        },
    )
```

该路径应在完整购买请求路径之后、负反馈路径之前或之后均可，但必须保证：

- `不要苹果` 这类负反馈不会被误判为泛品类推荐。
- `太贵了` 这类上下文价格反馈仍走原有 contextual price fallback。
- `推荐一下` 无 target，不命中。

### LLM 返回 clarify 时的接管

如果 LLM 对 `推荐手机` 返回 `clarify`，但规则能识别出泛品类请求，后端应使用规则结果覆盖 LLM 澄清。这和现有上下文 fallback 思路一致：LLM 是主路径，但后端对高频确定性场景保留安全接管。

## 推荐查询设计

泛品类请求的推荐 query 应包含：

- 用户原始 `purchase_need`
- `target_category`
- `category`

示例：

```text
推荐手机，手机，数码电子
推荐护肤品，护肤品，美妆护肤
```

如果原始 `purchase_need` 已包含 `target_category`，`query_builder` 可以避免重复；现有 `_append_missing()` 已具备类似能力。

推荐链路的 `extract_filters()` 应能解析目录 category。若目标词是 `护肤品`，而现有 `CATEGORY_RULES` 只包含 `护肤`，实现时需要保证 `护肤品` 能命中 `美妆护肤`。可选做法：

- 在 `CATEGORY_RULES["美妆护肤"]` 增加 `护肤品`、`美妆`、`化妆品`。
- 或确保 query 中同时追加 `护肤`。

MVP 推荐第一种，更直接。

## 回复策略

### 普通推荐回复

保持现有文案：

```text
我根据你的需求筛选了这几款商品，可以先看第一款的匹配理由。
```

### 泛品类推荐回复

如果本轮 `preferences.is_broad_category_request=True`，且推荐成功返回 `items`：

```text
我先按{target_category}给你筛了几款。如果你告诉我{refinement_fields}，我可以继续缩小范围。
```

不同品类的建议细化字段：

```text
手机：预算、用途或品牌偏好
耳机：预算、佩戴方式或降噪需求
电脑/笔记本：预算、用途或性能需求
护肤品/护肤/美妆/化妆品：肤质、功效需求或预算
咖啡/饮品：口味、饮用场景或预算
服饰/T恤/外套：尺码、场景或风格偏好
默认：预算、用途或品牌偏好
```

如果泛品类推荐无结果：

```text
我暂时没有找到完全匹配的{target_category}商品。你可以告诉我预算、用途或品牌偏好，我再帮你缩小范围。
```

如果推荐工具错误：

```text
推荐服务暂时不可用，可以稍后重试或补充更多条件。
```

工具错误分支可沿用现有 `tool_error_reply`，不必专门改文案。

## 与上下文切换的关系

如果当前已有购买上下文，用户提出新的泛品类：

```text
当前：手机
用户：推荐护肤品
```

应视为新目标：

- `understanding.reset_context=True`
- `reset_for_new_target()` 归档手机上下文
- 清空活跃状态
- 写入护肤品上下文并推荐

如果当前已有手机上下文，用户继续说：

```text
推荐手机
```

可以视为刷新当前手机推荐，不必归档和恢复。

如果用户疑似回到归档过的旧目标：

```text
之前看过手机，现在正在看咖啡
用户：还是推荐手机吧
```

现有恢复确认逻辑可继续生效。MVP 不强行改变这套机制。若 `restore_context_category` 命中旧手机上下文，应先询问是否恢复之前需求，而不是直接覆盖。

## API 和协议

不改变请求响应 schema。

`/chat` 仍返回：

```json
{
  "session_id": "...",
  "reply": "...",
  "items": [],
  "state": {}
}
```

`state.preferences` 中可以出现：

```json
{
  "target_category": "手机",
  "category": "数码电子",
  "is_broad_category_request": true
}
```

`/chat/stream` 事件顺序保持：

```text
start -> delta -> items -> state -> done
```

`/recommend` 不变。它可以继续按 query 推荐，但是否把泛品类视为可推荐，主要由 Agent 负责。

## 错误处理和边界

- LLM 不可用：规则 fallback 应能识别泛品类请求。
- LLM 返回脏 JSON：schema 防御后仍应尝试规则 fallback。
- 泛品类无商品：返回无结果建议，不伪造商品。
- 向量检索失败：保持当前策略，`RETRIEVER_MODE=vector` 暴露错误；Agent 工具层转成 `tool_error`。
- 关键词检索模式：应同样支持泛品类，因为 query 和 CATEGORY_RULES 都能命中。
- 负反馈优先级：`不要苹果`、`不要第2个` 不应被泛品类规则吞掉。
- 无 target：`推荐一下`、`随便看看` 仍澄清。
- 别名纠错：`爱疯`、`华伟`、`护肤平` 暂不作为 MVP 验收项。

## 测试计划

### 单元测试

在 `backend/tests/test_agent.py` 增加：

- `test_category_rules_detect_broad_skin_care_category`
  - `推荐护肤品` 命中 target 和 catalog category。
- `test_fallback_understanding_recommends_broad_phone_request`
  - `推荐手机` 返回 `intent=recommend`。
  - `preference_updates.is_broad_category_request is True`。
- `test_fallback_understanding_recommends_broad_skin_care_request`
  - `推荐护肤品` 返回 `intent=recommend`。
- `test_fallback_understanding_keeps_generic_recommendation_as_clarify`
  - `推荐一下` 返回 `None`，最终走澄清。
- `test_fallback_understanding_does_not_treat_negative_feedback_as_broad_request`
  - `不要苹果` 仍进入 negative updates，不变成泛品类推荐。
- `test_query_builder_includes_broad_target_category`
  - broad context 下 query 包含 `手机` 或 `护肤品` 以及 catalog category。

### Runner 集成测试

在 `backend/tests/test_agent.py` 或 `backend/tests/test_main.py` 增加：

- `test_langgraph_runner_recommends_for_broad_phone_request`
  - 使用 fake recommendation tool。
  - 输入 `推荐手机`。
  - 期望 `action=recommend`、`items` 非空、不是 clarify。
- `test_langgraph_runner_recommends_for_broad_skin_care_request`
  - 输入 `推荐护肤品`。
  - 期望调用推荐工具。
- `test_broad_category_reply_includes_refinement_prompt`
  - 回复包含 `预算`、`用途`、`品牌偏好` 或护肤品场景下的 `肤质`、`功效`。
- `test_broad_category_request_can_be_refined_in_next_turn`
  - 第一轮 `推荐手机`。
  - 第二轮 `预算4000以内，拍照好一点`。
  - 期望保留 target category，并进入推荐。
- `test_broad_category_new_target_resets_previous_context`
  - 先手机，再 `推荐护肤品`。
  - 期望旧手机上下文归档，新上下文为护肤品。

### API/SSE 测试

- `/chat` 输入 `推荐手机` 返回 200，`items` 和 `state.preferences.is_broad_category_request` 正确。
- `/chat/stream` 输入 `推荐护肤品` 仍返回 `start -> delta -> items -> state -> done`。
- 工具错误时仍返回稳定 `tool_error` state，不破坏 broad category 状态。

### 推荐链路测试

在 `backend/tests/test_recommendation.py` 中补充：

- `extract_filters("推荐护肤品")["category"] == "美妆护肤"`。
- `extract_filters("推荐手机")["category"] == "数码电子"`。
- keyword retriever 在只给品类词时仍能返回 Top K 候选。

## 日志与可观测性

建议新增或保留：

```text
understanding source=fallback reason=broad_category_request target_category=手机
agent broad_category_request target_category=手机 category=数码电子
agent recommendation query_length=...
```

日志仍不记录完整用户消息，不记录 API Key，不记录完整外部响应。

## 实施顺序

1. 为泛品类识别写失败测试。
2. 扩展 `category_rules.py` 的 target aliases 和 broad request 判断。
3. 扩展 `fallback_understanding.py`，让泛品类请求返回 `UserUnderstanding(intent=recommend)`。
4. 补 LLM prompt 示例，降低模型过度澄清概率。
5. 确保 `query_builder.py` 能构造有效泛品类 query。
6. 在 `runner` 推荐回复中加入 broad category 细化提示。
7. 补 `/chat` 和 `/chat/stream` 回归测试。
8. 跑定向测试和全量后端检查。
9. 更新 README 或 API 文档中的 Agent 多轮行为说明。

## 验收标准

- `推荐手机` 在 `/chat` 中触发推荐，返回商品，不返回通用澄清。
- `推荐护肤品` 在 `/chat` 中触发推荐，返回商品，不返回通用澄清。
- broad category 推荐回复包含继续细化提示。
- `推荐一下` 仍返回澄清，不随机选择品类。
- 泛品类请求后的下一轮约束补充能复用当前上下文。
- 从手机切换到护肤品时，旧上下文被归档，新上下文不继承旧手机偏好或负反馈。
- LLM 关闭时，上述行为仍通过规则 fallback 成立。
- `/chat/stream` 事件顺序不变。
- `/recommend` 顶层协议不变。
- 现有负反馈、无结果、工具错误测试不回退。

## 后续扩展

MVP 稳定后可以继续做：

- 品牌和商品别名纠错，例如 `爱疯 -> iPhone/Apple`、`华伟 -> 华为`。
- 品类同义词扩展，例如 `面部护理 -> 护肤品`。
- 根据品类生成更精细的追问策略，例如护肤品优先问肤质，手机优先问预算和用途。
- 将 broad category 默认排序从“检索相关”升级为“热度/评分/多样性”混合排序。
- 前端快捷 chips，例如 `预算3000以内`、`拍照优先`、`敏感肌`。

## 设计结论

这个能力应作为 Agent 的泛品类推荐能力实现，而不是只改检索器。

最小可靠路径是：

```text
泛品类自然语言
 -> category_rules 识别目标品类
 -> fallback_understanding 生成 recommend
 -> conversation.preferences 标记 broad category
 -> recommendation_tool 返回默认 Top3
 -> runner 回复中提示继续细化
```

这样既能让 `推荐手机`、`推荐护肤品` 立即产生有用结果，又保留导购继续追问和多轮细化的空间。
