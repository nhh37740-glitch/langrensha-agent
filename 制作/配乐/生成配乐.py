"""Issue #76：确定性原创编曲 → MIDI / 乐谱事件 → 本地 FluidSynth → Ogg。

只读取本地音色库；不访问任何模型、音乐生成 API 或游戏隐藏状态。
运行依赖：Python、numpy、libfluidsynth、ffmpeg；用 --soundfont 指定 FluidR3_GM.sf2。
"""

from __future__ import annotations

import argparse
import ctypes as ct
import ctypes.util
import hashlib
import html
import json
import math
import shutil
import struct
import subprocess
import tempfile
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RATE = 48000
TICKS = 480
SHORT = {"dawn", "dusk", "verdict"}
WORLD = {
    "common": {
        "root": 60,
        "scale": [0, 2, 4, 5, 7, 9, 11],
        "motif": [0, 2, 7, 4],
        "harmony": [[0, 4, 7, 14], [-3, 0, 4, 7], [5, 9, 12, 16], [7, 12, 14, 19]],
        "programs": [0, 42, 89, 11, 12],
        "mood": "钢琴、柔和大提琴、薄电子长音与木质敲击",
    },
    "mist": {
        "root": 62,
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "motif": [0, 3, 2, 7],
        "harmony": [[0, 3, 7, 14], [-4, 0, 3, 7], [-7, -4, 0, 5], [-2, 2, 7, 12]],
        "programs": [0, 42, 71, 45, 14],
        "mood": "柔钢琴、单簧管、大提琴、拨弦与远铜钟",
    },
    "hyperion": {
        "root": 64,
        "scale": [0, 1, 3, 5, 7, 8, 10],
        "motif": [0, 1, 7, 5],
        "harmony": [[0, 3, 7, 10], [1, 5, 8, 12], [-7, -4, 0, 7], [0, 5, 7, 15]],
        "programs": [4, 42, 48, 46, 11],
        "mood": "处理电钢琴、低弦、竖琴和金属泛音",
    },
    "threebody": {
        "root": 60,
        "scale": [0, 2, 4, 6, 7, 9, 11],
        "motif": [0, 2, 6, 7],
        "harmony": [[0, 4, 7, 14], [2, 6, 9, 16], [4, 7, 11, 14], [-5, 2, 6, 11]],
        "programs": [0, 42, 89, 10, 8],
        "mood": "干净钢琴、圆润电子脉冲、薄弦与信号泛音",
    },
    "tidal_archive": {
        "root": 57,
        "scale": [0, 2, 3, 5, 7, 9, 10],
        "motif": [0, 3, 5, 7],
        "harmony": [[0, 3, 7, 14], [5, 9, 12, 15], [-2, 2, 5, 9], [0, 5, 7, 12]],
        "programs": [12, 71, 24, 45, 11],
        "mood": "木质马林巴、单簧管、尼龙拨弦与柔铜片琴",
    },
}


@dataclass(frozen=True)
class Note:
    beat: float
    duration: float
    pitch: int
    velocity: int
    channel: int
    program: int
    pan: float


