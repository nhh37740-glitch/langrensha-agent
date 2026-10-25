"""仅消费受限玩家视图；将事实映射为当前世界书故事，不输出主持审计。"""

from .content import PERSONAS, ROLE_NAMES
from .content import story_language as _story_language
from .worldbooks import get_worldbook, worldbook_ids

DEFAULT_WORLD = "mist"

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

# 每个世界只公开表现层数据：目录接口不会导出 entries / guidance / personas / basis。
THEMES = {
    "mist": {
        "id": "mist",
        "name": "雾钟镇",
        "tagline": "雾夜钟声里，十二位旅人彼此试探。",
        "summary": (
            "浓雾困住钟楼广场，白昼交换证词，夜晚灯火熄灭。夜裔藏在旅人之中，"
            "铜铃只交给最值得信任的人。"
        ),
        "glyph": "♜",
        "motif": "bell",
        "palette": {
            "sky": "#0b1a21",
            "mid": "#2f4a45",
            "accent": "#d8bd85",
            "paper": "#e9dfc6",
            "ink": "#081014",
        },
        "role_labels": dict(ROLE_NAMES),
        "scene": {
            "eyebrow": "钟声之后 / CHAPTER OF THE MIST",
            "title": ["有人守着灯，", "有人藏在雾里。"],
            "subtitle": "听清每一句证词，再决定相信谁。",
            "caption": "钟楼广场",
            "chapter": "十二位旅人，一个雾夜",
            "footer": "雾钟镇 · 第一卷",
            "intro": "雾封住了出镇的路。十一位旅人已经等在广场，今夜，你会带着怎样的秘密入座？",
        },
        "chapters": {
            **PHASE_NAMES,
            "night": "灯火熄灭之后",
            "night_wolves": "夜裔密谈",
            "night_witch": "药师用药",
            "night_seer": "观星询问",
            "default": "雾中的等待",
        },
        "labels": dict(LABELS),
        "endings": {
            "village": "夜裔尽散，镇上的灯火终于安稳。",
            "wolves": "雾吞没了最后的守护，夜裔留在镇中。",
            "draw": "最后的灯与暗影一同消失，钟楼只余寂静。",
        },
        "jargon": {},
        "narrator": "钟楼记事",
        "bell": "铜铃",
        "vision": "星兆",
        "dawn": "晨钟响起，雾中的广场渐渐明亮。",
        "empty_seat": "的座位已空。",
    },
    "hyperion": {
        "id": "hyperion",
        "name": "海伯利安",
        "tagline": "光阴冢外，最后一批朝圣者各怀心愿。",
        "summary": (
            "边境行星海伯利安没有远距传输门，光阴冢在反熵场中缓缓移动。"
            "十二名朝圣者在冢外扎营；白天核对来历与时间，夜里有人被献祭。"
        ),
        "glyph": "✶",
        "motif": "tombs",
        "palette": {
            "sky": "#1a0f0a",
            "mid": "#6b3a24",
            "accent": "#d9a05b",
            "paper": "#f0dfbd",
            "ink": "#120b07",
        },
        "role_labels": {
            "wolf": "荆棘使徒",
            "villager": "朝圣者",
            "seer": "时隙观测者",
            "witch": "随队医官",
            "hunter": "霸军老兵",
            "idiot": "立誓者",
        },
        "scene": {
            "eyebrow": "冢门将启 / CHAPTER OF THE TOMBS",
            "title": ["有人向伯劳许愿，", "有人把名字藏进风里。"],
            "subtitle": "在最后一支朝圣队里，分辨誓言与谎言。",
            "caption": "光阴冢外营地",
            "chapter": "十二名朝圣者，一个漫长的夜",
            "footer": "海伯利安 · 第一卷",
            "intro": (
                "朝圣船停在光阴冢外，冢门尚未开启。十二名朝圣者围坐营火，"
                "今夜，你准备向伯劳许下什么愿望？"
            ),
        },
        "chapters": {
            "sheriff_signup": "执灯之选 · 举手",
            "sheriff_speech": "执灯之选 · 陈述",
            "sheriff_withdraw": "执灯之选 · 最后的抉择",
            "sheriff_vote": "执灯之选 · 表决",
            "sheriff_pk_speech": "执灯之选 · 再陈述",
            "sheriff_pk_vote": "执灯之选 · 再表决",
            "day_speech": "营地中央的证词",
            "exile_vote": "冢影下的抉择",
            "exile_pk_speech": "未解的争议",
            "exile_pk_vote": "最后的表决",
            "last_words": "离去之前",
            "hunter": "最后一声回响",
            "idiot": "朝圣誓约的抉择",
            "badge": "灯盏的去向",
            "ended": "冢门开启时分",
            "night": "营火熄灭之后",
            "night_wolves": "使徒夜谈",
            "night_witch": "医官用药",
            "night_seer": "时隙观测",
            "default": "冢影中的等待",
        },
        "labels": {
            "wolf_chat": "向同伴低语",
            "wolf_vote": "选定今夜的献祭",
            "speak": "陈述朝圣见闻",
            "abstain": "暂且不作选择",
            "inspect": "读取时隙残影",
            "antidote": "送出修复剂",
            "poison": "送出神经毒素",
            "shoot": "最后一枪",
            "reveal": "亮出朝圣誓约",
            "signup": "举手争取灯盏",
            "withdraw": "退出执灯之选",
            "sheriff_vote": "支持执灯人",
            "exile_vote": "决定谁离开营地",
            "transfer_badge": "把灯盏交给他",
            "explode": "撕下伪装离去",
        },
        "endings": {
            "village": "荆棘退去，朝圣者在冢门前等到了天亮。",
            "wolves": "伯劳收下了朝圣队，冢间的金属声彻夜未停。",
            "draw": "最后一位朝圣者与荆棘一同消失在时隙里。",
        },
        "jargon": {"铜铃": "灯盏", "争铃": "争灯"},
        "narrator": "营地纪事",
        "bell": "灯盏",
        "vision": "时隙残影",
        "dawn": "冢间的反熵场暗了一瞬，营地迎来灰白的天光。",
        "empty_seat": "的铺位空了。",
    },
    "threebody": {
        "id": "threebody",
        "name": "三体",
        "tagline": "临海监听站里，警报与沉默同时抵达。",
        "summary": (
            "风暴把十二名观测员困在临海监听站，三体舰队逼近的警报反复响起。"
            "站内有人替三体文明工作；白天交换证词，夜里有人被清除。"
        ),
        "glyph": "◎",
        "motif": "signal",
        "palette": {
            "sky": "#040a12",
            "mid": "#17324d",
            "accent": "#e2574c",
            "paper": "#e8f0f6",
            "ink": "#03070d",
        },
        "role_labels": {
            "wolf": "潜伏者",
            "villager": "地球公民",
            "seer": "监听员",
            "witch": "面壁者",
            "hunter": "执剑人",
            "idiot": "冬眠者",
        },
        "scene": {
            "eyebrow": "信号之后 / CHAPTER OF THE SIGNAL",
            "title": ["有人监听宇宙，", "有人替沉默传话。"],
            "subtitle": "在舰队抵达之前，先听清频道里的每一句。",
            "caption": "临海监听站",
            "chapter": "十二名观测员，一次封锁",
            "footer": "三体 · 第一卷",
            "intro": (
                "风暴封住了临海监听站的航道，舰队警报越来越近。十二名观测员守在频道前，"
                "今夜，你选择监听谁的声音？"
            ),
        },
        "chapters": {
            "sheriff_signup": "执剑之选 · 举手",
            "sheriff_speech": "执剑之选 · 陈述",
            "sheriff_withdraw": "执剑之选 · 最后的抉择",
            "sheriff_vote": "执剑之选 · 表决",
            "sheriff_pk_speech": "执剑之选 · 再陈述",
            "sheriff_pk_vote": "执剑之选 · 再表决",
            "day_speech": "频道里的证词",
            "exile_vote": "静默中的抉择",
            "exile_pk_speech": "未解的争议",
            "exile_pk_vote": "最后的表决",
            "last_words": "信号中断之前",
            "hunter": "最后一次广播",
            "idiot": "冬眠舱的抉择",
            "badge": "执剑权限的去向",
            "ended": "静默降临",
            "night": "监听站熄灯之后",
            "night_wolves": "潜伏者密语",
            "night_witch": "面壁者预案",
            "night_seer": "监听员推演",
            "default": "噪声中的等待",
        },
        "labels": {
            "wolf_chat": "向同伴发送密语",
            "wolf_vote": "选定今夜清除目标",
            "speak": "提交证词",
            "abstain": "暂且保持静默",
            "inspect": "推演信号归属",
            "antidote": "注射解药",
            "poison": "注射毒药",
            "shoot": "最后一次广播",
            "reveal": "启动冬眠舱",
            "signup": "举手争取执剑权限",
            "withdraw": "退出执剑推选",
            "sheriff_vote": "支持执剑人",
            "exile_vote": "决定谁被逐离",
            "transfer_badge": "移交执剑权限",
            "explode": "撕下伪装离去",
        },
        "endings": {
            "village": "潜伏者被清除，监听站的警报第一次安静下来。",
            "wolves": "临海监听站失守，三体文明的信号接管了频道。",
            "draw": "最后的广播中断，海面上只剩没有回应的噪声。",
        },
        "jargon": {"铜铃": "执剑权限", "争铃": "执剑推选"},
        "narrator": "站内记录",
        "bell": "执剑权限",
        "vision": "信号",
        "dawn": "警报声低了下去，监听站迎来没有太阳的清晨。",
        "empty_seat": "的席位熄灯了。",
    },
    "tidal_archive": {
        "id": "tidal_archive",
        "name": "潮汐档案馆",
        "tagline": "潮窗之内，名字比人更先被潮水带走。",
        "summary": (
            "低潮时，十二位岛民穿过玄武岩缝进入册屿的潮汐档案馆，为校对《生民册》而来。"
            "一页名字被刮成空白；退潮只有几个时辰，下一次开门要等明天。"
        ),
        "glyph": "⚓",
        "motif": "tide",
        "palette": {
            "sky": "#06191a",
            "mid": "#2d6259",
            "accent": "#c98f5a",
            "paper": "#f0eadb",
            "ink": "#041312",
        },
        "role_labels": {
            "wolf": "噬名者",
            "villager": "守册人",
            "seer": "验潮员",
            "witch": "盐药师",
            "hunter": "灯守",
            "idiot": "誓痕人",
        },
        "scene": {
            "eyebrow": "潮窗之内 / CHAPTER OF THE TIDE",
            "title": ["有人守着名字，", "有人把名字还给海。"],
            "subtitle": "趁潮水尚未合拢，核对每一页证词。",
            "caption": "潮汐档案馆 · 放册台",
            "chapter": "十二位岛民，一次校册",
            "footer": "潮汐档案馆 · 第一卷",
            "intro": (
                "低潮门只开几个时辰，盐雾已经漫进册屿。十二位岛民围在放册台前，"
                "今夜，你的名字会被谁记住？"
            ),
        },
        "chapters": {
            "sheriff_signup": "执时之选 · 举手",
            "sheriff_speech": "执时之选 · 陈述",
            "sheriff_withdraw": "执时之选 · 最后的抉择",
            "sheriff_vote": "执时之选 · 表决",
            "sheriff_pk_speech": "执时之选 · 再陈述",
            "sheriff_pk_vote": "执时之选 · 再表决",
            "day_speech": "放册台上的证词",
            "exile_vote": "退潮前的抉择",
            "exile_pk_speech": "未解的争议",
            "exile_pk_vote": "最后的表决",
            "last_words": "离岛之前",
            "hunter": "最后一声铳响",
            "idiot": "誓痕的抉择",
            "badge": "潮钟钥匙的去向",
            "ended": "潮水合拢时分",
            "night": "潮钟停摆之后",
            "night_wolves": "噬名者刻名",
            "night_witch": "盐药师取盐",
            "night_seer": "验潮员照影",
            "default": "盐雾中的等待",
        },
        "labels": {
            "wolf_chat": "在密室交换名字",
            "wolf_vote": "刻下今夜的名字",
            "speak": "说出证词",
            "abstain": "暂不投石",
            "inspect": "在验潮井照影",
            "antidote": "送出返名盐",
            "poison": "送出蚀名盐",
            "shoot": "击发熄灯铳",
            "reveal": "亮出誓痕",
            "signup": "举手争取潮钟钥匙",
            "withdraw": "退出执时之选",
            "sheriff_vote": "支持执时人",
            "exile_vote": "决定谁离岛",
            "transfer_badge": "交出潮钟钥匙",
            "explode": "撕下伪装离岛",
        },
        "endings": {
            "village": "噬名者离岛，《生民册》上的名字重新有了归处。",
            "wolves": "潮水合拢，最后一页名字被盐霜抹平。",
            "draw": "潮钟停摆，册屿只余空白的册页与回声。",
        },
        "jargon": {"铜铃": "潮钟钥匙", "争铃": "争钥"},
        "narrator": "馆内潮记",
        "bell": "潮钟钥匙",
        "vision": "潮影",
        "dawn": "潮钟敲过一轮，盐雾里的册屿露出湿冷的石阶。",
        "empty_seat": "的名字从册上淡去。",
    },
}

