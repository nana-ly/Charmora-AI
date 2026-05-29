# Shopping Agent Broad Category Recommendation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让购物 Agent 正确支持“推荐手机/推荐护肤品”这类泛品类推荐，并在负反馈、目标切换、归档恢复、API/SSE 状态中保持一致语义。

**Architecture:** 以现有 LangGraph runner 为编排中心，理解层只产出本轮结构化意图和 canonical target，runner 负责基于 reset 前 active snapshot 计算恢复、item-index 过滤和 effective reset。负反馈状态继续保持 MVP 单字段模型，query 清洗使用同一规则入口从原始文本移除全部负向短语。

**Tech Stack:** Python 3.12, FastAPI, Pydantic, LangGraph, pytest, ruff.

---

## 参考资料

- 设计文档：`docs/superpowers/specs/2026-05-29-shopping-agent-broad-category-recommendation-design.md`
- 现有负反馈计划：`docs/superpowers/plans/2026-05-28-shopping-agent-negative-feedback-exclusion.md`
- 后端测试目录：`backend/tests/`

## 执行前保护

- [ ] **Step 0.1: 检查脏工作树**

Run:

```powershell
git status --short
```

Expected:
- 允许看到用户或其它代理留下的设计文档、本计划文件、`rag/.chroma/` 数据目录等未提交改动。
- 实施本计划时只修改每个 Task 的 **Files** 列表中的文件。
- 每次 `git add` 只添加本 Task touched files；不要添加 `rag/.chroma/` 数据目录、无关设计文档或其它代理改动。

- [ ] **Step 0.2: 保持架构边界**

执行约束：
- 不新增架构层，不把 category rule、context manager、runner、recommendation filters 的职责混在一起。
- 关键业务逻辑必须写清晰中文注释，至少覆盖 `active_target_key()`、`request_restore()`、`filter_item_index_negative_updates_for_current_target()`、`effective_reset`、`current_turn_is_broad`。
- 涉及用户可见契约或多轮状态语义的实现，同步修改 `backend/README.md`。

## 文件结构与职责

- `backend/agent/category_rules.py`
  - 维护目标品类别名、catalog category、canonical target key、购买信号、恢复信号。
  - 新增 `canonical_target_key()`、`detect_restore_target()`，并让 `detect_target_category()` 返回 canonical key。

- `backend/agent/memory.py`
  - 扩展 `PurchaseContext` 与 `ConversationState`：归档保存 `canonical_target_key/display_target_category`，会话保存 `pending_restore_display_target`。
  - 归档对象不得保存 stale `is_broad_category_request`。

- `backend/agent/context_manager.py`
  - 基于 canonical key 归档、去重、查找、恢复。
  - `request_restore()` 写 pending canonical key 与 display target。
  - `confirm_restore()` 恢复后清空 pending 字段，并强制清除 broad 标记。

- `backend/agent/negative_feedback_rules.py`
  - 负反馈抽取保持单字段优先级。
  - 新增 `clean_positive_purchase_need()` 和内部 negative phrase/span 识别，使 query 清洗覆盖全部负向短语。

- `backend/agent/negative_feedback.py`
  - 新增 `filter_item_index_negative_updates_for_current_target()`。
  - `apply_negative_feedback()` 保持当前状态变更职责，不负责跨 target 判定。

- `backend/agent/fallback_understanding.py`
  - 规则 fallback 识别泛品类 recommend、混合负反馈、purchase_need 清洗、canonical key。
  - 不把 `reset_context` 作为新目标最终依据。

- `backend/agent/understanding.py`
  - 更新 LLM system prompt 与返回接管逻辑。
  - LLM 缺字段或返回 clarify 时，规则 fallback 能补齐 deterministic broad 字段。

- `backend/agent/query_builder.py`
  - 构建 query 前调用 `clean_positive_purchase_need()`。
  - query 包含正向 `purchase_need/target_category/category`，不包含负向短语。

- `backend/recommendation_core/filters.py`
  - 推荐链路的 catalog category 过滤入口，确保 `护肤品/美妆/化妆品` 映射到 `美妆护肤`。

- `backend/agent/graph/runner.py`
  - 先处理 pending restore，再处理恢复信号。
  - reset 前读取 active snapshot，先过滤 item-index 负反馈，再计算 effective reset，再 merge/apply。
  - 回复时区分本轮 broad 标记与持久状态。

- `backend/tests/test_agent.py`
  - 品类规则、fallback、LLM 边界、runner 集成主测试。

- `backend/tests/test_negative_feedback.py`
  - 负反馈抽取、清洗、item-index filter helper 测试。

- `backend/tests/test_recommendation.py`
  - 推荐 filters 的品类映射回归测试。

- `backend/tests/test_main.py`
  - `/chat` API 状态契约测试。

- `backend/tests/test_sse.py`
  - `/chat/stream` SSE 状态事件测试。

- `backend/README.md`
  - 补充多轮 Agent 行为说明。

---

### Task 1: Canonical Target 与归档状态模型

**Files:**
- Modify: `backend/agent/category_rules.py`
- Modify: `backend/agent/memory.py`
- Modify: `backend/agent/context_manager.py`
- Test: `backend/tests/test_agent.py`

- [ ] **Step 1: 写 canonical key 与状态模型失败测试**

在 `backend/tests/test_agent.py` 追加这些测试。测试使用现有中文字符串风格；如果文件里中文显示为乱码，不要转换整文件编码，只追加 UTF-8 文本。

```python
def test_category_rules_canonical_target_key_aliases():
    from agent.category_rules import canonical_target_key, detect_target_category

    phone = detect_target_category("推荐手机")
    headphones = detect_target_category("推荐耳机")
    skin_care = detect_target_category("推荐护肤品")
    skin_care_alias = detect_target_category("看看护肤产品")
    tshirt = detect_target_category("推荐T恤")
    jacket = detect_target_category("推荐外套")

    assert phone is not None
    assert headphones is not None
    assert skin_care is not None
    assert skin_care_alias is not None
    assert tshirt is not None
    assert jacket is not None
    assert phone.canonical_target_key == "phone"
    assert headphones.canonical_target_key == "headphones"
    assert phone.catalog_category == "数码电子"
    assert headphones.catalog_category == "数码电子"
    assert skin_care.target_category == "护肤品"
    assert skin_care.canonical_target_key == "skin_care"
    assert skin_care_alias.canonical_target_key == "skin_care"
    assert tshirt.catalog_category == "服饰运动"
    assert jacket.catalog_category == "服饰运动"
    assert canonical_target_key("护肤品", "美妆护肤") == "skin_care"
    assert canonical_target_key("手机", "数码电子") == "phone"
```

```python
def test_purchase_context_archive_uses_canonical_key_and_drops_broad_flag():
    from agent.context_manager import archive_active_context
    from agent.memory import ConversationState

    state = ConversationState(session_id="archive-canonical")
    state.purchase_need = "推荐手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
        "is_broad_category_request": True,
    }

    archive_active_context(state)

    archived = state.previous_purchase_contexts[0]
    assert archived.canonical_target_key == "phone"
    assert archived.display_target_category == "手机"
    assert archived.preferences["target_category"] == "手机"
    assert "is_broad_category_request" not in archived.preferences
```

```python
def test_conversation_state_tracks_pending_restore_display_target_default():
    from agent.memory import ConversationState

    state = ConversationState(session_id="pending-display-default")

    assert state.pending_restore_category is None
    assert state.pending_restore_display_target is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "canonical_target_key_aliases or archive_uses_canonical_key or pending_restore_display" -v
```

Expected:
- `canonical_target_key` import 失败，或 `TargetCategoryMatch` 缺少 `canonical_target_key`。
- `PurchaseContext` 缺少 `canonical_target_key/display_target_category`。
- `ConversationState` 缺少 `pending_restore_display_target`。

- [ ] **Step 3: 实现 category rules canonical key**

修改 `backend/agent/category_rules.py`：

```python
class TargetCategoryMatch(BaseModel):
    target_category: str
    catalog_category: str | None = None
    matched_text: str
    canonical_target_key: str
```

将 alias 配置改成有序结构。长 alias 必须排在短 alias 前，避免 `"推荐护肤品"` 先命中 `"护肤"` 导致 display target 错误：

```python
from collections.abc import Sequence


TARGET_CATEGORY_ALIASES: Sequence[tuple[str, str, str, str]] = tuple(
    sorted(
        (
            ("护肤产品", "护肤产品", "美妆护肤", "skin_care"),
            ("护肤品", "护肤品", "美妆护肤", "skin_care"),
            ("化妆品", "护肤品", "美妆护肤", "skin_care"),
            ("笔记本", "笔记本", "数码电子", "laptop"),
            ("防晒", "防晒", "美妆护肤", "skin_care"),
            ("面霜", "面霜", "美妆护肤", "skin_care"),
            ("护肤", "护肤", "美妆护肤", "skin_care"),
            ("美妆", "护肤品", "美妆护肤", "skin_care"),
            ("手机", "手机", "数码电子", "phone"),
            ("耳机", "耳机", "数码电子", "headphones"),
            ("电脑", "电脑", "数码电子", "computer"),
            ("平板", "平板", "数码电子", "tablet"),
            ("咖啡", "咖啡", "食品生活", "coffee"),
            ("饮品", "饮品", "食品生活", "beverage"),
            ("T恤", "T恤", "服饰运动", "t_shirt"),
            ("外套", "外套", "服饰运动", "jacket"),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


def detect_target_category(message: str) -> TargetCategoryMatch | None:
    for alias, target_category, catalog_category, key in TARGET_CATEGORY_ALIASES:
        if alias in message:
            return TargetCategoryMatch(
                target_category=target_category,
                catalog_category=catalog_category,
                matched_text=alias,
                canonical_target_key=key,
            )
    return None


def canonical_target_key(
    target_category: str | None,
    catalog_category: str | None = None,
) -> str | None:
    if not target_category and not catalog_category:
        return None
    for _, canonical, catalog, key in TARGET_CATEGORY_ALIASES:
        if target_category == canonical:
            return key
    if target_category:
        for alias, _, _, key in TARGET_CATEGORY_ALIASES:
            if target_category == alias:
                return key
    return None


def catalog_category_for(target_category: str) -> str | None:
    for _, canonical, catalog_category, _ in TARGET_CATEGORY_ALIASES:
        if canonical == target_category:
            return catalog_category
    return None
```

