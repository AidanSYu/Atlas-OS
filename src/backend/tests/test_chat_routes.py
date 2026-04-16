"""Coverage for grounded Librarian/Cortex chat routing."""

from __future__ import annotations

import asyncio

from app.api import data_routes
from app.api.data_routes import ChatRequest, chat_query


class _StubChatService:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, user_question: str, project_id: str | None = None, mode: str = "librarian"):
        self.calls.append(
            {
                "user_question": user_question,
                "project_id": project_id,
                "mode": mode,
            }
        )
        return {
            "answer": "Grounded answer",
            "reasoning": "Cortex reviewed 2 text chunks, 1 graph nodes, and 1 graph edges.",
            "citations": [
                {
                    "source": "paper.pdf",
                    "page": 3,
                    "doc_id": "doc-1",
                    "text": "Example excerpt",
                }
            ],
            "relationships": [
                {
                    "source": "node-a",
                    "target": "node-b",
                    "type": "RELATES_TO",
                    "properties": {"weight": 0.8},
                }
            ],
            "context_sources": {
                "vector_chunks": 2,
                "graph_nodes": 1,
                "graph_edges": 1,
            },
        }


def test_chat_route_uses_grounded_chat_service(monkeypatch) -> None:
    stub = _StubChatService()
    monkeypatch.setattr(data_routes, "get_chat_service", lambda: stub)

    response = asyncio.run(
        chat_query(
            ChatRequest(
                query="Hi",
                project_id="project-123",
                mode="cortex",
                stage_context={"activeEpochId": "epoch-1", "activeStage": 2},
            )
        )
    )

    assert stub.calls == [
        {
            "user_question": "Hi",
            "project_id": "project-123",
            "mode": "cortex",
        }
    ]
    assert response.answer == "Grounded answer"
    assert response.citations[0].source == "paper.pdf"
    assert response.relationships[0].type == "RELATES_TO"
    assert response.context_sources["graph_edges"] == 1
