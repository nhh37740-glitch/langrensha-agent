from langchain_core.messages import AIMessage

from langrensha.assistant import assist


class NoteModel:
    def __init__(self, sources=None):
        self.sources = sources or ["event:3"]

    def bind_tools(self, tools):
        assert [t["function"]["name"] for t in tools] == ["compose_note"]
        return self

    def invoke(self, messages, config):
        self.context = messages[-1].content
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "note",
                    "name": "compose_note",
                    "args": {
                        "text": "他先提到灯下所见，随后承认并不确定。",
                        "sources": self.sources,
                    },
                }
            ],
        )


def test_summary_uses_visible_sources_without_acting():
    evidence = {
        "answer": "原文",
        "method": "extractive_retrieval",
        "sources": [{"source": "event:3", "text": "我没看清。", "actor": 2, "round": 1}],
    }
    model = NoteModel()
    result = assist(model, "summarize_player", {"seat": 2}, evidence)
    assert result["method"] == "grounded_model_note"
    assert result["sources"] == evidence["sources"]
    assert "SECRET" not in model.context
    assert assist(NoteModel(["event:404"]), "speech_hint", {}, evidence) == evidence


def test_unavailable_model_keeps_grounded_extracts():
    class Broken:
        def bind_tools(self, tools):
            raise RuntimeError("SECRET provider body")

    original = {"answer": "原文摘录", "sources": [{"source": "world:bell", "text": "铜铃"}]}
    assert assist(Broken(), "ask_world", {"question": "铜铃"}, original) == original
