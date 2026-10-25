"""潮汐档案馆接入共享世界书接口后的注册、检索与隔离测试。"""

import pytest

from langrensha.ai import Persona, system_prompt
from langrensha.retrieval import build_chunks, query
from langrensha.rules import Rejected
from langrensha.worldbooks import (
    get_worldbook,
    guidance_for,
    personas_for,
    role_name,
    visible_entries,
    worldbook_ids,
)

WOLF_SECRET = "world:tidal_archive:ebb-chamber"


def view(role="villager", *, worldbook="tidal_archive", game="g1", seat=1):
    return {
        "game_id": game,
        "seat": seat,
        "role": role,
        "round": 3,
        "events": [],
        "worldbook": worldbook,
    }


def test_tidal_archive_is_discovered_with_all_six_roles():
    assert "tidal_archive" in worldbook_ids()
    book = get_worldbook("tidal_archive")
    assert book["id"] == "tidal_archive"
    assert book["name"] == "潮汐档案馆"
    assert len(book["entries"]) == 22
    assert len(book["personas"]) == 12
    assert role_name(book, "wolf") == "噬名者"
    assert role_name(book, "villager") == "守册人"
    assert "退潮密室" in guidance_for(book, "wolf")
    assert len(personas_for(book)) == 12


def test_tidal_archive_visibility_is_role_scoped():
    wolf_ids = {entry["id"] for entry in visible_entries("tidal_archive", "wolf")}
    villager_ids = {entry["id"] for entry in visible_entries("tidal_archive", "villager")}
    assert WOLF_SECRET in wolf_ids
    assert WOLF_SECRET not in villager_ids
    assert "world:tidal_archive:star-gauge" in {
        entry["id"] for entry in visible_entries("tidal_archive", "seer")
    }
    assert "world:tidal_archive:star-gauge" not in villager_ids
    assert "world:tidal_archive:arrival" in villager_ids


def test_tidal_archive_retrieval_keeps_secret_from_other_roles():
    question = {"question": "第七级台阶 退潮密室"}
    wolf = query(view("wolf"), "ask_world", question)
    assert any(source["source"] == WOLF_SECRET for source in wolf["sources"]), wolf
    villager = query(view("villager"), "ask_world", question)
    assert all(source["source"] != WOLF_SECRET for source in villager["sources"]), villager
    assert "第七级台阶" not in villager["answer"], villager


def test_tidal_archive_self_info_uses_world_words():
    villager = query(view("villager"), "self_info", {})
    assert "守册人" in villager["answer"]
    assert "你没有夜间能力" in villager["answer"]
    wolf = query(view("wolf"), "self_info", {})
    assert "噬名者" in wolf["answer"]
    assert "退潮密室" in wolf["answer"]


def test_tidal_archive_does_not_mix_other_worlds():
    mist = query(view("villager", worldbook="mist"), "ask_world", {"question": "第七级台阶"})
    assert all(
        not source["source"].startswith("world:tidal_archive:") for source in mist["sources"]
    )
    tidal = query(view("villager"), "ask_world", {"question": "潮钟 低潮门"})
    assert tidal["sources"]
    assert all(
        source["source"].startswith("world:tidal_archive:") or source["source"] == "self:guide"
        for source in tidal["sources"]
    ), tidal
    with pytest.raises(Rejected) as error:
        query(view(worldbook="no-such-world"), "ask_world", {"question": "潮钟"})
    assert error.value.code == "unknown_worldbook"


def test_tidal_archive_chunks_use_world_name():
    document = {"source": "event:1", "text": "第一句证词。", "category": "speech"}
    assert build_chunks([document], view=view())[0].world == "潮汐档案馆"
    assert build_chunks([document], view=view(worldbook="mist"))[0].world == "雾钟镇"


def test_tidal_archive_system_prompt_uses_world_words():
    prompt = system_prompt(view("wolf"), Persona("拾汐", "先听完再判断。"))
    assert "潮汐档案馆" in prompt
    assert "噬名者" in prompt
    assert "退潮密室" in prompt
    assert "册屿" in prompt
    assert "雾钟镇" not in prompt
