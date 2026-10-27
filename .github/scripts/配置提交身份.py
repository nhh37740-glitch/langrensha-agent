"""为本仓库及共享 worktree 固定已核验的所有者提交身份，不访问 GitHub 或密钥。"""

import argparse
import os
import subprocess
from pathlib import Path

AUTHOR_NAME = "nhh37740-glitch"
AUTHOR_EMAIL = "242156787+nhh37740-glitch@users.noreply.github.com"


def configure_identity(repository: Path, environment=None):
    """持久写入共享 local config，并覆盖子进程继承的作者/提交者身份。"""
    environment = dict(os.environ if environment is None else environment)
    for key, value in (
        ("user.name", AUTHOR_NAME),
        ("user.email", AUTHOR_EMAIL),
        ("user.useConfigOnly", "true"),
    ):
        subprocess.run(
            ["git", "-C", str(repository), "config", "--local", key, value],
            check=True,
            capture_output=True,
            text=True,
        )
    for role in ("AUTHOR", "COMMITTER"):
        environment[f"GIT_{role}_NAME"] = AUTHOR_NAME
        environment[f"GIT_{role}_EMAIL"] = AUTHOR_EMAIL
    return environment


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    options = parser.parse_args()
    configure_identity(options.repo)
    print("已配置仓库所有者官方 noreply；未修改任何提交或远程引用。")
