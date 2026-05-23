import pytest

from retrieval.base import RetrievalResult, Retriever
from retrieval.keyword import KeywordRetriever, build_searchable_text, retrieve
from retrieval.vector import VectorRetriever


class DummyRetriever(Retriever):
    def search(
        self,
        query: str,
        candidates: list[dict] | None = None,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                product={"product_id": "p_dummy", "title": query},
                evidence="测试检索器返回。",
                score=1.0,
            )
        ]


def test_retriever_interface_returns_retrieval_results():
    retriever = DummyRetriever()

    results = retriever.search("测试需求")

    assert results[0].product["product_id"] == "p_dummy"
    assert results[0].evidence == "测试检索器返回。"
    assert results[0].score == 1.0


def test_keyword_retriever_searches_candidates_with_evidence():
    retriever = KeywordRetriever()
    candidates = [
        {
            "product_id": "p_1",
            "title": "拍照旗舰手机",
            "brand": "Apple",
            "category": "数码电子",
            "base_price": 8999,
        },
        {
            "product_id": "p_2",
            "title": "降噪耳机",
            "brand": "Sony",
            "category": "数码电子",
            "base_price": 1999,
        },
    ]

    results = retriever.search("想买拍照好的手机", candidates=candidates, top_k=1)

    assert len(results) == 1
    assert results[0].product["product_id"] == "p_1"
    assert results[0].evidence.startswith("临时匹配")
    assert results[0].score >= 1


def test_keyword_retriever_keeps_legacy_retrieve_shape():
    results = retrieve(
        "想买拍照好的手机",
        candidates=[
            {
                "product_id": "p_1",
                "title": "拍照旗舰手机",
                "brand": "Apple",
                "category": "数码电子",
                "base_price": 8999,
            }
        ],
        top_k=1,
    )

    assert results == [
        {
            "product": {
                "product_id": "p_1",
                "title": "拍照旗舰手机",
                "brand": "Apple",
                "category": "数码电子",
                "base_price": 8999,
            },
            "evidence": "临时匹配：命中 手机、拍照；来自结构化筛选结果。",
        }
    ]


def test_build_searchable_text_includes_product_fields():
    text = build_searchable_text(
        {
            "title": "轻薄办公电脑",
            "brand": "小米",
            "category": "数码电子",
            "sub_category": "笔记本",
            "rag_knowledge": {"marketing_description": "适合学生办公"},
        }
    )

    assert "轻薄办公电脑" in text
    assert "小米" in text
    assert "适合学生办公" in text


def test_vector_retriever_is_explicit_placeholder():
    retriever = VectorRetriever()

    with pytest.raises(NotImplementedError, match="向量检索"):
        retriever.search("测试需求")

