"""调试观察：显式模型说明、回合/阶段审计、/api/debug 认证与开关边界。"""

import hashlib
import json
import random
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from langrensha.ai import DecisionConfig, DecisionRunner, system_prompt
from langrensha.full_game import pending
from langrensha.presentation import debug_timeline
from langrensha.service import GameService
from langrensha.web import create_app
from langrensha.worldbooks import personas_for

HEADERS = {"X-Mist-Request": "1"}


class Model:
    def __init__(self, *responses):
        self.responses = iter(responses)

    def bind_tools(self, schemas):
        return self

    def invoke(self, messages, config):
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def reply(content="", *calls):
    return AIMessage(
        content=content,
        tool_calls=[
            {"name": name, "args": args, "id": f"call-{index}"}
            for index, (name, args) in enumerate(calls, 1)
        ],
    )


def command(view, tool, payload):
    return {
        "request_id": str(uuid4()),
        "phase_id": view["phase_id"],
        "expected_version": view["version"],
        "tool": tool,
        "payload": payload,
    }


def game_service(tmp_path):
    service = GameService(tmp_path / "debug.db")
    game_id = service.create(
        full=True, human_role="villager", rng=random.Random(9), worldbook="mist"
    )
    return service, game_id


def test_prompt_requests_visible_debug_statement_without_extra_secrets(tmp_path):
    service, game_id = game_service(tmp_path)
    view = service.bind_player(game_id, 1).view()
    prompt = system_prompt(view)
    assert "Web 调试观察" in prompt
    assert "不是公开发言" in prompt
    # 提示词只描述调试可见说明，不注入其他玩家秘密或未绑定信息。
    assert "隐藏推理" not in prompt


def test_runner_records_round_phase_and_visible_content_only(tmp_path):
    service, game_id = game_service(tmp_path)
    actor = pending(service.host_snapshot(game_id))[0]
    model = Model(reply("我先观察灯匠的证词。", ("wolf_vote", {"target": 1})))

    report = DecisionRunner(model).run(service.bind_player(game_id, actor))

    assert report["round"] == 1 and report["phase"] == "night_wolves"
    assert report["thinking"] == [
        {
            "step": 1,
            "content": "我先观察灯匠的证词。",
            "has_content": True,
            "tool_calls": [{"name": "wolf_vote", "args": {"target": 1}}],
        }
    ]
    assert "calls" not in report
    stored = service.host_decisions(game_id)[0]
    assert stored["round"] == 1 and stored["phase"] == "night_wolves"
    assert stored["thinking"] == report["thinking"]


def test_runner_does_not_invent_content_when_model_returns_empty(tmp_path):
    service, game_id = game_service(tmp_path)
    actor = pending(service.host_snapshot(game_id))[0]
    report = DecisionRunner(
        Model(AIMessage(content="   ", tool_calls=[])),
        DecisionConfig(max_rounds=1),
    ).run(service.bind_player(game_id, actor))

    assert report["reason"] == "thinking_rounds_exhausted"
    assert report["thinking"] == [
        {"step": 1, "content": "", "has_content": False, "tool_calls": []}
    ]


def test_runner_model_failure_has_no_thinking_and_no_provider_text(tmp_path):
    service, game_id = game_service(tmp_path)
    actor = pending(service.host_snapshot(game_id))[0]
    report = DecisionRunner(Model(RuntimeError("private-provider-secret"))).run(
        service.bind_player(game_id, actor)
    )

    assert report["reason"] == "model_unavailable"
    assert report["thinking"] == []
    assert "private-provider-secret" not in json.dumps(
        service.host_decisions(game_id), ensure_ascii=False
    )


def test_runner_window_closed_does_not_call_model_or_create_thinking(tmp_path):
    service, game_id = game_service(tmp_path)
    report = DecisionRunner(Model()).run(service.bind_player(game_id, 1))
    assert report["reason"] == "window_closed"
    assert report["thinking"] == []


