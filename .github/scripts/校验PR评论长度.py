"""校验或拆分 Agent 在 PR 对话中的评论：单条不超过 300 个汉字。

用法：
  python .github/scripts/校验PR评论长度.py --text "要发送的评论"
  python .github/scripts/校验PR评论长度.py --text-file 临时/评论.md
  python .github/scripts/校验PR评论长度.py --text-file 临时/评论.md --split

默认模式只报告是否超限；--split 输出按段拆分的多条评论，保证每条汉字数不超限。
只统计正文汉字：标点、链接地址与代码片段（闭合围栏代码与行内代码）不占汉字额度。
无法安全识别为闭合代码/完整链接的内容按正文计数，宁可多算也不放行超限评论。
"""

import argparse
import json
import re
from pathlib import Path

HANZI_LIMIT = 300
HANZI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
FENCE_OPEN_RE = re.compile(r"^\s*(`{3,})[^`]*$")
FENCE_CLOSE_RE = re.compile(r"^\s*(`{3,})\s*$")
INLINE_CODE_RE = re.compile(r"(?<!\\)`(?:\\.|[^`\\\n])*`")
INLINE_LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\n]*)\)")
ANGLE_LINK_RE = re.compile(r"<(https?://[^>\s]+)>")
BARE_LINK_RE = re.compile(r"https?://[^\s)>\]`'\"]+")


def merge_ranges(ranges):
    """排序并合并重叠区间，保持字符位置口径。"""
    merged = []
    for begin, end in sorted(ranges):
        if merged and begin <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((begin, end))
    return merged


def fence_ranges(text):
    """返回闭合围栏代码的字符区间；只有同长度以上的闭合围栏才结束代码。"""
    ranges = []
    opening = None
    opening_ticks = 0
    cursor = 0
    for line in text.splitlines(keepends=True):
        opened = FENCE_OPEN_RE.match(line)
        closed = FENCE_CLOSE_RE.match(line)
        if opening is None and opened:
            opening = cursor
            opening_ticks = len(opened.group(1))
        elif opening is not None and closed and len(closed.group(1)) >= opening_ticks:
            ranges.append((opening, cursor + len(line)))
            opening = None
        cursor += len(line)
    return ranges


def code_ranges(text):
    """返回闭合代码区间：围栏代码与单反引号行内代码。"""
    ranges = fence_ranges(text)
    for match in INLINE_CODE_RE.finditer(text):
        if not any(begin <= match.start() < end for begin, end in ranges):
            ranges.append(match.span())
    return merge_ranges(ranges)


def mask_ranges(text, ranges):
    """把指定区间的字符替换为非汉字占位符，长度与换行保持不变。"""
    characters = list(text)
    for begin, end in ranges:
        for index in range(begin, end):
            if characters[index] != "\n":
                characters[index] = "x"
    return "".join(characters)


def _overlaps(span, ranges):
    start, end = span
    return any(start < range_end and range_start < end for range_start, range_end in ranges)


def link_matches(text, code=None):
    """只在代码之外识别完整链接，返回 (完整匹配区间, 地址区间) 列表。

    行内链接允许显示文字内部出现代码；地址或跨边界的代码片段视为不合法匹配。
    """
    code = code_ranges(text) if code is None else code
    masked = mask_ranges(text, code)
    matches = []
    for pattern, address_group in (
        (INLINE_LINK_RE, 1),
        (ANGLE_LINK_RE, 1),
        (BARE_LINK_RE, 0),
    ):
        for match in pattern.finditer(masked):
            span = match.span()
            if pattern is INLINE_LINK_RE:
                label_length = masked[span[0] : span[1]].find("](")
                if label_length < 0:
                    continue
                label_end = span[0] + label_length + 1
                overlaps = [
                    item for item in code if item[0] < span[1] and span[0] < item[1]
                ]
                if any(not (item[0] >= span[0] and item[1] <= label_end) for item in overlaps):
                    continue
            elif _overlaps(span, code):
                continue
            matches.append((span, match.span(address_group)))
    return matches


def excluded_ranges(text):
    """返回不占汉字额度的区间：代码与链接地址，并合并重叠部分。"""
    code = code_ranges(text)
    ranges = list(code)
    ranges.extend(address for _, address in link_matches(text, code))
    return merge_ranges(ranges)


def syntax_ranges(text):
    """返回拆分时不可切断的区间：代码与完整链接语法。"""
    code = code_ranges(text)
    ranges = list(code)
    ranges.extend(match for match, _ in link_matches(text, code))
    return merge_ranges(ranges)


def count_hanzi(text):
    """返回正文汉字数量；标点、链接地址与代码片段不计入。"""
    return len(HANZI_RE.findall(mask_ranges(text, excluded_ranges(text))))


def _take_prefix(masked, start, limit):
    """从 start 起在掩码文本上取尽量长的片段，使其汉字数不超过 limit。"""
    used = 0
    index = start
    while index < len(masked):
        if HANZI_RE.match(masked[index]):
            if used == limit:
                break
            used += 1
        index += 1
    return index


def _range_containing(ranges, position):
    for begin, end in ranges:
        if begin < position < end:
            return begin, end
    return None


def _preferred_break(masked, start, end):
    """在 [start, end) 内找自然断点；没有则返回 end。"""
    window = masked[start:end]
    for separator in ("\n\n", "\n", "。", "！", "？", "；", "!", "?", ";", " "):
        position = window.rfind(separator)
        if position > 0:
            return start + position + len(separator)
    return end


def split_comment(text, limit=HANZI_LIMIT):
    """把一条超长评论按原文顺序拆成多条，每条正文汉字数不超过 limit。"""
    if limit < 1:
        raise ValueError("limit_must_be_positive")
    if text is None:
        raise ValueError("text_required")
    masked = mask_ranges(text, excluded_ranges(text))
    protected = syntax_ranges(text)
    chunks = []
    start = 0
    while start < len(text):
        if count_hanzi(text[start:]) <= limit:
            chunks.append(text[start:])
            break
        end = _take_prefix(masked, start, limit)
        end = _preferred_break(masked, start, end)
        boundary = _range_containing(protected, end)
        if boundary is not None:
            begin, close = boundary
            if count_hanzi(text[start:close]) <= limit:
                end = close
            elif begin > start:
                end = begin
            else:
                # 代码块或完整链接自身超过额度：拦截，绝不拆坏原链接或围栏。
                raise ValueError("protected_range_exceeds_limit")
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
        try:
            chunks = split_comment(text, limit)
        except ValueError as error:
            result["unsplittable"] = True
            result["code"] = str(error)
            result["comments"] = []
            result["comment_hanzi"] = []
        else:
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
        if result.get("unsplittable"):
            print(
                json.dumps(
                    {"ok": False, "code": result["code"], "hanzi": result["hanzi"]},
                    ensure_ascii=False,
                )
            )
            return 2
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
