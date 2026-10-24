import json
import random
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from langrensha.ai import DecisionConfig, DecisionRunner
from langrensha.full_game import pending
from langrensha.presentation import present
from langrensha.rules import Rejected
from langrensha.service import GameService
from langrensha.web import create_app

HEADERS = {"X-Mist-Request": "1"}


def command(view, tool, payload):
    return {
        "request_id": str(uuid4()),
        "phase_id": view["phase_id"],
        "expected_version": view["version"],
        "tool": tool,
        "payload": payload,
    }


def test_retrieval_filters_before_search_and_keeps_sources(tmp_path):
    service = GameService(tmp_path / "g.db")
    gid = service.create(full=True, human_role="villager", rng=random.Random(9))
    snapshot = service.host_snapshot(gid)
    wolf = service.bind_player(gid, pending(snapshot)[0])
    ordinary = service.bind_player(gid, 1)
    wolf.submit(command(wolf.view(), "wolf_chat", {"text": "SECRET 独有词，今夜选灯匠"}))
    query = {"query": "SECRET"}
    assert "SECRET" in wolf.query("search_history", query)["answer"]
    assert "SECRET" not in ordinary.query("search_history", query)["answer"]
    assert ordinary.query("search_history", query)["sources"] == []
    assert wolf.query("search_history", query)["sources"][0]["source"].startswith("event:")
    assert "SECRET" not in ordinary.query("speech_hint", {})["answer"]
    assert "SECRET" not in json.dumps(present(ordinary.view()))
    before = ordinary.view()
    assert ordinary.query("self_info", {})["method"] == "fact"
    assert ordinary.view() == before
    for name, payload in [
        ("search_history", {"query": "", "actor": 3}),
        ("summarize_player", {"seat": True}),
        ("search_history", {"query": "", "from_round": 3}),
        ("ask_world", {"question": ""}),
    ]:
        with pytest.raises(Rejected):
            ordinary.query(name, payload)
    assert ordinary.query("ask_world", {"question": "铜铃"})["sources"]
    assert "没有记载" in ordinary.query("ask_world", {"question": "zzzzzxxyy"})["answer"]


class RetrievalModel:
    def __init__(self):
        self.calls = 0
        self.messages = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages, config):
        self.messages.append(messages)
        self.calls += 1
        name, args = (
            ("ask_world", {"question": "铜铃"}) if self.calls == 1 else ("wolf_vote", {"target": 1})
        )
        return AIMessage(
            content="", tool_calls=[{"id": str(self.calls), "name": name, "args": args}]
        )


def test_ai_can_retrieve_then_act_without_query_consuming_action(tmp_path):
    service = GameService(tmp_path / "g.db")
    gid = service.create(full=True, rng=random.Random(9))
    actor = pending(service.host_snapshot(gid))[0]
    model = RetrievalModel()
    report = DecisionRunner(model, DecisionConfig(max_rounds=2)).run(
        service.bind_player(gid, actor)
    )
    assert report["reason"] == "acted" and model.calls == 2
    assert service.host_snapshot(gid)["version"] == 1
    calls = service.host_decisions(gid)[0]["calls"]
    assert calls[0]["result"]["sources"]
    assert calls[1]["tool"] == "wolf_vote"


def client(tmp_path, runner=None):
    app = create_app(database=tmp_path / "web.db", access_token="only-test-password", runner=runner)
    return TestClient(app), app


def enter(c):
    assert (
        c.post("/api/enter", json={"password": "only-test-password"}, headers=HEADERS).status_code
        == 200
    )