- [ ] **Step 4: 实现 memory 字段**

修改 `backend/agent/memory.py`。注意：不要替换整个 `PurchaseContext` 类；只在现有字段和现有复制逻辑上新增两个字段，避免误删已有字段：

在 import 区新增纯规则函数导入：

```python
from agent.category_rules import canonical_target_key
```

这是从 `category_rules` 导入的纯规则函数，只用于从 `target_category/category` 派生 canonical key；不要把 `context_manager` 的状态流转、归档查找或恢复逻辑引入 `memory.py`，避免 memory 层反向依赖 context_manager。

```python
class PurchaseContext(BaseModel):
    canonical_target_key: str | None = None
    display_target_category: str | None = None
```

在 `PurchaseContext.from_conversation()` 里保留所有现有字段复制逻辑，只增加 broad 标记剥离、canonical/display 读取或派生，以及 `return cls` 调用里的两个新字段。不要引入不存在的会话备注字段或任何备注相关代码；不允许复制截断版 `return cls(...)` 示例，必须基于当前 `backend/agent/memory.py` 的完整字段复制来改：

```python
preferences = deepcopy(conversation.preferences)
preferences.pop("is_broad_category_request", None)
target_category = preferences.get("target_category")
category = preferences.get("category")
canonical_key = preferences.get("canonical_target_key")
if not isinstance(canonical_key, str) or not canonical_key.strip():
    canonical_key = canonical_target_key(
        target_category if isinstance(target_category, str) else None,
        category if isinstance(category, str) else None,
    )
display_target = target_category if isinstance(target_category, str) else None

return cls(
    purchase_need=conversation.purchase_need or "",
    preferences=preferences,
    excluded_product_ids=deepcopy(conversation.excluded_product_ids),
    excluded_brands=deepcopy(conversation.excluded_brands),
    excluded_keywords=deepcopy(conversation.excluded_keywords),
    excluded_price_ranges=deepcopy(conversation.excluded_price_ranges),
    negative_feedback_items=deepcopy(conversation.negative_feedback_items),
    latest_attempt_status=conversation.latest_attempt_status,
    latest_attempt_error=conversation.latest_attempt_error,
    latest_no_results_relax_options=deepcopy(
        conversation.latest_no_results_relax_options
    ),
    last_successful_items=deepcopy(conversation.last_successful_items),
    last_successful_result_id=conversation.last_successful_result_id,
    last_successful_query=conversation.last_successful_query,
    last_successful_filters=deepcopy(conversation.last_successful_filters),
    last_query=conversation.last_query,
    last_filters=deepcopy(conversation.last_filters),
    last_items=deepcopy(conversation.last_items),
    last_result_status=conversation.last_result_status,
    last_no_results_need=conversation.last_no_results_need,
    last_no_results_relax_options=deepcopy(conversation.last_no_results_relax_options),
    target_category=target_category if isinstance(target_category, str) else None,
    category=category if isinstance(category, str) else None,
    canonical_target_key=canonical_key if isinstance(canonical_key, str) else None,
    display_target_category=display_target,
)
```

在 `apply_to_conversation()` 里恢复后强制 broad 为 `False`：

```python
conversation.preferences = deepcopy(self.preferences)
if self.canonical_target_key:
    conversation.preferences["canonical_target_key"] = self.canonical_target_key
if self.target_category:
    conversation.preferences["target_category"] = self.target_category
if self.category:
    conversation.preferences["category"] = self.category
conversation.preferences["is_broad_category_request"] = False
```

在 `ConversationState` 添加：

```python
pending_restore_display_target: str | None = None
```

- [ ] **Step 5: 实现 context_manager canonical 归档去重**

修改 `backend/agent/context_manager.py`，新增内部 helper：

```python
from agent.category_rules import canonical_target_key


def active_target_key(conversation: ConversationState) -> str | None:
    # 当前目标统一用 canonical key 判断；旧状态缺 key 时从 target_category + category 推导并写回。
    # 不要只用 catalog category 判断，否则“手机”和“耳机”都会落到“数码电子”而无法区分目标。
    key = conversation.preferences.get("canonical_target_key")
    if isinstance(key, str) and key.strip():
        return key
    target = conversation.preferences.get("target_category")
    category = conversation.preferences.get("category")
    if isinstance(target, str):
        derived = canonical_target_key(
            target,
            category if isinstance(category, str) else None,
        )
        if derived:
            conversation.preferences["canonical_target_key"] = derived
            return derived
    return None
```

新增归档项 legacy 修复 helper。归档恢复和归档去重都必须从 `item.target_category` 或 `item.preferences["target_category"]` 结合 `item.category`/`item.preferences["category"]` 派生 canonical key，并写回 `canonical_target_key` 与 `display_target_category`：

```python
def ensure_archived_target_fields(item: PurchaseContext) -> str | None:
    target = item.target_category or item.preferences.get("target_category")
    category = item.category or item.preferences.get("category")
    if not item.display_target_category and isinstance(target, str):
        item.display_target_category = target
    if item.canonical_target_key:
        return item.canonical_target_key
    key = canonical_target_key(
        target if isinstance(target, str) else None,
        category if isinstance(category, str) else None,
    )
    if key:
        item.canonical_target_key = key
    return key
```

更新 `archive_active_context()` 以 canonical key 去重：

```python
archived = PurchaseContext.from_conversation(conversation)
key = archived.canonical_target_key or active_target_key(conversation)
if key:
    archived.canonical_target_key = key
deduped = [
    item
    for item in conversation.previous_purchase_contexts
    if ensure_archived_target_fields(item) != key
]
conversation.previous_purchase_contexts = [archived, *deduped][:max_contexts]
```

- [ ] **Step 6: 运行 Task 1 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "canonical_target_key_aliases or archive_uses_canonical_key or pending_restore_display" -v
```

Expected: 3 passed.

- [ ] **Step 7: 提交 Task 1**

```powershell
git add backend/agent/category_rules.py backend/agent/memory.py backend/agent/context_manager.py backend/tests/test_agent.py
git commit -m "feat(agent): add canonical target state"
```

---

### Task 2: 负反馈单字段模型与 query 清洗入口

**Files:**
- Modify: `backend/agent/negative_feedback_rules.py`
- Modify: `backend/agent/query_builder.py`
- Test: `backend/tests/test_negative_feedback.py`
- Test: `backend/tests/test_agent.py`

- [ ] **Step 1: 写负反馈抽取与清洗失败测试**

在 `backend/tests/test_negative_feedback.py` 追加：

```python
def test_extract_negative_updates_single_field_priority_for_mixed_item_index_and_brand():
    from agent.negative_feedback_rules import extract_negative_updates

    assert extract_negative_updates("推荐手机，不要第2个，不要苹果") == {
        "excluded_item_indexes": [2]
    }
```

```python
def test_clean_positive_purchase_need_removes_all_negative_phrases_with_single_field_updates():
    from agent.negative_feedback_rules import (
        clean_positive_purchase_need,
        extract_negative_updates,
    )

    message = "推荐手机，不要第2个，不要苹果"
    negative_updates = extract_negative_updates(message)

    cleaned = clean_positive_purchase_need(message, negative_updates)

    assert cleaned == "推荐手机"
    assert "不要第2个" not in cleaned
    assert "不要苹果" not in cleaned
```

```python
def test_clean_positive_purchase_need_allows_empty_string_for_pure_negative_text():
    from agent.negative_feedback_rules import clean_positive_purchase_need

    assert clean_positive_purchase_need("不要苹果") == ""
```

在 `backend/tests/test_agent.py` 追加 query builder 测试：

```python
def test_query_builder_excludes_all_negative_phrases_when_negative_updates_is_single_field():
    from agent.memory import ConversationState
    from agent.query_builder import build_recommendation_query

    state = ConversationState(session_id="query-clean-all-negative")
    state.purchase_need = "推荐手机，不要第2个，不要苹果"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
    }
    state.excluded_brands = ["苹果"]

    query = build_recommendation_query(state)

    assert "推荐手机" in query
    assert "手机" in query
    assert "数码电子" in query
    assert "不要第2个" not in query
    assert "不要苹果" not in query
    assert "苹果" not in query
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_negative_feedback.py -k "single_field_priority or clean_positive" -v
uv run pytest tests/test_agent.py -k "query_builder_excludes_all_negative" -v
```

Expected:
- `clean_positive_purchase_need` import 失败。
- 混合 item-index 和 brand 时现有抽取可能只测不到全部清洗语义。

- [ ] **Step 3: 实现全部负向短语识别与清洗**

在 `backend/agent/negative_feedback_rules.py` 中新增：

```python
NegativeFeedbackUpdates = dict[str, Any]


from collections.abc import Sequence


def _negative_phrase_patterns() -> Sequence[str]:
    brand_names = "|".join(re.escape(brand) for brand in BRAND_TERMS)
    return (
        r"(?:不要|不买|不考虑|排除)\s*第\s*\d+\s*[个款]?",
        r"第\s*\d+\s*[个款]?\s*(?:不要|不买|不考虑|排除)",
        rf"(?:不要|不买|不考虑|排除)\s*(?:{brand_names})",
        rf"(?:{brand_names})\s*(?:(?:也)?(?:可以|行)\s*)?(?:不要|不买|不考虑|排除)",
    )


def _remove_negative_phrases(text: str) -> str:
    cleaned = text
    for pattern in _negative_phrase_patterns():
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"[，,、；;]\s*[，,、；;]+", "，", cleaned)
    cleaned = cleaned.strip(" ，,、；;\n\t")
    return cleaned.strip()


