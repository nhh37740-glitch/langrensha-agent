"""四世界公开人物映射一致性。

校验三层数据只含公开边界（席位、姓名、公开描述、色标）：

1. 服务器 ``langrensha.worldbooks`` 的 personas（唯一业务事实）；
2. 前端运行时 ``前端/src/worlds/personas.json``（选择卡/对局绑定用）；
3. Codex 交接的 ``人物映射.json``（图集 slot 约定，临时目录，不在仓库内）。

任何一层出现身份/阵营/暗牌字段都应失败。测试只读本地文件，不访问网络。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from langrensha.worldbooks import personas_for, worldbook_ids

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "前端/src/worlds/personas.json"
HANDOFF_CANDIDATES = (
    ROOT / "临时/世界书视觉Issue/完整美术包/人物映射.json",
    # 团队 worktree 的 临时/ 独立于主 checkout，交接目录留在主仓库根下。
    ROOT.parents[2] / "临时/世界书视觉Issue/完整美术包/人物映射.json",
)
WORLDS = ("mist", "hyperion", "threebody", "tidal_archive")
# 运行时允许的公开字段；后续可加 row/col，仍不得出现身份类字段。
PUBLIC_KEYS = {"seat", "slot", "row", "col", "name", "description", "color"}
HANDOFF_KEYS = {"seat", "slot", "row", "col", "name", "public_description", "color"}
# 只检查键名，不扫描“说明”里 declarative 的“不含身份”文案。
FORBIDDEN_KEY_PARTS = (
    "identity",
    "role",
    "camp",
    "faction",
    "alignment",
    "secret",
    "hidden",
    "undercover",
    "身份",
    "阵营",
    "暗牌",
    "角色",
)
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _load(path: Path) -> dict:
    assert path.is_file(), f"缺少公开人物数据：{path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_keys(value, prefix=""):
    """递归列出身份类字段；数组只检查元素字典。"""
    found = []
    if isinstance(value, dict):
        for key, nested in value.items():
            trail = f"{prefix}.{key}" if prefix else key
            lowered = str(key).lower()
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                found.append(trail)
            found.extend(_forbidden_keys(nested, trail))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_forbidden_keys(nested, f"{prefix}[{index}]"))
    return found


def _check_public_persona(persona: dict, world: str, index: int) -> None:
    assert isinstance(persona, dict), f"{world} 第 {index + 1} 项不是对象"
    assert set(persona) <= PUBLIC_KEYS, (
        f"{world} 第 {index + 1} 项含非公开字段：{sorted(set(persona) - PUBLIC_KEYS)}"
    )
    assert persona["seat"] == index + 1, f"{world} seat 必须是 1..12 顺序排列"
    assert persona["slot"] == index, f"{world} slot 必须是 0..11 顺序排列"
    assert persona["slot"] == persona["seat"] - 1
    assert isinstance(persona["name"], str) and persona["name"].strip()
    assert isinstance(persona["description"], str) and persona["description"].strip()
    assert COLOR.fullmatch(persona["color"]), f"{world} 色标格式错误：{persona['color']}"
    if "row" in persona or "col" in persona:
        assert persona.get("row") == persona["slot"] // 3
        assert persona.get("col") == persona["slot"] % 3
    assert not _forbidden_keys(persona), (
        f"{world} 第 {index + 1} 项含身份/阵营/暗牌字段：{_forbidden_keys(persona)}"
    )


def test_runtime_personas_match_worldbooks_and_stay_public():
    runtime = _load(RUNTIME)
    assert set(runtime["worlds"]) == set(WORLDS)
    assert not _forbidden_keys({"worlds": runtime["worlds"]})
    assert set(worldbook_ids()) == set(WORLDS)
    assert len(WORLDS) * 12 == 48

    seen_names = []
    for world in WORLDS:
        book = runtime["worlds"][world]
        assert book["name"].strip(), f"{world} 缺少公开世界名"
        personas = book["personas"]
        assert len(personas) == 12, f"{world} 必须正好 12 名公开人物"
        for index, persona in enumerate(personas):
            _check_public_persona(persona, world, index)
        names = [persona["name"] for persona in personas]
        assert len(names) == len(set(names)), f"{world} 公开人物姓名重复：{names}"
        seen_names.extend(names)

        official = personas_for(world)
        assert len(official) == 12, f"{world} 世界书人物应正好 12 名"
        for index, ((name, description, color), persona) in enumerate(
            zip(official, personas, strict=True)
        ):
            assert persona["name"] == name, f"{world} 第 {index + 1} 位姓名与世界书不一致"
            assert persona["description"] == description, (
                f"{world} 第 {index + 1} 位公开描述与世界书不一致"
            )
            assert persona["color"].lower() == color.lower(), (
                f"{world} 第 {index + 1} 位色标与世界书不一致"
            )
    # 48 个公开姓名在整个美术包里也应彼此可辨。
    assert len(seen_names) == len(set(seen_names)), "四世界公开人物姓名出现跨世界重复"


def test_handoff_mapping_matches_runtime_and_atlas_layout():
    handoff_path = next((path for path in HANDOFF_CANDIDATES if path.is_file()), None)
    if handoff_path is None:
        pytest.skip("交接目录未提供人物映射（临时文件不入库）")
    handoff = _load(handoff_path)
    assert handoff.get("issue") == 67
    atlas = handoff["atlas"]
    assert atlas["columns"] == 3
    assert atlas["rows"] == 4
    assert atlas["cell_order"] == "row-major"
    assert atlas.get("background") == "transparent"
    assert set(handoff["worlds"]) == set(WORLDS)

    runtime = _load(RUNTIME)
    for world in WORLDS:
        rows = handoff["worlds"][world]["public_personas"]
        assert len(rows) == 12, f"{world} 交接映射必须正好 12 人"
        runtime_rows = runtime["worlds"][world]["personas"]
        for index, row in enumerate(rows):
            assert set(row) <= HANDOFF_KEYS, (
                f"{world} 交接第 {index + 1} 项含非公开字段："
                f"{sorted(set(row) - HANDOFF_KEYS)}"
            )
            assert not _forbidden_keys(row), (
                f"{world} 交接第 {index + 1} 项含身份/阵营/暗牌字段"
            )
            assert row["seat"] == index + 1
            assert row["slot"] == index
            assert row["row"] == index // 3
            assert row["col"] == index % 3
            assert row["name"] == runtime_rows[index]["name"], (
                f"{world} 交接姓名与运行时不一致"
            )
            assert row["public_description"] == runtime_rows[index]["description"], (
                f"{world} 交接公开描述与运行时不一致"
            )
            assert row["color"].lower() == runtime_rows[index]["color"].lower(), (
                f"{world} 交接色标与运行时不一致"
            )
        names = [row["name"] for row in rows]
        assert len(names) == len(set(names)), f"{world} 交接人物姓名重复"
