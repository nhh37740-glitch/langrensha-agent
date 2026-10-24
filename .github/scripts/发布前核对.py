"""只准从已合并且检查成功的版本标签发布；不读取应用密钥。"""

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
import tomllib
from pathlib import Path

REQUIRED_CHECKS = {
    "Python 内核检查",
    "文档阶段检查",
    "版本图检查",
    "容器构建与启动",
    "网页交互与完整发行包",
}


class ReleaseRejected(ValueError):
    pass


def release_version(tag):
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ReleaseRejected("invalid_release_tag")
    return tag[1:]


def verify_checks(checks):
    latest = {}
    for check in checks:
        if check.get("app", {}).get("slug") != "github-actions":
            continue
        name = check["name"]
        if name in REQUIRED_CHECKS and (name not in latest or check["id"] > latest[name]["id"]):
            latest[name] = check
    if set(latest) != REQUIRED_CHECKS or any(
        c["status"] != "completed" or c["conclusion"] != "success" for c in latest.values()
    ):
        raise ReleaseRejected("main_checks_not_successful")


def verify_main_tag(directory, tag):
    release_version(tag)
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
        cwd=directory,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ReleaseRejected("tag_not_found")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "origin/main"],
        cwd=directory,
        capture_output=True,
    ).returncode:
        raise ReleaseRejected("tag_not_on_main")
    content = subprocess.check_output(["git", "show", f"{commit}:pyproject.toml"], cwd=directory)
    if tomllib.loads(content.decode())["project"]["version"] != release_version(tag):
        raise ReleaseRejected("tag_version_mismatch")
    return commit


def expected_assets(tag):
    version = release_version(tag)
    return {
        f"langrensha_agent-{version}-py3-none-any.whl",
        f"langrensha_agent-{version}.tar.gz",
        "requirements-dev.lock",
        "env.example",
        "SHA256SUMS",
    }


def source_marker(commit):
    return f"<!-- langrensha-release-source: {commit} -->"


def release_plan(existing, tag, commit):
    if existing is None:
        return "create_draft"
    if existing.get("tag_name") != tag or source_marker(commit) not in (existing.get("body") or ""):
        raise ReleaseRejected("existing_release_not_managed")
    if existing["draft"]:
        return "resume_draft"
    names = {a["name"] for a in existing["assets"]}
    if not expected_assets(tag) <= names:
        raise ReleaseRejected("published_release_incomplete")
    return "sealed"


def find_visible_release(api, tag, attempts=10, delay=1.0):
    """刚创建的草稿可能短时间读不到；先轮询等待，再决定发布计划。"""
    for attempt in range(attempts):
        existing = api(f"releases/tags/{tag}", missing=True)
        if existing is None:
            existing = next(
                (r for r in api("releases?per_page=100") if r.get("tag_name") == tag), None
            )
        if existing is not None:
            return existing
        if attempt + 1 < attempts:
            time.sleep(delay)
    return None


