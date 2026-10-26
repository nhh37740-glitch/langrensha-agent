"""世界书可阅读正文与检索链路的一致性；不访问网络或真实模型服务。"""

import pytest

from langrensha.content import ROLE_NAMES
from langrensha.retrieval import build_chunks, query
from langrensha.worldbooks import _render, get_worldbook, visible_entries, worldbook_ids

CASES = [
    ("mist", "铜铃 执铃人 逐离 夜裔"),
    ("hyperion", "伯劳 光阴冢 朝圣 世界网"),
    ("threebody", "三颗太阳 脱水 智子 黑暗森林"),
    ("tidal_archive", "潮汐档案馆 生民册 潮窗 退潮密室"),
]


def view(role="villager", *, worldbook, game="g1", seat=1):
    return {
        "game_id": game,
        "seat": seat,
        "role": role,
        "round": 3,
        "events": [],
        "worldbook": worldbook,
    }


def test_generated_body_matches_canonical_worldbook_data():
    assert _render.OUTPUT.is_file()
    assert _render.OUTPUT.read_text(encoding="utf-8") == _render.render_markdown()


def test_generated_body_lists_every_world_entry_role_and_persona():
    text = _render.render_markdown()
    for worldbook_id in worldbook_ids():
        book = get_worldbook(worldbook_id)
        assert f"## {book['name']}（`{worldbook_id}`）" in text
        for entry in book["entries"]:
            assert f"`{entry['id']}`" in text
        for name, _description, _color in book["personas"]:
            assert f"**{name}**" in text
        for role, label in book["roles"].items():
            assert f"**{label}（{role}）**" in text


@pytest.mark.parametrize("worldbook_id", worldbook_ids())
def test_every_entry_chunks_preserve_source_and_original_text(worldbook_id):
    book = get_worldbook(worldbook_id)
    for entry in book["entries"]:
        chunks = build_chunks(
            [
                {
                    "source": entry["id"],
                    "text": entry["text"],
                    "title": entry["title"],
                    "category": "world",
                }
            ],
            view=view(worldbook=worldbook_id),
        )
        assert chunks
        assert "".join(chunk.text for chunk in chunks) == entry["text"]
        assert all(chunk.source == entry["id"] for chunk in chunks)
        assert all(chunk.world == book["name"] for chunk in chunks)


@pytest.mark.parametrize("worldbook_id", worldbook_ids())
def test_secret_entries_are_visible_only_to_listed_roles(worldbook_id):
    book = get_worldbook(worldbook_id)
    all_ids = {entry["id"] for entry in book["entries"]}
    for role in ROLE_NAMES:
        visible_ids = {entry["id"] for entry in visible_entries(book, role)}
        assert visible_ids <= all_ids
        for entry in book["entries"]:
            if entry["visibility"] == "public":
                assert entry["id"] in visible_ids
            else:
                assert (entry["id"] in visible_ids) is (role in entry["visibility"])


@pytest.mark.parametrize(("worldbook_id", "question"), CASES)
def test_each_world_has_a_real_public_hit_from_its_own_entries(worldbook_id, question):
    book = get_worldbook(worldbook_id)
    public_ids = {
        entry["id"] for entry in book["entries"] if entry["visibility"] == "public"
    }
    result = query(view(worldbook=worldbook_id), "ask_world", {"question": question})
    assert result["method"] in {"semantic_retrieval", "lexical_fallback"}
    assert result["sources"]
    assert all(
        source["source"] == "self:guide" or source["source"] in public_ids
        for source in result["sources"]
    )


@pytest.mark.parametrize(("worldbook_id", "question"), CASES)
def test_public_query_never_returns_role_secret(worldbook_id, question):
    book = get_worldbook(worldbook_id)
    secret_ids = {
        entry["id"] for entry in book["entries"] if entry["visibility"] != "public"
    }
    result = query(
        view(worldbook=worldbook_id),
        "ask_world",
        {"question": f"{question} 秘密 夜间 同伴 名单 密室"},
    )
    assert not any(source["source"] in secret_ids for source in result["sources"])