def compose(track: dict) -> dict:
    """十种场景各有配器、密度与乐句；世界共享动机但不共享同一音轨。"""
    world = WORLD[track["world"]]
    scene = track["scene"]
    root = world["root"]
    programs = world["programs"]
    bpm = track["bpm"]
    motif = list(world["motif"])
    notes: list[Note] = []
    is_short = scene in SHORT
    ending = scene.endswith("_end")
    bars = 2 if is_short else (6 if bpm < 55 else 8) if ending else 16
    length_beats = 5.6 * bpm / 60 if is_short else bars * 4

    def add(beat, duration, pitch, velocity, voice=0, pan=0, lane=None):
        # 非打击乐 MIDI 通道9预留；固定轻微错位与力度变化，重建不靠随机种子。
        accent = (len(notes) * 5 % 7) - 3
        notes.append(
            Note(
                round(float(beat), 5),
                round(float(duration), 5),
                int(pitch),
                max(16, min(95, int(velocity + accent))),
                voice if lane is None else lane,
                programs[voice],
                float(pan),
            )
        )

    if is_short:
        contour = motif if scene == "dawn" else motif[::-1]
        if scene == "verdict":
            contour = [motif[2], motif[1], motif[0], motif[0] - 5]
        for i, pitch in enumerate(contour):
            add(i * bpm / 60 * 0.48, bpm / 60 * 0.85, root + pitch, 47 - i * 2, 0, -0.15)
        base = root if scene == "dawn" else root - 12
        for interval in [0, 7, 14 if scene == "dawn" else 10]:
            add(bpm / 60 * 1.8, bpm / 60 * 1.2, base + interval, 29, 2, 0.2)
        return {
            **track,
            "bars": bars,
            "length_beats": length_beats,
            "tail_seconds": 0,
            "notes": [asdict(n) for n in notes],
        }

    quiet = scene in {"night", "reading", "farewell", "draw_end"}
    active = scene in {"debate", "vote"}
    # 两小节一个和声；后八小节转位与节奏应答，不是四音单轨机械循环。
    progression = [0, 1, 2, 3, 0, 2, 1, 3]
    if scene == "night":
        progression = [0, 0, 3, 2, 0, 3, 1, 3]
    elif scene == "farewell":
        progression = [2, 1, 0, 3, 1, 2, 3, 0]
    elif scene == "reading":
        progression = [0, 2, 0, 1, 0, 1, 2, 3]
    elif ending:
        progression = [0, 1, 2, 0] if scene == "light_end" else [2, 1, 3, 0]

    for pair in range(bars // 2):
        beat = pair * 8
        chord = list(world["harmony"][progression[pair]])
        if scene == "light_end" and pair == bars // 2 - 1:
            chord = [0, 4 if track["world"] != "hyperion" else 3, 7, 12]
        elif scene == "shadow_end" and pair == bars // 2 - 1:
            chord = [0, 3, 7, 10]
        elif scene == "draw_end" and pair == bars // 2 - 1:
            chord = [0, 7, 14]
        # 低音与长音有起伏/留白，避免连续厚重铺底盖过阅读。
        bass = root + chord[0] - 24
        while bass < 36:
            bass += 12
        add(beat + 0.04, 5.6 if quiet else 7.15, bass, 34 if quiet else 40, 1, -0.12)
        for j, interval in enumerate(chord[1:]):
            if quiet and j == 2 and pair % 2:
                continue
            add(
                beat + 0.08 + j * 0.035,
                6.1 if quiet else 7.2,
                root + interval - 12,
                24 if quiet else 29,
                2,
                (j - 1) * 0.23,
            )

        # 织体：白昼用错拍分解，表决收紧，夜晚/阅读显著稀疏。
        pattern = {
            "theme": [0, 2.5, 4, 6.5],
            "menu": [0, 3, 4.5, 6.5],
            "day": [0.5, 2, 3.5, 5, 6.5],
            "debate": [0, 1, 2.5, 4, 5, 6.5],
            "vote": list(np.arange(0, 8, 0.75)),
            "night": [2.5, 6],
            "farewell": [1, 5.5],
            "reading": [1.5, 4.5, 6.5],
            "light_end": [0, 1.5, 3, 4.5, 6],
            "shadow_end": [0, 3, 5.5],
            "draw_end": [1.5, 5],
        }[scene]
        for k, step in enumerate(pattern):
            interval = chord[(k + pair) % len(chord)]
            octave = -12 if scene in {"vote", "night", "shadow_end"} else 0
            add(
                beat + step + ((k % 3) - 1) * 0.012 + 0.025,
                0.36 if active else 0.85 if quiet else 0.65,
                root + interval + octave,
                30 if quiet else 37,
                3,
                -0.35 if k % 2 else 0.35,
            )

        # 四音主题的轮廓按公开环节改写；问答、倒影、增时各自独立。
        melodic = motif[:]
        if scene == "day":
            melodic = [motif[2], motif[0], motif[3], motif[1]]
        elif scene == "debate":
            melodic = [motif[0], motif[2], motif[1], motif[3], motif[2], motif[0]]
        elif scene == "vote":
            melodic = [motif[0], motif[0], motif[2], motif[1], motif[3], motif[2]]
        elif scene in {"farewell", "shadow_end"}:
            melodic = motif[::-1]
        elif scene == "reading":
            melodic = [motif[0], motif[2]]
        elif scene == "night":
            melodic = [motif[pair % 4]] if pair % 2 == 0 else []
        elif scene == "draw_end":
            melodic = motif[:2] if pair % 2 else motif[2:]
        if pair % 2 and melodic:
            melodic = melodic[1:] + melodic[:1]
        if pair >= 4 and scene not in {"night", "farewell"}:
            melodic = [p + (12 if i == 2 and not active else 0) for i, p in enumerate(melodic)]
        timings = {
            1: [1.5],
            2: [1, 5],
            4: [0.5, 2.25, 4.25, 6],
            6: [0.5, 1.5, 3, 4.5, 5.5, 6.5],
        }.get(len(melodic), [])
        for k, (offset, step) in enumerate(zip(melodic, timings, strict=True)):
            sustain = 2.4 if quiet else 0.8 if active else 1.4
            # 雾镇主题让单簧管回答钢琴，潮汐让拨弦回答木琴。
            voice = 2 if track["world"] == "mist" and pair % 2 else 0
            if track["world"] == "tidal_archive" and pair % 2:
                voice = 2
            pitch = root + offset + (12 if scene == "reading" else 0)
            add(
                beat + step,
                sustain,
                pitch,
                (42 if quiet else 53) - (k % 3),
                voice,
                -0.18 if voice == 0 else 0.16,
                lane=5 if voice == 2 else None,
            )
        if pair % 2 == 0 and scene not in {"reading", "farewell", "draw_end"}:
            add(beat + 6.8, 1.1, root + 19, 25 if quiet else 29, 4, 0.42)

    if ending:
        # 独立结局有真实尾奏；尾音发生在末两拍，随后保留衰减空间。
        for interval in [0, 7, 12 if scene == "light_end" else 14]:
            add(length_beats - 2, 2.5, root + interval - 12, 32, 0, 0, lane=6)
    return {
        **track,
        "bars": bars,
        "length_beats": length_beats,
        "tail_seconds": 4 if ending else 0,
        "notes": [asdict(n) for n in notes],
    }


def varint(value: int) -> bytes:
    out = [value & 0x7F]
    while value := value >> 7:
        out.insert(0, (value & 0x7F) | 0x80)
    return bytes(out)


def midi(score: dict, path: Path) -> None:
    events = [(0, -3, b"\xff\x51\x03" + round(60_000_000 / score["bpm"]).to_bytes(3))]
    for voice, program in sorted({n["channel"]: n["program"] for n in score["notes"]}.items()):
        events.append((0, -2, bytes([0xC0 + voice, program])))
    for note in score["notes"]:
        start = round(note["beat"] * TICKS)
        stop = round((note["beat"] + note["duration"]) * TICKS)
        channel = note["channel"]
        events.extend(
            [
                (start, 1, bytes([0x90 + channel, note["pitch"], note["velocity"]])),
                (stop, 0, bytes([0x80 + channel, note["pitch"], 0])),
            ]
        )
    end = round((score["length_beats"] + score["tail_seconds"] * score["bpm"] / 60) * TICKS)
    events.append((max(end, max(e[0] for e in events)), 2, b"\xff\x2f\x00"))
    body = bytearray()
    previous = 0
    for tick, _, payload in sorted(events, key=lambda x: (x[0], x[1])):
        body += varint(tick - previous) + payload
        previous = tick
    path.write_bytes(
        b"MThd"
        + struct.pack(">IHHH", 6, 0, 1, TICKS)
        + b"MTrk"
        + struct.pack(">I", len(body))
        + body
    )


class Synth:
    """不安装音频驱动，离线读取音色采样；没有网络和声卡依赖。"""

    def __init__(self, soundfont: Path):
        library = ctypes.util.find_library("fluidsynth")
        if not library:
            raise RuntimeError("缺少 libfluidsynth；请先安装系统制作依赖")
        self.lib = ct.CDLL(library)
        declarations = {
            "new_fluid_settings": (ct.c_void_p, []),
            "fluid_settings_setnum": (ct.c_int, [ct.c_void_p, ct.c_char_p, ct.c_double]),
            "fluid_settings_setint": (ct.c_int, [ct.c_void_p, ct.c_char_p, ct.c_int]),
            "new_fluid_synth": (ct.c_void_p, [ct.c_void_p]),
            "fluid_synth_sfload": (ct.c_int, [ct.c_void_p, ct.c_char_p, ct.c_int]),
            "fluid_synth_program_change": (ct.c_int, [ct.c_void_p, ct.c_int, ct.c_int]),
            "fluid_synth_all_sounds_off": (ct.c_int, [ct.c_void_p, ct.c_int]),
            "fluid_synth_noteon": (ct.c_int, [ct.c_void_p, ct.c_int, ct.c_int, ct.c_int]),
            "fluid_synth_noteoff": (ct.c_int, [ct.c_void_p, ct.c_int, ct.c_int]),
            "fluid_synth_write_float": (
                ct.c_int,
                [
                    ct.c_void_p,
                    ct.c_int,
                    ct.c_void_p,
                    ct.c_int,
                    ct.c_int,
                    ct.c_void_p,
                    ct.c_int,
                    ct.c_int,
                ],
            ),
            "delete_fluid_synth": (None, [ct.c_void_p]),
            "delete_fluid_settings": (None, [ct.c_void_p]),
        }
        for name, (result, args) in declarations.items():
            fn = getattr(self.lib, name)
            fn.restype = result
            fn.argtypes = args
        self.settings = self.lib.new_fluid_settings()
        for key, value in [(b"synth.sample-rate", RATE), (b"synth.gain", 0.5)]:
            if self.lib.fluid_settings_setnum(self.settings, key, value) != 0:
                raise RuntimeError(f"音色引擎设置失败：{key!r}")
        for key, value in [
            (b"synth.reverb.active", 0),
            (b"synth.chorus.active", 0),
            (b"synth.cpu-cores", 1),
            (b"synth.threadsafe-api", 0),
        ]:
            self.lib.fluid_settings_setint(self.settings, key, value)
        self.synth = self.lib.new_fluid_synth(self.settings)
        if self.lib.fluid_synth_sfload(self.synth, str(soundfont).encode(), 1) < 0:
            raise RuntimeError("无法加载音色库")

    def read(self, frames: int) -> np.ndarray:
        left = np.empty(frames, np.float32)
        right = np.empty(frames, np.float32)
        result = self.lib.fluid_synth_write_float(
            self.synth, frames, left.ctypes.data, 0, 1, right.ctypes.data, 0, 1
        )
        if result != 0:
            raise RuntimeError("离线音色渲染失败")
        return np.stack([left, right], axis=1)

    def sample(self, note: dict, seconds_per_beat: float) -> np.ndarray:
        self.lib.fluid_synth_all_sounds_off(self.synth, 0)
        self.lib.fluid_synth_program_change(self.synth, 0, note["program"])
        self.lib.fluid_synth_noteon(self.synth, 0, note["pitch"], note["velocity"])
        hold = self.read(max(1, round(note["duration"] * seconds_per_beat * RATE)))
        self.lib.fluid_synth_noteoff(self.synth, 0, note["pitch"])
        release = self.read(2 * RATE)
        result = np.concatenate([hold, release])
        # 单音尾部的短淡出只清除采样截断；循环曲的尾音会真正卷回开头。
        fade = min(2400, len(result))
        result[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
        result[:96] *= np.linspace(0, 1, 96, dtype=np.float32)[:, None]
        return result

    def close(self):
        self.lib.delete_fluid_synth(self.synth)
        self.lib.delete_fluid_settings(self.settings)


def render(score: dict, synth: Synth) -> np.ndarray:
    beat_seconds = 60 / score["bpm"]
    seconds = score["length_beats"] * beat_seconds + score["tail_seconds"]
    size = round(seconds * RATE)
    output = np.zeros((size, 2), np.float32)
    cache: dict[tuple, np.ndarray] = {}
    for note in score["notes"]:
        key = note["program"], note["pitch"], note["velocity"], note["duration"]
        if key not in cache:
            cache[key] = synth.sample(note, beat_seconds)
        sample = cache[key]
        start = round(note["beat"] * beat_seconds * RATE)
        pan = note["pan"]
        stereo = sample * np.array([math.sqrt((1 - pan) / 2), math.sqrt((1 + pan) / 2)], np.float32)
        if score["loop"]:
            # 环形叠加释放尾音：首尾来自同一乐句的连续采样，不把尾奏硬切掉。
            position = 0
            while position < len(stereo):
                offset = (start + position) % size
                count = min(size - offset, len(stereo) - position)
                output[offset : offset + count] += stereo[position : position + count]
                position += count
        elif start < size:
            count = min(len(stereo), size - start)
            output[start : start + count] += stereo[:count]
    cache.clear()
    # 稀疏立体声反射；循环使用环形延迟，结局使用真实衰减延迟。
    dry = output.copy()
    for i, delay in enumerate(
        [0.071, 0.113, 0.173, 0.239, 0.317, 0.419, 0.557, 0.701, 0.887, 1.13]
    ):
        shift = round(delay * RATE)
        wet = dry[:, ::-1] if i % 2 else dry
        gain = 0.13 * 0.79**i
        if score["loop"]:
            output += np.roll(wet, shift, axis=0) * gain
        elif shift < size:
            output[shift:] += wet[:-shift] * gain
    if score["world"] == "threebody":
        # 监听站额外的正弦低频脉冲，非警报音，不含外部录音。
        t = np.arange(size, dtype=np.float64) / RATE
        pulse = 0.018 * np.sin(2 * np.pi * 65.4064 * t)
        pulse *= (0.5 + 0.5 * np.cos(2 * np.pi * t / (beat_seconds * 2))) ** 6
        if score["loop"]:
            # 所有低频以整数周期契合循环总长度。
            cycles = round(65.4064 * seconds)
            pulse = 0.018 * np.sin(2 * np.pi * cycles * np.arange(size) / size)
            pulse *= (0.5 + 0.5 * np.cos(2 * np.pi * t / (beat_seconds * 2))) ** 6
        else:
            # 非循环结局/过门必须结束电子脉冲，最后两秒留给乐器余韵。
            pulse *= np.clip((seconds - 2 - t) / 2, 0, 1)
        output += pulse.astype(np.float32)[:, None]
    if not score["loop"]:
        fade = min(2 * RATE, size // 3)
        output[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None] ** 1.6
        output[:480] *= np.linspace(0, 1, 480, dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(output)))
    if not np.isfinite(output).all() or peak <= 1e-6:
        raise RuntimeError("音轨为空或包含非法采样")
    output *= 0.82 / peak
    return output


def loudness(path: Path, target: float) -> dict:
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"loudnorm=I={target}:TP=-3:LRA=7:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    # ffmpeg 的进度摘要可能出现在 JSON 之后。
    return json.JSONDecoder().raw_decode(result.stderr[result.stderr.rfind("{") :])[0]


def encode(samples: np.ndarray, score: dict, path: Path) -> dict:
    target = -24 if score["loop"] or score["scene"] in SHORT else -22
    with tempfile.TemporaryDirectory(prefix="score76-") as temp:
        wav = Path(temp) / "mix.wav"
        with wave.open(str(wav), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(RATE)
            out.writeframes((samples * 32767).round().astype("<i2").tobytes())
        first = loudness(wav, target)
        filt = (
            f"loudnorm=I={target}:TP=-3:LRA=7:measured_I={first['input_i']}:"
            f"measured_TP={first['input_tp']}:measured_LRA={first['input_lra']}:"
            f"measured_thresh={first['input_thresh']}:offset={first['target_offset']}:"
            "linear=true:print_format=json"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(wav),
                "-af",
                filt,
                "-ar",
                str(RATE),
                "-c:a",
                "libvorbis",
                "-q:a",
                "5",
                "-metadata",
                f"title={score['title']}",
                "-metadata",
                f"album={score['world_title']}",
                "-metadata",
                "artist=Codex original code composition / FluidR3 GM instruments",
                str(path),
            ],
            check=True,
        )
    # 从最终压缩文件解码核验，避免只检查中间 WAV。
    raw = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ar",
            str(RATE),
            "-ac",
            "2",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    decoded = np.frombuffer(raw, dtype="<f4").reshape(-1, 2)
    if len(decoded) != len(samples):
        raise RuntimeError(f"编码长度改变：{len(samples)} -> {len(decoded)}")
    measured = loudness(path, target)
    peak = float(np.max(np.abs(decoded)))
    edge = float(np.max(np.abs(decoded[-1] - decoded[0])))
    diff = np.abs(np.diff(decoded, axis=0))
    max_step = float(diff.max())
    # 接缝以局部音频导数比较，同时保留绝对幅度，不靠强行归零制造“通过”。
    seam_ok = edge < 0.015 and edge <= max(0.001, max_step * 1.5)
    rms_start = float(np.sqrt(np.mean(decoded[:RATE] ** 2)))
    rms_end = float(np.sqrt(np.mean(decoded[-RATE:] ** 2)))
    seconds = len(decoded) / RATE
    checks = {
        "finite": bool(np.isfinite(decoded).all()),
        "audible": peak > 0.01,
        "headroom": peak < 0.78 and float(measured["input_tp"]) <= -2.5,
        "loudness": abs(float(measured["input_i"]) - target) <= 1.0,
        "loop_seam": seam_ok if score["loop"] else None,
        "ending_tail": rms_end < 0.004 if not score["loop"] else None,
        "transition_duration": 3 <= seconds <= 6 if score["scene"] in SHORT else None,
        "ending_duration": 20 <= seconds <= 40 if score["scene"].endswith("_end") else None,
    }
    return {
        "id": score["id"],
        "file": path.name,
        "seconds": round(seconds, 6),
        "frames": len(decoded),
        "rate": RATE,
        "channels": 2,
        "target_lufs": target,
        "integrated_lufs": float(measured["input_i"]),
        "true_peak_dbtp": float(measured["input_tp"]),
        "sample_peak": peak,
        "seam_step": edge,
        "largest_internal_step": max_step,
        "start_rms": rms_start,
        "end_rms": rms_end,
        "checks": checks,
        "all_pass": all(v for v in checks.values() if v is not None),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def audition(catalog: list[dict], path: Path):
    cards = []
    for track in catalog:
        ident = html.escape(track["id"])
        title = html.escape(track["world_title"] + " · " + track["title"])
        usage = html.escape(track["usage"])
        loop = "循环" if track["loop"] else "单次"
        cards.append(
            f'<article id="{ident}"><h2>{title}</h2><p>{usage} · {loop}</p>'
            f'<audio controls preload="none" src="{ident}.ogg"></audio>'
            f'<p><a href="{ident}.ogg" download>下载 Ogg</a></p></article>'
        )
    path.write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>四世界配乐试听</title><style>body{font:16px/1.7 system-ui;"
        "max-width:1100px;margin:auto;padding:24px;background:#10202c;color:#eee}"
        "main{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));"
        "gap:20px}article{background:#213543;padding:18px;border-radius:12px}"
        "h2{font-size:18px}audio{width:100%}a{color:#9bded6}</style>"
        "<h1>群星渡海 · 四世界代码配乐</h1><p>41首背景音乐与12条转场。"
        "原创代码编曲，本地音色库离线合成；尚未接入游戏自动播放。"
        "请先低音量试听。技术检查不代替音乐听感验收。</p><main>"
        + "".join(cards)
        + "</main><script>document.addEventListener('play',event=>{"
        "for(const audio of document.querySelectorAll('audio')){"
        "if(audio!==event.target)audio.pause();}},true);</script></html>",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soundfont", type=Path, required=True)
    parser.add_argument("--only", nargs="*", help="只生成指定编号；省略时生成全部53段")
    parser.add_argument("--out", type=Path, default=ROOT / "素材/音乐")
    args = parser.parse_args()
    if not args.soundfont.is_file() or not shutil.which("ffmpeg"):
        parser.error("需存在本地音色库和 ffmpeg")
    tracks = json.loads((Path(__file__).with_name("曲目清单.json")).read_text())["tracks"]
    if len(tracks) != 53 or len({t["id"] for t in tracks}) != 53:
        raise ValueError("清单必须为53个不同编号")
    selected = [t for t in tracks if not args.only or t["id"] in args.only]
    if args.only and set(args.only) - {t["id"] for t in selected}:
        parser.error("--only 包含未知曲目")
    args.out.mkdir(parents=True, exist_ok=True)
    scores = Path(__file__).with_name("乐谱")
    scores.mkdir(exist_ok=True)
    report_path = args.out / "技术核验.json"
    previous = json.loads(report_path.read_text()) if report_path.exists() else {"tracks": []}
    # 不把旧音色库的技术回执混到本次重建中。
    sf_hash = hashlib.sha256(args.soundfont.read_bytes()).hexdigest()
    if previous.get("soundfont_sha256", sf_hash) != sf_hash:
        previous = {"tracks": []}
    reports = {r["id"]: r for r in previous["tracks"]}
    synth = Synth(args.soundfont)
    try:
        for track in selected:
            score = compose(track)
            (scores / f"{track['id']}.json").write_text(
                json.dumps(score, ensure_ascii=False, indent=2) + "\n"
            )
            midi(score, scores / f"{track['id']}.mid")
            samples = render(score, synth)
            report = encode(samples, score, args.out / f"{track['id']}.ogg")
            reports[track["id"]] = report
            record = {
                "issue": 76,
                "generator": "original arrangement + local FluidSynth",
                "soundfont": "FluidR3 GM / Frank Wen / MIT",
                "soundfont_sha256": sf_hash,
                "tracks": [reports[t["id"]] for t in tracks if t["id"] in reports],
            }
            record["complete"] = len(reports) == 53
            record["all_pass"] = all(r["all_pass"] for r in reports.values())
            report_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        k: report[k]
                        for k in [
                            "id",
                            "seconds",
                            "integrated_lufs",
                            "true_peak_dbtp",
                            "checks",
                            "all_pass",
                        ]
                    }
                ),
                flush=True,
            )
    finally:
        synth.close()
    audition([t for t in tracks if t["id"] in reports], args.out / "试听.html")
    if not all(r["all_pass"] for r in reports.values()):
        raise SystemExit("存在未通过的音频技术检查，详见技术核验.json")


if __name__ == "__main__":
    main()
