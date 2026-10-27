"""使用隔离 Git 仓库核验真实提交身份，不调用模型、GitHub 或用户仓库。"""

import importlib.util
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/配置提交身份.py"
spec = importlib.util.spec_from_file_location("commit_identity", SCRIPT)
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def git(repository, *arguments, env=None):
    return subprocess.check_output(
        ["git", "-C", str(repository), *arguments], text=True, env=env
    ).strip()


def test_shared_worktree_and_inherited_identity_are_corrected(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "Wrong fixture")
    git(repository, "config", "user.email", "wrong@example.invalid")
    git(repository, "commit", "--allow-empty", "-m", "fixture")
    worktree = tmp_path / "worktree"
    git(repository, "worktree", "add", "-b", "issue", str(worktree))
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Inherited fixture")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "inherited@example.invalid")
    environment = identity.configure_identity(worktree)
    assert git(repository, "config", "--local", "user.email") == identity.AUTHOR_EMAIL
    assert git(repository, "config", "--local", "user.useConfigOnly") == "true"
    git(worktree, "commit", "--allow-empty", "-m", "Issue fixture", env=environment)
    actual = git(worktree, "show", "-s", "--format=%an%n%ae%n%cn%n%ce%n%B")
    assert actual.splitlines()[:4] == [
        identity.AUTHOR_NAME, identity.AUTHOR_EMAIL,
        identity.AUTHOR_NAME, identity.AUTHOR_EMAIL,
    ]
    assert "Co-authored-by:" not in actual
