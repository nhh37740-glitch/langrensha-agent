"""仅消费受限玩家视图；将事实映射为雾钟镇故事，不输出主持审计。"""

from .content import PERSONAS, ROLE_NAMES, story_language

LABELS = {
    "wolf_chat": "向同伴低语",
    "wolf_vote": "选定今夜去处",
    "speak": "说出证词",
    "abstain": "暂且不作选择",
    "inspect": "向星空询问",
    "antidote": "送出解药",
    "poison": "送出毒药",
    "shoot": "最后一枪",
    "reveal": "亮明誓印",
    "signup": "举手争取铜铃",
    "withdraw": "退出争铃",
    "sheriff_vote": "支持执铃人",
    "exile_vote": "决定谁离开",
    "transfer_badge": "把铜铃交给他",
    "explode": "撕下伪装离去",
}
PHASE_NAMES = {
    "sheriff_signup": "铜铃之选 · 举手",
    "sheriff_speech": "铜铃之选 · 陈述",
    "sheriff_withdraw": "铜铃之选 · 最后的抉择",
    "sheriff_vote": "铜铃之选 · 表决",
    "sheriff_pk_speech": "铜铃之选 · 再陈述",
    "sheriff_pk_vote": "铜铃之选 · 再表决",
    "day_speech": "广场上的证词",
    "exile_vote": "暮色中的抉择",
    "exile_pk_speech": "未解的争议",
    "exile_pk_vote": "最后的表决",
    "last_words": "离去之前",
    "hunter": "最后一声回响",
    "idiot": "誓印的抉择",
    "badge": "铜铃的去向",
    "ended": "雾散时分",
}


def _line(e):
    d, kind, actor = e["data"], e["kind"], e["actor"]
    prefix = f"{actor}号 · {PERSONAS[actor - 1][0]}" if actor else "钟楼记事"
    effect = None
    if kind == "action":
        tool = d["tool"]
        if tool in {"speak", "wolf_chat"}:
            text = d["text"]
        elif tool in {
            "wolf_vote",
            "sheriff_vote",
            "exile_vote",
            "transfer_badge",
            "poison",
            "shoot",
        }:
            text = f"{LABELS[tool]}：{d['target']}号。"
        elif tool == "inspect":
            text = f"将目光投向{d['target']}号的星空。"
        else:
            text = LABELS.get(tool, "暂且不作选择") + "。"
        effect = {
            "inspect": "vision",
            "poison": "potion",
            "antidote": "potion",
            "shoot": "shot",
            "reveal": "oath",
            "explode": "shadow",
        }.get(tool)
    elif kind == "vision":
        text = (
            f"{d['target']}号的星兆中，{'潜藏暗影' if d['alignment'] == 'wolves' else '未见暗影'}。"
        )
        effect = "vision"
    elif kind == "wolf_tally":
        text = (
            f"同伴们今夜选定了{d['target']}号。" if d["target"] else "同伴们今夜没有达成唯一选择。"
        )
    elif kind == "deaths":
        text = "、".join(f"{s}号" for s in d["seats"]) + "的座位已空。"
    elif kind == "dawn":
        text = "晨钟响起，雾中的广场渐渐明亮。"
    elif kind == "badge":
        text = f"{d['seat']}号接过铜铃。" if d["seat"] else "铜铃不再由任何人执掌。"
    elif kind == "ballot_result":
        counts = "，".join(f"{s}号 {n:g}票" for s, n in d["counts"].items())
        ballots = "；".join(
            f"{s}号支持{t}号" if t else f"{s}号未作选择" for s, t in d.get("ballots", {}).items()
        )
        text = "众人留下的选择：" + (counts or "无人作出选择") + "。" + ballots
    elif kind == "reveal":
        text = f"{d['seat']}号亮明了{ROLE_NAMES[d['role']]}的印记。"
    elif kind == "ending":
        text = {
            "village": "夜裔尽散，镇上的灯火终于安稳。",
            "wolves": "雾吞没了最后的守护，夜裔留在镇中。",
            "draw": "最后的灯与暗影一同消失，钟楼只余寂静。",
        }[d["winner"]]
    else:
        return None
    return {
        "id": e["id"],
        "round": e["round"],
        "speaker": prefix,
        "text": story_language(text),
        "private": kind in {"vision", "wolf_tally"}
        or (
            kind == "action"
            and d["tool"] in {"wolf_chat", "wolf_vote", "inspect", "poison", "antidote"}
        ),
        "effect": effect,
        "actor": actor,
    }


def present(view):
    own = view["own"]
    people = []
    for p in view["players"]:
        name, description, color = PERSONAS[p["seat"] - 1]
        role = p.get("role")
        if p["seat"] == view["seat"]:
            role = view["role"]
        elif p["seat"] in view["wolf_team"]:
            role = "wolf"
        people.append(
            {
                "seat": p["seat"],
                "name": name,
                "description": description,
                "color": color,
                "alive": p["alive"],
                "role": ROLE_NAMES.get(role),
                "sheriff": p["seat"] == view["sheriff"],
            }
        )
    night = view["phase"].startswith("night")
    return {
        "game_id": view["game_id"],
        "seat": view["seat"],
        "identity": ROLE_NAMES[view["role"]],
        "round": view["round"],
        "night": night,
        "chapter": "灯火熄灭之后" if night else PHASE_NAMES.get(view["phase"], "雾中的等待"),
        "phase_id": view["phase_id"],
        "version": view["version"],
        "alive": own["alive"],
        "winner": view["winner"],
        "players": people,
        "note": (f"今夜遇袭的是{own['attack']}号。" if own.get("attack") else ""),
        "resources": (
            {"解药": own["antidote"], "毒药": own["poison"]} if "antidote" in own else {}
        ),
        "choices": [
            {
                "tool": t,
                "label": LABELS[t],
                "targets": view["targets"].get(t),
                "text": t in {"speak", "wolf_chat"},
            }
            for t in view["tools"]
        ],
        "story": [line for e in view["events"] if (line := _line(e))],
    }
