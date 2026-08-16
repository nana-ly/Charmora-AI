from __future__ import annotations

from uuid import UUID

from agent.memory import ConversationState
from agent.understanding import ActionResult, AgentAction, UserUnderstanding
from db.session import DatabaseRuntime
from services.commerce_service import CommerceService
from schemas.commerce import CreateOrderRequest


class CommerceTool:
    """Deterministic bridge from Agent actions to transactional commerce services."""

    def __init__(self, database: DatabaseRuntime) -> None:
        self.database = database

    def run(
        self,
        action: AgentAction,
        conversation: ConversationState,
        understanding: UserUnderstanding,
    ) -> ActionResult:
        with self.database.session_factory() as session:
            service = CommerceService(session)
            if action == AgentAction.VIEW_CART:
                cart = service.get_cart(conversation.session_id)
                return self._result(action, "cart_reply", cart.model_dump(mode="json"))
            if action == AgentAction.ADD_TO_CART:
                index = understanding.target_item_index or 1
                if index > len(conversation.last_items):
                    return ActionResult(
                        action=action,
                        reply_type="clarify_reply",
                        clarifying_question="请告诉我要加入购物车的是哪一款商品。",
                    )
                item = conversation.last_items[index - 1]
                if not item.sku_id:
                    return ActionResult(
                        action=action,
                        reply_type="commerce_error_reply",
                        commerce_state={"code": "sku_unavailable"},
                    )
                cart = service.add_item(
                    conversation.session_id,
                    UUID(item.sku_id),
                    understanding.quantity,
                )
                return self._result(action, "cart_updated_reply", cart.model_dump(mode="json"))
            if action == AgentAction.CHECKOUT:
                if not understanding.checkout_confirmed:
                    preview = service.preview_checkout(conversation.session_id)
                    conversation.pending_checkout_token = preview.confirmation_token
                    return self._result(
                        action,
                        "checkout_preview_reply",
                        preview.model_dump(mode="json"),
                    )
                if not conversation.pending_checkout_token:
                    return ActionResult(
                        action=action,
                        reply_type="clarify_reply",
                        clarifying_question="请先查看结算预览，再明确说“确认下单”。",
                    )
                request = CreateOrderRequest(
                    session_id=conversation.session_id,
                    confirmation_token=conversation.pending_checkout_token,
                    idempotency_key=f"agent-{conversation.session_id}-{conversation.pending_checkout_token}",
                )
                order = service.checkout(conversation.session_id, request)
                conversation.last_order_id = str(order.id)
                conversation.pending_checkout_token = None
                return self._result(action, "order_created_reply", order.model_dump(mode="json"))

            order_id = understanding.order_id or conversation.last_order_id
            if not order_id:
                return ActionResult(
                    action=action,
                    reply_type="clarify_reply",
                    clarifying_question="请提供订单号。",
                )
            if action == AgentAction.ORDER_STATUS:
                order = service.get_order(UUID(order_id))
                return self._result(action, "order_status_reply", order.model_dump(mode="json"))
            order = service.cancel_order(UUID(order_id))
            conversation.last_order_id = str(order.id)
            return self._result(action, "order_cancelled_reply", order.model_dump(mode="json"))

    @staticmethod
    def _result(action: AgentAction, reply_type: str, state: dict) -> ActionResult:
        return ActionResult(action=action, reply_type=reply_type, commerce_state=state)