def test_web_auth_csrf_cookie_and_no_host_endpoint(tmp_path):
    c, _ = client(tmp_path)
    assert c.get("/api/state").status_code == 401
    assert c.post("/api/enter", json={"password": "bad"}, headers=HEADERS).status_code == 403
    assert c.post("/api/enter", json={"password": "only-test-password"}).status_code == 403
    assert (
        c.post(
            "/api/enter",
            json={"password": "only-test-password"},
            headers={**HEADERS, "origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    enter(c)
    assert (
        "httponly" in c.cookies.get("mist_session").lower()
        or len(c.cookies.get("mist_session")) > 40
    )
    for role in [[], {}, True, 1, "invalid"]:
        assert c.post("/api/game", json={"role": role}, headers=HEADERS).status_code == 422
    state = c.post("/api/game", json={"role": "villager"}, headers=HEADERS).json()
    assert state["identity"] == "镇民"
    assert not any(p["role"] for p in state["players"] if p["seat"] != 1)
    for path in ["/api/host", "/api/snapshot", "/api/state?seat=2", "/api/state?actor=2"]:
        response = c.get(path)
        if response.status_code == 200:
            assert response.json()["seat"] == 1
    assert c.post("/api/action", json={"actor": 2}, headers=HEADERS).status_code == 409
    assert (
        c.post(
            "/api/query", json={"name": "self_info", "payload": {"actor": 2}}, headers=HEADERS
        ).status_code
        == 422
    )
    assert (
        c.post("/api/query", json={"name": "self_info", "payload": {}}, headers=HEADERS)
        .json()["answer"]
        .startswith("你坐在1号")
    )
    assert c.post("/api/advance", json={}, headers=HEADERS).status_code == 503
    assert (
        c.post(
            "/api/action",
            content="{" + " " * 21000,
            headers={**HEADERS, "Content-Type": "application/json"},
        ).status_code
        == 413
    )
    assert (
        c.post(
            "/api/action", content="{", headers={**HEADERS, "Content-Type": "application/json"}
        ).status_code
        == 422
    )
    assert "frame-ancestors 'none'" in c.get("/api/health").headers["content-security-policy"]


def test_session_survives_restart_and_second_client_cannot_read_game(tmp_path):
    c, app = client(tmp_path)
    enter(c)
    original = c.post("/api/game", json={"role": "seer"}, headers=HEADERS).json()
    fresh, _ = client(tmp_path)
    fresh.cookies.update(c.cookies)
    assert fresh.get("/api/state").json()["game_id"] == original["game_id"]
    other = TestClient(app)
    enter(other)
    assert other.get("/api/state").status_code == 404
    different = other.post("/api/game", json={"role": "witch"}, headers=HEADERS).json()
    assert different["game_id"] != original["game_id"]
    assert "药师" not in json.dumps(fresh.get("/api/state").json(), ensure_ascii=False)


class AbandonRunner:
    def run(self, player, persona):
        v = player.view()
        player.submit(command(v, "abstain", {}))


def test_advance_stops_at_human_and_does_not_choose_for_them(tmp_path):
    c, app = client(tmp_path, AbandonRunner())
    enter(c)
    state = c.post("/api/game", json={"role": "wolf"}, headers=HEADERS).json()
    for _ in range(3):
        response = c.post("/api/advance", json={}, headers=HEADERS)
        assert response.json()["version"] == state["version"]
    response = c.post(
        "/api/action",
        json=command(state, "wolf_chat", {"text": "<img src=x onerror=alert(1)>"}),
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert app.state.service.host_snapshot(state["game_id"])["version"] == 1


@pytest.mark.parametrize(
    "role,phase,tool",
    [
        ("seer", "night_seer", "inspect"),
        ("witch", "night_witch", "poison"),
        ("hunter", "hunter", "shoot"),
        ("idiot", "idiot", "reveal"),
        ("villager", "day_speech", "speak"),
        ("wolf", "night_wolves", "wolf_vote"),
    ],
)
def test_each_role_native_tool_reaches_real_backend(tmp_path, role, phase, tool):
    from langrensha import full_game as game
    from langrensha.service import utc_now

    service = GameService(tmp_path / "role.db")
    gid = service.create(full=True, human_role=role, rng=random.Random(9))
    snapshot = service.host_snapshot(gid)
    spec = game._task(phase, **({"seat": 1} if phase in {"hunter", "idiot"} else {}))
    snapshot["queue"] = [spec, game._task("day_speech")]
    game._advance(snapshot, utc_now())
    with service.store.transaction() as db:
        service.store.save(db, snapshot)
    payload = (
        {"target": game.targets(snapshot, 1, tool)[0]}
        if tool in game.TARGET_TOOLS
        else {"text": "我愿核对灯下的证词。"}
        if tool == "speak"
        else {}
    )

    class RoleModel:
        def bind_tools(self, tools):
            assert tool in [t["function"]["name"] for t in tools]
            return self

        def invoke(self, messages, config):
            return AIMessage(content="", tool_calls=[{"name": tool, "args": payload, "id": "role"}])

    report = DecisionRunner(RoleModel()).run(service.bind_player(gid, 1))
    assert report["reason"] == "acted"
    accepted = service.host_decisions(gid)[0]["calls"][0]
    assert accepted["tool"] == tool and accepted["result"]["accepted"]
