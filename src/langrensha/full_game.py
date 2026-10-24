"""mist-v1 完整裁定；纯函数状态机，玩家和模型均不能指定主持事实。"""

import copy
import json
from collections import Counter
from uuid import uuid4

from .rules import Rejected, Role, _text, create_game, event, seat_number, wolves

SPEECH = {"sheriff_speech", "sheriff_pk_speech", "day_speech", "exile_pk_speech", "last_words"}
VOTES = {"sheriff_vote", "sheriff_pk_vote", "exile_vote", "exile_pk_vote", "night_wolves"}
ELECTION = {
    "sheriff_signup",
    "sheriff_speech",
    "sheriff_withdraw",
    "sheriff_vote",
    "sheriff_pk_speech",
    "sheriff_pk_vote",
}
TARGET_TOOLS = {
    "wolf_vote",
    "inspect",
    "poison",
    "shoot",
    "transfer_badge",
    "sheriff_vote",
    "exile_vote",
}
TEXT_TOOLS = {"speak", "wolf_chat"}


def player(state, seat):
    return state["players"][seat - 1]


def alive(state):
    return [p["seat"] for p in state["players"] if p["alive"]]


def create_full_game(*, now, human_seat=1, human_role=None, rng=None):
    state = create_game(now=now, human_seat=human_seat, human_role=human_role, rng=rng)
    state.update(
        mode="full_game",
        rules="mist-v1",
        queue=[],
        winner=None,
        sheriff=None,
        election_done=False,
        election_explosions=0,
        candidates=[],
        registered=[],
        antidote=True,
        poison=True,
        seer_last=None,
        night={},
        candidates_pk=[],
    )
    for p in state["players"]:
        p.update(alive=True, revealed=False, can_vote=True, died_at=None)
    state["events"][0]["data"]["mode"] = "full_game"
    _night(state)
    _advance(state, now)
    return state


def _task(name, **data):
    return {"name": name, **data}


def _prepend(state, tasks):
    state["queue"] = tasks + state["queue"]


def _night(state):
    state["night"] = {"attack": None, "poison": None, "saved": False}
    tasks = [_task("night_wolves"), _task("night_witch"), _task("night_seer")]
    if not state["election_done"]:
        tasks += [
            _task("sheriff_signup"),
            _task("sheriff_speech"),
            _task("sheriff_withdraw"),
            _task("sheriff_vote"),
        ]
    state["queue"] = tasks + [
        _task("dawn"),
        _task("day_speech"),
        _task("exile_vote"),
        _task("next_night"),
    ]


def _victory(state, now):
    living = [p for p in state["players"] if p["alive"]]
    good = not any(p["role"] == Role.WOLF for p in living)
    bad = not any(p["role"] == Role.VILLAGER for p in living) or not any(
        p["role"] not in {Role.WOLF, Role.VILLAGER} for p in living
    )
    if good or bad:
        state["winner"] = "draw" if good and bad else ("village" if good else "wolves")
        state["queue"] = []
        state["phase"] = "ended"
        state["phase_id"] = str(uuid4())
        state["actors"] = []
        event(
            state,
            "ending",
            {
                "winner": state["winner"],
                "identities": [{"seat": p["seat"], "role": p["role"]} for p in state["players"]],
            },
            now=now,
        )
        return True
    return False


def _kill(state, deaths, now, *, daytime=False, explode=None):
    """同时更新死亡；公开死讯不附死因。deaths 是主持专属的 seat -> 原因。"""
    deaths = {s: cause for s, cause in deaths.items() if player(state, s)["alive"]}
    if not deaths:
        return
    event_id = event(state, "deaths", {"seats": sorted(deaths)}, now=now)
    for seat in deaths:
        player(state, seat).update(alive=False, died_at=event_id)
    if _victory(state, now):
        return
    effects = []
    for seat, cause in sorted(deaths.items()):
        if player(state, seat)["role"] == Role.HUNTER and cause != "poison":
            effects.append(_task("hunter", seat=seat, daytime=daytime))
        if seat == state["sheriff"]:
            effects.append(_task("badge", seat=seat))
        if daytime or state["round"] == 1 or seat == explode:
            effects.append(_task("last_words", seat=seat))
    _prepend(state, effects)


