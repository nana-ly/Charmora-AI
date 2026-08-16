"""LLM Agent 编排器。取代 policy + query_builder + reply_builder 的碎片逻辑。

LLM 自己决定：推荐什么、搜几件、要不要对比、怎么回复。
"""

import json
import logging
import re

from agent.tools.recommendation import RecommendationTool
from agent.tools.compare import CompareTool
from agent.tools.explain import ExplainTool
from core.config import LLMConfig
from llm.client import UniversalChatClient
from schemas.product import ProductCard
from schemas.recommend import NegativeFilters

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """你是 ShopGuide，一个智能导购 AI Agent。

你的任务是：理解用户需求 → 决定用什么工具 → 自然回复。

## 可用工具

### recommend(query, top_k=3)
搜索商品。query 用中文描述用户想要什么。top_k 控制返回几件。
- 用户说"想买手机"→ recommend("拍照手机 旗舰")
- 用户说"便宜一点"→ recommend("性价比手机", top_k=3)
- 用户说"还有别的吗"→ recommend("手机 热门", top_k=5)

### compare(items, indexes)
对比已有商品。items 是上一轮的完整商品列表，indexes 是序号（从1开始）。
- 用户说"第一个和第三个哪个好"→ compare(items, [1, 3])

### explain(items, target_index)
解释某个商品。target_index 是序号（从1开始）。
- 用户说"第二个怎么样"→ explain(items, 2)

## 工作流程

1. 理解用户意图
2. 调用合适的工具（一个或多个）
3. 根据工具返回的商品数据，生成自然的中文导购回复

## 回复要求

- 语气温暖自然，像真人导购
- 提到商品时，在该句末尾插入 [INSERT:编号]（0表示第1件），这样商品卡片会出现在那句话后面
- 不要提及"第一/第二/第三款"，直接用商品名
- 不要照搬技术字段（商品ID、相似度等）
- 结尾可以问一句引导性问题
- 长度视商品数量而定，1-2件约80-120字，3件约120-180字

## 示例

用户: "推荐拍照手机"
你: recommend("拍照手机 旗舰", top_k=3)
然后回复: "华为Pura 90 Pro拍照很强 [INSERT:0]，小米14徕卡镜头也很棒 [INSERT:1]。你更看重夜景还是人像？"

用户: "第一个和第二个哪个好"
你: compare(items, [1, 2])
然后回复: "华为Pura 90 Pro暗光表现更强 [INSERT:0]，但小米14充电更快更轻薄 [INSERT:1]。如果你经常晚上拍照的话，华为更合适。"
"""


