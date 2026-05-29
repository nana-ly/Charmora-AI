"""购买上下文切换与恢复的状态工具。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from agent.category_rules import (
    canonical_target_key,
    is_restore_confirmation,
    is_restore_rejection,
)
from agent.fallback_understanding import fallback_understanding
from agent.memory import ConversationState, PurchaseContext
from agent.understanding import UserIntent, UserUnderstanding, clarify_understanding


class ConversationCommand(str, Enum):
    """恢复确认流给 runner 的显式命令。"""

    NONE = "none"
    CONFIRM_RESTORE = "confirm_restore"
    REJECT_RESTORE = "reject_restore"


class PendingRestoreResolution(BaseModel):
    """待恢复状态的解析结果，由 runner 决定何时落状态。"""

    handled: bool = False
    command: ConversationCommand = ConversationCommand.NONE
    understanding: UserUnderstanding | None = None
    clear_pending_before_understanding: bool = False


def active_target_category(conversation: ConversationState) -> str | None:
    """返回当前活跃需求的具体目标品类。"""

    target_category = conversation.preferences.get("target_category")
    if isinstance(target_category, str) and target_category.strip():
        return target_category

    category = conversation.preferences.get("category")
    if isinstance(category, str) and category.strip():
        return category
    return None


def active_target_key(conversation: ConversationState) -> str | None:
    """返回当前目标的 canonical key，旧状态缺 key 时就地补齐。"""

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


def ensure_archived_target_fields(item: PurchaseContext) -> str | None:
    """补齐旧归档的 canonical/display 目标字段。"""

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


def archive_active_context(conversation: ConversationState, max_contexts: int = 5) -> None:
    """归档当前购买需求，并按目标品类替换旧归档。"""

    if not conversation.purchase_need:
        return

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


def clear_active_context(conversation: ConversationState) -> None:
    """清空当前购买上下文，保留消息、归档和待恢复标记。"""

    conversation.purchase_need = None
    conversation.preferences = {}
    conversation.excluded_product_ids = []
    conversation.excluded_brands = []
    conversation.excluded_keywords = []
    conversation.excluded_price_ranges = []
    conversation.negative_feedback_items = []
    conversation.latest_attempt_status = None
    conversation.latest_attempt_error = None
    conversation.latest_no_results_relax_options = []
    conversation.last_successful_items = []
    conversation.last_successful_result_id = None
    conversation.last_successful_query = None
    conversation.last_successful_filters = None
    conversation.target_item_index = None
    conversation.last_query = None
    conversation.last_filters = None
    conversation.last_items = []
    conversation.last_result_status = None
    conversation.last_no_results_need = None
    conversation.last_no_results_relax_options = []
    conversation.last_intent = None


def reset_for_new_target(conversation: ConversationState) -> None:
    """切换到新目标前，先归档旧需求再清空活跃上下文。"""

    archive_active_context(conversation)
    clear_active_context(conversation)


def find_archived_context(
    conversation: ConversationState,
    target_category: str,
) -> PurchaseContext | None:
    """按具体目标品类查找已归档的购买上下文。"""

    target_key = canonical_target_key(target_category)
    for item in conversation.previous_purchase_contexts:
        item_target = item.target_category or item.preferences.get("target_category")
        item_key = ensure_archived_target_fields(item)
        if target_key is not None and item_key == target_key:
            return item
        if item_target == target_category:
            return item
    return None


def request_restore(conversation: ConversationState, target_category: str) -> bool:
    """只有存在可恢复归档时，才进入待确认恢复状态。"""

    if find_archived_context(conversation, target_category) is None:
        return False

    conversation.pending_restore_category = target_category
    archived = find_archived_context(conversation, target_category)
    if archived is not None:
        conversation.pending_restore_display_target = (
            archived.display_target_category or archived.target_category or target_category
        )
    return True


def confirm_restore(conversation: ConversationState) -> UserUnderstanding:
    """执行恢复确认：归档当前需求，恢复旧需求，并清除待恢复标记。"""

    target_category = conversation.pending_restore_category
    archived = (
        find_archived_context(conversation, target_category)
        if target_category is not None
        else None
    )
    if archived is None:
        conversation.pending_restore_category = None
        conversation.pending_restore_display_target = None
        return clarify_understanding("没有找到之前的需求，可以重新说一下想买什么吗？")

    archive_active_context(conversation)
    archived.apply_to_conversation(conversation)
    conversation.pending_restore_category = None
    conversation.pending_restore_display_target = None

    return UserUnderstanding(
        intent=UserIntent.RECOMMEND,
        confidence=0.9,
        purchase_need=conversation.purchase_need,
        preference_updates=conversation.preferences.copy(),
    )


def reject_restore(conversation: ConversationState) -> None:
    """执行恢复拒绝：只清除待恢复标记。"""

    conversation.pending_restore_category = None
    conversation.pending_restore_display_target = None


def build_restore_rejection_understanding(
    target_category: str,
    message: str,
) -> UserUnderstanding:
    """把拒绝恢复后的新需求转成理解结果；不修改会话状态。"""

    scratch = ConversationState(session_id="restore-rejection")
    candidates = [message]
    if target_category not in message:
        candidates.append(f"{target_category}，{message}")

    for candidate in candidates:
        fallback = fallback_understanding(
            message=candidate,
            conversation=scratch,
            reason="restore_rejection",
        )
        if fallback is None:
            continue

        fallback.purchase_need = message
        fallback.reset_context = True
        fallback.confidence = max(fallback.confidence, 0.6)
        return fallback

    return clarify_understanding(
        f"不恢复之前的{target_category}需求。可以告诉我新的品类、预算和最在意的点吗？"
    )


def resolve_pending_restore(
    conversation: ConversationState,
    message: str,
) -> PendingRestoreResolution:
    """解析待恢复确认消息，但不直接修改会话状态。"""

    target_category = conversation.pending_restore_category
    if target_category is None:
        return PendingRestoreResolution(handled=False)

    if is_restore_rejection(message):
        return PendingRestoreResolution(
            handled=True,
            command=ConversationCommand.REJECT_RESTORE,
            understanding=build_restore_rejection_understanding(target_category, message),
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
            f"不恢复之前的{target_category}需求。可以告诉我新的品类、预算和最在意的点吗？"
        ),
    )