def clean_positive_purchase_need(
    text: str,
    negative_updates: NegativeFeedbackUpdates | None = None,
) -> str:
    del negative_updates
    return _remove_negative_phrases(text)
```

调整 `extract_negative_updates()` 顺序，确保 MVP 单字段优先级：

```python
item_exclusion = _extract_item_index_exclusion(text)
if item_exclusion:
    return {"excluded_item_indexes": [item_exclusion]}

excluded_brand = _extract_brand_exclusion(text)
if excluded_brand:
    return {"excluded_brands": [excluded_brand]}
```

保留现有 unsupported/remove 逻辑，但不能让 brand 与 item-index 同轮同时返回。

- [ ] **Step 4: 让 query builder 使用唯一清洗入口**

修改 `backend/agent/query_builder.py`：

```python
from agent.negative_feedback_rules import clean_positive_purchase_need
```

在 `build_recommendation_query()` 开头替换当前品牌片段清洗：

```python
purchase_need = clean_positive_purchase_need(conversation.purchase_need)
purchase_need = _clean_negative_brand_fragments(
    purchase_need,
    conversation.excluded_brands,
)
if not purchase_need:
    target = preferences.get("target_category")
    category = preferences.get("category")
    purchase_need = str(target or category or "").strip()
```

- [ ] **Step 5: 运行 Task 2 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_negative_feedback.py -k "single_field_priority or clean_positive" -v
uv run pytest tests/test_agent.py -k "query_builder_excludes_all_negative" -v
```

Expected: all selected tests passed.

- [ ] **Step 6: 提交 Task 2**

```powershell
git add backend/agent/negative_feedback_rules.py backend/agent/query_builder.py backend/tests/test_negative_feedback.py backend/tests/test_agent.py
git commit -m "feat(agent): clean negative phrases from queries"
```

---

### Task 3: 规则 fallback 支持泛品类 recommend

**Files:**
- Modify: `backend/agent/fallback_understanding.py`
- Modify: `backend/agent/category_rules.py`
- Test: `backend/tests/test_agent.py`

- [ ] **Step 1: 写 fallback 失败测试**

在 `backend/tests/test_agent.py` 追加：

```python
def test_fallback_understanding_recommends_broad_phone_request():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    understanding = fallback_understanding(
        message="推荐手机",
        conversation=ConversationState(session_id="fallback-broad-phone"),
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == "推荐手机"
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["category"] == "数码电子"
    assert understanding.preference_updates["canonical_target_key"] == "phone"
    assert understanding.preference_updates["is_broad_category_request"] is True
    assert understanding.negative_updates == {}
```

```python
def test_fallback_understanding_keeps_negative_updates_for_mixed_broad_request():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    understanding = fallback_understanding(
        message="推荐手机，不要苹果",
        conversation=ConversationState(session_id="fallback-broad-negative"),
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == "推荐手机"
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["category"] == "数码电子"
    assert understanding.preference_updates["canonical_target_key"] == "phone"
    assert understanding.preference_updates["is_broad_category_request"] is True
    assert understanding.negative_updates == {"excluded_brands": ["苹果"]}
```

```python
def test_fallback_understanding_does_not_recommend_without_target():
    from agent.fallback_understanding import fallback_understanding

    assert fallback_understanding(
        message="推荐一下",
        conversation=ConversationState(session_id="fallback-no-target"),
        reason="test",
    ) is None
```

```python
def test_clean_positive_purchase_need_empty_falls_back_to_target_category():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    understanding = fallback_understanding(
        message="手机，不要苹果",
        conversation=ConversationState(session_id="fallback-empty-clean"),
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == "手机"
```

```python
def test_fallback_understanding_recommends_target_with_negative_without_purchase_signal():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    understanding = fallback_understanding(
        message="手机，不要苹果",
        conversation=ConversationState(session_id="fallback-target-negative"),
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == "手机"
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["canonical_target_key"] == "phone"
    assert understanding.negative_updates == {"excluded_brands": ["苹果"]}
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "fallback_understanding_recommends_broad or mixed_broad_request or does_not_recommend_without_target or empty_falls_back or target_with_negative" -v
```

Expected:
- `推荐手机` 可能返回 `None` 或缺少 `is_broad_category_request/canonical_target_key`。
- `purchase_need` 仍含负向短语。

- [ ] **Step 3: 实现 broad 信号 helper**

在 `backend/agent/category_rules.py` 增加：

```python
BROAD_CATEGORY_SIGNALS = ("推荐", "看看", "有什么", "想买", "要买")


def has_broad_category_signal(message: str) -> bool:
    return any(signal in message for signal in BROAD_CATEGORY_SIGNALS)


def is_standalone_category_term(message: str, target: TargetCategoryMatch) -> bool:
    stripped = message.strip(" ，,。.!！？?")
    return stripped == target.matched_text
```

- [ ] **Step 4: 实现 fallback broad 分支**

修改 `backend/agent/fallback_understanding.py` import：

```python
from agent.category_rules import (
    catalog_category_for,
    detect_target_category,
    extract_preference_hints,
    has_broad_category_signal,
    has_purchase_signal,
    is_standalone_category_term,
)
from agent.negative_feedback_rules import (
    clean_positive_purchase_need,
    extract_negative_updates,
)
```

新增 positive constraint 判断：

```python
def _has_positive_constraints(hints: dict[str, object]) -> bool:
    return any(
        key in hints
        for key in ("budget", "brand", "focus", "usage", "preferred_brands")
    )
```

更新 `_purchase_request_understanding()`：

```python
target = detect_target_category(message)
if target is None:
    return None

hints = extract_preference_hints(message)
negative_updates = negative_updates or {}
positive_purchase_need = clean_positive_purchase_need(message, negative_updates)
if not positive_purchase_need and target.target_category:
    positive_purchase_need = target.target_category
has_negative_updates = bool(negative_updates)

is_broad = (
    (has_broad_category_signal(message) or is_standalone_category_term(message, target))
    and not _has_positive_constraints(hints)
)
has_clean_positive_target = bool(positive_purchase_need)
if not has_purchase_signal(message) and not is_broad and not (has_clean_positive_target and has_negative_updates):
    return None

updates = {
    "target_category": target.target_category,
    "category": target.catalog_category or catalog_category_for(target.target_category),
    "canonical_target_key": target.canonical_target_key,
    **hints,
}
updates["is_broad_category_request"] = bool(is_broad)

return UserUnderstanding(
    intent=UserIntent.RECOMMEND,
    confidence=0.55,
    purchase_need=positive_purchase_need,
    preference_updates={key: value for key, value in updates.items() if value is not None},
    negative_updates=negative_updates,
)
```

- [ ] **Step 5: 运行 Task 3 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "fallback_understanding_recommends_broad or mixed_broad_request or does_not_recommend_without_target or empty_falls_back or target_with_negative" -v
```

Expected: selected tests passed.

- [ ] **Step 6: 提交 Task 3**

```powershell
git add backend/agent/category_rules.py backend/agent/fallback_understanding.py backend/tests/test_agent.py
git commit -m "feat(agent): add deterministic broad category understanding"
```

---

### Task 4: LLM 理解边界与 prompt 接管

**Files:**
- Modify: `backend/agent/understanding.py`
- Test: `backend/tests/test_agent.py`

- [ ] **Step 1: 写 LLM 边界失败测试**

在 `backend/tests/test_agent.py` 追加：

```python
def test_llm_clarify_for_broad_phone_is_overridden_by_fallback():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    llm = FakeLLM(
        json.dumps(
            {
                "intent": "clarify",
                "confidence": 0.7,
                "purchase_need": None,
                "preference_updates": {},
                "negative_updates": {},
                "target_item_index": None,
                "clarifying_question": "想买什么类型？",
                "reset_context": False,
                "restore_context_category": None,
            },
            ensure_ascii=False,
        )
    )
    service = LLMUserUnderstandingService(llm=llm)

    understanding = service.understand(
        message="推荐手机",
        conversation=ConversationState(session_id="llm-clarify-broad"),
    )

    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == "推荐手机"
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["canonical_target_key"] == "phone"
    assert understanding.preference_updates["is_broad_category_request"] is True
