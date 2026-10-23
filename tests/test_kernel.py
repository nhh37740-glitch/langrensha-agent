"""核查规则结果、重试、并发、恢复和实际玩家视图；不调用外部模型。"""

import json
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from langrensha.rules import DAY, DECK, NIGHT, Rejected, Role, tally
from langrensha.service import GameService


@pytest.fixture
def game(tmp_path):
    service = GameService(tmp_path / "games.sqlite3")
    game_id = service.create(human_seat=2, human_role=Role.VILLAGER, rng=random.Random(7))
    return service, game_id


def session_for(game, role=Role.WOLF):
    service, game_id = game
    seat = next(p["seat"] for p in service.host_snapshot(game_id)["players"] if p["role"] == role)
    return service.bind_player(game_id, seat)


def command(session, tool="abstain", payload=None):
    view = session.view()
    return {
        "request_id": str(uuid4()),
        "phase_id": view["phase_id"],
        "expected_version": view["version"],
        "tool": tool,
        "payload": payload or {},
    }


def night(game, votes=None):
    service, game_id = game
    wolf_seats = [
        p["seat"] for p in service.host_snapshot(game_id)["players"] if p["role"] == Role.WOLF
    ]
    for seat, target in zip(wolf_seats, votes or [None] * 4, strict=True):
        session = service.bind_player(game_id, seat)
        action = command(session, "wolf_vote", {"target": target}) if target else command(session)
        session.submit(action)
    return wolf_seats


def test_deck_and_human_selection(game):
    service, game_id = game
    players = service.host_snapshot(game_id)["players"]
    assert Counter(p["role"] for p in players) == Counter(DECK)
    assert sum(p["human"] for p in players) == 1
    assert players[1] == {"seat": 2, "role": "villager", "human": True}


@pytest.mark.parametrize("role", list(Role) + [None])
def test_each_human_role_and_random(tmp_path, role):
    service = GameService(tmp_path / "roles.db")
    game_id = service.create(human_seat=12, human_role=role)
    players = service.host_snapshot(game_id)["players"]
    assert Counter(p["role"] for p in players) == Counter(DECK)
    if role:
        assert service.bind_player(game_id, 12).view()["role"] == role


@pytest.mark.parametrize(
    "votes,expected",
    [
        ([2, 2, 3, None], (2, "unique")),
        ([2, 2, 3, 3], (None, "tie")),
        ([None] * 4, (None, "no_votes")),
        ([2, None, None, None], (2, "unique")),
    ],
)
def test_wolf_result_and_confidentiality(game, votes, expected):
    service, game_id = game
    seats = night(game, votes)
    for seat in range(1, 13):
        view = service.bind_player(game_id, seat).view()
        results = [e for e in view["events"] if e["kind"] == "wolf_tally"]
        private_actions = [
            e for e in view["events"] if e["kind"] == "action" and e["data"]["tool"] != "speak"
        ]
        assert view["phase"] == DAY
        if seat in seats:
            assert len(results) == 1 and len(private_actions) == 4
            assert (results[0]["data"]["target"], results[0]["data"]["reason"]) == expected
        else:
            assert results == [] and private_actions == [] and view["wolf_team"] == []


def test_complete_cycle_survives_process_restart(game):
    service, game_id = game
    night(game, [2, 2, 3, None])
    service = GameService(service.store.path)
    for seat in range(1, 13):
        session = service.bind_player(game_id, seat)
        session.submit(command(session, "speak", {"text": f"我记住了第{seat}处脚步声。"}))
    restored = GameService(service.store.path)
    state = restored.host_snapshot(game_id)
    assert state["round"] == 2 and state["phase"] == NIGHT
    assert state["version"] == 16
    assert len([e for e in state["events"] if e["kind"] == "action"]) == 16
    assert len([e for e in state["events"] if e["kind"] == "phase_changed"]) == 2
    assert all(e["game_id"] == game_id and e["time"] for e in state["events"])


def test_retry_after_phase_change_is_same_result(game):
    service, game_id = game
    wolf_seats = [
        p["seat"] for p in service.host_snapshot(game_id)["players"] if p["role"] == Role.WOLF
    ]
    for seat in wolf_seats[:-1]:
        session = service.bind_player(game_id, seat)
        session.submit(command(session))
    session = service.bind_player(game_id, wolf_seats[-1])
    action = command(session, "wolf_vote", {"target": 2})
    receipt = session.submit(action)
    snapshot = service.host_snapshot(game_id)
    assert session.submit(action) == receipt
    assert service.host_snapshot(game_id) == snapshot


def test_request_id_conflict_and_closed_window(game):
    session = session_for(game)
    action = command(session, "wolf_vote", {"target": 2})
    session.submit(action)
    changed = {**action, "payload": {"target": 3}}
    with pytest.raises(Rejected, match="request_id_conflict"):
        session.submit(changed)
    with pytest.raises(Rejected, match="tool_not_allowed"):
        session.submit(command(session))


def test_retry_with_boolean_in_place_of_integer_is_conflict(game):
    session = session_for(game)
    action = command(session, "wolf_vote", {"target": 1})
    session.submit(action)
    with pytest.raises(Rejected, match="request_id_conflict"):
        session.submit({**action, "payload": {"target": True}})