def test_debug_timeline_uses_real_events_roles_and_personas(tmp_path):
    service, game_id = game_service(tmp_path)
    snapshot = service.host_snapshot(game_id)
    seats = pending(snapshot)[:3]
    wolf = service.bind_player(game_id, seats[0])
    wolf.submit(command(wolf.view(), "wolf_chat", {"text": "真实暗语-夜潮"}))

    first = reply("我记录灯匠的证词。", ("wolf_vote", {"target": 1}))
    DecisionRunner(Model(first)).run(service.bind_player(game_id, seats[0]))
    DecisionRunner(Model(RuntimeError("provider failed"))).run(
        service.bind_player(game_id, seats[1])
    )

    snapshot = service.host_snapshot(game_id)
    timeline = debug_timeline(snapshot, service.host_decisions(game_id))
    personas = personas_for("mist")

    assert [round_["round"] for round_ in timeline["rounds"]] == [1]
    phase = timeline["rounds"][0]["phases"][0]
    assert phase["phase"] == "night_wolves"
    assert phase["label"] == "夜裔密谈"
    assert [player["seat"] for player in phase["players"]] == seats[:2]
    first_player = phase["players"][0]
    assert first_player["name"] == personas[seats[0] - 1][0]
    assert first_player["role"] == "夜裔"
    assert first_player["alive"] is True
    assert first_player["decisions"][0]["thinking"][0]["content"] == "我记录灯匠的证词。"
    assert first_player["decisions"][0]["calls"][0]["tool"] == "wolf_vote"
    assert first_player["decisions"][0]["missing"] == []

    second_player = phase["players"][1]
    assert second_player["decisions"][0]["thinking"] == []
    assert second_player["decisions"][0]["missing"][0]["reason"] == "model_unavailable"
    assert timeline["missing"] == [
        {
            "seat": seats[1],
            "round": 1,
            "phase": "night_wolves",
            "reason": "model_unavailable",
            "label": "模型不可用，未返回显式说明",
        }
    ]

    chat = timeline["wolf_chat"][0]
    assert chat["round"] == 1
    assert chat["phase"] == "night_wolves"
    assert chat["seat"] == seats[0]
    assert chat["name"] == personas[seats[0] - 1][0]
    assert chat["text"] == "真实暗语-夜潮"
    assert chat["time"]


def test_debug_timeline_marks_empty_content_as_missing(tmp_path):
    service, game_id = game_service(tmp_path)
    actor = pending(service.host_snapshot(game_id))[0]
    DecisionRunner(
        Model(AIMessage(content="", tool_calls=[])),
        DecisionConfig(max_rounds=1),
    ).run(service.bind_player(game_id, actor))

    timeline = debug_timeline(
        service.host_snapshot(game_id), service.host_decisions(game_id)
    )
    decision = timeline["rounds"][0]["phases"][0]["players"][0]["decisions"][0]
    assert decision["thinking"][0]["has_content"] is False
    assert decision["missing"] == [{"reason": "no_content", "label": "模型未返回显式说明"}]
    assert timeline["missing"][0]["reason"] == "no_content"


def test_debug_endpoint_requires_login_and_strict_body(tmp_path):
    c, _ = client(tmp_path)
    assert c.get("/api/debug").status_code == 401
    assert c.post("/api/debug", json={"enabled": False}, headers=HEADERS).status_code == 401

    enter(c)
    assert c.get("/api/debug").json() == {
        "enabled": True,
        "game_id": None,
        "rounds": [],
        "wolf_chat": [],
        "missing": [],
    }
    for body in ({}, {"enabled": "false"}, {"enabled": 1}, {"enabled": True, "x": 1}, []):
        assert c.post("/api/debug", json=body, headers=HEADERS).status_code == 422


def client(tmp_path, runner=None):
    app = create_app(
        database=tmp_path / "web.db",
        access_token="only-test-password",
        runner=runner,
    )
    return TestClient(app), app


