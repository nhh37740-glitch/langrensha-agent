"""真实会话/权限边界：阅读接口、模型背景与检索输入遵守同一开放阶段。"""

import copy
import json
import re

import pytest
from fastapi.testclient import TestClient

from langrensha import ai, retrieval, semantic
from langrensha.web import create_app
from langrensha.worldbooks import get_worldbook, worldbook_ids
from langrensha.worldbooks._reading import reading_for, reading_stage

HEADERS = {"X-Mist-Request": "1"}


@pytest.mark.parametrize("world", worldbook_ids())
def test_story_volume_cast_and_role_isolation(world):
    book = get_worldbook(world)
    entries = [entry for entry in book["entries"] if "chapter" in entry]
    assert len(entries) == 13
    assert len(re.findall(r"[\u4e00-\u9fff]", "".join(e["text"] for e in entries))) >= 5000
    names = {p[0] for p in book["personas"]}
    assert all(set(e["chapter"]["cast"]) <= names for e in entries)
    assert len(reading_for(book)["chapters"]) == 1
    for role in book["roles"]:
        view = {"role": role, "round": 1, "phase": "night_wolves", "winner": None}
        first = reading_for(book, view)
        assert len(first["chapters"]) == 3
        assert [c["id"].rsplit(":", 1)[-1] for c in first["chapters"] if c["private"]] == [role]
        last = reading_for(book, {**view, "winner": "village"})
        assert len(last["chapters"]) == 8
        assert sum(c["private"] for c in last["chapters"]) == 1


def test_reading_unlocks_follow_round_and_phase():
    assert reading_stage(None) == 0
    assert [
        reading_stage({"round": r, "phase": p})
        for r, p in (
            (1, "night_wolves"),
            (1, "day_speech"),
            (2, "night_seer"),
            (2, "exile_vote"),
            (3, "night_witch"),
            (8, "day_speech"),
        )
    ] == [1, 2, 3, 4, 5, 5]
    assert reading_stage({"winner": "wolves"}) == 6
    assert reading_stage({"round": 1, "phase": "sheriff_signup"}) == 1
    assert reading_stage({"round": 1, "phase": "hunter"}) == 1
    assert (
        reading_stage({"round": 1, "phase": "hunter", "events": [{"kind": "dawn", "round": 1}]})
        == 2
    )


def test_reading_api_uses_cookie_role_and_never_switches_world(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(database=tmp_path / "reading.db", static_dir=static)
    with TestClient(app) as client:
        assert client.get("/api/reading/no-such-world").status_code == 404
        assert client.get("/world/no-such-world").status_code == 404
        for world in worldbook_ids():
            response = client.get(f"/api/reading/{world}")
            assert response.headers["cache-control"] == "no-store"
            assert len(response.json()["chapters"]) == 1
        assert client.post("/api/enter", json={"password": ""}, headers=HEADERS).status_code == 200
        created = client.post(
            "/api/game", json={"role": "seer", "worldbook": "hyperion"}, headers=HEADERS
        ).json()
        own = client.get("/api/reading/hyperion?role=wolf").json()
        assert own["stage"] == 1
        assert [c["id"].split(":")[-1] for c in own["chapters"] if c["private"]] == ["seer"]
        assert len(client.get("/api/reading/threebody").json()["chapters"]) == 1
        for url in ("/", "/world/threebody", "/world/hyperion"):
            assert client.get(url).status_code == 200
        restored = client.get("/api/state").json()
        assert (restored["game_id"], restored["worldbook"], restored["version"]) == (
            created["game_id"],
            "hyperion",
            created["version"],
        )


def test_model_background_filters_before_first_entry_and_caps_length(monkeypatch):
    book = copy.deepcopy(get_worldbook("mist"))
    book["entries"] = [
        {"id": "locked", "text": "未开放终篇暗号", "visibility": "public", "chapter": {"stage": 6}},
        {"id": "private", "text": "其他身份暗号", "visibility": ["wolf"]},
        {"id": "open", "text": "已开放背景" + "甲" * 1600, "visibility": "public"},
    ]
    monkeypatch.setattr(ai, "get_worldbook", lambda *_: book)
    prompt = ai.system_prompt({"role": "villager", "round": 1, "phase": "night_wolves"})
    assert "未开放终篇暗号" not in prompt and "其他身份暗号" not in prompt
    assert "已开放背景" in prompt and prompt.count("甲") == 795
    assert "不是本局已发生的行动" in prompt


@pytest.mark.parametrize("fallback", [False, True])
def test_locked_and_other_role_text_never_reaches_semantic_or_fallback(monkeypatch, fallback):
    book = get_worldbook("threebody")
    view = {
        "worldbook": "threebody",
        "role": "seer",
        "round": 1,
        "phase": "night_wolves",
        "game_id": "reading",
        "seat": 1,
    }
    allowed = reading_for(book, view)["chapters"]
    forbidden = [
        e for e in book["entries"] if "chapter" in e and e["id"] not in {c["id"] for c in allowed}
    ]
    indexed = []

    def scores(texts, question):
        indexed.extend(texts)
        if fallback:
            raise semantic.EmbeddingUnavailable("offline test")
        return [0.99] * len(texts)

    monkeypatch.setattr(semantic, "scores", scores)
    result = retrieval.query(view, "ask_world", {"question": "天气麦苗手记"})
    assert indexed
    dump = json.dumps(result, ensure_ascii=False)
    joined = "".join(indexed)
    for entry in forbidden:
        assert entry["text"][:35] not in joined
        assert entry["id"] not in dump
    assert any(c["text"][:35] in joined for c in allowed if c["private"])
    assert result["method"] == ("lexical_fallback" if fallback else "semantic_retrieval")
