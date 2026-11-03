"""四世界称谓一致：提示词、工具描述、札记与展示共用世界书术语，不做机械改写。"""

from langchain_core.messages import AIMessage

from langrensha import ai, assistant, presentation
from langrensha.worldbooks import get_worldbook, worldbook_ids

TERMS = {
    "mist": ("铜铃", "星兆"),
    "hyperion": ("灯盏", "时隙残影"),
    "threebody": ("执剑权限", "信号"),
    "tidal_archive": ("潮钟钥匙", "潮影"),
}

# 脱敏公开对白：只含座位、主张与依据，不含身份秘密、私聊或后台信息。
PUBLIC_DIALOGUE = (
    "6号接过铜铃后说，先核对7号的证词。",
    "2号认为3号昨夜没有离开房间，4号提醒这只能说明3号当时在场。",
)


def view(worldbook, role="villager"):
    return {
        "worldbook": worldbook,
        "role": role,
        "round": 1,
        "phase": "day_speech",
        "events": [],
        "winner": None,
    }


def test_system_prompt_and_tool_schemas_use_each_world_terms():
    for worldbook in worldbook_ids():
        bell, vision = TERMS[worldbook]
        book = get_worldbook(worldbook)
        prompt = ai.system_prompt(view(worldbook))
        assert book["name"] in prompt
        assert bell in prompt and vision in prompt
        assert "狼人杀" in prompt
        descriptions = {
            item["function"]["name"]: item["function"]["description"]
            for item in ai.tool_schemas(["signup", "transfer_badge", "explode"], worldbook)
        }
        assert bell in descriptions["signup"]
        assert bell in descriptions["transfer_badge"]
        assert book["roles"]["wolf"] in descriptions["explode"]
        if worldbook != "mist":
            assert "铜铃" not in prompt and "星兆" not in prompt
            assert "铜铃" not in "".join(descriptions.values())


class NoteModel:
    def __init__(self, text):
        self.text = text

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, config):
        self.system = messages[0].content
        self.context = messages[-1].content
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "note",
                    "name": "compose_note",
                    "args": {"text": self.text, "sources": ["event:1"]},
                }
            ],
        )


def test_assistant_uses_world_context_without_rewriting_model_text():
    evidence = {
        "answer": "原文",
        "method": "extractive_retrieval",
        "sources": [{"source": "event:1", "text": "我没看清。", "actor": 2, "round": 1}],
    }
    model = NoteModel("2号对3号的查杀，先看警徽。")
    result = assistant.assist(
        model, "summarize_player", {"seat": 2}, evidence, view("threebody")
    )
    assert "三体" in model.system
    assert "执剑权限" in model.system and "信号" in model.system
    assert "雾钟镇" not in model.system
    assert result["answer"] == "2号对3号的查杀，先看警徽。"
    assert "星兆" not in result["answer"]


def test_assistant_without_view_keeps_mist_default():
    evidence = {
        "answer": "原文",
        "method": "extractive_retrieval",
        "sources": [{"source": "event:1", "text": "我没看清。", "actor": 2, "round": 1}],
    }
    model = NoteModel("先听6号说完。")
    assistant.assist(model, "summarize_player", {"seat": 2}, evidence)
    assert "雾钟镇" in model.system
    assert "铜铃" in model.system and "星兆" in model.system


def test_story_and_notes_share_the_same_worldbook_terms():
    for worldbook in worldbook_ids():
        book = get_worldbook(worldbook)
        theme = presentation._theme_for(worldbook)
        assert theme["bell"] == book["terms"]["bell"]
        assert theme["vision"] == book["terms"]["vision"]
        shown = presentation.story_language(PUBLIC_DIALOGUE[0], theme["jargon"])
        assert book["terms"]["bell"] in shown
        if worldbook != "mist":
            assert "铜铃" not in shown


def test_public_dialogue_is_not_mechanically_rewritten():
    for worldbook in worldbook_ids():
        theme = presentation._theme_for(worldbook)
        assert presentation.story_language(PUBLIC_DIALOGUE[1], theme["jargon"]) == (
            PUBLIC_DIALOGUE[1]
        )
    assert presentation.story_language("2号对3号的查杀。") == "2号对3号的查杀。"
