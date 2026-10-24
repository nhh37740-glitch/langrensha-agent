"""完整剧本验收：真实服务事务及纯规则的稀有边界。"""

import copy
import random
from uuid import uuid4

import pytest

from langrensha import full_game as game
from langrensha.rules import Rejected, Role
from langrensha.service import GameService

NOW = "2026-10-23T00:00:00+00:00"


def new(role="villager"):
    return game.create_full_game(now=NOW, human_role=role, rng=random.Random(9))


def seat(state, role):
    return next(p["seat"] for p in state["players"] if p["role"] == role)


def act(state, actor, tool="abstain", **payload):
    return game.reduce_action(
        state,
        actor,
        {
            "request_id": str(uuid4()),
            "phase_id": state["phase_id"],
            "expected_version": state["version"],
            "tool": tool,
            "payload": payload,
        },
        now=NOW,
    )[0]


def reach(state, phase, *, limit=200):
    for _ in range(limit):
        if state["phase"] == phase:
            return state
        state = act(state, game.pending(state)[0])
    raise AssertionError((phase, state["phase"]))


def task(state, name, **kwargs):
    state = copy.deepcopy(state)
    state["queue"] = [game._task(name, **kwargs), game._task("day_speech")]
    game._advance(state, NOW)
    return state


def test_entire_game_to_village_victory_and_restart(tmp_path):
    service = GameService(tmp_path / "game.db")
    gid = service.create(human_role="villager", full=True, rng=random.Random(9))
    for _ in range(600):
        state = service.host_snapshot(gid)
        if state["winner"]:
            break
        actor = game.pending(state)[0]
        session = service.bind_player(gid, actor)
        view = session.view()
        target = next((s for s in game.alive(state) if s in game.wolves(state)), None)
        tool = "exile_vote" if "exile_vote" in view["tools"] else "abstain"
        payload = {"target": target} if tool == "exile_vote" else {}
        session.submit(
            {
                "request_id": str(uuid4()),
                "phase_id": view["phase_id"],
                "expected_version": view["version"],
                "tool": tool,
                "payload": payload,
            }
        )
        service = GameService(tmp_path / "game.db")
    assert state["winner"] == "village"
    assert service.bind_player(gid, 1).view()["tools"] == []
    assert len(service.bind_player(gid, 1).view()["players"]) == 12


def test_wolf_votes_tie_no_attack_and_private():
    state = new()
    pack = game.wolves(state)
    for actor, target in zip(pack, [1, 1, 2, 2], strict=True):
        state = act(state, actor, "wolf_vote", target=target)
    assert state["night"]["attack"] is None
    assert any(e["kind"] == "wolf_tally" for e in game.player_view(state, pack[0])["events"])
    assert not any(e["kind"] == "wolf_tally" for e in game.player_view(state, 1)["events"])


def test_witch_resources_no_self_rescue_and_poison_suppresses_hunter():
    state = new()
    witch, hunter = seat(state, Role.WITCH), seat(state, Role.HUNTER)
    for actor in game.wolves(state):
        state = act(state, actor, "wolf_vote", target=witch)
    assert "antidote" not in game.tools(state, witch)
    state = act(state, witch, "poison", target=hunter)
    assert not state["poison"] and state["antidote"]
    state = reach(state, "last_words")
    assert not game.player(state, hunter)["alive"]
    assert state["phase"] != "hunter"
    assert not any(t["name"] == "hunter" for t in state["queue"])
    # 先做警长竞选，随后才公开夜间死亡。
    kinds = [e["kind"] for e in state["events"]]
    assert kinds.index("badge") < kinds.index("deaths")


def test_antidote_consumed_only_once_and_death_cause_hidden():
    state = new()
    for actor in game.wolves(state):
        state = act(state, actor, "wolf_vote", target=1)
    witch = seat(state, Role.WITCH)
    state = act(state, witch, "antidote")
    assert state["night"]["saved"] and not state["antidote"]
    state = reach(state, "day_speech")
    assert game.player(state, 1)["alive"]
    assert not any(e["kind"] == "deaths" for e in state["events"])


def test_seer_repeat_and_self_rejected_without_mutation():
    state = reach(new(), "night_seer")
    seer = seat(state, Role.SEER)
    before = copy.deepcopy(state)
    with pytest.raises(Rejected, match="invalid_target"):
        act(state, seer, "inspect", target=seer)
    assert before == state
    state = act(state, seer, "inspect", target=1)
    result = [e for e in game.player_view(state, seer)["events"] if e["kind"] == "vision"][-1]
    assert result["data"] == {"target": 1, "alignment": "village"}
    assert not any(e["kind"] == "vision" for e in game.player_view(state, 1)["events"])
    state = reach(state, "night_seer")
    assert 1 not in game.targets(state, seer, "inspect")


