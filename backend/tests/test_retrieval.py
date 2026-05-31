from retrieval.base import RetrievalResult, Retriever
from retrieval.keyword import KeywordRetriever, build_searchable_text
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
    assert results[0].rank is None
    assert results[0].source is None
    assert results[0].retriever_mode is None
    assert results[0].score_type is None
    assert results[0].metadata == {}


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


def test_keyword_retriever_prioritizes_requested_product_type():
    retriever = KeywordRetriever()
    candidates = [
        {
            "product_id": "p_tablet",
            "title": "小米平板 12.1英寸高刷大屏平板电脑",
            "brand": "小米",
            "category": "数码电子",
            "sub_category": "平板电脑",
            "base_price": 3299,
            "rag_knowledge": {"marketing_description": "支持和手机跨屏互联。"},
        },
        {
            "product_id": "p_phone",
            "title": "OPPO Reno 轻薄人像摄影5G智能手机",
            "brand": "OPPO",
            "category": "数码电子",
            "sub_category": "智能手机",
            "base_price": 3299,
            "rag_knowledge": {"marketing_description": "适合人像摄影和日常拍摄。"},
        },
    ]

    results = retriever.search("预算9000以内的拍照手机", candidates=candidates, top_k=1)

    assert results[0].product["product_id"] == "p_phone"
    assert results[0].score >= 2


def test_keyword_retriever_returns_retrieval_results():
    retriever = KeywordRetriever()

    results = retriever.search(
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

    assert results[0].product["product_id"] == "p_1"
    assert results[0].evidence == "临时匹配：命中 手机、拍照；来自结构化筛选结果。"
    assert results[0].score >= 1
    assert results[0].rank == 1
    assert results[0].source == "keyword"
    assert results[0].retriever_mode == "keyword"
    assert results[0].score_type == "keyword_weighted_match"
    assert results[0].metadata["matched_terms"] == ["手机", "拍照"]


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


class FakeVectorStore:
    def query_by_text(self, query: str, top_k: int = 5):
        return [
            {
                "product_id": "p_1",
                "score": 0.92,
                "document": "标题：拍照旗舰手机\n营销描述：适合拍照和剪视频。",
                "metadata": {
                    "product_id": "p_1",
                    "title": "拍照旗舰手机",
                    "brand": "Apple",
                    "category": "数码电子",
                },
            }
        ]


def test_vector_retriever_maps_rag_results_to_retrieval_results():
    product = {
        "product_id": "p_1",
        "title": "拍照旗舰手机",
        "brand": "Apple",
        "category": "数码电子",
        "base_price": 8999,
    }
    retriever = VectorRetriever(store=FakeVectorStore())

    results = retriever.search("想买拍照好的手机", candidates=[product], top_k=1)

    assert len(results) == 1
    assert results[0].product == product
    assert results[0].evidence.startswith("向量召回")
    assert results[0].score == 0.92
    assert results[0].rank == 1
    assert results[0].source == "vector"
    assert results[0].retriever_mode == "vector"
    assert results[0].score_type == "vector_similarity"
    assert results[0].metadata["document_preview"] == "标题：拍照旗舰手机 营销描述：适合拍照和剪视频。"


def test_vector_retriever_returns_empty_results_for_empty_candidates():
    retriever = VectorRetriever(store=FakeVectorStore())

    results = retriever.search("想买拍照好的手机", candidates=[], top_k=1)

    assert results == []

