"""潮汐档案馆世界书的数据契约、秘密可见性与跨世界隔离测试。"""

import re

import pytest

from langrensha.content import ROLE_NAMES, WORLD
from langrensha.retrieval import split_text
from langrensha.worldbooks.tidal_archive import WORLDBOOK

ROLE_KEYS = tuple(ROLE_NAMES)
PUBLIC = "public"
MARKERS = {
    "第七级台阶": "wolf",
    "倒写的潮纹": "wolf",
    "浮板不能照自己": "seer",
    "返名盐": "witch",
    "熄灯铳": "hunter",
    "亮出誓痕": "idiot",
}


def visible_entries(entries, role):
    """按接口 v0 模拟“先按查看者角色过滤，再索引/排序”。"""
    return [e for e in entries if e["visibility"] == PUBLIC or role in e["visibility"]]


def search_entries(entries, role, query):
    """过滤后的最朴素检索；用于证明秘密条目不进入其他角色的候选集。"""
    return [e for e in visible_entries(entries, role) if query in e["text"]]


def test_worldbook_metadata_and_entry_contract():
    assert WORLDBOOK["id"] == "tidal_archive"
    assert WORLDBOOK["name"] == "潮汐档案馆"
    assert "文档/调研/世界书/潮汐档案馆世界书调研.md" in WORLDBOOK["basis"]
    assert set(WORLDBOOK) == {
        "id",
        "name",
        "basis",
        "entries",
        "roles",
        "guidance",
        "personas",
    }
    entries = WORLDBOOK["entries"]
    assert len(entries) >= 12
    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids))
    prefix = f"world:{WORLDBOOK['id']}:"
    for entry in entries:
        assert set(entry) == {"id", "title", "text", "visibility"}
        assert entry["id"].startswith(prefix)
        assert entry["title"].strip()
        assert entry["text"].strip()
        assert len(entry["text"]) <= 300


def test_entries_fit_existing_chunker_without_losing_text():
    for entry in WORLDBOOK["entries"]:
        chunks = split_text(entry["text"])
        assert chunks
        assert all(len(chunk) <= 300 for chunk in chunks)
        assert "".join(chunks) == entry["text"]


def test_visibility_values_are_public_or_known_roles():
    public_count = 0
    for entry in WORLDBOOK["entries"]:
        visibility = entry["visibility"]
        if visibility == PUBLIC:
            public_count += 1
            continue
        assert isinstance(visibility, list) and visibility
        assert set(visibility) <= set(ROLE_KEYS)
        assert PUBLIC not in visibility
    assert public_count >= 8


def test_roles_guidance_and_personas_are_complete():
    assert set(WORLDBOOK["roles"]) == set(ROLE_KEYS)
    assert set(WORLDBOOK["guidance"]) == set(ROLE_KEYS)
    assert len(set(WORLDBOOK["roles"].values())) == len(ROLE_KEYS)
    default_names = {"狼人", "村民", "预言家", "女巫", "猎人", "白痴"}
    assert not default_names & set(WORLDBOOK["roles"].values())
    for role in ROLE_KEYS:
        assert isinstance(WORLDBOOK["roles"][role], str)
        assert WORLDBOOK["roles"][role].strip()
        assert isinstance(WORLDBOOK["guidance"][role], str)
        assert WORLDBOOK["guidance"][role].strip()
    personas = WORLDBOOK["personas"]
    assert len(personas) == 12
    assert len({name for name, _, _ in personas}) == 12
    assert len({color for _, _, color in personas}) == 12
    for name, description, color in personas:
        assert name.strip() and description.strip()
        assert re.fullmatch(r"#[0-9a-f]{6}", color)


def test_entries_use_in_world_language():
    joined = "".join(entry["text"] for entry in WORLDBOOK["entries"])
    for term in ("查杀", "跳预言家", "金水", "银水", "警徽", "狼刀", "狼人", "预言家", "女巫"):
        assert term not in joined


