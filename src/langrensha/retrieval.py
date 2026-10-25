"""先取得受限视图，再做语义/词项检索和有出处的摘要；权限过滤先于索引。"""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from . import semantic
from .content import GUIDANCE, ROLE_NAMES, WORLD
from .rules import Rejected, seat_number

QUERY_TOOLS = {"ask_world", "search_history", "summarize_player", "self_info"}
WORLD_NAME = "雾钟镇"
CHUNK_CHARS = 300
# 该固定模型在中文短文本上的实测分界；低于此值视为无命中，避免无意义查询返回资料。
SEMANTIC_THRESHOLD = 0.40
RESULT_LIMIT = 12
_LOG = logging.getLogger(__name__)


def _tokens(text):
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower())
    return words + [a + b for a, b in zip(words, words[1:], strict=False)]


def _lexical_rank(documents, question):
    """BM25 风格词项召回，中文使用字与二元组；输入已经过权限过滤。"""
    if not question.strip():
        return documents[-RESULT_LIMIT:]
    query_tokens = set(_tokens(question))
    counters = [Counter(_tokens(d["text"])) for d in documents]
    size = len(documents)
    avg = sum(map(lambda c: sum(c.values()), counters)) / max(size, 1) or 1
    scored = []
    for index, (document, terms) in enumerate(zip(documents, counters, strict=True)):
        score = 0
        for token in query_tokens & terms.keys():
            df = sum(token in c for c in counters)
            tf = terms[token]
            score += (
                math.log(1 + (size - df + 0.5) / (df + 0.5))
                * tf
                * 2.2
                / (tf + 1.2 * (0.25 + 0.75 * sum(terms.values()) / avg))
            )
        if score:
            scored.append((score, index, document))
    return [
        d
        for _, _, d in sorted(scored, key=lambda x: (x[0], x[1]), reverse=True)[:RESULT_LIMIT]
    ]


def split_text(text, limit=CHUNK_CHARS):
    """按句读/换行边界切块；超长单句再按长度硬切，拼接后保持原顺序与原文。"""
    if not isinstance(text, str) or not text.strip():
        return []
    pieces = []
    start = 0
    for match in re.finditer(r"[。！？；!?;\n]", text):
        end = match.end()
        pieces.append(text[start:end])
        start = end
    if start < len(text):
        pieces.append(text[start:])
    chunks = []
    pending = ""
    for piece in pieces:
        if not piece:
            continue
        if not piece.strip():
            pending += piece
            continue
        piece = pending + piece
        pending = ""
        while len(piece) > limit:
            chunks.append(piece[:limit])
            piece = piece[limit:]
        if piece:
            chunks.append(piece)
    if pending and chunks:
        chunks[-1] += pending
    return chunks


@dataclass(frozen=True)
class Chunk:
    """带来源、世界/对局、说话人、时间和可见座位的最小检索单元。"""

    source: str
    text: str
    category: str
    world: str
    game: str
    actor: int | None
    round: int | None
    time: str | None
    visible_to: int
    part: int
    document: dict = field(repr=False, compare=False)


def build_chunks(documents, *, view):
    """只对已过滤的可见文档切块，并保留追溯所需的元数据。"""
    chunks = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        source, text = document.get("source"), document.get("text")
        if not isinstance(source, str) or not isinstance(text, str):
            continue
        for part, piece in enumerate(split_text(text)):
            chunks.append(
                Chunk(
                    source=source,
                    text=piece,
                    category=document.get("category", "world"),
                    world=WORLD_NAME,
                    game=view["game_id"],
                    actor=document.get("actor"),
                    round=document.get("round"),
                    time=document.get("time"),
                    visible_to=view["seat"],
                    part=part,
                    document=document,
                )
            )
    return chunks


def _semantic_rank(chunks, question):
    values = semantic.scores([chunk.text for chunk in chunks], question)
    order = sorted(range(len(chunks)), key=lambda index: (-values[index], index))
    matches = []
    seen = set()
    for index in order:
        if values[index] < SEMANTIC_THRESHOLD:
            break
        chunk = chunks[index]
        if chunk.source in seen:
            continue
        seen.add(chunk.source)
        matches.append(chunk.document)
        if len(matches) >= RESULT_LIMIT:
            break
    return matches


@dataclass(frozen=True)
class SemanticIndex:
    """由权限视图构建的临时语义索引；每次查询重建，避免旧权限/旧对局残留。"""

    chunks: list[Chunk]

    @classmethod
    def build(cls, documents, *, view):
        return cls(build_chunks(documents, view=view))

    def search(self, question):
        return _semantic_rank(self.chunks, question)


def rebuild_index():
    """清空向量缓存；下一次查询按当前可见视图重建索引。"""
    semantic.clear_cache()


def _rank(documents, question, *, view):
    if not question.strip():
        return documents[-RESULT_LIMIT:], "extractive_retrieval", None
    index = SemanticIndex.build(documents, view=view)
    try:
        matches = index.search(question)
    except semantic.EmbeddingUnavailable as exc:
        _LOG.warning("语义检索不可用，回退词项检索：%s", exc)
        matches = _lexical_rank(documents, question)
        return matches, "lexical_fallback", "语义模型不可用，已回退词项检索。"
    return matches, "semantic_retrieval", None


