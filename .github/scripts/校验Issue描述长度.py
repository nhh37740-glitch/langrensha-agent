"""校验 GitHub Issue 问题描述正文汉字数：不超过 300。"""

import argparse
import json
import re
from pathlib import Path

HANZI_LIMIT = 300
HANZI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")


def issue_body_text(text):
    """Issue Form 会把字段标题写入 Markdown；这里只统计正文内容。"""
    lines = text.splitlines()
    return "\n".join(line for line in lines if not HEADING_RE.match(line)).strip()


def count_hanzi(text):
    return len(HANZI_RE.findall(text))


def check_issue(text, limit=HANZI_LIMIT):
    body = issue_body_text(text or "")
    hanzi = count_hanzi(body)
    return {"ok": hanzi <= limit, "limit": limit, "hanzi": hanzi}


def read_text(args):
    if args.text is not None:
        return args.text
    if args.text_file is not None:
        return Path(args.text_file).read_text(encoding="utf-8")
    raise ValueError("text_required")


def main(argv=None):
    parser = argparse.ArgumentParser(description="校验 Issue 问题描述正文（不超过 300 个汉字）")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="直接传入 Issue Markdown 正文")
    source.add_argument("--text-file", help="从 UTF-8 文件读取 Issue Markdown 正文")
    parser.add_argument("--limit", type=int, default=HANZI_LIMIT)
    args = parser.parse_args(argv)
    try:
        result = check_issue(read_text(args), args.limit)
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "code": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
