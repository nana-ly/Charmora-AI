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
    target = archived.target_category or archived.preferences.get("target_category")
    if key:
        deduped = [
            item
            for item in conversation.previous_purchase_contexts
            if ensure_archived_target_fields(item) != key
        ]
    elif isinstance(target, str) and target.strip():
        deduped = [
            item
            for item in conversation.previous_purchase_contexts
            if (item.target_category or item.preferences.get("target_category")) != target
        ]
    else:
        deduped = list(conversation.previous_purchase_contexts)
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
    """切换到新目标前，先归档旧需求再清空活跃上下文。

    如需记录 transition 元数据，可调用 agent.context_lifecycle.switch_target_with_transition()。
    """

    archive_active_context(conversation)
    clear_active_context(conversation)


def find_archived_context(
    conversation: ConversationState,
    canonical_key: str,
) -> PurchaseContext | None:
    """按 canonical key 查找已归档的购买上下文。"""

    lookup_key = canonical_target_key(canonical_key) or canonical_key
    for item in conversation.previous_purchase_contexts:
        item_key = ensure_archived_target_fields(item)
        if item_key == lookup_key:
            return item
    return None


def request_restore(
    conversation: ConversationState,
    canonical_key: str,
    display_target_category: str | None = None,
) -> bool:
    """只有存在可恢复归档时，才进入待确认恢复状态。"""

    pending_key = canonical_target_key(canonical_key) or canonical_key
    archived = find_archived_context(conversation, pending_key)
    if archived is None:
        return False

    conversation.pending_restore_category = pending_key
    conversation.pending_restore_display_target = (
        display_target_category
        or archived.display_target_category
        or archived.target_category
    )
    return True


def clear_pending_restore(conversation: ConversationState) -> None:
    conversation.pending_restore_category = None
    conversation.pending_restore_display_target = None


def _pending_restore_display_target(conversation: ConversationState) -> str:
    if conversation.pending_restore_display_target:
        return conversation.pending_restore_display_target
    pending_key = conversation.pending_restore_category
    if pending_key and canonical_target_key(pending_key):
        return pending_key
    return "之前的需求"


def confirm_restore(conversation: ConversationState) -> UserUnderstanding:
    """执行恢复确认：归档当前需求，恢复旧需求，并清除待恢复标记。"""

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
    """执行恢复拒绝：只清除待恢复标记。"""

    clear_pending_restore(conversation)


def build_restore_rejection_understanding(
    conversation: ConversationState,
    message: str,
) -> UserUnderstanding:
    """把拒绝恢复后的新需求转成理解结果；不修改会话状态。"""

    display_target = _pending_restore_display_target(conversation)
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
        if fallback is None:
            continue

        fallback.purchase_need = message
        fallback.reset_context = True
        fallback.confidence = max(fallback.confidence, 0.65)
        return fallback

    return clarify_understanding(
        f"不恢复{display_target}。可以告诉我新的品类、预算和最在意的点吗？"
    )


def resolve_pending_restore(
    conversation: ConversationState,
    message: str,
) -> PendingRestoreResolution:
    """解析待恢复确认消息，但不直接修改会话状态。"""

    pending_key = conversation.pending_restore_category
    if pending_key is None:
        return PendingRestoreResolution(handled=False)

    display_target = _pending_restore_display_target(conversation)

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