def history_documents(view):
    documents = []
    for e in view["events"]:
        data = e["data"]
        if e["kind"] == "action" and data.get("tool") in {"speak", "wolf_chat"}:
            text = data["text"]
        elif e["kind"] == "action" and data.get("tool") == "wolf_vote":
            text = f"{e['actor']}号夜间选择{data['target']}号。"
        elif e["kind"] == "wolf_tally":
            text = f"夜间同伴商议结果：{data['target'] or '无人'}。"
        elif e["kind"] == "vision":
            alignment = "潜藏暗影" if data["alignment"] == "wolves" else "未见暗影"
            text = f"你记下的星兆：{data['target']}号{alignment}。"
        else:
            continue
        category = "speech" if data.get("tool") in {"speak", "wolf_chat"} else e["kind"]
        documents.append(
            {
                "source": f"event:{e['id']}",
                "category": category,
                "actor": e["actor"],
                "round": e["round"],
                "time": e.get("time"),
                "text": text,
            }
        )
    return documents


def _bounded_text(value, *, optional=False):
    if optional and value is None:
        return ""
    if not isinstance(value, str) or (not optional and not value.strip()) or len(value) > 500:
        raise Rejected("invalid_query")
    return value.strip()


def query(view, name, payload):
    if not isinstance(payload, dict):
        raise Rejected("invalid_payload")
    fields = {
        "ask_world": ({"question"}, set()),
        "search_history": ({"query"}, {"seat", "from_round", "to_round"}),
        "summarize_player": ({"seat"}, {"from_round", "to_round"}),
        "self_info": (set(), set()),
        "speech_hint": (set(), {"focus"}),
    }
    if not isinstance(name, str) or name not in fields:
        raise Rejected("tool_not_allowed")
    required, optional = fields[name]
    if not required <= payload.keys() or not payload.keys() <= required | optional:
        raise Rejected("invalid_payload")
    if "seat" in payload:
        seat_number(payload["seat"])
    for key in ("from_round", "to_round"):
        if key in payload and (
            type(payload[key]) is not int or not 1 <= payload[key] <= view["round"]
        ):
            raise Rejected("invalid_round")
    lower, upper = payload.get("from_round", 1), payload.get("to_round", view["round"])
    if lower > upper:
        raise Rejected("invalid_round")
    if name == "self_info":
        title = ROLE_NAMES[view["role"]]
        facts = [d for d in history_documents(view) if d["category"] == "vision"]
        return {
            "answer": f"你坐在{view['seat']}号位置，身份是{title}。{GUIDANCE[view['role']]}"
            + "".join(d["text"] for d in facts),
            "sources": [{"source": "self:identity", "text": title}, *facts],
            "method": "fact",
        }
    if name == "ask_world":
        question = _bounded_text(payload["question"])
        docs = [
            {"source": w["id"], "text": w["text"], "title": w["title"], "category": "world"}
            for w in WORLD
        ]
        docs.append(
            {
                "source": "self:guide",
                "text": GUIDANCE[view["role"]],
                "title": "身份指导",
                "category": "guide",
            }
        )
        matches, method, warning = _rank(docs, question, view=view)
    else:
        docs = [
            d
            for d in history_documents(view)
            if lower <= d["round"] <= upper
            and ("seat" not in payload or d["actor"] == payload["seat"])
            and (name != "summarize_player" or d["category"] == "speech")
        ]
        question = (
            _bounded_text(payload["query"], optional=True)
            if name == "search_history"
            else _bounded_text(payload.get("focus"), optional=True)
        )
        if name == "summarize_player":
            matches, method, warning = docs[-RESULT_LIMIT:], "extractive_retrieval", None
        else:
            matches, method, warning = _rank(docs, question, view=view)
    if name == "speech_hint":
        evidence = "；".join(
            (
                f"{d['actor']}号曾说“{d['text'][:140]}”"
                if d["category"] == "speech"
                else d["text"][:140]
            )
            for d in matches[-3:]
        )
        answer = (
            f"我想先核对这些证词：{evidence}。请当事人解释前后依据；在得到回答前，我保留判断。"
            if evidence
            else "我还没有足够证词。我愿先听各位讲述所见，再根据能核对的细节作判断。"
        )
    elif name == "summarize_player":
        answer = (
            "可核对的陈述依次为："
            + "；".join(f"第{d['round']}日“{d['text'][:240]}”" for d in matches)
            + "。这些是原话摘录；是否矛盾或可信仍需结合依据，不能据此断言其秘密身份。"
            if matches
            else "尚无这位旅人可供你查阅的发言。"
        )
    else:
        answer = (
            "\n".join(d["text"] for d in matches)
            if matches
            else "现有可见资料没有记载，暂时无法回答。"
        )
    result = {"answer": answer, "sources": matches, "method": method}
    if warning:
        result["warning"] = warning
    return result
