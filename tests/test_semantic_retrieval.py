import json
import os
import random
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from langrensha import semantic
from langrensha.full_game import pending
from langrensha.retrieval import _tokens, build_chunks, query, split_text
from langrensha.service import GameService

ROOT = Path(__file__).resolve().parents[1]


def view(role="villager", *, game="g1", seat=1, events=None):
    return {
        "game_id": game,
        "seat": seat,
        "role": role,
        "round": 3,
        "events": events or [],
    }


def event(number, actor, text, *, kind="action", round_number=1, **data):
    payload = {"tool": "speak", "text": text, **data}
    return {"id": number, "kind": kind, "round": round_number, "actor": actor, "data": payload}


def test_synonym_recall_without_shared_characters():
    events = [
        event(1, 2, "我觉得铁匠昨晚的证词有问题，他一直在回避关键时间。"),
        event(2, 3, "我当时在钟楼附近，听见有人匆匆下楼。"),
        event(3, 4, "我昨夜看见三号身上有暗影。", kind="vision", alignment="wolves", target=3),
    ]
    events += [
        event(number, 5, f"第{number}位旅人谈论广场上的灯火与天气。")
        for number in range(4, 12)
    ]
    current = view(events=events)
    question = "谁认为那个手艺人不太对劲"
    assert not (set(_tokens(question)) & set(_tokens(events[0]["data"]["text"])))
    result = query(current, "search_history", {"query": question})
    assert result["method"] == "semantic_retrieval"
    assert result["sources"][0]["source"] == "event:1"
    assert "语义模型不可用" not in result


def test_chunks_keep_source_world_game_speaker_time_and_permission():
    current = view(game="game-甲", seat=7)
    documents = [
        {
            "source": "event:9",
            "text": "第一句证词。第二句证词。",
            "category": "speech",
            "actor": 3,
            "round": 2,
            "time": "2026-10-25T00:00:00+00:00",
        }
    ]
    chunks = build_chunks(documents, view=current)
    assert [chunk.text for chunk in chunks] == ["第一句证词。", "第二句证词。"]
    first = chunks[0]
    assert first.source == "event:9"
    assert first.world == "雾钟镇"
    assert first.game == "game-甲"
    assert first.actor == 3
    assert first.round == 2
    assert first.time == "2026-10-25T00:00:00+00:00"
    assert first.visible_to == 7
    assert first.category == "speech"
    assert first.part == 0
    assert first.document is documents[0]

    text = "".join(f"第{number}句证词。" for number in range(120))
    pieces = split_text(text, limit=90)
    assert "".join(pieces) == text
    assert all(len(piece) <= 90 for piece in pieces)
    hard = split_text("甲" * 250, limit=100)
    assert "".join(hard) == "甲" * 250
    assert [len(piece) for piece in hard] == [100, 100, 50]
    spaced = "  第一句。 第二句。"
    assert "".join(split_text(spaced, limit=90)) == spaced


def test_role_guidance_and_cross_game_messages_do_not_leak(tmp_path):
    wolf = view("wolf")
    villager = view("villager")
    wolf_result = query(wolf, "ask_world", {"question": "夜裔同伴"})
    assert any("共同求胜" in source["text"] for source in wolf_result["sources"])
    villager_result = query(villager, "ask_world", {"question": "夜裔同伴"})
    assert all("共同求胜" not in source["text"] for source in villager_result["sources"])

    service = GameService(tmp_path / "跨局.db")
    first = service.create(full=True, human_role="villager", rng=random.Random(9))
    second = service.create(full=True, human_role="villager", rng=random.Random(9))
    wolf_seat = pending(service.host_snapshot(first))[0]
    wolf_player = service.bind_player(first, wolf_seat)
    wolf_player.submit(
        {
            "request_id": str(uuid4()),
            "phase_id": wolf_player.view()["phase_id"],
            "expected_version": wolf_player.view()["version"],
            "tool": "wolf_chat",
            "payload": {"text": "跨局密语 CROSSGAME"},
        }
    )
    assert "CROSSGAME" in wolf_player.query("search_history", {"query": "跨局密语"})["answer"]
    other = service.bind_player(second, 1).query("search_history", {"query": "跨局密语"})
    assert "CROSSGAME" not in json.dumps(other, ensure_ascii=False)


def test_real_model_cpu_budget_in_fresh_process():
    script = """
import json
import resource
import time

from langrensha import semantic

texts = [
    f"第{number}条可见证词：镇民要让所有夜裔离开，夜里夜裔各自选择袭击对象。"
    for number in range(60)
]
semantic.scores(["预热"], "预热")
start = time.perf_counter()
values = semantic.scores(texts, "谁认为那个手艺人不太对劲")
elapsed = (time.perf_counter() - start) * 1000
print(json.dumps({
    "ms": round(elapsed, 1),
    "peak_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
    "count": len(values),
}))
"""
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src")
        + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
    }
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=180,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    measured = json.loads(completed.stdout.strip().splitlines()[-1])
    assert measured["count"] == 60
    assert measured["ms"] < 20_000, measured
    assert measured["peak_mb"] < 1_500, measured
    print(f"语义模型 CPU 实测：{measured}")
    assert semantic.embed(["铜铃"]).shape == (1, 512)


def test_cache_eviction_does_not_drop_vectors_needed_by_current_request(monkeypatch):
    monkeypatch.setattr(semantic, "CACHE_LIMIT", 2)
    monkeypatch.setattr(semantic, "_load_runtime", lambda: object())

    def fake_embed(runtime, texts):
        import numpy as np

        vectors = np.array([[float(len(text)), 1.0] for text in texts], dtype=np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    monkeypatch.setattr(semantic, "_embed_batch", fake_embed)
    semantic.reset()
    try:
        vectors = semantic.embed(["a", "bb", "ccc"])
        assert vectors.shape == (3, 2)
    finally:
        semantic.reset()


def test_corrupt_model_is_rejected_instead_of_used(monkeypatch, tmp_path):
    (tmp_path / "model.onnx").write_bytes(b"not-a-real-model")
    (tmp_path / "tokenizer.json").write_bytes(b"not-a-real-tokenizer")
    monkeypatch.setenv("LANGRENSHA_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("LANGRENSHA_RAG_OFFLINE", "1")
    semantic.reset()
    try:
        with pytest.raises(semantic.EmbeddingUnavailable, match="缺失或损坏"):
            semantic.embed(["铜铃"])
    finally:
        semantic.reset()


def test_model_unavailable_is_reported_and_uses_lexical_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGRENSHA_MODEL_DIR", str(tmp_path / "空模型目录"))
    monkeypatch.setenv("LANGRENSHA_RAG_OFFLINE", "1")
    semantic.reset()
    try:
        result = query(view(), "ask_world", {"question": "铜铃"})
    finally:
        semantic.reset()
    assert result["method"] == "lexical_fallback"
    assert "语义模型不可用" in result["warning"]
    assert any(source["source"] == "world:bell" for source in result["sources"])