def _dawn(state, now):
    night = state["night"]
    deaths = {}
    if night["attack"] is not None and not night["saved"]:
        deaths[night["attack"]] = "attack"
    if night["poison"] is not None:
        deaths[night["poison"]] = "poison"
    state["night"] = {"attack": None, "poison": None, "saved": False}
    event(state, "dawn", {"round": state["round"]}, now=now)
    _kill(state, deaths, now)


def _voters(state):
    return [s for s in alive(state) if player(state, s)["can_vote"]]


def pending(state):
    candidates = [s for s in state.get("actors", []) if str(s) not in state["completed"]]
    return candidates[:1] if state["phase"] in SPEECH else candidates


def _advance(state, now):
    # 空阶段自动跳过，不通过公开口播透露是否仍有对应夜间身份。
    for _ in range(100):
        if state["winner"] or not state["queue"]:
            return
        task = state["queue"].pop(0)
        phase = task["name"]
        state.update(phase=phase, phase_id=str(uuid4()), completed={}, task=task)
        seats = alive(state)
        if phase == "next_night":
            state["round"] += 1
            _night(state)
            continue
        if phase == "dawn":
            _dawn(state, now)
            continue
        if phase == "night_wolves":
            actors = [s for s in wolves(state) if s in seats]
        elif phase in {"night_witch", "night_seer"}:
            role = Role.WITCH if phase == "night_witch" else Role.SEER
            actors = [s for s in seats if player(state, s)["role"] == role]
        elif phase == "sheriff_signup":
            state["candidates"], state["registered"] = [], []
            actors = seats
        elif phase in {"sheriff_speech", "sheriff_withdraw"}:
            actors = list(state["candidates"])
        elif phase in {"sheriff_vote", "sheriff_pk_vote"}:
            targets = state["candidates"] if phase == "sheriff_vote" else state["candidates_pk"]
            if phase == "sheriff_vote" and len(targets) <= 1:
                _elect(state, targets[0] if targets else None, now)
                continue
            actors = [s for s in _voters(state) if s not in state["registered"]]
        elif phase in {"sheriff_pk_speech", "exile_pk_speech"}:
            actors = list(state["candidates_pk"])
        elif phase == "day_speech":
            actors = [s for s in seats if s != state["sheriff"]]
            if state["sheriff"] in seats:
                actors.append(state["sheriff"])
        elif phase in {"exile_vote", "exile_pk_vote"}:
            actors = _voters(state)
            if phase == "exile_pk_vote":
                actors = [s for s in actors if s not in state["candidates_pk"]]
        else:
            actors = [task["seat"]]
        state["actors"] = actors
        if actors:
            return
        _settle(state, now)
    raise RuntimeError("phase_transition_limit")


def _elect(state, seat, now):
    state["sheriff"] = seat
    state["election_done"] = True
    event(state, "badge", {"seat": seat}, now=now)


def _count(state, *, weighted):
    counts = Counter()
    for actor, target in state["completed"].items():
        if type(target) is int:
            counts[target] += 1.5 if weighted and int(actor) == state["sheriff"] else 1
    maximum = max(counts.values(), default=0)
    return [s for s, n in counts.items() if n == maximum], {str(s): n for s, n in counts.items()}


def _settle(state, now):
    phase = state["phase"]
    if phase == "night_wolves":
        leaders, counts = _count(state, weighted=False)
        target = leaders[0] if len(leaders) == 1 else None
        state["night"]["attack"] = target
        event(
            state,
            "wolf_tally",
            {"target": target, "counts": counts},
            audience=wolves(state),
            now=now,
        )
    elif phase in {"sheriff_vote", "sheriff_pk_vote", "exile_vote", "exile_pk_vote"}:
        leaders, counts = _count(state, weighted=phase.startswith("exile"))
        event(
            state,
            "ballot_result",
            {
                "counts": counts,
                "leaders": leaders,
                "election": phase.startswith("sheriff"),
                "ballots": dict(state["completed"]),
            },
            now=now,
        )
        if len(leaders) > 1 and phase in {"sheriff_vote", "exile_vote"}:
            state["candidates_pk"] = sorted(leaders)
            stem = "sheriff" if phase.startswith("sheriff") else "exile"
            _prepend(state, [_task(stem + "_pk_speech"), _task(stem + "_pk_vote")])
        elif phase.startswith("sheriff"):
            _elect(state, leaders[0] if len(leaders) == 1 else None, now)
        elif len(leaders) == 1:
            target = leaders[0]
            p = player(state, target)
            if p["role"] == Role.IDIOT and not p["revealed"]:
                _prepend(state, [_task("idiot", seat=target)])
            else:
                _kill(state, {target: "exile"}, now, daytime=True)


