"""PR 评论长度约束：单条不超过 300 个汉字，超限可拆分。"""

import importlib.util
import json
from pathlib import Path

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


def test_split_keeps_code_ranges_whole():
    text = "汉" * 250 + "\n\n```\n" + "注释" * 30 + "\n```\n" + "汉" * 50
    chunks = length.split_comment(text)
    assert "".join(chunks) == text
    assert all(length.count_hanzi(chunk) <= 300 for chunk in chunks)
    assert all(chunk.count("```") % 2 == 0 for chunk in chunks)


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
