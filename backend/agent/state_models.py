"""Agent 状态字段的 typed helper。

这些模型只做兼容适配，不替换现有持久化 JSON 结构；ConversationState 仍保存 dict。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _clean_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _clean_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _clean_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        cleaned = _clean_str(value)
        return [cleaned] if cleaned else []
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        cleaned = _clean_str(item)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _clean_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    result: list[int] = []
    for item in value:
        cleaned = _clean_int(item)
        if cleaned is not None and cleaned not in result:
            result.append(cleaned)
    return result


class PurchasePreferences(BaseModel):
    """购买偏好的兼容模型，未知字段会原样写回。"""

    target_category: str | None = None
    category: str | None = None
    canonical_target_key: str | None = None
    display_target_category: str | None = None
    budget: int | None = None
    max_price: int | None = None
    brand: str | None = None
    preferred_brands: list[str] = Field(default_factory=list)
    focus: list[str] = Field(default_factory=list)
    price_direction: str | None = None
    price_preference: str | None = None
    avoid_current_price_band: bool | None = None
    is_broad_category_request: bool | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "PurchasePreferences":
        source = dict(data or {})
        known: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        for key, value in source.items():
            if key in cls.model_fields and key != "extra":
                known[key] = value
            else:
                extra[key] = value
        return cls(
            target_category=_clean_str(known.get("target_category")),
            category=_clean_str(known.get("category")),
            canonical_target_key=_clean_str(known.get("canonical_target_key")),
            display_target_category=_clean_str(known.get("display_target_category")),
            budget=_clean_int(known.get("budget")),
            max_price=_clean_int(known.get("max_price")),
            brand=_clean_str(known.get("brand")),
            preferred_brands=_clean_str_list(known.get("preferred_brands")),
            focus=_clean_str_list(known.get("focus")),
            price_direction=_clean_str(known.get("price_direction")),
            price_preference=_clean_str(known.get("price_preference")),
            avoid_current_price_band=_clean_bool(
                known.get("avoid_current_price_band")
            ),
            is_broad_category_request=_clean_bool(
                known.get("is_broad_category_request")
            ),
            extra=extra,
        )

    def to_dict(self, *, exclude_none: bool = True) -> dict[str, Any]:
        data = dict(self.extra)
        for key in (
            "target_category",
            "category",
            "canonical_target_key",
            "display_target_category",
            "budget",
            "max_price",
            "brand",
            "preferred_brands",
            "focus",
            "price_direction",
            "price_preference",
            "avoid_current_price_band",
            "is_broad_category_request",
        ):
            value = getattr(self, key)
            if value is None and exclude_none:
                continue
            if isinstance(value, list) and not value and exclude_none:
                continue
            data[key] = value
        return data

    def merge_updates(self, updates: Mapping[str, Any] | None) -> "PurchasePreferences":
        data = self.to_dict()
        for key, value in dict(updates or {}).items():
            if value is None:
                continue
            if key in {"preferred_brands", "focus"}:
                incoming = _clean_str_list(value)
                if not incoming:
                    continue
                current = _clean_str_list(data.get(key))
                data[key] = _merge_unique(current, incoming)
                continue
            if key in {"budget", "max_price"}:
                cleaned_int = _clean_int(value)
                if cleaned_int is not None:
                    data[key] = cleaned_int
                continue
            if key in {"avoid_current_price_band", "is_broad_category_request"}:
                cleaned_bool = _clean_bool(value)
                if cleaned_bool is not None:
                    data[key] = cleaned_bool
                continue
            if key in {
                "target_category",
                "category",
                "canonical_target_key",
                "display_target_category",
                "brand",
                "price_direction",
                "price_preference",
            }:
                cleaned_str = _clean_str(value)
                if cleaned_str is not None:
                    data[key] = cleaned_str
                continue
            # 未知字段是旧会话兼容边界：只跳过 None，其他值原样保留。
            data[key] = value
        return type(self).from_dict(data)


class NegativeUpdates(BaseModel):
    """负反馈更新的兼容模型，未知字段不会生效。"""

    excluded_item_indexes: list[int] = Field(default_factory=list)
    excluded_item_reference: Literal["current"] | None = None
    exclude_all_last_items: bool = False
    excluded_brands: list[str] = Field(default_factory=list)
    remove_excluded_brands: list[str] = Field(default_factory=list)
    remove_excluded_item_indexes: list[int] = Field(default_factory=list)
    unsupported_negative_type: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "NegativeUpdates":
        source = dict(data or {})
        reference = (
            "current" if source.get("excluded_item_reference") == "current" else None
        )
        return cls(
            excluded_item_indexes=_clean_int_list(source.get("excluded_item_indexes")),
            excluded_item_reference=reference,
            exclude_all_last_items=source.get("exclude_all_last_items") is True,
            excluded_brands=_clean_str_list(source.get("excluded_brands")),
            remove_excluded_brands=_clean_str_list(
                source.get("remove_excluded_brands")
            ),
            remove_excluded_item_indexes=_clean_int_list(
                source.get("remove_excluded_item_indexes")
            ),
            unsupported_negative_type=_clean_str(
                source.get("unsupported_negative_type")
            ),
        )

    def to_dict(self, *, exclude_empty: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.excluded_item_indexes or not exclude_empty:
            data["excluded_item_indexes"] = list(self.excluded_item_indexes)
        if self.excluded_item_reference is not None or not exclude_empty:
            data["excluded_item_reference"] = self.excluded_item_reference
        if self.exclude_all_last_items or not exclude_empty:
            data["exclude_all_last_items"] = self.exclude_all_last_items
        if self.excluded_brands or not exclude_empty:
            data["excluded_brands"] = list(self.excluded_brands)
        if self.remove_excluded_brands or not exclude_empty:
            data["remove_excluded_brands"] = list(self.remove_excluded_brands)
        if self.remove_excluded_item_indexes or not exclude_empty:
            data["remove_excluded_item_indexes"] = list(
                self.remove_excluded_item_indexes
            )
        if self.unsupported_negative_type is not None or not exclude_empty:
            data["unsupported_negative_type"] = self.unsupported_negative_type
        return data


class TurnResultState(BaseModel):
    """本轮执行结果写入 response.state 的小型 helper。"""

    latest_attempt_status: str | None = None
    latest_attempt_error: str | None = None
    result_status: str | None = None
    tool_error: str | None = None
    relax_options: list[str] = Field(default_factory=list)
    result_count: int | None = None

    def to_dict(self, *, exclude_empty: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key in (
            "latest_attempt_status",
            "latest_attempt_error",
            "result_status",
            "tool_error",
            "result_count",
        ):
            value = getattr(self, key)
            if value is None and exclude_empty:
                continue
            data[key] = value
        if self.relax_options or not exclude_empty:
            data["relax_options"] = list(self.relax_options)
        return data


def _merge_unique(current: list[Any], updates: list[Any]) -> list[Any]:
    merged: list[Any] = []
    for item in [*current, *updates]:
        if item not in merged:
            merged.append(item)
    return merged