def test_election_dropout_no_vote_and_weighted_exile():
    state = reach(new(), "sheriff_signup")
    for actor in list(game.pending(state)):
        state = act(state, actor, "signup" if actor in {1, 2, 3} else "abstain")
    state = reach(state, "sheriff_withdraw")
    state = act(state, 1, "withdraw")
    state = act(state, 2)
    state = act(state, 3)
    assert 1 not in game.pending(state) and 2 not in game.pending(state)
    for actor in list(game.pending(state)):
        state = act(state, actor, "sheriff_vote", target=2)
    assert state["sheriff"] == 2
    state = reach(state, "day_speech")
    assert state["actors"][-1] == 2
    state = reach(state, "exile_vote")
    living = list(game.pending(state))
    for actor in living:
        if actor == 2:
            state = act(state, actor, "exile_vote", target=1)
        elif actor == 3:
            state = act(state, actor, "exile_vote", target=4)
        else:
            state = act(state, actor)
    assert not game.player(state, 1)["alive"]
    tally = [e for e in state["events"] if e["kind"] == "ballot_result"][-1]
    assert tally["data"]["counts"] == {"1": 1.5, "4": 1}


@pytest.mark.parametrize("election", [True, False])
def test_tie_once_then_no_result(election):
    state = reach(new(), "sheriff_signup")
    if election:
        for actor in list(game.pending(state)):
            state = act(state, actor, "signup" if actor in {1, 2} else "abstain")
        state = reach(state, "sheriff_vote")
        tool, pk = "sheriff_vote", "sheriff_pk_vote"
    else:
        state = reach(state, "exile_vote")
        tool, pk = "exile_vote", "exile_pk_vote"
    voters = list(game.pending(state))
    for index, actor in enumerate(voters):
        state = act(state, actor, tool, target=1 if index % 2 == 0 else 2)
    state = reach(state, pk)
    assert all(s not in game.pending(state) for s in {1, 2})
    for index, actor in enumerate(list(game.pending(state))):
        state = act(state, actor, tool, target=1 if index % 2 == 0 else 2)
    assert state["sheriff"] is None
    assert all(p["alive"] for p in state["players"])


def test_idiot_reveal_then_cannot_vote_but_can_speak():
    state = task(new(), "idiot", seat=seat(new(), Role.IDIOT))
    idiot = seat(state, Role.IDIOT)
    state = act(state, idiot, "reveal")
    assert game.player(state, idiot)["alive"] and not game.player(state, idiot)["can_vote"]
    assert idiot in state["actors"]
    state = task(state, "exile_vote")
    assert idiot not in game.pending(state)


def test_hunter_chain_badge_and_no_shot_after_victory():
    state = new()
    hunter, target = seat(state, Role.HUNTER), seat(state, Role.WITCH)
    state["sheriff"] = hunter
    state["queue"] = [game._task("day_speech")]
    game._kill(state, {hunter: "exile"}, NOW, daytime=True)
    game._advance(state, NOW)
    assert state["phase"] == "hunter"
    state = act(state, hunter, "shoot", target=target)
    assert not game.player(state, target)["alive"] and state["phase"] == "last_words"
    state = reach(state, "badge")
    state = act(state, hunter, "transfer_badge", target=1)
    assert state["sheriff"] == 1
    state = new()
    for p in state["players"]:
        if p["role"] in {Role.SEER, Role.WITCH, Role.IDIOT}:
            p["alive"] = False
    game._kill(state, {seat(state, Role.HUNTER): "attack"}, NOW)
    assert state["winner"] == "wolves" and game.pending(state) == []


def test_double_explode_cancels_election_and_day():
    state = reach(new(), "sheriff_signup")
    pack = game.wolves(state)
    state = act(state, pack[0], "explode")
    state = reach(state, "sheriff_signup")
    assert state["round"] == 2 and state["election_explosions"] == 1
    state = act(state, pack[1], "explode")
    assert state["election_done"] and state["sheriff"] is None
    state = reach(state, "day_speech")
    assert state["round"] == 3


