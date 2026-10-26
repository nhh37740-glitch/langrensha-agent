"""把世界书条目渲染为可阅读 Markdown；条目数据是唯一维护源。"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import get_worldbook, role_name

READING_ORDER = ("mist", "hyperion", "threebody", "tidal_archive")
OUTPUT = Path(__file__).resolve().parents[3] / "文档" / "世界书" / "四世界正文.md"
ROLE_ORDER = ("wolf", "villager", "seer", "witch", "hunter", "idiot")


def _visibility_label(book, visibility):
    if visibility == "public":
        return "公开"
    labels = "、".join(f"{role_name(book, role)}（{role}）" for role in visibility)
    return f"仅 {labels} 可见"


def _entry_section(book, entry):
    return (
        f"#### {entry['title']}\n\n"
        f"条目：`{entry['id']}` · 可见性：{_visibility_label(book, entry['visibility'])}\n\n"
        f"{entry['text']}\n"
    )


def _world_section(book):
    public = [entry for entry in book["entries"] if entry["visibility"] == "public"]
    secrets = [entry for entry in book["entries"] if entry["visibility"] != "public"]
    lines = [f"## {book['name']}（`{book['id']}`）", "", f"**依据**：{book['basis']}", ""]
    lines += ["### 设定与阵营（公开条目）", ""]
    for entry in public:
        lines.append(_entry_section(book, entry))
    if secrets:
        lines += [
            "### 角色可见秘密（运行时按角色过滤）",
            "",
            "以下条目不会进入其他角色或公开检索的索引。",
            "",
        ]
        for entry in secrets:
            lines.append(_entry_section(book, entry))
    lines += ["### 本局人物", ""]
    for name, description, _color in book["personas"]:
        lines.append(f"- **{name}**：{description}")
    lines += ["", "### 身份与夜间能力", ""]
    for role in ROLE_ORDER:
        if role in book["roles"]:
            lines.append(
                f"- **{book['roles'][role]}（{role}）**：{book['guidance'].get(role, '')}"
            )
    lines += ["", "### 检索条目索引", "", "| 条目 id | 可见性 | 标题 |", "| --- | --- | --- |"]
    for entry in book["entries"]:
        visibility = _visibility_label(book, entry["visibility"])
        lines.append(f"| `{entry['id']}` | {visibility} | {entry['title']} |")
    lines.append("")
    return "\n".join(lines)


def render_markdown():
    lines = [
        "# 四世界世界书正文",
        "",
        "> 本文件由 `src/langrensha/worldbooks/*.py` 的 `WORLDBOOK` 数据生成，",
        "> 是运行时可检索条目的可阅读视图。请勿直接编辑；修改条目后运行",
        "> `python -m langrensha.worldbooks._render` 重新生成。",
        ">",
        "> 正文 → 可见条目 → 分块 → 检索出处的对应关系见",
        "> [正文与检索链路](正文与检索链路.md)。一致性由",
        "> `tests/test_worldbook_docs.py` 校验。",
        "",
    ]
    for worldbook_id in READING_ORDER:
        lines.append(_world_section(get_worldbook(worldbook_id)))
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成四世界世界书可阅读正文")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(), encoding="utf-8", newline="\n")
    print(args.output)


if __name__ == "__main__":
    main()
