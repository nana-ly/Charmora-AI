"""Prompt 模板加载器。"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
import logging

logger = logging.getLogger(__name__)

DEFAULT_UNDERSTANDING_PROMPT = (
    "你是电商导购 Agent 的用户意图理解器。\n"
    "Return one JSON object only. Do not use Markdown. Do not explain.\n"
    "Do not invent product cards. Product recommendations come only from tools.\n"
    "intent 只能是 recommend、update_preference、explain、compare、clarify。\n"
    "如果用户询问上一轮第几个商品，target_item_index 使用 1-based 序号。\n"
    "如果用户要求比较上一轮多个商品，intent=compare，compare_item_indexes 使用 1-based 序号列表。\n"
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
    "Always include confidence, purchase_need, preference_updates, negative_updates, target_item_index, compare_item_indexes, clarifying_question, "
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


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    content: str


def load_prompt(name: str) -> PromptTemplate:
    """从包内 markdown 读取 prompt，失败时回退到内置默认版本。"""
    try:
        content = (
            resources.files("agent.prompts")
            .joinpath(f"{name}.md")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        logger.warning("prompt load failed name=%s error=%s", name, type(exc).__name__)
        return PromptTemplate(version=name, content=DEFAULT_UNDERSTANDING_PROMPT)
    return PromptTemplate(version=name, content=content)
