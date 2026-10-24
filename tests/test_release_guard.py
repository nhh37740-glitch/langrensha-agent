import copy
import hashlib
import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "release_guard", Path(__file__).resolve().parents[1] / ".github/scripts/发布前核对.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
TAG, COMMIT = "v0.4.0", "a" * 40


def checks():
    return [
        {
            "id": i,
            "name": name,
            "app": {"slug": "github-actions"},
            "status": "completed",
            "conclusion": "success",
        }
        for i, name in enumerate(sorted(guard.REQUIRED_CHECKS), 1)
    ]


@pytest.mark.parametrize("tag", ["main", "v0.4.0; echo token", "v01.4.0", "v0.4.0-rc1"])
def test_untrusted_tag_is_rejected(tag):
    with pytest.raises(guard.ReleaseRejected, match="invalid_release_tag"):
        guard.release_version(tag)


def test_latest_main_checks_must_all_be_successful():
    guard.verify_checks(checks())
    for invalid in [checks()[:-1], [{**c, "app": {"slug": "untrusted"}} for c in checks()]]:
        with pytest.raises(guard.ReleaseRejected):
            guard.verify_checks(invalid)
    failed = {**checks()[0], "id": 999, "conclusion": "failure"}
    with pytest.raises(guard.ReleaseRejected):
        guard.verify_checks([*checks(), failed])
    # 发布流水线自身尚在运行，不参与五项主线检查，避免自等待。
    guard.verify_checks(
        [
            *checks(),
            {
                "id": 1000,
                "name": "发布",
                "app": {"slug": "github-actions"},
                "status": "in_progress",
                "conclusion": None,
            },
        ]
    )


def test_only_matching_drafts_or_complete_sealed_release_are_reusable():
    release = {
        "id": 1,
        "tag_name": TAG,
        "body": guard.source_marker(COMMIT),
        "draft": True,
        "assets": [],
    }
    assert guard.release_plan(None, TAG, COMMIT) == "create_draft"
    assert guard.release_plan(release, TAG, COMMIT) == "resume_draft"
    with pytest.raises(guard.ReleaseRejected):
        guard.release_plan({**release, "body": "user-authored release"}, TAG, COMMIT)
    with pytest.raises(guard.ReleaseRejected):
        guard.release_plan({**release, "draft": False}, TAG, COMMIT)
    complete = {
        **release,
        "draft": False,
        "assets": [{"name": n} for n in guard.expected_assets(TAG)],
    }
    assert guard.release_plan(complete, TAG, COMMIT) == "sealed"


def test_tag_must_match_version_and_be_merged(tmp_path):
    def git(*args):
        return (
            subprocess.check_output(["git", *args], cwd=tmp_path, stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )

    git("init", "-b", "main")
    git("config", "user.email", "release-test@example.invalid")
    git("config", "user.name", "Release test")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.4.0"\n')
    git("add", ".")
    git("commit", "-m", "main snapshot")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    git("tag", TAG)
    assert guard.verify_main_tag(tmp_path, TAG) == git("rev-parse", "HEAD")
    git("tag", "v0.4.1")
    with pytest.raises(guard.ReleaseRejected, match="tag_version_mismatch"):
        guard.verify_main_tag(tmp_path, "v0.4.1")
    git("switch", "-c", "unmerged")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.5.0"\n')
    git("add", ".")
    git("commit", "-m", "unmerged snapshot")
    git("tag", "v0.5.0")
    with pytest.raises(guard.ReleaseRejected, match="tag_not_on_main"):
        guard.verify_main_tag(tmp_path, "v0.5.0")


def test_partial_draft_resumes_without_replacing_assets_and_checksums_remote_bytes(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "assets"
    folder.mkdir()
    (tmp_path / "临时/发布").mkdir(parents=True)
    payloads = guard.expected_assets(TAG) - {"SHA256SUMS"}
    for name in payloads:
        (folder / name).write_bytes(b"current build " + name.encode())
    first = sorted(payloads)[0]
    remote_bytes = {first: b"previous partial build, same source"}
    release = {
        "id": 7,
        "tag_name": TAG,
        "body": guard.source_marker(COMMIT),
        "draft": True,
        "assets": [],
    }
    commands = []

    def api(_path):
        release["assets"] = [
            {"name": name, "digest": "sha256:" + hashlib.sha256(data).hexdigest()}
            for name, data in remote_bytes.items()
        ]
        return copy.deepcopy(release)

    def run(args, **kwargs):
        commands.append(args)
        assert "--clobber" not in args
        if args[2] == "upload":
            path = Path(args[-1])
            assert path.name not in remote_bytes
            remote_bytes[path.name] = path.read_bytes()
        elif args[2] == "edit":
            release["draft"] = False
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(guard.subprocess, "run", run)
    guard.publish_files(TAG, COMMIT, folder, api, api("release"))
    assert not release["draft"]
    assert remote_bytes[first] == b"previous partial build, same source"
    assert set(remote_bytes) == guard.expected_assets(TAG)
    for line in remote_bytes["SHA256SUMS"].decode().splitlines():
        digest, name = line.split("  ", 1)
        assert digest == hashlib.sha256(remote_bytes[name]).hexdigest()
    assert commands[-1] == ["gh", "release", "edit", TAG, "--draft=false"]


def test_release_visibility_polling_waits_for_new_draft(monkeypatch):
    release = {
        "id": 9,
        "tag_name": TAG,
        "body": guard.source_marker(COMMIT),
        "draft": True,
        "assets": [],
    }
    state = {"lists": 0}

    def api(_path, *, missing=False):
        if missing:
            return None
        state["lists"] += 1
        return [release] if state["lists"] >= 3 else []

    monkeypatch.setattr(guard.time, "sleep", lambda _seconds: None)
    assert guard.find_visible_release(api, TAG) == release
    assert state["lists"] == 3


def test_publish_files_waits_for_draft_visibility_then_resumes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "assets"
    folder.mkdir()
    (tmp_path / "临时/发布").mkdir(parents=True)
    for name in guard.expected_assets(TAG) - {"SHA256SUMS"}:
        (folder / name).write_bytes(b"current build " + name.encode())
    release = {
        "id": 7,
        "tag_name": TAG,
        "body": guard.source_marker(COMMIT),
        "draft": True,
        "assets": [],
    }
    state = {"lists": 0}
    commands = []

    def api(path, *, missing=False):
        if missing:
            return None
        if path.startswith("releases?"):
            state["lists"] += 1
            return [release] if state["lists"] >= 3 else []
        return copy.deepcopy(release)

    def run(args, **kwargs):
        commands.append(args)
        if args[2] == "upload":
            path = Path(args[-1])
            release["assets"].append(
                {
                    "name": path.name,
                    "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        elif args[2] == "edit":
            release["draft"] = False
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(guard.subprocess, "run", run)
    monkeypatch.setattr(guard.time, "sleep", lambda _seconds: None)
    guard.publish_files(TAG, COMMIT, folder, api, None)
    assert not release["draft"]
    assert commands[-1] == ["gh", "release", "edit", TAG, "--draft=false"]
    assert {a["name"] for a in release["assets"]} == guard.expected_assets(TAG)