def test_every_role_has_at_least_one_secret_entry():
    for role in ROLE_KEYS:
        if role == "villager":
            continue
        own = [
            entry
            for entry in WORLDBOOK["entries"]
            if entry["visibility"] != PUBLIC and role in entry["visibility"]
        ]
        assert own, role
    wolf_entries = [entry for entry in WORLDBOOK["entries"] if entry["visibility"] == ["wolf"]]
    assert len(wolf_entries) >= 2


@pytest.mark.parametrize("role", ROLE_KEYS)
def test_public_entries_are_visible_to_every_role_and_texts_are_disjoint(role):
    visible = visible_entries(WORLDBOOK["entries"], role)
    visible_ids = {entry["id"] for entry in visible}
    public_ids = {entry["id"] for entry in WORLDBOOK["entries"] if entry["visibility"] == PUBLIC}
    assert public_ids <= visible_ids
    joined = "".join(entry["text"] for entry in visible)
    for marker, owner in MARKERS.items():
        assert (marker in joined) is (role == owner), (role, marker, owner)


def test_secret_details_do_not_leak_from_filtered_search():
    entries = WORLDBOOK["entries"]
    assert search_entries(entries, "wolf", "第七级台阶")
    assert search_entries(entries, "wolf", "倒写的潮纹")
    assert search_entries(entries, "seer", "浮板不能照自己")
    assert search_entries(entries, "witch", "返名盐")
    assert search_entries(entries, "hunter", "熄灯铳")
    assert search_entries(entries, "idiot", "亮出誓痕")
    for role in ("villager", "seer", "witch", "hunter", "idiot"):
        assert search_entries(entries, role, "第七级台阶") == []
        assert search_entries(entries, role, "倒写的潮纹") == []
    for role in ("wolf", "villager", "witch", "hunter", "idiot"):
        assert search_entries(entries, role, "浮板不能照自己") == []
    for role in ("wolf", "villager", "seer", "hunter", "idiot"):
        assert search_entries(entries, role, "返名盐") == []
    for role in ("wolf", "villager", "seer", "idiot"):
        assert search_entries(entries, role, "熄灯铳") == []
    for role in ("wolf", "villager", "seer", "witch", "hunter"):
        assert search_entries(entries, role, "亮出誓痕") == []


def test_index_is_built_after_role_filtering():
    def build_index(role):
        return {entry["id"]: entry["text"] for entry in visible_entries(WORLDBOOK["entries"], role)}

    villager_index = build_index("villager")
    wolf_index = build_index("wolf")
    assert "world:tidal_archive:ebb-chamber" not in villager_index
    assert "world:tidal_archive:name-eaters" not in villager_index
    assert "world:tidal_archive:ebb-chamber" in wolf_index
    assert len(villager_index) < len(wolf_index)


def _mixed_corpus():
    mist = [
        {
            "id": item["id"],
            "world": "mist",
            "text": item["text"],
            "visibility": PUBLIC,
        }
        for item in WORLD
    ]
    tidal = [
        {
            "id": entry["id"],
            "world": "tidal_archive",
            "text": entry["text"],
            "visibility": entry["visibility"],
        }
        for entry in WORLDBOOK["entries"]
    ]
    return mist + tidal


def test_cross_world_and_cross_role_isolation():
    corpus = _mixed_corpus()

    def query(world, role, needle):
        candidates = [
            document
            for document in corpus
            if document["world"] == world
            and (document["visibility"] == PUBLIC or role in document["visibility"])
        ]
        return [document["id"] for document in candidates if needle in document["text"]]

    assert query("mist", "wolf", "潮汐档案馆") == []
    assert query("mist", "wolf", "第七级台阶") == []
    assert query("tidal_archive", "villager", "雾钟镇") == []
    assert query("tidal_archive", "villager", "第七级台阶") == []
    assert query("tidal_archive", "wolf", "第七级台阶") == ["world:tidal_archive:ebb-chamber"]
    assert query("mist", "villager", "夜裔")
