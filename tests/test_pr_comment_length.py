"""PR 评论长度约束：单条不超过 300 个汉字，超限可拆分。"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/校验PR评论长度.py"
spec = importlib.util.spec_from_file_location("comment_length", SCRIPT)
length = importlib.util.module_from_spec(spec)
spec.loader.exec_module(length)


def test_counts_only_body_hanzi():
    assert length.count_hanzi("你好，世界！") == 4
    assert length.count_hanzi("见 [说明](https://example.com) 与 `code`") == 4
    assert length.count_hanzi("hello world") == 0


def test_code_spans_and_fences_do_not_consume_quota():
    inline = "说明 `" + "汉" * 301 + "` 结束"
    assert length.count_hanzi(inline) == 4
    assert length.check_comment(inline)["ok"]
    fenced = "说明\n\n```\n" + "汉" * 301 + "\n```\n"
    assert length.count_hanzi(fenced) == 2
    assert length.check_comment(fenced)["ok"]
    mixed = "汉" * 299 + "\n\n```\n" + "注释" * 100 + "\n```\n"
    assert length.count_hanzi(mixed) == 299
    assert length.check_comment(mixed)["ok"]


def test_chinese_link_address_does_not_consume_quota():
    url = "https://example.com/" + "汉" * 301
    text = f"说明 [详情]({url})"
    assert length.count_hanzi(text) == 4
    assert length.check_comment(text)["ok"]
    bare = "说明 " + url + " 结束"
    assert length.count_hanzi(bare) == 4


def test_inline_code_url_does_not_swallow_following_text():
    text = "`https://example.com`" + "汉" * 301
    assert length.count_hanzi(text) == 301
    assert not length.check_comment(text)["ok"]


def test_longer_fence_contains_shorter_example():
    text = "````\n```\n````\n" + "汉" * 301 + "\n```\ncode\n```\n"
    assert length.count_hanzi(text) == 301
    assert not length.check_comment(text)["ok"]


def test_inline_link_syntax_inside_code_does_not_eat_following_text():
    text = "`[x](`" + "汉" * 301 + ")"
    assert length.count_hanzi(text) == 301
    assert not length.check_comment(text)["ok"]


def test_link_does_not_cross_inline_code_boundary():
    text = "https://example.com`code`" + "汉" * 301
    assert length.count_hanzi(text) == 301
    assert not length.check_comment(text)["ok"]


def test_link_label_may_contain_inline_code():
    text = "汉" * 297 + " [`模块`](文档/开发/说明.md)"
    assert length.count_hanzi(text) == 297
    assert length.check_comment(text)["ok"]
    over = "汉" * 301 + " [`模块`](文档/开发/说明.md)"
    assert length.count_hanzi(over) == 301
    assert not length.check_comment(over)["ok"]
    chunks = length.split_comment(over)
    assert "".join(chunks) == over
    assert all(length.count_hanzi(chunk) <= 300 for chunk in chunks)
    assert sum(chunk.count("](") for chunk in chunks) == 1
    assert any("(文档/开发/说明.md)" in chunk for chunk in chunks)


def test_escaped_backticks_are_body_text():
    text = "\\`" + "汉" * 301 + "\\`"
    assert length.count_hanzi(text) == 301
    assert not length.check_comment(text)["ok"]


def test_backslash_inside_inline_code_does_not_escape_closing_tick():
    text = "`code\\`" + "汉" * 301 + "`"
    assert length.count_hanzi(text) == 301
    assert not length.check_comment(text)["ok"]


def test_fence_info_string_with_backtick_is_not_a_fence():
    text = "```example```\n" + "汉" * 301 + "\n```\ncode\n```\n"
    assert length.count_hanzi(text) == 301
    assert not length.check_comment(text)["ok"]


def test_unsplittable_link_is_blocked_instead_of_broken():
    text = "[" + "汉" * 301 + "](https://example.com)"
    result = length.check_comment(text)
    assert not result["ok"] and result["needs_split"]
    assert result["unsplittable"] is True
    assert result["code"] == "protected_range_exceeds_limit"
    with pytest.raises(ValueError, match="protected_range_exceeds_limit"):
        length.split_comment(text)
    assert length.main(["--text", text, "--split"]) == 2


def test_exact_boundaries_299_300_301():
    for count in (299, 300):
        result = length.check_comment("汉" * count)
        assert result["ok"] and not result["needs_split"]
        assert result["hanzi"] == count
    over = length.check_comment("汉" * 301)
    assert not over["ok"] and over["needs_split"]
    assert len(over["comments"]) == 2
    assert "".join(over["comments"]) == "汉" * 301
    assert all(count <= 300 for count in over["comment_hanzi"])


def test_punctuation_links_and_code_do_not_consume_quota():
    text = "汉" * 295 + "，\n\n[链接](https://example.com)\n\n```\ncode here\n```"
    assert length.count_hanzi(text) == 297
    assert length.check_comment(text)["ok"]


def test_split_preserves_content_and_limits_each_comment():
    text = "\n\n".join(["汉" * 120, "汉" * 130, "汉" * 140])
    chunks = length.split_comment(text)
    assert "".join(chunks) == text
    assert all(length.count_hanzi(chunk) <= 300 for chunk in chunks)
    assert sum(length.count_hanzi(chunk) for chunk in chunks) == 390


def test_split_keeps_code_and_link_ranges_whole():
    url = "https://example.com/" + "汉" * 120
    text = "汉" * 250 + "\n\n```\n" + "注释" * 30 + "\n```\n[详情](" + url + ")" + "汉" * 50
    chunks = length.split_comment(text)
    assert "".join(chunks) == text
    assert all(length.count_hanzi(chunk) <= 300 for chunk in chunks)
    assert all(chunk.count("```") % 2 == 0 for chunk in chunks)
    assert all(chunk.count("(") == chunk.count(")") for chunk in chunks)


def test_cli_reports_and_splits(capsys):
    assert length.main(["--text", "汉" * 300]) == 0
    capsys.readouterr()
    assert length.main(["--text", "汉" * 301]) == 1
    capsys.readouterr()
    assert length.main(["--text", "汉" * 301, "--split"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["split"] is True
    assert len(payload["comments"]) == 2
    assert all(count <= 300 for count in payload["comment_hanzi"])
    assert length.main(["--text", "汉" * 5, "--limit", "4"]) == 1