```

```python
def test_llm_recommend_missing_broad_fields_is_completed_by_fallback():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    llm = FakeLLM(
        json.dumps(
            {
                "intent": "recommend",
                "confidence": 0.8,
                "purchase_need": "推荐手机",
                "preference_updates": {},
                "negative_updates": {},
                "target_item_index": None,
                "clarifying_question": None,
                "reset_context": False,
                "restore_context_category": None,
            },
            ensure_ascii=False,
        )
    )
    service = LLMUserUnderstandingService(llm=llm)

    understanding = service.understand(
        message="推荐手机",
        conversation=ConversationState(session_id="llm-missing-broad-fields"),
    )

    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["category"] == "数码电子"
    assert understanding.preference_updates["canonical_target_key"] == "phone"
    assert understanding.preference_updates["is_broad_category_request"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "llm_clarify_for_broad or llm_recommend_missing_broad" -v
```

Expected: recommend 缺字段场景没有被 fallback 补齐，或 prompt 不包含泛品类要求。

- [ ] **Step 3: 增加 LLM fallback overlay 判断**

在 `backend/agent/understanding.py` 增加：

```python
def _has_broad_target_fields(self, understanding: UserUnderstanding) -> bool:
    updates = understanding.preference_updates
    return all(
        isinstance(updates.get(key), str) and updates[key].strip()
        for key in ("target_category", "category", "canonical_target_key")
    ) and isinstance(updates.get("is_broad_category_request"), bool)
```

在 `understand()` 解析 `understanding` 后加入：

```python
fallback = self._fallback_understanding(
    message=message,
    conversation=conversation,
    reason="deterministic_broad_overlay",
)
if (
    fallback is not None
    and fallback.intent == UserIntent.RECOMMEND
    and fallback.preference_updates.get("is_broad_category_request") is True
):
    if understanding.intent == UserIntent.CLARIFY or not self._has_broad_target_fields(understanding):
        return fallback
```

确保这个判断在 `_needs_purchase_need()` 前执行。

- [ ] **Step 4: 更新 system prompt 示例**

在 `_system_prompt()` 中加入泛品类约束，保持 JSON-only：

```python
"Broad category requests such as 推荐手机, 看看护肤品, 有什么咖啡推荐 must return intent=recommend, "
"purchase_need cleaned from negative phrases, preference_updates.target_category, category, canonical_target_key, "
"and is_broad_category_request=true. Do not put negative phrases into purchase_need.\n"
"For 推荐手机，不要苹果, return intent=recommend with target phone fields and negative_updates.excluded_brands.\n"
```

- [ ] **Step 5: 运行 Task 4 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "llm_clarify_for_broad or llm_recommend_missing_broad" -v
```

Expected: selected tests passed.

- [ ] **Step 6: 提交 Task 4**

```powershell
git add backend/agent/understanding.py backend/tests/test_agent.py
git commit -m "feat(agent): override weak llm broad understanding"
```

---

### Task 5: Restore 流程使用 canonical key 与 display target

**Files:**
- Modify: `backend/agent/category_rules.py`
- Modify: `backend/agent/context_manager.py`
- Modify: `backend/agent/graph/runner.py`
- Test: `backend/tests/test_agent.py`

- [ ] **Step 1: 写 restore 失败测试**

在 `backend/tests/test_agent.py` 追加：

```python
def test_detect_restore_target_requires_signal_and_target():
    from agent.category_rules import detect_restore_target

    assert detect_restore_target("还是推荐手机吧").canonical_target_key == "phone"
    assert detect_restore_target("恢复之前的手机").canonical_target_key == "phone"
    assert detect_restore_target("继续看护肤品").canonical_target_key == "skin_care"
    assert detect_restore_target("推荐手机") is None
```

```python
def test_request_restore_uses_canonical_key_and_display_target():
    from agent.context_manager import request_restore
    from agent.memory import ConversationState, PurchaseContext

    state = ConversationState(session_id="restore-canonical")
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="推荐护肤",
            preferences={
                "target_category": "护肤",
                "category": "美妆护肤",
                "canonical_target_key": "skin_care",
            },
            target_category="护肤",
            category="美妆护肤",
            canonical_target_key="skin_care",
            display_target_category="护肤",
        )
    ]

    assert request_restore(state, "skin_care", "护肤品") is True
    assert state.pending_restore_category == "skin_care"
    assert state.pending_restore_display_target == "护肤品"
```

```python
def test_confirm_restore_uses_canonical_key_and_clears_pending_display_target():
    from agent.context_manager import confirm_restore
    from agent.memory import ConversationState, PurchaseContext

    state = ConversationState(session_id="confirm-restore-canonical")
    state.purchase_need = "推荐咖啡"
    state.preferences = {
        "target_category": "咖啡",
        "category": "食品生活",
        "canonical_target_key": "coffee",
    }
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="推荐护肤",
            preferences={
                "target_category": "护肤",
                "category": "美妆护肤",
                "canonical_target_key": "skin_care",
            },
            target_category="护肤",
            category="美妆护肤",
            canonical_target_key="skin_care",
            display_target_category="护肤",
        )
    ]
    state.pending_restore_category = "skin_care"
    state.pending_restore_display_target = "护肤品"

    understanding = confirm_restore(state)

    assert understanding.intent.value == "recommend"
    assert state.preferences["canonical_target_key"] == "skin_care"
    assert state.preferences["is_broad_category_request"] is False
    assert state.pending_restore_category is None
    assert state.pending_restore_display_target is None
```

```python
def test_reject_restore_clears_pending_restore_fields():
    from agent.context_manager import reject_restore
    from agent.memory import ConversationState

    state = ConversationState(session_id="reject-restore-canonical")
    state.pending_restore_category = "skin_care"
    state.pending_restore_display_target = "护肤品"

    reject_restore(state)

    assert state.pending_restore_category is None
    assert state.pending_restore_display_target is None
```

```python
def test_build_restore_rejection_understanding_uses_display_target_not_canonical_key():
    from agent.context_manager import build_restore_rejection_understanding
    from agent.memory import ConversationState

    state = ConversationState(session_id="reject-restore-display")
    state.pending_restore_category = "skin_care"
    state.pending_restore_display_target = "护肤品"

    understanding = build_restore_rejection_understanding(state, "不要了")

    assert understanding.intent.value == "clarify"
    assert "护肤品" in understanding.clarifying_question
    assert "skin_care" not in understanding.clarifying_question
```

```python
def test_build_restore_rejection_understanding_falls_back_with_display_target():
    from agent.context_manager import build_restore_rejection_understanding
    from agent.memory import ConversationState
    from agent.understanding import UserIntent

    state = ConversationState(session_id="reject-restore-phone-budget")
    state.pending_restore_category = "phone"
    state.pending_restore_display_target = "手机"

    understanding = build_restore_rejection_understanding(
        state,
        "不是，预算3000以内就行",
    )

    assert understanding.intent in {UserIntent.RECOMMEND, UserIntent.UPDATE_PREFERENCE}
    assert understanding.intent != UserIntent.CLARIFY
    assert understanding.reset_context is True
    assert understanding.purchase_need == "不是，预算3000以内就行"
    assert state.pending_restore_category == "phone"
    assert state.pending_restore_display_target == "手机"
    assert understanding.preference_updates.get("canonical_target_key") == "phone"
    assert understanding.preference_updates.get("target_category") == "手机"
    assert "phone" not in (understanding.clarifying_question or "")
```

```python
def test_resolve_pending_restore_uses_current_resolution_model_for_confirmation():
    from agent.context_manager import ConversationCommand, resolve_pending_restore
    from agent.memory import ConversationState

    state = ConversationState(session_id="resolve-pending-confirm")
    state.pending_restore_category = "skin_care"
    state.pending_restore_display_target = "护肤品"

    result = resolve_pending_restore(state, "是的")

    assert result.handled is True
    assert result.command == ConversationCommand.CONFIRM_RESTORE
    assert result.clear_pending_before_understanding is False
```

```python
def test_clear_pending_restore_clears_pending_fields_for_direct_runner_path():
    from agent.context_manager import clear_pending_restore
    from agent.memory import ConversationState

    state = ConversationState(session_id="clear-pending")
    state.pending_restore_category = "skin_care"
    state.pending_restore_display_target = "护肤品"

    clear_pending_restore(state)

    assert state.pending_restore_category is None
    assert state.pending_restore_display_target is None
```

```python
def test_confirm_restore_clears_pending_fields_when_archive_missing():
    from agent.context_manager import confirm_restore
    from agent.memory import ConversationState

    state = ConversationState(session_id="resolve-pending-no-match")
    state.pending_restore_category = "skin_care"
    state.pending_restore_display_target = "护肤品"

    understanding = confirm_restore(state)

    assert understanding.intent.value == "clarify"
    assert state.pending_restore_category is None
    assert state.pending_restore_display_target is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "detect_restore_target or request_restore_uses_canonical or confirm_restore_uses_canonical or reject_restore_clears or rejection_understanding or resolve_pending_restore" -v
```

Expected:
- `detect_restore_target` import 失败。
- `request_restore()` 签名仍只接收 target_category。
- pending display 字段未清空，或拒绝恢复文案暴露 `skin_care`。

- [ ] **Step 3: 实现 detect_restore_target**

在 `backend/agent/category_rules.py` 增加：

```python
RESTORE_SIGNAL_TERMS = ("还是", "之前", "恢复", "回到", "继续看")


def detect_restore_target(message: str) -> TargetCategoryMatch | None:
    if not any(term in message for term in RESTORE_SIGNAL_TERMS):
        return None
    return detect_target_category(message)
```

- [ ] **Step 4: 更新 context_manager restore helper**

修改 `find_archived_context()` 签名和实现：

```python
def find_archived_context(
    conversation: ConversationState,
    canonical_key: str,
) -> PurchaseContext | None:
    for item in conversation.previous_purchase_contexts:
        item_key = ensure_archived_target_fields(item)
        if item_key == canonical_key:
            return item
    return None
```

修改 `request_restore()`：

```python
def request_restore(
    conversation: ConversationState,
    canonical_key: str,
    display_target_category: str | None = None,
) -> bool:
    # pending_restore_category 保存 canonical key；display target 只用于用户可见文案，不能把 skin_care 暴露给用户。
    archived = find_archived_context(conversation, canonical_key)
    if archived is None:
        return False
    conversation.pending_restore_category = canonical_key
    conversation.pending_restore_display_target = (
        display_target_category
        or archived.display_target_category
        or archived.target_category
    )
    return True
```

新增统一 pending 清理 helper，并在所有直接清空 pending 的路径调用它：

```python
def clear_pending_restore(conversation: ConversationState) -> None:
    conversation.pending_restore_category = None
    conversation.pending_restore_display_target = None
```

实现 pending 解析、确认、拒绝和拒绝文案。必须保持当前 runner 兼容的模型：`resolve_pending_restore(conversation, message) -> PendingRestoreResolution`，继续使用 `ConversationCommand`、`resolution.handled`、`resolution.clear_pending_before_understanding` 流程；不要改成布尔确认参数 API。注意：`pending_restore_category` 是 canonical key，`pending_restore_display_target` 才能进用户可见文案：

```python
def resolve_pending_restore(
    conversation: ConversationState,
    message: str,
) -> PendingRestoreResolution:
    pending_key = conversation.pending_restore_category
    if pending_key is None:
        return PendingRestoreResolution(handled=False)

    display_target = conversation.pending_restore_display_target or "之前的需求"

    if is_restore_rejection(message):
        return PendingRestoreResolution(
            handled=True,
            command=ConversationCommand.REJECT_RESTORE,
            understanding=build_restore_rejection_understanding(conversation, message),
        )

    if is_restore_confirmation(message):
        return PendingRestoreResolution(
            handled=True,
            command=ConversationCommand.CONFIRM_RESTORE,
        )

    if (
        fallback_understanding(
            message=message,
            conversation=conversation,
            reason="pending_restore_new_complete_request",
        )
        is not None
    ):
        return PendingRestoreResolution(
            handled=False,
            clear_pending_before_understanding=True,
        )

    return PendingRestoreResolution(
        handled=True,
        command=ConversationCommand.REJECT_RESTORE,
        understanding=clarify_understanding(
            f"不恢复{display_target}。可以告诉我新的品类、预算和最在意的点吗？"
        ),
    )


def confirm_restore(conversation: ConversationState) -> UserUnderstanding:
    pending_key = conversation.pending_restore_category
    archived = (
        find_archived_context(conversation, pending_key)
        if pending_key is not None
        else None
    )
    if archived is None:
        clear_pending_restore(conversation)
        return clarify_understanding("没有找到之前的需求，可以重新说一下想买什么吗？")

    archive_active_context(conversation)
    archived.apply_to_conversation(conversation)
    clear_pending_restore(conversation)
    return UserUnderstanding(
        intent=UserIntent.RECOMMEND,
        confidence=0.9,
        purchase_need=conversation.purchase_need,
        preference_updates=conversation.preferences.copy(),
    )


def reject_restore(conversation: ConversationState) -> None:
    clear_pending_restore(conversation)


def build_restore_rejection_understanding(
    conversation: ConversationState,
    message: str,
) -> UserUnderstanding:
    # 只使用 display target 参与 fallback/用户可见文案；不要用 pending_restore_category 这个 canonical key 拼接。
    display_target = conversation.pending_restore_display_target or "之前的需求"
    scratch = ConversationState(session_id="restore-rejection")
    candidates = [message]
    if display_target and display_target not in message:
        candidates.append(f"{display_target}，{message}")

    for candidate in candidates:
        fallback = fallback_understanding(
            message=candidate,
            conversation=scratch,
            reason="restore_rejection",
        )
        if fallback is not None:
            fallback.purchase_need = message
            fallback.reset_context = True
            fallback.confidence = max(fallback.confidence, 0.65)
            return fallback

    return clarify_understanding(
        f"不恢复{display_target}。可以告诉我新的品类、预算和最在意的点吗？"
    )
```

- [ ] **Step 5: 更新 runner restore 检测**

修改 `backend/agent/graph/runner.py` imports：

```python
from agent.category_rules import detect_restore_target
from agent.context_manager import active_target_key, clear_pending_restore, request_restore
```

在 runner 里所有直接清空 pending 的路径都统一替换为 `clear_pending_restore(conversation)`，至少包括：
- 负反馈打断 pending restore 的分支，即 `conversation.pending_restore_category and message_negative_updates`。
- `resolution.clear_pending_before_understanding` 分支。
- `_update_memory()` 里的 confirm/reject 命令路径；`confirm_restore()`、`reject_restore()` 内部也使用 helper。
- confirm 归档缺失路径，即 `confirm_restore()` 找不到归档时。

兼容当前 runner 的 `_understand_user()` 关键控制流如下。先保留 `resolve_pending_restore(conversation, message)`；在 pending restore resolution 完成之后、调用 `self.understanding_service.understand(...)` 之前执行 `detect_restore_target()`。归档命中时直接 `request_restore(...)` 并返回 clarify，不调用 fake/LLM；无归档命中时再继续普通 understanding。这个顺序保证 `test_restore_signal_with_broad_target_does_not_directly_recommend_archived_context()` 使用 `FakeUnderstandingService([])` 时不会先 pop 空列表：

```python
message_negative_updates = extract_negative_updates(message)
if conversation.pending_restore_category and message_negative_updates:
    clear_pending_restore(conversation)

resolution = resolve_pending_restore(conversation, message)
if resolution.handled:
    understanding = resolution.understanding or clarify_understanding("正在恢复之前的需求。")
    return {
        "conversation": conversation,
        "understanding": understanding,
        "pending_restore_command": resolution.command,
    }

if resolution.clear_pending_before_understanding:
    clear_pending_restore(conversation)

restore_target = detect_restore_target(message)
if restore_target is not None:
    active_key = active_target_key(conversation)
    if active_key != restore_target.canonical_target_key and request_restore(
        conversation,
        restore_target.canonical_target_key,
        restore_target.target_category,
    ):
        understanding = UserUnderstanding(
            intent=UserIntent.CLARIFY,
            confidence=0.8,
            clarifying_question=f"要恢复之前的{conversation.pending_restore_display_target or restore_target.target_category}需求吗？",
            restore_context_category=restore_target.target_category,
        )
        return {"conversation": conversation, "understanding": understanding}

understanding = self.understanding_service.understand(
    message=message,
    conversation=conversation,
)
```

保留后续普通 understanding 流程：无归档命中但 target 可识别时不 clarify，继续 recommend/new target。

在 `_update_memory()` 中保持现有 `ConversationCommand` 分支，不要把确认/拒绝折叠到 `_understand_user()`：

```python
if restore_command == ConversationCommand.CONFIRM_RESTORE:
    restored_understanding = confirm_restore(conversation)
    conversation.last_intent = restored_understanding.intent.value
    negative_feedback_result = apply_negative_feedback(
        conversation,
        restored_understanding.negative_updates,
        catalog_products=catalog_products,
    )
    return {
        "conversation": conversation,
        "understanding": restored_understanding,
        "negative_feedback_result": negative_feedback_result,
    }

if restore_command == ConversationCommand.REJECT_RESTORE:
    reject_restore(conversation)
```

- [ ] **Step 6: 运行 Task 5 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "detect_restore_target or request_restore_uses_canonical or confirm_restore_uses_canonical or reject_restore_clears or rejection_understanding or resolve_pending_restore" -v
```

Expected: selected tests passed.

- [ ] **Step 7: 提交 Task 5**

```powershell
git add backend/agent/category_rules.py backend/agent/context_manager.py backend/agent/graph/runner.py backend/tests/test_agent.py
git commit -m "feat(agent): restore archived targets by canonical key"
```

---

### Task 6: Runner reset 前 snapshot 与 item-index 过滤顺序

**Files:**
- Modify: `backend/agent/negative_feedback.py`
- Modify: `backend/agent/graph/runner.py`
- Test: `backend/tests/test_negative_feedback.py`
- Test: `backend/tests/test_agent.py`

- [ ] **Step 1: 写 helper 单元测试**

在 `backend/tests/test_negative_feedback.py` 追加：

```python
def test_filter_item_index_negative_updates_drops_indexes_before_apply_negative_feedback():
    from agent.negative_feedback import filter_item_index_negative_updates_for_current_target
    from schemas.product import ProductCard

    items = [
        ProductCard(
            product_id="p_phone_1",
            title="手机1",
            brand="BrandA",
            price=1000,
            reason="test",
            evidence="test",
        )
    ]

    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_item_indexes": [1]},
        current_target_key="headphones",
        active_target_key="phone",
        active_last_successful_items=items,
    ) == {}
    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_brands": ["苹果"]},
        current_target_key="phone",
        active_target_key="phone",
        active_last_successful_items=items,
    ) == {"excluded_brands": ["苹果"]}
    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_item_indexes": [1]},
        current_target_key="phone",
        active_target_key="phone",
        active_last_successful_items=items,
    ) == {"excluded_item_indexes": [1]}
