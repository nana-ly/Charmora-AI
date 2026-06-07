"""显式上下文生命周期 transition helper。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from agent.context_manager import active_target_key, reset_for_new_target
from agent.memory import ConversationState


class ContextTransitionType(str, Enum):
    """上下文生命周期动作类型，用于调试和后续 trace 扩展。"""

    CREATE_CURRENT = "create_current"
    UPDATE_CURRENT = "update_current"
    SWITCH_TARGET = "switch_target"
    ARCHIVE_CURRENT = "archive_current"
    CLEAR_CURRENT = "clear_current"
    REQUEST_RESTORE = "request_restore"
    RESTORE_ARCHIVED = "restore_archived"
    REJECT_RESTORE = "reject_restore"
    NONE = "none"


class ContextTransition(BaseModel):
    """一次上下文状态变化的可序列化记录。"""

    type: ContextTransitionType
    from_target_key: str | None = None
    to_target_key: str | None = None
    archived_context_id: str | None = None
    restored_context_id: str | None = None
    reason: str | None = None


def switch_target_with_transition(
    conversation: ConversationState,
    *,
    new_target_key: str | None,
    reason: str,
) -> ContextTransition:
    """切换目标并返回 transition，不改变既有 reset_for_new_target 语义。"""
    previous_key = active_target_key(conversation)
    reset_for_new_target(conversation)
    archived_context_id = None
    if conversation.previous_purchase_contexts:
        archived_context_id = conversation.previous_purchase_contexts[0].canonical_target_key

    return ContextTransition(
        type=ContextTransitionType.SWITCH_TARGET,
        from_target_key=previous_key,
        to_target_key=new_target_key,
        archived_context_id=archived_context_id,
        reason=reason,
    )
