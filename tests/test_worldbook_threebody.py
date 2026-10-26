"""三体世界书的数据契约、秘密可见性与真实检索隔离测试。

本文件直接使用共享注册表与检索层（#39 已合入），不再用测试内模拟过滤；
模拟过滤只能证明数据形状，不能证明真实接入。
"""

import re

import pytest

from langrensha.content import WORLD
from langrensha.retrieval import build_chunks, query
from langrensha.rules import Rejected
from langrensha.worldbooks import (
    get_worldbook,
    guidance_for,
    visible_entries,
    worldbook_ids,
)
from langrensha.worldbooks.threebody import WORLDBOOK

BOOK = get_worldbook("threebody")
ROLES = {"wolf", "villager", "seer", "witch", "hunter", "idiot"}
SECRET_IDS_BY_ROLE = {
    "wolf": {
        "world:threebody:wolf_advent",
        "world:threebody:wolf_sophon",
        "world:threebody:wolf_wallbreaker",
    },
    "seer": {
        "world:threebody:seer_darkforest",
        "world:threebody:seer_redcoast",
    },
    "witch": {
        "world:threebody:witch_plan",
        "world:threebody:witch_timing",
    },
    "hunter": {"world:threebody:hunter_broadcast"},
    "idiot": {"world:threebody:idiot_hibernation"},
}
CANON_ROLE_NAMES = {"叶文洁", "汪淼", "史强", "罗辑", "程心", "云天明", "章北海", "维德"}


def view(role, *, worldbook="threebody"):
    return {
        "game_id": "g1",
        "seat": 1,
        "role": role,
        "round": 3,
        "events": [],
        "worldbook": worldbook,
    }


def ask(role, question, *, worldbook="threebody"):
    result = query(view(role, worldbook=worldbook), "ask_world", {"question": question})
    return [source["source"] for source in result["sources"]], result["answer"]


def visible_ids(role):
    return {entry["id"] for entry in visible_entries(BOOK, role)}


def test_book_is_registered_and_has_complete_metadata():
    assert "threebody" in worldbook_ids()
    assert BOOK is WORLDBOOK
    assert BOOK["id"] == "threebody"
    assert BOOK["name"] == "三体"
    assert isinstance(BOOK["basis"], str) and BOOK["basis"].strip()
    assert "未授权" in BOOK["basis"] and "原创改编" in BOOK["basis"]
    assert isinstance(BOOK["entries"], list) and BOOK["entries"]
    assert set(BOOK["roles"]) == ROLES
    assert set(BOOK["guidance"]) == ROLES
    assert all(BOOK["roles"][role].strip() for role in ROLES)
    assert all(BOOK["guidance"][role].strip() for role in ROLES)


def test_entry_ids_are_namespaced_unique_and_bounded():
    ids = [entry["id"] for entry in BOOK["entries"]]
    assert len(ids) == len(set(ids))
    assert all(entry_id.startswith("world:threebody:") for entry_id in ids)
    for entry in BOOK["entries"]:
        assert set(entry) == {"id", "title", "text", "visibility"}
        assert entry["title"].strip() and len(entry["title"]) <= 40
        assert entry["text"].strip() and len(entry["text"]) <= 300
    # 只做世界书条目，不把整章原文搬进 RAG；总正文规模保持可审阅。
    assert sum(len(entry["text"]) for entry in BOOK["entries"]) < 12_000


def test_visibility_values_are_public_or_known_roles():
    for entry in BOOK["entries"]:
        visibility = entry["visibility"]
        if visibility == "public":
            continue
        assert isinstance(visibility, list) and visibility
        assert set(visibility) <= ROLES
        assert len(visibility) == len(set(visibility))
        assert "public" not in visibility


def test_each_role_only_sees_its_own_secret_entries():
    public_ids = {
        entry["id"] for entry in BOOK["entries"] if entry["visibility"] == "public"
    }
    for role in ROLES:
        actual = visible_ids(role) - public_ids
        assert actual == SECRET_IDS_BY_ROLE.get(role, set()), role


def test_public_projection_never_contains_secret_title_or_text():
    public_text = "".join(
        entry["title"] + entry["text"] for entry in visible_entries(BOOK, "villager")
    )
    for entry in BOOK["entries"]:
        if entry["visibility"] == "public":
            continue
        assert entry["title"] not in public_text
        assert entry["text"] not in public_text