_MERGE_KEYS = ("palette", "role_labels", "scene", "chapters", "labels", "endings", "jargon")


def _theme_for(worldbook_id):
    """缺字段或未知世界都回退雾钟镇，保证旧局与坏数据仍可展示。"""
    if not isinstance(worldbook_id, str) or worldbook_id not in THEMES:
        worldbook_id = DEFAULT_WORLD
    base = THEMES[DEFAULT_WORLD]
    theme = THEMES[worldbook_id]
    if theme is base:
        return {**base, **_copy_nested(base, _MERGE_KEYS)}
    merged = {**base, **theme}
    merged.update(_copy_nested(theme, _MERGE_KEYS, fallback=base))
    return merged


def _copy_nested(source, keys, fallback=None):
    result = {}
    for key in keys:
        base = (fallback or source).get(key, {})
        value = source.get(key, {})
        result[key] = {**base, **value}
    return result


def _personas(worldbook_id):
    """人物名、描述与颜色属于公开表现信息；坏数据回退雾钟镇。"""
    try:
        rows = get_worldbook(worldbook_id)["personas"]
    except KeyError:
        rows = PERSONAS
    cleaned = [
        (str(row[0]), str(row[1]), str(row[2]))
        for row in rows
        if isinstance(row, (list, tuple)) and len(row) == 3
    ]
    return cleaned if len(cleaned) == 12 else list(PERSONAS)


