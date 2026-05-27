# Shopping Agent v1 Design

## Goal

Upgrade the backend chat flow from rule-based keyword intent detection to an LLM-driven shopping agent that understands user intent in context.

The v1 agent should:

- Understand first-turn shopping needs.
- Understand follow-up messages using conversation context.
- Maintain structured shopping memory.
- Recommend products through the existing recommendation tool.
- Explain products from the previous recommendation result.
- Ask clarifying questions when the user need is incomplete.
- Handle no-results recommendations honestly without fabricating products.
- Keep the external `/chat` and `/chat/stream` response contracts stable.

## Migration Policy

The implementation should not preserve the old internal rule-based chain.

Stable external contracts:

- Keep `/chat` request and response shape stable.
- Keep `/chat/stream` event shape stable.
- Keep recommendation product cards sourced from the recommendation tool.

Internal behavior to remove rather than support:

- Remove `AgentPolicy` from the active backend path.
- Remove keyword intent detection from `LangGraphAgentRunner`.
- Remove policy injection from `create_agent_runner` and runner constructors.
- Remove tests that assert keyword-policy behavior as product behavior.
- Do not add a compatibility adapter that maps old policy decisions into the new agent.

LLM failure may still return a conservative `clarify` response. That is an availability fallback, not compatibility with the old rule system.

Current code references that must be removed during implementation:

- `backend/agent/runner.py` imports `AgentPolicy`, accepts `policy`, creates `shared_policy`, and passes it into `LangGraphAgentRunner`.
- `backend/agent/graph/runner.py` imports `AgentDecision`, `AgentIntent`, and `AgentPolicy`; stores `self.policy`; and calls `self.policy.detect_intent`.
- `backend/agent/__init__.py` exports `AgentIntent` and `AgentPolicy`.
- `backend/tests/test_agent.py` imports and directly tests `AgentPolicy`; those tests should be replaced with understanding-driven tests.

## Current Problem

The current implementation uses `AgentPolicy.detect_intent(message)` as the first decision point. It only inspects the latest user message and relies on keyword lists.

This makes common shopping-agent follow-ups fragile:

- "这个太贵了"
- "第二个为什么适合我"
- "不要苹果"
- "有没有轻一点的"
- "换个适合通勤的"
- "还有别的吗"

These messages need conversation history, saved preferences, and previous recommendation results to be interpreted correctly.

## Architecture

The v1 agent should keep LangGraph as the orchestration layer, but move intent and need understanding into a dedicated LLM-based understanding step.

```text
/chat
  -> LangGraph ShoppingAgent
  -> understand_user
  -> update_memory
  -> decide_next_action
  -> execute_action
  -> generate_reply
  -> finalize_response
```

## Internal Contracts

### UserUnderstanding

The LLM understanding layer should return one validated JSON object. The object is parsed and validated before the graph uses it.

```json
{
  "intent": "recommend",
  "confidence": 0.9,
  "purchase_need": "9000以内、拍照好的手机",
  "preference_updates": {
    "category": "手机",
    "budget": "9000以内",
    "focus": ["拍照"],
    "usage": ["日常"],
    "preferred_brands": [],
    "excluded_brands": [],
    "price_preference": null
  },
  "target_item_index": null,
  "clarifying_question": null
}
```

Field rules:

- `intent` must be one of `recommend`, `update_preference`, `explain`, or `clarify`.
- `confidence` must be between `0` and `1`.
- `purchase_need` should contain the complete current shopping need for recommendation retrieval. For `recommend` and `update_preference`, it is required unless memory already has a usable `purchase_need`.
- `preference_updates` is a partial update. Missing keys mean "no change".
- `target_item_index` is 1-based because users refer to "第一个/第二个". The runner converts it to 0-based only when reading `last_items`.
- `clarifying_question` is used when the intent is `clarify` or when required recommendation fields are missing.

If the LLM returns invalid JSON, an unknown intent, an out-of-range confidence, or an unusable shape, the understanding service must return a conservative `clarify` object.

### ActionResult

The execution layer should produce a small action result for `generate_reply`.

```json
{
  "action": "recommend",
  "reply_type": "recommendation_reply",
  "recommendation_query": "9000以内、拍照好的手机",
  "items": [],
  "no_results": null,
  "target_item_index": null
}
```

Supported actions:

- `recommend`
- `explain`
- `clarify`

Supported reply types:

- `recommendation_reply`
- `explain_reply`
- `clarify_reply`
- `no_results_reply`

Recommendation tool exceptions are not no-results. No-results only means the recommendation tool completed successfully and returned an empty `items` list.

### Recommendation Query Boundary

