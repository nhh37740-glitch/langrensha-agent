"""功能分支被 squash 合并并删除后，主线仍必须能获取固定版本的图源代码。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/获取版本图源码.py"
ARCHIVE = "refs/heads/evidence/archify-v0.1.0"


def git(cwd, *args):
    return subprocess.check_output(
        ["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL
    ).strip()


@pytest.fixture
def squashed_repo(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-b", "main")
    git(origin, "config", "user.name", "diagram-test")
    git(origin, "config", "user.email", "diagram-test@example.invalid")
    (origin / "file").write_text("initial")
    git(origin, "add", "file")
    git(origin, "commit", "-m", "initial")
    git(origin, "checkout", "-b", "feature")
    (origin / "file").write_text("implementation")
    git(origin, "commit", "-am", "implementation")
    source_sha = git(origin, "rev-parse", "HEAD")
    git(origin, "branch", "evidence/archify-v0.1.0")
    git(origin, "checkout", "main")
    git(origin, "merge", "--squash", "feature")
    git(origin, "commit", "-m", "squash")
    git(origin, "branch", "-D", "feature")
    checkout = tmp_path / "checkout"
    git(
        tmp_path, "clone", "--single-branch", "--no-local", "-b", "main", str(origin), str(checkout)
    )
    candidate = checkout / "图源.json"
    candidate.write_text(json.dumps({"meta": {"repository": {"revision": source_sha}}}))
    return checkout, candidate, source_sha


def test_fetch_after_squash_and_feature_branch_deletion(squashed_repo):
    checkout, candidate, source_sha = squashed_repo
    missing = subprocess.run(
        ["git", "cat-file", "-e", source_sha], cwd=checkout, capture_output=True, check=False
    )
    assert missing.returncode != 0
    subprocess.run(
        [sys.executable, str(SCRIPT), str(candidate), ARCHIVE],
        cwd=checkout,
        capture_output=True,
        check=True,
    )
    assert git(checkout, "cat-file", "-t", source_sha) == "commit"


def test_archive_ref_must_match_pinned_revision(squashed_repo):
    checkout, candidate, _ = squashed_repo
    candidate.write_text(
        json.dumps({"meta": {"repository": {"revision": git(checkout, "rev-parse", "HEAD")}}})
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(candidate), ARCHIVE],
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0


def test_non_archive_ref_is_rejected_before_fetch(squashed_repo):
    checkout, candidate, _ = squashed_repo
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(candidate), "refs/heads/main"],
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