def test_dead_wolf_no_new_private_events_and_ending_keeps_private_history_hidden():
    state = new()
    pack = game.wolves(state)
    state = act(state, pack[0], "wolf_chat", text="before")
    state["queue"] = [game._task("next_night")]
    game._kill(state, {pack[0]: "exile"}, NOW)
    game._advance(state, NOW)
    state = reach(state, "night_wolves")
    state = act(state, pack[1], "wolf_chat", text="after")
    texts = [e["data"].get("text") for e in game.player_view(state, pack[0])["events"]]
    assert "before" in texts and "after" not in texts
    assert "after" not in json_text(game.player_view(state, 1))


def json_text(value):
    import json

    return json.dumps(value)


def test_full_idempotency_and_strict_payload():
    state = new()
    actor = game.pending(state)[0]
    command = {
        "request_id": "same",
        "phase_id": state["phase_id"],
        "expected_version": state["version"],
        "tool": "wolf_vote",
        "payload": {"target": 1},
    }
    updated, result = game.reduce_action(state, actor, command, now=NOW)
    retried, repeated = game.reduce_action(updated, actor, command, now=NOW)
    assert retried == updated and result == repeated
    for value in [True, 0, 13, "1"]:
        with pytest.raises(Rejected):
            act(state, actor, "wolf_vote", target=value)
    with pytest.raises(Rejected):
        act(state, actor, "wolf_vote", target=1, forged_actor=actor)


def test_ballots_are_not_revealed_before_everyone_finishes():
    state = reach(new(), "exile_vote")
    state = act(state, 1, "exile_vote", target=2)
    assert not any(
        e["data"].get("tool") == "exile_vote" for e in game.player_view(state, 2)["events"]
    )
    for actor in list(game.pending(state)):
        state = act(state, actor)
    tally = [e for e in game.player_view(state, 2)["events"] if e["kind"] == "ballot_result"][-1]
    assert tally["data"]["ballots"]["1"] == 2


def test_explosion_settles_pending_night_deaths_together_before_victory():
    state = reach(new(), "sheriff_signup")
    pack = game.wolves(state)
    for wolf in pack[1:]:
        game.player(state, wolf)["alive"] = False
    villagers = [p for p in state["players"] if p["role"] == Role.VILLAGER]
    for p in villagers[1:]:
        p["alive"] = False
    state["night"]["attack"] = villagers[0]["seat"]
    state = act(state, pack[0], "explode")
    assert state["winner"] == "draw"
    assert not game.player(state, villagers[0]["seat"])["alive"]


@pytest.mark.parametrize("seed", range(15))
def test_legal_random_play_reaches_a_consistent_ending(seed):
    state = game.create_full_game(now=NOW, rng=random.Random(seed))
    rng = random.Random(seed + 100)
    for _ in range(500):
        if state["winner"]:
            break
        actors = game.pending(state)
        assert actors
        actor = actors[0]
        names = [t for t in game.tools(state, actor) if t not in {"wolf_chat", "explode"}]
        tool = rng.choice(names)
        payload = {}
        if tool in game.TARGET_TOOLS:
            possible = game.targets(state, actor, tool)
            if possible:
                payload = {"target": rng.choice(possible)}
            else:
                tool = "abstain"
        elif tool == "speak":
            payload = {"text": "让我再听听钟楼下的证词。"}
        previous = state["version"]
        state = act(state, actor, tool, **payload)
        assert state["version"] == previous + 1
    assert state["winner"] in {"wolves", "village", "draw"}
    assert game.pending(state) == []


def test_seer_may_repeat_after_skipping_a_night():
    state = reach(new(), "night_seer")
    seer = seat(state, Role.SEER)
    state = act(state, seer, "inspect", target=1)
    state = reach(state, "night_seer")
    assert 1 not in game.targets(state, seer, "inspect")
    state = act(state, seer)
    state = reach(state, "night_seer")
    assert 1 in game.targets(state, seer, "inspect")


@pytest.mark.parametrize(
    "phase", ["sheriff_vote", "sheriff_pk_vote", "exile_vote", "exile_pk_vote"]
)
def test_explosion_is_public_even_during_secret_ballots(phase):
    state = new()
    state["election_done"] = True
    state["candidates"] = [1, 2]
    state["candidates_pk"] = [1, 2]
    state = task(state, phase)
    wolf = game.wolves(state)[0]
    state = act(state, wolf, "explode")
    ordinary = game.player_view(state, 1)
    assert any(e["data"].get("tool") == "explode" for e in ordinary["events"])
    assert ordinary["players"][wolf - 1]["role"] == Role.WOLF