def test_visibility_filter_happens_before_real_ranking():
    # 红岸：公共条目所有角色可见，监听员另有旧档；平民不能因检索得分高而看到旧档。
    villager_sources, _ = ask("villager", "红岸")
    seer_sources, _ = ask("seer", "红岸")
    assert "world:threebody:red_coast" in villager_sources
    assert "world:threebody:seer_redcoast" not in villager_sources
    assert "world:threebody:seer_redcoast" in seer_sources

    # 黑暗森林：公共条目与监听员密档分离，平民只得到公共解释。
    villager_sources, _ = ask("villager", "黑暗森林")
    seer_sources, _ = ask("seer", "黑暗森林")
    assert "world:threebody:dark_forest" in villager_sources
    assert "world:threebody:seer_darkforest" not in villager_sources

    # 监听员密档用其独有词“信号归属”召回，避免依赖公共词的全量排序名次。
    villager_sources, _ = ask("villager", "信号归属")
    seer_sources, _ = ask("seer", "信号归属")
    assert "world:threebody:seer_darkforest" not in villager_sources
    assert "world:threebody:seer_darkforest" in seer_sources

    # 纯角色秘密词：公共条目可讲派别，但狼队密令只对狼队召回。
    villager_sources, villager_answer = ask("villager", "降临派")
    wolf_sources, wolf_answer = ask("wolf", "降临派")
    assert "world:threebody:eto" in villager_sources
    assert "world:threebody:wolf_advent" not in villager_sources
    assert "world:threebody:wolf_advent" in wolf_sources
    assert "降临派" in wolf_answer
    assert "降临派" in villager_answer

    hunter_sources, _ = ask("hunter", "坐标广播")
    seer_sources, _ = ask("seer", "坐标广播")
    assert "world:threebody:hunter_broadcast" in hunter_sources
    assert "world:threebody:hunter_broadcast" not in seer_sources

    idiot_sources, _ = ask("idiot", "冬眠")
    hunter_sources, _ = ask("hunter", "冬眠")
    assert "world:threebody:idiot_hibernation" in idiot_sources
    assert "world:threebody:idiot_hibernation" not in hunter_sources


def test_role_guidance_is_world_and_role_specific():
    villager = query(view("villager"), "self_info", {})
    seer = query(view("seer"), "self_info", {})
    assert "地球公民" in villager["answer"]
    assert "监听员" in seer["answer"]
    assert "你没有夜间能力" in villager["answer"]
    assert "不可询问自己或连续两夜同一人" in seer["answer"]
    assert guidance_for(BOOK, "villager") == BOOK["guidance"]["villager"]


def test_cross_world_ids_and_retrieval_do_not_collide():
    mist_ids = {entry["id"] for entry in WORLD}
    threebody_ids = {entry["id"] for entry in BOOK["entries"]}
    assert mist_ids.isdisjoint(threebody_ids)

    threebody_sources, _ = ask("villager", "伯劳 光阴冢 朝圣")
    assert all(
        source == "self:guide" or source.startswith("world:threebody:")
        for source in threebody_sources
    )
    assert "world:bell" not in threebody_sources

    mist_sources, _ = ask("villager", "黑暗森林 智子", worldbook="mist")
    assert all(
        source == "self:guide" or source.startswith("world:")
        for source in mist_sources
    )
    assert not any(source.startswith("world:threebody:") for source in mist_sources)


def test_chunks_use_current_worldbook_name():
    documents = [
        {"source": "event:1", "text": "站内第一句证词。", "category": "speech"}
    ]
    assert build_chunks(documents, view=view("villager"))[0].world == "三体"
    assert build_chunks(documents, view=view("villager", worldbook="mist"))[0].world == "雾钟镇"


def test_unknown_worldbook_is_rejected():
    with pytest.raises(KeyError):
        get_worldbook("no-such-world")
    with pytest.raises(Rejected) as error:
        query(view("villager", worldbook="no-such-world"), "ask_world", {"question": "三体"})
    assert error.value.code == "unknown_worldbook"


def test_standard_skill_semantics_are_not_changed():
    roles = BOOK["roles"]
    assert "平票或无人选择则当夜无袭击" in roles["wolf"]
    assert "没有夜间能力" in roles["villager"]
    assert "不可询问自己或连续两夜同一人" in roles["seer"]
    assert "一份修复预案和一份清除预案" in roles["witch"]
    assert "不可解救自己" in roles["witch"]
    assert "清除预案使你无法开枪" in roles["hunter"]
    assert "永久失去选票" in roles["idiot"]


def test_personas_are_twelve_original_crew_with_valid_colors():
    personas = BOOK["personas"]
    assert len(personas) == 12
    names = [name for name, _, _ in personas]
    assert len(names) == len(set(names))
    assert not (set(names) & CANON_ROLE_NAMES)
    for name, description, color in personas:
        assert name.strip() and description.strip()
        assert re.fullmatch(r"#[0-9a-f]{6}", color), color