def story_language(text, replacements=None):
    """沿用默认黑话替换，再按世界覆盖表现词；不传替换表时行为不变。"""
    text = _story_language(text)
    for original, replacement in (replacements or {}).items():
        text = text.replace(original, replacement)
    return text


def worldbook_catalog():
    """只返回公开目录数据；秘密条目、指导、人物表和来源依据一律不导出。"""
    order = [DEFAULT_WORLD, "hyperion", "threebody", "tidal_archive"]
    order += sorted(set(worldbook_ids()) - set(order))
    books = []
    for worldbook_id in order:
        book = get_worldbook(worldbook_id)
        theme = _theme_for(worldbook_id)
        public = [entry for entry in book["entries"] if entry["visibility"] == "public"]
        excerpt = public[0]["text"].strip()[:140] if public else ""
        books.append(
            {
                "id": book["id"],
                "name": book["name"],
                "tagline": theme["tagline"],
                "summary": theme["summary"],
                "glyph": theme["glyph"],
                "motif": theme["motif"],
                "palette": dict(theme["palette"]),
                "role_labels": dict(theme["role_labels"]),
                "public_count": len(public),
                "excerpt": excerpt,
                "scene": {**theme["scene"], "title": list(theme["scene"]["title"])},
            }
        )
    return {"default": DEFAULT_WORLD, "worldbooks": books}


