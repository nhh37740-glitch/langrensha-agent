import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "review_cli", Path(__file__).resolve().parents[1] / ".github/scripts/请求PR审查.py"
)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def item(number=1, commit="current", body="Review completed", state="COMMENTED"):
    return {
        "id": number,
        "commit_id": commit,
        "body": body,
        "state": state,
        "user": {"login": review.COPILOT},
        "html_url": "https://github.com/example/review",
    }


def test_old_commit_and_dismissed_review_do_not_satisfy_current_head():
    assert (
        review.classify([item(commit="old"), item(state="DISMISSED")], "current", 0)[0] == "waiting"
    )
    assert review.classify([item()], "current", 0)[0] == "reviewed"


def test_quota_notification_is_not_review_and_old_failure_does_not_cover_new_request():
    unavailable = item(
        body=(
            "Copilot was unable to review this pull request "
            "because the user has insufficient remaining quota."
        )
    )
    assert review.classify([unavailable], "current", 0)[0] == "unavailable"
    assert review.classify([unavailable], "current", 1)[0] == "waiting"


def test_cli_failure_falls_back_to_reviewer_api_without_browser(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=1 if len(calls) == 1 else 0)

    monkeypatch.setattr(review, "run", run)
    assert review.request("owner/repo", 23) == "github_api"
    assert calls[0][0][-1] == "@copilot"
    assert calls[1][1]["payload"] == {"reviewers": [review.COPILOT]}


def test_head_changed_while_waiting_never_reports_reviewed(monkeypatch):
    calls = iter(
        [
            {"head": {"sha": "first"}, "state": "open", "draft": False},
            [],
            {"head": {"sha": "second"}, "state": "open"},
        ]
    )
    monkeypatch.setattr(review, "api", lambda *a, **k: next(calls))
    monkeypatch.setattr(review, "request", lambda *a: "github_api")
    assert review.inspect("owner/repo", 23, 10, 5)["status"] == "head_or_state_changed"


def test_cli_reads_all_review_pages(monkeypatch):
    monkeypatch.setattr(
        review,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout='[{"id":1}]\n[{"id":2}]'),
    )
    assert review.api("reviews", pages=True) == [{"id": 1}, {"id": 2}]
