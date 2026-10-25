"""四套公开表现主题：人物、称谓、章节、行动标签、结局与旧局回退。"""

import json
import random

from langrensha import full_game as game
from langrensha.content import GUIDANCE, PERSONAS, ROLE_NAMES
from langrensha.presentation import (
    LABELS,
    PHASE_NAMES,
    THEMES,
    present,
    story_language,
)
from langrensha.worldbooks import get_worldbook, personas_for

NOW = "2026-10-25T00:00:00Z"
WORLDS = ("mist", "hyperion", "threebody", "tidal_archive")
MOTIFS = {
    "mist": "bell",
    "hyperion": "tombs",
    "threebody": "signal",
    "tidal_archive": "tide",
}
WOLF_LABELS = {
    "mist": "夜裔",
    "hyperion": "荆棘使徒",
    "threebody": "潜伏者",
    "tidal_archive": "噬名者",
}
PALETTES = {
    "mist": {
        "sky": "#0b1a21",
        "mid": "#2f4a45",
        "accent": "#d8bd85",
        "paper": "#e9dfc6",
        "ink": "#081014",
    },
    "hyperion": {
        "sky": "#1a0f0a",
        "mid": "#6b3a24",
        "accent": "#d9a05b",
        "paper": "#f0dfbd",
        "ink": "#120b07",
    },
    "threebody": {
        "sky": "#040a12",
        "mid": "#17324d",
        "accent": "#e2574c",
        "paper": "#e8f0f6",
        "ink": "#03070d",
    },
    "tidal_archive": {
        "sky": "#06191a",
        "mid": "#2d6259",
        "accent": "#c98f5a",
        "paper": "#f0eadb",
        "ink": "#041312",
    },
}


def state(worldbook="mist", role="villager"):
    return game.create_full_game(
        now=NOW,
        human_role=role,
        rng=random.Random(9),
        worldbook=worldbook,
    )


def presented(worldbook="mist", role="villager"):
    return present(game.player_view(state(worldbook, role), 1))


def test_themes_cover_public_presentation_fields_and_keep_defaults():
    assert set(THEMES) == set(WORLDS)
    for worldbook in WORLDS:
        theme = THEMES[worldbook]
        assert theme["id"] == worldbook
        assert theme["motif"] == MOTIFS[worldbook]
        assert theme["tagline"] and theme["summary"] and theme["glyph"]
        assert set(theme["palette"]) == {"sky", "mid", "accent", "paper", "ink"}
        assert theme["palette"] == PALETTES[worldbook]
        assert set(theme["role_labels"]) == set(ROLE_NAMES)
        assert set(theme["labels"]) == set(LABELS)
        assert set(theme["endings"]) == {"village", "wolves", "draw"}
        assert set(PHASE_NAMES) <= set(theme["chapters"])
        assert {"night", "default"} <= set(theme["chapters"])
        assert theme["scene"]["title"] and theme["scene"]["subtitle"]
        assert theme["scene"]["intro"]
    assert THEMES["mist"]["labels"] == LABELS
    assert set(PHASE_NAMES) <= set(THEMES["mist"]["chapters"])
    assert THEMES["mist"]["scene"]["intro"] == (
        "雾封住了出镇的路。十一位旅人已经等在广场，今夜，你会带着怎样的秘密入座？"
    )
    assert len({theme["scene"]["intro"] for theme in THEMES.values()}) == len(WORLDS)


def test_present_switches_worldbook_name_identity_and_public_players():
    for worldbook in WORLDS:
        result = presented(worldbook)
        persona = personas_for(worldbook)[0]
        assert result["worldbook"] == worldbook
        assert result["worldbook_name"] == get_worldbook(worldbook)["name"]
        assert result["identity"] == THEMES[worldbook]["role_labels"]["villager"]
        assert result["players"][0]["name"] == persona[0]
        assert result["players"][0]["description"] == persona[1]
        assert result["players"][0]["color"] == persona[2]
    assert presented("hyperion")["identity"] == "朝圣者"
    assert presented("threebody")["identity"] == "地球公民"
    assert presented("tidal_archive")["identity"] == "守册人"
    for worldbook in ("hyperion", "threebody", "tidal_archive"):
        assert presented(worldbook)["players"][0]["name"] != PERSONAS[0][0]


