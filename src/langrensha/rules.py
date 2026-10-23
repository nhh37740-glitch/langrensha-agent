"""确定性内核；不依赖模型、网络或存储。完整剧本规则由后续任务接入。"""

import copy
import json
from collections import Counter
from enum import StrEnum
from random import SystemRandom
from typing import Any
from uuid import uuid4


class Role(StrEnum):
    WOLF = "wolf"
    VILLAGER = "villager"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    IDIOT = "idiot"


DECK = [Role.WOLF] * 4 + [Role.VILLAGER] * 4 + [Role.SEER, Role.WITCH, Role.HUNTER, Role.IDIOT]
NIGHT = "night_votes"
DAY = "day_speech"


class Rejected(ValueError):
    """行动未生效；code 可供调用方处理，不包含其他玩家的私密事实。"""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def seat_number(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 12:
        raise Rejected("invalid_seat")
    return value


def event(state, kind, data, *, actor=None, audience=None, now):
    """audience=None 表示公开；其他记录只允许名单中的玩家及受信主持读取。"""
    item = {
        "id": len(state["events"]) + 1,
        "game_id": state["id"],
        "round": state["round"],
        "phase_id": state["phase_id"],
        "actor": actor,
        "kind": kind,
        "data": data,
        "audience": audience,
        "time": now,
    }
    state["events"].append(item)
    return item["id"]


def create_game(*, human_seat=1, human_role=None, now, rng=None):
    """rng 仅供受信测试重放；正常发牌使用 SystemRandom。"""
    seat_number(human_seat)
    deck = list(DECK)
    if human_role is not None:
        try:
            human_role = Role(human_role)
        except ValueError:
            raise Rejected("invalid_role") from None
        deck.remove(human_role)
    (rng or SystemRandom()).shuffle(deck)
    if human_role is not None:
        deck.insert(human_seat - 1, human_role)
    state = {
        "schema_version": 1,
        "id": str(uuid4()),
        "mode": "kernel_rehearsal",
        "round": 1,
        "phase": NIGHT,
        "phase_id": str(uuid4()),
        "version": 0,
        "players": [
            {"seat": i, "role": str(role), "human": i == human_seat}
            for i, role in enumerate(deck, 1)
        ],
        "completed": {},
        "events": [],
        "receipts": {},
    }
    event(state, "game_created", {"mode": state["mode"]}, now=now)
    for player in state["players"]:
        event(
            state,
            "identity",
            {"role": player["role"]},
            actor=player["seat"],
            audience=[player["seat"]],
            now=now,
        )
    return state


def wolves(state):
    return [p["seat"] for p in state["players"] if p["role"] == Role.WOLF]


def tools(state, actor):
    seat_number(actor)
    if str(actor) in state["completed"]:
        return []
    if state["phase"] == NIGHT and actor in wolves(state):
        return ["wolf_chat", "wolf_vote", "abstain"]
    if state["phase"] == DAY:
        current = next(i for i in range(1, 13) if str(i) not in state["completed"])
        if actor == current:
            return ["speak", "abstain"]
    return []


def tally(votes):
    counts = Counter(v for v in votes if v is not None)
    if not counts:
        return {"target": None, "reason": "no_votes", "counts": {}}
    maximum = max(counts.values())
    leaders = [target for target, count in counts.items() if count == maximum]
    return {
        "target": leaders[0] if len(leaders) == 1 else None,
        "reason": "unique" if len(leaders) == 1 else "tie",
        "counts": {str(k): v for k, v in sorted(counts.items())},
    }


def _text(payload):
    value = payload.get("text")
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise Rejected("invalid_text")
    return value.strip()


def reduce_action(state, actor, command, *, now):
    """在副本中处理行动；失败不修改输入。操作者由服务绑定，不取自 command。"""
    if not isinstance(command, dict) or set(command) != {
        "request_id",
        "phase_id",
        "expected_version",
        "tool",
        "payload",
    }:
        raise Rejected("invalid_command")
    request_id = command["request_id"]
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        raise Rejected("invalid_request_id")
    seat_number(actor)
    try:
        canonical = json.dumps(command, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
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
    fields = {"wolf_chat": {"text"}, "wolf_vote": {"target"}, "speak": {"text"}, "abstain": set()}
    if not isinstance(payload, dict) or set(payload) != fields[tool]:
        raise Rejected("invalid_payload")
    if tool == "wolf_vote":
        seat_number(payload["target"])
    if tool in ("wolf_chat", "speak"):
        _text(payload)
    updated = copy.deepcopy(state)
    audience = wolves(state) if state["phase"] == NIGHT else None
    data = {"tool": tool, **payload}
    event_id = event(updated, "action", data, actor=actor, audience=audience, now=now)
    if tool != "wolf_chat":
        updated["completed"][str(actor)] = payload.get("target")
    if state["phase"] == NIGHT and len(updated["completed"]) == 4:
        event(
            updated,
            "wolf_tally",
            tally(updated["completed"].values()),
            audience=wolves(state),
            now=now,
        )
        _next_phase(updated, DAY, now)
    elif state["phase"] == DAY and len(updated["completed"]) == 12:
        updated["round"] += 1
        _next_phase(updated, NIGHT, now)
    updated["version"] += 1
    receipt = {
        "request_id": request_id,
        "event_id": event_id,
        "version": updated["version"],
        "accepted": True,
    }
    updated["receipts"][key] = {"command": copy.deepcopy(command), "result": receipt}
    return updated, copy.deepcopy(receipt)


def _next_phase(state, phase, now):
    state["phase"] = phase
    state["phase_id"] = str(uuid4())
    state["completed"] = {}
    event(state, "phase_changed", {"phase": phase}, now=now)


def player_view(state, actor):
    seat_number(actor)
    player = state["players"][actor - 1]
    visible = [e for e in state["events"] if e["audience"] is None or actor in e["audience"]]
    return copy.deepcopy(
        {
            "game_id": state["id"],
            "mode": state["mode"],
            "seat": actor,
            "role": player["role"],
            "round": state["round"],
            "phase": state["phase"],
            "phase_id": state["phase_id"],
            "version": state["version"],
            "tools": tools(state, actor),
            "wolf_team": wolves(state) if player["role"] == Role.WOLF else [],
            "events": [{k: v for k, v in e.items() if k != "audience"} for e in visible],
        }
    )
