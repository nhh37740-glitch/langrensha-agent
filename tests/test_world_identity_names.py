"""四世界24个名称贯通目录、真实建局视图、模型提示和RAG自身事实，零模型调用。"""

import pytest
from fastapi.testclient import TestClient

from langrensha.ai import system_prompt
from langrensha.content import ROLE_NAMES
from langrensha.presentation import worldbook_catalog
from langrensha.retrieval import query
from langrensha.web import create_app
from langrensha.worldbooks import get_worldbook

CASES = [
    (world, role)
    for world in ("mist", "hyperion", "threebody", "tidal_archive")
    for role in ROLE_NAMES
]


@pytest.mark.parametrize(("world", "role"), CASES)
def test_identity_names_have_one_source_across_real_layers(tmp_path, world, role):
    label = get_worldbook(world)["roles"][role]
    assert 1 <= len(label) <= 8
    assert not any(mark in label for mark in "（）。；\n")
    book = next(item for item in worldbook_catalog()["worldbooks"] if item["id"] == world)
    assert book["role_labels"][role] == label
    client = TestClient(create_app(database=tmp_path / "identity.sqlite", access_token="fixture"))
    headers = {"X-Mist-Request": "1"}
    entered = client.post("/api/enter", json={"password": "fixture"}, headers=headers)
    assert entered.status_code == 200
    created = client.post("/api/game", json={"role": role, "worldbook": world}, headers=headers)
    assert created.status_code == 200
    assert created.json()["identity"] == label
    assert client.get("/api/state").json()["identity"] == label
    # 此处是同一个合法身份的受限数据，不将主持视图或秘密分配传给目录。
    limited = {
        "game_id": created.json()["game_id"],
        "seat": 1,
        "role": role,
        "worldbook": world,
        "round": 1,
        "events": [],
    }
    assert f"身份称谓：{label}；" in system_prompt(limited)
    self_info = query(limited, "self_info", {})
    assert self_info["sources"][0] == {"source": "self:identity", "text": label}
    assert f"身份是{label}。" in self_info["answer"]
    for player in created.json()["players"]:
        if player["seat"] != 1 and role != "wolf":
            assert not player.get("role")
