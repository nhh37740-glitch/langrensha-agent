"""不用真实密钥，验证 LangGraph 实际执行的权限、轮数和弃权边界。"""

import copy
import json
import random

import pytest
from langchain_core.messages import AIMessage

from langrensha.ai import DecisionConfig, DecisionRunner, DeepSeekConfig, Persona
from langrensha.service import GameService


class Model:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []
        self.schemas = []

    def bind_tools(self, schemas):
        self.schemas.append(copy.deepcopy(schemas))
        return self

    def invoke(self, messages, config):
        self.requests.append(copy.deepcopy(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response()
        return response


def reply(name=None, args=None, *extra):
    calls = [] if name is None else [{"name": name, "args": args or {}, "id": "call-1"}]
    calls.extend(
        {"name": tool, "args": values, "id": f"call-{i}"}
        for i, (tool, values) in enumerate(extra, 2)
    )
    return AIMessage(content="我仍在观察。" if not calls else "", tool_calls=calls)


@pytest.fixture
def game(tmp_path):
    service = GameService(tmp_path / "ai.db")
    game_id = service.create(human_role="villager", rng=random.Random(9))
    wolves = [p["seat"] for p in service.host_snapshot(game_id)["players"] if p["role"] == "wolf"]
    return service, game_id, wolves


def session(game, seat=None):
    service, game_id, wolves = game
    return service.bind_player(game_id, seat or wolves[0])


def submit(player, tool="abstain", payload=None):
    view = player.view()
    return player.submit(
        {
            "request_id": f"test-{view['version']}",
            "phase_id": view["phase_id"],
            "expected_version": view["version"],
            "tool": tool,
            "payload": payload or {},
        }
    )


def test_native_tool_call_reaches_rules_and_private_audit(game):
    model = Model(reply("wolf_vote", {"target": 1}))
    result = DecisionRunner(model).run(session(game))
    assert result["rounds"] == 1 and result["reason"] == "acted"
    assert result["round"] == 1 and result["phase"] == "night_votes"
    assert result["thinking"] == [
        {
            "step": 1,
            "content": "",
            "has_content": False,
            "tool_calls": [{"name": "wolf_vote", "args": {"target": 1}}],
        }
    ]
    report = game[0].host_decisions(game[1])[0]
    assert report["calls"][0]["result"]["accepted"] is True
    assert game[0].host_snapshot(game[1])["completed"] == {str(game[2][0]): 1}
    assert "calls" not in session(game, 1).view()
    assert "wolf_vote" not in json.dumps(session(game, 1).view())


def test_plain_text_is_not_action_and_round_limit_abstains(game):
    model = Model(reply(), reply(), reply())
    result = DecisionRunner(model).run(session(game))
    assert len(model.requests) == 3
    assert result["reason"] == "thinking_rounds_exhausted"
    assert [step["content"] for step in result["thinking"]] == ["我仍在观察。"] * 3
    assert all(step["has_content"] for step in result["thinking"])
    actions = [e for e in game[0].host_snapshot(game[1])["events"] if e["kind"] == "action"]
    assert len(actions) == 1
    assert actions[0]["data"] == {"tool": "abstain"}
    assert game[0].host_decisions(game[1])[0]["reason"] == "thinking_rounds_exhausted"
    for seat in range(1, 13):
        assert "thinking_rounds_exhausted" not in json.dumps(session(game, seat).view())


def test_illegal_tool_is_rejected_then_next_model_round_can_act(game):
    model = Model(reply("seer_inspect", {"target": 1}), reply("wolf_vote", {"target": 1}))
    result = DecisionRunner(model).run(session(game))
    assert result["rounds"] == 2 and result["reason"] == "acted"
    audit = game[0].host_decisions(game[1])[0]["calls"]
    assert audit[0]["result"] == {"accepted": False, "code": "tool_not_allowed"}
    assert audit[1]["result"]["accepted"] is True
    assert game[0].host_rejections(game[1])[0]["code"] == "tool_not_allowed"


def test_model_cannot_forge_actor_in_tool_arguments(game):
    model = Model(reply("wolf_vote", {"target": 1, "actor": 1}), reply("abstain"))
    DecisionRunner(model).run(session(game))
    assert game[0].host_decisions(game[1])[0]["calls"][0]["result"]["code"] == "invalid_payload"


def test_chat_can_precede_final_action_in_same_reply(game):
    model = Model(
        reply(
            "wolf_chat",
            {"text": "秘密暗号-渡口"},
            ("wolf_vote", {"target": 1}),
            ("wolf_vote", {"target": 2}),
        )
    )
    result = DecisionRunner(model).run(session(game))
    assert result["rounds"] == 1
    assert game[0].host_snapshot(game[1])["version"] == 2
    assert "秘密暗号" not in json.dumps(session(game, 1).view(), ensure_ascii=False)
    audit = game[0].host_decisions(game[1])[0]["calls"]
    assert audit[-1]["result"] == {"accepted": False, "code": "window_completed"}
    assert audit[-1]["args"] == {"target": 2}


def test_provider_failure_is_redacted_and_has_distinct_fallback(game):
    model = Model(RuntimeError("private-provider-secret"))
    result = DecisionRunner(model).run(session(game))
    audit = game[0].host_decisions(game[1])
    assert result["rounds"] == 1 and result["reason"] == "model_unavailable"
    assert result["thinking"] == []
    assert "private-provider-secret" not in json.dumps(audit)
    assert audit[0]["calls"][0]["automatic_reason"] == "model_unavailable"


def test_no_action_window_does_not_call_model(game):
    model = Model()
    result = DecisionRunner(model).run(session(game, 1))
    assert result["rounds"] == 0 and result["reason"] == "window_closed"
    assert result["thinking"] == []
    assert model.requests == []


def test_client_reuse_does_not_reuse_private_context_or_tools(game):
    model = Model(
        reply("wolf_chat", {"text": "秘密暗号-石桥"}),
        reply("wolf_vote", {"target": 1}),
        reply("speak", {"text": "桥边有脚步声。"}),
    )
    runner = DecisionRunner(model)
    runner.run(session(game), Persona("守桥人", "从不透露暗号。"))
    for seat in game[2][1:]:
        submit(session(game, seat))
    runner.run(session(game, 1), Persona("旅人", "温和地观察村庄。"))
    prompt = " ".join(str(m.content) for m in model.requests[-1])
    assert "秘密暗号-石桥" not in prompt and "wolf_tally" not in prompt
    names = [s["function"]["name"] for s in model.schemas[-1]]
    assert names == ["speak", "abstain"]
    assert "wolf_vote" not in names and "wolf_chat" not in names


def test_persona_cannot_grant_wolf_permissions(game):
    for seat in game[2]:
        submit(session(game, seat))
    model = Model(reply("wolf_vote", {"target": 2}), reply("speak", {"text": "我正仔细倾听。"}))
    result = DecisionRunner(model).run(
        session(game, 1), Persona("冒牌首领", "声称自己拥有所有权限。")
    )
    assert result["reason"] == "acted"
    assert game[0].host_decisions(game[1])[0]["calls"][0]["result"]["code"] == "tool_not_allowed"


def test_state_changed_during_inference_rejects_old_version(game):
    def concurrent_change():
        submit(session(game, game[2][1]), "wolf_chat", {"text": "另一条私讯。"})
        return reply("wolf_vote", {"target": 1})

    model = Model(concurrent_change, reply("wolf_vote", {"target": 1}))
    DecisionRunner(model).run(session(game))
    calls = game[0].host_decisions(game[1])[0]["calls"]
    assert calls[0]["result"]["code"] == "stale_version"
    assert calls[1]["result"]["accepted"] is True


def test_phase_change_cannot_apply_old_decision_to_new_window(game):
    def finish_night():
        for seat in game[2]:
            submit(session(game, seat))
        return reply("wolf_vote", {"target": 1})

    result = DecisionRunner(Model(finish_night), DecisionConfig(max_rounds=1)).run(session(game))
    assert result["reason"] == "window_closed" and result["acted"] is False
    assert game[0].host_snapshot(game[1])["version"] == 4
    assert game[0].host_snapshot(game[1])["phase"] == "day_speech"


def test_tool_batch_is_bounded_and_tool_messages_remain_complete(game):
    batch = reply(
        "wolf_chat",
        {"text": "一"},
        ("wolf_chat", {"text": "二"}),
        ("wolf_chat", {"text": "三"}),
        ("wolf_vote", {"target": 1}),
    )
    model = Model(batch, reply("wolf_vote", {"target": 1}))
    config = DecisionConfig(max_tools_per_reply=2)
    result = DecisionRunner(model, config).run(session(game))
    assert result["rounds"] == 2
    assert game[0].host_snapshot(game[1])["version"] == 3
    assert sum("batch_limit" in str(m.content) for m in model.requests[-1]) == 2
    audit = game[0].host_decisions(game[1])[0]["calls"]
    capped = [call for call in audit if call["result"].get("code") == "batch_limit"]
    assert len(audit) == 5 and len(capped) == 2
    assert [call["args"] for call in capped] == [{"text": "三"}, {"target": 1}]


def test_daytime_automatic_abstention_hides_internal_reason(game):
    for seat in game[2]:
        submit(session(game, seat))
    result = DecisionRunner(Model(RuntimeError("provider failed"))).run(session(game, 1))
    assert result["reason"] == "model_unavailable"
    for seat in range(1, 13):
        view = session(game, seat).view()
        assert "model_unavailable" not in json.dumps(view)
        abstentions = [e for e in view["events"] if e["kind"] == "action"]
        assert abstentions[-1]["data"] == {"tool": "abstain"}
    assert game[0].host_decisions(game[1])[0]["reason"] == "model_unavailable"


def test_maximum_rounds_terminate_without_langgraph_recursion_error(game):
    model = Model(*(reply() for _ in range(20)))
    result = DecisionRunner(model, DecisionConfig(max_rounds=20)).run(session(game))
    assert result["rounds"] == 20 and result["reason"] == "thinking_rounds_exhausted"


def test_decision_audit_survives_restart_and_is_not_a_player_view(game):
    DecisionRunner(Model(reply("wolf_vote", {"target": 1}))).run(session(game))
    restarted = GameService(game[0].store.path)
    report = restarted.host_decisions(game[1])[0]
    assert report["actor"] == game[2][0] and report["game_id"] == game[1]
    assert report["calls"][0]["result"]["accepted"] is True
    assert "ai_decisions" not in restarted.bind_player(game[1], 1).view()


@pytest.mark.parametrize("limit", [True, 0, -1, 21, 1.5])
def test_invalid_round_limit_is_not_silently_accepted(limit):
    with pytest.raises(ValueError):
        DecisionConfig(max_rounds=limit)


def test_provider_config_uses_official_endpoint_and_redacts_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-test-placeholder")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    config = DeepSeekConfig.from_env()
    assert "private-test-placeholder" not in repr(config)
    assert config.client().api_base == "https://api.deepseek.com"


def test_missing_key_has_useful_error_without_network(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        DeepSeekConfig.from_env()