def _line(e, theme, personas):
    d, kind, actor = e["data"], e["kind"], e["actor"]
    prefix = f"{actor}号 · {personas[actor - 1][0]}" if actor else theme["narrator"]
    labels = theme["labels"]
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
            text = f"{labels[tool]}：{d['target']}号。"
        elif tool == "inspect":
            text = f"将目光投向{d['target']}号的方向。"
        else:
            text = labels.get(tool, "暂且不作选择") + "。"
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
            f"{d['target']}号的{theme['vision']}中，"
            f"{'潜藏暗影' if d['alignment'] == 'wolves' else '未见暗影'}。"
        )
        effect = "vision"
    elif kind == "wolf_tally":
        text = (
            f"同伴们今夜选定了{d['target']}号。" if d["target"] else "同伴们今夜没有达成唯一选择。"
        )
    elif kind == "deaths":
        text = "、".join(f"{s}号" for s in d["seats"]) + theme["empty_seat"]
    elif kind == "dawn":
        text = theme["dawn"]
    elif kind == "badge":
        text = (
            f"{d['seat']}号接过{theme['bell']}。"
            if d["seat"]
            else f"{theme['bell']}不再由任何人执掌。"
        )
    elif kind == "ballot_result":
        counts = "，".join(f"{s}号 {n:g}票" for s, n in d["counts"].items())
        ballots = "；".join(
            f"{s}号支持{t}号" if t else f"{s}号未作选择" for s, t in d.get("ballots", {}).items()
        )
        text = "众人留下的选择：" + (counts or "无人作出选择") + "。" + ballots
    elif kind == "reveal":
        text = f"{d['seat']}号亮明了{theme['role_labels'].get(d['role'], d['role'])}的印记。"
    elif kind == "ending":
        text = theme["endings"][d["winner"]]
    else:
        return None
    return {
        "id": e["id"],
        "round": e["round"],
        "speaker": prefix,
        "text": story_language(text, theme["jargon"]),
        "private": kind in {"vision", "wolf_tally"}
        or (
            kind == "action"
            and d["tool"] in {"wolf_chat", "wolf_vote", "inspect", "poison", "antidote"}
        ),
        "effect": effect,
        "actor": actor,
    }


