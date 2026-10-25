"""无人值守的串行与审查边界，不访问网络或真实模型。"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "supervisor", ROOT / ".github/scripts/DeepSeek无人值守.py"
)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


def issue(number, *labels):
    return {"number": number, "labels": [{"name": label} for label in labels]}


def review(sha="head", author=supervisor.BOT, **kwargs):
    data = {
        "commit_sha": sha,
        "status": "completed",
        "has_any_findings": False,
        "has_unresolved_findings": False,
    } | kwargs
    return {
        "user": {"login": author},
        "body": "<!-- codex-review-state:v1 " + json.dumps({"code_review": data}) + " -->",
    }


def test_requires_explicit_queue_label():
    assert supervisor.choose([issue(14)], [])[0] is None
    assert supervisor.choose([issue(14), issue(40, "deepseek-ready")], [])[0]["number"] == 40


def test_active_issue_precedes_queue():
    assert (
        supervisor.choose([issue(5, "deepseek-ready"), issue(8, "deepseek-active")], [])[0][
            "number"
        ]
        == 8
    )


def test_blocked_active_issue_does_not_spend_or_advance():
    assert (
        supervisor.choose(
            [issue(8, "deepseek-active", "deepseek-blocked"), issue(9, "deepseek-ready")], []
        )[0]
        is None
    )


def test_open_pr_blocks_next_issue():
    assert supervisor.choose([issue(5, "deepseek-ready")], [{"number": 6}])[0] is None


def test_ambiguous_active_tasks_stop():
    assert (
        supervisor.choose([issue(5, "deepseek-active"), issue(6, "deepseek-active")], [])[0] is None
    )


def test_old_or_spoofed_review_cannot_pass():
    assert supervisor.codex_state([review(sha="old")], "head") == "等待 Codex 审查"
    assert supervisor.codex_state([review(author="someone")], "head") == "等待 Codex 审查"


def test_completed_clean_head_review_passes():
    assert supervisor.codex_state([review()], "head") == "Codex 当前提交无发现"


def test_findings_and_incomplete_reviews_cannot_pass():
    assert supervisor.codex_state([review(has_any_findings=True)], "head") == "Codex 发现待处理"
    assert supervisor.codex_state([review(status="in_progress")], "head") == "Codex 审查中"


def test_review_request_idempotent_per_commit(monkeypatch):
    calls = []
    monkeypatch.setattr(supervisor, "comment", lambda *args: calls.append(args))
    pr = {"number": 1, "head": {"sha": "head"}}
    supervisor.request_review(pr, [{"body": "<!-- deepseek-codex:head -->"}])
    assert not calls
    supervisor.request_review(pr, [{"body": "<!-- deepseek-codex:old -->"}])
    assert len(calls) == 1 and "@codex review" in calls[0][1]


def test_paginated_gh_output_works_with_older_cli(monkeypatch):
    monkeypatch.setattr(supervisor, "run", lambda *a: SimpleNamespace(stdout="[1]\n[2, 3]\n"))
    assert supervisor.items("issues") == [1, 2, 3]


def test_ci_requires_all_project_checks_and_no_failure():
    checks = [
        {"name": n, "status": "completed", "conclusion": "success"}
        for n in supervisor.REQUIRED_CHECKS
    ]
    statuses = {"statuses": [], "state": "pending"}
    assert supervisor.ci_passes(checks, statuses)
    assert not supervisor.ci_passes(checks[:-1], statuses)
    checks[0]["conclusion"] = "failure"
    assert not supervisor.ci_passes(checks, statuses)
