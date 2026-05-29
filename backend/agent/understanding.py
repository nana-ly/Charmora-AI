"""LLM 驱动的用户购物意图理解。"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from agent.memory import ConversationState
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from core.config import LLMConfig
from schemas.product import ProductCard

logger = logging.getLogger(__name__)


class UserIntent(str, Enum):
    """用户消息理解层支持的意图。"""

    RECOMMEND = "recommend"
    UPDATE_PREFERENCE = "update_preference"
    EXPLAIN = "explain"
    CLARIFY = "clarify"


class AgentAction(str, Enum):
    """执行层支持的动作。"""

    RECOMMEND = "recommend"
    EXPLAIN = "explain"
    CLARIFY = "clarify"
    REPLY_ONLY = "reply_only"


class UserUnderstanding(BaseModel):
    """LLM 返回并经过校验的结构化用户理解。"""

    intent: UserIntent
    confidence: float = Field(ge=0, le=1)
    purchase_need: str | None = None
    preference_updates: dict[str, Any] = Field(default_factory=dict)
    negative_updates: dict[str, Any] = Field(default_factory=dict)
    target_item_index: int | None = Field(default=None, ge=1)
    clarifying_question: str | None = None
    reset_context: bool = False
    restore_context_category: str | None = None


DEFAULT_UNDERSTANDING_FIELDS: dict[str, Any] = {
    "confidence": 0.5,
    "purchase_need": None,
    "preference_updates": {},
    "negative_updates": {},
    "target_item_index": None,
    "clarifying_question": None,
    "reset_context": False,
    "restore_context_category": None,
}

DEFAULT_CLARIFY_QUESTION = "可以告诉我想买的品类、预算和最在意的点吗？"
GENERIC_CONTEXTUAL_CLARIFY_QUESTION = (
    "我还在按之前的购买需求理解。你是想降低预算、换品牌，还是调整关注点？"
)


def normalize_understanding_payload(payload: Any) -> dict[str, Any]:
    """在 Pydantic 校验前补齐安全默认值，并清洗可安全降级的脏字段。"""
    if not isinstance(payload, dict):
        raise TypeError("understanding payload must be a JSON object")

    missing_fields = [
        field for field in DEFAULT_UNDERSTANDING_FIELDS if field not in payload
    ]
    if missing_fields:
        logger.debug("understanding source=normalized missing_fields=%s", missing_fields)

    unknown_fields = sorted(set(payload) - set(UserUnderstanding.model_fields))
    if unknown_fields:
        logger.debug("understanding ignored_unknown_fields=%s", unknown_fields)

    normalized = {
        **DEFAULT_UNDERSTANDING_FIELDS,
        "preference_updates": {},
        "negative_updates": {},
        **payload,
    }
    invalid_fields: list[str] = []

    if not isinstance(normalized.get("preference_updates"), dict):
        normalized["preference_updates"] = {}
        invalid_fields.append("preference_updates")

    if not isinstance(normalized.get("negative_updates"), dict):
        normalized["negative_updates"] = {}
        invalid_fields.append("negative_updates")

    target_item_index = normalized.get("target_item_index")
    if target_item_index is not None:
        is_valid_index = (
            isinstance(target_item_index, int)
            and not isinstance(target_item_index, bool)
            and target_item_index >= 1
        )
        if not is_valid_index:
            normalized["target_item_index"] = None
            invalid_fields.append("target_item_index")

    if invalid_fields:
        logger.info(
            "understanding normalized_invalid_fields fields=%s",
            invalid_fields,
        )

    return normalized


class NoResultsSuggestion(BaseModel):
    """无结果分支的确定性建议。"""

    purchase_need: str
    blocking_constraints: list[str] = Field(default_factory=list)
    relax_options: list[str] = Field(default_factory=list)


class ActionResult(BaseModel):
    """执行层传给回复生成层的结果。"""

    action: AgentAction
    reply_type: str
    recommendation_query: str | None = None
    items: list[ProductCard] = Field(default_factory=list)
    tool_error: str | None = None
    no_results: NoResultsSuggestion | None = None
    target_item_index: int | None = None
    clarifying_question: str | None = None
    negative_feedback: NegativeFeedbackApplicationResult | None = None


class InvokeChatClient(Protocol):
    """理解层需要的最小聊天模型接口。"""

    def invoke(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 160,
    ) -> Any:
        """调用模型并返回带 content 属性的响应。"""
        ...


class UserUnderstandingService(Protocol):
    """可替换、便于测试的用户理解服务协议。"""

    def understand(
        self,
        *,
        message: str,
        conversation: ConversationState,
    ) -> UserUnderstanding:
        """理解当前用户消息和会话状态。"""
        ...


class LLMUserUnderstandingService:
    """调用 LLM 生成结构化用户理解。"""

    def __init__(
        self,
        *,
        llm: InvokeChatClient | None = None,
        config: LLMConfig | None = None,
        max_tokens: int = 3000,
    ) -> None:
        self.llm = llm
        self.config = config or LLMConfig()
        self.max_tokens = max_tokens

    def understand(
        self,
        *,
        message: str,
        conversation: ConversationState,
    ) -> UserUnderstanding:
        """调用模型并解析为 `UserUnderstanding`。"""
        llm = self._resolve_llm()
        if llm is None:
            logger.debug("llm understanding skipped; returning clarify fallback")
            return self._fallback_or_clarify(
                message=message,
                conversation=conversation,
                reason="llm_unavailable",
            )

        try:
            response = llm.invoke(
                self._build_messages(message, conversation),
                max_tokens=self.max_tokens,
            )
            parsed = json.loads(getattr(response, "content", ""))
            normalized = normalize_understanding_payload(parsed)
            understanding = UserUnderstanding.model_validate(normalized)
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

            if understanding.intent == UserIntent.CLARIFY:
                return (
                    self._fallback_understanding(
                        message=message,
                        conversation=conversation,
                        reason="contextual_fallback_after_llm_understanding",
                    )
                    or understanding
                )

            if self._should_try_contextual_fallback(understanding, conversation):
                return self._fallback_or_clarify(
                    message=message,
                    conversation=conversation,
                    reason="contextual_fallback_after_llm_understanding",
                )

            if self._needs_purchase_need(understanding, conversation):
                return self._fallback_or_clarify(
                    message=message,
                    conversation=conversation,
                    reason="missing_purchase_need",
                )
            return understanding
        except (TypeError, json.JSONDecodeError, ValidationError):
            logger.exception("LLM understanding response could not be parsed")
            return self._fallback_or_clarify(
                message=message,
                conversation=conversation,
                reason="parse_validation_failure",
            )
        except Exception:
            logger.exception("LLM understanding failed")
            return self._fallback_or_clarify(
                message=message,
                conversation=conversation,
                reason="llm_call_failure",
            )

    def _resolve_llm(self) -> InvokeChatClient | None:
        if self.llm is not None:
            return self.llm
        if not self.config.is_available:
            return None

        from llm.client import create_llm

        self.llm = create_llm(self.config)
        return self.llm

    def _has_active_purchase_context(self, conversation: ConversationState) -> bool:
        return bool(
            conversation.purchase_need
            or conversation.preferences.get("target_category")
            or conversation.last_items
        )

    def _should_try_contextual_fallback(
        self,
        understanding: UserUnderstanding,
        conversation: ConversationState,
    ) -> bool:
        if understanding.intent == UserIntent.CLARIFY:
            return True
        if understanding.intent != UserIntent.UPDATE_PREFERENCE:
            return False
        if understanding.preference_updates:
            return False
        if understanding.negative_updates:
            return False
        return self._has_active_purchase_context(conversation)

    def _has_broad_target_fields(self, understanding: UserUnderstanding) -> bool:
        updates = understanding.preference_updates
        return all(
            isinstance(updates.get(key), str) and updates[key].strip()
            for key in ("target_category", "category", "canonical_target_key")
        ) and isinstance(updates.get("is_broad_category_request"), bool)

    def _needs_purchase_need(
        self,
        understanding: UserUnderstanding,
        conversation: ConversationState,
    ) -> bool:
        if understanding.intent not in {UserIntent.RECOMMEND, UserIntent.UPDATE_PREFERENCE}:
            return False
        return not (understanding.purchase_need or conversation.purchase_need)

    def _fallback_or_clarify(
        self,
        *,
        message: str,
        conversation: ConversationState,
        reason: str,
    ) -> UserUnderstanding:
        fallback = self._fallback_understanding(
            message=message,
            conversation=conversation,
            reason=reason,
        )
        return fallback or clarify_for_context(conversation)

    def _fallback_understanding(
        self,
        *,
        message: str,
        conversation: ConversationState,
        reason: str,
    ) -> UserUnderstanding | None:
        from agent.fallback_understanding import fallback_understanding

        return fallback_understanding(
            message=message,
            conversation=conversation,
            reason=reason,
        )

    def _build_messages(
        self,
        message: str,
        conversation: ConversationState,
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._context_block(message, conversation)},
        ]

    def _system_prompt(self) -> str:
        return (
            "你是电商导购 Agent 的用户意图理解器。\n"
            "Return one JSON object only. Do not use Markdown. Do not explain.\n"
            "Do not invent product cards. Product recommendations come only from tools.\n"
            "intent 只能是 recommend、update_preference、explain、clarify。\n"
            "如果用户询问上一轮第几个商品，target_item_index 使用 1-based 序号。\n"
            "如果需求不足以推荐，intent=clarify 并给出 clarifying_question。\n"
            "category means catalog category, for example 数码电子 or 食品生活.\n"
            "target_category means the concrete shopping target, for example 手机 or 咖啡.\n"
            "Use reset_context=true only when the user starts a different shopping target.\n"
            "Use restore_context_category only when the user may be returning to an archived target and needs confirmation.\n"
            "Negative feedback such as 不要苹果, 不考虑华为, 排除第2款 belongs in negative_updates, "
            "not in preference_updates brand/preferred_brands.\n"
            "Broad category requests such as 推荐手机, 看看护肤品, 有什么咖啡推荐 must return intent=recommend, "
            "purchase_need cleaned from negative phrases, preference_updates.target_category, category, canonical_target_key, "
            "and is_broad_category_request=true. Do not put negative phrases into purchase_need.\n"
            "For 推荐手机，不要苹果, return intent=recommend with target phone fields and negative_updates.excluded_brands.\n"
            "Always include confidence, purchase_need, preference_updates, negative_updates, target_item_index, clarifying_question, "
            "reset_context, restore_context_category.\n"
            "Example complete request: 用户=我想买一台华为手机，预算6000以内，主要拍照和续航; "
            "return intent=recommend, target_category=手机, category=数码电子.\n"
            "Example contextual price feedback: 已有手机需求后，用户=太贵了; "
            "return intent=update_preference, purchase_need=null, "
            "preference_updates must be a JSON object such as "
            "{\"price_direction\":\"lower\",\"avoid_current_price_band\":true}, "
            "negative_updates must be a JSON object, "
            "target_item_index must be null.\n"
            "Example ambiguous restore: 用户=还是看手机吧; "
            "return intent=clarify, restore_context_category=手机, clarifying_question=是否恢复之前的手机需求."
        )

    def _context_block(self, message: str, conversation: ConversationState) -> str:
        recent_messages = conversation.messages[-8:]
        history = "\n".join(
            f"{item.role}: {item.content}"
            for item in recent_messages
            if item.content.strip()
        )
        previous_items = "\n".join(
            self._format_previous_item(index, item)
            for index, item in enumerate(conversation.last_items, start=1)
        )
        # 归档上下文只摘要关键购买意图，避免把历史商品列表塞进提示词。
        previous_contexts = "\n".join(
            (
                f"- target_category={item.target_category or '无'}; "
                f"category={item.category or '无'}; "
                f"purchase_need={item.purchase_need}"
            )
            for item in conversation.previous_purchase_contexts
        )
        return (
            f"最新用户消息：{message}\n"
            f"最近对话：\n{history or '无'}\n"
            f"当前 purchase_need：{conversation.purchase_need or '无'}\n"
            f"当前 preferences：{json.dumps(conversation.preferences, ensure_ascii=False)}\n"
            f"排除品牌：{json.dumps(conversation.excluded_brands, ensure_ascii=False)}\n"
            f"pending_restore_category：{conversation.pending_restore_category or '无'}\n"
            f"previous_purchase_contexts：\n{previous_contexts or '无'}\n"
            f"上一轮成功推荐：\n{previous_items or '无'}"
        )

    def _format_previous_item(self, index: int, item: ProductCard) -> str:
        return (
            f"{index}. title={item.title}; brand={item.brand}; "
            f"price={item.price}; evidence={item.evidence}"
        )


def clarify_for_context(conversation: ConversationState) -> UserUnderstanding:
    """根据已有购买上下文选择澄清文案。"""
    target_category = conversation.preferences.get("target_category")
    has_context = bool(
        conversation.purchase_need
        or target_category
        or conversation.last_items
    )
    if not has_context:
        return clarify_understanding()

    if isinstance(target_category, str) and target_category:
        return clarify_understanding(
            f"我还在按之前的{target_category}需求理解。"
            "你是想降低预算、换品牌，还是调整关注点？"
        )

    return clarify_understanding(GENERIC_CONTEXTUAL_CLARIFY_QUESTION)


def clarify_understanding(
    question: str = DEFAULT_CLARIFY_QUESTION,
) -> UserUnderstanding:
    """保守澄清兜底，供 LLM 不可用或解析失败时使用。"""
    return UserUnderstanding(
        intent=UserIntent.CLARIFY,
        confidence=0.0,
        purchase_need=None,
        preference_updates={},
        target_item_index=None,
        clarifying_question=question,
        reset_context=False,
        restore_context_category=None,
    )
