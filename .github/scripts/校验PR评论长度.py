"""校验或拆分 Agent 在 PR 对话中的评论：单条不超过 300 个汉字。

用法：
  python .github/scripts/校验PR评论长度.py --text "要发送的评论"
  python .github/scripts/校验PR评论长度.py --text-file 临时/评论.md
  python .github/scripts/校验PR评论长度.py --text-file 临时/评论.md --split

默认模式只报告是否超限；--split 输出按段拆分的多条评论，保证每条汉字数不超限。
只统计汉字，标点、链接与代码片段中的 ASCII 字符不占汉字额度。
"""

import argparse
import json
import re
from pathlib import Path

HANZI_LIMIT = 300
HANZI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
FENCE_RE = re.compile(r"^\s*```")


def count_hanzi(text):
    """返回文本中的汉字数量；标点、英文、链接与代码不计入。"""
    return len(HANZI_RE.findall(text))


def fence_ranges(text):
    """返回代码围栏内部的字符区间列表，避免把代码块从中间拆开。"""
    ranges = []
    opening = None
    cursor = 0
    for line in text.splitlines(keepends=True):
        if FENCE_RE.match(line):
            if opening is None:
                opening = cursor
            else:
                ranges.append((opening, cursor + len(line)))
                opening = None
        cursor += len(line)
    return ranges


def _take_prefix(text, start, limit):
    """从 start 起取尽量长的片段，使其汉字数不超过 limit。"""
    used = 0
    index = start
    while index < len(text):
        if HANZI_RE.match(text[index]):
            if used == limit:
                break
            used += 1
        index += 1
    return index


def _fence_containing(ranges, position):
    for begin, end in ranges:
        if begin < position < end:
            return begin, end
    return None


def _preferred_break(text, start, end):
    """在 [start, end) 内找自然断点；没有则返回 end。"""
    window = text[start:end]
    for separator in ("\n\n", "\n", "。", "！", "？", "；", "!", "?", ";", " "):
        position = window.rfind(separator)
        if position > 0:
            return start + position + len(separator)
    return end


def split_comment(text, limit=HANZI_LIMIT):
    """把一条超长评论按原文顺序拆成多条，每条汉字数不超过 limit。"""
    if limit < 1:
        raise ValueError("limit_must_be_positive")
    if text is None:
        raise ValueError("text_required")
    chunks = []
    start = 0
    fences = fence_ranges(text)
    while start < len(text):
        if count_hanzi(text[start:]) <= limit:
            chunks.append(text[start:])
            break
        end = _take_prefix(text, start, limit)
        end = _preferred_break(text, start, end)
        fence = _fence_containing(fences, end)
        if fence is not None:
            begin, close = fence
            if count_hanzi(text[start:close]) <= limit:
                end = close
            elif begin > start:
                end = begin
        if end <= start:
            end = start + 1
        chunks.append(text[start:end])
        start = end
    return [chunk for chunk in chunks if chunk]


def check_comment(text, limit=HANZI_LIMIT):
    """返回检查结果；超限时给出需要的拆分条数与每条的汉字数。"""
    total = count_hanzi(text)
    result = {
        "limit": limit,
        "hanzi": total,
        "ok": total <= limit,
        "needs_split": total > limit,
    }
    if total > limit:
        chunks = split_comment(text, limit)
        result["comments"] = chunks
        result["comment_hanzi"] = [count_hanzi(chunk) for chunk in chunks]
    return result


def read_text(args):
    if args.text is not None:
        return args.text
    if args.text_file is not None:
        return Path(args.text_file).read_text(encoding="utf-8")
    raise ValueError("text_required")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="校验或拆分 Agent PR 评论（单条不超过 300 个汉字）"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="直接传入评论内容")
    source.add_argument("--text-file", help="从 UTF-8 文件读取评论内容")
    parser.add_argument("--limit", type=int, default=HANZI_LIMIT)
    parser.add_argument("--split", action="store_true", help="超限时输出拆分后的多条评论")
    args = parser.parse_args(argv)
    try:
        text = read_text(args)
        result = check_comment(text, args.limit)
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "code": str(error)}, ensure_ascii=False))
        return 2
    if args.split and result["needs_split"]:
        print(
            json.dumps(
                {
                    "ok": True,
                    "split": True,
                    "limit": result["limit"],
                    "hanzi": result["hanzi"],
                    "comment_hanzi": result["comment_hanzi"],
                    "comments": result["comments"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
