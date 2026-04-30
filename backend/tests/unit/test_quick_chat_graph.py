from app.chat.graphs.types import QuickGraphState


def test_quick_graph_state_minimal_fields():
    state: QuickGraphState = {
        "message": "hello",
        "knowledge_base_ids": [],
        "attempts": [],
        "hits": [],
        "events": [],
    }
    assert state["message"] == "hello"


async def test_quick_graph_returns_answer_and_citations():
    from app.chat.graphs.quick_chat_graph import run_quick_graph

    result = await run_quick_graph(
        message="什么是RAG",
        knowledge_base_ids=[],
        retriever=lambda *_args, **_kwargs: [],
        answer_generator=lambda question, context, has_hits: f"A:{question}|{has_hits}",
    )
    assert result.answer.startswith("A:")
    assert isinstance(result.citations, list)