def test_rejected_command_keeps_snapshot_and_records_host_only_audit(game):
    service, game_id = game
    session = session_for(game, Role.VILLAGER)
    before = service.host_snapshot(game_id)
    with pytest.raises(Rejected, match="tool_not_allowed"):
        session.submit(command(session, "wolf_chat", {"text": "secret-token"}))
    assert service.host_snapshot(game_id) == before
    assert service.host_rejections(game_id)[0]["code"] == "tool_not_allowed"
    assert "rejections" not in session.view()
    assert "secret-token" not in json.dumps(service.host_rejections(game_id))


@pytest.mark.parametrize("target", [True, False, 0, 13, "2", 1.5, None])
def test_invalid_targets_do_not_advance(game, target):
    service, game_id = game
    session = session_for(game)
    before = service.host_snapshot(game_id)
    with pytest.raises(Rejected, match="invalid_seat"):
        session.submit(command(session, "wolf_vote", {"target": target}))
    assert service.host_snapshot(game_id) == before


@pytest.mark.parametrize("text", ["", "  ", 12, None, "字" * 4001])
def test_invalid_chat_is_rejected(game, text):
    session = session_for(game)
    with pytest.raises(Rejected, match="invalid_text"):
        session.submit(command(session, "wolf_chat", {"text": text}))


def test_chat_does_not_end_action_and_is_private(game):
    service, game_id = game
    wolf = session_for(game)
    wolf.submit(command(wolf, "wolf_chat", {"text": "今晚注意古井。"}))
    assert "wolf_vote" in wolf.view()["tools"]
    assert any(e.get("data", {}).get("text") == "今晚注意古井。" for e in wolf.view()["events"])
    for role in (Role.VILLAGER, Role.SEER, Role.WITCH, Role.HUNTER, Role.IDIOT):
        assert "今晚注意古井" not in json.dumps(session_for(game, role).view(), ensure_ascii=False)
    assert service.host_snapshot(game_id)["completed"] == {}


def test_no_forged_actor_or_extra_parameters(game):
    session = session_for(game)
    action = command(session)
    with pytest.raises(Rejected, match="invalid_command"):
        session.submit({**action, "actor": 2})
    with pytest.raises(Rejected, match="invalid_payload"):
        session.submit({**action, "payload": {"role": "wolf"}})


@pytest.mark.parametrize("value", [{1, 2}, float("nan"), float("inf")])
def test_non_json_request_is_rejected_with_audit(game, value):
    service, game_id = game
    session = session_for(game)
    with pytest.raises(Rejected, match="invalid_command"):
        session.submit(command(session, "wolf_vote", {"target": value}))
    assert service.host_rejections(game_id)[-1]["code"] == "invalid_command"


def test_stale_calls_and_turn_order(game):
    wolf = session_for(game)
    stale = command(wolf)
    wolf.submit(command(wolf, "wolf_chat", {"text": "稍后再议。"}))
    with pytest.raises(Rejected, match="stale_version"):
        wolf.submit(stale)
    for seat in [
        p["seat"] for p in game[0].host_snapshot(game[1])["players"] if p["role"] == Role.WOLF
    ]:
        session = game[0].bind_player(game[1], seat)
        session.submit(command(session))
    with pytest.raises(Rejected, match="stale_phase"):
        wolf.submit(stale)
    second = game[0].bind_player(game[1], 2)
    with pytest.raises(Rejected, match="tool_not_allowed"):
        second.submit(command(second, "speak", {"text": "提前发言。"}))


def test_concurrent_duplicate_applies_exactly_once(game):
    service, game_id = game
    session = session_for(game)
    action = command(session, "wolf_vote", {"target": 2})
    with ThreadPoolExecutor(max_workers=8) as executor:
        receipts = list(executor.map(lambda _: session.submit(action), range(8)))
    assert all(receipt == receipts[0] for receipt in receipts)
    state = service.host_snapshot(game_id)
    assert state["version"] == 1
    assert len(state["completed"]) == 1


def test_concurrent_conflicting_requests_cannot_double_act(game):
    service, game_id = game
    session = session_for(game)
    first, second = command(session), command(session, "wolf_vote", {"target": 2})

    def submit(action):
        try:
            return session.submit(action)["accepted"]
        except Rejected:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(submit, [first, second])) == [False, True]
    assert service.host_snapshot(game_id)["version"] == 1


def test_views_and_receipts_cannot_mutate_persisted_game(game):
    service, game_id = game
    session = session_for(game)
    view = session.view()
    view["events"][0]["data"]["mode"] = "tampered"
    view["wolf_team"].clear()
    assert service.host_snapshot(game_id)["mode"] == "kernel_rehearsal"
    action = command(session)
    receipt = session.submit(action)
    receipt["accepted"] = False
    assert session.submit(action)["accepted"] is True


def test_games_and_actor_receipts_are_isolated(game):
    service, game_id = game
    other_id = service.create()
    first = session_for(game)
    first.submit(command(first, "wolf_chat", {"text": "只属于本局的暗号。"}))
    assert "只属于本局" not in json.dumps(service.host_snapshot(other_id), ensure_ascii=False)
    for seat in range(1, 13):
        view = service.bind_player(game_id, seat).view()
        identities = [e for e in view["events"] if e["kind"] == "identity"]
        assert len(identities) == 1 and identities[0]["actor"] == seat
        assert "receipts" not in view and "players" not in view


def test_tally_pure_function_does_not_change_votes():
    votes = [2, 2, 3, None]
    assert tally(votes)["counts"] == {"2": 2, "3": 1}
    assert votes == [2, 2, 3, None]