def publish_files(tag, commit, folder, api, existing):
    """只增加缺少的附件，绝不删除或覆盖已有 Release 附件。"""
    if existing is None:
        existing = find_visible_release(api, tag)
    plan = release_plan(existing, tag, commit)
    if plan == "sealed":
        return
    if plan != "resume_draft":
        raise ReleaseRejected("draft_not_ready")
    payloads = expected_assets(tag) - {"SHA256SUMS"}
    if any(not (folder / name).is_file() for name in payloads):
        raise ReleaseRejected("local_assets_missing")

    def fresh_draft():
        release = api(f"releases/{existing['id']}")
        if release_plan(release, tag, commit) != "resume_draft":
            raise ReleaseRejected("release_no_longer_draft")
        return release

    def command(arguments):
        result = subprocess.run(arguments, capture_output=True, text=True)
        if result.returncode:
            raise ReleaseRejected("release_operation_failed")

    for name in sorted(payloads):
        current = fresh_draft()
        if name not in {a["name"] for a in current["assets"]}:
            command(["gh", "release", "upload", tag, str(folder / name)])
    for attempt in range(5):
        current = fresh_draft()
        records = {a["name"]: a for a in current["assets"]}
        if all(
            re.fullmatch(r"sha256:[0-9a-f]{64}", records[n].get("digest") or "") for n in payloads
        ):
            break
        if attempt < 4:
            time.sleep(1)
    lines = []
    for name in sorted(payloads):
        digest = records[name].get("digest") or ""
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ReleaseRejected("uploaded_asset_digest_missing")
        lines.append(digest.removeprefix("sha256:") + "  " + name)
    manifest = "\n".join(lines) + "\n"
    if "SHA256SUMS" in records:
        with tempfile.TemporaryDirectory(dir="临时/发布") as directory:
            command(
                ["gh", "release", "download", tag, "--pattern", "SHA256SUMS", "--dir", directory]
            )
            if (Path(directory) / "SHA256SUMS").read_text() != manifest:
                raise ReleaseRejected("existing_manifest_mismatch")
    else:
        (folder / "SHA256SUMS").write_text(manifest)
        command(["gh", "release", "upload", tag, str(folder / "SHA256SUMS")])
    final = fresh_draft()
    if not expected_assets(tag) <= {a["name"] for a in final["assets"]}:
        raise ReleaseRejected("draft_assets_incomplete")
    command(["gh", "release", "edit", tag, "--draft=false"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--publish-files", type=Path)
    args = parser.parse_args()
    try:
        release_version(args.tag)
        repository = os.environ["GITHUB_REPOSITORY"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ReleaseRejected("invalid_repository")
        commit = verify_main_tag(Path.cwd(), args.tag)

        def api(suffix, *, missing=False):
            response = subprocess.run(
                ["gh", "api", f"repos/{repository}/{suffix}"], text=True, capture_output=True
            )
            if response.returncode:
                if missing and "HTTP 404" in response.stderr:
                    return None
                raise ReleaseRejected("github_metadata_unavailable")
            return json.loads(response.stdout)

        checks = api(f"commits/{commit}/check-runs?per_page=100")["check_runs"]
        verify_checks(checks)
        existing = find_visible_release(api, args.tag)
        plan = release_plan(existing, args.tag, commit)
        directory = Path("临时/发布")
        directory.mkdir(parents=True, exist_ok=True)
        notes = directory / "发布说明.md"
        notes.write_text(
            f"{source_marker(commit)}\n\n"
            f"{args.tag} 的安装包由通过五项主线检查的提交自动构建。\n\n"
            "wheel 已包含网页与 Phaser，安装 `[ai,web]` 后使用 `langrensha-web`。"
            "将附件 `env.example` 复制为私密 `.env` 并配置自己的密钥，勿提交。\n\n"
            f"[运行与部署](https://github.com/{repository}/blob/{args.tag}/"
            "文档/开发/完整可玩版运行与部署.md) · "
            f"[版本说明](https://github.com/{repository}/blob/{args.tag}/文档/版本/{args.tag}/版本说明.md)\n\n"
            f"来源提交：`{commit}`。附件 SHA256SUMS 用于核对文件完整性。"
            "用户服务器的实际部署与上线验收另由 Issue #14 跟踪。\n",
            encoding="utf-8",
        )
        if args.publish_files:
            publish_files(args.tag, commit, args.publish_files, api, existing)
        output = {"tag": args.tag, "commit": commit, "plan": plan}
        if os.environ.get("GITHUB_OUTPUT"):
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
                stream.write(f"tag={args.tag}\ncommit={commit}\nplan={plan}\n")
        print(json.dumps({"ok": True, **output}, ensure_ascii=False))
        return 0
    except (ReleaseRejected, OSError, KeyError, ValueError) as exc:
        code = str(exc) if isinstance(exc, ReleaseRejected) else "release_validation_failed"
        print(json.dumps({"ok": False, "code": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