```

- [ ] **Step 2: 写 runner 集成失败测试**

在 `backend/tests/test_agent.py` 追加：

```python
def test_mixed_broad_item_index_negative_target_switch_ignores_old_items():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    state = store.get_or_create("item-index-target-switch")
    state.purchase_need = "推荐手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
    }
    state.last_successful_items = [
        ProductCard(
            product_id="p_phone_1",
            title="第一款手机",
            brand="BrandA",
            price=1000,
            reason="test",
            evidence="test",
        ),
        ProductCard(
            product_id="p_phone_2",
            title="第二款手机",
            brand="BrandB",
            price=2000,
            reason="test",
            evidence="test",
        ),
    ]
    state.last_items = list(state.last_successful_items)
    store.save(state)
    captured = {}

    def capture_recommendation(query: str, top_k: int = 3, negative_filters=None):
        captured["query"] = query
        captured["negative_filters"] = negative_filters
        return {
            "query": query,
            "filters": {"category": "数码电子", "max_price": None, "brand": None, "keywords": ["耳机"]},
            "items": [
                {
                    "product_id": "p_headphones_1",
                    "title": "测试耳机",
                    "brand": "BrandC",
                    "price": 499,
                    "reason": "test",
                    "evidence": "test",
                }
            ],
        }

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=capture_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="推荐耳机",
                    preference_updates={
                        "target_category": "耳机",
                        "category": "数码电子",
                        "canonical_target_key": "headphones",
                        "is_broad_category_request": True,
                    },
                    negative_updates={"excluded_item_indexes": [2]},
                )
            ]
        ),
    )

    response = runner.run("item-index-target-switch", "推荐耳机，不要第2个")
    saved = store.get_or_create("item-index-target-switch")

    assert "不要第2个" not in captured["query"]
    assert captured["negative_filters"].excluded_product_ids == []
    assert saved.excluded_product_ids == []
    assert response.state["action"] == "recommend"
    assert "negative_feedback" not in response.state or response.state["negative_feedback"].get("needs_clarification") is not True
