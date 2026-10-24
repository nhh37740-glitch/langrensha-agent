"""通过 gh 优先请求 Copilot；只报告事实，降级审查由调用者明确启动。"""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

COPILOT = "copilot-pull-request-reviewer[bot]"


class MetadataUnavailable(Exception):
    pass


def run(arguments, *, payload=None):
    try:
        return subprocess.run(
            ["gh", *arguments],
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MetadataUnavailable from exc


def api(path, *, pages=False):
    response = run(["api", path, *(["--paginate"] if pages else [])])
    if response.returncode:
        raise MetadataUnavailable
    if not pages:
        return json.loads(response.stdout)
    # gh --paginate 可输出多个连续数组；不依赖新版 gh 的 --slurp。
    remaining, result = response.stdout.strip(), []
    while remaining:
        page, end = json.JSONDecoder().raw_decode(remaining)
        result.extend(page)
        remaining = remaining[end:].lstrip()
    return result


def classify(reviews, commit, baseline):
    current = [
        r
        for r in reviews
        if r["user"]["login"] == COPILOT
        and r.get("commit_id") == commit
        and r["state"] not in {"PENDING", "DISMISSED"}
    ]
    if not current:
        return "waiting", []
    latest = max(current, key=lambda r: r["id"])
    body = (latest.get("body") or "").lower()
    unavailable = any(
        phrase in body for phrase in ("unable to review", "could not review", "cannot review")
    )
    if unavailable:
        return ("unavailable" if latest["id"] > baseline else "waiting"), [latest]
    return "reviewed", [latest]


def request(repository, number):
    response = run(["pr", "edit", str(number), "--repo", repository, "--add-reviewer", "@copilot"])
    if response.returncode == 0:
        return "gh_pr_edit"
    response = run(
        [
            "api",
            "--method",
            "POST",
            f"repos/{repository}/pulls/{number}/requested_reviewers",
            "--input",
            "-",
        ],
        payload={"reviewers": [COPILOT]},
    )
    return "github_api" if response.returncode == 0 else None


def inspect(repository, number, wait, interval):
    base = f"repos/{repository}/pulls/{number}"
    initial = api(base)
    result = {"repository": repository, "pr": number, "commit": initial["head"]["sha"]}
    if initial["state"] != "open" or initial["draft"]:
        return {**result, "status": "not_reviewable"}
    before = api(base + "/reviews?per_page=100", pages=True)
    baseline = max((r["id"] for r in before), default=0)
    method = request(repository, number)
    if method is None:
        return {**result, "status": "request_failed"}
    result["request_method"] = method
    deadline = time.monotonic() + wait
    while True:
        current = api(base)
        if current["head"]["sha"] != result["commit"] or current["state"] != "open":
            return {**result, "status": "head_or_state_changed"}
        status, reviews = classify(
            api(base + "/reviews?per_page=100", pages=True), result["commit"], baseline
        )
        if status != "waiting":
            return {
                **result,
                "status": status,
                "reviews": [
                    {"id": r["id"], "url": r["html_url"], "state": r["state"]} for r in reviews
                ],
            }
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {**result, "status": "timed_out"}
        time.sleep(min(interval, remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr", type=int)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--wait-seconds", type=int, default=600)
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if (
        args.pr < 1
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo)
        or not 0 <= args.wait_seconds <= 1800
        or not 5 <= args.interval <= 60
    ):
        parser.error("PR、仓库名或轮询范围无效")
    try:
        result = inspect(args.repo, args.pr, args.wait_seconds, args.interval)
    except (MetadataUnavailable, ValueError, KeyError):
        result = {"repository": args.repo, "pr": args.pr, "status": "metadata_unavailable"}
    directory = Path("临时/PR审查")
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / f"PR-{args.pr}.json"
    report.touch(mode=0o600, exist_ok=True)
    report.chmod(0o600)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "reviewed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