def present(view):
    theme = _theme_for(view.get("worldbook", DEFAULT_WORLD))
    personas = _personas(theme["id"])
    own = view["own"]
    people = []
    for p in view["players"]:
        name, description, color = personas[p["seat"] - 1]
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
                "role": theme["role_labels"].get(role),
                "sheriff": p["seat"] == view["sheriff"],
            }
        )
    night = view["phase"].startswith("night")
    chapter = theme["chapters"].get(
        "night" if night else view["phase"], theme["chapters"]["default"]
    )
    if view["phase"] == "hunter" and "shoot" not in view["tools"]:
        chapter = theme["chapters"]["last_words"]
    elif view["phase"] == "idiot" and "reveal" not in view["tools"]:
        chapter = theme["chapters"]["exile_vote"]
    return {
        "game_id": view["game_id"],
        "seat": view["seat"],
        "worldbook": theme["id"],
        "worldbook_name": theme["name"],
        "identity": theme["role_labels"][view["role"]],
        "round": view["round"],
        "night": night,
        "chapter": chapter,
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
                "label": theme["labels"][t],
                "targets": view["targets"].get(t),
                "text": t in {"speak", "wolf_chat"},
            }
            for t in view["tools"]
        ],
        "story": [line for e in view["events"] if (line := _line(e, theme, personas))],
    }


def _debug_thinking(value):
    """调试面板只复原 DecisionRunner 已存的可见说明与工具调用。"""
    thinking = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        content = content if isinstance(content, str) else ""
        calls = []
        for call in item.get("tool_calls") if isinstance(item.get("tool_calls"), list) else []:
            if isinstance(call, dict) and isinstance(call.get("name"), str):
                args = call.get("args")
                calls.append({"name": call["name"], "args": args if isinstance(args, dict) else {}})
        thinking.append(
            {
                "step": len(thinking) + 1,
                "content": content,
                "has_content": bool(content.strip()),
                "tool_calls": calls,
            }
        )
    return thinking


def _debug_missing(thinking, reason):
    """模型没有返回可见说明时给出准确标记；不补写任何内容。"""
    if reason == "model_unavailable":
        return [{"reason": "model_unavailable", "label": "模型不可用，未返回显式说明"}]
    if not thinking:
        label = (
            "本回合未调用模型，无显式说明"
            if reason == "window_closed"
            else "未取得模型显式说明"
        )
        return [{"reason": reason or "no_thinking", "label": label}]
    if not any(item["has_content"] for item in thinking):
        return [{"reason": "no_content", "label": "模型未返回显式说明"}]
    return []


