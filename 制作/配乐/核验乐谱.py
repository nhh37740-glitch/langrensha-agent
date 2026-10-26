"""独立检查交付乐谱与 MIDI，避免清单完整但乐曲/节奏文件错误。"""

import hashlib
import json
import struct
from pathlib import Path

from 生成配乐 import WORLD, compose

ROOT = Path(__file__).resolve().parents[2]


def read_varint(data, cursor):
    result = 0
    for _ in range(4):
        value = data[cursor]
        cursor += 1
        result = (result << 7) | (value & 127)
        if not value & 128:
            return result, cursor
    raise ValueError("无效的 MIDI 变长整数")


def check_midi(path, score):
    data = path.read_bytes()
    assert data[:4] == b"MThd" and struct.unpack(">IHHH", data[4:14]) == (6, 0, 1, 480)
    assert data[14:18] == b"MTrk"
    size = struct.unpack(">I", data[18:22])[0]
    assert size == len(data) - 22
    cursor, tick = 22, 0
    active = {}
    completed = []
    programs = {}
    tempo = None
    ended = False
    while cursor < len(data):
        delta, cursor = read_varint(data, cursor)
        tick += delta
        status = data[cursor]
        cursor += 1
        if status == 0xFF:
            kind = data[cursor]
            cursor += 1
            length, cursor = read_varint(data, cursor)
            payload = data[cursor : cursor + length]
            cursor += length
            if kind == 0x51:
                tempo = int.from_bytes(payload)
            if kind == 0x2F:
                ended = True
                assert cursor == len(data)
        elif status & 0xF0 == 0xC0:
            programs[status & 15] = data[cursor]
            cursor += 1
        elif status & 0xF0 in {0x80, 0x90}:
            pitch, velocity = data[cursor : cursor + 2]
            cursor += 2
            key = status & 15, pitch
            if status & 0xF0 == 0x90 and velocity:
                assert key not in active, f"同通道同音高重叠，MIDI会提前停止：{key}"
                active[key] = tick, velocity
            else:
                assert key in active, f"没有对应开始的 NoteOff：{key}"
                start, strength = active.pop(key)
                assert tick > start
                completed.append((start, tick, key, strength))
        else:
            raise ValueError(f"未知 MIDI 事件：{status:x}")
    assert ended and not active and tempo == round(60_000_000 / score["bpm"])
    expected = sorted(
        (
            round(n["beat"] * 480),
            round((n["beat"] + n["duration"]) * 480),
            (n["channel"], n["pitch"]),
            n["velocity"],
        )
        for n in score["notes"]
    )
    assert sorted(completed) == expected, f"MIDI与实际合成乐谱不符：{path.name}"
    assert programs == {n["channel"]: n["program"] for n in score["notes"]}


def main():
    folder = Path(__file__).parent
    tracks = json.loads((folder / "曲目清单.json").read_text())["tracks"]
    assert len(tracks) == len({t["id"] for t in tracks}) == 53
    assert sum(t["loop"] for t in tracks) == 29
    fingerprints = set()
    results = []
    for track in tracks:
        path = folder / "乐谱" / f"{track['id']}.json"
        score = json.loads(path.read_text())
        assert score == compose(track), f"乐谱不是当前脚本的输出：{track['id']}"
        assert score == compose(track), "创作过程不可重复"
        assert all(
            0 <= n["pitch"] <= 127
            and 0 < n["velocity"] <= 127
            and n["beat"] >= 0
            and n["duration"] > 0
            for n in score["notes"]
        )
        if track["loop"]:
            allowed = {
                (WORLD[track["world"]]["root"] + p) % 12 for p in WORLD[track["world"]]["scale"]
            }
            assert all(n["pitch"] % 12 in allowed for n in score["notes"]), (
                f"循环曲出现未声明的调外音：{track['id']}"
            )
        fingerprint = hashlib.sha256(
            json.dumps(score["notes"], sort_keys=True).encode()
        ).hexdigest()
        assert fingerprint not in fingerprints, "曲目复用了完全相同的编排"
        fingerprints.add(fingerprint)
        check_midi(path.with_suffix(".mid"), score)
        results.append(
            {
                "id": track["id"],
                "notes": len(score["notes"]),
                "score_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "midi_sha256": hashlib.sha256(path.with_suffix(".mid").read_bytes()).hexdigest(),
            }
        )
    out = ROOT / "素材/音乐/乐谱核验.json"
    out.write_text(
        json.dumps({"issue": 76, "all_pass": True, "tracks": results}, ensure_ascii=False, indent=2)
        + "\n"
    )
    print(f"{len(results)} 首乐谱与MIDI核验通过")


if __name__ == "__main__":
    main()
