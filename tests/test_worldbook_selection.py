"""世界书目录、建局选择与视图/检索/提示词贯通；接口只用真实 FastAPI TestClient。"""

import json
import random

import pytest
from fastapi.testclient import TestClient

from langrensha.ai import system_prompt
from langrensha.content import ROLE_NAMES
from langrensha.full_game import pending
from langrensha.presentation import present, worldbook_catalog
from langrensha.rules import Rejected
from langrensha.service import GameService
from langrensha.web import create_app
from langrensha.worldbooks import get_worldbook, personas_for

HEADERS = {"X-Mist-Request": "1"}
WORLDS = ("mist", "hyperion", "threebody", "tidal_archive")
MOTIFS = {
    "mist": "bell",
    "hyperion": "tombs",
    "threebody": "signal",
    "tidal_archive": "tide",
}
IDENTITY = {
    "mist": "镇民",
    "hyperion": "朝圣者",
    "threebody": "地球公民",
    "tidal_archive": "守册人",
}
FORBIDDEN_KEYS = {"entries", "guidance", "personas", "basis"}


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


def keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from keys(nested)


def test_catalog_is_public_and_never_exports_secret_worldbook_data():
    catalog = worldbook_catalog()
    assert catalog["default"] == "mist"
    assert [book["id"] for book in catalog["worldbooks"]] == list(WORLDS)
    dump = json.dumps(catalog, ensure_ascii=False)
    assert not (FORBIDDEN_KEYS & set(keys(catalog)))
    for book in catalog["worldbooks"]:
        worldbook = get_worldbook(book["id"])
        public = [entry for entry in worldbook["entries"] if entry["visibility"] == "public"]
        assert book["name"] == worldbook["name"]
        assert book["motif"] == MOTIFS[book["id"]]
        assert book["tagline"] and book["summary"] and book["glyph"]
        assert set(book["palette"]) == {"sky", "mid", "accent", "paper", "ink"}
        assert set(book["role_labels"]) == set(ROLE_NAMES)
        assert set(book["scene"]) == {
            "eyebrow",
            "title",
            "subtitle",
            "caption",
            "chapter",
            "footer",
            "intro",
        }
        assert len(book["scene"]["title"]) == 2
        assert book["scene"]["intro"]
        assert book["public_count"] == len(public)
        assert book["excerpt"] == public[0]["text"].strip()[:140]
        assert len(book["excerpt"]) <= 140
        for entry in worldbook["entries"]:
            if entry["visibility"] != "public":
                assert entry["text"] not in dump


def test_worldbook_endpoint_is_public_and_has_no_store_cache(tmp_path):
    c, _ = client(tmp_path)
    response = c.get("/api/worldbooks")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["default"] == "mist"
    assert [book["id"] for book in payload["worldbooks"]] == list(WORLDS)
    assert not (FORBIDDEN_KEYS & set(keys(payload)))


def test_all_four_worldbooks_can_create_games_and_survive_refresh(tmp_path):
    c, app = client(tmp_path)
    enter(c)
    for worldbook in WORLDS:
        response = c.post(
            "/api/game",
            json={"role": "villager", "worldbook": worldbook},
            headers=HEADERS,
        )
        assert response.status_code == 200, response.text
        created = response.json()
        assert created["worldbook"] == worldbook
        assert created["worldbook_name"] == get_worldbook(worldbook)["name"]
        assert created["identity"] == IDENTITY[worldbook]

        refreshed = c.get("/api/state").json()
        assert refreshed["game_id"] == created["game_id"]
        assert refreshed["worldbook"] == worldbook
        assert app.state.service.host_snapshot(created["game_id"])["worldbook"] == worldbook


def test_game_request_defaults_to_mist_and_rejects_unknown_worldbooks(tmp_path):
    c, _ = client(tmp_path)
    enter(c)
    assert c.get("/api/state").status_code == 404

    unknown = c.post(
        "/api/game",
        json={"role": "villager", "worldbook": "no-such-world"},
        headers=HEADERS,
    )
    assert unknown.status_code == 422
    assert "世界书" in unknown.json()["detail"]
    assert c.get("/api/state").status_code == 404

    for value in (1, True, ["mist"]):
        assert (
            c.post(
                "/api/game",
                json={"role": "villager", "worldbook": value},
                headers=HEADERS,
            ).status_code
            == 422
        )

    assert c.post("/api/game", json={"role": "villager"}, headers=HEADERS).json()["worldbook"] == (
        "mist"
    )
    assert (
        c.post(
            "/api/game",
            json={"role": "villager", "worldbook": None},
            headers=HEADERS,
        ).json()["worldbook"]
        == "mist"
    )


def test_selected_worldbook_reaches_persisted_view_retrieval_and_prompt(tmp_path):
    c, app = client(tmp_path)
    enter(c)
    created = c.post(
        "/api/game",
        json={"role": "seer", "worldbook": "threebody"},
        headers=HEADERS,
    ).json()
    assert created["worldbook"] == "threebody"

    refreshed = c.get("/api/state").json()
    assert refreshed["worldbook"] == "threebody"
    assert refreshed["identity"] == "监听员"

    result = c.post(
        "/api/query",
        json={"name": "ask_world", "payload": {"question": "智子 水滴 黑暗森林"}},
        headers=HEADERS,
    ).json()
    assert result["sources"]
    assert all(
        source["source"].startswith("world:threebody:") or source["source"] == "self:guide"
        for source in result["sources"]
    )
    assert "雾钟镇" not in result["answer"]

    view = app.state.service.bind_player(created["game_id"], 1).view()
    prompt = system_prompt(view)
    assert view["worldbook"] == "threebody"
    assert "三体" in prompt and "监听员" in prompt
    assert "雾钟镇" not in prompt


def test_service_persists_worldbook_and_rejects_unknown(tmp_path):
    service = GameService(tmp_path / "worldbooks.db")
    game_id = service.create(
        full=True,
        human_role="villager",
        rng=random.Random(9),
        worldbook="hyperion",
    )
    snapshot = service.host_snapshot(game_id)
    assert snapshot["worldbook"] == "hyperion"
    current = service.bind_player(game_id, 1).view()
    assert current["worldbook"] == "hyperion"
    assert present(current)["worldbook"] == "hyperion"

    rehearsal = service.create(full=False, worldbook="tidal_archive")
    assert service.bind_player(rehearsal, 1).view()["worldbook"] == "tidal_archive"

    with pytest.raises(Rejected) as error:
        service.create(worldbook="no-such-world")
    assert error.value.code == "unknown_worldbook"


class RecordingRunner:
    def __init__(self):
        self.personas = []

    def run(self, player, persona):
        self.personas.append((player.view()["game_id"], persona))


def test_advance_uses_worldbook_personas_for_ai(tmp_path):
    runner = RecordingRunner()
    c, app = client(tmp_path, runner)
    enter(c)
    created = c.post(
        "/api/game",
        json={"role": "villager", "worldbook": "hyperion"},
        headers=HEADERS,
    ).json()
    actor = pending(app.state.service.host_snapshot(created["game_id"]))[0]
    expected = personas_for("hyperion")[actor - 1]

    assert c.post("/api/advance", json={}, headers=HEADERS).status_code == 200
    assert runner.personas
    game_id, persona = runner.personas[-1]
    assert game_id == created["game_id"]
    assert persona.name == expected[0]
    assert persona.description == expected[1]