def test_present_switches_chapters_action_labels_and_endings():
    for worldbook in WORLDS:
        daytime = state(worldbook, "seer")
        daytime["phase"] = "day_speech"
        daytime["phase_id"] = "phase-day"
        chapter = present(game.player_view(daytime, 1))["chapter"]
        assert chapter == THEMES[worldbook]["chapters"]["day_speech"]

        seer = state(worldbook, "seer")
        seer["queue"] = [game._task("night_seer"), game._task("day_speech")]
        game._advance(seer, NOW)
        view = game.player_view(seer, 1)
        assert "inspect" in view["tools"]
        choices = present(view)["choices"]
        inspect = next(choice for choice in choices if choice["tool"] == "inspect")
        assert inspect["label"] == THEMES[worldbook]["labels"]["inspect"]

        ended = state(worldbook)
        game.event(ended, "ending", {"winner": "village"}, now=NOW)
        result = present(game.player_view(ended, 1))
        assert any(
            line["text"] == THEMES[worldbook]["endings"]["village"] for line in result["story"]
        )
        if worldbook != "mist":
            assert "铜铃" not in chapter
            assert "铜铃" not in inspect["label"]


def test_world_jargon_keeps_mist_default_and_removes_bell_from_other_worlds():
    expected = {
        "hyperion": "灯盏",
        "threebody": "执剑权限",
        "tidal_archive": "潮钟钥匙",
    }
    assert story_language("我先上警，再谈警徽。") == "我先争取铜铃，再谈铜铃。"
    for worldbook in WORLDS:
        text = "我先上警，再谈警徽。"
        state_for_world = state(worldbook)
        game.event(
            state_for_world,
            "action",
            {"tool": "speak", "text": text},
            actor=1,
            now=NOW,
        )
        line = present(game.player_view(state_for_world, 1))["story"][-1]["text"]
        if worldbook == "mist":
            assert line == "我先争取铜铃，再谈铜铃。"
            assert "铜铃" in line
        else:
            assert "铜铃" not in line
            assert expected[worldbook] in line


def test_vision_narration_switches_by_world():
    expected = {
        "mist": "星兆",
        "hyperion": "时隙",
        "threebody": "信号",
        "tidal_archive": "潮影",
    }
    for worldbook in WORLDS:
        state_for_world = state(worldbook, "seer")
        game.event(
            state_for_world,
            "vision",
            {"target": 2, "alignment": "wolves"},
            actor=1,
            audience=[1],
            now=NOW,
        )
        line = present(game.player_view(state_for_world, 1))["story"][-1]["text"]
        assert expected[worldbook] in line
        if worldbook != "mist":
            assert "星兆" not in line


def test_presentation_does_not_leak_other_players_or_secret_entries():
    for worldbook in WORLDS:
        result = presented(worldbook, "villager")
        assert result["players"][1]["role"] is None
        dump = json.dumps(result, ensure_ascii=False)
        for entry in get_worldbook(worldbook)["entries"]:
            if entry["visibility"] != "public":
                assert entry["text"] not in dump
        for role in ROLE_NAMES:
            if role != "villager":
                assert GUIDANCE[role][:12] not in dump


def test_unknown_worldbook_value_falls_back_to_mist():
    view = game.player_view(state("hyperion"), 1)
    view["worldbook"] = "no-such-world"
    fallback = present(view)
    assert fallback["worldbook"] == "mist"
    assert fallback["worldbook_name"] == "雾钟镇"
    assert fallback["identity"] == ROLE_NAMES["villager"]
    assert fallback["players"][0]["name"] == PERSONAS[0][0]
    assert fallback["players"][0]["color"] == PERSONAS[0][2]


def test_worldbook_roles_switch_without_exposing_hidden_identity():
    for worldbook in WORLDS:
        wolf = presented(worldbook, "wolf")
        assert wolf["identity"] == WOLF_LABELS[worldbook]
        assert wolf["players"][0]["role"] == WOLF_LABELS[worldbook]
        villager = presented(worldbook, "villager")
        assert villager["identity"] == THEMES[worldbook]["role_labels"]["villager"]
        assert all(
            player["role"] is None for player in villager["players"] if player["seat"] != 1
        )
