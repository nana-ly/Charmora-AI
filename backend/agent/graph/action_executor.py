"""LangGraph 动作执行器。"""

from __future__ import annotations

import logging
from uuid import uuid4

from agent.memory import ConversationState
from agent.negative_feedback import build_negative_filters
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.query_builder import build_recommendation_query
from agent.tools import CompareTool, ExplainTool, RecommendationTool
from agent.understanding import (
    ActionResult,
    AgentAction,
    NoResultsSuggestion,
    UserUnderstanding,
)
from schemas.recommend import RecommendResponse

logger = logging.getLogger(__name__)


class ActionExecutor:
    """执行 policy 决定出的动作，并维护推荐尝试状态。"""

    def __init__(
        self,
        recommendation_tool: RecommendationTool,
        *,
        explain_tool: ExplainTool | None = None,
        compare_tool: CompareTool | None = None,
    ) -> None:
        self.recommendation_tool = recommendation_tool
        self.explain_tool = explain_tool or ExplainTool()
        self.compare_tool = compare_tool or CompareTool()

    def execute(
        self,
        *,
        action: AgentAction,
        conversation: ConversationState,
        understanding: UserUnderstanding | None = None,
        negative_feedback_result: NegativeFeedbackApplicationResult | None = None,
    ) -> ActionResult:
        if action == AgentAction.RECOMMEND:
            return self._execute_recommendation(
                conversation,
                negative_feedback_result,
            )

        if action == AgentAction.EXPLAIN:
            return self._execute_explain(
                conversation,
                understanding.target_item_index if understanding else None,
            )

        if action == AgentAction.COMPARE:
            return self.compare_tool.run(
                items=conversation.last_items,
                compare_item_indexes=(
                    understanding.compare_item_indexes if understanding else []
                ),
            )

        if action == AgentAction.REPLY_ONLY:
            return ActionResult(
                action=AgentAction.REPLY_ONLY,
                reply_type="negative_feedback_noop_reply",
                items=[],
                negative_feedback=negative_feedback_result,
            )

        question = (
            negative_feedback_result.clarifying_question
            if negative_feedback_result and negative_feedback_result.clarifying_question
            else (understanding.clarifying_question if understanding else None)
            or "可以告诉我想买的品类、预算和最在意的点吗？"
        )
        return ActionResult(
            action=AgentAction.CLARIFY,
            reply_type="clarify_reply",
            clarifying_question=question,
            negative_feedback=negative_feedback_result,
        )

    def _execute_recommendation(
        self,
        conversation: ConversationState,
        negative_feedback: NegativeFeedbackApplicationResult | None = None,
    ) -> ActionResult:
        recommendation_query = build_recommendation_query(conversation)
        logger.debug("agent recommendation query_length=%s", len(recommendation_query))
        try:
            result = self.recommendation_tool.run(
                recommendation_query,
                negative_filters=build_negative_filters(conversation),
            )
        except Exception:
            return self._handle_recommendation_tool_error(
                conversation,
                recommendation_query,
                negative_feedback,
            )
        logger.info("agent recommendation completed item_count=%s", len(result.items))

        if not result.items:
            no_results = self._handle_no_results(
                conversation,
                result,
                recommendation_query,
            )
            return ActionResult(
                action=AgentAction.RECOMMEND,
                reply_type="no_results_reply",
                recommendation_query=recommendation_query,
                items=[],
                no_results=no_results,
                negative_feedback=negative_feedback,
            )

        self._save_successful_recommendation(conversation, result)
        return ActionResult(
            action=AgentAction.RECOMMEND,
            reply_type="recommendation_reply",
            recommendation_query=recommendation_query,
            items=result.items,
            negative_feedback=negative_feedback,
        )

    def _execute_explain(
        self,
        conversation: ConversationState,
        target_item_index: int | None,
    ) -> ActionResult:
        result = self.explain_tool.run(
            items=conversation.last_items,
            target_item_index=target_item_index,
            fallback_item_index=conversation.target_item_index,
        )
        if result.reply_type == "explain_reply":
            conversation.target_item_index = result.target_item_index
        return result

    def _save_successful_recommendation(
        self,
        conversation: ConversationState,
        result: RecommendResponse,
    ) -> None:
        conversation.last_query = result.query
        conversation.last_filters = result.filters
        conversation.last_items = result.items
        conversation.latest_attempt_status = "success"
        conversation.latest_attempt_error = None
        conversation.latest_no_results_relax_options = []
        conversation.last_result_status = "success"
        conversation.last_no_results_need = None
        conversation.last_no_results_relax_options = []
        conversation.last_successful_result_id = str(uuid4())
        conversation.last_successful_query = result.query
        conversation.last_successful_filters = result.filters
        conversation.last_successful_items = result.items
        conversation.preferences.update(result.filters.model_dump(exclude_none=True))

    def _handle_no_results(
        self,
        conversation: ConversationState,
        result: RecommendResponse,
        recommendation_query: str,
    ) -> NoResultsSuggestion:
        conversation.last_query = recommendation_query
        conversation.last_filters = result.filters
        conversation.latest_attempt_status = "no_results"
        conversation.latest_attempt_error = None
        conversation.last_result_status = "no_results"
        conversation.last_no_results_need = recommendation_query

        suggestion = NoResultsSuggestion(
            purchase_need=recommendation_query,
            blocking_constraints=self._detect_blocking_constraints(conversation, result),
            relax_options=self._build_relax_options(conversation, result),
        )
        conversation.latest_no_results_relax_options = suggestion.relax_options
        conversation.last_no_results_relax_options = suggestion.relax_options
        return suggestion

    def _handle_recommendation_tool_error(
        self,
        conversation: ConversationState,
        recommendation_query: str,
        negative_feedback: NegativeFeedbackApplicationResult | None = None,
    ) -> ActionResult:
        """推荐工具失败时保留上一轮结果，只记录本轮可恢复错误。"""
        logger.exception("agent recommendation tool failed")
        conversation.last_query = recommendation_query
        conversation.latest_attempt_status = "tool_error"
        conversation.latest_attempt_error = "recommendation_failed"
        conversation.last_result_status = "tool_error"
        return ActionResult(
            action=AgentAction.RECOMMEND,
            reply_type="tool_error_reply",
            recommendation_query=recommendation_query,
            items=[],
            tool_error="recommendation_failed",
            negative_feedback=negative_feedback,
        )

    def _detect_blocking_constraints(
        self,
        conversation: ConversationState,
        result: RecommendResponse,
    ) -> list[str]:
        constraints: list[str] = []
        budget = conversation.preferences.get("budget")
        if budget:
            constraints.append(str(budget))
        elif result.filters.max_price is not None:
            constraints.append(f"预算{result.filters.max_price}以内")

        category = conversation.preferences.get("category") or result.filters.category
        if category:
            constraints.append(str(category))

        focus = conversation.preferences.get("focus")
        if isinstance(focus, list):
            constraints.extend(str(item) for item in focus[:3])
        elif focus:
            constraints.append(str(focus))

        return _merge_unique([], constraints)

    def _build_relax_options(
        self,
        conversation: ConversationState,
        result: RecommendResponse,
    ) -> list[str]:
        options: list[str] = []
        if conversation.preferences.get("budget") or result.filters.max_price is not None:
            options.append("提高预算或放宽价格上限")
        if result.filters.brand or conversation.excluded_brands:
            options.append("放宽品牌限制")

        category = conversation.preferences.get("category") or result.filters.category
        if category:
            options.append("考虑相近或更宽的品类")

        focus = conversation.preferences.get("focus")
        if isinstance(focus, list) and len(focus) > 1:
            options.append("只保留最重要的一个功能重点")

        if not options:
            options = ["放宽预算", "放宽品牌或品类", "告诉我哪个条件最重要"]
        return options[:3]


def _merge_unique(current: list, updates: list) -> list:
    merged: list = []
    for item in [*current, *updates]:
        if item not in merged:
            merged.append(item)
    return merged