def targets(state, actor, tool):
    seats = alive(state)
    if tool == "inspect":
        return [s for s in seats if s not in {actor, state["seer_last"]}]
    if tool in {"shoot", "transfer_badge"}:
        return [s for s in seats if s != actor]
    if tool == "sheriff_vote":
        return list(
            state["candidates_pk"] if state["phase"] == "sheriff_pk_vote" else state["candidates"]
        )
    if tool == "exile_vote" and state["phase"] == "exile_pk_vote":
        return list(state["candidates_pk"])
    return seats


def tools(state, actor):
    seat_number(actor)
    if state["winner"]:
        return []
    p, phase = player(state, actor), state["phase"]
    extra = (
        ["explode"]
        if p["alive"]
        and p["role"] == Role.WOLF
        and (
            phase in ELECTION
            or phase in {"day_speech", "exile_vote", "exile_pk_speech", "exile_pk_vote"}
        )
        else []
    )
    if actor not in pending(state):
        return extra
    active = {
        "night_wolves": ["wolf_chat", "wolf_vote"],
        "night_seer": ["inspect"],
        "sheriff_signup": ["signup"],
        "sheriff_withdraw": ["withdraw"],
        "sheriff_vote": ["sheriff_vote"],
        "sheriff_pk_vote": ["sheriff_vote"],
        "exile_vote": ["exile_vote"],
        "exile_pk_vote": ["exile_vote"],
        "hunter": ["shoot"],
        "idiot": ["reveal"],
        "badge": ["transfer_badge"],
    }.get(phase, ["speak"] if phase in SPEECH else [])
    if phase == "night_witch":
        active = []
        if state["antidote"] and state["night"]["attack"] not in {None, actor}:
            active.append("antidote")
        if state["poison"]:
            active.append("poison")
    return active + ["abstain"] + extra


def _apply(state, actor, tool, payload, now):
    phase = state["phase"]
    private = phase.startswith("night_")
    audience = (
        wolves(state)
        if phase == "night_wolves"
        else ([actor] if private or phase in VOTES else None)
    )
    # 技能内部名字只保留在主持事实；对外事件由各自可见视图转为剧本文案。
    event_id = event(
        state, "action", {"tool": tool, **payload}, actor=actor, audience=audience, now=now
    )
    if tool == "wolf_chat":
        return event_id
    if tool == "explode":
        interrupted = not state["election_done"]
        if interrupted:
            state["election_explosions"] += 1
            if state["election_explosions"] >= 2:
                _elect(state, None, now)
        state["queue"] = [_task("next_night")]
        deaths = {actor: "explode"}
        if interrupted:
            night = state["night"]
            if night["attack"] is not None and not night["saved"]:
                deaths[night["attack"]] = "attack"
            if night["poison"] is not None:
                deaths[night["poison"]] = "poison"
            state["night"] = {"attack": None, "poison": None, "saved": False}
            event(state, "dawn", {"round": state["round"]}, now=now)
        _kill(state, deaths, now, daytime=not interrupted, explode=actor)
        _advance(state, now)
        return event_id
    if tool == "signup":
        state["candidates"].append(actor)
        state["registered"].append(actor)
    elif tool == "withdraw":
        state["candidates"].remove(actor)
    elif tool == "inspect":
        target = payload["target"]
        state["seer_last"] = target
        event(
            state,
            "vision",
            {"target": target, "alignment": "wolves" if target in wolves(state) else "village"},
            actor=actor,
            audience=[actor],
            now=now,
        )
    elif tool == "antidote":
        state["antidote"], state["night"]["saved"] = False, True
    elif tool == "poison":
        state["poison"], state["night"]["poison"] = False, payload["target"]
    elif tool == "reveal":
        player(state, actor).update(revealed=True, can_vote=False)
        event(state, "reveal", {"seat": actor, "role": Role.IDIOT}, now=now)
    elif tool == "abstain" and phase == "idiot":
        _kill(state, {actor: "exile"}, now, daytime=True)
    elif tool == "shoot":
        player(state, actor)["revealed"] = True
        event(state, "reveal", {"seat": actor, "role": Role.HUNTER}, now=now)
        _kill(state, {payload["target"]: "shot"}, now, daytime=state["task"].get("daytime", False))
    elif phase == "badge":
        _elect(state, payload["target"] if tool == "transfer_badge" else None, now)
    # _kill 可改变 phase 为 ended；不能再推进已结束的对局。
    if not state["winner"]:
        state["completed"][str(actor)] = payload.get("target")
        if len(state["completed"]) == len(state["actors"]):
            _settle(state, now)
            _advance(state, now)
    return event_id


