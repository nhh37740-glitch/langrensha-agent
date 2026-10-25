"""Issue 问题描述正文长度约束：不超过 300 个汉字。"""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/校验Issue描述长度.py"
spec = importlib.util.spec_from_file_location("issue_length", SCRIPT)
length = importlib.util.module_from_spec(spec)
spec.loader.exec_module(length)


def test_ignores_markdown_headings_from_issue_forms():
    text = "### 用户要完成什么\n" + "汉" * 300 + "\n\n### 验收方式\nok"
    assert length.check_issue(text)["ok"]
    assert length.check_issue(text)["hanzi"] == 300
    over = "### 用户要完成什么\n" + "汉" * 301
    assert not length.check_issue(over)["ok"]
    assert length.check_issue(over)["hanzi"] == 301


def test_exact_boundaries_299_300_301():
    for count in (299, 300):
        result = length.check_issue("汉" * count)
        assert result["ok"] and result["hanzi"] == count
    result = length.check_issue("汉" * 301)
    assert not result["ok"] and result["hanzi"] == 301


def test_cli_reports_result(capsys):
    assert length.main(["--text", "汉" * 300]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] and payload["hanzi"] == 300
    assert length.main(["--text", "汉" * 301]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert not payload["ok"] and payload["hanzi"] == 301