```

```python
def test_pure_item_index_negative_feedback_keeps_existing_list_semantics():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    state = store.get_or_create("pure-item-index")
    state.purchase_need = "推荐手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
    }
    state.last_successful_items = [
        ProductCard(product_id="p_phone_1", title="第一款手机", brand="A", price=1, reason="r", evidence="e"),
        ProductCard(product_id="p_phone_2", title="第二款手机", brand="B", price=2, reason="r", evidence="e"),
    ]
    state.last_items = list(state.last_successful_items)
    store.save(state)
    captured = {}

    def capture_recommendation(query: str, top_k: int = 3, negative_filters=None):
        captured["negative_filters"] = negative_filters
        return {
            "query": query,
            "filters": {"category": "数码电子", "max_price": None, "brand": None, "keywords": ["手机"]},
            "items": [
                {"product_id": "p_phone_3", "title": "第三款手机", "brand": "C", "price": 3, "reason": "r", "evidence": "e"}
            ],
        }

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=capture_recommendation),
        understanding_service=FakeUnderstandingService(
            [make_understanding(intent=UserIntent.UPDATE_PREFERENCE, negative_updates={"excluded_item_indexes": [2]})]
        ),
    )

    response = runner.run("pure-item-index", "不要第2款")

    assert captured["negative_filters"].excluded_product_ids == ["p_phone_2"]
    assert response.state["excluded_product_ids"] == ["p_phone_2"]
```

```python
def test_reset_context_true_without_canonical_target_still_clears_legacy_state():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    state = store.get_or_create("legacy-reset-without-canonical")
    state.purchase_need = "推荐手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
        "budget": 3000,
    }
    store.save(state)

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.UPDATE_PREFERENCE,
                    purchase_need="推荐手机",
                    preference_updates={"focus": "拍照"},
                    reset_context=True,
                )
            ]
        ),
    )

    runner.run("legacy-reset-without-canonical", "我要看一个新东西")
    saved = store.get_or_create("legacy-reset-without-canonical")

    assert saved.preferences["focus"] == "拍照"
    assert "canonical_target_key" not in saved.preferences
    assert "target_category" not in saved.preferences
    assert "budget" not in saved.preferences
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_negative_feedback.py -k "filter_item_index_negative_updates" -v
uv run pytest tests/test_agent.py -k "mixed_broad_item_index_negative_target_switch or pure_item_index_negative_feedback_keeps or legacy-reset-without-canonical" -v
```

Expected:
- helper import 失败。
- target switch 场景可能把旧手机第 2 个加入排除，或触发 clarification。

- [ ] **Step 4: 实现 item-index filter helper**

在 `backend/agent/negative_feedback.py` 增加：

```python
def filter_item_index_negative_updates_for_current_target(
    negative_updates: dict[str, Any] | None,
    current_target_key: str | None,
    active_target_key: str | None,
    active_last_successful_items: list[ProductCard],
) -> dict[str, Any]:
    if not negative_updates:
        return {}
    filtered = dict(negative_updates)
    if set(filtered) != {"excluded_item_indexes"}:
        return filtered
    # 只有当前理解出的目标和 reset 前 active 目标一致时，第 N 个才指向同一批商品。
    # 目标切换时丢弃 item-index 负反馈，避免把旧手机列表的第 2 款误排除到耳机推荐里。
    if (
        current_target_key
        and active_target_key
        and current_target_key == active_target_key
        and active_last_successful_items
    ):
        return filtered
    filtered.pop("excluded_item_indexes", None)
    return filtered
```

- [ ] **Step 5: 更新 runner `_update_memory()` 顺序**

在 `backend/agent/graph/runner.py` imports 添加：

```python
from agent.context_manager import active_target_key
from agent.negative_feedback import filter_item_index_negative_updates_for_current_target
```

在 `_update_memory()` 开头读取 reset 前 snapshot：

```python
active_key_before = active_target_key(conversation)
active_items_before = list(conversation.last_successful_items)
updates = understanding.preference_updates
current_target_key = updates.get("canonical_target_key")
if not isinstance(current_target_key, str):
    current_target_key = None
if current_target_key is None and set(understanding.negative_updates) == {"excluded_item_indexes"}:
    current_target_key = active_key_before

filtered_negative_updates = filter_item_index_negative_updates_for_current_target(
    understanding.negative_updates,
    current_target_key,
    active_key_before,
    active_items_before,
)
```

计算 effective reset，替换 `if understanding.reset_context:`。兼容旧 `reset_context=True`，但只有当前没有 active target 时才让旧字段触发 reset：

```python
canonical_target_changed = (
    current_target_key is not None
    and active_key_before is not None
    and current_target_key != active_key_before
)
effective_reset = canonical_target_changed or (
    understanding.reset_context and current_target_key is None
)
# reset_context 是旧理解层字段；没有 canonical target 的旧结果仍可触发 reset。
# 一旦有 canonical target，就只按 canonical_target_changed 判断，避免同品类细化误清空状态。
if effective_reset:
    reset_for_new_target(conversation)
```

后续调用：

```python
negative_feedback_result = apply_negative_feedback(
    conversation,
    filtered_negative_updates,
    catalog_products=catalog_products,
)
```

- [ ] **Step 6: 运行 Task 6 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_negative_feedback.py -k "filter_item_index_negative_updates" -v
uv run pytest tests/test_agent.py -k "mixed_broad_item_index_negative_target_switch or pure_item_index_negative_feedback_keeps or legacy-reset-without-canonical" -v
```

Expected: selected tests passed.

- [ ] **Step 7: 提交 Task 6**

```powershell
git add backend/agent/negative_feedback.py backend/agent/graph/runner.py backend/tests/test_negative_feedback.py backend/tests/test_agent.py
git commit -m "feat(agent): guard item-index feedback across target switches"
```

---

### Task 7: Broad 回复与 stale broad 标记清理

**Files:**
- Modify: `backend/agent/graph/runner.py`
- Test: `backend/tests/test_agent.py`

- [ ] **Step 1: 写 broad 回复和细化清理失败测试**

在 `backend/tests/test_agent.py` 追加：

```python
def test_langgraph_runner_broad_category_reply_uses_broad_copy():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="推荐手机",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                        "canonical_target_key": "phone",
                        "is_broad_category_request": True,
                    },
                )
            ]
        ),
    )

    response = runner.run("broad-reply", "推荐手机")

    assert "手机" in response.reply
    assert response.state["preferences"]["is_broad_category_request"] is True
```

```python
def test_langgraph_runner_refinement_clears_stale_broad_flag():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="推荐手机",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                        "canonical_target_key": "phone",
                        "is_broad_category_request": True,
                    },
                ),
                make_understanding(
                    intent=UserIntent.UPDATE_PREFERENCE,
                    purchase_need="推荐手机",
                    preference_updates={"budget": 3000},
                ),
            ]
        ),
    )

    runner.run("stale-broad", "推荐手机")
    second = runner.run("stale-broad", "3000以内")

    assert second.state["preferences"]["is_broad_category_request"] is False
    assert "我先按" not in second.reply
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "broad_category_reply or refinement_clears_stale_broad" -v
```

Expected:
- 回复仍是普通推荐文案，或第二轮 stale broad 未清理。

- [ ] **Step 3: runner 合并前写入本轮 broad 标记**

在 `_update_memory()` merge preferences 前计算：

```python
current_turn_is_broad = (
    understanding.intent == UserIntent.RECOMMEND
    and understanding.preference_updates.get("is_broad_category_request") is True
)
# broad 是“本轮是否泛品类推荐”的瞬时语义；细化预算/品牌时必须写回 False，避免复用上一轮 broad 文案。
if understanding.intent in {UserIntent.RECOMMEND, UserIntent.UPDATE_PREFERENCE}:
    understanding.preference_updates["is_broad_category_request"] = current_turn_is_broad
```

在 state dict 返回中带上：

```python
"current_turn_is_broad": current_turn_is_broad
```

并将 `ShoppingAgentState` 类型加字段：

```python
current_turn_is_broad: bool
```

- [ ] **Step 4: 生成 broad 文案**

在 `_generate_reply()` 的 recommendation reply 分支里：

```python
if (
    action_result.reply_type == "recommendation_reply"
    and state.get("current_turn_is_broad") is True
):
    target = state["conversation"].preferences.get("target_category") or "这个品类"
    return {
        "reply": f"我先按{target}这个品类给你挑几款代表商品，你可以再告诉我预算、品牌或使用场景。",
        "items": action_result.items,
    }
```

保留负反馈 ack 文案优先级：如果 `negative_feedback.ack_message` 存在，仍先输出 ack。

- [ ] **Step 5: 运行 Task 7 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "broad_category_reply or refinement_clears_stale_broad" -v
```

Expected: selected tests passed.

- [ ] **Step 6: 提交 Task 7**

```powershell
git add backend/agent/graph/runner.py backend/tests/test_agent.py
git commit -m "feat(agent): use broad reply only for current broad turns"
```

---

### Task 8: 新目标切换、归档恢复与 API/SSE 契约

**Files:**
- Modify: `backend/agent/graph/runner.py`
- Modify: `backend/agent/context_manager.py`
- Test: `backend/tests/test_agent.py`
- Test: `backend/tests/test_main.py`
- Test: `backend/tests/test_sse.py`

- [ ] **Step 1: 写 runner 新目标切换测试**

在 `backend/tests/test_agent.py` 追加：

```python
def test_canonical_target_key_resets_for_phone_to_headphones():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="推荐手机",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                        "canonical_target_key": "phone",
                        "is_broad_category_request": True,
                    },
                ),
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="推荐耳机",
                    preference_updates={
                        "target_category": "耳机",
                        "category": "数码电子",
                        "canonical_target_key": "headphones",
                        "is_broad_category_request": True,
                    },
                ),
            ]
        ),
    )

    runner.run("phone-to-headphones", "推荐手机")
    runner.run("phone-to-headphones", "推荐耳机")
    saved = store.get_or_create("phone-to-headphones")

    assert saved.preferences["canonical_target_key"] == "headphones"
    assert any(ctx.canonical_target_key == "phone" for ctx in saved.previous_purchase_contexts)
```

```python
def test_canonical_target_key_alias_does_not_reset_for_skin_care():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="推荐护肤",
                    preference_updates={
                        "target_category": "护肤",
                        "category": "美妆护肤",
                        "canonical_target_key": "skin_care",
                        "is_broad_category_request": True,
                    },
                ),
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="推荐护肤品",
                    preference_updates={
                        "target_category": "护肤品",
                        "category": "美妆护肤",
                        "canonical_target_key": "skin_care",
                        "is_broad_category_request": True,
                    },
                ),
            ]
        ),
    )

    runner.run("skin-care-alias", "推荐护肤")
    runner.run("skin-care-alias", "推荐护肤品")
    saved = store.get_or_create("skin-care-alias")

    assert saved.preferences["canonical_target_key"] == "skin_care"
    assert saved.previous_purchase_contexts == []
