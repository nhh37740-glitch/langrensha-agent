import random
from uuid import uuid4

import pytest

from langrensha import full_game as game
from langrensha.presentation import PHASE_NAMES, present

NOW = "2026-10-24T00:00:00Z"


def window(role):
    state = game.create_full_game(now=NOW, human_role=role, rng=random.Random(9))
    if role == "hunter":
        state["queue"] = [game._task("day_speech")]
        game._kill(state, {1: "attack"}, NOW)
    else:
        state["queue"] = [game._task("idiot", seat=1), game._task("day_speech")]
    game._advance(state, NOW)
    return state


def submit(state, tool, payload):
    return game.reduce_action(
        state,
        1,
        {
            "request_id": str(uuid4()),
            "phase_id": state["phase_id"],
            "expected_version": state["version"],
            "tool": tool,
            "payload": payload,
        },
        now=NOW,
    )[0]


@pytest.mark.parametrize(
    "role,tool,public_phase",
    [
        ("hunter", "shoot", "last_words"),
        ("idiot", "reveal", "exile_vote"),
    ],
)
def test_private_skill_prompt_and_decline_do_not_reveal_identity(role, tool, public_phase):
    state = window(role)
    own = present(game.player_view(state, 1))
    assert any(c["tool"] == tool for c in own["choices"])
    ordinary = present(game.player_view(state, 2))
    assert ordinary["chapter"] == PHASE_NAMES[public_phase]
    assert ordinary["players"][0]["role"] is None
    updated = submit(state, "abstain", {})
    other = game.player_view(updated, 2)
    assert not any(e["actor"] == 1 and e["data"].get("tool") == "abstain" for e in other["events"])
    assert "role" not in other["players"][0]
    assert any(e["data"].get("tool") == "abstain" for e in game.player_view(updated, 1)["events"])


@pytest.mark.parametrize("role,tool", [("hunter", "shoot"), ("idiot", "reveal")])
def test_used_skill_still_reveals_identity_and_visible_effect(role, tool):
    state = window(role)
    target = next(p["seat"] for p in state["players"] if p["role"] == "villager")
    updated = submit(state, tool, {"target": target} if tool == "shoot" else {})
    view = game.player_view(updated, 2)
    assert view["players"][0]["role"] == role
    assert any(e["kind"] == "reveal" and e["data"]["seat"] == 1 for e in view["events"])
