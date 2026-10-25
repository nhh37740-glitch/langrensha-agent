"""Issue 声明、活动任务与分支的交叉核查。"""

import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / ".github/scripts/校验PR问题关联.py"
spec = importlib.util.spec_from_file_location("issue_link", path)
link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link)


def test_valid_unique_issue():
    pr = {"body": "Issue: #36\n\nCloses #36", "head": {"ref": "deepseek/issue-36"}}
    assert link.validate(pr, {"number": 36, "state": "open"}, [{"number": 36}]) == 36


@pytest.mark.parametrize("body", ["Closes #36", "Issue: #36\nIssue: #37", "Issue: #编号"])
def test_missing_or_multiple_declarations_fail(body):
    with pytest.raises(ValueError):
        link.declared_issue(body)


@pytest.mark.parametrize("change", ["active", "branch", "closing", "closed", "is_pr"])
def test_cross_checks_fail(change):
    pr = {"body": "Issue: #36\n\nCloses #36", "head": {"ref": "deepseek/issue-36"}}
    issue = {"number": 36, "state": "open"}
    active = [{"number": 36}]
    if change == "active":
        active = [{"number": 14}]
    elif change == "branch":
        pr["head"]["ref"] = "deepseek/issue-14"
    elif change == "closing":
        pr["body"] += "\nFixes #14"
    elif change == "closed":
        issue["state"] = "closed"
    else:
        issue["pull_request"] = {}
    with pytest.raises(ValueError):
        link.validate(pr, issue, active)