The current `RecommendationTool.run(query, top_k=3)` accepts one natural-language query and returns a `RecommendResponse`.

`RecommendFilters` currently contains only:

- `category`
- `max_price`
- `brand`
- `keywords`

Therefore v1 should keep passing a natural-language `purchase_need` into the recommendation tool. Structured preferences such as `excluded_brands`, `usage`, `focus`, and `price_preference` should be stored in agent memory and folded into `purchase_need` text for retrieval. The v1 implementation should not require the recommendation pipeline to accept a new structured filter object.

If a preference cannot be enforced by the existing recommendation pipeline, the agent may still include it in `purchase_need` and memory, but it should not claim that the filter was strictly applied unless the returned filters or items prove it.

### Node Responsibilities

#### understand_user

Input:

- Latest user message.
- Recent conversation messages.
- Structured shopping memory.
- Previous recommendation items.

Output: a structured `UserUnderstanding` object.

Supported intent values:

- `recommend`
- `update_preference`
- `explain`
- `clarify`

Example:

```json
{
  "intent": "update_preference",
  "confidence": 0.88,
  "purchase_need": "9000以内、拍照好、价格更低的手机",
  "preference_updates": {
    "price_preference": "lower",
    "focus": ["拍照"]
  },
  "target_item_index": null,
  "clarifying_question": null
}
```

The LLM must return structured data only. If the LLM is unavailable or the response cannot be parsed, the system should return a conservative `clarify` understanding instead of falling back to keyword rules.

The prompt should explicitly forbid Markdown fences, explanations, and product fabrication. The parser should use a JSON parser plus Pydantic validation rather than string matching.

#### update_memory

Merge the structured understanding into the session state.

The memory should track:

- `purchase_need`
- `preferences`
- `excluded_brands`
- `target_item_index`
- `last_query`
- `last_filters`
- `last_items`
- `last_result_status`
- `last_no_results_need`
- `last_no_results_relax_options`
- `last_intent`
- `messages`

The existing `ConversationState` can be extended rather than replaced.

Memory merge rules:

- Latest scalar values win, such as `category`, `budget`, and `price_preference`.
- List values are merged and de-duplicated while preserving order, such as `focus`, `usage`, `preferred_brands`, and `excluded_brands`.
- `excluded_brands` should be kept both in `preferences` and as a top-level convenience field if implementation chooses to add one.
- A successful non-empty recommendation updates `last_items`.
- A no-results recommendation must not overwrite `last_items`; `last_items` should continue to mean the last successful recommendation list.
- No-results metadata is stored in `last_result_status`, `last_no_results_need`, and `last_no_results_relax_options`.
- `last_query` should record the query sent to the recommendation tool, even when the result is empty.

#### decide_next_action

Map the structured understanding to one of the supported actions:

- `recommend`
- `explain`
- `clarify`

`update_preference` is an understanding intent, not a separate execution action. After `update_memory` merges the preference change, the next action should usually be `recommend`. This keeps action execution simple: a preference update changes memory, then recommendation uses the revised memory.

This node should not re-run keyword rules. It should use the LLM understanding and the current memory.

#### execute_action

Execute the selected action:

- `recommend`: call the recommendation tool using the current `purchase_need`.
- `explain`: explain a target item from `last_items`.
- `clarify`: prepare a clarifying question without calling the recommendation tool.

Product cards must only come from the recommendation tool or previous saved recommendation results.

For `explain`, if `target_item_index` is missing, default to the first item. If the index is out of range or there is no `last_items`, return a clarify-style reply asking the user which product they want to discuss or asking for an initial shopping need.

#### generate_reply

Generate the user-facing reply from the action result.

Reply types:

- `recommendation_reply`
- `explain_reply`
- `clarify_reply`
- `no_results_reply`

For v1, recommendation and clarify replies may use deterministic templates. The LLM may be used to make replies more natural, but it must not invent products.

#### finalize_response

Append the assistant message, save the conversation state, and return the existing `ChatResponse` shape:

```json
{
  "session_id": "...",
  "reply": "...",
  "items": [],
  "state": {}
}
```

`state` should remain compact. It may include `intent`, `action`, `confidence`, `purchase_need`, `preferences`, and `result_status`, but should not include full message history or duplicate product cards.

## No-Results Strategy

No-results is a normal agent branch, not an exception.

Trigger:

```text
understanding intent is recommend or update_preference
and selected action is recommend
and recommendation_tool returns items = []
```

Flow:

```text
execute_recommendation
  -> items empty?
  -> yes: generate_no_results_reply
  -> no: generate_recommendation_reply
```

Reply principles:

- Do not fabricate products.
- Do not pretend the recommendation succeeded.
- Clearly say no exact match was found.
- Restate the current key shopping need.
- Identify likely blocking constraints.
- Offer 2-3 practical relaxation options.
- Invite the user to choose how to adjust.

Example:

```text
我暂时没有找到同时满足“3000以内、折叠屏、拍照强”的商品。
主要限制可能是预算和折叠屏这两个条件同时存在。你可以选择提高预算、
取消折叠屏限制，或者保留 3000 预算但改看直板拍照手机。
```

Internal action result example:

```json
{
  "reply_type": "no_results",
  "purchase_need": "3000以内、拍照强、折叠屏手机",
  "blocking_constraints": ["预算3000以内", "折叠屏", "拍照强"],
  "relax_options": [
    "提高预算",
    "取消折叠屏限制",
    "保留预算但改看直板手机"
  ]
}
```

The LLM may help phrase the reply, but only from the structured need, known filters, empty result, and relaxation options. It must not create product cards.

Relaxation option generation should be deterministic in v1. Suggested rules:

- If a budget or price ceiling is present, include an option to raise the budget or loosen the price ceiling.
- If a specific brand is required or many brands are excluded, include an option to loosen brand constraints.
- If the category is narrow, include an option to consider a nearby broader category.
- If there are multiple focus points, include an option to keep only the most important one.
- If no clear blocker is detected, use generic options: loosen budget, loosen brand/category, or tell the agent which condition matters most.

The no-results response returns `items: []` and sets `state.result_status` to `no_results`.

Because the current recommendation pipeline raises infrastructure failures instead of returning fallback products, exception handling remains transport-level:

- `/chat` may surface the exception through FastAPI/TestClient behavior.
- `/chat/stream` should continue converting post-start exceptions into an `error` SSE event.
- Only successful empty `RecommendResponse.items` triggers `no_results_reply`.

## LLM Prompt and Parsing Contract

The understanding service should call the LLM with a compact, explicit context block:

- Latest user message.
- Recent conversation, capped to the latest useful turns.
- Current `purchase_need`.
- Current preferences and excluded brands.
- Previous successful recommendation list with 1-based indexes, title, brand, price, and evidence.

The response must be JSON only. Example system requirement:

```text
Return one JSON object only. Do not use Markdown. Do not explain.
Do not invent product cards. Product recommendations come only from tools.
If the user asks about an indexed previous item, set target_item_index to that 1-based index.
If the user need is not specific enough to recommend, set intent to clarify and provide clarifying_question.
```

Parsing rules:

- Parse with `json.loads`.
- Validate with the `UserUnderstanding` schema.
- Treat parse or validation failure as LLM-unavailable behavior.
- Do not inspect the output with ad hoc string matching.
- The understanding call should have enough output budget for the JSON object and should not reuse a response limit meant only for short recommendation reasons.

Current LLM client note:

- `backend/llm/client.py::OpenAIInvokeChatClient.invoke` currently uses `max_tokens=160`, which is sized for short text and may be too small for structured understanding JSON.
- Implementation should either raise that limit for `invoke` or add an optional `max_tokens` parameter so the understanding service can request enough output.
- Tests should cover parsing directly with fake LLM responses instead of relying on the OpenAI client.

## Current Code Migration Map

The implementation should update these files deliberately:

```text
backend/agent/understanding.py
  Create. Owns UserUnderstanding schemas, fake-friendly service protocol,
  LLMUserUnderstandingService, JSON parsing, validation, and clarify fallback.

backend/agent/memory.py
  Extend ConversationState with purchase_need, excluded_brands, target_item_index,
  last_result_status, last_no_results_need, and last_no_results_relax_options.

backend/agent/graph/runner.py
  Replace parse_intent/run_agent_step with understand_user/update_memory/
  decide_next_action/execute_action/generate_reply/finalize_response nodes.
  Remove AgentPolicy imports and policy constructor argument.

backend/agent/runner.py
  Remove AgentPolicy import and policy parameter.
  Create or inject a UserUnderstandingService and pass it to LangGraphAgentRunner.

backend/agent/__init__.py
  Remove AgentIntent and AgentPolicy exports.
  Export the new understanding types only if callers need them.

backend/llm/client.py
  Allow the understanding service to request enough max_tokens for JSON output.

backend/tests/test_agent.py
  Replace policy tests and policy-based runner construction with understanding-service fakes.

backend/tests/test_main.py
  Update chat tests to inject fake understanding where needed.
  Keep response-contract and SSE event-shape tests.
```

`backend/api/deps.py` currently creates the app-level singleton using `create_agent_runner(recommendation_tool=...)`. That pattern can stay, but `create_agent_runner` must construct the new understanding service internally from config unless a test passes a fake.