def enter(c):
    assert (
        c.post("/api/enter", json={"password": "only-test-password"}, headers=HEADERS).status_code
        == 200
    )


def test_web_debug_shows_real_ai_content_and_wolf_chat_but_state_does_not(tmp_path):
    model = Model(
        reply(
            "我先把暗语留给同伴。",
            ("wolf_chat", {"text": "真实暗语-夜潮"}),
            ("wolf_vote", {"target": 1}),
        )
    )
    c, app = client(tmp_path, DecisionRunner(model))
    enter(c)
    game = c.post("/api/game", json={"role": "villager"}, headers=HEADERS).json()
    assert c.get("/api/debug").json()["enabled"] is True
    assert c.post("/api/advance", json={}, headers=HEADERS).status_code == 200

    debug = c.get("/api/debug").json()
    assert debug["enabled"] is True and debug["game_id"] == game["game_id"]
    phase = debug["rounds"][0]["phases"][0]
    assert phase["phase"] == "night_wolves" and phase["label"] == "夜裔密谈"
    player = phase["players"][0]
    assert player["role"] == "夜裔"
    assert player["decisions"][0]["thinking"][0]["content"] == "我先把暗语留给同伴。"
    assert {call["tool"] for call in player["decisions"][0]["calls"]} == {
        "wolf_chat",
        "wolf_vote",
    }
    assert debug["wolf_chat"][0]["text"] == "真实暗语-夜潮"
    assert debug["wolf_chat"][0]["seat"] == player["seat"]
    assert debug["missing"] == []

    state = c.get("/api/state").json()
    encoded = json.dumps(state, ensure_ascii=False)
    assert "真实暗语-夜潮" not in encoded
    for key in ("thinking", "wolf_chat", "calls", "debug"):
        assert key not in encoded
    assert app.state.service.host_snapshot(game["game_id"])["worldbook"] == "mist"


def test_web_debug_off_hides_audit_and_on_restores_without_changing_game(tmp_path):
    model = Model(reply("我记录证词。", ("wolf_vote", {"target": 1})))
    c, _ = client(tmp_path, DecisionRunner(model))
    enter(c)
    game = c.post("/api/game", json={"role": "villager"}, headers=HEADERS).json()
    assert c.post("/api/advance", json={}, headers=HEADERS).status_code == 200
    before = c.get("/api/state").json()
    assert c.get("/api/debug").json()["rounds"]

    assert c.post("/api/debug", json={"enabled": False}, headers=HEADERS).json() == {
        "enabled": False
    }
    off = c.get("/api/debug").json()
    assert off["enabled"] is False and off["game_id"] == game["game_id"]
    assert off["rounds"] == [] and off["wolf_chat"] == [] and off["missing"] == []
    assert c.get("/api/state").json() == before

    assert c.post("/api/debug", json={"enabled": True}, headers=HEADERS).json() == {
        "enabled": True
    }
    on = c.get("/api/debug").json()
    assert on["enabled"] is True and on["rounds"]
    assert c.get("/api/state").json() == before
    assert c.get(f"/api/debug?game_id={game['game_id']}-other").json()["game_id"] == game["game_id"]


def test_legacy_sessions_table_migrates_debug_default_on(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE web_sessions ("
        "digest TEXT PRIMARY KEY, game_id TEXT, seat INTEGER NOT NULL DEFAULT 1)"
    )
    conn.execute(
        "INSERT INTO web_sessions(digest,game_id,seat) VALUES (?,NULL,1)",
        (hashlib.sha256(b"legacy-token").hexdigest(),),
    )
    conn.commit()
    conn.close()

    app = create_app(database=path)
    c = TestClient(app)
    c.cookies.set("mist_session", "legacy-token")
    response = c.get("/api/debug")
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    with app.state.service.store.transaction() as db:
        row = db.execute("SELECT debug FROM web_sessions").fetchone()
    assert row[0] == 1