class ShoppingAgent:
    """LLM 驱动的导购 Agent。"""

    def __init__(
        self,
        llm_config: LLMConfig,
        recommend_tool: RecommendationTool | None = None,
        compare_tool: CompareTool | None = None,
        explain_tool: ExplainTool | None = None,
    ):
        self.llm = UniversalChatClient(llm_config)
        self.recommend_tool = recommend_tool or RecommendationTool()
        self.compare_tool = compare_tool or CompareTool()
        self.explain_tool = explain_tool or ExplainTool()
        self._last_items: list[ProductCard] = []

    # ── 对外接口 ──

    def run(
        self,
        user_message: str,
        chat_history: list[dict[str, str]],
        preferences: dict,
        excluded_brands: list[str] | None = None,
    ) -> dict:
        """执行一轮 Agent 对话。

        返回: {"reply": str, "items": list[ProductCard], "thinking_steps": list[str]}
        """
        thinking: list[str] = []

        # 1. LLM 决定调用哪些工具
        thinking.append("理解需求")
        tool_calls = self._plan_tools(user_message, chat_history, preferences)

        # 2. 执行工具
        items: list[ProductCard] = []
        for call in tool_calls:
            result = self._execute_tool(call, excluded_brands)
            if result.get("items"):
                items.extend(result["items"])
            thinking.append(result.get("thinking", call["tool"]))

        # 3. LLM 生成回复
        thinking.append("生成回复")
        self._last_items = items
        reply = self._generate_reply(user_message, items, chat_history, preferences)

        return {"reply": reply, "items": items, "thinking_steps": thinking}

    # ── 工具计划 ──

    def _plan_tools(
        self,
        user_message: str,
        history: list[dict[str, str]],
        preferences: dict,
    ) -> list[dict]:
        """让 LLM 输出 JSON 工具调用计划。"""
        history_str = "\n".join(
            f"{m.get('role','')}: {m.get('content','')[:200]}" for m in history[-6:]
        )
        prompt = (
            f"对话历史:\n{history_str}\n\n"
            f"用户偏好: {preferences}\n"
            f"用户最新消息: {user_message}\n\n"
            f"你需要决定用什么工具。输出 JSON 格式:\n"
            f'[{{"tool":"recommend","args":{{"query":"...","top_k":3}}}}]\n'
            f'或 [{{"tool":"compare","args":{{"indexes":[1,2]}}}}]\n'
            f'或 [{{"tool":"explain","args":{{"target_index":1}}}}]\n'
            f'如果只是追问、澄清或不需要工具，输出空数组 []。\n'
            f"只输出 JSON，不要其他内容。"
        )

        raw = self.llm._call(
            system="你是工具路由助手。只输出 JSON 数组。",
            user=prompt,
            temperature=0.1,
            max_tokens=200,
        )
        try:
            # 提取 JSON 数组
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            logger.warning("Failed to parse tool plan: %s", raw[:200])

        # 兜底：默认推荐
        return [{"tool": "recommend", "args": {"query": user_message, "top_k": 3}}]

    # ── 工具执行 ──

    def _execute_tool(self, call: dict, excluded_brands: list[str] | None) -> dict:
        tool = call.get("tool", "recommend")
        args = call.get("args", {})

        if tool == "recommend":
            return self._do_recommend(args, excluded_brands)
        elif tool == "compare":
            return self._do_compare(args)
        elif tool == "explain":
            return self._do_explain(args)
        else:
            return {"thinking": f"未知工具: {tool}", "items": []}

    def _do_recommend(self, args: dict, excluded_brands: list[str] | None) -> dict:
        query = args.get("query", "推荐商品")
        top_k = int(args.get("top_k", 3))
        negative = NegativeFilters(excluded_brands=excluded_brands) if excluded_brands else None

        result = self.recommend_tool.run(query=query, top_k=top_k, negative_filters=negative)
        return {
            "thinking": f"检索商品 — {len(result.items)} 件",
            "items": result.items,
        }

    def _do_compare(self, args: dict) -> dict:
        indexes = args.get("indexes", [1, 2])
        if not self._last_items:
            return {"thinking": "对比 — 无历史商品", "items": []}

        result = self.compare_tool.run(items=self._last_items, compare_item_indexes=indexes)
        return {
            "thinking": f"对比 — {len(result.items)} 件",
            "items": result.items,
        }

    def _do_explain(self, args: dict) -> dict:
        target = args.get("target_index", 1)
        if not self._last_items:
            return {"thinking": "解释 — 无历史商品", "items": []}

        self.explain_tool.run(
            items=self._last_items,
            target_item_index=target,
        )
        return {
            "thinking": f"解释 — 第 {target} 件",
            "items": self._last_items,
        }

    # ── 回复生成 ──

    def _generate_reply(
        self,
        user_message: str,
        items: list[ProductCard],
        history: list[dict[str, str]],
        preferences: dict,
    ) -> str:
        items_text = "\n".join(
            f"[{i}] {item.brand} {item.title} | ¥{item.price} | "
            f"理由:{item.reason} | 依据:{item.evidence}"
            for i, item in enumerate(items)
        ) if items else "（无商品数据）"

        history_str = "\n".join(
            f"{m.get('role','')}: {m.get('content','')[:300]}" for m in history[-6:]
        )

        prompt = (
            f"对话历史:\n{history_str}\n\n"
            f"用户偏好: {preferences}\n"
            f"用户最新消息: {user_message}\n\n"
            f"商品数据:\n{items_text}\n\n"
            f"请根据以上信息生成自然的中文导购回复。"
        )

        raw = self.llm._call(
            system=AGENT_SYSTEM_PROMPT,
            user=prompt,
            temperature=0.5,
            max_tokens=800,
        )
        return raw.strip() if raw else "我根据你的需求找到了相关商品，请看看哪一个更合适。"