## File Layout

Initial v1 layout:

```text
backend/agent/
  graph/runner.py
  understanding.py
  memory.py
  tools.py
```

`runner.py` should orchestrate nodes and avoid prompt details.

`understanding.py` should define:

- `UserUnderstanding`
- `UserIntent`
- `AgentAction`
- `ActionResult`
- `NoResultsSuggestion`
- `LLMUserUnderstandingService`
- `UserUnderstandingService` protocol or equivalent fake-friendly interface
- parsing and conservative fallback behavior

`policy.py` should be deleted when the implementation removes the old rule-based path. Any exports from `agent.__init__` and imports in tests should be updated instead of kept compatible.

If the understanding layer grows, it can later be split into:

```text
backend/agent/understanding/
  schemas.py
  llm.py
```

## LLM Unavailable Behavior

When the LLM call fails, is disabled, or returns invalid structured output:

```text
return clarify understanding
```

The agent should ask for the missing shopping basics, such as category, budget, and key preferences.

The system should not fall back to keyword rules because the target architecture is an LLM-driven shopping agent, not a rule system.

The clarify fallback should be explicit and stable:

```json
{
  "intent": "clarify",
  "confidence": 0.0,
  "purchase_need": null,
  "preference_updates": {},
  "target_item_index": null,
  "clarifying_question": "可以告诉我想买的品类、预算和最在意的点吗？"
}
```

This fallback is an availability behavior, not a business rule classifier.

## Out of Scope for v1

To keep the backend structure controlled, v1 will not include:

- Free-form multi-tool planning.
- LLM execution of arbitrary Python tools.
- Long-term user profile storage.
- Reflection loops.
- Token-level streaming.
- A separate reranking model.
- A full replacement of the recommendation pipeline.

The v1 scope is:

```text
contextual understanding
  -> shopping memory
  -> recommend / explain / clarify / no-results guidance
  -> stable chat response
```

## Testing Plan

Add focused tests for:

- First-turn shopping need produces `recommend`.
- "这个太贵了" uses history and produces `update_preference`.
- "第二个为什么适合我" uses previous items and produces `explain`.
- "不要苹果" updates excluded brand preference and triggers recommendation.
- Empty recommendation result produces a no-results reply and no fabricated items.
- LLM unavailable or invalid output produces `clarify`.
- `/chat` response shape remains stable.
- `/chat/stream` SSE event shape remains stable.

Tests should use fake LLM and fake recommendation services where possible so they are deterministic and do not depend on network calls.

Concrete test migration notes:

- Delete or replace `test_agent_policy_detects_recommend_update_explain_and_clarify`.
- Delete or replace `test_agent_policy_detects_product_need_without_buy_word`.
- Update runner construction in tests so it passes `understanding_service=FakeUnderstandingService(...)` instead of `policy=AgentPolicy()`.
- Keep `test_conversation_store_creates_and_updates_state`, but extend it for the new memory fields.
- Keep API contract assertions in `test_main.py`, but avoid depending on keyword detection for chat behavior.
- Keep `/chat/stream` serialization-failure coverage because `state` remains a free-form JSON-like dict and must stay serializable.

Acceptance criteria:

- No active chat path calls `AgentPolicy.detect_intent`.
- `backend/agent/policy.py` is deleted or contains no active production code.
- `create_agent_runner` no longer accepts or wires a `policy` dependency.
- No LLM parse failure causes `/chat` to crash.
- Empty recommendation results never produce fabricated product cards.
- `last_items` still points to the last successful recommendation after a no-results turn.
- `/chat/stream` emits the existing `start`, `delta`, `items`, `state`, and `done` events.
- Tests can run without real LLM credentials.
- Chat response `state` contains only JSON-serializable values.
- Recommendation integration still uses `RecommendationTool.run(query, top_k=3)` and `RecommendResponse`.

## Migration Notes

Implementation should be incremental:

1. Add the new understanding schema and service with tests.
2. Extend conversation memory for structured shopping context.
3. Inject the understanding service into `LangGraphAgentRunner` so tests can provide fakes.
4. Update `create_agent_runner` to remove `policy` and wire the understanding service.
5. Update the LangGraph runner nodes to use `understand_user`.
6. Add no-results action handling.
7. Keep API response contracts stable.
8. Delete the old `AgentPolicy` path, including production imports and obsolete keyword-policy tests.

The implementation should not mix the old keyword policy with the new LLM understanding path. When a test conflicts with the new architecture because it asserts keyword-policy behavior, replace it with an understanding-driven agent test instead of preserving compatibility.
