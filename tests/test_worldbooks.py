"""世界书接口、角色可见性与跨世界隔离；默认雾钟镇行为保持不变。"""

import random

import pytest

from langrensha.ai import Persona, system_prompt
from langrensha.content import GUIDANCE, ROLE_NAMES
from langrensha.full_game import pending
from langrensha.retrieval import build_chunks, query
from langrensha.rules import Rejected
from langrensha.service import GameService
from langrensha.worldbooks import (
    DEFAULT_WORLD_ID,
    get_worldbook,
    guidance_for,
    role_name,
    visible_entries,
    worldbook_ids,
)


def view(role="villager", *, worldbook=None, game="g1", seat=1):
    result = {"game_id": game, "seat": seat, "role": role, "round": 3, "events": []}
    if worldbook is not None:
        result["worldbook"] = worldbook
    return result


def test_builtin_worldbooks_are_discovered_and_complete():
    assert DEFAULT_WORLD_ID == "mist"
    assert {"mist", "hyperion"} <= set(worldbook_ids())
    for worldbook_id in worldbook_ids():
        book = get_worldbook(worldbook_id)
        assert book["id"] == worldbook_id
        assert isinstance(book["basis"], str) and book["basis"].strip()
        assert set(book["roles"]) <= set(ROLE_NAMES)
        assert set(book["guidance"]) <= set(ROLE_NAMES)
        assert book["personas"]
        assert len({entry["id"] for entry in book["entries"]}) == len(book["entries"])
        for entry in book["entries"]:
            assert entry["id"].startswith(
                f"world:{worldbook_id}:" if worldbook_id != "mist" else "world:"
            )
            assert entry["visibility"] == "public" or set(entry["visibility"]) <= set(ROLE_NAMES)
    for worldbook_id in ("mist", "hyperion"):
        book = get_worldbook(worldbook_id)
        assert set(book["roles"]) == set(ROLE_NAMES)
        assert set(book["guidance"]) == set(ROLE_NAMES)
        assert len(book["personas"]) == 12


def test_visibility_filter_keeps_secrets_out_of_other_roles_and_worlds():
    hyperion = get_worldbook("hyperion")
    wolf_entries = {entry["id"] for entry in visible_entries(hyperion, "wolf")}
    villager_entries = {entry["id"] for entry in visible_entries(hyperion, "villager")}
    assert "world:hyperion:thorn-pact" in wolf_entries
    assert "world:hyperion:thorn-pact" not in villager_entries
    assert "world:hyperion:seer-eye" not in villager_entries
    assert "world:hyperion:arrival" in villager_entries
    villager_text = "".join(entry["text"] for entry in visible_entries(hyperion, "villager"))
    assert "荆棘之约" not in villager_text

    mist_entries = {entry["id"] for entry in visible_entries("mist", "villager")}
    assert not any(entry.startswith("world:hyperion:") for entry in mist_entries)
    assert "world:arrival" in mist_entries


def test_unknown_worldbook_is_rejected_instead_of_falling_back_to_another_world():
    with pytest.raises(KeyError):
        get_worldbook("no-such-world")
    with pytest.raises(Rejected) as error:
        query(view(worldbook="no-such-world"), "ask_world", {"question": "伯劳"})
    assert error.value.code == "unknown_worldbook"


def test_hyperion_view_retrieves_current_world_only(tmp_path):
    service = GameService(tmp_path / "worldbooks.db")
    game_id = service.create(full=True, human_role="villager", rng=random.Random(9))
    current = service.bind_player(game_id, 1).view()
    current["worldbook"] = "hyperion"

    result = query(current, "ask_world", {"question": "伯劳 光阴冢 朝圣"})
    assert result["sources"]
    assert all(
        source["source"].startswith("world:hyperion:") or source["source"] == "self:guide"
        for source in result["sources"]
    )
    assert "雾钟镇" not in result["answer"]
    assert not any(source["source"] == "world:bell" for source in result["sources"])

    mist_result = query(view(), "ask_world", {"question": "伯劳 光阴冢 朝圣"})
    assert not any(
        source["source"].startswith("world:hyperion:") for source in mist_result["sources"]
    )


def test_hyperion_self_info_and_guidance_are_world_specific():
    villager = query(view("villager", worldbook="hyperion"), "self_info", {})
    assert "朝圣者" in villager["answer"]
    assert "你没有夜间能力" in villager["answer"]
    wolf = query(view("wolf", worldbook="hyperion"), "self_info", {})
    assert "荆棘使徒" in wolf["answer"]
    assert "夜间与同伴低语" in wolf["answer"]

    assert role_name({"roles": {}}, "villager") == ROLE_NAMES["villager"]
    assert guidance_for({"guidance": {}}, "villager") == GUIDANCE["villager"]


def test_villager_cannot_retrieve_wolf_secret_by_question():
    question = {"question": "荆棘之约 秘密小组 夜间献祭"}
    villager = query(view("villager", worldbook="hyperion"), "ask_world", question)
    assert "荆棘之约" not in villager["answer"]
    assert all(source["source"] != "world:hyperion:thorn-pact" for source in villager["sources"])

    wolf = query(view("wolf", worldbook="hyperion"), "ask_world", question)
    assert any(source["source"] == "world:hyperion:thorn-pact" for source in wolf["sources"])

    wolf_entries = visible_entries("hyperion", "wolf")
    assert any(entry["id"] == "world:hyperion:thorn-pact" for entry in wolf_entries)


def test_chunks_use_current_worldbook_name():
    document = {
        "source": "event:1",
        "text": "营地里的第一句证词。",
        "category": "speech",
        "actor": 2,
        "round": 1,
    }
    assert build_chunks([document], view=view())[0].world == "雾钟镇"
    assert build_chunks([document], view=view(worldbook="hyperion"))[0].world == "海伯利安"


def test_ai_system_prompt_uses_current_worldbook_and_keeps_mist_default():
    hyperion_prompt = system_prompt(
        view("wolf", worldbook="hyperion"), Persona("随队看护", "先听完再判断。")
    )
    assert "海伯利安" in hyperion_prompt
    assert "荆棘使徒" in hyperion_prompt
    assert "夜间与同伴低语" in hyperion_prompt
    assert "入场背景：二十八世纪" in hyperion_prompt
    assert "雾钟镇" not in hyperion_prompt

    mist_prompt = system_prompt(view("wolf"))
    assert "雾钟镇" in mist_prompt
    assert "夜裔" in mist_prompt
    assert "mist-v1" in mist_prompt


def test_hyperion_does_not_add_rule_tools_or_change_default_game(tmp_path):
    service = GameService(tmp_path / "default.db")
    game_id = service.create(full=True, human_role="villager", rng=random.Random(9))
    current = service.bind_player(game_id, 1).view()
    assert "worldbook" not in current
    wolf_seat = pending(service.host_snapshot(game_id))[0]
    assert "wolf_vote" in service.bind_player(game_id, wolf_seat).view()["tools"]
    assert "wolf_vote" not in current["tools"]
