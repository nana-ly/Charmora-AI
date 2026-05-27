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
- `last_intent`
- `messages`

The existing `ConversationState` can be extended rather than replaced.

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
- `LLMUserUnderstandingService`
- parsing and conservative fallback behavior

`policy.py` should stop being the core agent decision path. It may remain temporarily for compatibility until tests and imports are migrated.

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

## Migration Notes

Implementation should be incremental:

1. Add the new understanding schema and service with tests.
2. Extend conversation memory for structured shopping context.
3. Update the LangGraph runner nodes to use `understand_user`.
4. Add no-results action handling.
5. Keep API response contracts stable.
6. Retire `AgentPolicy` from the active path once the new tests cover the agent behavior.