def reduce_action(state, actor, command, *, now):
    if not isinstance(command, dict) or set(command) != {
        "request_id",
        "phase_id",
        "expected_version",
        "tool",
        "payload",
    }:
        raise Rejected("invalid_command")
    seat_number(actor)
    request_id = command["request_id"]
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        raise Rejected("invalid_request_id")
    try:
        canonical = json.dumps(command, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError):
        raise Rejected("invalid_command") from None
    key = f"{actor}:{request_id}"
    prior = state["receipts"].get(key)
    if prior:
        if json.dumps(prior["command"], sort_keys=True, allow_nan=False) != canonical:
            raise Rejected("request_id_conflict")
        return copy.deepcopy(state), copy.deepcopy(prior["result"])
    if command["phase_id"] != state["phase_id"]:
        raise Rejected("stale_phase")
    if type(command["expected_version"]) is not int:
        raise Rejected("invalid_version")
    if command["expected_version"] != state["version"]:
        raise Rejected("stale_version")
    tool, payload = command["tool"], command["payload"]
    if not isinstance(tool, str) or tool not in tools(state, actor):
        raise Rejected("tool_not_allowed")
    required = {"target"} if tool in TARGET_TOOLS else ({"text"} if tool in TEXT_TOOLS else set())
    if not isinstance(payload, dict) or set(payload) != required:
        raise Rejected("invalid_payload")
    if tool in TARGET_TOOLS:
        seat_number(payload["target"])
        if payload["target"] not in targets(state, actor, tool):
            raise Rejected("invalid_target")
    if tool in TEXT_TOOLS:
        _text(payload)
    updated = copy.deepcopy(state)
    event_id = _apply(updated, actor, tool, payload, now)
    updated["version"] += 1
    receipt = {
        "request_id": request_id,
        "accepted": True,
        "event_id": event_id,
        "version": updated["version"],
    }
    updated["receipts"][key] = {"command": copy.deepcopy(command), "result": receipt}
    return updated, copy.deepcopy(receipt)


def player_view(state, actor):
    seat_number(actor)
    p = player(state, actor)
    visible = [
        e
        for e in state["events"]
        if e["audience"] is None
        or (
            actor in e["audience"]
            and (
                p["died_at"] is None
                or e["id"] <= p["died_at"]
                or (e["actor"] == actor and e["kind"] == "action")
            )
        )
    ]
    available = tools(state, actor)
    own = {"alive": p["alive"], "can_vote": p["can_vote"]}
    if p["role"] == Role.WITCH:
        own.update(antidote=state["antidote"], poison=state["poison"])
        if state["phase"] == "night_witch" and actor in pending(state):
            own["attack"] = state["night"]["attack"]
    return copy.deepcopy(
        {
            "game_id": state["id"],
            "mode": state["mode"],
            "rules": state["rules"],
            "seat": actor,
            "role": p["role"],
            "round": state["round"],
            "phase": state["phase"],
            "phase_id": state["phase_id"],
            "version": state["version"],
            "tools": available,
            "targets": {t: targets(state, actor, t) for t in available if t in TARGET_TOOLS},
            "own": own,
            "sheriff": state["sheriff"],
            "winner": state["winner"],
            "wolf_team": wolves(state) if p["role"] == Role.WOLF else [],
            "players": [
                {
                    "seat": q["seat"],
                    "alive": q["alive"],
                    "revealed": q["revealed"],
                    **({"role": q["role"]} if q["revealed"] or state["winner"] else {}),
                }
                for q in state["players"]
            ],
            "events": [{k: v for k, v in e.items() if k != "audience"} for e in visible],
        }
    )
