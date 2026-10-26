"""四世界技能名称、资源、说明与治疗/伤害动效映射；不依赖浏览器。"""

import random
from uuid import uuid4

import pytest

from langrensha import full_game as game
from langrensha.presentation import LABELS, THEMES, present
from langrensha.worldbooks import worldbook_ids

NOW = "2026-10-24T00:00:00Z"

EXPECTED = {
    "mist": {
        "antidote": ("送出解药", "解药", "heal"),
        "poison": ("送出毒药", "毒药", "harm"),
    },
    "hyperion": {
        "antidote": ("送出修复剂", "修复剂", "heal"),
        "poison": ("送出神经毒素", "神经毒素", "harm"),
    },
    "threebody": {
        "antidote": ("执行修复预案", "修复预案", "heal"),
        "poison": ("执行清除预案", "清除预案", "harm"),
    },
    "tidal_archive": {
        "antidote": ("送出返名盐", "返名盐", "heal"),
        "poison": ("送出蚀名盐", "蚀名盐", "harm"),
    },
}


def witch_view(worldbook_id):
    state = game.create_full_game(now=NOW, human_role="witch", rng=random.Random(9))
    state["worldbook"] = worldbook_id
    state["queue"] = [game._task("night_witch", seat=1)]
    game._advance(state, NOW)
    state["night"]["attack"] = 2
    return state, game.player_view(state, 1)


@pytest.mark.parametrize("worldbook_id", worldbook_ids())
def test_theme_has_complete_skill_labels_and_resource_names(worldbook_id):
    expected = EXPECTED[worldbook_id]
    theme = THEMES[worldbook_id]
    assert set(theme["labels"]) == set(LABELS)
    assert set(theme["resource_labels"]) == {"antidote", "poison"}
    assert {"antidote", "poison"} <= set(theme["skill_notes"])
    for tool in ("antidote", "poison"):
        label, resource, _effect = expected[tool]
        assert theme["labels"][tool] == label
        assert theme["resource_labels"][tool] == resource
        assert theme["skill_notes"][tool]


@pytest.mark.parametrize("worldbook_id", worldbook_ids())
def test_present_uses_world_resources_labels_and_descriptions(worldbook_id):
    expected = EXPECTED[worldbook_id]
    _state, view = witch_view(worldbook_id)
    payload = present(view)
    assert payload["resources"] == {
        expected["antidote"][1]: True,
        expected["poison"][1]: True,
    }
    choices = {choice["tool"]: choice for choice in payload["choices"]}
    for tool in ("antidote", "poison"):
        label, _resource, _effect = expected[tool]
        assert choices[tool]["label"] == label
        assert choices[tool]["description"] == THEMES[worldbook_id]["skill_notes"][tool]


@pytest.mark.parametrize("worldbook_id", worldbook_ids())
@pytest.mark.parametrize("tool", ["antidote", "poison"])
def test_antidote_and_poison_use_distinct_effect_keys(worldbook_id, tool):
    state, view = witch_view(worldbook_id)
    command = {
        "request_id": str(uuid4()),
        "phase_id": view["phase_id"],
        "expected_version": view["version"],
        "tool": tool,
        "payload": {} if tool == "antidote" else {"target": 3},
    }
    updated, _result = game.reduce_action(state, 1, command, now=NOW)
    effects = [
        line["effect"]
        for line in present(game.player_view(updated, 1))["story"]
        if line["effect"]
    ]
    assert EXPECTED[worldbook_id][tool][2] in effects