```

- [ ] **Step 2: 修改现有 restore runner 测试，并补齐有归档/无归档场景**

先定位 `backend/tests/test_agent.py` 里当前 restore runner 相关测试区域（通常在 runner 切换目标、恢复旧需求、`FakeUnderstandingService`/`service.calls` 断言附近），优先修改现有测试断言；只有缺少覆盖时才在同一区域追加下面测试。因为 deterministic `detect_restore_target()` 会放在 `understanding_service.understand(...)` 之前，归档命中 restore signal 的语义会变成不调用 fake/LLM 直接返回 clarify，必须同步更新旧断言以免全量 pytest 失败：

- 归档命中 restore signal 场景不再断言 fake/LLM 被调用；如果现有测试检查 `service.calls` 或 fake understanding 调用次数，应改为断言没有调用，或删除该旧断言。
- `pending_restore_category` 断言 canonical key，例如 `"phone"`，不要断言中文 `"手机"`。
- 用户可见文案断言使用 `pending_restore_display_target` 或回复文本中的 display target，例如 `"手机"`；不要把 canonical key（如 `"phone"`）暴露给用户。
- 现有测试里构造归档 `PurchaseContext` 时，如果不是专门验证 legacy 迁移，必须补上 `canonical_target_key` 与 `display_target_category`；专门验证旧归档的测试则要明确依赖 `ensure_archived_target_fields()`/legacy helper 从 `target_category/category` 派生。

在 `backend/tests/test_agent.py` 同一区域修改或追加：

```python
def test_restore_signal_with_broad_target_does_not_directly_recommend_archived_context():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.memory import PurchaseContext

    store = InMemoryConversationStore()
    state = store.get_or_create("restore-with-archive")
    state.purchase_need = "推荐咖啡"
    state.preferences = {
        "target_category": "咖啡",
        "category": "食品生活",
        "canonical_target_key": "coffee",
    }
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="推荐手机",
            preferences={
                "target_category": "手机",
                "category": "数码电子",
                "canonical_target_key": "phone",
            },
            target_category="手机",
            category="数码电子",
            canonical_target_key="phone",
            display_target_category="手机",
        )
    ]
    store.save(state)

    def fail_recommendation(query: str, top_k: int = 3, negative_filters=None):
        raise AssertionError("restore confirmation should not call recommendation")

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=fail_recommendation),
        understanding_service=FakeUnderstandingService([]),
    )

    response = runner.run("restore-with-archive", "还是推荐手机吧")
    saved = store.get_or_create("restore-with-archive")

    assert response.state["action"] == "clarify"
    assert saved.pending_restore_category == "phone"
    assert saved.pending_restore_display_target == "手机"
    assert "手机" in response.reply
    assert "phone" not in response.reply
```

```python
def test_restore_signal_without_archive_but_recognizable_target_recommends():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    state = store.get_or_create("restore-without-archive")
    state.purchase_need = "推荐咖啡"
    state.preferences = {
        "target_category": "咖啡",
        "category": "食品生活",
        "canonical_target_key": "coffee",
    }
    store.save(state)

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="推荐手机",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                        "canonical_target_key": "phone",
                        "is_broad_category_request": True,
                    },
                )
            ]
        ),
    )

    response = runner.run("restore-without-archive", "还是推荐手机吧")

    assert response.state["action"] == "recommend"
    assert response.state["preferences"]["canonical_target_key"] == "phone"
    assert store.get_or_create("restore-without-archive").pending_restore_category is None
```

```python
def test_restore_signal_uses_active_target_key_for_legacy_state_without_canonical_key():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.memory import PurchaseContext
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    state = store.get_or_create("restore-legacy-active")
    state.purchase_need = "推荐手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
    }
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="推荐手机",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
            display_target_category="手机",
        )
    ]
    store.save(state)

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.UPDATE_PREFERENCE,
                    purchase_need="推荐手机",
                    preference_updates={"budget": 3000},
                )
            ]
        ),
    )

    response = runner.run("restore-legacy-active", "还是推荐手机吧")
    saved = store.get_or_create("restore-legacy-active")

    assert response.state["action"] == "recommend"
    assert saved.pending_restore_category is None
    assert saved.preferences["canonical_target_key"] == "phone"
