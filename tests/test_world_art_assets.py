"""四世界美术资源清单校验。

清单约定：``前端/src/assets/worlds/素材清单.json``，只记录真实交接并接入的
资产；缺失槽位不写占位。测试逐世界核对：

* cover / scene_day / scene_night / personas / icons / effects 六个槽位齐全；
* 文件存在、字节数与 SHA-256 与清单一致；
* WebP 实际宽高与清单一致，透明槽位确实带 alpha；
* 人物图集 3×4、图标 4×4、动效 6×5，且实际像素可被行列整除；
* 来源、生成方式、提示词可追溯，不能是复用占位图。

只读本地文件，不访问网络。素材未到齐时测试明确失败并列出缺失槽位。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "前端/src/assets/worlds"
MANIFEST = ASSET_ROOT / "素材清单.json"
WORLDS = ("mist", "hyperion", "threebody", "tidal_archive")
SLOTS = {
    "cover": "cover.webp",
    "scene_day": "scene-day.webp",
    "scene_night": "scene-night.webp",
    "personas": "personas.webp",
    "icons": "icons.webp",
    "effects": "effects.webp",
}
LAYOUT = {
    "personas": (3, 4, 12),
    "icons": (4, 4, 16),
    "effects": (6, 5, 30),
}
ALPHA_REQUIRED = {"personas", "icons", "effects"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _load_manifest() -> dict:
    if not MANIFEST.is_file():
        pytest.fail(
            "缺少美术资源清单 前端/src/assets/worlds/素材清单.json；"
            "素材未接入时不能以占位图通过。"
        )
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _webp_info(path: Path) -> tuple[int, int, bool]:
    """读取 WebP 宽高与 alpha 标记，避免测试额外依赖 Pillow。"""
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", f"{path.name} 不是 WebP"
    chunk = data[12:16]
    if chunk == b"VP8X":
        flags = data[20]
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height, bool(flags & 0x10)
    if chunk == b"VP8 ":
        assert data[23:26] == b"\x9d\x01\x2a", f"{path.name} VP8 帧头异常"
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height, False
    if chunk == b"VP8L":
        assert data[20] == 0x2F, f"{path.name} VP8L 签名异常"
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height, bool((bits >> 28) & 1)
    raise AssertionError(f"{path.name} 的 WebP 块类型未知：{chunk!r}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_covers_four_worlds_and_declares_atlas_layout():
    manifest = _load_manifest()
    assert manifest.get("issue") == 67
    assert set(manifest["worlds"]) == set(WORLDS), (
        f"清单世界应正好四项，实际：{sorted(manifest['worlds'])}"
    )
    atlas = manifest["atlas"]
    for kind, (columns, rows, _frames) in LAYOUT.items():
        assert atlas[kind]["columns"] == columns, f"{kind} 图集应为 {columns} 列"
        assert atlas[kind]["rows"] == rows, f"{kind} 图集应为 {rows} 行"


def test_every_required_world_slot_is_delivered():
    manifest = _load_manifest()
    missing = []
    for world in WORLDS:
        records = manifest["worlds"].get(world) or {}
        for slot in SLOTS:
            if slot not in records:
                missing.append(f"{world}/{slot}")
    assert not missing, (
        "素材尚未到齐，不能用占位图通过；缺失槽位："
        + "、".join(missing)
    )


def test_asset_files_match_manifest_hashes_and_dimensions():
    manifest = _load_manifest()
    errors = []
    all_hashes = {}
    for world in WORLDS:
        for slot, filename in SLOTS.items():
            record = (manifest["worlds"].get(world) or {}).get(slot)
            if record is None:
                continue
            path = ASSET_ROOT / world / filename
            label = f"{world}/{slot}"
            if not path.is_file():
                errors.append(f"{label} 文件不存在：{path.relative_to(ROOT)}")
                continue
            if record.get("file") != filename:
                errors.append(f"{label} 清单文件名应为 {filename}，实际 {record.get('file')!r}")
            if record.get("bytes") != path.stat().st_size:
                errors.append(f"{label} 字节数不一致")
            actual_sha = _sha256(path)
            if record.get("sha256") != actual_sha:
                errors.append(f"{label} SHA-256 不一致")
            all_hashes[label] = actual_sha
            width, height, has_alpha = _webp_info(path)
            if (record.get("width"), record.get("height")) != (width, height):
                errors.append(
                    f"{label} 清单尺寸 {record.get('width')}×{record.get('height')} "
                    f"与实际 {width}×{height} 不一致"
                )
            if slot in ALPHA_REQUIRED:
                if not has_alpha:
                    errors.append(f"{label} 缺少透明通道")
                if record.get("alpha") is not True:
                    errors.append(f"{label} 清单未标记 alpha=true")
                mode = str(record.get("mode", ""))
                if "A" not in mode:
                    errors.append(f"{label} 清单通道应为 RGBA，实际 {mode!r}")
            else:
                if has_alpha:
                    errors.append(f"{label} 应为不透明 WebP，实际带透明通道")
                if record.get("alpha") is True:
                    errors.append(f"{label} 清单把不透明资产标成了 alpha=true")
    assert not errors, "素材清单与实际文件不一致：\n" + "\n".join(errors)
    assert len(all_hashes) == len(set(all_hashes.values())), (
        "不同槽位出现相同 SHA-256，疑似复用占位图"
    )


def test_atlas_frames_match_actual_layout():
    manifest = _load_manifest()
    errors = []
    for world in WORLDS:
        for kind, (columns, rows, frame_count) in LAYOUT.items():
            record = (manifest["worlds"].get(world) or {}).get(kind)
            if record is None:
                continue
            path = ASSET_ROOT / world / SLOTS[kind]
            if not path.is_file():
                errors.append(f"{world}/{kind} 文件缺失，无法核对图集")
                continue
            width, height, _alpha = _webp_info(path)
            if width % columns or height % rows:
                errors.append(
                    f"{world}/{kind} 实际 {width}×{height} 不能被 {columns}×{rows} 整除"
                )
            frames = record.get("frames") or {}
            if (frames.get("columns"), frames.get("rows")) != (columns, rows):
                errors.append(
                    f"{world}/{kind} 帧布局应为 {columns}×{rows}，"
                    f"实际 {frames.get('columns')}×{frames.get('rows')}"
                )
            if frames.get("layout") != "row-major":
                errors.append(f"{world}/{kind} 帧顺序应为 row-major")
            cell_width = frames.get("cell_width")
            cell_height = frames.get("cell_height")
            if not cell_width or not cell_height:
                errors.append(f"{world}/{kind} 缺少 cell_width/cell_height")
            elif (cell_width * columns, cell_height * rows) != (width, height):
                errors.append(
                    f"{world}/{kind} 单元格与总尺寸不符："
                    f"{cell_width}×{cell_height} × {columns}×{rows}"
                )
            slots = frames.get("slots") or []
            if slots != list(range(frame_count)):
                errors.append(
                    f"{world}/{kind} 帧语义槽应为 0..{frame_count - 1}，实际 {slots}"
                )
    assert not errors, "图集布局不符合约定：\n" + "\n".join(errors)


def test_records_are_traceable_and_not_reused_placeholders():
    manifest = _load_manifest()
    errors = []
    for world in WORLDS:
        for slot, filename in SLOTS.items():
            record = (manifest["worlds"].get(world) or {}).get(slot)
            if record is None:
                continue
            label = f"{world}/{slot}"
            source = str(record.get("source") or record.get("handoff") or "").strip()
            if not source:
                errors.append(f"{label} 缺少来源路径")
            if not str(record.get("generator") or "").strip():
                errors.append(f"{label} 缺少生成方式 generator")
            if not str(record.get("prompt_file") or "").strip():
                errors.append(f"{label} 缺少提示词位置 prompt_file")
            else:
                prompt_path = ROOT / str(record["prompt_file"])
                if not prompt_path.is_file():
                    errors.append(f"{label} 提示词文件不存在：{record['prompt_file']}")
            if not SHA256.fullmatch(str(record.get("sha256") or "")):
                errors.append(f"{label} sha256 不是 64 位十六进制")
            if not str(record.get("received_at") or "").strip():
                errors.append(f"{label} 缺少 received_at")
            notes = str(record.get("notes") or "").lower()
            if "placeholder" in notes or "占位" in notes:
                errors.append(f"{label} 备注表明仍是占位图")
            path = ASSET_ROOT / world / filename
            if path.is_file() and path.stat().st_size < 2048:
                errors.append(f"{label} 文件过小，疑似占位图")
    assert not errors, "素材可追溯性不足：\n" + "\n".join(errors)