def debug_timeline(state, decisions):
    """把主持快照与真实决策审计整理为调试时间线；只读，不生成内容。"""
    theme = _theme_for(state.get("worldbook", DEFAULT_WORLD))
    personas = _personas(theme["id"])
    players = {
        item["seat"]: item
        for item in state.get("players", [])
        if isinstance(item, dict) and isinstance(item.get("seat"), int)
    }
    phase_by_id = {}
    event_rounds = {}
    for event in state.get("events", []):
        if not isinstance(event, dict):
            continue
        phase_id = event.get("phase_id")
        round_number = event.get("round")
        if isinstance(phase_id, str) and type(round_number) is int:
            event_rounds.setdefault(phase_id, round_number)
    groups = {}
    order = []
    missing = []
    for decision in decisions if isinstance(decisions, list) else []:
        if not isinstance(decision, dict):
            continue
        seat = decision.get("actor")
        if type(seat) is not int or not 1 <= seat <= len(personas):
            continue
        phase_id = decision.get("phase_id")
        round_number = decision.get("round")
        if type(round_number) is not int:
            # 旧审计只有 phase_id；从快照事件恢复历史轮次，恢复不了就保持未知。
            round_number = event_rounds.get(phase_id)
        if type(round_number) is not int:
            round_number = None
        phase = decision.get("phase")
        if not isinstance(phase, str) or not phase:
            phase = phase_by_id.get(phase_id)
        if not isinstance(phase, str) or not phase:
            # 历史审计没有阶段名时不能用当前阶段冒充历史事实。
            phase = "unknown"
        if isinstance(phase_id, str) and phase != "unknown":
            phase_by_id.setdefault(phase_id, phase)
        key = (round_number, phase_id if isinstance(phase_id, str) else phase)
        if key not in groups:
            groups[key] = {
                "round": round_number,
                "phase": phase,
                "phase_id": phase_id if isinstance(phase_id, str) else "",
                "time": decision.get("time", ""),
                "players": {},
            }
            order.append(key)
        player = groups[key]["players"].setdefault(
            seat,
            {
                "seat": seat,
                "name": personas[seat - 1][0],
                "role": theme["role_labels"].get(players.get(seat, {}).get("role")),
                "alive": bool(players.get(seat, {}).get("alive", False)),
                "decisions": [],
            },
        )
        thinking = _debug_thinking(decision.get("thinking"))
        markers = _debug_missing(thinking, decision.get("reason"))
        calls = decision.get("calls")
        player["decisions"].append(
            {
                "time": decision.get("time", ""),
                "reason": decision.get("reason", ""),
                "acted": bool(decision.get("acted")),
                "thinking": thinking,
                "calls": calls if isinstance(calls, list) else [],
                "missing": markers,
            }
        )
        missing.extend(
            {"seat": seat, "round": round_number, "phase": phase, **marker}
            for marker in markers
        )

    order.sort(
        key=lambda key: (
            groups[key]["round"] is None,
            groups[key]["round"] or 0,
            groups[key]["time"],
        )
    )
    rounds = []
    for key in order:
        group = groups[key]
        if not rounds or rounds[-1]["round"] != group["round"]:
            rounds.append({"round": group["round"], "phases": []})
        rounds[-1]["phases"].append(
            {
                "phase": group["phase"],
                "phase_id": group["phase_id"],
                "label": (
                    theme["chapters"].get(group["phase"])
                    or ("阶段未知（历史审计）" if group["phase"] == "unknown" else group["phase"])
                ),
                "players": [group["players"][seat] for seat in sorted(group["players"])],
            }
        )

    wolf_chat = []
    for event in state.get("events", []):
        if not isinstance(event, dict) or event.get("kind") != "action":
            continue
        data = event.get("data")
        if not isinstance(data, dict) or data.get("tool") != "wolf_chat":
            continue
        seat, text = event.get("actor"), data.get("text")
        if type(seat) is not int or not 1 <= seat <= len(personas):
            continue
        if not isinstance(text, str) or not text:
            continue
        phase_id = event.get("phase_id")
        phase = phase_by_id.get(phase_id) or "unknown"
        wolf_chat.append(
            {
                "round": event.get("round", 1),
                "phase": phase,
                "seat": seat,
                "name": personas[seat - 1][0],
                "text": text,
                "time": event.get("time", ""),
            }
        )
    wolf_chat.sort(key=lambda item: (str(item["time"]), item["round"] or 0))

    return {"rounds": rounds, "wolf_chat": wolf_chat, "missing": missing}