```

- [ ] **Step 3: 写 API/SSE 状态测试**

在 `backend/tests/test_main.py` 追加：

```python
def test_chat_response_exposes_canonical_target_key(monkeypatch):
    inject_recommend_chat_runner(
        monkeypatch,
        understanding_service=FakeUnderstandingService(
            UserUnderstanding(
                intent=UserIntent.RECOMMEND,
                confidence=0.9,
                purchase_need="推荐手机",
                preference_updates={
                    "target_category": "手机",
                    "category": "数码电子",
                    "canonical_target_key": "phone",
                    "is_broad_category_request": True,
                },
            )
        ),
    )

    response = client.post(
        "/chat",
        json={"session_id": "api-canonical", "message": "推荐手机"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"]["preferences"]["canonical_target_key"] == "phone"
    assert body["state"]["preferences"]["is_broad_category_request"] is True
```

在 `backend/tests/test_sse.py` 追加；如果文件已有同名 `client`、`FakeUnderstandingService` 或 `inject_recommend_chat_runner`，复用已有夹具并保留下面测试体的显式 fake understanding 注入：

```python
from fastapi.testclient import TestClient

import api.deps as api_deps
from agent.graph.runner import LangGraphAgentRunner
from agent.memory import InMemoryConversationStore
from agent.tools import RecommendationTool
from agent.understanding import UserIntent, UserUnderstanding
from main import app


client = TestClient(app)


class FakeUnderstandingService:
    def __init__(self, understanding: UserUnderstanding):
        self.understanding = understanding

    def understand(self, *, message, conversation):
        return self.understanding


def _single_recommendation(query: str, top_k: int = 3, negative_filters=None):
    return {
        "query": query,
        "filters": {"category": "数码电子", "max_price": None, "brand": None, "keywords": ["手机"]},
        "items": [
            {
                "product_id": "p_phone_1",
                "title": "测试手机",
                "brand": "测试品牌",
                "price": 1999,
                "reason": "test",
                "evidence": "test",
            }
        ],
    }


def inject_recommend_chat_runner(monkeypatch, understanding_service):
    runner = LangGraphAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(recommend_func=_single_recommendation),
        understanding_service=understanding_service,
    )
    monkeypatch.setattr(api_deps, "agent_runner", runner)


def test_chat_stream_exposes_canonical_target_key(monkeypatch):
    inject_recommend_chat_runner(
        monkeypatch,
        understanding_service=FakeUnderstandingService(
            UserUnderstanding(
                intent=UserIntent.RECOMMEND,
                confidence=0.9,
                purchase_need="推荐手机",
                preference_updates={
                    "target_category": "手机",
                    "category": "数码电子",
                    "canonical_target_key": "phone",
                    "is_broad_category_request": True,
                },
            )
        ),
    )

    with client.stream(
        "POST",
        "/chat/stream",
        json={"session_id": "sse-canonical", "message": "推荐手机"},
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert '"canonical_target_key": "phone"' in body
    assert '"is_broad_category_request": true' in body
```

- [ ] **Step 4: 运行测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "canonical_target_key_resets or alias_does_not_reset or restore_signal_with_broad or restore_signal_without_archive or restore_signal_uses_active_target_key" -v
uv run pytest tests/test_main.py -k "canonical_target_key" -v
uv run pytest tests/test_sse.py -k "canonical_target_key" -v
```

Expected:
- reset 仍按旧 `reset_context` 字段或 catalog category。
- restore 无归档场景可能 clarify。
- API/SSE state 可能缺少 canonical key。

- [ ] **Step 5: 修正 runner 与 state 输出**

在当前 `LangGraphAgentRunner._finalize_response(self, state: ShoppingAgentState) -> dict[str, ChatResponse]` 中增量修改已有 `response_state`：保留 `ChatResponse` 返回结构、现有 `preferences` 暴露方式，以及已有 `negative_feedback`、`result_status`、`tool_error`、`relax_options` 逻辑；只在 `response_state` 构建后加入 pending restore 字段。不要替换函数签名，不要引入旧版响应对象或额外参数。

```python
def _finalize_response(self, state: ShoppingAgentState) -> dict[str, ChatResponse]:
    conversation = state["conversation"]
    understanding = state["understanding"]
    action = state["action"]
    action_result = state["action_result"]

    conversation.messages.append(ChatMessage(role="assistant", content=state["reply"]))
    self.store.save(conversation)

    response_state: dict[str, Any] = {
        "intent": understanding.intent.value,
        "action": action.value,
        "confidence": understanding.confidence,
        "purchase_need": conversation.purchase_need,
        "preferences": conversation.preferences.copy(),
        "excluded_product_ids": list(conversation.excluded_product_ids),
        "excluded_brands": list(conversation.excluded_brands),
        "latest_attempt_status": conversation.latest_attempt_status,
    }
    if conversation.pending_restore_category:
        response_state["pending_restore_category"] = conversation.pending_restore_category
    if conversation.pending_restore_display_target:
        response_state["pending_restore_display_target"] = conversation.pending_restore_display_target

    negative_feedback = action_result.negative_feedback or state.get(
        "negative_feedback_result"
    )
    if negative_feedback and negative_feedback.detected:
        response_state["negative_feedback"] = negative_feedback.model_dump()
    if action_result.action == AgentAction.RECOMMEND and conversation.last_result_status:
        response_state["result_status"] = conversation.last_result_status
    if action_result.tool_error:
        response_state["tool_error"] = action_result.tool_error
    if action_result.no_results:
        response_state["relax_options"] = action_result.no_results.relax_options

    return {
        "response": ChatResponse(
            session_id=state["session_id"],
            reply=state["reply"],
            items=state["items"],
            state=response_state,
        )
    }
```

在 `_understand_user()` restore 分支保留下面的控制流，位置必须在 pending restore resolution 之后、`self.understanding_service.understand(...)` 之前。确保旧状态通过 `active_target_key(conversation)` 推导当前目标；归档命中时直接 `request_restore(...)` 并返回 clarify，不调用 fake/LLM；无归档命中时不提前返回 clarify，而是继续普通 understanding：

```python
restore_target = detect_restore_target(message)
if restore_target is not None:
    active_key = active_target_key(conversation)
    if active_key != restore_target.canonical_target_key and request_restore(
        conversation,
        restore_target.canonical_target_key,
        restore_target.target_category,
    ):
        understanding = UserUnderstanding(
            intent=UserIntent.CLARIFY,
            confidence=0.8,
            clarifying_question=f"要恢复之前的{conversation.pending_restore_display_target or restore_target.target_category}需求吗？",
            restore_context_category=restore_target.target_category,
        )
        return {"conversation": conversation, "understanding": understanding}

understanding = self.understanding_service.understand(
    message=message,
    conversation=conversation,
)
```

- [ ] **Step 6: 运行 Task 8 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_agent.py -k "canonical_target_key_resets or alias_does_not_reset or restore_signal_with_broad or restore_signal_without_archive or restore_signal_uses_active_target_key" -v
uv run pytest tests/test_main.py -k "canonical_target_key" -v
uv run pytest tests/test_sse.py -k "canonical_target_key" -v
```

Expected: selected tests passed.

- [ ] **Step 7: 提交 Task 8**

```powershell
git add backend/agent/graph/runner.py backend/agent/context_manager.py backend/tests/test_agent.py backend/tests/test_main.py backend/tests/test_sse.py
git commit -m "feat(agent): expose broad category state through chat APIs"
```

---

### Task 9: 推荐链路与手工回归场景

**Files:**
- Modify: `backend/recommendation_core/filters.py`
- Modify: `backend/README.md`
- Test: `backend/tests/test_recommendation.py`
- Test: `backend/tests/test_agent.py`
- Test: `backend/tests/test_main.py`
- Test: `backend/tests/test_sse.py`
- Test: `backend/tests/test_negative_feedback.py`

- [ ] **Step 1: 写推荐 filters 品类映射失败测试**

在 `backend/tests/test_recommendation.py` 追加：

```python
def test_extract_filters_maps_skin_care_terms_to_beauty_category():
    from recommendation_core.filters import extract_filters

    for query in ("推荐护肤品", "推荐美妆", "推荐化妆品"):
        filters = extract_filters(query)
        assert filters["category"] == "美妆护肤"
```

- [ ] **Step 2: 运行推荐 filters 测试确认失败**

Run:

```powershell
cd backend
uv run pytest tests/test_recommendation.py -k "maps_skin_care_terms" -v
```

Expected:
- `extract_filters("推荐护肤品")`、`推荐美妆` 或 `推荐化妆品` 未映射到 `美妆护肤`。

- [ ] **Step 3: 实现推荐 filters 映射**

修改 `backend/recommendation_core/filters.py` 中品类关键词映射，保持现有 filters 结构，不新增架构层：

```python
from collections.abc import Sequence


CATEGORY_KEYWORDS: dict[str, Sequence[str]] = {
    "数码电子": ("手机", "耳机", "电脑", "笔记本", "平板"),
    "美妆护肤": ("护肤产品", "护肤品", "化妆品", "美妆", "护肤", "防晒", "面霜"),
    "服饰运动": ("T恤", "外套", "运动", "服饰"),
    "食品生活": ("咖啡", "饮品", "食品"),
}


def _detect_category(query: str) -> str | None:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return category
    return None
```

在 `extract_filters()` 里使用 `_detect_category(query)` 填充 `category` 字段；如果文件已有同名逻辑，只替换品类关键词判断，不改价格、品牌、keywords 的职责。必须保留现有 keywords 收集逻辑，不要为了修 category 只返回或只设置 `category`。

- [ ] **Step 4: 运行推荐 filters 测试确认通过**

Run:

```powershell
cd backend
uv run pytest tests/test_recommendation.py -k "maps_skin_care_terms" -v
```

Expected: selected tests passed.

- [ ] **Step 5: 更新 README 行为说明**

在 `backend/README.md` 的 Agent/Chat 说明段落加入：

```markdown
### 泛品类推荐与多轮状态

`/chat` 和 `/chat/stream` 支持“推荐手机”“推荐护肤品”这类泛品类请求。Agent 会写入 `state.preferences.target_category`、`category`、`canonical_target_key` 和本轮 `is_broad_category_request`，并先返回代表性推荐；用户后续补充预算、品牌、用途时会清除 stale broad 标记。

负反馈只作为结构化过滤条件进入状态，例如“推荐手机，不要苹果”会保留 `excluded_brands=["苹果"]`，但 query 不会包含“不要苹果”。“推荐手机，不要第2个，不要苹果”在 MVP 下只应用 item-index 单字段负反馈，query 仍会移除全部负向短语。

目标切换使用 `canonical_target_key` 判断。`手机` 与 `耳机` 都属于 `数码电子`，但会被视为不同购买目标；`护肤` 与 `护肤品` 会归为同一个 `skin_care` 目标。恢复旧目标时，`pending_restore_category` 保存 canonical key，`pending_restore_display_target` 只用于展示文案。

推荐链路的 `extract_filters()` 会把“护肤品”“美妆”“化妆品”统一映射到 catalog category `美妆护肤`，因此理解层、query_builder 和向量检索过滤条件使用同一类目语义。
```

- [ ] **Step 6: 跑核心回归测试**

Run:

```powershell
cd backend
uv run pytest tests/test_negative_feedback.py tests/test_agent.py tests/test_main.py tests/test_sse.py tests/test_recommendation.py -v
```

Expected: all selected files passed.

- [ ] **Step 7: 跑 lint**

Run:

```powershell
cd backend
uv run ruff check .
```

Expected: no errors.

- [ ] **Step 8: 手工对话验证**

Run:

```powershell
cd backend
uv run python tests/manual_chat_cli.py
```

手工输入并观察：

```text
推荐手机
3000以内
推荐耳机，不要第2个
还是推荐手机吧
是的
推荐手机，不要第2个，不要苹果
```

Expected:
- `推荐手机` 返回推荐，不澄清。
- `3000以内` 清理 stale broad 文案，继续手机推荐。
- `推荐耳机，不要第2个` 不把旧手机第二款加入排除。
- `还是推荐手机吧` 命中归档时先问是否恢复。
- 确认恢复后 active state 的 `is_broad_category_request` 为 `False`。
- `推荐手机，不要第2个，不要苹果` 的 query 不含两个负向短语。

- [ ] **Step 9: 提交 Task 9**

```powershell
git add backend/recommendation_core/filters.py backend/README.md backend/tests/test_recommendation.py backend/tests/test_agent.py backend/tests/test_main.py backend/tests/test_sse.py backend/tests/test_negative_feedback.py
git commit -m "test(agent): cover broad category recommendation flows"
```

---

## 最终验收

- [ ] **Step 1: 跑完整 backend 测试**

Run:

```powershell
cd backend
uv run pytest -v
```

Expected: all tests passed.

- [ ] **Step 2: 跑 lint**

Run:

```powershell
cd backend
uv run ruff check .
```

Expected: no errors.

- [ ] **Step 3: 检查目标文档与计划没有未决措辞**

Run:

```powershell
$paths = @(
  "docs/superpowers/specs/2026-05-29-shopping-agent-broad-category-recommendation-design.md",
  "docs/superpowers/plans/2026-05-29-shopping-agent-broad-category-recommendation-implementation.md"
)
$patterns = @(
  "TB" + "D",
  "TO" + "DO",
  "可" + "选",
  "可" + "选择",
  "或" + "原有",
  "restore" + " or " + "clarify",
  "understanding" + ".reset_context=True",
  "服饰" + "鞋包"
)
foreach ($path in $paths) {
  foreach ($pattern in $patterns) {
    rg -n --fixed-strings $pattern $path
  }
}
```

Expected: no output.

- [ ] **Step 4: 检查工作树范围**

Run:

```powershell
git status --short
```

Expected:
- 实现提交前只出现本计划涉及的 backend files、`backend/README.md`、测试文件和本计划文件。
- 不把 `rag/.chroma/` 数据目录这类无关数据文件加入提交。

- [ ] **Step 5: 最终提交**

```powershell
git add docs/superpowers/plans/2026-05-29-shopping-agent-broad-category-recommendation-implementation.md
git commit -m "docs: plan broad category recommendation implementation"
```

---

## 自检清单

- [ ] 泛品类请求 `推荐手机`、`推荐护肤品` 命中 recommend，不澄清。
- [ ] 无 target 的 `推荐一下`、`随便看看` 仍澄清。
- [ ] `推荐手机，不要苹果` 保留单字段 brand 负反馈，query 不含负向短语。
- [ ] `推荐手机，不要第2个，不要苹果` 只应用 item-index 单字段负反馈，query 同时移除两个负向短语。
- [ ] `不要第2款` 在 active list 存在时继续排除上一轮第二款商品。
- [ ] target switch 场景不使用旧列表 item-index。
- [ ] `手机` 与 `耳机` canonical key 不同，即使 catalog category 相同也会 reset/archive。
- [ ] `护肤`、`护肤品`、`护肤产品` canonical key 相同，不重复归档。
- [ ] `T恤`、`外套` 的 catalog category 是 `服饰运动`。
- [ ] `pending_restore_category` 保存 canonical key，`pending_restore_display_target` 只用于文案。
- [ ] `confirm_restore()` 恢复后清空两个 pending 字段，并清除 broad 标记。
- [ ] `/chat` 与 `/chat/stream` state 暴露 `preferences.canonical_target_key`。
