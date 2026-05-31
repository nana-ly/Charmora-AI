"""LangGraph 节点的会话状态归约逻辑。"""

from __future__ import annotations

from dataclasses import dataclass

from agent.context_manager import (
    ConversationCommand,
    active_target_key,
    confirm_restore,
    reject_restore,
    reset_for_new_target,
)
from agent.memory import ConversationState
from agent.negative_feedback import (
    apply_negative_feedback,
    filter_item_index_negative_updates_for_current_target,
    migrate_legacy_excluded_brands,
)
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.state_models import NegativeUpdates
from agent.understanding import UserIntent, UserUnderstanding
from recommendation_core.data import products as default_catalog_products
from schemas.product import ProductCard

ITEM_SCOPED_NEGATIVE_UPDATE_KEYS = {
    "excluded_item_indexes",
    "excluded_item_reference",
    "exclude_all_last_items",
}


@dataclass
class StateReductionResult:
    conversation: ConversationState
    understanding: UserUnderstanding
    negative_feedback_result: NegativeFeedbackApplicationResult
    current_turn_is_broad: bool


class ConversationStateReducer:
    """把理解结果落到会话状态，避免 Runner 继续承载状态细节。"""

    def __init__(
        self,
        *,
        catalog_products: list[ProductCard | dict] | None = None,
    ) -> None:
        self.catalog_products = catalog_products or default_catalog_products

    def reduce(
        self,
        *,
        conversation: ConversationState,
        understanding: UserUnderstanding,
        restore_command: ConversationCommand | None = None,
    ) -> StateReductionResult:
        active_key_before = active_target_key(conversation)
        active_items_before = list(conversation.last_successful_items)
        current_turn_is_broad = (
            understanding.intent == UserIntent.RECOMMEND
            and understanding.preference_updates.get("is_broad_category_request") is True
        )
        # broad 是“本轮是否泛品类推荐”的瞬时语义；细化预算/品牌时必须写回 False。
        if understanding.intent in {UserIntent.RECOMMEND, UserIntent.UPDATE_PREFERENCE}:
            understanding.preference_updates["is_broad_category_request"] = (
                current_turn_is_broad
            )

        filtered_negative_updates = self._filtered_negative_updates(
            conversation=conversation,
            understanding=understanding,
            active_key_before=active_key_before,
            active_items_before=active_items_before,
        )

        if restore_command == ConversationCommand.CONFIRM_RESTORE:
            restored_understanding = confirm_restore(conversation)
            conversation.last_intent = restored_understanding.intent.value
            negative_feedback_result = apply_negative_feedback(
                conversation,
                restored_understanding.negative_updates,
                catalog_products=self.catalog_products,
            )
            return StateReductionResult(
                conversation=conversation,
                understanding=restored_understanding,
                negative_feedback_result=negative_feedback_result,
                current_turn_is_broad=current_turn_is_broad,
            )

        if restore_command == ConversationCommand.REJECT_RESTORE:
            reject_restore(conversation)

        current_target_key = self._current_target_key(
            understanding,
            active_key_before=active_key_before,
        )
        canonical_target_changed = (
            current_target_key is not None
            and active_key_before is not None
            and current_target_key != active_key_before
        )
        effective_reset = canonical_target_changed or (
            understanding.reset_context and current_target_key is None
        )
        # reset_context 是旧版理解状态；标准目标变化会自行重置。
        if effective_reset:
            reset_for_new_target(conversation)

        if understanding.purchase_need:
            conversation.purchase_need = understanding.purchase_need
        if understanding.target_item_index is not None:
            conversation.target_item_index = understanding.target_item_index

        self._merge_preferences(conversation, understanding.preference_updates)
        migrate_legacy_excluded_brands(conversation)
        negative_feedback_result = apply_negative_feedback(
            conversation,
            filtered_negative_updates,
            catalog_products=self.catalog_products,
        )
        conversation.last_intent = understanding.intent.value
        return StateReductionResult(
            conversation=conversation,
            understanding=understanding,
            negative_feedback_result=negative_feedback_result,
            current_turn_is_broad=current_turn_is_broad,
        )

    def _filtered_negative_updates(
        self,
        *,
        conversation: ConversationState,
        understanding: UserUnderstanding,
        active_key_before: str | None,
        active_items_before: list[ProductCard],
    ) -> dict:
        negative_updates = NegativeUpdates.from_dict(
            understanding.negative_updates
        ).to_dict()
        current_target_key = self._current_target_key(
            understanding,
            active_key_before=active_key_before,
        )
        return filter_item_index_negative_updates_for_current_target(
            negative_updates,
            current_target_key,
            active_key_before,
            active_items_before,
        )

    def _current_target_key(
        self,
        understanding: UserUnderstanding,
        *,
        active_key_before: str | None,
    ) -> str | None:
        updates = understanding.preference_updates
        current_target_key = updates.get("canonical_target_key")
        if not isinstance(current_target_key, str):
            current_target_key = None
        negative_update_keys = set(NegativeUpdates.from_dict(understanding.negative_updates).to_dict())
        if (
            current_target_key is None
            and negative_update_keys
            and negative_update_keys.issubset(ITEM_SCOPED_NEGATIVE_UPDATE_KEYS)
        ):
            return active_key_before
        return current_target_key

    def _merge_preferences(
        self,
        conversation: ConversationState,
        updates: dict,
    ) -> None:
        model = conversation.preferences_model().merge_updates(updates)
        conversation.apply_preferences_model(model)
